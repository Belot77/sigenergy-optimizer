"""
Decision guard helpers — compatibility wrappers for guard-policy modules.
"""
from __future__ import annotations

from .models import SolarState
from .forecast_guard_service import (
    morning_dump_window as morning_dump_window_service,
    morning_dump_active as morning_dump_active_service,
    morning_slow_charge_active as morning_slow_charge_active_service,
    evening_export_boost_active as evening_export_boost_active_service,
    battery_full_safeguard_block as battery_full_safeguard_block_service,
    export_blocked_for_forecast as export_blocked_for_forecast_service,
    export_forecast_guard as export_forecast_guard_service,
)

# Mode string sets needed locally (mirrors optimizer.py constants)
_DISCHARGE_MODES = {"Command Discharging (PV First)", "Command Discharging (ESS First)"}


def morning_dump_window(optimizer, s: SolarState, actual_sunrise_ts: float):
    return morning_dump_window_service(optimizer, s, actual_sunrise_ts)


def morning_dump_active(
    optimizer,
    s: SolarState,
    dump_start,
    dump_end,
    productive_solar_end_ts,
    bat_fill_need_kwh: float,
    now_ts: float,
) -> bool:
    return morning_dump_active_service(
        optimizer,
        s,
        dump_start,
        dump_end,
        productive_solar_end_ts,
        bat_fill_need_kwh,
        now_ts,
    )


def morning_slow_charge_active(
    optimizer,
    s: SolarState,
    now,
    now_ts: float,
    slow_end_ts: float,
) -> bool:
    return morning_slow_charge_active_service(optimizer, s, now, now_ts, slow_end_ts)


def evening_export_boost_active(
    optimizer,
    s: SolarState,
    now_ts: float,
    productive_solar_end_ts,
    sunrise_soc_target: float,
    bat_fill_need_kwh: float,
) -> bool:
    return evening_export_boost_active_service(
        optimizer,
        s,
        now_ts,
        productive_solar_end_ts,
        sunrise_soc_target,
        bat_fill_need_kwh,
    )


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
    return battery_full_safeguard_block_service(
        optimizer,
        s,
        now_ts,
        sunset_ts,
        bat_fill_need_kwh,
        is_evening_or_night,
    )


def export_blocked_for_forecast(
    optimizer,
    s: SolarState,
    pv_surplus: float,
    is_evening_or_night: bool,
    bat_fill_need_kwh: float,
    hours_to_sunset: float,
    close_to_sunset: bool,
) -> bool:
    return export_blocked_for_forecast_service(
        optimizer,
        s,
        pv_surplus,
        is_evening_or_night,
        bat_fill_need_kwh,
        hours_to_sunset,
        close_to_sunset,
    )


def export_forecast_guard(
    optimizer,
    s: SolarState,
    sunrise_fill_need_kwh: float,
    is_evening_or_night: bool,
    evening_boost: bool,
    close_to_sunset: bool,
) -> bool:
    return export_forecast_guard_service(
        optimizer,
        s,
        sunrise_fill_need_kwh,
        is_evening_or_night,
        evening_boost,
        close_to_sunset,
    )
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
