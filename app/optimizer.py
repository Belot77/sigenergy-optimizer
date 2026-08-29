"""
SigEnergy Optimizer — core decision engine.

This module is a faithful Python translation of the ~3400-line YAML blueprint
automation (sigenergy_optimiser.yaml).  Every decision variable from the
original Jinja2 template block is now a typed Python method or property.

Architecture:
  - SigEnergyOptimizer.run_forever()  — polling loop
  - SigEnergyOptimizer._read_state()  — bulk-read all HA entities
  - SigEnergyOptimizer._decide()      — pure decision logic, no side effects
  - SigEnergyOptimizer._apply()       — push decisions to HA via REST
"""
from __future__ import annotations

import asyncio
from collections import deque
from decimal import Decimal, ROUND_FLOOR
import logging
import math
import os
from datetime import datetime, time, timedelta, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import Settings
from .earnings import EarningsService
from .forecast_utils import (
    extract_forecast_entries,
    forecast_entity_candidates,
    forecast_entry_time,
    forecast_entry_value,
)
from .ha_client import HAClient
from .models import (
    Decision,
    HVACObservedValue,
    HVACSolarInputContext,
    HVACSolarPermissionResult,
    SolarState,
)
from .state_store import StateStore

logger = logging.getLogger(__name__)

# EMS mode string constants
MODE_MAX_SELF = "Maximum Self Consumption"
MODE_CMD_DISCHARGE_PV = "Command Discharging (PV First)"
MODE_CMD_DISCHARGE_ESS = "Command Discharging (ESS First)"
MODE_CMD_CHARGE_PV = "Command Charging (PV First)"
MODE_CMD_CHARGE_GRID = "Command Charging (Grid First)"

DISCHARGE_MODES = {MODE_CMD_DISCHARGE_PV, MODE_CMD_DISCHARGE_ESS}
CHARGE_MODES = {MODE_CMD_CHARGE_PV, MODE_CMD_CHARGE_GRID}

# Manual mode labels for the mode select entity
AUTOMATED_MODES = {"Automated"}

# Maximum time between full cycles even when WebSocket is quiet (safety net)
_HEARTBEAT_INTERVAL = 60  # seconds

# Minimum gap between back-to-back rapid triggers (debounce)
_DEBOUNCE_SECONDS = 3.0

# Remote EMS switch service-call protection. State is still checked every cycle,
# but unavailable targets are never called and valid-off retries are bounded.
_HA_CONTROL_ENABLE_RETRY_SECONDS = 60.0
_HA_CONTROL_WARNING_INTERVAL_SECONDS = 300.0

# Config attribute names whose entity IDs should trigger immediate cycles
_TRIGGER_ENTITY_ATTRS = [
    "pv_power_sensor",
    "consumed_power_sensor",
    "battery_power_sensor",
    "grid_import_power_sensor",
    "grid_export_power_sensor",
    "solar_power_now_sensor",
    "sun_entity",
    "ems_mode_select",
    "grid_export_limit",
    "battery_soc_sensor",
    "price_sensor",
    "feedin_sensor",
    "demand_window_sensor",
    "price_spike_sensor",
    "sigenergy_mode_select",
]

_POWER_LIMIT_MAX_KW = 100.0
_RUNTIME_SIGNATURE = "2.3.41-haos52"


class _DesiredExportLimit(float):
    """Numeric export limit carrying the exact policy branch that produced it."""

    source: str

    def __new__(cls, value: float, source: str) -> "_DesiredExportLimit":
        result = float.__new__(cls, value)
        result.source = source
        return result


class SigEnergyOptimizer:
    def __init__(self, ha: HAClient, cfg: Settings) -> None:
        self.ha = ha
        self.cfg = cfg
        self._last_state: Optional[SolarState] = None
        self._last_decision: Optional[Decision] = None
        self._last_daily_summary_date: Optional[datetime] = None
        self._last_morning_summary_date: Optional[datetime] = None
        self._running = False
        self._ws_connected = False
        self._prev_demand_window: bool = False
        self._config_time_warnings: list[str] = self._validate_time_config()
        self._sensor_parse_warning_cache: dict[tuple[str, str], float] = {}
        self._forecast_parse_warning_cache: dict[tuple[str, str, str, str, str], float] = {}
        self._last_ha_control_enable_attempt_at: Optional[float] = None
        self._last_ha_control_switch_warning_at: Optional[float] = None
        self._last_ha_control_switch_warning_key: Optional[tuple[str, str]] = None
        self._holdoff_entry_floor: Optional[float] = None  # Stable SoC floor for holdoff window
        self._last_hw_charge_cap_kw: Optional[float] = None
        self._last_hw_discharge_cap_kw: Optional[float] = None
        self._last_cycle_started: Optional[datetime] = None
        self._last_cycle_completed: Optional[datetime] = None
        self._last_cycle_error: str = ""
        self._last_published_hvac_solar_permission_result: Optional[
            HVACSolarPermissionResult
        ] = None
        self._notif_export_active: Optional[bool] = None
        self._last_export_start_notice_at: Optional[datetime] = None
        self._battery_full_alert_armed: bool = True
        self._battery_empty_alert_armed: bool = True
        self._last_battery_full_notice_at: Optional[datetime] = None
        self._last_battery_empty_notice_at: Optional[datetime] = None
        self._manual_mode_override: Optional[str] = None
        self._manual_ess_charge_override_kw: Optional[float] = None
        self._manual_ess_discharge_override_kw: Optional[float] = None
        self._morning_slow_charge_runtime_disabled: bool = False
        self._morning_slow_disable_logged: bool = False
        logger.warning(
            "Runtime signature=%s morning_slow_charge_runtime_disabled=%s",
            _RUNTIME_SIGNATURE,
            self._morning_slow_charge_runtime_disabled,
        )
        tz_name = os.environ.get("TZ", "Australia/Adelaide")
        try:
            self._tz = ZoneInfo(tz_name)
        except ZoneInfoNotFoundError:
            logger.warning("Timezone '%s' not found; falling back to UTC", tz_name)
            self._tz = timezone.utc
        self._last_tracked_block: Optional[int] = None
        self._last_tracked_import_kw: float = -999.0
        self._last_tracked_export_kw: float = -999.0
        self._last_tracked_import_price: Optional[float] = None
        self._last_tracked_feedin_price: Optional[float] = None
        self._last_optimizer_import_daily_kwh: Optional[float] = None
        self._last_optimizer_import_track_at: Optional[datetime] = None
        db_path = os.environ.get("STATE_DB_PATH", "/data/optimizer_state.db")
        self._state_store = StateStore(db_path)
        self._earnings = EarningsService(self.ha, self.cfg, self._state_store, self._tz)
        self._decision_trace: deque[dict[str, Any]] = deque(maxlen=1000)
        # Serialize cycle apply and manual mode writes to avoid race-driven reverts.
        self._control_lock = asyncio.Lock()

        # Shared queue — HAWebSocketClient puts entity_ids here; we consume them
        self.trigger_queue: asyncio.Queue = asyncio.Queue(maxsize=64)
        self._watch_entities: set[str] = set()

    # ------------------------------------------------------------------
    # Public accessors for the web UI
    # ------------------------------------------------------------------

    @property
    def last_state(self) -> Optional[SolarState]:
        return self._last_state

    @property
    def last_decision(self) -> Optional[Decision]:
        return self._last_decision

    @property
    def ws_connected(self) -> bool:
        return self._ws_connected

    @property
    def last_cycle_started(self) -> Optional[datetime]:
        return self._last_cycle_started

    @property
    def last_cycle_completed(self) -> Optional[datetime]:
        return self._last_cycle_completed

    @property
    def last_cycle_error(self) -> str:
        return self._last_cycle_error

    @property
    def config_time_warnings(self) -> list[str]:
        return self._config_time_warnings

    @property
    def runtime_signature(self) -> str:
        return _RUNTIME_SIGNATURE

    def refresh_config_time_warnings(self) -> None:
        self._config_time_warnings = self._validate_time_config()

    @staticmethod
    def _valid_hw_cap_kw(v: Any) -> bool:
        return isinstance(v, (int, float)) and 0 < float(v) < 999

    def get_power_caps_kw(self, s: Optional[SolarState] = None) -> tuple[float, float]:
        fallback = float(self.cfg.ess_limit_fallback_kw)
        if not (0 < fallback <= _POWER_LIMIT_MAX_KW):
            fallback = min(max(fallback, 1.0), _POWER_LIMIT_MAX_KW)

        state = s if s is not None else self._last_state

        charge_cap = fallback
        discharge_cap = fallback

        configured_charge_baseline = max(0.1, float(self.cfg.ess_charge_limit_value))
        configured_discharge_baseline = max(0.1, float(self.cfg.ess_discharge_limit_value))

        # Prefer number-entity max attributes as authoritative hardware/UI bounds.
        # Some dynamic sensors can temporarily report throttled operating limits
        # (e.g. 3kW during special modes), which must not become global cap sources.
        if state and self._valid_hw_cap_kw(state.ess_charge_limit_entity_max_kw):
            charge_cap = float(state.ess_charge_limit_entity_max_kw)
        elif state and self._valid_hw_cap_kw(state.ess_max_charge_kw):
            charge_cap = float(state.ess_max_charge_kw)
        elif self._valid_hw_cap_kw(self._last_hw_charge_cap_kw):
            charge_cap = float(self._last_hw_charge_cap_kw)

        if state and self._valid_hw_cap_kw(state.ess_discharge_limit_entity_max_kw):
            discharge_cap = float(state.ess_discharge_limit_entity_max_kw)
        elif state and self._valid_hw_cap_kw(state.ess_max_discharge_kw):
            discharge_cap = float(state.ess_max_discharge_kw)
        elif self._valid_hw_cap_kw(self._last_hw_discharge_cap_kw):
            discharge_cap = float(self._last_hw_discharge_cap_kw)

        charge_cap = max(charge_cap, configured_charge_baseline)
        discharge_cap = max(discharge_cap, configured_discharge_baseline)
        return charge_cap, discharge_cap

    def _validate_time_config(self) -> list[str]:
        warnings: list[str] = []
        for field in (
            "daily_summary_time",
            "morning_summary_time",
            "standby_holdoff_end_time",
            "morning_slow_charge_until",
        ):
            value = getattr(self.cfg, field, "")
            if not self._is_valid_time(value):
                warnings.append(f"{field}={value!r} is invalid (expected HH:MM or HH:MM:SS)")
        if warnings:
            for msg in warnings:
                logger.warning("Config time validation: %s", msg)
        return warnings

    @staticmethod
    def _is_valid_time(value: str) -> bool:
        try:
            parts = str(value).split(":")
            if len(parts) not in (2, 3):
                return False
            h, m = int(parts[0]), int(parts[1])
            s = int(parts[2]) if len(parts) == 3 else 0
            return 0 <= h <= 23 and 0 <= m <= 59 and 0 <= s <= 59
        except (ValueError, TypeError):
            return False

    def _warn_parse_issue(self, entity_id: str, raw_value: str, label: str) -> None:
        now_ts = datetime.now().timestamp()
        cache_key = (entity_id, raw_value)
        last_ts = self._sensor_parse_warning_cache.get(cache_key)
        # Rate-limit repeated malformed payload logs to keep signal useful.
        if last_ts is not None and now_ts - last_ts < 300:
            return

        # Prune stale entries and cap memory growth for long-lived processes.
        cutoff = now_ts - 1800  # keep last 30 minutes
        if len(self._sensor_parse_warning_cache) > 512:
            self._sensor_parse_warning_cache = {
                k: ts for k, ts in self._sensor_parse_warning_cache.items() if ts >= cutoff
            }

        if len(self._sensor_parse_warning_cache) > 512:
            newest = sorted(
                self._sensor_parse_warning_cache.items(),
                key=lambda item: item[1],
                reverse=True,
            )[:512]
            self._sensor_parse_warning_cache = dict(newest)

        self._sensor_parse_warning_cache[cache_key] = now_ts

        if len(self._sensor_parse_warning_cache) > 512:
            newest = sorted(
                self._sensor_parse_warning_cache.items(),
                key=lambda item: item[1],
                reverse=True,
            )[:512]
            self._sensor_parse_warning_cache = dict(newest)

        logger.warning("%s sensor %s returned non-numeric state %r; using safe defaults", label, entity_id, raw_value)

    def _warn_forecast_issue(self, label: str, diagnostics: dict[str, Any]) -> None:
        if not diagnostics or diagnostics.get("selected_entity"):
            return

        entities = [str(v) for v in diagnostics.get("entities_tried", []) if v]
        attributes = [str(v) for v in diagnostics.get("attributes_tried", []) if v]
        time_keys = [str(v) for v in diagnostics.get("time_keys_tried", []) if v]
        value_keys = [str(v) for v in diagnostics.get("value_keys_tried", []) if v]
        cache_key = (
            label,
            "|".join(entities),
            "|".join(attributes),
            "|".join(time_keys),
            "|".join(value_keys),
        )
        now_ts = datetime.now().timestamp()
        last_ts = self._forecast_parse_warning_cache.get(cache_key)
        if last_ts is not None and now_ts - last_ts < 900:
            return

        cutoff = now_ts - 3600
        if len(self._forecast_parse_warning_cache) > 128:
            self._forecast_parse_warning_cache = {
                k: ts for k, ts in self._forecast_parse_warning_cache.items() if ts >= cutoff
            }
        self._forecast_parse_warning_cache[cache_key] = now_ts

        logger.warning(
            "%s parsing failed; entities tried=%s; attributes tried=%s; time keys tried=%s; "
            "value keys tried=%s; missing entities=%s; unavailable entities=%s; reason=%s",
            label,
            entities,
            attributes,
            time_keys,
            value_keys,
            diagnostics.get("missing_entities", []),
            diagnostics.get("unavailable_entities", []),
            diagnostics.get("failure_reason", "no compatible forecast entries found"),
        )

    def get_watch_entities(self) -> set[str]:
        """Return the set of entity IDs the WS client should subscribe to."""
        if not self._watch_entities:
            self._watch_entities = {
                getattr(self.cfg, attr)
                for attr in _TRIGGER_ENTITY_ATTRS
                if getattr(self.cfg, attr, "")
            }
        return self._watch_entities

    def on_ws_connect(self) -> None:
        self._ws_connected = True
        logger.info("WebSocket connected — event-driven mode active")

    def on_ws_disconnect(self) -> None:
        self._ws_connected = False
        logger.warning("WebSocket disconnected — heartbeat fallback active")

    # ------------------------------------------------------------------
    # Background loop (event-driven + heartbeat fallback)
    # ------------------------------------------------------------------

    async def run_forever(self) -> None:
        """
        Event-driven main loop.

        Waits on trigger_queue for entity_ids pushed by HAWebSocketClient.
        Rapid bursts are debounced so we don't thrash when a sensor updates
        every second. A heartbeat fires every _HEARTBEAT_INTERVAL seconds
        regardless, so we always converge even if WS events are missed.

        Falls back gracefully to pure heartbeat polling when the WebSocket
        is disconnected — no separate code path needed.
        """
        self._running = True
        last_tick_ts = 0.0
        last_heartbeat_ts = 0.0

        logger.info(
            "Optimizer event loop started (debounce=%.0fs, heartbeat=%ds)",
            _DEBOUNCE_SECONDS, _HEARTBEAT_INTERVAL,
        )

        # One immediate startup tick
        try:
            await self._tick()
            last_tick_ts = datetime.now().timestamp()
            last_heartbeat_ts = last_tick_ts
        except Exception as exc:
            logger.exception("Startup tick failed: %s", exc)

        while self._running:
            now = datetime.now().timestamp()
            time_since_heartbeat = now - last_heartbeat_ts
            wait_max = max(0.01, _HEARTBEAT_INTERVAL - time_since_heartbeat)

            try:
                entity_id = await asyncio.wait_for(
                    self.trigger_queue.get(),
                    timeout=wait_max,
                )
                self.trigger_queue.task_done()

                # Minute tick from WS time_changed event
                if entity_id == "__time_changed__":
                    if datetime.now().timestamp() - last_tick_ts >= _HEARTBEAT_INTERVAL - 1:
                        logger.debug("Heartbeat tick (WS time_changed)")
                        await self._safe_tick()
                        last_tick_ts = last_heartbeat_ts = datetime.now().timestamp()
                    continue

                # Real entity state change — drain burst then run
                logger.debug("Event-driven tick triggered by: %s", entity_id)
                await self._drain_queue(_DEBOUNCE_SECONDS)
                await self._safe_tick()
                last_tick_ts = last_heartbeat_ts = datetime.now().timestamp()

            except asyncio.TimeoutError:
                # No WS events — heartbeat tick
                logger.debug("Heartbeat tick (timeout, ws=%s)", self._ws_connected)
                await self._safe_tick()
                last_tick_ts = last_heartbeat_ts = datetime.now().timestamp()

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception("Event loop error: %s", exc)
                await asyncio.sleep(5)

    async def _drain_queue(self, window: float) -> None:
        """Consume all queued items within `window` seconds to collapse a burst into one tick."""
        deadline = asyncio.get_event_loop().time() + window
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                break
            try:
                item = await asyncio.wait_for(self.trigger_queue.get(), timeout=remaining)
                self.trigger_queue.task_done()
            except asyncio.TimeoutError:
                break

    async def _safe_tick(self) -> None:
        self._last_cycle_started = datetime.now(timezone.utc)
        try:
            await self._tick()
            self._last_cycle_error = ""
            self._last_cycle_completed = datetime.now(timezone.utc)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._last_cycle_error = str(exc)
            self._last_cycle_completed = datetime.now(timezone.utc)
            logger.exception("Optimizer tick failed: %s", exc)

    async def run_once(self) -> Decision:
        """Run a single optimisation cycle and return the decision (for manual trigger)."""
        await self._tick()
        return self._last_decision

    async def _tick(self) -> None:
        async with self._control_lock:
            try:
                prev_decision = self._last_decision
                prev_state = self._last_state
                state = await self._read_state()
                self._last_state = state
                decision = self._decide(state)
                effective_mode = self._manual_mode_override or state.sigenergy_mode
                if effective_mode not in {self.cfg.automated_option, ""}:
                    self._freeze_decision_to_live_mode(state, decision, effective_mode)
                self._last_decision = decision
                await self._apply(state, decision)
                permission = self._evaluate_hvac_solar_permission(
                    state,
                    decision,
                    effective_mode=effective_mode,
                    previous_result=self._last_published_hvac_solar_permission_result,
                )
                await self._publish_hvac_solar_permission(permission)
                self._record_automation_audit(state, decision, prev_decision)
                self._record_decision_trace(state, decision)
                await self._handle_notifications(state, decision, prev_decision, prev_state)
                await self._handle_daily_summaries(state, decision)
                self._accumulate_history(state, decision)
                self._record_price_tracking(state, decision)
            except asyncio.CancelledError:
                raise
            except Exception:
                await self._publish_hvac_solar_permission(
                    self._hvac_solar_cycle_error_result()
                )
                raise

    def _evaluate_hvac_solar_permission(
        self,
        s: SolarState,
        d: Decision,
        *,
        effective_mode: str,
        previous_result: Optional[HVACSolarPermissionResult],
        evaluated_at: Optional[datetime] = None,
    ) -> HVACSolarPermissionResult:
        """Evaluate authoritative HVAC permission with no inverter-control effect."""
        cfg = self.cfg
        inputs = s.hvac_solar_inputs
        evaluated_at = evaluated_at or datetime.now(timezone.utc)
        if evaluated_at.tzinfo is None:
            evaluated_at = evaluated_at.replace(tzinfo=timezone.utc)
        else:
            evaluated_at = evaluated_at.astimezone(timezone.utc)
        expires_at = evaluated_at + timedelta(
            seconds=cfg.hvac_solar_data_max_age_seconds
        )
        previous = previous_result.state if previous_result is not None else "none"
        previous_expires_at = (
            previous_result.expires_at if previous_result is not None else None
        )
        if previous_expires_at is not None and previous_expires_at.tzinfo is None:
            previous_expires_at = previous_expires_at.replace(tzinfo=timezone.utc)
        previous_allows_continue = bool(
            previous in {"start", "continue"}
            and previous_expires_at is not None
            and previous_expires_at.astimezone(timezone.utc) > evaluated_at
        )
        normal_export_cap = max(0.0, float(cfg.export_limit_high))
        export_constraint_active = bool(
            normal_export_cap > 0.0
            and float(d.export_limit) < normal_export_cap - 0.011
        )
        observed_export_limit = (
            float(inputs.observed_export_limit.value)
            if inputs.observed_export_limit.available
            and inputs.observed_export_limit.fresh
            else None
        )

        control_mode = "unavailable"
        observed_ems_mode: Optional[str] = None
        measured_opportunity: Optional[float] = None
        estimated_opportunity: Optional[float] = None
        hidden_opportunity: Optional[float] = None
        battery_discharge: Optional[float] = None
        battery_flow_source = "unavailable"

        def _result(
            state: str,
            reason_code: str,
            *,
            source: str = "none",
            data_fresh: bool,
        ) -> HVACSolarPermissionResult:
            return HVACSolarPermissionResult(
                state=state,
                reason_code=reason_code,
                source=source,
                export_constraint_active=export_constraint_active,
                control_mode=control_mode,
                data_fresh=data_fresh,
                measured_opportunity_kw=measured_opportunity,
                estimated_opportunity_kw=estimated_opportunity,
                hidden_opportunity_kw=hidden_opportunity,
                start_threshold_kw=cfg.hvac_solar_start_kw,
                continue_threshold_kw=cfg.hvac_solar_continue_kw,
                battery_discharge_kw=battery_discharge,
                battery_flow_source=battery_flow_source,
                observed_ems_mode=observed_ems_mode,
                desired_ems_mode=str(d.ems_mode) if d.ems_mode else None,
                previous_permission=previous,
                desired_export_limit_kw=float(d.export_limit),
                observed_export_limit_kw=observed_export_limit,
                evaluated_at=evaluated_at,
                expires_at=expires_at,
            )

        configured_modes = {
            cfg.automated_option,
            cfg.full_export_option,
            cfg.full_import_option,
            cfg.full_import_pv_option,
            cfg.block_flow_option,
            cfg.manual_option,
        }
        if self._manual_mode_override:
            control_mode = str(self._manual_mode_override)
        else:
            if not inputs.control_mode.available:
                return _result(
                    "unavailable",
                    "control_mode_unavailable",
                    data_fresh=False,
                )
            if not inputs.control_mode.fresh:
                return _result(
                    "unavailable",
                    "required_data_stale",
                    data_fresh=False,
                )
            control_mode = str(inputs.control_mode.value)
        if control_mode not in configured_modes:
            return _result(
                "unavailable",
                "control_mode_unavailable",
                data_fresh=False,
            )
        if control_mode != cfg.automated_option or effective_mode != cfg.automated_option:
            return _result(
                "blocked",
                "control_mode_not_automated",
                data_fresh=True,
            )

        if not inputs.observed_ems_mode.available:
            return _result(
                "unavailable",
                "ems_mode_unavailable",
                data_fresh=False,
            )
        if not inputs.observed_ems_mode.fresh:
            return _result(
                "unavailable",
                "required_data_stale",
                data_fresh=False,
            )
        observed_ems_mode = str(inputs.observed_ems_mode.value)
        known_ems_modes = {MODE_MAX_SELF, *DISCHARGE_MODES, *CHARGE_MODES}
        if observed_ems_mode not in known_ems_modes:
            return _result(
                "unavailable",
                "ems_mode_unavailable",
                data_fresh=False,
            )
        if observed_ems_mode in DISCHARGE_MODES:
            return _result("blocked", "ems_discharging", data_fresh=True)
        if observed_ems_mode != MODE_MAX_SELF:
            return _result("blocked", "ems_mode_not_solar_safe", data_fresh=True)
        if d.ems_mode in DISCHARGE_MODES:
            return _result("blocked", "ems_discharge_requested", data_fresh=True)
        if d.ems_mode != MODE_MAX_SELF:
            return _result("blocked", "ems_mode_not_solar_safe", data_fresh=True)

        required_power = (inputs.pv_power, inputs.load_power)
        if any(not reading.available for reading in required_power):
            return _result(
                "unavailable",
                "required_data_unavailable",
                data_fresh=False,
            )
        if any(not reading.fresh for reading in required_power):
            return _result(
                "unavailable",
                "required_data_stale",
                data_fresh=False,
            )
        pv_kw = float(inputs.pv_power.value)
        load_kw = float(inputs.load_power.value)
        measured_opportunity = max(pv_kw - load_kw, 0.0)

        if inputs.battery_power.available and inputs.battery_power.fresh:
            battery_discharge = max(0.0, -float(inputs.battery_power.value))
            battery_flow_source = "direct_battery_sensor"
        elif (
            inputs.grid_import_power.available
            and inputs.grid_import_power.fresh
            and inputs.grid_export_power.available
            and inputs.grid_export_power.fresh
        ):
            measured_import = max(float(inputs.grid_import_power.value), 0.0)
            measured_export = max(float(inputs.grid_export_power.value), 0.0)
            battery_power_kw = pv_kw + measured_import - measured_export - load_kw
            battery_discharge = max(0.0, -battery_power_kw)
            battery_flow_source = "measured_grid_flow"
        else:
            battery_candidates = (
                inputs.battery_power,
                inputs.grid_import_power,
                inputs.grid_export_power,
            )
            reason = (
                "required_data_stale"
                if any(reading.available and not reading.fresh for reading in battery_candidates)
                else "battery_flow_unavailable"
            )
            return _result("unavailable", reason, data_fresh=False)

        if battery_discharge > cfg.hvac_solar_battery_discharge_tolerance_kw:
            return _result("blocked", "battery_discharging", data_fresh=True)

        estimated_inputs = (inputs.solar_power_now, inputs.sun_above_horizon)
        estimated_inputs_available = all(
            reading.available for reading in estimated_inputs
        )
        estimated_inputs_fresh = all(reading.fresh for reading in estimated_inputs)
        if estimated_inputs_available and estimated_inputs_fresh:
            estimated_opportunity = max(
                max(pv_kw, float(inputs.solar_power_now.value)) - load_kw,
                0.0,
            )
            hidden_opportunity = max(
                estimated_opportunity - measured_opportunity,
                0.0,
            )

        if measured_opportunity >= cfg.hvac_solar_start_kw:
            return _result(
                "start",
                "measured_opportunity_start",
                source="measured",
                data_fresh=True,
            )
        if (
            previous_allows_continue
            and measured_opportunity >= cfg.hvac_solar_continue_kw
        ):
            return _result(
                "continue",
                "measured_opportunity_continue",
                source="measured",
                data_fresh=True,
            )
        return _result(
            "blocked",
            "insufficient_measured_surplus",
            data_fresh=True,
        )

    def _hvac_solar_cycle_error_result(self) -> HVACSolarPermissionResult:
        evaluated_at = datetime.now(timezone.utc)
        return HVACSolarPermissionResult(
            state="unavailable",
            reason_code="optimizer_cycle_error",
            source="none",
            export_constraint_active=False,
            control_mode="unavailable",
            data_fresh=False,
            measured_opportunity_kw=None,
            estimated_opportunity_kw=None,
            hidden_opportunity_kw=None,
            start_threshold_kw=self.cfg.hvac_solar_start_kw,
            continue_threshold_kw=self.cfg.hvac_solar_continue_kw,
            battery_discharge_kw=None,
            battery_flow_source="unavailable",
            observed_ems_mode=None,
            desired_ems_mode=None,
            previous_permission=str(
                self._last_published_hvac_solar_permission_result.state
                if self._last_published_hvac_solar_permission_result is not None
                else "none"
            ),
            desired_export_limit_kw=None,
            observed_export_limit_kw=None,
            evaluated_at=evaluated_at,
            expires_at=evaluated_at
            + timedelta(seconds=self.cfg.hvac_solar_data_max_age_seconds),
        )

    async def _publish_hvac_solar_permission(
        self,
        result: HVACSolarPermissionResult,
    ) -> bool:
        entity_id = self.cfg.hvac_solar_permission_entity
        try:
            published = await self.ha.set_state(
                entity_id,
                result.state,
                result.attributes(),
            )
        except Exception as exc:
            logger.warning("HVAC solar permission publication failed for %s: %s", entity_id, exc)
            return False
        if not published:
            logger.warning("HVAC solar permission publication failed for %s", entity_id)
            return False
        self._last_published_hvac_solar_permission_result = result
        return True

    def _record_price_tracking(self, s: SolarState, d: Decision | None = None) -> None:
        now = datetime.now(self._tz)
        if d is not None:
            self._record_optimizer_import_topup(s, d, now)
        now_block = int(now.timestamp()) // 300
        import_kw = max(0.0, float(s.grid_import_power_kw or 0.0))
        export_kw = max(0.0, float(s.grid_export_power_kw or 0.0))
        import_price = s.current_price if s.current_price is not None else None
        feedin_price = s.feedin_price if s.feedin_price is not None else None
        should_record = False
        if self._last_tracked_block is None or now_block != self._last_tracked_block:
            should_record = True
        if abs(import_kw - self._last_tracked_import_kw) >= 0.25:
            should_record = True
        if abs(export_kw - self._last_tracked_export_kw) >= 0.25:
            should_record = True
        if import_price is not None and import_price != self._last_tracked_import_price:
            should_record = True
        if feedin_price is not None and feedin_price != self._last_tracked_feedin_price:
            should_record = True
        if not should_record:
            return
        block_start = datetime.fromtimestamp(now_block * 300, tz=self._tz).replace(second=0, microsecond=0)
        self._state_store.record_price_event(
            ts=now.isoformat(timespec="seconds"),
            block_ts=block_start.isoformat(timespec="seconds"),
            grid_import_kw=import_kw,
            grid_export_kw=export_kw,
            import_price=import_price,
            feedin_price=feedin_price,
            battery_soc=float(s.battery_soc),
        )
        self._last_tracked_block = now_block
        self._last_tracked_import_kw = import_kw
        self._last_tracked_export_kw = export_kw
        self._last_tracked_import_price = import_price
        self._last_tracked_feedin_price = feedin_price
        if now.hour == 0 and now.minute < 10:
            self._state_store.purge_old_price_tracking(retain_days=60)

    def _record_optimizer_import_topup(self, s: SolarState, d: Decision, now: datetime) -> None:
        near_zero = 0.011
        current_daily_import_kwh = max(0.0, float(s.daily_import_kwh or 0.0))
        import_active = d.import_limit > near_zero

        if not import_active:
            self._last_optimizer_import_daily_kwh = current_daily_import_kwh
            self._last_optimizer_import_track_at = now
            return

        previous_daily_import_kwh = self._last_optimizer_import_daily_kwh
        previous_track_at = self._last_optimizer_import_track_at
        import_kwh = 0.0

        if previous_daily_import_kwh is not None:
            import_kwh = max(0.0, current_daily_import_kwh - previous_daily_import_kwh)
        if import_kwh <= 0.0 and previous_track_at is not None and s.grid_import_power_kw is not None:
            elapsed_h = max(0.0, min((now - previous_track_at).total_seconds(), 300.0)) / 3600.0
            import_kwh = max(0.0, float(s.grid_import_power_kw or 0.0)) * elapsed_h

        self._last_optimizer_import_daily_kwh = current_daily_import_kwh
        self._last_optimizer_import_track_at = now

        price_trusted = bool(s.price_is_actual and s.current_price is not None)
        import_price = float(s.current_price) if price_trusted else None
        self._state_store.record_optimizer_import_topup(
            date=now.date().isoformat(),
            ts=now.isoformat(timespec="seconds"),
            import_kwh=import_kwh,
            import_price=import_price,
            price_trusted=price_trusted,
        )

    def price_tracking_events(self, date: str | None = None, limit: int = 2000) -> list[dict[str, Any]]:
        return self._state_store.get_price_events(date=date, limit=limit)

    async def daily_earnings_summary(self, date: str | None = None) -> dict[str, Any]:
        target_date = date or datetime.now(self._tz).date().isoformat()
        return await self._earnings.daily_summary(target_date)

    async def earnings_history(self, days: int = 7) -> dict[str, Any]:
        return await self._earnings.history(days)

    def audit_events(self, limit: int = 200) -> list[dict[str, Any]]:
        return self._state_store.get_audit_events(limit=limit)

    def record_audit_event(
        self,
        *,
        action: str,
        source: str,
        actor: str,
        result: str,
        target_key: str | None = None,
        old_value: Any = None,
        new_value: Any = None,
        details: Any = None,
    ) -> None:
        self._state_store.record_audit_event(
            action=action,
            source=source,
            actor=actor,
            result=result,
            target_key=target_key,
            old_value=old_value,
            new_value=new_value,
            details=details,
        )

    def list_threshold_presets(self) -> list[dict[str, Any]]:
        return self._state_store.list_threshold_presets()

    def get_threshold_preset(self, name: str) -> dict[str, Any] | None:
        return self._state_store.get_threshold_preset(name)

    def save_threshold_preset(self, name: str, payload: dict[str, Any]) -> None:
        self._state_store.save_threshold_preset(name, payload)

    def delete_threshold_preset(self, name: str) -> bool:
        return self._state_store.delete_threshold_preset(name)

    def decision_trace(self, limit: int = 200) -> list[dict[str, Any]]:
        n = max(1, min(int(limit), 2000))
        return list(self._decision_trace)[:n]

    def _record_decision_trace(self, s: SolarState, d: Decision) -> None:
        gates = d.trace_gates if isinstance(d.trace_gates, dict) else {}
        values = d.trace_values if isinstance(d.trace_values, dict) else {}
        self._decision_trace.appendleft(
            {
                "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "summary": {
                    "ems_mode": d.ems_mode,
                    "export_limit_kw": d.export_limit,
                    "import_limit_kw": d.import_limit,
                    "pv_max_power_limit_kw": d.pv_max_power_limit,
                    "ess_charge_limit_kw": d.ess_charge_limit,
                    "ess_discharge_limit_kw": d.ess_discharge_limit,
                    "outcome_reason": d.outcome_reason,
                },
                "state": {
                    "battery_soc": s.battery_soc,
                    "pv_kw": s.pv_kw,
                    "load_kw": s.load_kw,
                    "grid_import_power_kw": s.grid_import_power_kw,
                    "grid_export_power_kw": s.grid_export_power_kw,
                    "current_price": s.current_price,
                    "feedin_price": s.feedin_price,
                    "forecast_remaining_kwh": s.forecast_remaining_kwh,
                    "forecast_today_kwh": s.forecast_today_kwh,
                    "forecast_tomorrow_kwh": s.forecast_tomorrow_kwh,
                },
                "gates": gates,
                "values": values,
            }
        )

    def _record_automation_audit(self, s: SolarState, d: Decision, prev: Optional[Decision]) -> None:
        cfg = self.cfg
        effective_mode = self._manual_mode_override or s.sigenergy_mode
        if effective_mode not in {cfg.automated_option, ""}:
            return
        if prev is None:
            return

        def _changed(a: float | None, b: float | None, tol: float = 0.1) -> bool:
            try:
                return abs(float(a) - float(b)) > tol
            except Exception:
                return a != b

        changed_keys: list[str] = []
        if prev.ems_mode != d.ems_mode:
            changed_keys.append("ems_mode")
        if _changed(prev.export_limit, d.export_limit):
            changed_keys.append("export_limit")
        if _changed(prev.import_limit, d.import_limit):
            changed_keys.append("import_limit")
        if _changed(prev.pv_max_power_limit, d.pv_max_power_limit):
            changed_keys.append("pv_max_power_limit")
        if _changed(prev.ess_charge_limit, d.ess_charge_limit):
            changed_keys.append("ess_charge_limit")
        if _changed(prev.ess_discharge_limit, d.ess_discharge_limit):
            changed_keys.append("ess_discharge_limit")

        if not changed_keys:
            return

        self.record_audit_event(
            action="optimizer_apply",
            source="optimizer_cycle",
            actor="system:optimizer",
            result="ok",
            old_value={
                "ems_mode": prev.ems_mode,
                "export_limit": prev.export_limit,
                "import_limit": prev.import_limit,
                "pv_max_power_limit": prev.pv_max_power_limit,
                "ess_charge_limit": prev.ess_charge_limit,
                "ess_discharge_limit": prev.ess_discharge_limit,
            },
            new_value={
                "ems_mode": d.ems_mode,
                "export_limit": d.export_limit,
                "import_limit": d.import_limit,
                "pv_max_power_limit": d.pv_max_power_limit,
                "ess_charge_limit": d.ess_charge_limit,
                "ess_discharge_limit": d.ess_discharge_limit,
            },
            details={
                "initiator": "system",
                "changed_keys": changed_keys,
                "reason": d.outcome_reason,
            },
        )

    def _accumulate_history(self, s, d) -> None:
        import time as _time
        if not hasattr(self, "_chart_history_power"):
            self._chart_history_power = []
            self._chart_history_price = []
        now_ms = int(_time.time() * 1000)
        cutoff = now_ms - 86_400_000
        self._chart_history_power.append({
            "t": now_ms, "battery": s.battery_soc, "pv": s.pv_kw,
            "load": s.load_kw, "exp": s.grid_export_power_kw,
            "imp": s.grid_import_power_kw, "minSoc": d.min_soc_to_sunrise,
            "pvForecast": s.solar_power_now_kw,
        })
        self._chart_history_price.append({"t": now_ms, "imp": s.current_price, "fit": s.feedin_price})
        self._chart_history_power = [x for x in self._chart_history_power if x["t"] >= cutoff]
        self._chart_history_price = [x for x in self._chart_history_price if x["t"] >= cutoff]

    # ------------------------------------------------------------------
    # 1. Read all HA entities into a SolarState snapshot
    # ------------------------------------------------------------------

    async def _read_state(self) -> SolarState:
        cfg = self.cfg
        s = SolarState()

        # ---- bulk fetch -----------------------------------------------
        entity_ids = [
            cfg.pv_power_sensor, cfg.consumed_power_sensor, cfg.battery_soc_sensor,
            cfg.rated_capacity_sensor, cfg.available_discharge_sensor,
            cfg.ess_rated_discharge_power_sensor, cfg.ess_rated_charge_power_sensor,
            cfg.sun_entity, cfg.price_sensor, cfg.feedin_sensor,
            cfg.demand_window_sensor, cfg.price_spike_sensor,
            cfg.price_forecast_sensor, cfg.feedin_forecast_sensor,
            cfg.forecast_remaining_sensor, cfg.forecast_today_sensor,
            cfg.forecast_tomorrow_sensor, cfg.solar_power_now_sensor,
            cfg.daily_export_energy, cfg.daily_import_energy, cfg.daily_load_energy,
            cfg.daily_pv_energy, cfg.daily_battery_charge_energy, cfg.daily_battery_discharge_energy,
            cfg.grid_export_limit, cfg.grid_import_limit, cfg.pv_max_power_limit,
            cfg.ems_mode_select, cfg.ha_control_switch,
            cfg.export_session_start, cfg.import_session_start,
            cfg.last_export_notification, cfg.last_import_notification,
            cfg.sigenergy_mode_select,
        ]
        if cfg.ess_max_charging_limit:
            entity_ids.append(cfg.ess_max_charging_limit)
        if cfg.ess_max_discharging_limit:
            entity_ids.append(cfg.ess_max_discharging_limit)
        if cfg.battery_power_sensor:
            entity_ids.append(cfg.battery_power_sensor)
        if cfg.grid_import_power_sensor:
            entity_ids.append(cfg.grid_import_power_sensor)
        if cfg.grid_export_power_sensor:
            entity_ids.append(cfg.grid_export_power_sensor)
        for candidate in forecast_entity_candidates(cfg.price_sensor, cfg.price_forecast_sensor):
            if candidate and candidate not in entity_ids:
                entity_ids.append(candidate)
        for candidate in forecast_entity_candidates(cfg.feedin_sensor, cfg.feedin_forecast_sensor):
            if candidate and candidate not in entity_ids:
                entity_ids.append(candidate)
        bulk = await self.ha.bulk_states(entity_ids)

        def _fv(eid: str, default: Optional[float] = 0.0) -> Optional[float]:
            obj = bulk.get(eid)
            if not obj:
                return default
            try:
                value = float(obj["state"])
            except (TypeError, ValueError):
                return default
            return value if math.isfinite(value) else default

        def _sv(eid: str, default: str = "") -> str:
            obj = bulk.get(eid)
            if not obj:
                return default
            v = obj.get("state", "")
            return v if v not in {"unknown", "unavailable", "none", ""} else default

        def _bv(eid: str) -> bool:
            return _sv(eid, "off").lower() in ("on", "true", "1")

        def _attr(eid: str, attr: str, default=None):
            obj = bulk.get(eid)
            if not obj:
                return default
            return obj.get("attributes", {}).get(attr, default)

        observed_at = datetime.now(timezone.utc)
        unavailable_states = {"unknown", "unavailable", "none", ""}

        def _metadata_is_fresh(
            obj: dict[str, Any],
            max_age_seconds: float,
        ) -> bool:
            raw_timestamp = (
                obj.get("last_reported")
                if "last_reported" in obj
                else obj.get("last_updated")
            )
            if not raw_timestamp:
                return False
            try:
                updated_at = datetime.fromisoformat(
                    str(raw_timestamp).replace("Z", "+00:00")
                )
                if updated_at.tzinfo is None:
                    return False
                age_seconds = (
                    observed_at - updated_at.astimezone(timezone.utc)
                ).total_seconds()
                return -5.0 <= age_seconds <= max_age_seconds
            except (TypeError, ValueError):
                return False

        def _observed_number(
            eid: str,
            converter=None,
            *,
            max_age_seconds: float,
        ) -> HVACObservedValue:
            obj = bulk.get(eid)
            if not obj:
                return HVACObservedValue()
            raw_value = obj.get("state", "")
            if str(raw_value).strip().lower() in unavailable_states:
                return HVACObservedValue()
            try:
                value = float(raw_value)
                if not math.isfinite(value):
                    return HVACObservedValue()
                if converter is not None:
                    value = float(converter(value))
                return HVACObservedValue(
                    value=value,
                    available=True,
                    fresh=_metadata_is_fresh(obj, max_age_seconds),
                )
            except (TypeError, ValueError, OverflowError):
                return HVACObservedValue()

        def _observed_text(
            eid: str,
            *,
            current_when_present: bool = False,
            max_age_seconds: float,
        ) -> HVACObservedValue:
            obj = bulk.get(eid)
            if not obj:
                return HVACObservedValue()
            value = str(obj.get("state", "")).strip()
            if value.lower() in unavailable_states:
                return HVACObservedValue()
            return HVACObservedValue(
                value=value,
                available=True,
                fresh=current_when_present
                or _metadata_is_fresh(obj, max_age_seconds),
            )

        def _positive_power_kw(value: float) -> float:
            return value / 1000.0 if value > 100 else value

        def _battery_power_kw(value: float) -> float:
            value = value / 1000.0 if abs(value) > 100 else value
            return -value if cfg.battery_power_sensor_invert else value

        live_max_age = cfg.hvac_solar_data_max_age_seconds
        forecast_max_age = cfg.hvac_solar_forecast_max_age_seconds
        sun_observation = _observed_text(
            cfg.sun_entity,
            max_age_seconds=live_max_age,
        )
        if sun_observation.available:
            if sun_observation.value in {"above_horizon", "below_horizon"}:
                sun_observation = HVACObservedValue(
                    value=sun_observation.value == "above_horizon",
                    available=True,
                    fresh=sun_observation.fresh,
                )
            else:
                sun_observation = HVACObservedValue()

        configured_control_modes = {
            cfg.automated_option,
            cfg.full_export_option,
            cfg.full_import_option,
            cfg.full_import_pv_option,
            cfg.block_flow_option,
            cfg.manual_option,
        }
        control_mode_observation = _observed_text(
            cfg.sigenergy_mode_select,
            current_when_present=str(cfg.sigenergy_mode_select).startswith("input_select."),
            max_age_seconds=live_max_age,
        )
        if (
            control_mode_observation.available
            and control_mode_observation.value not in configured_control_modes
        ):
            control_mode_observation = HVACObservedValue()

        s.hvac_solar_inputs = HVACSolarInputContext(
            pv_power=_observed_number(
                cfg.pv_power_sensor,
                _positive_power_kw,
                max_age_seconds=live_max_age,
            ),
            load_power=_observed_number(
                cfg.consumed_power_sensor,
                _positive_power_kw,
                max_age_seconds=live_max_age,
            ),
            battery_power=_observed_number(
                cfg.battery_power_sensor,
                _battery_power_kw,
                max_age_seconds=live_max_age,
            ),
            grid_import_power=_observed_number(
                cfg.grid_import_power_sensor,
                _positive_power_kw,
                max_age_seconds=live_max_age,
            ),
            grid_export_power=_observed_number(
                cfg.grid_export_power_sensor,
                _positive_power_kw,
                max_age_seconds=live_max_age,
            ),
            solar_power_now=_observed_number(
                cfg.solar_power_now_sensor,
                _positive_power_kw,
                max_age_seconds=forecast_max_age,
            ),
            sun_above_horizon=sun_observation,
            control_mode=control_mode_observation,
            observed_ems_mode=_observed_text(
                cfg.ems_mode_select,
                current_when_present=True,
                max_age_seconds=live_max_age,
            ),
            observed_export_limit=_observed_number(
                cfg.grid_export_limit,
                max_age_seconds=live_max_age,
            ),
            live_snapshot=True,
        )

        # ---- PV / battery ---------------------------------------------
        pv_raw = _fv(cfg.pv_power_sensor)
        s.pv_kw = pv_raw / 1000 if pv_raw > 100 else pv_raw

        load_raw = _fv(cfg.consumed_power_sensor)
        s.load_kw = load_raw / 1000 if load_raw > 100 else load_raw
        if cfg.grid_import_power_sensor:
            grid_import_raw = _fv(cfg.grid_import_power_sensor, None)
            if grid_import_raw is not None:
                s.grid_import_power_kw = grid_import_raw / 1000 if grid_import_raw > 100 else grid_import_raw
        if cfg.grid_export_power_sensor:
            grid_export_raw = _fv(cfg.grid_export_power_sensor, None)
            if grid_export_raw is not None:
                s.grid_export_power_kw = grid_export_raw / 1000 if grid_export_raw > 100 else grid_export_raw
        if cfg.battery_power_sensor:
            battery_power_raw = _fv(cfg.battery_power_sensor, None)
            if isinstance(battery_power_raw, (int, float)):
                battery_power_kw = battery_power_raw / 1000 if abs(battery_power_raw) > 100 else battery_power_raw
                if cfg.battery_power_sensor_invert:
                    battery_power_kw = -battery_power_kw
                s.battery_power_sensor_kw = battery_power_kw

        s.battery_soc = max(0.0, min(100.0, _fv(cfg.battery_soc_sensor)))

        cap_raw = _fv(cfg.rated_capacity_sensor, 10.0)
        cap_uom = (_attr(cfg.rated_capacity_sensor, "unit_of_measurement") or "kwh").lower()
        if cap_uom == "wh":
            s.battery_capacity_kwh = cap_raw / 1000
        elif cap_raw < 1.0 and cap_raw > 0:
            s.battery_capacity_kwh = cap_raw * 1000
        else:
            s.battery_capacity_kwh = cap_raw if cap_raw > 0 else 10.0

        avail_raw = _fv(cfg.available_discharge_sensor)
        avail_uom = (_attr(cfg.available_discharge_sensor, "unit_of_measurement") or "kwh").lower()
        if avail_uom == "wh":
            s.available_discharge_energy_kwh = avail_raw / 1000
        else:
            s.available_discharge_energy_kwh = avail_raw

        def _kw_from_sensor(raw: float) -> float:
            if raw <= 0:
                return 999.0
            return raw / 1000 if raw >= 1000 else raw

        s.ess_max_discharge_kw = _kw_from_sensor(_fv(cfg.ess_rated_discharge_power_sensor))
        s.ess_max_charge_kw = _kw_from_sensor(_fv(cfg.ess_rated_charge_power_sensor))
        if self._valid_hw_cap_kw(s.ess_max_charge_kw):
            self._last_hw_charge_cap_kw = float(s.ess_max_charge_kw)
        if self._valid_hw_cap_kw(s.ess_max_discharge_kw):
            self._last_hw_discharge_cap_kw = float(s.ess_max_discharge_kw)

        # ---- Grid limits / EMS mode -----------------------------------
        s.current_export_limit = _fv(cfg.grid_export_limit)
        try:
            grid_export_max_attr = _attr(cfg.grid_export_limit, "max")
            if grid_export_max_attr is not None:
                grid_export_max_kw = float(grid_export_max_attr)
                if (
                    math.isfinite(grid_export_max_kw)
                    and 0.0 <= grid_export_max_kw <= _POWER_LIMIT_MAX_KW
                ):
                    s.grid_export_limit_entity_max_kw = grid_export_max_kw
        except (TypeError, ValueError):
            s.grid_export_limit_entity_max_kw = None
        s.current_import_limit = _fv(cfg.grid_import_limit)
        s.current_pv_max_power_limit = _fv(cfg.pv_max_power_limit)
        if cfg.ess_max_charging_limit:
            s.current_ess_charge_limit = _fv(cfg.ess_max_charging_limit)
            try:
                max_attr = _attr(cfg.ess_max_charging_limit, "max")
                if max_attr is not None:
                    s.ess_charge_limit_entity_max_kw = float(max_attr)
            except (TypeError, ValueError):
                s.ess_charge_limit_entity_max_kw = None
        if cfg.ess_max_discharging_limit:
            s.current_ess_discharge_limit = _fv(cfg.ess_max_discharging_limit)
            try:
                max_attr = _attr(cfg.ess_max_discharging_limit, "max")
                if max_attr is not None:
                    s.ess_discharge_limit_entity_max_kw = float(max_attr)
            except (TypeError, ValueError):
                s.ess_discharge_limit_entity_max_kw = None
        # Preserve an unknown/unavailable EMS selector as unknown. Safety-critical
        # export paths must not infer Maximum Self Consumption from a missing state.
        ems_mode_obj = bulk.get(cfg.ems_mode_select)
        ems_mode_raw = (
            str(ems_mode_obj.get("state", "")).strip()
            if ems_mode_obj
            else ""
        )
        s.ems_mode_observed = bool(
            ems_mode_raw
            and ems_mode_raw.lower() not in unavailable_states
        )
        s.current_ems_mode = ems_mode_raw if s.ems_mode_observed else ""
        ha_control_entity = str(cfg.ha_control_switch or "").strip()
        ha_control_obj = bulk.get(ha_control_entity)
        ha_control_raw_state = (
            str(ha_control_obj.get("state", "")).strip().lower()
            if ha_control_obj
            else ""
        )
        if not ha_control_entity.startswith("switch."):
            s.ha_control_switch_state = "invalid_domain"
        elif not ha_control_obj:
            s.ha_control_switch_state = "missing"
        elif ha_control_raw_state not in {"on", "off"}:
            s.ha_control_switch_state = ha_control_raw_state or "unknown"
        else:
            s.ha_control_switch_state = ha_control_raw_state
            s.ha_control_switch_available = True
        s.ha_control_enabled = (
            s.ha_control_switch_available and s.ha_control_switch_state == "on"
        )

        # ---- Prices ---------------------------------------------------
        price_obj = bulk.get(cfg.price_sensor, {})
        price_state = price_obj.get("state", "") if price_obj else ""
        price_is_estimate = str(_attr(cfg.price_sensor, "estimate") or "false").lower() == "true"
        price_available = price_state not in {"unknown", "unavailable", "none", ""}

        if price_available:
            try:
                raw_price = float(price_state)
                s.price_is_actual = not price_is_estimate
                s.price_is_estimated = price_is_estimate
                s.current_price = raw_price
                s.current_price_cents = raw_price * cfg.price_multiplier
            except (TypeError, ValueError):
                self._warn_parse_issue(cfg.price_sensor, str(price_state), "Price")
                s.current_price = 1.0
                s.current_price_cents = 1.0 * cfg.price_multiplier
        else:
            s.current_price = 1.0
            s.current_price_cents = 1.0 * cfg.price_multiplier

        fit_state = _sv(cfg.feedin_sensor, "")
        fit_available = fit_state != ""
        if fit_available:
            try:
                s.feedin_price = float(fit_state)
                s.feedin_price_cents = s.feedin_price * cfg.price_multiplier
            except (TypeError, ValueError):
                self._warn_parse_issue(cfg.feedin_sensor, str(fit_state), "FIT")
                s.feedin_price = -999.0
                s.feedin_price_cents = -999.0
                fit_available = False
        else:
            s.feedin_price = -999.0
            s.feedin_price_cents = -999.0

        s.price_is_negative = s.price_is_actual and s.current_price < 0
        s.feedin_is_negative = fit_available and s.feedin_price < 0
        s.price_spike_active = _bv(cfg.price_spike_sensor)
        s.demand_window_active = _bv(cfg.demand_window_sensor)

        # ---- Forecasts ------------------------------------------------
        s.forecast_remaining_kwh = _fv(cfg.forecast_remaining_sensor)
        s.forecast_today_kwh = _fv(cfg.forecast_today_sensor)
        s.forecast_tomorrow_kwh = _fv(cfg.forecast_tomorrow_sensor)

        solar_raw = _fv(cfg.solar_power_now_sensor)
        # Solcast power_now can return Watts (e.g. 554 W) or kW (e.g. 0.554 kW).
        # Values > 100 are assumed to be in Watts and converted; <= 100 assumed already kW.
        s.solar_power_now_kw = solar_raw / 1000 if solar_raw > 100 else solar_raw

        s.solcast_detailed = _attr(cfg.forecast_today_sensor, "detailedForecast") or []
        price_forecast_diagnostics: dict[str, Any] = {}
        s.price_forecast_entries = extract_forecast_entries(
            bulk,
            primary_entity=cfg.price_sensor,
            explicit_entity=cfg.price_forecast_sensor,
            preferred_attr=cfg.price_forecast_attribute,
            preferred_time_key=cfg.price_forecast_time_key,
            preferred_value_key=cfg.price_forecast_value_key,
            diagnostics=price_forecast_diagnostics,
        )
        self._warn_forecast_issue("Price forecast", price_forecast_diagnostics)
        feedin_forecast_diagnostics: dict[str, Any] = {}
        s.feedin_forecast_entries = extract_forecast_entries(
            bulk,
            primary_entity=cfg.feedin_sensor,
            explicit_entity=cfg.feedin_forecast_sensor,
            preferred_attr=cfg.feedin_forecast_attribute,
            preferred_time_key=cfg.price_forecast_time_key,
            preferred_value_key=cfg.feedin_forecast_value_key,
            diagnostics=feedin_forecast_diagnostics,
        )
        self._warn_forecast_issue("Feed-in forecast", feedin_forecast_diagnostics)

        # ---- Sun ------------------------------------------------------
        s.sun_elevation = float(_attr(cfg.sun_entity, "elevation") or 0)
        s.sun_above_horizon = _sv(cfg.sun_entity, "below_horizon") == "above_horizon"

        def _ts(attr: str) -> Optional[float]:
            v = _attr(cfg.sun_entity, attr)
            if not v:
                return None
            try:
                return datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp()
            except Exception:
                return None

        s.next_sunrise_ts = _ts("next_rising")
        s.next_sunset_ts = _ts("next_setting")

        now_ts = datetime.now().timestamp()
        if s.next_sunrise_ts:
            raw_h = (s.next_sunrise_ts - now_ts) / 3600
            s.hours_to_sunrise = max(0.0, raw_h)
        if s.next_sunset_ts:
            s.hours_to_sunset = max(0.0, (s.next_sunset_ts - now_ts) / 3600)

        # ---- Daily totals / session tracking --------------------------
        s.daily_export_kwh = _fv(cfg.daily_export_energy)
        s.daily_import_kwh = _fv(cfg.daily_import_energy)
        s.daily_load_kwh = _fv(cfg.daily_load_energy)
        s.daily_pv_kwh = _fv(cfg.daily_pv_energy)
        s.daily_battery_charge_kwh = _fv(cfg.daily_battery_charge_energy)
        s.daily_battery_discharge_kwh = _fv(cfg.daily_battery_discharge_energy)
        s.export_session_start_kwh = _fv(cfg.export_session_start)
        s.import_session_start_kwh = _fv(cfg.import_session_start)
        s.last_export_notification = _sv(cfg.last_export_notification, "stopped")
        s.last_import_notification = _sv(cfg.last_import_notification, "stopped")

        # ---- Mode select ----------------------------------------------
        sigenergy_mode_obj = bulk.get(cfg.sigenergy_mode_select)
        sigenergy_mode_raw = (
            str(sigenergy_mode_obj.get("state", "")).strip()
            if sigenergy_mode_obj
            else ""
        )
        s.sigenergy_mode_observed = bool(
            sigenergy_mode_raw
            and sigenergy_mode_raw.lower() not in unavailable_states
        )
        last_mode = self._last_state.sigenergy_mode if self._last_state else ""
        mode_default = self._manual_mode_override or last_mode or cfg.automated_option
        s.sigenergy_mode = _sv(cfg.sigenergy_mode_select, mode_default)
        if self._manual_mode_override and s.sigenergy_mode in {cfg.automated_option, ""}:
            logger.warning(
                "Mode selector read as '%s' while manual override '%s' is active; preserving manual mode",
                s.sigenergy_mode,
                self._manual_mode_override,
            )
            s.sigenergy_mode = self._manual_mode_override

        return s

    # ------------------------------------------------------------------
    # 2. Pure decision logic
    # ------------------------------------------------------------------

    def _decide(self, s: SolarState) -> Decision:
        """Translate the full YAML variable block into a Decision object."""
        cfg = self.cfg
        d = Decision()
        now = datetime.now()
        now_ts = now.timestamp()

        # ---- Time windows -------------------------------------------
        day_start_ts, day_end_ts = self._day_window(s)
        is_evening_or_night = now_ts < day_start_ts or now_ts > day_end_ts
        d.is_evening_or_night = is_evening_or_night

        sunset_ts = s.next_sunset_ts or (now_ts + 86400)
        sunrise_ts = s.next_sunrise_ts or (now_ts + 86400)
        if s.sun_above_horizon:
            actual_sunrise_ts = sunrise_ts - 86400
        else:
            actual_sunrise_ts = sunrise_ts

        hours_to_sunrise = s.hours_to_sunrise
        hours_to_sunset = s.hours_to_sunset
        close_to_sunset = hours_to_sunset <= cfg.sunset_export_grace_hours
        d.hours_to_sunrise = hours_to_sunrise

        # ---- Re-derive price flags (in case s came from a test, not _read_state) ----
        s.price_is_negative = s.price_is_actual and s.current_price < 0
        s.feedin_is_negative = s.feedin_price not in (-999.0,) and s.feedin_price < 0

        # ---- Battery capacity helpers --------------------------------
        cap = s.battery_capacity_kwh
        bat_fill_need_kwh = max(0.0, cap - s.available_discharge_energy_kwh)

        # ---- Sunrise SoC target (dynamic calculation) ----------------
        soc_required = self._battery_soc_required_to_sunrise(s)
        d.battery_soc_required_to_sunrise = soc_required
        sunrise_soc_target = max(soc_required, cfg.sunrise_reserve_soc)
        d.sunrise_soc_target = sunrise_soc_target
        sunrise_fill_need_kwh = max(0.0, cap * ((sunrise_soc_target - s.battery_soc) / 100))
        d.min_soc_to_sunrise = soc_required

        # ---- Price forecasts -----------------------------------------
        negative_price_before_cutoff = self._negative_price_before_cutoff(s, now_ts)

        # ---- Productive solar window ---------------------------------
        productive_solar_end_ts = self._productive_solar_end_ts(s, sunset_ts, now_ts)

        # ---- Morning dump -------------------------------------------
        morning_dump_start_ts, morning_dump_end_ts = self._morning_dump_window(s, actual_sunrise_ts)
        morning_dump_active = self._morning_dump_active(
            s, morning_dump_start_ts, morning_dump_end_ts,
            productive_solar_end_ts, bat_fill_need_kwh, now_ts
        )
        within_morning_grace = (
            cfg.morning_dump_enabled
            and morning_dump_end_ts is not None
            and now_ts >= morning_dump_end_ts
            and now_ts < morning_dump_end_ts + 7200
        )

        d.morning_dump_active = morning_dump_active

        # ---- Morning slow charge ------------------------------------
        morning_slow_charge_end_ts = (
            (sunset_ts - cfg.morning_slow_charge_sunset_cutoff * 3600)
            if sunset_ts else now_ts
        )
        morning_slow_charge_active = self._morning_slow_charge_active(
            s, now, now_ts, morning_slow_charge_end_ts
        )
        d.morning_slow_charge_active = morning_slow_charge_active

        # ---- Standby holdoff ----------------------------------------
        battery_can_reach_from_pv = (
            s.forecast_remaining_kwh >= sunrise_fill_need_kwh * cfg.forecast_safety_charging
        )
        standby_holdoff_active = (
            cfg.standby_holdoff_enabled
            and s.forecast_today_kwh >= cfg.pv_forecast_holdoff_kwh
            and negative_price_before_cutoff
            and now < self._today_at(cfg.standby_holdoff_end_time)
            and s.current_price > cfg.import_threshold_low
            and battery_can_reach_from_pv
        )
        d.standby_holdoff_active = standby_holdoff_active
        
        # Store holdoff floor at entry to prevent drift from forecast updates mid-holdoff
        prev_holdoff = self._last_decision and self._last_decision.standby_holdoff_active
        if standby_holdoff_active and not prev_holdoff:
            # Holdoff just became active — snapshot the SoC floor
            soc_required = self._battery_soc_required_to_sunrise(s)
            holdoff_sunrise_target = max(soc_required, cfg.sunrise_reserve_soc)
            self._holdoff_entry_floor = holdoff_sunrise_target + cfg.soc_hysteresis
        elif not standby_holdoff_active:
            # Holdoff expired — clear the stored floor
            self._holdoff_entry_floor = None

        # ---- Evening boost ------------------------------------------
        evening_export_boost_active = self._evening_export_boost_active(
            s, now_ts, productive_solar_end_ts, sunrise_soc_target, bat_fill_need_kwh
        )
        d.evening_export_boost_active = evening_export_boost_active

        # ---- Effective min SoC for export ---------------------------
        if is_evening_or_night:
            relaxed = sunrise_soc_target - cfg.sunrise_export_relax_percent
            effective_min_soc = max(relaxed, cfg.sunrise_reserve_soc)
        else:
            effective_min_soc = cfg.min_soc_floor

        export_sunrise_guard_active = is_evening_or_night
        export_min_soc = effective_min_soc
        if export_sunrise_guard_active:
            export_min_soc = max(effective_min_soc, soc_required)

        # ---- Export flags -------------------------------------------
        export_spike_active = (
            s.price_spike_active
            and s.feedin_price >= cfg.export_spike_threshold
        )
        d.export_spike_active = export_spike_active

        positive_fit_override = (
            cfg.allow_low_medium_export_positive_fit
            and s.feedin_price >= 0.01
        )

        solar_potential_kw = max(s.pv_kw, s.solar_power_now_kw)
        pv_surplus = max(solar_potential_kw - s.load_kw, 0.0)
        pv_surplus_actual = max(s.pv_kw - s.load_kw, 0.0)

        export_solar_override = (
            s.feedin_price > 0
            and s.feedin_price >= cfg.export_threshold_medium
            and s.battery_soc >= cfg.max_battery_soc
            and not is_evening_or_night
            and pv_surplus > cfg.min_grid_transfer_kw
            and (
                s.forecast_remaining_kwh >= bat_fill_need_kwh * 1.25
                or bat_fill_need_kwh <= 0
            )
        )

        # ---- PV safeguard -------------------------------------------
        full_export_override_check = (
            s.battery_soc >= cfg.max_battery_soc
            and not is_evening_or_night
            and pv_surplus > cfg.min_grid_transfer_kw
        )
        est_load_kwh = s.load_kw * hours_to_sunset
        net_forecast = s.forecast_remaining_kwh - est_load_kwh
        tomorrow_kwh = s.forecast_tomorrow_kwh
        low_today = s.forecast_remaining_kwh > 0 and net_forecast <= bat_fill_need_kwh * cfg.forecast_safety_charging
        low_tomorrow = is_evening_or_night and tomorrow_kwh < cap * cfg.forecast_safety_charging
        pv_safeguard_active = (
            not full_export_override_check
            and not positive_fit_override
            and (low_today or low_tomorrow)
        )
        d.pv_safeguard_active = pv_safeguard_active

        # ---- Solar surplus bypass -----------------------------------
        solar_surplus_bypass = self._solar_surplus_bypass(
            s, morning_slow_charge_active, cap, pv_surplus_actual,
            previously_active=bool(
                self._last_decision
                and self._last_decision.trace_gates.get(
                    "pv_only_branch_high_ceiling_active"
                )
                and self._last_decision.trace_gates.get(
                    "observed_automated_control_mode"
                )
                and self._last_decision.trace_values.get("pv_only_branch_source")
                == "solar_surplus_bypass"
            ),
        )
        d.solar_surplus_bypass = solar_surplus_bypass

        # ---- Battery full safeguard ---------------------------------
        battery_full_safeguard_block = self._battery_full_safeguard_block(
            s, now_ts, sunset_ts, bat_fill_need_kwh, is_evening_or_night
        )
        d.battery_full_safeguard = battery_full_safeguard_block

        # ---- Export blocked for forecast ----------------------------
        export_blocked_for_forecast = self._export_blocked_for_forecast(
            s, pv_surplus, is_evening_or_night, bat_fill_need_kwh,
            hours_to_sunset, close_to_sunset
        )
        export_forecast_guard = self._export_forecast_guard(
            s, sunrise_fill_need_kwh, is_evening_or_night,
            evening_export_boost_active, close_to_sunset
        )
        export_blocked_effective = export_blocked_for_forecast

        # ---- Morning dump limit -------------------------------------
        morning_dump_limit = min(cfg.export_limit_high, s.ess_max_discharge_kw)

        # ---- Desired export limit -----------------------------------
        # Keep exact policy provenance with the numeric result. Activity flags can
        # overlap, but only the branch that produced the limit may claim PV-only
        # high-ceiling authority.
        def choose_export_limit(
            *,
            surplus_bypass_for_policy: bool,
            morning_slow_for_policy: bool,
        ) -> tuple[float, str, float]:
            tier_limit = self._export_tier_limit(
                s,
                export_spike_active,
                export_solar_override,
                pv_safeguard_active,
                evening_export_boost_active,
                surplus_bypass_for_policy,
            )
            raw_choice = self._desired_export_limit(
                s, export_spike_active, export_solar_override,
                export_blocked_effective, export_forecast_guard,
                export_min_soc, positive_fit_override, surplus_bypass_for_policy,
                evening_export_boost_active, morning_dump_active, morning_dump_limit,
                battery_full_safeguard_block,
                tier_limit, hours_to_sunrise, cap,
                # Forecast potential avoids the old self-curtailed measured-PV loop.
                pv_surplus, is_evening_or_night, morning_slow_for_policy,
                within_morning_grace,
            )
            return (
                float(raw_choice),
                str(getattr(raw_choice, "source", "external_override")),
                float(tier_limit),
            )

        (
            desired_export_limit,
            desired_export_source,
            export_tier_limit,
        ) = choose_export_limit(
            surplus_bypass_for_policy=solar_surplus_bypass,
            morning_slow_for_policy=morning_slow_charge_active,
        )
        initial_desired_export_source = desired_export_source
        # Morning Slow Charge deliberately retains its established priority here:
        # the hotfix contract requires any export selected by that branch to remain
        # PV-only under MSC. Solar Bypass is the overlay that can coexist with and
        # must defer to separately owned discharge/export policies.
        pv_only_branch_policy_deferred = bool(
            solar_surplus_bypass
            and initial_desired_export_source in {
                "solar_surplus_pv_high",
                "solar_surplus_pv_closed",
                "solar_surplus_closed",
            }
            and (
                export_solar_override
                or s.demand_window_active
                or evening_export_boost_active
            )
        )
        if pv_only_branch_policy_deferred:
            (
                desired_export_limit,
                desired_export_source,
                export_tier_limit,
            ) = choose_export_limit(
                surplus_bypass_for_policy=False,
                morning_slow_for_policy=morning_slow_charge_active,
            )
            pv_only_branch_policy_deferred_reason = (
                "Solar Surplus Bypass PV-only ceiling deferred to independently "
                f"selected policy source {desired_export_source}."
            )
        else:
            pv_only_branch_policy_deferred_reason = "inactive: no competing policy owner"
        export_value_gate_vetoed = False
        measured_pv_surplus_kw = max(s.pv_kw - s.load_kw, 0.0)
        export_value_gate_pv_surplus_initiated_active = False
        export_value_gate_pv_surplus_carveout_active = False
        export_value_gate_export_type = "unknown"
        pv_surplus_export_allowed_below_import_floor = False
        pv_surplus_initiation_source = "none"
        pv_surplus_estimated_init_active = False
        pv_surplus_breathe_probe_active = False
        pv_surplus_breathe_probe_continuation_active = False
        pv_only_msc_stage1_active = False
        pv_only_msc_transition_ready = False
        pv_only_msc_high_ceiling_active = False
        pv_only_msc_high_ceiling_kw = 0.0
        pv_only_msc_authoritative_cap_kw: Optional[float] = None
        pv_only_msc_transition_reason = "inactive"
        pv_only_msc_high_ceiling_reason = "inactive"
        pv_surplus_estimated_init_reason = (
            "diagnostic-only: legacy measured/estimated/breathe PV discovery cannot "
            "change the live export ceiling."
        )
        pv_surplus_probe_export_cap_kw = 0.0
        topoff_target_soc = self._topoff_target_soc()
        topoff_target_met = bool(
            math.isfinite(float(s.battery_soc))
            and s.battery_soc + 1e-6 >= topoff_target_soc
        )
        mode_label = str(s.sigenergy_mode or cfg.automated_option)
        manual_exempt_modes = {
            str(cfg.full_export_option),
            str(cfg.full_import_option),
            str(cfg.full_import_pv_option),
            str(cfg.block_flow_option),
            str(cfg.manual_option),
        }
        automatic_control_mode = mode_label not in manual_exempt_modes
        observed_automated_control_mode = bool(
            not self._manual_mode_override
            and s.sigenergy_mode_observed
            and
            str(s.sigenergy_mode or "") == str(cfg.automated_option)
        )
        observed_max_self_consumption = bool(
            s.ems_mode_observed
            and s.current_ems_mode == MODE_MAX_SELF
        )
        battery_discharge_kw_for_pv_only, battery_flow_source_for_pv_only = (
            self._battery_discharge_kw_for_pv_only_check(s)
        )
        pv_only_discharge_tolerance_kw = 0.1
        pv_only_discharge_ok = (
            battery_discharge_kw_for_pv_only is not None
            and battery_discharge_kw_for_pv_only <= pv_only_discharge_tolerance_kw
        )
        # Identify the two PV-only high-ceiling branches from the exact winning
        # policy source, never from overlapping activity flags.
        morning_slow_pv_only_high_ceiling_requested = bool(
            desired_export_source == "morning_slow_pv_high"
            and desired_export_limit > 0.01
        )
        solar_surplus_pv_only_high_ceiling_requested = bool(
            desired_export_source == "solar_surplus_pv_high"
            and desired_export_limit > 0.01
        )
        pv_only_branch_zero_ceiling = bool(
            desired_export_source in {
                "morning_slow_pv_closed",
                "solar_surplus_pv_closed",
            }
            or (
                desired_export_source == "morning_slow_closed"
                and observed_automated_control_mode
            )
        )
        pv_only_branch_high_ceiling_requested = bool(
            morning_slow_pv_only_high_ceiling_requested
            or solar_surplus_pv_only_high_ceiling_requested
        )
        pv_only_branch_source = (
            "morning_slow_charge"
            if morning_slow_pv_only_high_ceiling_requested
            else (
                "solar_surplus_bypass"
                if solar_surplus_pv_only_high_ceiling_requested
                else "none"
            )
        )
        pv_only_branch_battery_safety_blocked = bool(
            pv_only_branch_high_ceiling_requested and not pv_only_discharge_ok
        )
        pv_only_branch_automated_ownership_blocked = bool(
            pv_only_branch_high_ceiling_requested
            and not observed_automated_control_mode
        )
        pv_only_branch_exception_rejected = bool(
            pv_only_branch_battery_safety_blocked
            or pv_only_branch_automated_ownership_blocked
        )
        if pv_only_branch_exception_rejected:
            # Reject only the PV-only high-ceiling exception. Re-run without either
            # overlay so an independently valid battery-export branch remains
            # available and still receives normal classification/economic guards.
            (
                desired_export_limit,
                desired_export_source,
                export_tier_limit,
            ) = choose_export_limit(
                surplus_bypass_for_policy=False,
                morning_slow_for_policy=False,
            )
        desired_export_limit_pre_value_gate = desired_export_limit
        pv_only_branch_high_ceiling_active = bool(
            pv_only_branch_high_ceiling_requested
            and not pv_only_branch_exception_rejected
        )
        if not pv_only_branch_high_ceiling_requested:
            pv_only_branch_safety_reason = "inactive: no PV-only operating ceiling requested"
        elif pv_only_branch_automated_ownership_blocked:
            pv_only_branch_safety_reason = (
                f"blocked {pv_only_branch_source}: Automated ownership is unavailable "
                "or not genuinely observed"
            )
        elif battery_discharge_kw_for_pv_only is None:
            pv_only_branch_safety_reason = (
                f"blocked {pv_only_branch_source}: battery flow is unknown or untrustworthy"
            )
        elif battery_discharge_kw_for_pv_only > pv_only_discharge_tolerance_kw:
            pv_only_branch_safety_reason = (
                f"blocked {pv_only_branch_source}: battery discharge "
                f"{battery_discharge_kw_for_pv_only:.2f} kW exceeds PV-only tolerance "
                f"{pv_only_discharge_tolerance_kw:.2f} kW"
            )
        else:
            pv_only_branch_safety_reason = (
                f"active {pv_only_branch_source}: trusted battery discharge "
                f"{battery_discharge_kw_for_pv_only:.2f} kW is within PV-only tolerance"
            )
        pv_only_ems_safe = s.current_ems_mode in ({MODE_MAX_SELF} | CHARGE_MODES)
        live_pv_value = float(s.pv_kw or 0.0)
        live_load_value = float(s.load_kw or 0.0)
        live_pv_and_load_finite = bool(
            math.isfinite(live_pv_value) and math.isfinite(live_load_value)
        )
        live_pv_kw = max(live_pv_value, 0.0) if live_pv_and_load_finite else 0.0
        live_load_kw = max(live_load_value, 0.0) if live_pv_and_load_finite else 0.0
        live_pv_plausible_for_msc_ceiling = (
            live_pv_and_load_finite
            and
            live_pv_kw > 0.05
            and (
                live_pv_kw >= max(float(cfg.productive_solar_threshold_kw or 0.0), 0.0)
                or live_pv_kw + pv_only_discharge_tolerance_kw >= live_load_kw
            )
        )
        feedin_price_for_pv_only = float(s.feedin_price or 0.0)
        pv_surplus_common_conditions = (
            not is_evening_or_night
            and math.isfinite(feedin_price_for_pv_only)
            and feedin_price_for_pv_only >= 0.01
            and not s.feedin_is_negative
            and not export_spike_active
            and not morning_dump_active
            and not evening_export_boost_active
        )
        pv_surplus_base_conditions = (
            pv_surplus_common_conditions
            and measured_pv_surplus_kw >= cfg.min_grid_transfer_kw
        )
        pv_surplus_only_proven = (
            pv_surplus_base_conditions
            and topoff_target_met
            and pv_only_discharge_ok
            and pv_only_ems_safe
        )
        pv_surplus_topoff_block_active = bool(
            pv_surplus_base_conditions and not topoff_target_met
        )

        (
            pv_only_msc_high_ceiling_kw,
            pv_only_msc_authoritative_cap_kw,
        ) = self._bounded_pv_only_high_ceiling(s)
        pv_only_classification_cap_kw = pv_only_msc_high_ceiling_kw
        pv_only_msc_transition_ready = bool(
            observed_automated_control_mode
            and pv_surplus_common_conditions
            and topoff_target_met
            and pv_only_discharge_ok
            and live_pv_plausible_for_msc_ceiling
            and not s.price_is_negative
            and not s.demand_window_active
            and not morning_slow_charge_active
            and not standby_holdoff_active
            and not battery_full_safeguard_block
            and not export_blocked_effective
            and not export_forecast_guard
            and not positive_fit_override
            and pv_only_msc_high_ceiling_kw >= float(cfg.min_grid_transfer_kw)
        )
        pv_only_msc_stage1_active = bool(
            pv_only_msc_transition_ready
            and not observed_max_self_consumption
        )
        pv_only_msc_high_ceiling_active = bool(
            pv_only_msc_transition_ready
            and observed_max_self_consumption
        )

        if pv_only_msc_stage1_active:
            desired_export_limit = 0.0
            pv_only_msc_transition_reason = (
                "stage 1: full-battery PV-only opportunity qualifies, but Maximum "
                "Self Consumption is not genuinely observed; keep export closed, "
                "command Maximum Self Consumption, and wait for a later cycle."
            )
        if pv_only_msc_high_ceiling_active:
            desired_export_limit = pv_only_msc_high_ceiling_kw
            export_value_gate_pv_surplus_initiated_active = True
            pv_surplus_initiation_source = "msc_full_battery_high_ceiling"
            pv_only_msc_transition_reason = (
                "stage 2: genuine Automated and Maximum Self Consumption observations "
                "are present in this cycle; open the configured high export ceiling directly."
            )
            pv_only_msc_high_ceiling_reason = (
                "active: genuinely observed Automated and Maximum Self Consumption with "
                "the 100% top-off target met, known battery flow within discharge "
                "tolerance, qualifying daytime PV, and FiT at or above 1c/kWh; the "
                "export setpoint is a ceiling."
            )

        def classify_export_type() -> tuple[str, bool, float, str]:
            if desired_export_limit <= 0.01:
                return "no_live_export", False, 0.0, "export limit closed"
            if battery_discharge_kw_for_pv_only is None:
                return (
                    "unknown_or_mixed",
                    False,
                    0.0,
                    "battery flow unknown, so export cannot be proven PV-only",
                )
            if battery_discharge_kw_for_pv_only > pv_only_discharge_tolerance_kw:
                return (
                    "battery_backed",
                    False,
                    0.0,
                    "battery discharge above PV-only tolerance",
                )

            if pv_only_branch_high_ceiling_active:
                return (
                    "pv_surplus_only",
                    True,
                    measured_pv_surplus_kw,
                    (
                        f"PV-only {pv_only_branch_source} Maximum Self Consumption "
                        "export ceiling; dispatch requires exact MSC confirmation and "
                        "known battery discharge remains within tolerance"
                    ),
                )

            pv_only_context_ok = bool(
                automatic_control_mode
                and pv_surplus_common_conditions
                and topoff_target_met
                and pv_only_discharge_ok
                and pv_only_ems_safe
            )
            if not pv_only_context_ok:
                return (
                    "unknown_or_mixed",
                    False,
                    0.0,
                    "PV-only safety context not satisfied",
                )

            if pv_only_msc_high_ceiling_active:
                return (
                    "pv_surplus_only",
                    True,
                    measured_pv_surplus_kw,
                    (
                        "confirmed PV-only Automated Maximum Self Consumption export "
                        "ceiling; the ceiling is not a request for battery energy"
                    ),
                )

            if not pv_surplus_only_proven:
                return (
                    "unknown_or_mixed",
                    False,
                    0.0,
                    "export source is not safely identified as PV-only",
                )
            if (
                desired_export_limit <= (measured_pv_surplus_kw + 0.05)
                and desired_export_limit <= (pv_only_classification_cap_kw + 1e-6)
            ):
                return (
                    "pv_surplus_only",
                    True,
                    measured_pv_surplus_kw,
                    "confirmed PV-only export capped to measured surplus",
                )
            return (
                "unknown_or_mixed",
                False,
                measured_pv_surplus_kw,
                "export cap exceeds confirmed PV-only basis",
            )

        export_value_gate = self._export_value_gate_advisory(
            s,
            desired_export_limit=desired_export_limit,
            sunrise_soc_target=sunrise_soc_target,
            soc_required=soc_required,
            productive_solar_end_ts=productive_solar_end_ts,
            now_ts=now_ts,
            export_spike_active=export_spike_active,
        )
        d.protected_reserve_soc = float(export_value_gate["protected_reserve_soc"])
        d.export_surplus_soc = float(export_value_gate["export_surplus_soc"])
        d.stored_energy_value_floor = float(export_value_gate["stored_energy_value_floor"])
        d.export_value_gate_would_allow = bool(export_value_gate["export_value_gate_would_allow"])
        d.export_value_gate_would_block = bool(export_value_gate["export_value_gate_would_block"])
        d.export_value_gate_reason = str(export_value_gate["export_value_gate_reason"])
        export_value_gate_block_reason = str(export_value_gate.get("export_value_gate_block_reason", "unknown"))
        export_value_gate_mode = str(export_value_gate.get("export_value_gate_mode", "Disabled"))
        export_value_gate_fit_cents = float(export_value_gate.get("export_value_gate_fit_cents", float(s.feedin_price or 0.0) * 100.0))
        export_value_gate_floor_cents = float(export_value_gate.get("export_value_gate_floor_cents", d.stored_energy_value_floor * 100.0))
        export_value_gate_difference_cents = float(export_value_gate.get("export_value_gate_difference_cents", export_value_gate_fit_cents - export_value_gate_floor_cents))
        today_import_topup_kwh = float(export_value_gate.get("today_import_topup_kwh", 0.0) or 0.0)
        today_highest_actual_import_price = export_value_gate.get("today_highest_actual_import_price")
        import_cost_export_floor = export_value_gate.get("import_cost_export_floor")
        effective_battery_export_floor = float(export_value_gate.get("effective_battery_export_floor", d.stored_energy_value_floor) or 0.0)
        import_cost_floor_trusted = bool(export_value_gate.get("import_cost_floor_trusted", True))
        import_cost_floor_unknown = bool(export_value_gate.get("import_cost_floor_unknown", False))
        # Value Gate is advisory only. It may calculate and report what it would
        # have blocked, but it has no authority to alter the live export decision.
        value_gate_enforcement_active = False
        actual_import_cost_guard_active = bool(
            automatic_control_mode
            and (import_cost_floor_unknown or today_highest_actual_import_price is not None)
        )
        actual_import_cost_guard_blocking = False
        automatic_export_blocked_below_actual_import_cost = False
        actual_import_cost_guard_reason = "inactive: no optimiser import/top-up recorded today."

        (
            export_value_gate_export_type,
            pv_surplus_only_safe_for_export,
            pv_surplus_limit_basis_kw,
            export_classification_reason,
        ) = classify_export_type()
        export_value_gate_applies_to_export_type = export_value_gate_export_type in {
            "battery_backed",
            "unknown_or_mixed",
        }
        if export_value_gate_export_type == "no_live_export" and pv_surplus_topoff_block_active:
            d.export_value_gate_reason = (
                "PV-surplus export not initiated because battery SoC "
                f"{s.battery_soc:.1f}% is below top-off target {topoff_target_soc:.1f}%."
            )
            export_value_gate_block_reason = "topoff_target_not_met"

        if (
            pv_only_msc_high_ceiling_active
            and d.export_value_gate_would_block
            and export_value_gate_block_reason in {"price_below_floor", "price_below_import_cost_floor", "import_cost_floor_untrusted"}
            and pv_surplus_only_safe_for_export
        ):
            pv_surplus_export_allowed_below_import_floor = True
            d.export_value_gate_would_allow = True
            d.export_value_gate_would_block = False
            d.export_value_gate_reason = (
                "PV-surplus-only MSC export ceiling allowed: feed-in price "
                f"{export_value_gate_fit_cents:.1f}c/kWh is below floor "
                f"{export_value_gate_floor_cents:.1f}c/kWh, but the "
                f"{desired_export_limit:.1f} kW Maximum Self Consumption setpoint "
                "is a ceiling and known battery discharge remains within tolerance."
            )
            export_value_gate_export_type = "pv_surplus_only"

        if (
            not export_value_gate_pv_surplus_initiated_active
            and
            d.export_value_gate_would_block
            and export_value_gate_block_reason in {"price_below_floor", "price_below_import_cost_floor", "import_cost_floor_untrusted"}
            and pv_surplus_only_proven
            and desired_export_limit <= (measured_pv_surplus_kw + 0.05)
            and d.export_surplus_soc > 0.05
        ):
            export_value_gate_pv_surplus_carveout_active = True
            pv_surplus_export_allowed_below_import_floor = True
            d.export_value_gate_would_allow = True
            d.export_value_gate_would_block = False
            d.export_value_gate_reason = (
                "PV-surplus-only export allowed: feed-in price "
                f"{export_value_gate_fit_cents:.0f}c/kWh is below floor {export_value_gate_floor_cents:.0f}c/kWh, "
                f"but daytime surplus PV export is capped to measured surplus {measured_pv_surplus_kw:.1f} kW."
            )
            export_value_gate_export_type = "pv_surplus_only"
            if value_gate_enforcement_active:
                desired_export_limit = min(desired_export_limit, measured_pv_surplus_kw)

        export_value_gate_applies_to_export_type = export_value_gate_export_type in {
            "battery_backed",
            "unknown_or_mixed",
        }
        actual_import_cost_guard_applies_to_export_type = export_value_gate_applies_to_export_type
        actual_import_cost_guard_bypassed_for_pv_surplus_only = bool(
            export_value_gate_export_type == "pv_surplus_only"
            and pv_surplus_only_safe_for_export
        )
        value_gate_would_veto_live = bool(
            value_gate_enforcement_active
            and d.export_value_gate_would_block
            and desired_export_limit > 0
            and export_value_gate_applies_to_export_type
        )

        if not automatic_control_mode:
            actual_import_cost_guard_reason = (
                f"inactive: manual mode '{mode_label}' is exempt from automatic import-cost guard."
            )
        elif not actual_import_cost_guard_active:
            actual_import_cost_guard_reason = "inactive: no optimiser import/top-up recorded today."
        elif desired_export_limit <= 0.01:
            actual_import_cost_guard_reason = "active: no automatic export requested."
        elif actual_import_cost_guard_bypassed_for_pv_surplus_only:
            if (
                import_cost_floor_unknown
                or (
                    import_cost_export_floor is not None
                    and float(s.feedin_price or 0.0) < float(import_cost_export_floor)
                )
            ):
                pv_surplus_export_allowed_below_import_floor = True
            if pv_only_msc_high_ceiling_active or pv_only_branch_high_ceiling_active:
                actual_import_cost_guard_reason = (
                    "bypassed: confirmed PV-only Maximum Self Consumption export ceiling; "
                    "the ceiling is not requested battery energy and battery discharge "
                    "remains within tolerance."
                )
            else:
                actual_import_cost_guard_reason = (
                    "bypassed: confirmed measured PV-surplus-only export; battery discharge within tolerance."
                )
        elif not actual_import_cost_guard_applies_to_export_type:
            actual_import_cost_guard_reason = (
                f"inactive: export type {export_value_gate_export_type} is not subject to the import-cost guard."
            )
        elif import_cost_floor_unknown:
            actual_import_cost_guard_blocking = True
            actual_import_cost_guard_reason = (
                "blocking: optimiser import/top-up occurred today but actual import price was unavailable or untrusted."
            )
        else:
            import_cost_floor_value = (
                float(import_cost_export_floor)
                if import_cost_export_floor is not None
                else None
            )
            if (
                import_cost_floor_value is not None
                and float(s.feedin_price or 0.0) + 1e-9 < import_cost_floor_value
            ):
                actual_import_cost_guard_blocking = True
                automatic_export_blocked_below_actual_import_cost = True
                actual_import_cost_guard_reason = (
                    "blocking: automatic battery-backed/mixed export below today's highest actual import price "
                    f"({float(s.feedin_price or 0.0) * 100.0:.0f}c/kWh < {import_cost_floor_value * 100.0:.0f}c/kWh)."
                )
            else:
                actual_import_cost_guard_reason = (
                    "active: feed-in price meets today's actual import-cost floor."
                )

        if actual_import_cost_guard_blocking and desired_export_limit > 0:
            if value_gate_would_veto_live:
                export_value_gate_vetoed = True
                d.export_value_gate_reason = (
                    "Enforced veto: export blocked by value gate. "
                    f"{d.export_value_gate_reason}"
                )
            desired_export_limit = 0.0

        if (
            value_gate_would_veto_live
            and not export_value_gate_vetoed
            and desired_export_limit > 0
        ):
            export_value_gate_vetoed = True
            desired_export_limit = 0.0
            d.export_value_gate_reason = (
                "Enforced veto: export blocked by value gate. "
                f"{d.export_value_gate_reason}"
            )

        d.export_limit = desired_export_limit
        d.requires_verified_msc_before_export = bool(
            desired_export_limit > 0.01
            and (
                pv_only_msc_high_ceiling_active
                or pv_only_branch_high_ceiling_active
            )
        )
        export_value_gate_bypassed_for_pv_surplus_only = bool(
            export_value_gate_export_type == "pv_surplus_only"
            and pv_surplus_only_safe_for_export
            and pv_surplus_export_allowed_below_import_floor
        )

        # ---- Import limit (grid_limit_base → desired_import_limit) --
        desired_import_limit = self._desired_import_limit(
            s, morning_dump_active, demand_window_active=s.demand_window_active,
            standby_holdoff_active=standby_holdoff_active,
            feedin_price_ok=(s.feedin_price >= cfg.export_threshold_low),
            pv_surplus=pv_surplus_actual,
        )
        d.import_limit = desired_import_limit

        # ---- Desired EMS mode ---------------------------------------
        desired_ems_mode = self._desired_ems_mode(
            s, morning_dump_active, standby_holdoff_active, export_solar_override,
            desired_export_limit, desired_import_limit, export_min_soc,
            sunrise_soc_target, within_morning_grace,
            export_blocked_for_forecast, is_evening_or_night,
        )
        pv_surplus_only_ems_safety_clamp = False
        pv_surplus_only_ems_safety_clamp_reason = (
            f"inactive: final export type is {export_value_gate_export_type}."
        )
        if (
            desired_export_limit > 0.01
            and pv_only_branch_high_ceiling_active
        ):
            pv_surplus_only_ems_safety_clamp = desired_ems_mode != MODE_MAX_SELF
            pv_surplus_only_ems_safety_clamp_reason = (
                "Maximum Self Consumption is required for Morning Slow Charge "
                "and Solar Surplus Bypass high export ceilings."
            )
            desired_ems_mode = MODE_MAX_SELF
        elif pv_only_branch_zero_ceiling:
            pv_surplus_only_ems_safety_clamp = desired_ems_mode != MODE_MAX_SELF
            if desired_export_source == "morning_slow_closed":
                pv_surplus_only_ems_safety_clamp_reason = (
                    "Maximum Self Consumption retained because Morning Slow "
                    "Charge owns the cycle while export waits for its PV "
                    "start/continuation threshold."
                )
            else:
                pv_surplus_only_ems_safety_clamp_reason = (
                    "Maximum Self Consumption retained because the authoritative "
                    "PV-only export ceiling is effectively closed."
                )
            desired_ems_mode = MODE_MAX_SELF
        elif pv_only_msc_stage1_active or pv_only_msc_high_ceiling_active:
            pv_surplus_only_ems_safety_clamp = desired_ems_mode != MODE_MAX_SELF
            if pv_only_msc_stage1_active:
                pv_surplus_only_ems_safety_clamp_reason = (
                    "Stage 1 commands Maximum Self Consumption while the automatic "
                    "PV-only export ceiling remains closed."
                )
            else:
                pv_surplus_only_ems_safety_clamp_reason = (
                    "Maximum Self Consumption is required for the qualifying "
                    "full-battery PV-only high export ceiling."
                )
            desired_ems_mode = MODE_MAX_SELF
        elif (
            export_value_gate_export_type == "pv_surplus_only"
            and desired_ems_mode in DISCHARGE_MODES
        ):
            pv_surplus_only_ems_safety_clamp = True
            pv_surplus_only_ems_safety_clamp_reason = (
                "forced Maximum Self Consumption because final export type is confirmed PV-only; "
                "discharge EMS is not allowed for PV-only export."
            )
            desired_ems_mode = MODE_MAX_SELF
        elif export_value_gate_export_type == "pv_surplus_only":
            pv_surplus_only_ems_safety_clamp_reason = (
                "inactive: confirmed PV-only export already uses a non-discharge EMS mode."
            )
        if (
            export_value_gate_pv_surplus_carveout_active
            and (value_gate_enforcement_active or actual_import_cost_guard_active)
            and desired_ems_mode in DISCHARGE_MODES
        ):
            # Keep below-floor PV-only carve-outs from entering a discharge/export EMS mode.
            desired_ems_mode = MODE_MAX_SELF
        if export_value_gate_vetoed and desired_ems_mode in DISCHARGE_MODES:
            desired_ems_mode = MODE_MAX_SELF
        if actual_import_cost_guard_blocking and desired_ems_mode in DISCHARGE_MODES:
            desired_ems_mode = MODE_MAX_SELF
        d.ems_mode = desired_ems_mode

        # ---- PV max power ---------------------------------------------
        desired_pv_max = self._desired_pv_max_power(
            s, standby_holdoff_active, morning_dump_active,
            morning_slow_charge_active, desired_export_limit,
        )
        d.pv_max_power_limit = desired_pv_max

        # ---- Visibility-only PV cap/curtailment diagnostics ---------
        # Diagnostic signals only. These fields must not influence live control.
        normal_pv_max_limit_kw = max(float(cfg.pv_max_power_normal or 0.0), 0.0)
        current_pv_max_limit_kw = float(
            s.current_pv_max_power_limit
            if s.current_pv_max_power_limit is not None
            else normal_pv_max_limit_kw
        )
        desired_pv_max_limit_kw = float(desired_pv_max)
        measured_pv_surplus_kw = max(float(pv_surplus_actual), 0.0)
        estimated_pv_surplus_kw = max(float(pv_surplus), 0.0)
        hidden_pv_surplus_kw = max(estimated_pv_surplus_kw - measured_pv_surplus_kw, 0.0)

        pv_cap_active = False
        pv_cap_reason = "none"
        if standby_holdoff_active:
            pv_cap_active = True
            pv_cap_reason = "standby_holdoff_active"
        elif current_pv_max_limit_kw + 0.05 < normal_pv_max_limit_kw:
            pv_cap_active = True
            pv_cap_reason = "current_pv_max_below_normal"
        elif desired_pv_max_limit_kw + 0.05 < normal_pv_max_limit_kw:
            pv_cap_active = True
            pv_cap_reason = "desired_pv_max_below_normal"

        hidden_pv_possible = bool(
            hidden_pv_surplus_kw >= 0.2
            and estimated_pv_surplus_kw >= cfg.min_grid_transfer_kw
            and pv_cap_active
        )
        pv_surplus_trusted_for_export = bool(measured_pv_surplus_kw >= cfg.min_grid_transfer_kw)
        if hidden_pv_possible:
            curtailment_diagnostic_reason = (
                "Possible hidden PV: estimated surplus exceeds measured surplus while PV may be capped. "
                "Value Gate uses measured surplus only; estimated hidden PV is diagnostic and does not bypass battery protection."
            )
        elif hidden_pv_surplus_kw >= 0.2:
            curtailment_diagnostic_reason = (
                "Estimated surplus exceeds measured surplus, but PV cap is not evident. "
                "Surplus not proven; Value Gate uses measured surplus only."
            )
        else:
            curtailment_diagnostic_reason = (
                "No possible hidden PV detected. Value Gate uses measured surplus only."
            )

        # ---- ESS charge / discharge limits --------------------------
        d.ess_charge_limit = self._desired_ess_charge_limit(
            s, desired_import_limit, morning_slow_charge_active,
            desired_export_limit, pv_surplus_actual
        )
        d.ess_discharge_limit = self._desired_ess_discharge_limit(
            s, standby_holdoff_active, positive_fit_override,
            evening_export_boost_active
        )

        # ---- Needs HA control auto-enable? --------------------------
        d.needs_ha_control_switch = (
            cfg.auto_enable_ha_control
            and s.ha_control_switch_available
            and not s.ha_control_enabled
            and (
                s.feedin_is_negative
                or desired_export_limit > 0
                or desired_import_limit > 0
                or s.current_ems_mode != desired_ems_mode
            )
        )

        # ---- Battery ETA -------------------------------------------
        # Prefer measured grid flow for battery power estimation; setpoint-based math
        # can diverge from actual inverter behavior and misreport charge/discharge.
        if s.battery_power_sensor_kw is not None:
            battery_power_kw = float(s.battery_power_sensor_kw)
            battery_power_source = "direct_battery_sensor"
            effective_import_for_math = 0.0
        elif s.grid_import_power_kw is not None and s.grid_export_power_kw is not None:
            measured_import = max(float(s.grid_import_power_kw), 0.0)
            measured_export = max(float(s.grid_export_power_kw), 0.0)
            battery_power_kw = s.pv_kw + measured_import - measured_export - s.load_kw
            battery_power_source = "measured_grid_flow"
            effective_import_for_math = measured_import
        else:
            # Keep holdoff sentinel (0.01 kW) out of analytical flow/ETA math.
            effective_import_for_math = 0.0 if desired_import_limit <= 0.011 else desired_import_limit
            battery_power_kw = s.pv_kw + (effective_import_for_math - desired_export_limit) - s.load_kw
            battery_power_source = "setpoint_balance_fallback"
        d.battery_power_kw = battery_power_kw
        d.battery_eta_formatted = self._battery_eta(s, battery_power_kw)

        # ---- Reason strings -----------------------------------------
        d.export_reason = self._export_reason(
            s, export_spike_active, export_solar_override, morning_dump_active,
            export_blocked_effective, export_forecast_guard, is_evening_or_night,
            export_min_soc, pv_safeguard_active, export_tier_limit,
            morning_slow_charge_active, solar_surplus_bypass, evening_export_boost_active,
            battery_full_safeguard_block, desired_export_limit, positive_fit_override,
        )
        if actual_import_cost_guard_blocking:
            d.export_reason = "Export vetoed by actual import-cost guard; export limit forced to 0.0 kW"
        elif export_value_gate_vetoed:
            d.export_reason = "Export vetoed by value gate enforcement; export limit forced to 0.0 kW"
        elif pv_only_branch_exception_rejected:
            if desired_export_limit > 0.01:
                d.export_reason = (
                    "PV-only high export ceiling rejected; independent "
                    f"{desired_export_source} policy selected {desired_export_limit:.1f} kW. "
                    f"{pv_only_branch_safety_reason}"
                )
            else:
                d.export_reason = (
                    "PV-only high export ceiling held closed: "
                    f"{pv_only_branch_safety_reason}"
                )
        elif pv_only_branch_zero_ceiling:
            if desired_export_source == "morning_slow_closed":
                d.export_reason = (
                    "Morning Slow Charge remains under MSC; export stays closed "
                    "until PV potential meets its start/continuation threshold."
                )
            else:
                d.export_reason = (
                    "PV-only export remains closed because the authoritative high "
                    "ceiling is at the 0.01 kW closed sentinel; MSC is retained."
                )
        elif pv_only_msc_stage1_active:
            d.export_reason = (
                "PV-only MSC transition stage 1: export remains closed while Maximum "
                "Self Consumption is commanded and must be observed on a later cycle."
            )
        elif pv_only_msc_high_ceiling_active:
            d.export_reason = (
                "PV-only MSC ceiling active: export limit set directly to "
                f"{desired_export_limit:.1f} kW; Maximum Self Consumption controls "
                "actual surplus-PV export without commanded battery discharge."
            )
        d.import_reason = self._import_reason(
            s, morning_dump_active, standby_holdoff_active,
            sunrise_soc_target, desired_import_limit, pv_surplus_actual
        )
        eta_label = ""
        if d.battery_eta_formatted not in ("idle", "Full", "Empty"):
            if battery_power_kw > 0.1:
                eta_label = f"Bat→Full:{d.battery_eta_formatted}"
            elif battery_power_kw < -0.1:
                eta_label = f"Bat→Empty:{d.battery_eta_formatted}"
        parts = [d.export_reason, d.import_reason]
        if eta_label:
            parts.append(eta_label)
        if s.price_is_estimated:
            parts.append("*est")
        d.outcome_reason = "; ".join(p for p in parts if p and p != "n/a")

        export_branch_by_source = {
            "morning_dump": "morning_dump",
            "morning_slow_closed": "morning_slow_charge",
            "morning_slow_pv_closed": "morning_slow_charge",
            "morning_slow_pv_high": "morning_slow_charge",
            "high_price_or_spike": (
                "export_spike" if export_spike_active else "high_price"
            ),
            "positive_fit_override": "positive_fit_override",
            "solar_surplus_pv_high": "solar_surplus_bypass",
            "solar_override": "solar_override",
            "ordinary_tier": "normal_tier",
        }
        export_branch = export_branch_by_source.get(
            desired_export_source,
            "blocked_or_zero" if desired_export_limit <= 0 else "normal_tier",
        )
        if morning_dump_active and desired_export_source == "morning_dump":
            export_branch = "morning_dump"
        elif pv_only_msc_stage1_active:
            export_branch = "msc_full_battery_stage1_closed"
        elif pv_only_msc_high_ceiling_active:
            export_branch = "msc_full_battery_high_ceiling"
        elif actual_import_cost_guard_blocking:
            export_branch = "actual_import_cost_guard"
        elif export_value_gate_vetoed:
            export_branch = "value_gate_veto"

        import_branch = "blocked"
        if morning_dump_active:
            import_branch = "morning_dump_block"
        elif s.demand_window_active:
            import_branch = "demand_window_block"
        elif standby_holdoff_active:
            import_branch = "standby_holdoff_block"
        elif desired_import_limit > 0 and s.price_is_negative:
            import_branch = "negative_price_import"
        elif desired_import_limit > 0:
            import_branch = "cheap_topup_import"

        d.trace_gates = {
            "is_evening_or_night": is_evening_or_night,
            "close_to_sunset": close_to_sunset,
            "within_morning_grace": within_morning_grace,
            "morning_dump_active": morning_dump_active,
            "morning_slow_charge_active": morning_slow_charge_active,
            "standby_holdoff_active": standby_holdoff_active,
            "negative_price_before_cutoff": negative_price_before_cutoff,
            "battery_can_reach_from_pv": battery_can_reach_from_pv,
            "evening_export_boost_active": evening_export_boost_active,
            "export_spike_active": export_spike_active,
            "positive_fit_override": positive_fit_override,
            "export_solar_override": export_solar_override,
            "pv_safeguard_active": pv_safeguard_active,
            "solar_surplus_bypass": solar_surplus_bypass,
            "battery_full_safeguard_block": battery_full_safeguard_block,
            "export_blocked_for_forecast": export_blocked_for_forecast,
            "export_forecast_guard": export_forecast_guard,
            "export_blocked_effective": export_blocked_effective,
            # Retained as a compatibility trace field; the legacy PV-MAX mode is removed.
            "battery_only_mode": False,
            "ha_control_switch_available": s.ha_control_switch_available,
            "needs_ha_control_switch": d.needs_ha_control_switch,
            "demand_window_active": s.demand_window_active,
            "price_is_negative": s.price_is_negative,
            "feedin_is_negative": s.feedin_is_negative,
            "export_value_gate_enabled": bool(cfg.export_value_gate_enabled),
            "export_value_gate_dry_run": bool(cfg.export_value_gate_dry_run),
            "export_value_gate_enforce": bool(cfg.export_value_gate_enforce),
            "export_value_gate_would_allow": d.export_value_gate_would_allow,
            "export_value_gate_would_block": d.export_value_gate_would_block,
            "export_value_gate_enforcement_active": value_gate_enforcement_active,
            "export_value_gate_vetoed": export_value_gate_vetoed,
            "export_value_gate_veto_active": export_value_gate_vetoed,
            "export_value_gate_applies_to_export_type": export_value_gate_applies_to_export_type,
            "export_value_gate_bypassed_for_pv_surplus_only": export_value_gate_bypassed_for_pv_surplus_only,
            "export_value_gate_pv_surplus_initiated_active": export_value_gate_pv_surplus_initiated_active,
            "export_value_gate_pv_surplus_carveout_active": export_value_gate_pv_surplus_carveout_active,
            "pv_surplus_export_allowed_below_import_floor": pv_surplus_export_allowed_below_import_floor,
            "pv_surplus_only_proven": pv_surplus_only_proven,
            "pv_surplus_estimated_init_enabled": bool(cfg.pv_surplus_estimated_init_enabled),
            "pv_surplus_estimated_init_active": pv_surplus_estimated_init_active,
            "pv_surplus_breathe_probe_active": pv_surplus_breathe_probe_active,
            "pv_surplus_breathe_probe_continuation_active": pv_surplus_breathe_probe_continuation_active,
            "sigenergy_mode_observed": s.sigenergy_mode_observed,
            "ems_mode_observed": s.ems_mode_observed,
            "observed_automated_control_mode": observed_automated_control_mode,
            "pv_only_msc_transition_ready": pv_only_msc_transition_ready,
            "pv_only_msc_stage1_active": pv_only_msc_stage1_active,
            "pv_only_msc_high_ceiling_active": pv_only_msc_high_ceiling_active,
            "morning_slow_pv_only_high_ceiling_requested": morning_slow_pv_only_high_ceiling_requested,
            "solar_surplus_pv_only_high_ceiling_requested": solar_surplus_pv_only_high_ceiling_requested,
            "pv_only_branch_high_ceiling_requested": pv_only_branch_high_ceiling_requested,
            "pv_only_branch_high_ceiling_active": pv_only_branch_high_ceiling_active,
            "pv_only_branch_battery_safety_blocked": pv_only_branch_battery_safety_blocked,
            "pv_only_branch_automated_ownership_blocked": pv_only_branch_automated_ownership_blocked,
            "pv_only_branch_exception_rejected": pv_only_branch_exception_rejected,
            "pv_only_branch_policy_deferred": pv_only_branch_policy_deferred,
            "pv_only_branch_zero_ceiling": pv_only_branch_zero_ceiling,
            "pv_only_discovery_active": False,
            "pv_only_discovery_continuation_active": False,
            "pv_only_discovery_state_active": False,
            "pv_only_discovery_state_fresh": False,
            "pv_surplus_breathe_probe_state_active": False,
            "pv_surplus_breathe_probe_state_fresh": False,
            "pv_surplus_breathe_probe_state_from_carveout": False,
            "pv_surplus_discovery_state_from_controller": False,
            "meaningful_live_export_open_for_discovery": False,
            "export_effectively_closed_for_discovery": True,
            "pv_surplus_topoff_block_active": pv_surplus_topoff_block_active,
            "topoff_target_met": topoff_target_met,
            "import_cost_floor_trusted": import_cost_floor_trusted,
            "import_cost_floor_unknown": import_cost_floor_unknown,
            "import_cost_floor_block_active": export_value_gate_block_reason in {
                "price_below_import_cost_floor",
                "import_cost_floor_untrusted",
            },
            "actual_import_cost_guard_active": actual_import_cost_guard_active,
            "actual_import_cost_guard_applies_to_export_type": actual_import_cost_guard_applies_to_export_type,
            "actual_import_cost_guard_bypassed_for_pv_surplus_only": actual_import_cost_guard_bypassed_for_pv_surplus_only,
            "actual_import_cost_guard_blocking": actual_import_cost_guard_blocking,
            "automatic_export_blocked_below_actual_import_cost": automatic_export_blocked_below_actual_import_cost,
            "pv_surplus_only_ems_safety_clamp": pv_surplus_only_ems_safety_clamp,
            "pv_only_discharge_ok": pv_only_discharge_ok,
            "pv_only_ems_safe": pv_only_ems_safe,
            "pv_cap_active": pv_cap_active,
            "hidden_pv_possible": hidden_pv_possible,
            "pv_surplus_trusted_for_export": pv_surplus_trusted_for_export,
        }
        d.trace_values = {
            "battery_soc": s.battery_soc,
            "ha_control_switch_state": s.ha_control_switch_state,
            "current_price": s.current_price,
            "feedin_price": s.feedin_price,
            "pv_kw": s.pv_kw,
            "solar_potential_kw": solar_potential_kw,
            "load_kw": s.load_kw,
            "grid_import_power_kw": s.grid_import_power_kw,
            "grid_export_power_kw": s.grid_export_power_kw,
            "pv_surplus_actual": pv_surplus_actual,
            "pv_surplus_estimated": pv_surplus,
            "cap_kwh": cap,
            "bat_fill_need_kwh": bat_fill_need_kwh,
            "soc_required": soc_required,
            "sunrise_soc_target": sunrise_soc_target,
            "sunrise_fill_need_kwh": sunrise_fill_need_kwh,
            "hours_to_sunrise": hours_to_sunrise,
            "hours_to_sunset": hours_to_sunset,
            "protected_reserve_soc": d.protected_reserve_soc,
            "export_surplus_soc": d.export_surplus_soc,
            "stored_energy_value_floor": d.stored_energy_value_floor,
            "export_value_gate_reason": d.export_value_gate_reason,
            "export_value_gate_mode": export_value_gate_mode,
            "export_value_gate_block_reason": export_value_gate_block_reason,
            "actual_import_cost_guard_reason": actual_import_cost_guard_reason,
            "pv_surplus_only_ems_safety_clamp_reason": pv_surplus_only_ems_safety_clamp_reason,
            "export_value_gate_export_type": export_value_gate_export_type,
            "export_classification_reason": export_classification_reason,
            "pv_surplus_initiation_source": pv_surplus_initiation_source,
            "pv_surplus_estimated_init_reason": pv_surplus_estimated_init_reason,
            "pv_surplus_probe_export_cap_kw": pv_surplus_probe_export_cap_kw,
            "pv_only_msc_high_ceiling_kw": pv_only_msc_high_ceiling_kw,
            "pv_only_msc_authoritative_cap_kw": pv_only_msc_authoritative_cap_kw,
            "pv_only_msc_transition_reason": pv_only_msc_transition_reason,
            "pv_only_msc_high_ceiling_reason": pv_only_msc_high_ceiling_reason,
            "pv_only_branch_source": pv_only_branch_source,
            "pv_only_branch_safety_reason": pv_only_branch_safety_reason,
            "pv_only_branch_policy_deferred_reason": pv_only_branch_policy_deferred_reason,
            "initial_desired_export_source": initial_desired_export_source,
            "desired_export_source": desired_export_source,
            "pv_only_discovery_source": "none",
            "pv_only_discovery_reason": pv_surplus_estimated_init_reason,
            "pv_only_discovery_cap_kw": 0.0,
            "pv_only_discovery_state_source": "none",
            "pv_only_discovery_state_cap_kw": 0.0,
            "pv_only_discovery_state_last_safe_cap_kw": 0.0,
            "pv_surplus_breathe_probe_state_source": "none",
            "pv_surplus_breathe_probe_state_cap_kw": 0.0,
            "pv_surplus_breathe_probe_state_age_s": None,
            "export_value_gate_fit_cents": export_value_gate_fit_cents,
            "export_value_gate_floor_cents": export_value_gate_floor_cents,
            "export_value_gate_difference_cents": export_value_gate_difference_cents,
            "export_value_gate_pv_surplus_kw": measured_pv_surplus_kw,
            "today_import_topup_kwh": today_import_topup_kwh,
            "today_highest_actual_import_price": today_highest_actual_import_price,
            "import_cost_export_floor": import_cost_export_floor,
            "effective_battery_export_floor": effective_battery_export_floor,
            "topoff_target_soc": topoff_target_soc,
            "battery_discharge_kw_for_pv_only": battery_discharge_kw_for_pv_only,
            "battery_flow_source_for_pv_only": battery_flow_source_for_pv_only,
            "pv_only_discharge_tolerance_kw": pv_only_discharge_tolerance_kw,
            "meaningful_export_open_threshold_kw": 0.0,
            "pv_cap_reason": pv_cap_reason,
            "current_pv_max_limit_kw": current_pv_max_limit_kw,
            "desired_pv_max_limit_kw": desired_pv_max_limit_kw,
            "normal_pv_max_limit_kw": normal_pv_max_limit_kw,
            "measured_pv_surplus_kw": measured_pv_surplus_kw,
            "estimated_pv_surplus_kw": estimated_pv_surplus_kw,
            "hidden_pv_surplus_kw": hidden_pv_surplus_kw,
            "curtailment_diagnostic_reason": curtailment_diagnostic_reason,
            "export_min_soc": export_min_soc,
            "export_tier_limit": export_tier_limit,
            "morning_dump_limit": morning_dump_limit,
            "desired_export_limit_pre_value_gate": desired_export_limit_pre_value_gate,
            "desired_export_limit": desired_export_limit,
            "desired_import_limit": desired_import_limit,
            "desired_ems_mode": desired_ems_mode,
            "desired_pv_max": desired_pv_max,
            "effective_import_for_math": effective_import_for_math,
            "battery_power_kw": battery_power_kw,
            "battery_power_source": battery_power_source,
            "battery_power_sensor_kw": s.battery_power_sensor_kw,
            "ess_charge_limit": d.ess_charge_limit,
            "ess_discharge_limit": d.ess_discharge_limit,
            "holdoff_entry_floor": self._holdoff_entry_floor,
            "current_export_limit": s.current_export_limit,
            "current_import_limit": s.current_import_limit,
            "current_pv_max_power_limit": s.current_pv_max_power_limit,
            "current_ems_mode": s.current_ems_mode,
            "sigenergy_mode": s.sigenergy_mode,
            "manual_mode_override": self._manual_mode_override,
            "export_branch": export_branch,
            "import_branch": import_branch,
            "cfg_morning_slow_charge_enabled": cfg.morning_slow_charge_enabled,
            "cfg_morning_slow_charge_rate_kw": cfg.morning_slow_charge_rate_kw,
            "cfg_morning_slow_export_start_margin_kw": cfg.morning_slow_export_start_margin_kw,
            "cfg_morning_slow_export_stop_margin_kw": cfg.morning_slow_export_stop_margin_kw,
            "cfg_morning_slow_export_ramp_up_step_kw": cfg.morning_slow_export_ramp_up_step_kw,
            "cfg_morning_slow_export_ramp_down_step_kw": cfg.morning_slow_export_ramp_down_step_kw,
            "cfg_morning_slow_export_probe_enabled": cfg.morning_slow_export_probe_enabled,
            "cfg_morning_slow_export_probe_step_kw": cfg.morning_slow_export_probe_step_kw,
            "cfg_morning_slow_export_probe_saturation_margin_kw": cfg.morning_slow_export_probe_saturation_margin_kw,
            "cfg_target_battery_charge": cfg.target_battery_charge,
            "cfg_max_price_threshold": cfg.max_price_threshold,
            "cfg_export_threshold_low": cfg.export_threshold_low,
            "cfg_export_threshold_medium": cfg.export_threshold_medium,
            "cfg_export_threshold_high": cfg.export_threshold_high,
            "cfg_export_limit_low": cfg.export_limit_low,
            "cfg_export_limit_medium": cfg.export_limit_medium,
            "cfg_export_limit_high": cfg.export_limit_high,
            "cfg_export_value_gate_min_floor": cfg.export_value_gate_min_floor,
            "cfg_export_value_gate_manual_import_premium": cfg.export_value_gate_manual_import_premium,
            "cfg_export_value_gate_winter_premium": cfg.export_value_gate_winter_premium,
            "cfg_export_value_gate_cooling_premium": cfg.export_value_gate_cooling_premium,
            "cfg_export_value_gate_safety_margin": cfg.export_value_gate_safety_margin,
            "cfg_export_value_gate_spike_override_threshold": cfg.export_value_gate_spike_override_threshold,
            "cfg_export_value_gate_useful_solar_offset_hours": cfg.export_value_gate_useful_solar_offset_hours,
            "cfg_min_export_target_soc": cfg.min_export_target_soc,
            "cfg_min_soc_floor": cfg.min_soc_floor,
            "cfg_sunrise_export_relax_percent": cfg.sunrise_export_relax_percent,
            "cfg_pv_max_power_normal": cfg.pv_max_power_normal,
        }

        return d

    # ------------------------------------------------------------------
    # 3. Apply decisions to Home Assistant
    # ------------------------------------------------------------------

    async def _wait_for_exact_entity_state(
        self,
        entity_id: str,
        expected: str,
        *,
        timeout_s: float = 4.0,
    ) -> bool:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_s
        while loop.time() < deadline:
            current = str(await self.ha.get_state_value(entity_id, "") or "")
            if current == expected:
                return True
            await asyncio.sleep(0.3)
        return False

    async def _wait_for_number_at_most(
        self,
        entity_id: str,
        maximum: float,
        *,
        timeout_s: float = 4.0,
        tolerance: float = 0.011,
    ) -> bool:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_s
        while loop.time() < deadline:
            raw_value = await self.ha.get_state_value(entity_id, None)
            try:
                numeric_value = float(raw_value) if raw_value is not None else None
                if (
                    numeric_value is not None
                    and math.isfinite(numeric_value)
                    and numeric_value <= maximum + tolerance
                ):
                    return True
            except (TypeError, ValueError):
                pass
            await asyncio.sleep(0.3)
        return False

    async def _apply(self, s: SolarState, d: Decision) -> None:
        cfg = self.cfg
        ha = self.ha

        async def _safe_fallback(reason: str) -> None:
            logger.error("Entering safe fallback: %s", reason)
            await ha.set_number(cfg.grid_export_limit, 0.01)
            await ha.select_option(cfg.ems_mode_select, MODE_MAX_SELF)
            await ha.set_number(cfg.grid_import_limit, 0.01)
            if cfg.ess_max_discharging_limit:
                await ha.set_number(cfg.ess_max_discharging_limit, 0.01)

        effective_mode = self._manual_mode_override or s.sigenergy_mode
        if self._manual_mode_override and s.sigenergy_mode != self._manual_mode_override:
            logger.warning(
                "Mode selector drift detected (%s -> %s); restoring manual selection",
                s.sigenergy_mode,
                self._manual_mode_override,
            )
            ok_restore = await ha.select_option(cfg.sigenergy_mode_select, self._manual_mode_override)
            if not ok_restore:
                logger.error(
                    "Failed to restore mode selector %s to %s",
                    cfg.sigenergy_mode_select,
                    self._manual_mode_override,
                )
            s.sigenergy_mode = self._manual_mode_override
            effective_mode = self._manual_mode_override

        # If in a manual mode, keep manual targets pinned when external writers drift
        # them (e.g. morning slow-charge branch in other automations).
        if effective_mode not in {cfg.automated_option, ""}:
            manual_targets = self._manual_mode_targets(
                effective_mode,
                s,
                include_block_flow_ess_limits=(effective_mode == cfg.block_flow_option),
            )
            if manual_targets:
                threshold = max(0.05, float(cfg.min_change_threshold))
                drifted_keys: list[str] = []
                if s.current_ems_mode != str(manual_targets["ems_mode"]):
                    drifted_keys.append("ems_mode")
                if abs(float(manual_targets["grid_export_limit"]) - s.current_export_limit) >= threshold:
                    drifted_keys.append("grid_export_limit")
                if abs(float(manual_targets["grid_import_limit"]) - s.current_import_limit) >= threshold:
                    drifted_keys.append("grid_import_limit")
                if abs(float(manual_targets["pv_max_power_limit"]) - s.current_pv_max_power_limit) >= threshold:
                    drifted_keys.append("pv_max_power_limit")
                if "ess_charge_limit" in manual_targets and s.current_ess_charge_limit is not None:
                    if abs(float(manual_targets["ess_charge_limit"]) - float(s.current_ess_charge_limit)) >= threshold:
                        drifted_keys.append("ess_charge_limit")
                if "ess_discharge_limit" in manual_targets and s.current_ess_discharge_limit is not None:
                    if abs(float(manual_targets["ess_discharge_limit"]) - float(s.current_ess_discharge_limit)) >= threshold:
                        drifted_keys.append("ess_discharge_limit")

                if drifted_keys:
                    logger.warning(
                        "Manual mode drift detected (%s): %s; reapplying manual targets",
                        effective_mode,
                        ", ".join(drifted_keys),
                    )
                    write_results = await self._apply_manual_mode_targets(
                        manual_targets,
                        mode_label=effective_mode,
                    )
                    failed = [name for name, ok in write_results.items() if not ok]
                    self.record_audit_event(
                        action="manual_enforce",
                        source="optimizer_cycle",
                        actor="system:optimizer",
                        result="partial" if failed else "ok",
                        old_value={
                            "ems_mode": s.current_ems_mode,
                            "grid_export_limit": s.current_export_limit,
                            "grid_import_limit": s.current_import_limit,
                            "pv_max_power_limit": s.current_pv_max_power_limit,
                            "ess_charge_limit": s.current_ess_charge_limit,
                            "ess_discharge_limit": s.current_ess_discharge_limit,
                        },
                        new_value=manual_targets,
                        details={
                            "mode": effective_mode,
                            "drifted_keys": drifted_keys,
                            "failed": failed,
                        },
                    )
                    if failed:
                        logger.error("Manual mode drift correction had failures: %s", ", ".join(failed))

            logger.debug("Manual mode active (%s); optimizer decisions paused", effective_mode)
            return
        if cfg.auto_enable_ha_control and not s.ha_control_switch_available:
            now_ts = datetime.now().timestamp()
            warning_key = (str(cfg.ha_control_switch), s.ha_control_switch_state)
            warning_due = (
                warning_key != self._last_ha_control_switch_warning_key
                or self._last_ha_control_switch_warning_at is None
                or now_ts - self._last_ha_control_switch_warning_at
                >= _HA_CONTROL_WARNING_INTERVAL_SECONDS
            )
            if warning_due:
                logger.warning(
                    "Remote EMS control switch unavailable: configured entity=%s status=%s; "
                    "automatic EMS writes are paused and no turn_on call will be made until "
                    "a real available switch entity is observed",
                    cfg.ha_control_switch,
                    s.ha_control_switch_state,
                )
                self._last_ha_control_switch_warning_at = now_ts
                self._last_ha_control_switch_warning_key = warning_key
            return

        effective_ha_control = s.ha_control_enabled

        # Auto-enable an explicitly available HA control switch if needed.
        if d.needs_ha_control_switch and not s.ha_control_enabled:
            now_ts = datetime.now().timestamp()
            last_attempt = self._last_ha_control_enable_attempt_at
            if (
                last_attempt is not None
                and now_ts - last_attempt < _HA_CONTROL_ENABLE_RETRY_SECONDS
            ):
                logger.debug(
                    "Remote EMS control switch remains off; enable retry suppressed for %s",
                    cfg.ha_control_switch,
                )
                return
            self._last_ha_control_enable_attempt_at = now_ts
            logger.info("Auto-enabling Remote EMS control switch %s", cfg.ha_control_switch)
            enable_ok = await ha.turn_on(cfg.ha_control_switch)
            if not enable_ok:
                logger.warning(
                    "Failed to enable Remote EMS control switch %s; automatic EMS writes "
                    "remain paused and retry is delayed",
                    cfg.ha_control_switch,
                )
                return
            logger.info("Remote EMS control switch enable requested successfully: %s", cfg.ha_control_switch)
            effective_ha_control = True

        if not effective_ha_control:
            return

        ems_mode_to_apply = d.ems_mode
        near_zero = 0.011
        export_val = d.export_limit if d.export_limit > 0 else 0.01
        export_turning_on = s.current_export_limit <= near_zero and export_val > near_zero
        export_turning_off = s.current_export_limit > near_zero and export_val <= near_zero
        pv_only_over_cap_correction_required = bool(
            d.requires_verified_msc_before_export
            and float(s.current_export_limit or 0.0) > export_val + 1e-6
        )
        export_write_required = bool(
            abs(export_val - s.current_export_limit) >= cfg.min_change_threshold
            or export_turning_on
            or export_turning_off
            or pv_only_over_cap_correction_required
        )
        export_written = False

        if d.requires_verified_msc_before_export:
            live_ems_mode = str(
                await ha.get_state_value(cfg.ems_mode_select, "") or ""
            ).strip()
            if live_ems_mode != MODE_MAX_SELF:
                # A previously opened ceiling must never overlap EMS drift into a
                # discharge mode while MSC is being reasserted. Close and confirm
                # export first, then reopen only after exact MSC confirmation.
                ok_close = await ha.set_number(cfg.grid_export_limit, 0.01)
                if not ok_close:
                    await _safe_fallback(
                        "failed closing export before Maximum Self Consumption transition"
                    )
                    return
                if not await self._wait_for_number_at_most(
                    cfg.grid_export_limit,
                    0.01,
                    timeout_s=3.0,
                    tolerance=0.001,
                ):
                    await _safe_fallback(
                        "export limit did not close before Maximum Self Consumption transition"
                    )
                    return
                export_write_required = True

            # The decision snapshot can race an external EMS writer. Reassert and
            # confirm exact MSC immediately before deliberately opening the high
            # automatic PV-only ceiling, even when the snapshot already reported MSC.
            ok_mode = await ha.select_option(cfg.ems_mode_select, MODE_MAX_SELF)
            if not ok_mode:
                await _safe_fallback("failed reasserting Maximum Self Consumption before high PV-only export")
                return
            if not await self._wait_for_exact_entity_state(
                cfg.ems_mode_select,
                MODE_MAX_SELF,
                timeout_s=3.0,
            ):
                await _safe_fallback("Maximum Self Consumption did not settle before high PV-only export")
                return

        prepare_export_before_discharge = bool(
            ems_mode_to_apply in DISCHARGE_MODES
            and (
                s.current_ems_mode != ems_mode_to_apply
                or export_val + 1e-6 < float(s.current_export_limit or 0.0)
            )
        )
        if prepare_export_before_discharge:
            # Never let an unobserved or higher prior export ceiling overlap a newly
            # selected discharge EMS. Write and confirm the deliberate export target
            # first; an intentional battery-export target is preserved rather than
            # replaced with an unrelated blanket low cap.
            ok_export = await ha.set_number(cfg.grid_export_limit, export_val)
            if not ok_export:
                await _safe_fallback(
                    f"failed lowering export limit to {export_val:.2f}kW before discharge EMS"
                )
                return
            if not await self._wait_for_number_at_most(
                cfg.grid_export_limit,
                export_val,
                timeout_s=3.0,
            ):
                await _safe_fallback(
                    f"export limit did not settle at or below {export_val:.2f}kW before discharge EMS"
                )
                return
            export_written = True

        # EMS mode
        if (
            not d.requires_verified_msc_before_export
            and s.current_ems_mode != ems_mode_to_apply
        ):
            logger.info("EMS mode: %s → %s", s.current_ems_mode, ems_mode_to_apply)
            ok_mode = await ha.select_option(cfg.ems_mode_select, ems_mode_to_apply)
            if not ok_mode:
                await _safe_fallback(f"failed setting EMS mode to {ems_mode_to_apply}")
                return

        # Export limit
        if export_write_required and not export_written:
            ok_export = await ha.set_number(cfg.grid_export_limit, export_val)
            if not ok_export:
                await _safe_fallback(f"failed setting export limit to {export_val:.2f}kW")
                return
            if (
                pv_only_over_cap_correction_required
                and not await self._wait_for_number_at_most(
                    cfg.grid_export_limit,
                    export_val,
                    timeout_s=3.0,
                    tolerance=0.001,
                )
            ):
                await _safe_fallback(
                    f"PV-only export limit did not settle at or below {export_val:.2f}kW"
                )
                return

        # Import limit
        import_val = 0.01 if d.import_limit == 0 else d.import_limit
        if standby := d.standby_holdoff_active:
            import_val = 0.01
        import_turning_on = s.current_import_limit <= near_zero and import_val > near_zero
        import_turning_off = s.current_import_limit > near_zero and import_val <= near_zero
        if abs(import_val - s.current_import_limit) >= cfg.min_change_threshold or import_turning_on or import_turning_off:
            ok_import = await ha.set_number(cfg.grid_import_limit, import_val)
            if not ok_import:
                await _safe_fallback(f"failed setting import limit to {import_val:.2f}kW")
                return

        # ESS charge / discharge limits
        if cfg.ess_max_charging_limit:
            ok_chg = await ha.set_number(cfg.ess_max_charging_limit, d.ess_charge_limit)
            if not ok_chg:
                logger.error("Failed setting ESS charge limit to %.2fkW", d.ess_charge_limit)
        if cfg.ess_max_discharging_limit:
            discharge_limit = d.ess_discharge_limit
            ok_dis = await ha.set_number(cfg.ess_max_discharging_limit, discharge_limit)
            if not ok_dis:
                await _safe_fallback(f"failed setting ESS discharge limit to {discharge_limit:.2f}kW")
                return

        # PV max power limit
        if abs(d.pv_max_power_limit - s.current_pv_max_power_limit) > 0.05:
            await ha.set_number(cfg.pv_max_power_limit, d.pv_max_power_limit)

        # Reason text helper
        reason = d.outcome_reason[:250]
        if reason:
            await ha.set_input_text(cfg.reason_text_helper, reason)

        # Min SoC to sunrise helper — clamp to 100 for HA entity bounds; raw value may
        # exceed 100 when overnight load exceeds full battery capacity, which is valid
        # for internal logic but rejected by input_number entities with max: 100.
        await ha.set_input_number(cfg.min_soc_to_sunrise_helper, min(d.min_soc_to_sunrise, 100.0))

        logger.debug(
            "Applied: mode=%s exp=%.1f imp=%.1f pv=%.1f | %s",
            d.ems_mode, d.export_limit, d.import_limit, d.pv_max_power_limit,
            d.outcome_reason[:80]
        )

    def _manual_mode_targets(
        self,
        mode_label: str,
        state: Optional[SolarState] = None,
        include_block_flow_ess_limits: bool = False,
    ) -> Optional[dict[str, float | str]]:
        cfg = self.cfg
        if mode_label in {cfg.automated_option, cfg.manual_option, ""}:
            return None

        import_cap, export_cap = self.get_power_caps_kw(state)
        block = cfg.block_flow_limit_value
        pv_max = cfg.pv_max_power_value

        # Use hardware caps/config baselines here; number-entity max attributes can be
        # temporarily reduced during slow-charge windows and must not leak into manual
        # mode reset targets.
        ess_charge = max(import_cap, cfg.ess_charge_limit_value)
        ess_discharge = max(export_cap, cfg.ess_discharge_limit_value)

        # Prefer explicit number-entity max attributes when available; these are
        # closer to what HA will actually accept for set_value.
        if state and self._valid_hw_cap_kw(state.ess_charge_limit_entity_max_kw):
            ess_charge = max(ess_charge, float(state.ess_charge_limit_entity_max_kw))
        if state and self._valid_hw_cap_kw(state.ess_discharge_limit_entity_max_kw):
            ess_discharge = max(ess_discharge, float(state.ess_discharge_limit_entity_max_kw))

        if mode_label == cfg.block_flow_option:
            if self._manual_ess_charge_override_kw is not None:
                ess_charge = float(self._manual_ess_charge_override_kw)
            if self._manual_ess_discharge_override_kw is not None:
                ess_discharge = float(self._manual_ess_discharge_override_kw)

        if mode_label == cfg.full_export_option:
            return {
                "ems_mode": MODE_CMD_DISCHARGE_PV,
                "grid_export_limit": export_cap,
                "grid_import_limit": block,
                "pv_max_power_limit": pv_max,
                "ess_charge_limit": ess_charge,
                "ess_discharge_limit": ess_discharge,
            }
        if mode_label == cfg.full_import_option:
            return {
                "ems_mode": MODE_CMD_CHARGE_GRID,
                "grid_export_limit": block,
                "grid_import_limit": import_cap,
                "pv_max_power_limit": pv_max,
                "ess_charge_limit": ess_charge,
                "ess_discharge_limit": ess_discharge,
            }
        if mode_label == cfg.full_import_pv_option:
            return {
                "ems_mode": MODE_CMD_CHARGE_PV,
                "grid_export_limit": block,
                "grid_import_limit": import_cap,
                "pv_max_power_limit": pv_max,
                "ess_charge_limit": ess_charge,
                "ess_discharge_limit": ess_discharge,
            }
        if mode_label == cfg.block_flow_option:
            targets = {
                "ems_mode": MODE_MAX_SELF,
                "grid_export_limit": block,
                "grid_import_limit": block,
                "pv_max_power_limit": pv_max,
            }
            if include_block_flow_ess_limits:
                targets["ess_charge_limit"] = ess_charge
                targets["ess_discharge_limit"] = ess_discharge
            return targets
        return None

    def _freeze_decision_to_live_mode(self, state: SolarState, decision: Decision, mode_label: str) -> None:
        if mode_label != self.cfg.automated_option:
            decision.requires_verified_msc_before_export = False
            decision.trace_gates["observed_automated_control_mode"] = False
            decision.trace_gates["pv_only_branch_high_ceiling_active"] = False
            decision.trace_gates["pv_only_msc_transition_ready"] = False
            decision.trace_gates["pv_only_msc_stage1_active"] = False
            decision.trace_gates["pv_only_msc_high_ceiling_active"] = False
            if decision.trace_gates.get("pv_only_branch_high_ceiling_requested"):
                decision.trace_gates["pv_only_branch_automated_ownership_blocked"] = True
                decision.trace_gates["pv_only_branch_exception_rejected"] = True
                branch_source = decision.trace_values.get("pv_only_branch_source", "PV-only branch")
                decision.trace_values["pv_only_branch_safety_reason"] = (
                    f"blocked {branch_source}: Automated ownership is unavailable "
                    "or not genuinely observed"
                )
        decision.ems_mode = state.current_ems_mode
        decision.export_limit = state.current_export_limit
        decision.import_limit = state.current_import_limit
        decision.pv_max_power_limit = state.current_pv_max_power_limit
        decision.ess_charge_limit = (
            state.current_ess_charge_limit
            if state.current_ess_charge_limit is not None
            else decision.ess_charge_limit
        )
        decision.ess_discharge_limit = (
            state.current_ess_discharge_limit
            if state.current_ess_discharge_limit is not None
            else decision.ess_discharge_limit
        )
        decision.export_reason = f"Manual mode active ({mode_label})"
        decision.import_reason = "manual"
        decision.outcome_reason = f"Manual mode active ({mode_label}); optimizer writes paused"

    def set_manual_ess_overrides(
        self,
        charge_kw: Optional[float] = None,
        discharge_kw: Optional[float] = None,
    ) -> None:
        if charge_kw is not None:
            self._manual_ess_charge_override_kw = max(0.0, float(charge_kw))
        if discharge_kw is not None:
            self._manual_ess_discharge_override_kw = max(0.0, float(discharge_kw))

    async def _apply_manual_mode_targets(
        self,
        targets: dict[str, float | str],
        mode_label: Optional[str] = None,
    ) -> dict[str, bool]:
        cfg = self.cfg
        ha = self.ha

        async def _set_number_with_retry(entity_id: str, value: float, retries: int = 3) -> bool:
            ok = await ha.set_number(entity_id, value)
            if ok:
                return True
            for attempt in range(1, retries):
                # Allow EMS mode transition and HA integration state to settle.
                await asyncio.sleep(0.7)
                ok = await ha.set_number(entity_id, value)
                if ok:
                    logger.info(
                        "Manual set_number retry succeeded for %s on attempt %d",
                        entity_id,
                        attempt + 1,
                    )
                    return True
            return False

        async def _select_mode_with_retry(entity_id: str, expected: str, retries: int = 4) -> bool:
            for attempt in range(retries):
                ok = await ha.select_option(entity_id, expected)
                if not ok:
                    await asyncio.sleep(0.5)
                    continue
                settled = await self._wait_for_exact_entity_state(
                    entity_id,
                    expected,
                    timeout_s=3.0,
                )
                if settled:
                    if attempt > 0:
                        logger.info(
                            "Manual mode settle succeeded for %s on attempt %d",
                            expected,
                            attempt + 1,
                        )
                    return True
                await asyncio.sleep(0.6)
            return False

        target_mode = str(targets["ems_mode"])
        ok_mode = await _select_mode_with_retry(cfg.ems_mode_select, target_mode)
        if not ok_mode:
            logger.warning(
                "Manual mode target apply: EMS mode did not settle to '%s'; applying non-mode limits anyway",
                target_mode,
            )

        ok_exp = await ha.set_number(cfg.grid_export_limit, float(targets["grid_export_limit"]))
        ok_imp = await ha.set_number(cfg.grid_import_limit, float(targets["grid_import_limit"]))
        ok_pv = await ha.set_number(cfg.pv_max_power_limit, float(targets["pv_max_power_limit"]))

        ok_chg = True
        if cfg.ess_max_charging_limit and "ess_charge_limit" in targets:
            retries = 4 if mode_label == cfg.block_flow_option else 2
            ok_chg = await _set_number_with_retry(
                cfg.ess_max_charging_limit,
                float(targets["ess_charge_limit"]),
                retries=retries,
            )

        ok_dis = True
        if cfg.ess_max_discharging_limit and "ess_discharge_limit" in targets:
            retries = 4 if mode_label == cfg.block_flow_option else 2
            ok_dis = await _set_number_with_retry(
                cfg.ess_max_discharging_limit,
                float(targets["ess_discharge_limit"]),
                retries=retries,
            )

        if not all([ok_mode, ok_exp, ok_imp, ok_pv, ok_chg, ok_dis]):
            logger.error(
                "Manual mode target apply had failures: mode=%s exp=%s imp=%s pv=%s chg=%s dis=%s",
                ok_mode,
                ok_exp,
                ok_imp,
                ok_pv,
                ok_chg,
                ok_dis,
            )
        return {
            "ems_mode": ok_mode,
            "grid_export_limit": ok_exp,
            "grid_import_limit": ok_imp,
            "pv_max_power_limit": ok_pv,
            "ess_charge_limit": ok_chg,
            "ess_discharge_limit": ok_dis,
        }

    # ------------------------------------------------------------------
    # 4. Manual mode application (mirrors sigenergy_manual_control.yaml)
    # ------------------------------------------------------------------

    async def apply_manual_mode(self, mode_label: str) -> None:
        """Push EMS settings for a manual mode selection."""
        cfg = self.cfg
        ha = self.ha

        async with self._control_lock:
            # Update the input_select in HA
            ok_mode_select = await ha.select_option(cfg.sigenergy_mode_select, mode_label)
            if not ok_mode_select:
                raise RuntimeError(
                    f"Failed to set mode selector {cfg.sigenergy_mode_select} to '{mode_label}'"
                )
            if mode_label == cfg.automated_option:
                self._manual_mode_override = None
                self._manual_ess_charge_override_kw = None
                self._manual_ess_discharge_override_kw = None
            else:
                self._manual_mode_override = mode_label
                if mode_label in {
                    cfg.block_flow_option,
                    cfg.full_export_option,
                    cfg.full_import_option,
                    cfg.full_import_pv_option,
                }:
                    # Preset modes should start from current capability defaults,
                    # not stale ESS overrides from prior manual edits.
                    self._manual_ess_charge_override_kw = None
                    self._manual_ess_discharge_override_kw = None
            if self._last_state is not None:
                self._last_state.sigenergy_mode = mode_label

            if mode_label == cfg.automated_option:
                # Re-enable the optimiser (nothing else needed — next tick applies)
                logger.info("Mode → Automated")
                return

            # All manual modes disable the optimizer for one cycle
            # (the next _apply will skip because sigenergy_mode != "Automated")
            logger.info("Manual mode → %s", mode_label)

            if mode_label == cfg.manual_option:
                refreshed_state = await self._read_state()
                refreshed_state.sigenergy_mode = mode_label
                self._last_state = refreshed_state
                self._manual_ess_charge_override_kw = None
                self._manual_ess_discharge_override_kw = None
                decision = self._decide(refreshed_state)
                self._freeze_decision_to_live_mode(refreshed_state, decision, mode_label)
                self._last_decision = decision
                return  # just disables optimizer, no limit changes
            # Re-read live state right before computing manual targets so stale
            # per-cycle values cannot contaminate one-shot manual writes.
            current_state = await self._read_state()
            targets = self._manual_mode_targets(
                mode_label,
                current_state,
                include_block_flow_ess_limits=(mode_label == cfg.block_flow_option),
            )
            if targets:
                write_results = await self._apply_manual_mode_targets(
                    targets,
                    mode_label=mode_label,
                )
                failed = [name for name, ok in write_results.items() if not ok]
                if mode_label == cfg.block_flow_option:
                    self.set_manual_ess_overrides(
                        charge_kw=float(targets.get("ess_charge_limit")) if "ess_charge_limit" in targets else None,
                        discharge_kw=float(targets.get("ess_discharge_limit")) if "ess_discharge_limit" in targets else None,
                    )
                else:
                    self._manual_ess_charge_override_kw = None
                    self._manual_ess_discharge_override_kw = None
                refreshed_state = await self._read_state()
                refreshed_state.sigenergy_mode = mode_label
                self._last_state = refreshed_state
                decision = self._decide(refreshed_state)
                self._freeze_decision_to_live_mode(refreshed_state, decision, mode_label)
                self._last_decision = decision
                if failed:
                    raise RuntimeError(
                        f"Manual mode target writes failed for: {', '.join(failed)}"
                    )

    # ------------------------------------------------------------------
    # Notification helpers
    # ------------------------------------------------------------------

    async def _handle_notifications(self, s: SolarState, d: Decision, prev: Optional[Decision], prev_state: Optional[SolarState] = None) -> None:
        cfg = self.cfg
        if not cfg.notification_service:
            return

        notify = lambda title, msg: self.ha.send_notification(cfg.notification_service, title, msg)
        if prev is None:
            self._notif_export_active = d.export_limit > 0.011
            self._prev_demand_window = s.demand_window_active
            self._battery_full_alert_armed = s.battery_soc < 98.0
            self._battery_empty_alert_armed = s.battery_soc > 2.0
            return

        export_session_kwh = max(0.0, s.daily_export_kwh - s.export_session_start_kwh)
        import_session_kwh = max(0.0, s.daily_import_kwh - s.import_session_start_kwh)

        # Debounce export start notifications so tiny control flaps do not spam users.
        export_near_zero = 0.011
        export_active_now = d.export_limit > export_near_zero
        export_active_prev = self._notif_export_active
        if export_active_prev is None:
            export_active_prev = prev.export_limit > export_near_zero
        export_started = (not export_active_prev) and export_active_now
        export_stopped = export_active_prev and (not export_active_now)
        self._notif_export_active = export_active_now

        # Export started
        if export_started:
            await self.ha.set_input_number(cfg.export_session_start, s.daily_export_kwh)
            await self.ha.logbook_log("SigEnergy Export",
                f"Export ENABLED → {d.export_limit:.1f} kW  FIT={s.feedin_price:.3f} $/kWh")
            now = datetime.now(timezone.utc)
            last_notice = self._last_export_start_notice_at
            if last_notice and (now - last_notice) < timedelta(minutes=20):
                logger.debug("Suppressing duplicate export started notification within cooldown window")
            else:
                self._last_export_start_notice_at = now
                if s.last_export_notification != "started":
                    if cfg.notify_export_started_stopped:
                        await notify("📤 SigEnergy: Export Started",
                            f"💲 FIT: {s.feedin_price:.3f} $/kWh\n"
                            f"⚡ Limit: {d.export_limit:.1f} kW\n"
                            f"🔋 Battery: {s.battery_soc:.0f}%\n"
                            f"🌙 Night: {d.is_evening_or_night}")
                    await self.ha.set_input_text(cfg.last_export_notification, "started")

        # Export stopped
        if export_stopped:
            await self.ha.logbook_log("SigEnergy Export",
                f"Export DISABLED → Session {export_session_kwh:.3f} kWh  FIT={s.feedin_price:.3f} $/kWh")
            if s.last_export_notification != "stopped":
                if cfg.notify_export_started_stopped:
                    await notify("🛑 SigEnergy: Export Stopped",
                        f"📤 Session: {export_session_kwh:.3f} kWh\n"
                        f"📈 Daily Total: {s.daily_export_kwh:.3f} kWh\n"
                        f"🔋 Battery: {s.battery_soc:.0f}%\n"
                        f"💲 FIT: {s.feedin_price:.3f} $/kWh")
                await self.ha.set_input_text(cfg.last_export_notification, "stopped")

        # Import started/stopped use near-zero semantics because holdoff mode uses 0.01
        near_zero = 0.011
        prev_import_active = prev.import_limit > near_zero
        now_import_active = d.import_limit > near_zero

        # Import started
        if not prev_import_active and now_import_active:
            await self.ha.set_input_number(cfg.import_session_start, s.daily_import_kwh)
            await self.ha.logbook_log("SigEnergy Import",
                f"Import ENABLED → {d.import_limit:.1f} kW  Price={s.current_price}")
            if s.last_import_notification != "started":
                if cfg.notify_import_started_stopped:
                    await notify("⚡ SigEnergy: Import Started",
                        f"💲 Price: {s.current_price:.3f} $/kWh\n"
                        f"📥 Limit: {d.import_limit:.1f} kW\n"
                        f"🔋 Battery: {s.battery_soc:.0f}%\n"
                        f"🌙 Night: {d.is_evening_or_night}")
                await self.ha.set_input_text(cfg.last_import_notification, "started")

        # Import stopped
        if prev_import_active and not now_import_active:
            await self.ha.logbook_log("SigEnergy Import",
                f"Import DISABLED → Session {import_session_kwh:.3f} kWh")
            if s.last_import_notification != "stopped":
                if cfg.notify_import_started_stopped:
                    await notify("🛑 SigEnergy: Import Stopped",
                        f"📥 Session: {import_session_kwh:.3f} kWh\n"
                        f"📈 Daily Total: {s.daily_import_kwh:.3f} kWh\n"
                        f"💲 Last price: ${s.current_price:.3f}/kWh\n"
                        f"🔋 Battery: {s.battery_soc:.0f}%")
                await self.ha.set_input_text(cfg.last_import_notification, "stopped")

        # Battery alerts
        prev_soc_was_ok = prev_state is None or prev_state.battery_soc >= d.battery_soc_required_to_sunrise
        if cfg.notify_battery_alerts and s.battery_soc < d.battery_soc_required_to_sunrise and prev_soc_was_ok:
            await notify("⚠️ Battery below reserve SoC",
                f"Battery below reserve ({d.battery_soc_required_to_sunrise:.0f}%): {s.battery_soc:.0f}%")

        # Battery full/empty anti-spam:
        # - Hysteresis arming avoids repeated alerts when SoC hovers around thresholds.
        # - Cooldown avoids notification floods from noisy sensors or restart loops.
        if s.battery_soc <= 97.0:
            self._battery_full_alert_armed = True
        if s.battery_soc >= 3.0:
            self._battery_empty_alert_armed = True

        now_utc = datetime.now(timezone.utc)
        alert_cooldown = timedelta(minutes=180)

        full_cooldown_ok = (
            self._last_battery_full_notice_at is None
            or (now_utc - self._last_battery_full_notice_at) >= alert_cooldown
        )
        empty_cooldown_ok = (
            self._last_battery_empty_notice_at is None
            or (now_utc - self._last_battery_empty_notice_at) >= alert_cooldown
        )

        if cfg.notify_battery_alerts and self._battery_empty_alert_armed and s.battery_soc <= 1.0 and empty_cooldown_ok:
            await notify("🪫 Battery Empty!", f"Battery SoC: {s.battery_soc:.0f}%")
            self._battery_empty_alert_armed = False
            self._last_battery_empty_notice_at = now_utc

        if cfg.notify_battery_alerts and self._battery_full_alert_armed and s.battery_soc >= 99.0 and full_cooldown_ok:
            await notify("🔋 Battery Full!", f"Battery SoC: {s.battery_soc:.0f}%")
            self._battery_full_alert_armed = False
            self._last_battery_full_notice_at = now_utc

        if cfg.notify_price_spike_alert and s.price_spike_active and (not prev or not prev.export_spike_active):
            await notify("📈 Price Spike Active",
                f"Buy: ${s.current_price:.3f}/kWh\nFIT: ${s.feedin_price:.3f}/kWh")

        if cfg.notify_demand_window_alert and s.demand_window_active and not self._prev_demand_window:
            await notify("⏱️ Demand Window In Effect",
                "Demand window active; import is blocked until it ends.")
        self._prev_demand_window = s.demand_window_active

    async def _handle_daily_summaries(self, s: SolarState, d: Decision) -> None:
        cfg = self.cfg
        if not cfg.notification_service:
            return
        now = datetime.now()
        notify = lambda title, msg: self.ha.send_notification(cfg.notification_service, title, msg)

        if cfg.notify_daily_summary:
            t = self._today_at(cfg.daily_summary_time)
            if abs((now - t).total_seconds()) < cfg.poll_interval_seconds:
                if self._last_daily_summary_date != now.date():
                    self._last_daily_summary_date = now.date()
                    await notify("☀️ SigEnergy Summary",
                        f"🔌 Use: {s.daily_load_kwh:.2f} kWh\n"
                        f"☀️ PV: {s.daily_pv_kwh:.2f} kWh\n"
                        f"🔋 Batt: +{s.daily_battery_charge_kwh:.2f} / -{s.daily_battery_discharge_kwh:.2f} kWh\n"
                        f"📥 Import: {s.daily_import_kwh:.2f} kWh\n"
                        f"📤 Export: {s.daily_export_kwh:.2f} kWh\n"
                        f"🔚 SoC: {s.battery_soc:.0f}%")

        if cfg.notify_morning_summary:
            t = self._today_at(cfg.morning_summary_time)
            if abs((now - t).total_seconds()) < cfg.poll_interval_seconds:
                if self._last_morning_summary_date != now.date():
                    self._last_morning_summary_date = now.date()
                    await notify("🌅 SigEnergy Morning",
                        f"☀️ PV forecast today: {s.forecast_today_kwh:.1f} kWh\n"
                        f"🔋 Batt discharge so far: {s.daily_battery_discharge_kwh:.2f} kWh\n"
                        f"🔚 SoC: {s.battery_soc:.0f}%")

    # ==================================================================
    # Private calculation helpers (pure functions; no I/O)
    # ==================================================================

    @staticmethod
    def _today_at(time_str: str) -> datetime:
        """Return today's date combined with a HH:MM or HH:MM:SS string."""
        try:
            parts = time_str.split(":")
            h, m = int(parts[0]), int(parts[1])
            s = int(parts[2]) if len(parts) > 2 else 0
            return datetime.now().replace(hour=h, minute=m, second=s, microsecond=0)
        except (ValueError, IndexError, AttributeError):
            logger.warning("Invalid time string in config: %r — using end of day", time_str)
            return datetime.now().replace(hour=23, minute=59, second=59, microsecond=0)

    def _day_window(self, s: SolarState):
        """Return (day_start_ts, day_end_ts) in Unix seconds."""
        now_ts = datetime.now().timestamp()
        sunrise_ts = s.next_sunrise_ts or now_ts
        if s.sun_above_horizon:
            actual_sunrise = sunrise_ts - 86400
        else:
            actual_sunrise = sunrise_ts
        day_start = actual_sunrise + 3600

        sunset_ts = s.next_sunset_ts or now_ts
        day_end = sunset_ts - self.cfg.evening_mode_hours_before_sunset * 3600
        return day_start, day_end

    def _battery_soc_required_to_sunrise(self, s: SolarState) -> float:
        """Dynamic overnight SoC target based on current load until sunrise."""
        cfg = self.cfg
        cap = s.battery_capacity_kwh
        sunrise_ts = s.next_sunrise_ts
        if not sunrise_ts:
            return cfg.night_reserve_soc + cfg.night_reserve_buffer

        now_ts = datetime.now().timestamp()
        sunset_ts = s.next_sunset_ts or now_ts
        if s.sun_above_horizon:
            start_ts = sunset_ts
        else:
            start_ts = now_ts

        target_ts = sunrise_ts + 3600
        hours = max(0.0, (target_ts - start_ts) / 3600)
        load_kw = s.load_kw
        energy_need_kwh = load_kw * hours * cfg.sunrise_safety_factor
        need_pct = (energy_need_kwh / cap) * 100 if cap > 0 else 0
        target = need_pct + cfg.sunrise_buffer_percent
        return max(target, cfg.sunrise_reserve_soc)

    def _manual_import_recent_for_value_gate(self) -> bool:
        # TODO: wire this to an explicit manual import or force-import audit signal when one exists.
        return False

    def _topoff_target_soc(self) -> float:
        # PV-surplus export requires a genuinely full battery; ordinary daytime
        # import top-up remains governed separately by daytime_topup_max_soc.
        return 100.0

    def _bounded_pv_only_high_ceiling(
        self,
        s: SolarState,
    ) -> tuple[float, Optional[float]]:
        authoritative_cap_kw: Optional[float] = None
        ceiling_candidates = [max(float(self.cfg.export_limit_high), 0.0)]
        if (
            s.grid_export_limit_entity_max_kw is not None
            and math.isfinite(float(s.grid_export_limit_entity_max_kw))
            and 0.0 <= float(s.grid_export_limit_entity_max_kw) <= _POWER_LIMIT_MAX_KW
        ):
            authoritative_cap_kw = float(s.grid_export_limit_entity_max_kw)
            ceiling_candidates.append(authoritative_cap_kw)

        # HAClient serialises number writes to two decimal places. Quantise down
        # so later rounding can never lift the command above the entity maximum.
        bounded_ceiling_kw = float(
            Decimal(str(min(ceiling_candidates))).quantize(
                Decimal("0.01"),
                rounding=ROUND_FLOOR,
            )
        )
        return bounded_ceiling_kw, authoritative_cap_kw

    def _battery_discharge_kw_for_pv_only_check(self, s: SolarState) -> tuple[Optional[float], str]:
        inputs = s.hvac_solar_inputs
        if inputs.live_snapshot:
            direct = inputs.battery_power
            if direct.available and direct.fresh:
                try:
                    direct_battery_power_kw = float(direct.value)
                except (TypeError, ValueError, OverflowError):
                    direct_battery_power_kw = math.nan
                if math.isfinite(direct_battery_power_kw):
                    return max(0.0, -direct_battery_power_kw), "direct_battery_sensor"

            # A present-but-stale/unusable direct sensor is not proof. Derivation is
            # allowed only when every independent power input is fresh and available;
            # this prevents unavailable PV/load values defaulted to 0.0 from looking
            # like a trustworthy zero-discharge measurement.
            derived_observations = (
                inputs.grid_import_power,
                inputs.grid_export_power,
                inputs.pv_power,
                inputs.load_power,
            )
            if not all(
                observation.available and observation.fresh
                for observation in derived_observations
            ):
                return None, "unknown"
            try:
                measured_import, measured_export, pv_kw, load_kw = (
                    float(observation.value) for observation in derived_observations
                )
            except (TypeError, ValueError, OverflowError):
                return None, "unknown"
            if not all(
                math.isfinite(value)
                for value in (measured_import, measured_export, pv_kw, load_kw)
            ):
                return None, "unknown"
            battery_power_kw = (
                pv_kw
                + max(measured_import, 0.0)
                - max(measured_export, 0.0)
                - load_kw
            )
            return max(0.0, -battery_power_kw), "measured_grid_flow"

        # Hand-built unit SolarState objects predate the freshness evidence above.
        # Preserve their finite raw-field behavior without weakening live snapshots.
        if s.battery_power_sensor_kw is not None:
            direct_battery_power_kw = float(s.battery_power_sensor_kw)
            if math.isfinite(direct_battery_power_kw):
                return max(0.0, -direct_battery_power_kw), "direct_battery_sensor"
            return None, "unknown"
        if s.grid_import_power_kw is not None and s.grid_export_power_kw is not None:
            derived_inputs = (
                float(s.grid_import_power_kw),
                float(s.grid_export_power_kw),
                float(s.pv_kw),
                float(s.load_kw),
            )
            if not all(math.isfinite(value) for value in derived_inputs):
                return None, "unknown"
            measured_import = max(derived_inputs[0], 0.0)
            measured_export = max(derived_inputs[1], 0.0)
            battery_power_kw = derived_inputs[2] + measured_import - measured_export - derived_inputs[3]
            return max(0.0, -battery_power_kw), "measured_grid_flow"
        return None, "unknown"

    def _optimizer_import_topup_summary_today(self) -> dict[str, Any]:
        return self._state_store.optimizer_import_topup_summary(
            datetime.now(self._tz).date().isoformat()
        )

    def _export_value_gate_advisory(
        self,
        s: SolarState,
        *,
        desired_export_limit: float,
        sunrise_soc_target: float,
        soc_required: float,
        productive_solar_end_ts: Optional[float],
        now_ts: float,
        export_spike_active: bool,
    ) -> dict[str, float | bool | str | None]:
        cfg = self.cfg
        fit_price = float(s.feedin_price or 0.0)
        fit_cents = fit_price * 100.0

        def _mode_text() -> str:
            if bool(cfg.export_value_gate_enabled or cfg.export_value_gate_dry_run):
                return "Advisory only"
            return "Disabled"

        gate_active = bool(cfg.export_value_gate_enabled or cfg.export_value_gate_dry_run)
        if not gate_active:
            import_summary = self._optimizer_import_topup_summary_today()
            today_highest_actual_import_price_raw = import_summary.get("today_highest_actual_import_price")
            today_highest_actual_import_price = (
                float(today_highest_actual_import_price_raw)
                if today_highest_actual_import_price_raw is not None
                else None
            )
            import_cost_export_floor = today_highest_actual_import_price
            import_cost_floor_unknown = bool(import_summary.get("import_cost_floor_unknown", False))
            return {
                "protected_reserve_soc": 0.0,
                "export_surplus_soc": 0.0,
                "stored_energy_value_floor": 0.0,
                "today_import_topup_kwh": float(import_summary.get("today_import_topup_kwh") or 0.0),
                "today_highest_actual_import_price": today_highest_actual_import_price,
                "import_cost_export_floor": import_cost_export_floor,
                "effective_battery_export_floor": import_cost_export_floor or 0.0,
                "import_cost_floor_trusted": bool(import_summary.get("import_cost_floor_trusted", True)),
                "import_cost_floor_unknown": import_cost_floor_unknown,
                "export_value_gate_would_allow": False,
                "export_value_gate_would_block": False,
                "export_value_gate_reason": "Value gate disabled.",
                "export_value_gate_block_reason": "disabled",
                "export_value_gate_mode": _mode_text(),
                "export_value_gate_fit_cents": fit_cents,
                "export_value_gate_floor_cents": 0.0,
                "export_value_gate_difference_cents": fit_cents,
            }

        cap = max(float(s.battery_capacity_kwh or 0.0), 0.1)
        useful_solar_ts = None
        if s.next_sunrise_ts:
            useful_solar_ts = s.next_sunrise_ts + max(cfg.export_value_gate_useful_solar_offset_hours, 0.0) * 3600

        start_ts = now_ts
        if productive_solar_end_ts is not None:
            start_ts = max(now_ts, productive_solar_end_ts)
        elif s.sun_above_horizon and s.next_sunset_ts:
            start_ts = max(now_ts, s.next_sunset_ts)

        if useful_solar_ts is None:
            useful_solar_hours = max(float(s.hours_to_sunrise or 0.0), 0.0) + max(
                cfg.export_value_gate_useful_solar_offset_hours,
                0.0,
            )
        else:
            useful_solar_hours = max(0.0, (useful_solar_ts - start_ts) / 3600)

        expected_load_until_useful_solar_kwh = (
            max(float(s.load_kw or 0.0), 0.0)
            * useful_solar_hours
            * max(float(cfg.sunrise_safety_factor or 0.0), 0.1)
        )
        useful_solar_soc = ((expected_load_until_useful_solar_kwh / cap) * 100.0) + cfg.sunrise_buffer_percent
        protected_reserve_soc = max(
            float(cfg.export_value_gate_min_floor),
            float(cfg.sunrise_reserve_soc),
            float(sunrise_soc_target),
            float(soc_required),
            useful_solar_soc,
        )
        export_surplus_soc = max(0.0, float(s.battery_soc) - protected_reserve_soc)

        manual_import_recent = self._manual_import_recent_for_value_gate()
        avoided_import_price = max(float(s.current_price or 0.0), float(cfg.export_threshold_low), 0.0)
        manual_import_premium = cfg.export_value_gate_manual_import_premium if manual_import_recent else 0.0
        forecast_modifier = min(
            float(cfg.export_value_gate_safety_margin),
            max(0.0, float(s.forecast_tomorrow_kwh or 0.0) - expected_load_until_useful_solar_kwh) / cap * 0.01,
        )
        stored_energy_value_floor = max(
            float(cfg.export_threshold_low),
            avoided_import_price
            + float(cfg.export_value_gate_safety_margin)
            + float(cfg.export_value_gate_winter_premium)
            + float(cfg.export_value_gate_cooling_premium)
            + manual_import_premium
            - forecast_modifier,
        )
        import_summary = self._optimizer_import_topup_summary_today()
        today_import_topup_kwh = float(import_summary.get("today_import_topup_kwh") or 0.0)
        today_highest_actual_import_price_raw = import_summary.get("today_highest_actual_import_price")
        today_highest_actual_import_price = (
            float(today_highest_actual_import_price_raw)
            if today_highest_actual_import_price_raw is not None
            else None
        )
        import_cost_export_floor = today_highest_actual_import_price
        import_cost_floor_trusted = bool(import_summary.get("import_cost_floor_trusted", True))
        import_cost_floor_unknown = bool(import_summary.get("import_cost_floor_unknown", False))
        effective_battery_export_floor = max(
            stored_energy_value_floor,
            import_cost_export_floor if import_cost_export_floor is not None else 0.0,
        )
        floor_cents = effective_battery_export_floor * 100.0
        difference_cents = fit_cents - floor_cents

        desired_export_active = desired_export_limit > 0.01
        spike_override_threshold = float(cfg.export_value_gate_spike_override_threshold)
        if spike_override_threshold <= 0:
            spike_override_threshold = float(cfg.export_spike_threshold)

        def _payload(
            *,
            would_allow: bool,
            would_block: bool,
            reason: str,
            block_reason: str,
        ) -> dict[str, float | bool | str | None]:
            return {
                "protected_reserve_soc": protected_reserve_soc,
                "export_surplus_soc": export_surplus_soc,
                "stored_energy_value_floor": stored_energy_value_floor,
                "today_import_topup_kwh": today_import_topup_kwh,
                "today_highest_actual_import_price": today_highest_actual_import_price,
                "import_cost_export_floor": import_cost_export_floor,
                "effective_battery_export_floor": effective_battery_export_floor,
                "import_cost_floor_trusted": import_cost_floor_trusted,
                "import_cost_floor_unknown": import_cost_floor_unknown,
                "export_value_gate_would_allow": would_allow,
                "export_value_gate_would_block": would_block,
                "export_value_gate_reason": reason,
                "export_value_gate_block_reason": block_reason,
                "export_value_gate_mode": _mode_text(),
                "export_value_gate_fit_cents": fit_cents,
                "export_value_gate_floor_cents": floor_cents,
                "export_value_gate_difference_cents": difference_cents,
            }

        if not desired_export_active:
            return _payload(
                would_allow=False,
                would_block=False,
                reason="No live export is active, so value gate does not apply.",
                block_reason="inactive",
            )

        if export_surplus_soc <= 0.05:
            return _payload(
                would_allow=False,
                would_block=True,
                reason=(
                    "Would block export because battery is at or below protected reserve "
                    f"{protected_reserve_soc:.1f}% for evening/load until useful solar."
                ),
                block_reason="protected_reserve",
            )

        if import_cost_floor_unknown:
            return _payload(
                would_allow=False,
                would_block=True,
                reason=(
                    "Would block export because optimizer import/top-up occurred today "
                    "while actual import price was unavailable or untrusted."
                ),
                block_reason="import_cost_floor_untrusted",
            )

        if (
            export_spike_active
            and spike_override_threshold > 0
            and float(s.feedin_price or 0.0) >= spike_override_threshold
            and float(s.feedin_price or 0.0) >= effective_battery_export_floor
        ):
            return _payload(
                would_allow=True,
                would_block=False,
                reason=(
                    "Would allow export because spike feed-in price "
                    f"{fit_cents:.0f}c/kWh exceeds override {(spike_override_threshold * 100.0):.0f}c/kWh "
                    f"and meets effective battery export floor {floor_cents:.0f}c/kWh "
                    f"with {export_surplus_soc:.1f}% above protected reserve."
                ),
                block_reason="spike_override",
            )

        if float(s.feedin_price or 0.0) >= effective_battery_export_floor:
            return _payload(
                would_allow=True,
                would_block=False,
                reason=(
                    "Would allow export because feed-in price "
                    f"{fit_cents:.0f}c/kWh meets effective battery export floor {floor_cents:.0f}c/kWh "
                    f"with {export_surplus_soc:.1f}% above protected reserve."
                ),
                block_reason="price_meets_floor",
            )

        if (
            import_cost_export_floor is not None
            and float(s.feedin_price or 0.0) < import_cost_export_floor
        ):
            return _payload(
                would_allow=False,
                would_block=True,
                reason=(
                    "Would block export because feed-in price "
                    f"{fit_cents:.0f}c/kWh is below today's highest actual optimizer import cost "
                    f"{(import_cost_export_floor * 100.0):.0f}c/kWh."
                ),
                block_reason="price_below_import_cost_floor",
            )

        return _payload(
            would_allow=False,
            would_block=True,
            reason=(
                "Would block export because feed-in price "
                f"{fit_cents:.0f}c/kWh is below effective battery export floor {floor_cents:.0f}c/kWh "
                "and battery is protected for evening/load until useful solar."
            ),
            block_reason="price_below_floor",
        )

    def _negative_price_forecast_ahead(self, s: SolarState, now_ts: float) -> bool:
        cutoff = now_ts + self.cfg.negative_price_forecast_lookahead_hours * 3600
        for f in s.price_forecast_entries:
            if not isinstance(f, dict):
                continue
            try:
                ts = self._parse_ts(forecast_entry_time(f, self.cfg.price_forecast_time_key))
                price = forecast_entry_value(f, self.cfg.price_forecast_value_key)
                if ts and ts <= cutoff and price < 0:
                    return True
            except Exception:
                pass
        return False

    def _negative_price_before_cutoff(self, s: SolarState, now_ts: float) -> bool:
        cutoff_dt = self._today_at(self.cfg.standby_holdoff_end_time)
        if datetime.now() >= cutoff_dt:
            return False
        cutoff_ts = cutoff_dt.timestamp()
        for f in s.price_forecast_entries:
            if not isinstance(f, dict):
                continue
            try:
                ts = self._parse_ts(forecast_entry_time(f, self.cfg.price_forecast_time_key))
                price = forecast_entry_value(f, self.cfg.price_forecast_value_key)
                if ts and ts <= cutoff_ts and price < 0:
                    return True
            except Exception:
                pass
        return False

    def _productive_solar_end_ts(self, s: SolarState, sunset_ts: float, now_ts: float) -> Optional[float]:
        cfg = self.cfg
        threshold = cfg.productive_solar_threshold_kw
        forecasts = s.solcast_detailed
        if not forecasts:
            return None
        found = None
        for f in reversed(forecasts):
            if not isinstance(f, dict):
                continue
            try:
                f_ts = self._parse_ts(f.get("period_start", ""))
                pv_kw = float(f.get("pv_estimate", 0))
                if f_ts and f_ts <= sunset_ts and pv_kw >= threshold:
                    found = f_ts
                    break
            except Exception:
                pass
        return found

    def _morning_dump_window(self, s: SolarState, actual_sunrise_ts: float):
        cfg = self.cfg
        day_start = actual_sunrise_ts + 3600
        hours_before = cfg.morning_dump_hours_before_sunrise
        dump_start = day_start - hours_before * 3600
        dump_end = actual_sunrise_ts + 3600
        return dump_start, dump_end

    def _morning_dump_active(self, s: SolarState, dump_start, dump_end,
                              productive_solar_end_ts, bat_fill_need_kwh, now_ts) -> bool:
        cfg = self.cfg
        if not cfg.morning_dump_enabled:
            return False
        if dump_start is None or dump_end is None:
            return False
        if not (dump_start <= now_ts <= dump_end):
            return False
        if s.battery_soc <= cfg.morning_dump_min_soc:
            return False

        # Check forecast can refill
        ns_total = 0.0
        for f in s.solcast_detailed:
            if not isinstance(f, dict):
                continue
            try:
                f_ts = self._parse_ts(f.get("period_start", ""))
                pv_kw = float(f.get("pv_estimate", 0))
                if f_ts and dump_end <= f_ts < (productive_solar_end_ts or now_ts + 86400):
                    ns_total += pv_kw * cfg.solcast_forecast_period_hours
            except Exception:
                pass
        load_need = ((productive_solar_end_ts or now_ts + 86400) - dump_end) / 3600 * s.load_kw
        return ns_total >= (bat_fill_need_kwh + load_need) * cfg.forecast_safety_charging

    def _morning_slow_charge_active(self, s: SolarState, now: datetime,
                                     now_ts: float, slow_end_ts: float) -> bool:
        if self._morning_slow_charge_runtime_disabled:
            if not self._morning_slow_disable_logged:
                logger.warning("Morning slow charge is runtime-disabled in this build")
                self._morning_slow_disable_logged = True
            return False
        cfg = self.cfg
        if not cfg.morning_slow_charge_enabled:
            return False
        target_dt = self._today_at(cfg.morning_slow_charge_until)
        if now >= target_dt or now.hour < 5:
            return False
        if not s.sun_above_horizon and now.hour < 7:
            return False
        if s.feedin_price < cfg.morning_slow_charge_min_feedin_price:
            return False

        # Use remaining-forecast energy from now; this is more robust than requiring
        # fine-grained detailed forecast bins in a narrow post-target slice.
        cap = s.battery_capacity_kwh
        bat_fill_need = max(0.0, cap - s.available_discharge_energy_kwh)
        hours_left = max((slow_end_ts - now_ts) / 3600, 0.0)
        load_need = hours_left * cfg.morning_slow_charge_base_load_kw
        required_kwh = (bat_fill_need + load_need) * cfg.forecast_safety_charging
        return s.forecast_remaining_kwh >= required_kwh

    def _evening_export_boost_active(self, s: SolarState, now_ts: float,
                                      productive_solar_end_ts, sunrise_soc_target, bat_fill_need_kwh) -> bool:
        cfg = self.cfg
        if not cfg.evening_boost_enabled:
            return False
        if productive_solar_end_ts is None or now_ts < productive_solar_end_ts:
            return False
        midnight = (datetime.now() + timedelta(days=1)).replace(hour=0, minute=0, second=0).timestamp()
        if now_ts >= midnight:
            return False

        overnight_covered = s.battery_soc > (sunrise_soc_target + 10)
        tomorrow_forecast_meets_minimum = (
            s.forecast_tomorrow_kwh >= cfg.evening_boost_min_tomorrow_forecast_kwh
        )
        tomorrow_will_refill = (
            s.forecast_tomorrow_kwh >= bat_fill_need_kwh * cfg.evening_boost_forecast_safety
        )
        # Check no high FIT forecast overnight
        tomorrow_6am = (datetime.now() + timedelta(days=1)).replace(hour=6, minute=0, second=0).timestamp()
        no_high_fit = True
        for f in s.feedin_forecast_entries:
            if not isinstance(f, dict):
                continue
            try:
                ts = self._parse_ts(forecast_entry_time(f, cfg.price_forecast_time_key))
                price = forecast_entry_value(f, cfg.feedin_forecast_value_key)
                if price is None:
                    continue
                if ts and now_ts <= ts <= tomorrow_6am and price >= cfg.export_threshold_medium:
                    no_high_fit = False
                    break
            except Exception:
                pass
        return no_high_fit and overnight_covered and tomorrow_forecast_meets_minimum and tomorrow_will_refill

    def _solar_surplus_bypass(self, s: SolarState, morning_slow_charge_active: bool,
                               cap: float, pv_surplus: float,
                               previously_active: bool = False) -> bool:
        cfg = self.cfg
        if not cfg.solar_surplus_bypass_enabled or morning_slow_charge_active:
            return False
        start_thresh = cap * cfg.solar_surplus_start_multiplier
        stop_thresh = cap * cfg.solar_surplus_stop_multiplier
        pv_over_load = pv_surplus > cfg.solar_surplus_min_pv_margin
        start_ok = s.forecast_remaining_kwh >= start_thresh
        continue_ok = (
            s.forecast_remaining_kwh >= stop_thresh
            and previously_active
        )
        return pv_over_load and (start_ok or continue_ok)

    def _battery_full_safeguard_block(self, s: SolarState, now_ts: float,
                                       sunset_ts: float, bat_fill_need_kwh: float,
                                       is_evening_or_night: bool) -> bool:
        cfg = self.cfg
        if not cfg.battery_full_safeguard_enabled or is_evening_or_night:
            return False
        if bat_fill_need_kwh <= 0:
            return False
        target_ts = sunset_ts - cfg.battery_full_hours_before_sunset * 3600
        if now_ts >= target_ts:
            return True

        # Forecast check
        ns_total = 0.0
        max_charge_kw = s.ess_max_charge_kw if 0 < s.ess_max_charge_kw < 999 else cfg.ess_charge_limit_value
        for f in s.solcast_detailed:
            if not isinstance(f, dict):
                continue
            try:
                f_ts = self._parse_ts(f.get("period_start", ""))
                pv_kw = float(f.get("pv_estimate", 0))
                if f_ts and now_ts <= f_ts < target_ts:
                    net = max(pv_kw - s.load_kw, 0.0)
                    usable = min(net, max_charge_kw) * cfg.solcast_forecast_period_hours
                    ns_total += usable
            except Exception:
                pass
        return (ns_total * cfg.battery_full_forecast_multiplier) < bat_fill_need_kwh

    def _export_blocked_for_forecast(self, s: SolarState, pv_surplus: float,
                                      is_evening_or_night: bool, bat_fill_need_kwh: float,
                                      hours_to_sunset: float, close_to_sunset: bool) -> bool:
        cfg = self.cfg
        if s.battery_soc >= cfg.export_guard_relax_soc or close_to_sunset:
            return False
        allow_full = (
            s.battery_soc >= cfg.max_battery_soc
            and not is_evening_or_night
            and pv_surplus > cfg.min_grid_transfer_kw
        )
        if is_evening_or_night or allow_full or s.forecast_remaining_kwh == 0:
            return False
        est_load = s.load_kw * hours_to_sunset
        net_fc = s.forecast_remaining_kwh - est_load
        return net_fc < bat_fill_need_kwh * cfg.forecast_safety_export

    def _export_forecast_guard(self, s: SolarState, sunrise_fill_need_kwh: float,
                                is_evening_or_night: bool, evening_boost: bool,
                                close_to_sunset: bool) -> bool:
        cfg = self.cfg
        if s.battery_soc >= cfg.export_guard_relax_soc or close_to_sunset:
            return False
        if is_evening_or_night:
            floor = cfg.evening_aggressive_floor if evening_boost else cfg.min_export_target_soc
            return s.battery_soc < floor
        if sunrise_fill_need_kwh <= 0:
            return False
        required = sunrise_fill_need_kwh * cfg.forecast_safety_export
        return s.forecast_remaining_kwh < required

    def _export_tier_limit(self, s: SolarState, spike: bool, solar_override: bool,
                            pv_safeguard: bool, boost: bool, surplus_bypass: bool) -> float:
        cfg = self.cfg
        fit = s.feedin_price
        bsoc = s.battery_soc
        below_boost_floor = bsoc < cfg.evening_aggressive_floor
        below_target = bsoc < cfg.min_export_target_soc

        if spike:
            return cfg.export_limit_high
        if solar_override:
            return cfg.export_limit_high
        if bsoc >= 99 and fit >= 0.01:
            return cfg.export_limit_high
        if fit < cfg.export_threshold_low:
            return 0.0
        if fit >= cfg.export_threshold_high:
            return cfg.export_limit_high
        if fit >= cfg.export_threshold_medium:
            if pv_safeguard:
                return 0.0
            frac = (fit - cfg.export_threshold_medium) / (cfg.export_threshold_high - cfg.export_threshold_medium)
            return cfg.export_limit_medium + frac * (cfg.export_limit_high - cfg.export_limit_medium)
        # low tier
        if boost and not below_boost_floor:
            frac = (fit - cfg.export_threshold_low) / max(cfg.export_threshold_medium - cfg.export_threshold_low, 0.001)
            return cfg.export_limit_low + frac * (cfg.export_limit_medium - cfg.export_limit_low)
        if (below_target or pv_safeguard) and not surplus_bypass:
            return 0.0
        frac = (fit - cfg.export_threshold_low) / max(cfg.export_threshold_medium - cfg.export_threshold_low, 0.001)
        return cfg.export_limit_low + frac * (cfg.export_limit_medium - cfg.export_limit_low)

    def _desired_export_limit(self, s: SolarState, spike: bool, solar_override: bool,
                               export_blocked: bool, forecast_guard: bool,
                               export_min_soc: float, positive_fit_override: bool,
                               surplus_bypass: bool, evening_boost: bool,
                               morning_dump: bool, morning_dump_limit: float,
                               battery_full_safeguard_block: bool,
                               tier_limit: float, hours_to_sunrise: float,
                               cap: float, pv_surplus: float,
                               is_evening_or_night: bool,
                               morning_slow_charge_active: bool,
                               within_morning_grace: bool) -> float:
        cfg = self.cfg
        fit_cents = s.feedin_price_cents
        bsoc = s.battery_soc

        def choice(limit_kw: float, source: str) -> _DesiredExportLimit:
            return _DesiredExportLimit(limit_kw, source)

        if fit_cents < 1:
            return choice(0.0, "closed_fit_below_minimum")

        high_price = s.feedin_price >= cfg.export_threshold_high

        if (
            battery_full_safeguard_block
            and not morning_slow_charge_active
            and not (high_price or spike)
        ):
            return choice(0.0, "closed_battery_full_safeguard")

        effective_export_floor = cfg.evening_aggressive_floor if evening_boost else cfg.min_export_target_soc

        # No PV surplus during daytime → no export
        if (pv_surplus == 0 and not is_evening_or_night and not high_price
                and not spike and not evening_boost):
            return choice(0.0, "closed_no_daytime_pv")

        if morning_dump:
            return choice(morning_dump_limit, "morning_dump")

        if s.price_is_negative or s.feedin_is_negative:
            return choice(0.0, "closed_negative_price")

        if (bsoc < effective_export_floor and not within_morning_grace
                and not morning_slow_charge_active and not surplus_bypass):
            return choice(0.0, "closed_below_export_floor")

        if (
            (export_blocked or forecast_guard)
            and not surplus_bypass
            and not morning_slow_charge_active
        ):
            return choice(0.0, "closed_forecast_guard")

        poor_tomorrow_forecast = (
            not is_evening_or_night
            and s.forecast_tomorrow_kwh < cap * cfg.forecast_safety_charging
        )

        bypass_min_soc = high_price or spike or surplus_bypass or positive_fit_override
        if not bypass_min_soc and bsoc <= export_min_soc:
            if not (morning_slow_charge_active and pv_surplus >= cfg.morning_slow_charge_rate_kw + cfg.min_grid_transfer_kw):
                return choice(0.0, "closed_below_min_soc")

        # When near the export floor, never allow battery-backed export on bypass paths.
        # Keep export limited to measured PV excess so empty batteries cannot sustain large export.
        def cap_near_floor_to_pv(limit_value: float) -> float:
            if limit_value <= 0:
                return 0.0
            if bypass_min_soc and bsoc <= (export_min_soc + 0.05):
                excess_solar_kw = max(s.pv_kw - s.load_kw, 0.0)
                return min(limit_value, excess_solar_kw)
            return limit_value

        def cap_full_battery_poor_tomorrow(limit_value: float) -> float:
            if limit_value <= 0:
                return 0.0
            if bsoc >= 99 and poor_tomorrow_forecast:
                measured_surplus_kw = max(s.pv_kw - s.load_kw, 0.0)
                return min(limit_value, measured_surplus_kw)
            return limit_value

        # Morning slow charge: keep the battery charge rate deliberately limited,
        # but let Maximum Self Consumption balance real PV surplus naturally.
        # The export setting is a ceiling, not a commanded discharge target.
        if morning_slow_charge_active:
            start_threshold = cfg.morning_slow_charge_rate_kw + cfg.morning_slow_export_start_margin_kw
            stop_threshold = cfg.morning_slow_charge_rate_kw + cfg.morning_slow_export_stop_margin_kw
            current_export = s.current_export_limit if s.current_export_limit > 0.05 else 0.0
            export_is_open = current_export >= cfg.min_grid_transfer_kw
            has_surplus_window = (
                pv_surplus >= start_threshold
                or (export_is_open and pv_surplus >= stop_threshold)
            )
            if not has_surplus_window:
                return choice(0.0, "morning_slow_closed")

            ceiling, _authoritative_cap_kw = self._bounded_pv_only_high_ceiling(s)
            if ceiling <= 0.01:
                return choice(0.0, "morning_slow_pv_closed")
            return choice(ceiling, "morning_slow_pv_high")

        if high_price or spike:
            cap_val = min(tier_limit, cfg.export_limit_high)
            if spike and cfg.export_spike_full_power:
                cap_val = max(tier_limit, cfg.cap_total_import)
            limit = min(cap_val, s.ess_max_discharge_kw)
            limit = cap_near_floor_to_pv(limit)
            limit = cap_full_battery_poor_tomorrow(limit)
            return choice(
                max(cfg.min_grid_transfer_kw, round(limit, 1)) if limit > 0 else 0.0,
                "high_price_or_spike",
            )

        if positive_fit_override:
            eff_tier = tier_limit if tier_limit > 0 else cfg.export_limit_low
            limit = min(eff_tier, s.ess_max_discharge_kw)
            limit = cap_near_floor_to_pv(limit)
            limit = cap_full_battery_poor_tomorrow(limit)
            return choice(
                max(cfg.min_grid_transfer_kw, round(limit, 1)) if limit > 0 else 0.0,
                "positive_fit_override",
            )

        # Solar-surplus bypass still respects the configured export price threshold.
        # Once export is economically permitted, Maximum Self Consumption receives
        # the configured high export ceiling and naturally limits actual export to PV.
        if surplus_bypass:
            if tier_limit <= 0:
                return choice(0.0, "solar_surplus_closed")
            ceiling, _authoritative_cap_kw = self._bounded_pv_only_high_ceiling(s)
            if ceiling <= 0.01:
                return choice(0.0, "solar_surplus_pv_closed")
            return choice(ceiling, "solar_surplus_pv_high")

        if tier_limit <= 0:
            return choice(0.0, "closed_tier")

        # Scale by SoC headroom
        diff = bsoc - export_min_soc
        span = max(self._export_soc_span_dynamic(s, hours_to_sunrise, is_evening_or_night, cap), 0.1)
        scale_soc = max(0.0, min(1.0, diff / span))

        if solar_override:
            surplus_kw = max(s.pv_kw - s.load_kw, 0.0)
            override_cap = min(surplus_kw, cfg.export_limit_high, tier_limit)
            limit = min(override_cap, s.ess_max_discharge_kw)
            return choice(round(limit, 1) if limit > 0 else 0.0, "solar_override")

        hours = max(hours_to_sunrise, 0.01)
        discharge_window = max(cfg.export_discharge_window_hours, 1.0)
        hours_div = min(hours, discharge_window)
        headroom_kwh = (diff / 100) * cap
        safe_kw_base = headroom_kwh / max(hours_div, 1.0)
        boost_fac = min(1.5, 1 + (tier_limit / max(cfg.export_limit_high, 1.0)) * 0.3)
        safe_kw = safe_kw_base * boost_fac
        safe_cap = min(safe_kw, tier_limit)
        raw_limit = tier_limit * scale_soc * 0.9
        final_limit = min(raw_limit, safe_cap)
        limit = min(final_limit, s.ess_max_discharge_kw)

        # PV surplus cap during normal daytime
        if not is_evening_or_night and not high_price and not spike:
            if bsoc >= 99:
                pv_surplus_full = max(max(s.pv_kw, s.solar_power_now_kw) - s.load_kw, 0.0)
                limit = min(limit, pv_surplus_full)
            else:
                raw_surplus = max(s.pv_kw - s.load_kw, 0.0)
                max_charge = cfg.target_battery_charge
                charge_priority = 0 if surplus_bypass else (max_charge if bsoc < 98 else 0)
                pv_surplus_net = max(raw_surplus - charge_priority, 0.0)
                limit = min(limit, pv_surplus_net)

        limit = cap_near_floor_to_pv(limit)
        limit = cap_full_battery_poor_tomorrow(limit)

        if limit <= 0:
            return choice(0.0, "closed_ordinary")
        if limit < cfg.min_grid_transfer_kw:
            return choice(cfg.min_grid_transfer_kw, "ordinary_tier")
        return choice(round(limit, 1), "ordinary_tier")

    def _desired_import_limit(self, s: SolarState, morning_dump_active: bool,
                               demand_window_active: bool, standby_holdoff_active: bool,
                               feedin_price_ok: bool,
                               pv_surplus: float) -> float:
        cfg = self.cfg
        if morning_dump_active or demand_window_active:
            return 0.0
        if standby_holdoff_active:
            return 0.0

        # Negative price → full import
        if s.price_is_negative and s.current_price <= cfg.import_threshold_low:
            rated = s.ess_max_charge_kw
            if s.current_price <= cfg.import_threshold_high:
                return min(cfg.import_limit_high, rated)
            if s.current_price <= cfg.import_threshold_medium:
                return min(cfg.import_limit_medium, rated)
            return min(cfg.import_limit_low, rated)

        # Positive FIT → block import
        if feedin_price_ok:
            return 0.0

        # Price too high or battery at max
        if s.current_price > cfg.max_price_threshold:
            return 0.0

        # Battery full for topup
        if s.battery_soc >= cfg.daytime_topup_max_soc:
            return 0.0

        # PV sufficient
        if pv_surplus >= cfg.target_battery_charge:
            return 0.0

        # Cheap top-up
        if s.current_price <= cfg.max_price_threshold:
            return min(cfg.target_battery_charge, s.ess_max_charge_kw, cfg.cap_total_import)

        return 0.0

    def _desired_ems_mode(self, s: SolarState, morning_dump: bool, standby_holdoff: bool,
                           export_solar_override: bool, desired_export: float,
                           desired_import: float, export_min_soc: float,
                           sunrise_soc_target: float, within_morning_grace: bool,
                           export_blocked_forecast: bool,
                           is_evening_or_night: bool) -> str:
        cfg = self.cfg
        bsoc = s.battery_soc
        currently_discharging = s.current_ems_mode in DISCHARGE_MODES
        currently_charging = s.current_ems_mode in CHARGE_MODES

        def _charge_mode():
            if within_morning_grace and s.pv_kw < s.load_kw * 0.5:
                return MODE_MAX_SELF
            return MODE_CMD_CHARGE_PV

        if morning_dump:
            return MODE_CMD_DISCHARGE_PV
        if s.demand_window_active:
            return MODE_CMD_DISCHARGE_PV if desired_export > 0 else MODE_MAX_SELF
        if standby_holdoff and desired_export == 0:
            # Use stored floor from holdoff entry to avoid drift from forecast updates
            holdoff_discharge_floor = self._holdoff_entry_floor or (sunrise_soc_target + cfg.soc_hysteresis)
            return MODE_MAX_SELF if bsoc < holdoff_discharge_floor else MODE_CMD_DISCHARGE_PV
        if desired_import > 0 and not s.price_is_negative:
            return _charge_mode()
        if export_solar_override:
            return MODE_CMD_DISCHARGE_PV
        if s.price_is_negative and s.current_price <= cfg.import_threshold_low:
            return MODE_CMD_CHARGE_GRID
        if s.feedin_is_negative:
            return MODE_MAX_SELF
        if desired_export > 0:
            return MODE_CMD_DISCHARGE_PV
        if not export_blocked_forecast and bsoc > export_min_soc + cfg.soc_hysteresis:
            pv_surplus = max(s.pv_kw - s.load_kw, 0.0)
            if pv_surplus == 0 and not is_evening_or_night:
                return MODE_MAX_SELF
            if currently_discharging and s.feedin_price >= cfg.export_threshold_low * cfg.export_hysteresis_percent:
                return MODE_CMD_DISCHARGE_PV
            if s.feedin_price >= cfg.export_threshold_low:
                return MODE_CMD_DISCHARGE_PV
            return MODE_MAX_SELF
        # Cheap import conditions
        grid_limit_base = self._grid_limit_base(s, standby_holdoff)
        if (grid_limit_base > 0
                and s.feedin_price < cfg.export_threshold_low - cfg.price_hysteresis
                and bsoc < cfg.max_battery_soc - cfg.soc_hysteresis):
            return _charge_mode()
        if (currently_charging and grid_limit_base > 0
                and s.feedin_price < cfg.export_threshold_low + cfg.price_hysteresis
                and bsoc < cfg.max_battery_soc):
            return _charge_mode()
        return MODE_MAX_SELF

    def _grid_limit_base(self, s: SolarState, standby_holdoff_active: bool) -> float:
        """Determines base import limit before adjustments."""
        cfg = self.cfg
        price = s.current_price
        fit = s.feedin_price
        bsoc = s.battery_soc

        spike_low_soc = s.price_spike_active and bsoc < cfg.export_spike_min_soc
        if s.demand_window_active:
            return 0.0
        if price <= cfg.import_threshold_high and s.price_is_actual:
            return min(cfg.import_limit_high, s.ess_max_charge_kw)
        if price <= cfg.import_threshold_medium and s.price_is_actual:
            return min(cfg.import_limit_medium, s.ess_max_charge_kw)
        if price <= cfg.import_threshold_low and s.price_is_actual:
            return min(cfg.import_limit_low, s.ess_max_charge_kw)
        if standby_holdoff_active:
            return 0.0
        if spike_low_soc:
            return 0.0
        if fit >= cfg.export_threshold_low:
            return 0.0
        # Cheap topup
        if (price <= cfg.max_price_threshold
                and bsoc < cfg.daytime_topup_max_soc
                and s.forecast_remaining_kwh < s.battery_capacity_kwh * cfg.forecast_safety_charging):
            surplus = max(s.pv_kw - s.load_kw, 0.0)
            if surplus < cfg.target_battery_charge:
                return min(cfg.target_battery_charge, cfg.cap_total_import)
        return 0.0

    def _desired_pv_max_power(self, s: SolarState, standby_holdoff: bool,
                               morning_dump: bool, morning_slow_charge: bool,
                               desired_export: float) -> float:
        cfg = self.cfg
        cover_load = min(s.load_kw * 1.2, cfg.pv_max_power_normal)
        cover_load = max(round(cover_load, 0), 0.1)

        if s.price_is_negative and s.current_price <= cfg.import_threshold_low:
            return 0.1
        if standby_holdoff and desired_export == 0:
            return max(cover_load, 0.1)
        if morning_dump:
            return cfg.pv_max_power_normal
        if morning_slow_charge:
            # Never cap PV potential during morning slow-charge. Capping based on
            # measured PV can lock the inverter into a low-production equilibrium.
            return cfg.pv_max_power_normal
        return cfg.pv_max_power_normal

    def _desired_ess_charge_limit(self, s: SolarState, desired_import: float,
                                   morning_slow_charge: bool, desired_export: float,
                                   pv_surplus: float) -> float:
        cfg = self.cfg
        hw_charge, _ = self.get_power_caps_kw(s)
        max_charge = max(0.1, hw_charge)
        if desired_import > 0:
            return min(max_charge, desired_import)
        if morning_slow_charge:
            slow = cfg.morning_slow_charge_rate_kw
            # Keep true slow-charge behavior; avoid charge spikes that collapse export.
            return round(min(slow, max_charge), 1)
        return max_charge

    def _desired_ess_discharge_limit(self, s: SolarState, standby_holdoff: bool,
                                      positive_fit_override: bool, evening_boost: bool) -> float:
        cfg = self.cfg
        _, hw_discharge = self.get_power_caps_kw(s)
        max_dis = max(0.1, hw_discharge)
        if s.price_is_negative and s.current_price <= cfg.import_threshold_low:
            return 0.01
        if positive_fit_override and s.battery_soc < cfg.min_export_target_soc:
            if evening_boost and s.battery_soc >= cfg.evening_aggressive_floor:
                return max_dis
            return 0.01
        if positive_fit_override:
            return max_dis if cfg.allow_positive_fit_battery_discharging else 0.01
        return max_dis

    def _export_soc_span_dynamic(self, s: SolarState, hours_to_sunrise: float,
                                  is_evening_or_night: bool, cap: float) -> float:
        if is_evening_or_night:
            span = (hours_to_sunrise * s.load_kw / max(cap, 0.1)) * 100
            return max(4.0, min(span, 25.0))
        return self.cfg.export_soc_span_day

    def _battery_eta(self, s: SolarState, battery_power_kw: float) -> str:
        bsoc = s.battery_soc
        if bsoc >= 100:
            return "Full"
        if bsoc <= 0:
            return "Empty"
        power_abs = abs(battery_power_kw)
        if power_abs < 0.2:
            return "idle"
        cap = s.battery_capacity_kwh
        if battery_power_kw > 0:
            soc_gap = 100 - bsoc
            if soc_gap <= 0:
                return "Full"
            mins = (cap * soc_gap / 100) / power_abs * 60
        else:
            avail = s.available_discharge_energy_kwh
            if avail <= 0:
                return "Empty"
            mins = avail / power_abs * 60
        if mins > 48 * 60:
            return "idle"
        mins = max(1, round(mins))
        if mins >= 1440:
            d = mins // 1440
            h = (mins % 1440) // 60
            return f"{d}d{h}h"
        if mins >= 60:
            h = mins // 60
            m = mins % 60
            return f"{h}h{m}m"
        return f"{mins}m"

    def _export_reason(self, s: SolarState, spike: bool, solar_override: bool,
                        morning_dump: bool, export_blocked: bool, forecast_guard: bool,
                        is_evening_or_night: bool, export_min_soc: float,
                        pv_safeguard: bool, tier_limit: float, morning_slow_charge: bool,
                        surplus_bypass: bool, evening_boost: bool, safeguard: bool,
                        desired_export: float,
                        positive_fit_override: bool) -> str:
        cfg = self.cfg
        fit = s.feedin_price_cents
        c = s.current_price_cents
        fit_d = f"{fit:.0f}" if abs(fit) >= 1 else f"{fit:.1f}"
        c_d = f"{c:.0f}" if abs(c) >= 1 else f"{c:.1f}"
        est = "*" if s.price_is_estimated else ""
        ex_low = cfg.export_threshold_low * cfg.price_multiplier
        ex_low_d = f"{ex_low:.0f}" if abs(ex_low) >= 1 else f"{ex_low:.1f}"
        measured_export = s.grid_export_power_kw if isinstance(s.grid_export_power_kw, (int, float)) else None
        actual_export = max(float(measured_export), 0.0) if measured_export is not None else max(s.pv_kw - s.load_kw, 0.0)
        target_export = max(float(desired_export or 0.0), 0.0)
        export_kw_label = f"{actual_export:.1f}kW"
        if target_export > 0.01 and abs(actual_export - target_export) >= 0.2:
            export_kw_label = f"{actual_export:.1f}kW (set {target_export:.1f})"

        if s.price_is_negative:
            return f"Export blocked, price is negative ({c_d}¢{est})"
        if s.feedin_price_cents < 1:
            return f"Export blocked, FIT zero/negative ({fit_d}¢{est})"
        if (
            safeguard
            and not morning_slow_charge
            and not (s.feedin_price >= cfg.export_threshold_high or spike)
        ):
            return f"Export blocked, saving for sunset ({s.battery_soc:.0f}% < 100%)"
        if morning_dump:
            return f"Exporting {export_kw_label}, Morning dump @ {fit_d}¢{est}, {s.battery_soc:.0f}%"
        if s.feedin_price >= cfg.export_threshold_high:
            return f"Exporting {export_kw_label}, High tier @ {fit_d}¢{est}"
        if spike:
            return f"Exporting {export_kw_label}, Spike @ {fit_d}¢{est}"
        if solar_override:
            return f"Exporting {export_kw_label}, Solar override{est}"
        if morning_slow_charge:
            return f"Exporting {export_kw_label}, Slow charge"
        if surplus_bypass:
            if target_export <= 0.01:
                if s.feedin_price < cfg.export_threshold_low:
                    return (
                        f"Solar bypass active; export held because FIT {fit_d}c{est} "
                        f"is below {ex_low_d}c threshold"
                    )
                if actual_export > 0.05:
                    return f"Solar bypass active, export settling; measured {actual_export:.1f}kW"
                return f"Solar bypass active, export currently closed"
            return f"Exporting {export_kw_label}, Solar bypass ({s.forecast_remaining_kwh:.1f}kWh left){est}"
        effective_floor = cfg.evening_aggressive_floor if evening_boost else cfg.min_export_target_soc
        if is_evening_or_night and forecast_guard and s.battery_soc < effective_floor:
            return f"Export blocked, below {effective_floor:.0f}% target"
        if (export_blocked or forecast_guard) and not surplus_bypass:
            return "Export blocked, low forecast"
        if s.battery_soc <= export_min_soc:
            return f"Export blocked, at {export_min_soc:.0f}% floor"
        if s.battery_soc < effective_floor:
            return f"Export blocked, below {effective_floor:.0f}% target"
        poor_tomorrow_forecast = (
            s.sun_above_horizon
            and s.forecast_tomorrow_kwh < s.battery_capacity_kwh * cfg.forecast_safety_charging
        )
        if poor_tomorrow_forecast and target_export <= 0.01:
            return "Export blocked, low tomorrow forecast"
        if poor_tomorrow_forecast and target_export > 0.01:
            return f"Exporting {export_kw_label}, PV-only (low tomorrow forecast){est}"
        if s.battery_soc >= 99 and s.feedin_price >= 0.01:
            return f"Exporting {export_kw_label}, Full battery @ {fit_d}¢{est}"
        if tier_limit <= 0:
            if pv_safeguard:
                return "Export blocked, forecast protection"
            return f"Export blocked, FIT {fit_d}¢{est} < {ex_low_d}¢"
        if s.feedin_price >= cfg.export_threshold_medium:
            return f"Exporting {export_kw_label}, Med tier @ {fit_d}¢{est}"
        if evening_boost:
            return f"Exporting {export_kw_label}, Low tier (boost) @ {fit_d}¢{est}"
        return f"Exporting {export_kw_label}, Low tier @ {fit_d}¢{est}"

    def _import_reason(self, s: SolarState, morning_dump: bool, standby_holdoff: bool,
                        sunrise_soc_target: float, desired_import: float,
                        pv_surplus: float) -> str:
        cfg = self.cfg
        c = s.current_price_cents
        c_d = f"{c:.0f}" if abs(c) >= 1 else f"{c:.1f}"
        est = "*" if s.price_is_estimated else ""
        ex_low = cfg.export_threshold_low * cfg.price_multiplier
        ex_low_d = f"{ex_low:.0f}" if abs(ex_low) >= 1 else f"{ex_low:.1f}"
        fit = s.feedin_price_cents
        fit_d = f"{fit:.0f}" if abs(fit) >= 1 else f"{fit:.1f}"

        if morning_dump:
            return "Import blocked, morning dump"
        if s.demand_window_active:
            return "Import blocked, demand window"
        if standby_holdoff:
            return "Import blocked, charge holdoff"
        if not (s.price_is_actual or s.price_is_estimated):
            return "Import blocked, price N/A"
        if s.price_is_actual and s.current_price <= 0:
            if s.current_price < 0:
                return f"Importing, paid price={c_d}¢"
            return "Importing, FREE"
        if s.feedin_price >= cfg.export_threshold_low:
            return f"Import blocked, FIT {fit_d}¢{est} > export min {ex_low_d}¢"
        if s.current_price > cfg.max_price_threshold and s.battery_soc >= sunrise_soc_target:
            return f"Import blocked, price too high ({c_d}¢{est})"
        if desired_import <= 0:
            if s.current_price > cfg.max_price_threshold:
                return f"Import blocked, price too high ({c_d}¢{est})"
            if s.battery_soc >= cfg.daytime_topup_max_soc:
                return "Import blocked, battery full"
            if pv_surplus >= cfg.target_battery_charge:
                return "Import blocked, PV sufficient"
            return "Import blocked, forecast sufficient"
        if s.price_is_negative:
            return f"Importing, paid price={c_d}¢"
        return f"Importing, cheap {c_d}¢{est}"

    @staticmethod
    def _parse_ts(value) -> Optional[float]:
        if not value:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            pass
        try:
            s = str(value).replace("Z", "+00:00")
            return datetime.fromisoformat(s).timestamp()
        except Exception:
            return None
