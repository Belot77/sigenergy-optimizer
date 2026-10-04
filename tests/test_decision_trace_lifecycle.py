from __future__ import annotations

import asyncio
import ast
import copy
import json
import tempfile
import threading
import time
import unittest
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from fastapi import FastAPI

from app import main
from app.decision_trace_store import DecisionTraceStore, MAX_PENDING_WORK
from app.routers.api import get_decision_trace


def trace_row():
    return {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "summary": {}, "state": {}, "gates": {"trusted": True}, "values": {"pv_kw": 3.0}}


class DecisionTraceLifecycleTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = DecisionTraceStore(Path(self.tmp.name) / "trace")
        self.rows = deque([trace_row()], maxlen=1000)
        self.optimizer = SimpleNamespace(
            decision_trace=lambda limit: list(self.rows)[:limit],
            run_once=AsyncMock(), trigger_queue=asyncio.Queue(),
        )

    def tearDown(self):
        self.store.stop()
        self.assertTrue(self.store._closed.wait(5))
        self.tmp.cleanup()

    async def test_periodic_interval_is_900_seconds_and_sleep_cancellation_is_clean(self):
        with patch("app.decision_trace_store.asyncio.sleep", new=AsyncMock(side_effect=asyncio.CancelledError)) as sleep:
            with self.assertRaises(asyncio.CancelledError):
                await self.store.run_forever(self.optimizer)
        sleep.assert_awaited_once_with(900)
        self.optimizer.run_once.assert_not_awaited()
        self.assertTrue(self.optimizer.trigger_queue.empty())
        self.assertTrue(self.store._stopping.is_set())

    async def test_periodic_pass_captures_without_cycle_trigger_or_row_mutation(self):
        sleeps = 0

        async def interval(seconds):
            nonlocal sleeps
            self.assertEqual(seconds, 900)
            sleeps += 1
            if sleeps == 2:
                raise asyncio.CancelledError

        before = copy.deepcopy(list(self.rows))
        with patch("app.decision_trace_store.asyncio.sleep", side_effect=interval):
            with self.assertRaises(asyncio.CancelledError):
                await self.store.run_forever(self.optimizer)
        self.assertEqual(list(self.rows), before)
        self.assertEqual(self.rows.maxlen, 1000)
        self.optimizer.run_once.assert_not_awaited()
        self.assertTrue(self.optimizer.trigger_queue.empty())
        self.assertEqual(len(list(self.store.directory.glob("*.jsonl"))), 1)

    async def test_existing_api_preserves_newest_first_order_and_schema(self):
        second = trace_row()
        second["values"]["pv_kw"] = 4.0
        self.rows.appendleft(second)
        captured = self.store.capture(self.optimizer)
        await asyncio.to_thread(self.store.flush, captured)
        request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(optimizer=self.optimizer)),
                                  client=SimpleNamespace(host="127.0.0.1"), headers={})
        result = await get_decision_trace(request, limit=1000)
        self.assertEqual(result, {"rows": list(self.rows)})
        self.assertIs(result["rows"][0], second)
        self.assertNotIn("_trace", second)

    async def test_active_worker_does_not_block_event_loop_and_cancellation_does_not_wait(self):
        started, release, finished = threading.Event(), threading.Event(), threading.Event()
        original_append = self.store._append

        def slow_append(path, records):
            started.set()
            try:
                if not release.wait(5):
                    raise RuntimeError("test worker was not released")
                original_append(path, records)
            finally:
                finished.set()

        self.store.flush([], datetime.now(timezone.utc))
        entered = asyncio.Event()

        async def interval(_):
            if entered.is_set():
                await asyncio.Event().wait()
            entered.set()

        with patch.object(self.store, "_append", side_effect=slow_append), patch(
            "app.decision_trace_store.asyncio.sleep", side_effect=interval
        ):
            task = asyncio.create_task(self.store.run_forever(self.optimizer))
            try:
                self.assertTrue(await asyncio.to_thread(started.wait, 5))
                marker = asyncio.Event()
                asyncio.get_running_loop().call_soon(marker.set)
                await asyncio.wait_for(marker.wait(), timeout=5)
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await asyncio.wait_for(task, timeout=5)
                self.assertFalse(finished.is_set())
                self.assertTrue(self.store._stopping.is_set())
                replacement = DecisionTraceStore(self.store.directory)
                orphan = self.store.directory / "20251001T12.tmp"
                orphan.write_bytes(b"owned compaction")
                try:
                    with patch.object(replacement, "_recover", wraps=replacement._recover) as recover:
                        self.assertFalse(await replacement.run_worker(replacement.flush, []))
                        recover.assert_not_called()
                        self.assertFalse(replacement.ready)
                        self.assertTrue(orphan.exists())
                    release.set()
                    self.assertTrue(await asyncio.to_thread(self.store._closed.wait, 5))
                    self.assertTrue(await replacement.run_worker(replacement.flush, []))
                    self.assertEqual(len(replacement._committed), 1)
                    self.assertFalse(orphan.exists())
                finally:
                    release.set()
                    replacement.stop()
                    self.assertTrue(await asyncio.to_thread(replacement._closed.wait, 5))
            finally:
                release.set()
                self.assertTrue(await asyncio.to_thread(finished.wait, 5))
        self.optimizer.run_once.assert_not_awaited()
        self.assertTrue(self.optimizer.trigger_queue.empty())

    async def test_diagnostics_submission_queue_is_bounded(self):
        release = threading.Event()
        futures = []
        try:
            for _ in range(MAX_PENDING_WORK):
                futures.append(self.store.submit_work(release.wait, 5))
            with self.assertRaisesRegex(OSError, "workers are busy"):
                self.store.submit_work(lambda: None)
        finally:
            release.set()
            await asyncio.gather(*(asyncio.wrap_future(future) for future in futures))

    async def test_lifespan_constructor_and_task_setup_failures_disable_only_diagnostics(self):
        original_create_task = asyncio.create_task
        for failure in ("constructor", "task_setup"):
            with self.subTest(failure=failure):
                app = FastAPI()
                optimizer_started, websocket_started = asyncio.Event(), asyncio.Event()

                async def optimizer_loop():
                    optimizer_started.set()
                    await asyncio.Event().wait()

                async def websocket_loop():
                    websocket_started.set()
                    await asyncio.Event().wait()

                self.optimizer.run_forever = optimizer_loop
                self.optimizer.get_watch_entities = lambda: set()
                self.optimizer.on_ws_connect = Mock()
                self.optimizer.on_ws_disconnect = Mock()
                self.optimizer.on_provider_state_observation = Mock()
                ha = SimpleNamespace(close=AsyncMock())
                ws = SimpleNamespace(run_forever=websocket_loop)

                def create_task(coroutine, *, name=None, **kwargs):
                    if failure == "task_setup" and name == "decision_trace":
                        raise RuntimeError("diagnostic task setup failed")
                    return original_create_task(coroutine, name=name, **kwargs)

                with patch.object(main, "HAClient", return_value=ha), patch.object(
                    main, "SigEnergyOptimizer", return_value=self.optimizer
                ), patch.object(main, "HAWebSocketClient", return_value=ws), patch.object(
                    main, "DecisionTraceStore", side_effect=OSError("diagnostic construction failed")
                    if failure == "constructor" else None, return_value=self.store
                ), patch.object(main.asyncio, "create_task", side_effect=create_task), self.assertLogs(level="ERROR"):
                    async with main.lifespan(app):
                        await asyncio.wait_for(optimizer_started.wait(), 5)
                        await asyncio.wait_for(websocket_started.wait(), 5)
                        self.assertIsNone(app.state.decision_trace_store)
                        self.assertIsNone(app.state.decision_trace_task)
                        self.assertFalse(app.state.optimizer_task.done())
                        self.assertFalse(app.state.ws_task.done())
                self.assertTrue(app.state.optimizer_task.cancelled())
                self.assertTrue(app.state.ws_task.cancelled())
                ha.close.assert_awaited_once()

    async def test_lifespan_filesystem_failure_keeps_optimizer_and_websocket_healthy(self):
        app = FastAPI()
        optimizer_started, websocket_started = asyncio.Event(), asyncio.Event()

        async def optimizer_loop():
            optimizer_started.set()
            await asyncio.Event().wait()

        async def websocket_loop():
            websocket_started.set()
            await asyncio.Event().wait()

        self.optimizer.run_forever = optimizer_loop
        self.optimizer.get_watch_entities = lambda: set()
        self.optimizer.on_ws_connect = Mock()
        self.optimizer.on_ws_disconnect = Mock()
        self.optimizer.on_provider_state_observation = Mock()
        ha = SimpleNamespace(close=AsyncMock())
        ws = SimpleNamespace(run_forever=websocket_loop)
        with patch.object(main, "HAClient", return_value=ha), patch.object(
            main, "SigEnergyOptimizer", return_value=self.optimizer
        ), patch.object(main, "HAWebSocketClient", return_value=ws), patch.object(
            main, "DecisionTraceStore", return_value=self.store
        ), patch.object(self.store, "_recover", side_effect=OSError("test unavailable storage")), self.assertLogs(level="ERROR"):
            async with main.lifespan(app):
                await asyncio.wait_for(optimizer_started.wait(), 5)
                await asyncio.wait_for(websocket_started.wait(), 5)
                # Ensure the diagnostics initialization has actually failed.
                await asyncio.to_thread(self.store.flush, [])
                self.assertFalse(app.state.optimizer_task.done())
                self.assertFalse(app.state.ws_task.done())
                self.assertFalse(self.store.ready)
        self.assertTrue(app.state.optimizer_task.cancelled())
        self.assertTrue(app.state.ws_task.cancelled())
        self.assertTrue(app.state.decision_trace_task.cancelled())
        ha.close.assert_awaited_once()

    async def test_periodic_write_failure_leaves_optimizer_task_healthy(self):
        failed = asyncio.Event()
        loop = asyncio.get_running_loop()
        control_cycles = []

        async def control_loop():
            while True:
                control_cycles.append(1)
                await asyncio.sleep(0.001)

        def fail_write(*_):
            loop.call_soon_threadsafe(failed.set)
            raise OSError("test periodic write failure")

        self.store.flush([])
        control = asyncio.create_task(control_loop())
        with patch("app.decision_trace_store.FLUSH_INTERVAL", 0.01), patch.object(
            self.store, "_append", side_effect=fail_write
        ), self.assertLogs(level="ERROR"):
            diagnostics = asyncio.create_task(self.store.run_forever(self.optimizer))
            try:
                await asyncio.wait_for(failed.wait(), 5)
                self.assertFalse(control.done())
                self.assertFalse(diagnostics.done())
                self.assertGreater(len(control_cycles), 0)
                self.optimizer.run_once.assert_not_awaited()
                self.assertTrue(self.optimizer.trigger_queue.empty())
            finally:
                diagnostics.cancel()
                control.cancel()
                await asyncio.gather(diagnostics, control, return_exceptions=True)

    async def test_full_1000_row_measurement_uses_worker_for_serialization_and_disk(self):
        source = ast.parse((Path(__file__).parents[1] / "app/optimizer.py").read_text(encoding="utf-8-sig"))
        example = trace_row()
        for node in ast.walk(source):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
                for target in node.targets:
                    if isinstance(target, ast.Attribute) and target.attr in {"trace_gates", "trace_values"}:
                        key = "gates" if target.attr == "trace_gates" else "values"
                        example[key] = {k.value: False if key == "gates" else (
                            "representative diagnostic reason" if any(word in k.value for word in
                            ("reason", "owner", "mode", "source", "intent", "stage")) else 123.456789012345
                        ) for k in node.value.keys if isinstance(k, ast.Constant)}
        example["summary"] = {"ems_mode": "Maximum Self Consumption", "export_limit_kw": 25.0,
                              "import_limit_kw": 25.0, "pv_max_power_limit_kw": 25.0,
                              "ess_charge_limit_kw": 21.0, "ess_discharge_limit_kw": 21.0,
                              "outcome_reason": "representative diagnostic reason"}
        example["state"] = {key: 123.456789012345 for key in (
            "battery_soc", "pv_kw", "load_kw", "grid_import_power_kw", "grid_export_power_kw",
            "current_price", "feedin_price", "forecast_remaining_kwh", "forecast_today_kwh", "forecast_tomorrow_kwh")}
        self.rows.clear()
        self.rows.extend(copy.deepcopy(example) for _ in range(1000))
        event_thread = threading.get_ident()
        thread_ids = []
        disk_thread_ids = []
        original_dumps = json.dumps
        original_append = self.store._append

        def measured_dumps(*args, **kwargs):
            thread_ids.append(threading.get_ident())
            return original_dumps(*args, **kwargs)

        def measured_append(*args, **kwargs):
            disk_thread_ids.append(threading.get_ident())
            return original_append(*args, **kwargs)

        start = time.perf_counter()
        with self.assertLogs(level="WARNING"):
            snapshot = self.store.capture(self.optimizer)
        copy_ms = (time.perf_counter() - start) * 1000
        worker_start = time.perf_counter()
        with patch("app.decision_trace_store.json.dumps", side_effect=measured_dumps), patch.object(
            self.store, "_append", side_effect=measured_append
        ):
            self.assertTrue(await asyncio.to_thread(self.store.flush, snapshot))
        worker_ms = (time.perf_counter() - worker_start) * 1000
        self.assertEqual(len(thread_ids), 1000)
        self.assertTrue(all(identity != event_thread for identity in thread_ids))
        self.assertTrue(disk_thread_ids)
        self.assertTrue(all(identity != event_thread for identity in disk_thread_ids))
        size = sum(path.stat().st_size for path in self.store.directory.glob("*.jsonl"))
        print(f"\nTRACE PERFORMANCE: 1000 rows snapshot/copy={copy_ms:.2f} ms; worker flush={worker_ms:.2f} ms; compact archive={size:,} bytes ({size / 1024 / 1024:.2f} MiB)")

