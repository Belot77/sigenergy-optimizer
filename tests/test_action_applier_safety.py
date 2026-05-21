from __future__ import annotations

import os
import tempfile
import unittest

from app.action_applier import apply_decision
from app.config import Settings
from app.models import Decision, SolarState
from app.optimizer import MODE_MAX_SELF, SigEnergyOptimizer


class _FakeHA:
    def __init__(self) -> None:
        self.fail_select_for: set[str] = set()
        self.fail_set_number_for: set[str] = set()
        self.select_calls: list[tuple[str, str]] = []
        self.number_calls: list[tuple[str, float]] = []
        self.input_text_calls: list[tuple[str, str]] = []
        self.input_number_calls: list[tuple[str, float]] = []
        self.turn_on_calls: list[str] = []

    async def select_option(self, entity_id: str, value: str) -> bool:
        self.select_calls.append((entity_id, value))
        return entity_id not in self.fail_select_for

    async def set_number(self, entity_id: str, value: float) -> bool:
        self.number_calls.append((entity_id, float(value)))
        return entity_id not in self.fail_set_number_for

    async def set_input_text(self, entity_id: str, value: str) -> bool:
        self.input_text_calls.append((entity_id, value))
        return True

    async def set_input_number(self, entity_id: str, value: float) -> bool:
        self.input_number_calls.append((entity_id, float(value)))
        return True

    async def turn_on(self, entity_id: str) -> bool:
        self.turn_on_calls.append(entity_id)
        return True


class ActionApplierSafetyTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._optimizers: list[SigEnergyOptimizer] = []
        self._old_db = os.environ.get("STATE_DB_PATH")
        os.environ["STATE_DB_PATH"] = os.path.join(self._tmp.name, "state.db")

    def tearDown(self) -> None:
        for opt in self._optimizers:
            opt._state_store.close()
        if self._old_db is None:
            os.environ.pop("STATE_DB_PATH", None)
        else:
            os.environ["STATE_DB_PATH"] = self._old_db
        self._tmp.cleanup()

    def _make_optimizer(self, ha: _FakeHA) -> SigEnergyOptimizer:
        optimizer = SigEnergyOptimizer(
            ha,
            Settings(
                ems_mode_select="select.ems_mode",
                grid_export_limit="number.grid_export_limit",
                grid_import_limit="number.grid_import_limit",
                ess_max_discharging_limit="number.ess_discharge_limit",
                ess_max_charging_limit="number.ess_charge_limit",
                pv_max_power_limit="number.pv_max_power_limit",
                reason_text_helper="input_text.sigenergy_reason",
                min_soc_to_sunrise_helper="input_number.min_soc",
                ha_control_switch="switch.ha_control",
            ),
        )
        self._optimizers.append(optimizer)
        return optimizer

    @staticmethod
    def _state(**overrides) -> SolarState:
        defaults = {
            "ha_control_enabled": True,
            "sigenergy_mode": "Automated",
            "current_ems_mode": MODE_MAX_SELF,
            "current_export_limit": 0.01,
            "current_import_limit": 0.01,
            "current_pv_max_power_limit": 25.0,
            "current_ess_charge_limit": 6.0,
            "current_ess_discharge_limit": 7.0,
        }
        defaults.update(overrides)
        return SolarState(**defaults)

    @staticmethod
    def _decision(**overrides) -> Decision:
        defaults = {
            "ems_mode": "Command Discharging (PV First)",
            "export_limit": 5.0,
            "import_limit": 4.0,
            "pv_max_power_limit": 25.0,
            "ess_charge_limit": 6.0,
            "ess_discharge_limit": 7.0,
            "outcome_reason": "test decision",
            "min_soc_to_sunrise": 15.0,
        }
        defaults.update(overrides)
        return Decision(**defaults)

    def _assert_safe_fallback_calls(self, optimizer: SigEnergyOptimizer, ha: _FakeHA) -> None:
        self.assertIn((optimizer.cfg.ems_mode_select, MODE_MAX_SELF), ha.select_calls)
        self.assertIn((optimizer.cfg.grid_export_limit, 0.01), ha.number_calls)
        self.assertIn((optimizer.cfg.grid_import_limit, 0.01), ha.number_calls)
        self.assertIn((optimizer.cfg.ess_max_discharging_limit, 0.01), ha.number_calls)

    async def test_safe_fallback_when_ems_mode_write_fails(self) -> None:
        ha = _FakeHA()
        optimizer = self._make_optimizer(ha)
        ha.fail_select_for.add(optimizer.cfg.ems_mode_select)

        state = self._state(current_ems_mode=MODE_MAX_SELF)
        decision = self._decision(ems_mode="Command Charging (Grid First)")

        await apply_decision(optimizer, state, decision, MODE_MAX_SELF)

        self._assert_safe_fallback_calls(optimizer, ha)
        self.assertEqual(ha.input_text_calls, [])
        self.assertEqual(ha.input_number_calls, [])

    async def test_safe_fallback_when_export_limit_write_fails(self) -> None:
        ha = _FakeHA()
        optimizer = self._make_optimizer(ha)
        ha.fail_set_number_for.add(optimizer.cfg.grid_export_limit)

        state = self._state(current_ems_mode="Command Discharging (PV First)", current_export_limit=0.01)
        decision = self._decision(ems_mode="Command Discharging (PV First)", export_limit=5.0)

        await apply_decision(optimizer, state, decision, MODE_MAX_SELF)

        self._assert_safe_fallback_calls(optimizer, ha)

    async def test_safe_fallback_when_import_limit_write_fails(self) -> None:
        ha = _FakeHA()
        optimizer = self._make_optimizer(ha)
        ha.fail_set_number_for.add(optimizer.cfg.grid_import_limit)

        state = self._state(
            current_ems_mode="Command Discharging (PV First)",
            current_export_limit=5.0,
            current_import_limit=0.01,
        )
        decision = self._decision(
            ems_mode="Command Discharging (PV First)",
            export_limit=5.0,
            import_limit=4.0,
        )

        await apply_decision(optimizer, state, decision, MODE_MAX_SELF)

        self._assert_safe_fallback_calls(optimizer, ha)

    async def test_safe_fallback_when_discharge_limit_write_fails(self) -> None:
        ha = _FakeHA()
        optimizer = self._make_optimizer(ha)
        ha.fail_set_number_for.add(optimizer.cfg.ess_max_discharging_limit)

        state = self._state(
            current_ems_mode="Command Discharging (PV First)",
            current_export_limit=5.0,
            current_import_limit=4.0,
        )
        decision = self._decision(
            ems_mode="Command Discharging (PV First)",
            export_limit=5.0,
            import_limit=4.0,
            ess_discharge_limit=7.0,
        )

        await apply_decision(optimizer, state, decision, MODE_MAX_SELF)

        self._assert_safe_fallback_calls(optimizer, ha)


if __name__ == "__main__":
    unittest.main()