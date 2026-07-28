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
    MODE_CMD_DISCHARGE_ESS,
    MODE_CMD_DISCHARGE_PV,
    MODE_MAX_SELF,
    SigEnergyOptimizer,
)


TRUSTED_OBSERVED_EMS_MODES = (
    MODE_MAX_SELF,
    MODE_CMD_CHARGE_PV,
    MODE_CMD_CHARGE_GRID,
    MODE_CMD_DISCHARGE_PV,
    MODE_CMD_DISCHARGE_ESS,
)
APPROVED_AUTOMATED_TARGET_EMS_MODES = (
    MODE_MAX_SELF,
    MODE_CMD_CHARGE_PV,
    MODE_CMD_CHARGE_GRID,
    MODE_CMD_DISCHARGE_PV,
)
AUTOMATED_MODE_CHANGES = tuple(
    (observed, target)
    for observed in TRUSTED_OBSERVED_EMS_MODES
    for target in APPROVED_AUTOMATED_TARGET_EMS_MODES
    if observed != target
)


class _SettlementRecordingHA:
    """HA fake whose successful service calls never fabricate later observations."""

    def __init__(self) -> None:
        self.states: dict[str, dict] = {}
        self.calls: list[tuple[str, str, object]] = []
        self.bulk_state_reads = 0
        self.select_option_results: dict[str, bool] = {}
        self.set_number_results: dict[str, bool] = {}
        self.turn_on_results: dict[str, bool] = {}
        self.select_option_exceptions: dict[str, Exception] = {}
        self.set_number_exceptions: dict[str, Exception] = {}
        self.turn_on_exceptions: dict[str, Exception] = {}

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
        if exc := self.turn_on_exceptions.get(entity_id):
            raise exc
        return self.turn_on_results.get(entity_id, True)

    async def select_option(self, entity_id: str, value: str) -> bool:
        self.calls.append(("select_option", entity_id, value))
        if exc := self.select_option_exceptions.get(entity_id):
            raise exc
        return self.select_option_results.get(entity_id, True)

    async def set_number(self, entity_id: str, value: float) -> bool:
        self.calls.append(("set_number", entity_id, value))
        if exc := self.set_number_exceptions.get(entity_id):
            raise exc
        return self.set_number_results.get(entity_id, True)

    async def set_input_text(self, entity_id: str, value: str) -> bool:
        self.calls.append(("set_input_text", entity_id, value))
        return True

    async def set_input_number(self, entity_id: str, value: float) -> bool:
        self.calls.append(("set_input_number", entity_id, value))
        return True


class AutomatedEMSSettlementSpecificationTests(unittest.TestCase):
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
        observed_ems: str = MODE_MAX_SELF,
        export_limit: object = 0.01,
        import_limit: object = 0.01,
        remote_ems: str = "on",
        helper_mode: str | None = None,
        ordinary_runtime: bool = True,
    ) -> tuple[_SettlementRecordingHA, SigEnergyOptimizer]:
        ha = _SettlementRecordingHA()
        cfg = Settings(
            ha_control_switch="switch.test_remote_ems",
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
        optimizer._startup_automated_transition_checked = ordinary_runtime
        self._optimizers.append(optimizer)
        self._seed_live_state(
            ha,
            optimizer,
            observed_ems=observed_ems,
            export_limit=export_limit,
            import_limit=import_limit,
            remote_ems=remote_ems,
            helper_mode=helper_mode,
        )
        return ha, optimizer

    @staticmethod
    def _seed_live_state(
        ha: _SettlementRecordingHA,
        optimizer: SigEnergyOptimizer,
        *,
        observed_ems: str,
        export_limit: object,
        import_limit: object,
        remote_ems: str,
        helper_mode: str | None,
    ) -> None:
        cfg = optimizer.cfg
        ha.set_state(cfg.sigenergy_mode_select, helper_mode or cfg.automated_option)
        ha.set_state(cfg.ems_mode_select, observed_ems)
        ha.set_state(cfg.ha_control_switch, remote_ems)
        ha.set_state(cfg.grid_export_limit, export_limit)
        ha.set_state(cfg.grid_import_limit, import_limit)
        ha.set_state(cfg.pv_max_power_limit, 30.0)
        ha.set_state(cfg.ess_max_charging_limit, 25.0, {"max": 25.0})
        ha.set_state(cfg.ess_max_discharging_limit, 25.0, {"max": 25.0})

    @staticmethod
    def _decision(
        ems_mode: str,
        *,
        export_limit: float = 2.0,
        import_limit: float = 3.0,
        ess_charge_limit: float = 10.0,
        ess_discharge_limit: float = 11.0,
        pv_max_power_limit: float = 20.0,
        needs_ha_control_switch: bool = False,
    ) -> Decision:
        return Decision(
            ems_mode=ems_mode,
            export_limit=export_limit,
            import_limit=import_limit,
            ess_charge_limit=ess_charge_limit,
            ess_discharge_limit=ess_discharge_limit,
            pv_max_power_limit=pv_max_power_limit,
            needs_ha_control_switch=needs_ha_control_switch,
        )

    @staticmethod
    def _inverter_calls(
        ha: _SettlementRecordingHA,
        optimizer: SigEnergyOptimizer,
    ) -> list[tuple[str, str, object]]:
        cfg = optimizer.cfg
        actuator_entities = {
            cfg.ems_mode_select,
            cfg.grid_export_limit,
            cfg.grid_import_limit,
            cfg.ess_max_charging_limit,
            cfg.ess_max_discharging_limit,
            cfg.pv_max_power_limit,
        }
        return [call for call in ha.calls if call[1] in actuator_entities]

    @staticmethod
    def _control_calls(
        ha: _SettlementRecordingHA,
        optimizer: SigEnergyOptimizer,
    ) -> list[tuple[str, str, object]]:
        return [
            call
            for call in ha.calls
            if call[1] == optimizer.cfg.ha_control_switch
            or call in AutomatedEMSSettlementSpecificationTests._inverter_calls(
                ha, optimizer
            )
        ]

    @staticmethod
    def _close_calls(optimizer: SigEnergyOptimizer) -> list[tuple[str, str, object]]:
        cfg = optimizer.cfg
        return [
            ("set_number", cfg.grid_export_limit, cfg.block_flow_limit_value),
            ("set_number", cfg.grid_import_limit, cfg.block_flow_limit_value),
        ]

    @staticmethod
    def _normal_limit_calls(
        optimizer: SigEnergyOptimizer,
        decision: Decision,
    ) -> list[tuple[str, str, object]]:
        cfg = optimizer.cfg
        return [
            ("set_number", cfg.grid_export_limit, decision.export_limit),
            ("set_number", cfg.grid_import_limit, decision.import_limit),
            ("set_number", cfg.ess_max_charging_limit, decision.ess_charge_limit),
            ("set_number", cfg.ess_max_discharging_limit, decision.ess_discharge_limit),
            ("set_number", cfg.pv_max_power_limit, decision.pv_max_power_limit),
        ]

    @staticmethod
    def _observe_grid(
        ha: _SettlementRecordingHA,
        optimizer: SigEnergyOptimizer,
        export_limit: object,
        import_limit: object,
    ) -> None:
        ha.set_state(optimizer.cfg.grid_export_limit, export_limit)
        ha.set_state(optimizer.cfg.grid_import_limit, import_limit)

    @staticmethod
    def _observe_ems(
        ha: _SettlementRecordingHA,
        optimizer: SigEnergyOptimizer,
        ems_mode: str,
    ) -> None:
        ha.set_state(optimizer.cfg.ems_mode_select, ems_mode)

    @staticmethod
    def _run_tick(
        optimizer: SigEnergyOptimizer,
        decision: Decision,
        *,
        now: float,
        catch_tick_exception: bool = False,
    ) -> None:
        with (
            patch("app.optimizer.monotonic", return_value=now),
            patch.object(optimizer, "_decide", return_value=decision),
            patch.object(optimizer, "_record_automation_audit"),
            patch.object(optimizer, "_record_decision_trace"),
            patch.object(optimizer, "_handle_notifications", new=AsyncMock()),
            patch.object(optimizer, "_handle_daily_summaries", new=AsyncMock()),
            patch.object(optimizer, "_accumulate_history"),
            patch.object(optimizer, "_record_price_tracking"),
        ):
            if catch_tick_exception:
                asyncio.run(optimizer._safe_tick())
            else:
                asyncio.run(optimizer._tick())

    def _start_attempted_automated_ems_request(
        self,
        ha: _SettlementRecordingHA,
        optimizer: SigEnergyOptimizer,
        *,
        target: str = MODE_CMD_CHARGE_PV,
        now: float = 100.0,
    ) -> Decision:
        decision = self._decision(target)
        self._run_tick(optimizer, decision, now=now)
        self.assertEqual(
            self._inverter_calls(ha, optimizer),
            [("select_option", optimizer.cfg.ems_mode_select, target)],
        )
        self.assertEqual(
            optimizer._ordinary_ems_settlement.last_requested_target,
            target,
        )
        ha.calls.clear()
        return decision

    def test_each_ordinary_automated_mode_change_uses_settlement_barrier(self) -> None:
        self.assertEqual(len(AUTOMATED_MODE_CHANGES), 16)
        self.assertEqual(
            {
                target
                for observed, target in AUTOMATED_MODE_CHANGES
                if observed == MODE_CMD_DISCHARGE_ESS
            },
            set(APPROVED_AUTOMATED_TARGET_EMS_MODES),
        )
        self.assertNotIn(
            MODE_CMD_DISCHARGE_ESS,
            {target for _, target in AUTOMATED_MODE_CHANGES},
        )
        for observed, target in AUTOMATED_MODE_CHANGES:
            with self.subTest(observed=observed, target=target):
                ha, optimizer = self._optimizer(
                    observed_ems=observed,
                    export_limit=5.0,
                    import_limit=6.0,
                )

                self._run_tick(optimizer, self._decision(target), now=100.0)

                self.assertEqual(
                    self._inverter_calls(ha, optimizer),
                    self._close_calls(optimizer),
                )

    def test_ordinary_settlement_does_not_reuse_manual_transition_or_recovery_state(
        self,
    ) -> None:
        ha, optimizer = self._optimizer(
            observed_ems=MODE_CMD_DISCHARGE_ESS,
            export_limit=5.0,
            import_limit=6.0,
        )
        decision = self._decision(MODE_CMD_CHARGE_PV)

        self.assertEqual(optimizer._automated_transition.phase, "IDLE")
        self.assertFalse(optimizer._ems_mode_recovery_required)

        self._run_tick(optimizer, decision, now=100.0)
        containment_calls = self._inverter_calls(ha, optimizer)
        manual_phase_while_containing = optimizer._automated_transition.phase
        recovery_while_containing = optimizer._ems_mode_recovery_required

        self._observe_grid(ha, optimizer, 0.01, 0.01)
        ha.calls.clear()
        self._run_tick(optimizer, decision, now=101.0)
        target_request_calls = self._inverter_calls(ha, optimizer)

        self.assertEqual(containment_calls, self._close_calls(optimizer))
        self.assertEqual(
            target_request_calls,
            [("select_option", optimizer.cfg.ems_mode_select, MODE_CMD_CHARGE_PV)],
        )
        self.assertEqual(manual_phase_while_containing, "IDLE")
        self.assertEqual(optimizer._automated_transition.phase, "IDLE")
        self.assertFalse(recovery_while_containing)
        self.assertFalse(optimizer._ems_mode_recovery_required)

    def test_ordinary_trusted_ems_change_contains_grid_before_requesting_target(
        self,
    ) -> None:
        ha, optimizer = self._optimizer(
            observed_ems=MODE_CMD_DISCHARGE_PV,
            export_limit=5.0,
            import_limit=6.0,
        )

        self._run_tick(
            optimizer,
            self._decision(MODE_CMD_CHARGE_PV),
            now=100.0,
        )

        self.assertEqual(self._inverter_calls(ha, optimizer), self._close_calls(optimizer))

    def test_ordinary_grid_close_attempts_import_after_export_false(self) -> None:
        ha, optimizer = self._optimizer(
            observed_ems=MODE_CMD_DISCHARGE_PV,
            export_limit=5.0,
            import_limit=6.0,
        )
        ha.set_number_results[optimizer.cfg.grid_export_limit] = False

        self._run_tick(
            optimizer,
            self._decision(MODE_CMD_CHARGE_PV),
            now=100.0,
        )

        self.assertEqual(self._inverter_calls(ha, optimizer), self._close_calls(optimizer))

    def test_ordinary_grid_service_success_requires_later_fresh_observation(self) -> None:
        ha, optimizer = self._optimizer(
            observed_ems=MODE_CMD_DISCHARGE_PV,
            export_limit=5.0,
            import_limit=6.0,
        )
        decision = self._decision(MODE_CMD_CHARGE_PV)

        self._run_tick(optimizer, decision, now=100.0)
        ha.calls.clear()
        self._run_tick(optimizer, decision, now=101.0)

        self.assertEqual(self._inverter_calls(ha, optimizer), [])

        self._observe_grid(ha, optimizer, 0.01, 0.01)
        ha.calls.clear()
        self._run_tick(optimizer, decision, now=102.0)
        self.assertEqual(
            self._inverter_calls(ha, optimizer),
            [("select_option", optimizer.cfg.ems_mode_select, MODE_CMD_CHARGE_PV)],
        )

    def test_ordinary_ems_request_cycle_has_no_dependent_writes(self) -> None:
        ha, optimizer = self._optimizer(observed_ems=MODE_CMD_DISCHARGE_PV)

        self._run_tick(
            optimizer,
            self._decision(MODE_CMD_CHARGE_PV),
            now=100.0,
        )

        self.assertEqual(
            self._inverter_calls(ha, optimizer),
            [("select_option", optimizer.cfg.ems_mode_select, MODE_CMD_CHARGE_PV)],
        )

    def test_ordinary_ems_service_success_requires_later_fresh_observation(self) -> None:
        ha, optimizer = self._optimizer(observed_ems=MODE_CMD_DISCHARGE_PV)
        decision = self._decision(MODE_CMD_CHARGE_PV)

        self._run_tick(optimizer, decision, now=100.0)
        ha.calls.clear()
        self._run_tick(optimizer, decision, now=101.0)

        self.assertEqual(self._inverter_calls(ha, optimizer), [])

    def test_ordinary_fresh_target_observation_applies_latest_dependent_limits(
        self,
    ) -> None:
        ha, optimizer = self._optimizer(observed_ems=MODE_CMD_DISCHARGE_PV)
        initial = self._decision(MODE_CMD_CHARGE_PV)
        latest = self._decision(
            MODE_CMD_CHARGE_PV,
            export_limit=4.0,
            import_limit=5.0,
            ess_charge_limit=6.0,
            ess_discharge_limit=7.0,
            pv_max_power_limit=8.0,
        )

        self._run_tick(optimizer, initial, now=100.0)
        first_cycle_calls = self._inverter_calls(ha, optimizer)
        self._observe_ems(ha, optimizer, MODE_CMD_CHARGE_PV)
        ha.calls.clear()
        self._run_tick(optimizer, latest, now=101.0)

        self.assertEqual(
            first_cycle_calls,
            [("select_option", optimizer.cfg.ems_mode_select, MODE_CMD_CHARGE_PV)],
        )
        self.assertEqual(
            self._inverter_calls(ha, optimizer),
            self._normal_limit_calls(optimizer, latest),
        )

    def test_ordinary_same_mode_limit_changes_apply_immediately(self) -> None:
        ha, optimizer = self._optimizer(
            observed_ems=MODE_CMD_CHARGE_PV,
            export_limit=5.0,
            import_limit=6.0,
        )
        decision = self._decision(MODE_CMD_CHARGE_PV)

        self._run_tick(optimizer, decision, now=100.0)

        self.assertEqual(
            self._inverter_calls(ha, optimizer),
            self._normal_limit_calls(optimizer, decision),
        )

    def test_ordinary_newest_target_supersedes_before_any_ems_request(self) -> None:
        ha, optimizer = self._optimizer(
            observed_ems=MODE_CMD_DISCHARGE_PV,
            export_limit=5.0,
            import_limit=6.0,
        )

        self._run_tick(optimizer, self._decision(MODE_CMD_CHARGE_PV), now=100.0)
        self._run_tick(optimizer, self._decision(MODE_CMD_CHARGE_GRID), now=101.0)
        self._observe_grid(ha, optimizer, 0.01, 0.01)
        self._run_tick(optimizer, self._decision(MODE_CMD_CHARGE_GRID), now=102.0)

        mode_calls = [
            call
            for call in self._inverter_calls(ha, optimizer)
            if call[0] == "select_option"
        ]
        self.assertEqual(
            mode_calls,
            [("select_option", optimizer.cfg.ems_mode_select, MODE_CMD_CHARGE_GRID)],
        )

    def test_ordinary_target_return_before_request_cancels_safely(self) -> None:
        ha, optimizer = self._optimizer(
            observed_ems=MODE_CMD_DISCHARGE_PV,
            export_limit=5.0,
            import_limit=6.0,
        )
        returned = self._decision(MODE_CMD_DISCHARGE_PV)

        self._run_tick(optimizer, self._decision(MODE_CMD_CHARGE_PV), now=100.0)
        ha.calls.clear()
        self._run_tick(optimizer, returned, now=101.0)

        self.assertEqual(
            self._inverter_calls(ha, optimizer),
            self._normal_limit_calls(optimizer, returned),
        )

    def test_ordinary_newest_target_supersedes_after_ems_request(self) -> None:
        ha, optimizer = self._optimizer(observed_ems=MODE_CMD_DISCHARGE_PV)

        self._run_tick(optimizer, self._decision(MODE_CMD_CHARGE_PV), now=100.0)
        self._run_tick(optimizer, self._decision(MODE_CMD_CHARGE_GRID), now=110.0)
        self._run_tick(optimizer, self._decision(MODE_CMD_CHARGE_GRID), now=160.0)

        self.assertEqual(
            self._inverter_calls(ha, optimizer),
            [
                ("select_option", optimizer.cfg.ems_mode_select, MODE_CMD_CHARGE_PV),
                ("select_option", optimizer.cfg.ems_mode_select, MODE_CMD_CHARGE_GRID),
            ],
        )

    def test_ordinary_old_target_observation_cannot_complete_newer_target(self) -> None:
        ha, optimizer = self._optimizer(observed_ems=MODE_CMD_DISCHARGE_PV)

        self._run_tick(optimizer, self._decision(MODE_CMD_CHARGE_PV), now=100.0)
        self._observe_ems(ha, optimizer, MODE_CMD_CHARGE_PV)
        ha.calls.clear()
        self._run_tick(optimizer, self._decision(MODE_CMD_CHARGE_GRID), now=110.0)

        self.assertEqual(self._inverter_calls(ha, optimizer), [])

    def test_ordinary_target_return_after_request_requires_superseding_confirmation(
        self,
    ) -> None:
        ha, optimizer = self._optimizer(observed_ems=MODE_CMD_DISCHARGE_PV)
        returned = self._decision(MODE_CMD_DISCHARGE_PV)

        self._run_tick(optimizer, self._decision(MODE_CMD_CHARGE_PV), now=100.0)
        ha.calls.clear()
        self._run_tick(optimizer, returned, now=110.0)
        self.assertEqual(self._inverter_calls(ha, optimizer), [])

        self._run_tick(optimizer, returned, now=160.0)
        self.assertEqual(
            self._inverter_calls(ha, optimizer),
            [("select_option", optimizer.cfg.ems_mode_select, MODE_CMD_DISCHARGE_PV)],
        )

        ha.calls.clear()
        self._run_tick(optimizer, returned, now=161.0)
        self.assertEqual(
            self._inverter_calls(ha, optimizer),
            self._normal_limit_calls(optimizer, returned),
        )

    def test_ordinary_remote_ems_unavailable_blocks_all_writes(self) -> None:
        ha, optimizer = self._optimizer(
            observed_ems=MODE_CMD_DISCHARGE_PV,
            export_limit=5.0,
            import_limit=6.0,
            remote_ems="unavailable",
        )

        self._run_tick(
            optimizer,
            self._decision(MODE_CMD_CHARGE_PV, needs_ha_control_switch=True),
            now=100.0,
        )

        self.assertEqual(self._control_calls(ha, optimizer), [])

    def test_ordinary_remote_ems_off_requests_only_activation(self) -> None:
        ha, optimizer = self._optimizer(
            observed_ems=MODE_CMD_DISCHARGE_PV,
            export_limit=5.0,
            import_limit=6.0,
            remote_ems="off",
        )
        decision = self._decision(
            MODE_CMD_CHARGE_PV,
            needs_ha_control_switch=True,
        )

        self._run_tick(optimizer, decision, now=100.0)
        self._run_tick(optimizer, decision, now=101.0)

        self.assertEqual(
            self._control_calls(ha, optimizer),
            [("turn_on", optimizer.cfg.ha_control_switch, True)],
        )

    def test_ordinary_untrusted_ems_recovery_precedes_settlement(self) -> None:
        ha, optimizer = self._optimizer(observed_ems=MODE_CMD_DISCHARGE_PV)
        decision = self._decision(MODE_CMD_CHARGE_PV)

        self._run_tick(optimizer, decision, now=100.0)
        self._observe_ems(ha, optimizer, "unavailable")
        ha.calls.clear()
        self._run_tick(optimizer, decision, now=101.0)

        self.assertEqual(
            self._inverter_calls(ha, optimizer),
            [("select_option", optimizer.cfg.ems_mode_select, MODE_MAX_SELF)],
        )

    def test_manual_to_automated_transition_precedes_ordinary_settlement(self) -> None:
        ha, optimizer = self._optimizer(
            observed_ems=MODE_CMD_DISCHARGE_PV,
            export_limit=5.0,
            import_limit=6.0,
            helper_mode="Force Full Export",
        )
        cfg = optimizer.cfg
        optimizer._manual_mode_override = cfg.full_export_option
        optimizer._last_state = asyncio.run(optimizer._read_state())
        asyncio.run(optimizer.apply_manual_mode(cfg.automated_option))
        ha.set_state(cfg.sigenergy_mode_select, cfg.automated_option)
        ha.calls.clear()

        self._run_tick(
            optimizer,
            self._decision(MODE_CMD_CHARGE_PV),
            now=100.0,
        )

        self.assertEqual(self._inverter_calls(ha, optimizer), self._close_calls(optimizer))
        self.assertEqual(
            optimizer.last_decision.trace_values.get("automated_transition_source"),
            "apply_manual_mode",
        )

    def test_ordinary_failed_grid_and_ems_requests_remain_pending(self) -> None:
        with self.subTest(failure="grid close returns false"):
            grid_ha, grid_optimizer = self._optimizer(
                observed_ems=MODE_CMD_DISCHARGE_PV,
                export_limit=5.0,
                import_limit=6.0,
            )
            grid_ha.set_number_results[grid_optimizer.cfg.grid_export_limit] = False
            decision = self._decision(MODE_CMD_CHARGE_PV)

            self._run_tick(grid_optimizer, decision, now=100.0)
            first_calls = self._inverter_calls(grid_ha, grid_optimizer)
            grid_ha.calls.clear()
            self._run_tick(grid_optimizer, decision, now=159.0)

            self.assertEqual(first_calls, self._close_calls(grid_optimizer))
            self.assertEqual(self._inverter_calls(grid_ha, grid_optimizer), [])

            grid_ha.calls.clear()
            self._run_tick(grid_optimizer, decision, now=160.0)
            self.assertEqual(
                self._inverter_calls(grid_ha, grid_optimizer),
                self._close_calls(grid_optimizer),
            )

        with self.subTest(failure="EMS request returns false"):
            ems_ha, ems_optimizer = self._optimizer(
                observed_ems=MODE_CMD_DISCHARGE_PV
            )
            ems_ha.select_option_results[ems_optimizer.cfg.ems_mode_select] = False
            decision = self._decision(MODE_CMD_CHARGE_PV)

            self._run_tick(ems_optimizer, decision, now=100.0)
            first_calls = self._inverter_calls(ems_ha, ems_optimizer)
            ems_ha.calls.clear()
            self._run_tick(ems_optimizer, decision, now=159.0)

            self.assertEqual(
                first_calls,
                [
                    (
                        "select_option",
                        ems_optimizer.cfg.ems_mode_select,
                        MODE_CMD_CHARGE_PV,
                    )
                ],
            )
            self.assertEqual(self._inverter_calls(ems_ha, ems_optimizer), [])

            ems_ha.calls.clear()
            self._run_tick(ems_optimizer, decision, now=160.0)
            self.assertEqual(
                self._inverter_calls(ems_ha, ems_optimizer),
                [
                    (
                        "select_option",
                        ems_optimizer.cfg.ems_mode_select,
                        MODE_CMD_CHARGE_PV,
                    )
                ],
            )

    def test_ordinary_raised_service_exceptions_remain_fail_closed(self) -> None:
        with self.subTest(exception="grid close raises"):
            grid_ha, grid_optimizer = self._optimizer(
                observed_ems=MODE_CMD_DISCHARGE_PV,
                export_limit=5.0,
                import_limit=6.0,
            )
            grid_ha.set_number_exceptions[grid_optimizer.cfg.grid_export_limit] = (
                RuntimeError("grid close failed")
            )
            decision = self._decision(MODE_CMD_CHARGE_PV)

            self._run_tick(
                grid_optimizer,
                decision,
                now=100.0,
                catch_tick_exception=True,
            )
            first_calls = self._inverter_calls(grid_ha, grid_optimizer)
            grid_ha.calls.clear()
            self._run_tick(
                grid_optimizer,
                decision,
                now=159.0,
                catch_tick_exception=True,
            )

            self.assertEqual(
                first_calls,
                [
                    (
                        "set_number",
                        grid_optimizer.cfg.grid_export_limit,
                        grid_optimizer.cfg.block_flow_limit_value,
                    ),
                    (
                        "set_number",
                        grid_optimizer.cfg.grid_import_limit,
                        grid_optimizer.cfg.block_flow_limit_value,
                    ),
                ],
            )
            self.assertEqual(self._inverter_calls(grid_ha, grid_optimizer), [])

            grid_ha.calls.clear()
            self._run_tick(
                grid_optimizer,
                decision,
                now=160.0,
                catch_tick_exception=True,
            )
            self.assertEqual(
                self._inverter_calls(grid_ha, grid_optimizer),
                [
                    (
                        "set_number",
                        grid_optimizer.cfg.grid_export_limit,
                        grid_optimizer.cfg.block_flow_limit_value,
                    ),
                    (
                        "set_number",
                        grid_optimizer.cfg.grid_import_limit,
                        grid_optimizer.cfg.block_flow_limit_value,
                    ),
                ],
            )

        with self.subTest(exception="EMS request raises"):
            ems_ha, ems_optimizer = self._optimizer(
                observed_ems=MODE_CMD_DISCHARGE_PV
            )
            ems_ha.select_option_exceptions[ems_optimizer.cfg.ems_mode_select] = (
                RuntimeError("EMS request failed")
            )
            decision = self._decision(MODE_CMD_CHARGE_PV)

            self._run_tick(
                ems_optimizer,
                decision,
                now=100.0,
                catch_tick_exception=True,
            )
            first_calls = self._inverter_calls(ems_ha, ems_optimizer)
            ems_ha.calls.clear()
            self._run_tick(
                ems_optimizer,
                decision,
                now=159.0,
                catch_tick_exception=True,
            )

            self.assertEqual(
                first_calls,
                [
                    (
                        "select_option",
                        ems_optimizer.cfg.ems_mode_select,
                        MODE_CMD_CHARGE_PV,
                    )
                ],
            )
            self.assertEqual(self._inverter_calls(ems_ha, ems_optimizer), [])

            ems_ha.calls.clear()
            self._run_tick(
                ems_optimizer,
                decision,
                now=160.0,
                catch_tick_exception=True,
            )
            self.assertEqual(
                self._inverter_calls(ems_ha, ems_optimizer),
                [
                    (
                        "select_option",
                        ems_optimizer.cfg.ems_mode_select,
                        MODE_CMD_CHARGE_PV,
                    )
                ],
            )

    def test_ordinary_untrusted_or_reopened_grid_returns_to_containment(self) -> None:
        cases = (
            ("export reopened", 1.0, 0.01, "grid_export_limit"),
            ("export untrusted", "unavailable", 0.01, None),
            ("import reopened", 0.01, 1.0, "grid_import_limit"),
            ("import untrusted", 0.01, "unavailable", None),
        )
        for label, export_observation, import_observation, close_entity_attr in cases:
            with self.subTest(grid=label):
                ha, optimizer = self._optimizer(
                    observed_ems=MODE_CMD_DISCHARGE_PV
                )
                decision = self._decision(MODE_CMD_CHARGE_PV)
                self._run_tick(optimizer, decision, now=100.0)
                self._observe_ems(ha, optimizer, MODE_CMD_CHARGE_PV)
                self._observe_grid(
                    ha,
                    optimizer,
                    export_observation,
                    import_observation,
                )
                ha.calls.clear()

                self._run_tick(optimizer, decision, now=101.0)

                expected = (
                    [
                        (
                            "set_number",
                            getattr(optimizer.cfg, close_entity_attr),
                            optimizer.cfg.block_flow_limit_value,
                        )
                    ]
                    if close_entity_attr is not None
                    else []
                )
                self.assertEqual(self._inverter_calls(ha, optimizer), expected)

    def test_ordinary_prolonged_pending_never_fails_open(self) -> None:
        ha, optimizer = self._optimizer(observed_ems=MODE_CMD_DISCHARGE_PV)
        decision = self._decision(MODE_CMD_CHARGE_PV)

        self._run_tick(optimizer, decision, now=0.0)
        ha.calls.clear()
        for heartbeat_time in (10.0, 59.0, 60.0, 301.0):
            self._run_tick(optimizer, decision, now=heartbeat_time)

        calls = self._inverter_calls(ha, optimizer)
        self.assertTrue(calls)
        self.assertTrue(
            all(
                call
                == ("select_option", optimizer.cfg.ems_mode_select, MODE_CMD_CHARGE_PV)
                for call in calls
            )
        )
        self.assertFalse(any(call[0] == "set_number" for call in calls))

    def test_ordinary_settlement_requires_real_fresh_read_cycles(self) -> None:
        ha, optimizer = self._optimizer(
            observed_ems=MODE_CMD_DISCHARGE_PV,
            export_limit=5.0,
            import_limit=6.0,
        )
        decision = self._decision(MODE_CMD_CHARGE_PV)
        reads_before = ha.bulk_state_reads

        self._run_tick(optimizer, decision, now=100.0)
        ha.calls.clear()
        self._run_tick(optimizer, decision, now=101.0)

        self.assertEqual(ha.bulk_state_reads, reads_before + 2)
        self.assertEqual(self._inverter_calls(ha, optimizer), [])

        self._observe_grid(ha, optimizer, 0.01, 0.01)
        ha.calls.clear()
        self._run_tick(optimizer, decision, now=102.0)
        self.assertEqual(ha.bulk_state_reads, reads_before + 3)
        self.assertEqual(
            self._inverter_calls(ha, optimizer),
            [("select_option", optimizer.cfg.ems_mode_select, MODE_CMD_CHARGE_PV)],
        )

    def test_ordinary_restart_mismatch_uses_existing_startup_containment(self) -> None:
        with self.subTest(startup="mismatch"):
            ha, optimizer = self._optimizer(
                observed_ems=MODE_CMD_DISCHARGE_PV,
                export_limit=5.0,
                import_limit=6.0,
                ordinary_runtime=False,
            )

            self._run_tick(
                optimizer,
                self._decision(MODE_CMD_CHARGE_PV),
                now=100.0,
            )

            self.assertEqual(
                self._inverter_calls(ha, optimizer),
                self._close_calls(optimizer),
            )
            self.assertEqual(
                optimizer.last_decision.trace_values.get("automated_transition_source"),
                "startup",
            )

        with self.subTest(startup="already matching"):
            ha, optimizer = self._optimizer(
                observed_ems=MODE_CMD_CHARGE_PV,
                export_limit=5.0,
                import_limit=6.0,
                ordinary_runtime=False,
            )
            decision = self._decision(MODE_CMD_CHARGE_PV)

            self._run_tick(optimizer, decision, now=100.0)

            self.assertEqual(
                self._inverter_calls(ha, optimizer),
                self._normal_limit_calls(optimizer, decision),
            )

    def test_ordinary_barrier_does_not_change_manual_mode_mappings(self) -> None:
        _, optimizer = self._optimizer()
        cfg = optimizer.cfg
        state = SolarState(
            ess_max_charge_kw=25.0,
            ess_max_discharge_kw=25.0,
            ess_charge_limit_entity_max_kw=25.0,
            ess_discharge_limit_entity_max_kw=25.0,
        )
        cases = (
            (cfg.full_export_option, MODE_CMD_DISCHARGE_PV, 25.0, 0.01),
            (cfg.full_import_option, MODE_CMD_CHARGE_GRID, 0.01, 25.0),
            (cfg.full_import_pv_option, MODE_CMD_CHARGE_PV, 0.01, 25.0),
            (cfg.block_flow_option, MODE_MAX_SELF, 0.01, 0.01),
        )

        for mode_label, ems_mode, export_limit, import_limit in cases:
            with self.subTest(mode=mode_label):
                targets = optimizer._manual_mode_targets(mode_label, state)
                self.assertIsNotNone(targets)
                self.assertEqual(targets["ems_mode"], ems_mode)
                self.assertEqual(targets["grid_export_limit"], export_limit)
                self.assertEqual(targets["grid_import_limit"], import_limit)

        self.assertIsNone(optimizer._manual_mode_targets(cfg.manual_option, state))

    def test_ordinary_barrier_preserves_pv_only_max_self_requirement(self) -> None:
        ha, optimizer = self._optimizer(observed_ems=MODE_CMD_DISCHARGE_PV)
        decision = self._decision(MODE_MAX_SELF, export_limit=1.0, import_limit=0.0)
        decision.trace_values["export_value_gate_export_type"] = "pv_surplus_only"

        self._run_tick(optimizer, decision, now=100.0)

        calls = self._inverter_calls(ha, optimizer)
        self.assertEqual(
            calls,
            [("select_option", optimizer.cfg.ems_mode_select, MODE_MAX_SELF)],
        )
        self.assertNotIn(
            ("select_option", optimizer.cfg.ems_mode_select, MODE_CMD_DISCHARGE_PV),
            calls,
        )

    def test_ordinary_invalid_containment_config_blocks_all_writes(self) -> None:
        invalid_values = (
            ("negative", -0.01),
            ("above closed threshold", 0.012),
            ("not a number", float("nan")),
            ("infinite", float("inf")),
        )
        for label, invalid_value in invalid_values:
            with self.subTest(value=label):
                ha, optimizer = self._optimizer(
                    observed_ems=MODE_CMD_DISCHARGE_PV,
                    export_limit=5.0,
                    import_limit=6.0,
                )
                optimizer.cfg.block_flow_limit_value = invalid_value
                decision = self._decision(MODE_CMD_CHARGE_PV)

                for now in (100.0, 101.0, 401.0):
                    self._run_tick(optimizer, decision, now=now)

                self.assertEqual(self._control_calls(ha, optimizer), [])
                self.assertNotEqual(
                    decision.trace_values.get("ordinary_ems_settlement_phase"),
                    "IDLE",
                )
                self.assertIn(
                    "invalid",
                    str(
                        decision.trace_values.get(
                            "ordinary_ems_settlement_block_reason",
                            "",
                        )
                    ).lower(),
                )

    def test_ordinary_initial_containment_handles_trusted_and_untrusted_sides(
        self,
    ) -> None:
        missing = object()
        cases = (
            ("export open import unavailable", 5.0, "unavailable", ("export",)),
            ("export missing import open", missing, 6.0, ("import",)),
            ("export unavailable import missing", "unavailable", missing, ()),
            ("export contained import open", 0.01, 6.0, ("import",)),
            ("export open import contained", 5.0, 0.01, ("export",)),
            ("both contained", 0.01, 0.01, ("ems",)),
        )
        for label, export_observation, import_observation, expected_actions in cases:
            with self.subTest(grid=label):
                ha, optimizer = self._optimizer(
                    observed_ems=MODE_CMD_DISCHARGE_PV,
                )
                cfg = optimizer.cfg
                if export_observation is missing:
                    ha.states.pop(cfg.grid_export_limit, None)
                else:
                    ha.set_state(cfg.grid_export_limit, export_observation)
                if import_observation is missing:
                    ha.states.pop(cfg.grid_import_limit, None)
                else:
                    ha.set_state(cfg.grid_import_limit, import_observation)

                self._run_tick(
                    optimizer,
                    self._decision(MODE_CMD_CHARGE_PV),
                    now=100.0,
                )

                expected_calls: list[tuple[str, str, object]] = []
                if "export" in expected_actions:
                    expected_calls.append(
                        (
                            "set_number",
                            cfg.grid_export_limit,
                            cfg.block_flow_limit_value,
                        )
                    )
                if "import" in expected_actions:
                    expected_calls.append(
                        (
                            "set_number",
                            cfg.grid_import_limit,
                            cfg.block_flow_limit_value,
                        )
                    )
                if "ems" in expected_actions:
                    expected_calls.append(
                        ("select_option", cfg.ems_mode_select, MODE_CMD_CHARGE_PV)
                    )
                observed_state = optimizer._last_state
                self.assertIsNotNone(observed_state)
                if export_observation is missing or export_observation == "unavailable":
                    self.assertFalse(observed_state.current_export_limit_trusted)
                    self.assertEqual(observed_state.current_export_limit, 0.0)
                if import_observation is missing or import_observation == "unavailable":
                    self.assertFalse(observed_state.current_import_limit_trusted)
                    self.assertEqual(observed_state.current_import_limit, 0.0)
                self.assertEqual(self._inverter_calls(ha, optimizer), expected_calls)

    def test_ordinary_remote_ems_observed_on_resumes_pending_settlement(self) -> None:
        ha, optimizer = self._optimizer(
            observed_ems=MODE_CMD_DISCHARGE_PV,
            export_limit="unavailable",
            import_limit="unavailable",
        )
        initial_decision = self._decision(
            MODE_CMD_CHARGE_PV,
            needs_ha_control_switch=True,
        )
        newest_decision = self._decision(
            MODE_CMD_CHARGE_GRID,
            needs_ha_control_switch=True,
        )

        self._run_tick(optimizer, initial_decision, now=100.0)
        initial_calls = self._control_calls(ha, optimizer)

        ha.set_state(optimizer.cfg.ha_control_switch, "unavailable")
        self._observe_grid(ha, optimizer, 5.0, 6.0)
        ha.calls.clear()
        self._run_tick(optimizer, newest_decision, now=101.0)
        unavailable_calls = self._control_calls(ha, optimizer)

        ha.set_state(optimizer.cfg.ha_control_switch, "off")
        ha.calls.clear()
        self._run_tick(optimizer, newest_decision, now=102.0)
        activation_calls = self._control_calls(ha, optimizer)

        ha.calls.clear()
        self._run_tick(optimizer, newest_decision, now=103.0)
        unconfirmed_calls = self._control_calls(ha, optimizer)

        ha.set_state(optimizer.cfg.ha_control_switch, "on")
        ha.calls.clear()
        self._run_tick(optimizer, newest_decision, now=104.0)
        resumed_calls = self._inverter_calls(ha, optimizer)

        self._observe_grid(ha, optimizer, 0.01, 0.01)
        ha.calls.clear()
        self._run_tick(optimizer, newest_decision, now=105.0)
        target_request_calls = self._inverter_calls(ha, optimizer)

        self.assertEqual(initial_calls, [])
        self.assertEqual(unavailable_calls, [])
        self.assertEqual(
            activation_calls,
            [("turn_on", optimizer.cfg.ha_control_switch, True)],
        )
        self.assertEqual(unconfirmed_calls, [])
        self.assertEqual(
            resumed_calls,
            self._close_calls(optimizer),
        )
        self.assertEqual(
            target_request_calls,
            [
                (
                    "select_option",
                    optimizer.cfg.ems_mode_select,
                    MODE_CMD_CHARGE_GRID,
                )
            ],
        )
        self.assertNotIn(
            ("select_option", optimizer.cfg.ems_mode_select, MODE_CMD_CHARGE_PV),
            resumed_calls + target_request_calls,
        )

    def test_ordinary_recovery_observed_max_self_resumes_pending_settlement(
        self,
    ) -> None:
        ha, optimizer = self._optimizer(
            observed_ems=MODE_CMD_DISCHARGE_PV,
            export_limit="unavailable",
            import_limit="unavailable",
        )
        decision = self._decision(MODE_CMD_CHARGE_PV)

        self._run_tick(optimizer, decision, now=100.0)
        initial_calls = self._inverter_calls(ha, optimizer)

        self._observe_ems(ha, optimizer, "unavailable")
        self._observe_grid(ha, optimizer, 5.0, 6.0)
        ha.calls.clear()
        self._run_tick(optimizer, decision, now=101.0)
        recovery_calls = self._inverter_calls(ha, optimizer)

        ha.calls.clear()
        self._run_tick(optimizer, decision, now=102.0)
        unconfirmed_recovery_calls = self._inverter_calls(ha, optimizer)

        self._observe_ems(ha, optimizer, MODE_MAX_SELF)
        ha.calls.clear()
        self._run_tick(optimizer, decision, now=103.0)
        resumed_calls = self._inverter_calls(ha, optimizer)

        self._observe_grid(ha, optimizer, 0.01, 0.01)
        ha.calls.clear()
        self._run_tick(optimizer, decision, now=104.0)
        target_request_calls = self._inverter_calls(ha, optimizer)

        ha.calls.clear()
        self._run_tick(optimizer, decision, now=105.0)
        unconfirmed_target_calls = self._inverter_calls(ha, optimizer)

        self.assertEqual(initial_calls, [])
        self.assertEqual(
            recovery_calls,
            [("select_option", optimizer.cfg.ems_mode_select, MODE_MAX_SELF)],
        )
        self.assertEqual(unconfirmed_recovery_calls, [])
        self.assertEqual(resumed_calls, self._close_calls(optimizer))
        self.assertEqual(
            target_request_calls,
            [("select_option", optimizer.cfg.ems_mode_select, MODE_CMD_CHARGE_PV)],
        )
        self.assertEqual(unconfirmed_target_calls, [])

    def test_api_preset_manual_takeover_after_attempted_automated_request(
        self,
    ) -> None:
        ha, optimizer = self._optimizer(
            observed_ems=MODE_CMD_DISCHARGE_PV,
            export_limit=0.01,
            import_limit=0.01,
        )
        automated_target = MODE_CMD_CHARGE_PV
        self._start_attempted_automated_ems_request(
            ha,
            optimizer,
            target=automated_target,
        )
        cfg = optimizer.cfg
        manual_mode = cfg.full_export_option

        asyncio.run(optimizer.apply_manual_mode(manual_mode))
        calls = self._inverter_calls(ha, optimizer)

        self.assertEqual(optimizer._manual_mode_override, manual_mode)
        self.assertIn(
            ("select_option", cfg.ems_mode_select, MODE_CMD_DISCHARGE_PV),
            calls,
        )
        self.assertNotIn(
            ("select_option", cfg.ems_mode_select, automated_target),
            calls,
        )
        self.assertEqual(
            [call for call in calls if call[0] == "set_number"],
            [],
            "Manual dependent targets must wait for later Manual EMS observation",
        )

    def test_helper_observed_preset_manual_takeover_after_attempted_automated_request(
        self,
    ) -> None:
        ha, optimizer = self._optimizer(
            observed_ems=MODE_CMD_DISCHARGE_PV,
            export_limit=0.01,
            import_limit=0.01,
        )
        automated_target = MODE_CMD_CHARGE_PV
        decision = self._start_attempted_automated_ems_request(
            ha,
            optimizer,
            target=automated_target,
        )
        cfg = optimizer.cfg
        manual_mode = cfg.full_export_option
        manual_targets = optimizer._manual_mode_targets(
            manual_mode,
            optimizer._last_state,
        )
        self.assertIsNotNone(manual_targets)
        ha.set_state(cfg.sigenergy_mode_select, manual_mode)

        self._run_tick(optimizer, decision, now=101.0)
        calls = self._inverter_calls(ha, optimizer)

        self.assertEqual(optimizer._last_state.sigenergy_mode, manual_mode)
        self.assertIn(
            ("select_option", cfg.ems_mode_select, MODE_CMD_DISCHARGE_PV),
            calls,
        )
        self.assertNotIn(
            ("select_option", cfg.ems_mode_select, automated_target),
            calls,
        )
        self.assertEqual(
            [call for call in calls if call[0] == "set_number"],
            [],
            "Helper-observed Manual takeover must retain the safety barrier",
        )

        ha.set_state(cfg.ems_mode_select, MODE_CMD_DISCHARGE_PV)
        ha.calls.clear()
        reads_before_confirmation = ha.bulk_state_reads
        self._run_tick(optimizer, decision, now=102.0)
        confirmed_cycle_calls = self._inverter_calls(ha, optimizer)

        self.assertGreater(ha.bulk_state_reads, reads_before_confirmation)
        self.assertIn(
            (
                "set_number",
                cfg.grid_export_limit,
                manual_targets["grid_export_limit"],
            ),
            confirmed_cycle_calls,
        )

    def test_preset_manual_takeover_requires_later_independent_ems_observation(
        self,
    ) -> None:
        ha, optimizer = self._optimizer(
            observed_ems=MODE_MAX_SELF,
            export_limit=0.01,
            import_limit=0.01,
        )
        decision = self._start_attempted_automated_ems_request(ha, optimizer)
        cfg = optimizer.cfg
        manual_mode = cfg.full_export_option
        manual_target = MODE_CMD_DISCHARGE_PV
        manual_targets = optimizer._manual_mode_targets(
            manual_mode,
            optimizer._last_state,
        )
        self.assertIsNotNone(manual_targets)

        same_operation_poll = AsyncMock(return_value=manual_target)
        with patch.object(ha, "get_state_value", new=same_operation_poll):
            asyncio.run(optimizer.apply_manual_mode(manual_mode))
        request_cycle_calls = self._inverter_calls(ha, optimizer)

        self.assertEqual(
            same_operation_poll.await_count,
            0,
            "Same-operation polling must not count as Manual EMS confirmation",
        )
        self.assertIn(
            ("select_option", cfg.ems_mode_select, manual_target),
            request_cycle_calls,
        )
        self.assertEqual(
            [call for call in request_cycle_calls if call[0] == "set_number"],
            [],
            "Manual dependent targets must not be written in the EMS request operation",
        )

        ha.set_state(cfg.sigenergy_mode_select, manual_mode)
        ha.set_state(cfg.ems_mode_select, manual_target)
        ha.calls.clear()
        reads_before_confirmation = ha.bulk_state_reads
        self._run_tick(optimizer, decision, now=101.0)
        confirmed_cycle_calls = self._inverter_calls(ha, optimizer)

        self.assertGreater(ha.bulk_state_reads, reads_before_confirmation)
        self.assertIn(
            (
                "set_number",
                cfg.grid_export_limit,
                manual_targets["grid_export_limit"],
            ),
            confirmed_cycle_calls,
        )

    def test_unrestricted_manual_with_outstanding_automated_request_stays_contained_and_targetless(
        self,
    ) -> None:
        ha, optimizer = self._optimizer(
            observed_ems=MODE_MAX_SELF,
            export_limit=0.01,
            import_limit=0.01,
        )
        decision = self._start_attempted_automated_ems_request(ha, optimizer)
        cfg = optimizer.cfg
        self._observe_grid(ha, optimizer, 5.0, 6.0)

        asyncio.run(optimizer.apply_manual_mode(cfg.manual_option))
        first_calls = self._inverter_calls(ha, optimizer)

        self.assertEqual(optimizer._manual_mode_override, cfg.manual_option)
        self.assertEqual(first_calls, self._close_calls(optimizer))
        self.assertNotIn(
            ("select_option", cfg.ems_mode_select, MODE_MAX_SELF),
            first_calls,
        )

        ha.set_state(cfg.sigenergy_mode_select, cfg.manual_option)
        self._observe_grid(ha, optimizer, 0.01, 0.01)
        ha.calls.clear()
        self._run_tick(optimizer, decision, now=101.0)

        self.assertEqual(self._inverter_calls(ha, optimizer), [])

    def test_unrestricted_manual_without_outstanding_request_preserves_existing_behavior(
        self,
    ) -> None:
        ha, optimizer = self._optimizer(
            observed_ems=MODE_MAX_SELF,
            export_limit=5.0,
            import_limit=6.0,
        )
        cfg = optimizer.cfg
        self.assertEqual(
            optimizer._automated_transition.last_requested_target,
            "",
        )
        self.assertEqual(
            optimizer._ordinary_ems_settlement.last_requested_target,
            "",
        )

        asyncio.run(optimizer.apply_manual_mode(cfg.manual_option))

        self.assertEqual(optimizer._manual_mode_override, cfg.manual_option)
        self.assertEqual(self._inverter_calls(ha, optimizer), [])

        ha.set_state(cfg.sigenergy_mode_select, cfg.manual_option)
        ha.calls.clear()
        self._run_tick(
            optimizer,
            self._decision(MODE_CMD_CHARGE_PV),
            now=101.0,
        )
        self.assertEqual(self._inverter_calls(ha, optimizer), [])

    def test_manual_takeover_immediately_recontains_after_dependent_write_failure(
        self,
    ) -> None:
        ha, optimizer = self._optimizer(
            observed_ems=MODE_MAX_SELF,
            export_limit=0.01,
            import_limit=0.01,
        )
        decision = self._start_attempted_automated_ems_request(ha, optimizer)
        cfg = optimizer.cfg
        manual_mode = cfg.full_export_option
        manual_targets = optimizer._manual_mode_targets(
            manual_mode,
            optimizer._last_state,
        )
        self.assertIsNotNone(manual_targets)

        asyncio.run(optimizer.apply_manual_mode(manual_mode))
        ha.set_state(cfg.sigenergy_mode_select, manual_mode)
        ha.set_state(cfg.ems_mode_select, MODE_CMD_DISCHARGE_PV)
        ha.set_number_results[cfg.pv_max_power_limit] = False
        ha.calls.clear()

        self._run_tick(optimizer, decision, now=101.0)
        calls = self._inverter_calls(ha, optimizer)
        open_export = ("set_number", cfg.grid_export_limit, manual_targets["grid_export_limit"])
        failed_pv = ("set_number", cfg.pv_max_power_limit, manual_targets["pv_max_power_limit"])
        close_export = ("set_number", cfg.grid_export_limit, cfg.block_flow_limit_value)
        close_import = ("set_number", cfg.grid_import_limit, cfg.block_flow_limit_value)

        self.assertIn(open_export, calls)
        self.assertIn(failed_pv, calls)
        self.assertLess(calls.index(open_export), calls.index(failed_pv))
        post_failure_calls = calls[calls.index(failed_pv) + 1 :]
        self.assertIn(close_export, post_failure_calls)
        self.assertIn(close_import, post_failure_calls)
        self.assertLess(post_failure_calls.index(close_export), post_failure_calls.index(close_import))
        self.assertTrue(decision.trace_gates.get("manual_takeover_pending"))
        self.assertNotIn(("select_option", cfg.ems_mode_select, MODE_MAX_SELF), post_failure_calls)

    def test_block_flow_takeover_preserves_existing_ess_override_pinning(self) -> None:
        ha, optimizer = self._optimizer(
            observed_ems=MODE_CMD_DISCHARGE_PV,
            export_limit=0.01,
            import_limit=0.01,
        )
        decision = self._start_attempted_automated_ems_request(ha, optimizer)
        cfg = optimizer.cfg
        manual_mode = cfg.block_flow_option
        initial_targets = optimizer._manual_mode_targets(
            manual_mode, optimizer._last_state, include_block_flow_ess_limits=True
        )
        self.assertIsNotNone(initial_targets)

        asyncio.run(optimizer.apply_manual_mode(manual_mode))
        ha.set_state(cfg.sigenergy_mode_select, manual_mode)
        ha.set_state(cfg.ems_mode_select, MODE_MAX_SELF)
        ha.calls.clear()
        self._run_tick(optimizer, decision, now=101.0)
        initial_calls = self._inverter_calls(ha, optimizer)

        initial_charge = float(initial_targets["ess_charge_limit"])
        initial_discharge = float(initial_targets["ess_discharge_limit"])
        self.assertIn(("set_number", cfg.ess_max_charging_limit, initial_charge), initial_calls)
        self.assertIn(("set_number", cfg.ess_max_discharging_limit, initial_discharge), initial_calls)

        changed_charge = initial_charge + 5.0
        changed_discharge = initial_discharge + 5.0
        ha.set_state(cfg.grid_export_limit, initial_targets["grid_export_limit"])
        ha.set_state(cfg.grid_import_limit, initial_targets["grid_import_limit"])
        ha.set_state(cfg.pv_max_power_limit, initial_targets["pv_max_power_limit"])
        ha.set_state(cfg.ess_max_charging_limit, 1.0, {"max": changed_charge})
        ha.set_state(cfg.ess_max_discharging_limit, 1.0, {"max": changed_discharge})
        ha.calls.clear()

        self._run_tick(optimizer, decision, now=102.0)
        drift_calls = self._inverter_calls(ha, optimizer)

        self.assertIn(("set_number", cfg.ess_max_charging_limit, initial_charge), drift_calls)
        self.assertIn(("set_number", cfg.ess_max_discharging_limit, initial_discharge), drift_calls)
        self.assertNotIn(("set_number", cfg.ess_max_charging_limit, changed_charge), drift_calls)
        self.assertNotIn(("set_number", cfg.ess_max_discharging_limit, changed_discharge), drift_calls)
        self.assertEqual(optimizer._manual_ess_charge_override_kw, initial_charge)
        self.assertEqual(optimizer._manual_ess_discharge_override_kw, initial_discharge)

    def test_successful_manual_reentry_cancels_ordinary_settlement(self) -> None:
        ha, optimizer = self._optimizer(
            observed_ems=MODE_CMD_DISCHARGE_PV,
            export_limit="unavailable",
            import_limit="unavailable",
        )
        stale_ordinary_decision = self._decision(MODE_CMD_CHARGE_PV)

        self._run_tick(optimizer, stale_ordinary_decision, now=100.0)
        initial_calls = self._control_calls(ha, optimizer)

        cfg = optimizer.cfg
        asyncio.run(optimizer.apply_manual_mode(cfg.full_export_option))
        self.assertEqual(optimizer._manual_mode_override, cfg.full_export_option)
        ordinary_phase_after_manual_reentry = getattr(
            getattr(optimizer, "_ordinary_ems_settlement", None),
            "phase",
            None,
        )
        manual_targets = optimizer._manual_mode_targets(
            cfg.full_export_option,
            optimizer._last_state,
        )
        self.assertIsNotNone(manual_targets)
        ha.set_state(cfg.sigenergy_mode_select, cfg.full_export_option)
        ha.set_state(cfg.ems_mode_select, manual_targets["ems_mode"])
        ha.set_state(cfg.grid_export_limit, manual_targets["grid_export_limit"])
        ha.set_state(cfg.grid_import_limit, manual_targets["grid_import_limit"])
        ha.set_state(cfg.pv_max_power_limit, manual_targets["pv_max_power_limit"])
        ha.set_state(
            cfg.ess_max_charging_limit,
            manual_targets["ess_charge_limit"],
            {"max": 25.0},
        )
        ha.set_state(
            cfg.ess_max_discharging_limit,
            manual_targets["ess_discharge_limit"],
            {"max": 25.0},
        )

        ha.calls.clear()
        self._run_tick(optimizer, stale_ordinary_decision, now=101.0)
        manual_tick_calls = self._inverter_calls(ha, optimizer)

        with patch("app.optimizer.monotonic", return_value=102.0):
            asyncio.run(optimizer.apply_manual_mode(cfg.automated_option))
        self.assertEqual(optimizer._automated_transition.phase, "CONTAINING_GRID")

        newest_automated_decision = self._decision(MODE_CMD_CHARGE_GRID)
        ha.set_state(cfg.sigenergy_mode_select, cfg.automated_option)
        self._observe_grid(ha, optimizer, 5.0, 6.0)
        ha.calls.clear()
        self._run_tick(optimizer, newest_automated_decision, now=103.0)
        manual_transition_close_calls = self._inverter_calls(ha, optimizer)

        self._observe_grid(ha, optimizer, 0.01, 0.01)
        ha.calls.clear()
        self._run_tick(optimizer, newest_automated_decision, now=104.0)
        newest_target_request_calls = self._inverter_calls(ha, optimizer)

        self._observe_ems(ha, optimizer, MODE_CMD_CHARGE_GRID)
        ha.calls.clear()
        self._run_tick(optimizer, newest_automated_decision, now=105.0)
        applied_normal_calls = self._inverter_calls(ha, optimizer)

        self.assertEqual(initial_calls, [])
        self.assertEqual(manual_tick_calls, [])
        self.assertEqual(ordinary_phase_after_manual_reentry, "IDLE")
        self.assertEqual(manual_transition_close_calls, self._close_calls(optimizer))
        self.assertEqual(
            newest_target_request_calls,
            [
                (
                    "select_option",
                    cfg.ems_mode_select,
                    MODE_CMD_CHARGE_GRID,
                )
            ],
        )
        self.assertEqual(
            applied_normal_calls,
            self._normal_limit_calls(optimizer, newest_automated_decision),
        )
        self.assertEqual(optimizer._automated_transition.phase, "IDLE")
        self.assertNotIn(
            ("select_option", cfg.ems_mode_select, MODE_CMD_CHARGE_PV),
            manual_tick_calls
            + manual_transition_close_calls
            + newest_target_request_calls
            + applied_normal_calls,
        )

    def test_ordinary_settlement_diagnostics_expose_pending_safety_state(
        self,
    ) -> None:
        ha, optimizer = self._optimizer(
            observed_ems=MODE_CMD_DISCHARGE_PV,
            export_limit=5.0,
            import_limit=6.0,
        )
        decision = self._decision(MODE_CMD_CHARGE_PV)

        self._run_tick(optimizer, decision, now=100.0)

        required_keys = {
            "ordinary_ems_settlement_phase",
            "ordinary_ems_settlement_initial_observed_ems",
            "ordinary_ems_settlement_current_observed_ems",
            "ordinary_ems_settlement_target_ems",
            "ordinary_ems_settlement_last_requested_target",
            "ordinary_ems_settlement_elapsed_seconds",
            "ordinary_ems_settlement_retry_suppressed",
            "ordinary_ems_settlement_blocked_writes",
            "ordinary_ems_settlement_block_reason",
            "ordinary_ems_settlement_higher_precedence",
        }
        values = decision.trace_values
        self.assertTrue(required_keys.issubset(values))
        self.assertEqual(values["ordinary_ems_settlement_phase"], "CONTAINING_GRID")
        self.assertEqual(
            values["ordinary_ems_settlement_initial_observed_ems"],
            MODE_CMD_DISCHARGE_PV,
        )
        self.assertEqual(
            values["ordinary_ems_settlement_current_observed_ems"],
            MODE_CMD_DISCHARGE_PV,
        )
        self.assertEqual(
            values["ordinary_ems_settlement_target_ems"],
            MODE_CMD_CHARGE_PV,
        )
        self.assertIn(
            values["ordinary_ems_settlement_last_requested_target"],
            (None, ""),
        )
        self.assertGreaterEqual(
            float(values["ordinary_ems_settlement_elapsed_seconds"]),
            0.0,
        )
        self.assertIs(values["ordinary_ems_settlement_retry_suppressed"], False)
        self.assertTrue(values["ordinary_ems_settlement_blocked_writes"])
        block_reason = str(values["ordinary_ems_settlement_block_reason"]).strip()
        self.assertTrue(block_reason)
        self.assertTrue(
            "grid" in block_reason.lower() or "contain" in block_reason.lower()
        )
        self.assertIn(
            values["ordinary_ems_settlement_higher_precedence"],
            (None, "", "none", False),
        )
        self.assertEqual(
            self._inverter_calls(ha, optimizer),
            self._close_calls(optimizer),
        )

    def test_ordinary_settlement_warning_is_throttled_without_clearing(self) -> None:
        ha, optimizer = self._optimizer(
            observed_ems=MODE_CMD_DISCHARGE_PV,
            export_limit="unavailable",
            import_limit="unavailable",
        )
        decision = self._decision(MODE_CMD_CHARGE_PV)

        self._run_tick(optimizer, decision, now=0.0)
        initial_calls = self._control_calls(ha, optimizer)
        ha.calls.clear()

        with patch("app.optimizer.logger.warning") as warning:
            self._run_tick(optimizer, decision, now=300.0)
            due_count = warning.call_count

            self._run_tick(optimizer, decision, now=599.0)
            within_interval_count = warning.call_count

            self._run_tick(optimizer, decision, now=600.0)
            after_interval_count = warning.call_count

        self.assertEqual(initial_calls, [])
        self.assertGreaterEqual(due_count, 1)
        self.assertEqual(within_interval_count, due_count)
        self.assertGreater(after_interval_count, within_interval_count)
        self.assertNotEqual(
            decision.trace_values.get("ordinary_ems_settlement_phase"),
            "IDLE",
        )
        self.assertEqual(self._control_calls(ha, optimizer), [])

    def test_unsupported_automated_target_with_different_observed_ems_blocks_all_writes(
        self,
    ) -> None:
        for rejected_target in (
            MODE_CMD_DISCHARGE_ESS,
            "Unsupported Automated Target",
            "",
        ):
            with self.subTest(target=rejected_target):
                ha, optimizer = self._optimizer(observed_ems=MODE_MAX_SELF)
                decision = self._decision(rejected_target)

                self._run_tick(optimizer, decision, now=100.0)

                self.assertEqual(self._control_calls(ha, optimizer), [])
                self.assertEqual(
                    [call for call in ha.calls if call[0] != "get_state_value"],
                    [],
                )
                self.assertEqual(optimizer._ordinary_ems_settlement.phase, "IDLE")
                self.assertTrue(
                    decision.trace_gates["automated_ems_target_unsupported"]
                )
                self.assertTrue(
                    decision.trace_gates["automated_ems_target_blocked_writes"]
                )
                self.assertEqual(
                    decision.trace_values["automated_ems_rejected_target"],
                    rejected_target,
                )
                self.assertIn("unsupported", decision.outcome_reason.lower())
                self.assertIn("blocked", decision.outcome_reason.lower())

    def test_unsupported_automated_target_matching_observation_blocks_dependent_writes(
        self,
    ) -> None:
        ha, optimizer = self._optimizer(observed_ems=MODE_CMD_DISCHARGE_ESS)
        decision = self._decision(MODE_CMD_DISCHARGE_ESS)

        self._run_tick(optimizer, decision, now=100.0)

        self.assertEqual(self._control_calls(ha, optimizer), [])
        self.assertEqual(
            [call for call in ha.calls if call[0] != "get_state_value"],
            [],
        )
        self.assertEqual(optimizer._ordinary_ems_settlement.phase, "IDLE")
        self.assertTrue(decision.trace_gates["automated_ems_target_unsupported"])
        self.assertTrue(decision.trace_gates["automated_ems_target_blocked_writes"])
        self.assertEqual(
            decision.trace_values["automated_ems_rejected_target"],
            MODE_CMD_DISCHARGE_ESS,
        )

    def test_unsupported_automated_target_warning_is_throttled(self) -> None:
        ha, optimizer = self._optimizer(observed_ems=MODE_MAX_SELF)
        rejected_target = "Unsupported Automated Target"
        decision = self._decision(rejected_target)

        with patch("app.optimizer.logger.warning") as warning:
            self._run_tick(optimizer, decision, now=100.0)
            first_count = sum(
                rejected_target in str(call) for call in warning.call_args_list
            )

            self._run_tick(optimizer, decision, now=399.0)
            within_interval_count = sum(
                rejected_target in str(call) for call in warning.call_args_list
            )

            self._run_tick(optimizer, decision, now=400.0)
            after_interval_count = sum(
                rejected_target in str(call) for call in warning.call_args_list
            )

        self.assertEqual(first_count, 1)
        self.assertEqual(within_interval_count, first_count)
        self.assertEqual(after_interval_count, first_count + 1)
        self.assertEqual(self._control_calls(ha, optimizer), [])
        self.assertEqual(
            [call for call in ha.calls if call[0] != "get_state_value"],
            [],
        )
        self.assertEqual(optimizer._ordinary_ems_settlement.phase, "IDLE")

    def test_unsupported_idle_target_does_not_block_untrusted_ems_recovery(
        self,
    ) -> None:
        ha, optimizer = self._optimizer(observed_ems="unavailable")
        decision = self._decision("Unsupported Automated Target")

        self._run_tick(optimizer, decision, now=100.0)

        self.assertEqual(
            self._control_calls(ha, optimizer),
            [("select_option", optimizer.cfg.ems_mode_select, MODE_MAX_SELF)],
        )
        self.assertTrue(optimizer._ems_mode_recovery_required)
        self.assertEqual(optimizer._ordinary_ems_settlement.phase, "IDLE")
        self.assertNotIn(
            "automated_ems_target_unsupported",
            decision.trace_gates,
        )


if __name__ == "__main__":
    unittest.main()
