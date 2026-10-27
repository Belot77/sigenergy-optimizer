from __future__ import annotations

import asyncio
import unittest
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from app.models import BATTERY_EXPORT, EXPORT_BLOCKED
from app.optimizer import MODE_MAX_SELF
import app.optimizer as optimizer_module
import haos49_characterization_helpers as shared_fixtures
import test_evening_boost_reserve_trust_characterization as reserve_fixtures


class ReportingActuatorHA(shared_fixtures.RecordingHA):
    """Service acceptance and later explicitly delivered reports stay separate."""

    def __init__(self, clock):
        super().__init__(settle_numbers=False, settle_selects=False)
        self.clock = clock
        self.pending = {}

    def deliver(self, entity_ids):
        for entity in entity_ids:
            if entity not in self.pending:
                continue
            self.clock[0] += timedelta(milliseconds=1)
            self.state_values[entity] = self.pending.pop(entity)
            reported = self.clock[0].isoformat()
            self._state_value_metadata[entity] = {
                "last_updated": reported, "last_reported": reported,
            }

    async def set_number(self, entity, value):
        self.calls.append(("set_number", entity, value))
        self.pending[entity] = value
        return True

    async def select_option(self, entity, value):
        self.calls.append(("select_option", entity, value))
        self.pending[entity] = value
        return True

    async def bulk_states(self, entity_ids):
        self.deliver(entity_ids)
        return await super().bulk_states(entity_ids)

    async def get_state_value(self, entity, default=""):
        self.deliver([entity])
        return await super().get_state_value(entity, default)

    async def get_state_report_metadata(self, entity_ids):
        self.deliver(entity_ids)
        return {
            entity: {"entity_id": entity, "state": self.state_values[entity],
                     **self._state_value_metadata[entity]}
            for entity in entity_ids if entity in self.state_values
        }


class EveningBoostReentryStabilityTests(unittest.TestCase):
    START = datetime(2026, 1, 15, 19, 18)
    KNOWN_EMPTY_IMPORT_HISTORY = {
        "today_import_topup_kwh": 0.0,
        "today_highest_actual_import_price": None,
        "import_cost_export_floor": None,
        "import_cost_floor_trusted": True,
        "import_cost_floor_unknown": False,
        "import_history_complete": True,
    }

    def setUp(self) -> None:
        self.fixture = reserve_fixtures.EveningBoostReserveTrustCharacterizationTests()
        self.fixture.setUp()
        self.optimizer = self.new_optimizer()
        self.optimizer._tz = timezone(self.START.astimezone().utcoffset() or timedelta())

    def tearDown(self) -> None:
        self.fixture.tearDown()

    def new_optimizer(self):
        # Use the real admission gate even if narrow legacy policy fixtures mock it.
        optimizer = self.fixture.optimizer(
            evening_boost_enabled=True,
            evening_boost_min_tomorrow_forecast_kwh=100.0,
            evening_boost_min_feedin_price=0.01,
        )
        # Admission timing tests isolate reentry behavior from persisted cost
        # history, which is covered by the dedicated veto test below.
        optimizer._optimizer_import_topup_summary_today = (
            lambda: dict(self.KNOWN_EMPTY_IMPORT_HISTORY)
        )
        return optimizer

    def prepare(self, elapsed: float, *, load_kw: float = 0.0,
                report_elapsed=None, feedin_price=0.15, mutate=None):
        when = self.START + timedelta(seconds=elapsed)
        report_when = self.START + timedelta(
            seconds=elapsed if report_elapsed is None else report_elapsed
        )
        self.optimizer.ha.states = self.fixture._fixture_states(
            self.optimizer, report_when, load_kw=load_kw, feedin_price=feedin_price
        )
        if mutate is not None:
            mutate(self.optimizer.ha.states, self.optimizer.cfg, when)
        return when

    def decide(self, elapsed: float, *, clock=None, **kwargs):
        when = self.prepare(elapsed, **kwargs)
        with self.fixture.optimizer_time(when), patch(
            "app.optimizer.monotonic",
            return_value=elapsed if clock is None else clock, create=True
        ):
            state = asyncio.run(self.optimizer._read_state())
            decision = self.optimizer._decide(state)
        return state, decision

    def tick(self, elapsed: float, *, outcome=None, **kwargs):
        when = self.prepare(elapsed, **kwargs)

        async def apply(state, decision):
            if callable(outcome):
                return outcome(state, decision)
            return outcome or optimizer_module._ActuatorApplicationResult(
                succeeded=True, automatic_application_completed=True
            )

        with ExitStack() as stack:
            stack.enter_context(self.fixture.optimizer_time(when))
            stack.enter_context(patch("app.optimizer.monotonic", return_value=elapsed))
            stack.enter_context(patch.object(self.optimizer, "_apply", side_effect=apply))
            for name in ("_publish_hvac_solar_permission", "_handle_notifications",
                         "_handle_daily_summaries"):
                stack.enter_context(patch.object(self.optimizer, name, new=AsyncMock()))
            for name in ("_record_application_trace", "_record_automation_audit",
                         "_accumulate_history", "_record_price_tracking"):
                stack.enter_context(patch.object(self.optimizer, name, new=Mock()))
            asyncio.run(self.optimizer._tick())
        return self.optimizer.last_decision

    def qualify(self):
        for elapsed in (0, 30, 60, 90):
            self.assert_waiting(self.tick(elapsed))
        admitted = self.tick(120)
        self.assertEqual(BATTERY_EXPORT, admitted.export_intent)
        return admitted

    def real_tick(self, elapsed, *, mutate=None):
        """Exercise the real reader, tick and application against fake services."""
        when = self.prepare(elapsed, mutate=mutate)
        meter = self.optimizer.cfg.daily_import_energy
        self.optimizer.ha.states[meter] = {
            "entity_id": meter,
            "state": "0",
            "attributes": {},
            "last_updated": when.isoformat(),
            "last_reported": when.isoformat(),
        }
        clock = self.optimizer.ha.clock
        clock[0] = datetime.fromtimestamp(when.timestamp(), timezone.utc)

        class ReportClock(datetime):
            @classmethod
            def now(cls, tz=None):
                return (clock[0].astimezone(tz) if tz else
                        datetime.fromtimestamp(clock[0].timestamp()))

        with ExitStack() as stack:
            stack.enter_context(patch("app.optimizer.datetime", ReportClock))
            stack.enter_context(patch("app.optimizer.monotonic", return_value=elapsed))
            for name in ("_publish_hvac_solar_permission", "_handle_notifications",
                         "_handle_daily_summaries"):
                stack.enter_context(patch.object(self.optimizer, name, new=AsyncMock()))
            for name in ("_record_application_trace", "_record_automation_audit",
                         "_accumulate_history", "_record_price_tracking"):
                stack.enter_context(patch.object(self.optimizer, name, new=Mock()))
            try:
                asyncio.run(self.optimizer._tick())
            except RuntimeError as error:
                self.assertIn("MSC transition awaiting", str(error))
        return self.optimizer.last_decision

    def assert_waiting(self, decision) -> None:
        self.assertEqual(EXPORT_BLOCKED, decision.export_intent)
        self.assertEqual(0.0, decision.export_limit)
        self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
        self.assertEqual("none", decision.trace_values.get("battery_export_final_owner"))

    def test_initial_qualification_withholds_boost_export(self) -> None:
        state, decision = self.decide(0)
        self.assertTrue(state.load_power_trusted)
        self.assertTrue(state.sunrise_observation_trusted)
        self.assertTrue(decision.evening_export_boost_active)
        self.assert_waiting(decision)
        self.assertTrue(decision.trace_gates.get("evening_boost_reentry_waiting"))

    def test_repeated_cached_load_reports_cannot_complete_qualification(self) -> None:
        for elapsed in (0, 30, 60, 90, 119):
            with self.subTest(elapsed=elapsed):
                _state, decision = self.decide(elapsed, report_elapsed=0)
                self.assert_waiting(decision)

    def test_five_second_load_alternation_never_reacquires_boost(self) -> None:
        for index in range(26):
            elapsed = index * 5
            load_kw = 1.6 if index % 2 == 0 else 1.7
            with self.subTest(elapsed=elapsed, load_kw=load_kw):
                _state, decision = self.decide(elapsed, load_kw=load_kw)
                self.assertNotEqual(BATTERY_EXPORT, decision.export_intent)
                self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
                self.assertEqual(0.0, decision.export_limit)

    def test_fresh_unchanged_values_admit_at_exact_120_second_boundary(self) -> None:
        for elapsed in (0, 30, 60, 90, 119.999):
            _state, decision = self.decide(elapsed)
            self.assert_waiting(decision)
        _state, admitted = self.decide(120)
        self.assertEqual(BATTERY_EXPORT, admitted.export_intent)
        self.assertGreater(admitted.export_limit, 0.01)
        self.assertTrue(admitted.trace_gates.get("evening_boost_reentry_allowed"))

    def test_source_span_does_not_replace_monotonic_elapsed_time(self) -> None:
        for elapsed, clock in ((0, 0), (30, 30), (60, 60), (90, 90), (120, 119)):
            _state, decision = self.decide(elapsed, clock=clock)
            self.assert_waiting(decision)

    def test_report_gap_over_60_seconds_starts_a_new_sequence(self) -> None:
        for elapsed in (0, 61, 121):
            _state, decision = self.decide(elapsed)
            self.assert_waiting(decision)
        _state, admitted = self.decide(181)
        self.assertEqual(BATTERY_EXPORT, admitted.export_intent)

    def test_report_and_processing_gap_boundaries(self) -> None:
        for gap, processing_gap, expected in (
            (59.9, 59.9, BATTERY_EXPORT),
            (60.0, 60.0, BATTERY_EXPORT),
            (60.1, 60.1, EXPORT_BLOCKED),
            (60.0, 60.1, EXPORT_BLOCKED),
        ):
            with self.subTest(report_gap=gap, processing_gap=processing_gap):
                self.optimizer = self.new_optimizer()
                self.optimizer._tz = timezone(self.START.astimezone().utcoffset() or timedelta())
                for index in range(4):
                    _state, decision = self.decide(index * gap, clock=index * processing_gap)
                self.assertEqual(expected, decision.export_intent)

    def test_cached_poll_does_not_extend_time_until_next_advancing_report(self) -> None:
        self.decide(0)
        self.decide(59.9, report_elapsed=0)
        _state, restarted = self.decide(60.1)
        self.assert_waiting(restarted)
        self.assertEqual(0.0, restarted.trace_values["evening_boost_reentry_elapsed_seconds"])

    def test_source_only_timestamp_regression_keeps_high_water_protection(self) -> None:
        self.qualify()
        for elapsed, report in ((150, 90), (151, 100)):
            _state, rejected = self.decide(elapsed, report_elapsed=report)
            self.assert_waiting(rejected)
            self.assertEqual("load_report_regressed",
                             rejected.trace_values["evening_boost_reentry_reason"])
        for elapsed in (180, 240):
            _state, waiting = self.decide(elapsed)
            self.assert_waiting(waiting)
        _state, admitted = self.decide(300)
        self.assertEqual(BATTERY_EXPORT, admitted.export_intent)

    def test_failed_reserve_gate_just_before_release_restarts_full_period(self) -> None:
        for elapsed in (0, 30, 60, 90):
            self.decide(elapsed, load_kw=1.6)
        _state, failed = self.decide(119, load_kw=1.7)
        self.assert_waiting(failed)
        for elapsed in (120, 150, 180, 210):
            _state, decision = self.decide(elapsed, load_kw=1.6)
            self.assert_waiting(decision)
        _state, admitted = self.decide(240, load_kw=1.6)
        self.assertEqual(BATTERY_EXPORT, admitted.export_intent)

    def test_admitted_boost_closes_immediately_on_reserve_failure(self) -> None:
        self.qualify()
        _state, failed = self.decide(125, load_kw=1.7)
        self.assert_waiting(failed)
        _state, retry = self.decide(130)
        self.assert_waiting(retry)

    def test_untrusted_load_after_admission_removes_boost_permission(self) -> None:
        self.qualify()

        def unavailable(states, cfg, when):
            states[cfg.consumed_power_sensor]["state"] = "unavailable"

        state, failed = self.decide(125, mutate=unavailable)
        self.assertFalse(state.load_power_trusted)
        self.assert_waiting(failed)

    def test_independent_high_owner_is_not_delayed_and_resets_boost_sequence(self) -> None:
        self.decide(0)
        self.decide(30)
        _state, high = self.decide(60, feedin_price=1.20)
        self.assertEqual(BATTERY_EXPORT, high.export_intent)
        self.assertEqual("high_price", high.trace_values.get("battery_export_final_owner"))
        for elapsed in (90, 120, 150, 180):
            _state, decision = self.decide(elapsed)
            self.assert_waiting(decision)
        _state, admitted = self.decide(210)
        self.assertEqual(BATTERY_EXPORT, admitted.export_intent)

    def test_import_cost_veto_resets_boost_sequence(self) -> None:
        self.decide(0)
        self.decide(30)
        with patch.object(self.optimizer, "_optimizer_import_topup_summary_today",
                          return_value={"import_cost_floor_unknown": True,
                                        "today_highest_actual_import_price": 1.0}):
            _state, blocked = self.decide(60)
        self.assertTrue(blocked.trace_gates["actual_import_cost_guard_blocking"])
        self.assert_waiting(blocked)
        for elapsed in (90, 120, 150, 180):
            _state, decision = self.decide(elapsed)
            self.assert_waiting(decision)
        _state, admitted = self.decide(210)
        self.assertEqual(BATTERY_EXPORT, admitted.export_intent)

    def test_unknown_history_without_known_price_keeps_boost_qualification(self) -> None:
        self.decide(0)
        self.decide(30)
        with patch.object(self.optimizer, "_optimizer_import_topup_summary_today",
                          return_value={"import_cost_floor_unknown": True,
                                        "today_highest_actual_import_price": None}):
            _state, warning = self.decide(60)
        self.assertTrue(warning.trace_gates["import_cost_floor_unknown"])
        self.assertTrue(warning.trace_gates["actual_import_cost_guard_active"])
        self.assertFalse(warning.trace_gates["actual_import_cost_guard_blocking"])
        self.assertTrue(warning.trace_gates["evening_boost_reentry_candidate"])
        self.assert_waiting(warning)
        self.decide(90)
        _state, admitted = self.decide(120)
        self.assertEqual(BATTERY_EXPORT, admitted.export_intent)
        self.assertTrue(admitted.trace_gates["evening_boost_reentry_allowed"])

    def test_monotonic_regression_discards_previous_qualification(self) -> None:
        self.decide(0, clock=0)
        self.decide(60, clock=60)
        for elapsed, clock in ((120, 10), (180, 70), (240, 130)):
            _state, decision = self.decide(elapsed, clock=clock)
            self.assert_waiting(decision)
        _state, admitted = self.decide(300, clock=190)
        self.assertEqual(BATTERY_EXPORT, admitted.export_intent)

    def test_process_restart_cannot_reuse_an_admitted_session(self) -> None:
        self.qualify()
        self.optimizer = self.new_optimizer()
        self.optimizer._tz = timezone(self.START.astimezone().utcoffset() or timedelta())
        _state, decision = self.decide(125)
        self.assert_waiting(decision)

    def test_same_instance_run_restart_resets_before_first_tick(self) -> None:
        self.qualify()

        async def startup_tick():
            self.assertEqual("closed", self.optimizer._evening_boost_reentry.phase)
            self.optimizer._running = False

        with patch.object(self.optimizer, "_tick", side_effect=startup_tick) as tick:
            asyncio.run(self.optimizer.run_forever())
        tick.assert_awaited_once()
        _state, waiting = self.decide(125)
        self.assert_waiting(waiting)

    def test_sunrise_tariff_and_forecast_failure_close_admitted_boost(self) -> None:
        for source in ("sun_entity", "feedin_sensor", "forecast_tomorrow_sensor"):
            with self.subTest(source=source):
                self.optimizer = self.new_optimizer()
                self.optimizer._tz = timezone(self.START.astimezone().utcoffset() or timedelta())
                self.qualify()

                def unavailable(states, cfg, when):
                    states[getattr(cfg, source)]["state"] = "unavailable"

                _state, failed = self.decide(125, mutate=unavailable)
                self.assert_waiting(failed)
                _state, retry = self.decide(130)
                self.assert_waiting(retry)

    def test_generic_success_pause_does_not_preserve_admission(self) -> None:
        self.qualify()
        self.tick(125, outcome=optimizer_module._ActuatorApplicationResult(succeeded=True))
        _state, decision = self.decide(130)
        self.assert_waiting(decision)

    def test_failed_application_cannot_restore_admission_with_old_decision(self) -> None:
        prior = self.qualify()
        with self.assertRaises(RuntimeError):
            self.tick(125, outcome=optimizer_module._ActuatorApplicationResult(
                succeeded=False, error="synthetic failure",
                fallback_attempted=True, fallback_succeeded=True,
            ))
        self.assertIs(prior, self.optimizer.last_decision)
        _state, decision = self.decide(130)
        self.assert_waiting(decision)

    def test_cancelled_application_requires_a_fresh_qualification(self) -> None:
        self.qualify()

        def cancelled(state, decision):
            raise asyncio.CancelledError()

        with self.assertRaises(asyncio.CancelledError):
            self.tick(125, outcome=cancelled)
        _state, decision = self.decide(130)
        self.assert_waiting(decision)

    def test_wall_rollback_with_untrusted_cached_future_reports_recovers(self) -> None:
        self.qualify()
        # Future-dated cached inputs make the candidate untrusted on rollback.
        _state, failed = self.decide(80, clock=125, report_elapsed=120)
        self.assertNotEqual(BATTERY_EXPORT, failed.export_intent)
        for elapsed, clock in ((110, 155), (140, 185), (170, 215), (200, 245)):
            _state, decision = self.decide(elapsed, clock=clock)
            self.assert_waiting(decision)
        _state, admitted = self.decide(230, clock=275)
        self.assertEqual(BATTERY_EXPORT, admitted.export_intent)

    def test_load_source_change_restarts_qualification(self) -> None:
        self.decide(0)
        self.decide(30)
        self.optimizer.cfg.consumed_power_sensor = "sensor.synthetic_replacement_load"
        for elapsed in (60, 90, 120, 150):
            _state, decision = self.decide(elapsed)
            self.assert_waiting(decision)
        _state, admitted = self.decide(180)
        self.assertEqual(BATTERY_EXPORT, admitted.export_intent)

    def test_competing_grid_charge_never_gets_unqualified_boost_export(self) -> None:
        self.optimizer.cfg.daytime_topup_max_soc = 90.0

        def cheap_price(states, cfg, when):
            states[cfg.price_sensor]["state"] = 0.01

        for elapsed in (0, 30, 60, 90, 120):
            _state, decision = self.decide(
                elapsed, feedin_price=0.08, mutate=cheap_price
            )
            self.assertEqual(0.0, decision.export_limit)
            self.assertEqual(EXPORT_BLOCKED, decision.export_intent)
            self.assertGreater(decision.import_limit, 0.0)
            self.assertEqual(optimizer_module.MODE_CMD_CHARGE_PV, decision.ems_mode)
        _state, decision = self.decide(150)
        self.assert_waiting(decision)

    def test_manual_and_remote_off_cannot_preserve_an_admitted_session(self) -> None:
        for kind in ("manual", "remote_off"):
            with self.subTest(kind=kind):
                self.optimizer = self.new_optimizer()
                self.optimizer._tz = timezone(self.START.astimezone().utcoffset() or timedelta())
                self.qualify()

                def change_authority(states, cfg, when):
                    if kind == "manual":
                        states[cfg.sigenergy_mode_select]["state"] = cfg.manual_option
                    else:
                        states[cfg.ha_control_switch]["state"] = "off"

                _state, paused = self.decide(125, mutate=change_authority)
                self.assertFalse(paused.trace_gates.get("evening_boost_reentry_allowed"))
                _state, retry = self.decide(130)
                self.assert_waiting(retry)

    def test_real_application_qualifies_and_enters_boost_with_later_reports(self) -> None:
        clock = [datetime.fromtimestamp(self.START.timestamp(), timezone.utc)]
        ha = ReportingActuatorHA(clock)
        self.optimizer = self.fixture.optimizer(
            ha=ha, evening_boost_enabled=True,
            evening_boost_min_tomorrow_forecast_kwh=100.0,
        )
        self.optimizer._optimizer_import_topup_summary_today = (
            lambda: dict(self.KNOWN_EMPTY_IMPORT_HISTORY)
        )
        self.optimizer._tz = timezone(self.START.astimezone().utcoffset() or timedelta())
        for elapsed in (0, 30, 60, 90):
            decision = self.real_tick(elapsed)
            if decision is not None:
                self.assert_waiting(decision)
        admitted = self.real_tick(120)
        self.assertIsNotNone(admitted)
        self.assertEqual(BATTERY_EXPORT, admitted.export_intent)
        self.assertTrue(admitted.trace_gates.get("evening_boost_reentry_application_retained"))
        self.assertIn(
            ("select_option", self.optimizer.cfg.ems_mode_select,
             optimizer_module.MODE_CMD_DISCHARGE_PV), ha.calls,
        )

    def test_real_remote_enable_only_success_does_not_count_as_applied(self) -> None:
        clock = [datetime.fromtimestamp(self.START.timestamp(), timezone.utc)]
        ha = ReportingActuatorHA(clock)
        self.optimizer = self.fixture.optimizer(
            ha=ha, evening_boost_enabled=True,
            evening_boost_min_tomorrow_forecast_kwh=100.0,
        )
        self.optimizer._optimizer_import_topup_summary_today = (
            lambda: dict(self.KNOWN_EMPTY_IMPORT_HISTORY)
        )
        self.optimizer._tz = timezone(self.START.astimezone().utcoffset() or timedelta())

        def remote_off(states, cfg, when):
            states[cfg.ha_control_switch]["state"] = "off"
            # EMS drift creates a legitimate automatic recovery request.
            states[cfg.ems_mode_select]["state"] = optimizer_module.MODE_CMD_DISCHARGE_PV

        paused = self.real_tick(0, mutate=remote_off)
        self.assertFalse(paused.trace_gates.get("evening_boost_reentry_application_retained"))
        self.assertIn(("turn_on", self.optimizer.cfg.ha_control_switch, True), ha.calls)
        self.assertFalse(any(call[0] == "select_option" for call in ha.calls))
        for elapsed in (30, 60, 90, 120):
            decision = self.real_tick(elapsed)
            if decision is not None:
                self.assert_waiting(decision)
        admitted = self.real_tick(150)
        self.assertEqual(BATTERY_EXPORT, admitted.export_intent)

    def test_verified_msc_pending_preserves_qualification(self) -> None:
        clock = [datetime.fromtimestamp(self.START.timestamp(), timezone.utc)]
        ha = ReportingActuatorHA(clock)
        self.optimizer = self.fixture.optimizer(
            ha=ha, evening_boost_enabled=True,
            evening_boost_min_tomorrow_forecast_kwh=100.0,
        )
        self.optimizer._optimizer_import_topup_summary_today = (
            lambda: dict(self.KNOWN_EMPTY_IMPORT_HISTORY)
        )
        self.optimizer._tz = timezone(self.START.astimezone().utcoffset() or timedelta())
        captured = []
        original = self.optimizer._finish_evening_boost_reentry_application

        def capture(state, decision, result):
            retained = original(state, decision, result)
            captured.append((decision, result, retained,
                             self.optimizer._evening_boost_reentry.phase))
            return retained

        def initially_discharging(states, cfg, when):
            states[cfg.ems_mode_select]["state"] = optimizer_module.MODE_CMD_DISCHARGE_PV
            states[cfg.grid_export_limit]["state"] = 25.0

        with patch.object(self.optimizer, "_finish_evening_boost_reentry_application",
                          side_effect=capture):
            self.assertIsNone(self.real_tick(0, mutate=initially_discharging))
            decision, result, retained, phase = captured[-1]
            self.assertFalse(result.succeeded)
            self.assertTrue(result.transition_pending)
            self.assertTrue(result.automatic_transition_pending)
            self.assertFalse(result.fallback_attempted)
            self.assertTrue(retained)
            self.assertEqual("qualifying", phase)
            self.assertTrue(decision.trace_gates["evening_boost_reentry_application_retained"])
            self.assertEqual("qualifying", decision.trace_values[
                "evening_boost_reentry_after_application_state"])
            self.assertEqual("close", decision.trace_values["msc_transition_phase"])

            self.assertIsNone(self.real_tick(30))
            decision, result, retained, phase = captured[-1]
            self.assertFalse(result.succeeded)
            self.assertTrue(result.transition_pending)
            self.assertTrue(result.automatic_transition_pending)
            self.assertTrue(retained)
            self.assertEqual("qualifying", phase)
            self.assertEqual("msc", decision.trace_values["msc_transition_phase"])

            for elapsed in (60, 90):
                decision = self.real_tick(elapsed)
                self.assert_waiting(decision)
                self.assertTrue(captured[-1][1].automatic_application_completed)
                self.assertEqual("qualifying", captured[-1][3])

            admitted = self.real_tick(120)
            self.assertEqual(BATTERY_EXPORT, admitted.export_intent)
            self.assertTrue(captured[-1][1].automatic_application_completed)
            self.assertEqual("admitted", captured[-1][3])
            self.assertIn(("select_option", self.optimizer.cfg.ems_mode_select,
                           optimizer_module.MODE_CMD_DISCHARGE_PV), ha.calls)

    def apply_with_settlement_race(self, scenario):
        # Real admission and application, with an awaited actuator boundary.
        for elapsed in (0, 30, 60, 90, 120):
            state, decision = self.decide(elapsed)
        self.assertTrue(decision.trace_gates["evening_boost_reentry_allowed"])
        cfg = self.optimizer.cfg
        clock = [self.START + timedelta(seconds=120)]
        monotonic_clock = [120.0]
        authority_lost = [False]
        boundary_crossed = [False]

        class Clock(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime.fromtimestamp(clock[0].timestamp(), tz) if tz else clock[0]

        async def read_authority(evidence=None):
            if evidence is not None:
                for entity in evidence:
                    request = self.optimizer._number_settlement_requests.get(entity)
                    reported = (clock[0] + timedelta(milliseconds=1)).astimezone(timezone.utc).isoformat()
                    evidence[entity] = {
                        "state": str(request[0] if request else 0.01),
                        "last_updated": reported, "last_reported": reported,
                    }
            return SimpleNamespace(
                available=True, fresh=True,
                value=cfg.manual_option if authority_lost[0] else cfg.automated_option,
            ), "on"

        async def wait_for_settlement(entity, target, **kwargs):
            if target > 0.011 and not boundary_crossed[0]:
                boundary_crossed[0] = True
                await asyncio.sleep(0)
                if scenario == "expiry":
                    clock[0] += timedelta(seconds=61)
                    monotonic_clock[0] += 61
                else:
                    authority_lost[0] = True
                return True
            # Acceptance and fallback settlement are deliberately unproved.
            return False

        with (
            patch("app.optimizer.datetime", Clock),
            patch("app.optimizer.monotonic", side_effect=lambda: monotonic_clock[0]),
            patch.object(self.optimizer, "_read_control_authority", side_effect=read_authority),
            patch.object(self.optimizer, "_wait_for_number_at_most", side_effect=wait_for_settlement),
            patch.object(self.optimizer, "_wait_for_exact_entity_state", new=AsyncMock(return_value=False)),
        ):
            result = asyncio.run(self.optimizer._apply(state, decision))

        self.assertTrue(boundary_crossed[0], "Awaited settlement boundary was not reached")
        self.assertFalse(result.succeeded)
        self.assertEqual("closed", self.optimizer._evening_boost_reentry.phase)
        self.assertFalse(any(
            call[0] == "select_option" and call[2] in optimizer_module.DISCHARGE_MODES
            for call in self.optimizer.ha.calls
        ))
        self.assertFalse(any(
            call[0] == "set_number" and call[1] == cfg.ess_max_discharging_limit
            and call[2] > 0.011 for call in self.optimizer.ha.calls
        ))
        return result

    def test_expiry_during_awaited_export_settlement_prevents_discharge(self) -> None:
        result = self.apply_with_settlement_race("expiry")
        self.assertTrue(result.fallback_attempted)
        self.assertTrue(any(
            call[0] == "set_number" and call[1] == self.optimizer.cfg.grid_export_limit
            and call[2] <= 0.011 for call in self.optimizer.ha.calls
        ))

    def test_manual_takeover_during_export_settlement_stops_subsequent_writes(self) -> None:
        self.apply_with_settlement_race("manual_takeover")
        # Only the export request made before takeover is permitted.
        self.assertEqual(1, len(self.optimizer.ha.calls))


if __name__ == "__main__":
    unittest.main()
