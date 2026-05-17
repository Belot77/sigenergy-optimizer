from __future__ import annotations

from .models import SolarState


def measure_battery_power(
    s: SolarState,
    desired_import_limit: float,
    desired_export_limit: float,
) -> tuple[float, str, float]:
    if s.battery_power_sensor_kw is not None:
        battery_power_kw = float(s.battery_power_sensor_kw)
        return battery_power_kw, "direct_battery_sensor", 0.0

    if s.grid_import_power_kw is not None and s.grid_export_power_kw is not None:
        measured_import = max(float(s.grid_import_power_kw), 0.0)
        measured_export = max(float(s.grid_export_power_kw), 0.0)
        battery_power_kw = s.pv_kw + measured_import - measured_export - s.load_kw
        return battery_power_kw, "measured_grid_flow", measured_import

    effective_import_for_math = 0.0 if desired_import_limit <= 0.011 else desired_import_limit
    battery_power_kw = s.pv_kw + (effective_import_for_math - desired_export_limit) - s.load_kw
    return battery_power_kw, "setpoint_balance_fallback", effective_import_for_math