"""Approved fill-progress policy; limits are permissions, never measured charge."""
from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import timedelta
import unittest

from app.models import MSC_SURPLUS_CEILING
from app.optimizer import MODE_MAX_SELF
from test_msc_baseline_overlay_contract import (
    ClockedRecordingHA, establish_observed_msc_baseline, later_msc_report_clock,
)


class SolarFillProgressTrajectoryTests(unittest.TestCase):
    def setUp(self):
        from test_phase1_solar_dynamic_charge_ceiling_characterization import SolarDynamicChargeFixture
        self.fixture = SolarDynamicChargeFixture("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)

    def _completed_physical(self):
        from test_phase1_solar_physical_relief_characterization import SolarPhysicalReliefCharacterizationTests
        physical = SolarPhysicalReliefCharacterizationTests("runTest")
        physical.setUp()
        self.addCleanup(physical.tearDown)
        opt = physical._optimizer(solar_surplus_fill_deadline_margin_minutes=0.0)
        ha = ClockedRecordingHA()
        asyncio.run(establish_observed_msc_baseline(
            physical, opt, ha, physical.WHEN - timedelta(seconds=1),
        ))
        for second in (0, 1, 2, 3):
            state, decision = physical._decision(opt, second, charge=1.21)
            result = self._apply_physical(physical, opt, ha, state, decision)
            self.assertTrue(result.automatic_application_completed, result.error)
        self.assertEqual(1.61, opt._solar_relief.completed_total_kw)
        return physical, opt, ha

    def _apply_physical(self, physical, opt, ha, state, decision):
        with later_msc_report_clock(ha, state.timestamp):
            for entity, value in (
                (opt.cfg.sigenergy_mode_select, opt.cfg.automated_option),
                (opt.cfg.ha_control_switch, "on"),
                (opt.cfg.ems_mode_select, MODE_MAX_SELF),
                (opt.cfg.grid_export_limit, 25.0),
            ):
                ha._record_state_value(entity, value)
            result = asyncio.run(opt._apply(state, decision))
            opt._finish_solar_reentry_application(state, decision, result)
        if result.automatic_application_completed:
            opt._last_state, opt._last_decision = state, decision
        return result

    def test_abundant_future_opportunity_keeps_positive_fill_progress_cap(self):
        opt = self.fixture._optimizer()
        decision = self.fixture._decide(opt)
        self.assertEqual(0.0, decision.trace_values["solar_charge_ceiling_required_now_kwh"])
        self.assertEqual(1.2, decision.ess_charge_limit)
        self.assertEqual(1.2, decision.trace_values["solar_charge_ceiling_fill_progress_floor_kw"])
        self.assertEqual(4.0, decision.trace_values["solar_charge_ceiling_fill_progress_hours"])
        self.assertEqual("fill_progress_floor", decision.trace_values["solar_charge_ceiling_trajectory_source"])
        self.assertEqual("fill_progress_floor_for_protected_fill", decision.trace_values["solar_charge_ceiling_reason"])
        self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
        self.assertEqual(MSC_SURPLUS_CEILING, decision.export_intent)
        self.assertEqual(25.0, decision.export_limit)
        self.assertEqual("none", decision.trace_values["battery_export_owner"])

    def test_urgent_current_interval_requirement_wins_over_progress_floor(self):
        decision = self.fixture._decide(
            self.fixture._optimizer(), forecast_pv_kw=[6.0] + [1.8] * 7,
        )
        self.assertEqual(4.0, decision.ess_charge_limit)
        self.assertEqual(1.2, decision.trace_values["solar_charge_ceiling_fill_progress_floor_kw"])
        self.assertEqual("urgent_current_interval", decision.trace_values["solar_charge_ceiling_trajectory_source"])
        self.assertEqual("present_charging_required_for_fill_trajectory", decision.trace_values["solar_charge_ceiling_reason"])

    def test_existing_normal_request_still_bounds_the_combined_trajectory(self):
        decision = self.fixture._decide(
            self.fixture._optimizer(), forecast_pv_kw=[6.0, 5.6] + [1.0] * 6,
        )
        self.assertTrue(decision.trace_gates["solar_charge_ceiling_owned"])
        self.assertEqual(5.0, decision.ess_charge_limit)
        self.assertLessEqual(decision.trace_values["solar_charge_ceiling_fill_progress_floor_kw"], 5.0)

    def test_partial_bin_rounding_near_full_and_exact_full(self):
        when = self.fixture.WHEN + timedelta(minutes=15)
        for soc, expected in ((60.0, 1.28), (99.99, 0.01), (100.0, 0.0)):
            with self.subTest(soc=soc):
                decision = self.fixture._decide(
                    self.fixture._optimizer(), when=when,
                    solcast_detailed=self.fixture._detailed_forecast([6.0] + [3.0] * 7),
                    next_sunset_ts=(self.fixture.WHEN + timedelta(hours=4)).timestamp(),
                    battery_soc=soc, available_discharge_energy_kwh=soc / 10.0,
                )
                self.assertEqual(expected, decision.ess_charge_limit)
                self.assertEqual(3.75, decision.trace_values["solar_charge_ceiling_fill_progress_hours"])
                self.assertEqual(0.25, decision.trace_values["solar_charge_ceiling_current_window_hours"])
                if soc == 100.0:
                    self.assertEqual("exact_full", decision.trace_values["solar_charge_ceiling_trajectory_source"])

    def test_observed_soc_progress_reduces_floor_without_crediting_requested_charge(self):
        opt = self.fixture._optimizer()
        for soc, expected in ((60.0, 1.2), (60.0, 1.2), (80.0, 0.6), (99.99, 0.01)):
            with self.subTest(soc=soc):
                decision = self.fixture._decide(
                    opt, battery_soc=soc, available_discharge_energy_kwh=soc / 10.0,
                )
                self.assertEqual(expected, decision.ess_charge_limit)
                opt._last_decision = decision

    def test_forecast_downgrade_retains_floor_until_urgent_requirement_overtakes_it(self):
        opt = self.fixture._optimizer()
        for future, expected, source in (
            (3.0, 1.2, "fill_progress_floor"),
            (2.4, 1.2, "fill_progress_floor"),
            (1.8, 4.0, "urgent_current_interval"),
        ):
            with self.subTest(future=future):
                decision = self.fixture._decide(opt, forecast_pv_kw=[6.0] + [future] * 7)
                self.assertEqual(expected, decision.ess_charge_limit)
                self.assertEqual(source, decision.trace_values["solar_charge_ceiling_trajectory_source"])

    def test_existing_deadline_margin_and_trust_loss_keep_their_authority(self):
        decision = self.fixture._decide(self.fixture._optimizer(solar_surplus_fill_deadline_margin_minutes=60.0))
        self.assertEqual(1.6, decision.ess_charge_limit)
        self.assertEqual(3.0, decision.trace_values["solar_charge_ceiling_fill_progress_hours"])
        for changes in (
            {"load_power_trusted": False},
            {"solcast_detailed_source_trusted": False},
            {"solcast_provider_next_update": None},
            {"next_sunset_ts": self.fixture.WHEN.timestamp()},
        ):
            with self.subTest(changes=tuple(changes)):
                decision = self.fixture._decide(self.fixture._optimizer(), **changes)
                self.assertEqual(5.0, decision.ess_charge_limit)
                self.assertFalse(decision.trace_gates["solar_charge_ceiling_owned"])
                self.assertIsNone(decision.trace_values["solar_charge_ceiling_fill_progress_floor_kw"])

    def test_soc_time_trajectory_preserves_earned_total_across_pure_baseline_movement(self):
        from test_phase1_solar_physical_relief_characterization import SolarPhysicalReliefCharacterizationTests
        physical = SolarPhysicalReliefCharacterizationTests("runTest")
        physical.setUp()
        try:
            opt = physical._optimizer(solar_surplus_fill_deadline_margin_minutes=0.0)
            ha = ClockedRecordingHA()
            asyncio.run(establish_observed_msc_baseline(
                physical, opt, ha, physical.WHEN - timedelta(seconds=1),
            ))
            previous_cap, observed_energy_kwh = 0.0, 0.0
            rows, drops = [], []
            for second in range(0, 601, 6):
                if second:
                    # Synthetic measured absorption, independently supplied as
                    # actual SoC/flows. Service acceptance alone earns no energy.
                    observed_energy_kwh += previous_cap * 6.0 / 3600.0
                state, decision = physical._decision(
                    opt, second, charge=previous_cap,
                    battery_soc=60.0 + observed_energy_kwh / 10.0 * 100.0,
                    available_discharge_energy_kwh=6.0 + observed_energy_kwh,
                )
                row = (second, decision.trace_values["solar_charge_ceiling_baseline_kw"],
                       decision.trace_values["solar_physical_relief_kw"], decision.ess_charge_limit)
                rows.append(row)
                if second and decision.ess_charge_limit < previous_cap - 1e-9:
                    drops.append((second, previous_cap, decision.ess_charge_limit))
                with later_msc_report_clock(ha, state.timestamp):
                    for entity, value in (
                        (opt.cfg.sigenergy_mode_select, opt.cfg.automated_option),
                        (opt.cfg.ha_control_switch, "on"),
                        (opt.cfg.ems_mode_select, MODE_MAX_SELF),
                        (opt.cfg.grid_export_limit, 25.0),
                    ):
                        ha._record_state_value(entity, value)
                    result = asyncio.run(opt._apply(state, decision))
                    opt._finish_solar_reentry_application(state, decision, result)
                self.assertTrue(result.automatic_application_completed, result.error)
                opt._last_decision = decision
                previous_cap = decision.ess_charge_limit
            self.assertEqual([], drops, {
                "cap_drops": drops,
                "first_rows": rows[:12],
                "last_row": rows[-1],
                "observed_energy_kwh": observed_energy_kwh,
            })
        finally:
            physical.tearDown()
    def test_real_application_baseline_rebase_retains_total_without_weaker_balance_gate(self):
        from test_phase1_solar_physical_relief_characterization import SolarPhysicalReliefCharacterizationTests
        physical = SolarPhysicalReliefCharacterizationTests("runTest")
        physical.setUp()
        try:
            opt = physical._optimizer(solar_surplus_fill_deadline_margin_minutes=0.0)
            ha = ClockedRecordingHA()
            asyncio.run(establish_observed_msc_baseline(
                physical, opt, ha, physical.WHEN - timedelta(seconds=1),
            ))
            for second, measured_charge, expected, relief in (
                (0, 1.2, 1.2, 0.0), (1, 1.2, 1.21, 0.0),
                (2, 1.21, 1.21, 0.0), (3, 1.21, 1.61, 0.4),
                (120, 1.61, 1.61, 0.39),
            ):
                state, decision = physical._decision(opt, second, charge=measured_charge)
                self.assertAlmostEqual(expected, decision.ess_charge_limit)
                self.assertAlmostEqual(relief, decision.trace_values["solar_physical_relief_kw"])
                with later_msc_report_clock(ha, state.timestamp):
                    # Independently refresh live authority/export reports; a
                    # two-minute snapshot must not reuse stale startup authority.
                    for entity, value in (
                        (opt.cfg.sigenergy_mode_select, opt.cfg.automated_option),
                        (opt.cfg.ha_control_switch, "on"),
                        (opt.cfg.ems_mode_select, MODE_MAX_SELF),
                        (opt.cfg.grid_export_limit, 25.0),
                    ):
                        ha._record_state_value(entity, value)
                    result = asyncio.run(opt._apply(state, decision))
                    opt._finish_solar_reentry_application(state, decision, result)
                self.assertTrue(result.automatic_application_completed, result.error)
                opt._last_decision = decision
            bad = physical._flow_state(121, export=15.051, charge=0.002)
            bad.pv_kw, bad.load_kw = 16.026, 1.049
            bad.hvac_solar_inputs = replace(
                bad.hvac_solar_inputs,
                pv_power=replace(bad.hvac_solar_inputs.pv_power, value=16.026),
                load_power=replace(bad.hvac_solar_inputs.load_power, value=1.049),
            )
            with physical.optimizer_time(bad.timestamp):
                rejected = opt._decide(bad)
            self.assertEqual("physical_flow_untrusted", rejected.trace_values["solar_physical_relief_reason"])
            self.assertEqual(0.0, rejected.trace_values["solar_physical_relief_kw"])
            self.assertEqual(1.22, rejected.ess_charge_limit)
        finally:
            physical.tearDown()

    def test_completed_total_survives_baseline_rebase_without_epoch_or_cohort_donation(self):
        physical, opt, ha = self._completed_physical()
        command_ts = opt._solar_relief.command_ts
        for second, soc, baseline in ((4, 60.3, 1.2), (5, 59.6, 1.22)):
            state, decision = physical._decision(opt, second, charge=1.61, battery_soc=soc)
            self.assertEqual(baseline, decision.trace_values["solar_charge_ceiling_baseline_kw"])
            self.assertEqual(1.61, decision.ess_charge_limit)
            self.assertEqual("fill_progress_baseline_rebased", decision.trace_values["solar_physical_relief_reason"])
            self.assertEqual(0, opt._solar_relief.confirmations)
            self.assertEqual(command_ts, opt._solar_relief.command_ts)
            self.assertEqual(state.hvac_solar_inputs.pv_power.observed_at_ts, opt._solar_relief.feedback_ts[0])
            self.assertTrue(self._apply_physical(physical, opt, ha, state, decision).automatic_application_completed)
            self.assertEqual(command_ts, opt._solar_relief.command_ts)
            self.assertEqual(1.61, opt._solar_relief.completed_total_kw)

    def test_uncompleted_relief_proposal_is_not_a_reusable_total(self):
        physical, opt, _ = self._completed_physical()
        physical._decision(opt, 4, charge=1.61)
        _, proposed = physical._decision(opt, 5, charge=1.61)
        self.assertEqual(2.01, proposed.ess_charge_limit)
        self.assertEqual(1.61, opt._solar_relief.completed_total_kw)
        _, rebased = physical._decision(opt, 6, charge=1.61, battery_soc=60.3)
        self.assertEqual(1.61, rebased.ess_charge_limit)
        self.assertEqual(0, opt._solar_relief.confirmations)

    def test_export_reduction_retires_old_total_before_lower_command_completes(self):
        for export in (14.49, 13.99):
            with self.subTest(export=export):
                physical, opt, _ = self._completed_physical()
                _, lower = physical._decision(opt, 4, export=export, charge=1.61)
                self.assertLess(lower.ess_charge_limit, 1.61)
                self.assertIsNone(opt._solar_relief.completed_total_kw)
                self.assertTrue(opt._solar_relief.retry)
                _, moved = physical._decision(opt, 5, charge=1.61, battery_soc=60.3)
                self.assertEqual(1.2, moved.ess_charge_limit)
                self.assertIsNone(opt._solar_relief.completed_total_kw)
                self.assertTrue(opt._solar_relief.retry)

    def test_provider_generation_or_normal_cap_change_rejects_receipt(self):
        from datetime import datetime, timezone
        for changed in ("provider", "normal"):
            with self.subTest(changed=changed):
                physical, opt, _ = self._completed_physical()
                updates = ({"solcast_provider_polled": datetime.fromtimestamp(
                    physical.WHEN.timestamp() + 4, timezone.utc,
                ).isoformat()} if changed == "provider" else {
                    "ess_max_charge_kw": 4.0, "ess_charge_limit_entity_max_kw": 4.0,
                })
                _, decision = physical._decision(opt, 4, charge=1.61, **updates)
                self.assertEqual(1.21, decision.ess_charge_limit)
                self.assertEqual(0.0, opt._solar_relief.relief_kw)
                self.assertIsNone(opt._solar_relief.completed_total_kw)

    def test_late_helper_exception_or_cancellation_retires_same_target_receipt(self):
        for cancelled in (False, True):
            with self.subTest(cancelled=cancelled):
                physical, opt, ha = self._completed_physical()
                state, same = physical._decision(opt, 4, charge=1.61)
                self.assertEqual(1.61, same.ess_charge_limit)
                async def fail_helper(*args):
                    if cancelled:
                        raise asyncio.CancelledError()
                    raise RuntimeError("synthetic late helper failure")
                ha.set_input_number = fail_helper
                with self.assertRaises(asyncio.CancelledError if cancelled else RuntimeError):
                    self._apply_physical(physical, opt, ha, state, same)
                self.assertIsNone(opt._solar_relief.completed_total_kw)

    def test_final_joint_read_rejects_wrong_stale_or_regressed_msc_and_old_receipt(self):
        from datetime import datetime, timezone
        for fault in ("wrong", "stale", "pre_request", "regressed_post_request"):
            with self.subTest(fault=fault):
                physical, opt, ha = self._completed_physical()
                state, same = physical._decision(opt, 4, charge=1.61)
                original_helper, original_bulk = ha.set_input_number, ha.bulk_states
                original_wait = opt._wait_for_exact_entity_state
                final_read = False
                async def finish_helper(*args):
                    nonlocal final_read
                    accepted = await original_helper(*args)
                    final_read = True
                    return accepted
                async def corrupted_final_read(entities):
                    nonlocal final_read
                    rows = await original_bulk(entities)
                    if final_read and opt.cfg.ems_mode_select in entities:
                        final_read = False
                        row = dict(rows[opt.cfg.ems_mode_select])
                        if fault == "wrong":
                            row["state"] = "Command Discharging (PV First)"
                        else:
                            delta = {"stale": -1000, "pre_request": 4, "regressed_post_request": 4.0005}[fault]
                            stamp = datetime.fromtimestamp(physical.WHEN.timestamp() + delta, timezone.utc).isoformat()
                            row["last_updated"] = row["last_reported"] = stamp
                        rows[opt.cfg.ems_mode_select] = row
                    return rows
                async def bounded_wait(*args, **kwargs):
                    kwargs["timeout_s"] = 0.01
                    return await original_wait(*args, **kwargs)
                ha.set_input_number, ha.bulk_states = finish_helper, corrupted_final_read
                opt._wait_for_exact_entity_state = bounded_wait
                result = self._apply_physical(physical, opt, ha, state, same)
                self.assertFalse(result.automatic_application_completed)
                self.assertTrue(result.fallback_attempted)
                self.assertIsNone(opt._solar_relief.completed_total_kw)

    def test_replaced_state_during_final_joint_read_cannot_be_promoted(self):
        physical, opt, ha = self._completed_physical()
        state, same = physical._decision(opt, 4, charge=1.61)
        original_helper, original_bulk = ha.set_input_number, ha.bulk_states
        final_read = False
        previous_state = opt._solar_relief
        async def finish_helper(*args):
            nonlocal final_read
            accepted = await original_helper(*args)
            final_read = True
            return accepted
        async def replace_during_read(entities):
            nonlocal final_read
            rows = await original_bulk(entities)
            if final_read:
                final_read = False
                opt._clear_solar_physical_relief()
            return rows
        ha.set_input_number, ha.bulk_states = finish_helper, replace_during_read
        result = self._apply_physical(physical, opt, ha, state, same)
        self.assertTrue(result.automatic_application_completed, result.error)
        self.assertIsNot(previous_state, opt._solar_relief)
        self.assertIsNone(opt._solar_relief.completed_total_kw)

    def test_successful_command_or_fabricated_completion_cannot_mint_receipt(self):
        from app.optimizer import _ActuatorApplicationResult
        from test_phase1_solar_physical_relief_characterization import SolarPhysicalReliefCharacterizationTests
        physical = SolarPhysicalReliefCharacterizationTests("runTest")
        physical.setUp()
        self.addCleanup(physical.tearDown)
        opt = physical._optimizer(solar_surplus_fill_deadline_margin_minutes=0.0)
        state, decision = physical._decision(opt, 0)
        physical._command(opt, decision.ess_charge_limit, 0)
        with physical.optimizer_time(state.timestamp):
            opt._finish_solar_reentry_application(
                state, decision, _ActuatorApplicationResult(
                    succeeded=True, automatic_application_completed=True,
                ),
            )
        self.assertIsNotNone(opt._solar_relief.command_ts)
        self.assertIsNone(opt._solar_relief.completed_total_kw)
        _, changed = physical._decision(opt, 1)
        self.assertEqual(1.21, changed.ess_charge_limit)
        self.assertEqual(0.0, opt._solar_relief.relief_kw)

    def test_provider_invalidation_during_final_read_restores_normal_without_receipt(self):
        physical, opt, ha = self._completed_physical()
        state, same = physical._decision(opt, 4, charge=1.61)
        original_helper, original_bulk = ha.set_input_number, ha.bulk_states
        final_read = False
        old_epoch = opt._solar_provider_epoch
        async def finish_helper(*args):
            nonlocal final_read
            accepted = await original_helper(*args)
            final_read = True
            return accepted
        async def invalidate_during_read(entities):
            nonlocal final_read
            rows = await original_bulk(entities)
            if final_read:
                final_read = False
                opt.on_ws_disconnect()
            return rows
        ha.set_input_number, ha.bulk_states = finish_helper, invalidate_during_read
        ha.calls.clear()
        result = self._apply_physical(physical, opt, ha, state, same)
        self.assertTrue(result.automatic_application_completed, result.error)
        self.assertGreater(opt._solar_provider_epoch, old_epoch)
        writes = [value for action, entity, value in ha.calls
                  if action == "set_number" and entity == opt.cfg.ess_max_charging_limit]
        self.assertEqual([1.61, 5.0], writes)
        self.assertFalse(same.trace_gates["solar_charge_ceiling_owned"])
        self.assertIsNone(opt._solar_relief.completed_total_kw)

    def test_baseline_above_completed_total_requires_changed_command_epoch(self):
        physical, opt, ha = self._completed_physical()
        old_command_ts = opt._solar_relief.command_ts
        state, higher = physical._decision(opt, 4, charge=1.61, battery_soc=45.0)
        self.assertEqual(1.66, higher.ess_charge_limit)
        self.assertEqual(0.0, opt._solar_relief.relief_kw)
        self.assertEqual(0, opt._solar_relief.confirmations)
        self.assertIsNone(opt._solar_relief.completed_total_kw)
        self.assertEqual(old_command_ts, opt._solar_relief.command_ts)
        self.assertTrue(self._apply_physical(physical, opt, ha, state, higher).automatic_application_completed)
        self.assertGreater(opt._solar_relief.command_ts, old_command_ts)
        self.assertEqual(1.66, opt._solar_relief.completed_total_kw)
        _, held = physical._decision(
            opt, 5, charge=1.66, battery_soc=45.0, feedback_seconds=4,
        )
        self.assertEqual(1.66, held.ess_charge_limit)
        self.assertEqual(0, opt._solar_relief.confirmations)
        self.assertEqual("awaiting_post_command_feedback", held.trace_values["solar_physical_relief_reason"])
