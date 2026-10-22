from __future__ import annotations

import asyncio
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
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
from test_msc_baseline_overlay_contract import later_msc_report_clock


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
            self._record_state_value(entity_id, value)
        return outcome

    async def set_number(self, entity_id: str, value: float) -> object:
        self.calls.append(("set_number", entity_id, value))
        outcome = self._next_outcome("set_number", entity_id)
        if outcome is True and self.settle_numbers:
            self._record_state_value(entity_id, value)
        return outcome


class Phase1ActuatorSettlementFallbackCharacterizationTests(
    Haos49CharacterizationCase
):
    """Package 5 characterization; production policy remains deliberately unchanged."""

    MORNING = datetime(2026, 1, 15, 9, 0, 0)

    @staticmethod
    def _supply_owner(optimizer, ha, when, mode):
        # Ownership is explicit test evidence, never inferred from a software
        # default or successful actuator request. Manual callers retain Manual.
        reported = when.isoformat()
        for entity, value in (
            (optimizer.cfg.sigenergy_mode_select, mode),
            (optimizer.cfg.ha_control_switch, "on"),
        ):
            ha.states[entity] = {
                "entity_id": entity, "state": value, "attributes": {},
                "last_updated": reported, "last_reported": reported,
            }

    @contextmanager
    def _automated_fallback_clock(self, optimizer, ha, when):
        with later_msc_report_clock(ha, when) as moment:
            self._supply_owner(optimizer, ha, moment[0], optimizer.cfg.automated_option)
            original_bulk_states = ha.bulk_states
            closure_report_pending = True

            async def later_closure_report(entity_ids):
                nonlocal closure_report_pending
                entity = optimizer.cfg.grid_export_limit
                if (
                    closure_report_pending and entity in entity_ids
                    and ha.calls.count(("set_number", entity, 0.01)) == 2
                ):
                    # Only opted-in fixtures supply this independent physical
                    # report. An accepted close command alone proves nothing.
                    moment[0] += timedelta(milliseconds=1)
                    ha._record_state_value(entity, 0.01)
                    closure_report_pending = False
                return await original_bulk_states(entity_ids)

            ha.bulk_states = later_closure_report
            try:
                yield
            finally:
                ha.bulk_states = original_bulk_states

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
        self._supply_owner(optimizer, ha, datetime.now(timezone.utc), optimizer.cfg.automated_option)
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
        ha = _ScriptedActuatorHA(
            settle_numbers=False,
            settle_selects=False,
        )
        optimizer = self._morning_slow_optimizer(ha)
        cfg = optimizer.cfg
        self._supply_owner(optimizer, ha, datetime.now(timezone.utc), cfg.automated_option)
        ha._record_state_value(cfg.grid_export_limit, 25.0)
        state = self._morning_slow_state(
            battery_discharge_kw=0.273,
            grid_export_kw=1.837,
            current_export_limit=25.0,
        )
        state.current_import_limit = 25.0
        state.current_import_limit_observed = True
        decision = self.decide(optimizer, state, self.MORNING)
        decision.pv_max_power_limit = 10.0

        result = asyncio.run(optimizer._apply(state, decision))

        self.assertTrue(
            any(
                optimizer.cfg.grid_export_limit in entity_ids
                for entity_ids in ha.bulk_state_calls
            ),
            "ordinary safety closure needs a provenance-bearing readback, not request success alone",
        )
        self.assertEqual(
            [
                ("set_number", cfg.grid_export_limit, 0.01),
                ("set_number", cfg.grid_import_limit, 0.01),
            ],
            ha.calls,
            "an unproven export close must still issue the independent import safety close and stop",
        )
        self.assertFalse(result.succeeded)

    def test_import_safety_close_failure_after_unproven_export_close_stops_application(
        self,
    ) -> None:
        ha = _ScriptedActuatorHA(
            settle_numbers=False,
            settle_selects=False,
        )
        optimizer = self.optimizer(ha)
        cfg = optimizer.cfg
        self._supply_owner(optimizer, ha, datetime.now(timezone.utc), cfg.automated_option)
        ha._record_state_value(cfg.grid_export_limit, 25.0)
        ha.outcomes[("set_number", cfg.grid_import_limit)] = [False]
        state = self._automatic_apply_state(
            current_import_limit=25.0,
            current_pv_max_power_limit=25.0,
        )
        decision = self._closed_decision(pv_max_power_limit=10.0)

        result = asyncio.run(optimizer._apply(state, decision))

        self.assertEqual(
            [
                ("set_number", cfg.grid_export_limit, 0.01),
                ("set_number", cfg.grid_import_limit, 0.01),
            ],
            ha.calls,
        )
        self.assertFalse(result.succeeded)
        self.assertIn("grid import safety close returned failure", result.error)

    def test_successful_fallback_observes_safe_state_before_bounded_recovery(
        self,
    ) -> None:
        ha = _ScriptedActuatorHA()
        optimizer = self.optimizer(
            ha,
            cap_total_import=13.25,
            pv_max_power_normal=9.5,
            ess_charge_limit_value=12.0,
            ess_discharge_limit_value=11.0,
        )
        cfg = optimizer.cfg
        ha.outcomes[("set_number", cfg.grid_export_limit)] = [False, True]
        state = self._automatic_apply_state(
            current_pv_max_power_limit=2.0,
            current_ess_charge_limit=0.01,
            current_ess_discharge_limit=0.01,
            ess_max_charge_kw=10.0,
            ess_max_discharge_kw=9.0,
            ess_charge_limit_entity_max_kw=8.75,
            ess_discharge_limit_entity_max_kw=7.65,
            demand_window_active=False,
            demand_window_observed=True,
        )
        decision = self._closed_decision()
        decision.trace_values["battery_export_owner"] = "none"

        with self._automated_fallback_clock(optimizer, ha, self.FIXED_AFTERNOON):
            result = asyncio.run(optimizer._apply(state, decision))

        self.assertEqual(
            [
                ("set_number", cfg.grid_export_limit, 0.01),
                ("set_number", cfg.grid_export_limit, 0.01),
                ("select_option", cfg.ems_mode_select, MODE_MAX_SELF),
                ("set_number", cfg.ess_max_discharging_limit, 0.01),
                ("set_number", cfg.grid_import_limit, 13.25),
                ("set_number", cfg.ess_max_charging_limit, 8.75),
                ("set_number", cfg.ess_max_discharging_limit, 7.65),
                ("set_number", cfg.pv_max_power_limit, 9.5),
            ],
            [
                call
                for call in ha.calls
                if call[0] in {"set_number", "select_option"}
            ],
        )
        self.assertTrue(
            any(
                cfg.grid_export_limit in entity_ids
                for entity_ids in ha.bulk_state_calls
            ),
            "fallback must prove export closure from a trusted readback",
        )
        self.assertEqual(0.01, ha.state_values[cfg.grid_export_limit])
        self.assertEqual(MODE_MAX_SELF, ha.state_values[cfg.ems_mode_select])
        self.assertEqual(13.25, ha.state_values[cfg.grid_import_limit])
        self.assertEqual(8.75, ha.state_values[cfg.ess_max_charging_limit])
        self.assertEqual(7.65, ha.state_values[cfg.ess_max_discharging_limit])
        self.assertEqual(9.5, ha.state_values[cfg.pv_max_power_limit])
        self.assertFalse(result.succeeded)
        self.assertTrue(result.fallback_succeeded)
        self.assertEqual(EXPORT_BLOCKED, decision.export_intent)
        self.assertEqual("none", decision.trace_values["battery_export_owner"])

    def test_demand_window_fallback_keeps_import_blocked_but_restores_house_supply(
        self,
    ) -> None:
        ha = _ScriptedActuatorHA()
        optimizer = self.optimizer(
            ha,
            cap_total_import=14.0,
            pv_max_power_normal=8.5,
            ess_charge_limit_value=12.0,
            ess_discharge_limit_value=11.0,
        )
        cfg = optimizer.cfg
        ha.outcomes[("set_number", cfg.grid_export_limit)] = [False, True]
        state = self._automatic_apply_state(
            demand_window_active=True,
            demand_window_observed=True,
            ess_charge_limit_entity_max_kw=6.5,
            ess_discharge_limit_entity_max_kw=7.5,
        )

        with self._automated_fallback_clock(optimizer, ha, self.FIXED_AFTERNOON):
            result = asyncio.run(optimizer._apply(state, self._closed_decision()))

        self.assertEqual(
            [
                ("set_number", cfg.grid_export_limit, 0.01),
                ("set_number", cfg.grid_export_limit, 0.01),
                ("select_option", cfg.ems_mode_select, MODE_MAX_SELF),
                ("set_number", cfg.grid_import_limit, 0.01),
                ("set_number", cfg.ess_max_discharging_limit, 0.01),
                ("set_number", cfg.ess_max_charging_limit, 6.5),
                ("set_number", cfg.ess_max_discharging_limit, 7.5),
                ("set_number", cfg.pv_max_power_limit, 8.5),
            ],
            [
                call
                for call in ha.calls
                if call[0] in {"set_number", "select_option"}
            ],
        )
        self.assertEqual(0.01, ha.state_values[cfg.grid_import_limit])
        self.assertEqual(7.5, ha.state_values[cfg.ess_max_discharging_limit])
        self.assertEqual(8.5, ha.state_values[cfg.pv_max_power_limit])
        self.assertFalse(result.succeeded)
        self.assertTrue(result.fallback_succeeded)

    def _run_import_owner_fallback(
        self, *, standby: bool, demand_observed: bool, msc_settles: bool,
        morning_dump: bool = False,
    ):
        ha = _ScriptedActuatorHA(settle_selects=msc_settles)
        optimizer = self.optimizer(
            ha, cap_total_import=13.25,
            standby_holdoff_enabled=standby,
            morning_dump_enabled=morning_dump,
            standby_holdoff_end_time="23:59",
            pv_forecast_holdoff_kwh=120.0,
        )
        optimizer._tz = timezone.utc
        cfg = optimizer.cfg
        when = datetime(2026, 1, 15, 6, 0) if morning_dump else self.FIXED_AFTERNOON
        state = self.state(
            when, sun_above_horizon=not morning_dump,
            battery_soc=80.0,
            available_discharge_energy_kwh=24.0,
            current_export_limit=25.0,
            current_import_limit=13.25,
            demand_window_active=False,
            demand_window_observed=demand_observed,
            current_price=0.30,
            current_price_cents=30.0,
            price_is_negative=False,
            feedin_price=0.0,
            feedin_price_cents=0.0,
            forecast_today_kwh=150.0,
            forecast_remaining_kwh=150.0,
            price_forecast_source_trusted=True,
            price_forecast_entries=[{
                "start_time": when.timestamp() + 1800,
                "per_kwh": -0.10,
            }],
            solcast_detailed=[{
                "period_start": (when + timedelta(hours=hours)).isoformat(),
                "pv_estimate": 10.0,
            } for hours in (3, 5, 7, 9, 11)] if morning_dump else [],
        )
        decision = self.decide(optimizer, state, when)
        self.assertEqual(standby, decision.standby_holdoff_active)
        self.assertEqual(morning_dump, decision.morning_dump_active)
        if morning_dump:
            self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
            self.assertEqual(EXPORT_BLOCKED, decision.export_intent)
            self.assertEqual(0.0, decision.export_limit)
        self.assertEqual(0.0, decision.import_limit)
        ha._record_state_value(cfg.grid_import_limit, 13.25)
        ha.outcomes[("set_number", cfg.grid_export_limit)] = [False, True]
        import_writes_before_wait = []
        real_export_wait = optimizer._wait_for_number_at_most
        real_msc_wait = optimizer._wait_for_exact_entity_state

        def record_import_writes():
            import_writes_before_wait.append([
                value for method, entity, value in ha.calls
                if method == "set_number" and entity == cfg.grid_import_limit
            ])

        async def observe_export_wait(*args, **kwargs):
            record_import_writes()
            return await real_export_wait(*args, **kwargs)

        async def observe_msc_wait(*args, **kwargs):
            record_import_writes()
            return await real_msc_wait(*args, **kwargs)

        optimizer._wait_for_number_at_most = observe_export_wait
        optimizer._wait_for_exact_entity_state = observe_msc_wait
        # This fixture supplies independent post-dispatch export closure and
        # exact MSC reports. With settle_selects=False the latter stays absent.
        with self._automated_fallback_clock(optimizer, ha, when):
            result = asyncio.run(optimizer._apply(state, decision))
        self.assertFalse(result.succeeded)
        self.assertTrue(result.fallback_attempted)
        self.assertEqual(msc_settles, result.fallback_succeeded, result.error)
        self.assertEqual(2, len(import_writes_before_wait), "must reach both real settlement waiters")
        return cfg, ha, decision, import_writes_before_wait

    def test_standby_fallback_closes_import_before_settlement_and_never_reopens(self) -> None:
        cfg, ha, decision, before_wait = self._run_import_owner_fallback(
            standby=True, demand_observed=True, msc_settles=True,
        )
        self.assertEqual([[0.01], [0.01]], before_wait)
        self.assertEqual([0.01], [
            value for method, entity, value in ha.calls
            if method == "set_number" and entity == cfg.grid_import_limit
        ])
        self.assertEqual(0.01, ha.state_values[cfg.grid_import_limit])
        self.assertEqual(decision.pv_max_power_limit, ha.state_values[cfg.pv_max_power_limit])
        self.assertEqual(0.01, ha.state_values[cfg.grid_export_limit])

    def test_standby_unsettled_fallback_closes_previously_open_import(self) -> None:
        cfg, ha, _decision, before_wait = self._run_import_owner_fallback(
            standby=True, demand_observed=True, msc_settles=False,
        )
        self.assertEqual([[0.01], [0.01]], before_wait)
        self.assertEqual([0.01], [
            value for method, entity, value in ha.calls
            if method == "set_number" and entity == cfg.grid_import_limit
        ])
        self.assertEqual(0.01, ha.state_values[cfg.grid_import_limit])

    def test_unknown_demand_fallback_retains_its_independent_import_close(self) -> None:
        cfg, ha, _decision, before_wait = self._run_import_owner_fallback(
            standby=False, demand_observed=False, msc_settles=True,
        )
        self.assertEqual([[0.01], [0.01]], before_wait)
        self.assertEqual([0.01], [
            value for method, entity, value in ha.calls
            if method == "set_number" and entity == cfg.grid_import_limit
        ])
        self.assertEqual(0.01, ha.state_values[cfg.grid_import_limit])

    def test_economic_zero_import_without_standby_retains_normal_fallback_recovery(self) -> None:
        cfg, ha, _decision, before_wait = self._run_import_owner_fallback(
            standby=False, demand_observed=True, msc_settles=True,
        )
        self.assertEqual([[], []], before_wait)
        self.assertEqual([13.25], [
            value for method, entity, value in ha.calls
            if method == "set_number" and entity == cfg.grid_import_limit
        ])
        self.assertEqual(13.25, ha.state_values[cfg.grid_import_limit])

    def test_morning_dump_fallback_closes_import_before_settlement_and_never_reopens(self) -> None:
        cfg, ha, _decision, before_wait = self._run_import_owner_fallback(
            standby=False, demand_observed=True, msc_settles=True, morning_dump=True,
        )
        self.assertEqual([[0.01], [0.01]], before_wait)
        self.assertEqual([0.01], [
            value for method, entity, value in ha.calls
            if method == "set_number" and entity == cfg.grid_import_limit
        ])
        self.assertEqual(0.01, ha.state_values[cfg.grid_import_limit])
        self.assertEqual(0.01, ha.state_values[cfg.grid_export_limit])

    def test_morning_dump_unsettled_fallback_closes_previously_open_import(self) -> None:
        cfg, ha, _decision, before_wait = self._run_import_owner_fallback(
            standby=False, demand_observed=True, msc_settles=False, morning_dump=True,
        )
        self.assertEqual([[0.01], [0.01]], before_wait)
        self.assertEqual([0.01], [
            value for method, entity, value in ha.calls
            if method == "set_number" and entity == cfg.grid_import_limit
        ])
        self.assertEqual(0.01, ha.state_values[cfg.grid_import_limit])

    def test_morning_dump_with_unknown_demand_keeps_import_closed_in_fallback(self) -> None:
        cfg, ha, _decision, before_wait = self._run_import_owner_fallback(
            standby=False, demand_observed=False, msc_settles=True, morning_dump=True,
        )
        self.assertEqual([[0.01], [0.01]], before_wait)
        self.assertEqual([0.01], [
            value for method, entity, value in ha.calls
            if method == "set_number" and entity == cfg.grid_import_limit
        ])
        self.assertEqual(0.01, ha.state_values[cfg.grid_import_limit])

    def test_unsettled_fallback_export_close_withholds_permissive_recovery(
        self,
    ) -> None:
        ha = _ScriptedActuatorHA(settle_numbers=False)
        optimizer = self.optimizer(ha)
        cfg = optimizer.cfg
        self._supply_owner(optimizer, ha, datetime.now(timezone.utc), cfg.automated_option)
        ha._record_state_value(cfg.grid_export_limit, 25.0)
        ha.outcomes[("set_number", cfg.grid_export_limit)] = [False, True]
        state = self._automatic_apply_state(
            demand_window_active=False,
            demand_window_observed=True,
        )

        result = asyncio.run(optimizer._apply(state, self._closed_decision()))

        self.assertEqual(
            [
                ("set_number", cfg.grid_export_limit, 0.01),
                ("set_number", cfg.grid_export_limit, 0.01),
                ("select_option", cfg.ems_mode_select, MODE_MAX_SELF),
                ("set_number", cfg.ess_max_discharging_limit, 0.01),
            ],
            [
                call
                for call in ha.calls
                if call[0] in {"set_number", "select_option"}
            ],
        )
        self.assertFalse(result.succeeded)
        self.assertFalse(result.fallback_succeeded)
        self.assertIn("grid export safety close settlement was not observed", result.error)

    def test_unsettled_fallback_msc_withholds_permissive_recovery(self) -> None:
        ha = _ScriptedActuatorHA(settle_selects=False)
        optimizer = self.optimizer(ha)
        cfg = optimizer.cfg
        ha._record_state_value(cfg.grid_export_limit, 25.0)
        ha._record_state_value(cfg.ems_mode_select, MODE_CMD_CHARGE_GRID)
        ha.outcomes[("set_number", cfg.grid_export_limit)] = [False, True]
        state = self._automatic_apply_state(
            current_ems_mode=MODE_CMD_CHARGE_GRID,
            demand_window_active=False,
            demand_window_observed=True,
        )

        # Closure is observed, but the intentionally absent MSC report remains
        # absent. This negative case cannot recover through command acceptance.
        with self._automated_fallback_clock(optimizer, ha, datetime.now(timezone.utc)):
            result = asyncio.run(optimizer._apply(state, self._closed_decision()))

        self.assertEqual(
            [
                ("select_option", cfg.ems_mode_select, MODE_MAX_SELF),
                ("set_number", cfg.grid_export_limit, 0.01),
                ("set_number", cfg.grid_export_limit, 0.01),
                ("select_option", cfg.ems_mode_select, MODE_MAX_SELF),
                ("set_number", cfg.ess_max_discharging_limit, 0.01),
            ],
            [
                call
                for call in ha.calls
                if call[0] in {"set_number", "select_option"}
            ],
        )
        self.assertEqual(0.01, ha.state_values[cfg.grid_export_limit])
        self.assertEqual(
            MODE_CMD_CHARGE_GRID,
            ha.state_values[cfg.ems_mode_select],
        )
        self.assertFalse(result.succeeded)
        self.assertFalse(result.fallback_succeeded)
        self.assertIn("Maximum Self Consumption settlement was not observed", result.error)

    def test_failed_primary_and_fallback_results_mark_cycle_failed(self) -> None:
        ha = _ScriptedActuatorHA()
        optimizer = self.optimizer(ha)
        cfg = optimizer.cfg
        self._supply_owner(optimizer, ha, datetime.now(timezone.utc), cfg.automated_option)
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
        self._supply_owner(optimizer, ha, datetime.now(timezone.utc), cfg.automated_option)
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
        self._supply_owner(optimizer, ha, datetime.now(timezone.utc), cfg.automated_option)
        ha.outcomes[("set_number", cfg.grid_export_limit)] = [
            False,
            RuntimeError("fallback export request failed"),
        ]
        state = self._automatic_apply_state(
            demand_window_active=True,
            demand_window_observed=True,
        )

        result = asyncio.run(optimizer._apply(state, self._closed_decision()))

        self.assertIn(
            ("select_option", cfg.ems_mode_select, MODE_MAX_SELF),
            ha.calls,
            "one fallback exception must not prevent later independent safety requests",
        )
        self.assertIn(("set_number", cfg.grid_import_limit, 0.01), ha.calls)
        self.assertIn(
            ("set_number", cfg.ess_max_discharging_limit, 0.01), ha.calls
        )
        self.assertFalse(result.succeeded)
        self.assertFalse(result.fallback_succeeded)
        self.assertIn("fallback export request failed", result.error)

    def test_ems_success_then_export_failure_leaves_asymmetric_observed_state(
        self,
    ) -> None:
        ha = _ScriptedActuatorHA()
        optimizer = self.optimizer(ha)
        cfg = optimizer.cfg
        self._supply_owner(optimizer, ha, datetime.now(timezone.utc), cfg.automated_option)
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
        self._supply_owner(optimizer, ha, datetime.now(timezone.utc), cfg.automated_option)
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
        self._supply_owner(optimizer, ha, datetime.now(timezone.utc), cfg.automated_option)
        ha.outcomes[("set_number", cfg.grid_export_limit)] = [False, True]
        decision = self._closed_decision(pv_max_power_limit=10.0)

        asyncio.run(optimizer._apply(self._automatic_apply_state(), decision))

        self.assertNotIn(("set_number", cfg.pv_max_power_limit, 10.0), ha.calls)

    def test_late_pv_max_write_failure_marks_cycle_failed(self) -> None:
        ha = _ScriptedActuatorHA()
        optimizer = self.optimizer(ha)
        cfg = optimizer.cfg
        self._supply_owner(optimizer, ha, datetime.now(timezone.utc), cfg.automated_option)
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
        self._supply_owner(optimizer, ha, datetime.now(timezone.utc), optimizer.cfg.manual_option)
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
