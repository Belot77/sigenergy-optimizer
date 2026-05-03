"""
Configuration â€” loaded from environment variables (or a .env file).
Every setting here maps 1:1 to a blueprint input from the original YAML automations.
"""
from __future__ import annotations
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    # ------------------------------------------------------------------
    # Home Assistant connection
    # ------------------------------------------------------------------
    ha_url: str = Field("http://homeassistant.local:8123")
    ha_token: str = Field("")
    ui_api_key: str = Field("")
    allow_loopback_without_api_key: bool = Field(True)
    require_api_key_for_all_mutations: bool = Field(False)
    require_api_key_for_config_read: bool = Field(False)
    ess_limit_fallback_kw: float = Field(30.0)
    cors_allowed_origins: str = Field(
        "http://localhost,http://127.0.0.1,http://[::1]",
    )

    # ------------------------------------------------------------------
    # Polling interval
    # ------------------------------------------------------------------
    poll_interval_seconds: int = Field(30)

    # ------------------------------------------------------------------
    # Notifications
    # ------------------------------------------------------------------
    notification_service: str = Field("")
    auto_enable_ha_control: bool = Field(True)
    notify_daily_summary: bool = Field(True)
    daily_summary_time: str = Field("23:55")
    notify_morning_summary: bool = Field(True)
    morning_summary_time: str = Field("07:30")
    notify_export_started_stopped: bool = Field(True)
    notify_import_started_stopped: bool = Field(True)
    notify_battery_alerts: bool = Field(True)
    notify_price_spike_alert: bool = Field(True)
    notify_demand_window_alert: bool = Field(True)

    # ------------------------------------------------------------------
    # EMS entity IDs
    # ------------------------------------------------------------------
    ha_control_switch: str = Field("switch.sigen_plant_remote_ems_controled_by_home_assistant")
    ems_mode_select: str = Field("select.sigen_plant_remote_ems_control_mode")
    grid_export_limit: str = Field("number.sigen_plant_grid_export_limitation")
    grid_import_limit: str = Field("number.sigen_plant_grid_import_limitation")
    pv_max_power_limit: str = Field("number.sigen_plant_pv_max_power_limit")
    ess_max_charging_limit: str = Field("number.sigen_plant_ess_max_charging_limit")
    ess_max_discharging_limit: str = Field("number.sigen_plant_ess_max_discharging_limit")

    # ------------------------------------------------------------------
    # SigEnergy sensors
    # ------------------------------------------------------------------
    pv_power_sensor: str = Field("sensor.sigen_plant_pv_power")
    consumed_power_sensor: str = Field("sensor.sigen_plant_consumed_power")
    grid_import_power_sensor: str = Field("sensor.sigen_plant_grid_import_power")
    grid_export_power_sensor: str = Field("sensor.sigen_plant_grid_export_power")
    battery_power_sensor: str = Field("sensor.sigen_plant_battery_power")
    battery_power_sensor_invert: bool = Field(False)
    battery_soc_sensor: str = Field("sensor.sigen_plant_battery_state_of_charge")
    rated_capacity_sensor: str = Field("sensor.sigen_plant_rated_energy_capacity")
    available_discharge_sensor: str = Field("sensor.sigen_plant_available_max_discharging_capacity")
    ess_rated_discharge_power_sensor: str = Field("sensor.sigen_inverter_ess_rated_discharge_power")
    ess_rated_charge_power_sensor: str = Field("sensor.sigen_plant_ess_rated_charging_power")
    sun_entity: str = Field("sun.sun")
    daily_export_energy: str = Field("sensor.sigen_plant_daily_grid_export_energy")
    daily_import_energy: str = Field("sensor.sigen_plant_daily_grid_import_energy")
    daily_import_cost_entity: str = Field("sensor.sigen_plant_daily_grid_import_energy_cost")
    daily_export_compensation_entity: str = Field("sensor.sigen_plant_daily_grid_export_energy_compensation")
    daily_load_energy: str = Field("sensor.sigen_plant_daily_load_consumption")
    daily_battery_charge_energy: str = Field("sensor.sigen_plant_daily_battery_charge_energy")
    daily_battery_discharge_energy: str = Field("sensor.sigen_plant_daily_battery_discharge_energy")
    daily_pv_energy: str = Field("sensor.sigen_plant_daily_pv_generation")

    # ------------------------------------------------------------------
    # Earnings sources
    # ------------------------------------------------------------------
    earnings_source: str = Field("auto")
    earnings_import_energy_entity: str = Field("")
    earnings_export_energy_entity: str = Field("")
    earnings_import_value_entity: str = Field("")
    earnings_export_value_entity: str = Field("")
    earnings_custom_mode: str = Field("daily")
    amber_balance_import_kwh_entity: str = Field("sensor.import_kwh")
    amber_balance_export_kwh_entity: str = Field("sensor.export_kwh")
    amber_balance_import_value_entity: str = Field("sensor.import")
    amber_balance_export_value_entity: str = Field("sensor.export")

    # ------------------------------------------------------------------
    # Amber / price sensors
    # ------------------------------------------------------------------
    price_sensor: str = Field("sensor.amber_general_price")
    feedin_sensor: str = Field("sensor.amber_feed_in_price")
    feedin_forecast_sensor: str = Field("sensor.amber_feed_in_price_detailed")
    demand_window_sensor: str = Field("binary_sensor.amber_demand_window")
    price_spike_sensor: str = Field("binary_sensor.amber_price_spike")
    price_forecast_sensor: str = Field("sensor.amber_general_forecast")
    price_forecast_attribute: str = Field("forecasts")
    price_forecast_value_key: str = Field("per_kwh")
    price_forecast_time_key: str = Field("start_time")
    price_multiplier: float = Field(100.0)  # $/kWh â†’ cents
    feedin_forecast_attribute: str = Field("forecasts")
    feedin_forecast_value_key: str = Field("per_kwh")

    # ------------------------------------------------------------------
    # Solcast / forecast sensors
    # ------------------------------------------------------------------
    forecast_remaining_sensor: str = Field("sensor.solcast_pv_forecast_forecast_remaining_today")
    forecast_today_sensor: str = Field("sensor.solcast_pv_forecast_forecast_today")
    forecast_tomorrow_sensor: str = Field("sensor.solcast_pv_forecast_forecast_tomorrow")
    solar_power_now_sensor: str = Field("sensor.solcast_pv_forecast_power_now")
    productive_solar_threshold_kw: float = Field(1.0)
    solcast_forecast_period_hours: float = Field(0.5)

    # ------------------------------------------------------------------
    # HA helpers
    # ------------------------------------------------------------------
    automated_export_flag: str = Field("input_boolean.sigenergy_automated_export")
    export_session_start: str = Field("input_number.sigenergy_export_session_start_kwh")
    import_session_start: str = Field("input_number.sigenergy_import_session_start_kwh")
    last_export_notification: str = Field("input_text.sigenergy_last_export_notification")
    last_import_notification: str = Field("input_text.sigenergy_last_import_notification")
    reason_text_helper: str = Field("input_text.sigenergy_reason")
    min_soc_to_sunrise_helper: str = Field("input_number.battery_min_soc_to_last_till_sunrise")
    sigenergy_mode_select: str = Field("input_select.sigenergy_mode")

    # ------------------------------------------------------------------
    # Export pricing thresholds and caps
    # ------------------------------------------------------------------
    export_threshold_low: float = Field(0.10)
    export_threshold_medium: float = Field(0.20)
    export_threshold_high: float = Field(1.00)
    export_limit_low: float = Field(5.0)
    export_limit_medium: float = Field(12.0)
    export_limit_high: float = Field(25.0)
    export_spike_threshold: float = Field(0.0)
    export_spike_min_soc: float = Field(0.0)
    export_spike_full_power: bool = Field(False)
    allow_low_medium_export_positive_fit: bool = Field(False)
    allow_positive_fit_battery_discharging: bool = Field(False)

    # ------------------------------------------------------------------
    # Import pricing thresholds and caps
    # ------------------------------------------------------------------
    import_threshold_low: float = Field(0.0)
    import_threshold_medium: float = Field(-0.15)
    import_threshold_high: float = Field(-0.30)
    import_limit_low: float = Field(30.0)
    import_limit_medium: float = Field(30.0)
    import_limit_high: float = Field(30.0)

    # ------------------------------------------------------------------
    # SoC floors and reserves
    # ------------------------------------------------------------------
    min_export_target_soc: float = Field(90.0)
    min_soc_floor: float = Field(20.0)
    night_reserve_soc: float = Field(30.0)
    night_reserve_buffer: float = Field(10.0)
    max_battery_soc: float = Field(50.0)
    sunrise_reserve_soc: float = Field(10.0)
    sunrise_safety_factor: float = Field(1.0)
    sunrise_buffer_percent: float = Field(0.0)
    sunrise_export_relax_percent: float = Field(12.0)

    # ------------------------------------------------------------------
    # Evening boost
    # ------------------------------------------------------------------
    evening_boost_enabled: bool = Field(True)
    evening_aggressive_floor: float = Field(35.0)
    evening_boost_forecast_safety: float = Field(1.1)
    evening_boost_min_tomorrow_forecast_kwh: float = Field(100.0)

    # ------------------------------------------------------------------
    # Cheap import top-up
    # ------------------------------------------------------------------
    max_price_threshold: float = Field(0.015)
    target_battery_charge: float = Field(2.0)
    cap_total_import: float = Field(30.0)
    pv_max_power_normal: float = Field(25.0)
    daytime_topup_max_soc: float = Field(50.0)

    # ------------------------------------------------------------------
    # Forecast holdoff
    # ------------------------------------------------------------------
    standby_holdoff_enabled: bool = Field(True)
    slow_charge_holdoff: bool = Field(False)
    slow_charge_limit_kw: float = Field(2.0)
    pv_forecast_holdoff_kwh: float = Field(120.0)
    negative_price_forecast_lookahead_hours: int = Field(12)
    standby_holdoff_end_time: str = Field("11:00")

    # ------------------------------------------------------------------
    # Morning slow charge
    # ------------------------------------------------------------------
    morning_slow_charge_enabled: bool = Field(False)
    morning_slow_charge_until: str = Field("11:00")
    morning_slow_charge_rate_kw: float = Field(2.0)
    morning_slow_charge_min_feedin_price: float = Field(0.0)
    morning_slow_charge_base_load_kw: float = Field(0.5)
    morning_slow_charge_sunset_cutoff: float = Field(1.0)
    morning_slow_export_start_margin_kw: float = Field(0.7)
    morning_slow_export_stop_margin_kw: float = Field(0.2)
    morning_slow_export_ramp_up_step_kw: float = Field(0.8)
    morning_slow_export_ramp_down_step_kw: float = Field(1.2)
    morning_slow_export_probe_enabled: bool = Field(True)
    morning_slow_export_probe_step_kw: float = Field(0.4)
    morning_slow_export_probe_saturation_margin_kw: float = Field(0.2)

    # ------------------------------------------------------------------
    # Morning dump
    # ------------------------------------------------------------------
    morning_dump_enabled: bool = Field(False)
    morning_dump_hours_before_sunrise: float = Field(2.0)

    # ------------------------------------------------------------------
    # Battery full safeguard
    # ------------------------------------------------------------------
    battery_full_safeguard_enabled: bool = Field(True)
    battery_full_hours_before_sunset: float = Field(2.0)
    battery_full_forecast_multiplier: float = Field(0.8)

    # ------------------------------------------------------------------
    # Anti-flap hysteresis
    # ------------------------------------------------------------------
    soc_hysteresis: float = Field(2.0)
    min_change_threshold: float = Field(0.1)
    min_grid_transfer_kw: float = Field(0.5)
    export_hysteresis_percent: float = Field(0.8)
    price_hysteresis: float = Field(0.01)

    # ------------------------------------------------------------------
    # Forecast safety
    # ------------------------------------------------------------------
    forecast_safety_charging: float = Field(1.25)
    forecast_safety_export: float = Field(1.1)

    # ------------------------------------------------------------------
    # Export scheduling
    # ------------------------------------------------------------------
    export_soc_span_day: float = Field(20.0)
    export_discharge_window_hours: float = Field(3.0)
    sun_elevation_evening_threshold: float = Field(10.0)
    sunset_export_grace_hours: float = Field(2.0)
    evening_mode_hours_before_sunset: float = Field(1.0)
    export_guard_relax_soc: float = Field(90.0)

    # ------------------------------------------------------------------
    # Solar surplus bypass
    # ------------------------------------------------------------------
    solar_surplus_bypass_enabled: bool = Field(True)
    solar_surplus_start_multiplier: float = Field(2.0)
    solar_surplus_stop_multiplier: float = Field(1.25)
    solar_surplus_min_pv_margin: float = Field(0.5)

    # ------------------------------------------------------------------
    # Manual mode labels (mirrors sigenergy_manual_control blueprint)
    # ------------------------------------------------------------------
    automated_option: str = Field("Automated")
    full_export_option: str = Field("Force Full Export")
    full_import_option: str = Field("Force Full Import")
    full_import_pv_option: str = Field("Force Full Import + PV")
    block_flow_option: str = Field("Prevent Import & Export")
    manual_option: str = Field("Manual")
    block_flow_limit_value: float = Field(0.01)
    ess_charge_limit_value: float = Field(25.0)
    ess_discharge_limit_value: float = Field(25.0)
    export_limit_value: float = Field(30.0)
    import_limit_value: float = Field(30.0)
    pv_max_power_value: float = Field(30.0)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()  # type: ignore[call-arg]  # pydantic-settings reads all fields from env/defaults

