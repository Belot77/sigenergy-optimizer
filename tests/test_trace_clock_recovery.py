from __future__ import annotations

import json
import asyncio
import threading
import tempfile
import subprocess
import os
from email.utils import format_datetime
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.decision_trace_store import DecisionTraceStore, STATUS_FILE
from app import trace_clock

OLD = datetime(2026, 10, 18, 12, tzinfo=timezone.utc)
CURRENT = OLD + timedelta(days=6)


def trace_row(at):
    return {"ts": at.isoformat(), "summary": {}, "state": {}, "gates": {}, "values": {}}


class TraceClockRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self.tmp.name) / "trace"
        self.stores = []
        self.boot = patch.object(DecisionTraceStore, "_boot_identity", return_value="old-boot")
        self.boot_mock = self.boot.start()
        self.addCleanup(self.boot.stop)
        # No real external service is used by these deterministic archive tests.
        self.proof = patch.object(DecisionTraceStore, "_corroborated_time", return_value=False, create=True)
        self.proof_mock = self.proof.start()
        self.addCleanup(self.proof.stop)

    def tearDown(self):
        for store in self.stores:
            store.stop()
            self.assertTrue(store._closed.wait(5))
        self.tmp.cleanup()

    def new_store(self, monotonic):
        store = DecisionTraceStore(self.directory)
        store._clock_now = Mock(return_value=monotonic)
        self.stores.append(store)
        return store

    def seed(self):
        store = self.new_store(100)
        optimizer = SimpleNamespace(decision_trace=lambda limit: [trace_row(OLD)])
        self.assertTrue(store.flush(store.capture(optimizer), OLD))
        before = {path.name: path.read_bytes() for path in self.directory.glob("*.jsonl")}
        store.stop()
        self.assertTrue(store._closed.wait(5))
        return before

    def test_restored_six_day_archive_recovers_only_with_independent_time_proof(self):
        before = self.seed()
        self.boot_mock.return_value = "replacement-boot"
        recovered = self.new_store(5)
        self.assertTrue(recovered.flush([], CURRENT))
        self.assertTrue(recovered._clock_uncertain)
        self.assertEqual({path.name: path.read_bytes() for path in self.directory.glob("*.jsonl")}, before)
        self.proof_mock.return_value = True
        recovered._next_attestation = 0
        self.assertTrue(recovered.flush([], CURRENT))
        self.assertFalse(recovered._clock_uncertain)
        live = trace_row(CURRENT)
        optimizer = SimpleNamespace(decision_trace=lambda limit: [live])
        self.assertTrue(recovered.flush(recovered.capture(optimizer), CURRENT))
        self.assertEqual(recovered._sequence, 1)
        records = [json.loads(line) for path in self.directory.glob("*.jsonl")
                   for line in path.read_bytes().splitlines()]
        self.assertEqual([record["ts"] for record in records], [live["ts"]])
        self.assertTrue(records[0]["_trace"]["possible_gap"])
        status = json.loads((self.directory / STATUS_FILE).read_text())
        self.assertFalse(status["clock"]["uncertain"])
        self.assertIn("clock_discontinuity", status["reasons"])
        preserved = list((self.directory / "clock-history").glob("*"))
        self.assertEqual(len(preserved), 1)
        self.assertEqual({path.name: path.read_bytes() for path in preserved[0].glob("*.jsonl")}, before)
        recovered.flush(recovered.capture(optimizer), CURRENT)
        self.assertEqual(len(recovered._committed), 1)

    def test_reboot_short_downtime_also_requires_proof_despite_300_second_tolerance(self):
        self.seed()
        self.boot_mock.return_value = "new-boot"
        recovered = self.new_store(5)
        self.assertTrue(recovered.flush([], OLD + timedelta(seconds=30)))
        self.assertTrue(recovered._clock_uncertain)
        self.assertEqual(recovered.capture(SimpleNamespace(decision_trace=lambda limit: [trace_row(OLD)])), [])


    def recovered(self):
        before = self.seed()
        self.boot_mock.return_value = "new-boot"
        store = self.new_store(5)
        self.proof_mock.return_value = True
        return store, before

    def test_failed_cross_boot_proof_remains_required_after_same_boot_app_restart(self):
        self.seed()
        self.boot_mock.return_value = "new-boot"
        store = self.new_store(5)
        store.flush([], CURRENT)
        self.assertTrue(store._clock_uncertain)
        self.assertTrue(json.loads((self.directory / STATUS_FILE).read_text())["clock"]["requires_attestation"])
        before = {p.name: p.read_bytes() for p in self.directory.glob("*.jsonl")}
        store.stop()
        self.assertTrue(store._closed.wait(5))
        restarted = self.new_store(65)
        # This agrees with the fabricated old epoch, not current UTC.
        restarted.flush([], OLD + timedelta(seconds=60))
        self.assertTrue(restarted._clock_uncertain)
        self.assertEqual(restarted.capture(SimpleNamespace(decision_trace=lambda limit: [trace_row(OLD)])), [])
        self.assertEqual({p.name: p.read_bytes() for p in self.directory.glob("*.jsonl")}, before)

    def test_unavailable_proof_is_rate_limited_and_download_never_probes(self):
        store, before = self.recovered()
        self.proof_mock.return_value = False
        store.flush([], CURRENT)
        store.flush([], CURRENT)
        view = store.open_download(CURRENT)
        view.close()
        self.assertEqual(self.proof_mock.call_count, 1)
        store._clock_now.return_value = 905
        store.flush([], CURRENT + timedelta(seconds=900))
        self.assertEqual(self.proof_mock.call_count, 2)
        self.assertEqual({p.name: p.read_bytes() for p in self.directory.glob("*.jsonl")}, before)

    def test_same_boot_restart_requires_no_network_and_preserves_original_session_gap(self):
        self.seed()
        store = self.new_store(200)
        store.flush([], OLD + timedelta(seconds=100))
        self.proof_mock.assert_not_called()
        self.assertFalse(store._clock_uncertain)
        self.assertTrue(store.possible_gap)
        self.assertFalse((self.directory / "clock-history").exists())

    def test_preservation_publish_failure_keeps_original_bytes_and_no_acknowledgement(self):
        store, before = self.recovered()
        original_replace = os.replace
        def fail_history(source, target):
            if Path(source).name.endswith(".pending"):
                raise OSError("synthetic interrupted history publication")
            return original_replace(source, target)
        with patch("app.decision_trace_store.os.replace", side_effect=fail_history), self.assertLogs(level="ERROR"):
            self.assertFalse(store.flush([], CURRENT))
        self.assertTrue(store._clock_uncertain)
        self.assertEqual({p.name: p.read_bytes() for p in self.directory.glob("*.jsonl")}, before)
        self.assertEqual(len(list((self.directory / "clock-history").glob("*.pending"))), 1)
        store.stop()
        self.assertTrue(store._closed.wait(5))
        restarted = self.new_store(6)
        self.assertTrue(restarted.flush([], CURRENT))
        self.assertFalse(restarted._clock_uncertain)
        self.assertEqual(len(list((self.directory / "clock-history").iterdir())), 1)

    def test_restart_after_history_publish_before_status_commit_reuses_verified_copy(self):
        store, before = self.recovered()
        original_save = store._save_status
        def fail_new_anchor():
            if not store._clock_uncertain:
                raise OSError("synthetic new anchor commit failure")
            return original_save()
        with patch.object(store, "_save_status", side_effect=fail_new_anchor), self.assertLogs(level="ERROR"):
            self.assertFalse(store.flush([], CURRENT))
        self.assertTrue(store._clock_uncertain)
        self.assertEqual({p.name: p.read_bytes() for p in self.directory.glob("*.jsonl")}, before)
        history = self.directory / "clock-history"
        epoch = next(history.iterdir())
        original_copy = {p.name: p.read_bytes() for p in epoch.iterdir()}
        store.stop()
        self.assertTrue(store._closed.wait(5))
        restarted = self.new_store(6)
        self.assertTrue(restarted.flush([], CURRENT))
        self.assertFalse(restarted._clock_uncertain)
        self.assertEqual(len(list(history.iterdir())), 1)
        self.assertEqual({p.name: p.read_bytes() for p in epoch.iterdir()}, original_copy)

    def test_tampered_preserved_copy_prevents_anchor_commit_and_pruning(self):
        store, before = self.recovered()
        original_save = store._save_status
        def fail_new_anchor():
            if not store._clock_uncertain:
                raise OSError("synthetic status failure")
            return original_save()
        with patch.object(store, "_save_status", side_effect=fail_new_anchor), self.assertLogs(level="ERROR"):
            store.flush([], CURRENT)
        epoch = next((self.directory / "clock-history").iterdir())
        next(epoch.glob("*.jsonl")).write_bytes(b"synthetic corruption")
        store._next_attestation = 0
        with self.assertLogs(level="ERROR"):
            self.assertFalse(store.flush([], CURRENT))
        self.assertTrue(store._clock_uncertain)
        self.assertEqual({p.name: p.read_bytes() for p in self.directory.glob("*.jsonl")}, before)

    def test_full_corrupt_source_bytes_survive_before_active_repair(self):
        before = self.seed()
        path = next(self.directory.glob("*.jsonl"))
        path.write_bytes(path.read_bytes() + b'{"incomplete')
        original = path.read_bytes()
        self.boot_mock.return_value = "new-boot"
        store = self.new_store(5)
        self.proof_mock.return_value = True
        with self.assertLogs(level="WARNING"):
            self.assertTrue(store.flush([], CURRENT))
        epoch = next((self.directory / "clock-history").iterdir())
        self.assertEqual((epoch / path.name).read_bytes(), original)
        self.assertFalse(path.exists())
        self.assertIn("discarded_record", json.loads((self.directory / STATUS_FILE).read_text())["reasons"])

    def test_new_anchor_restart_has_no_duplicate_or_repeated_history(self):
        store, before = self.recovered()
        store.flush([], CURRENT)
        optimizer = SimpleNamespace(decision_trace=lambda limit: [trace_row(CURRENT)])
        store.flush(store.capture(optimizer), CURRENT)
        store.stop()
        self.assertTrue(store._closed.wait(5))
        restarted = self.new_store(6)
        self.proof_mock.reset_mock()
        restarted.flush([], CURRENT + timedelta(seconds=1))
        self.proof_mock.assert_not_called()
        self.assertFalse(restarted._clock_uncertain)
        self.assertEqual(len(restarted._committed), 1)
        self.assertEqual(len(list((self.directory / "clock-history").iterdir())), 1)


    def assert_preservation_fault(self, target):
        store, before = self.recovered()
        self.proof_mock.return_value = False
        store.flush([], CURRENT)
        self.proof_mock.return_value = True
        store._next_attestation = 0
        with patch.object(store, target, side_effect=OSError("synthetic disk/fsync failure")), self.assertLogs(level="ERROR"):
            self.assertFalse(store.flush([], CURRENT))
        self.assertTrue(store._clock_uncertain)
        self.assertEqual({p.name: p.read_bytes() for p in self.directory.glob("*.jsonl")}, before)

    def test_preservation_read_failure_leaves_archive_and_uncertainty_intact(self):
        self.assert_preservation_fault("_file_digest")

    def test_preservation_sync_failure_leaves_archive_and_uncertainty_intact(self):
        self.assert_preservation_fault("_sync_directory")

    def test_disk_full_while_copying_does_not_modify_original_or_publish_epoch(self):
        store, before = self.recovered()
        original_open = Path.open
        def disk_full(path, mode="r", *args, **kwargs):
            if "w" in mode and path.parent.name.endswith(".pending") and path.suffix == ".jsonl":
                raise OSError("synthetic full disk")
            return original_open(path, mode, *args, **kwargs)
        with patch.object(Path, "open", disk_full), self.assertLogs(level="ERROR"):
            self.assertFalse(store.flush([], CURRENT))
        self.assertTrue(store._clock_uncertain)
        self.assertEqual({p.name: p.read_bytes() for p in self.directory.glob("*.jsonl")}, before)
        self.assertTrue(all(path.name.endswith(".pending") for path in (self.directory / "clock-history").iterdir()))

    def test_failed_directory_sync_after_anchor_replace_is_safe_on_restart(self):
        store, before = self.recovered()
        original_sync = store._sync_directory
        def fail_after_anchor(directory):
            if not store._clock_uncertain and Path(directory) == self.directory:
                raise OSError("synthetic crash after anchor replacement")
            return original_sync(directory)
        with patch.object(store, "_sync_directory", side_effect=fail_after_anchor), self.assertLogs(level="ERROR"):
            self.assertFalse(store.flush([], CURRENT))
        self.assertTrue(store._clock_uncertain)
        self.assertEqual({p.name: p.read_bytes() for p in self.directory.glob("*.jsonl")}, before)
        store.stop()
        self.assertTrue(store._closed.wait(5))
        restarted = self.new_store(6)
        self.proof_mock.reset_mock()
        restarted.flush([], CURRENT + timedelta(seconds=1))
        self.proof_mock.assert_not_called()
        self.assertFalse(restarted._clock_uncertain)
        epoch = next((self.directory / "clock-history").iterdir())
        self.assertEqual({p.name: p.read_bytes() for p in epoch.glob("*.jsonl")}, before)

    def test_bad_clock_correction_and_interrupted_append_resume_without_duplicates(self):
        store, before = self.recovered()
        store.flush([], CURRENT)
        live = trace_row(CURRENT)
        future = trace_row(CURRENT + timedelta(days=2))
        optimizer = SimpleNamespace(decision_trace=lambda limit: [live, future])
        captured = store.capture(optimizer)
        def interrupted(path, records):
            with path.open("ab") as writer:
                writer.write(records[0][1])
                writer.write(b'{"partial')
            raise OSError("synthetic append interruption")
        with patch.object(store, "_append", side_effect=interrupted), self.assertLogs(level="ERROR"):
            self.assertFalse(store.flush(captured, CURRENT))
        with self.assertLogs(level="WARNING"):
            self.assertTrue(store.flush(captured, CURRENT))
        self.assertEqual(len(store._committed), 1)
        self.assertEqual([json.loads(line)["ts"] for p in self.directory.glob("*.jsonl")
                          for line in p.read_bytes().splitlines()], [live["ts"]])
        self.assertIn("discarded_record", json.loads((self.directory / STATUS_FILE).read_text())["reasons"])
        epoch = next((self.directory / "clock-history").iterdir())
        self.assertEqual({p.name: p.read_bytes() for p in epoch.glob("*.jsonl")}, before)

    def test_cancelled_await_does_not_release_running_probe_or_block_event_loop(self):
        store, before = self.recovered()
        entered, release = threading.Event(), threading.Event()
        def probe(now):
            entered.set()
            if not release.wait(5):
                raise OSError("synthetic probe release timeout")
            return None
        async def exercise():
            task = asyncio.create_task(store.run_worker(store.flush, [], CURRENT))
            try:
                self.assertTrue(await asyncio.to_thread(entered.wait, 5))
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await asyncio.wait_for(task, .5)
                self.assertFalse(store._closed.is_set())
                store.stop()
                self.assertFalse(store._closed.is_set())
            finally:
                release.set()
            self.assertTrue(await asyncio.to_thread(store._closed.wait, 5))
        with patch.object(store, "_corroborated_time", side_effect=probe):
            asyncio.run(exercise())
        self.assertEqual({p.name: p.read_bytes() for p in self.directory.glob("*.jsonl")}, before)

    def test_preservation_limits_never_authorize_pruning(self):
        store, before = self.recovered()
        with patch("app.decision_trace_store.MAX_HISTORY_BYTES", 1), self.assertLogs(level="ERROR"):
            self.assertFalse(store.flush([], CURRENT))
        self.assertTrue(store._clock_uncertain)
        self.assertEqual({p.name: p.read_bytes() for p in self.directory.glob("*.jsonl")}, before)


class TraceTimeProofTests(unittest.TestCase):
    def proof(self, responses=None, ticks=None, wall=None):
        if responses is None:
            responses = [Mock(status_code=200, headers=Mock()), Mock(status_code=204, headers=Mock())]
            for response in responses:
                response.headers.get_list.side_effect = lambda name: [format_datetime(CURRENT, usegmt=True)] if name == "date" else []
        client = Mock()
        client.head.side_effect = responses
        context = Mock()
        context.__enter__ = Mock(return_value=client)
        context.__exit__ = Mock(return_value=False)
        with patch.object(trace_clock.httpx, "Client", return_value=context) as factory, patch.object(
            trace_clock.time, "monotonic", side_effect=ticks or [0, .1, .2, .3, .4, .5]
        ), patch.object(trace_clock, "datetime", wraps=datetime) as clock:
            clock.now.return_value = wall or CURRENT
            result = trace_clock.corroborate(CURRENT)
        return result, client, factory

    def test_two_https_sources_require_verified_tls_no_proxy_no_redirect_and_no_cache_nonce(self):
        proof, client, factory = self.proof()
        self.assertEqual(proof["method"], "dual_https_date")
        self.assertEqual([s["source"] for s in proof["sources"]], ["google", "cloudflare"])
        factory.assert_called_once_with(verify=True, trust_env=False, follow_redirects=False, timeout=3)
        self.assertEqual(client.head.call_count, 2)
        for call in client.head.call_args_list:
            self.assertEqual(call.kwargs["headers"]["Cache-Control"], "no-cache, no-store")
            self.assertEqual(len(call.kwargs["params"]["trace_clock_nonce"]), 32)

    def test_redirect_cache_missing_malformed_old_future_and_duplicate_dates_fail_closed(self):
        good = format_datetime(CURRENT, usegmt=True)
        cases = [(301, [good], []), (304, [good], []), (200, [], []),
                 (200, [good], ["1"]), (200, [good], ["bad"]), (200, [good, good], []),
                 (200, ["bad"], []), (200, [good.replace("GMT", "EST")], []),
                 (200, [format_datetime(OLD, usegmt=True)], []),
                 (200, [format_datetime(CURRENT + timedelta(hours=2), usegmt=True)], [])]
        for status, dates, ages in cases:
            with self.subTest(status=status, dates=dates, ages=ages):
                response = Mock(status_code=status, headers=Mock())
                response.headers.get_list.side_effect = lambda name: dates if name == "date" else ages
                self.assertIsNone(self.proof([response])[0])

    def test_tls_timeout_slow_rtt_wall_step_and_source_disagreement_fail_closed(self):
        self.assertIsNone(self.proof([OSError("synthetic TLS failure")])[0])
        self.assertIsNone(self.proof(ticks=[0, .1, 4])[0])
        self.assertIsNone(self.proof(wall=CURRENT + timedelta(hours=1))[0])
        responses = []
        for offset in (-5, 5):
            response = Mock(status_code=200, headers=Mock())
            date = format_datetime(CURRENT + timedelta(seconds=offset), usegmt=True)
            response.headers.get_list.side_effect = lambda name, date=date: [date] if name == "date" else []
            responses.append(response)
        self.assertIsNone(self.proof(responses)[0])

    def test_subprocess_deadline_malformed_output_and_failure_never_establish_proof(self):
        store = DecisionTraceStore(Path(tempfile.gettempdir()) / "unused-trace-time-test")
        try:
            for outcome in (subprocess.TimeoutExpired("probe", 12), OSError("synthetic child failure")):
                with self.subTest(outcome=type(outcome).__name__), patch(
                    "app.decision_trace_store.subprocess.run", side_effect=outcome
                ) as run:
                    self.assertIsNone(store._corroborated_time(datetime.now(timezone.utc)))
                    self.assertEqual(run.call_args.kwargs["timeout"], 12)
                    self.assertIn("app.trace_clock", run.call_args.args[0])
            for output in ("", "partial{", "null", "{}", '{"method":"dual_https_date","sources":[]}', "x" * 2049):
                with self.subTest(output=output[:25]), patch(
                    "app.decision_trace_store.subprocess.run", return_value=Mock(stdout=output)
                ):
                    self.assertIsNone(store._corroborated_time(datetime.now(timezone.utc)))
        finally:
            store.stop()
            self.assertTrue(store._closed.wait(5))
