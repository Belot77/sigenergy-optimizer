"""Offline sunset trace checks using the real snapshot and decision paths."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.config import Settings
from app.decision_trace_store import _copy_row
from app.models import EXPORT_BLOCKED
from app.optimizer import MODE_MAX_SELF
from haos49_characterization_helpers import Haos49CharacterizationCase, RecordingHA
import test_phase1_forecast_solar_clock_telemetry_trust_characterization as solar_fixtures


class SunsetMetadataHA(RecordingHA):
    async def get_state_report_metadata(self, entity_ids):
        self.report_metadata_calls.append(list(entity_ids))
        return {
            entity: self.metadata[entity]
            for entity in entity_ids
            if entity in self.metadata
        }


class O4SunsetProvenanceTests(Haos49CharacterizationCase):
    SUNSET = datetime(2026, 1, 15, 18, tzinfo=timezone.utc)
    NEXT_RISING = SUNSET + timedelta(hours=13)
    NEXT_SETTING = SUNSET + timedelta(days=1, minutes=1)
    TRACE_KEY = "o4_sunset_provenance"

    def new_optimizer(self):
        with patch(
            "haos49_characterization_helpers.Settings",
            side_effect=lambda **values: Settings(_env_file=None, **values),
        ):
            optimizer = self.optimizer(ha=SunsetMetadataHA(), evening_boost_enabled=True)
        optimizer._tz = timezone.utc
        return optimizer

    @staticmethod
    def entities_by_role(cfg):
        return {
            "sun": cfg.sun_entity,
            "control_mode": cfg.sigenergy_mode_select,
            "remote_ems": cfg.ha_control_switch,
            "ems_mode": cfg.ems_mode_select,
            "export_limit": cfg.grid_export_limit,
        }

    def observe(self, optimizer, seconds_from_sunset, *, mutate=None):
        when = self.SUNSET + timedelta(seconds=seconds_from_sunset)
        below = when >= self.SUNSET
        setting = self.NEXT_SETTING if below else self.SUNSET
        fixture = solar_fixtures.Phase1ForecastSolarClockTelemetryTrustCharacterizationTests()
        ha = optimizer.ha
        ha.states = fixture._states(
            optimizer,
            # The shared fixture generates defaults in host-local naïve time.
            when=when.astimezone().replace(tzinfo=None),
            sun_state="below_horizon" if below else "above_horizon",
            next_rising=self.NEXT_RISING.isoformat(),
            next_setting=setting.isoformat(),
        )
        ha.metadata = {}
        for role, entity in self.entities_by_role(optimizer.cfg).items():
            rest = ha.states[entity]
            rest["state"] = str(rest["state"])
            updated = when - timedelta(seconds=1)
            changed = (
                self.SUNSET if below and role == "sun" else when - timedelta(hours=2)
            )
            rest["last_changed"] = changed.isoformat()
            rest["last_updated"] = updated.isoformat()
            rest["last_reported"] = updated.isoformat()
            rest["attributes"]["test_only_private_attribute"] = "test-only raw attribute"
            metadata = {
                "entity_id": entity,
                "state": rest["state"],
                "last_changed": rest["last_changed"],
                "last_updated": rest["last_updated"],
                "last_reported": when.isoformat(),
                "test_only_private_attribute": "test-only raw attribute",
            }
            if role == "sun":
                metadata["next_rising"] = self.NEXT_RISING.isoformat()
                metadata["next_setting"] = setting.isoformat()
            ha.metadata[entity] = metadata
        if mutate is not None:
            mutate(ha, optimizer.cfg)

        with self.optimizer_time(when):
            state = asyncio.run(optimizer._read_state())
            decision = optimizer._decide(state)
            optimizer._record_decision_trace(state, decision)
        return state, decision, optimizer.decision_trace(limit=1)[0]

    def test_natural_sunset_rollover_preserves_both_report_chronologies(self):
        optimizer = self.new_optimizer()
        roles = self.entities_by_role(optimizer.cfg)
        for seconds, horizon, expected_setting in (
            (-60, "above_horizon", self.SUNSET),
            (60, "below_horizon", self.NEXT_SETTING),
        ):
            with self.subTest(seconds=seconds):
                _, decision, row = self.observe(optimizer, seconds)
                evidence = row[self.TRACE_KEY]
                when = self.SUNSET + timedelta(seconds=seconds)
                updated = when - timedelta(seconds=1)
                self.assertEqual("pre_application", evidence["snapshot_phase"])
                self.assertEqual(when.timestamp(), evidence["snapshot_at_ts"])
                self.assertEqual(EXPORT_BLOCKED, decision.export_intent)
                self.assertFalse(decision.evening_export_boost_active)
                self.assertEqual(horizon, evidence["sun"]["rest"]["state"])
                self.assertEqual("automated", evidence["control_mode"]["rest"]["state"])
                self.assertEqual("on", evidence["remote_ems"]["rest"]["state"])
                self.assertEqual(MODE_MAX_SELF, evidence["ems_mode"]["rest"]["state"])
                self.assertEqual(0.01, evidence["export_limit"]["rest"]["state"])
                for role in roles:
                    report = evidence[role]
                    self.assertEqual("accepted", report["metadata_status"])
                    self.assertIs(True, report["correlated_chronology"])
                    self.assertEqual(when.timestamp(), report["effective_report_ts"])
                    rest, metadata = report["rest"], report["state_object"]
                    self.assertEqual(rest["state"], metadata["state"])
                    self.assertEqual(updated.timestamp(), rest["last_updated_ts"])
                    self.assertEqual(updated.timestamp(), metadata["last_updated_ts"])
                    self.assertEqual(updated.timestamp(), rest["last_reported_ts"])
                    self.assertEqual(when.timestamp(), metadata["last_reported_ts"])
                    changed = (
                        self.SUNSET if seconds > 0 and role == "sun" else when - timedelta(hours=2)
                    )
                    self.assertEqual(changed.timestamp(), rest["last_changed_ts"])
                    self.assertEqual(changed.timestamp(), metadata["last_changed_ts"])
                for source in ("rest", "state_object"):
                    sun = evidence["sun"][source]
                    self.assertEqual(self.NEXT_RISING.timestamp(), sun["next_rising_ts"])
                    self.assertEqual(expected_setting.timestamp(), sun["next_setting_ts"])

                copied = _copy_row(row)
                self.assertEqual(evidence, copied[self.TRACE_KEY])
                copied[self.TRACE_KEY]["sun"]["rest"]["state"] = "changed copy"
                self.assertEqual(horizon, evidence["sun"]["rest"]["state"])
                serialized = json.dumps(evidence, allow_nan=False)
                self.assertNotIn("test-only raw attribute", serialized)
                for entity in roles.values():
                    self.assertNotIn(entity, serialized)

        self.assertEqual(2, len(optimizer.ha.bulk_state_calls))
        self.assertEqual(2, len(optimizer.ha.report_metadata_calls))
        for request in optimizer.ha.report_metadata_calls:
            self.assertTrue(set(roles.values()) <= set(request))
        self.assertEqual([], optimizer.ha.calls)

    def test_optional_horizon_disagreement_keeps_existing_sun_trust(self):
        def conflicting_horizon(ha, cfg):
            ha.metadata[cfg.sun_entity]["next_rising"] = later_rising.isoformat()

        later_rising = self.NEXT_RISING + timedelta(minutes=10)
        _, _, matched_row = self.observe(self.new_optimizer(), 60)
        state, decision, row = self.observe(self.new_optimizer(), 60, mutate=conflicting_horizon)
        sun = row[self.TRACE_KEY]["sun"]
        self.assertEqual("accepted", sun["metadata_status"])
        self.assertIs(False, sun["correlated_chronology"])
        self.assertEqual(self.NEXT_RISING.timestamp(), sun["rest"]["next_rising_ts"])
        self.assertEqual(later_rising.timestamp(), sun["state_object"]["next_rising_ts"])
        self.assertEqual(self.NEXT_RISING.timestamp(), state.next_sunrise_ts)
        for gate in ("sun_state", "sunrise", "sunset"):
            key = f"{gate}_observation_trusted"
            self.assertIs(True, decision.trace_gates[key])
            self.assertEqual(matched_row["gates"][key], row["gates"][key])
        self.assertEqual(matched_row["summary"], row["summary"])

    def test_template_match_does_not_corroborate_a_control_metadata_conflict(self):
        def invalid_rest_report(ha, cfg):
            ha.states[cfg.sigenergy_mode_select]["last_reported"] = "malformed"

        state, _, row = self.observe(self.new_optimizer(), 60, mutate=invalid_rest_report)
        selector = row[self.TRACE_KEY]["control_mode"]
        self.assertEqual("accepted", selector["metadata_status"])
        self.assertIs(True, selector["control_metadata_conflict"])
        self.assertIs(False, selector["correlated_chronology"])
        self.assertFalse(state.sigenergy_mode_observed)

    def test_future_report_cannot_corroborate_chronology(self):
        def future_report(ha, cfg):
            report = ha.metadata[cfg.grid_export_limit]
            report["last_reported"] = (self.SUNSET + timedelta(seconds=61)).isoformat()

        _, _, row = self.observe(self.new_optimizer(), 60, mutate=future_report)
        export_limit = row[self.TRACE_KEY]["export_limit"]
        self.assertEqual("accepted", export_limit["metadata_status"])
        self.assertIs(False, export_limit["correlated_chronology"])

    def test_outside_sunset_window_omits_provenance(self):
        for seconds in (-301, 301):
            with self.subTest(seconds=seconds):
                _, _, row = self.observe(self.new_optimizer(), seconds)
                self.assertNotIn(self.TRACE_KEY, row)

    def test_nighttime_sun_entity_restart_does_not_look_like_sunset(self):
        for changed_seconds, observed_seconds in ((299, 550), (7198, 7200)):
            with self.subTest(changed_seconds=changed_seconds):
                def recreate_below_horizon_state(ha, cfg):
                    changed = self.SUNSET + timedelta(seconds=changed_seconds)
                    ha.states[cfg.sun_entity]["last_changed"] = changed.isoformat()
                    ha.metadata[cfg.sun_entity]["last_changed"] = changed.isoformat()

                state, _, row = self.observe(
                    self.new_optimizer(), observed_seconds, mutate=recreate_below_horizon_state,
                )
                self.assertTrue(state.sun_state_observation_trusted)
                self.assertFalse(state.sun_above_horizon)
                self.assertNotIn(self.TRACE_KEY, row)

    def test_diagnostic_failure_keeps_snapshot_and_decision_available(self):
        optimizer = self.new_optimizer()
        with patch.object(
            optimizer, "_o4_sunset_trace_evidence", side_effect=ValueError("test-only error"),
        ):
            state, decision, row = self.observe(optimizer, 60)
        self.assertTrue(state.sun_state_observation_trusted)
        self.assertEqual(EXPORT_BLOCKED, decision.export_intent)
        self.assertNotIn(self.TRACE_KEY, row)

    def test_prior_sunset_horizon_can_capture_missing_current_sun(self):
        def remove_sun(ha, cfg):
            ha.states.pop(cfg.sun_entity)
            ha.metadata.pop(cfg.sun_entity)

        optimizer = self.new_optimizer()
        prior, _, _ = self.observe(optimizer, -60)
        optimizer._last_state = prior
        state, _, row = self.observe(optimizer, 60, mutate=remove_sun)
        self.assertFalse(state.sun_state_observation_trusted)
        evidence = row[self.TRACE_KEY]
        self.assertIs(False, evidence["sun"]["correlated_chronology"])
        self.assertIs(True, evidence["control_mode"]["correlated_chronology"])
