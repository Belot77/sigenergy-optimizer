"""Characterize current floor re-entry; this is not a damping fix or live proof.

Use real decision eligibility with trusted continuous synthetic forecasts. No
actuator application occurs, and prior decisions are synthetic history only.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.config import Settings
from app.optimizer import BATTERY_EXPORT, EXPORT_BLOCKED, MODE_CMD_DISCHARGE_PV, MODE_MAX_SELF
from haos49_characterization_helpers import Haos49CharacterizationCase


class MorningDumpFloorCyclingCharacterizationTests(Haos49CharacterizationCase):
    START = datetime(2026, 1, 15, 6, 0, tzinfo=timezone.utc)

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
        super().setUp()

    def test_current_floor_reentry_is_not_damped_by_general_soc_hysteresis(self):
        for hysteresis in (0.0, 2.0, 10.0):
            with self.subTest(soc_hysteresis=hysteresis):
                optimizer = self.optimizer(
                    morning_dump_enabled=True,
                    morning_dump_min_soc=15.0,
                    soc_hysteresis=hysteresis,
                )
                optimizer._tz = timezone.utc
                active_sequence = []
                for index, soc in enumerate((15.1, 15.0, 15.1, 15.0, 15.1)):
                    when = self.START + timedelta(seconds=6 * index)
                    # The shared helper builds naive local sun times. Explicit
                    # UTC overrides keep forecast coverage independent of host TZ.
                    state = self.state(
                        when.replace(tzinfo=None),
                        sun_above_horizon=False,
                        timestamp=when,
                        next_sunrise_ts=self.START.replace(hour=7).timestamp(),
                        next_sunset_ts=self.START.replace(hour=18).timestamp(),
                        battery_soc=soc,
                        battery_soc_trusted=True,
                        battery_capacity_trusted=True,
                        available_discharge_energy_kwh=soc * 0.3,
                        available_discharge_energy_trusted=True,
                        feedin_price=0.05,
                        feedin_price_cents=5.0,
                        load_kw=1.0,
                        forecast_remaining_observation_trusted=True,
                        solcast_detailed_source_trusted=True,
                        solcast_detailed=[
                            {
                                "period_start": (
                                    self.START + timedelta(minutes=30 * period)
                                ).isoformat(),
                                "pv_estimate": 10.0,
                            }
                            for period in range(25)
                        ],
                    )
                    with patch.object(
                        optimizer,
                        "_optimizer_import_topup_summary_today",
                        return_value={},
                    ):
                        decision = self.decide(optimizer, state, when)
                    self.assertTrue(decision.trace_gates["morning_dump_detailed_coverage"])
                    self.assertTrue(decision.trace_gates["morning_dump_refill_timing_evidence_trusted"])
                    self.assertTrue(decision.trace_gates["morning_dump_refill_timing_feasible"])
                    active_sequence.append(decision.morning_dump_active)
                    if soc > 15.0:
                        self.assertEqual(BATTERY_EXPORT, decision.export_intent)
                        self.assertEqual("morning_dump", decision.trace_values["battery_export_final_owner"])
                        self.assertEqual(MODE_CMD_DISCHARGE_PV, decision.ems_mode)
                        self.assertEqual(25.0, decision.export_limit)
                    else:
                        self.assertEqual(EXPORT_BLOCKED, decision.export_intent)
                        self.assertEqual("none", decision.trace_values["battery_export_final_owner"])
                        self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
                        self.assertEqual(0.0, decision.export_limit)
                    self.assertEqual(0.0, decision.import_limit)
                    # Carry prior requested decisions to expose any decision-level
                    # latch; this does not simulate successful actuator settlement.
                    optimizer._last_decision = decision
                self.assertEqual([True, False, True, False, True], active_sequence)
                self.assertEqual([], optimizer.ha.calls)
