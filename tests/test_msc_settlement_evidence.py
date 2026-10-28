from __future__ import annotations

from datetime import datetime, timezone
import math
import unittest

from app.msc_settlement_evidence import MscSettlementEvidence


class MscSettlementEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.evidence = MscSettlementEvidence()
        self.evidence.start()

    def test_records_allowlisted_request_and_observation_fields(self) -> None:
        stamp = datetime(2026, 10, 28, 1, 2, 3, tzinfo=timezone.utc)
        self.evidence.record_request("msc", "primary", "Maximum Self Consumption", stamp, "accepted")
        self.evidence.record_observation(
            "msc", "msc", "Maximum Self Consumption", stamp,
            {
                "state": "Maximum Self Consumption",
                "last_reported": stamp,
                "available": True,
                "entity_id": "secret.entity",
                "url": "https://secret.invalid",
            },
            stamp, "succeeded", "accepted",
        )
        snapshot = self.evidence.finish("succeeded")
        self.assertEqual("succeeded", snapshot["status"])
        self.assertEqual(1, snapshot["request_count"])
        self.assertEqual(1, snapshot["observation_count"])
        self.assertEqual({"state": "Maximum Self Consumption", "last_reported": "2026-10-28T01:02:03.000000Z", "available": True}, snapshot["observations"][0]["observed"])
        self.assertEqual("accepted", snapshot["observations"][0]["reason"])
        self.assertNotIn("secret.entity", repr(snapshot))
        self.assertNotIn("secret.invalid", repr(snapshot))

    def test_fixed_bounds_keep_initial_and_latest_summaries(self) -> None:
        for index in range(40):
            self.evidence.record_observation(
                "export", "fallback", index, index, {"value": float(index)}, index,
                "pending", "timeout" if index % 2 else "accepted",
            )
        snapshot = self.evidence.snapshot()
        entries = snapshot["observations"]
        self.assertEqual(40, snapshot["observation_count"])
        self.assertEqual(12, len(entries))
        self.assertEqual(list(range(6)), [entry["expected"] for entry in entries[:6]])
        self.assertEqual(list(range(34, 40)), [entry["expected"] for entry in entries[6:]])
        self.assertEqual(20, snapshot["observation_reason_counts"]["timeout"])
        self.assertEqual(20, snapshot["observation_reason_counts"]["accepted"])

    def test_untrusted_strings_objects_and_extra_keys_are_dropped(self) -> None:
        self.evidence.record_request("msc", "primary", "token=secret", True, "private-error")
        self.evidence.record_observation(
            "msc", "primary", "untrusted-state", float("nan"),
            {
                "state": "private-state",
                "last_reported": float("inf"),
                "last_updated": True,
                "nested": {"password": "secret"},
                "entity_id": "secret.entity",
            },
            math.inf, "private-error", "raw exception text",
        )
        snapshot = self.evidence.snapshot()
        request = snapshot["requests"][0]
        observed = snapshot["observations"][0]
        self.assertIsNone(request["target"])
        self.assertIsNone(request["requested_at"])
        self.assertIsNone(request["outcome"])
        self.assertIsNone(observed["expected"])
        self.assertIsNone(observed["boundary"])
        self.assertEqual({}, observed["observed"])
        self.assertIsNone(observed["observed_at"])
        self.assertIsNone(observed["outcome"])
        self.assertEqual("unknown", observed["reason"])
        for forbidden in ("secret", "password", "private", "exception text"):
            self.assertNotIn(forbidden, repr(snapshot))

    def test_realistic_ha_iso_timestamps_numeric_state_and_known_ems_modes(self) -> None:
        self.evidence.record_observation(
            "export", "primary", 25.0, "2026-10-28T07:42:14.000000+11:00",
            {
                "state": "25.0",
                "last_updated": "2026-10-28T07:42:15.123456+11:00",
                "last_reported": "2026-10-27T20:42:14.123456Z",
            },
            "2026-10-28T07:42:16+11:00", "succeeded", "accepted",
        )
        self.evidence.record_observation(
            "msc", "msc", "Maximum Self Consumption", 100.0,
            {"state": "Command Discharging (ESS First)"}, 101.0, "pending", "state_mismatch",
        )
        observations = self.evidence.snapshot()["observations"]
        self.assertEqual(25.0, observations[0]["observed"]["state"])
        self.assertEqual("2026-10-27T20:42:15.123456Z", observations[0]["observed"]["last_updated"])
        self.assertEqual("2026-10-27T20:42:14.123456Z", observations[0]["observed"]["last_reported"])
        self.assertEqual("2026-10-27T20:42:14.000000Z", observations[0]["boundary"])
        self.assertEqual("Command Discharging (ESS First)", observations[1]["observed"]["state"])

    def test_future_and_invalid_iso_report_times_are_flagged_but_invalid_values_omitted(self) -> None:
        self.evidence.record_observation(
            "msc", "primary", "Maximum Self Consumption", "2026-10-28T07:42:00Z",
            {"state": "Maximum Self Consumption", "last_reported": "2026-10-28T07:42:01Z"},
            "2026-10-28T07:42:00Z", "pending", "accepted",
        )
        self.evidence.record_observation(
            "msc", "primary", "Maximum Self Consumption", 1.0,
            {"state": "Maximum Self Consumption", "last_updated": "not-a-timestamp"},
            2.0, "failed", "unknown",
        )
        self.evidence.record_observation(
            "msc", "primary", "Maximum Self Consumption", "not-a-boundary",
            {"state": "Maximum Self Consumption"}, "not-an-observation-time", "failed", "unknown",
        )
        observations = self.evidence.snapshot()["observations"]
        self.assertEqual(["future"], observations[0]["reason_flags"])
        self.assertEqual("2026-10-28T07:42:01.000000Z", observations[0]["observed"]["last_reported"])
        self.assertEqual(["invalid_timestamp"], observations[1]["reason_flags"])
        self.assertNotIn("last_updated", observations[1]["observed"])
        self.assertEqual(["invalid_timestamp"], observations[2]["reason_flags"])

    def test_metadata_status_is_allowlisted_and_namespaced_value_takes_precedence(self) -> None:
        for metadata in (
            {"_msc_metadata_status": "accepted", "metadata_status": "missing"},
            {"metadata_status": "read_failed"},
            {"_msc_metadata_status": "unknown-secret"},
        ):
            self.evidence.record_observation(
                "msc", "primary", "Automated", 1.0,
                {"state": "Automated", **metadata, "raw_error": "secret"},
                2.0, "pending", "read_failed",
            )
        observations = self.evidence.snapshot()["observations"]
        self.assertEqual("accepted", observations[0]["observed"]["metadata_status"])
        self.assertEqual("read_failed", observations[1]["observed"]["metadata_status"])
        self.assertNotIn("metadata_status", observations[2]["observed"])
        self.assertNotIn("unknown-secret", repr(observations))
        self.assertNotIn("secret", repr(observations))

    def test_invalid_labels_and_phases_do_not_add_records(self) -> None:
        self.evidence.record_request("entity.secret", "primary", 1, 1)
        self.evidence.record_request("msc", "entity_id", 1, 1)
        self.evidence.record_observation("export", "unexpected", 1, 1, {"value": 1}, 1, True)
        snapshot = self.evidence.snapshot()
        self.assertEqual(0, snapshot["request_count"])
        self.assertEqual(0, snapshot["observation_count"])

    def test_new_start_resets_attempt_and_old_snapshots_are_detached(self) -> None:
        self.evidence.record_request("export", "close", 25.0, 100.0, True)
        first = self.evidence.finish("failed")
        self.evidence.start()
        self.assertEqual(1, first["request_count"])
        second = self.evidence.snapshot()
        self.assertEqual(2, second["attempt"])
        self.assertEqual(0, second["request_count"])
        self.assertEqual("unreported", second["status"])
        second["requests"].append({"state": "mutated"})
        self.assertEqual([], self.evidence.snapshot()["requests"])

    def test_finish_rejects_unlisted_status_and_freezes_attempt(self) -> None:
        snapshot = self.evidence.finish("raw error message")
        self.assertEqual("unreported", snapshot["status"])
        self.evidence.record_request("msc", "primary", 1, 2, "accepted")
        self.assertEqual(0, self.evidence.snapshot()["request_count"])

    def test_non_mapping_objects_and_mapping_subclasses_are_ignored(self) -> None:
        class HostileDict(dict):
            def __iter__(self):
                raise RuntimeError("must not escape")

            def __str__(self):
                raise RuntimeError("must not stringify")

        self.evidence.record_observation("msc", "msc", True, object(), HostileDict(state="ON"), object(), True)
        self.evidence.record_observation("msc", "msc", True, 1, object(), 2, True)
        snapshot = self.evidence.snapshot()
        self.assertEqual(2, snapshot["observation_count"])
        self.assertEqual({}, snapshot["observations"][0]["observed"])
        self.assertEqual({}, snapshot["observations"][1]["observed"])
        self.assertIsNone(snapshot["observations"][0]["boundary"])
        self.assertIsNone(snapshot["observations"][0]["observed_at"])


if __name__ == "__main__":
    unittest.main()

class AdditionalDiagnosticFidelityTests(unittest.TestCase):
    def test_naive_datetimes_are_not_serialized_as_trusted_times(self):
        evidence = MscSettlementEvidence()
        evidence.record_observation("msc", "primary", "Maximum Self Consumption", datetime(2026, 10, 28),
                                    {"state": "unavailable"}, datetime(2026, 10, 28), False, "unavailable")
        entry = evidence.snapshot()["observations"][0]
        self.assertIsNone(entry["boundary"])
        self.assertIsNone(entry["observed_at"])
        self.assertEqual("unavailable", entry["observed"]["state"])
