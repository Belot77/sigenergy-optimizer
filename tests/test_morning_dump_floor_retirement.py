"""Configured-floor Dump retirement with fake HA; no physical timing claim."""
from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import timedelta
import importlib
import unittest
from unittest.mock import patch

from app.optimizer import (
    BATTERY_EXPORT, EXPORT_BLOCKED, MODE_CMD_DISCHARGE_PV, MODE_MAX_SELF,
    _ActuatorApplicationResult,
)

reentry = importlib.import_module("test_morning_dump_refill_reentry")


class MorningDumpFloorRetirementTests(unittest.TestCase):
    # Share the established simulated HA and clock without collecting its tests
    # a second time through unittest inheritance.
    setUp = reentry.MorningDumpRefillReentryTests.setUp
    scenario = reentry.MorningDumpRefillReentryTests.scenario
    configure_day = reentry.MorningDumpRefillReentryTests.configure_day
    decision = reentry.MorningDumpRefillReentryTests.decision
    applied_dump = reentry.MorningDumpRefillReentryTests.applied_dump

    async def soc_decision(self, opt, ha, clock, soc, *, trusted=True):
        value = str(soc)
        ha.plant[opt.cfg.battery_soc_sensor] = value
        ha._report(opt.cfg.battery_soc_sensor, value, clock.elapsed)
        state, decision = await self.decision(opt, ha, clock, at=clock.elapsed + 6)
        if not trusted:
            state.battery_soc_trusted = False
            with patch.object(opt, "_optimizer_import_topup_summary_today", return_value={}):
                decision = opt._decide(state)
        return state, decision

    async def begin_dump(self, clock, ha, opt):
        ha.plant[opt.cfg.battery_soc_sensor] = str(opt.cfg.morning_dump_min_soc + .1)
        return await self.applied_dump(clock, ha, opt)

    def assert_floor_retired(self, decision):
        self.assertFalse(decision.morning_dump_active)
        self.assertTrue(decision.trace_gates.get("morning_dump_floor_window_retired"))
        self.assertFalse(decision.trace_gates["morning_dump_refill_window_retired"])
        self.assertEqual(
            "floor_reached_retired_this_window",
            decision.trace_values.get("morning_dump_floor_retirement_reason"),
        )
        self.assertNotEqual(
            "refill_veto_retired_this_window",
            decision.trace_values["morning_dump_refill_retirement_reason"],
        )

    def test_completed_dump_floor_close_blocks_15_point_1_reentry(self):
        async def run():
            clock, ha, opt = self.scenario()
            with clock.active():
                await self.begin_dump(clock, ha, opt)
                state, floor = await self.soc_decision(opt, ha, clock, 15.0)
                self.assertTrue(floor.trace_gates["morning_dump_refill_timing_feasible"])
                self.assertFalse(floor.morning_dump_active)
                candidate = floor.trace_values.get("morning_dump_floor_retire_candidate")
                self.assertEqual(opt._morning_dump_applied_window, candidate)
                self.assertIsNotNone(candidate)
                self.assertFalse(floor.trace_gates.get("morning_dump_floor_window_retired"))
                result = await opt._apply(state, floor)
                self.assertTrue(result.transition_pending, result.error)
                self.assertFalse(result.automatic_application_completed)
                self.assert_floor_retired(floor)
                state, rebound = await self.soc_decision(opt, ha, clock, 15.1)
                self.assertTrue(rebound.trace_gates["morning_dump_refill_timing_feasible"])
                self.assert_floor_retired(rebound)
                self.assertEqual("none", rebound.trace_values["battery_export_final_owner"])
                self.assertEqual(MODE_MAX_SELF, rebound.ems_mode)
                # The independently scheduled observations arrive on later
                # reads. Keep executing the real close across its close/MSC
                # phases; retirement must survive until genuine completion.
                before = len(ha.requests)
                for _attempt in range(4):
                    result = await opt._apply(state, rebound)
                    self.assert_floor_retired(rebound)
                    self.assertFalse(result.fallback_attempted, result.error)
                    if result.automatic_application_completed:
                        break
                    self.assertTrue(result.transition_pending, result.error)
                    state, rebound = await self.soc_decision(opt, ha, clock, 15.1)
                    self.assert_floor_retired(rebound)
                self.assertTrue(result.succeeded, result.error)
                self.assertTrue(result.automatic_application_completed, result.error)
                self.assertIsNone(opt._msc_transition)
                self.assertFalse(any(
                    row[1] == "select_option" and row[3] == MODE_CMD_DISCHARGE_PV
                    for row in ha.requests[before:]
                ))
                self.assertFalse(any(
                    row[1] == "set_number" and row[2] == opt.cfg.grid_export_limit and row[3] > .011
                    for row in ha.requests[before:]
                ))
                _, settled_rebound = await self.soc_decision(opt, ha, clock, 15.1)
                self.assert_floor_retired(settled_rebound)
        asyncio.run(run())

    def test_configured_floor_instead_of_hardcoded_15_percent(self):
        async def run():
            clock, ha, opt = self.scenario()
            opt.cfg.morning_dump_min_soc = 22.0
            with clock.active():
                await self.begin_dump(clock, ha, opt)
                state, floor = await self.soc_decision(opt, ha, clock, 22.0)
                await opt._apply(state, floor)
                _, rebound = await self.soc_decision(opt, ha, clock, 22.1)
                self.assert_floor_retired(rebound)
        asyncio.run(run())

    def test_preview_floor_after_completed_dump_does_not_retire(self):
        async def run():
            clock, ha, opt = self.scenario()
            with clock.active():
                await self.begin_dump(clock, ha, opt)
                _, preview = await self.soc_decision(opt, ha, clock, 15.0)
                self.assertFalse(preview.morning_dump_active)
                self.assertIsNotNone(preview.trace_values.get("morning_dump_floor_retire_candidate"))
                _, rebound = await self.soc_decision(opt, ha, clock, 15.1)
                self.assertTrue(rebound.morning_dump_active)
                self.assertFalse(rebound.trace_gates.get("morning_dump_floor_window_retired"))
        asyncio.run(run())

    def test_no_completed_dump_means_floor_does_not_retire(self):
        async def run(kind):
            clock, ha, opt = self.scenario()
            with clock.active():
                state, initial = await self.soc_decision(opt, ha, clock, 15.1)
                if kind != "preview":
                    outcome = {
                        "failed": _ActuatorApplicationResult(succeeded=False),
                        "pending": _ActuatorApplicationResult(succeeded=False, transition_pending=True),
                        "noop": _ActuatorApplicationResult(succeeded=True),
                        "fallback": _ActuatorApplicationResult(
                            succeeded=True, automatic_application_completed=True,
                            fallback_attempted=True,
                        ),
                    }[kind]
                    async def incomplete(_state, _decision):
                        return outcome
                    with patch.object(opt, "_apply_with_msc_proof", side_effect=incomplete):
                        await opt._apply(state, initial)
                state, floor = await self.soc_decision(opt, ha, clock, 15.0)
                self.assertIsNone(floor.trace_values.get("morning_dump_floor_retire_candidate"))
                await opt._apply(state, floor)
                _, rebound = await self.soc_decision(opt, ha, clock, 15.1)
                self.assertTrue(rebound.morning_dump_active)
                self.assertFalse(rebound.trace_gates.get("morning_dump_floor_window_retired"))
        for kind in ("preview", "failed", "pending", "noop", "fallback"):
            with self.subTest(initial_application=kind):
                asyncio.run(run(kind))

    def test_untrusted_soc_cannot_create_floor_retirement(self):
        async def run():
            clock, ha, opt = self.scenario()
            with clock.active():
                await self.begin_dump(clock, ha, opt)
                state, untrusted = await self.soc_decision(opt, ha, clock, 15.0, trusted=False)
                self.assertFalse(untrusted.morning_dump_active)
                self.assertIsNone(untrusted.trace_values.get("morning_dump_floor_retire_candidate"))
                await opt._apply(state, untrusted)
                _, rebound = await self.soc_decision(opt, ha, clock, 15.1)
                self.assertTrue(rebound.morning_dump_active)
                self.assertFalse(rebound.trace_gates.get("morning_dump_floor_window_retired"))
        asyncio.run(run())

    def test_floor_application_without_current_automatic_authority_cannot_retire(self):
        async def run(kind):
            clock, ha, opt = self.scenario()
            with clock.active():
                await self.begin_dump(clock, ha, opt)
                state, floor = await self.soc_decision(opt, ha, clock, 15.0)
                self.assertIsNotNone(floor.trace_values.get("morning_dump_floor_retire_candidate"))
                if kind == "frozen_decision":
                    # Preserve the real automatic state's floor candidate, then
                    # use the production operator-freeze path before applying.
                    opt._freeze_decision_to_live_mode(state, floor, opt.cfg.manual_option)
                    self.assertFalse(floor.trace_gates["observed_automated_control_mode"])
                else:
                    if kind == "remote_off":
                        entity, value = opt.cfg.ha_control_switch, "off"
                    else:
                        entity = opt.cfg.sigenergy_mode_select
                        value = opt.cfg.manual_option if kind == "manual" else "Force Full Export"
                    ha.plant[entity] = value
                    ha._report(entity, value, clock.elapsed)
                    if kind == "manual_override":
                        opt._manual_mode_override = value
                    state = await opt._read_state()
                await opt._apply(state, floor)
                self.assertIsNone(opt._morning_dump_floor_retired_window_id)
                self.assertFalse(floor.trace_gates.get("morning_dump_floor_window_retired"))
                # A subsequent verified Automated selection can still qualify
                # this morning because the excluded application set no latch.
                opt._manual_mode_override = None
                for entity, value in (
                    (opt.cfg.sigenergy_mode_select, opt.cfg.automated_option),
                    (opt.cfg.ha_control_switch, "on"),
                ):
                    ha.plant[entity] = value
                    ha._report(entity, value, clock.elapsed)
                _, rebound = await self.soc_decision(opt, ha, clock, 15.1)
                self.assertTrue(rebound.morning_dump_active)
                self.assertFalse(rebound.trace_gates.get("morning_dump_floor_window_retired"))
        for kind in ("manual", "force", "remote_off", "manual_override", "frozen_decision"):
            with self.subTest(excluded_application=kind):
                asyncio.run(run(kind))

    def test_retirement_precedes_await_and_survives_incomplete_closure(self):
        async def run(kind):
            clock, ha, opt = self.scenario()
            with clock.active():
                await self.begin_dump(clock, ha, opt)
                state, floor = await self.soc_decision(opt, ha, clock, 15.0)
                async def close(_state, _decision):
                    # This callback is entered by the first awaited apply helper.
                    # A concurrent fresh decision must already reject re-entry.
                    _, concurrent = await self.soc_decision(opt, ha, clock, 15.1)
                    self.assert_floor_retired(concurrent)
                    if kind == "cancelled":
                        raise asyncio.CancelledError()
                    if kind == "exception":
                        raise RuntimeError("simulated restrictive application error")
                    return _ActuatorApplicationResult(
                        succeeded=False, transition_pending=kind == "pending",
                        fallback_attempted=kind == "failed", fallback_succeeded=False,
                    )
                with patch.object(opt, "_apply_with_msc_proof", side_effect=close):
                    if kind in ("cancelled", "exception"):
                        expected = asyncio.CancelledError if kind == "cancelled" else RuntimeError
                        with self.assertRaises(expected):
                            await opt._apply(state, floor)
                    else:
                        result = await opt._apply(state, floor)
                        self.assertFalse(result.succeeded)
                _, rebound = await self.soc_decision(opt, ha, clock, 15.1)
                self.assert_floor_retired(rebound)
        for kind in ("pending", "failed", "cancelled", "exception"):
            with self.subTest(closure=kind):
                asyncio.run(run(kind))

    def test_failed_real_floor_close_retains_retirement(self):
        async def run():
            clock, ha, opt = self.scenario()
            with clock.active():
                await self.begin_dump(clock, ha, opt)
                state, floor = await self.soc_decision(opt, ha, clock, 15.0)
                ha.write_hook = lambda entity, value: False if entity == opt.cfg.grid_export_limit and value <= .011 else None
                result = await opt._apply(state, floor)
                self.assertFalse(result.succeeded)
                self.assertTrue(result.fallback_attempted)
                _, rebound = await self.soc_decision(opt, ha, clock, 15.1)
                self.assert_floor_retired(rebound)
        asyncio.run(run())

    def test_stale_precomputed_dump_cannot_reopen_retired_floor_window(self):
        async def run():
            clock, ha, opt = self.scenario()
            with clock.active():
                await self.begin_dump(clock, ha, opt)
                stale_state, stale = await self.soc_decision(opt, ha, clock, 15.1)
                self.assertTrue(stale.morning_dump_active)
                state, floor = await self.soc_decision(opt, ha, clock, 15.0)
                await opt._apply(state, floor)
                before = len(ha.requests)
                await opt._apply(stale_state, stale)
                self.assert_floor_retired(stale)
                self.assertEqual(MODE_MAX_SELF, stale.ems_mode)
                self.assertFalse(any(
                    row[1] == "select_option" and row[3] == MODE_CMD_DISCHARGE_PV
                    for row in ha.requests[before:]
                ))
                self.assertFalse(any(
                    row[1] == "set_number" and row[2] == opt.cfg.grid_export_limit and row[3] > .011
                    for row in ha.requests[before:]
                ))
        asyncio.run(run())

    def test_expired_or_mismatched_floor_candidate_cannot_retire(self):
        async def run(kind):
            clock, ha, opt = self.scenario()
            with clock.active():
                await self.begin_dump(clock, ha, opt)
                state, floor = await self.soc_decision(opt, ha, clock, 15.0)
                candidate = floor.trace_values.get("morning_dump_floor_retire_candidate")
                self.assertIsNotNone(candidate)
                if kind == "expired":
                    clock.elapsed = candidate[2] - clock.BASE.timestamp() + 1
                else:
                    floor.trace_values["morning_dump_floor_retire_candidate"] = (
                        candidate[0], candidate[1], candidate[2] + 1,
                    )
                async def noop(_state, _decision):
                    return _ActuatorApplicationResult(succeeded=True)
                with patch.object(opt, "_apply_with_msc_proof", side_effect=noop):
                    await opt._apply(state, floor)
                self.assertIsNone(opt._morning_dump_floor_retired_window_id)
                self.assertFalse(floor.trace_gates.get("morning_dump_floor_window_retired"))
        for kind in ("expired", "mismatched"):
            with self.subTest(candidate=kind):
                asyncio.run(run(kind))

    def test_floor_helper_preserves_independent_battery_export_owner(self):
        async def run():
            clock, ha, opt = self.scenario()
            with clock.active():
                await self.begin_dump(clock, ha, opt)
                _, earlier = await self.soc_decision(opt, ha, clock, 15.1)
                await opt._apply(*await self.soc_decision(opt, ha, clock, 15.0))
                # Synthetic helper-boundary case only: an independent owner
                # retains historical Dump window context. This does not claim
                # Boost eligibility at this time or actuate that owner.
                independent = replace(
                    earlier, morning_dump_active=False,
                    evening_export_boost_active=True, export_intent=BATTERY_EXPORT,
                    export_limit=7.0, ems_mode=MODE_CMD_DISCHARGE_PV,
                    trace_gates=dict(earlier.trace_gates),
                    trace_values={
                        **earlier.trace_values,
                        "battery_export_owner": "evening_export_boost",
                        "battery_export_final_owner": "evening_export_boost",
                    },
                )
                expected = replace(
                    independent, trace_gates=dict(independent.trace_gates),
                    trace_values=dict(independent.trace_values),
                )
                before = len(ha.requests)
                opt._apply_morning_dump_retirement(independent)
                self.assertEqual(expected, independent)
                self.assertEqual(before, len(ha.requests))
        asyncio.run(run())

    def test_stale_dump_clamp_preserves_independent_restrictive_targets(self):
        async def run():
            clock, ha, opt = self.scenario()
            with clock.active():
                await self.begin_dump(clock, ha, opt)
                state, earlier = await self.soc_decision(opt, ha, clock, 15.1)
                await opt._apply(*await self.soc_decision(opt, ha, clock, 15.0))
                # Synthetic restrictive targets exercise only the retirement
                # helper's mutation boundary, without actuator or policy claims.
                stale = replace(
                    earlier, ess_charge_limit=0.0, ess_discharge_limit=0.0,
                    import_limit=0.0, pv_max_power_limit=2.0,
                    trace_gates=dict(earlier.trace_gates),
                    trace_values=dict(earlier.trace_values),
                )
                self.assertTrue(stale.morning_dump_active)
                before = len(ha.requests)
                opt._apply_morning_dump_retirement(stale, state)
                self.assert_floor_retired(stale)
                self.assertEqual(EXPORT_BLOCKED, stale.export_intent)
                self.assertEqual(0.0, stale.export_limit)
                self.assertEqual(MODE_MAX_SELF, stale.ems_mode)
                self.assertFalse(stale.requires_verified_msc_before_export)
                self.assertEqual(0.0, stale.ess_charge_limit)
                self.assertEqual(0.0, stale.ess_discharge_limit)
                self.assertEqual(0.0, stale.import_limit)
                self.assertEqual(2.0, stale.pv_max_power_limit)
                self.assertEqual(before, len(ha.requests))
        asyncio.run(run())

    def test_sunrise_jitter_does_not_clear_floor_latch_and_next_window_qualifies(self):
        async def run():
            clock, ha, opt = self.scenario()
            with clock.active():
                await self.begin_dump(clock, ha, opt)
                await opt._apply(*await self.soc_decision(opt, ha, clock, 15.0))
                ha.states[opt.cfg.sun_entity]["attributes"]["next_rising"] = (
                    clock.BASE.replace(hour=7) + timedelta(seconds=1)
                ).isoformat()
                _, same = await self.soc_decision(opt, ha, clock, 15.1)
                self.assert_floor_retired(same)
                self.configure_day(opt, ha, clock.BASE + timedelta(days=1))
                ha.next_fast = ha.next_telemetry = ha.next_ems = 86400
                _, tomorrow = await self.decision(opt, ha, clock, at=86400)
                self.assertTrue(tomorrow.morning_dump_active)
                self.assertFalse(tomorrow.trace_gates.get("morning_dump_floor_window_retired"))
        asyncio.run(run())

    def test_restart_forgets_floor_latch_but_current_gates_still_apply(self):
        async def run():
            clock, ha, opt = self.scenario()
            with clock.active():
                await self.begin_dump(clock, ha, opt)
                await opt._apply(*await self.soc_decision(opt, ha, clock, 15.0))
                _, rebound = await self.soc_decision(opt, ha, clock, 15.1)
                self.assert_floor_retired(rebound)
            clock, ha, fresh = self.scenario()
            with clock.active():
                _, eligible = await self.soc_decision(fresh, ha, clock, 15.1)
                self.assertTrue(eligible.morning_dump_active)
                _, untrusted = await self.soc_decision(fresh, ha, clock, 15.1, trusted=False)
                self.assertFalse(untrusted.morning_dump_active)
                _, at_floor = await self.soc_decision(fresh, ha, clock, 15.0)
                self.assertFalse(at_floor.morning_dump_active)
        asyncio.run(run())

    def test_floor_retirement_preserves_frozen_manual_and_force_targets(self):
        async def run(export_limit):
            clock, ha, opt = self.scenario()
            with clock.active():
                await self.begin_dump(clock, ha, opt)
                _, earlier = await self.soc_decision(opt, ha, clock, 15.1)
                await opt._apply(*await self.soc_decision(opt, ha, clock, 15.0))
                frozen = replace(
                    earlier, morning_dump_active=False, export_intent=EXPORT_BLOCKED,
                    export_limit=export_limit, ems_mode=MODE_CMD_DISCHARGE_PV,
                    ess_charge_limit=3.0, ess_discharge_limit=4.0,
                )
                opt._apply_morning_dump_retirement(frozen)
                self.assertEqual(export_limit, frozen.export_limit)
                self.assertEqual(MODE_CMD_DISCHARGE_PV, frozen.ems_mode)
                self.assertEqual(3.0, frozen.ess_charge_limit)
                self.assertEqual(4.0, frozen.ess_discharge_limit)
                _, rebound = await self.soc_decision(opt, ha, clock, 15.1)
                self.assert_floor_retired(rebound)
        for export_limit in (7.0, 25.0):
            with self.subTest(operator_target=export_limit):
                asyncio.run(run(export_limit))
