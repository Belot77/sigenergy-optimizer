from __future__ import annotations

from datetime import datetime

from .models import Decision, SolarState


def build_decision(self, s: SolarState, mode_max_self: str) -> Decision:
    """Translate the full YAML variable block into a Decision object."""
    MODE_MAX_SELF = mode_max_self
    cfg = self.cfg
    d = Decision()
    now = datetime.now()
    now_ts = now.timestamp()

    # ---- Time windows -------------------------------------------
    day_start_ts, day_end_ts = self._day_window(s)
    is_evening_or_night = now_ts < day_start_ts or now_ts > day_end_ts
    d.is_evening_or_night = is_evening_or_night

    sunset_ts = s.next_sunset_ts or (now_ts + 86400)
    sunrise_ts = s.next_sunrise_ts or (now_ts + 86400)
    if s.sun_above_horizon:
        actual_sunrise_ts = sunrise_ts - 86400
    else:
        actual_sunrise_ts = sunrise_ts

    hours_to_sunrise = s.hours_to_sunrise
    hours_to_sunset = s.hours_to_sunset
    close_to_sunset = hours_to_sunset <= cfg.sunset_export_grace_hours
    d.hours_to_sunrise = hours_to_sunrise

    # ---- Re-derive price flags (in case s came from a test, not _read_state) ----
    s.price_is_negative = s.price_is_actual and s.current_price < 0
    s.feedin_is_negative = s.feedin_price not in (-999.0,) and s.feedin_price < 0

    # ---- Battery capacity helpers --------------------------------
    cap = s.battery_capacity_kwh
    bat_fill_need_kwh = max(0.0, cap - s.available_discharge_energy_kwh)

    # ---- Sunrise SoC target (dynamic calculation) ----------------
    soc_required = self._battery_soc_required_to_sunrise(s)
    d.battery_soc_required_to_sunrise = soc_required
    sunrise_soc_target = max(soc_required, cfg.sunrise_reserve_soc)
    d.sunrise_soc_target = sunrise_soc_target
    sunrise_fill_need_kwh = max(0.0, cap * ((sunrise_soc_target - s.battery_soc) / 100))
    d.min_soc_to_sunrise = soc_required

    # ---- Price forecasts -----------------------------------------
    negative_price_before_cutoff = self._negative_price_before_cutoff(s, now_ts)

    # ---- Productive solar window ---------------------------------
    productive_solar_end_ts = self._productive_solar_end_ts(s, sunset_ts, now_ts)

    # ---- Morning dump -------------------------------------------
    morning_dump_start_ts, morning_dump_end_ts = self._morning_dump_window(s, actual_sunrise_ts)
    morning_dump_active = self._morning_dump_active(
        s, morning_dump_start_ts, morning_dump_end_ts,
        productive_solar_end_ts, bat_fill_need_kwh, now_ts
    )
    within_morning_grace = (
        cfg.morning_dump_enabled
        and morning_dump_end_ts is not None
        and now_ts >= morning_dump_end_ts
        and now_ts < morning_dump_end_ts + 7200
    )

    d.morning_dump_active = morning_dump_active

    # ---- Morning slow charge ------------------------------------
    morning_slow_charge_end_ts = (
        (sunset_ts - cfg.morning_slow_charge_sunset_cutoff * 3600)
        if sunset_ts else now_ts
    )
    morning_slow_charge_active = self._morning_slow_charge_active(
        s, now, now_ts, morning_slow_charge_end_ts
    )
    d.morning_slow_charge_active = morning_slow_charge_active

    # ---- Standby holdoff ----------------------------------------
    battery_can_reach_from_pv = (
        s.forecast_remaining_kwh >= sunrise_fill_need_kwh * cfg.forecast_safety_charging
    )
    standby_holdoff_active = (
        cfg.standby_holdoff_enabled
        and s.forecast_today_kwh >= cfg.pv_forecast_holdoff_kwh
        and negative_price_before_cutoff
        and now < self._today_at(cfg.standby_holdoff_end_time)
        and s.current_price > cfg.import_threshold_low
        and battery_can_reach_from_pv
    )
    d.standby_holdoff_active = standby_holdoff_active

    # Store holdoff floor at entry to prevent drift from forecast updates mid-holdoff
    prev_holdoff = self._last_decision and self._last_decision.standby_holdoff_active
    if standby_holdoff_active and not prev_holdoff:
        # Holdoff just became active — snapshot the SoC floor
        soc_required = self._battery_soc_required_to_sunrise(s)
        holdoff_sunrise_target = max(soc_required, cfg.sunrise_reserve_soc)
        self._holdoff_entry_floor = holdoff_sunrise_target + cfg.soc_hysteresis
    elif not standby_holdoff_active:
        # Holdoff expired — clear the stored floor
        self._holdoff_entry_floor = None

    # ---- Evening boost ------------------------------------------
    evening_export_boost_active = self._evening_export_boost_active(
        s, now_ts, productive_solar_end_ts, sunrise_soc_target, bat_fill_need_kwh
    )
    d.evening_export_boost_active = evening_export_boost_active

    # ---- Effective min SoC for export ---------------------------
    if is_evening_or_night:
        relaxed = sunrise_soc_target - cfg.sunrise_export_relax_percent
        effective_min_soc = max(relaxed, cfg.sunrise_reserve_soc)
    else:
        effective_min_soc = cfg.min_soc_floor

    export_sunrise_guard_active = is_evening_or_night
    export_min_soc = effective_min_soc
    if export_sunrise_guard_active:
        export_min_soc = max(effective_min_soc, soc_required)

    # ---- Export flags -------------------------------------------
    export_spike_active = (
        s.price_spike_active
        and s.feedin_price >= cfg.export_spike_threshold
    )
    d.export_spike_active = export_spike_active

    positive_fit_override = (
        cfg.allow_low_medium_export_positive_fit
        and s.feedin_price >= 0.01
    )

    solar_potential_kw = max(s.pv_kw, s.solar_power_now_kw)
    pv_surplus = max(solar_potential_kw - s.load_kw, 0.0)
    pv_surplus_actual = max(s.pv_kw - s.load_kw, 0.0)

    export_solar_override = (
        s.feedin_price > 0
        and s.feedin_price >= cfg.export_threshold_medium
        and s.battery_soc >= cfg.max_battery_soc
        and not is_evening_or_night
        and pv_surplus > cfg.min_grid_transfer_kw
        and (
            s.forecast_remaining_kwh >= bat_fill_need_kwh * 1.25
            or bat_fill_need_kwh <= 0
        )
    )

    # ---- PV safeguard -------------------------------------------
    full_export_override_check = (
        s.battery_soc >= cfg.max_battery_soc
        and not is_evening_or_night
        and pv_surplus > cfg.min_grid_transfer_kw
    )
    est_load_kwh = s.load_kw * hours_to_sunset
    net_forecast = s.forecast_remaining_kwh - est_load_kwh
    tomorrow_kwh = s.forecast_tomorrow_kwh
    low_today = s.forecast_remaining_kwh > 0 and net_forecast <= bat_fill_need_kwh * cfg.forecast_safety_charging
    low_tomorrow = is_evening_or_night and tomorrow_kwh < cap * cfg.forecast_safety_charging
    pv_safeguard_active = (
        not full_export_override_check
        and not positive_fit_override
        and (low_today or low_tomorrow)
    )
    d.pv_safeguard_active = pv_safeguard_active

    # ---- Solar surplus bypass -----------------------------------
    solar_surplus_bypass = self._solar_surplus_bypass(
        s, morning_slow_charge_active, cap, pv_surplus_actual,
        prev_desired_mode=self._last_decision.ems_mode if self._last_decision else "",
    )
    d.solar_surplus_bypass = solar_surplus_bypass

    # ---- Battery full safeguard ---------------------------------
    battery_full_safeguard_block = self._battery_full_safeguard_block(
        s, now_ts, sunset_ts, bat_fill_need_kwh, is_evening_or_night
    )
    d.battery_full_safeguard = battery_full_safeguard_block

    # ---- Export blocked for forecast ----------------------------
    export_blocked_for_forecast = self._export_blocked_for_forecast(
        s, pv_surplus, is_evening_or_night, bat_fill_need_kwh,
        hours_to_sunset, close_to_sunset
    )
    export_forecast_guard = self._export_forecast_guard(
        s, sunrise_fill_need_kwh, is_evening_or_night,
        evening_export_boost_active, close_to_sunset
    )
    export_blocked_effective = export_blocked_for_forecast

    # ---- Export tier limit (kW cap based on price) --------------
    export_tier_limit = self._export_tier_limit(
        s, export_spike_active, export_solar_override,
        pv_safeguard_active, evening_export_boost_active,
        solar_surplus_bypass
    )

    # ---- Morning dump limit -------------------------------------
    morning_dump_limit = min(cfg.export_limit_high, s.ess_max_discharge_kw)

    # ---- Desired export limit -----------------------------------
    desired_export_limit = self._desired_export_limit(
        s, export_spike_active, export_solar_override,
        export_blocked_effective, export_forecast_guard,
        export_min_soc, positive_fit_override, solar_surplus_bypass,
        evening_export_boost_active, morning_dump_active, morning_dump_limit,
        battery_full_safeguard_block,
        export_tier_limit, hours_to_sunrise, cap,
        # Use forecast-based surplus (solar_potential_kw − load) so the morning
        # slow-charge export branch sees uncurtailed PV potential rather than the
        # inverter-curtailed measured output, which causes a self-locking feedback
        # loop where low export limit → low pv_kw reading → low export limit.
        pv_surplus, is_evening_or_night, morning_slow_charge_active,
        within_morning_grace,
    )
    d.export_limit = desired_export_limit

    # ---- Import limit (grid_limit_base → desired_import_limit) --
    desired_import_limit = self._desired_import_limit(
        s, morning_dump_active, demand_window_active=s.demand_window_active,
        standby_holdoff_active=standby_holdoff_active,
        feedin_price_ok=(s.feedin_price >= cfg.export_threshold_low),
        pv_surplus=pv_surplus_actual,
    )
    d.import_limit = desired_import_limit

    # ---- Desired EMS mode ---------------------------------------
    desired_ems_mode = self._desired_ems_mode(
        s, morning_dump_active, standby_holdoff_active, export_solar_override,
        desired_export_limit, desired_import_limit, export_min_soc,
        sunrise_soc_target, within_morning_grace,
        export_blocked_for_forecast, is_evening_or_night,
    )
    d.ems_mode = desired_ems_mode

    # ---- Battery-only mode → cap PV max power -------------------
    battery_only_mode = (
        desired_ems_mode == MODE_MAX_SELF
        and desired_export_limit == 0
        and desired_import_limit == 0
        and (is_evening_or_night or standby_holdoff_active)
    )
    desired_pv_max = self._desired_pv_max_power(
        s, standby_holdoff_active, battery_only_mode,
        morning_dump_active, morning_slow_charge_active,
        desired_export_limit,
    )
    d.pv_max_power_limit = desired_pv_max

    # ---- ESS charge / discharge limits --------------------------
    d.ess_charge_limit = self._desired_ess_charge_limit(
        s, desired_import_limit, morning_slow_charge_active,
        desired_export_limit, pv_surplus_actual
    )
    d.ess_discharge_limit = self._desired_ess_discharge_limit(
        s, standby_holdoff_active, positive_fit_override,
        evening_export_boost_active
    )

    # ---- Needs HA control auto-enable? --------------------------
    d.needs_ha_control_switch = (
        cfg.auto_enable_ha_control
        and not s.ha_control_enabled
        and (
            s.feedin_is_negative
            or desired_export_limit > 0
            or desired_import_limit > 0
            or s.current_ems_mode != desired_ems_mode
        )
    )

    # ---- Battery ETA -------------------------------------------
    # Prefer measured grid flow for battery power estimation; setpoint-based math
    # can diverge from actual inverter behavior and misreport charge/discharge.
    if s.battery_power_sensor_kw is not None:
        battery_power_kw = float(s.battery_power_sensor_kw)
        battery_power_source = "direct_battery_sensor"
        effective_import_for_math = 0.0
    elif s.grid_import_power_kw is not None and s.grid_export_power_kw is not None:
        measured_import = max(float(s.grid_import_power_kw), 0.0)
        measured_export = max(float(s.grid_export_power_kw), 0.0)
        battery_power_kw = s.pv_kw + measured_import - measured_export - s.load_kw
        battery_power_source = "measured_grid_flow"
        effective_import_for_math = measured_import
    else:
        # Keep holdoff sentinel (0.01 kW) out of analytical flow/ETA math.
        effective_import_for_math = 0.0 if desired_import_limit <= 0.011 else desired_import_limit
        battery_power_kw = s.pv_kw + (effective_import_for_math - desired_export_limit) - s.load_kw
        battery_power_source = "setpoint_balance_fallback"
    d.battery_power_kw = battery_power_kw
    d.battery_eta_formatted = self._battery_eta(s, battery_power_kw)

    # ---- Reason strings -----------------------------------------
    d.export_reason = self._export_reason(
        s, export_spike_active, export_solar_override, morning_dump_active,
        export_blocked_effective, export_forecast_guard, export_min_soc,
        pv_safeguard_active, export_tier_limit, morning_slow_charge_active,
        solar_surplus_bypass, evening_export_boost_active,
        battery_full_safeguard_block, desired_export_limit, positive_fit_override,
    )
    d.import_reason = self._import_reason(
        s, morning_dump_active, standby_holdoff_active,
        sunrise_soc_target, desired_import_limit, pv_surplus_actual
    )
    eta_label = ""
    if d.battery_eta_formatted not in ("idle", "Full", "Empty"):
        if battery_power_kw > 0.1:
            eta_label = f"Bat→Full:{d.battery_eta_formatted}"
        elif battery_power_kw < -0.1:
            eta_label = f"Bat→Empty:{d.battery_eta_formatted}"
    parts = [d.export_reason, d.import_reason]
    if eta_label:
        parts.append(eta_label)
    if s.price_is_estimated:
        parts.append("*est")
    d.outcome_reason = "; ".join(p for p in parts if p and p != "n/a")

    export_branch = "normal_tier"
    if morning_dump_active:
        export_branch = "morning_dump"
    elif morning_slow_charge_active:
        export_branch = "morning_slow_charge"
    elif export_spike_active:
        export_branch = "export_spike"
    elif export_solar_override:
        export_branch = "solar_override"
    elif solar_surplus_bypass:
        export_branch = "solar_surplus_bypass"
    elif battery_full_safeguard_block:
        export_branch = "battery_full_safeguard_block"
    elif export_blocked_effective or export_forecast_guard:
        export_branch = "forecast_guard_block"
    elif desired_export_limit <= 0:
        export_branch = "blocked_or_zero"

    import_branch = "blocked"
    if morning_dump_active:
        import_branch = "morning_dump_block"
    elif s.demand_window_active:
        import_branch = "demand_window_block"
    elif standby_holdoff_active:
        import_branch = "standby_holdoff_block"
    elif desired_import_limit > 0 and s.price_is_negative:
        import_branch = "negative_price_import"
    elif desired_import_limit > 0:
        import_branch = "cheap_topup_import"

    d.trace_gates = {
        "is_evening_or_night": is_evening_or_night,
        "close_to_sunset": close_to_sunset,
        "within_morning_grace": within_morning_grace,
        "morning_dump_active": morning_dump_active,
        "morning_slow_charge_active": morning_slow_charge_active,
        "standby_holdoff_active": standby_holdoff_active,
        "negative_price_before_cutoff": negative_price_before_cutoff,
        "battery_can_reach_from_pv": battery_can_reach_from_pv,
        "evening_export_boost_active": evening_export_boost_active,
        "export_spike_active": export_spike_active,
        "positive_fit_override": positive_fit_override,
        "export_solar_override": export_solar_override,
        "pv_safeguard_active": pv_safeguard_active,
        "solar_surplus_bypass": solar_surplus_bypass,
        "battery_full_safeguard_block": battery_full_safeguard_block,
        "export_blocked_for_forecast": export_blocked_for_forecast,
        "export_forecast_guard": export_forecast_guard,
        "export_blocked_effective": export_blocked_effective,
        "battery_only_mode": battery_only_mode,
        "needs_ha_control_switch": d.needs_ha_control_switch,
        "demand_window_active": s.demand_window_active,
        "price_is_negative": s.price_is_negative,
        "feedin_is_negative": s.feedin_is_negative,
    }
    d.trace_values = {
        "battery_soc": s.battery_soc,
        "current_price": s.current_price,
        "feedin_price": s.feedin_price,
        "pv_kw": s.pv_kw,
        "load_kw": s.load_kw,
        "grid_import_power_kw": s.grid_import_power_kw,
        "grid_export_power_kw": s.grid_export_power_kw,
        "pv_surplus_actual": pv_surplus_actual,
        "pv_surplus_estimated": pv_surplus,
        "cap_kwh": cap,
        "bat_fill_need_kwh": bat_fill_need_kwh,
        "soc_required": soc_required,
        "sunrise_soc_target": sunrise_soc_target,
        "sunrise_fill_need_kwh": sunrise_fill_need_kwh,
        "hours_to_sunrise": hours_to_sunrise,
        "hours_to_sunset": hours_to_sunset,
        "export_min_soc": export_min_soc,
        "export_tier_limit": export_tier_limit,
        "morning_dump_limit": morning_dump_limit,
        "desired_export_limit": desired_export_limit,
        "desired_import_limit": desired_import_limit,
        "desired_ems_mode": desired_ems_mode,
        "desired_pv_max": desired_pv_max,
        "effective_import_for_math": effective_import_for_math,
        "battery_power_kw": battery_power_kw,
        "battery_power_source": battery_power_source,
        "battery_power_sensor_kw": s.battery_power_sensor_kw,
        "ess_charge_limit": d.ess_charge_limit,
        "ess_discharge_limit": d.ess_discharge_limit,
        "holdoff_entry_floor": self._holdoff_entry_floor,
        "current_export_limit": s.current_export_limit,
        "current_import_limit": s.current_import_limit,
        "current_pv_max_power_limit": s.current_pv_max_power_limit,
        "current_ems_mode": s.current_ems_mode,
        "sigenergy_mode": s.sigenergy_mode,
        "manual_mode_override": self._manual_mode_override,
        "export_branch": export_branch,
        "import_branch": import_branch,
        "cfg_morning_slow_charge_enabled": cfg.morning_slow_charge_enabled,
        "cfg_morning_slow_charge_rate_kw": cfg.morning_slow_charge_rate_kw,
        "cfg_morning_slow_export_start_margin_kw": cfg.morning_slow_export_start_margin_kw,
        "cfg_morning_slow_export_stop_margin_kw": cfg.morning_slow_export_stop_margin_kw,
        "cfg_morning_slow_export_ramp_up_step_kw": cfg.morning_slow_export_ramp_up_step_kw,
        "cfg_morning_slow_export_ramp_down_step_kw": cfg.morning_slow_export_ramp_down_step_kw,
        "cfg_morning_slow_export_probe_enabled": cfg.morning_slow_export_probe_enabled,
        "cfg_morning_slow_export_probe_step_kw": cfg.morning_slow_export_probe_step_kw,
        "cfg_morning_slow_export_probe_saturation_margin_kw": cfg.morning_slow_export_probe_saturation_margin_kw,
        "cfg_target_battery_charge": cfg.target_battery_charge,
        "cfg_max_price_threshold": cfg.max_price_threshold,
        "cfg_export_threshold_low": cfg.export_threshold_low,
        "cfg_export_threshold_medium": cfg.export_threshold_medium,
        "cfg_export_threshold_high": cfg.export_threshold_high,
        "cfg_export_limit_low": cfg.export_limit_low,
        "cfg_export_limit_medium": cfg.export_limit_medium,
        "cfg_export_limit_high": cfg.export_limit_high,
        "cfg_min_export_target_soc": cfg.min_export_target_soc,
        "cfg_min_soc_floor": cfg.min_soc_floor,
        "cfg_sunrise_export_relax_percent": cfg.sunrise_export_relax_percent,
        "cfg_pv_max_power_normal": cfg.pv_max_power_normal,
    }

    return d
