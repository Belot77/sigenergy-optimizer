from __future__ import annotations

from .models import SolarState


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
    if (
        price <= cfg.max_price_threshold
        and bsoc < cfg.daytime_topup_max_soc
        and s.forecast_remaining_kwh < s.battery_capacity_kwh * cfg.forecast_safety_charging
    ):
        surplus = max(s.pv_kw - s.load_kw, 0.0)
        if surplus < cfg.target_battery_charge:
            return min(cfg.target_battery_charge, cfg.cap_total_import)
    return 0.0