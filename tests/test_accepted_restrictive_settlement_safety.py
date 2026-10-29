"""Independent safety checks for bounded accepted restrictive settlement.

Use actual reader/application/authority paths and independent setting reports.
Fixed decisions isolate application semantics; no physical response is inferred.
"""
from __future__ import annotations

import asyncio
from dataclasses import replace
import unittest
from unittest.mock import patch

import test_accepted_restrictive_settlement_pending as pending_helpers


class AcceptedRestrictiveSettlementSafetyTests(unittest.TestCase):
    def setUp(self):
        self.case = pending_helpers.AcceptedRestrictiveSettlementPendingTests("runTest")
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)

    def assert_not_pending(self, opt, result):
        self.assertFalse(result.restrictive_settlement_pending, result)
        self.assertFalse(result.automatic_application_completed, result)
        self.assertIsNone(opt._accepted_restrictive_settlement)
        self.assertIsNone(opt._msc_maintenance_epoch)
        self.assertIsNone(opt._solar_relief.completed_total_kw)

    def test_rejected_primary_or_restrictive_services_never_become_accepted_waiting(self):
        async def run(label, timeout):
            clock, ha, opt = self.case.scenario()
            fired = []
            entities = {
                "target": opt.cfg.grid_export_limit,
                "close": opt.cfg.grid_export_limit,
                "import": opt.cfg.grid_import_limit,
                "charge": opt.cfg.ess_max_charging_limit,
                "discharge": opt.cfg.ess_max_discharging_limit,
                "pv": opt.cfg.pv_max_power_limit,
            }

            def fail(entity, value):
                match = entity == entities[label] and (
                    value > .011 if label == "target" else value <= .011
                )
                if match and not fired:
                    fired.append((clock.elapsed, entity, value))
                    if timeout:
                        raise TimeoutError("synthetic rejected service response")
                    return False
                return None

            ha.write_hook = fail
            with clock.active():
                state = await opt._read_state()
                decision = self.case.decision(1.0)
                # Activate real independent import, charge and PV restrictions.
                # Every other required restriction still runs when one fails.
                decision.standby_holdoff_active = True
                decision.ess_charge_limit = 0.0
                decision.pv_max_power_limit = 0.0
                if label == "target" and timeout:
                    with self.assertRaises(TimeoutError):
                        await opt._apply(state, decision)
                    self.assertIsNone(opt._accepted_restrictive_settlement)
                else:
                    result = await opt._apply(state, decision)
                    self.assert_not_pending(opt, result)
                    self.assertFalse(result.succeeded, result)
                    self.assertTrue(result.fallback_attempted, result)
                self.assertTrue(fired, (label, timeout, ha.requests))
                self.case.assert_closed_requests(ha, 1)

        for label in ("target", "close", "import", "charge", "discharge", "pv"):
            for timeout in (False, True):
                with self.subTest(service=label, timeout=timeout):
                    asyncio.run(run(label, timeout))

    def test_authority_and_continuity_loss_during_pending_application_retire_waiting(self):
        async def run(kind):
            clock, ha, opt = self.case.scenario()
            with clock.active():
                _s, _d, first = await self.case.cycle(clock, ha, opt, 1.0)
                self.case.assert_pending(first)
                clock.elapsed = 8.0
                state = await opt._read_state()
                injected = []

                def takeover(entities):
                    if injected or opt.cfg.sigenergy_mode_select not in entities:
                        return
                    injected.append(len(ha.requests))
                    if kind == "cancel":
                        raise asyncio.CancelledError()
                    if kind == "reconnect":
                        opt.on_ws_disconnect()
                        opt.on_ws_connect()
                    elif kind == "configuration":
                        opt.cfg.battery_power_sensor_invert = not opt.cfg.battery_power_sensor_invert
                    else:
                        entity = (opt.cfg.sigenergy_mode_select if kind == "manual"
                                  else opt.cfg.ha_control_switch)
                        value = opt.cfg.manual_option if kind == "manual" else "off"
                        ha.plant[entity] = value
                        ha._report(entity, value, clock.elapsed)

                ha.metadata_hook = takeover
                if kind == "cancel":
                    with self.assertRaises(asyncio.CancelledError):
                        await opt._apply(state, self.case.decision(recovery=True))
                    self.assertIsNone(opt._accepted_restrictive_settlement)
                else:
                    result = await opt._apply(state, self.case.decision(recovery=True))
                    self.assert_not_pending(opt, result)
                self.assertTrue(injected, (kind, ha.requests))
                self.case.assert_closed_requests(ha, injected[0])
                if kind in {"manual", "remote_off"}:
                    self.assertEqual([], ha.requests[injected[0]:])
                self.assertFalse(opt._msc_baseline_established)
                self.assertIsNone(opt._msc_maintenance_epoch)

        for kind in ("manual", "remote_off", "reconnect", "configuration", "cancel"):
            with self.subTest(interruption=kind):
                asyncio.run(run(kind))

    def test_same_value_replacement_timestamp_or_exactness_retires_original_wait(self):
        async def run(field):
            clock, ha, opt = self.case.scenario(first_export=None, first_ems=None)
            with clock.active():
                _s, _d, first = await self.case.cycle(clock, ha, opt, 1.0)
                self.case.assert_pending(first)
                original = opt._accepted_restrictive_settlement
                value, stamp, exact = original.close_request
                # Model replacement of the actual dispatch ledger, never a
                # diagnostic record or a guard patched to return permission.
                opt._number_settlement_requests[opt.cfg.grid_export_limit] = (
                    value, stamp + .01 if field == "timestamp" else stamp,
                    not exact if field == "exactness" else exact,
                )
                before = len(ha.requests)
                _s, _d, result = await self.case.cycle(
                    clock, ha, opt, at=clock.elapsed + .1, recovery=True,
                )
                self.assert_not_pending(opt, result)
                self.assertFalse(result.succeeded, result)
                self.assertIn("identity", result.error)
                self.case.assert_closed_requests(ha, before)

        for field in ("timestamp", "exactness"):
            with self.subTest(replaced=field):
                asyncio.run(run(field))

    def test_ordinary_close_wait_cannot_be_reused_for_msc_recovery_purpose(self):
        async def run():
            clock, ha, opt = self.case.scenario(25.0, ordinary=True, first_export=None)
            with clock.active():
                _s, _d, first = await self.case.cycle(clock, ha, opt, 0.0, ordinary=True)
                self.case.assert_pending(first)
                self.assertEqual("ordinary_close", opt._accepted_restrictive_settlement.purpose)
                before = len(ha.requests)
                _s, _d, changed = await self.case.cycle(
                    clock, ha, opt, at=4.0, recovery=True,
                )
                self.assert_not_pending(opt, changed)
                self.assertFalse(changed.succeeded, changed)
                self.case.assert_closed_requests(ha, before)

        asyncio.run(run())

    def test_live_flag_without_reader_identity_and_legacy_snapshots_cannot_grant_waiting(self):
        async def run(legacy):
            clock, ha, opt = self.case.scenario()
            with clock.active():
                state = await opt._read_state()
                state._msc_read_identity = None
                if legacy:
                    state.hvac_solar_inputs = replace(state.hvac_solar_inputs, live_snapshot=False)
                result = await opt._apply(state, self.case.decision(1.0))
                self.assertFalse(result.restrictive_settlement_pending, result)
                self.assertIsNone(opt._accepted_restrictive_settlement)
                self.assertIsNone(opt._msc_maintenance_epoch)
                self.assertIsNone(opt._solar_relief.completed_total_kw)

        for legacy in (False, True):
            with self.subTest(legacy_snapshot=legacy):
                asyncio.run(run(legacy))

    def test_expired_fallback_with_fresh_closed_read_still_requires_real_new_close_request(self):
        async def run():
            clock, ha, opt = self.case.scenario(first_ems=None)
            with clock.active():
                _s, _d, first = await self.case.cycle(clock, ha, opt, 1.0)
                self.case.assert_pending(first)
                original = opt._accepted_restrictive_settlement
                state, _d, expired = await self.case.cycle(
                    clock, ha, opt, at=original.deadline_monotonic, recovery=True,
                )
                self.assertLessEqual(state.current_export_limit, .011)
                self.assertTrue(state.current_export_limit_observed)
                self.assert_not_pending(opt, expired)
                self.assertIn("deadline", expired.error)
                closes_before = [r for r in ha.requests if r[1] == "set_number"
                                 and r[2] == opt.cfg.grid_export_limit and r[3] <= .011]
                before = len(ha.requests)
                _s, _d, retry = await self.case.cycle(
                    clock, ha, opt, at=clock.elapsed + .1, recovery=True,
                )
                closes_after = [r for r in ha.requests if r[1] == "set_number"
                                and r[2] == opt.cfg.grid_export_limit and r[3] <= .011]
                self.assertEqual(len(closes_before) + 1, len(closes_after))
                self.assertGreater(opt._msc_transition.close_requested_at, original.close_request[1])
                self.assertFalse(retry.automatic_application_completed, retry)
                self.case.assert_closed_requests(ha, before)

        asyncio.run(run())

    def test_fresh_post_request_export_or_ems_contradiction_is_failure_not_waiting(self):
        async def run(kind):
            clock, ha, opt = self.case.scenario()
            with clock.active():
                _s, _d, first = await self.case.cycle(clock, ha, opt, 1.0)
                self.case.assert_pending(first)
                if kind == "ems":
                    _s, _d, pending = await self.case.cycle(
                        clock, ha, opt, at=clock.elapsed + .1, recovery=True,
                    )
                    self.case.assert_pending(pending)
                    self.assertTrue(opt._msc_transition.msc_accepted)
                    boundary = opt._msc_transition.msc_requested_at
                    entity = opt.cfg.ems_mode_select
                    value = pending_helpers.MODE_CMD_DISCHARGE_PV
                    previous_updated = ha._state_value_metadata[entity]["last_updated"]
                    ha.next_ems = None
                else:
                    boundary = opt._accepted_restrictive_settlement.close_request[1]
                    entity = opt.cfg.grid_export_limit
                    value = "1.1"
                    ha.next_export = None
                arrives = clock.elapsed + .1
                self.assertGreater(clock.at(arrives).timestamp(), boundary)
                ha.delayed_reports.append((arrives, arrives, entity, value))
                before = len(ha.requests)
                state, _d, contradicted = await self.case.cycle(
                    clock, ha, opt, at=arrives, recovery=True,
                )
                if kind == "ems":
                    self.assertEqual(value, state.current_ems_mode)
                    # A new same-value report, with unchanged last_updated,
                    # remains genuinely later contradictory device evidence.
                    self.assertEqual(previous_updated, ha._state_value_metadata[entity]["last_updated"])
                else:
                    self.assertGreater(state.current_export_limit, .011)
                self.assert_not_pending(opt, contradicted)
                self.assertFalse(contradicted.succeeded, contradicted)
                self.assertIn("contradict", contradicted.error)
                self.case.assert_closed_requests(ha, before)

        for kind in ("export", "ems"):
            with self.subTest(contradiction=kind):
                asyncio.run(run(kind))

    def test_expiry_retry_origin_is_retired_by_a_later_operator_or_remote_pause(self):
        async def run(kind):
            clock, ha, opt = self.case.scenario(first_export=None, first_ems=None)
            with clock.active():
                await self.case.cycle(clock, ha, opt, 1.0)
                _s, _d, expired = await self.case.cycle(clock, ha, opt, at=18.0, recovery=True)
                self.assertFalse(expired.succeeded)
                self.assertIsNotNone(opt._accepted_restrictive_retry)
                entity = (opt.cfg.sigenergy_mode_select if kind == "manual"
                          else opt.cfg.ha_control_switch)
                value = opt.cfg.manual_option if kind == "manual" else "off"
                ha.plant[entity] = value
                ha._report(entity, value, 18.1)
                before = len(ha.requests)
                _s, _d, paused = await self.case.cycle(clock, ha, opt, at=18.1, recovery=True)
                self.assertFalse(paused.automatic_application_completed, paused)
                self.assertFalse(paused.restrictive_settlement_pending, paused)
                self.assertIsNone(opt._accepted_restrictive_settlement)
                self.assertIsNone(opt._accepted_restrictive_retry)
                self.case.assert_closed_requests(ha, before)

        for kind in ("manual", "remote_off"):
            with self.subTest(pause=kind):
                asyncio.run(run(kind))

    def test_charge_authority_await_crossing_deadline_cannot_dispatch_late_permissive_charge(self):
        async def run():
            clock, ha, opt = self.case.scenario()
            with clock.active():
                await self.case.cycle(clock, ha, opt, 1.0)
                await self.case.cycle(clock, ha, opt, at=8.0, recovery=True)
                armed, control_reads, fired = [], [], []

                def opening(entity, value):
                    if entity == opt.cfg.grid_export_limit and value > .011:
                        armed.append(clock.elapsed)
                    return None

                def expire(entities):
                    if not armed or fired or opt.cfg.sigenergy_mode_select not in entities:
                        return
                    control_reads.append(clock.elapsed)
                    # After opening, the normal ESS preflight authority read
                    # precedes the charge request. Its original implementation
                    # directly writes charging after the token was consumed.
                    if len(control_reads) == 1:
                        fired.append(len(ha.requests))
                        clock.elapsed = 18.0
                        ha.deliver()

                ha.write_hook = opening
                ha.metadata_hook = expire
                _s, _d, result = await self.case.cycle(clock, ha, opt, at=9.0, recovery=True)
                self.assertTrue(armed)
                self.assertTrue(fired)
                self.assertFalse(result.succeeded, result)
                self.assertFalse(result.restrictive_settlement_pending, result)
                self.assertFalse(any(at >= 18.0 and method == "set_number"
                                     and entity == opt.cfg.ess_max_charging_limit and value > .011
                                     for at, method, entity, value in ha.requests))
                self.assertIsNone(opt._accepted_restrictive_settlement)
                self.assertIsNone(opt._msc_maintenance_epoch)
                self.assertIsNone(opt._solar_relief.completed_total_kw)

        asyncio.run(run())

    def test_active_pending_at_entry_yields_to_manual_force_and_remote_off_without_duplicate_actions(self):
        async def run(kind):
            clock, ha, opt = self.case.scenario()
            with clock.active():
                _s, _d, initial = await self.case.cycle(clock, ha, opt, 1.0)
                self.case.assert_pending(initial)
                self.assertIsNotNone(opt._accepted_restrictive_settlement)
                entity = (opt.cfg.ha_control_switch if kind == "remote_off"
                          else opt.cfg.sigenergy_mode_select)
                value = ("off" if kind == "remote_off" else
                         opt.cfg.manual_option if kind == "manual" else opt.cfg.full_export_option)
                ha.plant[entity] = value
                ha._report(entity, value, 8.0)
                before = len(ha.requests)
                _s, _d, paused = await self.case.cycle(clock, ha, opt, at=8.0, recovery=True)
                self.assertTrue(paused.succeeded, paused)
                self.assertFalse(paused.automatic_application_completed, paused)
                self.assertFalse(paused.restrictive_settlement_pending, paused)
                self.assertIsNone(opt._accepted_restrictive_settlement)
                self.assertIsNone(opt._accepted_restrictive_retry)
                self.assertIsNone(opt._msc_maintenance_epoch)
                if opt._msc_transition is not None:
                    self.assertFalse(opt._msc_transition.close_accepted)
                    self.assertFalse(opt._msc_transition.msc_accepted)
                actions = [(method, entity) for _at, method, entity, _value in ha.requests[before:]]
                self.assertEqual(len(actions), len(set(actions)), ha.requests[before:])
                if kind != "force":
                    self.case.assert_closed_requests(ha, before)

        for kind in ("manual", "force", "remote_off"):
            with self.subTest(owner=kind):
                asyncio.run(run(kind))

    def test_trace_sink_failure_preserves_requests_deadline_cause_and_uncommitted_outcome(self):
        async def run(broken):
            clock, ha, opt = self.case.scenario()
            decision = self.case.decision(1.0)
            with clock.active(), patch.object(opt, "_decide", return_value=decision):
                if broken:
                    with patch.object(opt, "_record_decision_trace", side_effect=RuntimeError("sink unavailable")):
                        await opt._safe_tick()
                else:
                    await opt._safe_tick()
                token = opt._accepted_restrictive_settlement
                self.assertIsNotNone(token)
                self.assertEqual("", opt._last_cycle_error)
                self.assertIsNone(opt._last_decision)
                self.assertIsNone(opt._solar_relief.completed_total_kw)
                self.assertIsNone(opt._msc_maintenance_epoch)
                if not broken:
                    application = opt._decision_trace[0]["application"]
                    self.assertEqual("pending", application["status"])
                    self.assertFalse(application["succeeded"])
                    self.assertTrue(application["fallback_attempted"])
                    self.assertEqual("accepted_restrictive_settlement_pending", application["error_code"])
                    self.assertEqual({
                        "pending": True,
                        "purpose": token.purpose,
                        "cause": token.cause,
                        "deadline_monotonic": token.deadline_monotonic,
                    }, application["restrictive_settlement"])
                return (ha.requests, token.purpose, token.cause, token.close_request,
                        token.started_monotonic, token.deadline_monotonic,
                        opt._evening_boost_reentry.phase)

        self.assertEqual(asyncio.run(run(False)), asyncio.run(run(True)))
