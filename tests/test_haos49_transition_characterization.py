from __future__ import annotations

import asyncio
import unittest

from app.optimizer import (
    MODE_CMD_DISCHARGE_PV,
    MODE_MAX_SELF,
)
from haos49_characterization_helpers import (
    Haos49CharacterizationCase,
    RecordingHA,
)


class Haos49TransitionCharacterizationTests(Haos49CharacterizationCase):
    def _full_battery_opportunity(self, **overrides: object):
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

    def test_loss_of_observed_msc_enters_closed_stage_one(self) -> None:
        optimizer = self.optimizer()
        state = self._full_battery_opportunity(
            current_ems_mode="",
            ems_mode_observed=False,
        )

        decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

        self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
        self.assertEqual(0.0, decision.export_limit)
        self.assertEqual(0.0, decision.import_limit)
        self.assertEqual(25.0, decision.pv_max_power_limit)
        self.assertEqual(25.0, decision.ess_charge_limit)
        self.assertEqual(25.0, decision.ess_discharge_limit)
        self.assertTrue(decision.trace_gates["pv_only_msc_transition_ready"])
        self.assertTrue(decision.trace_gates["pv_only_msc_stage1_active"])
        self.assertFalse(decision.trace_gates["pv_only_msc_high_ceiling_active"])
        self.assertFalse(decision.requires_verified_msc_before_export)
        self.assertEqual(
            "msc_full_battery_stage1_closed",
            decision.trace_values["export_branch"],
        )
        self.assertEqual("blocked", decision.trace_values["import_branch"])

    def test_stage_one_apply_requests_msc_before_closing_open_ceiling(self) -> None:
        ha = RecordingHA()
        optimizer = self.optimizer(ha)
        ha.state_values = {
            optimizer.cfg.ems_mode_select: "",
            optimizer.cfg.grid_export_limit: 25.0,
        }
        state = self._full_battery_opportunity(
            current_ems_mode="",
            ems_mode_observed=False,
        )
        decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

        asyncio.run(optimizer._apply(state, decision))

        mode_call = (
            "select_option",
            optimizer.cfg.ems_mode_select,
            MODE_MAX_SELF,
        )
        close_call = (
            "set_number",
            optimizer.cfg.grid_export_limit,
            0.01,
        )
        self.assertLess(ha.calls.index(mode_call), ha.calls.index(close_call))
        intervening = ha.calls[ha.calls.index(mode_call) + 1 : ha.calls.index(close_call)]
        self.assertFalse(any(call[0] == "get_state_value" for call in intervening))

    def test_stage_two_does_not_require_observed_closed_export(self) -> None:
        optimizer = self.optimizer()
        state = self._full_battery_opportunity(
            current_ems_mode=MODE_MAX_SELF,
            ems_mode_observed=True,
            current_export_limit=25.0,
        )

        decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

        self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
        self.assertEqual(25.0, decision.export_limit)
        self.assertEqual(0.0, decision.import_limit)
        self.assertEqual(25.0, decision.pv_max_power_limit)
        self.assertEqual(25.0, decision.ess_charge_limit)
        self.assertEqual(25.0, decision.ess_discharge_limit)
        self.assertFalse(decision.trace_gates["pv_only_msc_stage1_active"])
        self.assertTrue(decision.trace_gates["pv_only_msc_high_ceiling_active"])
        self.assertTrue(decision.requires_verified_msc_before_export)
        self.assertEqual(25.0, decision.trace_values["current_export_limit"])
        self.assertEqual(
            "msc_full_battery_high_ceiling",
            decision.trace_values["export_branch"],
        )

    def test_high_ceiling_apply_preflights_drift_then_reasserts_exact_msc(self) -> None:
        ha = RecordingHA()
        optimizer = self.optimizer(ha)
        ha.state_values = {
            optimizer.cfg.ems_mode_select: MODE_CMD_DISCHARGE_PV,
            optimizer.cfg.grid_export_limit: 0.01,
        }
        state = self._full_battery_opportunity(
            current_ems_mode=MODE_MAX_SELF,
            current_export_limit=0.01,
        )
        decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

        asyncio.run(optimizer._apply(state, decision))

        mode_call = ("select_option", optimizer.cfg.ems_mode_select, MODE_MAX_SELF)
        read_call = ("get_state_value", optimizer.cfg.ems_mode_select, "")
        close_call = ("set_number", optimizer.cfg.grid_export_limit, 0.01)
        export_call = ("set_number", optimizer.cfg.grid_export_limit, 25.0)
        read_indices = [
            index for index, call in enumerate(ha.calls) if call == read_call
        ]
        self.assertGreaterEqual(len(read_indices), 2)
        self.assertLess(read_indices[0], ha.calls.index(close_call))
        self.assertLess(ha.calls.index(close_call), ha.calls.index(mode_call))
        self.assertLess(ha.calls.index(mode_call), read_indices[-1])
        self.assertLess(read_indices[-1], ha.calls.index(export_call))

    def test_transition_into_discharge_settles_target_before_mode(self) -> None:
        ha = RecordingHA()
        optimizer = self.optimizer(ha)
        ha.state_values = {
            optimizer.cfg.ems_mode_select: MODE_MAX_SELF,
            optimizer.cfg.grid_export_limit: 25.0,
        }
        state = self.state(
            self.FIXED_AFTERNOON,
            battery_soc=95.0,
            available_discharge_energy_kwh=28.5,
            battery_power_sensor_kw=-0.2,
            feedin_price=1.10,
            feedin_price_cents=110.0,
            pv_kw=0.0,
            solar_power_now_kw=0.0,
            load_kw=0.0,
            ess_max_discharge_kw=12.0,
            current_export_limit=25.0,
            current_ems_mode=MODE_MAX_SELF,
        )
        decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

        self.assertEqual(MODE_CMD_DISCHARGE_PV, decision.ems_mode)
        self.assertEqual(12.0, decision.export_limit)
        self.assertEqual(0.0, decision.import_limit)
        self.assertEqual(25.0, decision.pv_max_power_limit)
        self.assertEqual(25.0, decision.ess_charge_limit)
        self.assertEqual(25.0, decision.ess_discharge_limit)

        asyncio.run(optimizer._apply(state, decision))

        export_call = ("set_number", optimizer.cfg.grid_export_limit, 12.0)
        read_call = ("get_state_value", optimizer.cfg.grid_export_limit, None)
        mode_call = (
            "select_option",
            optimizer.cfg.ems_mode_select,
            MODE_CMD_DISCHARGE_PV,
        )
        self.assertLess(ha.calls.index(export_call), ha.calls.index(read_call))
        self.assertLess(ha.calls.index(read_call), ha.calls.index(mode_call))

    def test_transition_out_of_discharge_requests_msc_before_export_close(self) -> None:
        ha = RecordingHA()
        optimizer = self.optimizer(ha)
        ha.state_values = {
            optimizer.cfg.ems_mode_select: MODE_CMD_DISCHARGE_PV,
            optimizer.cfg.grid_export_limit: 12.0,
        }
        state = self.state(
            self.FIXED_AFTERNOON,
            battery_soc=95.0,
            available_discharge_energy_kwh=28.5,
            feedin_price=0.0,
            feedin_price_cents=0.0,
            current_ems_mode=MODE_CMD_DISCHARGE_PV,
            current_export_limit=12.0,
        )
        decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

        self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
        self.assertEqual(0.0, decision.export_limit)
        self.assertEqual(0.0, decision.import_limit)
        self.assertEqual(25.0, decision.pv_max_power_limit)
        self.assertEqual(25.0, decision.ess_charge_limit)
        self.assertEqual(25.0, decision.ess_discharge_limit)
        self.assertEqual("blocked_or_zero", decision.trace_values["export_branch"])

        asyncio.run(optimizer._apply(state, decision))

        mode_call = ("select_option", optimizer.cfg.ems_mode_select, MODE_MAX_SELF)
        close_call = ("set_number", optimizer.cfg.grid_export_limit, 0.01)
        self.assertLess(ha.calls.index(mode_call), ha.calls.index(close_call))

    def test_next_observed_cycle_recovers_to_closed_msc(self) -> None:
        optimizer = self.optimizer()
        first_state = self.state(
            self.FIXED_AFTERNOON,
            battery_soc=95.0,
            available_discharge_energy_kwh=28.5,
            feedin_price=0.0,
            feedin_price_cents=0.0,
            current_ems_mode=MODE_CMD_DISCHARGE_PV,
            current_export_limit=12.0,
        )
        first = self.decide(optimizer, first_state, self.FIXED_AFTERNOON)
        optimizer._last_decision = first
        second_state = self.state(
            self.FIXED_AFTERNOON,
            battery_soc=95.0,
            available_discharge_energy_kwh=28.5,
            feedin_price=0.0,
            feedin_price_cents=0.0,
            current_ems_mode=MODE_MAX_SELF,
            ems_mode_observed=True,
            current_export_limit=0.01,
        )

        second = self.decide(optimizer, second_state, self.FIXED_AFTERNOON)

        self.assertEqual(MODE_MAX_SELF, second.ems_mode)
        self.assertEqual(0.0, second.export_limit)
        self.assertEqual(0.0, second.import_limit)
        self.assertEqual(25.0, second.pv_max_power_limit)
        self.assertEqual(25.0, second.ess_charge_limit)
        self.assertEqual(25.0, second.ess_discharge_limit)
        self.assertEqual("blocked_or_zero", second.trace_values["export_branch"])


if __name__ == "__main__":
    unittest.main()
