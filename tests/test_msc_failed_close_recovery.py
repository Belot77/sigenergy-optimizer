"""Offline actual-reader recovery after a failed MSC export-close command.

Accepted commands and independently delivered reports remain separate evidence;
these simulations establish permission ordering, not physical inverter behavior.
"""
from __future__ import annotations

import asyncio
import unittest

import test_msc_settled_epoch_reuse as reuse
from haos49_characterization_helpers import Haos49CharacterizationCase


class MscFailedCloseRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = Haos49CharacterizationCase("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.addCleanup(self.fixture.tearDown)

    def scenario(self, failure="false"):
        clock, ha, opt = reuse.MscSettledEpochReuseTests.scenario(
            self, first_ems=4.5, ems_period=1.0,
        )
        failed = []

        def fail_close(entity, value):
            if entity != ha.cfg.grid_export_limit or value > 0.011 or failed:
                return None
            failed.append(clock.elapsed)
            if failure == "timeout":
                # The fake plant applied the command before the transport failed.
                raise TimeoutError("offline applied-close response timeout")
            return False

        ha.write_hook = fail_close
        return clock, ha, opt

    async def cycle(self, clock, ha, opt, at=None, **kwargs):
        return await reuse.MscSettledEpochReuseTests.cycle(
            self, opt, ha, clock, at=at, **kwargs,
        )

    def close_requests(self, ha):
        return [r for r in ha.requests if r[1] == "set_number"
                and r[2] == ha.cfg.grid_export_limit and r[3] <= 0.011]

    async def failed_fallback(self, clock, ha, opt):
        _state, _decision, result = await self.cycle(clock, ha, opt)
        self.assertTrue(result.fallback_attempted, result)
        self.assertFalse(result.fallback_succeeded, result)
        epoch = opt._msc_transition
        self.assertIsNotNone(epoch.identity)
        self.assertFalse(epoch.close_accepted)
        self.assertTrue(epoch.msc_accepted)
        self.assertEqual(1, len(self.close_requests(ha)))
        clock.elapsed = max(5.0, clock.elapsed)
        ha.deliver()
        state = await opt._read_state()
        self.assertTrue(state.hvac_solar_inputs.live_snapshot)
        self.assertEqual(opt._msc_maintenance_identity(), state._msc_read_identity)
        self.assertTrue(opt._msc_export_closed(state))
        self.assertTrue(opt._msc_exact_observed(state))
        self.assertFalse(opt._msc_transition_observed(state))
        return epoch

    async def recovery(self, failure):
        clock, ha, opt = self.scenario(failure)
        with clock.active():
            failed = await self.failed_fallback(clock, ha, opt)
            original_close = failed.close_requested_at
            _s, _d, repaired = await self.cycle(clock, ha, opt)
            self.assertTrue(repaired.transition_pending, repaired)
            self.assertEqual(2, len(self.close_requests(ha)),
                             "matching closed reports must not strand a failed close; retry the restrictive command")
            renewed = opt._msc_transition
            self.assertTrue(renewed.close_accepted)
            self.assertGreater(renewed.close_requested_at, original_close)
            self.assertFalse(any(r[2] == ha.cfg.grid_export_limit and r[3] > 0.011
                                 for r in ha.requests if r[1] == "set_number"))
            _s, _d, waiting = await self.cycle(clock, ha, opt, clock.elapsed + 0.2)
            self.assertTrue(waiting.transition_pending, waiting)
            self.assertTrue(opt._msc_transition.msc_accepted)
            _s, _d, complete = await self.cycle(clock, ha, opt, clock.elapsed + 1.1)
            self.assertTrue(complete.automatic_application_completed, complete)
            self.assertTrue(complete.succeeded, complete)
            self.assertIsNone(opt._msc_transition)
            self.assertTrue(opt._msc_baseline_established)

    def test_false_fallback_close_is_retried_before_eventual_reopen(self):
        asyncio.run(self.recovery("false"))

    def test_applied_but_timed_out_fallback_close_requires_new_accepted_close(self):
        asyncio.run(self.recovery("timeout"))

    async def repaired_close(self, clock, ha, opt):
        await self.failed_fallback(clock, ha, opt)
        _s, _d, result = await self.cycle(clock, ha, opt)
        self.assertTrue(result.transition_pending, result)
        self.assertEqual(2, len(self.close_requests(ha)))
        epoch = opt._msc_transition
        self.assertTrue(epoch.close_accepted)
        self.assertEqual("close", epoch.phase)
        return epoch

    def assert_no_reopen(self, ha, start=0):
        self.assertFalse(any(method == "set_number" and entity == ha.cfg.grid_export_limit
                             and value > 0.011
                             for _at, method, entity, value in ha.requests[start:]))
        self.assertFalse(any(method == "select_option" and value in reuse.DISCHARGE_MODES
                             for _at, method, _entity, value in ha.requests[start:]))

    def test_accepted_repair_preserves_boundary_while_waiting_for_later_close_report(self):
        async def run():
            clock, ha, opt = self.scenario()
            with clock.active():
                epoch = await self.repaired_close(clock, ha, opt)
                boundary = epoch.close_requested_at
                # Same clock means independently delivered reports cannot advance.
                for _ in range(3):
                    _s, _d, pending = await self.cycle(clock, ha, opt)
                    self.assertTrue(pending.transition_pending, pending)
                    self.assertIs(epoch, opt._msc_transition)
                    self.assertEqual(boundary, epoch.close_requested_at)
                    self.assertEqual(2, len(self.close_requests(ha)))
                    self.assertEqual("close", epoch.phase)
                    self.assert_no_reopen(ha)
                _s, _d, pending = await self.cycle(clock, ha, opt, 5.2)
                self.assertTrue(pending.transition_pending, pending)
                self.assertEqual("msc", epoch.phase)
                self.assertEqual(boundary, epoch.close_requested_at)
                _s, _d, completed = await self.cycle(clock, ha, opt, 6.3)
                self.assertTrue(completed.automatic_application_completed, completed)
        asyncio.run(run())

    def test_nonqualifying_reports_after_repair_never_reopen(self):
        async def run(entity_kind, report_kind):
            clock, ha, opt = self.scenario()
            with clock.active():
                epoch = await self.repaired_close(clock, ha, opt)
                _s, _d, pending = await self.cycle(clock, ha, opt, 5.2)
                self.assertTrue(pending.transition_pending, pending)
                boundary = epoch.close_requested_at if entity_kind == "export" else epoch.msc_requested_at
                entity = ha.cfg.grid_export_limit if entity_kind == "export" else ha.cfg.ems_mode_select
                value = "0.01" if entity_kind == "export" else reuse.MODE_MAX_SELF
                ha.numeric.discard(ha.cfg.grid_export_limit)
                ha.next_ems = None
                stamp = {
                    "equal": boundary - clock.BASE.timestamp(),
                    "pre": boundary - clock.BASE.timestamp() - 0.1,
                    "stale": -1000.0, "future": 1000.0,
                    "conflict": 6.0,
                }[report_kind]
                clock.elapsed = 6.0
                ha.deliver()
                ha._report(entity, value, stamp)
                if report_kind == "conflict":
                    # Enrichment sees contradictory state for the very same report.
                    original = ha.get_state_report_metadata
                    async def conflicting(entities):
                        rows = await original(entities)
                        if entity in rows:
                            rows[entity]["state"] = "25" if entity_kind == "export" else reuse.MODE_CMD_DISCHARGE_PV
                        return rows
                    ha.get_state_report_metadata = conflicting
                for at in (6.0, 6.2):
                    _s, _d, result = await self.cycle(clock, ha, opt, at)
                    self.assertFalse(result.automatic_application_completed, result)
                    self.assertFalse(opt._msc_baseline_established)
                    self.assertIsNone(opt._msc_maintenance_epoch)
                    self.assert_no_reopen(ha)
        for entity in ("export", "msc"):
            for report in ("equal", "pre", "stale", "future", "conflict"):
                with self.subTest(entity=entity, report=report):
                    asyncio.run(run(entity, report))

    def test_repeated_failed_close_cannot_be_accepted_from_matching_reports(self):
        async def run(failure):
            clock, ha, opt = self.scenario()
            with clock.active():
                await self.failed_fallback(clock, ha, opt)
                def fail_again(entity, value):
                    if entity == ha.cfg.grid_export_limit and value <= 0.011:
                        if failure == "timeout":
                            raise TimeoutError("offline renewed-close timeout")
                        return False
                    return None
                ha.write_hook = fail_again
                previous_count = len(self.close_requests(ha))
                for _ in range(3):
                    _s, _d, result = await self.cycle(clock, ha, opt, clock.elapsed + 1.0)
                    self.assertFalse(result.automatic_application_completed, result)
                    self.assertTrue(result.fallback_attempted, result)
                    self.assertFalse(result.fallback_succeeded, result)
                    self.assertGreater(len(self.close_requests(ha)), previous_count)
                    previous_count = len(self.close_requests(ha))
                    self.assertFalse(opt._msc_transition.close_accepted)
                    self.assertFalse(opt._msc_baseline_established)
                    self.assert_no_reopen(ha)
        for failure in ("false", "timeout"):
            with self.subTest(failure=failure):
                asyncio.run(run(failure))

    def test_independent_import_ess_and_pv_restrictions_survive_every_recovery_tick(self):
        async def run():
            clock, ha, opt = self.scenario()
            def restrict(state, decision):
                state.demand_window_active = True
                decision.standby_holdoff_active = True
                decision.ess_charge_limit = 0.0
                decision.ess_discharge_limit = 0.0
                decision.pv_max_power_limit = 0.0
            with clock.active():
                for at in (0.0, 5.0, 5.2, 6.3):
                    before = len(ha.requests)
                    _s, _d, result = await self.cycle(clock, ha, opt, at, before_apply=restrict)
                    for entity in (ha.cfg.grid_import_limit, ha.cfg.ess_max_charging_limit,
                                   ha.cfg.ess_max_discharging_limit, ha.cfg.pv_max_power_limit):
                        values = [value for _at, method, target, value in ha.requests[before:]
                                  if method == "set_number" and target == entity]
                        if at < 6.3:
                            self.assertTrue(values, (at, entity))
                        self.assertTrue(all(value <= 0.011 for value in values), (at, entity, values))
                        self.assertLessEqual(float(ha.plant[entity]), 0.011, (at, entity))
                    if at < 6.3:
                        self.assertFalse(result.automatic_application_completed, result)
                        self.assert_no_reopen(ha)
                self.assertTrue(result.automatic_application_completed, result)
        asyncio.run(run())

    def test_manual_and_remote_takeover_before_repair_stop_all_requests(self):
        async def run(kind):
            clock, ha, opt = self.scenario()
            with clock.active():
                await self.failed_fallback(clock, ha, opt)
                before = len(ha.requests)
                fired = []
                def takeover(entities):
                    if fired or not {ha.cfg.sigenergy_mode_select, ha.cfg.ha_control_switch} <= entities:
                        return
                    fired.append(True)
                    entity = ha.cfg.sigenergy_mode_select if kind == "manual" else ha.cfg.ha_control_switch
                    value = ha.cfg.manual_option if kind == "manual" else "off"
                    ha.plant[entity] = value
                    ha._report(entity, value, clock.elapsed)
                _s, _d, result = await self.cycle(
                    clock, ha, opt, before_apply=lambda _s, _d: setattr(ha, "metadata_hook", takeover),
                )
                self.assertTrue(fired)
                self.assertFalse(result.automatic_application_completed, result)
                self.assertEqual([], ha.requests[before:])
                self.assertFalse(opt._msc_baseline_established)
                self.assertIsNone(opt._msc_maintenance_epoch)
        for kind in ("manual", "remote_off"):
            with self.subTest(takeover=kind):
                asyncio.run(run(kind))

    def test_takeover_during_repair_close_blocks_subsequent_writes(self):
        async def run(kind):
            clock, ha, opt = self.scenario()
            with clock.active():
                await self.failed_fallback(clock, ha, opt)
                at_takeover = []
                def takeover(entity, value):
                    if entity == ha.cfg.grid_export_limit and value <= 0.011 and not at_takeover:
                        at_takeover.append(len(ha.requests))
                        target = ha.cfg.sigenergy_mode_select if kind == "manual" else ha.cfg.ha_control_switch
                        state = ha.cfg.manual_option if kind == "manual" else "off"
                        ha.plant[target] = state
                        ha._report(target, state, clock.elapsed)
                    return None
                ha.write_hook = takeover
                _s, _d, result = await self.cycle(clock, ha, opt)
                self.assertTrue(at_takeover)
                self.assertFalse(result.automatic_application_completed, result)
                self.assertEqual([], ha.requests[at_takeover[0]:])
                self.assertFalse(opt._msc_baseline_established)
                self.assert_no_reopen(ha)
        for kind in ("manual", "remote_off"):
            with self.subTest(takeover=kind):
                asyncio.run(run(kind))

    def test_cancel_reconnect_or_request_replacement_during_repair_cannot_complete(self):
        from dataclasses import replace
        async def run(kind):
            clock, ha, opt = self.scenario()
            with clock.active():
                await self.failed_fallback(clock, ha, opt)
                fired = []
                def interrupt(entity, value):
                    if fired or entity != ha.cfg.grid_export_limit or value > 0.011:
                        return None
                    fired.append(True)
                    if kind == "cancel":
                        raise asyncio.CancelledError()
                    if kind == "reconnect":
                        opt.on_ws_disconnect()
                        opt.on_ws_connect()
                    elif kind == "epoch_replacement":
                        opt._msc_transition = replace(opt._msc_transition)
                    else:
                        old_value, stamp, exact = opt._number_settlement_requests[entity]
                        opt._number_settlement_requests[entity] = (old_value, stamp + 0.01, exact)
                    return None
                ha.write_hook = interrupt
                if kind == "cancel":
                    with self.assertRaises(asyncio.CancelledError):
                        await self.cycle(clock, ha, opt)
                else:
                    _s, _d, result = await self.cycle(clock, ha, opt)
                    self.assertFalse(result.automatic_application_completed, result)
                    _s, _d, result = await self.cycle(clock, ha, opt, clock.elapsed + 0.2)
                    self.assertFalse(result.automatic_application_completed, result)
                self.assertTrue(fired)
                self.assertFalse(opt._msc_baseline_established)
                self.assertIsNone(opt._msc_maintenance_epoch)
                self.assert_no_reopen(ha)
        for kind in ("cancel", "reconnect", "epoch_replacement", "numeric_replacement"):
            with self.subTest(interruption=kind):
                asyncio.run(run(kind))

    def test_repaired_epoch_rechecks_identity_and_request_at_joint_opening_read(self):
        from dataclasses import replace
        async def run(kind):
            clock, ha, opt = self.scenario()
            with clock.active():
                epoch = await self.repaired_close(clock, ha, opt)
                await self.cycle(clock, ha, opt, 5.2)
                fired = []
                def interrupt(entities):
                    if fired or not {ha.cfg.ems_mode_select, ha.cfg.grid_export_limit,
                                     ha.cfg.sigenergy_mode_select, ha.cfg.ha_control_switch} <= entities:
                        return
                    fired.append(True)
                    if kind == "cancel":
                        raise asyncio.CancelledError()
                    if kind == "reconnect":
                        opt.on_ws_disconnect()
                        opt.on_ws_connect()
                    elif kind == "epoch_replacement":
                        opt._msc_transition = replace(epoch)
                    else:
                        entity = ha.cfg.grid_export_limit
                        value, stamp, exact = opt._number_settlement_requests[entity]
                        opt._number_settlement_requests[entity] = (value, stamp + 0.01, exact)
                kwargs = {"before_apply": lambda _s, _d: setattr(ha, "metadata_hook", interrupt)}
                if kind == "cancel":
                    with self.assertRaises(asyncio.CancelledError):
                        await self.cycle(clock, ha, opt, 6.3, **kwargs)
                else:
                    _s, _d, result = await self.cycle(clock, ha, opt, 6.3, **kwargs)
                    self.assertFalse(result.automatic_application_completed, result)
                self.assertTrue(fired)
                self.assertFalse(opt._msc_baseline_established)
                self.assertIsNone(opt._msc_maintenance_epoch)
                self.assert_no_reopen(ha)
        for kind in ("cancel", "reconnect", "epoch_replacement", "numeric_replacement"):
            with self.subTest(interruption=kind):
                asyncio.run(run(kind))

    def test_real_tick_recovers_failed_close_without_committing_pending_attempts(self):
        import test_solar_msc_planning_integration as integration
        async def run():
            clock, ha, opt = integration.SolarMscPlanningIntegrationTests.scenario(self)
            failed = []
            def fail_initial_and_fallback(entity, value):
                if entity == ha.cfg.grid_export_limit and value <= 0.011 and len(failed) < 2:
                    failed.append(clock.elapsed)
                    return False
                return None
            ha.write_hook = fail_initial_and_fallback
            with clock.active():
                await opt._safe_tick()
                self.assertEqual(2, len(failed))
                self.assertTrue(opt._last_cycle_error)
                self.assertIsNone(opt._last_decision)
                self.assertFalse(opt._msc_transition.close_accepted)
                clock.elapsed = max(2.0, clock.elapsed)
                integration.SolarMscPlanningIntegrationTests.provider_advance(self, clock, ha)
                await opt._safe_tick()
                self.assertEqual("", opt._last_cycle_error)
                self.assertIsNone(opt._last_decision)
                self.assertTrue(opt._msc_transition.close_accepted)
                self.assert_no_reopen(ha)
                clock.elapsed += 0.2
                await opt._safe_tick()
                self.assertEqual("", opt._last_cycle_error)
                self.assertIsNone(opt._last_decision)
                self.assertTrue(opt._msc_transition.msc_accepted)
                self.assert_no_reopen(ha)
                clock.elapsed += 1.1
                await opt._safe_tick()
                self.assertEqual("", opt._last_cycle_error)
                self.assertIsNotNone(opt._last_decision)
                self.assertIsNone(opt._msc_transition)
                self.assertTrue(opt._msc_baseline_established)
                self.assertIsNotNone(opt._solar_relief.completed_total_kw)
                self.assertTrue(any(method == "set_number" and entity == ha.cfg.grid_export_limit
                                    and value > 0.011 for _at, method, entity, value in ha.requests))
        asyncio.run(run())
