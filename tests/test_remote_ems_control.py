from __future__ import annotations

import asyncio
import os
import tempfile
import unittest

from app.config import Settings
from app.models import Decision, SolarState
from app.optimizer import MODE_CMD_CHARGE_PV, MODE_MAX_SELF, SigEnergyOptimizer


REAL_CONTROL_SWITCH = "switch.sigen_plant_remote_ems_controlled_by_home_assistant"


class _RemoteEMSRecordingHA:
    def __init__(
        self,
        states: dict[str, dict] | None = None,
        *,
        select_option_result: bool = True,
    ) -> None:
        self.states = states or {}
        self.select_option_result = select_option_result
        self.calls: list[tuple[str, str, object]] = []

    async def bulk_states(self, entity_ids: list[str]) -> dict[str, dict]:
        return {entity_id: self.states[entity_id] for entity_id in entity_ids if entity_id in self.states}

    async def turn_on(self, entity_id: str) -> bool:
        self.calls.append(("turn_on", entity_id, True))
        return True

    async def select_option(self, entity_id: str, value: str) -> bool:
        self.calls.append(("select_option", entity_id, value))
        return self.select_option_result

    async def set_number(self, entity_id: str, value: float) -> bool:
        self.calls.append(("set_number", entity_id, value))
        return True

    async def set_input_text(self, entity_id: str, value: str) -> bool:
        self.calls.append(("set_input_text", entity_id, value))
        return True

    async def set_input_number(self, entity_id: str, value: float) -> bool:
        self.calls.append(("set_input_number", entity_id, value))
        return True


class RemoteEMSControlTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._optimizers: list[SigEnergyOptimizer] = []
        self._old_state_db_path = os.environ.get("STATE_DB_PATH")
        os.environ["STATE_DB_PATH"] = os.path.join(self._tmp.name, "state.db")

    def tearDown(self) -> None:
        for optimizer in self._optimizers:
            optimizer._state_store.close()
        if self._old_state_db_path is None:
            os.environ.pop("STATE_DB_PATH", None)
        else:
            os.environ["STATE_DB_PATH"] = self._old_state_db_path
        self._tmp.cleanup()

    def _optimizer(self, ha: _RemoteEMSRecordingHA, **overrides: object) -> SigEnergyOptimizer:
        values: dict[str, object] = {
            "ha_control_switch": REAL_CONTROL_SWITCH,
            "ess_max_charging_limit": "",
            "ess_max_discharging_limit": "",
        }
        values.update(overrides)
        optimizer = SigEnergyOptimizer(ha, Settings(**values))
        self._optimizers.append(optimizer)
        return optimizer

    @staticmethod
    def _state(**overrides: object) -> SolarState:
        state = SolarState(
            current_ems_mode=MODE_MAX_SELF,
            current_ems_mode_trusted=True,
            current_export_limit=0.01,
            current_import_limit=0.01,
            current_pv_max_power_limit=25.0,
            ha_control_enabled=False,
            ha_control_switch_available=True,
            ha_control_switch_state="off",
        )
        for key, value in overrides.items():
            setattr(state, key, value)
        return state

    @staticmethod
    def _decision(needs_control: bool = True) -> Decision:
        return Decision(
            ems_mode=MODE_MAX_SELF,
            export_limit=0.0,
            import_limit=0.0,
            pv_max_power_limit=25.0,
            needs_ha_control_switch=needs_control,
        )

    def _untrusted_ems_cycle(
        self,
        observed_ems_state: object,
        *,
        remote_ems_state: str = "on",
        select_option_result: bool = True,
    ) -> tuple[_RemoteEMSRecordingHA, SigEnergyOptimizer, SolarState]:
        ha = _RemoteEMSRecordingHA(select_option_result=select_option_result)
        optimizer = self._optimizer(
            ha,
            ess_max_charging_limit="number.test_ess_charge_limit",
            ess_max_discharging_limit="number.test_ess_discharge_limit",
        )
        cfg = optimizer.cfg
        ha.states.update(
            {
                REAL_CONTROL_SWITCH: {
                    "entity_id": REAL_CONTROL_SWITCH,
                    "state": remote_ems_state,
                    "attributes": {},
                },
                cfg.grid_export_limit: {
                    "entity_id": cfg.grid_export_limit,
                    "state": "0.01",
                    "attributes": {},
                },
                cfg.grid_import_limit: {
                    "entity_id": cfg.grid_import_limit,
                    "state": "0.01",
                    "attributes": {},
                },
                cfg.pv_max_power_limit: {
                    "entity_id": cfg.pv_max_power_limit,
                    "state": "25",
                    "attributes": {},
                },
                cfg.ess_max_charging_limit: {
                    "entity_id": cfg.ess_max_charging_limit,
                    "state": "21",
                    "attributes": {"max": 21},
                },
                cfg.ess_max_discharging_limit: {
                    "entity_id": cfg.ess_max_discharging_limit,
                    "state": "24",
                    "attributes": {"max": 24},
                },
            }
        )
        if observed_ems_state is not None:
            ha.states[cfg.ems_mode_select] = {
                "entity_id": cfg.ems_mode_select,
                "state": observed_ems_state,
                "attributes": {},
            }
        state = asyncio.run(optimizer._read_state())
        return ha, optimizer, state

    @staticmethod
    def _normal_strategy_decision(
        *,
        ems_mode: str = MODE_MAX_SELF,
        needs_ha_control_switch: bool = False,
    ) -> Decision:
        return Decision(
            ems_mode=ems_mode,
            export_limit=2.0,
            import_limit=3.0,
            pv_max_power_limit=20.0,
            ess_charge_limit=10.0,
            ess_discharge_limit=11.0,
            needs_ha_control_switch=needs_ha_control_switch,
        )

    @staticmethod
    def _sigenergy_actuator_calls(
        ha: _RemoteEMSRecordingHA,
        optimizer: SigEnergyOptimizer,
    ) -> list[tuple[str, str, object]]:
        cfg = optimizer.cfg
        actuator_entities = {
            cfg.ems_mode_select,
            cfg.grid_export_limit,
            cfg.grid_import_limit,
            cfg.pv_max_power_limit,
            cfg.ess_max_charging_limit,
            cfg.ess_max_discharging_limit,
        }
        return [call for call in ha.calls if call[1] in actuator_entities]

    def _assert_untrusted_ems_allows_only_max_self_recovery(
        self,
        observed_ems_state: object,
    ) -> None:
        ha, optimizer, state = self._untrusted_ems_cycle(observed_ems_state)

        asyncio.run(optimizer._apply(state, self._normal_strategy_decision()))

        self.assertEqual(
            self._sigenergy_actuator_calls(ha, optimizer),
            [("select_option", optimizer.cfg.ems_mode_select, MODE_MAX_SELF)],
        )

    def test_default_control_switch_uses_current_sigenergy_entity_spelling(self) -> None:
        self.assertEqual(Settings().ha_control_switch, REAL_CONTROL_SWITCH)

    def test_state_read_marks_real_on_switch_available_and_enabled(self) -> None:
        ha = _RemoteEMSRecordingHA(
            {REAL_CONTROL_SWITCH: {"entity_id": REAL_CONTROL_SWITCH, "state": "on", "attributes": {}}}
        )
        optimizer = self._optimizer(ha)

        state = asyncio.run(optimizer._read_state())

        self.assertTrue(state.ha_control_switch_available)
        self.assertTrue(state.ha_control_enabled)
        self.assertEqual(state.ha_control_switch_state, "on")

    def test_already_on_switch_does_not_receive_turn_on(self) -> None:
        ha = _RemoteEMSRecordingHA()
        optimizer = self._optimizer(ha)
        state = self._state(ha_control_enabled=True, ha_control_switch_state="on")

        asyncio.run(optimizer._apply(state, self._decision(needs_control=False)))

        self.assertFalse(any(call[0] == "turn_on" for call in ha.calls))

    def test_valid_off_switch_is_enabled_once_then_retry_is_suppressed(self) -> None:
        ha = _RemoteEMSRecordingHA()
        optimizer = self._optimizer(ha)
        state = self._state()
        decision = self._decision()

        asyncio.run(optimizer._apply(state, decision))
        asyncio.run(optimizer._apply(state, decision))

        turn_on_calls = [call for call in ha.calls if call[0] == "turn_on"]
        self.assertEqual(turn_on_calls, [("turn_on", REAL_CONTROL_SWITCH, True)])

    def test_missing_or_unavailable_switch_never_calls_turn_on_and_warning_is_throttled(self) -> None:
        ha = _RemoteEMSRecordingHA()
        optimizer = self._optimizer(ha)
        state = self._state(
            ha_control_switch_available=False,
            ha_control_switch_state="unavailable",
        )

        with self.assertLogs("app.optimizer", level="WARNING") as captured:
            asyncio.run(optimizer._apply(state, self._decision()))
            asyncio.run(optimizer._apply(state, self._decision()))

        self.assertFalse(any(call[0] == "turn_on" for call in ha.calls))
        warnings = [line for line in captured.output if "Remote EMS control switch unavailable" in line]
        self.assertEqual(len(warnings), 1)

    def test_input_boolean_helper_is_not_treated_as_remote_ems_switch(self) -> None:
        helper_entity = "input_boolean.switch_sigen_plant_remote_ems_controlled_by_home_assistant"
        ha = _RemoteEMSRecordingHA(
            {helper_entity: {"entity_id": helper_entity, "state": "off", "attributes": {}}}
        )
        optimizer = self._optimizer(ha, ha_control_switch=helper_entity)

        state = asyncio.run(optimizer._read_state())
        asyncio.run(optimizer._apply(state, self._decision()))

        self.assertFalse(state.ha_control_switch_available)
        self.assertEqual(state.ha_control_switch_state, "invalid_domain")
        self.assertFalse(any(call[0] == "turn_on" for call in ha.calls))

    def test_untrusted_ems_missing_allows_only_max_self_recovery(self) -> None:
        self._assert_untrusted_ems_allows_only_max_self_recovery(None)

    def test_untrusted_ems_unavailable_allows_only_max_self_recovery(self) -> None:
        self._assert_untrusted_ems_allows_only_max_self_recovery("unavailable")

    def test_untrusted_ems_unknown_allows_only_max_self_recovery(self) -> None:
        self._assert_untrusted_ems_allows_only_max_self_recovery("unknown")

    def test_untrusted_ems_empty_allows_only_max_self_recovery(self) -> None:
        self._assert_untrusted_ems_allows_only_max_self_recovery("")

    def test_untrusted_ems_malformed_allows_only_max_self_recovery(self) -> None:
        self._assert_untrusted_ems_allows_only_max_self_recovery("not-a-real-ems-mode")

    def test_untrusted_ems_remote_control_off_blocks_recovery_and_limits(self) -> None:
        ha, optimizer, state = self._untrusted_ems_cycle(
            "not-a-real-ems-mode",
            remote_ems_state="off",
        )

        asyncio.run(
            optimizer._apply(
                state,
                self._normal_strategy_decision(needs_ha_control_switch=True),
            )
        )

        turn_on_calls = [call for call in ha.calls if call[0] == "turn_on"]
        self.assertEqual(turn_on_calls, [("turn_on", REAL_CONTROL_SWITCH, True)])
        self.assertEqual(self._sigenergy_actuator_calls(ha, optimizer), [])

    def test_untrusted_ems_remote_control_unavailable_blocks_recovery_and_limits(self) -> None:
        ha, optimizer, state = self._untrusted_ems_cycle(
            "not-a-real-ems-mode",
            remote_ems_state="unavailable",
        )

        asyncio.run(
            optimizer._apply(
                state,
                self._normal_strategy_decision(needs_ha_control_switch=True),
            )
        )

        self.assertFalse(any(call[0] == "turn_on" for call in ha.calls))
        self.assertEqual(self._sigenergy_actuator_calls(ha, optimizer), [])

    def test_untrusted_ems_successful_recovery_call_does_not_allow_same_cycle_limits(self) -> None:
        ha, optimizer, state = self._untrusted_ems_cycle("not-a-real-ems-mode")

        asyncio.run(optimizer._apply(state, self._normal_strategy_decision()))

        actuator_calls = self._sigenergy_actuator_calls(ha, optimizer)
        self.assertIn(("select_option", optimizer.cfg.ems_mode_select, MODE_MAX_SELF), actuator_calls)
        self.assertFalse(any(call[0] == "set_number" for call in actuator_calls))

    def test_untrusted_ems_rapid_cycles_throttle_recovery_and_warning(self) -> None:
        ha, optimizer, state = self._untrusted_ems_cycle("not-a-real-ems-mode")
        decision = self._normal_strategy_decision()

        with self.assertLogs("app.optimizer", level="WARNING") as captured:
            asyncio.run(optimizer._apply(state, decision))
            asyncio.run(optimizer._apply(state, decision))

        actuator_calls = self._sigenergy_actuator_calls(ha, optimizer)
        self.assertEqual(
            actuator_calls,
            [("select_option", optimizer.cfg.ems_mode_select, MODE_MAX_SELF)],
        )
        warnings = [line for line in captured.output if "Observed EMS mode is untrusted" in line]
        self.assertEqual(len(warnings), 1)

    def test_untrusted_ems_recovery_retries_after_60_seconds(self) -> None:
        ha, optimizer, state = self._untrusted_ems_cycle("not-a-real-ems-mode")
        decision = self._normal_strategy_decision()

        asyncio.run(optimizer._apply(state, decision))
        self.assertIsNotNone(optimizer._last_ems_mode_recovery_attempt_at)
        optimizer._last_ems_mode_recovery_attempt_at -= 60.0
        asyncio.run(optimizer._apply(state, decision))

        actuator_calls = self._sigenergy_actuator_calls(ha, optimizer)
        self.assertEqual(
            actuator_calls,
            [
                ("select_option", optimizer.cfg.ems_mode_select, MODE_MAX_SELF),
                ("select_option", optimizer.cfg.ems_mode_select, MODE_MAX_SELF),
            ],
        )

    def test_untrusted_ems_failed_recovery_is_throttled_without_limit_writes(self) -> None:
        ha, optimizer, state = self._untrusted_ems_cycle(
            "not-a-real-ems-mode",
            select_option_result=False,
        )
        decision = self._normal_strategy_decision()

        with self.assertLogs("app.optimizer", level="ERROR"):
            asyncio.run(optimizer._apply(state, decision))
        asyncio.run(optimizer._apply(state, decision))

        actuator_calls = self._sigenergy_actuator_calls(ha, optimizer)
        self.assertEqual(
            actuator_calls,
            [("select_option", optimizer.cfg.ems_mode_select, MODE_MAX_SELF)],
        )

    def test_trusted_ems_observation_resets_recovery_retry_episode(self) -> None:
        ha, optimizer, state = self._untrusted_ems_cycle("not-a-real-ems-mode")
        decision = self._normal_strategy_decision()

        asyncio.run(optimizer._apply(state, decision))
        ha.states[optimizer.cfg.ems_mode_select]["state"] = MODE_CMD_CHARGE_PV
        trusted_state = asyncio.run(optimizer._read_state())
        self.assertTrue(trusted_state.current_ems_mode_trusted)
        ha.states[optimizer.cfg.ems_mode_select]["state"] = "not-a-real-ems-mode"
        new_untrusted_state = asyncio.run(optimizer._read_state())
        asyncio.run(optimizer._apply(new_untrusted_state, decision))

        recovery_calls = [
            call
            for call in self._sigenergy_actuator_calls(ha, optimizer)
            if call == ("select_option", optimizer.cfg.ems_mode_select, MODE_MAX_SELF)
        ]
        self.assertEqual(len(recovery_calls), 2)

    def test_untrusted_ems_requires_later_observed_max_self_before_normal_strategy(self) -> None:
        ha, optimizer, first_state = self._untrusted_ems_cycle("unavailable")
        first_decision = self._normal_strategy_decision()

        asyncio.run(optimizer._apply(first_state, first_decision))
        first_cycle_calls = self._sigenergy_actuator_calls(ha, optimizer)

        ha.calls.clear()
        ha.states[optimizer.cfg.ems_mode_select] = {
            "entity_id": optimizer.cfg.ems_mode_select,
            "state": MODE_MAX_SELF,
            "attributes": {},
        }
        second_state = asyncio.run(optimizer._read_state())
        second_decision = self._normal_strategy_decision(ems_mode=MODE_CMD_CHARGE_PV)
        asyncio.run(optimizer._apply(second_state, second_decision))
        second_cycle_calls = self._sigenergy_actuator_calls(ha, optimizer)

        self.assertEqual(
            first_cycle_calls,
            [("select_option", optimizer.cfg.ems_mode_select, MODE_MAX_SELF)],
        )
        self.assertIn(
            ("select_option", optimizer.cfg.ems_mode_select, MODE_CMD_CHARGE_PV),
            second_cycle_calls,
        )
        self.assertTrue(any(call[0] == "set_number" for call in second_cycle_calls))


if __name__ == "__main__":
    unittest.main()
