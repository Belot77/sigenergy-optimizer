"""Synthetic policy checkpoints with real reader, decision, tick and application.

This is deliberately not an energy-physics or complete-day replay. Fresh HA
snapshots explicitly prescribe SoC, available energy, measured flows and forecast
curves at selected times. Services only queue requests; later reads deliver the
scripted reports on the same advancing wall/monotonic clock. No production
control, qualification, authority or settlement helper is replaced.
"""
from __future__ import annotations

import asyncio
import os
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch

from app.models import BATTERY_EXPORT, EXPORT_BLOCKED, MSC_SURPLUS_CEILING
from app.optimizer import MODE_CMD_DISCHARGE_PV, MODE_MAX_SELF
from haos49_characterization_helpers import Haos49CharacterizationCase, RecordingHA
import test_evening_boost_reserve_trust_characterization as evening_fixtures
import test_phase1_forecast_solar_clock_telemetry_trust_characterization as reader_fixtures


class LifecycleClock:
    def __init__(self, when):
        self.start = when
        self.wall = when
        self.elapsed = 1000.0

    def advance_to(self, when):
        delta = (when - self.wall).total_seconds()
        if delta < 0:
            raise AssertionError("lifecycle clock must advance")
        self.elapsed += delta
        self.wall = when

    def report(self):
        self.advance_to(self.wall + timedelta(milliseconds=1))
        return datetime.fromtimestamp(self.wall.timestamp(), timezone.utc).isoformat()


class LifecycleReportingHA(RecordingHA):
    """Accepted requests and explicitly scheduled post-request reports differ."""

    def __init__(self, clock):
        super().__init__(settle_numbers=False, settle_selects=False)
        self.clock = clock
        self.pending = {}
        self.reports = []
        self.requests = []

    def deliver(self, entities):
        for entity in entities:
            if entity in self.pending:
                value, requested_at = self.pending.pop(entity)
                reported = self.clock.report()
                unchanged = self.state_values.get(entity) == value
                updated = self._state_value_metadata.get(entity, {}).get("last_updated")
                self.state_values[entity] = value
                self._state_value_metadata[entity] = {
                    "last_updated": updated if unchanged and updated else reported,
                    "last_reported": reported,
                }
                self.reports.append((entity, value, requested_at, self.clock.wall.timestamp()))

    async def set_number(self, entity, value):
        self.calls.append(("set_number", entity, value))
        requested_at = self.clock.wall.timestamp()
        self.requests.append((entity, value, requested_at))
        self.pending[entity] = (value, requested_at)
        return True

    async def select_option(self, entity, value):
        self.calls.append(("select_option", entity, value))
        requested_at = self.clock.wall.timestamp()
        self.requests.append((entity, value, requested_at))
        self.pending[entity] = (value, requested_at)
        return True

    async def bulk_states(self, entities):
        self.deliver(entities)
        return await super().bulk_states(entities)

    async def get_state_value(self, entity, default=""):
        self.deliver([entity])
        if entity in self.state_values:
            return self.state_values[entity]
        return self.states.get(entity, {}).get("state", default)

    async def get_state_report_metadata(self, entities):
        self.deliver(entities)
        metadata = {}
        for entity in entities:
            if entity in self.state_values:
                obj = {"state": self.state_values[entity], **self._state_value_metadata[entity]}
            else:
                obj = self.states.get(entity)
            if isinstance(obj, dict):
                metadata[entity] = {"entity_id": entity, **obj}
        return metadata


class CrossPolicyControlLifecycleTests(Haos49CharacterizationCase):
    START = datetime(2026, 1, 15, 6)
    # The inherited fixture seeds once through this time. Never create future
    # afternoon ledger rows before the first morning checkpoint.
    FIXED_AFTERNOON = START

    def setUp(self):
        environment = patch.dict(os.environ, {}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        super().setUp()
        # Each scenario has one isolated, non-persistent ledger/store.
        os.environ["STATE_DB_PATH"] = ":memory:"
        self.clock = LifecycleClock(self.START)
        self.ha = LifecycleReportingHA(self.clock)
        # Fix this synthetic day's local offset before the inherited helper's
        # single accounting seed. Platform ZoneInfo availability must not shift
        # the seed to a different day; this is not a DST scenario.
        local_tz = timezone(self.START.astimezone().utcoffset() or timedelta())
        with patch("app.optimizer.ZoneInfo", return_value=local_tz):
            self.optimizer = self.optimizer_factory()
        self.assertEqual(local_tz, self.optimizer._tz)
        # Model an uninterrupted fake HA observation connection. Provider
        # baseline/advancing generations still run through the real reader.
        self.optimizer._ws_connected = True
        self.reader = reader_fixtures.Phase1ForecastSolarClockTelemetryTrustCharacterizationTests()
        self.evening = evening_fixtures.EveningBoostReserveTrustCharacterizationTests()
        self.applications = []
        self.guard_ids = tuple(id(guard) for guard in (
            self.optimizer._solar_budget_reentry, self.optimizer._solar_charge_reentry,
        ))

    def optimizer_factory(self):
        return super().optimizer(
            ha=self.ha, _env_file=None, morning_dump_enabled=True,
            morning_dump_min_soc=15.0, morning_slow_charge_enabled=True,
            morning_slow_charge_until="11:00", morning_slow_charge_rate_kw=2.0,
            solar_surplus_bypass_enabled=True,
            solar_surplus_fill_deadline_margin_minutes=60.0,
            evening_boost_enabled=True,
            evening_boost_min_tomorrow_forecast_kwh=100.0,
        )

    def prepare(self, when, *, pv=0.0, soc=80.0, load=1.0, mode="Automated", load_age=0, load_raw=None):
        # Explicit synthetic inactive samples bridge skipped checkpoints using
        # the same real ledger, rather than granting an import-cost trust mock.
        previous = self.clock.wall
        source = self.optimizer._import_topup_source()
        while previous + timedelta(seconds=60) < when:
            previous += timedelta(seconds=60)
            self.optimizer._import_topup_ledger.record(
                now=previous.astimezone(self.optimizer._tz), source=source,
                daily_import_kwh=0.0, grid_import_kw=0.0, import_price=0.30,
                price_trusted=True, import_active=False,
            )
        self.clock.advance_to(when)
        cfg = self.optimizer.cfg
        states = self.evening._fixture_states(self.optimizer, when, load_kw=load, feedin_price=0.05)
        for entity, value in (
            (cfg.pv_power_sensor, pv), (cfg.solar_power_now_sensor, pv),
            (cfg.grid_export_power_sensor, max(0.0, pv - load)),
            (cfg.battery_soc_sensor, soc),
            (cfg.available_discharge_sensor, soc * 0.30),
            (cfg.daily_import_energy, 0.0),
        ):
            attrs = {"unit_of_measurement": "kWh"} if entity == cfg.available_discharge_sensor else {}
            states[entity] = self.reader._entity(value, when, attrs)
        states[cfg.consumed_power_sensor] = self.reader._entity(
            load if load_raw is None else load_raw, when,
            observed_at=when - timedelta(seconds=load_age),
        )
        states[cfg.solcast_api_last_polled_sensor] = self.reader._entity(
            self.reader._aware_iso(when - timedelta(seconds=1)), when,
            {"next_auto_update": self.reader._aware_iso(when + timedelta(hours=1))},
        )
        # Periodic reports of previous actuator settings do not assume the next
        # command's outcome. Only deliver() can report a queued new request.
        for entity, default in (
            (cfg.grid_export_limit, 0.01), (cfg.grid_import_limit, 0.01),
            (cfg.ess_max_charging_limit, 25.0), (cfg.ess_max_discharging_limit, 25.0),
            (cfg.pv_max_power_limit, 25.0), (cfg.ems_mode_select, MODE_MAX_SELF),
            (cfg.ha_control_switch, "on"), (cfg.sigenergy_mode_select, mode),
        ):
            value = mode if entity == cfg.sigenergy_mode_select else self.ha.state_values.get(entity, default)
            unchanged = self.ha.state_values.get(entity) == value
            updated = self.ha._state_value_metadata.get(entity, {}).get("last_updated")
            self.ha.state_values[entity] = value
            self.ha._state_value_metadata[entity] = {
                "last_updated": updated if unchanged and updated else self.reader._aware_iso(when),
                "last_reported": self.reader._aware_iso(when),
            }
        for entity, obj in states.items():
            previous_obj = self.ha.states.get(entity)
            if entity == cfg.consumed_power_sensor and load_age:
                continue
            if (previous_obj and previous_obj.get("state") == obj.get("state")
                    and previous_obj.get("attributes") == obj.get("attributes")):
                obj["last_updated"] = previous_obj["last_updated"]
        self.ha.states = states

    def tick(self, when, *, pending=False, **snapshot):
        self.prepare(when, **snapshot)
        clock = self.clock

        class SharedDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime.fromtimestamp(clock.wall.timestamp(), tz)

        with ExitStack() as stack:
            stack.enter_context(patch("app.optimizer.datetime", SharedDateTime))
            stack.enter_context(patch("app.optimizer.monotonic", side_effect=lambda: clock.elapsed))
            # Keep control and import accounting genuine; suppress only outbound
            # publications/notifications and unrelated history/audit recording.
            for name in ("_publish_hvac_solar_permission", "_handle_notifications", "_handle_daily_summaries"):
                stack.enter_context(patch.object(self.optimizer, name, new=AsyncMock()))
            for name in ("_record_automation_audit", "_accumulate_history", "_record_price_tracking"):
                stack.enter_context(patch.object(self.optimizer, name, new=Mock()))
            stack.enter_context(patch.object(
                self.optimizer, "_record_application_trace",
                side_effect=lambda s, d, result=None, **kw: self.applications.append((s, d, result)),
            ))
            if pending:
                with self.assertRaisesRegex(RuntimeError, "MSC transition awaiting"):
                    asyncio.run(self.optimizer._tick())
            else:
                asyncio.run(self.optimizer._tick())
        self.assertEqual(self.guard_ids, tuple(id(guard) for guard in (
            self.optimizer._solar_budget_reentry, self.optimizer._solar_charge_reentry,
        )))
        state, decision, result = self.applications[-1]
        self.assertTrue(state.hvac_solar_inputs.live_snapshot)
        self.assertIsNotNone(state.load_power_trusted)
        if pending:
            self.assertFalse(result.succeeded)
            self.assertTrue(result.automatic_transition_pending)
        else:
            self.assertTrue(result.succeeded, result.error)
        return state, decision, result

    def assert_outputs(self, decision, *, owner, intent, ems, export, charge):
        self.assertEqual((owner, intent, ems, export, 0.0, charge, 25.0, 25.0), (
            decision.trace_values["battery_export_final_owner"], decision.export_intent,
            decision.ems_mode, decision.export_limit, decision.import_limit,
            decision.ess_charge_limit, decision.ess_discharge_limit,
            decision.pv_max_power_limit,
        ))

    def test_shared_instance_dump_slow_solar_then_boost_qualifies_with_unknown_history(self):
        _, dump, result = self.tick(self.START)
        self.assertTrue(dump.morning_dump_active)
        self.assertTrue(result.automatic_application_completed)
        self.assert_outputs(dump, owner="morning_dump", intent=BATTERY_EXPORT,
                            ems=MODE_CMD_DISCHARGE_PV, export=25.0, charge=25.0)
        cfg = self.optimizer.cfg
        before = len(self.ha.calls)
        _, closing, _ = self.tick(self.START.replace(hour=8), pv=6.0, pending=True)
        self.assertTrue(closing.morning_slow_charge_active)
        self.assertTrue(closing.trace_gates["import_cost_floor_trusted"])
        self.assertEqual(dump, self.optimizer.last_decision)
        close_calls = self.ha.calls[before:]
        self.assertIn(("set_number", cfg.grid_export_limit, 0.01), close_calls)
        self.assertNotIn(("set_number", cfg.grid_export_limit, 25.0), close_calls)
        self.assertNotIn(("select_option", cfg.ems_mode_select, MODE_MAX_SELF), close_calls)
        before = len(self.ha.calls)
        self.tick(self.START.replace(hour=8, second=3), pv=6.0, pending=True)
        msc_calls = self.ha.calls[before:]
        self.assertIn(("select_option", cfg.ems_mode_select, MODE_MAX_SELF), msc_calls)
        self.assertNotIn(("set_number", cfg.grid_export_limit, 25.0), msc_calls)
        _, slow, _ = self.tick(self.START.replace(hour=8, second=6), pv=6.0)
        self.assertTrue(slow.morning_slow_charge_active)
        self.assertTrue(slow.trace_gates["import_cost_floor_unknown"])
        self.assert_outputs(slow, owner="none", intent=MSC_SURPLUS_CEILING,
                            ems=MODE_MAX_SELF, export=25.0, charge=2.0)
        self.assertTrue(self.ha.reports)
        for entity, value, requested_at, reported_at in self.ha.reports:
            self.assertGreater(reported_at, requested_at, (entity, value))
        _, solar, _ = self.tick(self.START.replace(hour=12), pv=6.0)
        self.assertTrue(solar.solar_surplus_policy_active)
        self.assert_outputs(solar, owner="none", intent=MSC_SURPLUS_CEILING,
                            ems=MODE_MAX_SELF, export=25.0, charge=0.0)
        self.assertTrue(solar.trace_gates["solar_charge_ceiling_owned"])
        evening = self.START.replace(hour=19, minute=18)
        for elapsed in (0, 30, 60, 90, 120, 121):
            _, decision, result = self.tick(evening + timedelta(seconds=elapsed), load=0.0)
            self.assertTrue(result.automatic_application_completed)
            self.assertTrue(decision.evening_export_boost_active)
            self.assertTrue(decision.trace_gates["import_cost_floor_unknown"])
            self.assertTrue(decision.trace_gates["actual_import_cost_guard_active"])
            self.assertFalse(decision.trace_gates["actual_import_cost_guard_blocking"])
            self.assertIn("warning", decision.trace_values["actual_import_cost_guard_reason"].lower())
            self.assertTrue(decision.trace_gates["evening_boost_reentry_candidate"])
            if elapsed == 120:
                # Fake HA acknowledges at +1 ms, so the monotonic interval is
                # still just under 120 seconds despite 120 s of load reports.
                self.assertLess(decision.trace_values["evening_boost_reentry_elapsed_seconds"], 120.0)
            if elapsed < 121:
                self.assert_outputs(decision, owner="none", intent=EXPORT_BLOCKED,
                                    ems=MODE_MAX_SELF, export=0.0, charge=25.0)
                self.assertFalse(decision.trace_gates["evening_boost_reentry_allowed"])
            else:
                self.assert_outputs(decision, owner="evening_export_boost", intent=BATTERY_EXPORT,
                                    ems=MODE_CMD_DISCHARGE_PV, export=4.5, charge=25.0)
                self.assertTrue(decision.trace_gates["evening_boost_reentry_allowed"])
            self.assertTrue(decision.trace_gates["evening_boost_reentry_application_retained"])

    def test_real_boost_admission_manual_freeze_and_observed_msc_return(self):
        evening = self.START.replace(hour=19, minute=18)
        for elapsed in (0, 30, 60, 90, 120):
            state, decision, result = self.tick(evening + timedelta(seconds=elapsed), load=0.0)
            self.assertTrue(state.load_power_trusted)
            # Unchanged zero load has old last_updated but advancing correlated
            # State-object last_reported; the real reader must accept the latter.
            load_obj = self.ha.states[self.optimizer.cfg.consumed_power_sensor]
            self.assertEqual(self.reader._aware_iso(evening), load_obj["last_updated"])
            self.assertEqual((evening + timedelta(seconds=elapsed)).timestamp(),
                             state.hvac_solar_inputs.load_power.observed_at_ts)
            self.assertTrue(result.automatic_application_completed)
            if elapsed < 120:
                self.assert_outputs(decision, owner="none", intent=EXPORT_BLOCKED,
                                    ems=MODE_MAX_SELF, export=0.0, charge=25.0)
            else:
                self.assert_outputs(decision, owner="evening_export_boost", intent=BATTERY_EXPORT,
                                    ems=MODE_CMD_DISCHARGE_PV, export=4.5, charge=25.0)
            self.assertTrue(decision.trace_gates["evening_boost_reentry_application_retained"])
        self.assertEqual("admitted", self.optimizer._evening_boost_reentry.phase)
        before = len(self.ha.calls)
        _, manual, result = self.tick(evening + timedelta(seconds=125), load=0.0, mode="Manual")
        self.assertFalse(result.automatic_application_completed)
        self.assertEqual("closed", self.optimizer._evening_boost_reentry.phase)
        writes = [call for call in self.ha.calls[before:] if call[0] in {
            "set_number", "select_option", "turn_on", "set_input_number", "set_input_text",
        }]
        self.assertEqual([], writes)
        self.assertFalse(manual.trace_gates["evening_boost_reentry_application_retained"])
        # Returning from observed Manual cannot reuse admission. The existing
        # close -> later close report -> MSC -> later MSC report barrier remains.
        self.tick(evening + timedelta(seconds=130), load=0.0, pending=True)
        self.tick(evening + timedelta(seconds=133), load=0.0, pending=True)
        _, returned, result = self.tick(evening + timedelta(seconds=136), load=0.0)
        self.assertTrue(result.automatic_application_completed)
        self.assert_outputs(returned, owner="none", intent=EXPORT_BLOCKED,
                            ems=MODE_MAX_SELF, export=0.0, charge=25.0)
        self.assertFalse(returned.trace_gates["evening_boost_reentry_allowed"])
        self.assertTrue(returned.trace_gates["import_cost_floor_unknown"])

    def test_stale_and_unknown_reader_reports_reset_qualification_before_recovery(self):
        evening = self.START.replace(hour=19, minute=18)
        for elapsed in (0, 30):
            _, decision, result = self.tick(evening + timedelta(seconds=elapsed), load=0.0)
            self.assertTrue(result.automatic_application_completed)
            self.assertTrue(decision.trace_gates["evening_boost_reentry_application_retained"])
        for elapsed, changes in (
            (60, {"load_age": 7200}), (90, {}), (120, {"load_raw": "unknown"}),
        ):
            state, decision, _ = self.tick(evening + timedelta(seconds=elapsed), load=0.0, **changes)
            self.assertEqual(not changes, state.load_power_trusted)
            self.assert_outputs(decision, owner="none", intent=EXPORT_BLOCKED,
                                ems=MODE_MAX_SELF, export=0.0, charge=25.0)
            if changes:
                self.assertEqual("closed", self.optimizer._evening_boost_reentry.phase)
                self.assertFalse(decision.trace_gates["evening_boost_reentry_application_retained"])
        for elapsed in (150, 180, 210, 240, 271):
            _, decision, result = self.tick(evening + timedelta(seconds=elapsed), load=0.0)
            self.assertTrue(result.automatic_application_completed)
            self.assertEqual(elapsed == 271, decision.export_intent == BATTERY_EXPORT)
            self.assertTrue(decision.trace_gates["evening_boost_reentry_application_retained"])
        self.assert_outputs(decision, owner="evening_export_boost", intent=BATTERY_EXPORT,
                            ems=MODE_CMD_DISCHARGE_PV, export=4.5, charge=25.0)
