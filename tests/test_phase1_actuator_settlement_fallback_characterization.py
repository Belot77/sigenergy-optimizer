from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, Mock

from app.models import (
    BATTERY_EXPORT,
    EXPORT_BLOCKED,
    MSC_SURPLUS_CEILING,
    Decision,
    HVACObservedValue,
    HVACSolarInputContext,
)
from app.optimizer import MODE_CMD_CHARGE_GRID, MODE_CMD_DISCHARGE_PV, MODE_MAX_SELF
from haos49_characterization_helpers import (
    Haos49CharacterizationCase,
    RecordingHA,
)


class _BooleanProbe:
    """Boolean-like service result that records whether the caller inspected it."""

    def __init__(self, value: bool) -> None:
        self.value = value
        self.checks = 0

    def __bool__(self) -> bool:
        self.checks += 1
        return self.value


class _ScriptedActuatorHA(RecordingHA):
    """HA double with per-actuator results independent from observed readback."""

    def __init__(
        self,
        outcomes: dict[tuple[str, str], list[object]] | None = None,
        *,
        state_values: dict[str, object] | None = None,
        settle_numbers: bool = True,
        settle_selects: bool = True,
    ) -> None:
        super().__init__(
            state_values=state_values,
            settle_numbers=settle_numbers,
            settle_selects=settle_selects,
        )
        self.outcomes = {
            key: list(values) for key, values in (outcomes or {}).items()
        }

    def _next_outcome(self, method: str, entity_id: str) -> object:
        queued = self.outcomes.get((method, entity_id), [])
        outcome = queued.pop(0) if queued else True
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    async def select_option(self, entity_id: str, value: str) -> object:
        self.calls.append(("select_option", entity_id, value))
        outcome = self._next_outcome("select_option", entity_id)
        if outcome is True and self.settle_selects:
            self.state_values[entity_id] = value
        return outcome

    async def set_number(self, entity_id: str, value: float) -> object:
        self.calls.append(("set_number", entity_id, value))
        outcome = self._next_outcome("set_number", entity_id)
        if outcome is True and self.settle_numbers:
            self.state_values[entity_id] = value
        return outcome


class Phase1ActuatorSettlementFallbackCharacterizationTests(
    Haos49CharacterizationCase
):
    """Package 5 characterization; production policy remains deliberately unchanged."""

    MORNING = datetime(2026, 1, 15, 9, 0, 0)

    @staticmethod
    def _fresh(value: float | str | bool) -> HVACObservedValue:
        return HVACObservedValue(value=value, available=True, fresh=True)

    def _fresh_inputs(
        self,
        *,
        pv_kw: float,
        load_kw: float,
        battery_power_kw: float,
        grid_export_kw: float,
        grid_import_kw: float = 0.0,
    ) -> HVACSolarInputContext:
        return HVACSolarInputContext(
            pv_power=self._fresh(pv_kw),
            load_power=self._fresh(load_kw),
            battery_power=self._fresh(battery_power_kw),
            grid_import_power=self._fresh(grid_import_kw),
            grid_export_power=self._fresh(grid_export_kw),
            solar_power_now=self._fresh(pv_kw),
            sun_above_horizon=self._fresh(True),
            control_mode=self._fresh("Automated"),
            observed_ems_mode=self._fresh(MODE_MAX_SELF),
            observed_export_limit=self._fresh(25.0),
            live_snapshot=True,
        )

    def _morning_slow_state(
        self,
        *,
        battery_discharge_kw: float,
        pv_kw: float = 4.2,
        load_kw: float = 1.0,
        grid_export_kw: float = 0.0,
        current_export_limit: float = 25.0,
    ):
        return self.state(
            self.MORNING,
            battery_soc=14.5,
            available_discharge_energy_kwh=4.35,
            battery_power_sensor_kw=-battery_discharge_kw,
            pv_kw=pv_kw,
            solar_power_now_kw=pv_kw,
            load_kw=load_kw,
            grid_import_power_kw=0.0,
            grid_export_power_kw=grid_export_kw,
            current_export_limit=current_export_limit,
            current_export_limit_observed=True,
            current_import_limit=0.01,
            current_import_limit_observed=True,
            feedin_price=0.15,
            feedin_price_cents=15.0,
            forecast_remaining_kwh=100.0,
            pv_power_trusted=True,
            load_power_trusted=True,
            hvac_solar_inputs=self._fresh_inputs(
                pv_kw=pv_kw,
                load_kw=load_kw,
                battery_power_kw=-battery_discharge_kw,
                grid_export_kw=grid_export_kw,
            ),
        )

    def _morning_slow_optimizer(self, ha: object | None = None):
        return self.optimizer(
            ha,
            morning_slow_charge_enabled=True,
            morning_slow_charge_rate_kw=2.0,
        )

    def _closed_decision(self, **overrides: object) -> Decision:
        decision = Decision(
            ems_mode=MODE_MAX_SELF,
            export_limit=0.0,
            import_limit=0.0,
            pv_max_power_limit=25.0,
            ess_charge_limit=25.0,
            ess_discharge_limit=25.0,
            export_intent=EXPORT_BLOCKED,
        )
        for key, value in overrides.items():
            setattr(decision, key, value)
        return decision

    def _automatic_apply_state(self, **overrides: object):
        values: dict[str, object] = {
            "current_ems_mode": MODE_MAX_SELF,
            "ems_mode_observed": True,
            "current_export_limit": 25.0,
            "current_export_limit_observed": True,
            "current_import_limit": 0.01,
            "current_import_limit_observed": True,
            "current_pv_max_power_limit": 25.0,
            "current_ess_charge_limit": 25.0,
            "current_ess_discharge_limit": 25.0,
        }
        values.update(overrides)
        return self.state(self.FIXED_AFTERNOON, **values)

    @staticmethod
    def _stub_tick_tail(optimizer, state, decision) -> None:
        optimizer._read_state = AsyncMock(return_value=state)
        optimizer._decide = Mock(return_value=decision)
        optimizer._evaluate_hvac_solar_permission = Mock(return_value=object())
        optimizer._publish_hvac_solar_permission = AsyncMock()
        optimizer._record_automation_audit = Mock()
        optimizer._record_decision_trace = Mock()
        optimizer._handle_notifications = AsyncMock()
        optimizer._handle_daily_summaries = AsyncMock()
        optimizer._accumulate_history = Mock()
        optimizer._record_price_tracking = Mock()

    def test_fresh_direct_discharge_0094_allows_morning_slow_ceiling(self) -> None:
        optimizer = self._morning_slow_optimizer()
        decision = self.decide(
            optimizer,
            self._morning_slow_state(battery_discharge_kw=0.094),
            self.MORNING,
        )

        self.assertTrue(decision.morning_slow_charge_active)
        self.assertEqual(0.094, decision.trace_values["battery_discharge_kw_for_pv_only"])
        self.assertEqual(0.1, decision.trace_values["pv_only_discharge_tolerance_kw"])
        self.assertEqual(optimizer.cfg.export_limit_high, decision.export_limit)
        self.assertEqual(MSC_SURPLUS_CEILING, decision.export_intent)
        self.assertEqual("none", decision.trace_values["battery_export_owner"])

    def test_fresh_direct_discharge_just_above_010_keeps_morning_slow_ceiling(
        self,
    ) -> None:
        optimizer = self._morning_slow_optimizer()
        decision = self.decide(
            optimizer,
            self._morning_slow_state(battery_discharge_kw=0.101),
            self.MORNING,
        )

        self.assertTrue(decision.morning_slow_charge_active)
        self.assertEqual(0.101, decision.trace_values["battery_discharge_kw_for_pv_only"])
        self.assertEqual(
            "load_serving_battery_discharge",
            decision.trace_values["ordinary_msc_flow_classification"],
        )
        self.assertTrue(decision.trace_gates["ordinary_msc_flow_safe"])
        self.assertFalse(decision.trace_gates["pv_only_branch_battery_safety_blocked"])
        self.assertEqual(optimizer.cfg.export_limit_high, decision.export_limit)
        self.assertEqual(MSC_SURPLUS_CEILING, decision.export_intent)
        self.assertEqual("none", decision.trace_values["battery_export_owner"])

    def test_material_32kw_load_serving_discharge_with_pv_below_load_stays_closed(
        self,
    ) -> None:
        optimizer = self._morning_slow_optimizer()
        decision = self.decide(
            optimizer,
            self._morning_slow_state(
                battery_discharge_kw=3.2,
                pv_kw=1.6,
                load_kw=4.7,
                grid_export_kw=0.0,
            ),
            self.MORNING,
        )

        self.assertEqual(
            "load_serving_battery_discharge",
            decision.trace_values["ordinary_msc_flow_classification"],
        )
        self.assertEqual(0.0, decision.export_limit)
        self.assertEqual(EXPORT_BLOCKED, decision.export_intent)
        self.assertEqual("none", decision.trace_values["battery_export_owner"])

    def test_simultaneous_0273kw_discharge_and_1837kw_grid_export_stays_fail_closed(
        self,
    ) -> None:
        optimizer = self._morning_slow_optimizer()
        decision = self.decide(
            optimizer,
            self._morning_slow_state(
                battery_discharge_kw=0.273,
                grid_export_kw=1.837,
            ),
            self.MORNING,
        )

        self.assertEqual(
            "simultaneous_battery_discharge_and_grid_export",
            decision.trace_values["ordinary_msc_flow_classification"],
        )
        self.assertTrue(
            decision.trace_gates[
                "ordinary_msc_simultaneous_battery_discharge_and_grid_export"
            ]
        )
        self.assertEqual(0.0, decision.export_limit)
        self.assertEqual(EXPORT_BLOCKED, decision.export_intent)

    def test_fresh_threshold_snapshots_keep_stable_ceiling_without_stateful_hold(
        self,
    ) -> None:
        optimizer = self._morning_slow_optimizer()
        observed_limits = (25.0, 25.0, 0.01, 25.0)
        discharge_snapshots = (0.094, 0.101, 0.094, 0.101)
        decisions: list[float] = []

        for current_limit, discharge_kw in zip(
            observed_limits, discharge_snapshots, strict=True
        ):
            state = self._morning_slow_state(
                battery_discharge_kw=discharge_kw,
                current_export_limit=current_limit,
            )
            decision = self.decide(optimizer, state, self.MORNING)
            decisions.append(decision.export_limit)
            optimizer._last_state = state
            optimizer._last_decision = decision

        self.assertEqual([25.0, 25.0, 25.0, 25.0], decisions)

    def test_unsettled_simultaneous_flow_reissues_safety_close_each_cycle(self) -> None:
        ha = RecordingHA(
            state_values={},
            settle_numbers=False,
            settle_selects=False,
        )
        optimizer = self._morning_slow_optimizer(ha)
        state = self._morning_slow_state(
            battery_discharge_kw=0.273,
            grid_export_kw=1.837,
            current_export_limit=25.0,
        )
        decision = self.decide(optimizer, state, self.MORNING)

        asyncio.run(optimizer._apply(state, decision))
        asyncio.run(optimizer._apply(state, decision))

        close_call = ("set_number", optimizer.cfg.grid_export_limit, 0.01)
        self.assertEqual(2, ha.calls.count(close_call))

    def test_ordinary_safety_close_is_verified_by_observed_readback_before_completion(
        self,
    ) -> None:
        ha = RecordingHA(
            state_values={},
            settle_numbers=False,
            settle_selects=False,
        )
        optimizer = self._morning_slow_optimizer(ha)
        state = self._morning_slow_state(
            battery_discharge_kw=0.273,
            grid_export_kw=1.837,
            current_export_limit=25.0,
        )
        decision = self.decide(optimizer, state, self.MORNING)

        asyncio.run(optimizer._apply(state, decision))

        close_index = ha.calls.index(
            ("set_number", optimizer.cfg.grid_export_limit, 0.01)
        )
        self.assertTrue(
            any(
                call[0] == "get_state_value"
                and call[1] == optimizer.cfg.grid_export_limit
                and index > close_index
                for index, call in enumerate(ha.calls)
            ),
            "ordinary safety closure needs observed readback, not request success alone",
        )

    def test_primary_export_failure_attempts_full_fallback_in_safety_order(self) -> None:
        ha = _ScriptedActuatorHA()
        optimizer = self.optimizer(ha)
        cfg = optimizer.cfg
        ha.outcomes[("set_number", cfg.grid_export_limit)] = [False, True]
        state = self._automatic_apply_state()

        asyncio.run(optimizer._apply(state, self._closed_decision()))

        self.assertEqual(
            [
                ("set_number", cfg.grid_export_limit, 0.01),
                ("set_number", cfg.grid_export_limit, 0.01),
                ("select_option", cfg.ems_mode_select, MODE_MAX_SELF),
                ("set_number", cfg.grid_import_limit, 0.01),
                ("set_number", cfg.ess_max_discharging_limit, 0.01),
            ],
            ha.calls,
        )

    def test_fallback_requests_are_awaited_but_results_and_readback_are_unchecked(
        self,
    ) -> None:
        ha = _ScriptedActuatorHA(settle_numbers=False, settle_selects=False)
        optimizer = self.optimizer(ha)
        cfg = optimizer.cfg
        probes = [_BooleanProbe(False) for _ in range(4)]
        ha.outcomes = {
            ("set_number", cfg.grid_export_limit): [False, probes[0]],
            ("select_option", cfg.ems_mode_select): [probes[1]],
            ("set_number", cfg.grid_import_limit): [probes[2]],
            ("set_number", cfg.ess_max_discharging_limit): [probes[3]],
        }

        asyncio.run(
            optimizer._apply(
                self._automatic_apply_state(),
                self._closed_decision(),
            )
        )

        self.assertEqual([0, 0, 0, 0], [probe.checks for probe in probes])
        self.assertFalse(any(call[0] == "get_state_value" for call in ha.calls))
        self.assertEqual(
            [
                cfg.grid_export_limit,
                cfg.grid_export_limit,
                cfg.grid_import_limit,
                cfg.ess_max_discharging_limit,
            ],
            [call[1] for call in ha.calls if call[0] == "set_number"],
        )

    def test_failed_primary_and_fallback_results_mark_cycle_failed(self) -> None:
        ha = _ScriptedActuatorHA()
        optimizer = self.optimizer(ha)
        cfg = optimizer.cfg
        ha.outcomes = {
            ("set_number", cfg.grid_export_limit): [False, False],
            ("select_option", cfg.ems_mode_select): [False],
            ("set_number", cfg.grid_import_limit): [False],
            ("set_number", cfg.ess_max_discharging_limit): [False],
        }
        state = self._automatic_apply_state()
        decision = self._closed_decision()
        self._stub_tick_tail(optimizer, state, decision)

        asyncio.run(optimizer._safe_tick())

        self.assertNotEqual(
            "",
            optimizer._last_cycle_error,
            "a failed primary request plus failed fallback must not complete as success",
        )

    def test_failed_primary_and_fallback_do_not_replace_last_applied_decision(
        self,
    ) -> None:
        ha = _ScriptedActuatorHA()
        optimizer = self.optimizer(ha)
        cfg = optimizer.cfg
        ha.outcomes = {
            ("set_number", cfg.grid_export_limit): [False, False],
            ("select_option", cfg.ems_mode_select): [False],
            ("set_number", cfg.grid_import_limit): [False],
            ("set_number", cfg.ess_max_discharging_limit): [False],
        }
        previous = Decision(outcome_reason="previous applied decision")
        requested = self._closed_decision(outcome_reason="unapplied decision")
        optimizer._last_decision = previous
        self._stub_tick_tail(optimizer, self._automatic_apply_state(), requested)

        asyncio.run(optimizer._safe_tick())

        self.assertIs(
            previous,
            optimizer._last_decision,
            "failed application must not replace remembered applied state",
        )

    def test_one_fallback_exception_does_not_skip_remaining_safety_commands(
        self,
    ) -> None:
        ha = _ScriptedActuatorHA()
        optimizer = self.optimizer(ha)
        cfg = optimizer.cfg
        ha.outcomes[("set_number", cfg.grid_export_limit)] = [
            False,
            RuntimeError("fallback export request failed"),
        ]

        try:
            asyncio.run(
                optimizer._apply(
                    self._automatic_apply_state(),
                    self._closed_decision(),
                )
            )
        except RuntimeError:
            pass

        self.assertIn(
            ("select_option", cfg.ems_mode_select, MODE_MAX_SELF),
            ha.calls,
            "one fallback exception must not prevent later independent safety requests",
        )
        self.assertIn(("set_number", cfg.grid_import_limit, 0.01), ha.calls)
        self.assertIn(
            ("set_number", cfg.ess_max_discharging_limit, 0.01), ha.calls
        )

    def test_ems_success_then_export_failure_leaves_asymmetric_observed_state(
        self,
    ) -> None:
        ha = _ScriptedActuatorHA()
        optimizer = self.optimizer(ha)
        cfg = optimizer.cfg
        ha.state_values = {
            cfg.ems_mode_select: MODE_CMD_CHARGE_GRID,
            cfg.grid_export_limit: 25.0,
        }
        ha.outcomes = {
            ("select_option", cfg.ems_mode_select): [True, False],
            ("set_number", cfg.grid_export_limit): [False, False],
        }
        state = self._automatic_apply_state(current_ems_mode=MODE_CMD_CHARGE_GRID)

        asyncio.run(optimizer._apply(state, self._closed_decision()))

        self.assertEqual(MODE_MAX_SELF, ha.state_values[cfg.ems_mode_select])
        self.assertEqual(25.0, ha.state_values[cfg.grid_export_limit])

    def test_failed_ems_then_successful_fallback_export_close_is_asymmetric(
        self,
    ) -> None:
        ha = _ScriptedActuatorHA()
        optimizer = self.optimizer(ha)
        cfg = optimizer.cfg
        ha.state_values = {
            cfg.ems_mode_select: MODE_CMD_CHARGE_GRID,
            cfg.grid_export_limit: 25.0,
        }
        ha.outcomes = {
            ("select_option", cfg.ems_mode_select): [False, False],
            ("set_number", cfg.grid_export_limit): [True],
        }
        state = self._automatic_apply_state(current_ems_mode=MODE_CMD_CHARGE_GRID)

        asyncio.run(optimizer._apply(state, self._closed_decision()))

        self.assertEqual(MODE_CMD_CHARGE_GRID, ha.state_values[cfg.ems_mode_select])
        self.assertEqual(0.01, ha.state_values[cfg.grid_export_limit])

    def test_primary_export_failure_prevents_later_pv_max_write(self) -> None:
        ha = _ScriptedActuatorHA()
        optimizer = self.optimizer(ha)
        cfg = optimizer.cfg
        ha.outcomes[("set_number", cfg.grid_export_limit)] = [False, True]
        decision = self._closed_decision(pv_max_power_limit=10.0)

        asyncio.run(optimizer._apply(self._automatic_apply_state(), decision))

        self.assertNotIn(("set_number", cfg.pv_max_power_limit, 10.0), ha.calls)

    def test_late_pv_max_write_failure_marks_cycle_failed(self) -> None:
        ha = _ScriptedActuatorHA()
        optimizer = self.optimizer(ha)
        cfg = optimizer.cfg
        ha.outcomes[("set_number", cfg.pv_max_power_limit)] = [False]
        state = self._automatic_apply_state(current_export_limit=0.01)
        decision = self._closed_decision(pv_max_power_limit=10.0)
        self._stub_tick_tail(optimizer, state, decision)

        asyncio.run(optimizer._safe_tick())

        self.assertNotEqual(
            "",
            optimizer._last_cycle_error,
            "a late partial actuator failure must be visible in cycle diagnostics",
        )

    def test_branch_controls_keep_export_permission_distinct_from_battery_export(
        self,
    ) -> None:
        optimizer = self.optimizer()
        ordinary = self.state(
            self.FIXED_AFTERNOON,
            battery_soc=60.0,
            available_discharge_energy_kwh=18.0,
            battery_power_sensor_kw=0.0,
            pv_kw=4.0,
            solar_power_now_kw=4.0,
            load_kw=1.0,
            feedin_price=0.15,
            feedin_price_cents=15.0,
        )
        deliberate = self.state(
            self.FIXED_AFTERNOON,
            battery_soc=95.0,
            available_discharge_energy_kwh=28.5,
            battery_power_sensor_kw=-0.2,
            pv_kw=0.0,
            solar_power_now_kw=0.0,
            load_kw=0.0,
            feedin_price=1.10,
            feedin_price_cents=110.0,
            ess_max_discharge_kw=12.0,
        )

        ordinary_decision = self.decide(optimizer, ordinary, self.FIXED_AFTERNOON)
        deliberate_decision = self.decide(
            optimizer, deliberate, self.FIXED_AFTERNOON
        )

        self.assertEqual(MSC_SURPLUS_CEILING, ordinary_decision.export_intent)
        self.assertEqual("none", ordinary_decision.trace_values["battery_export_owner"])
        self.assertEqual(BATTERY_EXPORT, deliberate_decision.export_intent)
        self.assertEqual(
            "high_price", deliberate_decision.trace_values["battery_export_owner"]
        )
        self.assertEqual(MODE_CMD_DISCHARGE_PV, deliberate_decision.ems_mode)

    def test_negative_price_grid_charge_and_demand_window_remain_independent(
        self,
    ) -> None:
        optimizer = self.optimizer()
        negative = self.state(
            self.FIXED_AFTERNOON,
            battery_soc=30.0,
            available_discharge_energy_kwh=9.0,
            current_price=-0.35,
            current_price_cents=-35.0,
            price_is_actual=True,
            price_is_negative=True,
            feedin_price=0.0,
            feedin_price_cents=0.0,
            pv_kw=0.0,
            solar_power_now_kw=0.0,
            load_kw=1.0,
        )
        demand = self.state(
            self.FIXED_AFTERNOON,
            demand_window_active=True,
            demand_window_observed=True,
            current_price=0.30,
            current_price_cents=30.0,
            feedin_price=0.15,
            feedin_price_cents=15.0,
            pv_kw=4.0,
            solar_power_now_kw=4.0,
            load_kw=1.0,
        )

        negative_decision = self.decide(optimizer, negative, self.FIXED_AFTERNOON)
        demand_decision = self.decide(optimizer, demand, self.FIXED_AFTERNOON)

        self.assertEqual(MODE_CMD_CHARGE_GRID, negative_decision.ems_mode)
        self.assertGreater(negative_decision.import_limit, 0.01)
        self.assertEqual(0.0, negative_decision.export_limit)
        self.assertEqual(0.0, demand_decision.import_limit)

    def test_plain_manual_mode_remains_user_owned_and_pauses_optimizer_writes(
        self,
    ) -> None:
        ha = RecordingHA()
        optimizer = self.optimizer(ha)
        state = self._automatic_apply_state(
            sigenergy_mode=optimizer.cfg.manual_option,
            current_export_limit=7.0,
            current_import_limit=8.0,
        )

        asyncio.run(optimizer._apply(state, self._closed_decision()))

        self.assertEqual([], ha.calls)


if __name__ == "__main__":
    import unittest

    unittest.main()
