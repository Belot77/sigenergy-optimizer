from __future__ import annotations

import math
import unittest
from unittest.mock import patch

import test_export_value_gate_advisory as advisory_fixture


class BatteryPlanningDiagnosticsTests(unittest.TestCase):
    """Distinguish an impossible planning requirement from a physical charge target."""

    def setUp(self) -> None:
        self.fixture = advisory_fixture.ExportValueGateAdvisoryTests(methodName="runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.addCleanup(self.fixture.tearDown)

    def _advisory(self, required_soc=113.0, **config):
        optimizer = self.fixture._optimizer(**config)
        state = self.fixture._state(load_kw=0.0, battery_soc=100.0, battery_capacity_kwh=30.0)
        payload = self.fixture._advisory(
            optimizer, state, desired_export_limit=25.0,
            sunrise_soc_target=required_soc, soc_required=required_soc,
        )
        return optimizer, state, payload

    def test_above_capacity_requirement_explains_shortfall_without_lowering_reserve(self) -> None:
        _, _, payload = self._advisory()
        self.assertEqual(113.0, payload["protected_reserve_soc"])
        self.assertEqual(0.0, payload["export_surplus_soc"])
        self.assertTrue(payload["export_value_gate_would_block"])
        self.assertEqual("protected_reserve", payload["export_value_gate_block_reason"])
        self.assertTrue(payload["reserve_planning_exceeds_full_capacity"])
        self.assertAlmostEqual(33.9, payload["reserve_planning_required_kwh"])
        self.assertAlmostEqual(3.9, payload["reserve_planning_full_capacity_shortfall_kwh"])
        self.assertIn("not a charge target", payload["export_value_gate_reason"])
        self.assertIn("3.90 kWh", payload["export_value_gate_reason"])

    def test_exact_capacity_is_not_reported_as_a_shortfall(self) -> None:
        _, _, payload = self._advisory(100.0)
        self.assertFalse(payload["reserve_planning_exceeds_full_capacity"])
        self.assertEqual(0.0, payload["reserve_planning_full_capacity_shortfall_kwh"])
        self.assertEqual("within_nominal_capacity", payload["reserve_planning_reason"])
        self.assertEqual(100.0, payload["protected_reserve_soc"])
        self.assertNotIn("not a charge target", payload["export_value_gate_reason"])

    def test_below_capacity_requirement_retains_ordinary_advisory_result(self) -> None:
        _, _, payload = self._advisory(35.0)
        self.assertEqual(35.0, payload["protected_reserve_soc"])
        self.assertEqual(65.0, payload["export_surplus_soc"])
        self.assertFalse(payload["reserve_planning_exceeds_full_capacity"])
        self.assertEqual(0.0, payload["reserve_planning_full_capacity_shortfall_kwh"])
        self.assertAlmostEqual(10.5, payload["reserve_planning_required_kwh"])

    def test_disabled_advisory_reports_planning_as_not_evaluated(self) -> None:
        _, _, payload = self._advisory(export_value_gate_enabled=False, export_value_gate_dry_run=False)
        self.assertEqual("not_evaluated", payload["reserve_planning_reason"])
        self.assertIsNone(payload["reserve_planning_required_kwh"])
        self.assertIsNone(payload["reserve_planning_exceeds_full_capacity"])
        self.assertIsNone(payload["reserve_planning_full_capacity_shortfall_kwh"])
        self.assertEqual("Value gate disabled.", payload["export_value_gate_reason"])

    def test_unknown_capacity_never_becomes_a_fabricated_shortfall_estimate(self) -> None:
        optimizer, state, _ = self._advisory()
        for capacity in (None, 0.0, -1.0, math.nan, math.inf, True):
            with self.subTest(capacity=capacity):
                state.battery_capacity_kwh = capacity
                payload = optimizer._reserve_planning_diagnostics(state, 113.0)
                self.assertEqual("capacity_unavailable", payload["reserve_planning_reason"])
                self.assertIsNone(payload["reserve_planning_required_kwh"])
                self.assertIsNone(payload["reserve_planning_full_capacity_shortfall_kwh"])

    def test_invalid_requirement_and_overflow_remain_explicitly_unavailable(self) -> None:
        optimizer, state, _ = self._advisory()
        for required in (True, -1.0, math.nan, math.inf, "unavailable"):
            with self.subTest(required=required):
                payload = optimizer._reserve_planning_diagnostics(state, required)
                self.assertEqual("requirement_unavailable", payload["reserve_planning_reason"])
                self.assertIsNone(payload["reserve_planning_exceeds_full_capacity"])
                self.assertIsNone(payload["reserve_planning_required_kwh"])
        state.battery_capacity_kwh = 1e308
        payload = optimizer._reserve_planning_diagnostics(state, 1e308)
        self.assertEqual("projection_out_of_range", payload["reserve_planning_reason"])
        self.assertIsNone(payload["reserve_planning_required_kwh"])
        self.assertIsNone(payload["reserve_planning_full_capacity_shortfall_kwh"])

    def test_decision_trace_carries_projection_without_changing_actuator_outputs(self) -> None:
        optimizer = self.fixture._optimizer()
        state = self.fixture._state(
            battery_soc=100.0, battery_capacity_kwh=30.0, load_kw=0.0,
            sigenergy_mode=optimizer.cfg.automated_option, sigenergy_mode_observed=True,
        )
        with patch.object(optimizer, "_battery_soc_required_to_sunrise", return_value=113.0):
            decision = optimizer._decide(state)
        self.assertEqual(113.0, decision.min_soc_to_sunrise)
        self.assertEqual(113.0, decision.trace_values["soc_required"])
        self.assertTrue(decision.trace_values["reserve_planning_exceeds_full_capacity"])
        self.assertAlmostEqual(3.9, decision.trace_values["reserve_planning_full_capacity_shortfall_kwh"])
        # Suppressing passive diagnostic payloads must preserve every actuator target.
        with patch.object(optimizer, "_battery_soc_required_to_sunrise", return_value=113.0), patch.object(
            optimizer, "_reserve_planning_diagnostics", return_value={},
        ):
            without_diagnostics = optimizer._decide(state)
        for field in ("ems_mode", "export_limit", "import_limit", "pv_max_power_limit", "ess_charge_limit", "ess_discharge_limit"):
            with self.subTest(actuator=field):
                self.assertEqual(getattr(decision, field), getattr(without_diagnostics, field))
