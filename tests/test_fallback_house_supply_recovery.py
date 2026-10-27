"""Fallback house-supply recovery after a failed real battery-export attempt.

The HA reports and races here are scripted State objects. They prove software
permission and write ordering, not physical inverter settlement.
"""

from __future__ import annotations

import unittest

from app.models import BATTERY_EXPORT
from app.optimizer import MODE_CMD_DISCHARGE_PV, MODE_MAX_SELF
import test_cross_policy_fallback_demand_characterization as demand_fixtures


class FallbackHouseSupplyRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        # Composition avoids importing another unittest class into this module
        # and collecting the inherited characterization cases a second time.
        self.case = demand_fixtures.CrossPolicyFallbackDemandTests(methodName="runTest")
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)

    def _run(self, **kwargs):
        cfg, ha, result, before = self.case._run_settled_fallback(
            "off", real_unknown_cost_decision=True, **kwargs,
        )
        decision = self.case.latest_real_decision
        self.assertEqual(BATTERY_EXPORT, decision.export_intent)
        self.assertGreater(decision.export_limit, 0.01)
        self.assertIn(
            ("set_number", cfg.grid_export_limit, decision.export_limit), ha.calls
        )
        self.assertFalse(result.succeeded)
        self.assertTrue(result.fallback_attempted)
        self.assertIn(("set_number", cfg.grid_export_limit, 0.01), before)
        self.assertIn(("select_option", cfg.ems_mode_select, MODE_MAX_SELF), before)
        self.assertFalse(any(
            method == "select_option" and entity == cfg.ems_mode_select
            and value == MODE_CMD_DISCHARGE_PV
            for method, entity, value in ha.calls
        ))
        return cfg, ha, result, decision

    @staticmethod
    def _ess_writes(cfg, ha):
        return [
            value for method, entity, value in ha.calls
            if method == "set_number" and entity == cfg.ess_max_discharging_limit
        ]

    def test_verified_fallback_restores_only_bounded_house_supply(self) -> None:
        cases = (
            ("decision", {"applied_discharge_limit": 7.0}, 7.0),
            ("config", {"optimizer_overrides": {"ess_discharge_limit_value": 9.0}}, 9.0),
            ("entity", {"real_state_overrides": {"ess_discharge_limit_entity_max_kw": 8.0}}, 8.0),
            ("rated", {"real_state_overrides": {"ess_max_discharge_kw": 6.0}}, 6.0),
        )
        for name, options, expected in cases:
            with self.subTest(bound=name):
                cfg, ha, result, decision = self._run(**options)
                requested_at, reported_at = self.case.latest_real_close_proof
                self.assertGreater(reported_at, requested_at)
                self.assertEqual(MODE_MAX_SELF, ha.state_values[cfg.ems_mode_select])
                self.assertEqual(0.01, ha.state_values[cfg.grid_export_limit])
                self.assertEqual(expected, self._ess_writes(cfg, ha)[-1])
                self.assertEqual(expected, ha.state_values[cfg.ess_max_discharging_limit])
                self.assertLessEqual(expected, decision.ess_discharge_limit)
                self.assertTrue(result.fallback_succeeded, result.error)

    def test_applied_decision_clamp_stays_closed(self) -> None:
        # The decision scalar is injected after real economic selection to
        # isolate the recovery bound; this is not a simulated policy owner.
        cfg, ha, result, _ = self._run(applied_discharge_limit=0.01)
        self.assertIn(0.01, self._ess_writes(cfg, ha))
        self.assertTrue(all(value <= 0.011 for value in self._ess_writes(cfg, ha)))
        self.assertEqual(0.01, ha.state_values[cfg.ess_max_discharging_limit])
        self.assertTrue(result.fallback_succeeded, result.error)

    def test_late_export_ems_and_authority_drift_withhold_ess_restore(self) -> None:
        cases = (
            ("export_reopened", {"late_export_reopen": 25.0}),
            ("ems_changed", {"late_ems_change": MODE_CMD_DISCHARGE_PV}),
            ("manual", {"late_takeover": "manual"}),
            ("remote_off", {"late_takeover": "remote_off"}),
        )
        for name, options in cases:
            with self.subTest(drift=name):
                cfg, ha, result, _ = self._run(**options)
                self.assertIn(0.01, self._ess_writes(cfg, ha))
                self.assertTrue(all(value <= 0.011 for value in self._ess_writes(cfg, ha)))
                if name == "export_reopened":
                    self.assertEqual(25.0, ha.state_values[cfg.grid_export_limit])
                elif name == "ems_changed":
                    self.assertEqual(MODE_CMD_DISCHARGE_PV, ha.state_values[cfg.ems_mode_select])
                elif name == "manual":
                    self.assertEqual(cfg.manual_option, ha.state_values[cfg.sigenergy_mode_select])
                else:
                    self.assertEqual("off", ha.state_values[cfg.ha_control_switch])
                self.assertFalse(result.fallback_succeeded)

    def test_equal_close_report_or_unsettled_msc_withholds_restore(self) -> None:
        for name, options in (
            ("equal_close_report", {"close_report_delay_ms": 0}),
            ("unsettled_msc", {"settle_msc": False}),
        ):
            with self.subTest(proof=name):
                cfg, ha, result, _ = self._run(**options)
                self.assertIn(0.01, self._ess_writes(cfg, ha))
                self.assertTrue(all(value <= 0.011 for value in self._ess_writes(cfg, ha)))
                if name == "equal_close_report":
                    requested_at, reported_at = self.case.latest_real_close_proof
                    self.assertEqual(requested_at, reported_at)
                else:
                    self.assertNotEqual(MODE_MAX_SELF, ha.state_values.get(cfg.ems_mode_select))
                self.assertFalse(result.fallback_succeeded)

    def test_failed_ess_restore_keeps_fallback_incomplete(self) -> None:
        cfg, ha, result, _ = self._run(ess_discharge_write_fails=True)
        writes = self._ess_writes(cfg, ha)
        self.assertIn(0.01, writes)
        self.assertTrue(any(value > 0.011 for value in writes))
        self.assertEqual([], ha.outcomes[("set_number", cfg.ess_max_discharging_limit)])
        self.assertEqual(0.01, ha.state_values[cfg.ess_max_discharging_limit])
        self.assertFalse(result.fallback_succeeded)
        self.assertIn("normal Automated ESS discharge capability returned failure", result.error)
