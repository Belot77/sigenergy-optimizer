"""Boost continuation across a natural sunset, using independently timed HA reports."""

from __future__ import annotations

import asyncio
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.models import BATTERY_EXPORT
import app.optimizer as optimizer_module
import test_evening_boost_reentry_stability as boost_fixtures


class EveningBoostSunsetContinuationTests(unittest.TestCase):
    SUNSET_SECONDS = 125

    def setUp(self):
        self.case = boost_fixtures.EveningBoostReentryStabilityTests()
        self.case.setUp()
        self.sun_metadata_mutation = None

    def tearDown(self):
        self.case.tearDown()

    @property
    def optimizer(self):
        return self.case.optimizer

    def sunset(self, states, cfg, when):
        setting = self.case.START + timedelta(seconds=self.SUNSET_SECONDS)
        below = when >= setting
        sun = states[cfg.sun_entity]
        sun["state"] = "below_horizon" if below else "above_horizon"
        changed = setting if below else setting - timedelta(hours=3)
        sun["last_changed"] = changed.astimezone(timezone.utc).isoformat()
        rising = datetime.fromisoformat(sun["attributes"]["next_rising"])
        sun["attributes"]["next_rising"] = rising.astimezone(timezone.utc).isoformat()
        sun["attributes"]["next_setting"] = (
            setting + timedelta(days=1, minutes=1) if below else setting
        ).astimezone(timezone.utc).isoformat()

    def supply_sun_metadata(self):
        ha = self.optimizer.ha
        original_reader = getattr(ha, "get_state_report_metadata", None)

        async def read(entity_ids):
            result = await original_reader(entity_ids) if original_reader else {}
            sun_id = self.optimizer.cfg.sun_entity
            sun = ha.states.get(sun_id)
            if sun_id in entity_ids and sun:
                metadata = {
                    "entity_id": sun_id,
                    **{key: sun.get(key) for key in (
                        "state", "last_changed", "last_updated", "last_reported",
                    )},
                    **{key: sun["attributes"].get(key) for key in ("next_rising", "next_setting")},
                }
                if self.sun_metadata_mutation:
                    self.sun_metadata_mutation(metadata)
                result[sun_id] = metadata
            return result

        ha.get_state_report_metadata = read

    def qualify(self, *, real=False):
        if real:
            clock = [datetime.fromtimestamp(self.case.START.timestamp(), timezone.utc)]
            ha = boost_fixtures.ReportingActuatorHA(clock)
            self.case.optimizer = self.case.fixture.optimizer(
                ha=ha, evening_boost_enabled=True,
                evening_boost_min_tomorrow_forecast_kwh=100.0,
            )
            self.optimizer._optimizer_import_topup_summary_today = (
                lambda: dict(self.case.KNOWN_EMPTY_IMPORT_HISTORY)
            )
            self.optimizer._tz = timezone(
                self.case.START.astimezone().utcoffset() or timedelta()
            )
        self.supply_sun_metadata()
        tick = self.case.real_tick if real else self.case.tick
        for elapsed in (0, 30, 60, 90, 120):
            decision = tick(elapsed, mutate=self.sunset)
        self.assertEqual(BATTERY_EXPORT, decision.export_intent)
        return decision

    def real_tick(self, elapsed, *, mutate=None):
        with patch.object(
            self.optimizer, "_finish_evening_boost_reentry_application",
            wraps=self.optimizer._finish_evening_boost_reentry_application,
        ) as finish:
            self.case.real_tick(elapsed, mutate=mutate or self.sunset)
        _, decision, result = finish.call_args.args
        return decision, result

    def test_completed_boost_continues_without_a_sunset_close(self):
        admitted = self.qualify(real=True)
        ha = self.optimizer.ha
        ha.calls.clear()
        continued, result = self.real_tick(126)
        self.assertEqual(BATTERY_EXPORT, continued.export_intent)
        self.assertTrue(result.automatic_application_completed)
        self.assertTrue(result.succeeded)
        self.assertTrue(continued.trace_gates["evening_boost_reentry_application_retained"])
        self.assertEqual(
            admitted.trace_values["evening_boost_reentry_generation"] + 1,
            continued.trace_values["evening_boost_reentry_generation"],
        )
        self.assertEqual(126, continued.trace_values["evening_boost_reentry_elapsed_seconds"])
        self.assertFalse(any(
            action == "set_number" and entity == self.optimizer.cfg.grid_export_limit
            and value <= 0.011
            for action, entity, value in ha.calls
        ))
        self.assertFalse(any(
            action == "select_option" and value == optimizer_module.MODE_MAX_SELF
            for action, entity, value in ha.calls
        ))
        continued, result = self.real_tick(131)
        self.assertEqual(BATTERY_EXPORT, continued.export_intent)
        self.assertTrue(result.succeeded)

    def test_real_application_closes_after_a_load_increase(self):
        self.qualify(real=True)
        continued, result = self.real_tick(126)
        self.assertEqual(BATTERY_EXPORT, continued.export_intent)
        self.assertTrue(result.succeeded)
        ha = self.optimizer.ha
        ha.calls.clear()

        def higher_load(states, cfg, when):
            self.sunset(states, cfg, when)
            states[cfg.consumed_power_sensor]["state"] = 6.0

        blocked, result = self.real_tick(131, mutate=higher_load)
        self.case.assert_waiting(blocked)
        self.assertTrue(result.transition_pending or result.succeeded)
        self.assertIn(("set_number", self.optimizer.cfg.grid_export_limit, 0.01), ha.calls)
        self.assertFalse(any(
            action == "select_option" and value in optimizer_module.DISCHARGE_MODES
            for action, _, value in ha.calls
        ))

    def test_eligibility_loss_after_sunset_closes_and_requires_full_requalification(self):
        self.qualify()
        self.assertEqual(BATTERY_EXPORT, self.case.tick(126, mutate=self.sunset).export_intent)
        blocked = self.case.tick(131, mutate=self.sunset, feedin_price=0.0)
        self.case.assert_waiting(blocked)
        self.assertEqual("closed", blocked.trace_values["evening_boost_reentry_state"])
        for elapsed in (136, 166, 196, 226, 255):
            self.case.assert_waiting(self.case.tick(elapsed, mutate=self.sunset))
        self.assertEqual(BATTERY_EXPORT, self.case.tick(256, mutate=self.sunset).export_intent)

    def test_unapplied_admission_cannot_use_sunset_continuation(self):
        self.supply_sun_metadata()
        for elapsed in (0, 30, 60, 90):
            self.case.tick(elapsed, mutate=self.sunset)
        _, admitted = self.case.decide(120, mutate=self.sunset)
        self.assertEqual(BATTERY_EXPORT, admitted.export_intent)
        self.case.assert_waiting(self.case.tick(126, mutate=self.sunset))

    def test_qualifying_boost_restarts_at_sunset(self):
        self.supply_sun_metadata()
        for elapsed in (30, 60, 90, 120):
            self.case.assert_waiting(self.case.tick(elapsed, mutate=self.sunset))
        reset = self.case.tick(126, mutate=self.sunset)
        self.case.assert_waiting(reset)
        self.assertEqual(0.0, reset.trace_values["evening_boost_reentry_elapsed_seconds"])

    def test_pending_only_application_cannot_supply_completed_sunset_proof(self):
        self.qualify()
        pending = optimizer_module._ActuatorApplicationResult(
            succeeded=False, transition_pending=True, automatic_transition_pending=True,
        )
        with self.assertRaises(RuntimeError):
            self.case.tick(123, mutate=self.sunset, outcome=pending)
        self.case.assert_waiting(self.case.tick(126, mutate=self.sunset))

    def test_application_completing_after_sunset_keeps_earlier_proof(self):
        self.qualify()
        state, straddling = self.case.decide(124, mutate=self.sunset)
        self.assertEqual(BATTERY_EXPORT, straddling.export_intent)
        with self.case.fixture.optimizer_time(self.case.START + timedelta(seconds=126)):
            self.optimizer._finish_evening_boost_reentry_application(
                state, straddling,
                optimizer_module._ActuatorApplicationResult(
                    succeeded=True, automatic_application_completed=True,
                ),
            )
        continued = self.case.tick(131, mutate=self.sunset)
        self.assertEqual(BATTERY_EXPORT, continued.export_intent)
        self.assertEqual(131, continued.trace_values["evening_boost_reentry_elapsed_seconds"])

    def test_failed_application_after_rollover_discards_continuation(self):
        self.qualify()
        with self.assertRaisesRegex(RuntimeError, "synthetic application failure"):
            self.case.tick(
                126, mutate=self.sunset,
                outcome=optimizer_module._ActuatorApplicationResult(
                    succeeded=False, error="synthetic application failure",
                    fallback_attempted=True, fallback_succeeded=True,
                ),
            )
        self.case.assert_waiting(self.case.tick(131, mutate=self.sunset))

    def test_stale_pre_sunset_decision_cannot_dispatch_after_context_migration(self):
        admitted = self.qualify()

        def cached_load(states, cfg, when):
            self.sunset(states, cfg, when)
            stamp = (self.case.START + timedelta(seconds=120)).astimezone(timezone.utc).isoformat()
            load = states[cfg.consumed_power_sensor]
            load["last_updated"] = load["last_reported"] = stamp

        when = self.case.prepare(126, mutate=cached_load)
        with self.case.fixture.optimizer_time(when), patch(
            "app.optimizer.monotonic", return_value=126,
        ):
            current = asyncio.run(self.optimizer._read_state())
            continued = self.optimizer._decide(current)
            self.assertEqual(BATTERY_EXPORT, continued.export_intent)
            self.assertTrue(self.optimizer._evening_boost_reentry_dispatch_current(current, continued))
            self.assertFalse(self.optimizer._evening_boost_reentry_dispatch_current(current, admitted))
            # The cached load report matches both snapshots. A new decision
            # still cannot dispatch against the old snapshot's horizon.
            before_when = self.case.prepare(120, mutate=self.sunset)
            with self.case.fixture.optimizer_time(before_when):
                before = asyncio.run(self.optimizer._read_state())
            self.assertFalse(self.optimizer._evening_boost_reentry_dispatch_current(before, continued))

    def test_sunset_exception_rejects_other_context_and_report_changes(self):
        cases = (
            "sunrise", "capacity", "policy", "missing_sunset", "wrong_day_sunset",
            "cached_sun", "pre_sunset_report", "future_sun", "stale_sun",
            "unknown_sun", "load_gap", "manual", "remote_off", "far_future_sunset",
            "early_horizon_change", "conflicting_state", "conflicting_horizon",
            "conflicting_change_time", "invalid_report_order",
        )
        for case in cases:
            with self.subTest(case=case):
                self.sun_metadata_mutation = None
                self.case.optimizer = self.case.new_optimizer()
                self.qualify()

                def change(states, cfg, when):
                    self.sunset(states, cfg, when)
                    sun = states[cfg.sun_entity]
                    if case == "sunrise":
                        rising = datetime.fromisoformat(sun["attributes"]["next_rising"])
                        sun["attributes"]["next_rising"] = (rising + timedelta(minutes=1)).isoformat()
                    elif case == "capacity":
                        states[cfg.rated_capacity_sensor]["state"] = 31.0
                    elif case == "policy":
                        cfg.evening_boost_min_tomorrow_forecast_kwh += 1.0
                    elif case == "missing_sunset":
                        sun["attributes"].pop("next_setting")
                    elif case == "wrong_day_sunset":
                        setting = when + timedelta(days=2)
                        sun["attributes"]["next_setting"] = setting.astimezone(timezone.utc).isoformat()
                    elif case == "far_future_sunset":
                        sun["attributes"]["next_setting"] = "9999-12-31T23:59:59+00:00"
                    elif case == "early_horizon_change":
                        changed = when - timedelta(seconds=2)
                        sun["last_changed"] = changed.astimezone(timezone.utc).isoformat()
                    elif case in {"cached_sun", "pre_sunset_report", "future_sun", "stale_sun"}:
                        offset = {"cached_sun": 120, "pre_sunset_report": 124,
                                  "future_sun": 127, "stale_sun": -120}[case]
                        at = self.case.START + timedelta(seconds=offset)
                        stamp = at.astimezone(timezone.utc).isoformat()
                        sun["last_updated"] = sun["last_reported"] = stamp
                    elif case == "unknown_sun":
                        sun["state"] = "unknown"
                    elif case == "load_gap":
                        stamp = (when - timedelta(seconds=61)).astimezone(timezone.utc).isoformat()
                        states[cfg.consumed_power_sensor]["last_updated"] = stamp
                        states[cfg.consumed_power_sensor]["last_reported"] = stamp
                    elif case == "manual":
                        states[cfg.sigenergy_mode_select]["state"] = cfg.manual_option
                    elif case == "remote_off":
                        states[cfg.ha_control_switch]["state"] = "off"

                def contradict(metadata):
                    if case == "conflicting_state":
                        metadata["state"] = "above_horizon"
                    elif case == "conflicting_horizon":
                        setting = datetime.fromisoformat(metadata["next_setting"])
                        metadata["next_setting"] = (setting + timedelta(minutes=1)).isoformat()
                    elif case == "conflicting_change_time":
                        changed = datetime.fromisoformat(metadata["last_changed"])
                        metadata["last_changed"] = (changed - timedelta(seconds=1)).isoformat()
                    elif case == "invalid_report_order":
                        updated = datetime.fromisoformat(metadata["last_updated"])
                        metadata["last_reported"] = (updated - timedelta(seconds=1)).isoformat()

                self.sun_metadata_mutation = contradict
                _, blocked = self.case.decide(126, mutate=change)
                self.assertFalse(blocked.trace_gates.get("evening_boost_reentry_allowed"))
                self.assertNotEqual(
                    "evening_export_boost", blocked.trace_values.get("battery_export_final_owner"),
                )
