from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock

from app.models import Decision, SolarState
from app.optimizer import (
    MODE_CMD_CHARGE_GRID,
    MODE_CMD_CHARGE_PV,
    MODE_CMD_DISCHARGE_PV,
    MODE_MAX_SELF,
)
from haos49_characterization_helpers import (
    Haos49CharacterizationCase,
    RecordingHA,
)


class Haos49FailureCharacterizationTests(Haos49CharacterizationCase):
    def assert_outputs(
        self,
        decision,
        expected: tuple[str, float, float, float, float, float],
    ) -> None:
        self.assertEqual(
            expected,
            (
                decision.ems_mode,
                decision.export_limit,
                decision.import_limit,
                decision.pv_max_power_limit,
                decision.ess_charge_limit,
                decision.ess_discharge_limit,
            ),
        )

    def _full_battery_state(self, **overrides: object):
        values: dict[str, object] = {
            "battery_soc": 100.0,
            "available_discharge_energy_kwh": 30.0,
            "battery_power_sensor_kw": 0.0,
            "feedin_price": 0.15,
            "feedin_price_cents": 15.0,
            "pv_kw": 6.0,
            "solar_power_now_kw": 6.0,
            "load_kw": 1.0,
            "current_export_limit": 25.0,
        }
        values.update(overrides)
        return self.state(self.FIXED_AFTERNOON, **values)

    def _negative_import_state(self, **overrides: object):
        values: dict[str, object] = {
            "battery_soc": 30.0,
            "available_discharge_energy_kwh": 9.0,
            "current_price": -0.35,
            "current_price_cents": -35.0,
            "price_is_actual": True,
            "feedin_price": 0.0,
            "feedin_price_cents": 0.0,
            "pv_kw": 0.0,
            "solar_power_now_kw": 0.0,
            "load_kw": 1.0,
            "forecast_remaining_kwh": 0.0,
        }
        values.update(overrides)
        return self.state(self.FIXED_AFTERNOON, **values)

    def test_raw_unknown_unavailable_and_missing_ems_are_not_observed(self) -> None:
        ha = RecordingHA()
        optimizer = self.optimizer(ha)
        cfg = optimizer.cfg
        cases = (
            ("missing", None),
            ("unknown", "unknown"),
            ("unavailable", "unavailable"),
            ("none", "none"),
            ("blank", ""),
        )

        for name, raw in cases:
            with self.subTest(name=name):
                ha.states = {}
                if raw is not None:
                    ha.states[cfg.ems_mode_select] = {
                        "state": raw,
                        "attributes": {},
                    }

                state = asyncio.run(optimizer._read_state())

                self.assertEqual("", state.current_ems_mode)
                self.assertFalse(state.ems_mode_observed)

    def test_malformed_ems_is_observed_but_does_not_count_as_msc(self) -> None:
        ha = RecordingHA()
        optimizer = self.optimizer(ha)
        ha.states = {
            optimizer.cfg.ems_mode_select: {
                "state": "malformed-mode",
                "attributes": {},
            }
        }

        parsed = asyncio.run(optimizer._read_state())
        decision = self.decide(
            optimizer,
            self._full_battery_state(
                current_ems_mode=parsed.current_ems_mode,
                ems_mode_observed=parsed.ems_mode_observed,
            ),
            self.FIXED_AFTERNOON,
        )

        self.assertEqual("malformed-mode", parsed.current_ems_mode)
        self.assertTrue(parsed.ems_mode_observed)
        self.assert_outputs(decision, (MODE_MAX_SELF, 0.0, 0.0, 25.0, 25.0, 25.0))
        self.assertFalse(decision.trace_gates["pv_only_ems_safe"])
        self.assertTrue(decision.trace_gates["pv_only_msc_stage1_active"])
        self.assertFalse(decision.trace_gates["pv_only_msc_high_ceiling_active"])
        self.assertEqual("msc_full_battery_stage1_closed", decision.trace_values["export_branch"])

    def test_exact_observed_msc_is_required_for_full_battery_high_ceiling(self) -> None:
        cases = (
            ("lost", "", False, 0.0, True, False),
            ("malformed", "malformed-mode", True, 0.0, True, False),
            ("exact_msc", MODE_MAX_SELF, True, 25.0, False, True),
        )
        for name, mode, observed, export, stage1, high in cases:
            with self.subTest(name=name):
                optimizer = self.optimizer()
                state = self._full_battery_state(
                    current_ems_mode=mode,
                    ems_mode_observed=observed,
                )

                decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

                self.assert_outputs(
                    decision,
                    (MODE_MAX_SELF, export, 0.0, 25.0, 25.0, 25.0),
                )
                self.assertEqual(observed, decision.trace_gates["ems_mode_observed"])
                self.assertEqual(stage1, decision.trace_gates["pv_only_msc_stage1_active"])
                self.assertEqual(high, decision.trace_gates["pv_only_msc_high_ceiling_active"])
                self.assertEqual(high, decision.requires_verified_msc_before_export)

    def test_remote_ems_switch_parsing_distinguishes_on_off_and_uncertain(self) -> None:
        ha = RecordingHA()
        optimizer = self.optimizer(ha)
        cfg = optimizer.cfg
        cases = (
            ("missing", None, False, False, "missing"),
            ("unavailable", "unavailable", False, False, "unavailable"),
            ("unknown", "unknown", False, False, "unknown"),
            ("malformed", "yes", False, False, "yes"),
            ("off", "off", True, False, "off"),
            ("on", "on", True, True, "on"),
        )
        for name, raw, available, enabled, parsed_state in cases:
            with self.subTest(name=name):
                ha.states = {}
                if raw is not None:
                    ha.states[cfg.ha_control_switch] = {
                        "state": raw,
                        "attributes": {},
                    }

                state = asyncio.run(optimizer._read_state())

                self.assertEqual(available, state.ha_control_switch_available)
                self.assertEqual(enabled, state.ha_control_enabled)
                self.assertEqual(parsed_state, state.ha_control_switch_state)

    def test_remote_ems_unavailable_pauses_all_automatic_writes(self) -> None:
        ha = RecordingHA()
        optimizer = self.optimizer(ha)
        state = self._negative_import_state(
            ha_control_enabled=False,
            ha_control_switch_available=False,
            ha_control_switch_state="unavailable",
        )
        decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

        self.assert_outputs(
            decision,
            (MODE_CMD_CHARGE_GRID, 0.0, 25.0, 0.1, 25.0, 0.01),
        )
        self.assertFalse(decision.needs_ha_control_switch)

        asyncio.run(optimizer._apply(state, decision))

        self.assertEqual([], ha.calls)

    def test_remote_ems_off_success_is_treated_as_same_cycle_authority(self) -> None:
        ha = RecordingHA(settle_switch=False, turn_on_result=True)
        optimizer = self.optimizer(ha)
        state = self._negative_import_state(
            ha_control_enabled=False,
            ha_control_switch_available=True,
            ha_control_switch_state="off",
        )
        decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

        self.assert_outputs(
            decision,
            (MODE_CMD_CHARGE_GRID, 0.0, 25.0, 0.1, 25.0, 0.01),
        )
        self.assertTrue(decision.needs_ha_control_switch)

        asyncio.run(optimizer._apply(state, decision))

        enable_call = ("turn_on", optimizer.cfg.ha_control_switch, True)
        mode_call = ("select_option", optimizer.cfg.ems_mode_select, MODE_CMD_CHARGE_GRID)
        self.assertLess(ha.calls.index(enable_call), ha.calls.index(mode_call))
        self.assertFalse(
            any(
                call[0] == "get_state_value" and call[1] == optimizer.cfg.ha_control_switch
                for call in ha.calls
            )
        )
        self.assertIn(("set_number", optimizer.cfg.grid_import_limit, 25.0), ha.calls)

    def test_remote_ems_on_writes_without_turn_on(self) -> None:
        ha = RecordingHA()
        optimizer = self.optimizer(ha)
        state = self._negative_import_state(
            ha_control_enabled=True,
            ha_control_switch_available=True,
            ha_control_switch_state="on",
        )
        decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

        self.assert_outputs(
            decision,
            (MODE_CMD_CHARGE_GRID, 0.0, 25.0, 0.1, 25.0, 0.01),
        )
        asyncio.run(optimizer._apply(state, decision))

        self.assertFalse(any(call[0] == "turn_on" for call in ha.calls))
        self.assertIn(("select_option", optimizer.cfg.ems_mode_select, MODE_CMD_CHARGE_GRID), ha.calls)

    def test_successful_msc_request_without_exact_readback_never_opens_high_ceiling(self) -> None:
        ha = RecordingHA(settle_selects=False)
        optimizer = self.optimizer(ha)
        state = self._full_battery_state(
            current_ems_mode=MODE_MAX_SELF,
            current_export_limit=0.01,
        )
        decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)
        self.assertTrue(decision.requires_verified_msc_before_export)
        ha.state_values = {
            optimizer.cfg.ems_mode_select: MODE_CMD_DISCHARGE_PV,
            optimizer.cfg.grid_export_limit: 0.01,
        }
        optimizer._wait_for_exact_entity_state = AsyncMock(return_value=False)

        asyncio.run(optimizer._apply(state, decision))

        self.assertIn(("select_option", optimizer.cfg.ems_mode_select, MODE_MAX_SELF), ha.calls)
        export_writes = [
            float(call[2])
            for call in ha.calls
            if call[0] == "set_number" and call[1] == optimizer.cfg.grid_export_limit
        ]
        self.assertIn(0.01, export_writes)
        self.assertFalse(any(value > 0.011 for value in export_writes))

    def test_cold_and_warm_unavailable_control_mode_fallbacks_differ(self) -> None:
        cold_ha = RecordingHA()
        cold = self.optimizer(cold_ha)
        cold_ha.states = {
            cold.cfg.sigenergy_mode_select: {
                "state": "unavailable",
                "attributes": {},
            }
        }
        cold_state = asyncio.run(cold._read_state())

        warm_ha = RecordingHA()
        warm = self.optimizer(warm_ha)
        warm._last_state = SolarState(sigenergy_mode=warm.cfg.full_export_option)
        warm_ha.states = {
            warm.cfg.sigenergy_mode_select: {
                "state": "unavailable",
                "attributes": {},
            }
        }
        warm_state = asyncio.run(warm._read_state())

        self.assertEqual(cold.cfg.automated_option, cold_state.sigenergy_mode)
        self.assertFalse(cold_state.sigenergy_mode_observed)
        self.assertEqual(warm.cfg.full_export_option, warm_state.sigenergy_mode)
        self.assertFalse(warm_state.sigenergy_mode_observed)

        qualifying = self._full_battery_state()
        for name in (
            "battery_soc",
            "battery_capacity_kwh",
            "available_discharge_energy_kwh",
            "battery_power_sensor_kw",
            "feedin_price",
            "feedin_price_cents",
            "pv_kw",
            "solar_power_now_kw",
            "load_kw",
            "forecast_remaining_kwh",
            "forecast_today_kwh",
            "forecast_tomorrow_kwh",
            "ess_max_charge_kw",
            "ess_max_discharge_kw",
            "next_sunrise_ts",
            "next_sunset_ts",
            "hours_to_sunrise",
            "hours_to_sunset",
            "sun_above_horizon",
            "current_export_limit",
        ):
            setattr(cold_state, name, getattr(qualifying, name))
        cold_state.current_ems_mode = MODE_MAX_SELF
        cold_state.ems_mode_observed = True
        cold_decision = self.decide(cold, cold_state, self.FIXED_AFTERNOON)
        self.assertFalse(cold_decision.trace_gates["pv_only_msc_transition_ready"])
        self.assertFalse(cold_decision.trace_gates["pv_only_msc_high_ceiling_active"])

        warm_state.current_ems_mode = MODE_MAX_SELF
        warm_state.current_export_limit = 1.7
        warm_state.current_import_limit = 0.2
        warm_state.current_pv_max_power_limit = 8.0
        warm_state.current_ess_charge_limit = 3.0
        warm_state.current_ess_discharge_limit = 4.0
        warm_decision = self.decide(warm, warm_state, self.FIXED_AFTERNOON)
        warm._freeze_decision_to_live_mode(
            warm_state,
            warm_decision,
            warm_state.sigenergy_mode,
        )
        self.assert_outputs(
            warm_decision,
            (MODE_MAX_SELF, 1.7, 0.2, 8.0, 3.0, 4.0),
        )
        self.assertIn("optimizer writes paused", warm_decision.outcome_reason)

    def test_plain_manual_freezes_all_outputs_and_pauses_writes(self) -> None:
        ha = RecordingHA()
        optimizer = self.optimizer(ha)
        cfg = optimizer.cfg
        state = self._full_battery_state(
            sigenergy_mode=cfg.manual_option,
            current_ems_mode=MODE_CMD_CHARGE_PV,
            current_export_limit=1.7,
            current_import_limit=0.2,
            current_pv_max_power_limit=8.0,
            current_ess_charge_limit=3.0,
            current_ess_discharge_limit=4.0,
        )
        decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)
        automatic_trace_export = decision.trace_values["desired_export_limit"]

        optimizer._freeze_decision_to_live_mode(state, decision, cfg.manual_option)
        asyncio.run(optimizer._apply(state, decision))

        self.assert_outputs(
            decision,
            (MODE_CMD_CHARGE_PV, 1.7, 0.2, 8.0, 3.0, 4.0),
        )
        self.assertNotEqual(decision.export_limit, automatic_trace_export)
        self.assertIn("optimizer writes paused", decision.outcome_reason)
        self.assertEqual([], ha.calls)

    def test_all_force_preset_target_maps_pin_six_outputs(self) -> None:
        optimizer = self.optimizer()
        cfg = optimizer.cfg
        state = self.state(self.FIXED_AFTERNOON)
        expected = {
            cfg.full_export_option: (MODE_CMD_DISCHARGE_PV, 25.0, 0.01, 30.0, 25.0, 25.0),
            cfg.full_import_option: (MODE_CMD_CHARGE_GRID, 0.01, 25.0, 30.0, 25.0, 25.0),
            cfg.full_import_pv_option: (MODE_CMD_CHARGE_PV, 0.01, 25.0, 30.0, 25.0, 25.0),
            cfg.block_flow_option: (MODE_MAX_SELF, 0.01, 0.01, 30.0, 25.0, 25.0),
        }
        for mode, outputs in expected.items():
            with self.subTest(mode=mode):
                targets = optimizer._manual_mode_targets(
                    mode,
                    state,
                    include_block_flow_ess_limits=True,
                )
                self.assertIsNotNone(targets)
                assert targets is not None
                self.assertEqual(
                    outputs,
                    (
                        targets["ems_mode"],
                        targets["grid_export_limit"],
                        targets["grid_import_limit"],
                        targets["pv_max_power_limit"],
                        targets["ess_charge_limit"],
                        targets["ess_discharge_limit"],
                    ),
                )
        self.assertIsNone(optimizer._manual_mode_targets(cfg.manual_option, state))

    def test_force_presets_reapply_targets_before_remote_control_gate(self) -> None:
        modes = (
            "full_export_option",
            "full_import_option",
            "full_import_pv_option",
            "block_flow_option",
        )
        for mode_attr in modes:
            with self.subTest(mode_attr=mode_attr):
                ha = RecordingHA()
                optimizer = self.optimizer(ha)
                cfg = optimizer.cfg
                mode = str(getattr(cfg, mode_attr))
                state = self.state(
                    self.FIXED_AFTERNOON,
                    sigenergy_mode=mode,
                    current_ems_mode="drifted-mode",
                    current_export_limit=2.0,
                    current_import_limit=2.0,
                    current_pv_max_power_limit=2.0,
                    current_ess_charge_limit=2.0,
                    current_ess_discharge_limit=2.0,
                    ha_control_enabled=False,
                    ha_control_switch_available=False,
                    ha_control_switch_state="unavailable",
                )
                targets = optimizer._manual_mode_targets(
                    mode,
                    state,
                    include_block_flow_ess_limits=True,
                )
                assert targets is not None
                ha.state_values[optimizer.cfg.ems_mode_select] = targets["ems_mode"]

                asyncio.run(optimizer._apply(state, Decision()))

                self.assertIn(
                    ("select_option", cfg.ems_mode_select, targets["ems_mode"]),
                    ha.calls,
                )
                self.assertIn(
                    ("set_number", cfg.grid_export_limit, targets["grid_export_limit"]),
                    ha.calls,
                )
                self.assertIn(
                    ("set_number", cfg.grid_import_limit, targets["grid_import_limit"]),
                    ha.calls,
                )
                self.assertFalse(any(call[0] == "turn_on" for call in ha.calls))


if __name__ == "__main__":
    unittest.main()
