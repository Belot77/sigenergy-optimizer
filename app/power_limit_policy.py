from __future__ import annotations

from .models import SolarState


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