from __future__ import annotations

import json
import copy
import math
import os
import tempfile
import unittest
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.decision_trace_store import DecisionTraceStore, RETENTION, STATUS_FILE

NOW = datetime(2026, 10, 3, 12, 30, tzinfo=timezone.utc)


def row(at: datetime = NOW, value: float = 1.0) -> dict:
    return {"ts": at.isoformat(timespec="seconds"), "summary": {"export_limit_kw": value},
            "state": {"pv_kw": value}, "gates": {"trusted": True}, "values": {"value": value}}


class DecisionTraceStoreTests(unittest.TestCase):
    def setUp(self):
        boot = patch.object(DecisionTraceStore, "_boot_identity", return_value="test-boot")
        boot.start()
        self.addCleanup(boot.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.store = DecisionTraceStore(Path(self.tmp.name) / "trace")
        self.stores = [self.store]
        self.store._clock_now = Mock(return_value=0.0)
        self.rows = deque(maxlen=1000)
        self.optimizer = SimpleNamespace(decision_trace=lambda limit: list(self.rows)[:limit])

    def tearDown(self):
        for store in self.stores:
            store.stop()
            self.assertTrue(store._closed.wait(5))
        self.tmp.cleanup()

    def flush(self, now=NOW):
        self.store._clock_now.return_value = (now - NOW).total_seconds()
        return self.store.flush(self.store.capture(self.optimizer), now)

    def restart(self):
        self.store.stop()
        self.assertTrue(self.store._closed.wait(5))
        restarted = DecisionTraceStore(self.store.directory)
        restarted._clock_now = Mock(return_value=self.store._clock_now())
        self.stores.append(restarted)
        return restarted

    def records(self):
        return [json.loads(line) for path in sorted(self.store.directory.glob("*.jsonl"))
                for line in path.read_bytes().splitlines()]

    def status(self):
        return json.loads((self.store.directory / STATUS_FILE).read_text(encoding="utf-8"))

    def test_location_follows_state_database_without_new_setting(self):
        with patch.dict(os.environ, {"STATE_DB_PATH": str(Path(self.tmp.name) / "state.db")}):
            self.assertEqual(DecisionTraceStore().directory, Path(self.tmp.name) / "decision_trace")
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(DecisionTraceStore().directory, Path("/data/decision_trace"))

    def test_first_write_and_overlapping_snapshots_preserve_cycle_order(self):
        first, second, third = row(value=1), row(value=2), row(value=3)
        self.rows.extendleft([first, second])
        self.assertTrue(self.flush())
        self.rows.appendleft(third)
        self.assertTrue(self.flush())
        self.assertTrue(self.flush())
        records = self.records()
        self.assertEqual([r["values"]["value"] for r in records], [1, 2, 3])
        self.assertEqual([r["_trace"]["sequence"] for r in records], [1, 2, 3])
        self.assertEqual(len({(r["_trace"]["session"], r["_trace"]["sequence"]) for r in records}), 3)

    def test_distinct_identical_rows_with_identical_second_timestamp(self):
        self.rows.extendleft([row(), row(), row()])
        self.flush()
        self.flush()
        self.assertEqual(len(self.records()), 3)

    def test_copies_and_nonfinite_normalization_leave_deque_unchanged(self):
        original = row(value=math.inf)
        original["values"]["nested"] = [math.nan, {"negative": -math.inf}]
        self.rows.appendleft(original)
        snapshot = self.store.capture(self.optimizer)
        snapshot[0]["summary"]["export_limit_kw"] = 3
        self.store.flush(snapshot, NOW)
        self.assertTrue(math.isinf(original["summary"]["export_limit_kw"]))
        self.assertNotIn("_trace", original)
        self.assertEqual(self.rows.maxlen, 1000)
        persisted = self.records()[0]
        self.assertIsNone(persisted["state"]["pv_kw"])
        self.assertEqual(persisted["values"]["nested"], [None, {"negative": None}])
        self.assertNotIn(b"Infinity", next(self.store.directory.glob("*.jsonl")).read_bytes())

    def test_partial_append_retry_recovers_complete_rows_without_duplicates(self):
        self.rows.extendleft([row(value=1), row(value=2), row(value=3)])
        captured = self.store.capture(self.optimizer)

        def partial(path, records):
            with path.open("ab") as handle:
                handle.write(records[0][1])
                handle.write(records[1][1][:20])
            raise OSError("test interrupted append")

        with patch.object(self.store, "_append", side_effect=partial), self.assertLogs(level="ERROR"):
            self.assertFalse(self.store.flush(captured, NOW))
        self.assertEqual(self.store._committed, set())
        with self.assertLogs(level="WARNING"):
            self.assertTrue(self.store.flush(self.store.capture(self.optimizer), NOW))
        self.assertEqual([r["_trace"]["sequence"] for r in self.records()], [1, 2, 3])

    def test_fsync_failure_is_not_acknowledged_until_recovery_succeeds(self):
        self.store.flush([], NOW)
        self.rows.appendleft(row())
        captured = self.store.capture(self.optimizer)
        with patch("app.decision_trace_store.os.fsync", side_effect=OSError("test fsync failure")), self.assertLogs(level="ERROR"):
            self.assertFalse(self.store.flush(captured, NOW))
        self.assertFalse(self.store._committed)
        self.assertTrue(self.store.flush(captured, NOW))
        self.assertEqual(len(self.records()), 1)

    def test_restart_retains_archive_and_uses_new_session(self):
        self.rows.appendleft(row())
        self.flush()
        restarted = self.restart()
        self.assertTrue(restarted.flush([], NOW))
        self.assertNotEqual(restarted.session, self.store.session)
        fresh = SimpleNamespace(decision_trace=lambda limit: [row()])
        restarted.flush(restarted.capture(fresh), NOW)
        self.assertEqual(len(self.records()), 2)
        self.assertEqual(len(restarted._committed), 2)
        self.assertTrue(self.status()["possible_gap"])
        self.assertIn("session_discontinuity", self.status()["reasons"])
        self.assertEqual(self.status()["last_session"], restarted.session)
        view = restarted.open_download(NOW)
        self.assertTrue(view.possible_gaps)
        view.close()

    def test_truncated_tail_preserves_valid_prefix_before_append(self):
        self.rows.appendleft(row())
        self.flush()
        path = next(self.store.directory.glob("*.jsonl"))
        valid = path.read_bytes()
        with path.open("ab") as handle:
            handle.write(b'{"ts":"truncated')
        restarted = self.restart()
        with self.assertLogs(level="WARNING"):
            self.assertTrue(restarted.flush([], NOW))
        self.assertEqual(path.read_bytes(), valid)
        self.assertEqual(len(restarted._committed), 1)
        self.assertIn("discarded_record", self.status()["reasons"])

    def test_malformed_interior_record_preserves_valid_records_on_both_sides(self):
        self.rows.extendleft([row(value=1), row(value=2)])
        self.flush()
        path = next(self.store.directory.glob("*.jsonl"))
        lines = path.read_bytes().splitlines(keepends=True)
        path.write_bytes(lines[0] + b"invalid JSON\n" + lines[1])
        restarted = self.restart()
        with self.assertLogs(level="WARNING"):
            self.assertTrue(restarted.flush([], NOW))
        self.assertEqual(path.read_bytes(), b"".join(lines))
        self.assertEqual(len(restarted._committed), 2)
        self.assertIn("discarded_record", self.status()["reasons"])

    def test_prune_boundary_and_hourly_deletion_only_rewrite_boundary(self):
        cutoff = NOW - RETENTION
        timestamps = [cutoff - timedelta(hours=1), cutoff - timedelta(seconds=1),
                      cutoff, cutoff + timedelta(seconds=1), cutoff + timedelta(hours=1)]
        self.rows.extendleft([row(at) for at in timestamps])
        self.assertTrue(self.store.flush(self.store.capture(self.optimizer), NOW - timedelta(hours=2)))
        newer_path = self.store._path(timestamps[-1])
        newer_bytes = newer_path.read_bytes()
        self.store._clock_now.return_value = 7200.0
        with patch.object(self.store, "_replace", wraps=self.store._replace) as rewrite:
            self.store.flush([], NOW)
        self.assertEqual(rewrite.call_count, 1)
        self.assertEqual(rewrite.call_args.args[0], self.store._path(cutoff))
        self.assertFalse(self.store._path(timestamps[0]).exists())
        self.assertEqual(newer_path.read_bytes(), newer_bytes)
        self.assertEqual([r["ts"] for r in self.records()], [r.isoformat(timespec="seconds") for r in timestamps[2:]])

    def test_expired_snapshot_rows_are_never_reappended(self):
        self.rows.appendleft(row(NOW - RETENTION - timedelta(seconds=1)))
        self.assertTrue(self.flush())
        self.assertTrue(self.flush())
        self.assertEqual(self.records(), [])

    def test_missing_overlap_warns_and_marks_possible_gap_with_bounded_observer(self):
        self.rows.appendleft(row())
        self.flush()
        for i in range(1001):
            self.rows.appendleft(row(value=i))
        with self.assertLogs(level="WARNING") as captured:
            self.flush()
        self.assertIn("missing deque overlap", " ".join(captured.output))
        self.assertTrue(self.records()[-1]["_trace"]["possible_gap"])
        self.assertEqual(len(self.store._observed), 1000)
        self.assertIn("deque_overflow", self.status()["reasons"])

    def test_recovery_removes_only_recognized_orphan_compaction_files(self):
        self.rows.appendleft(row())
        self.flush()
        self.store.stop()
        self.assertTrue(self.store._closed.wait(5))
        directory = self.store.directory
        recognized = [directory / "20251002T12.tmp", directory / (STATUS_FILE + ".tmp")]
        unrelated = [directory / "notes.tmp", directory / "20251302T12.tmp",
                     directory / "20251002T12.jsonl.tmp"]
        for path in recognized + unrelated:
            path.write_bytes(b"orphan test")
        (directory / "20251001T12.tmp").mkdir()
        restarted = self.restart()
        restarted._clock_now.return_value = 25 * 3600
        self.assertTrue(restarted.flush([], NOW + timedelta(hours=25)))
        self.assertTrue(all(not path.exists() for path in recognized))
        self.assertTrue(all(path.read_bytes() == b"orphan test" for path in unrelated))
        self.assertTrue((directory / "20251001T12.tmp").is_dir())
        self.assertIn("orphan_compaction", self.status()["reasons"])

    def test_clock_jumps_preserve_archive_and_pruning_resumes_after_correction(self):
        self.rows.appendleft(row(NOW - timedelta(hours=23)))
        self.flush()
        before = {path: path.read_bytes() for path in self.store.directory.glob("*.jsonl")}
        with patch.object(self.store, "_prune", wraps=self.store._prune) as prune:
            for offset in (26, -26):
                self.store._clock_now.return_value += 60
                self.assertTrue(self.store.flush([], NOW + timedelta(hours=offset)))
                self.assertEqual({path: path.read_bytes() for path in before}, before)
            prune.assert_not_called()
        self.assertIn("clock_discontinuity", self.status()["reasons"])
        view = self.store.open_download(NOW + timedelta(hours=26))
        self.assertTrue(view.possible_gaps)
        self.assertEqual(len(b"".join(view.chunks()).splitlines()), 1)
        self.store._clock_now.return_value = 25 * 3600
        self.assertTrue(self.store.flush([], NOW + timedelta(hours=25)))
        self.assertEqual(self.records(), [])
        self.assertTrue(self.status()["possible_gap"])

    def test_archive_status_commit_failure_prevents_row_acknowledgement(self):
        self.rows.appendleft(row())
        with patch.object(self.store, "_save_status", side_effect=OSError("status unavailable")), self.assertLogs(level="ERROR"):
            self.assertFalse(self.flush())
        self.assertFalse(self.store._committed)
        self.assertFalse(self.store.ready)
        self.assertTrue(self.flush())
        self.assertEqual(len(self.records()), 1)
        self.assertEqual(set(self.status()), {"possible_gap", "reasons", "last_session", "clock"})

    def test_clock_uncertainty_survives_restart_and_correction_resumes_writes_and_pruning(self):
        self.rows.appendleft(row(NOW - timedelta(hours=23)))
        self.flush()
        before = {path: path.read_bytes() for path in self.store.directory.glob("*.jsonl")}
        self.store._clock_now.return_value = 60.0
        self.assertTrue(self.store.flush([], NOW + timedelta(hours=26)))
        self.assertTrue(self.status()["clock"]["uncertain"])
        self.assertEqual(self.status()["clock"]["anchor"], NOW.isoformat())
        restarted = self.restart()
        with patch.object(restarted, "_prune", wraps=restarted._prune) as prune:
            self.assertTrue(restarted.flush([], NOW + timedelta(hours=26)))
            prune.assert_not_called()
        self.assertTrue(restarted._clock_uncertain)
        self.assertTrue(self.status()["clock"]["uncertain"])
        self.assertEqual({path: path.read_bytes() for path in before}, before)

        # Correction agrees with the persisted same-boot monotonic anchor,
        # including elapsed time before/during the application restart.
        corrected = NOW + timedelta(hours=2)
        restarted._clock_now.return_value = 7200.0
        self.assertTrue(restarted.flush([], corrected))
        self.assertFalse(restarted._clock_uncertain)
        self.assertTrue(all(not path.exists() for path in before))
        fresh = row(corrected)
        bad_clock_row = row(NOW + timedelta(hours=26))
        optimizer = SimpleNamespace(decision_trace=lambda limit: [fresh, bad_clock_row])
        self.assertTrue(restarted.flush(restarted.capture(optimizer), corrected))
        self.assertEqual([record["ts"] for record in self.records()], [fresh["ts"]])
        self.assertFalse(self.status()["clock"]["uncertain"])
        self.assertTrue(self.status()["possible_gap"])

    def test_uncertain_clock_never_adopts_a_startup_sample_from_an_unknown_boot(self):
        self.rows.appendleft(row())
        self.flush()
        self.store._clock_now.return_value = 60.0
        self.store.flush([], NOW + timedelta(hours=26))
        before = {path: path.read_bytes() for path in self.store.directory.glob("*.jsonl")}
        with patch.object(DecisionTraceStore, "_boot_identity", return_value=None):
            restarted = self.restart()
            restarted._clock_now.return_value = 0.0  # A reboot resets monotonic time.
            self.assertTrue(restarted.flush([], NOW + timedelta(hours=26)))
        self.assertTrue(restarted._clock_uncertain)
        self.assertEqual({path: path.read_bytes() for path in before}, before)
        # Without provable downtime, only agreement with the retained UTC
        # anchor plus this process's elapsed time can reconcile the clock.
        restarted._clock_now.return_value = 60.0
        self.assertTrue(restarted.flush([], NOW + timedelta(seconds=60)))
        self.assertFalse(restarted._clock_uncertain)

    def test_72_hours_of_clock_uncertainty_freezes_archive_and_identity_bookkeeping(self):
        self.rows.appendleft(row())
        self.flush()
        self.store._clock_now.return_value = 60.0
        self.store.flush([], NOW + timedelta(hours=26))
        before = {path: path.read_bytes() for path in self.store.directory.glob("*.jsonl")}
        lengths, ids = self.store._lengths.copy(), copy.deepcopy(self.store._ids)
        committed = self.store._committed.copy()
        confirmed = self.store._confirmed_sequences
        observed, sequence = self.store._observed.copy(), self.store._sequence
        with patch.object(self.store, "_append", wraps=self.store._append) as append, patch.object(
            self.store, "_prune", wraps=self.store._prune
        ) as prune:
            for hour in range(1, 73):
                at = NOW + timedelta(hours=26 + hour)
                self.rows.extendleft(row(at, value=i) for i in range(1001))
                live_rows = list(self.rows)
                self.assertEqual(self.store.capture(self.optimizer), [])
                self.assertEqual(list(self.rows), live_rows)
                self.assertEqual(self.rows.maxlen, 1000)
                self.store._clock_now.return_value = hour * 3600.0
                # Even a caller-provided snapshot cannot bypass the write pause.
                candidate = row(at)
                candidate["_trace"] = {"session": self.store.session, "sequence": hour + 1}
                self.assertTrue(self.store.flush([candidate], at))
            append.assert_not_called()
            prune.assert_not_called()
        self.assertEqual({path: path.read_bytes() for path in before}, before)
        self.assertEqual(self.store._lengths, lengths)
        self.assertEqual(self.store._ids, ids)
        self.assertEqual(self.store._committed, committed)
        self.assertEqual(self.store._confirmed_sequences, confirmed)
        self.assertEqual(self.store._observed, observed)
        self.assertEqual(self.store._sequence, sequence)
        self.assertTrue(self.status()["clock"]["uncertain"])
        self.assertTrue(self.status()["possible_gap"])

    def test_full_first_snapshot_reports_possible_missing_history(self):
        self.rows.extend(row() for _ in range(1000))
        with self.assertLogs(level="WARNING"):
            self.store.capture(self.optimizer)
        self.assertEqual(self.store._gap_count, 1)

    def test_failed_write_then_eviction_warns_even_when_newest_overlap_survives(self):
        older, newer = row(value=1), row(value=2)
        self.rows.extendleft([older, newer])
        with patch.object(self.store, "_append", side_effect=OSError("test write failure")), self.assertLogs(level="ERROR"):
            self.flush()
        self.rows.pop()
        self.rows.appendleft(row(value=3))
        with self.assertLogs(level="WARNING") as captured:
            self.flush()
        self.assertIn("unpersisted cycles left the deque", " ".join(captured.output))
        self.assertTrue(self.records()[-1]["_trace"]["possible_gap"])

    def test_recovery_write_serialization_and_prune_failures_are_isolated(self):
        self.rows.appendleft(row())
        with patch.object(self.store, "_recover", side_effect=OSError("test recovery failure")), self.assertLogs(level="ERROR"):
            self.assertFalse(self.flush())
        self.assertFalse(self.store.ready)
        with patch.object(self.store, "_append", side_effect=OSError("test write failure")), self.assertLogs(level="ERROR"):
            self.assertFalse(self.flush())
        self.assertTrue(self.flush())
        bad = row()
        bad["values"]["bad"] = object()
        self.rows.appendleft(bad)
        with self.assertLogs(level="ERROR"):
            self.assertTrue(self.flush())
        bad["values"]["bad"] = None
        self.assertTrue(self.flush())
        self.assertEqual(len(self.records()), 2)
        self.store._clock_now.return_value = 24 * 3600
        with patch.object(self.store, "_replace", side_effect=OSError("test prune failure")), self.assertLogs(level="ERROR"):
            self.assertTrue(self.store.flush([], NOW + timedelta(hours=24)))
        self.assertTrue(self.store.flush([], NOW + timedelta(hours=24)))

