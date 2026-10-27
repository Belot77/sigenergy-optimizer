"""Current cross-policy Decision outputs; characterization, not policy endorsement.

In particular, actual negative import price currently coexists with qualified
Morning Dump discharge ownership. The approved future trusted-non-positive
charging priority is not implemented and is intentionally not asserted here.
Exact-zero/high-export-value behavior and PV MAX behavior at non-positive
import price remain unresolved.
"""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from app.config import Settings
from app.optimizer import (
    BATTERY_EXPORT,
    EXPORT_BLOCKED,
    MODE_CMD_CHARGE_GRID,
    MODE_CMD_DISCHARGE_PV,
    MODE_MAX_SELF,
)
from haos49_characterization_helpers import Haos49CharacterizationCase as _Fixture


class CrossPolicyNegativePriceCharacterization(unittest.TestCase):
    """Decision-only cross-policy coverage; does not apply actuators."""

    WHEN = datetime(2026, 1, 15, 6, 0)
    FIXED_AFTERNOON = _Fixture.FIXED_AFTERNOON

    # Reuse fixture mechanics without inheriting its tests (which would cause
    # pytest/unittest to collect those tests again from this module).
    tearDown = _Fixture.tearDown
    optimizer = _Fixture.optimizer
    optimizer_time = staticmethod(_Fixture.optimizer_time)
    state = _Fixture.state
    decide = _Fixture.decide

    def setUp(self) -> None:
        environment = patch.dict(os.environ, {}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        settings = patch(
            "haos49_characterization_helpers.Settings",
            side_effect=lambda **values: Settings(_env_file=None, **values),
        )
        settings.start()
        self.addCleanup(settings.stop)
        # Install the fixture's temporary DB path after environment isolation.
        _Fixture.setUp(self)

    def characterize(
        self, *, current_price: float, actual: bool, fit: float,
        inactive_dump: bool = False,
    ):
        optimizer = self.optimizer(morning_dump_enabled=True, morning_dump_min_soc=15.0)
        state_values = dict(
            battery_soc=15.0 if inactive_dump else 80.0,
            available_discharge_energy_kwh=4.5 if inactive_dump else 24.0,
            demand_window_active=False,
            demand_window_observed=True,
        )
        state = _Fixture.state(
            self.WHEN,
            sun_above_horizon=False,
            battery_soc_trusted=True,
            battery_capacity_trusted=True,
            available_discharge_energy_trusted=True,
            current_price=current_price,
            current_price_cents=current_price * 100.0,
            price_is_negative=current_price < 0.0,
            price_is_actual=actual,
            feedin_price=fit,
            feedin_price_cents=fit * 100.0,
            feedin_is_negative=fit < 0.0,
            load_kw=1.0,
            **state_values,
            solcast_detailed=[
                {
                    "period_start": (self.WHEN + timedelta(hours=hours)).isoformat(),
                    "pv_estimate": 20.0,
                }
                for hours in (3, 5, 7, 9, 11)
            ],
        )
        with patch.object(optimizer, "_optimizer_import_topup_summary_today", return_value={}):
            decision = self.decide(optimizer, state, self.WHEN)
        self.assertEqual([], optimizer.ha.calls)
        return decision

    def test_negative_import_price_and_dump_complete_decision_outputs(self):
        cases = (
            # name, current price, actual?, FiT, active?, intent, EMS,
            # export kW, import kW, PV MAX, ESS charge, ESS discharge,
            # battery export owner, ESS charge owner
            ("actual negative", -0.05, True, 0.05, True, BATTERY_EXPORT,
             MODE_CMD_DISCHARGE_PV, 25.0, 0.0, 0.1, 25.0, 0.01,
             "morning_dump", "normal"),
            ("estimated negative", -0.05, False, 0.05, True, BATTERY_EXPORT,
             MODE_CMD_DISCHARGE_PV, 25.0, 0.0, 25.0, 25.0, 25.0,
             "morning_dump", "normal"),
            ("actual positive", 0.30, True, 0.05, True, BATTERY_EXPORT,
             MODE_CMD_DISCHARGE_PV, 25.0, 0.0, 25.0, 25.0, 25.0,
             "morning_dump", "normal"),
            ("blocked subcent FiT", -0.05, True, 0.0099, True, EXPORT_BLOCKED,
             MODE_MAX_SELF, 0.0, 0.0, 0.1, 25.0, 0.01,
             "none", "normal"),
            ("inactive Dump negative", -0.05, True, 0.05, False, EXPORT_BLOCKED,
             MODE_CMD_CHARGE_GRID, 0.0, 25.0, 0.1, 25.0, 0.01,
             "none", "grid_import"),
        )
        for (
            name, price, actual, fit, active, intent, ems, export_kw, import_kw,
            pv_max_kw, charge_kw, discharge_kw, export_owner, charge_owner,
        ) in cases:
            with self.subTest(case=name):
                decision = self.characterize(
                    current_price=price,
                    actual=actual,
                    fit=fit,
                    inactive_dump=name == "inactive Dump negative",
                )
                self.assertEqual(active, decision.morning_dump_active)
                self.assertEqual(intent, decision.export_intent)
                self.assertEqual(ems, decision.ems_mode)
                self.assertEqual(export_kw, decision.export_limit)
                self.assertEqual(import_kw, decision.import_limit)
                self.assertEqual(pv_max_kw, decision.pv_max_power_limit)
                self.assertEqual(charge_kw, decision.ess_charge_limit)
                self.assertEqual(discharge_kw, decision.ess_discharge_limit)
                self.assertEqual(export_owner, decision.trace_values["battery_export_final_owner"])
                self.assertEqual(charge_owner, decision.trace_values["ess_charge_limit_owner"])

