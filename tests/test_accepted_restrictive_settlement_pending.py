"""Accepted restrictive settlement is bounded waiting, never permission.

Fixed decisions isolate real reader/apply/wait/authority and scheduler paths.
Independently scheduled setting reports do not model physical power response.
"""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

from app.models import BATTERY_EXPORT, EXPORT_BLOCKED, MSC_SURPLUS_CEILING, Decision
from app.optimizer import DISCHARGE_MODES, MODE_CMD_DISCHARGE_PV, MODE_MAX_SELF
from haos49_characterization_helpers import Haos49CharacterizationCase
from test_msc_settled_epoch_reuse import PeriodicReportHA, ReportClock


class RestrictiveCadenceHA(PeriodicReportHA):
    def __init__(self, clock, *, first_export=4.0, first_ems=2.9):
        super().__init__(clock, first_ems=first_ems, ems_period=6.0)
        self.next_export = first_export

    def configure(self, cfg):
        super().configure(cfg)
        self.numeric.discard(cfg.grid_export_limit)

    def deliver(self):
        super().deliver()
        while self.next_export is not None and self.next_export <= self.clock.elapsed + 1e-7:
            self._report(self.cfg.grid_export_limit, self.plant[self.cfg.grid_export_limit], self.next_export)
            self.next_export = round(self.next_export + 6.0, 6)


class AcceptedRestrictiveSettlementPendingTests(unittest.TestCase):
    def setUp(self):
        self.fixture = Haos49CharacterizationCase("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.addCleanup(self.fixture.tearDown)

    def scenario(self, old=1.1, *, ordinary=False, **cadence):
        clock = ReportClock()
        ha = RestrictiveCadenceHA(clock, **cadence)
        opt = self.fixture.optimizer(ha, ess_max_charging_limit="number.test_charge",
                                     ess_max_discharging_limit="number.test_discharge")
        ha.configure(opt.cfg)
        for entity, value in ((opt.cfg.grid_export_limit, str(old)),
                              (opt.cfg.ems_mode_select, MODE_MAX_SELF if ordinary else MODE_CMD_DISCHARGE_PV)):
            ha.plant[entity] = value
            ha._report(entity, value, -1.0)
        return clock, ha, opt

    def decision(self, target=25.0, *, recovery=False, ordinary=False):
        return Decision(ems_mode=MODE_MAX_SELF if recovery or ordinary else MODE_CMD_DISCHARGE_PV,
                        export_limit=target, export_intent=MSC_SURPLUS_CEILING if recovery else
                        EXPORT_BLOCKED if ordinary else BATTERY_EXPORT,
                        requires_verified_msc_before_export=recovery, import_limit=0.0,
                        ess_charge_limit=25.0, ess_discharge_limit=25.0, pv_max_power_limit=25.0)

    async def cycle(self, clock, ha, opt, target=25.0, *, at=None, **kind):
        if at is not None:
            self.assertGreaterEqual(at, clock.elapsed)
            clock.elapsed = at
        state = await opt._read_state()
        self.assertEqual(opt._msc_maintenance_identity(), state._msc_read_identity)
        decision = self.decision(target, **kind)
        return state, decision, await opt._apply(state, decision)

    def assert_pending(self, result):
        self.assertTrue(getattr(result, "restrictive_settlement_pending", False), result)
        self.assertFalse(result.succeeded)
        self.assertFalse(result.automatic_application_completed)
        self.assertFalse(result.automatic_transition_pending)

    def assert_closed_requests(self, ha, start):
        self.assertFalse(any(method == "select_option" and value in DISCHARGE_MODES
                             or method == "set_number" and entity == ha.cfg.grid_export_limit and value > .011
                             for _at, method, entity, value in ha.requests[start:]))

    def test_accepted_reductions_keep_three_second_fallback_and_bound_recovery_pending(self):
        async def run(old, target):
            clock, ha, opt = self.scenario(old)
            with clock.active():
                _s, _d, result = await self.cycle(clock, ha, opt, target)
                self.assert_pending(result)
                self.assertTrue(result.fallback_attempted)
                self.assertIn("export limit did not settle", result.error)
                export = [r for r in ha.requests if r[1] == "set_number" and r[2] == ha.cfg.grid_export_limit]
                self.assertEqual([(0.0, target), (3.0, .01)], [(r[0], r[3]) for r in export])
                attempt = opt._accepted_restrictive_settlement
                self.assertEqual(3.0, attempt.started_monotonic)
                self.assertEqual(18.0, attempt.deadline_monotonic)
                self.assert_closed_requests(ha, ha.requests.index(export[1]))
        for old, target in ((1.1, 1.0), (5.8, 5.0)):
            with self.subTest(old=old, target=target):
                asyncio.run(run(old, target))

    def test_ordinary_close_pending_completes_only_after_later_report(self):
        async def run():
            clock, ha, opt = self.scenario(25.0, ordinary=True)
            with clock.active():
                _s, _d, result = await self.cycle(clock, ha, opt, 0.0, ordinary=True)
                self.assert_pending(result)
                self.assertFalse(result.fallback_attempted)
                self.assertEqual(15.0, opt._accepted_restrictive_settlement.deadline_monotonic)
                self.assertEqual(1.0, opt._accepted_restrictive_wait_seconds())
                _s, _d, result = await self.cycle(clock, ha, opt, 0.0, ordinary=True, at=4.1)
                self.assertTrue(result.automatic_application_completed, result)
                self.assertIsNone(opt._accepted_restrictive_settlement)
                self.assertEqual(1, len([r for r in ha.requests if r[1] == "set_number"
                                        and r[2] == ha.cfg.grid_export_limit]))
        asyncio.run(run())

    def test_new_msc_phase_and_cached_reports_do_not_extend_deadline(self):
        async def run():
            clock, ha, opt = self.scenario()
            with clock.active():
                await self.cycle(clock, ha, opt, 1.0)
                attempt = opt._accepted_restrictive_settlement
                _s, _d, pending = await self.cycle(clock, ha, opt, at=8.0, recovery=True)
                self.assert_pending(pending)
                self.assertEqual(clock.at(8).timestamp(), opt._msc_transition.msc_requested_at)
                before = len(ha.requests)
                _s, _d, pending = await self.cycle(clock, ha, opt, at=8.1, recovery=True)
                self.assert_pending(pending)
                self.assertIs(attempt, opt._accepted_restrictive_settlement)
                self.assertEqual(18.0, attempt.deadline_monotonic)
                self.assert_closed_requests(ha, before)
                _s, _d, completed = await self.cycle(clock, ha, opt, at=9.0, recovery=True)
                self.assertTrue(completed.automatic_application_completed, completed)
                self.assertIsNone(opt._accepted_restrictive_settlement)
        asyncio.run(run())

    def test_exact_deadline_is_failure_and_next_attempt_renews_close_boundary(self):
        async def run():
            clock, ha, opt = self.scenario(first_export=None, first_ems=None)
            with clock.active():
                _s, _d, initial = await self.cycle(clock, ha, opt, 1.0)
                self.assert_pending(initial)
                old = opt._msc_transition.close_requested_at
                _s, _d, expired = await self.cycle(clock, ha, opt, at=18.0, recovery=True)
                self.assertFalse(expired.succeeded)
                self.assertFalse(getattr(expired, "restrictive_settlement_pending", False))
                self.assertIn("deadline", expired.error)
                self.assertIsNone(opt._accepted_restrictive_settlement)
                self.assertIsNone(opt._msc_transition.close_requested_at)
                before = len(ha.requests)
                _s, _d, retry = await self.cycle(clock, ha, opt, at=18.1, recovery=True)
                self.assert_pending(retry)
                self.assertGreater(opt._msc_transition.close_requested_at, old)
                self.assertEqual(18.1, opt._accepted_restrictive_settlement.started_monotonic)
                self.assertEqual(33.1, opt._accepted_restrictive_settlement.deadline_monotonic)
                self.assert_closed_requests(ha, before)
                _s, _d, expired_again = await self.cycle(clock, ha, opt, at=33.1, recovery=True)
                self.assertFalse(getattr(expired_again, "restrictive_settlement_pending", False))
                self.assertIn("deadline", expired_again.error)
        asyncio.run(run())

    def test_real_event_loop_without_ws_events_rechecks_and_commits_after_independent_proof(self):
        async def run():
            clock, ha, opt = self.scenario()
            decisions, waits = [], []
            def decide(_state):
                decision = self.decision(1.0) if not decisions else self.decision(recovery=True)
                decisions.append(decision)
                return decision
            async def no_events(awaitable, timeout):
                waits.append(timeout)
                awaitable.close()
                self.assertGreater(timeout, 0.0)
                self.assertLessEqual(timeout, 1.0)
                await clock.sleep(timeout)
                raise asyncio.TimeoutError()
            async def stop_after_commit(*_args):
                opt._running = False
            with clock.active(), patch.object(opt, "_decide", side_effect=decide), \
                    patch.object(opt, "_handle_notifications", side_effect=stop_after_commit), \
                    patch("app.optimizer.asyncio.wait_for", side_effect=no_events):
                await opt.run_forever()
                self.assertTrue(waits)
                self.assertLessEqual(len(waits), 5)
                self.assertGreaterEqual(len(decisions), 3)
                self.assertIs(decisions[-1], opt._last_decision)
                self.assertIsNone(opt._accepted_restrictive_settlement)
                self.assertEqual("", opt._last_cycle_error)
                export = [r for r in ha.requests if r[1] == "set_number" and r[2] == ha.cfg.grid_export_limit]
                self.assertEqual([(0, 1.0), (3, .01)], [(r[0], r[3]) for r in export[:2]])
                self.assertEqual(25.0, export[-1][3])
                selects = [r for r in ha.requests if r[1] == "select_option"]
                self.assertEqual(2, len(selects))
                self.assertGreater(selects[-1][0], 4.0)
                self.assertLess(selects[-1][0], 8.9)
                self.assertGreaterEqual(export[-1][0], 8.9)
                self.assertTrue(all(r[3] == MODE_MAX_SELF for r in selects))
                counts = {"export": len(export), "msc": len(selects),
                          "import": len([r for r in ha.requests if r[2] == ha.cfg.grid_import_limit]),
                          "discharge": len([r for r in ha.requests if r[2] == ha.cfg.ess_max_discharging_limit])}
                self.assertEqual({"export": 3, "msc": 2, "import": 2, "discharge": 4}, counts)
                self.assertEqual(12, len(ha.requests))
                other = [r for r in ha.requests if r[2] not in {
                    ha.cfg.grid_export_limit, ha.cfg.ems_mode_select,
                    ha.cfg.grid_import_limit, ha.cfg.ess_max_discharging_limit}]
                self.assertEqual(1, len(other))
                self.assertEqual(ha.cfg.ess_max_charging_limit, other[0][2])
        asyncio.run(run())

    def test_no_event_loop_with_ignored_reports_reaches_failure_without_hot_loop_or_redispatch(self):
        async def run():
            clock, ha, opt = self.scenario(first_export=None, first_ems=None)
            decisions, waits, outcomes = [], [], []
            def decide(_state):
                decision = self.decision(1.0) if not decisions else self.decision(recovery=True)
                decisions.append(decision)
                return decision
            async def no_events(awaitable, timeout):
                waits.append(timeout)
                awaitable.close()
                self.assertGreater(timeout, 0.0)
                self.assertLessEqual(timeout, 1.0)
                await clock.sleep(timeout)
                raise asyncio.TimeoutError()
            original_trace = opt._record_application_trace
            def stop_on_visible_expiry(state, decision, result=None, **kwargs):
                original_trace(state, decision, result, **kwargs)
                if result is not None:
                    outcomes.append(result)
                    if result.restrictive_settlement_expired:
                        opt._running = False
            with clock.active(), patch.object(opt, "_decide", side_effect=decide), \
                    patch.object(opt, "_record_application_trace", side_effect=stop_on_visible_expiry), \
                    patch("app.optimizer.asyncio.wait_for", side_effect=no_events):
                await opt.run_forever()
                self.assertEqual(18.0, clock.elapsed)
                self.assertLessEqual(len(waits), 11)
                self.assertGreater(len(waits), 1)
                self.assertTrue(outcomes[-1].restrictive_settlement_expired)
                self.assertTrue(all(r.restrictive_settlement_deadline_monotonic == 18.0
                                    for r in outcomes[:-1]))
                self.assertIn("deadline", opt._last_cycle_error)
                self.assertIsNone(opt._last_decision)
                self.assertIsNone(opt._accepted_restrictive_settlement)
                self.assertIsNone(opt._accepted_restrictive_wait_seconds())
                export = [r for r in ha.requests if r[1] == "set_number" and r[2] == ha.cfg.grid_export_limit]
                self.assertEqual([(0.0, 1.0), (3.0, .01)], [(r[0], r[3]) for r in export])
                self.assertEqual(1, len([r for r in ha.requests if r[1] == "select_option"]))
                self.assertLessEqual(len(ha.requests), 26)
                counts = {"export": len(export),
                          "msc": len([r for r in ha.requests if r[1] == "select_option"]),
                          "import": len([r for r in ha.requests if r[2] == ha.cfg.grid_import_limit]),
                          "discharge": len([r for r in ha.requests if r[2] == ha.cfg.ess_max_discharging_limit])}
                self.assertEqual({"export": 2, "msc": 1, "import": 10, "discharge": 10}, counts)
                self.assertEqual(23, len(ha.requests))
                self.assert_closed_requests(ha, ha.requests.index(export[1]))
        asyncio.run(run())

    def test_report_phase_sweep_remains_pending_or_fails_at_absolute_boundary(self):
        async def run(first_report):
            clock, ha, opt = self.scenario(25.0, ordinary=True, first_export=first_report)
            with clock.active():
                _s, _d, initial = await self.cycle(clock, ha, opt, 0.0, ordinary=True)
                self.assert_pending(initial)
                at = min(first_report + .1, 15.0)
                _s, _d, result = await self.cycle(clock, ha, opt, 0.0, ordinary=True, at=at)
                if first_report < 15.0:
                    self.assertTrue(result.automatic_application_completed, result)
                else:
                    self.assertFalse(result.succeeded)
                    self.assertIn("deadline", result.error)
                self.assert_closed_requests(ha, 0)
        for first_report in (3.0, 6.0, 12.0, 15.0):
            with self.subTest(independent_report=first_report):
                asyncio.run(run(first_report))

    def test_monotonic_regression_nan_and_infinity_retire_pending_before_dispatch(self):
        async def run(value):
            clock, ha, opt = self.scenario()
            with clock.active():
                await self.cycle(clock, ha, opt, 1.0)
                before = len(ha.requests)
                with patch("app.optimizer.monotonic", return_value=value):
                    _s, _d, result = await self.cycle(clock, ha, opt, at=8.0, recovery=True)
                self.assertFalse(getattr(result, "restrictive_settlement_pending", False))
                self.assertFalse(result.succeeded)
                self.assertIn("monotonic", result.error)
                self.assertIsNone(opt._accepted_restrictive_settlement)
                self.assert_closed_requests(ha, before)
        for value in (7.0, float("nan"), float("inf")):
            with self.subTest(monotonic=value):
                asyncio.run(run(value))

    def test_deadline_crossed_inside_final_joint_authority_read_never_reopens(self):
        async def run():
            clock, ha, opt = self.scenario()
            with clock.active():
                await self.cycle(clock, ha, opt, 1.0)
                await self.cycle(clock, ha, opt, at=8.0, recovery=True)
                fired = []
                def expire(entities):
                    if not fired and {ha.cfg.grid_export_limit, ha.cfg.ems_mode_select} <= entities:
                        fired.append(len(ha.requests))
                        clock.elapsed = 18.0
                        ha.deliver()
                # Arm after the initial state read; expiry occurs inside the
                # real application-time joint proof, not before application.
                clock.elapsed = 9.0
                state = await opt._read_state()
                before = len(ha.requests)
                ha.metadata_hook = expire
                result = await opt._apply(state, self.decision(recovery=True))
                self.assertTrue(fired)
                self.assertFalse(result.succeeded)
                self.assertFalse(getattr(result, "restrictive_settlement_pending", False))
                self.assertIsNone(opt._accepted_restrictive_settlement)
                self.assert_closed_requests(ha, before)
        asyncio.run(run())

    def test_deadline_crossed_inside_opening_service_is_followed_by_restrictive_cleanup(self):
        async def run():
            clock, ha, opt = self.scenario()
            with clock.active():
                await self.cycle(clock, ha, opt, 1.0)
                await self.cycle(clock, ha, opt, at=8.0, recovery=True)
                fired = []
                def expire(entity, value):
                    if not fired and entity == ha.cfg.grid_export_limit and value > .011:
                        fired.append(len(ha.requests))
                        clock.elapsed = 18.0
                        ha.deliver()
                    return None
                ha.write_hook = expire
                _s, _d, result = await self.cycle(clock, ha, opt, at=9.0, recovery=True)
                self.assertTrue(fired)
                self.assertFalse(result.succeeded)
                self.assertFalse(getattr(result, "restrictive_settlement_pending", False))
                self.assertIsNone(opt._accepted_restrictive_settlement)
                self.assertEqual("accepted_discharge_target_unobserved", result.restrictive_settlement_cause)
                self.assertIn("export limit did not settle", result.error)
                self.assertTrue(any(r[1] == "set_number" and r[2] == ha.cfg.grid_export_limit
                                    and r[3] <= .011 for r in ha.requests[fired[0]:]))
                self.assertLessEqual(float(ha.plant[ha.cfg.grid_export_limit]), .011)
                self.assert_closed_requests(ha, fired[0])
        asyncio.run(run())

    def test_scheduler_pending_is_uncommitted_and_fallback_still_resets_boost(self):
        async def run():
            clock, ha, opt = self.scenario()
            decision = self.decision(1.0)
            decision.trace_gates["evening_boost_reentry_candidate"] = True
            with clock.active(), patch.object(opt, "_decide", return_value=decision):
                await opt._safe_tick()
                self.assertEqual("", opt._last_cycle_error)
                self.assertIsNone(opt._last_decision)
                self.assertIsNone(opt._solar_relief.completed_total_kw)
                self.assertEqual("closed", opt._evening_boost_reentry.phase)
                self.assertEqual("application_or_cycle_failed", opt._evening_boost_reentry.reason)
        asyncio.run(run())

    def test_event_loop_debounce_wakes_at_pending_one_second_recheck_without_events(self):
        async def run():
            clock, ha, opt = self.scenario()
            with clock.active():
                await self.cycle(clock, ha, opt, 1.0)
                before = clock.elapsed
                waits = []
                async def no_events(awaitable, timeout):
                    waits.append(timeout)
                    awaitable.close()
                    await clock.sleep(timeout)
                    raise asyncio.TimeoutError()
                with patch("app.optimizer.asyncio.wait_for", side_effect=no_events):
                    await opt._drain_queue(3.0)
                self.assertEqual(1, len(waits))
                self.assertAlmostEqual(1.0, waits[0])
                self.assertAlmostEqual(before + 1.0, clock.elapsed)
        asyncio.run(run())
