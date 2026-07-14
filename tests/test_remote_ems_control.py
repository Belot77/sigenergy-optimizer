from __future__ import annotations

import asyncio
import os
import tempfile
import unittest

from app.config import Settings
from app.models import Decision, SolarState
from app.optimizer import MODE_MAX_SELF, SigEnergyOptimizer


REAL_CONTROL_SWITCH = "switch.sigen_plant_remote_ems_controlled_by_home_assistant"


class _RemoteEMSRecordingHA:
    def __init__(self, states: dict[str, dict] | None = None) -> None:
        self.states = states or {}
        self.calls: list[tuple[str, str, object]] = []

    async def bulk_states(self, entity_ids: list[str]) -> dict[str, dict]:
        return {entity_id: self.states[entity_id] for entity_id in entity_ids if entity_id in self.states}

    async def turn_on(self, entity_id: str) -> bool:
        self.calls.append(("turn_on", entity_id, True))
        return True

    async def select_option(self, entity_id: str, value: str) -> bool:
        self.calls.append(("select_option", entity_id, value))
        return True

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


if __name__ == "__main__":
    unittest.main()
