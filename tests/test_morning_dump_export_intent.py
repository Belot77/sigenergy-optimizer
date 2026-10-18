"""Decision-only Morning Dump regressions; fake HA, no actuator application."""

from __future__ import annotations

import os
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
from haos49_characterization_helpers import Haos49CharacterizationCase


class MorningDumpExportIntentTests(Haos49CharacterizationCase):
    WHEN = datetime(2026, 1, 15, 6, 0)

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
        # Install the fixture's temporary database after environment isolation.
        super().setUp()

    def characterize(
        self,
        *,
        fit: float = 0.05,
        state_overrides: dict[str, object] | None = None,
        import_summary: dict[str, object] | None = None,
    ):
        optimizer = self.optimizer(morning_dump_enabled=True, morning_dump_min_soc=15.0)
        values = dict(
            battery_soc=80.0,
            battery_soc_trusted=True,
            battery_capacity_trusted=True,
            available_discharge_energy_kwh=24.0,
            available_discharge_energy_trusted=True,
            feedin_price=fit,
            feedin_price_cents=fit * 100.0,
            feedin_is_negative=fit < 0.0,
            load_kw=1.0,
            solcast_detailed=[
                {
                    "period_start": (self.WHEN + timedelta(hours=hours)).isoformat(),
                    "pv_estimate": 20.0,
                }
                for hours in (3, 5, 7, 9, 11)
            ],
        )
        values.update(state_overrides or {})
        state = self.state(self.WHEN, sun_above_horizon=False, **values)
        with patch.object(
            optimizer,
            "_optimizer_import_topup_summary_today",
            return_value={} if import_summary is None else import_summary,
        ):
            decision = self.decide(optimizer, state, self.WHEN)
        self.assertEqual([], optimizer.ha.calls)
        return decision

    def assert_closed_msc(self, decision) -> None:
        self.assertEqual(EXPORT_BLOCKED, decision.export_intent)
        self.assertEqual(0.0, decision.export_limit)
        self.assertEqual("none", decision.trace_values["battery_export_final_owner"])
        self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
        self.assertEqual(0.0, decision.import_limit)

    def test_sub_one_cent_fit_cannot_select_discharge_for_blocked_export(self):
        for fit in (0.0024502, 0.0099, 0.0, -0.01):
            with self.subTest(fit=fit):
                decision = self.characterize(fit=fit)
                self.assertTrue(decision.morning_dump_active)
                self.assert_closed_msc(decision)

    def test_qualified_dump_at_or_above_one_cent_keeps_discharge_ownership(self):
        for fit in (0.01, 0.05):
            with self.subTest(fit=fit):
                decision = self.characterize(fit=fit)
                self.assertTrue(decision.morning_dump_active)
                self.assertEqual(BATTERY_EXPORT, decision.export_intent)
                self.assertEqual("morning_dump", decision.trace_values["battery_export_final_owner"])
                self.assertGreater(decision.export_limit, 0.01)
                self.assertEqual(MODE_CMD_DISCHARGE_PV, decision.ems_mode)
                self.assertEqual(0.0, decision.import_limit)

    def test_qualified_dump_keeps_existing_priority_during_negative_import_price(self):
        for fit in (0.01, 0.05):
            with self.subTest(fit=fit):
                decision = self.characterize(fit=fit, state_overrides={
                    "current_price": -0.05,
                    "current_price_cents": -5.0,
                    "price_is_negative": True,
                })
                self.assertTrue(decision.morning_dump_active)
                self.assertEqual(BATTERY_EXPORT, decision.export_intent)
                self.assertEqual("morning_dump", decision.trace_values["battery_export_final_owner"])
                self.assertEqual(MODE_CMD_DISCHARGE_PV, decision.ems_mode)
                self.assertEqual(0.0, decision.import_limit)

    def test_blocked_dump_during_negative_import_price_keeps_closed_msc(self):
        for fit in (0.0024502, 0.0099):
            with self.subTest(fit=fit):
                decision = self.characterize(fit=fit, state_overrides={
                    "current_price": -0.05,
                    "current_price_cents": -5.0,
                    "price_is_negative": True,
                    "demand_window_active": False,
                    "demand_window_observed": True,
                })
                self.assertTrue(decision.morning_dump_active)
                self.assertTrue(decision.trace_gates["demand_window_observed"])
                self.assertFalse(decision.trace_gates["demand_window_import_blocked"])
                self.assertEqual(EXPORT_BLOCKED, decision.export_intent)
                self.assertEqual("none", decision.trace_values["battery_export_final_owner"])
                self.assertEqual(0.0, decision.import_limit)
                self.assertEqual(0.0, decision.export_limit)
                self.assertEqual(MODE_MAX_SELF, decision.ems_mode)

    def test_inactive_dump_preserves_qualified_negative_price_grid_charging(self):
        for fit in (0.0024502, 0.0099):
            with self.subTest(fit=fit):
                decision = self.characterize(fit=fit, state_overrides={
                    "battery_soc": 15.0,
                    "available_discharge_energy_kwh": 4.5,
                    "current_price": -0.05,
                    "current_price_cents": -5.0,
                    "price_is_negative": True,
                    "demand_window_active": False,
                    "demand_window_observed": True,
                })
                self.assertFalse(decision.morning_dump_active)
                self.assertFalse(decision.trace_gates["demand_window_import_blocked"])
                self.assertEqual(EXPORT_BLOCKED, decision.export_intent)
                self.assertEqual(0.0, decision.export_limit)
                self.assertGreater(decision.import_limit, 0.0)
                self.assertEqual(MODE_CMD_CHARGE_GRID, decision.ems_mode)

    def test_blocked_dump_keeps_msc_with_demand_window_on_or_unobserved(self):
        for fit in (0.0024502, 0.0099):
            for active, observed in ((True, True), (False, False)):
                with self.subTest(fit=fit, active=active, observed=observed):
                    decision = self.characterize(fit=fit, state_overrides={
                        "current_price": -0.05,
                        "current_price_cents": -5.0,
                        "price_is_negative": True,
                        "demand_window_active": active,
                        "demand_window_observed": observed,
                    })
                    self.assertTrue(decision.morning_dump_active)
                    self.assertEqual(observed, decision.trace_gates["demand_window_observed"])
                    self.assertTrue(decision.trace_gates["demand_window_import_blocked"])
                    self.assert_closed_msc(decision)

    def test_dump_stays_inactive_at_or_below_its_existing_floor(self):
        for soc in (14.9, 15.0):
            with self.subTest(soc=soc):
                decision = self.characterize(state_overrides={
                    "battery_soc": soc,
                    "available_discharge_energy_kwh": soc * 0.3,
                })
                self.assertFalse(decision.morning_dump_active)
                self.assert_closed_msc(decision)

    def test_untrusted_battery_evidence_cannot_enable_dump(self):
        for field in (
            "battery_soc_trusted",
            "battery_capacity_trusted",
            "available_discharge_energy_trusted",
        ):
            with self.subTest(field=field):
                decision = self.characterize(state_overrides={field: False})
                self.assertFalse(decision.morning_dump_active)
                self.assert_closed_msc(decision)

    def test_actual_import_cost_veto_still_closes_dump(self):
        for summary in (
            {"today_highest_actual_import_price": 0.20},
            {"import_cost_floor_unknown": True},
        ):
            with self.subTest(import_summary=summary):
                decision = self.characterize(import_summary=summary)
                self.assertTrue(decision.trace_gates["actual_import_cost_guard_blocking"])
                self.assert_closed_msc(decision)

    def test_zero_discharge_capability_cannot_select_discharge_ems(self):
        decision = self.characterize(state_overrides={"ess_max_discharge_kw": 0.0})
        self.assertTrue(decision.morning_dump_active)
        self.assert_closed_msc(decision)
