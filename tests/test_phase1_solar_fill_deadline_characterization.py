from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch

from app.config import Settings
from app.models import MSC_SURPLUS_CEILING
from app.optimizer import DISCHARGE_MODES, MODE_MAX_SELF
from haos49_characterization_helpers import RecordingHA
from test_phase1_solar_dynamic_charge_ceiling_characterization import (
    SolarDynamicChargeFixture,
)


class SolarFillDeadlineCharacterizationTests(SolarDynamicChargeFixture):
    """Solar fill timing is independent of export policy and Morning Slow."""

    def _optimizer(self, **overrides: object):
        values = {"solar_surplus_fill_deadline_margin_minutes": 60.0}
        values.update(overrides)
        return super()._optimizer(**values)

    def _assert_pv_export_controls(self, decision) -> None:
        self.assertEqual(MSC_SURPLUS_CEILING, decision.export_intent)
        self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
        self.assertNotIn(decision.ems_mode, DISCHARGE_MODES)
        self.assertEqual("none", decision.trace_values["battery_export_owner"])
        self.assertEqual(25.0, decision.export_limit)
        self.assertEqual(25.0, decision.pv_max_power_limit)

    def test_zero_margin_preserves_sunset_trajectory(self) -> None:
        decision = self._decide(
            self._optimizer(solar_surplus_fill_deadline_margin_minutes=0.0),
            forecast_pv_kw=[6.0] + [2.2] * 7,
        )

        self.assertTrue(decision.trace_gates["solar_charge_ceiling_owned"])
        self.assertEqual(1.2, decision.ess_charge_limit)
        self.assertEqual(4.2, decision.trace_values["solar_charge_ceiling_future_opportunity_kwh"])
        self.assertEqual(
            (self.WHEN + timedelta(hours=4)).timestamp(),
            decision.trace_values["solar_charge_ceiling_fill_deadline_ts"],
        )
        self.assertEqual(0.0, decision.trace_values["solar_charge_ceiling_fill_deadline_margin_minutes"])
        self._assert_pv_export_controls(decision)

    def test_default_sixty_minutes_clips_last_hour_without_changing_energy_budget(self) -> None:
        default_margin = Settings.model_fields["solar_surplus_fill_deadline_margin_minutes"].default
        self.assertEqual(60.0, default_margin)
        at_sunset = self._decide(
            self._optimizer(solar_surplus_fill_deadline_margin_minutes=0.0),
            forecast_pv_kw=[6.0] + [2.2] * 7,
        )
        earlier = self._decide(
            self._optimizer(solar_surplus_fill_deadline_margin_minutes=default_margin),
            forecast_pv_kw=[6.0] + [2.2] * 7,
        )

        self.assertTrue(earlier.solar_surplus_policy_active)
        self.assertEqual(3.0, earlier.trace_values["solar_charge_ceiling_future_opportunity_kwh"])
        self.assertEqual(3.6, earlier.ess_charge_limit)
        self.assertEqual(
            (self.WHEN + timedelta(hours=3)).timestamp(),
            earlier.trace_values["solar_charge_ceiling_fill_deadline_ts"],
        )
        self.assertEqual(60.0, earlier.trace_values["solar_charge_ceiling_fill_deadline_margin_minutes"])
        for key in (
            "solar_expected_remaining_load_kwh", "solar_fill_need_to_full_kwh",
            "solar_protected_required_energy_kwh", "solar_timed_charge_opportunity_kwh",
            "solar_hours_to_same_day_sunset", "solar_forecast_safety_factor",
        ):
            with self.subTest(unchanged_energy_evidence=key):
                self.assertEqual(at_sunset.trace_values[key], earlier.trace_values[key])
        self.assertEqual(1.20, earlier.trace_values["solar_forecast_safety_factor"])

    def test_margin_starts_positive_charging_earlier(self) -> None:
        forecast = [6.0] + [2.4] * 7
        no_margin = self._decide(
            self._optimizer(solar_surplus_fill_deadline_margin_minutes=0),
            forecast_pv_kw=forecast,
        )
        margin = self._decide(self._optimizer(), forecast_pv_kw=forecast)

        self.assertEqual(0.0, no_margin.ess_charge_limit)
        self.assertEqual(2.6, margin.ess_charge_limit)
        self.assertTrue(margin.trace_gates["solar_charge_ceiling_owned"])
        self.assertEqual("present_charging_required_for_fill_trajectory", margin.trace_values["solar_charge_ceiling_reason"])
        self._assert_pv_export_controls(margin)

    def test_partial_current_and_final_intervals_use_actual_deadline_overlap(self) -> None:
        when = self.WHEN + timedelta(minutes=15)
        sunset = self.WHEN + timedelta(hours=2, minutes=10)
        decision = self._decide(
            self._optimizer(), when=when,
            solcast_detailed=self._detailed_forecast([6.0] + [3.0] * 7),
            next_sunset_ts=sunset.timestamp(),
            battery_soc=80.0, available_discharge_energy_kwh=8.0,
        )

        self.assertTrue(decision.trace_gates["solar_charge_ceiling_owned"])
        self.assertEqual(0.25, decision.trace_values["solar_charge_ceiling_current_window_hours"])
        self.assertAlmostEqual(4 / 3, decision.trace_values["solar_charge_ceiling_future_opportunity_kwh"])
        self.assertEqual(4.27, decision.ess_charge_limit)
        self.assertEqual((sunset - timedelta(hours=1)).timestamp(), decision.trace_values["solar_charge_ceiling_fill_deadline_ts"])

    def test_deadline_inside_current_interval_clips_its_denominator(self) -> None:
        when = self.WHEN + timedelta(minutes=15)
        sunset = self.WHEN + timedelta(hours=1, minutes=20)
        decision = self._decide(
            self._optimizer(), when=when,
            solcast_detailed=self._detailed_forecast([6.0] * 8),
            next_sunset_ts=sunset.timestamp(),
            battery_soc=97.0, available_discharge_energy_kwh=9.7,
        )

        self.assertTrue(decision.trace_gates["solar_charge_ceiling_owned"])
        self.assertAlmostEqual(5 / 60, decision.trace_values["solar_charge_ceiling_current_window_hours"])
        self.assertEqual(0.0, decision.trace_values["solar_charge_ceiling_future_opportunity_kwh"])
        self.assertEqual(4.32, decision.ess_charge_limit)

    def test_earlier_deadline_never_exceeds_normal_safe_charge_request(self) -> None:
        decision = self._decide(
            self._optimizer(), forecast_pv_kw=[6.0, 5.6] + [1.0] * 6,
        )

        self.assertTrue(decision.trace_gates["solar_charge_ceiling_owned"])
        self.assertEqual(self.NORMAL_CHARGE_KW, decision.ess_charge_limit)
        self.assertLessEqual(decision.ess_charge_limit, decision.trace_values["solar_charge_ceiling_normal_request_kw"])
        self._assert_pv_export_controls(decision)

    def test_reached_deadline_releases_previous_restriction_without_closing_export(self) -> None:
        optimizer = self._optimizer()
        sunset = self.WHEN + timedelta(hours=4)
        before = self._decide(
            optimizer, when=sunset - timedelta(minutes=90),
            forecast_pv_kw=[6.0] * 3,
            battery_soc=80.0, available_discharge_energy_kwh=8.0,
        )
        self.assertEqual(4.8, before.ess_charge_limit)
        self.assertTrue(before.trace_gates["solar_charge_ceiling_owned"])
        optimizer._last_decision = before
        reached = self._decide(
            optimizer, when=sunset - timedelta(hours=1),
            forecast_pv_kw=[6.0] * 2,
            battery_soc=80.0, available_discharge_energy_kwh=8.0,
            current_ess_charge_limit=before.ess_charge_limit,
        )

        self.assertTrue(reached.solar_surplus_policy_active)
        self.assertFalse(reached.trace_gates["solar_charge_ceiling_owned"])
        self.assertEqual(self.NORMAL_CHARGE_KW, reached.ess_charge_limit)
        self.assertEqual("normal", reached.trace_values["ess_charge_limit_owner"])
        self.assertIsNone(reached.trace_values["solar_charge_ceiling_requested_kw"])
        self.assertEqual("fill_deadline_reached", reached.trace_values["solar_charge_ceiling_reason"])
        self._assert_pv_export_controls(reached)

    def test_large_margin_releases_charge_even_when_deadline_is_previous_local_day(self) -> None:
        for minutes in (240.0, 300.0, 1440.0):
            with self.subTest(margin_minutes=minutes):
                decision = self._decide(self._optimizer(solar_surplus_fill_deadline_margin_minutes=minutes))
                self.assertTrue(decision.solar_surplus_policy_active)
                self.assertFalse(decision.trace_gates["solar_charge_ceiling_owned"])
                self.assertEqual(self.NORMAL_CHARGE_KW, decision.ess_charge_limit)
                self.assertEqual("fill_deadline_reached", decision.trace_values["solar_charge_ceiling_reason"])
                self.assertEqual(
                    (self.WHEN + timedelta(hours=4) - timedelta(minutes=minutes)).timestamp(),
                    decision.trace_values["solar_charge_ceiling_fill_deadline_ts"],
                )
                self._assert_pv_export_controls(decision)

    def test_apply_authority_recheck_releases_at_fill_deadline_with_provider_still_valid(self) -> None:
        optimizer = self._optimizer()
        when = self.WHEN + timedelta(hours=2, minutes=59)
        sunset = self.WHEN + timedelta(hours=4)
        state_values = {
            "forecast_pv_kw": [6.0] * 3,
            "next_sunset_ts": sunset.timestamp(),
            "battery_soc": 99.9,
            "available_discharge_energy_kwh": 9.99,
        }
        decision = self._decide(optimizer, when=when, **state_values)
        state = self._state(when=when, **state_values)
        deadline = (sunset - timedelta(hours=1)).timestamp()
        self.assertTrue(decision.trace_gates["solar_charge_ceiling_owned"])
        self.assertEqual(0.72, decision.ess_charge_limit)

        optimizer._recheck_solar_charge_authority(state, decision, deadline - 0.001)
        self.assertTrue(decision.trace_gates["solar_charge_ceiling_owned"])
        optimizer._recheck_solar_charge_authority(state, decision, deadline)

        self.assertTrue(decision.trace_gates["solar_provider_authority_trusted"])
        self.assertFalse(decision.trace_gates["solar_charge_ceiling_owned"])
        self.assertEqual(self.NORMAL_CHARGE_KW, decision.ess_charge_limit)
        self.assertEqual("normal", decision.trace_values["ess_charge_limit_owner"])
        self.assertEqual("fill_deadline_reached_before_apply", decision.trace_values["solar_charge_ceiling_reason"])
        self._assert_pv_export_controls(decision)

    def test_actual_apply_crossing_deadline_restores_normal_in_same_application(self) -> None:
        async def check():
            for crossing in ("before_charge", "during_charge"):
                with self.subTest(crossing=crossing):
                    optimizer = self._optimizer(ess_max_charging_limit="number.test_charge")
                    when = self.WHEN + timedelta(hours=2, minutes=59)
                    sunset = self.WHEN + timedelta(hours=4)
                    state_values = {
                        "forecast_pv_kw": [6.0] * 3,
                        "next_sunset_ts": sunset.timestamp(),
                        "battery_soc": 99.9,
                        "available_discharge_energy_kwh": 9.99,
                    }
                    decision = self._decide(optimizer, when=when, **state_values)
                    state = self._state(when=when, **state_values)
                    state.current_export_limit = decision.export_limit
                    state.current_import_limit = 1.0 if crossing == "before_charge" else 0.01
                    ha = RecordingHA(state_values={optimizer.cfg.ems_mode_select: MODE_MAX_SELF})
                    optimizer.ha = ha
                    clock = [when]
                    deadline = sunset - timedelta(hours=1)
                    original_set_number = ha.set_number

                    class MovingDateTime(datetime):
                        @classmethod
                        def now(cls, tz=None):
                            return cls.fromtimestamp(clock[0].timestamp(), tz)

                    async def cross_deadline(entity, value):
                        result = await original_set_number(entity, value)
                        if (
                            crossing == "before_charge" and entity == optimizer.cfg.grid_import_limit
                            or crossing == "during_charge" and entity == "number.test_charge" and value == 0.72
                        ):
                            clock[0] = deadline
                        return result

                    ha.set_number = cross_deadline
                    with patch("app.optimizer.datetime", MovingDateTime):
                        result = await optimizer._apply(state, decision)

                    self.assertTrue(result.succeeded, result.error)
                    writes = [
                        value for action, entity, value in ha.calls
                        if action == "set_number" and entity == "number.test_charge"
                    ]
                    self.assertEqual([5.0] if crossing == "before_charge" else [0.72, 5.0], writes)
                    self.assertTrue(decision.trace_gates["solar_provider_authority_trusted"])
                    self.assertFalse(decision.trace_gates["solar_charge_ceiling_owned"])
                    self.assertEqual("fill_deadline_reached_before_apply", decision.trace_values["solar_charge_ceiling_reason"])
                    self._assert_pv_export_controls(decision)

        asyncio.run(check())

    def test_finite_margin_with_overflowing_seconds_fails_closed_without_crashing(self) -> None:
        decision = self._decide(self._optimizer(solar_surplus_fill_deadline_margin_minutes=1e308))

        self.assertTrue(decision.solar_surplus_policy_active)
        self.assertFalse(decision.trace_gates["solar_charge_ceiling_owned"])
        self.assertIsNone(decision.trace_values["solar_charge_ceiling_fill_deadline_ts"])
        self.assertEqual(self.NORMAL_CHARGE_KW, decision.ess_charge_limit)
        self.assertEqual("fill_deadline_untrusted_or_invalid", decision.trace_values["solar_charge_ceiling_reason"])
        self._assert_pv_export_controls(decision)

    def test_invalid_runtime_margin_cannot_retain_previous_restriction(self) -> None:
        for value in (float("nan"), float("inf"), float("-inf"), -1.0, True, "invalid"):
            with self.subTest(value=value):
                optimizer = self._optimizer()
                active = self._decide(optimizer)
                self.assertTrue(active.trace_gates["solar_charge_ceiling_owned"])
                optimizer._last_decision = active
                optimizer.cfg.solar_surplus_fill_deadline_margin_minutes = value
                invalid = self._decide(optimizer)
                self.assertTrue(invalid.solar_surplus_policy_active)
                self.assertFalse(invalid.trace_gates["solar_charge_ceiling_owned"])
                self.assertEqual(self.NORMAL_CHARGE_KW, invalid.ess_charge_limit)
                self.assertEqual("fill_deadline_untrusted_or_invalid", invalid.trace_values["solar_charge_ceiling_reason"])
                self._assert_pv_export_controls(invalid)

    def test_filled_battery_keeps_surplus_export_after_deadline_without_detail(self) -> None:
        optimizer = self._optimizer()
        full = self._decide(optimizer, battery_soc=100.0, available_discharge_energy_kwh=10.0)
        self.assertTrue(full.solar_surplus_policy_active)
        optimizer._last_decision = full
        late = self._decide(
            optimizer, when=self.WHEN + timedelta(hours=3, minutes=30),
            forecast_pv_kw=[6.0], battery_soc=100.0,
            available_discharge_energy_kwh=10.0,
            solcast_detailed=[], solcast_detailed_source_trusted=False,
        )

        self.assertTrue(late.solar_surplus_policy_active)
        self.assertFalse(late.trace_gates["solar_detailed_timing_required"])
        self.assertFalse(late.trace_gates["solar_charge_ceiling_owned"])
        self._assert_pv_export_controls(late)

    def test_untrusted_missing_or_other_day_sunset_never_restricts_charge(self) -> None:
        for evidence in (
            {"sunset_observation_trusted": False},
            {"next_sunset_ts": None, "sunset_observation_trusted": False},
            {"next_sunset_ts": (self.WHEN - timedelta(hours=1)).timestamp()},
            {"next_sunset_ts": (self.WHEN + timedelta(days=1)).timestamp()},
            {"sun_state_observation_trusted": False},
            {"sun_above_horizon": False},
        ):
            with self.subTest(evidence=evidence):
                decision = self._decide(self._optimizer(), **evidence)
                self.assertFalse(decision.trace_gates["solar_charge_ceiling_owned"])
                self.assertEqual(self.NORMAL_CHARGE_KW, decision.ess_charge_limit)
                self.assertEqual("none", decision.trace_values["battery_export_owner"])

    def test_next_local_day_sunset_cannot_be_made_valid_by_subtracting_margin(self) -> None:
        optimizer = self._optimizer()
        # The shared legacy fixture accepts host-local naive datetimes. Choose
        # an instant just before midnight in the optimizer's configured zone.
        when = datetime.fromtimestamp(
            datetime(2026, 1, 15, 23, 30, tzinfo=optimizer._tz).timestamp()
        )
        decision = self._decide(
            optimizer, when=when, forecast_pv_kw=[6.0, 6.0],
            battery_soc=90.0, available_discharge_energy_kwh=9.0,
        )

        self.assertFalse(decision.solar_surplus_policy_active)
        self.assertFalse(decision.trace_gates["solar_charge_ceiling_owned"])
        self.assertEqual(self.NORMAL_CHARGE_KW, decision.ess_charge_limit)

    def test_missing_untrusted_or_gapped_detail_cannot_restrict_charging(self) -> None:
        gapped = self._detailed_forecast([6.0] + [3.0] * 7)
        del gapped[2]
        for evidence in (
            {"solcast_detailed": []},
            {"solcast_detailed_source_trusted": False},
            {"solcast_detailed": gapped},
        ):
            with self.subTest(evidence=evidence):
                decision = self._decide(self._optimizer(), **evidence)
                self.assertFalse(decision.trace_gates["solar_charge_ceiling_owned"])
                self.assertEqual(self.NORMAL_CHARGE_KW, decision.ess_charge_limit)

    def test_morning_slow_cutoff_does_not_change_solar_deadline(self) -> None:
        decision = self._decide(self._optimizer(morning_slow_charge_sunset_cutoff=4.0))

        self.assertTrue(decision.trace_gates["solar_charge_ceiling_owned"])
        self.assertEqual((self.WHEN + timedelta(hours=3)).timestamp(), decision.trace_values["solar_charge_ceiling_fill_deadline_ts"])

    def test_morning_slow_remains_owner_with_earlier_solar_deadline(self) -> None:
        optimizer = self._optimizer(morning_slow_charge_enabled=True, morning_slow_charge_rate_kw=2.0)
        optimizer._morning_slow_charge_active = lambda *args, **kwargs: True
        decision = self._decide(optimizer)

        self.assertFalse(decision.solar_surplus_policy_active)
        self.assertFalse(decision.trace_gates["solar_charge_ceiling_owned"])
        self.assertEqual(2.0, decision.ess_charge_limit)
        self.assertEqual("morning_slow", decision.trace_values["ess_charge_limit_owner"])

    def test_manual_and_force_freeze_remove_solar_charge_ownership(self) -> None:
        for mode_key in ("manual_option", "full_export_option", "full_import_option", "full_import_pv_option", "block_flow_option"):
            with self.subTest(mode=mode_key):
                optimizer = self._optimizer()
                state = self._state(current_ess_charge_limit=4.5)
                decision = self._decide(optimizer)
                optimizer._freeze_decision_to_live_mode(state, decision, getattr(optimizer.cfg, mode_key))
                self.assertFalse(decision.solar_surplus_policy_active)
                self.assertFalse(decision.trace_gates["solar_charge_ceiling_owned"])
                self.assertEqual(4.5, decision.ess_charge_limit)

    def test_demand_window_keeps_import_ownership_and_grid_import_keeps_charge_priority(self) -> None:
        for blocked in (False, True):
            with self.subTest(demand_window=blocked):
                decision = self._decide(
                    self._optimizer(), battery_soc=45.0,
                    available_discharge_energy_kwh=4.5,
                    pv_kw=2.0, solar_power_now_kw=2.0,
                    current_price=0.01, current_price_cents=1.0,
                    demand_window_active=blocked, demand_window_observed=True,
                )
                self.assertTrue(decision.solar_surplus_policy_active)
                if blocked:
                    self.assertEqual(0.0, decision.import_limit)
                    self.assertEqual("demand_window_block", decision.trace_values["import_branch"])
                    self.assertTrue(decision.trace_gates["solar_charge_ceiling_owned"])
                else:
                    self.assertEqual(2.0, decision.import_limit)
                    self.assertEqual(2.0, decision.ess_charge_limit)
                    self.assertEqual("grid_import", decision.trace_values["ess_charge_limit_owner"])
                    self.assertFalse(decision.trace_gates["solar_charge_ceiling_owned"])
                self._assert_pv_export_controls(decision)
