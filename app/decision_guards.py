"""
Decision guard helpers — pure boolean guard functions extracted from optimizer.py.

Each function receives the optimizer instance as first argument so it can
access cfg, state attributes, and existing wrapper methods.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from .models import SolarState

logger = logging.getLogger(__name__)

# Mode string sets needed locally (mirrors optimizer.py constants)
_DISCHARGE_MODES = {"Command Discharging (PV First)", "Command Discharging (ESS First)"}


def morning_dump_window(optimizer, s: SolarState, actual_sunrise_ts: float):
    """Return (dump_start_ts, dump_end_ts) for the pre-sunrise dump window."""
    cfg = optimizer.cfg
    day_start = actual_sunrise_ts + 3600
    hours_before = cfg.morning_dump_hours_before_sunrise
    dump_start = day_start - hours_before * 3600
    dump_end = actual_sunrise_ts + 3600
    return dump_start, dump_end


def morning_dump_active(
    optimizer,
    s: SolarState,
    dump_start,
    dump_end,
    productive_solar_end_ts,
    bat_fill_need_kwh: float,
    now_ts: float,
) -> bool:
    cfg = optimizer.cfg
    if not cfg.morning_dump_enabled:
        return False
    if dump_start is None or dump_end is None:
        return False
    if not (dump_start <= now_ts <= dump_end):
        return False

    # Check forecast can refill after dump
    ns_total = 0.0
    for f in s.solcast_detailed:
        if not isinstance(f, dict):
            continue
        try:
            f_ts = optimizer._parse_ts(f.get("period_start", ""))
            pv_kw = float(f.get("pv_estimate", 0))
            if f_ts and dump_end <= f_ts < (productive_solar_end_ts or now_ts + 86400):
                ns_total += pv_kw * cfg.solcast_forecast_period_hours
        except Exception:
            pass
    load_need = ((productive_solar_end_ts or now_ts + 86400) - dump_end) / 3600 * s.load_kw
    return ns_total >= (bat_fill_need_kwh + load_need) * cfg.forecast_safety_charging


def morning_slow_charge_active(
    optimizer,
    s: SolarState,
    now: datetime,
    now_ts: float,
    slow_end_ts: float,
) -> bool:
    if optimizer._morning_slow_charge_runtime_disabled:
        if not optimizer._morning_slow_disable_logged:
            logger.warning("Morning slow charge is runtime-disabled in this build")
            optimizer._morning_slow_disable_logged = True
        return False
    cfg = optimizer.cfg
    if not cfg.morning_slow_charge_enabled:
        return False
    target_dt = optimizer._today_at(cfg.morning_slow_charge_until)
    if now >= target_dt or now.hour < 5:
        return False
    if not s.sun_above_horizon and now.hour < 7:
        return False
    if s.feedin_price <= cfg.morning_slow_charge_min_feedin_price:
        return False

    cap = s.battery_capacity_kwh
    bat_fill_need = max(0.0, cap - s.available_discharge_energy_kwh)
    hours_left = max((slow_end_ts - now_ts) / 3600, 0.0)
    load_need = hours_left * cfg.morning_slow_charge_base_load_kw
    required_kwh = (bat_fill_need + load_need) * cfg.forecast_safety_charging
    return s.forecast_remaining_kwh >= required_kwh


def evening_export_boost_active(
    optimizer,
    s: SolarState,
    now_ts: float,
    productive_solar_end_ts,
    sunrise_soc_target: float,
    bat_fill_need_kwh: float,
) -> bool:
    cfg = optimizer.cfg
    if not cfg.evening_boost_enabled:
        return False
    if productive_solar_end_ts is None or now_ts < productive_solar_end_ts:
        return False
    now_dt = datetime.fromtimestamp(now_ts)
    midnight = (now_dt + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
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
    tomorrow_6am = (now_dt + timedelta(days=1)).replace(hour=6, minute=0, second=0, microsecond=0).timestamp()
    no_high_fit = True
    for f in s.feedin_forecast_entries:
        if not isinstance(f, dict):
            continue
        try:
            ts = optimizer._parse_ts(f.get(cfg.price_forecast_time_key, ""))
            price = float(f.get(cfg.feedin_forecast_value_key, 0))
            if ts and now_ts <= ts <= tomorrow_6am and price >= cfg.export_threshold_medium:
                no_high_fit = False
                break
        except Exception:
            pass
    return no_high_fit and overnight_covered and tomorrow_forecast_meets_minimum and tomorrow_will_refill


def solar_surplus_bypass(
    optimizer,
    s: SolarState,
    morning_slow_charge_active_flag: bool,
    cap: float,
    pv_surplus: float,
    prev_desired_mode: str = "",
) -> bool:
    cfg = optimizer.cfg
    if not cfg.solar_surplus_bypass_enabled or morning_slow_charge_active_flag:
        return False
    start_thresh = cap * cfg.solar_surplus_start_multiplier
    stop_thresh = cap * cfg.solar_surplus_stop_multiplier
    pv_over_load = pv_surplus > cfg.solar_surplus_min_pv_margin
    start_ok = s.forecast_remaining_kwh >= start_thresh
    continue_ok = (
        s.forecast_remaining_kwh >= stop_thresh
        and (s.current_ems_mode in _DISCHARGE_MODES or prev_desired_mode in _DISCHARGE_MODES)
    )
    return pv_over_load and (start_ok or continue_ok)


def battery_full_safeguard_block(
    optimizer,
    s: SolarState,
    now_ts: float,
    sunset_ts: float,
    bat_fill_need_kwh: float,
    is_evening_or_night: bool,
) -> bool:
    cfg = optimizer.cfg
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
            f_ts = optimizer._parse_ts(f.get("period_start", ""))
            pv_kw = float(f.get("pv_estimate", 0))
            if f_ts and now_ts <= f_ts < target_ts:
                net = max(pv_kw - s.load_kw, 0.0)
                usable = min(net, max_charge_kw) * cfg.solcast_forecast_period_hours
                ns_total += usable
        except Exception:
            pass
    return (ns_total * cfg.battery_full_forecast_multiplier) < bat_fill_need_kwh


def export_blocked_for_forecast(
    optimizer,
    s: SolarState,
    pv_surplus: float,
    is_evening_or_night: bool,
    bat_fill_need_kwh: float,
    hours_to_sunset: float,
    close_to_sunset: bool,
) -> bool:
    cfg = optimizer.cfg
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


def export_forecast_guard(
    optimizer,
    s: SolarState,
    sunrise_fill_need_kwh: float,
    is_evening_or_night: bool,
    evening_boost: bool,
    close_to_sunset: bool,
) -> bool:
    cfg = optimizer.cfg
    if s.battery_soc >= cfg.export_guard_relax_soc or close_to_sunset:
        return False
    if is_evening_or_night:
        floor = cfg.evening_aggressive_floor if evening_boost else cfg.min_export_target_soc
        return s.battery_soc < floor
    if sunrise_fill_need_kwh <= 0:
        return False
    required = sunrise_fill_need_kwh * cfg.forecast_safety_export
    return s.forecast_remaining_kwh < required
