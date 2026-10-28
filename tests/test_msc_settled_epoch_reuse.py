"""Offline pending-MSC reuse regressions with independently scheduled reports.

Real read/apply/authority/settlement paths run against fake HA and temporary
storage. Simulated polling time proves ordering, not hardware response timing.
"""
from __future__ import annotations

import asyncio
import unittest
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.models import Decision, MSC_SURPLUS_CEILING
from app.optimizer import DISCHARGE_MODES, MODE_CMD_DISCHARGE_PV, MODE_MAX_SELF
from haos49_characterization_helpers import Haos49CharacterizationCase, RecordingHA


class ReportClock:
    """One simulated wall/loop clock; preserve production polling durations."""

    BASE = datetime(2026, 10, 28, 0, 0, tzinfo=timezone.utc)

    def __init__(self):
        self.elapsed = 0.0
        self.real_sleep = asyncio.sleep

    def at(self, elapsed):
        return self.BASE + timedelta(seconds=elapsed)

    def time(self):
        return self.elapsed

    async def sleep(self, seconds):
        self.elapsed = round(self.elapsed + seconds, 6)
        await self.real_sleep(0)

    @contextmanager
    def active(self):
        clock = self

        class SimulatedDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime.fromtimestamp(clock.at(clock.elapsed).timestamp(), tz)

        loop = asyncio.get_running_loop()
        with (
            patch("app.optimizer.datetime", SimulatedDateTime),
            patch("app.optimizer.monotonic", self.time),
            patch.object(loop, "time", self.time),
            patch("app.optimizer.asyncio.sleep", self.sleep),
        ):
            yield


class PeriodicReportHA(RecordingHA):
    """Accepted commands and periodic HA observations are separate events.

    The simulated EMS is already MSC. Same-value commands do not themselves
    create a report. A periodic report can advance last_reported without
    changing last_updated. No physical inverter or power-flow model is implied.
    """

    def __init__(self, clock, *, first_ems=1.2, ems_period=1.0):
        super().__init__(settle_numbers=False, settle_selects=False)
        self.clock = clock
        self.next_ems = first_ems
        self.ems_period = ems_period
        self.next_fast = 0.1
        self.next_telemetry = 0.0
        self.metadata_policy = "valid"
        self.metadata_hook = None
        self.write_hook = None
        self.helper_hook = None
        self.requests = []
        self.reports = []
        self.delayed_reports = []
        self.cfg = None
        self.plant = {}
        self.telemetry = set()
        self.numeric = set()

    def configure(self, cfg):
        self.cfg = cfg
        values = (
            (cfg.sigenergy_mode_select, cfg.automated_option, {}),
            (cfg.ha_control_switch, "on", {}),
            (cfg.ems_mode_select, MODE_MAX_SELF, {}),
            (cfg.grid_export_limit, "0.01", {"max": 25}),
            (cfg.grid_import_limit, "0.01", {"max": 25}),
            (cfg.pv_max_power_limit, "25", {"max": 25}),
            (cfg.ess_max_charging_limit, "25", {"max": 25}),
            (cfg.ess_max_discharging_limit, "25", {"max": 25}),
            (cfg.ess_rated_charge_power_sensor, "25", {"unit_of_measurement": "kW"}),
            (cfg.ess_rated_discharge_power_sensor, "25", {"unit_of_measurement": "kW"}),
            (cfg.battery_soc_sensor, "60", {"unit_of_measurement": "%"}),
            (cfg.rated_capacity_sensor, "30", {"unit_of_measurement": "kWh"}),
            (cfg.available_discharge_sensor, "18", {"unit_of_measurement": "kWh"}),
            (cfg.consumed_power_sensor, "1", {"unit_of_measurement": "kW"}),
            (cfg.pv_power_sensor, "18", {"unit_of_measurement": "kW"}),
            (cfg.battery_power_sensor, "17", {"unit_of_measurement": "kW"}),
            (cfg.grid_import_power_sensor, "0", {"unit_of_measurement": "kW"}),
            (cfg.grid_export_power_sensor, "0", {"unit_of_measurement": "kW"}),
            (cfg.demand_window_sensor, "off", {}),
            (cfg.price_sensor, "0.30", {}), (cfg.feedin_sensor, "0.15", {}),
            (cfg.forecast_remaining_sensor, "100", {}),
            (cfg.forecast_today_sensor, "100", {}),
            (cfg.forecast_tomorrow_sensor, "100", {}),
            (cfg.solar_power_now_sensor, "18", {}),
            (cfg.sun_entity, "above_horizon", {
                "next_rising": (self.clock.BASE + timedelta(days=1)).isoformat(),
                "next_setting": (self.clock.BASE + timedelta(hours=8)).isoformat(),
            }),
        )
        for entity, value, attributes in values:
            if not entity:
                continue
            self.plant[entity] = value
            self.states[entity] = {"attributes": attributes}
            self._report(entity, value, -1.0)
        self.numeric = {e for e in (cfg.grid_export_limit, cfg.grid_import_limit,
                        cfg.pv_max_power_limit, cfg.ess_max_charging_limit,
                        cfg.ess_max_discharging_limit) if e}
        self.telemetry = set(self.plant) - self.numeric - {cfg.ems_mode_select}
        self.reports.clear()

    def _report(self, entity, value, reported_at):
        old = self._state_value_metadata.get(entity)
        updated = (old["last_updated"] if old and self.state_values.get(entity) == value
                   else self.clock.at(reported_at).isoformat())
        self.state_values[entity] = value
        self._state_value_metadata[entity] = {
            "last_updated": updated, "last_reported": self.clock.at(reported_at).isoformat(),
        }
        self.reports.append((reported_at, entity, value))

    def deliver(self):
        now = self.clock.elapsed
        while self.next_fast <= now + 1e-7:
            for entity in self.numeric:
                self._report(entity, self.plant[entity], self.next_fast)
            self.next_fast = round(self.next_fast + 0.1, 6)
        while self.next_telemetry <= now + 1e-7:
            for entity in self.telemetry:
                self._report(entity, self.plant[entity], self.next_telemetry)
            self.next_telemetry = round(self.next_telemetry + 1.0, 6)
        while self.next_ems is not None and self.next_ems <= now + 1e-7:
            self._report(self.cfg.ems_mode_select, self.plant[self.cfg.ems_mode_select], self.next_ems)
            self.next_ems = round(self.next_ems + self.ems_period, 6)
        ready = [event for event in self.delayed_reports if event[0] <= now + 1e-7]
        for event in ready:
            self.delayed_reports.remove(event)
            _arrival, reported_at, entity, value = event
            self.plant[entity] = value
            self._report(entity, value, reported_at)

    async def bulk_states(self, entity_ids):
        self.deliver()
        rows = await super().bulk_states(entity_ids)
        for entity in rows:
            rows[entity]["attributes"] = self.states.get(entity, {}).get("attributes", {})
        if self.cfg.ems_mode_select in rows:
            row = rows[self.cfg.ems_mode_select]
            row["last_reported"] = row["last_updated"]
        return rows

    async def get_state_report_metadata(self, entity_ids):
        self.deliver()
        if self.metadata_hook is not None:
            self.metadata_hook(set(entity_ids))
        rows = {entity: {"entity_id": entity, "state": self.state_values[entity],
                        **self._state_value_metadata[entity]}
                for entity in entity_ids if entity in self.state_values}
        entity = self.cfg.ems_mode_select
        if entity in rows and self.metadata_policy == "missing":
            del rows[entity]
        elif entity in rows and self.metadata_policy == "conflict":
            rows[entity]["state"] = MODE_CMD_DISCHARGE_PV
        return rows

    async def get_state_value(self, entity_id, default=""):
        self.deliver()
        return await super().get_state_value(entity_id, default)

    async def select_option(self, entity_id, value):
        self.calls.append(("select_option", entity_id, value))
        self.requests.append((self.clock.elapsed, "select_option", entity_id, value))
        self.plant[entity_id] = value
        return True

    async def set_number(self, entity_id, value):
        self.calls.append(("set_number", entity_id, value))
        self.requests.append((self.clock.elapsed, "set_number", entity_id, value))
        self.plant[entity_id] = str(value)
        if self.write_hook is not None:
            result = self.write_hook(entity_id, value)
            if result is not None:
                return result
        return True

    async def set_input_number(self, entity_id, value):
        result = await super().set_input_number(entity_id, value)
        if self.helper_hook is not None:
            self.helper_hook()
        return result


class MscSettledEpochReuseTests(unittest.TestCase):
    def setUp(self):
        self.fixture = Haos49CharacterizationCase("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)

    def scenario(self, **kwargs):
        clock = ReportClock()
        ha = PeriodicReportHA(clock, **kwargs)
        optimizer = self.fixture.optimizer(
            ha, ess_max_charging_limit="number.test_charge",
            ess_max_discharging_limit="number.test_discharge",
        )
        ha.configure(optimizer.cfg)
        return clock, ha, optimizer

    async def cycle(self, optimizer, ha, clock, *, at=None, metadata_policy=None, before_apply=None):
        if at is not None:
            self.assertGreaterEqual(at, clock.elapsed)
            clock.elapsed = at
        state = await optimizer._read_state()
        self.assertTrue(state.sigenergy_mode_observed)
        self.assertTrue(state.ha_control_enabled)
        if metadata_policy is not None:
            ha.metadata_policy = metadata_policy
        decision = Decision(
            ems_mode=MODE_MAX_SELF, export_limit=25.0,
            export_intent=MSC_SURPLUS_CEILING, requires_verified_msc_before_export=True,
            import_limit=0.0, ess_charge_limit=25.0, ess_discharge_limit=25.0,
            pv_max_power_limit=25.0,
        )
        if before_apply is not None:
            before_apply(state, decision)
        result = await optimizer._apply(state, decision)
        return state, decision, result

    def assert_no_permissive_export(self, ha):
        self.assertFalse(any(method == "set_number" and entity == ha.cfg.grid_export_limit
                             and value > 0.011 for _at, method, entity, value in ha.requests))
        self.assertFalse(any(method == "select_option" and value in DISCHARGE_MODES
                             for _at, method, _entity, value in ha.requests))

    async def qualified_epoch(self, optimizer, ha, clock):
        _state, _decision, first = await self.cycle(optimizer, ha, clock)
        self.assertFalse(first.succeeded)
        self.assertTrue(first.fallback_succeeded, first.error)
        self.assertEqual(4.5, clock.elapsed)
        _state, _decision, pending = await self.cycle(optimizer, ha, clock, at=5.0)
        self.assertTrue(pending.transition_pending)
        epoch = optimizer._msc_transition
        self.assertEqual(clock.at(3.0).timestamp(), epoch.close_requested_at)
        self.assertEqual(clock.at(5.0).timestamp(), epoch.msc_requested_at)
        clock.elapsed = 9.6
        ha.deliver()
        ha.next_ems = None
        return epoch

    def test_proven_pending_epoch_reopens_without_replacing_original_request(self):
        async def run():
            clock, ha, optimizer = self.scenario(first_ems=4.5, ems_period=5.0)
            with clock.active():
                epoch = await self.qualified_epoch(optimizer, ha, clock)
                boundaries = epoch.close_requested_at, epoch.msc_requested_at
                _state, _decision, result = await self.cycle(optimizer, ha, clock)
                self.assertTrue(result.succeeded, result.error)
                self.assertTrue(result.automatic_application_completed)
                self.assertFalse(result.fallback_attempted)
                self.assertEqual(9.6, clock.elapsed)
                self.assertEqual([0.0, 3.0, 5.0],
                                 [r[0] for r in ha.requests if r[1] == "select_option"])
                self.assertEqual(boundaries, (epoch.close_requested_at, epoch.msc_requested_at))
                self.assertEqual("25.0", ha.plant[ha.cfg.grid_export_limit])
                self.assertTrue(optimizer._msc_baseline_established)
                self.assertIsNone(optimizer._msc_transition)
                # The separately approved maintenance path may now reuse the
                # original requests after later matching export readback.
                before = len(ha.requests)
                _state, _decision, maintenance = await self.cycle(optimizer, ha, clock, at=10.0)
                self.assertTrue(maintenance.succeeded, maintenance.error)
                self.assertFalse(any(r[1] == "select_option" for r in ha.requests[before:]))
        asyncio.run(run())

    def test_already_closed_startup_epoch_preserves_absent_close_boundary(self):
        async def run():
            clock, ha, optimizer = self.scenario()
            ha._report(ha.cfg.ems_mode_select, MODE_CMD_DISCHARGE_PV, -1.0)
            ha.plant[ha.cfg.ems_mode_select] = MODE_CMD_DISCHARGE_PV
            with clock.active():
                _state, _decision, pending = await self.cycle(optimizer, ha, clock)
                self.assertTrue(pending.transition_pending)
                epoch = optimizer._msc_transition
                self.assertIsNone(epoch.close_requested_at)
                self.assertEqual(clock.BASE.timestamp(), epoch.msc_requested_at)
                clock.elapsed = 1.3
                ha.deliver()
                ha.next_ems = None
                before = len(ha.requests)
                _state, _decision, result = await self.cycle(optimizer, ha, clock)
                self.assertTrue(result.succeeded, result.error)
                self.assertIsNone(epoch.close_requested_at)
                self.assertEqual(clock.BASE.timestamp(), epoch.msc_requested_at)
                self.assertFalse(any(r[1] == "select_option" for r in ha.requests[before:]))
                self.assertIsNone(optimizer._msc_transition)
        asyncio.run(run())

    def test_joint_dispatch_read_rejects_changed_epoch_or_regressed_report(self):
        cases = ("replacement", "msc_boundary", "close_boundary", "phase",
                 "msc_pre_request", "msc_equal_request", "export_pre_close", "export_open",
                 "missing", "conflict", "msc_stale", "msc_future", "ems_drift")
        async def run(kind):
            clock, ha, optimizer = self.scenario(first_ems=4.5, ems_period=5.0)
            with clock.active():
                epoch = await self.qualified_epoch(optimizer, ha, clock)
                before = len(ha.requests)
                fired = []
                joint = {ha.cfg.sigenergy_mode_select, ha.cfg.ha_control_switch,
                         ha.cfg.ems_mode_select, ha.cfg.grid_export_limit}
                def inject(entities):
                    if fired or not joint.issubset(entities):
                        return
                    fired.append(True)
                    if kind == "replacement":
                        optimizer._msc_transition = replace(epoch)
                    elif kind == "msc_boundary":
                        epoch.msc_requested_at += 0.001
                    elif kind == "close_boundary":
                        epoch.close_requested_at += 0.001
                    elif kind == "phase":
                        epoch.phase = "close"
                    elif kind == "ems_drift":
                        ha._report(ha.cfg.ems_mode_select, MODE_CMD_DISCHARGE_PV, clock.elapsed)
                    elif kind in {"missing", "conflict"}:
                        ha.metadata_policy = kind
                    elif kind.startswith("msc_"):
                        stamp = {"msc_equal_request": 5.0, "msc_pre_request": 4.0,
                                 "msc_stale": -200.0, "msc_future": 200.0}[kind]
                        ha._report(ha.cfg.ems_mode_select, MODE_MAX_SELF, stamp)
                    elif kind == "export_pre_close":
                        ha._report(ha.cfg.grid_export_limit, "0.01", 2.0)
                    else:
                        ha._report(ha.cfg.grid_export_limit, "25.0", clock.elapsed)
                _state, _decision, result = await self.cycle(
                    optimizer, ha, clock,
                    before_apply=lambda _s, _d: setattr(ha, "metadata_hook", inject),
                )
                self.assertTrue(fired)
                self.assertFalse(result.succeeded)
                self.assertFalse(result.automatic_application_completed)
                self.assertFalse(optimizer._msc_baseline_established)
                self.assertIsNotNone(optimizer._msc_transition)
                self.assertFalse(any(r[2] == ha.cfg.grid_export_limit and r[3] > 0.011
                                     for r in ha.requests[before:]))
                self.assertTrue(any(r[2] == ha.cfg.grid_export_limit and r[3] <= 0.011
                                    for r in ha.requests[before:]))
        for kind in cases:
            with self.subTest(invalidation=kind):
                asyncio.run(run(kind))

    def test_takeover_at_joint_dispatch_read_stops_reopening(self):
        async def run(kind):
            clock, ha, optimizer = self.scenario(first_ems=4.5, ems_period=5.0)
            with clock.active():
                await self.qualified_epoch(optimizer, ha, clock)
                before = len(ha.requests)
                fired = []
                joint = {ha.cfg.sigenergy_mode_select, ha.cfg.ha_control_switch,
                         ha.cfg.ems_mode_select, ha.cfg.grid_export_limit}
                def inject(entities):
                    if fired or not joint.issubset(entities):
                        return
                    fired.append(True)
                    entity = ha.cfg.ha_control_switch if kind == "remote_off" else ha.cfg.sigenergy_mode_select
                    value = "off" if kind == "remote_off" else (ha.cfg.manual_option if kind == "manual" else "Force Full Export")
                    ha.plant[entity] = value
                    ha._report(entity, value, clock.elapsed)
                _state, _decision, result = await self.cycle(
                    optimizer, ha, clock,
                    before_apply=lambda _s, _d: setattr(ha, "metadata_hook", inject),
                )
                self.assertTrue(fired)
                self.assertFalse(result.succeeded)
                self.assertEqual([], ha.requests[before:])
                self.assertFalse(optimizer._msc_baseline_established)
        for kind in ("manual", "force", "remote_off"):
            with self.subTest(takeover=kind):
                asyncio.run(run(kind))

    def test_epoch_invalidated_after_export_open_is_closed_before_completion(self):
        async def run():
            clock, ha, optimizer = self.scenario(first_ems=4.5, ems_period=5.0)
            with clock.active():
                epoch = await self.qualified_epoch(optimizer, ha, clock)
                before = len(ha.requests)
                replacement = replace(epoch)
                def invalidate(entity, value):
                    if entity == ha.cfg.grid_export_limit and value > 0.011:
                        optimizer._msc_transition = replacement
                ha.write_hook = invalidate
                _state, _decision, result = await self.cycle(optimizer, ha, clock)
                self.assertFalse(result.succeeded)
                self.assertTrue(result.fallback_attempted)
                export = [r[3] for r in ha.requests[before:] if r[2] == ha.cfg.grid_export_limit]
                self.assertEqual([25.0, 0.01], export)
                self.assertIsNotNone(optimizer._msc_transition)
                self.assertFalse(optimizer._msc_baseline_established)
        asyncio.run(run())

    def test_cancelled_application_does_not_consume_proven_epoch(self):
        async def run():
            clock, ha, optimizer = self.scenario(first_ems=4.5, ems_period=5.0)
            with clock.active():
                epoch = await self.qualified_epoch(optimizer, ha, clock)
                def cancel(entity, value):
                    if entity == ha.cfg.grid_export_limit and value > 0.011:
                        raise asyncio.CancelledError()
                ha.write_hook = cancel
                with self.assertRaises(asyncio.CancelledError):
                    await self.cycle(optimizer, ha, clock)
                self.assertIs(epoch, optimizer._msc_transition)
                self.assertFalse(optimizer._msc_baseline_established)
        asyncio.run(run())

    def test_failed_actuator_after_reopening_requests_restrictive_fallback(self):
        async def run():
            clock, ha, optimizer = self.scenario(first_ems=4.5, ems_period=5.0)
            with clock.active():
                await self.qualified_epoch(optimizer, ha, clock)
                before = len(ha.requests)
                ha.write_hook = lambda entity, _v: False if entity == ha.cfg.pv_max_power_limit else None
                _state, _decision, result = await self.cycle(
                    optimizer, ha, clock,
                    before_apply=lambda _s, d: setattr(d, "pv_max_power_limit", 24.0),
                )
                self.assertFalse(result.succeeded)
                self.assertTrue(result.fallback_attempted)
                self.assertIn("failed setting PV MAX", result.error)
                export = [r[3] for r in ha.requests[before:] if r[2] == ha.cfg.grid_export_limit]
                self.assertEqual([25.0, 0.01], export)
                self.assertFalse(optimizer._msc_baseline_established)
                self.assertIsNotNone(optimizer._msc_transition)
        asyncio.run(run())

    def test_final_authority_read_cannot_consume_replaced_or_changed_epoch(self):
        async def run(kind):
            clock, ha, optimizer = self.scenario(first_ems=4.5, ems_period=5.0)
            with clock.active():
                epoch = await self.qualified_epoch(optimizer, ha, clock)
                before = len(ha.requests)
                after_helpers, fired = [], []
                def helper_completed():
                    after_helpers.append(True)
                    if kind == "exception":
                        fired.append(True)
                        raise RuntimeError("synthetic helper failure after export opened")
                ha.helper_hook = helper_completed
                def inject(entities):
                    if not after_helpers or fired:
                        return
                    self.assertTrue({ha.cfg.sigenergy_mode_select, ha.cfg.ha_control_switch}.issubset(entities))
                    fired.append(True)
                    if kind == "replace":
                        optimizer._msc_transition = replace(epoch)
                    elif kind == "msc_boundary":
                        epoch.msc_requested_at += 0.001
                    elif kind == "close_boundary":
                        epoch.close_requested_at += 0.001
                    elif kind == "phase":
                        epoch.phase = "close"
                    elif kind == "cancel":
                        raise asyncio.CancelledError()
                    else:
                        raise RuntimeError("synthetic final authority read failure")
                ha.metadata_hook = inject
                if kind in {"cancel", "exception"}:
                    error = asyncio.CancelledError if kind == "cancel" else RuntimeError
                    with self.assertRaises(error):
                        await self.cycle(optimizer, ha, clock)
                    self.assertIs(epoch, optimizer._msc_transition)
                else:
                    _state, _decision, result = await self.cycle(optimizer, ha, clock)
                    self.assertFalse(result.succeeded)
                    self.assertTrue(result.fallback_attempted)
                    export = [r[3] for r in ha.requests[before:] if r[2] == ha.cfg.grid_export_limit]
                    self.assertEqual([25.0, 0.01], export)
                    self.assertIsNotNone(optimizer._msc_transition)
                self.assertTrue(fired)
                self.assertFalse(optimizer._msc_baseline_established)
        for kind in ("replace", "msc_boundary", "close_boundary", "phase", "cancel", "exception"):
            with self.subTest(late_change=kind):
                asyncio.run(run(kind))

    def test_final_authority_takeover_does_not_consume_epoch_or_write_after_takeover(self):
        async def run(kind):
            clock, ha, optimizer = self.scenario(first_ems=4.5, ems_period=5.0)
            with clock.active():
                epoch = await self.qualified_epoch(optimizer, ha, clock)
                after_helpers, fired, requests_at_takeover = [], [], []
                ha.helper_hook = lambda: after_helpers.append(True)
                def inject(entities):
                    if not after_helpers or fired:
                        return
                    fired.append(True)
                    entity = ha.cfg.ha_control_switch if kind == "remote_off" else ha.cfg.sigenergy_mode_select
                    value = "off" if kind == "remote_off" else ha.cfg.manual_option
                    ha.plant[entity] = value
                    ha._report(entity, value, clock.elapsed)
                    requests_at_takeover.append(len(ha.requests))
                ha.metadata_hook = inject
                _state, _decision, result = await self.cycle(optimizer, ha, clock)
                self.assertTrue(fired)
                self.assertFalse(result.succeeded)
                self.assertFalse(result.automatic_application_completed)
                self.assertIs(epoch, optimizer._msc_transition)
                self.assertFalse(optimizer._msc_baseline_established)
                self.assertEqual(requests_at_takeover[0], len(ha.requests))
        for kind in ("manual", "remote_off"):
            with self.subTest(late_takeover=kind):
                asyncio.run(run(kind))
