from __future__ import annotations

import unittest
from importlib import import_module

from app.models import MSC_SURPLUS_CEILING


class SolarExportChargeAllocationHandoffTests(unittest.TestCase):
    """Synthetic real-decision sequence with assumed completion-hook results.

    The fixture calls the real decision and completion hook using an assumed
    completed automatic result. It never calls _apply or simulates hardware.
    """

    def setUp(self) -> None:
        fixture_type = import_module(
            "test_morning_solar_charge_handoff_characterization",
        ).MorningSolarChargeHandoffCharacterizationTests
        self.fixture = fixture_type()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)

    def test_stale_reports_hold_normal_charge_until_both_sources_advance(self) -> None:
        optimizer = self.fixture._optimizer()

        # The fixture's typed completed-result assumption arms the real guard.
        morning = self.fixture._tick(optimizer, 0, 21.68)
        self.assertTrue(morning.morning_slow_charge_active)
        self.assertTrue(optimizer._solar_charge_reentry.required)

        # Solar eligibility remains true while both report streams repeat their
        # first timestamp. Local time advances, but charge qualification waits.
        decisions = [
            self.fixture._tick(optimizer, index, 21.29, report_index=1)
            for index in range(1, 6)
        ]
        self.assertTrue(optimizer._solar_charge_reentry.required)

        # At this endpoint both source timestamps span 30 seconds from the
        # held report and monotonic time spans 30 seconds from the first Solar
        # candidate, so the current qualification contract can admit Solar now.
        qualified = self.fixture._tick(optimizer, 6, 21.29)
        decisions.append(qualified)

        for index, decision in enumerate(decisions, start=1):
            with self.subTest(tick=index):
                self.assertTrue(decision.solar_surplus_policy_active)
                self.assertEqual(MSC_SURPLUS_CEILING, decision.export_intent)
                self.assertEqual(25.0, decision.export_limit)
                self.assertEqual(25.0, decision.pv_max_power_limit)
                self.assertEqual("none", decision.trace_values["battery_export_owner"])
                if index < 6:
                    self.assertFalse(decision.trace_gates["solar_charge_ceiling_owned"])
                    self.assertEqual("morning_handoff_qualifying", decision.trace_values[
                        "solar_charge_ceiling_reason"
                    ])
                    self.assertEqual(21.0, decision.ess_charge_limit)

        self.assertTrue(qualified.solar_surplus_policy_active)
        self.assertTrue(qualified.trace_gates["solar_charge_ceiling_owned"])
        self.assertFalse(optimizer._solar_charge_reentry.required)
        self.assertEqual(3.46, qualified.ess_charge_limit)
        # This fixture uses unchanged readback values; it has not applied the
        # final decision to or observed settlement from an inverter.
        self.assertEqual(21.0, self.fixture._fixture_state.current_ess_charge_limit)
        self.assertEqual([], optimizer.ha.calls)
