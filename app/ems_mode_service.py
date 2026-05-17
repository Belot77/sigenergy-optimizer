from __future__ import annotations

from .models import SolarState

_MODE_MAX_SELF = "Maximum Self Consumption"
_MODE_CMD_DISCHARGE_PV = "Command Discharging (PV First)"
_MODE_CMD_CHARGE_PV = "Command Charging (PV First)"
_MODE_CMD_CHARGE_GRID = "Command Charging (Grid First)"

_DISCHARGE_MODES = {_MODE_CMD_DISCHARGE_PV, "Command Discharging (ESS First)"}
_CHARGE_MODES = {_MODE_CMD_CHARGE_PV, _MODE_CMD_CHARGE_GRID}


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