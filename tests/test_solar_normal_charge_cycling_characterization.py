"""O2 re-entry protection, with trace-inspired inputs and synthetic detail.

The supplied trace does not serialize detailed Solcast intervals. These tests
therefore exercise the approved re-entry guard, not an exact trace replay or a
minimum-charge policy. All decisions use the real energy budget, final ownership
arbitration and dynamic charge calculation. Live report provenance is synthetic;
there are no HA calls or claims of physical application.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo

from app.models import (
    BATTERY_EXPORT, HVACObservedValue, HVACSolarInputContext, MSC_SURPLUS_CEILING,
)
from app.optimizer import DISCHARGE_MODES, MODE_MAX_SELF
from test_phase1_solar_dynamic_charge_ceiling_characterization import (
    SolarDynamicChargeFixture,
)


class SolarNormalChargeCyclingCharacterizationTests(SolarDynamicChargeFixture):
    START_SYDNEY = datetime(2026, 10, 25, 12, 0, 10, tzinfo=ZoneInfo("Australia/Sydney"))
    # The shared state helper accepts host-local naive datetimes. Preserve the
    # explicit Sydney instant independently of the test machine's timezone.
    WHEN = datetime.fromtimestamp(START_SYDNEY.timestamp())
    FIXED_AFTERNOON = WHEN  # Seed known-empty accounting for this synthetic day.
    SUNSET_TS = datetime(
        2026, 10, 25, 19, 29, 52, 793484, tzinfo=ZoneInfo("Australia/Sydney"),
    ).timestamp()
    NORMAL_CHARGE_KW = 21.0
    REMAINING_KWH = 35.9018

    @staticmethod
    @contextmanager
    def optimizer_time(when):
        # Advance wall/source and local monotonic clocks together for the
        # synthetic six-second sequence. Neither clock is read from HA.
        with SolarDynamicChargeFixture.optimizer_time(when), patch(
            "app.optimizer.monotonic", return_value=when.timestamp(),
        ):
            yield

    def _state(
        self, *, when=None, forecast_pv_kw=None,
        load_report_offset_seconds=0.0, **overrides,
    ):
        at = when or self.WHEN
        values = {
            "battery_soc": 62.6,
            "battery_capacity_kwh": 40.3,
            "available_discharge_energy_kwh": 40.3 * 0.626,
            "pv_kw": 16.129,
            "solar_power_now_kw": 16.129,
            "load_kw": 1.969,
            "forecast_remaining_kwh": self.REMAINING_KWH,
            "forecast_today_kwh": 79.325,
            "next_sunset_ts": self.SUNSET_TS,
            "hours_to_sunset": (self.SUNSET_TS - at.timestamp()) / 3600.0,
            # Fixed, complete half-hour intervals through the fixed sunset.
            # This synthetic shape produces positive then zero Solar charge
            # requests as load changes; the trace's exact 1.52 kW is not replayed.
            "solcast_detailed": self._detailed_forecast([15.7] + [4.4] * 14),
            "solcast_provider_polled": datetime.fromtimestamp(
                self.WHEN.timestamp() - 1, timezone.utc,
            ).isoformat(),
            "solcast_provider_next_update": datetime.fromtimestamp(
                self.WHEN.timestamp() + 3600, timezone.utc,
            ).isoformat(),
        }
        values.update(overrides)
        state = super()._state(when=at, **values)
        if "hvac_solar_inputs" not in overrides:
            def report(value, trusted=True, offset=0.0):
                return HVACObservedValue(
                    value=value, available=trusted, fresh=trusted,
                    observed_at_ts=at.timestamp() + offset,
                )

            state.hvac_solar_inputs = HVACSolarInputContext(
                live_snapshot=True,
                pv_power=report(state.pv_kw, state.pv_power_trusted),
                load_power=report(
                    state.load_kw, state.load_power_trusted,
                    offset=load_report_offset_seconds,
                ),
                battery_power=report(state.battery_power_sensor_kw),
                grid_import_power=report(state.grid_import_power_kw),
                grid_export_power=report(state.grid_export_power_kw),
                solar_power_now=report(state.solar_power_now_kw),
                sun_above_horizon=report(state.sun_above_horizon),
                control_mode=report(state.sigenergy_mode, state.sigenergy_mode_observed),
                observed_ems_mode=report(state.current_ems_mode, state.ems_mode_observed),
                remote_ems_control=report(state.ha_control_switch_state),
                observed_export_limit=report(state.current_export_limit),
            )
        return state

    def _sequence(self, loads, *, per_step=None, offsets=None, optimizer_overrides=None):
        optimizer = self._optimizer(**(optimizer_overrides or {}))
        decisions = []
        for index, load_kw in enumerate(loads):
            values = dict((per_step or {}).get(index, {}))
            if decisions:
                # Feed the prior request back as observed numeric limits while
                # retaining observed Automated/exact MSC authority. No dispatch
                # or successful physical application is implied by this fixture.
                values.update(
                    current_ess_charge_limit=decisions[-1].ess_charge_limit,
                    current_export_limit=decisions[-1].export_limit,
                )
            decision = self._decide(
                optimizer,
                when=self.WHEN + timedelta(seconds=(
                    offsets[index] if offsets is not None else 6 * index
                )),
                load_kw=load_kw,
                **values,
            )
            optimizer._last_decision = decision
            guard = optimizer._solar_budget_reentry
            if decision.solar_surplus_policy_active and guard.required:
                # Simulate ONLY the caller's successful automatic-application
                # commit boundary. Qualification and all decision calculations
                # are real; no service call or physical settlement is simulated.
                self.assertTrue(guard.commit(guard.generation))
            decisions.append(decision)
        return decisions

    def _assert_pv_only_without_import(self, decisions):
        for decision in decisions:
            self.assertEqual("none", decision.trace_values["battery_export_owner"])
            self.assertNotEqual(BATTERY_EXPORT, decision.export_intent)
            self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
            self.assertNotIn(decision.ems_mode, DISCHARGE_MODES)
            self.assertEqual(0.0, decision.import_limit)
            self.assertFalse(decision.morning_slow_charge_active)
            self.assertLessEqual(decision.ess_charge_limit, self.NORMAL_CHARGE_KW)

    def _assert_normal_charge(self, decision):
        self.assertFalse(decision.solar_surplus_policy_active)
        self.assertFalse(decision.trace_gates["solar_charge_ceiling_owned"])
        self.assertFalse(decision.trace_gates["solar_surplus_dip_hold_active"])
        self.assertEqual("normal", decision.trace_values["ess_charge_limit_owner"])
        self.assertEqual(self.NORMAL_CHARGE_KW, decision.ess_charge_limit)
        self.assertIsNone(decision.trace_values["solar_charge_ceiling_requested_kw"])

    def test_six_second_load_crossing_releases_21_kw_then_qualifies_reentry(self):
        decisions = self._sequence([1.969, 2.399] + [1.536] * 6)
        active, deficit, pending = decisions[:3]

        self.assertEqual([True] + [False] * 6 + [True], [d.solar_surplus_policy_active for d in decisions])
        self.assertEqual(
            ["solar_surplus", "normal", "normal"],
            [d.trace_values["ess_charge_limit_owner"] for d in decisions[:3]],
        )
        self.assertGreater(active.ess_charge_limit, 0.0)
        self.assertLess(active.ess_charge_limit, self.NORMAL_CHARGE_KW)
        self._assert_normal_charge(deficit)
        self._assert_normal_charge(pending)
        for decision in decisions[2:-1]:
            self._assert_normal_charge(decision)
        self.assertEqual(0.0, decisions[-1].ess_charge_limit)
        self.assertTrue(decisions[-1].trace_gates["solar_charge_ceiling_owned"])
        self.assertEqual("energy_budget_not_positive", deficit.trace_values["solar_surplus_fail_reason"])
        self.assertAlmostEqual(13.73, deficit.trace_values["solar_measured_pv_surplus_kw"])

        for index, (decision, load_kw) in enumerate(zip(decisions[:3], [1.969, 2.399, 1.536])):
            hours = (self.SUNSET_TS - self.WHEN.timestamp() - 6 * index) / 3600.0
            fill_kwh = 40.3 * (1.0 - 0.626)
            protected_kwh = 1.20 * (load_kw * hours + fill_kwh)
            self.assertAlmostEqual(load_kw * hours, decision.trace_values["solar_expected_remaining_load_kwh"])
            self.assertAlmostEqual(fill_kwh, decision.trace_values["solar_fill_need_to_full_kwh"])
            self.assertAlmostEqual(protected_kwh, decision.trace_values["solar_protected_required_energy_kwh"])
            self.assertAlmostEqual(self.REMAINING_KWH - protected_kwh, decision.trace_values["solar_raw_exportable_energy_kwh"])
            self.assertEqual(self.REMAINING_KWH, decision.trace_values["solar_remaining_forecast_kwh"])
            self.assertTrue(decision.trace_gates["solar_timing_passed"])
            self.assertTrue(decision.trace_gates["solar_measured_surplus_gate"])
            self.assertTrue(decision.trace_gates["solar_energy_evidence_trusted"])
            self.assertTrue(decision.trace_gates["solar_provider_authority_trusted"])
            self.assertEqual("VALID", decision.trace_values["solar_provider_state"])
            self.assertEqual(active.trace_values["solar_provider_verified_polled"], decision.trace_values["solar_provider_verified_polled"])
            self.assertEqual(active.trace_values["solar_charge_ceiling_fill_deadline_ts"], decision.trace_values["solar_charge_ceiling_fill_deadline_ts"])
            if decision.solar_surplus_policy_active:
                self.assertEqual(MSC_SURPLUS_CEILING, decision.export_intent)
                self.assertTrue(decision.trace_gates["solar_charge_ceiling_owned"])
        self.assertGreater(active.trace_values["solar_raw_exportable_energy_kwh"], 0.0)
        self.assertLess(deficit.trace_values["solar_raw_exportable_energy_kwh"], 0.0)
        self.assertGreater(pending.trace_values["solar_raw_exportable_energy_kwh"], 0.0)
        self._assert_pv_only_without_import(decisions)

    def test_short_load_spike_is_projected_across_remaining_daylight(self):
        active, spike, pending = self._sequence([1.969, 2.399, 1.969])

        # A six-second 0.430 kW load rise consumes only 0.000717 kWh if
        # transient; current policy projects it over almost 7.5 daylight hours.
        six_second_increment = (2.399 - 1.969) * 6.0 / 3600.0
        projected_increment = (
            spike.trace_values["solar_expected_remaining_load_kwh"]
            - active.trace_values["solar_expected_remaining_load_kwh"]
        )
        self.assertGreater(projected_increment, 3.2)
        self.assertGreater(projected_increment, 4000 * six_second_increment)
        self._assert_normal_charge(spike)
        self._assert_normal_charge(pending)
        self._assert_pv_only_without_import([active, spike, pending])

    def test_repeated_crossings_keep_normal_charge_after_first_budget_exit(self):
        decisions = self._sequence([1.969, 2.399, 1.536, 2.399, 1.969])

        self.assertEqual([True, False, False, False, False], [d.solar_surplus_policy_active for d in decisions])
        for decision in decisions[1:]:
            self._assert_normal_charge(decision)
        self.assertEqual("solar_surplus", decisions[0].trace_values["ess_charge_limit_owner"])
        self.assertLess(decisions[0].ess_charge_limit, self.NORMAL_CHARGE_KW)
        self._assert_pv_only_without_import(decisions)

    def test_safe_load_changes_keep_zero_charge_when_future_covers_fill(self):
        decisions = self._sequence([1.7, 1.75, 1.6, 1.7])

        for decision in decisions:
            self.assertTrue(decision.solar_surplus_policy_active)
            self.assertTrue(decision.trace_gates["solar_charge_ceiling_owned"])
            self.assertEqual(0.0, decision.ess_charge_limit)
            self.assertEqual(0.0, decision.trace_values["solar_charge_ceiling_required_now_kwh"])
            self.assertGreaterEqual(
                decision.trace_values["solar_charge_ceiling_future_opportunity_kwh"],
                decision.trace_values["solar_charge_ceiling_protected_fill_need_kwh"],
            )
            self.assertEqual("future_opportunity_covers_protected_fill", decision.trace_values["solar_charge_ceiling_reason"])
        self._assert_pv_only_without_import(decisions)

    def test_persistently_failed_budget_keeps_normal_charging(self):
        decisions = self._sequence([1.969, 2.399, 2.399, 2.399])

        self.assertTrue(decisions[0].solar_surplus_policy_active)
        for decision in decisions[1:]:
            self._assert_normal_charge(decision)
            self.assertEqual("energy_budget_not_positive", decision.trace_values["solar_surplus_fail_reason"])
            self.assertTrue(decision.trace_gates["solar_measured_surplus_gate"])
        self._assert_pv_only_without_import(decisions)

    def test_tariff_trust_and_automated_authority_loss_close_next_cycle(self):
        cases = (
            ({"feedin_price": 0.005, "feedin_price_cents": 0.5}, "feedin_tariff_below_one_cent_or_untrusted"),
            ({"pv_power_trusted": False}, "pv_power_untrusted_or_invalid"),
            ({"load_power_trusted": False}, "load_power_untrusted_or_invalid"),
            ({"forecast_remaining_observation_trusted": False}, "remaining_forecast_untrusted_or_invalid"),
            ({"pv_load_observations_coherent": False}, "pv_load_observations_incoherent"),
            ({"sigenergy_mode_observed": False}, "automated_authority_unavailable"),
        )
        for overrides, reason in cases:
            with self.subTest(reason=reason):
                decisions = self._sequence([1.969] * 3, per_step={1: overrides})
                self.assertTrue(decisions[0].solar_surplus_policy_active)
                self._assert_normal_charge(decisions[1])
                self.assertEqual(reason, decisions[1].trace_values["solar_surplus_fail_reason"])
                self.assertTrue(decisions[2].solar_surplus_policy_active)
                self._assert_pv_only_without_import(decisions)

    def test_forecast_downgrade_releases_zero_charge_without_minimum_policy(self):
        decisions = self._sequence(
            [1.536] * 8,
            per_step={1: {"forecast_remaining_kwh": 4.8182}},
        )

        self.assertEqual(0.0, decisions[0].ess_charge_limit)
        self._assert_normal_charge(decisions[1])
        self.assertEqual("energy_budget_not_positive", decisions[1].trace_values["solar_surplus_fail_reason"])
        self.assertEqual(4.8182, decisions[1].trace_values["solar_remaining_forecast_kwh"])
        for decision in decisions[2:-1]:
            self._assert_normal_charge(decision)
        self.assertTrue(decisions[-1].solar_surplus_policy_active)
        self.assertEqual(0.0, decisions[-1].ess_charge_limit)
        self._assert_pv_only_without_import(decisions)

    def test_trust_loss_during_qualification_requires_a_new_full_interval(self):
        decisions = self._sequence(
            [1.969, 2.399] + [1.536] * 9,
            per_step={4: {"load_power_trusted": False}},
        )

        self.assertTrue(decisions[0].solar_surplus_policy_active)
        for decision in decisions[1:-1]:
            self._assert_normal_charge(decision)
        self.assertEqual("load_power_untrusted_or_invalid", decisions[4].trace_values["solar_surplus_fail_reason"])
        self.assertTrue(decisions[-1].solar_surplus_policy_active)
        self.assertEqual(0.0, decisions[-1].ess_charge_limit)
        self._assert_pv_only_without_import(decisions)

    def test_cached_load_at_thirty_second_boundary_cannot_complete_reentry(self):
        decisions = self._sequence(
            [1.969, 2.399] + [1.536] * 4,
            offsets=[0.0, 6.0, 12.0, 41.999, 42.0, 42.001],
            # At exactly thirty elapsed seconds, PV advances but load retains
            # the previous report, whose source span is still only 29.999 s.
            per_step={4: {"load_report_offset_seconds": -0.001}},
        )

        self.assertTrue(decisions[0].solar_surplus_policy_active)
        for decision in decisions[1:-1]:
            self._assert_normal_charge(decision)
        self.assertTrue(decisions[-1].solar_surplus_policy_active)
        self.assertEqual(0.0, decisions[-1].ess_charge_limit)
        self._assert_pv_only_without_import(decisions)

    def test_unsafe_battery_flow_cannot_accrue_budget_reentry_qualification(self):
        decisions = self._sequence(
            [1.969, 2.399] + [1.536] * 11,
            per_step={
                index: {"battery_power_sensor_kw": -1.0}
                for index in range(2, 7)
            },
        )

        self.assertTrue(decisions[0].solar_surplus_policy_active)
        for decision in decisions[1:-1]:
            self._assert_normal_charge(decision)
        for decision in decisions[2:7]:
            self.assertTrue(decision.trace_gates["solar_budget_reentry_raw_candidate"])
            self.assertEqual("closed", decision.trace_values["solar_budget_reentry_state"])
        # Discharge is unsafe at 12..36 s. Safe flow returns at 42 s, which
        # starts a new full interval; 72 s is the earliest permitted readmission.
        self.assertEqual("qualifying", decisions[7].trace_values["solar_budget_reentry_state"])
        self.assertTrue(decisions[-1].solar_surplus_policy_active)
        self.assertEqual(0.0, decisions[-1].ess_charge_limit)
        self._assert_pv_only_without_import(decisions)

    def test_independent_high_owner_cannot_donate_budget_reentry_time(self):
        decisions = self._sequence(
            [1.969, 2.399] + [1.536] * 11,
            optimizer_overrides={
                "allow_low_medium_export_positive_fit": True,
                "allow_positive_fit_battery_discharging": True,
                "min_export_target_soc": 20.0,
            },
            per_step={
                index: {"feedin_price": 1.1, "feedin_price_cents": 110.0}
                for index in range(2, 7)
            },
        )

        self.assertTrue(decisions[0].solar_surplus_policy_active)
        for decision in decisions[2:7]:
            self.assertEqual(BATTERY_EXPORT, decision.export_intent)
            self.assertEqual("high_price", decision.trace_values["battery_export_owner"])
            self.assertFalse(decision.solar_surplus_policy_active)
            self.assertEqual("closed", decision.trace_values["solar_budget_reentry_state"])
        # The independently qualified High owner retains priority at 12..36 s;
        # returning Solar eligibility at 42 s must qualify until 72 s.
        for decision in decisions[7:-1]:
            self._assert_normal_charge(decision)
        self.assertTrue(decisions[-1].solar_surplus_policy_active)
        self.assertEqual(0.0, decisions[-1].ess_charge_limit)
        self._assert_pv_only_without_import([decisions[0], decisions[1]] + decisions[7:])
