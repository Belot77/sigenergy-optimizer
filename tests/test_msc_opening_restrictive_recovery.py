"""Bounded recovery after accepted primary MSC-opening proof is delayed.

Commands and reports are independent fake-HA events. Real reader, authority,
application and settlement paths run; no inverter power response is modeled.
"""
from __future__ import annotations

import asyncio
import importlib
import unittest

support = importlib.import_module("test_msc_settled_epoch_reuse")
pending_support = importlib.import_module("test_accepted_restrictive_settlement_pending")


class MscOpeningRestrictiveRecoveryTests(unittest.TestCase):
    CAUSE = "accepted_primary_msc_opening_unobserved"

    def setUp(self):
        self.fixture = support.MscSettledEpochReuseTests("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def scenario(self, *, first_ems=10.0):
        clock = support.ReportClock()
        ha = pending_support.RestrictiveCadenceHA(
            clock, first_export=4.0, first_ems=first_ems,
        )
        opt = self.fixture.fixture.optimizer(
            ha, ess_max_charging_limit="number.test_charge",
            ess_max_discharging_limit="number.test_discharge",
        )
        ha.configure(opt.cfg)
        return clock, ha, opt

    def assert_no_open(self, ha, start=0):
        self.assertFalse(any(
            method == "set_number" and entity == ha.cfg.grid_export_limit and value > .011
            or method == "select_option" and value in support.DISCHARGE_MODES
            for _at, method, entity, value in ha.requests[start:]
        ))

    def assert_pending(self, opt, result):
        self.assertTrue(result.restrictive_settlement_pending, result)
        self.assertFalse(result.succeeded)
        self.assertFalse(result.automatic_application_completed)
        self.assertTrue(result.fallback_attempted)
        self.assertEqual(self.CAUSE, result.restrictive_settlement_cause)
        attempt = opt._accepted_restrictive_settlement
        self.assertIsNotNone(attempt)
        self.assertEqual(self.CAUSE, attempt.cause)
        self.assertEqual("fallback", attempt.purpose)
        self.assertEqual(3.0, attempt.started_monotonic)
        self.assertEqual(18.0, attempt.deadline_monotonic)
        return attempt

    async def begin(self, clock, ha, opt):
        self.assertEqual(support.MODE_MAX_SELF, ha.plant[ha.cfg.ems_mode_select])
        _s, _d, result = await self.fixture.cycle(opt, ha, clock)
        attempt = self.assert_pending(opt, result)
        self.assertIn("Maximum Self Consumption did not settle", result.error)
        # The unchanged primary MSC request still gets its original three-second
        # wait. Only the subsequent accepted restrictive fallback is eligible.
        self.assertEqual([0.0, 3.0], [r[0] for r in ha.requests if r[1] == "select_option"])
        self.assertEqual([(3.0, .01)], [
            (r[0], r[3]) for r in ha.requests
            if r[1] == "set_number" and r[2] == ha.cfg.grid_export_limit
        ])
        self.assert_no_open(ha)
        return attempt

    def test_delayed_same_mode_report_uses_original_bounded_restrictive_recovery(self):
        async def run():
            clock, ha, opt = self.scenario()
            with clock.active():
                attempt = await self.begin(clock, ha, opt)
                _s, _d, waiting = await self.fixture.cycle(opt, ha, clock, at=8.0)
                self.assert_pending(opt, waiting)
                self.assertIs(attempt, opt._accepted_restrictive_settlement)
                epoch = opt._msc_transition
                self.assertEqual(clock.at(3.0).timestamp(), epoch.close_requested_at)
                self.assertEqual(clock.at(8.0).timestamp(), epoch.msc_requested_at)
                before = len(ha.requests)
                _s, _d, cached = await self.fixture.cycle(opt, ha, clock, at=8.1)
                self.assert_pending(opt, cached)
                self.assertEqual([], [r for r in ha.requests[before:]
                                      if r[1] == "select_option"])
                self.assert_no_open(ha)
                _s, _d, complete = await self.fixture.cycle(opt, ha, clock, at=10.1)
                self.assertTrue(complete.automatic_application_completed, complete.error)
                self.assertFalse(complete.fallback_attempted)
                self.assertIsNone(opt._accepted_restrictive_settlement)
                self.assertIsNone(opt._msc_transition)
                self.assertEqual([(3.0, .01), (10.1, 25.0)], [
                    (r[0], r[3]) for r in ha.requests
                    if r[1] == "set_number" and r[2] == ha.cfg.grid_export_limit
                ])
        asyncio.run(run())

    def test_exact_deadline_fails_without_extension_across_msc_phase(self):
        async def run():
            clock, ha, opt = self.scenario(first_ems=None)
            with clock.active():
                attempt = await self.begin(clock, ha, opt)
                await self.fixture.cycle(opt, ha, clock, at=8.0)
                for at in (8.1, 12.0, 17.9):
                    _s, _d, pending = await self.fixture.cycle(opt, ha, clock, at=at)
                    self.assert_pending(opt, pending)
                    self.assertIs(attempt, opt._accepted_restrictive_settlement)
                    self.assertEqual(18.0, attempt.deadline_monotonic)
                before = len(ha.requests)
                _s, _d, expired = await self.fixture.cycle(opt, ha, clock, at=18.0)
                self.assertFalse(expired.succeeded)
                self.assertFalse(expired.restrictive_settlement_pending)
                self.assertTrue(expired.restrictive_settlement_expired)
                self.assertIn("deadline expired", expired.error)
                self.assertIsNone(opt._accepted_restrictive_settlement)
                self.assertIsNone(opt._msc_transition.close_requested_at)
                self.assert_no_open(ha, before)
        asyncio.run(run())

    def test_later_open_contradiction_retires_budget_and_requires_new_close_then_msc(self):
        async def run():
            clock, ha, opt = self.scenario()
            with clock.active():
                old = await self.begin(clock, ha, opt)
                await self.fixture.cycle(opt, ha, clock, at=8.0)
                export = ha.cfg.grid_export_limit
                # Arrival and report time are both later than the accepted close.
                # Even an explained delayed opening is contradictory evidence.
                ha.delayed_reports.append((8.2, 8.2, export, "25.0"))
                before = len(ha.requests)
                _s, _d, invalid = await self.fixture.cycle(opt, ha, clock, at=8.3)
                self.assertFalse(invalid.succeeded)
                self.assertFalse(invalid.restrictive_settlement_pending)
                self.assertIn("contradicted by export report", invalid.error)
                self.assertIsNone(opt._accepted_restrictive_settlement)
                self.assert_no_open(ha, before)
                self.assertEqual(18.0, old.deadline_monotonic)

                _s, _d, close_pending = await self.fixture.cycle(opt, ha, clock, at=8.4)
                self.assertTrue(close_pending.transition_pending, close_pending)
                epoch = opt._msc_transition
                self.assertEqual(clock.at(8.4).timestamp(), epoch.close_requested_at)
                self.assertGreater(epoch.close_requested_at, old.close_request[1])
                self.assertEqual("close", epoch.phase)
                self.assertIsNone(opt._accepted_restrictive_settlement)
                self.assert_no_open(ha)
                # Scheduled close readback at t=10 permits a NEW MSC request.
                _s, _d, msc_pending = await self.fixture.cycle(opt, ha, clock, at=10.1)
                self.assertTrue(msc_pending.transition_pending, msc_pending)
                self.assertEqual(clock.at(10.1).timestamp(), epoch.msc_requested_at)
                self.assertGreater(epoch.msc_requested_at, epoch.close_requested_at)
                self.assert_no_open(ha)
                _s, _d, complete = await self.fixture.cycle(opt, ha, clock, at=16.1)
                self.assertTrue(complete.automatic_application_completed, complete.error)
                openings = [r for r in ha.requests if r[1] == "set_number"
                            and r[2] == export and r[3] > .011]
                self.assertEqual([(16.1, "set_number", export, 25.0)], openings)
        asyncio.run(run())

    def test_old_equal_future_missing_and_conflicting_reports_do_not_reopen(self):
        async def run(kind):
            clock, ha, opt = self.scenario(first_ems=None)
            with clock.active():
                await self.begin(clock, ha, opt)
                await self.fixture.cycle(opt, ha, clock, at=8.0)
                epoch = opt._msc_transition
                stamp = {"pre": 7.9, "equal": 8.0, "future": 1000.0,
                         "stale": -61.0, "missing": 8.0, "conflict": 8.05}[kind]
                ha._report(ha.cfg.ems_mode_select, support.MODE_MAX_SELF, stamp)
                if kind in {"missing", "conflict"}:
                    ha.metadata_policy = kind
                before = len(ha.requests)
                _s, _d, result = await self.fixture.cycle(opt, ha, clock, at=8.1)
                self.assertFalse(result.succeeded)
                self.assertFalse(result.automatic_application_completed)
                self.assert_no_open(ha, before)
                self.assertIsNone(opt._msc_maintenance_epoch)
                if opt._accepted_restrictive_settlement is not None:
                    self.assertEqual(18.0, opt._accepted_restrictive_settlement.deadline_monotonic)
                if opt._msc_transition is epoch:
                    self.assertEqual(clock.at(8.0).timestamp(), epoch.msc_requested_at)
        for kind in ("pre", "equal", "future", "stale", "missing", "conflict"):
            with self.subTest(report=kind):
                asyncio.run(run(kind))

    def test_fallback_close_rejection_is_not_eligible_waiting(self):
        async def run():
            clock, ha, opt = self.scenario()
            rejected = []
            def reject(entity, value):
                if entity == ha.cfg.grid_export_limit and value <= .011:
                    rejected.append(clock.elapsed)
                    return False
                return None
            ha.write_hook = reject
            with clock.active():
                _s, _d, result = await self.fixture.cycle(opt, ha, clock)
                self.assertEqual([3.0], rejected)
                self.assertFalse(result.succeeded)
                self.assertFalse(result.fallback_succeeded)
                self.assertFalse(result.restrictive_settlement_pending)
                self.assertIsNone(opt._accepted_restrictive_settlement)
                self.assert_no_open(ha)
        asyncio.run(run())

    def test_primary_msc_rejection_cannot_use_timeout_origin(self):
        async def run():
            clock, ha, opt = self.scenario()
            original = ha.select_option
            rejected = []
            async def reject_first(entity, value):
                if not rejected and entity == ha.cfg.ems_mode_select:
                    rejected.append(clock.elapsed)
                    ha.requests.append((clock.elapsed, "select_option", entity, value))
                    return False
                return await original(entity, value)
            ha.select_option = reject_first
            with clock.active():
                _s, _d, result = await self.fixture.cycle(opt, ha, clock)
                self.assertEqual([0.0], rejected)
                self.assertFalse(result.succeeded)
                self.assertFalse(result.restrictive_settlement_pending)
                self.assertIn("failed reasserting Maximum Self Consumption", result.error)
                self.assertIsNone(opt._accepted_restrictive_settlement)
                self.assert_no_open(ha)
        asyncio.run(run())

    def test_manual_or_remote_takeover_during_pending_stops_automatic_writes(self):
        async def run(kind):
            clock, ha, opt = self.scenario(first_ems=None)
            with clock.active():
                await self.begin(clock, ha, opt)
                clock.elapsed = 8.0
                state = await opt._read_state()
                decision = support.Decision(
                    ems_mode=support.MODE_MAX_SELF, export_limit=25.0,
                    export_intent=support.MSC_SURPLUS_CEILING,
                    requires_verified_msc_before_export=True, import_limit=0.0,
                    ess_charge_limit=25.0, ess_discharge_limit=25.0, pv_max_power_limit=25.0,
                )
                fired = []
                def takeover(entities):
                    if not fired and ha.cfg.sigenergy_mode_select in entities:
                        fired.append(len(ha.requests))
                        entity = ha.cfg.sigenergy_mode_select if kind == "manual" else ha.cfg.ha_control_switch
                        value = ha.cfg.manual_option if kind == "manual" else "off"
                        ha.plant[entity] = value
                        ha._report(entity, value, clock.elapsed)
                ha.metadata_hook = takeover
                result = await opt._apply(state, decision)
                self.assertTrue(fired)
                self.assertFalse(result.automatic_application_completed)
                self.assertFalse(result.restrictive_settlement_pending)
                self.assertIsNone(opt._accepted_restrictive_settlement)
                self.assertEqual([], ha.requests[fired[0]:])
                self.assert_no_open(ha)
        for kind in ("manual", "remote"):
            with self.subTest(owner=kind):
                asyncio.run(run(kind))
