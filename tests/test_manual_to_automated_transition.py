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
        self.select_option_result = True

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
        state = self.states.get(entity_id)
        return state.get("state", default) if state else default

    async def turn_on(self, entity_id: str) -> bool:
        self.calls.append(("turn_on", entity_id, True))
        self.set_state(entity_id, "on")
        return True

    async def select_option(self, entity_id: str, value: str) -> bool:
        self.calls.append(("select_option", entity_id, value))
        if self.optimizer and entity_id == self.optimizer.cfg.sigenergy_mode_select:
            self.mode_helper_lock_observations.append(
                self.optimizer._control_lock.locked()
            )
        if not self.select_option_result:
            return False
        self.set_state(entity_id, value)
        return True

    async def set_number(self, entity_id: str, value: float) -> bool:
        self.calls.append(("set_number", entity_id, value))
        attributes = self.states.get(entity_id, {}).get("attributes", {})
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
            current_import_limit=0.01,
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
            recovered_calls[0],
            ("select_option", cfg.ems_mode_select, MODE_CMD_CHARGE_PV),
        )
        self.assertTrue(any(call[0] == "set_number" for call in recovered_calls))

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

    def test_remote_ems_on_transition_allows_normal_writes(self) -> None:
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
        inverter_calls = self._inverter_calls(ha, optimizer)
        self.assertEqual(
            inverter_calls[0],
            ("select_option", cfg.ems_mode_select, MODE_CMD_CHARGE_PV),
        )
        self.assertTrue(
            any(call[0] == "set_number" for call in inverter_calls[1:])
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


if __name__ == "__main__":
    unittest.main()
