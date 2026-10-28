"""Characterize Solar fallback requests and cached status using fake HA only.

Synthetic forecasts and explicit later actuator reports exercise the real
decision/application/tick paths. These tests are not an exact trace replay or
evidence that an inverter obeyed a requested ESS charging ceiling.
"""
from __future__ import annotations

import asyncio
from datetime import timedelta
import unittest
from unittest.mock import AsyncMock, Mock, patch

from app.optimizer import MODE_MAX_SELF
from test_msc_baseline_overlay_contract import (
    ClockedRecordingHA, establish_observed_msc_baseline, later_msc_report_clock,
)


class SolarAllocationFallbackTests(unittest.TestCase):
    def setUp(self):
        # Composition avoids collecting the existing fixture's test methods.
        from test_phase1_solar_physical_relief_characterization import (
            SolarPhysicalReliefCharacterizationTests,
        )

        self.fixture = SolarPhysicalReliefCharacterizationTests(methodName="runTest")
        self.fixture.NORMAL_CHARGE_KW = 21.0
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)

    def test_fallback_restores_charge_only_after_later_msc_and_retains_old_status(self):
        async def run(fresh_msc, demand_blocked):
            fixture = self.fixture
            optimizer = fixture._optimizer()
            cfg = optimizer.cfg
            ha = ClockedRecordingHA()
            await establish_observed_msc_baseline(
                fixture, optimizer, ha, fixture.WHEN - timedelta(seconds=1),
            )
            previous_state, previous_decision = fixture._decision(
                optimizer, 0, demand_window_active=demand_blocked,
            )
            with later_msc_report_clock(ha, fixture.WHEN):
                initial_result = await optimizer._apply(previous_state, previous_decision)
            self.assertTrue(initial_result.succeeded, initial_result.error)
            self.assertEqual(1.6, previous_decision.ess_charge_limit)
            optimizer._last_state = previous_state
            optimizer._last_decision = previous_decision
            ha.calls.clear()

            state = fixture._flow_state(6, demand_window_active=demand_blocked)
            optimizer._read_state = AsyncMock(return_value=state)
            optimizer._publish_hvac_solar_permission = AsyncMock()
            optimizer._record_application_trace = Mock()

            original_set_number = ha.set_number
            original_bulk_states = ha.bulk_states
            original_apply = optimizer._apply
            original_decide = optimizer._decide
            failed_discharge = False
            pending_closure = False
            applied = []
            moment = None

            async def fail_first_discharge_write(entity, value):
                nonlocal failed_discharge, pending_closure
                if entity == cfg.ess_max_discharging_limit and value > 0.011 and not failed_discharge:
                    failed_discharge = True
                    ha.calls.append(("set_number", entity, value))
                    # Initial MSC application has already supplied its fresh
                    # report. Vary only the subsequent fallback's MSC report.
                    ha.settle_selects = fresh_msc
                    return False
                result = await original_set_number(entity, value)
                if failed_discharge and entity == cfg.grid_export_limit and value <= 0.011:
                    pending_closure = True
                return result

            async def report_later_export_closure(entity_ids):
                nonlocal pending_closure
                if pending_closure and cfg.grid_export_limit in entity_ids:
                    # Service acceptance does not provide the later report.
                    moment[0] += timedelta(milliseconds=1)
                    ha._record_state_value(cfg.grid_export_limit, 0.01)
                    pending_closure = False
                return await original_bulk_states(entity_ids)

            async def capture_application(snapshot, decision):
                result = await original_apply(snapshot, decision)
                applied.append((decision, result))
                return result

            def decide_at_local_snapshot_time(snapshot):
                # The shared actuator-report clock exposes UTC-naive now() for
                # older fixtures. Decisions use the fixture's local wall clock.
                with fixture.optimizer_time(snapshot.timestamp):
                    return original_decide(snapshot)

            ha.set_number = fail_first_discharge_write
            ha.bulk_states = report_later_export_closure
            # A cached exact MSC value is deliberately insufficient in the
            # negative case; production post-request provenance checks remain.
            optimizer._apply = capture_application
            optimizer._decide = decide_at_local_snapshot_time
            original_wait = optimizer._wait_for_exact_entity_state

            async def bounded_wait(*args, **kwargs):
                kwargs["timeout_s"] = 0.01
                return await original_wait(*args, **kwargs)

            optimizer._wait_for_exact_entity_state = bounded_wait
            with later_msc_report_clock(ha, state.timestamp) as moment, patch(
                "app.optimizer.monotonic", return_value=1006.0,
            ):
                with self.assertRaises(RuntimeError):
                    await optimizer._tick()

            self.assertTrue(failed_discharge, ([(d.ess_charge_limit, r.error) for d, r in applied], ha.calls))
            self.assertEqual(1, len(applied))
            attempted, result = applied[0]
            self.assertFalse(result.succeeded)
            self.assertTrue(result.fallback_attempted)
            self.assertEqual(fresh_msc, result.fallback_succeeded, result.error)
            self.assertEqual("solar_surplus", attempted.trace_values["ess_charge_limit_owner"])
            self.assertIn(("set_number", cfg.grid_export_limit, 0.01), ha.calls)
            self.assertIn(("select_option", cfg.ems_mode_select, MODE_MAX_SELF), ha.calls)
            charge_requests = [value for action, entity, value in ha.calls
                               if action == "set_number" and entity == cfg.ess_max_charging_limit]
            self.assertEqual([1.61, 21.0] if fresh_msc else [1.61], charge_requests)
            if fresh_msc:
                close_index = ha.calls.index(("set_number", cfg.grid_export_limit, 0.01))
                mode_index = ha.calls.index(("select_option", cfg.ems_mode_select, MODE_MAX_SELF))
                charge_index = ha.calls.index(("set_number", cfg.ess_max_charging_limit, 21.0))
                self.assertLess(close_index, charge_index)
                self.assertLess(mode_index, charge_index)
            if demand_blocked:
                self.assertIn(("set_number", cfg.grid_import_limit, 0.01), ha.calls)
                self.assertFalse(any(
                    action == "set_number" and entity == cfg.grid_import_limit and value > 0.011
                    for action, entity, value in ha.calls
                ))
            # Fallback never reopens export, even when house-serving recovery
            # succeeds. A failed requested decision cannot replace UI history.
            self.assertFalse(any(
                action == "set_number" and entity == cfg.grid_export_limit and value > 0.011
                for action, entity, value in ha.calls
            ))
            self.assertIs(previous_state, optimizer._last_state)
            self.assertIs(previous_decision, optimizer._last_decision)
            optimizer._record_application_trace.assert_called_once_with(state, attempted, result)
            self.assertIsNone(optimizer._solar_relief.command_ts)

        for fresh_msc in (True, False):
            for demand_blocked in (True, False):
                with self.subTest(fresh_msc=fresh_msc, demand_blocked=demand_blocked):
                    asyncio.run(run(fresh_msc, demand_blocked))
