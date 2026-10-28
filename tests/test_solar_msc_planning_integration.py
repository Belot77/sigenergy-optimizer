"""Combined offline lifecycles: observed reports never imply hardware acceptance.

Commands and independently scheduled reports use the actual reader, decision,
application and completion paths. No permission identities are manufactured.
"""
from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import timedelta
import unittest
from unittest.mock import Mock, patch

from app.optimizer import MODE_MAX_SELF
from haos49_characterization_helpers import Haos49CharacterizationCase
from test_msc_settled_epoch_reuse import PeriodicReportHA, ReportClock


class SolarMscPlanningIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = Haos49CharacterizationCase("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.addCleanup(self.fixture.tearDown)

    def scenario(self, **overrides):
        clock = ReportClock()
        ha = PeriodicReportHA(clock)
        settings = dict(
            solar_surplus_bypass_enabled=True,
            solar_surplus_fill_deadline_margin_minutes=0.0,
            grid_connection_export_limit_kw=15.0,
            ess_charge_limit_value=5.0,
            ess_max_charging_limit="number.test_charge",
            ess_max_discharging_limit="number.test_discharge",
            sigenergy_mode_select="input_select.combined_mode",
        )
        settings.update(overrides)
        opt = self.fixture.optimizer(ha, **settings)
        ha.configure(opt.cfg)
        opt.on_ws_connect()
        cfg = opt.cfg
        for entity, value in (
            (cfg.rated_capacity_sensor, "10"),
            (cfg.available_discharge_sensor, "6"),
            (cfg.ess_rated_charge_power_sensor, "5"),
            (cfg.ess_max_charging_limit, "5"),
            (cfg.grid_export_limit, "25"),
            (cfg.pv_power_sensor, "16"),
            (cfg.battery_power_sensor, "0"),
            (cfg.grid_export_power_sensor, "15"),
            (cfg.solar_power_now_sensor, "16"),
        ):
            ha.plant[entity] = value
            ha._report(entity, value, -1)
        ha.states[cfg.ess_max_charging_limit]["attributes"]["max"] = 5
        ha.states[cfg.sun_entity]["attributes"]["next_setting"] = clock.at(14400).isoformat()
        ha.states[cfg.forecast_today_sensor]["attributes"]["detailedForecast"] = [
            {"period_start": (clock.BASE + timedelta(minutes=30 * i)).isoformat(),
             "pv_estimate": pv}
            for i, pv in enumerate([6.0] + [3.0] * 7)
        ]
        entity = cfg.solcast_api_last_polled_sensor
        ha.plant[entity] = clock.at(-1).isoformat()
        ha.states[entity] = {"attributes": {"next_auto_update": clock.at(3600).isoformat()}}
        ha._report(entity, ha.plant[entity], -1)
        ha.telemetry.add(entity)
        return clock, ha, opt

    def provider_advance(self, clock, ha):
        entity = ha.cfg.solcast_api_last_polled_sensor
        ha.plant[entity] = clock.at(0.1).isoformat()
        ha._report(entity, ha.plant[entity], clock.elapsed)

    async def cycle(self, clock, ha, opt, at, *, charge=0.0, export=15.0):
        self.assertGreaterEqual(at, clock.elapsed)
        clock.elapsed = at
        ha.deliver()
        # These are explicit measured flows, independent of requested limits.
        for entity, value in (
            (ha.cfg.pv_power_sensor, 1.0 + charge + export),
            (ha.cfg.solar_power_now_sensor, 1.0 + charge + export),
            (ha.cfg.consumed_power_sensor, 1.0),
            (ha.cfg.battery_power_sensor, charge),
            (ha.cfg.grid_export_power_sensor, export),
            (ha.cfg.grid_import_power_sensor, 0.0),
        ):
            ha.plant[entity] = str(value)
            ha._report(entity, str(value), at)
        state = await opt._read_state()
        self.assertEqual(opt._msc_maintenance_identity(), getattr(state, "_msc_read_identity", None))
        decision = opt._decide(state)
        result = await opt._apply(state, decision)
        opt._finish_solar_reentry_application(state, decision, result)
        if result.automatic_application_completed:
            opt._last_state, opt._last_decision = state, decision
            opt._commit_solar_dip_proof(state, decision, result)
        return state, decision, result

    async def pending(self, clock, ha, opt):
        _s, _d, initial = await self.cycle(clock, ha, opt, 0.0)
        self.assertTrue(initial.transition_pending, initial)
        self.assertIsNone(opt._solar_relief.completed_total_kw)
        clock.elapsed = 0.2
        self.provider_advance(clock, ha)
        _s, _d, second = await self.cycle(clock, ha, opt, 0.2)
        self.assertTrue(second.transition_pending, second)
        epoch = opt._msc_transition
        self.assertTrue(epoch.close_accepted)
        self.assertTrue(epoch.msc_accepted)
        return epoch

    async def completed(self, clock, ha, opt):
        epoch = await self.pending(clock, ha, opt)
        state, decision, result = await self.cycle(clock, ha, opt, 1.3)
        self.assertTrue(result.automatic_application_completed, result)
        self.assertTrue(decision.trace_gates["solar_charge_ceiling_owned"], decision.trace_values)
        self.assertEqual(1.21, decision.ess_charge_limit)
        self.assertEqual(1.21, opt._solar_relief.completed_total_kw)
        return epoch, state, decision, result

    def test_pending_original_epoch_settles_into_real_solar_receipt_then_earns_relief(self):
        async def run():
            clock, ha, opt = self.scenario()
            with clock.active():
                epoch, _s, _d, _r = await self.completed(clock, ha, opt)
                self.assertEqual(clock.at(0).timestamp(), epoch.close_requested_at)
                self.assertEqual(clock.at(0.2).timestamp(), epoch.msc_requested_at)
                self.assertIsNone(opt._msc_transition)
                self.assertEqual([0.2], [r[0] for r in ha.requests if r[1] == "select_option"])
                for at in (2.0, 3.0):
                    _s, decision, result = await self.cycle(clock, ha, opt, at, charge=1.21)
                    self.assertTrue(result.automatic_application_completed, result)
                self.assertEqual(1.61, decision.ess_charge_limit)
                self.assertEqual(1.61, opt._solar_relief.completed_total_kw)
                self.assertEqual(0.4, opt._solar_relief.relief_kw)
                self.assertEqual(0.0, decision.import_limit)
                self.assertEqual("none", decision.trace_values["battery_export_owner"])
                self.assertFalse(any(r[1] == "set_number" and r[2] == opt.cfg.grid_import_limit
                                     and r[3] > 0.011 for r in ha.requests))
        asyncio.run(run())

    def test_final_joint_read_rejects_replaced_regressed_or_cancelled_pending_proof(self):
        async def run(case):
            clock, ha, opt = self.scenario()
            with clock.active():
                epoch = await self.pending(clock, ha, opt)
                armed, fired = False, False
                injected_request_count = None

                def arm():
                    nonlocal armed
                    armed = True

                def interrupt(entities):
                    nonlocal fired, injected_request_count
                    if not armed or fired or not {ha.cfg.ems_mode_select, ha.cfg.grid_export_limit} <= entities:
                        return
                    fired = True
                    injected_request_count = len(ha.requests)
                    if case == "replacement":
                        opt._msc_transition = replace(epoch)
                    elif case == "numeric_replacement":
                        value, stamp, exact = opt._number_settlement_requests[ha.cfg.grid_export_limit]
                        opt._number_settlement_requests[ha.cfg.grid_export_limit] = (value, stamp + 0.01, exact)
                    elif case in {"stale", "pre_request", "regressed"}:
                        stamp = {"stale": -1000, "pre_request": 0.1, "regressed": 1.1}[case]
                        ha._report(ha.cfg.ems_mode_select, MODE_MAX_SELF, stamp)
                    elif case == "reconnect":
                        opt.on_ws_disconnect()
                        opt.on_ws_connect()
                    elif case == "cancel":
                        raise asyncio.CancelledError()

                ha.helper_hook, ha.metadata_hook = arm, interrupt
                if case == "cancel":
                    with self.assertRaises(asyncio.CancelledError):
                        await self.cycle(clock, ha, opt, 1.3)
                    self.assertFalse(epoch.close_accepted)
                    self.assertFalse(epoch.msc_accepted)
                    self.assertEqual((), epoch.identity)
                else:
                    _s, _d, result = await self.cycle(clock, ha, opt, 1.3)
                    self.assertFalse(result.automatic_application_completed, (case, result))
                    if case in {"replacement", "numeric_replacement", "stale", "pre_request", "regressed"}:
                        self.assertTrue(result.fallback_attempted, (case, result))
                        later_exports = [value for _at, method, entity, value
                                         in ha.requests[injected_request_count:]
                                         if method == "set_number" and entity == ha.cfg.grid_export_limit]
                        self.assertTrue(later_exports, case)
                        self.assertTrue(all(value <= 0.011 for value in later_exports), (case, later_exports))
                    else:
                        self.assertTrue(result.fallback_attempted or not result.succeeded, (case, result))
                self.assertTrue(fired, case)
                self.assertIsNone(opt._solar_relief.completed_total_kw)
                self.assertIsNone(opt._msc_maintenance_epoch)
                self.assertFalse(opt._msc_baseline_established)
                # No accepted command or final failed proof becomes a receipt.
                self.assertIsNone(opt._solar_relief.completed_context)
        for case in ("replacement", "numeric_replacement", "stale", "pre_request", "regressed", "reconnect", "cancel"):
            with self.subTest(case=case):
                asyncio.run(run(case))

    def test_real_tick_typed_pending_remains_uncommitted_and_scheduler_error_free(self):
        from app.optimizer import _MscTransitionPending

        async def run():
            clock, ha, opt = self.scenario()
            with clock.active():
                with self.assertRaises(_MscTransitionPending):
                    await opt._tick()
                self.assertIsNone(opt._last_decision)
                self.assertIsNone(opt._solar_relief.completed_total_kw)
                self.assertIsNotNone(opt._msc_transition)
                self.assertTrue(opt._msc_transition.close_accepted)
                clock.elapsed = 0.2
                self.provider_advance(clock, ha)
                opt._last_cycle_error = "previous failure"
                await opt._safe_tick()
                self.assertEqual("", opt._last_cycle_error)
                self.assertIsNone(opt._last_decision)
                self.assertIsNone(opt._solar_relief.completed_total_kw)
                self.assertTrue(opt._msc_transition.msc_accepted)
                self.assertFalse(any(r[1] == "set_number" and r[2] == ha.cfg.grid_export_limit
                                     and r[3] > 0.011 for r in ha.requests))
        asyncio.run(run())

    def test_passive_msc_diagnostic_sink_cannot_change_commands_or_receipt_highwater(self):
        class Sink:
            def __init__(self, raises):
                self.raises = raises
                self.calls = 0

            def __getattr__(self, _name):
                def record(*_args, **_kwargs):
                    self.calls += 1
                    if self.raises:
                        raise RuntimeError("offline diagnostic sink unavailable")
                return record

        async def run(mode):
            clock, ha, opt = self.scenario()
            sink = None
            if mode != "normal":
                sink = Sink(mode == "raises")
                opt._msc_settlement_evidence = sink
            with clock.active():
                epoch, _s, _d, _r = await self.completed(clock, ha, opt)
                for at in (2.0, 3.0):
                    _s, d, result = await self.cycle(clock, ha, opt, at, charge=1.21)
                    self.assertTrue(result.automatic_application_completed, result)
                self.assertEqual(1.61, d.ess_charge_limit)
                if sink:
                    self.assertGreater(sink.calls, 0)
                return (ha.requests, epoch.close_requested_at, epoch.msc_requested_at,
                        opt._solar_relief.completed_total_kw, opt._solar_completion_msc_high_water)
        normal = asyncio.run(run("normal"))
        for mode in ("disabled", "raises"):
            with self.subTest(mode=mode):
                self.assertEqual(normal, asyncio.run(run(mode)))

    def test_old_persistent_helper_holds_until_original_dip_expiry_during_final_read(self):
        async def run(final_at):
            clock, ha, opt = self.scenario()
            with clock.active():
                await self.completed(clock, ha, opt)
                for at in (2.0, 3.0):
                    await self.cycle(clock, ha, opt, at, charge=1.21)
                self.assertEqual((clock.at(3).timestamp(),) * 2, opt._solar_dip_proof)
                # A persistent input_select does not periodically report by itself.
                ha.telemetry.remove(ha.cfg.sigenergy_mode_select)
                ha._state_value_metadata.pop(ha.cfg.sigenergy_mode_select)
                ha._report(ha.cfg.sigenergy_mode_select, ha.cfg.automated_option, -1000)
                ha.helper_hook = lambda: setattr(clock, "elapsed", final_at)
                state, decision, result = await self.cycle(clock, ha, opt, 4.0, charge=0.1, export=0.0)
                self.assertTrue(state.hvac_solar_inputs.control_mode.fresh)
                self.assertEqual(clock.at(-1000).timestamp(), state.hvac_solar_inputs.control_mode.observed_at_ts)
                self.assertTrue(decision.trace_gates["solar_surplus_dip_hold_active"])
                if final_at < 18:
                    self.assertTrue(result.automatic_application_completed, result)
                    self.assertFalse(result.fallback_attempted)
                    self.assertIsNotNone(opt._solar_relief.completed_total_kw)
                else:
                    self.assertFalse(result.automatic_application_completed)
                    self.assertTrue(result.fallback_attempted, result)
                    self.assertIsNone(opt._solar_relief.completed_total_kw)
                    self.assertIsNone(opt._msc_maintenance_epoch)
                    self.assertFalse(any(at >= 18 and method == "set_number" and entity == ha.cfg.grid_export_limit
                                         and value > 0.011 for at, method, entity, value in ha.requests))
        for final_at in (17.999, 18.0):
            with self.subTest(final_at=final_at):
                asyncio.run(run(final_at))

    def test_unbounded_reserve_projection_is_passive_and_does_not_inflate_fill_floor(self):
        async def run(suppress):
            clock, ha, opt = self.scenario(export_value_gate_enabled=True, export_value_gate_dry_run=True,
                                           sunrise_safety_factor=0.1)
            with clock.active(), patch.object(opt, "_battery_soc_required_to_sunrise", return_value=113.0):
                epoch = await self.pending(clock, ha, opt)
                if suppress:
                    with patch.object(opt, "_reserve_planning_diagnostics", return_value={}):
                        state, decision, result = await self.cycle(clock, ha, opt, 1.3)
                else:
                    state, decision, result = await self.cycle(clock, ha, opt, 1.3)
                    self.assertTrue(decision.trace_values["reserve_planning_exceeds_full_capacity"])
                    self.assertAlmostEqual(11.3, decision.trace_values["reserve_planning_required_kwh"])
                    self.assertAlmostEqual(1.3, decision.trace_values["reserve_planning_full_capacity_shortfall_kwh"])
                self.assertTrue(result.automatic_application_completed, result)
                self.assertEqual(60.0, state.battery_soc)
                self.assertEqual(113.0, decision.min_soc_to_sunrise)
                # 1.2 * 10kWh * (100%-60%) / just under four hours, rounded upward.
                self.assertEqual(1.21, decision.ess_charge_limit)
                self.assertEqual(1.21, opt._solar_relief.completed_total_kw)
                helper_values = [value for method, entity, value in ha.calls
                                 if method == "set_input_number" and entity == opt.cfg.min_soc_to_sunrise_helper]
                self.assertTrue(helper_values)
                self.assertEqual(100.0, helper_values[-1])
                return ha.requests
        self.assertEqual(asyncio.run(run(False)), asyncio.run(run(True)))

    def test_earned_receipt_and_maintenance_retire_on_later_proof_loss(self):
        async def run(case):
            clock, ha, opt = self.scenario()
            with clock.active():
                await self.completed(clock, ha, opt)
                for at in (2.0, 3.0):
                    await self.cycle(clock, ha, opt, at, charge=1.21)
                self.assertEqual(1.61, opt._solar_relief.completed_total_kw)
                self.assertIsNotNone(opt._msc_maintenance_epoch)
                armed, fired = False, False

                def arm():
                    nonlocal armed
                    armed = True
                    if case == "expiry":
                        # Only EMS stops reporting; numeric/telemetry reports continue.
                        ha.next_ems = None
                        clock.elapsed = 4.0 + opt.cfg.hvac_solar_data_max_age_seconds

                def lose_proof(entities):
                    nonlocal fired
                    if not armed or fired or not {ha.cfg.ems_mode_select, ha.cfg.grid_export_limit} <= entities:
                        return
                    fired = True
                    if case == "regressed":
                        ha._report(ha.cfg.ems_mode_select, MODE_MAX_SELF, 3.1)
                    elif case == "reconnect":
                        opt.on_ws_disconnect()
                        opt.on_ws_connect()
                    elif case == "cancel":
                        raise asyncio.CancelledError()
                    elif case == "exception":
                        raise RuntimeError("offline late joint read failure")

                ha.helper_hook, ha.metadata_hook = arm, lose_proof
                if case == "cancel":
                    with self.assertRaises(asyncio.CancelledError):
                        await self.cycle(clock, ha, opt, 4.0, charge=1.61)
                else:
                    _s, _d, result = await self.cycle(clock, ha, opt, 4.0, charge=1.61)
                    self.assertFalse(result.automatic_application_completed, result)
                self.assertTrue(fired)
                self.assertIsNone(opt._solar_relief.completed_total_kw)
                self.assertIsNone(opt._solar_relief.completed_context)
                self.assertIsNone(opt._msc_maintenance_epoch)
        for case in ("regressed", "reconnect", "cancel", "exception", "expiry"):
            with self.subTest(case=case):
                asyncio.run(run(case))

    def test_provider_deadline_expiry_during_final_read_releases_only_normal_charge(self):
        async def run():
            clock, ha, opt = self.scenario()
            provider = ha.cfg.solcast_api_last_polled_sensor
            ha.states[provider]["attributes"]["next_auto_update"] = clock.at(8).isoformat()
            with clock.active():
                await self.completed(clock, ha, opt)
                for at in (2.0, 3.0):
                    await self.cycle(clock, ha, opt, at, charge=1.21)
                self.assertEqual(1.61, opt._solar_relief.completed_total_kw)
                ha.helper_hook = lambda: setattr(clock, "elapsed", 8.0)
                _state, decision, result = await self.cycle(clock, ha, opt, 4.0, charge=1.61)
                self.assertTrue(result.automatic_application_completed, result)
                self.assertFalse(result.fallback_attempted)
                self.assertFalse(decision.trace_gates["solar_charge_ceiling_owned"])
                self.assertEqual(5.0, decision.ess_charge_limit)
                self.assertIsNone(opt._solar_relief.completed_total_kw)
                self.assertEqual("EXPIRED", opt._solar_provider_state)
                self.assertEqual(0.0, decision.import_limit)
                self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
                self.assertEqual("none", decision.trace_values["battery_export_owner"])
                self.assertEqual(5.0, [r[3] for r in ha.requests if r[1] == "set_number"
                                      and r[2] == ha.cfg.ess_max_charging_limit][-1])
        asyncio.run(run())
