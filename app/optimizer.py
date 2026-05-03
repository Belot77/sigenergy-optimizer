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
import logging
import os
from datetime import datetime, time, timedelta, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import Settings
from .earnings import EarningsService
from .ha_client import HAClient
from .models import Decision, SolarState
from .state_reader import read_state_snapshot
from .action_applier import apply_decision
from .decision_engine import build_decision
from .notification_service import handle_notifications, handle_daily_summaries
from .manual_mode_service import (
    manual_mode_targets,
    freeze_decision_to_live_mode,
    apply_manual_mode_targets,
)
from .telemetry_service import (
    record_price_tracking,
    record_decision_trace,
    record_automation_audit,
    accumulate_history,
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

# Config attribute names whose entity IDs should trigger immediate cycles
_TRIGGER_ENTITY_ATTRS = [
    "pv_power_sensor",
    "consumed_power_sensor",
    "battery_soc_sensor",
    "price_sensor",
    "feedin_sensor",
    "demand_window_sensor",
    "price_spike_sensor",
    "sigenergy_mode_select",
]

_POWER_LIMIT_MAX_KW = 100.0
_RUNTIME_SIGNATURE = "2.2.06-haos21-msc-enabled"


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
        self._holdoff_entry_floor: Optional[float] = None  # Stable SoC floor for holdoff window
        self._last_hw_charge_cap_kw: Optional[float] = None
        self._last_hw_discharge_cap_kw: Optional[float] = None
        self._last_cycle_started: Optional[datetime] = None
        self._last_cycle_completed: Optional[datetime] = None
        self._last_cycle_error: str = ""
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
            self._record_automation_audit(state, decision, prev_decision)
            self._record_decision_trace(state, decision)
            await self._handle_notifications(state, decision, prev_decision, prev_state)
            await self._handle_daily_summaries(state, decision)
            self._accumulate_history(state, decision)
            self._record_price_tracking(state)

    def _record_price_tracking(self, s: SolarState) -> None:
        record_price_tracking(self, s)

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
        record_decision_trace(self, s, d)

    def _record_automation_audit(self, s: SolarState, d: Decision, prev: Optional[Decision]) -> None:
        record_automation_audit(self, s, d, prev)

    def _accumulate_history(self, s, d) -> None:
        accumulate_history(self, s, d)

    # ------------------------------------------------------------------
    # 1. Read all HA entities into a SolarState snapshot
    # ------------------------------------------------------------------

    async def _read_state(self) -> SolarState:
        return await read_state_snapshot(self, mode_max_self=MODE_MAX_SELF)

    # ------------------------------------------------------------------
    # 2. Pure decision logic
    # ------------------------------------------------------------------

    def _decide(self, s: SolarState) -> Decision:
        return build_decision(self, s, mode_max_self=MODE_MAX_SELF)

    # ------------------------------------------------------------------
    # 3. Apply decisions to Home Assistant
    # ------------------------------------------------------------------

    async def _apply(self, s: SolarState, d: Decision) -> None:
        await apply_decision(self, s, d, mode_max_self=MODE_MAX_SELF)

    def _manual_mode_targets(
        self,
        mode_label: str,
        state: Optional[SolarState] = None,
        include_block_flow_ess_limits: bool = False,
    ) -> Optional[dict[str, float | str]]:
        return manual_mode_targets(
            self,
            mode_label,
            mode_max_self=MODE_MAX_SELF,
            mode_cmd_discharge_pv=MODE_CMD_DISCHARGE_PV,
            mode_cmd_charge_grid=MODE_CMD_CHARGE_GRID,
            mode_cmd_charge_pv=MODE_CMD_CHARGE_PV,
            state=state,
            include_block_flow_ess_limits=include_block_flow_ess_limits,
        )

    def _freeze_decision_to_live_mode(self, state: SolarState, decision: Decision, mode_label: str) -> None:
        freeze_decision_to_live_mode(state, decision, mode_label)

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
        return await apply_manual_mode_targets(self, targets, mode_label)

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
        await handle_notifications(self, s, d, prev, prev_state)

    async def _handle_daily_summaries(self, s: SolarState, d: Decision) -> None:
        await handle_daily_summaries(self, s, d)

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

    def _negative_price_forecast_ahead(self, s: SolarState, now_ts: float) -> bool:
        cutoff = now_ts + self.cfg.negative_price_forecast_lookahead_hours * 3600
        for f in s.price_forecast_entries:
            if not isinstance(f, dict):
                continue
            try:
                ts = self._parse_ts(f.get(self.cfg.price_forecast_time_key, ""))
                price = float(f.get(self.cfg.price_forecast_value_key, 0))
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
                ts = self._parse_ts(f.get(self.cfg.price_forecast_time_key, ""))
                price = float(f.get(self.cfg.price_forecast_value_key, 0))
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
        if s.feedin_price <= cfg.morning_slow_charge_min_feedin_price:
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
                ts = self._parse_ts(f.get(cfg.price_forecast_time_key, ""))
                price = float(f.get(cfg.feedin_forecast_value_key, 0))
                if ts and now_ts <= ts <= tomorrow_6am and price >= cfg.export_threshold_medium:
                    no_high_fit = False
                    break
            except Exception:
                pass
        return no_high_fit and overnight_covered and tomorrow_forecast_meets_minimum and tomorrow_will_refill

    def _solar_surplus_bypass(self, s: SolarState, morning_slow_charge_active: bool,
                               cap: float, pv_surplus: float, prev_desired_mode: str = "") -> bool:
        cfg = self.cfg
        if not cfg.solar_surplus_bypass_enabled or morning_slow_charge_active:
            return False
        start_thresh = cap * cfg.solar_surplus_start_multiplier
        stop_thresh = cap * cfg.solar_surplus_stop_multiplier
        pv_over_load = pv_surplus > cfg.solar_surplus_min_pv_margin
        start_ok = s.forecast_remaining_kwh >= start_thresh
        continue_ok = (
            s.forecast_remaining_kwh >= stop_thresh
            and (s.current_ems_mode in DISCHARGE_MODES or prev_desired_mode in DISCHARGE_MODES)
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

        if fit_cents < 1:
            return 0.0

        high_price = s.feedin_price >= cfg.export_threshold_high

        if battery_full_safeguard_block and not (high_price or spike):
            return 0.0

        effective_export_floor = cfg.evening_aggressive_floor if evening_boost else cfg.min_export_target_soc

        # No PV surplus during daytime → no export
        if (pv_surplus == 0 and not is_evening_or_night and not high_price
                and not spike and not evening_boost):
            return 0.0

        if morning_dump:
            return morning_dump_limit

        if s.price_is_negative or s.feedin_is_negative:
            return 0.0

        if (bsoc < effective_export_floor and not within_morning_grace
                and not morning_slow_charge_active and not surplus_bypass):
            return 0.0

        if (export_blocked or forecast_guard) and not surplus_bypass:
            return 0.0

        bypass_min_soc = high_price or spike or surplus_bypass or positive_fit_override
        if not bypass_min_soc and bsoc <= export_min_soc:
            if not (morning_slow_charge_active and pv_surplus >= cfg.morning_slow_charge_rate_kw + cfg.min_grid_transfer_kw):
                return 0.0

        # When near the export floor, never allow battery-backed export on bypass paths.
        # Keep export limited to measured PV excess so empty batteries cannot sustain large export.
        def cap_near_floor_to_pv(limit_value: float) -> float:
            if limit_value <= 0:
                return 0.0
            if bypass_min_soc and bsoc <= (export_min_soc + 0.05):
                excess_solar_kw = max(s.pv_kw - s.load_kw, 0.0)
                return min(limit_value, excess_solar_kw)
            return limit_value

        # Morning slow charge with PV surplus
        if morning_slow_charge_active:
            start_threshold = cfg.morning_slow_charge_rate_kw + cfg.morning_slow_export_start_margin_kw
            stop_threshold = cfg.morning_slow_charge_rate_kw + cfg.morning_slow_export_stop_margin_kw
            current_export = s.current_export_limit if s.current_export_limit > 0.05 else 0.0
            measured_export = max(0.0, float(s.grid_export_power_kw or 0.0))
            actual_surplus = max(s.pv_kw - s.load_kw, 0.0)
            export_is_open = current_export >= cfg.min_grid_transfer_kw
            has_surplus_window = pv_surplus >= start_threshold or (export_is_open and pv_surplus >= stop_threshold)
            if not has_surplus_window:
                return 0.0

            # Export can use PV left after honoring slow-charge target; avoid double-subtracting min transfer.
            available = max(actual_surplus - cfg.morning_slow_charge_rate_kw, 0.0)
            raw_limit = min(available, s.ess_max_discharge_kw)

            # If measured export is above real PV surplus, battery is assisting export.
            # Collapse toward PV-only export immediately instead of ramping/probing upward.
            battery_assist_detected = measured_export > (actual_surplus + 0.3)

            # Anti-curtailment probe: if export is already saturated at its own cap,
            # gently nudge the cap upward so PV can reveal hidden headroom.
            probe_enabled = bool(cfg.morning_slow_export_probe_enabled)
            saturation_margin = max(0.05, cfg.morning_slow_export_probe_saturation_margin_kw)
            probe_step = max(0.1, cfg.morning_slow_export_probe_step_kw)
            near_export_cap = measured_export >= max(cfg.min_grid_transfer_kw, current_export - saturation_margin)
            no_grid_import_pressure = (s.grid_import_power_kw is None) or (float(s.grid_import_power_kw) <= 0.2)
            if (probe_enabled and export_is_open and near_export_cap and no_grid_import_pressure
                    and not battery_assist_detected):
                raw_limit = max(raw_limit, current_export + probe_step)

            # Never allow probe logic to exceed true PV-leftover availability.
            raw_limit = min(raw_limit, available)

            raw_limit = min(raw_limit, s.ess_max_discharge_kw)
            if raw_limit <= 0:
                return 0.0
            if raw_limit < cfg.min_grid_transfer_kw:
                raw_limit = cfg.min_grid_transfer_kw

            # If current setpoint is materially above PV-leftover cap, clamp immediately.
            # This avoids multi-cycle ramp-down while battery is silently supporting export.
            if current_export > (available + 0.2):
                return round(raw_limit, 1)

            if battery_assist_detected:
                return round(raw_limit, 1)

            # Smooth morning slow-charge export setpoint changes to reduce oscillation.
            if current_export <= 0:
                return round(raw_limit, 1)
            if raw_limit > current_export:
                ramped = min(raw_limit, current_export + cfg.morning_slow_export_ramp_up_step_kw)
            else:
                ramped = max(raw_limit, current_export - cfg.morning_slow_export_ramp_down_step_kw)
            return round(max(ramped, 0.0), 1)

        if high_price or spike:
            cap_val = min(tier_limit, cfg.export_limit_high)
            if spike and cfg.export_spike_full_power:
                cap_val = max(tier_limit, cfg.cap_total_import)
            limit = min(cap_val, s.ess_max_discharge_kw)
            limit = cap_near_floor_to_pv(limit)
            return max(cfg.min_grid_transfer_kw, round(limit, 1)) if limit > 0 else 0.0

        if positive_fit_override:
            eff_tier = tier_limit if tier_limit > 0 else cfg.export_limit_low
            limit = min(eff_tier, s.ess_max_discharge_kw)
            limit = cap_near_floor_to_pv(limit)
            return max(cfg.min_grid_transfer_kw, round(limit, 1)) if limit > 0 else 0.0

        # Solar-surplus bypass should allow exporting real PV excess even when SoC is low.
        # Keep this PV-only by capping to measured excess so battery energy is not exported.
        if surplus_bypass:
            raw_surplus = max(s.pv_kw - s.load_kw, 0.0)
            limit = min(tier_limit, s.ess_max_discharge_kw, raw_surplus)
            limit = cap_near_floor_to_pv(limit)
            if limit <= 0:
                return 0.0
            if limit < cfg.min_grid_transfer_kw:
                return cfg.min_grid_transfer_kw
            return round(limit, 1)

        if tier_limit <= 0:
            return 0.0

        # Scale by SoC headroom
        diff = bsoc - export_min_soc
        span = max(self._export_soc_span_dynamic(s, hours_to_sunrise, is_evening_or_night, cap), 0.1)
        scale_soc = max(0.0, min(1.0, diff / span))

        if solar_override:
            surplus_kw = max(s.pv_kw - s.load_kw, 0.0)
            override_cap = min(surplus_kw, cfg.export_limit_high, tier_limit)
            limit = min(override_cap, s.ess_max_discharge_kw)
            return round(limit, 1) if limit > 0 else 0.0

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

        if limit <= 0:
            return 0.0
        if limit < cfg.min_grid_transfer_kw:
            return cfg.min_grid_transfer_kw
        return round(limit, 1)

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
                               battery_only: bool, morning_dump: bool,
                               morning_slow_charge: bool, desired_export: float) -> float:
        cfg = self.cfg
        cover_load = min(s.load_kw * 1.2, cfg.pv_max_power_normal)
        cover_load = max(round(cover_load, 0), 0.1)

        if s.price_is_negative and s.current_price <= cfg.import_threshold_low:
            return 0.1
        if s.feedin_is_negative and s.battery_soc >= 99:
            # FIT is negative and battery is full: curtail PV to approximately cover load only.
            return max(cover_load, 0.1)
        if standby_holdoff and desired_export == 0:
            return max(cover_load, 0.1)
        if battery_only:
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
                        export_min_soc: float, pv_safeguard: bool, tier_limit: float,
                        morning_slow_charge: bool, surplus_bypass: bool, evening_boost: bool,
                        safeguard: bool, desired_export: float,
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
        if safeguard and not (s.feedin_price >= cfg.export_threshold_high or spike):
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
                if actual_export > 0.05:
                    return f"Solar bypass active, waiting for surplus ({s.forecast_remaining_kwh:.1f}kWh left){est}; measured export {actual_export:.1f}kW is settling"
                return f"Solar bypass active, waiting for surplus ({s.forecast_remaining_kwh:.1f}kWh left){est}"
            return f"Exporting {export_kw_label}, Solar bypass ({s.forecast_remaining_kwh:.1f}kWh left){est}"
        if (export_blocked or forecast_guard) and not surplus_bypass:
            return "Export blocked, low forecast"
        if s.battery_soc <= export_min_soc:
            return f"Export blocked, at {export_min_soc:.0f}% floor"
        effective_floor = cfg.evening_aggressive_floor if evening_boost else cfg.min_export_target_soc
        if s.battery_soc < effective_floor:
            return f"Export blocked, below {effective_floor:.0f}% target"
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
