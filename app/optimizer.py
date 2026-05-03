"""
SigEnergy Optimizer — orchestrator and context object.

Architecture (post-modular refactor):
  - SigEnergyOptimizer         — constructor, public API, thin method wrappers
  - event_loop_service         — run_forever / drain_queue / safe_tick
  - state_reader               — read_state_snapshot (HA entity polling)
  - decision_engine            — build_decision (pure logic, no side effects)
  - action_applier             — apply_decision (push to HA via REST)
  - manual_mode_service        — manual mode targets and application
  - notification_service       — HA push notifications and daily summaries
  - telemetry_service          — price tracking, decision trace, audit log, history
  - time_forecast_service      — today_at, day_window, sunrise/solar forecasts
  - decision_guards            — boolean guard predicates (morning/evening/export)
  - limit_calculator           — export/import/EMS/PV/ESS limit calculations
  - reason_formatter           — human-readable export/import reason strings
  - runtime_utils              — config validation, parse helpers, power caps
"""
from __future__ import annotations

import asyncio
from collections import deque
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional, Union
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
    apply_manual_mode_selection,
)
from .telemetry_service import (
    record_price_tracking,
    record_decision_trace,
    record_automation_audit,
    accumulate_history,
)
from .time_forecast_service import (
    today_at,
    day_window,
    battery_soc_required_to_sunrise,
    negative_price_forecast_ahead,
    negative_price_before_cutoff,
    productive_solar_end_ts,
)
from .decision_guards import (
    morning_dump_window,
    morning_dump_active,
    morning_slow_charge_active,
    evening_export_boost_active,
    solar_surplus_bypass,
    battery_full_safeguard_block,
    export_blocked_for_forecast,
    export_forecast_guard,
)
from .limit_calculator import (
    export_tier_limit,
    desired_export_limit,
    desired_import_limit,
    desired_ems_mode,
    grid_limit_base,
    desired_pv_max_power,
    desired_ess_charge_limit,
    desired_ess_discharge_limit,
    export_soc_span_dynamic,
    battery_eta,
)
from .reason_formatter import export_reason, import_reason
from .runtime_utils import (
    valid_hw_cap_kw,
    get_power_caps_kw as get_power_caps_kw_util,
    validate_time_config,
    is_valid_time,
    warn_parse_issue,
    parse_ts,
)
from .event_loop_service import run_event_loop, drain_queue, safe_tick
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
_RUNTIME_SIGNATURE = "2.3.0-haos21"


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
        self._tz: Union[ZoneInfo, timezone]
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

    def _now(self) -> datetime:
        """Return current datetime; override via patch('app.optimizer.datetime') in tests."""
        return datetime.now()

    @staticmethod
    def _valid_hw_cap_kw(v: Any) -> bool:
        return valid_hw_cap_kw(v)

    def get_power_caps_kw(self, s: Optional[SolarState] = None) -> tuple[float, float]:
        return get_power_caps_kw_util(self, _POWER_LIMIT_MAX_KW, s)

    def _validate_time_config(self) -> list[str]:
        return validate_time_config(self)

    @staticmethod
    def _is_valid_time(value: str) -> bool:
        return is_valid_time(value)

    def _warn_parse_issue(self, entity_id: str, raw_value: str, label: str) -> None:
        warn_parse_issue(self, entity_id, raw_value, label)

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
        await run_event_loop(self)

    async def _drain_queue(self, window: float) -> None:
        await drain_queue(self, window)

    async def _safe_tick(self) -> None:
        await safe_tick(self)

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
        await apply_manual_mode_selection(self, mode_label)

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

    def _today_at(self, time_str: str) -> datetime:
        return today_at(self, time_str)

    def _day_window(self, s: SolarState):
        return day_window(self, s)

    def _battery_soc_required_to_sunrise(self, s: SolarState) -> float:
        return battery_soc_required_to_sunrise(self, s)

    def _negative_price_forecast_ahead(self, s: SolarState, now_ts: float) -> bool:
        return negative_price_forecast_ahead(self, s, now_ts)

    def _negative_price_before_cutoff(self, s: SolarState, now_ts: float) -> bool:
        return negative_price_before_cutoff(self, s, now_ts)

    def _productive_solar_end_ts(self, s: SolarState, sunset_ts: float, now_ts: float) -> Optional[float]:
        return productive_solar_end_ts(self, s, sunset_ts, now_ts)

    def _morning_dump_window(self, s: SolarState, actual_sunrise_ts: float):
        return morning_dump_window(self, s, actual_sunrise_ts)

    def _morning_dump_active(self, s: SolarState, dump_start, dump_end,
                              productive_solar_end_ts, bat_fill_need_kwh, now_ts) -> bool:
        return morning_dump_active(self, s, dump_start, dump_end, productive_solar_end_ts, bat_fill_need_kwh, now_ts)

    def _morning_slow_charge_active(self, s: SolarState, now: datetime,
                                     now_ts: float, slow_end_ts: float) -> bool:
        return morning_slow_charge_active(self, s, now, now_ts, slow_end_ts)

    def _evening_export_boost_active(self, s: SolarState, now_ts: float,
                                      productive_solar_end_ts, sunrise_soc_target, bat_fill_need_kwh) -> bool:
        return evening_export_boost_active(self, s, now_ts, productive_solar_end_ts, sunrise_soc_target, bat_fill_need_kwh)

    def _solar_surplus_bypass(self, s: SolarState, morning_slow_charge_active: bool,
                               cap: float, pv_surplus: float, prev_desired_mode: str = "") -> bool:
        return solar_surplus_bypass(self, s, morning_slow_charge_active, cap, pv_surplus, prev_desired_mode)

    def _battery_full_safeguard_block(self, s: SolarState, now_ts: float,
                                       sunset_ts: float, bat_fill_need_kwh: float,
                                       is_evening_or_night: bool) -> bool:
        return battery_full_safeguard_block(self, s, now_ts, sunset_ts, bat_fill_need_kwh, is_evening_or_night)

    def _export_blocked_for_forecast(self, s: SolarState, pv_surplus: float,
                                      is_evening_or_night: bool, bat_fill_need_kwh: float,
                                      hours_to_sunset: float, close_to_sunset: bool) -> bool:
        return export_blocked_for_forecast(self, s, pv_surplus, is_evening_or_night, bat_fill_need_kwh, hours_to_sunset, close_to_sunset)

    def _export_forecast_guard(self, s: SolarState, sunrise_fill_need_kwh: float,
                                is_evening_or_night: bool, evening_boost: bool,
                                close_to_sunset: bool) -> bool:
        return export_forecast_guard(self, s, sunrise_fill_need_kwh, is_evening_or_night, evening_boost, close_to_sunset)

    def _export_tier_limit(self, s: SolarState, spike: bool, solar_override: bool,
                            pv_safeguard: bool, boost: bool, surplus_bypass: bool) -> float:
        return export_tier_limit(self, s, spike, solar_override, pv_safeguard, boost, surplus_bypass)

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
        return desired_export_limit(
            self,
            s,
            spike,
            solar_override,
            export_blocked,
            forecast_guard,
            export_min_soc,
            positive_fit_override,
            surplus_bypass,
            evening_boost,
            morning_dump,
            morning_dump_limit,
            battery_full_safeguard_block,
            tier_limit,
            hours_to_sunrise,
            cap,
            pv_surplus,
            is_evening_or_night,
            morning_slow_charge_active,
            within_morning_grace,
        )

    def _desired_import_limit(self, s: SolarState, morning_dump_active: bool,
                               demand_window_active: bool, standby_holdoff_active: bool,
                               feedin_price_ok: bool,
                               pv_surplus: float) -> float:
        return desired_import_limit(self, s, morning_dump_active, demand_window_active, standby_holdoff_active, feedin_price_ok, pv_surplus)

    def _desired_ems_mode(self, s: SolarState, morning_dump: bool, standby_holdoff: bool,
                           export_solar_override: bool, desired_export: float,
                           desired_import: float, export_min_soc: float,
                           sunrise_soc_target: float, within_morning_grace: bool,
                           export_blocked_forecast: bool,
                           is_evening_or_night: bool) -> str:
        return desired_ems_mode(
            self,
            s,
            morning_dump,
            standby_holdoff,
            export_solar_override,
            desired_export,
            desired_import,
            export_min_soc,
            sunrise_soc_target,
            within_morning_grace,
            export_blocked_forecast,
            is_evening_or_night,
        )

    def _grid_limit_base(self, s: SolarState, standby_holdoff_active: bool) -> float:
        """Determines base import limit before adjustments."""
        return grid_limit_base(self, s, standby_holdoff_active)

    def _desired_pv_max_power(self, s: SolarState, standby_holdoff: bool,
                               battery_only: bool, morning_dump: bool,
                               morning_slow_charge: bool, desired_export: float) -> float:
        return desired_pv_max_power(
            self,
            s,
            standby_holdoff,
            battery_only,
            morning_dump,
            morning_slow_charge,
            desired_export,
        )

    def _desired_ess_charge_limit(self, s: SolarState, desired_import: float,
                                   morning_slow_charge: bool, desired_export: float,
                                   pv_surplus: float) -> float:
        return desired_ess_charge_limit(self, s, desired_import, morning_slow_charge, desired_export, pv_surplus)

    def _desired_ess_discharge_limit(self, s: SolarState, standby_holdoff: bool,
                                      positive_fit_override: bool, evening_boost: bool) -> float:
        return desired_ess_discharge_limit(self, s, standby_holdoff, positive_fit_override, evening_boost)

    def _export_soc_span_dynamic(self, s: SolarState, hours_to_sunrise: float,
                                  is_evening_or_night: bool, cap: float) -> float:
        return export_soc_span_dynamic(self, s, hours_to_sunrise, is_evening_or_night, cap)

    def _battery_eta(self, s: SolarState, battery_power_kw: float) -> str:
        return battery_eta(self, s, battery_power_kw)

    def _export_reason(self, s: SolarState, spike: bool, solar_override: bool,
                        morning_dump: bool, export_blocked: bool, forecast_guard: bool,
                        export_min_soc: float, pv_safeguard: bool, tier_limit: float,
                        morning_slow_charge: bool, surplus_bypass: bool, evening_boost: bool,
                        safeguard: bool, desired_export: float,
                        positive_fit_override: bool) -> str:
        return export_reason(
            self,
            s,
            spike,
            solar_override,
            morning_dump,
            export_blocked,
            forecast_guard,
            export_min_soc,
            pv_safeguard,
            tier_limit,
            morning_slow_charge,
            surplus_bypass,
            evening_boost,
            safeguard,
            desired_export,
            positive_fit_override,
        )

    def _import_reason(self, s: SolarState, morning_dump: bool, standby_holdoff: bool,
                        sunrise_soc_target: float, desired_import: float,
                        pv_surplus: float) -> str:
        return import_reason(self, s, morning_dump, standby_holdoff, sunrise_soc_target, desired_import, pv_surplus)

    @staticmethod
    def _parse_ts(value) -> Optional[float]:
        return parse_ts(value)
