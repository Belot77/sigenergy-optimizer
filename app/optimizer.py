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
    - telemetry_api              — telemetry wrapper surface
    - telemetry_recording        — telemetry persistence and recording
    - state_api                  — state, history, and preset accessors
    - state_store                — local persistence store
    - time_forecast_service      — time and forecast compatibility wrappers
    - sunrise_window_service     — day-window and sunrise SoC target logic
    - forecast_policy_service    — forecast-driven decision checks
    - decision_guards            — boolean guard compatibility wrappers
    - forecast_guard_service     — forecast-driven guard policy
    - decision_limits            — limit-policy compatibility wrappers
    - ems_mode_service           — EMS mode selection policy
    - import_policy_service      — import/grid charging policy
    - power_limit_policy         — PV/ESS output limit policy
  - reason_formatter           — human-readable export/import reason strings
    - optimizer_runtime          — config validation, parse helpers, power caps
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
from .forecast_utils import extract_forecast_entries, forecast_entry_time, forecast_entry_value
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
from .telemetry_api import (
    record_price_tracking,
    record_decision_trace,
    record_automation_audit,
    accumulate_history,
)
from .state_api import (
    price_tracking_events as price_tracking_events_util,
    daily_earnings_summary as daily_earnings_summary_util,
    earnings_history as earnings_history_util,
    audit_events as audit_events_util,
    record_audit_event as record_audit_event_util,
    list_threshold_presets as list_threshold_presets_util,
    get_threshold_preset as get_threshold_preset_util,
    save_threshold_preset as save_threshold_preset_util,
    delete_threshold_preset as delete_threshold_preset_util,
    decision_trace as decision_trace_util,
)
from .optimizer_bootstrap import initialize_runtime_state
from .lifecycle_service import (
    get_watch_entities as get_watch_entities_util,
    on_ws_connect as on_ws_connect_util,
    on_ws_disconnect as on_ws_disconnect_util,
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
    solar_surplus_bypass,
)
from .forecast_guard_service import (
    morning_dump_window,
    morning_dump_active,
    morning_slow_charge_active,
    evening_export_boost_active,
    battery_full_safeguard_block,
    export_blocked_for_forecast,
    export_forecast_guard,
)
from .decision_limits import (
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
from .optimizer_runtime import (
    valid_hw_cap_kw,
    get_power_caps_kw as get_power_caps_kw_util,
    validate_time_config,
    is_valid_time,
    warn_parse_issue,
    parse_ts,
)
from .event_loop_service import run_event_loop, drain_queue, safe_tick
from .tick_service import run_tick
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



_POWER_LIMIT_MAX_KW = 100.0
_RUNTIME_SIGNATURE = "2.3.7-haos22"


class SigEnergyOptimizer:
    def __init__(self, ha: HAClient, cfg: Settings) -> None:
        self.ha = ha
        self.cfg = cfg
        initialize_runtime_state(self)

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
        return get_watch_entities_util(self)

    def on_ws_connect(self) -> None:
        on_ws_connect_util(self)

    def on_ws_disconnect(self) -> None:
        on_ws_disconnect_util(self)

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
        await run_tick(self)

    def _record_price_tracking(self, s: SolarState) -> None:
        record_price_tracking(self, s)

    def price_tracking_events(self, date: str | None = None, limit: int = 2000) -> list[dict[str, Any]]:
        return price_tracking_events_util(self, date=date, limit=limit)

    async def daily_earnings_summary(self, date: str | None = None) -> dict[str, Any]:
        return await daily_earnings_summary_util(self, date=date)

    async def earnings_history(self, days: int = 7) -> dict[str, Any]:
        return await earnings_history_util(self, days)

    def audit_events(self, limit: int = 200) -> list[dict[str, Any]]:
        return audit_events_util(self, limit=limit)

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
        record_audit_event_util(
            self,
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
        return list_threshold_presets_util(self)

    def get_threshold_preset(self, name: str) -> dict[str, Any] | None:
        return get_threshold_preset_util(self, name)

    def save_threshold_preset(self, name: str, payload: dict[str, Any]) -> None:
        save_threshold_preset_util(self, name, payload)

    def delete_threshold_preset(self, name: str) -> bool:
        return delete_threshold_preset_util(self, name)

    def decision_trace(self, limit: int = 200) -> list[dict[str, Any]]:
        return decision_trace_util(self, limit=limit)

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

    def _manual_import_recent_for_value_gate(self) -> bool:
        # TODO: wire this to an explicit manual import or force-import audit signal when one exists.
        return False

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
    ) -> dict[str, float | bool | str]:
        cfg = self.cfg
        gate_active = bool(cfg.export_value_gate_enabled or cfg.export_value_gate_dry_run)
        if not gate_active:
            return {
                "protected_reserve_soc": 0.0,
                "export_surplus_soc": 0.0,
                "stored_energy_value_floor": 0.0,
                "export_value_gate_would_allow": False,
                "export_value_gate_would_block": False,
                "export_value_gate_reason": "Advisory gate disabled.",
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

        desired_export_active = desired_export_limit > 0.01
        spike_override_threshold = float(cfg.export_value_gate_spike_override_threshold)
        if spike_override_threshold <= 0:
            spike_override_threshold = float(cfg.export_spike_threshold)

        if not desired_export_active:
            return {
                "protected_reserve_soc": protected_reserve_soc,
                "export_surplus_soc": export_surplus_soc,
                "stored_energy_value_floor": stored_energy_value_floor,
                "export_value_gate_would_allow": False,
                "export_value_gate_would_block": False,
                "export_value_gate_reason": "Advisory only: live export is not active.",
            }

        if export_surplus_soc <= 0.05:
            return {
                "protected_reserve_soc": protected_reserve_soc,
                "export_surplus_soc": export_surplus_soc,
                "stored_energy_value_floor": stored_energy_value_floor,
                "export_value_gate_would_allow": False,
                "export_value_gate_would_block": True,
                "export_value_gate_reason": (
                    "Advisory only: would block export because battery is at or below protected reserve "
                    f"{protected_reserve_soc:.1f}% for evening/load until useful solar."
                ),
            }

        if export_spike_active and spike_override_threshold > 0 and float(s.feedin_price or 0.0) >= spike_override_threshold:
            return {
                "protected_reserve_soc": protected_reserve_soc,
                "export_surplus_soc": export_surplus_soc,
                "stored_energy_value_floor": stored_energy_value_floor,
                "export_value_gate_would_allow": True,
                "export_value_gate_would_block": False,
                "export_value_gate_reason": (
                    "Advisory only: would allow export because spike FIT "
                    f"{float(s.feedin_price or 0.0):.2f} exceeds override {spike_override_threshold:.2f} "
                    f"with {export_surplus_soc:.1f}% above protected reserve."
                ),
            }

        if float(s.feedin_price or 0.0) >= stored_energy_value_floor:
            return {
                "protected_reserve_soc": protected_reserve_soc,
                "export_surplus_soc": export_surplus_soc,
                "stored_energy_value_floor": stored_energy_value_floor,
                "export_value_gate_would_allow": True,
                "export_value_gate_would_block": False,
                "export_value_gate_reason": (
                    "Advisory only: would allow export because FIT "
                    f"{float(s.feedin_price or 0.0):.2f} meets stored energy value {stored_energy_value_floor:.2f} "
                    f"with {export_surplus_soc:.1f}% above protected reserve."
                ),
            }

        return {
            "protected_reserve_soc": protected_reserve_soc,
            "export_surplus_soc": export_surplus_soc,
            "stored_energy_value_floor": stored_energy_value_floor,
            "export_value_gate_would_allow": False,
            "export_value_gate_would_block": True,
            "export_value_gate_reason": (
                "Advisory only: would block export because FIT "
                f"{float(s.feedin_price or 0.0):.2f} is below stored energy value {stored_energy_value_floor:.2f} "
                "and battery is protected for evening/load until useful solar."
            ),
        }

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
