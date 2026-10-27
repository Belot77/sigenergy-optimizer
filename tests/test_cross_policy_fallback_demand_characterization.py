"""Regression tests for Demand Window ownership during settled fallback.

The fake HA supplies current State-object report metadata. These tests establish
software dispatch permission; they do not prove physical inverter settlement.
"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import os
import unittest
from unittest.mock import patch

from app.config import Settings
from app.models import BATTERY_EXPORT, EXPORT_BLOCKED
from app.optimizer import MODE_CMD_DISCHARGE_PV, MODE_MAX_SELF
from test_msc_baseline_overlay_contract import later_msc_report_clock


class CrossPolicyFallbackDemandTests(unittest.TestCase):
    def setUp(self) -> None:
        environment = patch.dict(os.environ, {}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        settings = patch(
            "haos49_characterization_helpers.Settings",
            side_effect=lambda **values: Settings(_env_file=None, **values),
        )
        settings.start()
        self.addCleanup(settings.stop)
        # The fixture installs its temporary STATE_DB_PATH after isolation;
        # unittest cleanup then closes it before restoring ambient variables.
        # Compose the existing fixture so its tests are not collected again.
        from test_phase1_actuator_settlement_fallback_characterization import (
            Phase1ActuatorSettlementFallbackCharacterizationTests,
            _ScriptedActuatorHA,
        )

        self.fixture = Phase1ActuatorSettlementFallbackCharacterizationTests(
            methodName="runTest"
        )
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        class ReportingHA(_ScriptedActuatorHA):
            fail_demand_metadata = False
            demand_metadata_override = None

            async def get_state_report_metadata(self, entity_ids):
                self.report_metadata_calls.append(list(entity_ids))
                if self.fail_demand_metadata and self.demand_sensor in entity_ids:
                    raise RuntimeError("simulated report enrichment failure")
                metadata = {
                    entity: {
                        "entity_id": entity,
                        "state": self.state_values[entity],
                        **self._state_value_metadata[entity],
                    }
                    for entity in entity_ids
                    if entity in self.state_values
                    and entity in self._state_value_metadata
                }
                if self.demand_metadata_override is not None:
                    metadata[self.demand_sensor] = self.demand_metadata_override
                return metadata

        self.ha_type = ReportingHA

    @contextmanager
    def _real_export_fallback_clock(self, optimizer, ha, when, *, close_report_delay_ms=1):
        """Report the single fallback close after a failed positive export write."""
        fixture = self.fixture
        with later_msc_report_clock(ha, when) as moment:
            fixture._supply_owner(optimizer, ha, moment[0], optimizer.cfg.automated_option)
            original_bulk_states = ha.bulk_states
            closure_report_pending = True

            async def later_fallback_close_report(entity_ids):
                nonlocal closure_report_pending
                entity = optimizer.cfg.grid_export_limit
                positive_primary_failed = any(
                    method == "set_number" and called_entity == entity and value > 0.011
                    for method, called_entity, value in ha.calls
                )
                if (
                    closure_report_pending and entity in entity_ids
                    and positive_primary_failed
                    and ha.calls.count(("set_number", entity, 0.01)) == 1
                ):
                    # An accepted fallback close is not itself settlement.
                    # Supply a distinct later State-object report for the real
                    # export candidate's first and only 0.01 close request.
                    request = optimizer._number_settlement_requests.get(entity)
                    self.assertIsNotNone(request)
                    self.assertEqual(0.01, request[0])
                    if close_report_delay_ms > 0:
                        moment[0] += timedelta(milliseconds=close_report_delay_ms)
                    ha._record_state_value(entity, 0.01)
                    if close_report_delay_ms == 0:
                        # An equal-time report is deliberately uncorrelated
                        # with the close request even if the fake clock later
                        # advanced for the independent MSC report.
                        equal_report = datetime.fromtimestamp(request[1], timezone.utc).isoformat()
                        ha._state_value_metadata[entity]["last_updated"] = equal_report
                        ha._state_value_metadata[entity]["last_reported"] = equal_report
                    reported_at = (
                        request[1] if close_report_delay_ms == 0 else moment[0].timestamp()
                    )
                    self.latest_real_close_proof = (request[1], reported_at)
                    closure_report_pending = False
                return await original_bulk_states(entity_ids)

            ha.bulk_states = later_fallback_close_report
            try:
                yield
            finally:
                ha.bulk_states = original_bulk_states

    def _run_settled_fallback(
        self, demand_at_msc_wait: str | None, *,
        initial_demand: str = "off",
        initial_import_kw: float = 0.01,
        updated_age_seconds: float | None = None,
        reported_age_seconds: float | None = None,
        fail_demand_metadata: bool = False,
        late_demand_on_joint_read: str | None = None,
        late_takeover: str | None = None,
        conflict_newer_on: bool = False,
        decision_overrides: dict | None = None,
        malformed_demand_bulk: object | None = None,
        fail_joint_read: bool = False,
        import_close_fails: bool = False,
        takeover_on_recursive_close: str | None = None,
        real_unknown_cost_decision: bool = False,
        settle_msc: bool = True,
        close_report_delay_ms: int = 1,
        late_export_reopen: float | None = None,
        late_ems_change: str | None = None,
        ess_discharge_write_fails: bool = False,
        applied_discharge_limit: float | None = None,
        real_state_overrides: dict | None = None,
        optimizer_overrides: dict | None = None,
    ):
        fixture = self.fixture
        ha = self.ha_type()
        if not settle_msc:
            ha.settle_selects = False
        optimizer = fixture.optimizer(
            ha, cap_total_import=13.25, **(optimizer_overrides or {})
        )
        cfg = optimizer.cfg
        sensor = cfg.demand_window_sensor
        ha.demand_sensor = sensor
        ha.outcomes[("set_number", cfg.grid_export_limit)] = [False, True]
        if import_close_fails:
            ha.outcomes[("set_number", cfg.grid_import_limit)] = [False]
        if ess_discharge_write_fails:
            ha.outcomes[("set_number", cfg.ess_max_discharging_limit)] = [True, False]
        state_overrides = dict(
            demand_window_active=initial_demand == "on",
            demand_window_observed=True,
            current_import_limit=initial_import_kw,
        )
        if real_unknown_cost_decision:
            state_overrides.update(
                current_export_limit=0.01,
                battery_soc=70.0,
                battery_capacity_trusted=True,
                available_discharge_energy_kwh=21.0,
                feedin_price=1.10,
                feedin_price_cents=110.0,
                pv_kw=10.0,
                solar_power_now_kw=10.0,
                load_kw=1.0,
                forecast_remaining_observation_trusted=True,
            )
            state_overrides.update(real_state_overrides or {})
        state = fixture._automatic_apply_state(**state_overrides)
        if real_unknown_cost_decision:
            # Real ledger evidence: a previously covered synthetic day is
            # invalidated, with no priced import in its temporary store.
            when = datetime.fromtimestamp(fixture.FIXED_AFTERNOON.timestamp(), optimizer._tz)
            optimizer._import_topup_ledger.invalidate(when, "application_not_confirmed")
            with fixture.optimizer_time(fixture.FIXED_AFTERNOON):
                decision = optimizer._decide(state)
            self.assertTrue(decision.trace_gates["import_cost_floor_unknown"])
            self.assertFalse(decision.trace_gates["actual_import_cost_guard_blocking"])
            self.assertEqual(BATTERY_EXPORT, decision.export_intent)
            self.assertEqual(MODE_CMD_DISCHARGE_PV, decision.ems_mode)
            self.assertGreater(decision.export_limit, 0.01)
            if applied_discharge_limit is not None:
                decision.ess_discharge_limit = applied_discharge_limit
            self.latest_real_decision = decision
        else:
            decision = fixture._closed_decision(**(decision_overrides or {}))
        self.assertTrue(state.demand_window_observed)

        real_wait = optimizer._wait_for_exact_entity_state
        before_sensor_change = []
        after_msc_wait = False
        recursive_close_pending = False

        async def change_demand_during_msc_settlement(*args, **kwargs):
            nonlocal after_msc_wait
            self.assertEqual(cfg.ems_mode_select, args[0])
            self.assertEqual(MODE_MAX_SELF, args[1])
            before_sensor_change.extend(ha.calls)
            # This occurs after fallback's MSC request and export-close wait,
            # while its exact-MSC settlement wait is about to read fake HA.
            if demand_at_msc_wait is None:
                ha.state_values.pop(sensor, None)
                ha._state_value_metadata.pop(sensor, None)
            else:
                ha._record_state_value(sensor, demand_at_msc_wait)
                if updated_age_seconds is not None:
                    ha._state_value_metadata[sensor]["last_updated"] = (
                        datetime.fromtimestamp(fixture.FIXED_AFTERNOON.timestamp(), timezone.utc)
                        - timedelta(seconds=updated_age_seconds)
                    ).isoformat()
                if reported_age_seconds is not None:
                    ha._state_value_metadata[sensor]["last_reported"] = (
                        datetime.fromtimestamp(fixture.FIXED_AFTERNOON.timestamp(), timezone.utc)
                        - timedelta(seconds=reported_age_seconds)
                    ).isoformat()
            ha.fail_demand_metadata = fail_demand_metadata
            if conflict_newer_on:
                later = (
                    datetime.fromtimestamp(fixture.FIXED_AFTERNOON.timestamp(), timezone.utc)
                    + timedelta(milliseconds=1)
                ).isoformat()
                ha.demand_metadata_override = {
                    "entity_id": sensor, "state": "on",
                    "last_updated": later, "last_reported": later,
                }
            after_msc_wait = True
            return await real_wait(*args, **kwargs)

        optimizer._wait_for_exact_entity_state = change_demand_during_msc_settlement
        fallback_clock = (
            self._real_export_fallback_clock(
                optimizer, ha, fixture.FIXED_AFTERNOON,
                close_report_delay_ms=close_report_delay_ms,
            ) if real_unknown_cost_decision
            else fixture._automated_fallback_clock(optimizer, ha, fixture.FIXED_AFTERNOON)
        )
        with fallback_clock:
            ha._record_state_value(sensor, initial_demand)
            ha._record_state_value(cfg.grid_import_limit, initial_import_kw)
            bulk_states = ha.bulk_states

            async def change_during_final_joint_authority_read(entity_ids):
                nonlocal recursive_close_pending
                if after_msc_wait and sensor in entity_ids:
                    if takeover_on_recursive_close is not None:
                        recursive_close_pending = True
                    if fail_joint_read:
                        raise RuntimeError("simulated final joint read failure")
                    if late_demand_on_joint_read is not None:
                        if late_demand_on_joint_read == "__missing__":
                            ha.state_values.pop(sensor, None)
                            ha._state_value_metadata.pop(sensor, None)
                        else:
                            ha._record_state_value(sensor, late_demand_on_joint_read)
                    if late_takeover == "manual":
                        ha._record_state_value(cfg.sigenergy_mode_select, cfg.manual_option)
                    elif late_takeover == "remote_off":
                        ha._record_state_value(cfg.ha_control_switch, "off")
                    if late_export_reopen is not None:
                        ha._record_state_value(cfg.grid_export_limit, late_export_reopen)
                    if late_ems_change is not None:
                        ha._record_state_value(cfg.ems_mode_select, late_ems_change)
                elif recursive_close_pending and cfg.sigenergy_mode_select in entity_ids:
                    recursive_close_pending = False
                    if takeover_on_recursive_close == "manual":
                        ha._record_state_value(cfg.sigenergy_mode_select, cfg.manual_option)
                    elif takeover_on_recursive_close == "remote_off":
                        ha._record_state_value(cfg.ha_control_switch, "off")
                bulk = await bulk_states(entity_ids)
                if after_msc_wait and sensor in entity_ids and malformed_demand_bulk is not None:
                    bulk[sensor] = malformed_demand_bulk
                return bulk

            ha.bulk_states = change_during_final_joint_authority_read
            result = asyncio.run(optimizer._apply(state, decision))

        expected_demand = (
            demand_at_msc_wait if late_demand_on_joint_read is None
            else None if late_demand_on_joint_read == "__missing__"
            else late_demand_on_joint_read
        )
        self.assertEqual(expected_demand, ha.state_values.get(sensor))
        self.assertIn(
            ("select_option", cfg.ems_mode_select, MODE_MAX_SELF),
            before_sensor_change,
        )
        self.assertIn(
            ("set_number", cfg.grid_export_limit, 0.01),
            before_sensor_change,
        )
        self.assertFalse(any(
            method == "set_number" and entity == cfg.grid_import_limit
            and value > 0.011
            for method, entity, value in before_sensor_change
        ))
        self.assertFalse(result.succeeded)
        self.assertTrue(result.fallback_attempted)
        if late_export_reopen is None:
            self.assertEqual(0.01, ha.state_values[cfg.grid_export_limit])
        else:
            self.assertEqual(late_export_reopen, ha.state_values[cfg.grid_export_limit])
        if settle_msc and late_ems_change is None:
            self.assertEqual(MODE_MAX_SELF, ha.state_values[cfg.ems_mode_select])
        elif late_ems_change is not None:
            self.assertEqual(late_ems_change, ha.state_values[cfg.ems_mode_select])
        self.latest_real_optimizer = optimizer
        return cfg, ha, result, before_sensor_change

    def _assert_import_closed(self, cfg, ha, *, was_open=False) -> None:
        writes = [
            value for method, entity, value in ha.calls
            if method == "set_number" and entity == cfg.grid_import_limit
        ]
        self.assertFalse(any(value > 0.011 for value in writes))
        if was_open:
            self.assertIn(0.01, writes)
        self.assertLessEqual(float(ha.state_values[cfg.grid_import_limit]), 0.011)

    def _assert_current_demand_read(self, cfg, ha) -> None:
        self.assertTrue(any(
            cfg.demand_window_sensor in entities
            for entities in ha.bulk_state_calls
        ))

    def test_new_on_during_msc_settlement_closes_even_open_import(self) -> None:
        cfg, ha, result, _ = self._run_settled_fallback(
            "on", initial_import_kw=13.25
        )
        self._assert_import_closed(cfg, ha, was_open=True)
        self._assert_current_demand_read(cfg, ha)
        self.assertTrue(result.fallback_succeeded, result.error)

    def test_new_untrusted_demand_during_msc_settlement_keeps_import_closed(self) -> None:
        for report in ("unknown", "unavailable", "other", None):
            with self.subTest(report=report):
                cfg, ha, result, _ = self._run_settled_fallback(report)
                self._assert_import_closed(cfg, ha)
                self._assert_current_demand_read(cfg, ha)
                self.assertTrue(result.fallback_succeeded, result.error)

    def test_stale_and_invalid_future_off_cannot_reopen_import(self) -> None:
        for age in (361.0, -6.0):
            with self.subTest(age_seconds=age):
                cfg, ha, result, _ = self._run_settled_fallback(
                    "off", updated_age_seconds=age,
                    reported_age_seconds=age,
                )
                self._assert_import_closed(cfg, ha)
                self.assertTrue(result.fallback_succeeded, result.error)

    def test_steady_current_off_keeps_legitimate_normal_recovery(self) -> None:
        cfg, ha, result, _ = self._run_settled_fallback("off")
        self.assertEqual([13.25], [
            value for method, entity, value in ha.calls
            if method == "set_number" and entity == cfg.grid_import_limit
        ])
        self._assert_current_demand_read(cfg, ha)
        self.assertTrue(result.fallback_succeeded, result.error)

    def test_unknown_cost_export_candidate_still_obeys_late_demand_and_settlement(self) -> None:
        for late_demand, should_recover in (("on", False), ("unknown", False), ("off", True)):
            with self.subTest(late_demand=late_demand):
                cfg, ha, result, before = self._run_settled_fallback(
                    "off", late_demand_on_joint_read=late_demand,
                    real_unknown_cost_decision=True,
                )
                decision = self.latest_real_decision
                self.assertEqual(BATTERY_EXPORT, decision.export_intent)
                self.assertTrue(decision.trace_gates["import_cost_floor_unknown"])
                self.assertFalse(decision.trace_gates["actual_import_cost_guard_blocking"])
                self.assertIn(
                    ("set_number", cfg.grid_export_limit, decision.export_limit), ha.calls
                )
                self.assertIn(
                    "failed lowering export limit", result.error
                )
                requested_at, reported_at = self.latest_real_close_proof
                self.assertGreater(reported_at, requested_at)
                self.assertFalse(any(
                    method == "set_number" and entity == cfg.grid_import_limit and value > 0.011
                    for method, entity, value in before
                ))
                self._assert_current_demand_read(cfg, ha)
                writes = [
                    value for method, entity, value in ha.calls
                    if method == "set_number" and entity == cfg.grid_import_limit
                ]
                if should_recover:
                    self.assertEqual([13.25], writes)
                else:
                    self._assert_import_closed(cfg, ha)
                # Verified MSC and the later export-close report permit normal
                # house-serving ESS capability, without reopening export or
                # selecting a discharge EMS mode.
                self.assertIn(
                    ("set_number", cfg.ess_max_discharging_limit, 0.01), ha.calls
                )
                self.assertTrue(any(
                    method == "set_number" and entity == cfg.ess_max_discharging_limit
                    and value > 0.011
                    for method, entity, value in ha.calls
                ))
                self.assertEqual(25.0, ha.state_values[cfg.ess_max_discharging_limit])
                self.assertEqual(MODE_MAX_SELF, ha.state_values[cfg.ems_mode_select])
                self.assertEqual(0.01, ha.state_values[cfg.grid_export_limit])
                self.assertFalse(any(
                    method == "select_option" and entity == cfg.ems_mode_select
                    and value == MODE_CMD_DISCHARGE_PV
                    for method, entity, value in ha.calls
                ))
                self.assertFalse(result.succeeded)
                self.assertTrue(result.fallback_attempted)
                self.assertTrue(result.fallback_succeeded, result.error)

    def test_unknown_cost_export_candidate_cannot_bypass_takeover_or_unsettled_msc(self) -> None:
        cfg, ha, result, _ = self._run_settled_fallback(
            "off", late_takeover="manual", real_unknown_cost_decision=True,
        )
        self.assertFalse(any(
            method == "set_number" and entity == cfg.grid_import_limit
            for method, entity, _ in ha.calls
        ))
        self.assertFalse(result.fallback_succeeded)

        cfg, ha, result, _ = self._run_settled_fallback(
            "off", real_unknown_cost_decision=True, settle_msc=False,
        )
        self._assert_import_closed(cfg, ha)
        self.assertFalse(result.fallback_succeeded)

    def test_known_priced_floor_still_vetoes_when_cost_history_is_unknown(self) -> None:
        fixture = self.fixture
        optimizer = fixture.optimizer(self.ha_type(), cap_total_import=13.25)
        when = datetime.fromtimestamp(fixture.FIXED_AFTERNOON.timestamp(), optimizer._tz)
        optimizer._import_topup_ledger.invalidate(when, "application_not_confirmed")
        optimizer._state_store.record_optimizer_import_topup(
            date=when.date().isoformat(), ts=when.isoformat(),
            import_kwh=1.0, import_price=2.0, price_trusted=True,
        )
        state = fixture._automatic_apply_state(
            current_export_limit=0.01, battery_soc=70.0,
            battery_capacity_trusted=True, available_discharge_energy_kwh=21.0,
            feedin_price=1.10, feedin_price_cents=110.0,
            pv_kw=10.0, solar_power_now_kw=10.0, load_kw=1.0,
            forecast_remaining_observation_trusted=True,
        )
        with fixture.optimizer_time(fixture.FIXED_AFTERNOON):
            decision = optimizer._decide(state)
        self.assertTrue(decision.trace_gates["import_cost_floor_unknown"])
        self.assertEqual(2.0, decision.trace_values["today_highest_actual_import_price"])
        self.assertTrue(decision.trace_gates["actual_import_cost_guard_blocking"])
        self.assertEqual(EXPORT_BLOCKED, decision.export_intent)
        self.assertEqual(0.0, decision.export_limit)
        self.assertEqual(MODE_MAX_SELF, decision.ems_mode)

    def test_unchanged_off_with_correlated_recent_report_can_recover(self) -> None:
        # Demand uses 360 seconds, independent of the shorter inverter bound.
        cfg, ha, result, _ = self._run_settled_fallback(
            "off", updated_age_seconds=600.0,
            reported_age_seconds=300.0,
        )
        self.assertIn(("set_number", cfg.grid_import_limit, 13.25), ha.calls)
        self.assertTrue(any(
            cfg.demand_window_sensor in entities
            for entities in ha.report_metadata_calls
        ))
        self.assertTrue(result.fallback_succeeded, result.error)

    def test_failed_enrichment_uses_stale_change_time_conservatively(self) -> None:
        cfg, ha, result, _ = self._run_settled_fallback(
            "off", updated_age_seconds=361.0,
            reported_age_seconds=0.0, fail_demand_metadata=True,
        )
        self._assert_import_closed(cfg, ha)
        self.assertTrue(result.fallback_succeeded, result.error)

    def test_new_on_or_missing_during_final_joint_authority_read_blocks_import(self) -> None:
        for report in ("on", "unknown", "__missing__"):
            with self.subTest(report=report):
                cfg, ha, result, _ = self._run_settled_fallback(
                    "off", late_demand_on_joint_read=report,
                )
                self._assert_import_closed(cfg, ha)
                self.assertTrue(result.fallback_succeeded, result.error)

    def test_newer_conflicting_on_report_does_not_validate_cached_off(self) -> None:
        cfg, ha, result, _ = self._run_settled_fallback(
            "off", conflict_newer_on=True,
        )
        self._assert_import_closed(cfg, ha)
        self.assertTrue(result.fallback_succeeded, result.error)

    def test_initial_demand_on_never_relaxes_on_later_off(self) -> None:
        cfg, ha, result, _ = self._run_settled_fallback(
            "off", initial_demand="on", initial_import_kw=13.25,
        )
        self._assert_import_closed(cfg, ha, was_open=True)
        self.assertTrue(result.fallback_succeeded, result.error)

    def test_other_initial_import_owners_never_relax_on_current_off(self) -> None:
        for owner in ("standby_holdoff_active", "morning_dump_active"):
            with self.subTest(owner=owner):
                cfg, ha, result, _ = self._run_settled_fallback(
                    "off", initial_import_kw=13.25,
                    decision_overrides={owner: True},
                )
                self._assert_import_closed(cfg, ha, was_open=True)
                self.assertTrue(result.fallback_succeeded, result.error)

    def test_manual_or_remote_takeover_during_final_read_has_no_import_write(self) -> None:
        for takeover in ("manual", "remote_off"):
            with self.subTest(takeover=takeover):
                cfg, ha, result, _ = self._run_settled_fallback(
                    "on", initial_import_kw=13.25,
                    late_takeover=takeover,
                )
                self.assertFalse(any(
                    method == "set_number" and entity == cfg.grid_import_limit
                    for method, entity, _ in ha.calls
                ))
                self.assertFalse(result.fallback_succeeded)

    def test_demand_block_does_not_prevent_independent_ess_recovery(self) -> None:
        cfg, ha, result, _ = self._run_settled_fallback("on")
        self._assert_import_closed(cfg, ha)
        self.assertIn(
            ("set_number", cfg.ess_max_charging_limit, 25.0), ha.calls
        )
        self.assertIn(
            ("set_number", cfg.ess_max_discharging_limit, 25.0), ha.calls
        )
        self.assertTrue(result.fallback_succeeded, result.error)

    def test_malformed_current_demand_bulk_keeps_import_closed(self) -> None:
        for malformed in ("off", {"state": "off"}):
            with self.subTest(malformed=malformed):
                cfg, ha, result, _ = self._run_settled_fallback(
                    "off", malformed_demand_bulk=malformed,
                )
                self._assert_import_closed(cfg, ha)
                self.assertTrue(result.fallback_succeeded, result.error)

    def test_joint_read_failure_cannot_authorize_import(self) -> None:
        cfg, ha, result, _ = self._run_settled_fallback(
            "off", fail_joint_read=True,
        )
        self._assert_import_closed(cfg, ha)
        self.assertFalse(result.fallback_succeeded)

    def test_late_demand_close_failure_is_not_reported_as_safe_recovery(self) -> None:
        cfg, ha, result, _ = self._run_settled_fallback(
            "on", initial_import_kw=13.25, import_close_fails=True,
        )
        self.assertFalse(any(
            method == "set_number" and entity == cfg.grid_import_limit
            and value > 0.011
            for method, entity, value in ha.calls
        ))
        self.assertIn(("set_number", cfg.grid_import_limit, 0.01), ha.calls)
        self.assertEqual(13.25, ha.state_values[cfg.grid_import_limit])
        self.assertFalse(result.fallback_succeeded)
        self.assertIn("grid import", result.error)

    def test_takeover_during_recursive_safety_close_prevents_import_write(self) -> None:
        for takeover in ("manual", "remote_off"):
            with self.subTest(takeover=takeover):
                cfg, ha, result, _ = self._run_settled_fallback(
                    "on", initial_import_kw=13.25,
                    takeover_on_recursive_close=takeover,
                )
                self.assertFalse(any(
                    method == "set_number" and entity == cfg.grid_import_limit
                    for method, entity, _ in ha.calls
                ))
                self.assertEqual(13.25, ha.state_values[cfg.grid_import_limit])
                self.assertFalse(result.fallback_succeeded)


if __name__ == "__main__":
    unittest.main()
