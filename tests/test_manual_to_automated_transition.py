from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from app.config import Settings
from app.models import Decision, SolarState
from app.optimizer import (
    MODE_CMD_CHARGE_GRID,
    MODE_CMD_CHARGE_PV,
    MODE_CMD_DISCHARGE_PV,
    MODE_MAX_SELF,
    SigEnergyOptimizer,
)


class _TransitionRecordingHA:
    def __init__(self) -> None:
        self.states: dict[str, dict] = {}
        self.calls: list[tuple[str, str, object]] = []
        self.bulk_state_reads = 0
        self.optimizer: SigEnergyOptimizer | None = None
        self.mode_helper_lock_observations: list[bool] = []
        self.mode_helper_read_lock_observations: list[bool] = []
        self.select_option_result = True
        self.select_option_results: dict[str, bool] = {}
        self.set_number_results: dict[str, bool] = {}
        self.get_state_value_exceptions: dict[str, Exception] = {}
        self.select_option_exceptions: dict[str, Exception] = {}
        self.set_number_exceptions: dict[str, Exception] = {}
        self.turn_on_exceptions: dict[str, Exception] = {}
        self.update_state_on_success = True

    def set_state(
        self,
        entity_id: str,
        state: object,
        attributes: dict | None = None,
    ) -> None:
        self.states[entity_id] = {
            "entity_id": entity_id,
            "state": str(state),
            "attributes": attributes or {},
        }

    async def bulk_states(self, entity_ids: list[str]) -> dict[str, dict]:
        self.bulk_state_reads += 1
        return {
            entity_id: self.states[entity_id]
            for entity_id in entity_ids
            if entity_id in self.states
        }

    async def get_state_value(self, entity_id: str, default: object = "") -> object:
        self.calls.append(("get_state_value", entity_id, default))
        if self.optimizer and entity_id == self.optimizer.cfg.sigenergy_mode_select:
            self.mode_helper_read_lock_observations.append(
                self.optimizer._control_lock.locked()
            )
        if exc := self.get_state_value_exceptions.get(entity_id):
            raise exc
        state = self.states.get(entity_id)
        return state.get("state", default) if state else default

    async def turn_on(self, entity_id: str) -> bool:
        self.calls.append(("turn_on", entity_id, True))
        if exc := self.turn_on_exceptions.get(entity_id):
            raise exc
        self.set_state(entity_id, "on")
        return True

    async def select_option(self, entity_id: str, value: str) -> bool:
        self.calls.append(("select_option", entity_id, value))
        if self.optimizer and entity_id == self.optimizer.cfg.sigenergy_mode_select:
            self.mode_helper_lock_observations.append(
                self.optimizer._control_lock.locked()
            )
        if exc := self.select_option_exceptions.get(entity_id):
            raise exc
        result = self.select_option_results.get(entity_id, self.select_option_result)
        if not result:
            return False
        if self.update_state_on_success:
            self.set_state(entity_id, value)
        return True

    async def set_number(self, entity_id: str, value: float) -> bool:
        self.calls.append(("set_number", entity_id, value))
        if exc := self.set_number_exceptions.get(entity_id):
            raise exc
        result = self.set_number_results.get(entity_id, True)
        if not result:
            return False
        attributes = self.states.get(entity_id, {}).get("attributes", {})
        if self.update_state_on_success:
            self.set_state(entity_id, value, attributes)
        return True

    async def set_input_text(self, entity_id: str, value: str) -> bool:
        self.calls.append(("set_input_text", entity_id, value))
        self.set_state(entity_id, value)
        return True

    async def set_input_number(self, entity_id: str, value: float) -> bool:
        self.calls.append(("set_input_number", entity_id, value))
        self.set_state(entity_id, value)
        return True


class ManualToAutomatedTransitionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._old_state_db_path = os.environ.get("STATE_DB_PATH")
        os.environ["STATE_DB_PATH"] = os.path.join(self._tmp.name, "state.db")
        self._optimizers: list[SigEnergyOptimizer] = []

    def tearDown(self) -> None:
        for optimizer in self._optimizers:
            optimizer._state_store.close()
        if self._old_state_db_path is None:
            os.environ.pop("STATE_DB_PATH", None)
        else:
            os.environ["STATE_DB_PATH"] = self._old_state_db_path
        self._tmp.cleanup()

    def _optimizer(
        self,
        *,
        ha_control_switch: str = "switch.test_remote_ems",
    ) -> tuple[_TransitionRecordingHA, SigEnergyOptimizer]:
        ha = _TransitionRecordingHA()
        cfg = Settings(
            ha_control_switch=ha_control_switch,
            ems_mode_select="select.test_ems_mode",
            grid_export_limit="number.test_grid_export_limit",
            grid_import_limit="number.test_grid_import_limit",
            pv_max_power_limit="number.test_pv_max_power_limit",
            ess_max_charging_limit="number.test_ess_charge_limit",
            ess_max_discharging_limit="number.test_ess_discharge_limit",
            sigenergy_mode_select="input_select.test_sigenergy_mode",
            reason_text_helper="input_text.test_sigenergy_reason",
            min_soc_to_sunrise_helper="input_number.test_min_soc_to_sunrise",
            ess_limit_fallback_kw=25.0,
            ess_charge_limit_value=25.0,
            ess_discharge_limit_value=25.0,
            pv_max_power_value=30.0,
        )
        optimizer = SigEnergyOptimizer(ha, cfg)
        ha.optimizer = optimizer
        self._optimizers.append(optimizer)
        self._seed_live_state(ha, optimizer)
        return ha, optimizer

    @staticmethod
    def _seed_live_state(
        ha: _TransitionRecordingHA,
        optimizer: SigEnergyOptimizer,
        *,
        helper_mode: str | None = None,
        ems_mode: str = MODE_MAX_SELF,
        remote_ems_state: str = "on",
    ) -> None:
        cfg = optimizer.cfg
        ha.set_state(
            cfg.sigenergy_mode_select,
            helper_mode or cfg.automated_option,
        )
        ha.set_state(cfg.ems_mode_select, ems_mode)
        ha.set_state(cfg.ha_control_switch, remote_ems_state)
        ha.set_state(cfg.grid_export_limit, 0.01)
        ha.set_state(cfg.grid_import_limit, 0.01)
        ha.set_state(cfg.pv_max_power_limit, 30.0)
        ha.set_state(cfg.ess_max_charging_limit, 25.0, {"max": 25.0})
        ha.set_state(cfg.ess_max_discharging_limit, 25.0, {"max": 25.0})

    @staticmethod
    def _state(**overrides: object) -> SolarState:
        state = SolarState(
            sigenergy_mode="Automated",
            current_ems_mode=MODE_MAX_SELF,
            current_ems_mode_trusted=True,
            current_export_limit=0.01,
            current_export_limit_raw="0.01",
            current_export_limit_trusted=True,
            current_import_limit=0.01,
            current_import_limit_raw="0.01",
            current_import_limit_trusted=True,
            current_pv_max_power_limit=30.0,
            current_ess_charge_limit=25.0,
            current_ess_discharge_limit=25.0,
            ha_control_enabled=True,
            ha_control_switch_available=True,
            ha_control_switch_state="on",
        )
        for key, value in overrides.items():
            setattr(state, key, value)
        return state

    @staticmethod
    def _normal_decision(
        *,
        ems_mode: str = MODE_CMD_CHARGE_PV,
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
    def _inverter_calls(
        ha: _TransitionRecordingHA,
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

    @staticmethod
    def _live_actuator_values(
        ha: _TransitionRecordingHA,
        optimizer: SigEnergyOptimizer,
    ) -> tuple[str, float, float, float, float, float]:
        cfg = optimizer.cfg
        return (
            str(ha.states[cfg.ems_mode_select]["state"]),
            float(ha.states[cfg.grid_export_limit]["state"]),
            float(ha.states[cfg.grid_import_limit]["state"]),
            float(ha.states[cfg.pv_max_power_limit]["state"]),
            float(ha.states[cfg.ess_max_charging_limit]["state"]),
            float(ha.states[cfg.ess_max_discharging_limit]["state"]),
        )

    def _enter_transition(
        self,
        ha: _TransitionRecordingHA,
        optimizer: SigEnergyOptimizer,
        *,
        previous_mode: str | None = None,
    ) -> None:
        cfg = optimizer.cfg
        mode = previous_mode or cfg.full_export_option
        optimizer._manual_mode_override = mode
        optimizer._last_state = self._state(sigenergy_mode=mode)
        ha.set_state(cfg.sigenergy_mode_select, mode)
        asyncio.run(optimizer.apply_manual_mode(cfg.automated_option))
        ha.calls.clear()

    @staticmethod
    def _run_tick_with_decision(
        optimizer: SigEnergyOptimizer,
        decision: Decision,
    ) -> None:
        with (
            patch.object(optimizer, "_decide", return_value=decision),
            patch.object(optimizer, "_record_automation_audit"),
            patch.object(optimizer, "_record_decision_trace"),
            patch.object(
                optimizer,
                "_handle_notifications",
                new=AsyncMock(),
            ),
            patch.object(
                optimizer,
                "_handle_daily_summaries",
                new=AsyncMock(),
            ),
            patch.object(optimizer, "_accumulate_history"),
            patch.object(optimizer, "_record_price_tracking"),
        ):
            asyncio.run(optimizer._tick())

    def test_apply_automated_clears_overrides_updates_cache_and_only_writes_helper_under_lock(
        self,
    ) -> None:
        ha, optimizer = self._optimizer()
        cfg = optimizer.cfg
        cached_state = self._state(
            sigenergy_mode=cfg.full_export_option,
            current_ems_mode=MODE_CMD_DISCHARGE_PV,
            current_export_limit=25.0,
            current_import_limit=0.01,
            current_pv_max_power_limit=30.0,
            current_ess_charge_limit=25.0,
            current_ess_discharge_limit=25.0,
        )
        optimizer._last_state = cached_state
        optimizer._manual_mode_override = cfg.full_export_option
        optimizer._manual_ess_charge_override_kw = 7.0
        optimizer._manual_ess_discharge_override_kw = 8.0

        asyncio.run(optimizer.apply_manual_mode(cfg.automated_option))

        self.assertEqual(
            ha.calls,
            [("select_option", cfg.sigenergy_mode_select, cfg.automated_option)],
        )
        self.assertEqual(ha.mode_helper_lock_observations, [True])
        self.assertIsNone(optimizer._manual_mode_override)
        self.assertIsNone(optimizer._manual_ess_charge_override_kw)
        self.assertIsNone(optimizer._manual_ess_discharge_override_kw)
        self.assertEqual(cached_state.sigenergy_mode, cfg.automated_option)
        self.assertEqual(cached_state.current_ems_mode, MODE_CMD_DISCHARGE_PV)
        self.assertEqual(cached_state.current_export_limit, 25.0)
        self.assertEqual(self._inverter_calls(ha, optimizer), [])
        self.assertEqual(optimizer._automated_transition.phase, "CONTAINING_GRID")
        self.assertEqual(
            optimizer._automated_transition.previous_mode,
            cfg.full_export_option,
        )

    def test_apply_automated_helper_failure_preserves_manual_state_and_targets(
        self,
    ) -> None:
        ha, optimizer = self._optimizer()
        cfg = optimizer.cfg
        cached_state = self._state(
            sigenergy_mode=cfg.full_export_option,
            current_ems_mode=MODE_CMD_DISCHARGE_PV,
            current_export_limit=14.0,
            current_import_limit=0.02,
            current_pv_max_power_limit=18.0,
            current_ess_charge_limit=9.0,
            current_ess_discharge_limit=10.0,
        )
        optimizer._last_state = cached_state
        optimizer._manual_mode_override = cfg.full_export_option
        optimizer._manual_ess_charge_override_kw = 7.0
        optimizer._manual_ess_discharge_override_kw = 8.0
        ha.set_state(cfg.sigenergy_mode_select, cfg.full_export_option)
        ha.set_state(cfg.ems_mode_select, MODE_CMD_DISCHARGE_PV)
        ha.set_state(cfg.grid_export_limit, 14.0)
        ha.set_state(cfg.grid_import_limit, 0.02)
        ha.set_state(cfg.pv_max_power_limit, 18.0)
        ha.set_state(cfg.ess_max_charging_limit, 9.0, {"max": 25.0})
        ha.set_state(cfg.ess_max_discharging_limit, 10.0, {"max": 25.0})
        targets_before = self._live_actuator_values(ha, optimizer)
        ha.select_option_result = False

        with self.assertRaises(RuntimeError):
            asyncio.run(optimizer.apply_manual_mode(cfg.automated_option))

        self.assertEqual(
            ha.calls,
            [("select_option", cfg.sigenergy_mode_select, cfg.automated_option)],
        )
        self.assertEqual(optimizer._manual_mode_override, cfg.full_export_option)
        self.assertEqual(optimizer._manual_ess_charge_override_kw, 7.0)
        self.assertEqual(optimizer._manual_ess_discharge_override_kw, 8.0)
        self.assertEqual(cached_state.sigenergy_mode, cfg.full_export_option)
        self.assertEqual(self._inverter_calls(ha, optimizer), [])
        self.assertEqual(
            self._live_actuator_values(ha, optimizer),
            targets_before,
        )
        self.assertEqual(optimizer._automated_transition.phase, "IDLE")

    def test_apply_automated_before_first_tick_manual_helper_starts_containment(
        self,
    ) -> None:
        ha, optimizer = self._optimizer()
        cfg = optimizer.cfg
        optimizer._manual_mode_override = None
        optimizer._last_state = None
        ha.set_state(cfg.sigenergy_mode_select, cfg.full_export_option)
        ha.set_state(cfg.ems_mode_select, MODE_CMD_CHARGE_PV)
        ha.set_state(cfg.grid_export_limit, 9.0)
        ha.set_state(cfg.grid_import_limit, 8.0)

        asyncio.run(optimizer.apply_manual_mode(cfg.automated_option))

        self.assertEqual(
            ha.calls,
            [
                ("get_state_value", cfg.sigenergy_mode_select, None),
                ("select_option", cfg.sigenergy_mode_select, cfg.automated_option),
            ],
        )
        self.assertEqual(ha.mode_helper_read_lock_observations, [True])
        self.assertEqual(ha.mode_helper_lock_observations, [True])
        self.assertEqual(self._inverter_calls(ha, optimizer), [])
        self.assertEqual(optimizer._automated_transition.phase, "CONTAINING_GRID")
        self.assertEqual(
            optimizer._automated_transition.previous_mode,
            cfg.full_export_option,
        )

        ha.calls.clear()
        self._run_tick_with_decision(
            optimizer,
            self._normal_decision(ems_mode=MODE_CMD_CHARGE_PV),
        )

        self.assertEqual(
            self._inverter_calls(ha, optimizer),
            [
                ("set_number", cfg.grid_export_limit, cfg.block_flow_limit_value),
                ("set_number", cfg.grid_import_limit, cfg.block_flow_limit_value),
            ],
        )
        self.assertEqual(optimizer._automated_transition.phase, "CONTAINING_GRID")

    def test_apply_automated_rejects_untrusted_fresh_prior_helper_state(
        self,
    ) -> None:
        cases = (
            ("unknown", "unknown", False),
            ("unavailable", "unavailable", False),
            ("none", "none", False),
            ("empty", "", False),
            ("unexpected helper option", "Unexpected Mode", False),
            ("missing helper entity", None, False),
            ("helper read exception", None, True),
        )
        for label, helper_value, raises_on_read in cases:
            with self.subTest(prior_helper=label):
                ha, optimizer = self._optimizer()
                cfg = optimizer.cfg
                cached_state = self._state(sigenergy_mode="untrusted-cached-mode")
                optimizer._last_state = cached_state
                optimizer._manual_mode_override = "untrusted-internal-mode"
                optimizer._manual_ess_charge_override_kw = 7.0
                optimizer._manual_ess_discharge_override_kw = 8.0
                if raises_on_read:
                    ha.get_state_value_exceptions[cfg.sigenergy_mode_select] = RuntimeError(
                        "helper read failed"
                    )
                elif helper_value is None:
                    ha.states.pop(cfg.sigenergy_mode_select, None)
                else:
                    ha.set_state(cfg.sigenergy_mode_select, helper_value)

                with self.assertRaises(RuntimeError):
                    asyncio.run(optimizer.apply_manual_mode(cfg.automated_option))

                self.assertEqual(
                    ha.calls,
                    [("get_state_value", cfg.sigenergy_mode_select, None)],
                )
                self.assertEqual(ha.mode_helper_read_lock_observations, [True])
                self.assertIs(optimizer._last_state, cached_state)
                self.assertEqual(cached_state.sigenergy_mode, "untrusted-cached-mode")
                self.assertEqual(
                    optimizer._manual_mode_override,
                    "untrusted-internal-mode",
                )
                self.assertEqual(optimizer._manual_ess_charge_override_kw, 7.0)
                self.assertEqual(optimizer._manual_ess_discharge_override_kw, 8.0)
                self.assertEqual(optimizer._automated_transition.phase, "IDLE")
                self.assertEqual(self._inverter_calls(ha, optimizer), [])

    def test_apply_automated_with_fresh_helper_already_automated_is_idempotent(
        self,
    ) -> None:
        ha, optimizer = self._optimizer()
        cfg = optimizer.cfg
        optimizer._manual_mode_override = None
        optimizer._last_state = None

        asyncio.run(optimizer.apply_manual_mode(cfg.automated_option))

        self.assertEqual(
            ha.calls,
            [
                ("get_state_value", cfg.sigenergy_mode_select, None),
                ("select_option", cfg.sigenergy_mode_select, cfg.automated_option),
            ],
        )
        self.assertEqual(ha.mode_helper_read_lock_observations, [True])
        self.assertEqual(ha.mode_helper_lock_observations, [True])
        self.assertEqual(optimizer._automated_transition.phase, "IDLE")
        self.assertFalse(optimizer._startup_automated_transition_checked)
        self.assertEqual(self._inverter_calls(ha, optimizer), [])

    def test_each_manual_mode_exit_leaves_current_inverter_targets_unchanged(self) -> None:
        cases = (
            (
                "force full export",
                "full_export_option",
                (MODE_CMD_DISCHARGE_PV, 25.0, 0.01, 30.0, 25.0, 25.0),
            ),
            (
                "force full import",
                "full_import_option",
                (MODE_CMD_CHARGE_GRID, 0.01, 25.0, 30.0, 25.0, 25.0),
            ),
            (
                "force full import plus pv",
                "full_import_pv_option",
                (MODE_CMD_CHARGE_PV, 0.01, 25.0, 30.0, 25.0, 25.0),
            ),
            (
                "prevent import and export",
                "block_flow_option",
                (MODE_MAX_SELF, 0.01, 0.01, 30.0, 25.0, 25.0),
            ),
            (
                "manual",
                "manual_option",
                (MODE_CMD_DISCHARGE_PV, 7.0, 8.0, 19.0, 9.0, 10.0),
            ),
        )

        for label, config_key, expected_residue in cases:
            with self.subTest(mode=label):
                ha, optimizer = self._optimizer()
                cfg = optimizer.cfg
                mode = str(getattr(cfg, config_key))
                if mode == cfg.manual_option:
                    ha.set_state(cfg.ems_mode_select, expected_residue[0])
                    ha.set_state(cfg.grid_export_limit, expected_residue[1])
                    ha.set_state(cfg.grid_import_limit, expected_residue[2])
                    ha.set_state(cfg.pv_max_power_limit, expected_residue[3])
                    ha.set_state(
                        cfg.ess_max_charging_limit,
                        expected_residue[4],
                        {"max": 25.0},
                    )
                    ha.set_state(
                        cfg.ess_max_discharging_limit,
                        expected_residue[5],
                        {"max": 25.0},
                    )

                asyncio.run(optimizer.apply_manual_mode(mode))
                self.assertEqual(
                    self._live_actuator_values(ha, optimizer),
                    expected_residue,
                )

                ha.calls.clear()
                residue_before_exit = self._live_actuator_values(ha, optimizer)
                asyncio.run(optimizer.apply_manual_mode(cfg.automated_option))

                self.assertEqual(
                    ha.calls,
                    [("select_option", cfg.sigenergy_mode_select, cfg.automated_option)],
                )
                self.assertEqual(
                    self._live_actuator_values(ha, optimizer),
                    residue_before_exit,
                )
                self.assertEqual(
                    optimizer._automated_transition.phase,
                    "CONTAINING_GRID",
                )

    def test_first_tick_after_each_manual_exit_uses_normal_decision_without_neutral_rewrite(
        self,
    ) -> None:
        mode_keys = (
            "full_export_option",
            "full_import_option",
            "full_import_pv_option",
            "block_flow_option",
            "manual_option",
        )

        for mode_key in mode_keys:
            with self.subTest(mode=mode_key):
                ha, optimizer = self._optimizer()
                cfg = optimizer.cfg
                prior_mode = str(getattr(cfg, mode_key))
                optimizer._manual_mode_override = prior_mode
                optimizer._last_state = self._state(sigenergy_mode=prior_mode)
                asyncio.run(optimizer.apply_manual_mode(cfg.automated_option))

                fresh_state = self._state(
                    sigenergy_mode=cfg.automated_option,
                    current_ems_mode=MODE_CMD_DISCHARGE_PV,
                )
                normal_decision = self._normal_decision(
                    ems_mode=MODE_CMD_CHARGE_GRID
                )
                with (
                    patch.object(
                        optimizer,
                        "_read_state",
                        new=AsyncMock(return_value=fresh_state),
                    ) as read_mock,
                    patch.object(
                        optimizer,
                        "_decide",
                        return_value=normal_decision,
                    ) as decide_mock,
                    patch.object(optimizer, "_apply", new=AsyncMock()) as apply_mock,
                    patch.object(optimizer, "_record_automation_audit"),
                    patch.object(optimizer, "_record_decision_trace"),
                    patch.object(
                        optimizer,
                        "_handle_notifications",
                        new=AsyncMock(),
                    ),
                    patch.object(
                        optimizer,
                        "_handle_daily_summaries",
                        new=AsyncMock(),
                    ),
                    patch.object(optimizer, "_accumulate_history"),
                    patch.object(optimizer, "_record_price_tracking"),
                ):
                    asyncio.run(optimizer._tick())

                read_mock.assert_awaited_once_with()
                decide_mock.assert_called_once_with(fresh_state)
                apply_mock.assert_awaited_once_with(fresh_state, normal_decision)
                self.assertIs(optimizer.last_decision, normal_decision)
                self.assertEqual(normal_decision.ems_mode, MODE_CMD_CHARGE_GRID)

    def test_supported_manual_ems_observations_do_not_start_recovery_on_automated_resume(
        self,
    ) -> None:
        supported_modes = (
            MODE_CMD_CHARGE_PV,
            MODE_CMD_CHARGE_GRID,
            MODE_CMD_DISCHARGE_PV,
            MODE_MAX_SELF,
        )

        for ems_mode in supported_modes:
            with self.subTest(ems_mode=ems_mode):
                ha, optimizer = self._optimizer()
                cfg = optimizer.cfg
                optimizer._manual_mode_override = cfg.manual_option
                optimizer._last_state = self._state(
                    sigenergy_mode=cfg.manual_option,
                    current_ems_mode=ems_mode,
                )
                asyncio.run(optimizer.apply_manual_mode(cfg.automated_option))
                ha.set_state(cfg.ems_mode_select, ems_mode)
                state = asyncio.run(optimizer._read_state())
                ha.calls.clear()

                self.assertTrue(state.current_ems_mode_trusted)
                asyncio.run(
                    optimizer._apply(
                        state,
                        self._normal_decision(ems_mode=ems_mode),
                    )
                )

                self.assertFalse(optimizer._ems_mode_recovery_required)
                self.assertFalse(
                    any(call[0] == "select_option" for call in ha.calls)
                )
                self.assertTrue(
                    any(call[0] == "set_number" for call in ha.calls)
                )

    def test_existing_recovery_episode_survives_automated_until_max_self_is_observed(
        self,
    ) -> None:
        ha, optimizer = self._optimizer(
            ha_control_switch="switch.test_remote_ems"
        )
        cfg = optimizer.cfg
        optimizer._manual_mode_override = cfg.full_export_option
        optimizer._last_state = self._state(
            sigenergy_mode=cfg.full_export_option,
            current_ems_mode="not-a-real-ems-mode",
            current_ems_mode_trusted=False,
        )
        ha.set_state(cfg.sigenergy_mode_select, cfg.full_export_option)
        ha.set_state(cfg.ems_mode_select, "not-a-real-ems-mode")
        asyncio.run(optimizer._read_state())
        self.assertTrue(optimizer._ems_mode_recovery_required)

        asyncio.run(optimizer.apply_manual_mode(cfg.automated_option))
        self.assertTrue(optimizer._ems_mode_recovery_required)

        ha.set_state(cfg.ems_mode_select, MODE_CMD_DISCHARGE_PV)
        command_state = asyncio.run(optimizer._read_state())
        self.assertTrue(command_state.current_ems_mode_trusted)
        self.assertTrue(optimizer._ems_mode_recovery_required)
        ha.calls.clear()

        asyncio.run(
            optimizer._apply(
                command_state,
                self._normal_decision(ems_mode=MODE_CMD_CHARGE_PV),
            )
        )
        self.assertEqual(
            self._inverter_calls(ha, optimizer),
            [("select_option", cfg.ems_mode_select, MODE_MAX_SELF)],
        )
        self.assertTrue(optimizer._ems_mode_recovery_required)

        ha.set_state(cfg.ems_mode_select, MODE_MAX_SELF)
        recovered_state = asyncio.run(optimizer._read_state())
        self.assertFalse(optimizer._ems_mode_recovery_required)
        ha.calls.clear()
        asyncio.run(
            optimizer._apply(
                recovered_state,
                self._normal_decision(ems_mode=MODE_CMD_CHARGE_PV),
            )
        )

        recovered_calls = self._inverter_calls(ha, optimizer)
        self.assertEqual(
            recovered_calls,
            [("select_option", cfg.ems_mode_select, MODE_CMD_CHARGE_PV)],
        )
        self.assertEqual(
            optimizer._automated_transition.phase,
            "WAITING_FOR_TARGET_EMS",
        )

        settled_state = self._state(current_ems_mode=MODE_CMD_CHARGE_PV)
        ha.calls.clear()
        asyncio.run(
            optimizer._apply(
                settled_state,
                self._normal_decision(ems_mode=MODE_CMD_CHARGE_PV),
            )
        )

        self.assertEqual(optimizer._automated_transition.phase, "IDLE")
        self.assertTrue(
            any(call[0] == "set_number" for call in self._inverter_calls(ha, optimizer))
        )

    def test_first_tick_reads_fresh_ha_state_before_normal_automated_decision(self) -> None:
        ha, optimizer = self._optimizer()
        cfg = optimizer.cfg
        optimizer._manual_mode_override = cfg.full_export_option
        optimizer._last_state = self._state(
            sigenergy_mode=cfg.full_export_option,
            current_ems_mode=MODE_CMD_DISCHARGE_PV,
            current_export_limit=25.0,
        )
        asyncio.run(optimizer.apply_manual_mode(cfg.automated_option))
        self.assertEqual(optimizer.last_state.current_export_limit, 25.0)

        ha.set_state(cfg.ems_mode_select, MODE_CMD_CHARGE_GRID)
        ha.set_state(cfg.grid_export_limit, 6.0)
        ha.set_state(cfg.grid_import_limit, 7.0)
        reads_before_tick = ha.bulk_state_reads

        with (
            patch.object(optimizer, "_decide", wraps=optimizer._decide) as decide_spy,
            patch.object(optimizer, "_apply", new=AsyncMock()) as apply_mock,
            patch.object(optimizer, "_record_automation_audit"),
            patch.object(optimizer, "_record_decision_trace"),
            patch.object(
                optimizer,
                "_handle_notifications",
                new=AsyncMock(),
            ),
            patch.object(
                optimizer,
                "_handle_daily_summaries",
                new=AsyncMock(),
            ),
            patch.object(optimizer, "_accumulate_history"),
            patch.object(optimizer, "_record_price_tracking"),
        ):
            asyncio.run(optimizer._tick())

        self.assertEqual(ha.bulk_state_reads, reads_before_tick + 1)
        fresh_state = decide_spy.call_args.args[0]
        self.assertEqual(fresh_state.sigenergy_mode, cfg.automated_option)
        self.assertEqual(fresh_state.current_ems_mode, MODE_CMD_CHARGE_GRID)
        self.assertEqual(fresh_state.current_export_limit, 6.0)
        self.assertEqual(fresh_state.current_import_limit, 7.0)
        self.assertNotIn("Manual mode active", optimizer.last_decision.outcome_reason)
        apply_mock.assert_awaited_once_with(fresh_state, optimizer.last_decision)

    def test_trusted_mode_change_writes_ems_then_dependent_limits_without_observed_confirmation(
        self,
    ) -> None:
        ha, optimizer = self._optimizer()
        cfg = optimizer.cfg
        state = self._state(
            current_ems_mode=MODE_CMD_DISCHARGE_PV,
            current_export_limit=0.01,
            current_import_limit=0.01,
            current_pv_max_power_limit=30.0,
            current_ess_charge_limit=25.0,
            current_ess_discharge_limit=25.0,
        )

        asyncio.run(
            optimizer._apply(
                state,
                self._normal_decision(ems_mode=MODE_CMD_CHARGE_PV),
            )
        )

        self.assertEqual(
            self._inverter_calls(ha, optimizer),
            [
                ("select_option", cfg.ems_mode_select, MODE_CMD_CHARGE_PV),
                ("set_number", cfg.grid_export_limit, 2.0),
                ("set_number", cfg.grid_import_limit, 3.0),
                ("set_number", cfg.ess_max_charging_limit, 10.0),
                ("set_number", cfg.ess_max_discharging_limit, 11.0),
                ("set_number", cfg.pv_max_power_limit, 20.0),
            ],
        )
        self.assertFalse(
            any(call[0] == "get_state_value" for call in ha.calls)
        )
        self.assertEqual(ha.bulk_state_reads, 0)

    def test_remote_ems_off_transition_requests_enable_only(self) -> None:
        ha, optimizer = self._optimizer()
        cfg = optimizer.cfg
        optimizer._manual_mode_override = cfg.full_export_option
        optimizer._last_state = self._state(sigenergy_mode=cfg.full_export_option)
        asyncio.run(optimizer.apply_manual_mode(cfg.automated_option))
        ha.calls.clear()

        state = self._state(
            ha_control_enabled=False,
            ha_control_switch_available=True,
            ha_control_switch_state="off",
        )
        asyncio.run(
            optimizer._apply(
                state,
                self._normal_decision(needs_ha_control_switch=True),
            )
        )

        self.assertEqual(ha.calls, [("turn_on", cfg.ha_control_switch, True)])
        self.assertEqual(self._inverter_calls(ha, optimizer), [])

    def test_remote_ems_unavailable_or_invalid_transition_blocks_all_writes(self) -> None:
        cases = (
            ("unavailable", "switch.test_remote_ems", "unavailable"),
            ("invalid", "input_boolean.test_remote_ems", "invalid_domain"),
        )

        for label, entity_id, state_label in cases:
            with self.subTest(remote_ems=label):
                ha, optimizer = self._optimizer(ha_control_switch=entity_id)
                cfg = optimizer.cfg
                optimizer._manual_mode_override = cfg.full_export_option
                optimizer._last_state = self._state(
                    sigenergy_mode=cfg.full_export_option
                )
                asyncio.run(optimizer.apply_manual_mode(cfg.automated_option))
                if label == "unavailable":
                    ha.set_state(entity_id, "unavailable")
                observed = asyncio.run(optimizer._read_state())
                self.assertFalse(observed.ha_control_switch_available)
                self.assertEqual(observed.ha_control_switch_state, state_label)
                observed.sigenergy_mode = cfg.automated_option
                ha.calls.clear()

                asyncio.run(
                    optimizer._apply(
                        observed,
                        self._normal_decision(needs_ha_control_switch=True),
                    )
                )

                self.assertEqual(ha.calls, [])

    def test_remote_ems_on_transition_requests_target_without_dependent_writes(self) -> None:
        ha, optimizer = self._optimizer()
        cfg = optimizer.cfg
        optimizer._manual_mode_override = cfg.full_export_option
        optimizer._last_state = self._state(sigenergy_mode=cfg.full_export_option)
        asyncio.run(optimizer.apply_manual_mode(cfg.automated_option))
        ha.calls.clear()
        state = self._state(
            current_ems_mode=MODE_CMD_DISCHARGE_PV,
            ha_control_enabled=True,
            ha_control_switch_available=True,
            ha_control_switch_state="on",
        )

        asyncio.run(
            optimizer._apply(
                state,
                self._normal_decision(ems_mode=MODE_CMD_CHARGE_PV),
            )
        )

        self.assertFalse(any(call[0] == "turn_on" for call in ha.calls))
        self.assertEqual(
            self._inverter_calls(ha, optimizer),
            [("select_option", cfg.ems_mode_select, MODE_CMD_CHARGE_PV)],
        )
        self.assertEqual(
            optimizer._automated_transition.phase,
            "WAITING_FOR_TARGET_EMS",
        )

    def test_direct_helper_automated_is_read_when_internal_override_is_absent(self) -> None:
        ha, optimizer = self._optimizer()
        cfg = optimizer.cfg
        optimizer._last_state = self._state(sigenergy_mode=cfg.manual_option)
        ha.set_state(cfg.sigenergy_mode_select, cfg.automated_option)

        observed = asyncio.run(optimizer._read_state())

        self.assertEqual(observed.sigenergy_mode, cfg.automated_option)
        self.assertIsNone(optimizer._manual_mode_override)

    def test_direct_helper_automated_is_masked_while_internal_manual_override_remains(
        self,
    ) -> None:
        ha, optimizer = self._optimizer()
        cfg = optimizer.cfg
        optimizer._manual_mode_override = cfg.full_export_option
        optimizer._last_state = self._state(
            sigenergy_mode=cfg.full_export_option
        )
        ha.set_state(cfg.sigenergy_mode_select, cfg.automated_option)

        with self.assertLogs("app.optimizer", level="WARNING"):
            observed = asyncio.run(optimizer._read_state())

        self.assertEqual(
            ha.states[cfg.sigenergy_mode_select]["state"],
            cfg.automated_option,
        )
        self.assertEqual(observed.sigenergy_mode, cfg.full_export_option)
        self.assertEqual(optimizer._manual_mode_override, cfg.full_export_option)

    def test_full_tick_manual_override_masks_direct_helper_automated(self) -> None:
        ha, optimizer = self._optimizer()
        cfg = optimizer.cfg
        optimizer._manual_mode_override = cfg.full_export_option
        optimizer._last_state = self._state(sigenergy_mode=cfg.full_export_option)
        ha.set_state(cfg.sigenergy_mode_select, cfg.automated_option)
        ha.set_state(cfg.ems_mode_select, MODE_CMD_DISCHARGE_PV)
        ha.set_state(cfg.grid_export_limit, cfg.ess_limit_fallback_kw)
        ha.set_state(cfg.grid_import_limit, cfg.block_flow_limit_value)
        ha.set_state(cfg.pv_max_power_limit, cfg.pv_max_power_value)
        ha.set_state(cfg.ess_max_charging_limit, cfg.ess_charge_limit_value, {"max": 25.0})
        ha.set_state(
            cfg.ess_max_discharging_limit,
            cfg.ess_discharge_limit_value,
            {"max": 25.0},
        )

        with self.assertLogs("app.optimizer", level="WARNING"):
            self._run_tick_with_decision(optimizer, self._normal_decision())

        self.assertEqual(optimizer._automated_transition.phase, "IDLE")
        self.assertEqual(optimizer._manual_mode_override, cfg.full_export_option)
        self.assertEqual(optimizer.last_state.sigenergy_mode, cfg.full_export_option)
        self.assertEqual(
            ha.states[cfg.sigenergy_mode_select]["state"],
            cfg.automated_option,
        )
        self.assertEqual(self._inverter_calls(ha, optimizer), [])

    def test_grid_limit_observation_trust_preserves_raw_values(self) -> None:
        ha, optimizer = self._optimizer()
        cfg = optimizer.cfg
        ha.set_state(cfg.grid_export_limit, "7")
        ha.set_state(cfg.grid_import_limit, " 3.25 ")

        valid = asyncio.run(optimizer._read_state())

        self.assertTrue(valid.current_export_limit_trusted)
        self.assertEqual(valid.current_export_limit, 7.0)
        self.assertEqual(valid.current_export_limit_raw, "7")
        self.assertTrue(valid.current_import_limit_trusted)
        self.assertEqual(valid.current_import_limit, 3.25)
        self.assertEqual(valid.current_import_limit_raw, "3.25")

        invalid_cases = (
            ("missing", None, None),
            ("unavailable", "unavailable", "unavailable"),
            ("unknown", "unknown", "unknown"),
            ("empty", "", ""),
            ("malformed", "  not-a-number  ", "not-a-number"),
            ("negative", "-0.01", "-0.01"),
            ("nan", "NaN", "NaN"),
            ("positive infinity", "inf", "inf"),
            ("negative infinity", "-inf", "-inf"),
        )
        for label, raw_state, expected_raw in invalid_cases:
            with self.subTest(observation=label):
                case_ha, case_optimizer = self._optimizer()
                case_cfg = case_optimizer.cfg
                if raw_state is None:
                    case_ha.states.pop(case_cfg.grid_export_limit, None)
                else:
                    case_ha.set_state(case_cfg.grid_export_limit, raw_state)

                observed = asyncio.run(case_optimizer._read_state())

                self.assertFalse(observed.current_export_limit_trusted)
                self.assertEqual(observed.current_export_limit, 0.0)
                self.assertEqual(observed.current_export_limit_raw, expected_raw)

        domain_ha, domain_optimizer = self._optimizer()
        domain_optimizer.cfg.grid_export_limit = "sensor.test_grid_export_limit"
        domain_ha.set_state("sensor.test_grid_export_limit", "0.01")

        invalid_domain = asyncio.run(domain_optimizer._read_state())

        self.assertFalse(invalid_domain.current_export_limit_trusted)
        self.assertEqual(invalid_domain.current_export_limit, 0.0)
        self.assertEqual(invalid_domain.current_export_limit_raw, "0.01")

    def test_import_grid_limit_observation_rejects_invalid_domain_none_and_null(
        self,
    ) -> None:
        cases = (
            ("invalid domain", "sensor.test_grid_import_limit", "0.01", "0.01"),
            ("literal none", None, "none", "none"),
            ("null state", None, None, ""),
        )
        for label, configured_entity, raw_state, expected_raw in cases:
            with self.subTest(observation=label):
                ha, optimizer = self._optimizer()
                cfg = optimizer.cfg
                entity_id = configured_entity or cfg.grid_import_limit
                if configured_entity:
                    cfg.grid_import_limit = configured_entity
                if raw_state is None:
                    ha.states[entity_id] = {
                        "entity_id": entity_id,
                        "state": None,
                        "attributes": {},
                    }
                else:
                    ha.set_state(entity_id, raw_state)

                observed = asyncio.run(optimizer._read_state())

                self.assertFalse(observed.current_import_limit_trusted)
                self.assertEqual(observed.current_import_limit, 0.0)
                self.assertEqual(observed.current_import_limit_raw, expected_raw)

    def test_untrusted_compatibility_zero_cannot_confirm_containment(self) -> None:
        ha, optimizer = self._optimizer()
        self._enter_transition(ha, optimizer)
        state = self._state(
            current_export_limit=0.0,
            current_export_limit_raw=None,
            current_export_limit_trusted=False,
        )
        decision = self._normal_decision()

        asyncio.run(optimizer._apply(state, decision))

        self.assertEqual(self._inverter_calls(ha, optimizer), [])
        self.assertEqual(optimizer._automated_transition.phase, "CONTAINING_GRID")
        self.assertFalse(decision.trace_gates["automated_transition_grid_contained"])
        self.assertTrue(decision.trace_gates["automated_transition_normal_writes_blocked"])
        self.assertEqual(decision.trace_values["current_export_limit_raw"], None)
        self.assertFalse(decision.trace_values["current_export_limit_trusted"])
        self.assertEqual(
            decision.trace_values["automated_transition_phase"],
            "CONTAINING_GRID",
        )
        self.assertEqual(
            decision.trace_values["automated_transition_source"],
            "apply_manual_mode",
        )
        self.assertEqual(
            decision.trace_values["automated_transition_target_ems_mode"],
            MODE_CMD_CHARGE_PV,
        )
        self.assertIn("waiting for trusted", decision.outcome_reason)

    def test_direct_helper_transition_and_manual_reentry_lifecycle(self) -> None:
        ha, optimizer = self._optimizer()
        cfg = optimizer.cfg
        optimizer._startup_automated_transition_checked = True
        optimizer._last_state = self._state(sigenergy_mode=cfg.manual_option)
        ha.set_state(cfg.sigenergy_mode_select, cfg.automated_option)
        ha.set_state(cfg.grid_export_limit, 5.0)

        self._run_tick_with_decision(optimizer, self._normal_decision())

        self.assertEqual(optimizer._automated_transition.phase, "CONTAINING_GRID")
        self.assertEqual(optimizer._automated_transition.source, "helper")
        self.assertEqual(
            self._inverter_calls(ha, optimizer),
            [("set_number", cfg.grid_export_limit, cfg.block_flow_limit_value)],
        )

        ha.select_option_result = False
        with self.assertRaises(RuntimeError):
            asyncio.run(optimizer.apply_manual_mode(cfg.full_import_option))
        self.assertEqual(optimizer._automated_transition.phase, "CONTAINING_GRID")

        ha.select_option_result = True
        asyncio.run(optimizer.apply_manual_mode(cfg.full_import_option))
        self.assertEqual(optimizer._automated_transition.phase, "IDLE")
        self.assertEqual(optimizer._manual_mode_override, cfg.full_import_option)

    def test_grid_containment_orders_calls_and_handles_untrusted_sides(self) -> None:
        cases = (
            (
                "export only",
                {
                    "current_export_limit": 5.0,
                    "current_export_limit_raw": "5.0",
                },
                ("export",),
            ),
            (
                "import only",
                {
                    "current_import_limit": 6.0,
                    "current_import_limit_raw": "6.0",
                },
                ("import",),
            ),
            (
                "both open",
                {
                    "current_export_limit": 5.0,
                    "current_export_limit_raw": "5.0",
                    "current_import_limit": 6.0,
                    "current_import_limit_raw": "6.0",
                },
                ("export", "import"),
            ),
            (
                "trusted export open import untrusted",
                {
                    "current_export_limit": 5.0,
                    "current_export_limit_raw": "5.0",
                    "current_import_limit": 0.0,
                    "current_import_limit_raw": "unavailable",
                    "current_import_limit_trusted": False,
                },
                ("export",),
            ),
            (
                "trusted closed export import untrusted",
                {
                    "current_import_limit": 0.0,
                    "current_import_limit_raw": "unavailable",
                    "current_import_limit_trusted": False,
                },
                (),
            ),
            (
                "both untrusted",
                {
                    "current_export_limit": 0.0,
                    "current_export_limit_raw": None,
                    "current_export_limit_trusted": False,
                    "current_import_limit": 0.0,
                    "current_import_limit_raw": "unknown",
                    "current_import_limit_trusted": False,
                },
                (),
            ),
        )

        for label, overrides, expected_sides in cases:
            with self.subTest(containment=label):
                ha, optimizer = self._optimizer()
                cfg = optimizer.cfg
                self._enter_transition(ha, optimizer)
                state = self._state(**overrides)

                asyncio.run(optimizer._apply(state, self._normal_decision()))

                side_to_entity = {
                    "export": cfg.grid_export_limit,
                    "import": cfg.grid_import_limit,
                }
                expected_calls = [
                    ("set_number", side_to_entity[side], cfg.block_flow_limit_value)
                    for side in expected_sides
                ]
                actual_close_calls = [
                    call
                    for call in self._inverter_calls(ha, optimizer)
                    if call[0] == "set_number"
                ]
                self.assertEqual(actual_close_calls, expected_calls)
                if not expected_sides and not (
                    state.current_export_limit_trusted
                    and state.current_import_limit_trusted
                ):
                    self.assertEqual(self._inverter_calls(ha, optimizer), [])
                    self.assertEqual(
                        optimizer._automated_transition.phase,
                        "CONTAINING_GRID",
                    )

    def test_both_closed_skip_closure_and_request_only_target_ems(self) -> None:
        ha, optimizer = self._optimizer()
        cfg = optimizer.cfg
        self._enter_transition(ha, optimizer)
        state = self._state(current_ems_mode=MODE_CMD_DISCHARGE_PV)

        asyncio.run(
            optimizer._apply(
                state,
                self._normal_decision(ems_mode=MODE_CMD_CHARGE_PV),
            )
        )

        self.assertEqual(
            self._inverter_calls(ha, optimizer),
            [("select_option", cfg.ems_mode_select, MODE_CMD_CHARGE_PV)],
        )
        self.assertEqual(
            optimizer._automated_transition.phase,
            "WAITING_FOR_TARGET_EMS",
        )

    def test_export_close_failure_still_attempts_import_and_consumes_retry(self) -> None:
        ha, optimizer = self._optimizer()
        cfg = optimizer.cfg
        self._enter_transition(ha, optimizer)
        ha.set_number_results[cfg.grid_export_limit] = False
        state = self._state(
            current_export_limit=5.0,
            current_export_limit_raw="5.0",
            current_import_limit=6.0,
            current_import_limit_raw="6.0",
        )

        with patch("app.optimizer.monotonic", return_value=100.0):
            asyncio.run(optimizer._apply(state, self._normal_decision()))

        self.assertEqual(
            self._inverter_calls(ha, optimizer),
            [
                ("set_number", cfg.grid_export_limit, cfg.block_flow_limit_value),
                ("set_number", cfg.grid_import_limit, cfg.block_flow_limit_value),
            ],
        )
        self.assertEqual(optimizer._automated_transition.phase, "CONTAINING_GRID")

        ha.calls.clear()
        suppressed_decision = self._normal_decision()
        with patch("app.optimizer.monotonic", return_value=159.0):
            asyncio.run(optimizer._apply(state, suppressed_decision))
        self.assertEqual(self._inverter_calls(ha, optimizer), [])
        self.assertTrue(
            suppressed_decision.trace_gates["automated_transition_retry_suppressed"]
        )

        ha.calls.clear()
        with patch("app.optimizer.monotonic", return_value=160.0):
            asyncio.run(optimizer._apply(state, self._normal_decision()))
        self.assertEqual(len(self._inverter_calls(ha, optimizer)), 2)

    def test_invalid_containment_config_blocks_all_transition_writes(self) -> None:
        invalid_values = (
            -0.01,
            float("nan"),
            float("inf"),
            float("-inf"),
            0.012,
        )
        for invalid_value in invalid_values:
            with self.subTest(block_flow_limit_value=invalid_value):
                ha, optimizer = self._optimizer()
                optimizer.cfg.block_flow_limit_value = invalid_value
                self._enter_transition(ha, optimizer)
                decision = self._normal_decision()
                state = self._state(
                    current_export_limit=5.0,
                    current_export_limit_raw="5.0",
                )

                asyncio.run(optimizer._apply(state, decision))

                self.assertEqual(self._inverter_calls(ha, optimizer), [])
                self.assertEqual(
                    optimizer._automated_transition.phase,
                    "CONTAINING_GRID",
                )
                self.assertIn("invalid grid containment", decision.outcome_reason)

    def test_pending_warning_is_throttled_without_timeout_fail_open(self) -> None:
        ha, optimizer = self._optimizer()
        self._enter_transition(ha, optimizer)
        optimizer._automated_transition.started_at = 0.0
        state = self._state(
            current_export_limit=0.0,
            current_export_limit_raw=None,
            current_export_limit_trusted=False,
            current_import_limit=0.0,
            current_import_limit_raw="unknown",
            current_import_limit_trusted=False,
        )

        with (
            patch("app.optimizer.monotonic", return_value=301.0),
            self.assertLogs("app.optimizer", level="WARNING"),
        ):
            asyncio.run(optimizer._apply(state, self._normal_decision()))

        ha.calls.clear()
        decision = self._normal_decision()
        with (
            patch("app.optimizer.monotonic", return_value=302.0),
            self.assertNoLogs("app.optimizer", level="WARNING"),
        ):
            asyncio.run(optimizer._apply(state, decision))

        self.assertEqual(self._inverter_calls(ha, optimizer), [])
        self.assertEqual(optimizer._automated_transition.phase, "CONTAINING_GRID")
        self.assertTrue(
            decision.trace_gates["automated_transition_warning_suppressed"]
        )

    def test_ems_service_success_requires_later_observation_before_normal_writes(self) -> None:
        ha, optimizer = self._optimizer()
        cfg = optimizer.cfg
        self._enter_transition(ha, optimizer)
        waiting_state = self._state(current_ems_mode=MODE_CMD_DISCHARGE_PV)
        decision = self._normal_decision(ems_mode=MODE_CMD_CHARGE_PV)

        asyncio.run(optimizer._apply(waiting_state, decision))

        self.assertEqual(
            self._inverter_calls(ha, optimizer),
            [("select_option", cfg.ems_mode_select, MODE_CMD_CHARGE_PV)],
        )
        self.assertEqual(
            optimizer._automated_transition.phase,
            "WAITING_FOR_TARGET_EMS",
        )

        ha.calls.clear()
        asyncio.run(optimizer._apply(waiting_state, self._normal_decision()))
        self.assertEqual(self._inverter_calls(ha, optimizer), [])

        observed_target = self._state(current_ems_mode=MODE_CMD_CHARGE_PV)
        ha.calls.clear()
        completed_decision = self._normal_decision(ems_mode=MODE_CMD_CHARGE_PV)
        asyncio.run(optimizer._apply(observed_target, completed_decision))

        self.assertEqual(optimizer._automated_transition.phase, "IDLE")
        self.assertEqual(
            self._inverter_calls(ha, optimizer),
            [
                ("set_number", cfg.grid_export_limit, 2.0),
                ("set_number", cfg.grid_import_limit, 3.0),
                ("set_number", cfg.ess_max_charging_limit, 10.0),
                ("set_number", cfg.ess_max_discharging_limit, 11.0),
                ("set_number", cfg.pv_max_power_limit, 20.0),
            ],
        )
        self.assertTrue(
            completed_decision.trace_gates["automated_transition_completed"]
        )

    def test_fresh_ticks_are_required_after_grid_containment_and_ems_requests(
        self,
    ) -> None:
        ha, optimizer = self._optimizer()
        cfg = optimizer.cfg
        self._enter_transition(ha, optimizer)
        ha.set_state(cfg.ems_mode_select, MODE_CMD_DISCHARGE_PV)
        ha.set_state(cfg.grid_export_limit, 5.0)
        ha.set_state(cfg.grid_import_limit, 6.0)
        decision = self._normal_decision(ems_mode=MODE_CMD_CHARGE_PV)

        self._run_tick_with_decision(optimizer, decision)

        self.assertEqual(
            self._inverter_calls(ha, optimizer),
            [
                ("set_number", cfg.grid_export_limit, cfg.block_flow_limit_value),
                ("set_number", cfg.grid_import_limit, cfg.block_flow_limit_value),
            ],
        )
        self.assertEqual(optimizer._automated_transition.phase, "CONTAINING_GRID")

        ha.calls.clear()
        self._run_tick_with_decision(
            optimizer,
            self._normal_decision(ems_mode=MODE_CMD_CHARGE_PV),
        )

        self.assertEqual(
            self._inverter_calls(ha, optimizer),
            [("select_option", cfg.ems_mode_select, MODE_CMD_CHARGE_PV)],
        )
        self.assertEqual(
            optimizer._automated_transition.phase,
            "WAITING_FOR_TARGET_EMS",
        )

        ha.calls.clear()
        self._run_tick_with_decision(
            optimizer,
            self._normal_decision(ems_mode=MODE_CMD_CHARGE_PV),
        )

        self.assertEqual(optimizer._automated_transition.phase, "IDLE")
        self.assertEqual(
            self._inverter_calls(ha, optimizer),
            [
                ("set_number", cfg.grid_export_limit, 2.0),
                ("set_number", cfg.grid_import_limit, 3.0),
                ("set_number", cfg.ess_max_charging_limit, 10.0),
                ("set_number", cfg.ess_max_discharging_limit, 11.0),
                ("set_number", cfg.pv_max_power_limit, 20.0),
            ],
        )

    def test_failed_ems_target_request_consumes_retry_without_fallback(self) -> None:
        ha, optimizer = self._optimizer()
        cfg = optimizer.cfg
        self._enter_transition(ha, optimizer)
        ha.select_option_results[cfg.ems_mode_select] = False
        waiting_state = self._state(current_ems_mode=MODE_CMD_DISCHARGE_PV)

        with patch("app.optimizer.monotonic", return_value=100.0):
            asyncio.run(optimizer._apply(waiting_state, self._normal_decision()))

        self.assertEqual(
            self._inverter_calls(ha, optimizer),
            [("select_option", cfg.ems_mode_select, MODE_CMD_CHARGE_PV)],
        )
        self.assertEqual(
            optimizer._automated_transition.phase,
            "WAITING_FOR_TARGET_EMS",
        )

        ha.calls.clear()
        suppressed_decision = self._normal_decision()
        with patch("app.optimizer.monotonic", return_value=159.0):
            asyncio.run(optimizer._apply(waiting_state, suppressed_decision))
        self.assertEqual(self._inverter_calls(ha, optimizer), [])
        self.assertTrue(
            suppressed_decision.trace_gates["automated_transition_retry_suppressed"]
        )

        with patch("app.optimizer.monotonic", return_value=160.0):
            asyncio.run(optimizer._apply(waiting_state, self._normal_decision()))
        self.assertEqual(
            self._inverter_calls(ha, optimizer),
            [("select_option", cfg.ems_mode_select, MODE_CMD_CHARGE_PV)],
        )

    def test_transition_ha_exceptions_remain_pending_without_normal_or_fallback_writes(
        self,
    ) -> None:
        grid_ha, grid_optimizer = self._optimizer()
        grid_cfg = grid_optimizer.cfg
        self._enter_transition(grid_ha, grid_optimizer)
        grid_ha.set_number_exceptions[grid_cfg.grid_export_limit] = RuntimeError(
            "grid close failed"
        )
        grid_state = self._state(
            current_export_limit=5.0,
            current_export_limit_raw="5.0",
            current_import_limit=6.0,
            current_import_limit_raw="6.0",
        )

        with (
            patch("app.optimizer.monotonic", return_value=100.0),
            self.assertRaises(RuntimeError),
        ):
            asyncio.run(grid_optimizer._apply(grid_state, self._normal_decision()))

        self.assertEqual(
            self._inverter_calls(grid_ha, grid_optimizer),
            [("set_number", grid_cfg.grid_export_limit, grid_cfg.block_flow_limit_value)],
        )
        self.assertEqual(grid_optimizer._automated_transition.phase, "CONTAINING_GRID")
        self.assertEqual(grid_optimizer._automated_transition.last_action_at, 100.0)

        ems_ha, ems_optimizer = self._optimizer()
        ems_cfg = ems_optimizer.cfg
        self._enter_transition(ems_ha, ems_optimizer)
        ems_ha.select_option_exceptions[ems_cfg.ems_mode_select] = RuntimeError(
            "EMS request failed"
        )
        ems_state = self._state(current_ems_mode=MODE_CMD_DISCHARGE_PV)

        with (
            patch("app.optimizer.monotonic", return_value=200.0),
            self.assertRaises(RuntimeError),
        ):
            asyncio.run(ems_optimizer._apply(ems_state, self._normal_decision()))

        self.assertEqual(
            self._inverter_calls(ems_ha, ems_optimizer),
            [("select_option", ems_cfg.ems_mode_select, MODE_CMD_CHARGE_PV)],
        )
        self.assertEqual(
            ems_optimizer._automated_transition.phase,
            "WAITING_FOR_TARGET_EMS",
        )
        self.assertEqual(ems_optimizer._automated_transition.last_action_at, 200.0)

        remote_ha, remote_optimizer = self._optimizer()
        remote_cfg = remote_optimizer.cfg
        self._enter_transition(remote_ha, remote_optimizer)
        remote_ha.turn_on_exceptions[remote_cfg.ha_control_switch] = RuntimeError(
            "Remote EMS activation failed"
        )
        remote_state = self._state(
            ha_control_enabled=False,
            ha_control_switch_available=True,
            ha_control_switch_state="off",
        )

        with self.assertRaises(RuntimeError):
            asyncio.run(
                remote_optimizer._apply(
                    remote_state,
                    self._normal_decision(needs_ha_control_switch=True),
                )
            )

        self.assertEqual(
            remote_ha.calls,
            [("turn_on", remote_cfg.ha_control_switch, True)],
        )
        self.assertEqual(
            remote_optimizer._automated_transition.phase,
            "CONTAINING_GRID",
        )
        self.assertIsNotNone(remote_optimizer._last_ha_control_enable_attempt_at)

    def test_newest_strategy_target_supersedes_observed_old_target(self) -> None:
        ha, optimizer = self._optimizer()
        cfg = optimizer.cfg
        self._enter_transition(ha, optimizer)
        initial_state = self._state(current_ems_mode=MODE_CMD_DISCHARGE_PV)
        with patch("app.optimizer.monotonic", return_value=100.0):
            asyncio.run(
                optimizer._apply(
                    initial_state,
                    self._normal_decision(ems_mode=MODE_CMD_CHARGE_PV),
                )
            )

        ha.calls.clear()
        observed_old_target = self._state(current_ems_mode=MODE_CMD_CHARGE_PV)
        changed_decision = self._normal_decision(ems_mode=MODE_CMD_CHARGE_GRID)
        with patch("app.optimizer.monotonic", return_value=120.0):
            asyncio.run(optimizer._apply(observed_old_target, changed_decision))

        self.assertEqual(self._inverter_calls(ha, optimizer), [])
        self.assertEqual(
            optimizer._automated_transition.target_ems_mode,
            MODE_CMD_CHARGE_GRID,
        )
        self.assertEqual(
            optimizer._automated_transition.phase,
            "WAITING_FOR_TARGET_EMS",
        )

        with patch("app.optimizer.monotonic", return_value=160.0):
            asyncio.run(optimizer._apply(observed_old_target, changed_decision))
        self.assertEqual(
            self._inverter_calls(ha, optimizer),
            [("select_option", cfg.ems_mode_select, MODE_CMD_CHARGE_GRID)],
        )

    def test_shared_transition_target_return_after_request_requires_superseding_confirmation(
        self,
    ) -> None:
        for source in ("apply_manual_mode", "startup"):
            with self.subTest(source=source):
                ha, optimizer = self._optimizer()
                cfg = optimizer.cfg
                if source == "apply_manual_mode":
                    self._enter_transition(ha, optimizer)
                else:
                    optimizer._start_automated_transition(
                        source="startup",
                        previous_mode=cfg.automated_option,
                    )
                self.assertEqual(
                    optimizer._automated_transition.last_requested_target,
                    "",
                )
                ha.update_state_on_success = False

                observed_b = self._state(current_ems_mode=MODE_CMD_DISCHARGE_PV)
                target_a = self._normal_decision(ems_mode=MODE_CMD_CHARGE_PV)
                with patch("app.optimizer.monotonic", return_value=100.0):
                    asyncio.run(optimizer._apply(observed_b, target_a))

                self.assertEqual(
                    self._inverter_calls(ha, optimizer),
                    [("select_option", cfg.ems_mode_select, MODE_CMD_CHARGE_PV)],
                )
                self.assertEqual(
                    optimizer._automated_transition.last_requested_target,
                    MODE_CMD_CHARGE_PV,
                )
                self.assertEqual(
                    optimizer._automated_transition.phase,
                    "WAITING_FOR_TARGET_EMS",
                )

                newest_b = self._normal_decision(ems_mode=MODE_CMD_DISCHARGE_PV)
                newest_b.export_limit = 4.0
                newest_b.import_limit = 5.0
                newest_b.ess_charge_limit = 8.0
                newest_b.ess_discharge_limit = 9.0
                newest_b.pv_max_power_limit = 18.0
                ha.calls.clear()
                with patch("app.optimizer.monotonic", return_value=159.0):
                    asyncio.run(optimizer._apply(observed_b, newest_b))

                self.assertEqual(self._inverter_calls(ha, optimizer), [])
                self.assertEqual(
                    optimizer._automated_transition.last_requested_target,
                    MODE_CMD_CHARGE_PV,
                )
                self.assertEqual(
                    optimizer._automated_transition.phase,
                    "WAITING_FOR_TARGET_EMS",
                )
                self.assertTrue(
                    newest_b.trace_gates["automated_transition_retry_suppressed"]
                )

                ha.calls.clear()
                with patch("app.optimizer.monotonic", return_value=160.0):
                    asyncio.run(optimizer._apply(observed_b, newest_b))

                self.assertEqual(
                    self._inverter_calls(ha, optimizer),
                    [
                        (
                            "select_option",
                            cfg.ems_mode_select,
                            MODE_CMD_DISCHARGE_PV,
                        )
                    ],
                )
                self.assertEqual(
                    optimizer._automated_transition.last_requested_target,
                    MODE_CMD_DISCHARGE_PV,
                )
                self.assertEqual(
                    optimizer._automated_transition.phase,
                    "WAITING_FOR_TARGET_EMS",
                )

                ha.set_state(cfg.ems_mode_select, MODE_CMD_DISCHARGE_PV)
                fresh_observed_b = asyncio.run(optimizer._read_state())
                ha.calls.clear()
                with patch("app.optimizer.monotonic", return_value=161.0):
                    asyncio.run(optimizer._apply(fresh_observed_b, newest_b))

                self.assertEqual(optimizer._automated_transition.phase, "IDLE")
                self.assertEqual(
                    self._inverter_calls(ha, optimizer),
                    [
                        ("set_number", cfg.grid_export_limit, 4.0),
                        ("set_number", cfg.grid_import_limit, 5.0),
                        ("set_number", cfg.ess_max_charging_limit, 8.0),
                        ("set_number", cfg.ess_max_discharging_limit, 9.0),
                        ("set_number", cfg.pv_max_power_limit, 18.0),
                    ],
                )

    def test_failed_or_raised_ems_request_records_history_and_blocks_target_return(
        self,
    ) -> None:
        for failure in ("false", "raises"):
            with self.subTest(failure=failure):
                ha, optimizer = self._optimizer()
                cfg = optimizer.cfg
                self._enter_transition(ha, optimizer)
                ha.update_state_on_success = False
                if failure == "false":
                    ha.select_option_results[cfg.ems_mode_select] = False
                else:
                    ha.select_option_exceptions[cfg.ems_mode_select] = RuntimeError(
                        "EMS request failed"
                    )

                observed_b = self._state(current_ems_mode=MODE_CMD_DISCHARGE_PV)
                target_a = self._normal_decision(ems_mode=MODE_CMD_CHARGE_PV)
                with patch("app.optimizer.monotonic", return_value=100.0):
                    if failure == "raises":
                        with self.assertRaises(RuntimeError):
                            asyncio.run(optimizer._apply(observed_b, target_a))
                    else:
                        asyncio.run(optimizer._apply(observed_b, target_a))

                self.assertEqual(
                    self._inverter_calls(ha, optimizer),
                    [("select_option", cfg.ems_mode_select, MODE_CMD_CHARGE_PV)],
                )
                self.assertEqual(
                    optimizer._automated_transition.last_requested_target,
                    MODE_CMD_CHARGE_PV,
                )
                self.assertEqual(
                    optimizer._automated_transition.phase,
                    "WAITING_FOR_TARGET_EMS",
                )

                ha.select_option_results.pop(cfg.ems_mode_select, None)
                ha.select_option_exceptions.pop(cfg.ems_mode_select, None)
                newest_b = self._normal_decision(ems_mode=MODE_CMD_DISCHARGE_PV)
                ha.calls.clear()
                with patch("app.optimizer.monotonic", return_value=120.0):
                    asyncio.run(optimizer._apply(observed_b, newest_b))

                self.assertEqual(self._inverter_calls(ha, optimizer), [])
                self.assertEqual(
                    optimizer._automated_transition.last_requested_target,
                    MODE_CMD_CHARGE_PV,
                )
                self.assertEqual(
                    optimizer._automated_transition.phase,
                    "WAITING_FOR_TARGET_EMS",
                )

                with patch("app.optimizer.monotonic", return_value=160.0):
                    asyncio.run(optimizer._apply(observed_b, newest_b))

                self.assertEqual(
                    self._inverter_calls(ha, optimizer),
                    [
                        (
                            "select_option",
                            cfg.ems_mode_select,
                            MODE_CMD_DISCHARGE_PV,
                        )
                    ],
                )
                self.assertEqual(
                    optimizer._automated_transition.last_requested_target,
                    MODE_CMD_DISCHARGE_PV,
                )
                self.assertEqual(
                    optimizer._automated_transition.phase,
                    "WAITING_FOR_TARGET_EMS",
                )

    def test_reopened_or_untrusted_grid_limit_returns_to_containment(self) -> None:
        cases = (
            (
                "export reopened",
                {
                    "current_export_limit": 1.0,
                    "current_export_limit_raw": "1.0",
                },
                "grid_export_limit",
            ),
            (
                "import reopened",
                {
                    "current_import_limit": 1.0,
                    "current_import_limit_raw": "1.0",
                },
                "grid_import_limit",
            ),
            (
                "export untrusted",
                {
                    "current_export_limit": 0.0,
                    "current_export_limit_raw": "unavailable",
                    "current_export_limit_trusted": False,
                },
                None,
            ),
            (
                "import untrusted",
                {
                    "current_import_limit": 0.0,
                    "current_import_limit_raw": "unknown",
                    "current_import_limit_trusted": False,
                },
                None,
            ),
        )
        for label, overrides, expected_config_attr in cases:
            with self.subTest(grid_state=label):
                ha, optimizer = self._optimizer()
                cfg = optimizer.cfg
                self._enter_transition(ha, optimizer)
                optimizer._automated_transition.phase = "WAITING_FOR_TARGET_EMS"
                optimizer._automated_transition.target_ems_mode = MODE_CMD_CHARGE_PV
                optimizer._automated_transition.last_action_at = 100.0
                state = self._state(
                    current_ems_mode=MODE_CMD_CHARGE_PV,
                    **overrides,
                )

                with patch("app.optimizer.monotonic", return_value=110.0):
                    asyncio.run(
                        optimizer._apply(
                            state,
                            self._normal_decision(ems_mode=MODE_CMD_CHARGE_PV),
                        )
                    )

                self.assertEqual(
                    optimizer._automated_transition.phase,
                    "CONTAINING_GRID",
                )
                if expected_config_attr is None:
                    self.assertEqual(self._inverter_calls(ha, optimizer), [])
                else:
                    self.assertEqual(
                        self._inverter_calls(ha, optimizer),
                        [
                            (
                                "set_number",
                                getattr(cfg, expected_config_attr),
                                cfg.block_flow_limit_value,
                            )
                        ],
                    )

    def test_remote_ems_observed_on_resumes_retained_transition(self) -> None:
        ha, optimizer = self._optimizer()
        cfg = optimizer.cfg
        self._enter_transition(ha, optimizer)
        off_state = self._state(
            current_ems_mode=MODE_CMD_DISCHARGE_PV,
            ha_control_enabled=False,
            ha_control_switch_available=True,
            ha_control_switch_state="off",
        )

        asyncio.run(optimizer._apply(off_state, self._normal_decision()))
        self.assertEqual(ha.calls, [("turn_on", cfg.ha_control_switch, True)])
        self.assertEqual(optimizer._automated_transition.phase, "CONTAINING_GRID")

        ha.calls.clear()
        on_state = self._state(current_ems_mode=MODE_CMD_DISCHARGE_PV)
        asyncio.run(optimizer._apply(on_state, self._normal_decision()))
        self.assertEqual(
            self._inverter_calls(ha, optimizer),
            [("select_option", cfg.ems_mode_select, MODE_CMD_CHARGE_PV)],
        )

    def test_remote_ems_off_with_auto_enable_disabled_remains_pending(self) -> None:
        ha, optimizer = self._optimizer()
        cfg = optimizer.cfg
        cfg.auto_enable_ha_control = False
        self._enter_transition(ha, optimizer)
        state = self._state(
            ha_control_enabled=False,
            ha_control_switch_available=True,
            ha_control_switch_state="off",
        )

        asyncio.run(
            optimizer._apply(
                state,
                self._normal_decision(needs_ha_control_switch=False),
            )
        )

        self.assertEqual(ha.calls, [])
        self.assertEqual(self._inverter_calls(ha, optimizer), [])
        self.assertEqual(optimizer._automated_transition.phase, "CONTAINING_GRID")

    def test_startup_transition_matching_mismatch_recovery_and_single_check(self) -> None:
        matching_ha, matching_optimizer = self._optimizer()
        matching_cfg = matching_optimizer.cfg
        self._run_tick_with_decision(
            matching_optimizer,
            self._normal_decision(ems_mode=MODE_MAX_SELF),
        )
        self.assertTrue(matching_optimizer._startup_automated_transition_checked)
        self.assertEqual(matching_optimizer._automated_transition.phase, "IDLE")

        matching_ha.calls.clear()
        matching_ha.set_state(matching_cfg.ems_mode_select, MODE_CMD_DISCHARGE_PV)
        matching_ha.set_state(matching_cfg.grid_export_limit, 5.0)
        matching_ha.set_state(matching_cfg.grid_import_limit, 6.0)
        self._run_tick_with_decision(
            matching_optimizer,
            self._normal_decision(ems_mode=MODE_CMD_CHARGE_PV),
        )
        self.assertEqual(matching_optimizer._automated_transition.phase, "IDLE")
        self.assertEqual(
            matching_optimizer._ordinary_ems_settlement.phase,
            "CONTAINING_GRID",
        )
        self.assertEqual(
            self._inverter_calls(matching_ha, matching_optimizer),
            [
                (
                    "set_number",
                    matching_cfg.grid_export_limit,
                    matching_cfg.block_flow_limit_value,
                ),
                (
                    "set_number",
                    matching_cfg.grid_import_limit,
                    matching_cfg.block_flow_limit_value,
                ),
            ],
        )

        mismatch_ha, mismatch_optimizer = self._optimizer()
        mismatch_cfg = mismatch_optimizer.cfg
        mismatch_ha.set_state(mismatch_cfg.ems_mode_select, MODE_CMD_DISCHARGE_PV)
        mismatch_ha.set_state(mismatch_cfg.grid_export_limit, 5.0)
        self._run_tick_with_decision(
            mismatch_optimizer,
            self._normal_decision(ems_mode=MODE_CMD_CHARGE_PV),
        )
        self.assertTrue(mismatch_optimizer._startup_automated_transition_checked)
        self.assertEqual(
            mismatch_optimizer._automated_transition.phase,
            "CONTAINING_GRID",
        )
        self.assertEqual(mismatch_optimizer._automated_transition.source, "startup")
        self.assertEqual(
            self._inverter_calls(mismatch_ha, mismatch_optimizer),
            [
                (
                    "set_number",
                    mismatch_cfg.grid_export_limit,
                    mismatch_cfg.block_flow_limit_value,
                )
            ],
        )

        recovery_ha, recovery_optimizer = self._optimizer()
        recovery_cfg = recovery_optimizer.cfg
        recovery_ha.set_state(recovery_cfg.ems_mode_select, "unavailable")
        self._run_tick_with_decision(
            recovery_optimizer,
            self._normal_decision(ems_mode=MODE_CMD_CHARGE_PV),
        )
        self.assertFalse(recovery_optimizer._startup_automated_transition_checked)
        self.assertTrue(recovery_optimizer._ems_mode_recovery_required)
        self.assertEqual(
            self._inverter_calls(recovery_ha, recovery_optimizer),
            [("select_option", recovery_cfg.ems_mode_select, MODE_MAX_SELF)],
        )

        recovery_ha.calls.clear()
        recovery_ha.set_state(recovery_cfg.ems_mode_select, MODE_MAX_SELF)
        self._run_tick_with_decision(
            recovery_optimizer,
            self._normal_decision(ems_mode=MODE_CMD_CHARGE_PV),
        )
        self.assertTrue(recovery_optimizer._startup_automated_transition_checked)
        self.assertFalse(recovery_optimizer._ems_mode_recovery_required)
        self.assertEqual(recovery_optimizer._automated_transition.source, "startup")
        self.assertEqual(
            self._inverter_calls(recovery_ha, recovery_optimizer),
            [("select_option", recovery_cfg.ems_mode_select, MODE_CMD_CHARGE_PV)],
        )

        manual_ha, manual_optimizer = self._optimizer()
        manual_cfg = manual_optimizer.cfg
        manual_ha.set_state(manual_cfg.sigenergy_mode_select, manual_cfg.manual_option)
        self._run_tick_with_decision(manual_optimizer, self._normal_decision())
        self.assertTrue(manual_optimizer._startup_automated_transition_checked)
        self.assertEqual(manual_optimizer._automated_transition.phase, "IDLE")

    def test_transition_watch_entities_include_confirmation_surfaces(self) -> None:
        _, optimizer = self._optimizer()
        cfg = optimizer.cfg

        self.assertTrue(
            {
                cfg.grid_export_limit,
                cfg.grid_import_limit,
                cfg.ems_mode_select,
                cfg.ha_control_switch,
            }.issubset(optimizer.get_watch_entities())
        )


if __name__ == "__main__":
    unittest.main()
