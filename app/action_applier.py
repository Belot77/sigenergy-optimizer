from __future__ import annotations

import logging

from .models import Decision, SolarState

logger = logging.getLogger(__name__)


async def apply_decision(optimizer, s: SolarState, d: Decision, mode_max_self: str) -> None:
	cfg = optimizer.cfg
	ha = optimizer.ha

	async def _safe_fallback(reason: str) -> None:
		logger.error("Entering safe fallback: %s", reason)
		await ha.select_option(cfg.ems_mode_select, mode_max_self)
		await ha.set_number(cfg.grid_export_limit, 0.01)
		await ha.set_number(cfg.grid_import_limit, 0.01)
		if cfg.ess_max_discharging_limit:
			await ha.set_number(cfg.ess_max_discharging_limit, 0.01)

	effective_mode = optimizer._manual_mode_override or s.sigenergy_mode
	if optimizer._manual_mode_override and s.sigenergy_mode != optimizer._manual_mode_override:
		logger.warning(
			"Mode selector drift detected (%s -> %s); restoring manual selection",
			s.sigenergy_mode,
			optimizer._manual_mode_override,
		)
		ok_restore = await ha.select_option(cfg.sigenergy_mode_select, optimizer._manual_mode_override)
		if not ok_restore:
			logger.error(
				"Failed to restore mode selector %s to %s",
				cfg.sigenergy_mode_select,
				optimizer._manual_mode_override,
			)
		s.sigenergy_mode = optimizer._manual_mode_override
		effective_mode = optimizer._manual_mode_override

	# If in a manual mode, keep manual targets pinned when external writers drift
	# them (e.g. morning slow-charge branch in other automations).
	if effective_mode not in {cfg.automated_option, ""}:
		manual_targets = optimizer._manual_mode_targets(
			effective_mode,
			s,
			include_block_flow_ess_limits=(effective_mode == cfg.block_flow_option),
		)
		if manual_targets:
			threshold = max(0.05, float(cfg.min_change_threshold))
			drifted_keys: list[str] = []
			if s.current_ems_mode != str(manual_targets["ems_mode"]):
				drifted_keys.append("ems_mode")
			if abs(float(manual_targets["grid_export_limit"]) - s.current_export_limit) >= threshold:
				drifted_keys.append("grid_export_limit")
			if abs(float(manual_targets["grid_import_limit"]) - s.current_import_limit) >= threshold:
				drifted_keys.append("grid_import_limit")
			if abs(float(manual_targets["pv_max_power_limit"]) - s.current_pv_max_power_limit) >= threshold:
				drifted_keys.append("pv_max_power_limit")
			if "ess_charge_limit" in manual_targets and s.current_ess_charge_limit is not None:
				if abs(float(manual_targets["ess_charge_limit"]) - float(s.current_ess_charge_limit)) >= threshold:
					drifted_keys.append("ess_charge_limit")
			if "ess_discharge_limit" in manual_targets and s.current_ess_discharge_limit is not None:
				if abs(float(manual_targets["ess_discharge_limit"]) - float(s.current_ess_discharge_limit)) >= threshold:
					drifted_keys.append("ess_discharge_limit")

			if drifted_keys:
				logger.warning(
					"Manual mode drift detected (%s): %s; reapplying manual targets",
					effective_mode,
					", ".join(drifted_keys),
				)
				write_results = await optimizer._apply_manual_mode_targets(
					manual_targets,
					mode_label=effective_mode,
				)
				failed = [name for name, ok in write_results.items() if not ok]
				optimizer.record_audit_event(
					action="manual_enforce",
					source="optimizer_cycle",
					actor="system:optimizer",
					result="partial" if failed else "ok",
					old_value={
						"ems_mode": s.current_ems_mode,
						"grid_export_limit": s.current_export_limit,
						"grid_import_limit": s.current_import_limit,
						"pv_max_power_limit": s.current_pv_max_power_limit,
						"ess_charge_limit": s.current_ess_charge_limit,
						"ess_discharge_limit": s.current_ess_discharge_limit,
					},
					new_value=manual_targets,
					details={
						"mode": effective_mode,
						"drifted_keys": drifted_keys,
						"failed": failed,
					},
				)
				if failed:
					logger.error("Manual mode drift correction had failures: %s", ", ".join(failed))

		logger.debug("Manual mode active (%s); optimizer decisions paused", effective_mode)
		return
	effective_ha_control = s.ha_control_enabled or d.needs_ha_control_switch

	# Auto-enable HA control switch if needed
	if d.needs_ha_control_switch and not s.ha_control_enabled:
		logger.info("Auto-enabling HA control switch")
		await ha.turn_on(cfg.ha_control_switch)

	if not effective_ha_control:
		return

	ems_mode_to_apply = d.ems_mode

	# EMS mode
	if s.current_ems_mode != ems_mode_to_apply:
		logger.info("EMS mode: %s → %s", s.current_ems_mode, ems_mode_to_apply)
		ok_mode = await ha.select_option(cfg.ems_mode_select, ems_mode_to_apply)
		if not ok_mode:
			await _safe_fallback(f"failed setting EMS mode to {ems_mode_to_apply}")
			return

	# Export limit
	near_zero = 0.011
	export_val = d.export_limit if d.export_limit > 0 else 0.01
	export_turning_on = s.current_export_limit <= near_zero and export_val > near_zero
	export_turning_off = s.current_export_limit > near_zero and export_val <= near_zero
	if abs(export_val - s.current_export_limit) >= cfg.min_change_threshold or export_turning_on or export_turning_off:
		ok_export = await ha.set_number(cfg.grid_export_limit, export_val)
		if not ok_export:
			await _safe_fallback(f"failed setting export limit to {export_val:.2f}kW")
			return

	# Import limit
	import_val = 0.01 if d.import_limit == 0 else d.import_limit
	if d.standby_holdoff_active:
		import_val = 0.01
	import_turning_on = s.current_import_limit <= near_zero and import_val > near_zero
	import_turning_off = s.current_import_limit > near_zero and import_val <= near_zero
	if abs(import_val - s.current_import_limit) >= cfg.min_change_threshold or import_turning_on or import_turning_off:
		ok_import = await ha.set_number(cfg.grid_import_limit, import_val)
		if not ok_import:
			await _safe_fallback(f"failed setting import limit to {import_val:.2f}kW")
			return

	# ESS charge / discharge limits
	if cfg.ess_max_charging_limit:
		ok_chg = await ha.set_number(cfg.ess_max_charging_limit, d.ess_charge_limit)
		if not ok_chg:
			logger.error("Failed setting ESS charge limit to %.2fkW", d.ess_charge_limit)
	if cfg.ess_max_discharging_limit:
		discharge_limit = d.ess_discharge_limit
		ok_dis = await ha.set_number(cfg.ess_max_discharging_limit, discharge_limit)
		if not ok_dis:
			await _safe_fallback(f"failed setting ESS discharge limit to {discharge_limit:.2f}kW")
			return

	# PV max power limit
	if abs(d.pv_max_power_limit - s.current_pv_max_power_limit) > 0.05:
		await ha.set_number(cfg.pv_max_power_limit, d.pv_max_power_limit)

	# Reason text helper
	reason = d.outcome_reason[:250]
	if reason:
		await ha.set_input_text(cfg.reason_text_helper, reason)

	# Min SoC to sunrise helper — clamp to 100 for HA entity bounds; raw value may
	# exceed 100 when overnight load exceeds full battery capacity, which is valid
	# for internal logic but rejected by input_number entities with max: 100.
	await ha.set_input_number(cfg.min_soc_to_sunrise_helper, min(d.min_soc_to_sunrise, 100.0))

	logger.debug(
		"Applied: mode=%s exp=%.1f imp=%.1f pv=%.1f | %s",
		d.ems_mode, d.export_limit, d.import_limit, d.pv_max_power_limit,
		d.outcome_reason[:80],
	)
