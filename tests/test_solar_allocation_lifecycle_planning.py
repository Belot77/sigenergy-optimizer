"""Offline allocation lifecycles; service acceptance never simulates PV physics.

Use the guarded test command in SOLAR_ALLOCATION_LIFECYCLE_PLANNING.md. Existing
fixtures provide explicit synthetic forecasts, source timestamps and fake HA.
"""
from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import AsyncMock, Mock, patch

from app.models import HVACObservedValue, MSC_SURPLUS_CEILING
from app.optimizer import MODE_MAX_SELF
from test_msc_baseline_overlay_contract import (
    ClockedRecordingHA, establish_observed_msc_baseline, later_msc_report_clock,
)


class SolarAllocationLifecyclePlanningTests(unittest.TestCase):
    def setUp(self):
        # Composition avoids collecting the source fixture's test methods.
        from test_phase1_solar_physical_relief_characterization import (
            SolarPhysicalReliefCharacterizationTests,
        )
        self.fixture = SolarPhysicalReliefCharacterizationTests("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)

    def _start(self, **settings):
        fixture = self.fixture
        settings.setdefault("solar_surplus_fill_deadline_margin_minutes", 0.0)
        opt = fixture._optimizer(**settings)
        ha = ClockedRecordingHA()
        asyncio.run(establish_observed_msc_baseline(
            fixture, opt, ha, fixture.WHEN - timedelta(seconds=2),
        ))
        # Setting writes now succeed without changing the reported setting.
        ha.settle_numbers = False
        return opt, ha

    @staticmethod
    def _readback(value, stamp):
        return HVACObservedValue(
            value=value, available=True, fresh=True, observed_at_ts=stamp,
        )

    def _decide(self, opt, seconds, *, charge=0.0, export=15.0,
                readback=5.0, stamps=None, forecast=None, **changes):
        fixture = self.fixture
        state = fixture._flow_state(seconds, charge=charge, export=export, **changes)
        state.current_ess_charge_limit = readback
        state.current_ess_charge_limit_observation = self._readback(
            readback, fixture.WHEN.timestamp() + seconds - 0.25,
        )
        state.hvac_solar_inputs = replace(
            state.hvac_solar_inputs, remote_ems_control=self._readback("on", state.timestamp.timestamp()),
        )
        if stamps is not None:
            state.hvac_solar_inputs = replace(state.hvac_solar_inputs, **{
                name: replace(getattr(state.hvac_solar_inputs, name), observed_at_ts=stamp)
                for name, stamp in stamps.items()
            })
        if forecast is not None:
            state.solcast_detailed = fixture._detailed_forecast(forecast)
        if not opt._solar_provider_baselined:
            baseline = replace(state, solcast_provider_polled=datetime.fromtimestamp(
                fixture.WHEN.timestamp() - 60, timezone.utc,
            ).isoformat())
            with fixture.optimizer_time(state.timestamp):
                opt._update_solar_provider(baseline, state.timestamp.timestamp())
        with fixture.optimizer_time(state.timestamp), patch(
            "app.optimizer.monotonic", return_value=1000.0 + seconds,
        ):
            decision = opt._decide(state)
        return state, decision

    def _apply(self, opt, ha, state, decision, *, finish=True, report_charge=False):
        with later_msc_report_clock(ha, state.timestamp) as moment, patch(
            "app.optimizer.monotonic", return_value=1000.0 + (
                state.timestamp - self.fixture.WHEN
            ).total_seconds(),
        ):
            for entity, value in (
                (opt.cfg.sigenergy_mode_select, opt.cfg.automated_option),
                (opt.cfg.ha_control_switch, "on"),
                (opt.cfg.ems_mode_select, MODE_MAX_SELF),
                (opt.cfg.grid_export_limit, state.current_export_limit),
            ):
                ha._record_state_value(entity, value)
            result = asyncio.run(opt._apply(state, decision))
            if finish:
                opt._finish_solar_reentry_application(state, decision, result)
            if result.succeeded and report_charge:
                # Independent later telemetry, never a side effect of service success.
                moment[0] += timedelta(milliseconds=100)
                ha._record_state_value(opt.cfg.ess_max_charging_limit, decision.ess_charge_limit)
        if result.succeeded and result.automatic_application_completed:
            opt._last_state, opt._last_decision = state, decision
        return result

    def _assert_solar(self, decision, charge):
        self.assertTrue(decision.solar_surplus_policy_active, decision.trace_values.get("solar_surplus_fail_reason"))
        self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
        self.assertEqual(MSC_SURPLUS_CEILING, decision.export_intent)
        self.assertEqual("none", decision.trace_values["battery_export_owner"])
        self.assertEqual(25.0, decision.export_limit)
        self.assertEqual(25.0, decision.pv_max_power_limit)
        self.assertAlmostEqual(charge, decision.ess_charge_limit)

    def test_real_application_negative_balance_reset_and_distinct_stream_reacquisition(self):
        opt, ha = self._start()
        for second, charge, target in ((0, 1.2, 1.2), (1, 1.2, 1.21), (2, 1.21, 1.21), (3, 1.21, 1.61)):
            state, decision = self._decide(opt, second, charge=charge)
            self._assert_solar(decision, target)
            self.assertTrue(self._apply(opt, ha, state, decision).automatic_application_completed)
        # Readback is deliberately still 5 kW: Solar currently consumes the
        # successful command boundary, not ESS setting confirmation, for feedback.
        self.assertEqual(5.0, state.current_ess_charge_limit_observation.value)
        self.assertAlmostEqual(1.61, opt._solar_relief.command_kw)

        bad = self.fixture._flow_state(4, charge=0.002, export=15.051)
        bad.pv_kw, bad.load_kw = 16.026, 1.049
        bad.hvac_solar_inputs = replace(
            bad.hvac_solar_inputs,
            pv_power=replace(bad.hvac_solar_inputs.pv_power, value=16.026),
            load_power=replace(bad.hvac_solar_inputs.load_power, value=1.049),
        )
        with self.fixture.optimizer_time(bad.timestamp):
            reset = opt._decide(bad)
        self._assert_solar(reset, 1.21)
        self.assertEqual("physical_flow_untrusted", reset.trace_values["solar_physical_relief_reason"])
        self.assertFalse(reset.trace_gates["solar_physical_relief_flow_trusted"])
        self.assertTrue(self._apply(opt, ha, bad, reset).succeeded)
        self.assertIsNone(opt._solar_relief.command_ts)

        state, baseline = self._decide(opt, 5)
        self.assertTrue(self._apply(opt, ha, state, baseline, report_charge=True).succeeded)
        boundary = opt._solar_relief.command_ts
        names = ("pv_power", "load_power", "grid_import_power", "grid_export_power")
        for index, lagging in enumerate(names):
            with self.subTest(lagging=lagging):
                # Each cohort holds one different source at the command boundary.
                stamps = {name: boundary if name == lagging else boundary + 0.1 for name in names}
                state, waiting = self._decide(opt, 6 + index * 0.1, stamps=stamps, readback=0.0)
                self.assertEqual(1.21, waiting.ess_charge_limit)
                self.assertEqual(0, waiting.trace_values["solar_physical_relief_confirmations"])
                self.assertTrue(self._apply(opt, ha, state, waiting).succeeded)
                self.assertEqual(boundary, opt._solar_relief.command_ts)
        for second, expected in ((7, 1.21), (8, 1.61)):
            stamps = {name: self.fixture.WHEN.timestamp() + second - index * 0.1
                      for index, name in enumerate(names)}
            state, recovered = self._decide(opt, second, stamps=stamps, readback=0.0)
            self._assert_solar(recovered, expected)
            self.assertTrue(self._apply(opt, ha, state, recovered).succeeded)

    def test_provider_expiry_during_charge_restores_normal_then_new_poll_reacquires(self):
        opt, ha = self._start()
        due = self.fixture.WHEN + timedelta(seconds=2)
        state, decision = self._decide(opt, 0, solcast_provider_next_update=datetime.fromtimestamp(due.timestamp(), timezone.utc).isoformat())
        original = ha.set_number
        clock = None
        async def expire_during_write(entity, value):
            accepted = await original(entity, value)
            if entity == opt.cfg.ess_max_charging_limit and value == 1.2:
                # The accepted service awaits until the scheduled deadline,
                # without manufacturing a new provider observation.
                clock[0] = datetime.fromtimestamp(due.timestamp(), timezone.utc)
            return accepted
        ha.set_number = expire_during_write
        with later_msc_report_clock(ha, state.timestamp) as clock:
            result = asyncio.run(opt._apply(state, decision))
            opt._finish_solar_reentry_application(state, decision, result)
        self.assertTrue(result.automatic_application_completed)
        writes = [v for a, e, v in ha.calls if a == "set_number" and e == opt.cfg.ess_max_charging_limit]
        self.assertEqual([1.2, 5.0], writes)
        self.assertFalse(decision.trace_gates["solar_charge_ceiling_owned"])
        self.assertIsNone(opt._solar_relief.command_ts)
        ha.set_number = original
        # Unchanged poll cannot clear the expired provider obligation.
        unchanged, normal = self._decide(opt, 3, solcast_provider_polled=state.solcast_provider_polled)
        self.assertEqual(5.0, normal.ess_charge_limit)
        self.assertTrue(self._apply(opt, ha, unchanged, normal).succeeded)
        advanced, recovered = self._decide(opt, 4, solcast_provider_polled=datetime.fromtimestamp(
            (self.fixture.WHEN + timedelta(seconds=4)).timestamp(), timezone.utc,
        ).isoformat())
        self._assert_solar(recovered, 1.21)
        self.assertTrue(self._apply(opt, ha, advanced, recovered).automatic_application_completed)
        self.assertEqual(1.21, opt._solar_relief.command_kw)

    def test_forecast_downgrade_recomputes_present_charge_without_repaying_deferred_energy(self):
        opt, ha = self._start(grid_connection_export_limit_kw=0.0)
        decisions = []
        # Fixed interval anchors keep the downgrade distinct from elapsed time.
        # Only the downgraded payloads introduce a new successful provider poll.
        for second, future_pv, poll_second in ((0, 3.0, -1), (6, 3.0, -1), (12, 2.2, 12), (18, 1.8, 18)):
            state, decision = self._decide(
                opt, second, forecast=[6.0] + [future_pv] * 7,
                solcast_provider_polled=datetime.fromtimestamp(
                    self.fixture.WHEN.timestamp() + poll_second, timezone.utc,
                ).isoformat(),
            )
            self.assertTrue(self._apply(opt, ha, state, decision).automatic_application_completed)
            decisions.append(decision)
            self.assertTrue(decision.trace_gates["solar_charge_ceiling_owned"])
            self.assertLessEqual(decision.ess_charge_limit, 5.0)
            self.assertEqual(25.0, decision.export_limit)
        self.assertEqual([1.2, 1.21], [d.ess_charge_limit for d in decisions[:2]])
        self.assertEqual([0.0, 0.0, 0.6, 2.0], [
            round(d.trace_values["solar_charge_ceiling_required_now_kwh"], 6) for d in decisions
        ])
        self.assertGreater(decisions[2].ess_charge_limit, 1.2)
        self.assertGreater(decisions[3].ess_charge_limit, 4.0)
        self.assertEqual(4.8, decisions[-1].trace_values["solar_charge_ceiling_protected_fill_need_kwh"])
        self.assertEqual(2.8, decisions[-1].trace_values["solar_charge_ceiling_future_opportunity_kwh"])
        # No synthetic SoC rise was delivered; the model reacts to the latest
        # opportunity, without asserting that lost charging can still be recovered.
        self.assertEqual(60.0, state.battery_soc)

    def test_late_forecast_shortfall_releases_solar_but_cannot_guarantee_fill(self):
        opt, ha = self._start(grid_connection_export_limit_kw=0.0)
        early_state, early = self._decide(opt, 0, forecast=[6.0] + [3.0] * 7)
        self.assertEqual(1.2, early.ess_charge_limit)
        self.assertTrue(self._apply(opt, ha, early_state, early).succeeded)
        # Explicit synthetic update at 17:30: no unobserved SoC/energy gain is
        # credited, current PV stays ample, future opportunity disappears.
        seconds = 3.5 * 3600
        late_state, late = self._decide(
            opt, seconds, forecast=[6.0] * 8, export=0.0, charge=5.0, current_export_limit=0.01,
            solcast_provider_polled=datetime.fromtimestamp(
                self.fixture.WHEN.timestamp() + seconds, timezone.utc,
            ).isoformat(),
            solcast_provider_next_update=datetime.fromtimestamp(
                self.fixture.WHEN.timestamp() + seconds + 3600, timezone.utc,
            ).isoformat(),
        )
        self.assertFalse(late.solar_surplus_policy_active)
        self.assertEqual("timed_charge_opportunity_insufficient", late.trace_values["solar_surplus_fail_reason"])
        self.assertEqual("normal", late.trace_values["ess_charge_limit_owner"])
        self.assertEqual(5.0, late.ess_charge_limit)
        self.assertIsNone(late.trace_values["solar_charge_ceiling_required_now_kwh"])
        self.assertLess(late.trace_values["solar_safe_timed_charge_opportunity_kwh"], 4.0)
        # Even continuously reaching the normal maximum for the last half hour
        # cannot supply the fixture's unchanged 4 kWh physical fill need.
        self.assertLess(late.ess_charge_limit * 0.5, 4.0)
        self.assertTrue(self._apply(opt, ha, late_state, late).automatic_application_completed)
    def test_inflight_operator_takeover_stops_automatic_recovery_writes(self):
        opt, ha = self._start()
        state, decision = self._decide(opt, 0)
        original = ha.set_number
        writes_after_takeover = []
        taken = False
        async def take_over(entity, value):
            nonlocal taken
            if taken:
                writes_after_takeover.append((entity, value))
            accepted = await original(entity, value)
            if entity == opt.cfg.ess_max_charging_limit:
                taken = True
                ha._record_state_value(opt.cfg.sigenergy_mode_select, opt.cfg.manual_option)
            return accepted
        ha.set_number = take_over
        result = self._apply(opt, ha, state, decision)
        self.assertFalse(result.automatic_application_completed)
        self.assertFalse(result.fallback_attempted)
        self.assertEqual([], writes_after_takeover)
        self.assertIsNone(opt._solar_relief.command_ts)

    def test_cancelled_real_tick_retires_feedback_without_committing_attempt(self):
        opt, ha = self._start()
        state, initial = self._decide(opt, 0)
        self.assertTrue(self._apply(opt, ha, state, initial).succeeded)
        previous = opt._last_decision
        next_state, _ = self._decide(opt, 1)
        opt._read_state = AsyncMock(return_value=next_state)
        opt._record_application_trace = Mock()
        original_decide = opt._decide
        def decide_at_snapshot_local_time(snapshot):
            with self.fixture.optimizer_time(snapshot.timestamp):
                return original_decide(snapshot)
        opt._decide = decide_at_snapshot_local_time
        original = ha.set_number
        async def cancel_charge(entity, value):
            if entity == opt.cfg.ess_max_charging_limit:
                raise asyncio.CancelledError()
            return await original(entity, value)
        ha.set_number = cancel_charge
        with later_msc_report_clock(ha, next_state.timestamp), patch(
            "app.optimizer.monotonic", return_value=1001.0,
        ):
            with self.assertRaises(asyncio.CancelledError):
                asyncio.run(opt._tick())
        self.assertIs(previous, opt._last_decision)
        self.assertIsNone(opt._solar_relief.command_ts)
        self.assertEqual(0.0, opt._solar_relief.relief_kw)
        self.assertEqual("cycle_cancelled", opt._solar_charge_reentry.reason)

    def test_rejected_provider_generation_cannot_restrict_until_another_poll(self):
        opt, ha = self._start()
        state, zero = self._decide(opt, 0)
        self.assertTrue(self._apply(opt, ha, state, zero).succeeded)
        later_poll = datetime.fromtimestamp(self.fixture.WHEN.timestamp() + 1, timezone.utc).isoformat()
        rejected_state, rejected = self._decide(
            opt, 1, solcast_provider_polled=later_poll, solcast_provider_next_update=None,
        )
        self.assertEqual(5.0, rejected.ess_charge_limit)
        self.assertFalse(rejected.trace_gates["solar_provider_authority_trusted"])
        self.assertTrue(self._apply(opt, ha, rejected_state, rejected).succeeded)
        repaired_state, repaired = self._decide(opt, 2, solcast_provider_polled=later_poll)
        self.assertEqual(5.0, repaired.ess_charge_limit)
        self.assertFalse(repaired.trace_gates["solar_provider_authority_trusted"])
        self.assertTrue(self._apply(opt, ha, repaired_state, repaired).succeeded)
        fresh_state, fresh = self._decide(opt, 3, solcast_provider_polled=datetime.fromtimestamp(
            self.fixture.WHEN.timestamp() + 3, timezone.utc,
        ).isoformat())
        self._assert_solar(fresh, 1.21)
        self.assertTrue(self._apply(opt, ha, fresh_state, fresh).automatic_application_completed)
        self.assertEqual(1.21, opt._solar_relief.command_kw)

    def test_fallback_requires_independent_close_and_msc_reports_before_normal_charge(self):
        for deliver_msc in (False, True):
            with self.subTest(deliver_msc=deliver_msc):
                opt, ha = self._start(ess_max_discharging_limit="number.test_discharge")
                state, initial = self._decide(opt, 0, demand_window_active=True)
                self.assertTrue(self._apply(opt, ha, state, initial).succeeded)
                state, decision = self._decide(opt, 1, demand_window_active=True)
                original_number, original_bulk = ha.set_number, ha.bulk_states
                original_wait = opt._wait_for_exact_entity_state
                failed, pending_close = False, False
                clock = None
                async def fail_discharge(entity, value):
                    nonlocal failed, pending_close
                    if entity == opt.cfg.ess_max_discharging_limit and value > 0.011 and not failed:
                        failed = True
                        ha.calls.append(("set_number", entity, value))
                        ha.settle_selects = deliver_msc
                        return False
                    accepted = await original_number(entity, value)
                    if failed and entity == opt.cfg.grid_export_limit and value <= 0.011:
                        pending_close = True
                    return accepted
                async def independent_close_report(entities):
                    nonlocal pending_close
                    if pending_close and opt.cfg.grid_export_limit in entities:
                        clock[0] += timedelta(milliseconds=1)
                        ha._record_state_value(opt.cfg.grid_export_limit, 0.01)
                        pending_close = False
                    return await original_bulk(entities)
                async def bounded_wait(*args, **kwargs):
                    kwargs["timeout_s"] = 0.01
                    return await original_wait(*args, **kwargs)
                ha.calls.clear()
                ha.set_number, ha.bulk_states = fail_discharge, independent_close_report
                opt._wait_for_exact_entity_state = bounded_wait
                with later_msc_report_clock(ha, state.timestamp) as clock:
                    result = asyncio.run(opt._apply(state, decision))
                    opt._finish_solar_reentry_application(state, decision, result)
                self.assertFalse(result.succeeded)
                self.assertTrue(result.fallback_attempted)
                self.assertEqual(deliver_msc, result.fallback_succeeded)
                charge_writes = [v for a, e, v in ha.calls
                                 if a == "set_number" and e == opt.cfg.ess_max_charging_limit]
                self.assertEqual([1.21, 5.0] if deliver_msc else [1.21], charge_writes)
                self.assertFalse(any(a == "set_number" and e == opt.cfg.grid_export_limit and v > 0.011
                                     for a, e, v in ha.calls))
                self.assertFalse(any(a == "set_number" and e == opt.cfg.grid_import_limit and v > 0.011
                                     for a, e, v in ha.calls))
                self.assertIsNone(opt._solar_relief.command_ts)
                self.assertIs(initial, opt._last_decision)
    def test_morning_partial_and_full_normal_completion_have_different_handoff_obligations(self):
        from test_morning_slow_partial_relief import MorningSlowPartialReliefTests
        for full_normal in (False, True):
            with self.subTest(full_normal=full_normal):
                morning = MorningSlowPartialReliefTests("runTest")
                morning.setUp()
                try:
                    opt, ha = morning._started_morning(14.8, solar_surplus_bypass_enabled=True, solar_surplus_fill_deadline_margin_minutes=0.0)
                    for second in (1, 2):
                        extra = ({"before_slow_end_pv_kw": 20.0, "after_slow_end_pv_kw": 0.5}
                                 if full_normal else {})
                        state, when = morning._flow_state(
                            opt, seconds=second, export_kw=14.8, charge_kw=2.0,
                            charge_readback=morning._charge_readback(opt, ha), **extra,
                        )
                        decision = morning.decide(opt, state, when)
                        result = self._apply(opt, ha, state, decision, report_charge=True)
                        self.assertTrue(result.automatic_application_completed)
                    self.assertEqual(full_normal, opt._solar_charge_reentry.required)
                    self.assertEqual(full_normal, decision.trace_gates["morning_slow_reentry_arm_candidate"])
                    self.assertGreater(decision.ess_charge_limit, 2.0)
                    if full_normal:
                        self.assertEqual(10.0, decision.ess_charge_limit)
                    else:
                        self.assertLess(decision.ess_charge_limit, 10.0)
                    # Transition through actual Solar dispatch after the Morning
                    # owner ends. Partial relief admits immediately; a completed
                    # full-normal owner preserves normal charging for 30 seconds.
                    for second in (0, 6, 30):
                        solar_state, solar = self._decide(
                            opt, second, readback=decision.ess_charge_limit,
                            ess_max_charge_kw=10.0, ess_charge_limit_entity_max_kw=10.0,
                        )
                        self.assertTrue(solar.solar_surplus_policy_active)
                        self.assertEqual(25.0, solar.export_limit)
                        if full_normal and second < 30:
                            self.assertEqual(10.0, solar.ess_charge_limit)
                            self.assertEqual("morning_handoff_qualifying", solar.trace_values[
                                "solar_charge_ceiling_reason"
                            ])
                        elif second == 0 or full_normal:
                            self.assertEqual(1.2 if second == 0 else 1.21, solar.ess_charge_limit)
                        self.assertTrue(self._apply(opt, ha, solar_state, solar).automatic_application_completed)
                    self.assertFalse(opt._solar_charge_reentry.required)
                finally:
                    morning.tearDown()