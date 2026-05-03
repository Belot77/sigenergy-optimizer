"""Human-readable reason text formatters extracted from optimizer.py."""
from __future__ import annotations

from .models import SolarState


def export_reason(
    optimizer,
    s: SolarState,
    spike: bool,
    solar_override: bool,
    morning_dump: bool,
    export_blocked: bool,
    forecast_guard: bool,
    export_min_soc: float,
    pv_safeguard: bool,
    tier_limit: float,
    morning_slow_charge: bool,
    surplus_bypass: bool,
    evening_boost: bool,
    safeguard: bool,
    desired_export: float,
    positive_fit_override: bool,
) -> str:
    cfg = optimizer.cfg
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


def import_reason(
    optimizer,
    s: SolarState,
    morning_dump: bool,
    standby_holdoff: bool,
    sunrise_soc_target: float,
    desired_import: float,
    pv_surplus: float,
) -> str:
    cfg = optimizer.cfg
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
