"""
Pydantic models for the optimizer's internal state snapshot and decision output.
These are the "variables" block from the original YAML automations, expressed as
typed Python dataclasses.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass(frozen=True)
class HVACObservedValue:
    """Raw HA evidence retained separately from control-path defaults."""

    value: float | str | bool | None = None
    available: bool = False
    fresh: bool = False


@dataclass(frozen=True)
class HVACSolarInputContext:
    pv_power: HVACObservedValue = field(default_factory=HVACObservedValue)
    load_power: HVACObservedValue = field(default_factory=HVACObservedValue)
    battery_power: HVACObservedValue = field(default_factory=HVACObservedValue)
    grid_import_power: HVACObservedValue = field(default_factory=HVACObservedValue)
    grid_export_power: HVACObservedValue = field(default_factory=HVACObservedValue)
    solar_power_now: HVACObservedValue = field(default_factory=HVACObservedValue)
    sun_above_horizon: HVACObservedValue = field(default_factory=HVACObservedValue)
    control_mode: HVACObservedValue = field(default_factory=HVACObservedValue)
    observed_ems_mode: HVACObservedValue = field(default_factory=HVACObservedValue)
    observed_export_limit: HVACObservedValue = field(default_factory=HVACObservedValue)


@dataclass(frozen=True)
class HVACSolarPermissionResult:
    state: str
    reason_code: str
    source: str
    export_constraint_active: bool
    control_mode: str
    data_fresh: bool
    measured_opportunity_kw: Optional[float]
    estimated_opportunity_kw: Optional[float]
    hidden_opportunity_kw: Optional[float]
    start_threshold_kw: float
    continue_threshold_kw: float
    battery_discharge_kw: Optional[float]
    battery_flow_source: str
    observed_ems_mode: Optional[str]
    desired_ems_mode: Optional[str]
    previous_permission: str
    desired_export_limit_kw: Optional[float]
    observed_export_limit_kw: Optional[float]
    evaluated_at: datetime
    expires_at: datetime

    def attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {
            "reason_code": self.reason_code,
            "source": self.source,
            "scope": "solar_target_opportunity_only",
            "contract_version": "hvac_solar_permission_v2",
            "soc_policy_included": False,
            "consumer_safety_overlay_required": True,
            "controls_hvac_directly": False,
            "estimated_opportunity_usable": False,
            "estimated_opportunity_rejection_reason": "diagnostics_only",
            "export_constraint_active": self.export_constraint_active,
            "control_mode": self.control_mode,
            "data_fresh": self.data_fresh,
            "start_threshold_kw": self.start_threshold_kw,
            "continue_threshold_kw": self.continue_threshold_kw,
            "battery_flow_source": self.battery_flow_source,
            "previous_permission": self.previous_permission,
            "evaluated_at": self.evaluated_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
        }
        optional = {
            "measured_opportunity_kw": self.measured_opportunity_kw,
            "estimated_opportunity_kw": self.estimated_opportunity_kw,
            "hidden_opportunity_kw": self.hidden_opportunity_kw,
            "battery_discharge_kw": self.battery_discharge_kw,
            "observed_ems_mode": self.observed_ems_mode,
            "desired_ems_mode": self.desired_ems_mode,
            "desired_export_limit_kw": self.desired_export_limit_kw,
            "observed_export_limit_kw": self.observed_export_limit_kw,
        }
        attrs.update({key: value for key, value in optional.items() if value is not None})
        return attrs


@dataclass
class SolarState:
    """Live readings from SigEnergy and Solcast."""
    pv_kw: float = 0.0
    load_kw: float = 0.0
    grid_import_power_kw: Optional[float] = None
    grid_export_power_kw: Optional[float] = None
    battery_power_sensor_kw: Optional[float] = None
    battery_soc: float = 0.0
    battery_capacity_kwh: float = 10.0
    available_discharge_energy_kwh: float = 0.0
    ess_max_discharge_kw: float = 999.0
    ess_max_charge_kw: float = 999.0

    # Grid
    current_export_limit: float = 0.0
    current_import_limit: float = 0.0
    current_pv_max_power_limit: float = 25.0
    current_ess_charge_limit: Optional[float] = None
    current_ess_discharge_limit: Optional[float] = None
    ess_charge_limit_entity_max_kw: Optional[float] = None
    ess_discharge_limit_entity_max_kw: Optional[float] = None
    current_ems_mode: str = "Maximum Self Consumption"
    ha_control_enabled: bool = False
    ha_control_switch_available: bool = False
    ha_control_switch_state: str = "missing"

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

    # Permission-only evidence; existing optimiser controls do not read this context.
    hvac_solar_inputs: HVACSolarInputContext = field(default_factory=HVACSolarInputContext)

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
    protected_reserve_soc: float = 0.0
    export_surplus_soc: float = 0.0
    stored_energy_value_floor: float = 0.0
    export_value_gate_would_allow: bool = False
    export_value_gate_would_block: bool = False
    export_value_gate_reason: str = ""
    needs_ha_control_switch: bool = False
    trace_gates: dict[str, bool] = field(default_factory=dict)
    trace_values: dict[str, float | str | bool | None] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
