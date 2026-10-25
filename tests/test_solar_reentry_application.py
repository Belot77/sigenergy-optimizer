"""Offline lifecycle/dispatch regressions using real decisions and fake actuators.

Typed result injections cover application bookkeeping; real _apply tests exercise
the authority-await boundaries. Neither proves physical inverter settlement.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from app.models import HVACObservedValue, HVACSolarInputContext
from app.optimizer import MODE_MAX_SELF, _ActuatorApplicationResult
from test_msc_baseline_overlay_contract import (
    ClockedRecordingHA, establish_observed_msc_baseline, later_msc_report_clock,
)
from test_phase1_solar_dynamic_charge_ceiling_characterization import SolarDynamicChargeFixture


class SolarReentryApplicationTests(SolarDynamicChargeFixture):
    def _state(self, *, when=None, **overrides):
        at = when or self.WHEN
        values = {
            "next_sunset_ts": (self.WHEN + timedelta(hours=4)).timestamp(),
            "solcast_detailed": self._detailed_forecast([6.0] + [3.0] * 7),
            "solcast_provider_polled": (self.WHEN - timedelta(seconds=1)).astimezone().isoformat(),
            "current_export_limit": 25.0,
            "grid_export_power_kw": 5.0,
        }
        values.update(overrides)
        state = super()._state(when=at, **values)
        stamp = at.timestamp()

        def observed(value):
            return HVACObservedValue(value=value, available=True, fresh=True, observed_at_ts=stamp)

        state.hvac_solar_inputs = HVACSolarInputContext(
            live_snapshot=True,
            pv_power=observed(state.pv_kw), load_power=observed(state.load_kw),
            battery_power=observed(state.battery_power_sensor_kw),
            grid_import_power=observed(state.grid_import_power_kw),
            grid_export_power=observed(state.grid_export_power_kw),
            solar_power_now=observed(state.solar_power_now_kw),
            sun_above_horizon=observed(True),
            control_mode=observed(state.sigenergy_mode),
            observed_ems_mode=observed(state.current_ems_mode),
            remote_ems_control=observed(state.ha_control_switch_state),
            observed_export_limit=observed(state.current_export_limit),
        )
        state._msc_ems_reported_at = stamp
        self._fixture_state = state
        return state

    def _at(self, optimizer, seconds, **overrides):
        at = self.WHEN + timedelta(seconds=seconds)
        with self.optimizer_time(at), patch("app.optimizer.monotonic", return_value=1000.0 + seconds):
            decision = self._decide(optimizer, when=at, **overrides)
        return self._fixture_state, decision

    def _qualified(self, *, charge):
        optimizer = self._optimizer(_env_file=None, ess_max_charging_limit="number.test_charge")
        guard = optimizer._solar_charge_reentry if charge else optimizer._solar_budget_reentry
        # Seed only the preceding cause; all timing, gates and final ownership
        # below come from the production decision path and fresh reports.
        guard.arm("prior_relieved_morning" if charge else "prior_aggregate_budget_exit")
        self._at(optimizer, 0)
        state, decision = self._at(optimizer, 30)
        prefix = "solar_charge" if charge else "solar_budget"
        self.assertTrue(decision.trace_gates[f"{prefix}_reentry_qualified"])
        self.assertTrue(decision.solar_surplus_policy_active)
        self.assertLess(decision.ess_charge_limit, self.NORMAL_CHARGE_KW)
        return optimizer, state, decision, guard

    def _finish(self, optimizer, state, decision, result, *, seconds=30):
        with self.optimizer_time(self.WHEN + timedelta(seconds=seconds)), patch(
            "app.optimizer.monotonic", return_value=1000.0 + seconds,
        ):
            optimizer._finish_solar_reentry_application(state, decision, result)

    def test_only_completed_automatic_result_commits_qualified_generation(self):
        results = (
            ("completed", _ActuatorApplicationResult(succeeded=True, automatic_application_completed=True), True),
            ("generic_noop", _ActuatorApplicationResult(succeeded=True), False),
            ("failed", _ActuatorApplicationResult(succeeded=False), False),
            ("pending", _ActuatorApplicationResult(succeeded=False, transition_pending=True,
                                                  automatic_transition_pending=True), False),
            ("fallback", _ActuatorApplicationResult(succeeded=True, automatic_application_completed=True,
                                                   fallback_attempted=True), False),
        )
        for charge in (False, True):
            for label, result, committed in results:
                with self.subTest(charge=charge, result=label):
                    optimizer, state, decision, guard = self._qualified(charge=charge)
                    self._finish(optimizer, state, decision, result)
                    self.assertEqual(not committed, guard.required)
                    self.assertEqual("idle" if committed else "closed", guard.phase)

    def test_completed_old_generation_cannot_commit_new_obligation(self):
        for charge in (False, True):
            with self.subTest(charge=charge):
                optimizer, state, decision, guard = self._qualified(charge=charge)
                guard.reset("invalidated_while_application_awaited")
                self._finish(optimizer, state, decision, _ActuatorApplicationResult(
                    succeeded=True, automatic_application_completed=True,
                ))
                self.assertTrue(guard.required)
                self.assertEqual("closed", guard.phase)

    def test_relieved_final_morning_arms_only_after_completed_automatic_result(self):
        for completed in (False, True):
            with self.subTest(completed=completed):
                optimizer = self._optimizer(
                    _env_file=None, morning_slow_charge_enabled=True,
                    morning_slow_charge_until="16:30", morning_slow_charge_rate_kw=0.1,
                    morning_slow_charge_sunset_cutoff=0.0, forecast_safety_charging=1.20,
                )
                state, decision = self._at(optimizer, 0)
                self.assertTrue(decision.morning_slow_charge_active)
                self.assertTrue(decision.trace_gates["morning_slow_forecast_refill_relief"])
                self.assertTrue(decision.trace_gates["morning_slow_reentry_arm_candidate"])
                self.assertFalse(optimizer._solar_charge_reentry.required)
                self._finish(optimizer, state, decision, _ActuatorApplicationResult(
                    succeeded=True, automatic_application_completed=completed,
                ), seconds=0)
                self.assertEqual(completed, optimizer._solar_charge_reentry.required)

    def test_failed_budget_exit_preserves_latch_when_tick_rolls_back_last_decision(self):
        optimizer = self._optimizer(_env_file=None)
        state, previous = self._at(optimizer, 0)
        optimizer._last_decision = previous
        state = self._state(when=self.WHEN + timedelta(seconds=6), forecast_remaining_kwh=1.0)
        optimizer._read_state = AsyncMock(return_value=state)
        optimizer._apply = AsyncMock(return_value=_ActuatorApplicationResult(succeeded=False))
        optimizer._publish_hvac_solar_permission = AsyncMock()
        with self.optimizer_time(state.timestamp), patch("app.optimizer.monotonic", return_value=1006.0):
            with self.assertRaises(RuntimeError):
                asyncio.run(optimizer._tick())
        self.assertIs(previous, optimizer._last_decision)
        self.assertTrue(optimizer._solar_budget_reentry.required)
        _, recovered = self._at(optimizer, 12)
        self.assertFalse(recovered.solar_surplus_policy_active)
        self.assertEqual(self.NORMAL_CHARGE_KW, recovered.ess_charge_limit)

    def test_manual_freeze_invalidates_proof_without_retiring_obligation(self):
        optimizer, state, decision, guard = self._qualified(charge=False)
        optimizer._freeze_decision_to_live_mode(state, decision, optimizer.cfg.manual_option)
        self.assertTrue(guard.required)
        self.assertEqual("closed", guard.phase)
        self.assertFalse(decision.solar_surplus_policy_active)

    def test_pending_charge_handoff_preserves_hardware_bound_and_demand_import_close(self):
        optimizer = self._optimizer(_env_file=None)
        optimizer._solar_charge_reentry.arm("prior_relieved_morning")
        _, decision = self._at(
            optimizer, 0, battery_soc=80.0, available_discharge_energy_kwh=8.0,
            ess_max_charge_kw=1.25, ess_charge_limit_entity_max_kw=1.25,
            demand_window_active=True, demand_window_observed=True,
        )
        self.assertTrue(decision.solar_surplus_policy_active)
        self.assertFalse(decision.trace_gates["solar_charge_ceiling_owned"])
        self.assertEqual("normal", decision.trace_values["ess_charge_limit_owner"])
        self.assertEqual(1.25, decision.ess_charge_limit)
        self.assertEqual(0.0, decision.import_limit)
        self.assertEqual(25.0, decision.export_limit)
        self.assertEqual(25.0, decision.pv_max_power_limit)

    def test_real_apply_rejects_generation_invalidated_after_authority_await(self):
        async def check(charge, boundary):
            optimizer, state, decision, guard = self._qualified(charge=charge)
            ha = ClockedRecordingHA()
            await establish_observed_msc_baseline(self, optimizer, ha, self.WHEN + timedelta(seconds=30))
            if boundary == "authority":
                original = optimizer._read_control_authority
                reads = 0

                async def invalidate_after_authority(*args, **kwargs):
                    nonlocal reads
                    result = await original(*args, **kwargs)
                    reads += 1
                    if reads == 2:
                        guard.reset("test_generation_changed_during_authority")
                    return result

                optimizer._read_control_authority = invalidate_after_authority
            elif boundary == "charge":
                original = ha.set_number

                async def invalidate_after_charge(entity, value):
                    result = await original(entity, value)
                    if entity == optimizer.cfg.ess_max_charging_limit:
                        guard.reset("test_generation_changed_during_charge")
                    return result

                ha.set_number = invalidate_after_charge
            else:
                original = ha.set_input_number

                async def invalidate_after_helper(entity, value):
                    result = await original(entity, value)
                    guard.reset("test_generation_changed_during_final_helper")
                    return result

                ha.set_input_number = invalidate_after_helper
            with later_msc_report_clock(ha, self.WHEN + timedelta(seconds=30)), patch(
                "app.optimizer.monotonic", return_value=1030.0,
            ):
                result = await optimizer._apply(state, decision)
            writes = [value for action, entity, value in ha.calls
                      if action == "set_number" and entity == optimizer.cfg.ess_max_charging_limit]
            self.assertTrue(guard.required)
            if charge:
                self.assertTrue(result.succeeded, result.error)
                self.assertTrue(writes, ha.calls)
                self.assertEqual(self.NORMAL_CHARGE_KW, writes[-1])
                self.assertFalse(decision.trace_gates["solar_charge_ceiling_owned"])
                self.assertTrue(decision.solar_surplus_policy_active)
                self.assertFalse(result.fallback_attempted)
            else:
                self.assertFalse(result.succeeded)
                self.assertTrue(result.fallback_attempted, (result.error, ha.calls))
                self.assertIn(("set_number", optimizer.cfg.grid_export_limit, 0.01), ha.calls)

        for charge in (False, True):
            for boundary in ("authority", "charge", "helper"):
                with self.subTest(charge=charge, boundary=boundary):
                    asyncio.run(check(charge, boundary))
