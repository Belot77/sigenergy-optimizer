"""Decision limit and mode helpers."""
from __future__ import annotations

from .models import SolarState
from .export_limit_service import export_tier_limit, desired_export_limit, export_soc_span_dynamic
from .battery_eta_service import battery_eta as battery_eta_service
from .ems_mode_service import desired_ems_mode as desired_ems_mode_service
from .import_policy_service import (
    desired_import_limit as desired_import_limit_service,
    grid_limit_base as grid_limit_base_service,
)
from .power_limit_policy import (
    desired_pv_max_power as desired_pv_max_power_service,
    desired_ess_charge_limit as desired_ess_charge_limit_service,
    desired_ess_discharge_limit as desired_ess_discharge_limit_service,
)

"""Re-exported from app.export_limit_service."""


def desired_import_limit(
    optimizer,
    s: SolarState,
    morning_dump_active: bool,
    demand_window_active: bool,
    standby_holdoff_active: bool,
    feedin_price_ok: bool,
    pv_surplus: float,
) -> float:
    return desired_import_limit_service(
        optimizer,
        s,
        morning_dump_active,
        demand_window_active,
        standby_holdoff_active,
        feedin_price_ok,
        pv_surplus,
    )


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
    return desired_ems_mode_service(
        optimizer,
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


def grid_limit_base(optimizer, s: SolarState, standby_holdoff_active: bool) -> float:
    return grid_limit_base_service(optimizer, s, standby_holdoff_active)


def desired_pv_max_power(
    optimizer,
    s: SolarState,
    standby_holdoff: bool,
    battery_only: bool,
    morning_dump: bool,
    morning_slow_charge: bool,
    desired_export: float,
) -> float:
    return desired_pv_max_power_service(
        optimizer,
        s,
        standby_holdoff,
        battery_only,
        morning_dump,
        morning_slow_charge,
        desired_export,
    )


def desired_ess_charge_limit(
    optimizer,
    s: SolarState,
    desired_import: float,
    morning_slow_charge: bool,
    desired_export: float,
    pv_surplus: float,
) -> float:
    return desired_ess_charge_limit_service(
        optimizer,
        s,
        desired_import,
        morning_slow_charge,
        desired_export,
        pv_surplus,
    )


def desired_ess_discharge_limit(
    optimizer,
    s: SolarState,
    standby_holdoff: bool,
    positive_fit_override: bool,
    evening_boost: bool,
) -> float:
    return desired_ess_discharge_limit_service(
        optimizer,
        s,
        standby_holdoff,
        positive_fit_override,
        evening_boost,
    )


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
    return battery_eta_service(s, battery_power_kw)