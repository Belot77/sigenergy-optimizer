from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.models import BATTERY_EXPORT, HVACObservedValue, HVACSolarInputContext, MSC_SURPLUS_CEILING
from app.optimizer import DISCHARGE_MODES, MODE_MAX_SELF
from haos49_characterization_helpers import Haos49CharacterizationCase, RecordingHA
import test_phase1_solar_dynamic_charge_ceiling_characterization as charge_fixture


class SolarPhysicalReliefCharacterizationTests(Haos49CharacterizationCase):
    """Approved Solar feedback contract, independent of Morning Slow tuning."""

    WHEN = charge_fixture.SolarDynamicChargeFixture.WHEN
    PERIOD_HOURS = 0.5
    NORMAL_CHARGE_KW = 5.0
    SAFETY_FACTOR = 1.20
    _state = charge_fixture.SolarDynamicChargeFixture._state
    _detailed_forecast = charge_fixture.SolarDynamicChargeFixture._detailed_forecast

    def _optimizer(self, **overrides):
        values = {
            "grid_connection_export_limit_kw": 15.0,
            "ess_max_charging_limit": "number.test_charge",
            "solar_surplus_bypass_enabled": True,
            "solar_surplus_forecast_safety_factor": self.SAFETY_FACTOR,
            "ess_charge_limit_value": self.NORMAL_CHARGE_KW,
        }
        values.update(overrides)
        return self.optimizer(**values)

    def _flow_state(self, seconds=0, *, export=15.0, charge=0.0, feedback_seconds=None, **changes):
        at = self.WHEN + timedelta(seconds=seconds)
        reported = self.WHEN.timestamp() + (seconds if feedback_seconds is None else feedback_seconds)
        pv = export + 1.0 + charge

        def observation(value):
            return HVACObservedValue(value=value, available=True, fresh=True, observed_at_ts=reported)

        state = self._state(
            forecast_pv_kw=[6.0] + [3.0] * 7,
            pv_kw=pv,
            solar_power_now_kw=pv,
            load_kw=1.0,
            grid_export_power_kw=export,
            battery_power_sensor_kw=charge,
            current_export_limit=25.0,
            current_import_limit=0.0,
            current_ess_charge_limit=charge,
            derived_power_flow_coherent=True,
            hvac_solar_inputs=HVACSolarInputContext(
                pv_power=observation(pv),
                load_power=observation(1.0),
                battery_power=observation(charge),
                grid_import_power=observation(0.0),
                grid_export_power=observation(export),
                solar_power_now=observation(pv),
                sun_above_horizon=observation(True),
                control_mode=observation("Automated"),
                observed_ems_mode=observation(MODE_MAX_SELF),
                observed_export_limit=observation(25.0),
                live_snapshot=True,
            ),
            timestamp=at,
        )
        for key, value in changes.items():
            setattr(state, key, value)
        return state

    def _sample(self, opt, seconds, *, state=None, baseline=0.0, normal=5.0, owned=True,
                ems_mode=MODE_MAX_SELF, battery_export_owner="none", **flow):
        state = state or self._flow_state(seconds, **flow)
        return opt._solar_physical_export_relief(
            state,
            now_ts=(self.WHEN + timedelta(seconds=seconds)).timestamp(),
            baseline_kw=baseline,
            normal_kw=normal,
            owned=owned,
            ems_mode=ems_mode,
            battery_export_owner=battery_export_owner,
        )

    def _command(self, opt, kw, seconds):
        opt._record_solar_physical_relief_command(
            applied_kw=kw, command_ts=self.WHEN.timestamp() + seconds,
        )

    def _prime(self, opt, *, baseline=0.0, normal=5.0):
        self.assertEqual(baseline, self._sample(opt, 0, baseline=baseline, normal=normal)[0])
        self._command(opt, baseline, 0)

    def _ramp(self, opt, steps, *, start=0, baseline=0.0, normal=5.0):
        self._prime(opt, baseline=baseline, normal=normal)
        for index in range(steps):
            previous = min(normal, baseline + index * 0.4)
            expected = min(normal, baseline + (index + 1) * 0.4)
            first = start + index * 2 + 1
            self.assertAlmostEqual(previous, self._sample(
                opt, first, baseline=baseline, normal=normal, charge=previous,
            )[0])
            self.assertAlmostEqual(expected, self._sample(
                opt, first + 1, baseline=baseline, normal=normal, charge=previous,
            )[0])
            self._command(opt, expected, first + 1)
        return start + steps * 2

    def test_zero_physical_limit_disables_even_with_saturated_export(self):
        opt = self._optimizer(grid_connection_export_limit_kw=0.0)
        self._prime(opt)
        for second in range(1, 5):
            self.assertEqual(0.0, self._sample(opt, second)[0])

    def test_entry_threshold_is_inclusive_14_8_and_excludes_14_79(self):
        for export, expected in ((14.79, 0.0), (14.8, 0.4), (15.0, 0.4)):
            with self.subTest(export=export):
                opt = self._optimizer()
                self._prime(opt)
                self.assertEqual(0.0, self._sample(opt, 1, export=export)[0])
                self.assertAlmostEqual(expected, self._sample(opt, 2, export=export)[0])

    def test_each_0_4_increase_requires_two_new_post_command_observations(self):
        opt = self._optimizer()
        self._ramp(opt, 4)

    def test_no_probe_before_successful_baseline_command(self):
        opt = self._optimizer()
        for second in range(4):
            self.assertEqual(0.0, self._sample(opt, second)[0])

    def test_unchanged_feedback_cannot_stack_increases(self):
        opt = self._optimizer()
        self._prime(opt)
        for second in range(1, 10):
            self.assertEqual(0.0, self._sample(opt, second, feedback_seconds=1)[0])
        self.assertAlmostEqual(0.4, self._sample(opt, 10, feedback_seconds=10)[0])
        for second in range(11, 15):
            self.assertAlmostEqual(0.4, self._sample(opt, second, feedback_seconds=10)[0])

    def test_feedback_at_or_before_command_is_not_post_command_confirmation(self):
        opt = self._optimizer()
        self.assertEqual(0.0, self._sample(opt, 0)[0])
        self._command(opt, 0.0, 2)
        for reported in (1, 2, 2):
            ceiling, _, values = self._sample(opt, 2, feedback_seconds=reported)
            self.assertEqual(0.0, ceiling)
            self.assertEqual("awaiting_post_command_feedback", values["solar_physical_relief_reason"])
            self.assertEqual(0, values["solar_physical_relief_confirmations"])
            self.assertEqual(self.WHEN.timestamp() + 2, opt._solar_relief.command_ts)
        self.assertEqual(0.0, self._sample(opt, 3)[0])
        self.assertAlmostEqual(0.4, self._sample(opt, 4)[0])

    def test_startup_feedback_regression_requires_baseline_reapplication(self):
        opt = self._optimizer()
        self._prime(opt, baseline=1.0)
        ceiling, gates, values = self._sample(
            opt, 1, baseline=1.0, charge=1.0, feedback_seconds=-1,
        )
        self.assertEqual(1.0, ceiling)
        self.assertFalse(gates["solar_physical_relief_active"])
        self.assertEqual("physical_feedback_regressed", values["solar_physical_relief_reason"])
        self.assertEqual(0, values["solar_physical_relief_confirmations"])
        self.assertIsNone(opt._solar_relief.command_ts)
        self.assertIsNone(opt._solar_relief.feedback_ts)
        for second in (2, 3):
            self.assertEqual(1.0, self._sample(opt, second, baseline=1.0, charge=1.0)[0])
        self._command(opt, 1.0, 3)
        self.assertEqual(1.0, self._sample(opt, 4, baseline=1.0, charge=1.0)[0])
        self.assertAlmostEqual(1.4, self._sample(opt, 5, baseline=1.0, charge=1.0)[0])

    def test_reissuing_unchanged_command_does_not_starve_confirmation(self):
        opt = self._optimizer()
        self._prime(opt)
        self.assertEqual(0.0, self._sample(opt, 1)[0])
        self._command(opt, 0.0, 1)
        self.assertAlmostEqual(0.4, self._sample(opt, 2)[0])

    def test_pre_command_feedback_without_regression_retains_active_relief(self):
        opt = self._optimizer()
        self._prime(opt, baseline=1.0)
        self.assertEqual(1.0, self._sample(opt, 1, baseline=1.0, charge=1.0)[0])
        self.assertAlmostEqual(1.4, self._sample(opt, 2, baseline=1.0, charge=1.0)[0])
        second = 2
        # The last accepted report predates command completion, but has not
        # regressed. Waiting for the next report must not revoke earned relief.
        self._command(opt, 1.4, second + 0.5)
        ceiling, gates, values = self._sample(
            opt, second + 1, baseline=1.0, charge=1.0,
            feedback_seconds=second,
        )
        self.assertAlmostEqual(1.4, ceiling)
        self.assertTrue(gates["solar_physical_relief_active"])
        self.assertEqual("awaiting_post_command_feedback", values["solar_physical_relief_reason"])
        self.assertEqual(0, values["solar_physical_relief_confirmations"])
        self.assertAlmostEqual(1.4, self._sample(opt, second + 2, baseline=1.0, charge=1.4)[0])
        self.assertAlmostEqual(1.8, self._sample(opt, second + 3, baseline=1.0, charge=1.4)[0])

    def test_regressed_pre_command_feedback_resets_active_relief_to_current_baseline(self):
        async def run():
            opt = self._optimizer()
            opt.ha = RecordingHA(state_values={opt.cfg.ems_mode_select: MODE_MAX_SELF})
            baseline = 0.81

            def decide(second, **flow):
                state, decision = self._decision(opt, second, battery_soc=55.0, **flow)
                self._assert_solar_controls(opt, decision)
                self.assertEqual(baseline, decision.trace_values["solar_charge_ceiling_baseline_kw"])
                return state, decision

            async def apply(second, state, decision):
                with self.optimizer_time(self.WHEN + timedelta(seconds=second)):
                    result = await opt._apply(state, decision)
                self.assertTrue(result.succeeded, result.error)

            # Establish actual Solar ownership and earn relief through two
            # post-command observations, then apply the resulting probe.
            for second, expected in ((1, baseline), (2, baseline), (3, 1.21)):
                state, decision = decide(second, charge=baseline)
                self.assertAlmostEqual(expected, decision.ess_charge_limit)
                await apply(second, state, decision)
            self.assertTrue(decision.trace_gates["solar_physical_relief_active"])
            self.assertEqual(0.4, decision.trace_values["solar_physical_relief_kw"])
            self.assertEqual(self.WHEN.timestamp() + 3, opt._solar_relief.command_ts)

            _, decision = decide(4, charge=1.21)
            self.assertEqual(1, decision.trace_values["solar_physical_relief_confirmations"])
            _, decision = decide(5, charge=baseline, feedback_seconds=2)
            self.assertTrue(decision.trace_gates["solar_physical_relief_flow_trusted"])
            self.assertEqual(baseline, decision.ess_charge_limit)
            self.assertFalse(decision.trace_gates["solar_physical_relief_active"])
            self.assertEqual(0.0, decision.trace_values["solar_physical_relief_kw"])
            self.assertEqual(0, decision.trace_values["solar_physical_relief_confirmations"])
            self.assertEqual("physical_feedback_regressed", decision.trace_values["solar_physical_relief_reason"])
            self.assertFalse(opt._solar_relief.retry)
            for reference in ("command_kw", "command_ts", "feedback_ts", "target_kw",
                              "limit_kw", "baseline_kw", "normal_kw"):
                self.assertIsNone(getattr(opt._solar_relief, reference), reference)

            # The invalid epoch cannot authorize another probe: reapply the
            # current baseline and require two newly observed confirmations.
            state, decision = decide(6, charge=baseline)
            self.assertEqual(baseline, decision.ess_charge_limit)
            self.assertEqual(0, decision.trace_values["solar_physical_relief_confirmations"])
            await apply(6, state, decision)
            _, decision = decide(7, charge=baseline)
            self.assertEqual(baseline, decision.ess_charge_limit)
            self.assertEqual(1, decision.trace_values["solar_physical_relief_confirmations"])
            _, decision = decide(8, charge=baseline)
            self.assertAlmostEqual(1.21, decision.ess_charge_limit)

        asyncio.run(run())

    def test_export_timestamp_alone_cannot_reuse_old_pv_load_and_import_evidence(self):
        opt = self._optimizer()
        self._prime(opt)
        self.assertEqual(0.0, self._sample(opt, 1)[0])
        state = self._flow_state(2, feedback_seconds=1)
        state.hvac_solar_inputs = replace(
            state.hvac_solar_inputs,
            grid_export_power=replace(
                state.hvac_solar_inputs.grid_export_power,
                observed_at_ts=self.WHEN.timestamp() + 2,
            ),
        )
        self.assertEqual(0.0, self._sample(opt, 2, state=state)[0])
        self.assertAlmostEqual(0.4, self._sample(opt, 3)[0])

    def test_saturated_export_without_charge_response_cannot_ramp_further(self):
        opt = self._optimizer()
        second = self._ramp(opt, 1)
        for offset in range(1, 5):
            self.assertAlmostEqual(0.4, self._sample(opt, second + offset, charge=0.0)[0])
        self.assertAlmostEqual(0.4, self._sample(opt, second + 5, charge=0.4)[0])
        self.assertAlmostEqual(0.8, self._sample(opt, second + 6, charge=0.4)[0])

    def test_morning_slow_probe_and_ramp_settings_do_not_tune_solar(self):
        opt = self._optimizer(
            morning_slow_physical_export_headroom_kw=0.0,
            morning_slow_export_probe_enabled=False,
            morning_slow_export_probe_step_kw=9.0,
            morning_slow_export_probe_saturation_margin_kw=3.0,
            morning_slow_export_ramp_up_step_kw=9.0,
            morning_slow_export_ramp_down_step_kw=9.0,
        )
        self._ramp(opt, 2)

    def test_enabled_physical_limit_is_site_specific_not_hard_coded_to_15(self):
        opt = self._optimizer(grid_connection_export_limit_kw=10.0)
        self._prime(opt)
        self.assertEqual(0.0, self._sample(opt, 1, export=9.8)[0])
        self.assertAlmostEqual(0.4, self._sample(opt, 2, export=9.8)[0])

    def test_failed_probe_backs_down_without_counterfactual_export_retention(self):
        opt = self._optimizer()
        second = self._ramp(opt, 4)
        self.assertAlmostEqual(0.4, self._sample(opt, second + 1, export=14.49, charge=1.6)[0])
        self._command(opt, 0.4, second + 1)
        self.assertEqual(0.0, self._sample(opt, second + 2, export=14.49, charge=0.4)[0])

    def test_new_export_drop_reduces_once_with_other_flows_still_fresh_and_coherent(self):
        opt = self._optimizer()
        second = self._ramp(opt, 4)
        state = self._flow_state(second + 1, export=14.49, charge=1.6, feedback_seconds=second)
        state.hvac_solar_inputs = replace(
            state.hvac_solar_inputs,
            grid_export_power=replace(
                state.hvac_solar_inputs.grid_export_power,
                observed_at_ts=self.WHEN.timestamp() + second + 1,
            ),
        )
        self.assertAlmostEqual(0.4, self._sample(opt, second + 1, state=state)[0])
        self._command(opt, 0.4, second + 1)
        self.assertAlmostEqual(0.4, self._sample(opt, second + 2, state=state)[0])

    def test_14_5_exit_boundary_holds_and_does_not_increase(self):
        opt = self._optimizer()
        second = self._ramp(opt, 2)
        for offset in range(1, 5):
            self.assertAlmostEqual(0.8, self._sample(opt, second + offset, export=14.5, charge=0.8)[0])

    def test_below_14_hard_resets_but_exact_14_uses_downward_step(self):
        for export, expected in ((13.99, 0.0), (14.0, 0.8)):
            with self.subTest(export=export):
                opt = self._optimizer()
                second = self._ramp(opt, 5)
                self.assertAlmostEqual(expected, self._sample(opt, second + 1, export=export, charge=2.0)[0])

    def test_startup_below_hard_threshold_keeps_normal_two_observation_entry(self):
        opt = self._optimizer()
        self.assertEqual(0.0, self._sample(opt, 0, export=13.0)[0])
        self._command(opt, 0.0, 0)
        self.assertEqual(0.0, self._sample(opt, 1, export=15.0)[0])
        self.assertAlmostEqual(0.4, self._sample(opt, 2, export=15.0)[0])

    def test_hard_reset_of_active_relief_retains_three_observation_retry(self):
        opt = self._optimizer()
        second = self._ramp(opt, 1)
        self.assertEqual(0.0, self._sample(opt, second + 1, export=13.0, charge=0.4)[0])
        self._command(opt, 0.0, second + 1)
        for offset in (2, 3):
            self.assertEqual(0.0, self._sample(opt, second + offset, export=15.0)[0])
        self.assertAlmostEqual(0.4, self._sample(opt, second + 4, export=15.0)[0])

    def test_three_fresh_saturated_observations_required_after_reduction(self):
        opt = self._optimizer()
        second = self._ramp(opt, 1)
        self.assertEqual(0.0, self._sample(opt, second + 1, export=14.49, charge=0.4)[0])
        self._command(opt, 0.0, second + 1)
        for offset in (2, 3):
            self.assertEqual(0.0, self._sample(opt, second + offset)[0])
        self.assertAlmostEqual(0.4, self._sample(opt, second + 4)[0])

    def test_alternating_saturation_and_export_fall_cannot_chatter_upward(self):
        opt = self._optimizer()
        second = self._ramp(opt, 1)
        self.assertEqual(0.0, self._sample(opt, second + 1, export=14.49, charge=0.4)[0])
        self._command(opt, 0.0, second + 1)
        for offset in range(2, 16):
            export = 15.0 if offset % 2 == 0 else 14.49
            self.assertEqual(0.0, self._sample(opt, second + offset, export=export)[0])

    def test_trust_coherence_or_provenance_loss_resets_active_relief(self):
        cases = ("stale_export", "unavailable_pv", "incoherent", "missing_provenance", "negative_import")
        for case in cases:
            with self.subTest(case=case):
                opt = self._optimizer()
                second = self._ramp(opt, 1)
                state = self._flow_state(second + 1, charge=0.4)
                inputs = state.hvac_solar_inputs
                if case == "stale_export":
                    inputs = replace(inputs, grid_export_power=replace(inputs.grid_export_power, fresh=False))
                elif case == "unavailable_pv":
                    inputs = replace(inputs, pv_power=replace(inputs.pv_power, available=False))
                elif case == "missing_provenance":
                    inputs = replace(inputs, grid_export_power=replace(inputs.grid_export_power, observed_at_ts=None))
                elif case == "negative_import":
                    inputs = replace(inputs, grid_import_power=replace(inputs.grid_import_power, value=-1.0))
                else:
                    state.derived_power_flow_coherent = False
                state.hvac_solar_inputs = inputs
                self.assertEqual(0.0, self._sample(opt, second + 1, state=state)[0])

    def test_owner_ems_and_configuration_loss_reset_active_relief(self):
        cases = ("solar", "automated", "manual", "force", "ems", "battery_export", "disabled", "invalid")
        for case in cases:
            with self.subTest(case=case):
                opt = self._optimizer()
                second = self._ramp(opt, 1)
                state = self._flow_state(second + 1, charge=0.4)
                args = {}
                if case == "solar":
                    args["owned"] = False
                elif case in {"automated", "manual", "force"}:
                    state.sigenergy_mode_observed = case != "automated"
                    state.sigenergy_mode = "Manual" if case == "manual" else opt.cfg.full_export_option if case == "force" else "Automated"
                elif case == "ems":
                    args["ems_mode"] = "Command Discharging (PV First)"
                elif case == "battery_export":
                    args["battery_export_owner"] = "high_price"
                else:
                    opt.cfg.__dict__["grid_connection_export_limit_kw"] = 0.0 if case == "disabled" else float("nan")
                self.assertEqual(0.0, self._sample(opt, second + 1, state=state, **args)[0])

    def test_relief_plus_baseline_never_exceeds_normal_safe_request(self):
        opt = self._optimizer()
        self._ramp(opt, 5, baseline=4.5, normal=5.0)

    def test_changed_baseline_restarts_confirmation_without_stale_relief(self):
        opt = self._optimizer()
        second = self._ramp(opt, 2)
        self.assertEqual(1.0, self._sample(opt, second + 1, baseline=1.0, charge=0.8)[0])
        self._command(opt, 1.0, second + 1)
        self.assertEqual(1.0, self._sample(opt, second + 2, baseline=1.0, charge=1.0)[0])
        self.assertAlmostEqual(1.4, self._sample(opt, second + 3, baseline=1.0, charge=1.0)[0])

    def test_changed_baseline_cannot_bypass_three_observation_retry_after_export_fall(self):
        opt = self._optimizer()
        second = self._ramp(opt, 1)
        self.assertEqual(0.0, self._sample(opt, second + 1, export=14.49, charge=0.4)[0])
        self._command(opt, 0.0, second + 1)
        self.assertEqual(1.0, self._sample(opt, second + 2, baseline=1.0, charge=0.0)[0])
        self._command(opt, 1.0, second + 2)
        for offset in (3, 4):
            self.assertEqual(1.0, self._sample(opt, second + offset, baseline=1.0, charge=1.0)[0])
        self.assertAlmostEqual(1.4, self._sample(opt, second + 5, baseline=1.0, charge=1.0)[0])

    def test_solcast_estimate_and_hidden_pv_are_not_probe_authority(self):
        opt = self._optimizer()
        self._prime(opt)
        for second in range(1, 5):
            state = self._flow_state(second, export=10.0)
            state.solar_power_now_kw = 100.0
            state.forecast_remaining_kwh = 1000.0
            self.assertEqual(0.0, self._sample(opt, second, state=state)[0])

    def test_live_reader_retains_source_flow_timestamps_across_repeated_fetches(self):
        opt = self._optimizer()
        entities = (
            (opt.cfg.pv_power_sensor, "pv_power", 16.0),
            (opt.cfg.consumed_power_sensor, "load_power", 1.0),
            (opt.cfg.grid_import_power_sensor, "grid_import_power", 0.0),
            (opt.cfg.grid_export_power_sensor, "grid_export_power", 15.0),
        )
        ha = RecordingHA()
        opt.ha = ha
        for index, (entity, _, value) in enumerate(entities):
            source_ts = self.WHEN.timestamp() - 20 + index
            ha.states[entity] = {
                "state": value,
                "attributes": {},
                "last_reported": datetime.fromtimestamp(source_ts, timezone.utc).isoformat(),
            }
        for elapsed in (0, 10):
            with self.optimizer_time(self.WHEN + timedelta(seconds=elapsed)):
                state = asyncio.run(opt._read_state())
            for index, (_, attribute, _) in enumerate(entities):
                observed = getattr(state.hvac_solar_inputs, attribute)
                self.assertEqual(self.WHEN.timestamp() - 20 + index, observed.observed_at_ts)
                self.assertTrue(observed.fresh)
            self.assertTrue(state.derived_power_flow_coherent)

        del ha.states[opt.cfg.pv_power_sensor]["last_reported"]
        with self.optimizer_time(self.WHEN + timedelta(seconds=11)):
            missing = asyncio.run(opt._read_state())
        self.assertIsNone(missing.hvac_solar_inputs.pv_power.observed_at_ts)
        self.assertFalse(missing.hvac_solar_inputs.pv_power.fresh)

    def _decision(self, opt, seconds, **changes):
        state = self._flow_state(seconds, **changes)
        if not opt._solar_provider_baselined:
            previous = replace(state, solcast_provider_polled=datetime.fromtimestamp(
                self.WHEN.timestamp() - 60, timezone.utc,
            ).isoformat())
            with self.optimizer_time(self.WHEN):
                opt._update_solar_provider(previous, self.WHEN.timestamp())
        return state, self.decide(opt, state, self.WHEN + timedelta(seconds=seconds))

    def _assert_solar_controls(self, opt, decision):
        self.assertTrue(decision.solar_surplus_policy_active)
        self.assertTrue(decision.trace_gates["solar_charge_ceiling_owned"])
        self.assertEqual("none", decision.trace_values["battery_export_owner"])
        self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
        self.assertNotIn(decision.ems_mode, DISCHARGE_MODES)
        self.assertEqual(MSC_SURPLUS_CEILING, decision.export_intent)
        self.assertNotEqual(BATTERY_EXPORT, decision.export_intent)
        self.assertEqual(opt.cfg.export_limit_high, decision.export_limit)
        self.assertEqual(opt.cfg.pv_max_power_normal, decision.pv_max_power_limit)

    def test_final_solar_integration_preserves_export_pv_msc_and_demand_import_owner(self):
        opt = self._optimizer()
        _, initial = self._decision(opt, 0, demand_window_active=True)
        self._assert_solar_controls(opt, initial)
        self.assertEqual(0.0, initial.ess_charge_limit)
        self._command(opt, 0.0, 0)
        for second, expected in ((1, 0.0), (2, 0.4)):
            _, decision = self._decision(opt, second, demand_window_active=True)
            self._assert_solar_controls(opt, decision)
            self.assertAlmostEqual(expected, decision.ess_charge_limit)
            self.assertEqual(0.0, decision.import_limit)
            self.assertEqual("demand_window_block", decision.trace_values["import_branch"])

    def test_morning_slow_and_exact_full_never_acquire_solar_relief(self):
        for owner in ("morning_slow", "exact_full"):
            with self.subTest(owner=owner):
                opt = self._optimizer()
                self._ramp(opt, 1)
                changes = {}
                if owner == "morning_slow":
                    opt._morning_slow_charge_active = lambda *args, **kwargs: True
                else:
                    changes.update(battery_soc=100.0, available_discharge_energy_kwh=10.0)
                _, decision = self._decision(opt, 3, **changes)
                self.assertFalse(decision.trace_gates.get("solar_physical_relief_active", False))
                if owner == "morning_slow":
                    self.assertFalse(decision.trace_gates["solar_charge_ceiling_owned"])
                    self.assertEqual(2.0, decision.ess_charge_limit)
                self.assertEqual("none", decision.trace_values["battery_export_owner"])
                self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
                self.assertEqual(25.0, decision.export_limit)
                self.assertEqual(25.0, decision.pv_max_power_limit)

    def test_successful_charge_application_arms_feedback_without_decision_only_authority(self):
        async def run():
            opt = self._optimizer()
            state, decision = self._decision(opt, 0)
            ha = RecordingHA(state_values={opt.cfg.ems_mode_select: MODE_MAX_SELF})
            opt.ha = ha
            with self.optimizer_time(self.WHEN):
                result = await opt._apply(state, decision)
            self.assertTrue(result.succeeded, result.error)
            self.assertIn(("set_number", "number.test_charge", 0.0), ha.calls)
            for second, expected in ((1, 0.0), (2, 0.4)):
                _, next_decision = self._decision(opt, second)
                self.assertAlmostEqual(expected, next_decision.ess_charge_limit)
        asyncio.run(run())

    def test_failed_charge_application_cannot_arm_feedback(self):
        async def run():
            opt = self._optimizer()
            state, decision = self._decision(opt, 0)
            ha = RecordingHA(state_values={opt.cfg.ems_mode_select: MODE_MAX_SELF})
            original = ha.set_number

            async def fail_charge(entity, value):
                if entity == "number.test_charge":
                    return False
                return await original(entity, value)

            ha.set_number = fail_charge
            opt.ha = ha
            with self.optimizer_time(self.WHEN):
                result = await opt._apply(state, decision)
            self.assertFalse(result.succeeded)
            for second in range(1, 4):
                _, next_decision = self._decision(opt, second)
                self.assertEqual(0.0, next_decision.ess_charge_limit)
        asyncio.run(run())

    def test_flow_expiry_during_pre_charge_await_removes_relief_before_write(self):
        self._assert_apply_flow_expiry(during_charge=False)

    def test_flow_expiry_during_charge_await_restores_baseline_in_same_application(self):
        self._assert_apply_flow_expiry(during_charge=True)

    def _assert_apply_flow_expiry(self, *, during_charge):
        async def run():
            opt = self._optimizer()
            self._decision(opt, 0)
            self._command(opt, 0.0, 0)
            self._decision(opt, 1)
            state, decision = self._decision(opt, 2)
            self.assertEqual(0.4, decision.ess_charge_limit)
            state.current_import_limit = 1.0
            moment = [self.WHEN.timestamp() + 2]

            class AdvancingDateTime(datetime):
                @classmethod
                def now(cls, tz=None):
                    return cls.fromtimestamp(moment[0], tz)

            ha = RecordingHA(state_values={opt.cfg.ems_mode_select: MODE_MAX_SELF})
            original = ha.set_number
            crossed = False

            async def cross_flow_age(entity, value):
                nonlocal crossed
                result = await original(entity, value)
                selected = entity == ("number.test_charge" if during_charge else opt.cfg.grid_import_limit)
                if selected and not crossed:
                    crossed = True
                    moment[0] += opt.cfg.hvac_solar_data_max_age_seconds + 1
                return result

            ha.set_number = cross_flow_age
            opt.ha = ha
            with patch("app.optimizer.datetime", AdvancingDateTime):
                result = await opt._apply(state, decision)
            self.assertTrue(crossed)
            self.assertTrue(result.succeeded, result.error)
            writes = [value for action, entity, value in ha.calls
                      if action == "set_number" and entity == "number.test_charge"]
            self.assertEqual([0.4, 0.0] if during_charge else [0.0], writes)
            self.assertTrue(decision.trace_gates["solar_charge_ceiling_owned"])
            self.assertFalse(decision.trace_gates["solar_physical_relief_active"])
            self.assertEqual(0.0, decision.ess_charge_limit)
            self.assertEqual(0.0, decision.trace_values["solar_charge_ceiling_requested_kw"])
        asyncio.run(run())
