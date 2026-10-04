from __future__ import annotations

import asyncio
import copy
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from app.ha_ws_client import HAWebSocketClient
from haos49_characterization_helpers import Haos49CharacterizationCase, RecordingHA
import test_phase1_solar_dynamic_charge_ceiling_characterization as charge_fixture
import test_phase1_forecast_solar_clock_telemetry_trust_characterization as forecast_fixture


class SolcastProviderFreshnessTests(Haos49CharacterizationCase):
    WHEN = charge_fixture.Phase1SolarDynamicChargeCeilingCharacterizationTests.WHEN
    PERIOD_HOURS = charge_fixture.Phase1SolarDynamicChargeCeilingCharacterizationTests.PERIOD_HOURS
    NORMAL_CHARGE_KW = charge_fixture.Phase1SolarDynamicChargeCeilingCharacterizationTests.NORMAL_CHARGE_KW
    SAFETY_FACTOR = charge_fixture.Phase1SolarDynamicChargeCeilingCharacterizationTests.SAFETY_FACTOR
    _optimizer = charge_fixture.Phase1SolarDynamicChargeCeilingCharacterizationTests._optimizer
    _state = charge_fixture.Phase1SolarDynamicChargeCeilingCharacterizationTests._state
    _detailed_forecast = charge_fixture.Phase1SolarDynamicChargeCeilingCharacterizationTests._detailed_forecast

    @staticmethod
    def iso(at):
        return datetime.fromtimestamp(at.timestamp(), timezone.utc).isoformat()

    def observe(self, opt, *, now=None, polled=None, deadline=None, **changes):
        now = now or self.WHEN
        state = self._state()
        state.solcast_provider_polled = self.iso(polled or self.WHEN)
        state.solcast_provider_next_update = self.iso(deadline or (self.WHEN + timedelta(hours=1)))
        state.solcast_provider_source = (opt.cfg.forecast_today_sensor, opt.cfg.solcast_api_last_polled_sensor)
        state.solcast_provider_epoch = opt._solar_provider_epoch
        state.solcast_provider_continuity = True
        for key, value in changes.items():
            setattr(state, key, value)
        return state, self.decide(opt, state, now)

    def valid(self, opt, deadline=None):
        self.observe(opt, polled=self.WHEN - timedelta(minutes=1), deadline=deadline)
        return self.observe(opt, deadline=deadline)

    def test_cached_startup_and_unchanged_poll_never_grant_authority(self):
        opt = self._optimizer()
        for _ in range(2):
            _, d = self.observe(opt)
            self.assertEqual("UNVERIFIED", d.trace_values["solar_provider_state"])
            self.assertEqual(self.NORMAL_CHARGE_KW, d.ess_charge_limit)
        _, d = self.observe(opt, now=self.WHEN + timedelta(seconds=1), polled=self.WHEN + timedelta(seconds=1))
        self.assertEqual("VALID", d.trace_values["solar_provider_state"])
        self.assertTrue(d.trace_gates["solar_charge_ceiling_owned"])

    def test_old_parent_metadata_does_not_revoke_verified_provider(self):
        opt = self._optimizer()
        self.valid(opt)
        _, d = self.observe(opt, forecast_today_observation_trusted=False)
        self.assertTrue(d.trace_gates["solar_charge_ceiling_owned"])
        self.assertFalse(d.trace_gates["forecast_today_observation_trusted"])

    def test_missed_deadline_and_schedule_slide_restore_normal_request(self):
        opt = self._optimizer()
        due = self.WHEN + timedelta(minutes=10)
        self.valid(opt, due)
        _, d = self.observe(opt, now=due, deadline=due + timedelta(days=1))
        self.assertEqual("EXPIRED", d.trace_values["solar_provider_state"])
        self.assertEqual(self.NORMAL_CHARGE_KW, d.ess_charge_limit)
        self.assertTrue(d.solar_surplus_policy_active)
        self.assertEqual(self.iso(due), d.trace_values["solar_provider_deadline"])

    def test_schedule_later_does_not_extend_and_earlier_shortens(self):
        opt = self._optimizer()
        due = self.WHEN + timedelta(minutes=10)
        self.valid(opt, due)
        _, d = self.observe(opt, deadline=due + timedelta(hours=1))
        self.assertEqual(self.iso(due), d.trace_values["solar_provider_deadline"])
        earlier = due - timedelta(minutes=5)
        _, d = self.observe(opt, deadline=earlier)
        self.assertEqual(self.iso(earlier), d.trace_values["solar_provider_deadline"])
        _, d = self.observe(opt, now=earlier, deadline=earlier)
        self.assertEqual("EXPIRED", d.trace_values["solar_provider_state"])

    def test_manual_success_one_second_before_due_does_not_forgive_due(self):
        opt = self._optimizer()
        due = self.WHEN + timedelta(minutes=10)
        self.valid(opt, due)
        early = due - timedelta(seconds=1)
        _, d = self.observe(opt, now=early, polled=early, deadline=due + timedelta(hours=1))
        self.assertEqual("VALID", d.trace_values["solar_provider_state"])
        self.assertEqual(self.iso(due), d.trace_values["solar_provider_deadline"])
        _, d = self.observe(opt, now=due, polled=early, deadline=due + timedelta(hours=1))
        self.assertEqual("EXPIRED", d.trace_values["solar_provider_state"])

    def test_success_at_or_after_due_can_discharge_obligation(self):
        for offset in (0, 1):
            with self.subTest(offset=offset):
                opt = self._optimizer()
                due = self.WHEN + timedelta(minutes=10)
                self.valid(opt, due)
                success = due + timedelta(seconds=offset)
                future = due + timedelta(hours=1)
                _, d = self.observe(opt, now=success, polled=success, deadline=future)
                self.assertEqual("VALID", d.trace_values["solar_provider_state"])
                self.assertEqual(self.iso(future), d.trace_values["solar_provider_deadline"])

    def test_tolerated_future_clock_skew_cannot_discharge_deadline_early(self):
        opt = self._optimizer()
        due = self.WHEN + timedelta(minutes=10)
        self.valid(opt, due)
        _, d = self.observe(opt, now=due - timedelta(seconds=1), polled=due, deadline=due + timedelta(hours=1))
        self.assertEqual(self.iso(due), d.trace_values["solar_provider_deadline"])
        _, d = self.observe(opt, now=due, polled=due, deadline=due + timedelta(hours=1))
        self.assertEqual("EXPIRED", d.trace_values["solar_provider_state"])

    def test_rejected_new_generation_is_consumed_and_cannot_repair_unchanged(self):
        opt = self._optimizer()
        self.valid(opt)
        later = self.WHEN + timedelta(seconds=1)
        self.observe(opt, now=later, polled=later, solcast_detailed=[])
        _, repaired = self.observe(opt, now=later, polled=later)
        self.assertFalse(repaired.trace_gates["solar_provider_authority_trusted"])
        next_poll = later + timedelta(seconds=1)
        _, d = self.observe(opt, now=next_poll, polled=next_poll)
        self.assertTrue(d.trace_gates["solar_provider_authority_trusted"])

    def test_missing_or_due_schedule_never_renews(self):
        for raw in (None, "unknown", "bad", "2026-01-15T15:00:00", self.iso(self.WHEN)):
            with self.subTest(raw=raw):
                opt = self._optimizer()
                self.valid(opt)
                later = self.WHEN + timedelta(seconds=1)
                _, d = self.observe(opt, now=later, polled=later, solcast_provider_next_update=raw)
                self.assertFalse(d.trace_gates["solar_provider_authority_trusted"])

    def test_timestamp_safety_and_future_equality_boundary(self):
        for raw in (None, "unavailable", "nan", "bad", "2026-01-15T14:00:00", self.iso(self.WHEN + timedelta(seconds=5.01))):
            with self.subTest(raw=raw):
                opt = self._optimizer()
                self.valid(opt)
                _, d = self.observe(opt, solcast_provider_polled=raw)
                self.assertFalse(d.trace_gates["solar_provider_authority_trusted"])
        opt = self._optimizer()
        self.valid(opt)
        _, d = self.observe(opt, polled=self.WHEN + timedelta(seconds=5))
        self.assertTrue(d.trace_gates["solar_provider_authority_trusted"])

    def test_regression_invalidates_and_rebaselines(self):
        opt = self._optimizer()
        self.valid(opt)
        _, d = self.observe(opt, polled=self.WHEN - timedelta(seconds=1))
        self.assertFalse(d.trace_gates["solar_provider_authority_trusted"])
        _, d = self.observe(opt)
        self.assertEqual("UNVERIFIED", d.trace_values["solar_provider_state"])
        _, d = self.observe(opt, now=self.WHEN + timedelta(seconds=1), polled=self.WHEN + timedelta(seconds=1))
        self.assertEqual("VALID", d.trace_values["solar_provider_state"])

    def test_payload_protections_fail_closed(self):
        detail = self._detailed_forecast([6.0] + [3.0] * 7)
        cases = []
        for estimate in (float("nan"), float("inf"), -1.0, True):
            bad = copy.deepcopy(detail)
            bad[0]["pv_estimate"] = estimate
            cases.append({"solcast_detailed": bad})
        cases.extend([
            {"solcast_detailed": [detail[0]] + detail},
            {"solcast_detailed": detail[:2] + detail[3:]},
            {"solcast_detailed": detail[1:]},
            {"solcast_detailed": detail[:-1]},
            {"solcast_detailed": list(reversed(detail))},
            {"solcast_detailed": self._detailed_forecast([6.0] * 8, when=self.WHEN - timedelta(days=1))},
            {"solcast_detailed_source_trusted": False},
            {"next_sunset_ts": (self.WHEN + timedelta(days=1)).timestamp()},
        ])
        for delta in (-0.5, 0.5):
            bad = copy.deepcopy(detail)
            bad[2]["period_start"] = self.iso(self.WHEN + timedelta(hours=1, seconds=delta))
            cases.append({"solcast_detailed": bad})
        bad = copy.deepcopy(detail)
        bad[0]["period_start"] = "2026-01-15T14:00:00"
        cases.append({"solcast_detailed": bad})
        for changes in cases:
            with self.subTest(changes=changes):
                opt = self._optimizer()
                self.observe(opt, polled=self.WHEN - timedelta(seconds=1))
                _, d = self.observe(opt, **changes)
                self.assertFalse(d.trace_gates["solar_provider_authority_trusted"])
                self.assertEqual(self.NORMAL_CHARGE_KW, d.ess_charge_limit)

    def test_final_daytime_poll_can_retain_tomorrow_deadline_but_not_roll_day(self):
        opt = self._optimizer()
        tomorrow = self.WHEN + timedelta(days=1)
        _, d = self.valid(opt, tomorrow)
        self.assertTrue(d.trace_gates["solar_provider_authority_trusted"])
        _, d = self.observe(opt, now=tomorrow, deadline=tomorrow + timedelta(hours=1))
        self.assertFalse(d.trace_gates["solar_provider_authority_trusted"])

    def test_disconnect_reconnect_requires_baseline_then_new_poll(self):
        opt = self._optimizer()
        self.valid(opt)
        epoch = opt._solar_provider_epoch
        opt.on_ws_disconnect()
        opt.on_ws_connect()
        self.assertGreater(opt._solar_provider_epoch, epoch)
        _, d = self.observe(opt)
        self.assertEqual("UNVERIFIED", d.trace_values["solar_provider_state"])
        _, d = self.observe(opt, now=self.WHEN + timedelta(seconds=1), polled=self.WHEN + timedelta(seconds=1))
        self.assertTrue(d.trace_gates["solar_provider_authority_trusted"])

    def test_source_reassignment_invalidates_and_updates_shared_watch_set(self):
        opt = self._optimizer()
        self.valid(opt)
        watched = opt.get_watch_entities()
        opt.cfg.solcast_api_last_polled_sensor = "sensor.other_last_polled"
        opt.refresh_config_time_warnings()
        self.assertIn("sensor.other_last_polled", watched)
        _, d = self.observe(opt)
        self.assertEqual("UNVERIFIED", d.trace_values["solar_provider_state"])

    def test_in_flight_snapshot_cannot_enter_new_epoch(self):
        opt = self._optimizer()
        self.valid(opt)
        old_epoch = opt._solar_provider_epoch
        opt.on_ws_disconnect()
        opt.on_ws_connect()
        _, d = self.observe(opt, polled=self.WHEN + timedelta(seconds=1), solcast_provider_epoch=old_epoch)
        self.assertFalse(d.trace_gates["solar_provider_authority_trusted"])
        _, d = self.observe(opt)
        self.assertEqual("UNVERIFIED", d.trace_values["solar_provider_state"])

    def test_preapply_check_restores_selected_normal_request_at_exact_deadline(self):
        opt = self._optimizer()
        due = self.WHEN + timedelta(minutes=10)
        state, d = self.valid(opt, due)
        opt._recheck_solar_charge_authority(state, d, due.timestamp())
        self.assertFalse(d.trace_gates["solar_charge_ceiling_owned"])
        self.assertEqual(self.NORMAL_CHARGE_KW, d.ess_charge_limit)
        self.assertEqual("normal", d.trace_values["ess_charge_limit_owner"])

    def test_unavailable_available_signal_survives_full_queue(self):
        async def check():
            opt = self._optimizer()
            self.valid(opt)
            opt.trigger_queue = asyncio.Queue(maxsize=1)
            opt.trigger_queue.put_nowait("sensor.unrelated")
            client = HAWebSocketClient("http://example", "test", opt.trigger_queue, opt.get_watch_entities(), on_state_observation=opt.on_provider_state_observation)
            epoch = opt._solar_provider_epoch
            good = {"state": "40", "attributes": {"detailedForecast": self._state().solcast_detailed}}
            for old, new in ((good, {"state": "unavailable"}), ({"state": "unavailable"}, good)):
                await client._handle_message({"type": "event", "event": {"event_type": "state_changed", "data": {"entity_id": opt.cfg.forecast_today_sensor, "old_state": old, "new_state": new}}})
            self.assertGreater(opt._solar_provider_epoch, epoch)
            _, d = self.observe(opt)
            self.assertEqual("UNVERIFIED", d.trace_values["solar_provider_state"])
        asyncio.run(check())

    def test_deadline_wakes_existing_loop_without_event_or_heartbeat(self):
        async def check():
            opt = self._optimizer()
            real_now = datetime.now()
            due = real_now + timedelta(seconds=0.04)
            opt._solar_provider_state = "VALID"
            opt._solar_provider_deadline = due.timestamp()
            opt._solar_provider_day = datetime.now(opt._tz).date()
            opt._tick = AsyncMock()
            times = []
            async def stop():
                times.append(datetime.now().timestamp())
                opt._running = False
            opt._safe_tick = AsyncMock(side_effect=stop)
            with patch("app.optimizer._HEARTBEAT_INTERVAL", 60):
                await asyncio.wait_for(opt.run_forever(), timeout=0.4)
            self.assertEqual(1, len(times))
            self.assertGreaterEqual(times[0], due.timestamp())
            self.assertLess(times[0] - due.timestamp(), 0.2)
        asyncio.run(check())

    def read_fixture(self, opt):
        reader = forecast_fixture.Phase1ForecastSolarClockTelemetryTrustCharacterizationTests()
        ha = RecordingHA()
        opt.ha = ha
        opt._ws_connected = True
        opt._tz = timezone(self.WHEN.astimezone().utcoffset() or timedelta())
        ha.states = reader._states(
            opt, when=self.WHEN, detailed_forecast=self._state().solcast_detailed,
            forecast_today_observed_at=self.WHEN - timedelta(hours=2),
            pv_kw=6.0, feedin_price=0.05,
        )
        ha.states[opt.cfg.rated_capacity_sensor]["state"] = 10.0
        ha.states[opt.cfg.available_discharge_sensor]["state"] = 6.0
        ha.states[opt.cfg.forecast_today_sensor]["attributes"]["dataCorrect"] = False
        ha.states[opt.cfg.solcast_api_last_polled_sensor] = {
            "state": self.iso(self.WHEN - timedelta(minutes=1)),
            "attributes": {
                "next_auto_update": self.iso(self.WHEN + timedelta(hours=1)),
                "last_attempt": self.iso(self.WHEN),
            },
        }
        return ha

    def test_actual_read_keeps_old_today_trust_and_provider_contract_separate(self):
        async def check():
            opt = self._optimizer()
            ha = self.read_fixture(opt)
            with self.optimizer_time(self.WHEN):
                baseline = await opt._read_state()
                self.assertFalse(opt._decide(baseline).trace_gates["solar_provider_authority_trusted"])
                ha.states[opt.cfg.solcast_api_last_polled_sensor]["state"] = self.iso(self.WHEN)
                state = await opt._read_state()
                d = opt._decide(state)
            self.assertFalse(state.forecast_today_observation_trusted)
            self.assertTrue(state.forecast_remaining_observation_trusted)
            self.assertTrue(d.trace_gates["solar_provider_authority_trusted"])
            self.assertTrue(d.trace_gates["solar_charge_ceiling_owned"])
            self.assertIn(opt.cfg.solcast_api_last_polled_sensor, ha.bulk_state_calls[0])
            # Advancing last_attempt or schedule alone cannot renew authority.
            ha.states[opt.cfg.solcast_api_last_polled_sensor]["attributes"].update(
                next_auto_update=self.iso(self.WHEN + timedelta(days=1)),
                last_attempt=self.iso(self.WHEN + timedelta(hours=1)),
            )
            with self.optimizer_time(self.WHEN + timedelta(hours=1)):
                d = opt._decide(await opt._read_state())
            self.assertFalse(d.trace_gates["solar_provider_authority_trusted"])
        asyncio.run(check())

    def test_actual_in_flight_read_is_rejected_after_disconnect(self):
        async def check():
            opt = self._optimizer()
            ha = self.read_fixture(opt)
            read_started = asyncio.Event()
            release = asyncio.Event()
            original = ha.bulk_states
            async def blocked(ids):
                snapshot = copy.deepcopy(await original(ids))
                read_started.set()
                await release.wait()
                return snapshot
            ha.bulk_states = blocked
            with self.optimizer_time(self.WHEN):
                task = asyncio.create_task(opt._read_state())
                await read_started.wait()
                old_epoch = opt._solar_provider_epoch
                opt.on_ws_disconnect()
                opt.on_ws_connect()
                release.set()
                state = await task
                d = opt._decide(state)
            self.assertEqual(old_epoch, state.solcast_provider_epoch)
            self.assertFalse(d.trace_gates["solar_provider_source_continuity_trusted"])
            self.assertFalse(opt._solar_provider_baselined)
        asyncio.run(check())

    def test_pending_ws_poll_advance_is_validated_by_coherent_read(self):
        opt = self._optimizer()
        self.observe(opt, polled=self.WHEN - timedelta(minutes=1))
        with self.optimizer_time(self.WHEN):
            opt.on_provider_state_observation(
                opt.cfg.solcast_api_last_polled_sensor,
                {"state": self.iso(self.WHEN - timedelta(minutes=1))},
                {"state": self.iso(self.WHEN), "attributes": {"next_auto_update": self.iso(self.WHEN + timedelta(hours=1))}},
            )
        _, d = self.observe(opt)
        self.assertTrue(d.trace_gates["solar_provider_authority_trusted"])

    def test_coalesced_ws_regression_and_reload_cannot_keep_authority(self):
        for new in (None, {"state": "unavailable"}, {"state": self.iso(self.WHEN - timedelta(seconds=1))}, {"state": "malformed"}):
            with self.subTest(new=new):
                opt = self._optimizer()
                state, d = self.valid(opt)
                with self.optimizer_time(self.WHEN):
                    opt.on_provider_state_observation(opt.cfg.solcast_api_last_polled_sensor, {"state": self.iso(self.WHEN)}, new)
                opt._recheck_solar_charge_authority(state, d, self.WHEN.timestamp())
                self.assertEqual(self.NORMAL_CHARGE_KW, d.ess_charge_limit)
                _, d = self.observe(opt)
                self.assertEqual("UNVERIFIED", d.trace_values["solar_provider_state"])

    def test_rejected_high_water_cannot_be_bypassed_by_intermediate_poll(self):
        opt = self._optimizer()
        self.valid(opt)
        rejected = self.WHEN + timedelta(seconds=2)
        self.observe(opt, now=rejected, polled=rejected, solcast_detailed=[])
        _, d = self.observe(opt, now=rejected, polled=self.WHEN + timedelta(seconds=1))
        self.assertFalse(d.trace_gates["solar_provider_authority_trusted"])
        self.assertEqual("provider_timestamp_regressed", d.trace_values["solar_provider_reason"])

    def test_ws_shortened_deadline_is_binding_before_rest_re_read(self):
        opt = self._optimizer()
        state, d = self.valid(opt)
        polled = self.iso(self.WHEN)
        with self.optimizer_time(self.WHEN):
            opt.on_provider_state_observation(
                opt.cfg.solcast_api_last_polled_sensor,
                {"state": polled},
                {"state": polled, "attributes": {"next_auto_update": polled}},
            )
        opt._recheck_solar_charge_authority(state, d, self.WHEN.timestamp())
        self.assertEqual("EXPIRED", d.trace_values["solar_provider_state"])
        self.assertEqual(self.NORMAL_CHARGE_KW, d.ess_charge_limit)

    def test_deadline_interrupts_three_second_debounce(self):
        async def check():
            opt = self._optimizer()
            due = datetime.now() + timedelta(seconds=0.04)
            opt._solar_provider_state = "VALID"
            opt._solar_provider_deadline = due.timestamp()
            opt._solar_provider_day = datetime.now(opt._tz).date()
            opt.trigger_queue.put_nowait("sensor.price")
            opt._tick = AsyncMock()
            called = []
            async def stop():
                called.append(datetime.now().timestamp())
                opt._running = False
            opt._safe_tick = AsyncMock(side_effect=stop)
            await asyncio.wait_for(opt.run_forever(), timeout=0.4)
            self.assertLess(called[0] - due.timestamp(), 0.2)
        asyncio.run(check())

    def test_midnight_wake_precedes_tomorrow_advertised_deadline(self):
        opt = self._optimizer()
        opt._tz = timezone.utc
        now = datetime(2026, 1, 15, 23, 59, 59, tzinfo=timezone.utc)
        opt._solar_provider_state = "VALID"
        opt._solar_provider_deadline = (now + timedelta(hours=12)).timestamp()
        self.assertEqual(1.0, opt._solar_provider_wait_seconds(now.timestamp()))

    def test_actual_apply_rechecks_after_await_and_restores_normal_charge(self):
        async def check():
            for discontinuity in (False, True):
                with self.subTest(discontinuity=discontinuity):
                    opt = self._optimizer(ess_max_charging_limit="number.test_charge")
                    state, d = self.valid(opt)
                    state.current_export_limit = d.export_limit
                    state.current_import_limit = 1.0
                    ha = RecordingHA(state_values={opt.cfg.ems_mode_select: "Maximum Self Consumption"})
                    opt.ha = ha
                    original_set_number = ha.set_number
                    async def pending_import(entity, value):
                        if entity != opt.cfg.grid_import_limit:
                            return await original_set_number(entity, value)
                        if discontinuity:
                            opt.on_ws_disconnect()
                        else:
                            opt._solar_provider_deadline = self.WHEN.timestamp()
                        return await original_set_number(entity, value)
                    # Cross an async actuator step preceding the charge write.
                    ha.set_number = pending_import
                    with self.optimizer_time(self.WHEN):
                        result = await opt._apply(state, d)
                    self.assertTrue(result.succeeded, result.error)
                    writes = [value for action, entity, value in ha.calls if action == "set_number" and entity == "number.test_charge"]
                    self.assertEqual([self.NORMAL_CHARGE_KW], writes)
                    self.assertFalse(d.trace_gates["solar_charge_ceiling_owned"])
        asyncio.run(check())

    def test_no_busy_retry_when_source_is_unavailable_or_deadline_read_fails(self):
        opt = self._optimizer()
        state = self._state()
        state.solcast_provider_epoch = opt._solar_provider_epoch
        state.solcast_provider_source = opt._solar_provider_source
        state.solcast_provider_continuity = False
        self.decide(opt, state, self.WHEN)
        self.assertFalse(opt._solar_provider_urgent)
        opt._solar_provider_state = "VALID"
        opt._solar_provider_deadline = self.WHEN.timestamp()
        self.assertEqual(0, opt._solar_provider_wait_seconds(self.WHEN.timestamp()))
        self.assertIsNone(opt._solar_provider_wait_seconds(self.WHEN.timestamp()))

    def test_in_flight_reduced_charge_write_is_restored_in_same_application(self):
        async def check():
            opt = self._optimizer(ess_max_charging_limit="number.test_charge")
            state, d = self.valid(opt)
            state.current_export_limit = d.export_limit
            state.current_import_limit = d.import_limit
            ha = RecordingHA(state_values={opt.cfg.ems_mode_select: "Maximum Self Consumption"})
            opt.ha = ha
            original = ha.set_number
            async def cross_deadline(entity, value):
                result = await original(entity, value)
                if entity == "number.test_charge" and value == 0.0:
                    opt._solar_provider_deadline = self.WHEN.timestamp()
                return result
            ha.set_number = cross_deadline
            with self.optimizer_time(self.WHEN):
                result = await opt._apply(state, d)
            self.assertTrue(result.succeeded, result.error)
            writes = [value for action, entity, value in ha.calls if action == "set_number" and entity == "number.test_charge"]
            self.assertEqual([0.0, self.NORMAL_CHARGE_KW], writes)
            self.assertFalse(d.trace_gates["solar_charge_ceiling_owned"])
        asyncio.run(check())
