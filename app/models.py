"""
Pydantic models for the optimizer's internal state snapshot and decision output.
These are the "variables" block from the original YAML automations, expressed as
typed Python dataclasses.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class SolarState:
    """Live readings from SigEnergy and Solcast."""
    pv_kw: float = 0.0
    load_kw: float = 0.0
    grid_import_power_kw: Optional[float] = None
    grid_export_power_kw: Optional[float] = None
    battery_soc: float = 0.0
    battery_capacity_kwh: float = 10.0
    available_discharge_energy_kwh: float = 0.0
    ess_max_discharge_kw: float = 999.0
    ess_max_charge_kw: float = 999.0

    # Grid
    current_export_limit: float = 0.0
    current_import_limit: float = 0.0
    current_pv_max_power_limit: float = 25.0
    current_ems_mode: str = "Maximum Self Consumption"
    ha_control_enabled: bool = False

    # Prices
    current_price: float = 1.0          # $/kWh
    current_price_cents: float = 100.0  # cents/kWh (× multiplier)
    feedin_price: float = -999.0
    feedin_price_cents: float = -999.0
    price_is_actual: bool = False
    price_is_estimated: bool = False
    price_is_negative: bool = False
    feedin_is_negative: bool = False
    price_spike_active: bool = False
    demand_window_active: bool = False

    # Forecasts
    forecast_remaining_kwh: float = 0.0
    forecast_today_kwh: float = 0.0
    forecast_tomorrow_kwh: float = 0.0
    solar_power_now_kw: float = 0.0

    # Sun
    sun_elevation: float = 0.0
    next_sunrise_ts: Optional[float] = None
    next_sunset_ts: Optional[float] = None
    sun_above_horizon: bool = False
    hours_to_sunrise: float = 6.0
    hours_to_sunset: float = 0.0

    # Solcast detailed forecasts (list of {period_start, pv_estimate})
    solcast_detailed: list = field(default_factory=list)
    price_forecast_entries: list = field(default_factory=list)  # [{start_time, per_kwh}, ...]
    feedin_forecast_entries: list = field(default_factory=list)

    # Session tracking
    daily_export_kwh: float = 0.0
    daily_import_kwh: float = 0.0
    daily_load_kwh: float = 0.0
    daily_pv_kwh: float = 0.0
    daily_battery_charge_kwh: float = 0.0
    daily_battery_discharge_kwh: float = 0.0
    export_session_start_kwh: float = 0.0
    import_session_start_kwh: float = 0.0
    last_export_notification: str = "stopped"
    last_import_notification: str = "stopped"

    # Mode
    sigenergy_mode: str = "Automated"

    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Decision:
    """What the optimizer wants to do this cycle."""
    ems_mode: str = "Maximum Self Consumption"
    export_limit: float = 0.0
    import_limit: float = 0.0
    pv_max_power_limit: float = 25.0
    ess_charge_limit: float = 21.0
    ess_discharge_limit: float = 24.0

    export_reason: str = ""
    import_reason: str = ""
    outcome_reason: str = ""

    # Derived flags (useful for UI)
    is_evening_or_night: bool = False
    morning_dump_active: bool = False
    standby_holdoff_active: bool = False
    morning_slow_charge_active: bool = False
    evening_export_boost_active: bool = False
    solar_surplus_bypass: bool = False
    pv_safeguard_active: bool = False

    # Runtime-computed (set in _decide / _apply)
    battery_eta_formatted: str = "idle"
    battery_power_kw: float = 0.0
    min_soc_to_sunrise: float = 0.0
    export_spike_active: bool = False
    sunrise_soc_target: float = 0.0
    battery_full_safeguard: bool = False
    hours_to_sunrise: float = 6.0
    battery_soc_required_to_sunrise: float = 0.0
    needs_ha_control_switch: bool = False
    trace_gates: dict[str, bool] = field(default_factory=dict)
    trace_values: dict[str, float | str | bool | None] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
