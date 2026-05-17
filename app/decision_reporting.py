from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import Decision, SolarState


@dataclass(frozen=True)
class DecisionReport:
    outcome_reason: str
    export_branch: str
    import_branch: str
    trace_gates: dict[str, Any]
    trace_values: dict[str, Any]


def _eta_label(battery_eta_formatted: str, battery_power_kw: float) -> str:
    if battery_eta_formatted in ("idle", "Full", "Empty"):
        return ""
    if battery_power_kw > 0.1:
        return f"Bat→Full:{battery_eta_formatted}"
    if battery_power_kw < -0.1:
        return f"Bat→Empty:{battery_eta_formatted}"
    return ""


def _build_outcome_reason(s: SolarState, d: Decision, battery_eta_formatted: str, battery_power_kw: float) -> str:
    parts = [d.export_reason, d.import_reason]
    eta_label = _eta_label(battery_eta_formatted, battery_power_kw)
    if eta_label:
        parts.append(eta_label)
    if s.price_is_estimated:
        parts.append("*est")
    return "; ".join(p for p in parts if p and p != "n/a")


def _build_branch_labels(trace_context: dict[str, Any]) -> tuple[str, str]:
    export_branch = "normal_tier"
    if trace_context["morning_dump_active"]:
        export_branch = "morning_dump"
    elif trace_context["morning_slow_charge_active"]:
        export_branch = "morning_slow_charge"
    elif trace_context["export_spike_active"]:
        export_branch = "export_spike"
    elif trace_context["export_solar_override"]:
        export_branch = "solar_override"
    elif trace_context["solar_surplus_bypass"]:
        export_branch = "solar_surplus_bypass"
    elif trace_context["battery_full_safeguard_block"]:
        export_branch = "battery_full_safeguard_block"
    elif trace_context["export_blocked_effective"] or trace_context["export_forecast_guard"]:
        export_branch = "forecast_guard_block"
    elif trace_context["desired_export_limit"] <= 0:
        export_branch = "blocked_or_zero"

    import_branch = "blocked"
    if trace_context["morning_dump_active"]:
        import_branch = "morning_dump_block"
    elif trace_context["demand_window_active"]:
        import_branch = "demand_window_block"
    elif trace_context["standby_holdoff_active"]:
        import_branch = "standby_holdoff_block"
    elif trace_context["desired_import_limit"] > 0 and trace_context["price_is_negative"]:
        import_branch = "negative_price_import"
    elif trace_context["desired_import_limit"] > 0:
        import_branch = "cheap_topup_import"

    return export_branch, import_branch


def _build_trace_gates(trace_context: dict[str, Any]) -> dict[str, Any]:
    return {
        "is_evening_or_night": trace_context["is_evening_or_night"],
        "close_to_sunset": trace_context["close_to_sunset"],
        "within_morning_grace": trace_context["within_morning_grace"],
        "morning_dump_active": trace_context["morning_dump_active"],
        "morning_slow_charge_active": trace_context["morning_slow_charge_active"],
        "standby_holdoff_active": trace_context["standby_holdoff_active"],
        "negative_price_before_cutoff": trace_context["negative_price_before_cutoff"],
        "battery_can_reach_from_pv": trace_context["battery_can_reach_from_pv"],
        "evening_export_boost_active": trace_context["evening_export_boost_active"],
        "export_spike_active": trace_context["export_spike_active"],
        "positive_fit_override": trace_context["positive_fit_override"],
        "export_solar_override": trace_context["export_solar_override"],
        "pv_safeguard_active": trace_context["pv_safeguard_active"],
        "solar_surplus_bypass": trace_context["solar_surplus_bypass"],
        "battery_full_safeguard_block": trace_context["battery_full_safeguard_block"],
        "export_blocked_for_forecast": trace_context["export_blocked_for_forecast"],
        "export_forecast_guard": trace_context["export_forecast_guard"],
        "export_blocked_effective": trace_context["export_blocked_effective"],
        "battery_only_mode": trace_context["battery_only_mode"],
        "needs_ha_control_switch": trace_context["needs_ha_control_switch"],
        "demand_window_active": trace_context["demand_window_active"],
        "price_is_negative": trace_context["price_is_negative"],
        "feedin_is_negative": trace_context["feedin_is_negative"],
    }


def _build_trace_values(trace_context: dict[str, Any]) -> dict[str, Any]:
    cfg = trace_context["cfg"]
    s = trace_context["s"]
    return {
        "battery_soc": s.battery_soc,
        "current_price": s.current_price,
        "feedin_price": s.feedin_price,
        "pv_kw": s.pv_kw,
        "load_kw": s.load_kw,
        "grid_import_power_kw": s.grid_import_power_kw,
        "grid_export_power_kw": s.grid_export_power_kw,
        "pv_surplus_actual": trace_context["pv_surplus_actual"],
        "pv_surplus_estimated": trace_context["pv_surplus_estimated"],
        "cap_kwh": trace_context["cap_kwh"],
        "bat_fill_need_kwh": trace_context["bat_fill_need_kwh"],
        "soc_required": trace_context["soc_required"],
        "sunrise_soc_target": trace_context["sunrise_soc_target"],
        "sunrise_fill_need_kwh": trace_context["sunrise_fill_need_kwh"],
        "hours_to_sunrise": trace_context["hours_to_sunrise"],
        "hours_to_sunset": trace_context["hours_to_sunset"],
        "export_min_soc": trace_context["export_min_soc"],
        "export_tier_limit": trace_context["export_tier_limit"],
        "morning_dump_limit": trace_context["morning_dump_limit"],
        "desired_export_limit": trace_context["desired_export_limit"],
        "desired_import_limit": trace_context["desired_import_limit"],
        "desired_ems_mode": trace_context["desired_ems_mode"],
        "desired_pv_max": trace_context["desired_pv_max"],
        "effective_import_for_math": trace_context["effective_import_for_math"],
        "battery_power_kw": trace_context["battery_power_kw"],
        "battery_power_source": trace_context["battery_power_source"],
        "battery_power_sensor_kw": trace_context["battery_power_sensor_kw"],
        "ess_charge_limit": trace_context["ess_charge_limit"],
        "ess_discharge_limit": trace_context["ess_discharge_limit"],
        "holdoff_entry_floor": trace_context["holdoff_entry_floor"],
        "current_export_limit": trace_context["current_export_limit"],
        "current_import_limit": trace_context["current_import_limit"],
        "current_pv_max_power_limit": trace_context["current_pv_max_power_limit"],
        "current_ems_mode": trace_context["current_ems_mode"],
        "sigenergy_mode": trace_context["sigenergy_mode"],
        "manual_mode_override": trace_context["manual_mode_override"],
        "export_branch": trace_context["export_branch"],
        "import_branch": trace_context["import_branch"],
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
        "cfg_min_export_target_soc": cfg.min_export_target_soc,
        "cfg_min_soc_floor": cfg.min_soc_floor,
        "cfg_sunrise_export_relax_percent": cfg.sunrise_export_relax_percent,
        "cfg_pv_max_power_normal": cfg.pv_max_power_normal,
    }


def build_trace_context(
    *,
    s: SolarState,
    d: Decision,
    is_evening_or_night: bool,
    close_to_sunset: bool,
    within_morning_grace: bool,
    morning_dump_active: bool,
    morning_slow_charge_active: bool,
    standby_holdoff_active: bool,
    negative_price_before_cutoff: bool,
    battery_can_reach_from_pv: bool,
    evening_export_boost_active: bool,
    export_spike_active: bool,
    positive_fit_override: bool,
    export_solar_override: bool,
    pv_safeguard_active: bool,
    solar_surplus_bypass: bool,
    battery_full_safeguard_block: bool,
    export_blocked_for_forecast: bool,
    export_forecast_guard: bool,
    export_blocked_effective: bool,
    battery_only_mode: bool,
    pv_surplus_actual: float,
    pv_surplus_estimated: float,
    cap_kwh: float,
    bat_fill_need_kwh: float,
    soc_required: float,
    sunrise_soc_target: float,
    sunrise_fill_need_kwh: float,
    hours_to_sunrise: float,
    hours_to_sunset: float,
    export_min_soc: float,
    export_tier_limit: float,
    morning_dump_limit: float,
    desired_export_limit: float,
    desired_import_limit: float,
    desired_ems_mode: str,
    desired_pv_max: float,
    effective_import_for_math: float,
    battery_power_kw: float,
    battery_power_source: str,
    battery_power_sensor_kw: float | None,
    ess_charge_limit: float,
    ess_discharge_limit: float,
    holdoff_entry_floor: float | None,
    current_export_limit: float | None,
    current_import_limit: float | None,
    current_pv_max_power_limit: float | None,
    current_ems_mode: str,
    sigenergy_mode: str,
    manual_mode_override: str | None,
) -> dict[str, Any]:
    return {
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
        "battery_only_mode": battery_only_mode,
        "needs_ha_control_switch": d.needs_ha_control_switch,
        "demand_window_active": s.demand_window_active,
        "price_is_negative": s.price_is_negative,
        "feedin_is_negative": s.feedin_is_negative,
        "pv_surplus_actual": pv_surplus_actual,
        "pv_surplus_estimated": pv_surplus_estimated,
        "cap_kwh": cap_kwh,
        "bat_fill_need_kwh": bat_fill_need_kwh,
        "soc_required": soc_required,
        "sunrise_soc_target": sunrise_soc_target,
        "sunrise_fill_need_kwh": sunrise_fill_need_kwh,
        "hours_to_sunrise": hours_to_sunrise,
        "hours_to_sunset": hours_to_sunset,
        "export_min_soc": export_min_soc,
        "export_tier_limit": export_tier_limit,
        "morning_dump_limit": morning_dump_limit,
        "desired_export_limit": desired_export_limit,
        "desired_import_limit": desired_import_limit,
        "desired_ems_mode": desired_ems_mode,
        "desired_pv_max": desired_pv_max,
        "effective_import_for_math": effective_import_for_math,
        "battery_power_kw": battery_power_kw,
        "battery_power_source": battery_power_source,
        "battery_power_sensor_kw": battery_power_sensor_kw,
        "ess_charge_limit": ess_charge_limit,
        "ess_discharge_limit": ess_discharge_limit,
        "holdoff_entry_floor": holdoff_entry_floor,
        "current_export_limit": current_export_limit,
        "current_import_limit": current_import_limit,
        "current_pv_max_power_limit": current_pv_max_power_limit,
        "current_ems_mode": current_ems_mode,
        "sigenergy_mode": sigenergy_mode,
        "manual_mode_override": manual_mode_override,
    }


def build_decision_report(
    optimizer,
    s: SolarState,
    d: Decision,
    *,
    battery_eta_formatted: str,
    battery_power_kw: float,
    battery_power_source: str,
    effective_import_for_math: float,
    trace_context: dict[str, Any],
) -> DecisionReport:
    trace_context = dict(trace_context)
    trace_context["cfg"] = optimizer.cfg
    trace_context["s"] = s
    trace_context["battery_power_kw"] = battery_power_kw
    trace_context["battery_power_source"] = battery_power_source
    trace_context["effective_import_for_math"] = effective_import_for_math
    outcome_reason = _build_outcome_reason(s, d, battery_eta_formatted, battery_power_kw)
    export_branch, import_branch = _build_branch_labels(trace_context)
    trace_context["export_branch"] = export_branch
    trace_context["import_branch"] = import_branch
    return DecisionReport(
        outcome_reason=outcome_reason,
        export_branch=export_branch,
        import_branch=import_branch,
        trace_gates=_build_trace_gates(trace_context),
        trace_values=_build_trace_values(trace_context),
    )