"""
Configuration — loaded from environment variables (or a .env file).
Every setting here maps 1:1 to a blueprint input from the original YAML automations.
"""
from __future__ import annotations
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # ------------------------------------------------------------------
    # Home Assistant connection
    # ------------------------------------------------------------------
    ha_url: str = Field("http://homeassistant.local:8123", env="HA_URL")
    ha_token: str = Field("", env="HA_TOKEN")
    ui_api_key: str = Field("", env="UI_API_KEY")
    allow_loopback_without_api_key: bool = Field(True, env="ALLOW_LOOPBACK_WITHOUT_API_KEY")
    require_api_key_for_all_mutations: bool = Field(False, env="REQUIRE_API_KEY_FOR_ALL_MUTATIONS")
    require_api_key_for_config_read: bool = Field(False, env="REQUIRE_API_KEY_FOR_CONFIG_READ")
    ess_limit_fallback_kw: float = Field(30.0, env="ESS_LIMIT_FALLBACK_KW")
    cors_allowed_origins: str = Field(
        "http://localhost,http://127.0.0.1,http://[::1]",
        env="CORS_ALLOWED_ORIGINS",
    )

    # ------------------------------------------------------------------
    # Polling interval
    # ------------------------------------------------------------------
    poll_interval_seconds: int = Field(30, env="POLL_INTERVAL_SECONDS")

    # ------------------------------------------------------------------
    # Notifications
    # ------------------------------------------------------------------
    notification_service: str = Field("", env="NOTIFICATION_SERVICE")
    auto_enable_ha_control: bool = Field(True, env="AUTO_ENABLE_HA_CONTROL")
    notify_daily_summary: bool = Field(True, env="NOTIFY_DAILY_SUMMARY")
    daily_summary_time: str = Field("23:55", env="DAILY_SUMMARY_TIME")
    notify_morning_summary: bool = Field(True, env="NOTIFY_MORNING_SUMMARY")
    morning_summary_time: str = Field("07:30", env="MORNING_SUMMARY_TIME")
    notify_export_started_stopped: bool = Field(True, env="NOTIFY_EXPORT_STARTED_STOPPED")
    notify_import_started_stopped: bool = Field(True, env="NOTIFY_IMPORT_STARTED_STOPPED")
    notify_battery_alerts: bool = Field(True, env="NOTIFY_BATTERY_ALERTS")
    notify_price_spike_alert: bool = Field(True, env="NOTIFY_PRICE_SPIKE_ALERT")
    notify_demand_window_alert: bool = Field(True, env="NOTIFY_DEMAND_WINDOW_ALERT")

    # ------------------------------------------------------------------
    # EMS entity IDs
    # ------------------------------------------------------------------
    ha_control_switch: str = Field("switch.sigen_plant_remote_ems_controled_by_home_assistant", env="HA_CONTROL_SWITCH")
    ems_mode_select: str = Field("select.sigen_plant_remote_ems_control_mode", env="EMS_MODE_SELECT")
    grid_export_limit: str = Field("number.sigen_plant_grid_export_limitation", env="GRID_EXPORT_LIMIT")
    grid_import_limit: str = Field("number.sigen_plant_grid_import_limitation", env="GRID_IMPORT_LIMIT")
    pv_max_power_limit: str = Field("number.sigen_plant_pv_max_power_limit", env="PV_MAX_POWER_LIMIT")
    ess_max_charging_limit: str = Field("number.sigen_plant_ess_max_charging_limit", env="ESS_MAX_CHARGING_LIMIT")
    ess_max_discharging_limit: str = Field("number.sigen_plant_ess_max_discharging_limit", env="ESS_MAX_DISCHARGING_LIMIT")

    # ------------------------------------------------------------------
    # SigEnergy sensors
    # ------------------------------------------------------------------
    pv_power_sensor: str = Field("sensor.sigen_plant_pv_power", env="PV_POWER_SENSOR")
    consumed_power_sensor: str = Field("sensor.sigen_plant_consumed_power", env="CONSUMED_POWER_SENSOR")
    grid_import_power_sensor: str = Field("sensor.sigen_plant_grid_import_power", env="GRID_IMPORT_POWER_SENSOR")
    grid_export_power_sensor: str = Field("sensor.sigen_plant_grid_export_power", env="GRID_EXPORT_POWER_SENSOR")
    battery_power_sensor: str = Field("sensor.sigen_plant_battery_power", env="BATTERY_POWER_SENSOR")
    battery_power_sensor_invert: bool = Field(False, env="BATTERY_POWER_SENSOR_INVERT")
    battery_soc_sensor: str = Field("sensor.sigen_plant_battery_state_of_charge", env="BATTERY_SOC_SENSOR")
    rated_capacity_sensor: str = Field("sensor.sigen_plant_rated_energy_capacity", env="RATED_CAPACITY_SENSOR")
    available_discharge_sensor: str = Field("sensor.sigen_plant_available_max_discharging_capacity", env="AVAILABLE_DISCHARGE_SENSOR")
    ess_rated_discharge_power_sensor: str = Field("sensor.sigen_inverter_ess_rated_discharge_power", env="ESS_RATED_DISCHARGE_POWER_SENSOR")
    ess_rated_charge_power_sensor: str = Field("sensor.sigen_plant_ess_rated_charging_power", env="ESS_RATED_CHARGE_POWER_SENSOR")
    sun_entity: str = Field("sun.sun", env="SUN_ENTITY")
    daily_export_energy: str = Field("sensor.sigen_plant_daily_grid_export_energy", env="DAILY_EXPORT_ENERGY")
    daily_import_energy: str = Field("sensor.sigen_plant_daily_grid_import_energy", env="DAILY_IMPORT_ENERGY")
    daily_import_cost_entity: str = Field("sensor.sigen_plant_daily_grid_import_energy_cost", env="DAILY_IMPORT_COST_ENTITY")
    daily_export_compensation_entity: str = Field("sensor.sigen_plant_daily_grid_export_energy_compensation", env="DAILY_EXPORT_COMPENSATION_ENTITY")
    daily_load_energy: str = Field("sensor.sigen_plant_daily_load_consumption", env="DAILY_LOAD_ENERGY")
    daily_battery_charge_energy: str = Field("sensor.sigen_plant_daily_battery_charge_energy", env="DAILY_BATTERY_CHARGE_ENERGY")
    daily_battery_discharge_energy: str = Field("sensor.sigen_plant_daily_battery_discharge_energy", env="DAILY_BATTERY_DISCHARGE_ENERGY")
    daily_pv_energy: str = Field("sensor.sigen_plant_daily_pv_generation", env="DAILY_PV_ENERGY")

    # ------------------------------------------------------------------
    # Earnings sources
    # ------------------------------------------------------------------
    earnings_source: str = Field("auto", env="EARNINGS_SOURCE")
    earnings_import_energy_entity: str = Field("", env="EARNINGS_IMPORT_ENERGY_ENTITY")
    earnings_export_energy_entity: str = Field("", env="EARNINGS_EXPORT_ENERGY_ENTITY")
    earnings_import_value_entity: str = Field("", env="EARNINGS_IMPORT_VALUE_ENTITY")
    earnings_export_value_entity: str = Field("", env="EARNINGS_EXPORT_VALUE_ENTITY")
    earnings_custom_mode: str = Field("daily", env="EARNINGS_CUSTOM_MODE")
    amber_balance_import_kwh_entity: str = Field("sensor.import_kwh", env="AMBER_BALANCE_IMPORT_KWH_ENTITY")
    amber_balance_export_kwh_entity: str = Field("sensor.export_kwh", env="AMBER_BALANCE_EXPORT_KWH_ENTITY")
    amber_balance_import_value_entity: str = Field("sensor.import", env="AMBER_BALANCE_IMPORT_VALUE_ENTITY")
    amber_balance_export_value_entity: str = Field("sensor.export", env="AMBER_BALANCE_EXPORT_VALUE_ENTITY")

    # ------------------------------------------------------------------
    # Amber / price sensors
    # ------------------------------------------------------------------
    price_sensor: str = Field("sensor.amber_general_price", env="PRICE_SENSOR")
    feedin_sensor: str = Field("sensor.amber_feed_in_price", env="FEEDIN_SENSOR")
    feedin_forecast_sensor: str = Field("sensor.amber_feed_in_price_detailed", env="FEEDIN_FORECAST_SENSOR")
    demand_window_sensor: str = Field("binary_sensor.amber_demand_window", env="DEMAND_WINDOW_SENSOR")
    price_spike_sensor: str = Field("binary_sensor.amber_price_spike", env="PRICE_SPIKE_SENSOR")
    price_forecast_sensor: str = Field("sensor.amber_general_forecast", env="PRICE_FORECAST_SENSOR")
    price_forecast_attribute: str = Field("forecasts", env="PRICE_FORECAST_ATTRIBUTE")
    price_forecast_value_key: str = Field("per_kwh", env="PRICE_FORECAST_VALUE_KEY")
    price_forecast_time_key: str = Field("start_time", env="PRICE_FORECAST_TIME_KEY")
    price_multiplier: float = Field(100.0, env="PRICE_MULTIPLIER")  # $/kWh → cents
    feedin_forecast_attribute: str = Field("forecasts", env="FEEDIN_FORECAST_ATTRIBUTE")
    feedin_forecast_value_key: str = Field("per_kwh", env="FEEDIN_FORECAST_VALUE_KEY")

    # ------------------------------------------------------------------
    # Solcast / forecast sensors
    # ------------------------------------------------------------------
    forecast_remaining_sensor: str = Field("sensor.solcast_pv_forecast_forecast_remaining_today", env="FORECAST_REMAINING_SENSOR")
    forecast_today_sensor: str = Field("sensor.solcast_pv_forecast_forecast_today", env="FORECAST_TODAY_SENSOR")
    forecast_tomorrow_sensor: str = Field("sensor.solcast_pv_forecast_forecast_tomorrow", env="FORECAST_TOMORROW_SENSOR")
    solar_power_now_sensor: str = Field("sensor.solcast_pv_forecast_power_now", env="SOLAR_POWER_NOW_SENSOR")
    productive_solar_threshold_kw: float = Field(1.0, env="PRODUCTIVE_SOLAR_THRESHOLD_KW")
    solcast_forecast_period_hours: float = Field(0.5, env="SOLCAST_FORECAST_PERIOD_HOURS")

    # ------------------------------------------------------------------
    # HA helpers
    # ------------------------------------------------------------------
    automated_export_flag: str = Field("input_boolean.sigenergy_automated_export", env="AUTOMATED_EXPORT_FLAG")
    export_session_start: str = Field("input_number.sigenergy_export_session_start_kwh", env="EXPORT_SESSION_START")
    import_session_start: str = Field("input_number.sigenergy_import_session_start_kwh", env="IMPORT_SESSION_START")
    last_export_notification: str = Field("input_text.sigenergy_last_export_notification", env="LAST_EXPORT_NOTIFICATION")
    last_import_notification: str = Field("input_text.sigenergy_last_import_notification", env="LAST_IMPORT_NOTIFICATION")
    reason_text_helper: str = Field("input_text.sigenergy_reason", env="REASON_TEXT_HELPER")
    min_soc_to_sunrise_helper: str = Field("input_number.battery_min_soc_to_last_till_sunrise", env="MIN_SOC_TO_SUNRISE_HELPER")
    sigenergy_mode_select: str = Field("input_select.sigenergy_mode", env="SIGENERGY_MODE_SELECT")

    # ------------------------------------------------------------------
    # Export pricing thresholds and caps
    # ------------------------------------------------------------------
    export_threshold_low: float = Field(0.10, env="EXPORT_THRESHOLD_LOW")
    export_threshold_medium: float = Field(0.20, env="EXPORT_THRESHOLD_MEDIUM")
    export_threshold_high: float = Field(1.00, env="EXPORT_THRESHOLD_HIGH")
    export_limit_low: float = Field(5.0, env="EXPORT_LIMIT_LOW")
    export_limit_medium: float = Field(12.0, env="EXPORT_LIMIT_MEDIUM")
    export_limit_high: float = Field(25.0, env="EXPORT_LIMIT_HIGH")
    export_spike_threshold: float = Field(0.0, env="EXPORT_SPIKE_THRESHOLD")
    export_spike_min_soc: float = Field(0.0, env="EXPORT_SPIKE_MIN_SOC")
    export_spike_full_power: bool = Field(False, env="EXPORT_SPIKE_FULL_POWER")
    allow_low_medium_export_positive_fit: bool = Field(False, env="ALLOW_LOW_MEDIUM_EXPORT_POSITIVE_FIT")
    allow_positive_fit_battery_discharging: bool = Field(False, env="ALLOW_POSITIVE_FIT_BATTERY_DISCHARGING")

    # ------------------------------------------------------------------
    # Import pricing thresholds and caps
    # ------------------------------------------------------------------
    import_threshold_low: float = Field(0.0, env="IMPORT_THRESHOLD_LOW")
    import_threshold_medium: float = Field(-0.15, env="IMPORT_THRESHOLD_MEDIUM")
    import_threshold_high: float = Field(-0.30, env="IMPORT_THRESHOLD_HIGH")
    import_limit_low: float = Field(30.0, env="IMPORT_LIMIT_LOW")
    import_limit_medium: float = Field(30.0, env="IMPORT_LIMIT_MEDIUM")
    import_limit_high: float = Field(30.0, env="IMPORT_LIMIT_HIGH")

    # ------------------------------------------------------------------
    # SoC floors and reserves
    # ------------------------------------------------------------------
    min_export_target_soc: float = Field(90.0, env="MIN_EXPORT_TARGET_SOC")
    min_soc_floor: float = Field(20.0, env="MIN_SOC_FLOOR")
    night_reserve_soc: float = Field(30.0, env="NIGHT_RESERVE_SOC")
    night_reserve_buffer: float = Field(10.0, env="NIGHT_RESERVE_BUFFER")
    max_battery_soc: float = Field(50.0, env="MAX_BATTERY_SOC")
    sunrise_reserve_soc: float = Field(10.0, env="SUNRISE_RESERVE_SOC")
    sunrise_safety_factor: float = Field(1.0, env="SUNRISE_SAFETY_FACTOR")
    sunrise_buffer_percent: float = Field(0.0, env="SUNRISE_BUFFER_PERCENT")
    sunrise_export_relax_percent: float = Field(12.0, env="SUNRISE_EXPORT_RELAX_PERCENT")

    # ------------------------------------------------------------------
    # Evening boost
    # ------------------------------------------------------------------
    evening_boost_enabled: bool = Field(True, env="EVENING_BOOST_ENABLED")
    evening_aggressive_floor: float = Field(35.0, env="EVENING_AGGRESSIVE_FLOOR")
    evening_boost_forecast_safety: float = Field(1.1, env="EVENING_BOOST_FORECAST_SAFETY")

    # ------------------------------------------------------------------
    # Cheap import top-up
    # ------------------------------------------------------------------
    max_price_threshold: float = Field(0.015, env="MAX_PRICE_THRESHOLD")
    target_battery_charge: float = Field(2.0, env="TARGET_BATTERY_CHARGE")
    cap_total_import: float = Field(30.0, env="CAP_TOTAL_IMPORT")
    pv_max_power_normal: float = Field(25.0, env="PV_MAX_POWER_NORMAL")
    daytime_topup_max_soc: float = Field(50.0, env="DAYTIME_TOPUP_MAX_SOC")

    # ------------------------------------------------------------------
    # Forecast holdoff
    # ------------------------------------------------------------------
    standby_holdoff_enabled: bool = Field(True, env="STANDBY_HOLDOFF_ENABLED")
    slow_charge_holdoff: bool = Field(False, env="SLOW_CHARGE_HOLDOFF")
    slow_charge_limit_kw: float = Field(2.0, env="SLOW_CHARGE_LIMIT_KW")
    pv_forecast_holdoff_kwh: float = Field(120.0, env="PV_FORECAST_HOLDOFF_KWH")
    negative_price_forecast_lookahead_hours: int = Field(12, env="NEGATIVE_PRICE_FORECAST_LOOKAHEAD_HOURS")
    standby_holdoff_end_time: str = Field("11:00", env="STANDBY_HOLDOFF_END_TIME")

    # ------------------------------------------------------------------
    # Morning slow charge
    # ------------------------------------------------------------------
    morning_slow_charge_enabled: bool = Field(False, env="MORNING_SLOW_CHARGE_ENABLED")
    morning_slow_charge_until: str = Field("11:00", env="MORNING_SLOW_CHARGE_UNTIL")
    morning_slow_charge_rate_kw: float = Field(2.0, env="MORNING_SLOW_CHARGE_RATE_KW")
    morning_slow_charge_min_feedin_price: float = Field(0.0, env="MORNING_SLOW_CHARGE_MIN_FEEDIN_PRICE")
    morning_slow_charge_base_load_kw: float = Field(0.5, env="MORNING_SLOW_CHARGE_BASE_LOAD_KW")
    morning_slow_charge_sunset_cutoff: float = Field(1.0, env="MORNING_SLOW_CHARGE_SUNSET_CUTOFF")
    morning_slow_export_start_margin_kw: float = Field(0.7, env="MORNING_SLOW_EXPORT_START_MARGIN_KW")
    morning_slow_export_stop_margin_kw: float = Field(0.2, env="MORNING_SLOW_EXPORT_STOP_MARGIN_KW")
    morning_slow_export_ramp_up_step_kw: float = Field(0.8, env="MORNING_SLOW_EXPORT_RAMP_UP_STEP_KW")
    morning_slow_export_ramp_down_step_kw: float = Field(1.2, env="MORNING_SLOW_EXPORT_RAMP_DOWN_STEP_KW")
    morning_slow_export_probe_enabled: bool = Field(True, env="MORNING_SLOW_EXPORT_PROBE_ENABLED")
    morning_slow_export_probe_step_kw: float = Field(0.4, env="MORNING_SLOW_EXPORT_PROBE_STEP_KW")
    morning_slow_export_probe_saturation_margin_kw: float = Field(0.2, env="MORNING_SLOW_EXPORT_PROBE_SATURATION_MARGIN_KW")

    # ------------------------------------------------------------------
    # Morning dump
    # ------------------------------------------------------------------
    morning_dump_enabled: bool = Field(False, env="MORNING_DUMP_ENABLED")
    morning_dump_hours_before_sunrise: float = Field(2.0, env="MORNING_DUMP_HOURS_BEFORE_SUNRISE")

    # ------------------------------------------------------------------
    # Battery full safeguard
    # ------------------------------------------------------------------
    battery_full_safeguard_enabled: bool = Field(True, env="BATTERY_FULL_SAFEGUARD_ENABLED")
    battery_full_hours_before_sunset: float = Field(2.0, env="BATTERY_FULL_HOURS_BEFORE_SUNSET")
    battery_full_forecast_multiplier: float = Field(0.8, env="BATTERY_FULL_FORECAST_MULTIPLIER")

    # ------------------------------------------------------------------
    # Anti-flap hysteresis
    # ------------------------------------------------------------------
    soc_hysteresis: float = Field(2.0, env="SOC_HYSTERESIS")
    min_change_threshold: float = Field(0.1, env="MIN_CHANGE_THRESHOLD")
    min_grid_transfer_kw: float = Field(0.5, env="MIN_GRID_TRANSFER_KW")
    export_hysteresis_percent: float = Field(0.8, env="EXPORT_HYSTERESIS_PERCENT")
    price_hysteresis: float = Field(0.01, env="PRICE_HYSTERESIS")

    # ------------------------------------------------------------------
    # Forecast safety
    # ------------------------------------------------------------------
    forecast_safety_charging: float = Field(1.25, env="FORECAST_SAFETY_CHARGING")
    forecast_safety_export: float = Field(1.1, env="FORECAST_SAFETY_EXPORT")

    # ------------------------------------------------------------------
    # Export scheduling
    # ------------------------------------------------------------------
    export_soc_span_day: float = Field(20.0, env="EXPORT_SOC_SPAN_DAY")
    export_discharge_window_hours: float = Field(3.0, env="EXPORT_DISCHARGE_WINDOW_HOURS")
    sun_elevation_evening_threshold: float = Field(10.0, env="SUN_ELEVATION_EVENING_THRESHOLD")
    sunset_export_grace_hours: float = Field(2.0, env="SUNSET_EXPORT_GRACE_HOURS")
    evening_mode_hours_before_sunset: float = Field(1.0, env="EVENING_MODE_HOURS_BEFORE_SUNSET")
    export_guard_relax_soc: float = Field(90.0, env="EXPORT_GUARD_RELAX_SOC")

    # ------------------------------------------------------------------
    # Solar surplus bypass
    # ------------------------------------------------------------------
    solar_surplus_bypass_enabled: bool = Field(True, env="SOLAR_SURPLUS_BYPASS_ENABLED")
    solar_surplus_start_multiplier: float = Field(2.0, env="SOLAR_SURPLUS_START_MULTIPLIER")
    solar_surplus_stop_multiplier: float = Field(1.25, env="SOLAR_SURPLUS_STOP_MULTIPLIER")
    solar_surplus_min_pv_margin: float = Field(0.5, env="SOLAR_SURPLUS_MIN_PV_MARGIN")

    # ------------------------------------------------------------------
    # Manual mode labels (mirrors sigenergy_manual_control blueprint)
    # ------------------------------------------------------------------
    automated_option: str = Field("Automated", env="AUTOMATED_OPTION")
    full_export_option: str = Field("Force Full Export", env="FULL_EXPORT_OPTION")
    full_import_option: str = Field("Force Full Import", env="FULL_IMPORT_OPTION")
    full_import_pv_option: str = Field("Force Full Import + PV", env="FULL_IMPORT_PV_OPTION")
    block_flow_option: str = Field("Prevent Import & Export", env="BLOCK_FLOW_OPTION")
    manual_option: str = Field("Manual", env="MANUAL_OPTION")
    block_flow_limit_value: float = Field(0.01, env="BLOCK_FLOW_LIMIT_VALUE")
    ess_charge_limit_value: float = Field(25.0, env="ESS_CHARGE_LIMIT_VALUE")
    ess_discharge_limit_value: float = Field(25.0, env="ESS_DISCHARGE_LIMIT_VALUE")
    export_limit_value: float = Field(30.0, env="EXPORT_LIMIT_VALUE")
    import_limit_value: float = Field(30.0, env="IMPORT_LIMIT_VALUE")
    pv_max_power_value: float = Field(30.0, env="PV_MAX_POWER_VALUE")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
