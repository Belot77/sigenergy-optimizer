"""Limit and mode calculation helpers extracted from optimizer.py."""
from __future__ import annotations

from .models import SolarState

# Local mirrors of optimizer mode constants
_MODE_MAX_SELF = "Maximum Self Consumption"
_MODE_CMD_DISCHARGE_PV = "Command Discharging (PV First)"
_MODE_CMD_CHARGE_PV = "Command Charging (PV First)"
_MODE_CMD_CHARGE_GRID = "Command Charging (Grid First)"

_DISCHARGE_MODES = {_MODE_CMD_DISCHARGE_PV, "Command Discharging (ESS First)"}
_CHARGE_MODES = {_MODE_CMD_CHARGE_PV, _MODE_CMD_CHARGE_GRID}


def export_tier_limit(
    optimizer,
    s: SolarState,
    spike: bool,
    solar_override: bool,
    pv_safeguard: bool,
    boost: bool,
    surplus_bypass: bool,
) -> float:
    cfg = optimizer.cfg
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
    if boost and not below_boost_floor:
        frac = (fit - cfg.export_threshold_low) / max(cfg.export_threshold_medium - cfg.export_threshold_low, 0.001)
        return cfg.export_limit_low + frac * (cfg.export_limit_medium - cfg.export_limit_low)
    if (below_target or pv_safeguard) and not surplus_bypass:
        return 0.0
    frac = (fit - cfg.export_threshold_low) / max(cfg.export_threshold_medium - cfg.export_threshold_low, 0.001)
    return cfg.export_limit_low + frac * (cfg.export_limit_medium - cfg.export_limit_low)


def desired_export_limit(
    optimizer,
    s: SolarState,
    spike: bool,
    solar_override: bool,
    export_blocked: bool,
    forecast_guard: bool,
    export_min_soc: float,
    positive_fit_override: bool,
    surplus_bypass: bool,
    evening_boost: bool,
    morning_dump: bool,
    morning_dump_limit: float,
    battery_full_safeguard_block: bool,
    tier_limit: float,
    hours_to_sunrise: float,
    cap: float,
    pv_surplus: float,
    is_evening_or_night: bool,
    morning_slow_charge_active: bool,
    within_morning_grace: bool,
) -> float:
    cfg = optimizer.cfg
    fit_cents = s.feedin_price_cents
    bsoc = s.battery_soc

    if fit_cents < 1:
        return 0.0

    high_price = s.feedin_price >= cfg.export_threshold_high

    if battery_full_safeguard_block and not (high_price or spike):
        return 0.0

    effective_export_floor = cfg.evening_aggressive_floor if evening_boost else cfg.min_export_target_soc

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

    def cap_near_floor_to_pv(limit_value: float) -> float:
        if limit_value <= 0:
            return 0.0
        if bypass_min_soc and bsoc <= (export_min_soc + 0.05):
            excess_solar_kw = max(s.pv_kw - s.load_kw, 0.0)
            return min(limit_value, excess_solar_kw)
        return limit_value

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

        available = max(actual_surplus - cfg.morning_slow_charge_rate_kw, 0.0)
        raw_limit = min(available, s.ess_max_discharge_kw)

        battery_assist_detected = measured_export > (actual_surplus + 0.3)

        probe_enabled = bool(cfg.morning_slow_export_probe_enabled)
        saturation_margin = max(0.05, cfg.morning_slow_export_probe_saturation_margin_kw)
        probe_step = max(0.1, cfg.morning_slow_export_probe_step_kw)
        near_export_cap = measured_export >= max(cfg.min_grid_transfer_kw, current_export - saturation_margin)
        no_grid_import_pressure = (s.grid_import_power_kw is None) or (float(s.grid_import_power_kw) <= 0.2)
        if (probe_enabled and export_is_open and near_export_cap and no_grid_import_pressure
                and not battery_assist_detected):
            raw_limit = max(raw_limit, current_export + probe_step)

        raw_limit = min(raw_limit, available)

        raw_limit = min(raw_limit, s.ess_max_discharge_kw)
        if raw_limit <= 0:
            return 0.0
        if raw_limit < cfg.min_grid_transfer_kw:
            raw_limit = cfg.min_grid_transfer_kw

        if current_export > (available + 0.2):
            return round(raw_limit, 1)

        if battery_assist_detected:
            return round(raw_limit, 1)

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

    diff = bsoc - export_min_soc
    span = max(optimizer._export_soc_span_dynamic(s, hours_to_sunrise, is_evening_or_night, cap), 0.1)
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


def desired_import_limit(
    optimizer,
    s: SolarState,
    morning_dump_active: bool,
    demand_window_active: bool,
    standby_holdoff_active: bool,
    feedin_price_ok: bool,
    pv_surplus: float,
) -> float:
    cfg = optimizer.cfg
    if morning_dump_active or demand_window_active:
        return 0.0
    if standby_holdoff_active:
        return 0.0

    if s.price_is_negative and s.current_price <= cfg.import_threshold_low:
        rated = s.ess_max_charge_kw
        if s.current_price <= cfg.import_threshold_high:
            return min(cfg.import_limit_high, rated)
        if s.current_price <= cfg.import_threshold_medium:
            return min(cfg.import_limit_medium, rated)
        return min(cfg.import_limit_low, rated)

    if feedin_price_ok:
        return 0.0

    if s.current_price > cfg.max_price_threshold:
        return 0.0

    if s.battery_soc >= cfg.daytime_topup_max_soc:
        return 0.0

    if pv_surplus >= cfg.target_battery_charge:
        return 0.0

    if s.current_price <= cfg.max_price_threshold:
        return min(cfg.target_battery_charge, s.ess_max_charge_kw, cfg.cap_total_import)

    return 0.0


def desired_ems_mode(
    optimizer,
    s: SolarState,
    morning_dump: bool,
    standby_holdoff: bool,
    export_solar_override: bool,
    desired_export: float,
    desired_import: float,
    export_min_soc: float,
    sunrise_soc_target: float,
    within_morning_grace: bool,
    export_blocked_forecast: bool,
    is_evening_or_night: bool,
) -> str:
    cfg = optimizer.cfg
    bsoc = s.battery_soc
    currently_discharging = s.current_ems_mode in _DISCHARGE_MODES
    currently_charging = s.current_ems_mode in _CHARGE_MODES

    def _charge_mode():
        if within_morning_grace and s.pv_kw < s.load_kw * 0.5:
            return _MODE_MAX_SELF
        return _MODE_CMD_CHARGE_PV

    if morning_dump:
        return _MODE_CMD_DISCHARGE_PV
    if s.demand_window_active:
        return _MODE_CMD_DISCHARGE_PV if desired_export > 0 else _MODE_MAX_SELF
    if standby_holdoff and desired_export == 0:
        holdoff_discharge_floor = optimizer._holdoff_entry_floor or (sunrise_soc_target + cfg.soc_hysteresis)
        return _MODE_MAX_SELF if bsoc < holdoff_discharge_floor else _MODE_CMD_DISCHARGE_PV
    if desired_import > 0 and not s.price_is_negative:
        return _charge_mode()
    if export_solar_override:
        return _MODE_CMD_DISCHARGE_PV
    if s.price_is_negative and s.current_price <= cfg.import_threshold_low:
        return _MODE_CMD_CHARGE_GRID
    if s.feedin_is_negative:
        return _MODE_MAX_SELF
    if desired_export > 0:
        return _MODE_CMD_DISCHARGE_PV
    if not export_blocked_forecast and bsoc > export_min_soc + cfg.soc_hysteresis:
        pv_surplus = max(s.pv_kw - s.load_kw, 0.0)
        if pv_surplus == 0 and not is_evening_or_night:
            return _MODE_MAX_SELF
        if currently_discharging and s.feedin_price >= cfg.export_threshold_low * cfg.export_hysteresis_percent:
            return _MODE_CMD_DISCHARGE_PV
        if s.feedin_price >= cfg.export_threshold_low:
            return _MODE_CMD_DISCHARGE_PV
        return _MODE_MAX_SELF
    grid_limit_base = optimizer._grid_limit_base(s, standby_holdoff)
    if (grid_limit_base > 0
            and s.feedin_price < cfg.export_threshold_low - cfg.price_hysteresis
            and bsoc < cfg.max_battery_soc - cfg.soc_hysteresis):
        return _charge_mode()
    if (currently_charging and grid_limit_base > 0
            and s.feedin_price < cfg.export_threshold_low + cfg.price_hysteresis
            and bsoc < cfg.max_battery_soc):
        return _charge_mode()
    return _MODE_MAX_SELF


def grid_limit_base(optimizer, s: SolarState, standby_holdoff_active: bool) -> float:
    cfg = optimizer.cfg
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
    if (price <= cfg.max_price_threshold
            and bsoc < cfg.daytime_topup_max_soc
            and s.forecast_remaining_kwh < s.battery_capacity_kwh * cfg.forecast_safety_charging):
        surplus = max(s.pv_kw - s.load_kw, 0.0)
        if surplus < cfg.target_battery_charge:
            return min(cfg.target_battery_charge, cfg.cap_total_import)
    return 0.0


def desired_pv_max_power(
    optimizer,
    s: SolarState,
    standby_holdoff: bool,
    battery_only: bool,
    morning_dump: bool,
    morning_slow_charge: bool,
    desired_export: float,
) -> float:
    cfg = optimizer.cfg
    cover_load = min(s.load_kw * 1.2, cfg.pv_max_power_normal)
    cover_load = max(round(cover_load, 0), 0.1)

    if s.price_is_negative and s.current_price <= cfg.import_threshold_low:
        return 0.1
    if s.feedin_is_negative and s.battery_soc >= 99:
        return max(cover_load, 0.1)
    if standby_holdoff and desired_export == 0:
        return max(cover_load, 0.1)
    if battery_only:
        return max(cover_load, 0.1)
    if morning_dump:
        return cfg.pv_max_power_normal
    if morning_slow_charge:
        return cfg.pv_max_power_normal
    return cfg.pv_max_power_normal


def desired_ess_charge_limit(
    optimizer,
    s: SolarState,
    desired_import: float,
    morning_slow_charge: bool,
    desired_export: float,
    pv_surplus: float,
) -> float:
    cfg = optimizer.cfg
    hw_charge, _ = optimizer.get_power_caps_kw(s)
    max_charge = max(0.1, hw_charge)
    if desired_import > 0:
        return min(max_charge, desired_import)
    if morning_slow_charge:
        slow = cfg.morning_slow_charge_rate_kw
        return round(min(slow, max_charge), 1)
    return max_charge


def desired_ess_discharge_limit(
    optimizer,
    s: SolarState,
    standby_holdoff: bool,
    positive_fit_override: bool,
    evening_boost: bool,
) -> float:
    cfg = optimizer.cfg
    _, hw_discharge = optimizer.get_power_caps_kw(s)
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


def export_soc_span_dynamic(
    optimizer,
    s: SolarState,
    hours_to_sunrise: float,
    is_evening_or_night: bool,
    cap: float,
) -> float:
    if is_evening_or_night:
        span = (hours_to_sunrise * s.load_kw / max(cap, 0.1)) * 100
        return max(4.0, min(span, 25.0))
    return optimizer.cfg.export_soc_span_day


def battery_eta(optimizer, s: SolarState, battery_power_kw: float) -> str:
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
