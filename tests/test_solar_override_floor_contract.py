"""Regressions for Solar Override respecting selected and protected SoC floors.

These decision-only checks do not establish live acceptance.
Every case uses fake HA and a temporary state store;
neither actuator application nor a Home Assistant service is invoked.
"""

from __future__ import annotations

import os
from unittest.mock import patch

from app.config import Settings
from app.optimizer import (
    BATTERY_EXPORT,
    EXPORT_BLOCKED,
    MODE_CMD_DISCHARGE_PV,
    MODE_MAX_SELF,
    MSC_SURPLUS_CEILING,
)
from haos49_characterization_helpers import Haos49CharacterizationCase


class SolarOverrideFloorCharacterizationTests(Haos49CharacterizationCase):
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
        # The shared fixture installs its temporary DB path after env isolation.
        super().setUp()

    def characterize(
        self,
        *,
        target_soc: float = 100.0,
        medium_floor: float = 100.0,
        high_floor: float = 100.0,
        spike_floor: float = 100.0,
        soc: float = 100.0,
        fit: float = 0.40,
        import_summary: dict[str, object] | None = None,
        config_overrides: dict[str, object] | None = None,
        state_overrides: dict[str, object] | None = None,
    ):
        config = dict(
            max_battery_soc=target_soc,
            battery_export_min_soc_medium=medium_floor,
            battery_export_min_soc_high=high_floor,
            battery_export_min_soc_spike=spike_floor,
        )
        config.update(config_overrides or {})
        optimizer = self.optimizer(**config)
        values = dict(
            battery_soc=soc,
            battery_soc_trusted=True,
            battery_capacity_trusted=True,
            available_discharge_energy_kwh=soc * 0.3,
            feedin_price=fit,
            feedin_price_cents=fit * 100.0,
            pv_kw=10.0,
            solar_power_now_kw=10.0,
            load_kw=1.0,
            forecast_remaining_observation_trusted=True,
        )
        values.update(state_overrides or {})
        state = self.state(self.FIXED_AFTERNOON, **values)
        with patch.object(
            optimizer,
            "_optimizer_import_topup_summary_today",
            return_value={} if import_summary is None else import_summary,
        ):
            decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)
        self.assertEqual([], optimizer.ha.calls)
        return decision

    def assert_rejected_tier(self, decision, tier: str) -> None:
        self.assertEqual(tier, decision.trace_values["battery_export_tier"])
        self.assertEqual("selected_soc_floor", decision.trace_values["battery_export_rejection"])
        self.assertFalse(decision.trace_values["battery_export_proposal_qualified"])
        self.assertFalse(decision.trace_values["battery_export_candidate_eligible"])

    def test_medium_floor_rejection_preserves_pv_only_without_solar_discharge(self):
        for target_soc, soc in ((100.0, 100.0), (50.0, 99.9)):
            with self.subTest(target_soc=target_soc, soc=soc):
                decision = self.characterize(target_soc=target_soc, soc=soc)
                self.assert_rejected_tier(decision, "medium")
                self.assertEqual(100.0, decision.trace_values["battery_export_selected_soc_floor"])
                self.assertFalse(decision.trace_gates["export_solar_override"])
                self.assertEqual("none", decision.trace_values["battery_export_final_owner"])
                self.assertEqual(MSC_SURPLUS_CEILING, decision.export_intent)
                self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
                self.assertEqual(25.0, decision.export_limit)

    def test_solar_override_requires_soc_strictly_above_selected_floor(self):
        for soc in (94.9, 95.0):
            with self.subTest(soc=soc):
                decision = self.characterize(target_soc=50.0, medium_floor=95.0, soc=soc)
                self.assert_rejected_tier(decision, "medium")
                self.assertFalse(decision.trace_gates["export_solar_override"])
                self.assertEqual("none", decision.trace_values["battery_export_final_owner"])
                self.assertEqual(MSC_SURPLUS_CEILING, decision.export_intent)
                self.assertEqual(MODE_MAX_SELF, decision.ems_mode)

        decision = self.characterize(target_soc=50.0, medium_floor=95.0, soc=95.1)
        self.assertTrue(decision.trace_gates["export_solar_override"])
        self.assertEqual("solar_override", decision.trace_values["battery_export_final_owner"])
        self.assertEqual(BATTERY_EXPORT, decision.export_intent)
        self.assertEqual(MODE_CMD_DISCHARGE_PV, decision.ems_mode)
        self.assertEqual(9.0, decision.export_limit)

    def test_higher_protected_floor_also_blocks_solar_override(self):
        decision = self.characterize(
            target_soc=50.0, medium_floor=40.0, soc=95.0,
            config_overrides={"min_soc_floor": 95.0},
        )
        self.assertEqual(95.0, decision.trace_values["battery_export_protected_soc_floor"])
        self.assertEqual("protected_soc_floor", decision.trace_values["battery_export_rejection"])
        self.assertFalse(decision.trace_gates["export_solar_override"])
        self.assertNotEqual(BATTERY_EXPORT, decision.export_intent)
        self.assertEqual("none", decision.trace_values["battery_export_final_owner"])

    def test_high_and_spike_use_their_selected_floor_not_the_medium_floor(self):
        for fit, spike, tier, owner in (
            (1.10, False, "high", "high_price"),
            (0.70, True, "spike", "export_spike"),
        ):
            for soc, eligible in ((95.0, False), (95.1, True)):
                with self.subTest(tier=tier, soc=soc):
                    decision = self.characterize(
                        target_soc=50.0, medium_floor=100.0,
                        high_floor=95.0, spike_floor=95.0, soc=soc, fit=fit,
                        config_overrides={"export_spike_threshold": 0.60},
                        state_overrides={"price_spike_active": spike},
                    )
                    self.assertEqual(tier, decision.trace_values["battery_export_tier"])
                    self.assertEqual(eligible, decision.trace_gates["export_solar_override"])
                    if eligible:
                        self.assertEqual(owner, decision.trace_values["battery_export_final_owner"])
                        self.assertEqual(BATTERY_EXPORT, decision.export_intent)
                    else:
                        self.assert_rejected_tier(decision, tier)
                        self.assertNotEqual(BATTERY_EXPORT, decision.export_intent)

    def test_rejected_override_does_not_create_pv_only_permission_with_unsafe_flow(self):
        decision = self.characterize(
            state_overrides={"battery_power_sensor_kw": -2.0, "grid_export_power_kw": 2.0},
        )
        self.assertFalse(decision.trace_gates["export_solar_override"])
        self.assertEqual(EXPORT_BLOCKED, decision.export_intent)
        self.assertEqual("none", decision.trace_values["battery_export_final_owner"])
        self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
        self.assertEqual(0.0, decision.export_limit)

    def test_below_solar_override_target_preserves_msc_surplus_ceiling(self):
        decision = self.characterize(target_soc=100.0, soc=99.9)
        self.assert_rejected_tier(decision, "medium")
        self.assertFalse(decision.trace_gates["export_solar_override"])
        self.assertEqual("none", decision.trace_values["battery_export_final_owner"])
        self.assertEqual(MSC_SURPLUS_CEILING, decision.export_intent)
        self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
        self.assertEqual(25.0, decision.export_limit)

    def test_medium_floor_is_strict_when_legacy_solar_override_is_absent(self):
        for soc in (69.9, 70.0):
            with self.subTest(soc=soc):
                decision = self.characterize(medium_floor=70.0, soc=soc)
                self.assert_rejected_tier(decision, "medium")
                self.assertFalse(decision.trace_gates["export_solar_override"])
                self.assertEqual("none", decision.trace_values["battery_export_final_owner"])
                self.assertNotEqual(BATTERY_EXPORT, decision.export_intent)
                self.assertEqual(MODE_MAX_SELF, decision.ems_mode)

        decision = self.characterize(medium_floor=70.0, soc=71.0)
        self.assertFalse(decision.trace_gates["export_solar_override"])
        self.assertTrue(decision.trace_values["battery_export_candidate_eligible"])
        self.assertEqual("medium_price", decision.trace_values["battery_export_final_owner"])
        self.assertEqual(BATTERY_EXPORT, decision.export_intent)
        self.assertEqual(MODE_CMD_DISCHARGE_PV, decision.ems_mode)

    def test_high_floor_rejection_does_not_select_the_legacy_solar_override(self):
        decision = self.characterize(fit=1.10)
        self.assert_rejected_tier(decision, "high")
        self.assertFalse(decision.trace_gates["export_solar_override"])
        self.assertEqual("closed_battery_tier", decision.trace_values["desired_export_source"])
        self.assertEqual("none", decision.trace_values["battery_export_final_owner"])
        self.assertEqual(MSC_SURPLUS_CEILING, decision.export_intent)
        self.assertEqual(MODE_MAX_SELF, decision.ems_mode)

    def test_low_price_full_battery_remains_pv_only(self):
        decision = self.characterize(fit=0.15)
        self.assertEqual("low", decision.trace_values["battery_export_tier"])
        self.assertEqual(
            "low_battery_export_disabled_by_policy",
            decision.trace_values["battery_export_rejection"],
        )
        self.assertFalse(decision.trace_gates["export_solar_override"])
        self.assertEqual("none", decision.trace_values["battery_export_final_owner"])
        self.assertEqual(MSC_SURPLUS_CEILING, decision.export_intent)
        self.assertEqual(MODE_MAX_SELF, decision.ems_mode)

    def test_actual_import_cost_guard_still_vetoes_legacy_solar_override(self):
        for summary in (
            {"today_highest_actual_import_price": 2.0},
            {"import_cost_floor_unknown": True,
             "today_highest_actual_import_price": 2.0},
        ):
            with self.subTest(import_summary=summary):
                decision = self.characterize(medium_floor=90.0, import_summary=summary)
                self.assertTrue(decision.trace_gates["export_solar_override"])
                self.assertTrue(decision.trace_gates["actual_import_cost_guard_blocking"])
                self.assertEqual(EXPORT_BLOCKED, decision.export_intent)
                self.assertEqual("none", decision.trace_values["battery_export_final_owner"])
                self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
                self.assertEqual(0.0, decision.export_limit)

    def test_unknown_cost_history_alone_keeps_qualified_solar_override(self):
        decision = self.characterize(medium_floor=90.0, import_summary={
            "import_cost_floor_unknown": True,
            "today_highest_actual_import_price": None,
        })
        self.assertTrue(decision.trace_gates["export_solar_override"])
        self.assertTrue(decision.trace_gates["import_cost_floor_unknown"])
        self.assertTrue(decision.trace_gates["actual_import_cost_guard_active"])
        self.assertFalse(decision.trace_gates["actual_import_cost_guard_blocking"])
        self.assertIn("warning", decision.trace_values["actual_import_cost_guard_reason"].lower())
        self.assertEqual(BATTERY_EXPORT, decision.export_intent)
        self.assertEqual("solar_override", decision.trace_values["battery_export_final_owner"])
        self.assertEqual(MODE_CMD_DISCHARGE_PV, decision.ems_mode)
        self.assertGreater(decision.export_limit, 0.01)
