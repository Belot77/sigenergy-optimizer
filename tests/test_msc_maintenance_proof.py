"""Offline maintenance-proof regressions composed from the settled-epoch fake HA."""
from __future__ import annotations

import asyncio
import importlib
import unittest
from dataclasses import replace
from unittest.mock import AsyncMock, patch
import app.optimizer as optimizer_module

support = importlib.import_module("test_msc_settled_epoch_reuse")


class MscMaintenanceProofTests(unittest.TestCase):
    def setUp(self):
        # Keep the support TestCase out of this module's globals so unittest
        # discovery collects only the tests below.
        self.fixture = support.MscSettledEpochReuseTests("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def scenario(self):
        return self.fixture.scenario(first_ems=1.2, ems_period=5.0)

    def test_post_opening_unchanged_reports_qualify_same_open_ceiling_without_reassertion(self):
        async def run():
            clock, ha, optimizer = self.scenario()
            with clock.active():
                _state, _decision, initial = await self.fixture.cycle(
                    optimizer, ha, clock,
                )
                self.assertTrue(initial.succeeded, initial.error)
                self.assertTrue(initial.automatic_application_completed)
                cfg = ha.cfg
                opening = [
                    request for request in ha.requests
                    if request[1] == "set_number" and request[2] == cfg.grid_export_limit
                    and request[3] == 25.0
                ]
                self.assertTrue(opening)
                self.assertEqual(1.2, opening[-1][0])

                # The same-valued EMS report at 6.2 is after the original MSC
                # request, and the export entity reports again after opening.
                before = len(ha.requests)
                _state, _decision, maintenance = await self.fixture.cycle(
                    optimizer, ha, clock, at=6.3,
                )
                self.assertTrue(any(
                    when == 6.2 and entity == cfg.ems_mode_select and value == support.MODE_MAX_SELF
                    for when, entity, value in ha.reports
                ))
                self.assertTrue(any(
                    when > opening[-1][0] and entity == cfg.grid_export_limit and value == "25.0"
                    for when, entity, value in ha.reports
                ))
                self.assertTrue(maintenance.succeeded, maintenance.error)
                self.assertTrue(maintenance.automatic_application_completed)
                self.assertEqual(6.3, clock.elapsed)
                self.assertEqual([], [
                    request for request in ha.requests[before:]
                    if (request[1] == "select_option" and request[2] == cfg.ems_mode_select)
                    or (request[1] == "set_number" and request[2] == cfg.grid_export_limit)
                ])
                self.assertEqual("25.0", ha.plant[cfg.grid_export_limit])
        asyncio.run(run())

    def test_initial_application_without_post_open_export_report_does_not_qualify_maintenance(self):
        async def run():
            clock, ha, optimizer = self.scenario()
            with clock.active():
                _state, _decision, initial = await self.fixture.cycle(
                    optimizer, ha, clock,
                )
                self.assertTrue(initial.succeeded, initial.error)
                cfg = ha.cfg
                opening = [
                    request for request in ha.requests
                    if request[1] == "set_number" and request[2] == cfg.grid_export_limit
                    and request[3] == 25.0
                ]
                self.assertTrue(opening)
                # Continue the periodic EMS reports, but withhold every export
                # report after the opening request. The initial application
                # result and baseline flag cannot substitute for later proof.
                ha.numeric.discard(cfg.grid_export_limit)
                post_open_export_reports = [
                    when for when, entity, _value in ha.reports
                    if entity == cfg.grid_export_limit and when > opening[-1][0]
                ]
                self.assertEqual([], post_open_export_reports)
                before = len(ha.requests)
                _state, _decision, maintenance = await self.fixture.cycle(
                    optimizer, ha, clock, at=6.3,
                )
                self.assertFalse(maintenance.succeeded)
                self.assertFalse(maintenance.automatic_application_completed)
                self.assertTrue(any(
                    request[1] == "select_option" and request[2] == cfg.ems_mode_select
                    for request in ha.requests[before:]
                ))
                self.assertFalse(any(
                    request[1] == "set_number" and request[2] == cfg.grid_export_limit
                    and request[3] > 0.011
                    for request in ha.requests[before:]
                ))
                self.assertTrue(any(
                    request[1] == "set_number" and request[2] == cfg.grid_export_limit
                    and request[3] <= 0.011
                    for request in ha.requests[before:]
                ))
        asyncio.run(run())

    def test_restart_and_changed_target_do_not_reuse_completed_epoch(self):
        async def run(kind):
            clock, ha, optimizer = self.scenario()
            with clock.active():
                before_apply = None
                if kind == "initial_target_20":
                    before_apply = lambda _state, decision: setattr(decision, "export_limit", 20.0)
                _state, _decision, initial = await self.fixture.cycle(
                    optimizer, ha, clock, before_apply=before_apply,
                )
                self.assertTrue(initial.succeeded, initial.error)
                cfg = ha.cfg
                opened_target = 20.0 if kind == "initial_target_20" else 25.0
                opening = [
                    request for request in ha.requests
                    if request[1] == "set_number" and request[2] == cfg.grid_export_limit
                    and request[3] == opened_target
                ]
                self.assertTrue(opening)

                if kind == "restart":
                    # A fresh optimizer has no in-memory candidate from the
                    # earlier completed application, even with identical HA.
                    optimizer = self.fixture.fixture.optimizer(
                        ha, ess_max_charging_limit="number.test_charge",
                        ess_max_discharging_limit="number.test_discharge",
                    )
                    ha.configure(optimizer.cfg)
                    ha.plant[optimizer.cfg.grid_export_limit] = "25.0"
                    ha.plant[optimizer.cfg.ems_mode_select] = support.MODE_MAX_SELF
                before = len(ha.requests)
                _state, _decision, later = await self.fixture.cycle(
                    optimizer, ha, clock, at=6.3,
                )
                self.assertFalse(later.succeeded)
                self.assertFalse(later.automatic_application_completed)
                if kind == "restart":
                    self.assertTrue(later.transition_pending)
                else:
                    self.assertTrue(any(
                        request[1] == "select_option" and request[2] == optimizer.cfg.ems_mode_select
                        for request in ha.requests[before:]
                    ))
                self.assertFalse(any(
                    request[1] == "set_number" and request[2] == optimizer.cfg.grid_export_limit
                    and request[3] > 0.011
                    for request in ha.requests[before:]
                ))
                self.assertTrue(any(
                    request[1] == "set_number" and request[2] == optimizer.cfg.grid_export_limit
                    and request[3] <= 0.011
                    for request in ha.requests[before:]
                ))
        for kind in ("restart", "initial_target_20"):
            with self.subTest(identity_or_target=kind):
                asyncio.run(run(kind))

    def test_current_export_mismatch_and_untrusted_joint_reports_block_reopening(self):
        async def run(kind):
            clock, ha, optimizer = self.scenario()
            with clock.active():
                _state, _decision, initial = await self.fixture.cycle(
                    optimizer, ha, clock,
                )
                self.assertTrue(initial.succeeded, initial.error)
                cfg = ha.cfg
                before = len(ha.requests)
                injected = []
                joint = {
                    cfg.sigenergy_mode_select, cfg.ha_control_switch,
                    cfg.ems_mode_select, cfg.grid_export_limit,
                }

                def inject(entities):
                    if injected or not joint.issubset(entities):
                        return
                    injected.append(True)
                    if kind == "ems_drift":
                        ha._report(cfg.ems_mode_select, support.MODE_CMD_DISCHARGE_PV, clock.elapsed)
                    elif kind == "export_reduced":
                        ha._report(cfg.grid_export_limit, "20.0", clock.elapsed)
                    elif kind == "ems_stale":
                        ha._report(cfg.ems_mode_select, "Maximum Self Consumption", -200.0)
                    elif kind == "ems_conflict":
                        ha.metadata_policy = "conflict"
                    elif kind == "ems_missing":
                        ha.metadata_policy = "missing"
                    elif kind == "authority_takeover":
                        ha._report(cfg.sigenergy_mode_select, cfg.manual_option, clock.elapsed)

                before_apply = lambda _state, _decision: setattr(ha, "metadata_hook", inject)
                _state, _decision, result = await self.fixture.cycle(
                    optimizer, ha, clock, at=6.3, before_apply=before_apply,
                )
                self.assertTrue(injected, f"joint read was not reached for {kind}")
                self.assertFalse(result.automatic_application_completed)
                self.assertFalse(any(
                    request[1] == "set_number" and request[2] == cfg.grid_export_limit
                    and request[3] > 25.0
                    for request in ha.requests[before:]
                ))
                if kind in {"ems_drift", "export_reduced", "ems_stale", "ems_conflict", "ems_missing"}:
                    self.assertFalse(result.succeeded)
                    self.assertFalse(any(
                        request[1] == "set_number" and request[2] == cfg.grid_export_limit
                        and request[3] > 0.011
                        for request in ha.requests[before:]
                    ))
                    self.assertTrue(any(
                        request[1] == "set_number" and request[2] == cfg.grid_export_limit
                        and request[3] <= 0.011
                        for request in ha.requests[before:]
                    ))
                else:
                    self.assertFalse(result.automatic_application_completed)
                    self.assertFalse(any(
                        request[1] == "set_number" and request[2] == cfg.grid_export_limit
                        and request[3] > 0.011
                        for request in ha.requests[before:]
                    ))
        for kind in ("ems_drift", "export_reduced", "ems_stale", "ems_conflict", "ems_missing", "authority_takeover"):
            with self.subTest(observation=kind):
                asyncio.run(run(kind))


    def test_failed_or_cancelled_followup_does_not_consume_maintenance_proof(self):
        async def run(kind):
            clock, ha, optimizer = self.scenario()
            with clock.active():
                _state, _decision, initial = await self.fixture.cycle(
                    optimizer, ha, clock,
                )
                self.assertTrue(initial.succeeded, initial.error)
                cfg = ha.cfg
                before_followup = len(ha.requests)

                def fail_pv_limit(entity, _value):
                    if entity == cfg.pv_max_power_limit:
                        if kind == "cancel":
                            raise asyncio.CancelledError()
                        return False
                    return None

                ha.write_hook = fail_pv_limit
                if kind == "cancel":
                    with self.assertRaises(asyncio.CancelledError):
                        await self.fixture.cycle(
                            optimizer, ha, clock, at=6.3,
                            before_apply=lambda _s, decision: setattr(decision, "pv_max_power_limit", 24.0),
                        )
                else:
                    _state, _decision, failed = await self.fixture.cycle(
                        optimizer, ha, clock, at=6.3,
                        before_apply=lambda _s, decision: setattr(decision, "pv_max_power_limit", 24.0),
                    )
                    self.assertFalse(failed.succeeded)
                    self.assertTrue(failed.fallback_attempted)
                self.assertTrue(any(
                    request[1] == "set_number" and request[2] == cfg.grid_export_limit
                    and request[3] <= 0.011
                    for request in ha.requests[before_followup:]
                ) or kind == "cancel")

                # The completed initial app cannot be replayed after an
                # incomplete/cancelled later application. Existing reports
                # predate this retry, so it may only remain restricted.
                ha.write_hook = None
                ha.next_ems = None
                before_retry = len(ha.requests)
                _state, _decision, retry = await self.fixture.cycle(
                    optimizer, ha, clock, at=clock.elapsed + 0.1,
                )
                self.assertFalse(retry.automatic_application_completed)
                self.assertFalse(any(
                    request[1] == "set_number" and request[2] == cfg.grid_export_limit
                    and request[3] > 0.011
                    for request in ha.requests[before_retry:]
                ))
        for kind in ("failure", "cancel"):
            with self.subTest(outcome=kind):
                asyncio.run(run(kind))

    def test_changed_ems_configuration_has_no_prior_maintenance_proof(self):
        async def run():
            clock, ha, optimizer = self.scenario()
            with clock.active():
                _state, _decision, initial = await self.fixture.cycle(
                    optimizer, ha, clock,
                )
                self.assertTrue(initial.succeeded, initial.error)
                before = len(ha.requests)
                changed = self.fixture.fixture.optimizer(
                    ha, ems_mode_select="select.changed_ems_mode",
                    ess_max_charging_limit="number.test_charge",
                    ess_max_discharging_limit="number.test_discharge",
                )
                ha.configure(changed.cfg)
                ha.plant[changed.cfg.grid_export_limit] = "25.0"
                ha.plant[changed.cfg.ems_mode_select] = support.MODE_MAX_SELF
                _state, _decision, result = await self.fixture.cycle(
                    changed, ha, clock, at=6.3,
                )
                self.assertFalse(result.succeeded)
                self.assertFalse(result.automatic_application_completed)
                self.assertTrue(result.transition_pending)
                self.assertTrue(any(
                    request[1] == "set_number" and request[2] == changed.cfg.grid_export_limit
                    and request[3] <= 0.011 for request in ha.requests[before:]
                ))
                self.assertFalse(any(
                    request[1] == "set_number" and request[2] == changed.cfg.grid_export_limit
                    and request[3] > 0.011
                    for request in ha.requests[before:]
                ))
        asyncio.run(run())


    def test_closed_ceiling_requires_new_proof_before_reopening(self):
        async def run():
            clock, ha, optimizer = self.scenario()
            with clock.active():
                _state, _decision, initial = await self.fixture.cycle(
                    optimizer, ha, clock,
                )
                self.assertTrue(initial.succeeded, initial.error)
                cfg = ha.cfg
                before = len(ha.requests)
                ha.plant[cfg.grid_export_limit] = "0.01"
                ha._report(cfg.grid_export_limit, "0.01", 6.3)
                _state, _decision, reopened = await self.fixture.cycle(
                    optimizer, ha, clock, at=6.4,
                )
                self.assertFalse(reopened.automatic_application_completed)
                self.assertTrue(any(
                    request[1] == "select_option" and request[2] == cfg.ems_mode_select
                    for request in ha.requests[before:]
                ))
                self.assertFalse(any(
                    request[1] == "set_number" and request[2] == cfg.grid_export_limit
                    and request[3] > 0.011
                    for request in ha.requests[before:]
                ))
        asyncio.run(run())

    def test_raw_baseline_flag_without_completed_candidate_cannot_reopen_ceiling(self):
        async def run():
            clock, ha, optimizer = self.scenario()
            with clock.active():
                _state, _decision, initial = await self.fixture.cycle(
                    optimizer, ha, clock,
                )
                self.assertTrue(initial.succeeded, initial.error)
                # Isolate the legacy boolean from the new completed-app token.
                # A matching EMS/export report from the earlier application
                # cannot be treated as a candidate merely because this flag is set.
                optimizer._msc_baseline_established = True
                optimizer._msc_maintenance_epoch = None
                ha.next_ems = None
                before = len(ha.requests)
                _state, _decision, result = await self.fixture.cycle(
                    optimizer, ha, clock, at=6.3,
                )
                self.assertFalse(result.succeeded)
                self.assertFalse(result.automatic_application_completed)
                self.assertTrue(any(
                    request[1] == "select_option" and request[2] == ha.cfg.ems_mode_select
                    for request in ha.requests[before:]
                ))
                self.assertFalse(any(
                    request[1] == "set_number" and request[2] == ha.cfg.grid_export_limit
                    and request[3] > 0.011
                    for request in ha.requests[before:]
                ))
        asyncio.run(run())

    def test_reused_maintenance_proof_keeps_import_ess_and_pv_restrictions_independent(self):
        async def run():
            clock, ha, optimizer = self.scenario()
            with clock.active():
                _state, _decision, initial = await self.fixture.cycle(
                    optimizer, ha, clock,
                )
                self.assertTrue(initial.succeeded, initial.error)
                cfg = ha.cfg
                before = len(ha.requests)

                def apply_independent_limits(_state, decision):
                    decision.import_limit = 0.0
                    decision.ess_charge_limit = 0.0
                    decision.ess_discharge_limit = 0.0
                    decision.pv_max_power_limit = 12.0

                _state, _decision, result = await self.fixture.cycle(
                    optimizer, ha, clock, at=6.3, before_apply=apply_independent_limits,
                )
                self.assertTrue(result.succeeded, result.error)
                writes = [
                    (request[2], request[3]) for request in ha.requests[before:]
                    if request[1] == "set_number"
                ]
                self.assertLessEqual(float(ha.plant[cfg.grid_import_limit]), 0.011)
                self.assertTrue(all(value <= 0.011 for entity, value in writes if entity == cfg.grid_import_limit))
                self.assertIn((cfg.ess_max_charging_limit, 0.0), writes)
                self.assertIn((cfg.ess_max_discharging_limit, 0.0), writes)
                self.assertIn((cfg.pv_max_power_limit, 12.0), writes)
                self.assertFalse(any(
                    request[1] == "set_number" and request[2] == cfg.grid_export_limit
                    for request in ha.requests[before:]
                ))
                self.assertFalse(any(
                    request[1] == "select_option" and request[2] == cfg.ems_mode_select
                    for request in ha.requests[before:]
                ))
        asyncio.run(run())


    def test_open_startup_anchors_once_then_reuses_after_later_matching_report(self):
        async def run():
            clock, ha, optimizer = self.scenario()
            cfg = ha.cfg
            ha.plant[cfg.grid_export_limit] = "25.0"
            ha._report(cfg.grid_export_limit, "25.0", -1.0)
            # Model a known open MSC baseline without a numeric request in this
            # process; the application must still create its own exact anchor.
            optimizer._msc_baseline_established = True
            with clock.active():
                _state, _decision, initial = await self.fixture.cycle(
                    optimizer, ha, clock,
                )
                self.assertTrue(initial.succeeded, initial.error)
                selector_requests = [
                    request for request in ha.requests
                    if request[1] == "select_option" and request[2] == cfg.ems_mode_select
                ]
                anchor_requests = [
                    request for request in ha.requests
                    if request[1] == "set_number" and request[2] == cfg.grid_export_limit
                    and request[3] == 25.0
                ]
                self.assertEqual(1, len(selector_requests))
                self.assertEqual(1, len(anchor_requests))
                self.assertGreater(anchor_requests[0][0], selector_requests[0][0])
                self.assertTrue(any(
                    when == 1.2 and entity == cfg.ems_mode_select and value == support.MODE_MAX_SELF
                    for when, entity, value in ha.reports
                ))

                before = len(ha.requests)
                _state, _decision, later = await self.fixture.cycle(
                    optimizer, ha, clock, at=6.3,
                )
                self.assertTrue(later.succeeded, later.error)
                self.assertTrue(any(
                    when > anchor_requests[0][0] and entity == cfg.grid_export_limit and value == "25.0"
                    for when, entity, value in ha.reports
                ))
                self.assertEqual([], [
                    request for request in ha.requests[before:]
                    if (request[1] == "select_option" and request[2] == cfg.ems_mode_select)
                    or (request[1] == "set_number" and request[2] == cfg.grid_export_limit)
                ])
                self.assertEqual(1, len([
                    request for request in ha.requests
                    if request[1] == "set_number" and request[2] == cfg.grid_export_limit
                    and request[3] == 25.0
                ]))
        asyncio.run(run())

    def test_open_startup_anchor_requires_later_matching_export_report(self):
        async def run():
            clock, ha, optimizer = self.scenario()
            cfg = ha.cfg
            ha.plant[cfg.grid_export_limit] = "25.0"
            ha._report(cfg.grid_export_limit, "25.0", -1.0)
            optimizer._msc_baseline_established = True
            with clock.active():
                _state, _decision, initial = await self.fixture.cycle(
                    optimizer, ha, clock,
                )
                self.assertTrue(initial.succeeded, initial.error)
                anchor = [
                    request for request in ha.requests
                    if request[1] == "set_number" and request[2] == cfg.grid_export_limit
                    and request[3] == 25.0
                ]
                self.assertEqual(1, len(anchor))
                # Keep EMS reports advancing, but withhold any matching export
                # report later than the process-local anchor request.
                ha.numeric.discard(cfg.grid_export_limit)
                before = len(ha.requests)
                _state, _decision, later = await self.fixture.cycle(
                    optimizer, ha, clock, at=6.3,
                )
                self.assertFalse(later.succeeded)
                self.assertFalse(later.automatic_application_completed)
                self.assertTrue(any(
                    request[1] == "select_option" and request[2] == cfg.ems_mode_select
                    for request in ha.requests[before:]
                ))
                self.assertFalse(any(
                    request[1] == "set_number" and request[2] == cfg.grid_export_limit
                    and request[3] > 0.011
                    for request in ha.requests[before:]
                ))
                self.assertEqual(1, len([
                    request for request in ha.requests
                    if request[1] == "set_number" and request[2] == cfg.grid_export_limit
                    and request[3] == 25.0
                ]))
        asyncio.run(run())

    def test_final_joint_read_export_reduction_or_close_never_reopens_25(self):
        async def run(kind):
            clock, ha, optimizer = self.scenario()
            with clock.active():
                _state, _decision, initial = await self.fixture.cycle(
                    optimizer, ha, clock,
                )
                self.assertTrue(initial.succeeded, initial.error)
                cfg = ha.cfg
                after_helpers = []
                injected = []
                joint = {
                    cfg.sigenergy_mode_select, cfg.ha_control_switch,
                    cfg.ems_mode_select, cfg.grid_export_limit,
                }
                ha.helper_hook = lambda: after_helpers.append(True)

                def inject(entities):
                    if not after_helpers or injected or not joint.issubset(entities):
                        return
                    injected.append(True)
                    value = "20.0" if kind == "reduced" else "0.01"
                    ha.plant[cfg.grid_export_limit] = value
                    ha._report(cfg.grid_export_limit, value, clock.elapsed)

                ha.metadata_hook = inject
                before = len(ha.requests)
                _state, _decision, result = await self.fixture.cycle(
                    optimizer, ha, clock, at=6.3,
                )
                self.assertTrue(after_helpers)
                self.assertTrue(injected, "final joint read was not reached")
                self.assertFalse(result.automatic_application_completed)
                self.assertFalse(any(
                    request[1] == "set_number" and request[2] == cfg.grid_export_limit
                    and request[3] == 25.0
                    for request in ha.requests[before:]
                ))
                self.assertFalse(any(
                    request[1] == "set_number" and request[2] == cfg.grid_export_limit
                    and request[3] > 25.0
                    for request in ha.requests[before:]
                ))
        for kind in ("reduced", "closed"):
            with self.subTest(final_export=kind):
                asyncio.run(run(kind))



    def test_late_helper_transition_or_epoch_replacement_cannot_be_erased(self):
        async def run(kind):
            clock, ha, opt = self.scenario()
            with clock.active():
                await self.fixture.cycle(opt, ha, clock)
                before = len(ha.requests)
                def invalidate():
                    if kind == "transition":
                        opt._msc_transition = optimizer_module._MscTransition()
                    elif kind == "epoch":
                        opt._msc_maintenance_epoch = replace(opt._msc_maintenance_epoch)
                    else:
                        opt._msc_maintenance_epoch.msc_requested_at += 0.001
                ha.helper_hook = invalidate
                _, _, result = await self.fixture.cycle(opt, ha, clock, at=6.3)
                self.assertFalse(result.succeeded)
                self.assertTrue(result.fallback_attempted)
                self.assertIsNotNone(opt._msc_transition)
                self.assertIsNone(opt._msc_maintenance_epoch)
                self.assertTrue(any(r[2] == ha.cfg.grid_export_limit and r[3] <= 0.011 for r in ha.requests[before:]))
                self.assertFalse(any(r[2] == ha.cfg.grid_export_limit and r[3] > 0.011 for r in ha.requests[before:]))
        for kind in ("transition", "epoch", "boundary"):
            with self.subTest(late_invalidation=kind):
                asyncio.run(run(kind))

    def test_continuity_change_during_initial_application_prevents_late_mint(self):
        async def run():
            clock, ha, opt = self.scenario()
            with clock.active():
                fired = []
                def change(entity, value):
                    if entity == ha.cfg.grid_export_limit and value > 0.011 and not fired:
                        fired.append(True)
                        opt.on_ws_disconnect()
                        opt.on_ws_connect()
                ha.write_hook = change
                _, _, result = await self.fixture.cycle(opt, ha, clock)
                self.assertTrue(result.succeeded, result.error)
                self.assertTrue(fired)
                self.assertIsNone(opt._msc_maintenance_epoch)
        asyncio.run(run())

    def test_uncommitted_read_failure_retires_maintenance_candidate(self):
        async def run():
            clock, ha, opt = self.scenario()
            with clock.active():
                await self.fixture.cycle(opt, ha, clock)
                self.assertIsNotNone(opt._msc_maintenance_epoch)
                with patch.object(opt, "_read_state", AsyncMock(side_effect=RuntimeError("synthetic read failure"))):
                    with self.assertRaises(RuntimeError):
                        await opt._tick()
                self.assertIsNone(opt._msc_maintenance_epoch)
        asyncio.run(run())

    def test_charge_owner_is_rechecked_after_the_new_joint_await(self):
        async def run():
            clock, ha, opt = self.scenario()
            with clock.active():
                await self.fixture.cycle(opt, ha, clock)
                before = len(ha.requests)
                expired, reads = [], []
                joint = {ha.cfg.sigenergy_mode_select, ha.cfg.ha_control_switch,
                         ha.cfg.ems_mode_select, ha.cfg.grid_export_limit}
                def metadata(entities):
                    if joint.issubset(entities):
                        reads.append(True)
                        if len(reads) == 2:
                            expired.append(True)
                def recheck(_s, d, _now):
                    if expired:
                        d.ess_charge_limit = 25.0
                        d.trace_gates["solar_charge_ceiling_owned"] = False
                def begin(_s, d):
                    d.ess_charge_limit = 2.0
                    ha.metadata_hook = metadata
                with patch.object(opt, "_recheck_solar_charge_authority", side_effect=recheck):
                    _, _, result = await self.fixture.cycle(opt, ha, clock, at=6.3, before_apply=begin)
                self.assertTrue(expired)
                self.assertFalse(result.succeeded)
                self.assertTrue(result.fallback_attempted)
                self.assertFalse(any(r[2] == ha.cfg.ess_max_charging_limit and r[3] == 2.0 for r in ha.requests[before:]))
        asyncio.run(run())

    def test_passive_diagnostic_failures_cannot_change_application(self):
        async def run():
            clock, ha, opt = self.scenario()
            with clock.active():
                with patch.object(opt, "_msc_diagnostic", side_effect=lambda *_a, **_k: None):
                    _, _, result = await self.fixture.cycle(opt, ha, clock)
                    self.assertTrue(result.succeeded, result.error)
                for name in ("start", "record_request", "record_observation", "finish", "snapshot"):
                    setattr(opt._msc_settlement_evidence, name, lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("synthetic recorder failure")))
                _, _, result = await self.fixture.cycle(opt, ha, clock, at=6.3)
                self.assertTrue(result.succeeded, result.error)
        asyncio.run(run())

    def test_application_trace_contains_bounded_real_metadata_without_raw_config(self):
        async def run():
            clock, ha, opt = self.scenario()
            with clock.active():
                await self.fixture.cycle(opt, ha, clock)
                state, decision, result = await self.fixture.cycle(opt, ha, clock, at=6.3)
                opt._record_application_trace(state, decision, result)
                trace = opt.decision_trace(1)[0]["application"]["msc_settlement"]
                self.assertEqual("succeeded", trace["status"])
                self.assertTrue(trace["context"]["maintenance"])
                self.assertLessEqual(len(trace["observations"]), 12)
                observations = [r["observed"] for r in trace["observations"]]
                self.assertTrue(any("last_reported" in r and "last_updated" in r for r in observations))
                self.assertTrue(any(r.get("state") == 25.0 for r in observations))
                self.assertNotIn("ha_token", str(trace))
                self.assertNotIn("http", str(trace))
        asyncio.run(run())

    def test_continuity_change_inside_state_read_cannot_label_pre_gap_evidence_current(self):
        async def run():
            clock, ha, opt = self.scenario()
            with clock.active():
                fired = []
                original = ha.bulk_states
                async def changing(entities):
                    rows = await original(entities)
                    if not fired:
                        fired.append(True)
                        opt.on_ws_disconnect()
                        opt.on_ws_connect()
                    return rows
                with patch.object(ha, "bulk_states", side_effect=changing):
                    state = await opt._read_state()
                self.assertTrue(fired)
                self.assertIsNone(getattr(state, "_msc_read_identity", None))
                self.assertIsNone(opt._msc_maintenance_epoch)
                self.assertNotIn(opt.cfg.ha_token, repr(getattr(state, "_msc_read_identity", None))) if opt.cfg.ha_token else None
        asyncio.run(run())
