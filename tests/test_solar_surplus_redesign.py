from __future__ import annotations

import asyncio
import math
import unittest
from datetime import datetime, timedelta, timezone

from app.models import BATTERY_EXPORT, MSC_SURPLUS_CEILING, Decision
from app.optimizer import (
    DISCHARGE_MODES,
    MODE_MAX_SELF,
    _solar_surplus_energy_budget,
    _solar_surplus_timing_budget,
)
from haos49_characterization_helpers import Haos49CharacterizationCase


class SolarSurplusEnergyBudgetTests(unittest.TestCase):
    @staticmethod
    def _budget(**overrides: float) -> dict[str, float | bool]:
        inputs = {
            "remaining_forecast_kwh": 35.0,
            "current_load_kw": 2.0,
            "hours_to_sunset": 4.0,
            "rated_capacity_kwh": 40.0,
            "battery_soc_pct": 50.0,
            "safety_factor": 1.20,
        }
        inputs.update(overrides)
        return _solar_surplus_energy_budget(**inputs)

    def test_typical_passing_budget_has_expected_arithmetic(self) -> None:
        result = self._budget()

        self.assertEqual(35.0, result["remaining_forecast_kwh"])
        self.assertEqual(8.0, result["remaining_load_kwh"])
        self.assertEqual(20.0, result["fill_need_kwh"])
        self.assertEqual(28.0, result["required_energy_kwh"])
        self.assertAlmostEqual(33.6, result["protected_requirement_kwh"])
        self.assertAlmostEqual(1.4, result["raw_exportable_kwh"])
        self.assertAlmostEqual(1.4, result["exportable_kwh"])
        self.assertIs(True, result["budget_passed"])

    def test_typical_failing_budget_clamps_only_diagnostic_exportable(self) -> None:
        result = self._budget(remaining_forecast_kwh=30.0)

        self.assertAlmostEqual(-3.6, result["raw_exportable_kwh"])
        self.assertEqual(0.0, result["exportable_kwh"])
        self.assertIs(False, result["budget_passed"])

    def test_exact_zero_raw_exportable_fails_strict_gate(self) -> None:
        result = self._budget(remaining_forecast_kwh=33.6)

        self.assertAlmostEqual(0.0, result["raw_exportable_kwh"])
        self.assertEqual(0.0, result["exportable_kwh"])
        self.assertIs(False, result["budget_passed"])

    def test_decimal_equality_cannot_become_a_tiny_positive_float(self) -> None:
        result = self._budget(
            remaining_forecast_kwh=7.2,
            current_load_kw=1.0,
            hours_to_sunset=4.0,
            rated_capacity_kwh=10.0,
            battery_soc_pct=80.0,
        )

        self.assertEqual(0.0, result["raw_exportable_kwh"])
        self.assertEqual(0.0, result["exportable_kwh"])
        self.assertIs(False, result["budget_passed"])

    def test_zero_forecast_is_valid_but_does_not_pass(self) -> None:
        result = self._budget(remaining_forecast_kwh=0.0)

        self.assertEqual(0.0, result["remaining_forecast_kwh"])
        self.assertAlmostEqual(-33.6, result["raw_exportable_kwh"])
        self.assertIs(False, result["budget_passed"])

    def test_zero_load_is_valid(self) -> None:
        result = self._budget(current_load_kw=0.0, remaining_forecast_kwh=25.0)

        self.assertEqual(0.0, result["remaining_load_kwh"])
        self.assertEqual(20.0, result["fill_need_kwh"])
        self.assertEqual(24.0, result["protected_requirement_kwh"])
        self.assertEqual(1.0, result["raw_exportable_kwh"])
        self.assertIs(True, result["budget_passed"])

    def test_full_soc_produces_zero_fill_need(self) -> None:
        result = self._budget(battery_soc_pct=100.0)

        self.assertEqual(0.0, result["fill_need_kwh"])
        self.assertEqual(8.0, result["required_energy_kwh"])

    def test_zero_soc_produces_full_capacity_fill_need(self) -> None:
        result = self._budget(battery_soc_pct=0.0, remaining_forecast_kwh=60.0)

        self.assertEqual(40.0, result["fill_need_kwh"])
        self.assertEqual(48.0, result["required_energy_kwh"])

    def test_negative_forecast_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "remaining_forecast_kwh"):
            self._budget(remaining_forecast_kwh=-0.01)

    def test_negative_load_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "current_load_kw"):
            self._budget(current_load_kw=-0.01)

    def test_negative_hours_to_sunset_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "hours_to_sunset"):
            self._budget(hours_to_sunset=-0.01)

    def test_nonpositive_capacity_is_rejected(self) -> None:
        for value in (0.0, -1.0):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "rated_capacity_kwh"):
                    self._budget(rated_capacity_kwh=value)

    def test_soc_below_zero_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "battery_soc_pct"):
            self._budget(battery_soc_pct=-0.01)

    def test_soc_above_one_hundred_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "battery_soc_pct"):
            self._budget(battery_soc_pct=100.01)

    def test_safety_factor_below_one_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "safety_factor"):
            self._budget(safety_factor=0.99)

    def test_nonfinite_values_are_rejected_for_every_energy_input(self) -> None:
        keys = (
            "remaining_forecast_kwh",
            "current_load_kw",
            "hours_to_sunset",
            "rated_capacity_kwh",
            "battery_soc_pct",
            "safety_factor",
        )
        for key in keys:
            for value in (math.nan, math.inf, -math.inf):
                with self.subTest(key=key, value=value):
                    with self.assertRaisesRegex(ValueError, key):
                        self._budget(**{key: value})

    def test_non_numeric_and_boolean_values_are_rejected(self) -> None:
        for value in ("35", True):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "remaining_forecast_kwh"):
                    _solar_surplus_energy_budget(
                        remaining_forecast_kwh=value,  # type: ignore[arg-type]
                        current_load_kw=2.0,
                        hours_to_sunset=4.0,
                        rated_capacity_kwh=40.0,
                        battery_soc_pct=50.0,
                        safety_factor=1.20,
                    )

    def test_safety_factor_one_uses_requirement_as_is(self) -> None:
        result = self._budget(safety_factor=1.0, remaining_forecast_kwh=29.0)

        self.assertEqual(28.0, result["protected_requirement_kwh"])
        self.assertEqual(1.0, result["raw_exportable_kwh"])
        self.assertIs(True, result["budget_passed"])

    def test_safety_factor_1_20_increases_requirement_by_twenty_percent(self) -> None:
        unprotected = self._budget(safety_factor=1.0)
        protected = self._budget(safety_factor=1.20)

        self.assertEqual(28.0, unprotected["protected_requirement_kwh"])
        self.assertAlmostEqual(33.6, protected["protected_requirement_kwh"])
        self.assertAlmostEqual(
            float(unprotected["protected_requirement_kwh"]) * 1.20,
            protected["protected_requirement_kwh"],
        )

    def test_larger_finite_safety_factor_is_accepted_and_more_conservative(self) -> None:
        baseline = self._budget(safety_factor=1.20)
        conservative = self._budget(safety_factor=2.0)

        self.assertAlmostEqual(33.6, baseline["protected_requirement_kwh"])
        self.assertEqual(56.0, conservative["protected_requirement_kwh"])
        self.assertIs(True, baseline["budget_passed"])
        self.assertIs(False, conservative["budget_passed"])


class SolarSurplusTimingBudgetTests(unittest.TestCase):
    NOW = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)

    @classmethod
    def _ts(cls, hours: float) -> float:
        return (cls.NOW + timedelta(hours=hours)).timestamp()

    @classmethod
    def _timing(
        cls,
        periods: list[tuple[float, float]] | None = None,
        **overrides: float,
    ) -> dict[str, float | bool]:
        inputs = {
            "forecast_period_hours": 1.0,
            "now_ts": cls._ts(0.0),
            "sunset_ts": cls._ts(2.0),
            "current_load_kw": 2.0,
            "charge_capability_kw": 4.0,
            "fill_need_kwh": 6.0,
            "safety_factor": 1.20,
        }
        inputs.update(overrides)
        return _solar_surplus_timing_budget(
            periods
            if periods is not None
            else [(cls._ts(0.0), 6.0), (cls._ts(1.0), 6.0)],
            **inputs,
        )

    def test_enough_timed_charge_opportunity_passes(self) -> None:
        result = self._timing()

        self.assertEqual(8.0, result["timed_charge_opportunity_kwh"])
        self.assertAlmostEqual(
            8.0 / 1.20,
            result["safe_timed_charge_opportunity_kwh"],
        )
        self.assertIs(True, result["timing_passed"])

    def test_insufficient_timed_charge_opportunity_fails(self) -> None:
        result = self._timing(fill_need_kwh=7.0)

        self.assertEqual(8.0, result["timed_charge_opportunity_kwh"])
        self.assertIs(False, result["timing_passed"])

    def test_zero_fill_need_passes_without_detailed_periods(self) -> None:
        result = self._timing(
            periods=[],
            fill_need_kwh=0.0,
            now_ts=self._ts(2.0),
            sunset_ts=self._ts(1.0),
        )

        self.assertEqual(0.0, result["timed_charge_opportunity_kwh"])
        self.assertEqual(0.0, result["safe_timed_charge_opportunity_kwh"])
        self.assertIs(True, result["timing_passed"])

    def test_current_partial_period_uses_actual_overlap(self) -> None:
        result = self._timing(
            periods=[(self._ts(-0.5), 4.0)],
            current_load_kw=0.0,
            charge_capability_kw=10.0,
            fill_need_kwh=1.0,
            safety_factor=1.0,
            sunset_ts=self._ts(1.0),
        )

        self.assertEqual(2.0, result["timed_charge_opportunity_kwh"])

    def test_final_partial_period_before_sunset_uses_actual_overlap(self) -> None:
        result = self._timing(
            periods=[(self._ts(0.5), 4.0)],
            current_load_kw=0.0,
            charge_capability_kw=10.0,
            fill_need_kwh=1.0,
            safety_factor=1.0,
            sunset_ts=self._ts(1.0),
        )

        self.assertEqual(2.0, result["timed_charge_opportunity_kwh"])

    def test_forecast_after_sunset_does_not_count(self) -> None:
        result = self._timing(
            periods=[(self._ts(1.0), 100.0)],
            current_load_kw=0.0,
            charge_capability_kw=100.0,
            fill_need_kwh=1.0,
            safety_factor=1.0,
            sunset_ts=self._ts(1.0),
        )

        self.assertEqual(0.0, result["timed_charge_opportunity_kwh"])
        self.assertIs(False, result["timing_passed"])

    def test_high_pv_is_capped_by_charge_capability(self) -> None:
        result = self._timing(
            periods=[(self._ts(0.0), 100.0)],
            current_load_kw=0.0,
            charge_capability_kw=5.0,
            fill_need_kwh=5.0,
            safety_factor=1.0,
            sunset_ts=self._ts(1.0),
        )

        self.assertEqual(5.0, result["timed_charge_opportunity_kwh"])
        self.assertIs(True, result["timing_passed"])

    def test_site_load_is_deducted_before_charging_opportunity(self) -> None:
        result = self._timing(
            periods=[(self._ts(0.0), 6.0)],
            current_load_kw=2.0,
            charge_capability_kw=10.0,
            fill_need_kwh=4.0,
            safety_factor=1.0,
            sunset_ts=self._ts(1.0),
        )

        self.assertEqual(4.0, result["timed_charge_opportunity_kwh"])
        self.assertIs(True, result["timing_passed"])

    def test_pv_at_or_below_load_contributes_zero(self) -> None:
        for pv_kw in (1.0, 2.0):
            with self.subTest(pv_kw=pv_kw):
                result = self._timing(
                    periods=[(self._ts(0.0), pv_kw)],
                    current_load_kw=2.0,
                    fill_need_kwh=1.0,
                    safety_factor=1.0,
                    sunset_ts=self._ts(1.0),
                )
                self.assertEqual(0.0, result["timed_charge_opportunity_kwh"])
                self.assertIs(False, result["timing_passed"])

    def test_safety_factor_1_20_discounts_timed_opportunity(self) -> None:
        result = self._timing(
            periods=[(self._ts(0.0), 12.0)],
            current_load_kw=0.0,
            charge_capability_kw=12.0,
            fill_need_kwh=9.0,
            safety_factor=1.20,
            sunset_ts=self._ts(1.0),
        )

        self.assertEqual(12.0, result["timed_charge_opportunity_kwh"])
        self.assertEqual(10.0, result["safe_timed_charge_opportunity_kwh"])
        self.assertIs(True, result["timing_passed"])

    def test_exact_safe_timing_equality_passes(self) -> None:
        result = self._timing(
            periods=[(self._ts(0.0), 12.0)],
            current_load_kw=0.0,
            charge_capability_kw=12.0,
            fill_need_kwh=10.0,
            safety_factor=1.20,
            sunset_ts=self._ts(1.0),
        )

        self.assertEqual(10.0, result["safe_timed_charge_opportunity_kwh"])
        self.assertIs(True, result["timing_passed"])

    def test_negative_pv_period_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "pv_kw"):
            self._timing(periods=[(self._ts(0.0), -0.01)])

    def test_nonfinite_pv_period_is_rejected(self) -> None:
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "pv_kw"):
                    self._timing(periods=[(self._ts(0.0), value)])

    def test_invalid_load_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "current_load_kw"):
            self._timing(current_load_kw=-0.01)

    def test_invalid_charge_capability_is_rejected(self) -> None:
        for value in (0.0, -0.01):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "charge_capability_kw"):
                    self._timing(charge_capability_kw=value)

    def test_invalid_time_order_fails_unless_fill_need_is_zero(self) -> None:
        for sunset_ts in (self._ts(0.0), self._ts(-1.0)):
            with self.subTest(sunset_ts=sunset_ts):
                with self.assertRaisesRegex(ValueError, "sunset_ts"):
                    self._timing(sunset_ts=sunset_ts)

        zero_fill = self._timing(
            periods=[],
            fill_need_kwh=0.0,
            sunset_ts=self._ts(-1.0),
        )
        self.assertIs(True, zero_fill["timing_passed"])

    def test_timing_model_has_no_aggregate_forecast_term(self) -> None:
        low_forecast = SolarSurplusEnergyBudgetTests._budget(
            remaining_forecast_kwh=0.0
        )
        high_forecast = SolarSurplusEnergyBudgetTests._budget(
            remaining_forecast_kwh=100.0
        )
        timing = self._timing()

        self.assertNotEqual(low_forecast["budget_passed"], high_forecast["budget_passed"])
        self.assertNotIn("remaining_forecast_kwh", timing)
        self.assertEqual(8.0, timing["timed_charge_opportunity_kwh"])

    def test_irregular_partial_overlap_arithmetic_is_exact(self) -> None:
        result = self._timing(
            periods=[
                (self._ts(-1.0 / 6.0), 6.0),
                (self._ts(1.0 / 3.0), 6.0),
                (self._ts(5.0 / 6.0), 6.0),
            ],
            forecast_period_hours=0.5,
            current_load_kw=2.0,
            charge_capability_kw=4.0,
            fill_need_kwh=3.0,
            safety_factor=1.0,
            sunset_ts=self._ts(13.0 / 12.0),
        )

        expected_kwh = 4.0 * (1.0 / 3.0 + 0.5 + 0.25)
        self.assertAlmostEqual(expected_kwh, result["timed_charge_opportunity_kwh"])
        self.assertAlmostEqual(expected_kwh, result["safe_timed_charge_opportunity_kwh"])
        self.assertIs(True, result["timing_passed"])

    def test_nonfinite_values_are_rejected_for_every_timing_input(self) -> None:
        keys = (
            "forecast_period_hours",
            "now_ts",
            "sunset_ts",
            "current_load_kw",
            "charge_capability_kw",
            "fill_need_kwh",
            "safety_factor",
        )
        for key in keys:
            for value in (math.nan, math.inf, -math.inf):
                with self.subTest(key=key, value=value):
                    with self.assertRaisesRegex(ValueError, key):
                        self._timing(**{key: value})

    def test_nonfinite_period_start_is_rejected(self) -> None:
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "period_start_ts"):
                    self._timing(periods=[(value, 6.0)])


class SolarSurplusControlWiringTests(Haos49CharacterizationCase):
    WHEN = datetime(2026, 1, 15, 14, 0, 0)

    def _optimizer(self, **overrides: object):
        values: dict[str, object] = {
            "solar_surplus_bypass_enabled": True,
            "solar_surplus_forecast_safety_factor": 1.20,
            "battery_full_safeguard_enabled": False,
            "morning_dump_enabled": False,
            "morning_slow_charge_enabled": False,
            "evening_boost_enabled": False,
            "standby_holdoff_enabled": False,
            "allow_low_medium_export_positive_fit": False,
            "export_value_gate_enabled": False,
            "export_value_gate_dry_run": False,
            "export_value_gate_enforce": False,
            "export_limit_high": 25.0,
            "pv_max_power_normal": 25.0,
        }
        values.update(overrides)
        return self.optimizer(**values)

    def _detailed_forecast(
        self,
        pv_kw: float = 5.0,
        *,
        when: datetime | None = None,
    ) -> list[dict[str, object]]:
        anchor = when or self.WHEN
        period_hours = 0.5
        return [
            {
                "period_start": datetime.fromtimestamp(
                    (anchor + timedelta(hours=index * period_hours)).timestamp(),
                    tz=timezone.utc,
                ).isoformat(),
                "pv_estimate": pv_kw,
            }
            for index in range(8)
        ]

    def _state(self, *, when: datetime | None = None, **overrides: object):
        at = when or self.WHEN
        values: dict[str, object] = {
            "sigenergy_mode": "Automated",
            "sigenergy_mode_observed": True,
            "current_ems_mode": MODE_MAX_SELF,
            "ems_mode_observed": True,
            "battery_soc": 80.0,
            "battery_soc_trusted": True,
            "battery_capacity_kwh": 10.0,
            "battery_capacity_trusted": True,
            "available_discharge_energy_kwh": 8.0,
            "available_discharge_energy_trusted": True,
            "battery_power_sensor_kw": 0.0,
            "pv_kw": 2.0,
            "pv_power_trusted": True,
            "load_kw": 1.0,
            "load_power_trusted": True,
            "pv_load_observations_coherent": True,
            "solar_power_now_kw": 2.0,
            "feedin_price": 0.01,
            "feedin_price_cents": 1.0,
            "forecast_remaining_kwh": 20.0,
            "forecast_remaining_observation_trusted": True,
            "forecast_today_kwh": 20.0,
            "forecast_today_observation_trusted": True,
            "forecast_tomorrow_kwh": 30.0,
            "forecast_tomorrow_observation_trusted": True,
            "sun_above_horizon": True,
            "sun_state_observation_trusted": True,
            "next_sunset_ts": (at + timedelta(hours=4.0)).timestamp(),
            "sunset_observation_trusted": True,
            "hours_to_sunset": 4.0,
            "solcast_detailed": self._detailed_forecast(when=at),
            "solcast_detailed_source_trusted": True,
            "ess_max_charge_kw": 5.0,
            "ess_max_discharge_kw": 25.0,
            "grid_export_limit_entity_max_kw": 25.0,
            "grid_import_power_kw": 0.0,
            "grid_export_power_kw": 0.0,
            "current_export_limit": 0.01,
            "current_export_limit_observed": True,
            "current_import_limit": 0.01,
            "current_import_limit_observed": True,
            "current_pv_max_power_limit": 25.0,
            "current_ess_charge_limit": 25.0,
            "current_ess_discharge_limit": 25.0,
            "demand_window_observed": True,
        }
        values.update(overrides)
        return self.state(at, **values)

    def _decide(
        self,
        optimizer,
        *,
        when: datetime | None = None,
        **state_overrides: object,
    ) -> Decision:
        at = when or self.WHEN
        return self.decide(optimizer, self._state(when=at, **state_overrides), at)

    def test_exact_one_cent_strong_budget_and_surplus_enters_as_final_solar_owner(self) -> None:
        optimizer = self._optimizer()

        decision = self._decide(optimizer)

        self.assertTrue(decision.solar_surplus_bypass)
        self.assertTrue(decision.solar_surplus_policy_active)
        self.assertEqual(MSC_SURPLUS_CEILING, decision.export_intent)
        self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
        self.assertNotIn(decision.ems_mode, DISCHARGE_MODES)
        self.assertEqual("none", decision.trace_values["battery_export_owner"])
        self.assertEqual(25.0, decision.export_limit)
        self.assertEqual(25.0, decision.pv_max_power_limit)
        self.assertEqual(5.0, decision.ess_charge_limit)

    def test_below_one_cent_blocks_solar(self) -> None:
        decision = self._decide(
            self._optimizer(),
            feedin_price=0.0099,
            feedin_price_cents=0.99,
        )

        self.assertFalse(decision.solar_surplus_bypass)
        self.assertFalse(decision.solar_surplus_policy_active)
        self.assertFalse(decision.trace_gates["solar_fit_at_least_one_cent"])

    def test_hysteresis_uses_only_previous_final_solar_owner(self) -> None:
        optimizer = self._optimizer()
        active = self._decide(optimizer)
        optimizer._last_decision = active

        continued = self._decide(optimizer, pv_kw=1.200001, solar_power_now_kw=1.200001)
        optimizer._last_decision = continued
        stopped = self._decide(optimizer, pv_kw=1.2, solar_power_now_kw=1.2)
        optimizer._last_decision = stopped
        cannot_reenter = self._decide(optimizer, pv_kw=1.3, solar_power_now_kw=1.3)

        self.assertTrue(continued.solar_surplus_policy_active)
        self.assertFalse(stopped.solar_surplus_policy_active)
        self.assertFalse(cannot_reenter.solar_surplus_policy_active)
        self.assertEqual(0.2, continued.trace_values["solar_surplus_threshold_kw"])
        self.assertEqual(0.5, cannot_reenter.trace_values["solar_surplus_threshold_kw"])

    def test_inactive_mid_band_cannot_enter(self) -> None:
        for measured_surplus_kw in (0.2, 0.3, 0.5):
            with self.subTest(measured_surplus_kw=measured_surplus_kw):
                decision = self._decide(
                    self._optimizer(),
                    pv_kw=1.0 + measured_surplus_kw,
                    solar_power_now_kw=1.0 + measured_surplus_kw,
                )

                self.assertFalse(decision.solar_surplus_policy_active)
                self.assertEqual(
                    0.5,
                    decision.trace_values["solar_surplus_threshold_kw"],
                )

    def test_forecast_update_is_consumed_next_cycle_without_cache(self) -> None:
        optimizer = self._optimizer()
        active = self._decide(optimizer, forecast_remaining_kwh=20.0)
        optimizer._last_decision = active

        deteriorated = self._decide(optimizer, forecast_remaining_kwh=7.2)

        self.assertTrue(active.solar_surplus_policy_active)
        self.assertFalse(deteriorated.solar_surplus_policy_active)
        self.assertEqual(7.2, deteriorated.trace_values["solar_remaining_forecast_kwh"])
        self.assertLessEqual(
            deteriorated.trace_values["solar_raw_exportable_energy_kwh"],
            0.0,
        )

    def test_legacy_capacity_multipliers_no_longer_change_start_or_continuation(self) -> None:
        low = self._optimizer(
            solar_surplus_start_multiplier=0.01,
            solar_surplus_stop_multiplier=0.01,
        )
        high = self._optimizer(
            solar_surplus_start_multiplier=100.0,
            solar_surplus_stop_multiplier=100.0,
        )

        low_start = self._decide(low)
        high_start = self._decide(high)
        low._last_decision = low_start
        high._last_decision = high_start
        low_continue = self._decide(low, pv_kw=1.3, solar_power_now_kw=1.3)
        high_continue = self._decide(high, pv_kw=1.3, solar_power_now_kw=1.3)

        self.assertTrue(low_start.solar_surplus_policy_active)
        self.assertTrue(high_start.solar_surplus_policy_active)
        self.assertTrue(low_continue.solar_surplus_policy_active)
        self.assertTrue(high_continue.solar_surplus_policy_active)

    def test_configured_safety_factor_changes_only_solar_eligibility(self) -> None:
        baseline = self._decide(
            self._optimizer(solar_surplus_forecast_safety_factor=1.20),
            forecast_remaining_kwh=7.5,
        )
        conservative = self._decide(
            self._optimizer(solar_surplus_forecast_safety_factor=1.30),
            forecast_remaining_kwh=7.5,
        )

        self.assertTrue(baseline.solar_surplus_policy_active)
        self.assertFalse(conservative.solar_surplus_policy_active)
        self.assertEqual(baseline.import_limit, conservative.import_limit)
        self.assertEqual(baseline.pv_max_power_limit, conservative.pv_max_power_limit)
        self.assertEqual(baseline.ess_charge_limit, conservative.ess_charge_limit)
        self.assertEqual(baseline.ess_discharge_limit, conservative.ess_discharge_limit)

    def test_aggregate_forecast_must_be_trusted_nonnegative_and_positive_enough(self) -> None:
        cases = (
            ({"forecast_remaining_observation_trusted": False}, "stale"),
            ({"forecast_remaining_kwh": -1.0}, "negative"),
            ({"forecast_remaining_kwh": 0.0}, "zero"),
        )
        for overrides, label in cases:
            with self.subTest(label=label):
                decision = self._decide(self._optimizer(), **overrides)
                self.assertFalse(decision.solar_surplus_policy_active)

    def test_soc_and_rated_capacity_trust_are_mandatory(self) -> None:
        untrusted_soc = self._decide(self._optimizer(), battery_soc_trusted=False)
        fallback_capacity = self._decide(
            self._optimizer(),
            battery_capacity_kwh=10.0,
            battery_capacity_trusted=False,
        )

        self.assertFalse(untrusted_soc.solar_surplus_policy_active)
        self.assertFalse(fallback_capacity.solar_surplus_policy_active)

    def test_full_soc_does_not_require_detailed_timing(self) -> None:
        decision = self._decide(
            self._optimizer(),
            battery_soc=100.0,
            available_discharge_energy_kwh=10.0,
            solcast_detailed=[],
            solcast_detailed_source_trusted=False,
        )

        self.assertTrue(decision.solar_surplus_policy_active)
        self.assertEqual(0.0, decision.trace_values["solar_fill_need_to_full_kwh"])
        self.assertFalse(decision.trace_gates["solar_detailed_timing_required"])
        self.assertTrue(decision.trace_gates["solar_timing_passed"])

    def test_sunset_and_detailed_timing_fail_closed_when_required(self) -> None:
        invalid_horizons = (
            {
                "next_sunset_ts": None,
                "sunset_observation_trusted": False,
            },
            {"next_sunset_ts": (self.WHEN - timedelta(hours=1)).timestamp()},
            {"next_sunset_ts": (self.WHEN + timedelta(days=1)).timestamp()},
            {"sun_state_observation_trusted": False},
            {"sun_above_horizon": False},
        )
        for overrides in invalid_horizons:
            with self.subTest(horizon=overrides):
                decision = self._decide(self._optimizer(), **overrides)
                self.assertFalse(decision.solar_surplus_policy_active)

        insufficient = self._decide(
            self._optimizer(),
            solcast_detailed=self._detailed_forecast(pv_kw=1.1),
        )
        gapped = self._detailed_forecast()
        del gapped[2]
        invalid_coverage = self._decide(
            self._optimizer(),
            solcast_detailed=gapped,
        )
        truncated = self._decide(
            self._optimizer(),
            solcast_detailed=self._detailed_forecast()[:-1],
        )
        untrusted_detailed = self._decide(
            self._optimizer(),
            solcast_detailed_source_trusted=False,
        )

        self.assertFalse(insufficient.solar_surplus_policy_active)
        self.assertFalse(invalid_coverage.solar_surplus_policy_active)
        self.assertFalse(truncated.solar_surplus_policy_active)
        self.assertFalse(untrusted_detailed.solar_surplus_policy_active)
        self.assertTrue(insufficient.trace_gates["solar_detailed_timing_required"])
        self.assertFalse(insufficient.trace_gates["solar_timing_passed"])

    def test_trusted_effective_charge_capability_bounds_timing(self) -> None:
        decision = self._decide(
            self._optimizer(),
            ess_max_charge_kw=0.5,
            ess_charge_limit_entity_max_kw=0.25,
        )

        self.assertFalse(decision.solar_surplus_policy_active)
        self.assertEqual(0.25, decision.trace_values["solar_trusted_charge_capability_kw"])
        self.assertEqual(1.0, decision.trace_values["solar_timed_charge_opportunity_kwh"])

    def test_timing_capability_uses_trusted_lkg_but_never_generic_fallback(self) -> None:
        optimizer = self._optimizer(ess_limit_fallback_kw=25.0)
        unavailable = self._decide(
            optimizer,
            ess_max_charge_kw=999.0,
            ess_charge_limit_entity_max_kw=None,
        )

        self.assertFalse(unavailable.solar_surplus_policy_active)
        self.assertIsNone(
            unavailable.trace_values["solar_trusted_charge_capability_kw"]
        )
        self.assertEqual(
            "trusted_charge_capability_unavailable",
            unavailable.trace_values["solar_surplus_fail_reason"],
        )

        optimizer._last_hw_charge_cap_kw = 0.25
        trusted_lkg = self._decide(
            optimizer,
            ess_max_charge_kw=999.0,
            ess_charge_limit_entity_max_kw=None,
        )

        self.assertFalse(trusted_lkg.solar_surplus_policy_active)
        self.assertEqual(
            0.25,
            trusted_lkg.trace_values["solar_trusted_charge_capability_kw"],
        )
        self.assertEqual(
            1.0,
            trusted_lkg.trace_values["solar_timed_charge_opportunity_kwh"],
        )

    def test_pv_load_trust_and_coherence_are_mandatory(self) -> None:
        cases = (
            {"pv_power_trusted": False},
            {"load_power_trusted": False},
            {"pv_load_observations_coherent": False},
        )
        for overrides in cases:
            with self.subTest(overrides=overrides):
                decision = self._decide(self._optimizer(), **overrides)
                self.assertFalse(decision.solar_surplus_policy_active)

    def test_unknown_or_material_battery_discharge_removes_solar_only(self) -> None:
        unknown = self._decide(
            self._optimizer(),
            battery_power_sensor_kw=None,
            grid_import_power_kw=None,
            grid_export_power_kw=None,
        )
        discharging = self._decide(
            self._optimizer(),
            battery_power_sensor_kw=-0.100001,
        )

        for decision in (unknown, discharging):
            self.assertTrue(decision.solar_surplus_bypass)
            self.assertFalse(decision.solar_surplus_policy_active)
            self.assertNotEqual(BATTERY_EXPORT, decision.export_intent)
            self.assertEqual("none", decision.trace_values["battery_export_owner"])

    def test_morning_slow_and_deliberate_export_owners_displace_solar(self) -> None:
        morning_slow_optimizer = self._optimizer(
            morning_slow_charge_enabled=True,
            morning_slow_charge_rate_kw=2.0,
        )
        morning_slow_optimizer._morning_slow_charge_active = lambda *args, **kwargs: True
        morning_slow = self._decide(morning_slow_optimizer)

        high_price = self._decide(
            self._optimizer(),
            feedin_price=1.20,
            feedin_price_cents=120.0,
        )

        self.assertTrue(morning_slow.morning_slow_charge_active)
        self.assertFalse(morning_slow.solar_surplus_policy_active)
        self.assertEqual(2.0, morning_slow.ess_charge_limit)
        self.assertFalse(high_price.solar_surplus_policy_active)
        self.assertEqual(BATTERY_EXPORT, high_price.export_intent)
        self.assertEqual("high_price", high_price.trace_values["battery_export_owner"])

    def test_morning_dump_wins_and_exit_requires_full_solar_entry(self) -> None:
        morning = datetime(2026, 1, 15, 6, 0, 0)
        optimizer = self._optimizer(morning_dump_enabled=True)
        optimizer._morning_dump_active = lambda *args, **kwargs: True

        morning_dump = self._decide(optimizer, when=morning)

        self.assertFalse(morning_dump.solar_surplus_policy_active)
        self.assertEqual(BATTERY_EXPORT, morning_dump.export_intent)
        self.assertEqual("morning_dump", morning_dump.trace_values["battery_export_owner"])
        self.assertIn(morning_dump.ems_mode, DISCHARGE_MODES)

        optimizer._last_decision = morning_dump
        optimizer._morning_dump_active = lambda *args, **kwargs: False
        after_dump_mid_band = self._decide(
            optimizer,
            when=morning,
            pv_kw=1.3,
            solar_power_now_kw=1.3,
        )

        self.assertFalse(after_dump_mid_band.solar_surplus_policy_active)
        self.assertEqual(
            0.5,
            after_dump_mid_band.trace_values["solar_surplus_threshold_kw"],
        )

    def test_deliberate_owner_with_same_numeric_ceiling_is_not_solar(self) -> None:
        decision = self._decide(
            self._optimizer(export_limit_high=25.0),
            feedin_price=1.20,
            feedin_price_cents=120.0,
        )

        self.assertEqual(25.0, decision.export_limit)
        self.assertFalse(decision.solar_surplus_policy_active)
        self.assertEqual("high_price_or_spike", decision.trace_values["desired_export_source"])

    def test_manual_freeze_clears_final_solar_ownership(self) -> None:
        optimizer = self._optimizer()
        state = self._state()
        decision = self.decide(optimizer, state, self.WHEN)
        self.assertTrue(decision.solar_surplus_policy_active)

        optimizer._freeze_decision_to_live_mode(
            state,
            decision,
            optimizer.cfg.manual_option,
        )

        self.assertFalse(decision.solar_surplus_policy_active)
        self.assertFalse(decision.trace_gates["solar_surplus_policy_active"])
        self.assertEqual(
            f"operator_mode_user_owned: {optimizer.cfg.manual_option}",
            decision.trace_values["solar_surplus_fail_reason"],
        )

    def test_force_mode_freeze_cannot_seed_solar_continuation(self) -> None:
        optimizer = self._optimizer()
        state = self._state()
        decision = self.decide(optimizer, state, self.WHEN)
        self.assertTrue(decision.solar_surplus_policy_active)

        optimizer._freeze_decision_to_live_mode(
            state,
            decision,
            optimizer.cfg.full_export_option,
        )
        optimizer._last_decision = decision
        next_decision = self._decide(
            optimizer,
            pv_kw=1.3,
            solar_power_now_kw=1.3,
        )

        self.assertFalse(decision.solar_surplus_policy_active)
        self.assertFalse(next_decision.solar_surplus_policy_active)
        self.assertEqual(
            0.5,
            next_decision.trace_values["solar_surplus_threshold_kw"],
        )

    def test_failed_application_cannot_seed_solar_continuation(self) -> None:
        optimizer = self._optimizer()
        prior = Decision()
        optimizer._last_decision = prior
        state = self._state()

        async def read_state():
            return state

        async def fail_apply(_state, _decision):
            raise RuntimeError("expected application failure")

        async def ignore_publish(_result):
            return None

        optimizer._read_state = read_state
        optimizer._apply = fail_apply
        optimizer._publish_hvac_solar_permission = ignore_publish

        with self.optimizer_time(self.WHEN):
            with self.assertRaisesRegex(RuntimeError, "expected application failure"):
                asyncio.run(optimizer._tick())

        self.assertIs(prior, optimizer._last_decision)
        next_decision = self._decide(
            optimizer,
            pv_kw=1.3,
            solar_power_now_kw=1.3,
        )
        self.assertFalse(next_decision.solar_surplus_policy_active)
        self.assertEqual(0.5, next_decision.trace_values["solar_surplus_threshold_kw"])

    def test_trace_contains_energy_timing_and_final_ownership_evidence(self) -> None:
        decision = self._decide(self._optimizer())

        expected_gates = {
            "solar_surplus_enabled",
            "previous_cycle_solar_surplus_policy_owned",
            "solar_fit_at_least_one_cent",
            "solar_energy_budget_passed",
            "solar_detailed_timing_required",
            "solar_timing_passed",
            "solar_surplus_policy_active",
        }
        expected_values = {
            "solar_measured_pv_surplus_kw",
            "solar_surplus_threshold_kw",
            "solar_remaining_forecast_kwh",
            "solar_expected_remaining_load_kwh",
            "solar_fill_need_to_full_kwh",
            "solar_forecast_safety_factor",
            "solar_protected_required_energy_kwh",
            "solar_raw_exportable_energy_kwh",
            "solar_exportable_energy_kwh",
            "solar_timed_charge_opportunity_kwh",
            "solar_safe_timed_charge_opportunity_kwh",
            "solar_surplus_fail_reason",
        }
        self.assertTrue(expected_gates.issubset(decision.trace_gates))
        self.assertTrue(expected_values.issubset(decision.trace_values))


if __name__ == "__main__":
    unittest.main()
