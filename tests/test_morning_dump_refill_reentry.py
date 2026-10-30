"""Process-local Dump retirement; fake HA reports, no physical timing claim."""
from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import importlib
import unittest
from unittest.mock import patch

from app.optimizer import BATTERY_EXPORT, EXPORT_BLOCKED, MODE_CMD_DISCHARGE_PV, MODE_MAX_SELF, _ActuatorApplicationResult

fixture_module = importlib.import_module("test_msc_settled_epoch_reuse")


class MorningDumpRefillReentryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture_module.Haos49CharacterizationCase("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)

    def scenario(self):
        clock = fixture_module.ReportClock()
        clock.BASE = datetime(2026, 1, 15, 6, 0, tzinfo=timezone.utc)
        ha = fixture_module.PeriodicReportHA(clock)
        opt = self.fixture.optimizer(
            ha, morning_dump_enabled=True, morning_dump_min_soc=15.0,
            ess_max_charging_limit="number.test_charge",
            ess_max_discharging_limit="number.test_discharge",
        )
        opt._tz = timezone.utc
        ha.configure(opt.cfg)
        self.configure_day(opt, ha, clock.BASE)
        return clock, ha, opt

    def configure_day(self, opt, ha, start):
        cfg = opt.cfg
        for entity, value in ((cfg.rated_capacity_sensor, "40.3"),
                              (cfg.battery_soc_sensor, "50"),
                              (cfg.available_discharge_sensor, "13.44"),
                              (cfg.consumed_power_sensor, "0.5"),
                              (cfg.pv_power_sensor, "0"),
                              (cfg.battery_power_sensor, "-0.5"),
                              (cfg.grid_import_power_sensor, "0"),
                              (cfg.grid_export_power_sensor, "0"),
                              (cfg.feedin_sensor, "0.05"),
                              (cfg.sun_entity, "below_horizon")):
            ha.plant[entity] = value
        ha.states[cfg.sun_entity]["attributes"] = {
            "next_rising": start.replace(hour=7).isoformat(),
            "next_setting": start.replace(hour=18).isoformat(),
        }
        ha.states[cfg.forecast_today_sensor]["attributes"] = {
            "detailedForecast": [
                {"period_start": (start + timedelta(minutes=30 * i)).isoformat(),
                 "pv_estimate": 5.5}
                for i in range(25)
            ]
        }

    async def decision(self, opt, ha, clock, *, need=None, at=None, sun_trusted=True):
        if at is not None:
            self.assertGreaterEqual(at, clock.elapsed)
            clock.elapsed = at
        if need is not None:
            value = str(40.3 - need)
            ha.plant[opt.cfg.available_discharge_sensor] = value
            ha._report(opt.cfg.available_discharge_sensor, value, clock.elapsed)
        state = await opt._read_state()
        if not sun_trusted:
            state.sun_state_observation_trusted = False
            state.sunrise_observation_trusted = False
            state.sunset_observation_trusted = False
        with patch.object(opt, "_optimizer_import_topup_summary_today", return_value={}):
            decision = opt._decide(state)
        return state, decision

    async def applied_dump(self, clock, ha, opt):
        state, decision = await self.decision(opt, ha, clock)
        self.assertTrue(decision.morning_dump_active)
        self.assertEqual("morning_dump", decision.trace_values["battery_export_final_owner"])
        self.assertEqual(BATTERY_EXPORT, decision.export_intent)
        self.assertEqual(MODE_CMD_DISCHARGE_PV, decision.ems_mode)
        result = await opt._apply(state, decision)
        self.assertTrue(result.automatic_application_completed, result.error)
        self.assertFalse(result.fallback_attempted)
        return decision.trace_values["morning_dump_safe_timed_charge_opportunity_kwh"]

    async def retire(self, clock, ha, opt, budget, *, sun_trusted=True):
        state, veto = await self.decision(
            opt, ha, clock, need=budget + .01, at=clock.elapsed + 6,
            sun_trusted=sun_trusted,
        )
        self.assertFalse(veto.morning_dump_active)
        result = await opt._apply(state, veto)
        return veto, result

    def test_applied_dump_refill_veto_stops_same_window_despite_energy_rebound(self):
        async def run():
            clock, ha, opt = self.scenario()
            with clock.active():
                budget = await self.applied_dump(clock, ha, opt)
                await self.retire(clock, ha, opt, budget)
                _, rebound = await self.decision(opt, ha, clock, need=budget - .1, at=clock.elapsed + 6)
                self.assertTrue(rebound.trace_gates["morning_dump_refill_timing_feasible"])
                self.assertFalse(rebound.morning_dump_active)
                self.assertEqual("none", rebound.trace_values["battery_export_final_owner"])
                self.assertEqual(MODE_MAX_SELF, rebound.ems_mode)
                self.assertTrue(rebound.trace_gates["morning_dump_refill_window_retired"])
        asyncio.run(run())

    def test_decisions_and_hypothetical_veto_do_not_arm_or_retire_an_episode(self):
        async def run():
            clock, ha, opt = self.scenario()
            with clock.active():
                _, first = await self.decision(opt, ha, clock)
                budget = first.trace_values["morning_dump_safe_timed_charge_opportunity_kwh"]
                await self.decision(opt, ha, clock, need=budget + .01, at=6)
                _, rebound = await self.decision(opt, ha, clock, need=budget - .1, at=12)
                self.assertTrue(rebound.morning_dump_active)
                await opt._apply(*await self.decision(opt, ha, clock, need=budget - .1, at=18))
                await self.decision(opt, ha, clock, need=budget + .01, at=24)
                _, preview_rebound = await self.decision(opt, ha, clock, need=budget - .1, at=30)
                self.assertTrue(preview_rebound.morning_dump_active)
        asyncio.run(run())

    def test_only_complete_automatic_dump_can_arm_retirement(self):
        async def run(kind):
            clock, ha, opt = self.scenario()
            with clock.active():
                state, decision = await self.decision(opt, ha, clock)
                result = {
                    "failed": _ActuatorApplicationResult(succeeded=False),
                    "pending": _ActuatorApplicationResult(succeeded=False, transition_pending=True),
                    "noop": _ActuatorApplicationResult(succeeded=True),
                    "fallback": _ActuatorApplicationResult(succeeded=True, automatic_application_completed=True, fallback_attempted=True),
                }[kind]
                async def fake_apply(_state, _decision):
                    return result
                with patch.object(opt, "_apply_with_msc_proof", side_effect=fake_apply):
                    await opt._apply(state, decision)
                budget = decision.trace_values["morning_dump_safe_timed_charge_opportunity_kwh"]
                await self.retire(clock, ha, opt, budget)
                _, rebound = await self.decision(opt, ha, clock, need=budget - .1, at=clock.elapsed + 6)
                self.assertTrue(rebound.morning_dump_active)
        for kind in ("failed", "pending", "noop", "fallback"):
            with self.subTest(result=kind):
                asyncio.run(run(kind))

    def test_sun_metadata_loss_cannot_hide_veto_or_clear_retirement(self):
        async def run():
            clock, ha, opt = self.scenario()
            with clock.active():
                budget = await self.applied_dump(clock, ha, opt)
                state, veto = await self.decision(
                    opt, ha, clock, need=budget - .1, at=clock.elapsed + 6,
                    sun_trusted=False,
                )
                self.assertFalse(veto.trace_gates["morning_dump_refill_timing_evidence_trusted"])
                await opt._apply(state, veto)
                _, rebound = await self.decision(opt, ha, clock, need=budget - .1, at=clock.elapsed + 6)
                self.assertTrue(rebound.trace_gates["morning_dump_refill_timing_evidence_trusted"])
                self.assertFalse(rebound.morning_dump_active)
        asyncio.run(run())

    def test_next_morning_qualifies_but_sunrise_jitter_does_not_clear_same_window(self):
        async def run():
            clock, ha, opt = self.scenario()
            with clock.active():
                budget = await self.applied_dump(clock, ha, opt)
                await self.retire(clock, ha, opt, budget)
                sunrise = clock.BASE.replace(hour=7) + timedelta(seconds=1)
                ha.states[opt.cfg.sun_entity]["attributes"]["next_rising"] = sunrise.isoformat()
                _, same = await self.decision(opt, ha, clock, need=budget - .1, at=clock.elapsed + 6)
                self.assertFalse(same.morning_dump_active)
                next_start = clock.BASE + timedelta(days=1)
                self.configure_day(opt, ha, next_start)
                # Skip unseen overnight reports; emit fresh reports at the next
                # window instead of simulating 864,000 irrelevant numeric polls.
                ha.next_fast = ha.next_telemetry = ha.next_ems = 86400
                _, tomorrow = await self.decision(opt, ha, clock, need=budget - .1, at=86400)
                self.assertTrue(tomorrow.morning_dump_active)
        asyncio.run(run())

    def test_failed_close_still_retires_after_real_refill_veto(self):
        async def run():
            clock, ha, opt = self.scenario()
            with clock.active():
                budget = await self.applied_dump(clock, ha, opt)
                ha.write_hook = lambda entity, value: False if entity == opt.cfg.grid_export_limit and value <= .011 else None
                _, result = await self.retire(clock, ha, opt, budget)
                self.assertFalse(result.succeeded)
                self.assertTrue(result.fallback_attempted)
                self.assertFalse(result.fallback_succeeded)
                _, rebound = await self.decision(opt, ha, clock, need=budget - .1, at=clock.elapsed + 6)
                self.assertFalse(rebound.morning_dump_active)
        asyncio.run(run())

    def test_stale_permissive_dump_cannot_reopen_after_retirement(self):
        async def run():
            clock, ha, opt = self.scenario()
            with clock.active():
                budget = await self.applied_dump(clock, ha, opt)
                state, stale = await self.decision(opt, ha, clock, need=budget - .1, at=clock.elapsed + 6)
                self.assertTrue(stale.morning_dump_active)
                await self.retire(clock, ha, opt, budget)
                before = len(ha.requests)
                await opt._apply(state, stale)
                self.assertFalse(stale.morning_dump_active)
                self.assertEqual(MODE_MAX_SELF, stale.ems_mode)
                self.assertFalse(any(r[1] == "select_option" and r[3] == MODE_CMD_DISCHARGE_PV for r in ha.requests[before:]))
                self.assertFalse(any(r[1] == "set_number" and r[2] == opt.cfg.grid_export_limit and r[3] > .011 for r in ha.requests[before:]))
        asyncio.run(run())

    def test_cancellation_during_restrictive_apply_does_not_clear_retirement(self):
        async def run():
            clock, ha, opt = self.scenario()
            with clock.active():
                budget = await self.applied_dump(clock, ha, opt)
                state, veto = await self.decision(opt, ha, clock, need=budget + .01, at=clock.elapsed + 6)
                async def cancelled(_state, _decision):
                    raise asyncio.CancelledError()
                with patch.object(opt, "_apply_with_msc_proof", side_effect=cancelled):
                    with self.assertRaises(asyncio.CancelledError):
                        await opt._apply(state, veto)
                _, rebound = await self.decision(opt, ha, clock, need=budget - .1, at=clock.elapsed + 6)
                self.assertFalse(rebound.morning_dump_active)
        asyncio.run(run())

    def test_refill_input_trust_loss_retires_but_soc_floor_alone_does_not(self):
        async def run(field):
            clock, ha, opt = self.scenario()
            with clock.active():
                budget = await self.applied_dump(clock, ha, opt)
                state, veto = await self.decision(opt, ha, clock, need=budget - .1, at=clock.elapsed + 6)
                if field == "soc_floor":
                    state.battery_soc = 15.0
                else:
                    setattr(state, field, False)
                with patch.object(opt, "_optimizer_import_topup_summary_today", return_value={}):
                    veto = opt._decide(state)
                self.assertFalse(veto.morning_dump_active)
                await opt._apply(state, veto)
                _, rebound = await self.decision(opt, ha, clock, need=budget - .1, at=clock.elapsed + 6)
                self.assertEqual(field == "soc_floor", rebound.morning_dump_active)
        for field in ("battery_capacity_trusted", "available_discharge_energy_trusted", "soc_floor"):
            with self.subTest(field=field):
                asyncio.run(run(field))

    def test_restart_loses_process_latch_but_still_requires_current_eligibility(self):
        async def run():
            clock, ha, opt = self.scenario()
            with clock.active():
                budget = await self.applied_dump(clock, ha, opt)
                await self.retire(clock, ha, opt, budget)
            new_clock, new_ha, fresh = self.scenario()
            with new_clock.active():
                _, eligible = await self.decision(fresh, new_ha, new_clock, need=budget - .1)
                self.assertTrue(eligible.morning_dump_active)
                _, untrusted = await self.decision(fresh, new_ha, new_clock, need=budget - .1, sun_trusted=False)
                self.assertFalse(untrusted.morning_dump_active)
        asyncio.run(run())

    def test_retirement_does_not_rewrite_frozen_operator_targets(self):
        async def run():
            clock, ha, opt = self.scenario()
            with clock.active():
                budget = await self.applied_dump(clock, ha, opt)
                _, earlier = await self.decision(opt, ha, clock, need=budget - .1, at=clock.elapsed + 6)
                await self.retire(clock, ha, opt, budget)
                # Operator-mode freezing retains historical trace context while
                # replacing automatic intent and displaying current user targets.
                frozen = replace(earlier, morning_dump_active=False,
                                 export_intent=EXPORT_BLOCKED, export_limit=7.0,
                                 ems_mode=MODE_CMD_DISCHARGE_PV)
                opt._apply_morning_dump_retirement(frozen)
                self.assertEqual(7.0, frozen.export_limit)
                self.assertEqual(MODE_CMD_DISCHARGE_PV, frozen.ems_mode)
        asyncio.run(run())

    def test_retired_trace_stays_true_while_sun_metadata_remains_unavailable(self):
        async def run():
            clock, ha, opt = self.scenario()
            with clock.active():
                budget = await self.applied_dump(clock, ha, opt)
                state, veto = await self.decision(opt, ha, clock, need=budget - .1, at=clock.elapsed + 6, sun_trusted=False)
                await opt._apply(state, veto)
                _, still_untrusted = await self.decision(opt, ha, clock, need=budget - .1, at=clock.elapsed + 6, sun_trusted=False)
                self.assertFalse(still_untrusted.morning_dump_active)
                self.assertTrue(still_untrusted.trace_gates["morning_dump_refill_window_retired"])
                self.assertEqual("refill_veto_retired_this_window", still_untrusted.trace_values["morning_dump_refill_retirement_reason"])
        asyncio.run(run())

    def test_expired_or_mismatched_retirement_candidate_cannot_set_latch(self):
        async def run(kind):
            clock, ha, opt = self.scenario()
            with clock.active():
                budget = await self.applied_dump(clock, ha, opt)
                _, veto = await self.decision(opt, ha, clock, need=budget + .01, at=clock.elapsed + 6)
                candidate = veto.trace_values["morning_dump_refill_retire_candidate"]
                self.assertIsNotNone(candidate)
                if kind == "expired":
                    clock.elapsed = candidate[2] - clock.BASE.timestamp() + 1
                else:
                    veto.trace_values["morning_dump_refill_retire_candidate"] = (candidate[0], candidate[1], candidate[2] + 1)
                opt._apply_morning_dump_retirement(veto)
                self.assertIsNone(opt._morning_dump_retired_window_id)
                self.assertFalse(veto.trace_gates["morning_dump_refill_window_retired"])
        for kind in ("expired", "mismatched"):
            with self.subTest(candidate=kind):
                asyncio.run(run(kind))
