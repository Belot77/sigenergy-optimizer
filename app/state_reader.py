from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from .models import SolarState

logger = logging.getLogger(__name__)


async def read_state_snapshot(optimizer, mode_max_self: str) -> SolarState:
	cfg = optimizer.cfg
	s = SolarState()

	# ---- bulk fetch -----------------------------------------------
	entity_ids = [
		cfg.pv_power_sensor, cfg.consumed_power_sensor, cfg.battery_soc_sensor,
		cfg.rated_capacity_sensor, cfg.available_discharge_sensor,
		cfg.ess_rated_discharge_power_sensor, cfg.ess_rated_charge_power_sensor,
		cfg.sun_entity, cfg.price_sensor, cfg.feedin_sensor,
		cfg.demand_window_sensor, cfg.price_spike_sensor,
		cfg.price_forecast_sensor, cfg.feedin_forecast_sensor,
		cfg.forecast_remaining_sensor, cfg.forecast_today_sensor,
		cfg.forecast_tomorrow_sensor, cfg.solar_power_now_sensor,
		cfg.daily_export_energy, cfg.daily_import_energy, cfg.daily_load_energy,
		cfg.daily_pv_energy, cfg.daily_battery_charge_energy, cfg.daily_battery_discharge_energy,
		cfg.grid_export_limit, cfg.grid_import_limit, cfg.pv_max_power_limit,
		cfg.ems_mode_select, cfg.ha_control_switch,
		cfg.export_session_start, cfg.import_session_start,
		cfg.last_export_notification, cfg.last_import_notification,
		cfg.sigenergy_mode_select,
	]
	if cfg.ess_max_charging_limit:
		entity_ids.append(cfg.ess_max_charging_limit)
	if cfg.ess_max_discharging_limit:
		entity_ids.append(cfg.ess_max_discharging_limit)
	if cfg.battery_power_sensor:
		entity_ids.append(cfg.battery_power_sensor)
	if cfg.grid_import_power_sensor:
		entity_ids.append(cfg.grid_import_power_sensor)
	if cfg.grid_export_power_sensor:
		entity_ids.append(cfg.grid_export_power_sensor)
	bulk = await optimizer.ha.bulk_states(entity_ids)

	def _fv(eid: str, default: float = 0.0) -> float:
		obj = bulk.get(eid)
		if not obj:
			return default
		try:
			return float(obj["state"])
		except (TypeError, ValueError):
			return default

	def _sv(eid: str, default: str = "") -> str:
		obj = bulk.get(eid)
		if not obj:
			return default
		v = obj.get("state", "")
		return v if v not in {"unknown", "unavailable", "none", ""} else default

	def _bv(eid: str) -> bool:
		return _sv(eid, "off").lower() in ("on", "true", "1")

	def _attr(eid: str, attr: str, default=None):
		obj = bulk.get(eid)
		if not obj:
			return default
		return obj.get("attributes", {}).get(attr, default)

	# ---- PV / battery ---------------------------------------------
	pv_raw = _fv(cfg.pv_power_sensor)
	s.pv_kw = pv_raw / 1000 if pv_raw > 100 else pv_raw

	load_raw = _fv(cfg.consumed_power_sensor)
	s.load_kw = load_raw / 1000 if load_raw > 100 else load_raw
	if cfg.grid_import_power_sensor:
		grid_import_raw = _fv(cfg.grid_import_power_sensor)
		s.grid_import_power_kw = grid_import_raw / 1000 if grid_import_raw > 100 else grid_import_raw
	if cfg.grid_export_power_sensor:
		grid_export_raw = _fv(cfg.grid_export_power_sensor)
		s.grid_export_power_kw = grid_export_raw / 1000 if grid_export_raw > 100 else grid_export_raw
	if cfg.battery_power_sensor:
		battery_power_raw = _fv(cfg.battery_power_sensor, None)
		if isinstance(battery_power_raw, (int, float)):
			battery_power_kw = battery_power_raw / 1000 if abs(battery_power_raw) > 100 else battery_power_raw
			if cfg.battery_power_sensor_invert:
				battery_power_kw = -battery_power_kw
			s.battery_power_sensor_kw = battery_power_kw

	s.battery_soc = max(0.0, min(100.0, _fv(cfg.battery_soc_sensor)))

	cap_raw = _fv(cfg.rated_capacity_sensor, 10.0)
	cap_uom = (_attr(cfg.rated_capacity_sensor, "unit_of_measurement") or "kwh").lower()
	if cap_uom == "wh":
		s.battery_capacity_kwh = cap_raw / 1000
	elif cap_raw < 1.0 and cap_raw > 0:
		s.battery_capacity_kwh = cap_raw * 1000
	else:
		s.battery_capacity_kwh = cap_raw if cap_raw > 0 else 10.0

	avail_raw = _fv(cfg.available_discharge_sensor)
	avail_uom = (_attr(cfg.available_discharge_sensor, "unit_of_measurement") or "kwh").lower()
	if avail_uom == "wh":
		s.available_discharge_energy_kwh = avail_raw / 1000
	else:
		s.available_discharge_energy_kwh = avail_raw

	def _kw_from_sensor(raw: float) -> float:
		if raw <= 0:
			return 999.0
		return raw / 1000 if raw >= 1000 else raw

	s.ess_max_discharge_kw = _kw_from_sensor(_fv(cfg.ess_rated_discharge_power_sensor))
	s.ess_max_charge_kw = _kw_from_sensor(_fv(cfg.ess_rated_charge_power_sensor))
	if optimizer._valid_hw_cap_kw(s.ess_max_charge_kw):
		optimizer._last_hw_charge_cap_kw = float(s.ess_max_charge_kw)
	if optimizer._valid_hw_cap_kw(s.ess_max_discharge_kw):
		optimizer._last_hw_discharge_cap_kw = float(s.ess_max_discharge_kw)

	# ---- Grid limits / EMS mode -----------------------------------
	s.current_export_limit = _fv(cfg.grid_export_limit)
	s.current_import_limit = _fv(cfg.grid_import_limit)
	s.current_pv_max_power_limit = _fv(cfg.pv_max_power_limit)
	if cfg.ess_max_charging_limit:
		s.current_ess_charge_limit = _fv(cfg.ess_max_charging_limit)
		try:
			max_attr = _attr(cfg.ess_max_charging_limit, "max")
			if max_attr is not None:
				s.ess_charge_limit_entity_max_kw = float(max_attr)
		except (TypeError, ValueError):
			s.ess_charge_limit_entity_max_kw = None
	if cfg.ess_max_discharging_limit:
		s.current_ess_discharge_limit = _fv(cfg.ess_max_discharging_limit)
		try:
			max_attr = _attr(cfg.ess_max_discharging_limit, "max")
			if max_attr is not None:
				s.ess_discharge_limit_entity_max_kw = float(max_attr)
		except (TypeError, ValueError):
			s.ess_discharge_limit_entity_max_kw = None
	s.current_ems_mode = _sv(cfg.ems_mode_select, mode_max_self)
	s.ha_control_enabled = _bv(cfg.ha_control_switch)

	# ---- Prices ---------------------------------------------------
	price_obj = bulk.get(cfg.price_sensor, {})
	price_state = price_obj.get("state", "") if price_obj else ""
	price_is_estimate = str(_attr(cfg.price_sensor, "estimate") or "false").lower() == "true"
	price_available = price_state not in {"unknown", "unavailable", "none", ""}

	if price_available:
		try:
			raw_price = float(price_state)
			s.price_is_actual = not price_is_estimate
			s.price_is_estimated = price_is_estimate
			s.current_price = raw_price
			s.current_price_cents = raw_price * cfg.price_multiplier
		except (TypeError, ValueError):
			optimizer._warn_parse_issue(cfg.price_sensor, str(price_state), "Price")
			s.current_price = 1.0
			s.current_price_cents = 1.0 * cfg.price_multiplier
	else:
		s.current_price = 1.0
		s.current_price_cents = 1.0 * cfg.price_multiplier

	fit_state = _sv(cfg.feedin_sensor, "")
	fit_available = fit_state != ""
	if fit_available:
		try:
			s.feedin_price = float(fit_state)
			s.feedin_price_cents = s.feedin_price * cfg.price_multiplier
		except (TypeError, ValueError):
			optimizer._warn_parse_issue(cfg.feedin_sensor, str(fit_state), "FIT")
			s.feedin_price = -999.0
			s.feedin_price_cents = -999.0
			fit_available = False
	else:
		s.feedin_price = -999.0
		s.feedin_price_cents = -999.0

	s.price_is_negative = s.price_is_actual and s.current_price < 0
	s.feedin_is_negative = fit_available and s.feedin_price < 0
	s.price_spike_active = _bv(cfg.price_spike_sensor)
	s.demand_window_active = _bv(cfg.demand_window_sensor)

	# ---- Forecasts ------------------------------------------------
	s.forecast_remaining_kwh = _fv(cfg.forecast_remaining_sensor)
	s.forecast_today_kwh = _fv(cfg.forecast_today_sensor)
	s.forecast_tomorrow_kwh = _fv(cfg.forecast_tomorrow_sensor)

	solar_raw = _fv(cfg.solar_power_now_sensor)
	s.solar_power_now_kw = solar_raw / 1000 if solar_raw > 100 else solar_raw

	s.solcast_detailed = _attr(cfg.forecast_today_sensor, "detailedForecast") or []
	s.price_forecast_entries = _attr(cfg.price_forecast_sensor, cfg.price_forecast_attribute) or []
	s.feedin_forecast_entries = _attr(cfg.feedin_forecast_sensor, cfg.feedin_forecast_attribute) or []

	# ---- Sun ------------------------------------------------------
	s.sun_elevation = float(_attr(cfg.sun_entity, "elevation") or 0)
	s.sun_above_horizon = _sv(cfg.sun_entity, "below_horizon") == "above_horizon"

	def _ts(attr: str) -> Optional[float]:
		v = _attr(cfg.sun_entity, attr)
		if not v:
			return None
		try:
			return datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp()
		except Exception:
			return None

	s.next_sunrise_ts = _ts("next_rising")
	s.next_sunset_ts = _ts("next_setting")

	now_ts = datetime.now().timestamp()
	if s.next_sunrise_ts:
		raw_h = (s.next_sunrise_ts - now_ts) / 3600
		s.hours_to_sunrise = max(0.0, raw_h)
	if s.next_sunset_ts:
		s.hours_to_sunset = max(0.0, (s.next_sunset_ts - now_ts) / 3600)

	# ---- Daily totals / session tracking --------------------------
	s.daily_export_kwh = _fv(cfg.daily_export_energy)
	s.daily_import_kwh = _fv(cfg.daily_import_energy)
	s.daily_load_kwh = _fv(cfg.daily_load_energy)
	s.daily_pv_kwh = _fv(cfg.daily_pv_energy)
	s.daily_battery_charge_kwh = _fv(cfg.daily_battery_charge_energy)
	s.daily_battery_discharge_kwh = _fv(cfg.daily_battery_discharge_energy)
	s.export_session_start_kwh = _fv(cfg.export_session_start)
	s.import_session_start_kwh = _fv(cfg.import_session_start)
	s.last_export_notification = _sv(cfg.last_export_notification, "stopped")
	s.last_import_notification = _sv(cfg.last_import_notification, "stopped")

	# ---- Mode select ----------------------------------------------
	last_mode = optimizer._last_state.sigenergy_mode if optimizer._last_state else ""
	mode_default = optimizer._manual_mode_override or last_mode or cfg.automated_option
	s.sigenergy_mode = _sv(cfg.sigenergy_mode_select, mode_default)
	if optimizer._manual_mode_override and s.sigenergy_mode in {cfg.automated_option, ""}:
		logger.warning(
			"Mode selector read as '%s' while manual override '%s' is active; preserving manual mode",
			s.sigenergy_mode,
			optimizer._manual_mode_override,
		)
		s.sigenergy_mode = optimizer._manual_mode_override

	return s
