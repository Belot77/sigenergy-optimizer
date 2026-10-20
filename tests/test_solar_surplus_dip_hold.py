"""Real decisions/ticks with synthetic live reports and simulated apply outcomes.

No inverter/HA services run. This proves bounded decision permission, not plant
response or the physical cause of the supplied incident's PV dips.
"""
from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

from app.models import HVACObservedValue, HVACSolarInputContext, MSC_SURPLUS_CEILING
from app.optimizer import MODE_MAX_SELF, SigEnergyOptimizer, _ActuatorApplicationResult, _MscTransition
from test_phase1_solar_dynamic_charge_ceiling_characterization import SolarDynamicChargeFixture
import test_solar_export_flapping_characterization as incident
from test_msc_baseline_overlay_contract import (
    ClockedRecordingHA, establish_observed_msc_baseline,
)


class SolarSurplusDipHoldTests(SolarDynamicChargeFixture):
    NORMAL_CHARGE_KW = 21.0
    _sample_state = incident.SolarExportFlappingCharacterizationTests._sample_state

    def optimizer_for_ticks(self, **overrides):
        optimizer = self._optimizer(_env_file=None, import_threshold_low=0.0, **overrides)
        optimizer._read_state = AsyncMock()
        optimizer._apply = AsyncMock(return_value=_ActuatorApplicationResult(succeeded=True))
        optimizer._evaluate_hvac_solar_permission = Mock(return_value=object())
        optimizer._publish_hvac_solar_permission = AsyncMock()
        optimizer._record_automation_audit = Mock()
        optimizer._handle_notifications = AsyncMock()
        optimizer._handle_daily_summaries = AsyncMock()
        optimizer._accumulate_history = Mock()
        optimizer._record_price_tracking = Mock()
        return optimizer

    def report_state(self, seconds, *, strong=False, report_seconds=None, **overrides):
        sample = incident.AUTOMATED_SAMPLES[0 if strong else 1]._replace(
            offset_seconds=seconds, export_readback_kw=25.0,
        )
        state = self._sample_state(sample)
        for key, value in overrides.items():
            setattr(state, key, value)
        stamp = (self.WHEN + timedelta(seconds=seconds if report_seconds is None else report_seconds)).timestamp()
        state._msc_ems_reported_at = stamp

        def observed(value):
            return HVACObservedValue(value=value, available=True, fresh=True, observed_at_ts=stamp)

        state.hvac_solar_inputs = HVACSolarInputContext(
            live_snapshot=True,
            pv_power=observed(state.pv_kw), load_power=observed(state.load_kw),
            battery_power=observed(state.battery_power_sensor_kw),
            grid_import_power=observed(state.grid_import_power_kw),
            grid_export_power=observed(state.grid_export_power_kw),
            control_mode=observed(state.sigenergy_mode),
            observed_ems_mode=observed(state.current_ems_mode),
            remote_ems_control=observed(state.ha_control_switch_state),
            observed_export_limit=observed(state.current_export_limit),
        )
        return state

    def tick(self, optimizer, state):
        optimizer._read_state.return_value = state
        with self.optimizer_time(state.timestamp):
            asyncio.run(optimizer._tick())
        return optimizer._last_decision

    def arm(self, optimizer):
        decision = self.tick(optimizer, self.report_state(0, strong=True))
        self.assertTrue(decision.solar_surplus_policy_active)
        self.assertIsNotNone(optimizer._solar_dip_proof)

    def assert_hold(self, decision):
        self.assertTrue(decision.trace_gates["solar_surplus_dip_hold_active"])
        self.assertTrue(decision.solar_surplus_policy_active)
        self.assertEqual(25.0, decision.export_limit)
        self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
        self.assertEqual(MSC_SURPLUS_CEILING, decision.export_intent)
        self.assertEqual("none", decision.trace_values["battery_export_owner"])
        self.assertEqual(21.0, decision.ess_charge_limit)
        self.assertFalse(decision.trace_gates["solar_charge_ceiling_owned"])

    def test_incident_power_sequence_retains_permission_with_new_strong_reports(self):
        optimizer = self.optimizer_for_ticks()
        limits = []
        for sample in incident.AUTOMATED_SAMPLES:
            state = self.report_state(
                sample.offset_seconds, pv_kw=sample.pv_kw,
                solar_power_now_kw=sample.pv_kw, load_kw=sample.load_kw,
                battery_soc=sample.soc,
                available_discharge_energy_kwh=sample.soc / 10.0,
                battery_power_sensor_kw=sample.battery_kw,
                grid_export_power_kw=sample.grid_export_kw,
            )
            # Readbacks model the corrected successful 25 kW permission,
            # rather than replaying the original controller's closures.
            decision = self.tick(optimizer, state)
            limits.append(decision.export_limit)
            if sample.requested_export_kw == 0.0:
                self.assert_hold(decision)
            self.assertEqual([], optimizer.ha.calls)
        self.assertEqual([25.0] * 14, limits)

    def test_persistent_low_closes_at_exact_source_deadline_and_cannot_self_renew(self):
        optimizer = self.optimizer_for_ticks()
        self.arm(optimizer)
        for seconds in (3, 6, 9, 12, 14.999):
            with self.subTest(seconds=seconds):
                self.assert_hold(self.tick(optimizer, self.report_state(seconds)))
                self.assertEqual((self.WHEN.timestamp(),) * 2, optimizer._solar_dip_proof)
        decision = self.tick(optimizer, self.report_state(15))
        self.assertEqual(0.0, decision.export_limit)
        self.assertFalse(decision.solar_surplus_policy_active)
        self.assertIsNone(optimizer._solar_dip_proof)
        self.assertEqual(0.0, self.tick(optimizer, self.report_state(18)).export_limit)
        self.assertTrue(self.tick(optimizer, self.report_state(21, strong=True)).solar_surplus_policy_active)

    def test_cached_high_and_midband_samples_cannot_renew_proof(self):
        for cached in (True, False):
            with self.subTest(cached=cached):
                optimizer = self.optimizer_for_ticks()
                self.arm(optimizer)
                for seconds in (4, 8, 12):
                    state = self.report_state(seconds, strong=True, report_seconds=0) if cached else self.report_state(
                        seconds, pv_kw=1.3, solar_power_now_kw=1.3, load_kw=1.0,
                    )
                    self.tick(optimizer, state)
                self.assertEqual((self.WHEN.timestamp(),) * 2, optimizer._solar_dip_proof)
                self.assertEqual(0.0, self.tick(optimizer, self.report_state(15)).export_limit)

    def test_no_successful_proof_after_restart_or_decision_only(self):
        for seed_decision in (False, True):
            with self.subTest(seed_decision=seed_decision):
                optimizer = self.optimizer_for_ticks()
                if seed_decision:
                    optimizer._last_decision = self.decide(optimizer, self.report_state(0, strong=True), self.WHEN)
                self.assertEqual(0.0, self.tick(optimizer, self.report_state(6)).export_limit)

    def test_failure_pending_exception_and_cancel_clear_proof_despite_old_decision(self):
        cases = (
            _ActuatorApplicationResult(succeeded=False),
            _ActuatorApplicationResult(succeeded=False, transition_pending=True),
            RuntimeError("simulated application error"), asyncio.CancelledError(),
        )
        for result in cases:
            with self.subTest(result=type(result).__name__, pending=getattr(result, "transition_pending", False)):
                optimizer = self.optimizer_for_ticks()
                self.arm(optimizer)
                if isinstance(result, BaseException):
                    optimizer._apply.side_effect = result
                else:
                    optimizer._apply.return_value = result
                with self.assertRaises((RuntimeError, asyncio.CancelledError)):
                    self.tick(optimizer, self.report_state(6))
                self.assertIsNone(optimizer._solar_dip_proof)
                self.assertEqual(8.0, optimizer._solar_dip_wait_seconds(self.WHEN.timestamp() + 7))
                optimizer._apply.side_effect = None
                optimizer._apply.return_value = _ActuatorApplicationResult(succeeded=True)
                self.assertEqual(0.0, self.tick(optimizer, self.report_state(7)).export_limit)
                self.assertIsNone(optimizer._solar_dip_wait_seconds(self.WHEN.timestamp() + 7))

    def test_hard_gate_losses_clear_hold_immediately(self):
        cases = (
            {"pv_power_trusted": False}, {"load_power_trusted": False},
            {"pv_load_observations_coherent": False}, {"battery_soc_trusted": False},
            {"battery_capacity_trusted": False}, {"sun_state_observation_trusted": False},
            {"sunset_observation_trusted": False}, {"forecast_remaining_observation_trusted": False},
            {"forecast_remaining_kwh": 0.0}, {"solcast_detailed_source_trusted": False},
            {"feedin_price": 0.009, "feedin_price_cents": 0.9},
            {"battery_power_sensor_kw": -0.100001}, {"battery_power_sensor_kw": None},
            {"grid_import_power_kw": 0.100001}, {"grid_export_power_kw": None},
            {"sigenergy_mode": "Manual"}, {"sigenergy_mode": "Force Full Export"},
            {"sigenergy_mode_observed": False}, {"ems_mode_observed": False},
            {"current_ems_mode": "Command Discharging (PV First)"},
            {"ha_control_enabled": False}, {"ha_control_switch_state": "off"},
            {"current_export_limit": 0.01}, {"current_export_limit_observed": False},
            {"current_export_limit": 10.0},
        )
        for overrides in cases:
            with self.subTest(overrides=overrides):
                optimizer = self.optimizer_for_ticks()
                self.arm(optimizer)
                decision = self.tick(optimizer, self.report_state(6, **overrides))
                self.assertFalse(decision.solar_surplus_policy_active)
                self.assertFalse(decision.trace_gates["solar_surplus_dip_hold_active"])
                self.assertIsNone(optimizer._solar_dip_proof)

    def test_timestamp_skew_missing_future_and_regression_reject_hold(self):
        for kind in ("missing", "future", "skew", "regression", "clock"):
            with self.subTest(kind=kind):
                optimizer = self.optimizer_for_ticks()
                self.arm(optimizer)
                state = self.report_state(6 if kind != "clock" else -1)
                observation = state.hvac_solar_inputs.pv_power
                stamp = {"missing": None, "future": self.WHEN.timestamp() + 7,
                         "skew": self.WHEN.timestamp(), "regression": self.WHEN.timestamp() - 1,
                         "clock": self.WHEN.timestamp() - 1}[kind]
                state.hvac_solar_inputs = replace(state.hvac_solar_inputs, pv_power=replace(observation, observed_at_ts=stamp))
                self.assertEqual(0.0, self.tick(optimizer, state).export_limit)
                self.assertIsNone(optimizer._solar_dip_proof)

    def test_held_ceiling_cannot_increase_and_lower_authoritative_cap_wins(self):
        for configured, authoritative, expected in ((40.0, 50.0, 25.0), (10.0, 50.0, 10.0), (25.0, 12.0, 12.0)):
            with self.subTest(configured=configured, authoritative=authoritative):
                optimizer = self.optimizer_for_ticks()
                self.arm(optimizer)
                optimizer.cfg.export_limit_high = configured
                state = self.report_state(6, grid_export_limit_entity_max_kw=authoritative)
                self.assertEqual(expected, self.tick(optimizer, state).export_limit)

    def test_pending_transition_and_websocket_epoch_invalidate_hold(self):
        for event in ("transition", "disconnect", "connect"):
            with self.subTest(event=event):
                optimizer = self.optimizer_for_ticks()
                self.arm(optimizer)
                if event == "transition":
                    optimizer._msc_transition = _MscTransition()
                else:
                    getattr(optimizer, "on_ws_" + event)()
                self.assertEqual(0.0, self.tick(optimizer, self.report_state(6)).export_limit)

    def test_hold_deadline_bounds_quiet_wait_and_event_debounce(self):
        optimizer = self.optimizer_for_ticks()
        self.arm(optimizer)
        self.assert_hold(self.tick(optimizer, self.report_state(14)))
        self.assertEqual(1.0, optimizer._solar_dip_wait_seconds(self.WHEN.timestamp() + 14))
        with self.optimizer_time(self.WHEN + timedelta(seconds=15)):
            asyncio.run(asyncio.wait_for(optimizer._drain_queue(3.0), timeout=0.05))
        self.assertEqual(3.0, optimizer._solar_dip_wait_seconds(self.WHEN.timestamp() + 15))

    def test_application_completion_cannot_refresh_an_already_expired_source(self):
        optimizer = self.optimizer_for_ticks()
        state = self.report_state(0, strong=True)
        decision = self.decide(optimizer, state, self.WHEN)
        with self.optimizer_time(self.WHEN + timedelta(seconds=15)):
            optimizer._commit_solar_dip_proof(state, decision, _ActuatorApplicationResult(succeeded=True))
        self.assertIsNone(optimizer._solar_dip_proof)

    def test_dispatch_rejects_hold_when_clock_crosses_deadline(self):
        optimizer = self.optimizer_for_ticks()
        self.arm(optimizer)
        state = self.report_state(6)
        self.assert_hold(self.tick(optimizer, state))
        with self.optimizer_time(self.WHEN + timedelta(seconds=15)):
            self.assertFalse(optimizer._solar_dip_dispatch_current(state))

    def test_missing_or_stale_provenance_cannot_be_replaced_by_available_booleans(self):
        for field in ("control_mode", "observed_ems_mode", "remote_ems_control",
                      "observed_export_limit", "pv_power", "load_power", "battery_power",
                      "grid_import_power", "grid_export_power"):
            for missing in (True, False):
                with self.subTest(field=field, missing=missing):
                    optimizer = self.optimizer_for_ticks()
                    self.arm(optimizer)
                    state = self.report_state(6)
                    observation = getattr(state.hvac_solar_inputs, field)
                    replacement = replace(observation, observed_at_ts=None) if missing else replace(observation, fresh=False)
                    state.hvac_solar_inputs = replace(state.hvac_solar_inputs, **{field: replacement})
                    self.assertEqual(0.0, self.tick(optimizer, state).export_limit)
                    self.assertIsNone(optimizer._solar_dip_proof)

    def test_only_advancing_paired_reports_can_rearm_after_invalidation(self):
        optimizer = self.optimizer_for_ticks()
        self.arm(optimizer)
        optimizer.on_ws_disconnect()
        self.tick(optimizer, self.report_state(3, strong=True, report_seconds=0))
        self.assertIsNone(optimizer._solar_dip_proof)
        state = self.report_state(4, strong=True)
        state.hvac_solar_inputs = replace(state.hvac_solar_inputs, load_power=replace(
            state.hvac_solar_inputs.load_power, observed_at_ts=self.WHEN.timestamp(),
        ))
        self.tick(optimizer, state)
        self.assertIsNone(optimizer._solar_dip_proof)
        self.tick(optimizer, self.report_state(5, strong=True))
        self.assertEqual((self.WHEN.timestamp() + 5,) * 2, optimizer._solar_dip_proof)

    def test_demand_import_block_and_independent_ess_restrictions_survive_hold(self):
        optimizer = self.optimizer_for_ticks()
        self.arm(optimizer)
        optimizer.cfg.ess_charge_limit_value = 0.4
        optimizer.cfg.ess_discharge_limit_value = 0.0
        decision = self.tick(optimizer, self.report_state(6, demand_window_active=True))
        self.assertTrue(decision.trace_gates["solar_surplus_dip_hold_active"])
        self.assertEqual(0.0, decision.import_limit)
        self.assertEqual(0.4, decision.ess_charge_limit)
        self.assertEqual(0.0, decision.ess_discharge_limit)

    def test_real_apply_expiry_requests_safety_close_at_each_awaited_exit(self):
        async def check(optimizer, boundary):
            optimizer._apply = SigEnergyOptimizer._apply.__get__(optimizer)
            ha = ClockedRecordingHA()
            await establish_observed_msc_baseline(self, optimizer, ha, self.WHEN)
            state = self.report_state(6, grid_export_limit_entity_max_kw=12.0 if boundary.startswith("readback_") else 25.0)
            clock = [self.WHEN + timedelta(seconds=6)]

            class ReportDateTime(datetime):
                @classmethod
                def now(cls, tz=None):
                    return datetime.fromtimestamp(clock[0].timestamp(), tz)

            with patch("app.optimizer.datetime", ReportDateTime):
                decision = optimizer._decide(state)
                self.assertTrue(decision.trace_gates["solar_surplus_dip_hold_active"])
                if boundary == "solar_charge":
                    self.assertTrue(decision.trace_gates["solar_charge_ceiling_owned"])
                original = ha.set_number

                async def cross_deadline(entity, value):
                    if entity == "number.test_charge" and boundary in ("solar_charge", "failed_charge", "post_helpers"):
                        clock[0] = self.WHEN + timedelta(seconds=15)
                        if boundary == "failed_charge":
                            return False
                    return await original(entity, value)

                ha.set_number = cross_deadline
                original_select = ha.select_option

                async def later_select(entity, value):
                    clock[0] += timedelta(milliseconds=1)
                    return await original_select(entity, value)

                ha.select_option = later_select
                if boundary.startswith("readback_"):
                    ha._record_state_value(optimizer.cfg.grid_export_limit, 5.0 if boundary == "readback_reduced" else 0.01)
                if boundary == "pre_charge":
                    original_authority = optimizer._read_control_authority
                    reads = 0

                    async def delayed_authority(*args, **kwargs):
                        nonlocal reads
                        result = await original_authority(*args, **kwargs)
                        reads += 1
                        if reads == 2:
                            clock[0] = self.WHEN + timedelta(seconds=15)
                        return result

                    optimizer._read_control_authority = delayed_authority
                result = await optimizer._apply(state, decision)
            self.assertFalse(result.succeeded)
            self.assertTrue(result.fallback_attempted, (result.error, ha.calls))
            closes = [value for action, entity, value in ha.calls
                      if action == "set_number" and entity == optimizer.cfg.grid_export_limit]
            self.assertIn(0.01, closes)
            if boundary.startswith("readback_"):
                self.assertNotIn(12.0, closes)
                self.assertTrue(decision.trace_gates["solar_surplus_dip_dispatch_rejected"])
            self.assertIsNone(optimizer._solar_dip_proof)
        for boundary in ("pre_charge", "solar_charge", "failed_charge", "post_helpers",
                         "readback_reduced", "readback_closed"):
            with self.subTest(boundary=boundary):
                optimizer = self.optimizer_for_ticks(ess_max_charging_limit="number.test_charge")
                if boundary == "solar_charge":
                    baseline = self.report_state(0, strong=True)
                    baseline.solcast_provider_polled = (self.WHEN - timedelta(seconds=60)).astimezone().isoformat()
                    self.decide(optimizer, baseline, self.WHEN)
                self.arm(optimizer)
                asyncio.run(check(optimizer, boundary))

    def test_failed_closure_keeps_bounded_deadline_retry_without_busy_loop(self):
        optimizer = self.optimizer_for_ticks()
        self.arm(optimizer)
        optimizer._apply.return_value = _ActuatorApplicationResult(succeeded=False)
        with self.assertRaises(RuntimeError):
            self.tick(optimizer, self.report_state(6))
        # A quiet-wait timeout calls the tick directly, before querying the
        # deadline helper again. Failure must still schedule the next retry.
        with self.assertRaises(RuntimeError):
            self.tick(optimizer, self.report_state(15))
        self.assertEqual(3.0, optimizer._solar_dip_wait_seconds(self.WHEN.timestamp() + 15))
        optimizer._apply.return_value = _ActuatorApplicationResult(succeeded=True)
        self.assertEqual(0.0, self.tick(optimizer, self.report_state(18)).export_limit)
        self.assertIsNone(optimizer._solar_dip_wait_seconds(self.WHEN.timestamp() + 18))
