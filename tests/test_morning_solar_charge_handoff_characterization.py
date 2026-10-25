from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.models import BATTERY_EXPORT, HVACObservedValue, HVACSolarInputContext, MSC_SURPLUS_CEILING
from app.optimizer import DISCHARGE_MODES, MODE_MAX_SELF, _ActuatorApplicationResult
from import_topup_coverage_helpers import seed_complete_import_history
from test_phase1_solar_dynamic_charge_ceiling_characterization import (
    SolarDynamicChargeFixture,
)


class MorningSolarChargeHandoffCharacterizationTests(SolarDynamicChargeFixture):
    """Synthetic O6 sequence and approved charge-only reacquisition protections.

    Capacity, SoC, aggregate forecast, FiT and available-energy changes follow
    the supplied 25 October evidence. The 2 kW Morning base load, 1.35 safety,
    12:00 owner end, 2h sunset cutoff, detailed curve, normal capability,
    economic settings, authority and zero-import history are fixture assumptions;
    they do not establish the installed configuration or physical application.
    Times use the existing harness's naive local wall-clock convention.
    """

    WHEN = datetime(2026, 10, 25, 11, 35, 42)
    SUNSET = datetime(2026, 10, 25, 19, 29, 52, 793484)
    NORMAL_CHARGE_KW = 21.0
    AVAILABLE_SEQUENCE = (21.57, 21.58, 21.34, 21.60, 21.29, 21.63, 21.36, 21.68)

    def _optimizer(self, **overrides: object):
        values: dict[str, object] = {
            "morning_slow_charge_enabled": True,
            "morning_slow_charge_until": "12:00",
            "morning_slow_charge_rate_kw": 2.0,
            "morning_slow_charge_base_load_kw": 2.0,
            "morning_slow_charge_sunset_cutoff": 2.0,
            "forecast_safety_charging": 1.35,
            "solar_surplus_fill_deadline_margin_minutes": 60.0,
            "grid_connection_export_limit_kw": 0.0,
            "morning_slow_physical_export_headroom_kw": 0.0,
        }
        values.update(overrides)
        optimizer = super()._optimizer(**values)
        optimizer._tz = timezone(self.WHEN.astimezone().utcoffset() or timedelta())
        # Known empty accounting is synthetic evidence, not unknown live cost.
        seed_complete_import_history(optimizer, self.WHEN)
        return optimizer

    def _state(self, **values):
        state = super()._state(**values)
        self._fixture_state = state
        return state

    def _tick(
        self, optimizer, index: int, available_kwh: float, *,
        report_index: int | None = None, monotonic_seconds: float | None = None,
        complete: bool = True, application_result=None, **overrides: object,
    ):
        when = self.WHEN + timedelta(seconds=6 * index)
        values: dict[str, object] = {
            "battery_soc": 50.8,
            "battery_capacity_kwh": 40.3,
            "available_discharge_energy_kwh": available_kwh,
            "forecast_remaining_kwh": 41.2198,
            "forecast_today_kwh": 79.325,
            "forecast_tomorrow_kwh": 60.0,
            "feedin_price": 0.0451714,
            "feedin_price_cents": 4.51714,
            "current_price": 0.30,
            "current_price_cents": 30.0,
            "price_is_actual": True,
            "load_kw": 1.0,
            "pv_kw": 12.0,
            "solar_power_now_kw": 12.0,
            "battery_power_sensor_kw": 0.0,
            "grid_export_power_kw": 11.0,
            "grid_import_power_kw": 0.0,
            "next_sunset_ts": self.SUNSET.timestamp(),
            "hours_to_sunset": (self.SUNSET - when).total_seconds() / 3600.0,
            # Fixed, continuous provider bins cover every tick through sunset.
            # This deliberately synthetic curve supplies ample late Solar
            # opportunity, but makes the Morning slow cap impede timed refill.
            "solcast_detailed": self._detailed_forecast(
                [12.0] + [4.85] * 15,
                when=self.WHEN.replace(minute=30, second=0),
            ),
            "current_export_limit": 25.0,
            # Fixed synthetic readback; decisions below are never applied.
            "current_ess_charge_limit": self.NORMAL_CHARGE_KW,
            "solcast_provider_epoch": optimizer._solar_provider_epoch,
            "solcast_provider_source": (
                optimizer.cfg.forecast_today_sensor,
                optimizer.cfg.solcast_api_last_polled_sensor,
            ),
        }
        values.update(overrides)
        reported_at = self.WHEN.timestamp() + 6 * (
            index if report_index is None else report_index
        )

        def observed(value):
            return HVACObservedValue(
                value=value, available=True, fresh=True, observed_at_ts=reported_at,
            )

        values.setdefault("hvac_solar_inputs", HVACSolarInputContext(
            pv_power=observed(values["pv_kw"]),
            load_power=observed(values["load_kw"]),
            battery_power=observed(values["battery_power_sensor_kw"]),
            grid_import_power=observed(values["grid_import_power_kw"]),
            grid_export_power=observed(values["grid_export_power_kw"]),
            solar_power_now=observed(values["solar_power_now_kw"]),
            sun_above_horizon=observed(True),
            control_mode=observed("Automated"),
            observed_ems_mode=observed(MODE_MAX_SELF),
            remote_ems_control=observed("on"),
            observed_export_limit=observed(25.0),
            live_snapshot=True,
        ))
        # The inherited harness supplies real baseline/advance provider evidence
        # and calls the real _decide. No owner, gate or charge helper is replaced.
        with self.optimizer_time(when), patch(
            "app.optimizer.monotonic", return_value=(
                1000.0 + 6 * index if monotonic_seconds is None else monotonic_seconds
            ),
        ):
            decision = self._decide(optimizer, when=when, **values)
            if complete:
                # Exercise the real completion hook using its typed automatic
                # result contract. This fixture never dispatches _apply or
                # claims that numeric helpers/inverter physically settled.
                result = application_result if application_result is not None else (
                    _ActuatorApplicationResult(
                        succeeded=True, automatic_application_completed=True,
                    )
                )
                optimizer._finish_solar_reentry_application(
                    self._fixture_state, decision, result,
                )
        optimizer._last_decision = decision
        return decision

    def _assert_pv_only(self, optimizer, decision) -> None:
        self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
        self.assertNotIn(decision.ems_mode, DISCHARGE_MODES)
        self.assertEqual("none", decision.trace_values["battery_export_owner"])
        self.assertNotEqual(BATTERY_EXPORT, decision.export_intent)
        self.assertEqual(25.0, decision.pv_max_power_limit)
        self.assertLessEqual(decision.ess_charge_limit, self.NORMAL_CHARGE_KW)
        self.assertEqual(0.0, decision.import_limit)
        self.assertEqual([], optimizer.ha.calls)

    def test_available_energy_crossing_keeps_solar_export_but_stops_charge_churn(self) -> None:
        optimizer = self._optimizer()
        decisions = [
            self._tick(optimizer, index, available)
            for index, available in enumerate(self.AVAILABLE_SEQUENCE)
        ]

        self.assertEqual(
            [False, True, False, True, False, True, False, True],
            [decision.morning_slow_charge_active for decision in decisions],
        )
        for index, decision in enumerate(decisions):
            with self.subTest(tick=index):
                self._assert_pv_only(optimizer, decision)
                self.assertEqual(MSC_SURPLUS_CEILING, decision.export_intent)
                self.assertEqual(25.0, decision.export_limit)
                if index % 2:
                    self.assertFalse(decision.solar_surplus_policy_active)
                    self.assertFalse(decision.trace_gates["solar_charge_ceiling_owned"])
                    self.assertTrue(decision.trace_gates["morning_slow_forecast_refill_relief"])
                    self.assertEqual(self.NORMAL_CHARGE_KW, decision.ess_charge_limit)
                    self.assertEqual("morning_slow", decision.trace_values["ess_charge_limit_owner"])
                else:
                    self.assertTrue(decision.solar_surplus_policy_active)
                    self.assertTrue(decision.trace_gates["solar_provider_authority_trusted"])
                    if index == 0:
                        self.assertTrue(decision.trace_gates["solar_charge_ceiling_owned"])
                        self.assertLessEqual(decision.ess_charge_limit, 2.82)
                    else:
                        self.assertFalse(decision.trace_gates["solar_charge_ceiling_owned"])
                        self.assertEqual("normal", decision.trace_values["ess_charge_limit_owner"])
                        self.assertEqual(self.NORMAL_CHARGE_KW, decision.ess_charge_limit)
        self.assertEqual(
            [0.0] + [self.NORMAL_CHARGE_KW] * 7,
            [decision.ess_charge_limit for decision in decisions],
        )

    def test_steady_available_energy_on_each_side_keeps_its_selected_owner(self) -> None:
        for available, morning in ((21.29, False), (21.68, True)):
            with self.subTest(available_kwh=available):
                optimizer = self._optimizer()
                for index in range(4):
                    decision = self._tick(optimizer, index, available)
                    self._assert_pv_only(optimizer, decision)
                    self.assertEqual(morning, decision.morning_slow_charge_active)
                    self.assertEqual(not morning, decision.solar_surplus_policy_active)
                    self.assertEqual(not morning, decision.trace_gates["solar_charge_ceiling_owned"])
                    if morning:
                        self.assertEqual(self.NORMAL_CHARGE_KW, decision.ess_charge_limit)
                    else:
                        self.assertLessEqual(decision.ess_charge_limit, 2.82)

    def test_real_forecast_deficit_releases_both_owners_and_restores_normal_charge(self) -> None:
        optimizer = self._optimizer()
        self.assertTrue(self._tick(optimizer, 0, 21.29).solar_surplus_policy_active)
        for index in (1, 2):
            decision = self._tick(optimizer, index, 21.29, forecast_remaining_kwh=5.0)
            self._assert_pv_only(optimizer, decision)
            self.assertFalse(decision.morning_slow_charge_active)
            self.assertFalse(decision.solar_surplus_policy_active)
            self.assertFalse(decision.trace_gates["solar_charge_ceiling_owned"])
            self.assertEqual("normal", decision.trace_values["ess_charge_limit_owner"])
            self.assertEqual(self.NORMAL_CHARGE_KW, decision.ess_charge_limit)

    def test_untrusted_forecast_immediately_removes_both_owners(self) -> None:
        optimizer = self._optimizer()
        self.assertTrue(self._tick(optimizer, 0, 21.68).morning_slow_charge_active)
        decision = self._tick(
            optimizer, 1, 21.68, forecast_remaining_observation_trusted=False,
        )
        self._assert_pv_only(optimizer, decision)
        self.assertFalse(decision.morning_slow_charge_active)
        self.assertFalse(decision.solar_surplus_policy_active)
        self.assertFalse(decision.trace_gates["solar_charge_ceiling_owned"])
        self.assertEqual(self.NORMAL_CHARGE_KW, decision.ess_charge_limit)

    def test_untrusted_available_energy_cannot_retain_morning_ownership(self) -> None:
        optimizer = self._optimizer()
        self.assertTrue(self._tick(optimizer, 0, 21.68).morning_slow_charge_active)
        decision = self._tick(
            optimizer, 1, 21.68, available_discharge_energy_trusted=False,
        )
        self._assert_pv_only(optimizer, decision)
        self.assertFalse(decision.morning_slow_charge_active)
        # Solar uses independently trusted SoC/capacity, so loss of the
        # available-energy sensor alone must not manufacture its authority loss.
        self.assertTrue(decision.solar_surplus_policy_active)
        self.assertFalse(decision.trace_gates["solar_charge_ceiling_owned"])
        self.assertEqual(self.NORMAL_CHARGE_KW, decision.ess_charge_limit)
        for index in range(2, 7):
            decision = self._tick(
                optimizer, index, 21.68, available_discharge_energy_trusted=False,
            )
        self.assertTrue(decision.solar_surplus_policy_active)
        self.assertTrue(decision.trace_gates["solar_charge_ceiling_owned"])
        self.assertLessEqual(decision.ess_charge_limit, 2.82)

    def test_detailed_source_loss_removes_only_the_authority_it_supplied(self) -> None:
        for available, morning in ((21.29, False), (21.68, True)):
            with self.subTest(available_kwh=available):
                optimizer = self._optimizer()
                before = self._tick(optimizer, 0, available)
                self.assertEqual(morning, before.morning_slow_charge_active)
                self.assertEqual(not morning, before.solar_surplus_policy_active)
                decision = self._tick(
                    optimizer, 1, available, solcast_detailed_source_trusted=False,
                )
                self._assert_pv_only(optimizer, decision)
                self.assertEqual(morning, decision.morning_slow_charge_active)
                self.assertFalse(decision.solar_surplus_policy_active)
                self.assertFalse(decision.trace_gates["solar_provider_authority_trusted"])
                self.assertFalse(decision.trace_gates["solar_charge_ceiling_owned"])
                self.assertFalse(decision.trace_gates["morning_slow_forecast_refill_relief"])
                self.assertEqual(
                    2.0 if morning else self.NORMAL_CHARGE_KW,
                    decision.ess_charge_limit,
                )

    def test_restrictive_charge_returns_only_after_thirty_seconds_of_fresh_reports(self) -> None:
        optimizer = self._optimizer()
        morning = self._tick(optimizer, 0, 21.68)
        self.assertTrue(morning.trace_gates["morning_slow_reentry_arm_candidate"])
        self.assertTrue(optimizer._solar_charge_reentry.required)
        for index in range(1, 7):
            decision = self._tick(optimizer, index, 21.29)
            self._assert_pv_only(optimizer, decision)
            self.assertTrue(decision.solar_surplus_policy_active)
            self.assertEqual(25.0, decision.export_limit)
            self.assertEqual(index == 6, decision.trace_gates["solar_charge_ceiling_owned"])
            self.assertEqual(0.0 if index == 6 else 21.0, decision.ess_charge_limit)

    def test_generic_failed_pending_or_fallback_application_cannot_arm_handoff(self) -> None:
        outcomes = (
            _ActuatorApplicationResult(succeeded=True),
            _ActuatorApplicationResult(succeeded=False, error="synthetic failure"),
            _ActuatorApplicationResult(
                succeeded=True, transition_pending=True, automatic_transition_pending=True,
            ),
            _ActuatorApplicationResult(
                succeeded=True, automatic_application_completed=True,
                fallback_attempted=True, fallback_succeeded=True,
            ),
        )
        for outcome in outcomes:
            with self.subTest(outcome=outcome):
                optimizer = self._optimizer()
                morning = self._tick(optimizer, 0, 21.68, application_result=outcome)
                self.assertTrue(morning.morning_slow_charge_active)
                self.assertFalse(optimizer._solar_charge_reentry.required)
                decision = self._tick(optimizer, 1, 21.29)
                self.assertTrue(decision.trace_gates["solar_charge_ceiling_owned"])
                self.assertEqual(0.0, decision.ess_charge_limit)

    def test_decision_without_application_does_not_arm_handoff(self) -> None:
        optimizer = self._optimizer()
        self._tick(optimizer, 0, 21.68, complete=False)
        self.assertFalse(optimizer._solar_charge_reentry.required)
        decision = self._tick(optimizer, 1, 21.29)
        self.assertTrue(decision.trace_gates["solar_charge_ceiling_owned"])

    def test_genuine_two_kw_morning_cap_does_not_create_normal_charge_hold(self) -> None:
        optimizer = self._optimizer()
        morning = self._tick(optimizer, 0, 21.68, solcast_detailed_source_trusted=False)
        self.assertTrue(morning.morning_slow_charge_active)
        self.assertEqual(2.0, morning.ess_charge_limit)
        self.assertFalse(morning.trace_gates["morning_slow_reentry_arm_candidate"])
        self.assertFalse(optimizer._solar_charge_reentry.required)
        solar = self._tick(optimizer, 1, 21.29)
        self.assertTrue(solar.solar_surplus_policy_active)
        self.assertTrue(solar.trace_gates["solar_charge_ceiling_owned"])
        self.assertEqual(0.0, solar.ess_charge_limit)

    def test_cached_reports_cannot_qualify_even_after_thirty_seconds(self) -> None:
        optimizer = self._optimizer()
        self._tick(optimizer, 0, 21.68)
        self._tick(optimizer, 1, 21.29)
        cached = self._tick(optimizer, 6, 21.29, report_index=1)
        self.assertTrue(cached.solar_surplus_policy_active)
        self.assertFalse(cached.trace_gates["solar_charge_ceiling_owned"])
        self.assertEqual(21.0, cached.ess_charge_limit)
        advancing = self._tick(optimizer, 7, 21.29)
        self.assertTrue(advancing.trace_gates["solar_charge_ceiling_owned"])

    def test_report_span_cannot_replace_monotonic_elapsed_time(self) -> None:
        optimizer = self._optimizer()
        self._tick(optimizer, 0, 21.68)
        self._tick(optimizer, 1, 21.29)
        fast_clock = self._tick(optimizer, 6, 21.29, monotonic_seconds=1007.0)
        self.assertFalse(fast_clock.trace_gates["solar_charge_ceiling_owned"])
        self.assertEqual(21.0, fast_clock.ess_charge_limit)

    def test_source_and_monotonic_gaps_restart_qualification(self) -> None:
        for changes in (
            {"report_index": 0},
            {"monotonic_seconds": 999.0},
            {},
        ):
            with self.subTest(changes=changes):
                optimizer = self._optimizer()
                self._tick(optimizer, 0, 21.68)
                self._tick(optimizer, 1, 21.29)
                # Index12 is a 66-second gap from the first Solar candidate;
                # cached/regressing evidence cannot bridge it either.
                decision = self._tick(optimizer, 12, 21.29, **changes)
                self.assertFalse(decision.trace_gates["solar_charge_ceiling_owned"])
                self.assertEqual(21.0, decision.ess_charge_limit)

    def test_failure_after_admission_closes_without_inventing_another_morning_episode(self) -> None:
        optimizer = self._optimizer()
        self._tick(optimizer, 0, 21.68)
        for index in range(1, 7):
            admitted = self._tick(optimizer, index, 21.29)
        self.assertTrue(admitted.trace_gates["solar_charge_ceiling_owned"])
        failed = self._tick(optimizer, 7, 21.29, load_power_trusted=False)
        self.assertFalse(failed.solar_surplus_policy_active)
        self.assertFalse(failed.trace_gates["solar_charge_ceiling_owned"])
        self.assertEqual(21.0, failed.ess_charge_limit)
        fresh = self._tick(optimizer, 8, 21.29)
        self.assertTrue(fresh.solar_surplus_policy_active)
        # Successful completion retired this handoff latch. A later trust loss
        # must close immediately without creating a new Morning episode.
        self.assertTrue(fresh.trace_gates["solar_charge_ceiling_owned"])
        self.assertEqual(0.0, fresh.ess_charge_limit)

    def test_grid_import_keeps_charge_ownership_and_cannot_arm_morning_handoff(self) -> None:
        optimizer = self._optimizer()
        imported = self._tick(
            optimizer, 0, 21.68, current_price=-0.05, current_price_cents=-5.0,
        )
        self.assertGreater(imported.import_limit, 0.0)
        self.assertEqual("grid_import", imported.trace_values["ess_charge_limit_owner"])
        self.assertFalse(imported.trace_gates["morning_slow_reentry_arm_candidate"])
        self.assertFalse(optimizer._solar_charge_reentry.required)
        solar = self._tick(optimizer, 1, 21.29)
        self.assertTrue(solar.trace_gates["solar_charge_ceiling_owned"])

    def test_medium_cannot_preempt_morning_but_qualified_high_retains_priority(self) -> None:
        for fit, expected_morning in ((0.4, True), (1.1, False)):
            with self.subTest(fit=fit):
                optimizer = self._optimizer(
                    allow_low_medium_export_positive_fit=True,
                    allow_positive_fit_battery_discharging=True,
                    min_export_target_soc=20.0,
                )
                decision = self._tick(
                    optimizer, 0, 21.68, feedin_price=fit, feedin_price_cents=100 * fit,
                )
                self.assertEqual(expected_morning, decision.morning_slow_charge_active)
                self.assertEqual(not expected_morning, decision.trace_values["morning_preempted"])
                self.assertEqual(expected_morning, optimizer._solar_charge_reentry.required)
                if expected_morning:
                    self.assertEqual("none", decision.trace_values["battery_export_owner"])
                    self.assertEqual("morning_slow", decision.trace_values["ess_charge_limit_owner"])
                else:
                    self.assertEqual(BATTERY_EXPORT, decision.export_intent)
                    self.assertEqual("high_price", decision.trace_values["battery_export_owner"])
                    self.assertFalse(decision.trace_gates["morning_slow_reentry_arm_candidate"])

    def test_exact_full_bypasses_charge_hold_but_partial_recovery_needs_fresh_proof(self) -> None:
        optimizer = self._optimizer(morning_slow_charge_until="11:36")
        self._tick(optimizer, 0, 21.68)
        self.assertTrue(optimizer._solar_charge_reentry.required)
        full = self._tick(optimizer, 4, 40.3, battery_soc=100.0)
        self.assertFalse(full.morning_slow_charge_active)
        self.assertEqual(MODE_MAX_SELF, full.ems_mode)
        self.assertEqual(25.0, full.export_limit)
        self.assertEqual("none", full.trace_values["battery_export_owner"])
        self.assertEqual(0.0, full.ess_charge_limit)
        partial = self._tick(optimizer, 5, 21.29)
        self.assertTrue(partial.solar_surplus_policy_active)
        self.assertFalse(partial.trace_gates["solar_charge_ceiling_owned"])
        self.assertEqual(21.0, partial.ess_charge_limit)

    def test_qualified_request_without_completed_application_must_requalify(self) -> None:
        for outcome in (
            _ActuatorApplicationResult(succeeded=True),
            _ActuatorApplicationResult(succeeded=False, error="synthetic apply failure"),
            _ActuatorApplicationResult(
                succeeded=True, transition_pending=True, automatic_transition_pending=True,
            ),
            _ActuatorApplicationResult(
                succeeded=True, automatic_application_completed=True,
                fallback_attempted=True, fallback_succeeded=True,
            ),
        ):
            with self.subTest(outcome=outcome):
                optimizer = self._optimizer()
                self._tick(optimizer, 0, 21.68)
                for index in range(1, 6):
                    self._tick(optimizer, index, 21.29)
                qualified = self._tick(
                    optimizer, 6, 21.29, application_result=outcome,
                )
                self.assertTrue(qualified.trace_gates["solar_charge_ceiling_owned"])
                self.assertTrue(optimizer._solar_charge_reentry.required)
                retry = self._tick(optimizer, 7, 21.29)
                self.assertTrue(retry.solar_surplus_policy_active)
                self.assertFalse(retry.trace_gates["solar_charge_ceiling_owned"])
                self.assertEqual(21.0, retry.ess_charge_limit)

    def test_provider_expiry_during_handoff_cannot_accrue_charge_qualification(self) -> None:
        optimizer = self._optimizer()
        self._tick(optimizer, 0, 21.68)
        self._tick(optimizer, 1, 21.29)
        expiry = self._tick(
            optimizer, 2, 21.29,
            solcast_provider_next_update=datetime.fromtimestamp(
                self.WHEN.timestamp() + 12, timezone.utc,
            ).isoformat(),
        )
        self.assertTrue(expiry.solar_surplus_policy_active)
        self.assertFalse(expiry.trace_gates["solar_provider_authority_trusted"])
        self.assertFalse(expiry.trace_gates["solar_charge_ceiling_owned"])
        self.assertEqual(21.0, expiry.ess_charge_limit)
        for index in range(3, 9):
            decision = self._tick(optimizer, index, 21.29)
            self.assertTrue(decision.trace_gates["solar_provider_authority_trusted"])
            self.assertEqual(index == 8, decision.trace_gates["solar_charge_ceiling_owned"])

    def test_fill_deadline_immediately_restores_normal_charge_during_handoff(self) -> None:
        optimizer = self._optimizer()
        self._tick(optimizer, 0, 21.68)
        self._tick(optimizer, 1, 21.29)
        optimizer.cfg.solar_surplus_fill_deadline_margin_minutes = 480.0
        deadline = self._tick(optimizer, 2, 21.29)
        self.assertTrue(deadline.solar_surplus_policy_active)
        self.assertEqual(25.0, deadline.export_limit)
        self.assertFalse(deadline.trace_gates["solar_charge_ceiling_owned"])
        self.assertEqual("fill_deadline_reached", deadline.trace_values["solar_charge_ceiling_reason"])
        self.assertEqual(21.0, deadline.ess_charge_limit)
