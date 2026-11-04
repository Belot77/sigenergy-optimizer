"""Real automatic application with independently reported export settings.

Fixed deliberate decisions isolate the actuator protocol, not Boost eligibility.
Fake HA records commands and observation provenance separately; no physical
inverter response or production service rejection is inferred.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
import importlib
import unittest

from app.models import BATTERY_EXPORT

support = importlib.import_module("test_msc_settled_epoch_reuse")


class ExportReportHA(support.PeriodicReportHA):
    """Inject setting reports, never settlement/authority permission results."""

    def __init__(self, clock):
        super().__init__(clock)
        self.export_report_policy = None
        self.active_target = None
        self.target_requested_at = None
        self.ess_dispatch_evidence = []

    def _report(self, entity, value, reported_at):
        policy = self.export_report_policy
        if self.cfg is not None and entity == self.cfg.grid_export_limit and self.active_target is not None:
            if policy == "missing":
                return
            if policy == "stricter":
                value = "5.0"
            elif policy == "closed":
                value = "0.01"
            elif policy in {"pre", "equal", "stale", "future"}:
                reported_at = self.target_requested_at + {
                    "pre": -.1, "equal": 0.0, "stale": -61.0, "future": 1000.0,
                }[policy]
        super()._report(entity, value, reported_at)

    async def get_state_report_metadata(self, entity_ids):
        rows = await super().get_state_report_metadata(entity_ids)
        if self.active_target is not None and self.cfg.grid_export_limit in rows:
            if self.export_report_policy == "conflict":
                # REST setting and provenance-bearing report disagree.
                rows[self.cfg.grid_export_limit]["state"] = "0.01"
            elif self.export_report_policy == "missing":
                del rows[self.cfg.grid_export_limit]
        return rows

    async def set_number(self, entity, value):
        if entity == self.cfg.grid_export_limit:
            if value > .011:
                self.active_target = value
                self.target_requested_at = self.clock.elapsed
            else:
                # Fallback close has its own independently scheduled reports.
                self.active_target = None
        if entity == self.cfg.ess_max_discharging_limit and value > .011:
            metadata = self._state_value_metadata.get(self.cfg.grid_export_limit, {})
            self.ess_dispatch_evidence.append({
                "request_index": len(self.requests), "at": self.clock.elapsed,
                "export": self.state_values.get(self.cfg.grid_export_limit),
                "reported_at": metadata.get("last_reported"),
                "ems": self.state_values.get(self.cfg.ems_mode_select),
            })
        return await super().set_number(entity, value)


class DeliberateExportTargetDeadbandTests(unittest.TestCase):
    def setUp(self):
        self.fixture = support.Haos49CharacterizationCase("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)

    def scenario(self, current, *, deadband=.1, cap=25.0):
        clock = support.ReportClock()
        ha = ExportReportHA(clock)
        opt = self.fixture.optimizer(
            ha, min_change_threshold=deadband,
            ess_max_charging_limit="number.test_charge",
            ess_max_discharging_limit="number.test_discharge",
        )
        ha.configure(opt.cfg)
        ha.states[opt.cfg.grid_export_limit]["attributes"]["max"] = cap
        for entity, value in ((opt.cfg.ems_mode_select, support.MODE_CMD_DISCHARGE_PV),
                              (opt.cfg.grid_export_limit, str(current))):
            ha.plant[entity] = value
            ha._report(entity, value, -1.0)
        return clock, ha, opt

    async def apply(self, clock, ha, opt, target, *, at=None):
        if at is not None:
            self.assertGreaterEqual(at, clock.elapsed)
            clock.elapsed = at
        state = await opt._read_state()
        decision = support.Decision(
            ems_mode=support.MODE_CMD_DISCHARGE_PV,
            export_limit=target, export_intent=BATTERY_EXPORT,
            import_limit=0.0, ess_charge_limit=25.0,
            ess_discharge_limit=24.0, pv_max_power_limit=25.0,
        )
        return state, decision, await opt._apply(state, decision)

    def target_requests(self, ha, start=0):
        return [r for r in ha.requests[start:]
                if r[1] == "set_number" and r[2] == ha.cfg.grid_export_limit and r[3] > .011]

    def assert_proven_target_before_ess(self, clock, ha, target):
        requests = self.target_requests(ha)
        self.assertEqual(1, len(requests), ha.requests)
        request = requests[0]
        self.assertEqual(target, request[3])
        self.assertEqual(1, len(ha.ess_dispatch_evidence), ha.requests)
        evidence = ha.ess_dispatch_evidence[0]
        self.assertGreater(evidence["request_index"], ha.requests.index(request))
        self.assertGreater(evidence["at"], request[0])
        self.assertLessEqual(abs(float(evidence["export"]) - target), .011)
        self.assertGreater(datetime.fromisoformat(evidence["reported_at"]).timestamp(),
                           clock.at(request[0]).timestamp())
        self.assertEqual(support.MODE_CMD_DISCHARGE_PV, evidence["ems"])

    def test_live_small_target_changes_settle_before_positive_discharge_capability(self):
        async def run(current, target, deadband):
            clock, ha, opt = self.scenario(current, deadband=deadband)
            with clock.active():
                _s, _d, result = await self.apply(clock, ha, opt, target)
                self.assertTrue(result.automatic_application_completed, result.error)
                self.assertFalse(result.fallback_attempted)
                self.assert_proven_target_before_ess(clock, ha, target)
        for current, target, deadband in (
            (5.3, 5.2, .1), (5.0, 5.1, .1),
            (5.6, 5.5, .1), (7.4, 7.5, .1),
            (5.0, 5.2, .5),
        ):
            with self.subTest(current=current, target=target, deadband=deadband):
                asyncio.run(run(current, target, deadband))

    def test_existing_small_deadband_dispatch_is_not_duplicated(self):
        async def run():
            clock, ha, opt = self.scenario(5.3, deadband=.05)
            with clock.active():
                _s, _d, result = await self.apply(clock, ha, opt, 5.2)
                self.assertTrue(result.automatic_application_completed, result.error)
                self.assertFalse(result.fallback_attempted)
                self.assert_proven_target_before_ess(clock, ha, 5.2)
        asyncio.run(run())

    def test_valid_unchanged_target_tolerance_does_not_reassert_export(self):
        async def run():
            clock, ha, opt = self.scenario(4.4)
            with clock.active():
                _s, _d, first = await self.apply(clock, ha, opt, 4.6)
                self.assertTrue(first.automatic_application_completed, first.error)
                self.assert_proven_target_before_ess(clock, ha, 4.6)
                # A real prior application established the request boundary;
                # this later report stays inside its unchanged .011 tolerance.
                ha.plant[ha.cfg.grid_export_limit] = "4.591"
                ha._report(ha.cfg.grid_export_limit, "4.591", 1.0)
                before = len(ha.requests)
                _s, _d, followup = await self.apply(clock, ha, opt, 4.6, at=1.0)
                self.assertTrue(followup.automatic_application_completed, followup.error)
                self.assertFalse(followup.fallback_attempted)
                self.assertEqual([], self.target_requests(ha, before))
        asyncio.run(run())

    def test_stricter_closed_or_unproven_reports_cannot_prove_new_target(self):
        async def run(policy):
            clock, ha, opt = self.scenario(5.3)
            ha.export_report_policy = policy
            with clock.active():
                _s, _d, result = await self.apply(clock, ha, opt, 5.2)
                self.assertFalse(result.automatic_application_completed)
                targets = self.target_requests(ha)
                self.assertEqual(1, len(targets), ha.requests)
                self.assertEqual(5.2, targets[0][3])
                closes = [i for i, r in enumerate(ha.requests)
                          if r[1] == "set_number" and r[2] == ha.cfg.grid_export_limit and r[3] <= .011]
                self.assertTrue(closes, ha.requests)
                # House-serving recovery under proven MSC may subsequently
                # restore capability; it is not deliberate-discharge permission.
                self.assertEqual([], [e for e in ha.ess_dispatch_evidence
                                      if e["request_index"] < closes[0]])
                self.assertFalse(any(r[1] == "select_option" and r[3] in support.DISCHARGE_MODES
                                     for r in ha.requests))
        for policy in ("stricter", "closed", "pre", "equal", "stale", "future", "missing", "conflict"):
            with self.subTest(report=policy):
                asyncio.run(run(policy))

    def test_cap_bounds_the_requested_and_proven_target(self):
        async def run():
            clock, ha, opt = self.scenario(5.0, cap=5.05)
            with clock.active():
                state, _d, result = await self.apply(clock, ha, opt, 5.1)
                self.assertEqual(5.05, state.grid_export_limit_entity_max_kw)
                self.assertTrue(result.automatic_application_completed, result.error)
                self.assertFalse(result.fallback_attempted)
                self.assert_proven_target_before_ess(clock, ha, 5.05)
        asyncio.run(run())

    def test_late_manual_or_remote_takeover_stops_permissive_writes(self):
        async def run(kind):
            clock, ha, opt = self.scenario(5.3)
            fired = []
            def takeover(entities):
                if (not fired and ha.active_target is not None
                        and ha.cfg.sigenergy_mode_select in entities):
                    fired.append(len(ha.requests))
                    entity = ha.cfg.sigenergy_mode_select if kind == "manual" else ha.cfg.ha_control_switch
                    value = ha.cfg.manual_option if kind == "manual" else "off"
                    ha.plant[entity] = value
                    ha._report(entity, value, clock.elapsed)
            ha.metadata_hook = takeover
            with clock.active():
                _s, _d, result = await self.apply(clock, ha, opt, 5.2)
                self.assertEqual(1, len(self.target_requests(ha)))
                self.assertTrue(fired)
                self.assertFalse(result.automatic_application_completed)
                self.assertEqual([], ha.requests[fired[0]:])
                self.assertEqual([], ha.ess_dispatch_evidence)
        for kind in ("manual", "remote"):
            with self.subTest(owner=kind):
                asyncio.run(run(kind))
