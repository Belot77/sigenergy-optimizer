from __future__ import annotations

import math
import unittest
from datetime import datetime, timedelta, timezone

from app.optimizer import (
    _solar_surplus_energy_budget,
    _solar_surplus_timing_budget,
)


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


if __name__ == "__main__":
    unittest.main()
