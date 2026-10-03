from __future__ import annotations

import asyncio
import json
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx
from fastapi import FastAPI

from app.decision_trace_store import (
    CHUNK_BYTES, DOWNLOAD_SECONDS, MAX_DOWNLOAD_BYTES, MAX_DOWNLOAD_SEGMENTS,
    MAX_DOWNLOADS, MAX_TICKETS, DecisionTraceStore,
)
from app.routers import api


class DecisionTraceDownloadTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = DecisionTraceStore(Path(self.tmp.name) / "trace")
        self.now = datetime.now(timezone.utc).replace(microsecond=0)
        self.store._clock_now = Mock(return_value=0.0)
        self.store.flush([], self.now - timedelta(hours=2))
        self.store._clock_now.return_value = 7200.0
        self.app = FastAPI()
        self.app.state.decision_trace_store = self.store
        self.app.include_router(api.router, prefix="/api")
        self.settings = SimpleNamespace(
            ui_api_key="test-only-key", require_api_key_for_config_read=True,
            allow_loopback_without_api_key=True, require_api_key_for_all_mutations=True,
        )
        self.auth_patch = patch.object(api, "settings", self.settings)
        self.auth_patch.start()
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app, client=("203.0.113.8", 1234)),
                                        base_url="http://test")

    async def asyncTearDown(self):
        await self.client.aclose()
        self.auth_patch.stop()
        self.store.stop()
        self.assertTrue(await asyncio.to_thread(self.store._closed.wait, 5))
        self.tmp.cleanup()

    def persist(self, timestamps, payload="example", now=None):
        rows = [{"ts": at.isoformat(), "summary": {}, "state": {}, "gates": {},
                 "values": {"payload": payload}} for at in timestamps]
        optimizer = SimpleNamespace(decision_trace=lambda limit: list(reversed(rows)))
        at = now or self.now
        self.store._clock_now.return_value = (at - self.now).total_seconds() + 7200
        self.store.flush(self.store.capture(optimizer), at)
        self.store._clock_now.return_value = 7200.0

    async def ticket(self):
        return await self.client.post("/api/decision_trace/24h/download-ticket", headers={"x-api-key": "test-only-key"})

    async def test_ticket_issue_read_auth_single_use_and_download_headers(self):
        self.persist([self.now])
        unauthorized = await self.client.post("/api/decision_trace/24h/download-ticket")
        self.assertEqual(unauthorized.status_code, 401)
        issued = await self.ticket()
        self.assertEqual(issued.status_code, 200)
        self.assertEqual(issued.headers["cache-control"], "no-store")
        url = issued.json()["url"]
        self.assertNotIn("test-only-key", url)
        download = await self.client.get("/" + url)
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download.headers["content-type"], "application/x-ndjson")
        self.assertEqual(download.headers["cache-control"], "no-store")
        self.assertRegex(download.headers["content-disposition"], r'attachment; filename="sigenergy_decision_trace_24h_\d{8}T\d{6}Z.jsonl"')
        self.assertEqual(download.headers["referrer-policy"], "no-referrer")
        self.assertIn("_trace", json.loads(download.content))
        self.assertEqual((await self.client.get("/" + url)).status_code, 401)
        self.assertEqual(self.store._pins, {})

    async def test_ordinary_authorization_and_existing_optional_read_policy(self):
        self.assertEqual((await self.client.get("/api/decision_trace/24h/download")).status_code, 401)
        authorized = await self.client.get("/api/decision_trace/24h/download", headers={"x-api-key": "test-only-key"})
        self.assertEqual(authorized.status_code, 200)
        self.settings.require_api_key_for_config_read = False
        self.assertEqual((await self.client.get("/api/decision_trace/24h/download")).status_code, 200)
        # An explicitly invalid ticket must never use permissive auth fallback.
        self.assertEqual((await self.client.get("/api/decision_trace/24h/download?ticket=invalid")).status_code, 401)

    async def test_loopback_and_ingress_follow_existing_read_authorization(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app, client=("127.0.0.1", 1)),
                                    base_url="http://test") as loopback:
            self.assertEqual((await loopback.post("/api/decision_trace/24h/download-ticket")).status_code, 200)
        self.settings.require_api_key_for_all_mutations = False
        self.assertEqual((await self.client.post("/api/decision_trace/24h/download-ticket",
                                                headers={"x-ingress-path": "/ingress/test"})).status_code, 200)

    async def test_expiry_and_bounded_outstanding_tickets(self):
        with patch("app.decision_trace_store.time.monotonic", return_value=100):
            issued = await self.ticket()
        with patch("app.decision_trace_store.time.monotonic", return_value=160):
            expired = await self.client.get("/" + issued.json()["url"])
        self.assertEqual(expired.status_code, 401)
        with patch("app.decision_trace_store.time.monotonic", return_value=200):
            for _ in range(MAX_TICKETS):
                self.assertEqual((await self.ticket()).status_code, 200)
            self.assertEqual((await self.ticket()).status_code, 429)
            self.assertEqual(len(self.store._tickets), MAX_TICKETS)
        with patch("app.decision_trace_store.time.monotonic", return_value=261):
            self.assertEqual((await self.ticket()).status_code, 200)
            self.assertEqual(len(self.store._tickets), 1)

    async def test_empty_archive_is_valid_empty_ndjson(self):
        issued = await self.ticket()
        response = await self.client.get("/" + issued.json()["url"])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"")
        self.assertEqual(self.store._pins, {})

    async def test_archive_open_stream_and_close_use_only_dedicated_workers(self):
        self.persist([self.now])
        loop = asyncio.get_running_loop()
        names = []
        original_open = Path.open

        def observed_open(path, *args, **kwargs):
            names.append(threading.current_thread().name)
            return original_open(path, *args, **kwargs)

        with patch.object(loop, "run_in_executor", side_effect=AssertionError("shared executor used")), patch(
            "anyio.to_thread.run_sync", side_effect=AssertionError("shared streaming pool used")
        ), patch.object(Path, "open", new=observed_open):
            self.assertTrue(await self.store.run_worker(self.store.flush, []))
            response = await self.client.get("/api/decision_trace/24h/download",
                                             headers={"x-api-key": "test-only-key"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.content.splitlines()), 1)
        self.assertTrue(names)
        self.assertTrue(all(name.startswith("decision-trace") for name in names))
        self.assertEqual(self.store._active_downloads, 0)
        self.assertEqual(self.store._pins, {})

    async def test_active_download_admission_precedes_submission_and_does_not_starve_dns(self):
        self.persist([self.now])
        requests = []
        self.store._lock.acquire()
        try:
            with patch.object(self.store, "submit_work", wraps=self.store.submit_work) as submit:
                for _ in range(MAX_DOWNLOADS):
                    requests.append(asyncio.create_task(self.client.get(
                        "/api/decision_trace/24h/download", headers={"x-api-key": "test-only-key"})))
                async def admitted():
                    while self.store._active_downloads < MAX_DOWNLOADS:
                        await asyncio.sleep(0)
                await asyncio.wait_for(admitted(), 5)
                self.assertEqual(submit.call_count, MAX_DOWNLOADS)
                response = await self.client.get("/api/decision_trace/24h/download",
                                                 headers={"x-api-key": "test-only-key"})
                self.assertEqual(response.status_code, 429)
                self.assertEqual(submit.call_count, MAX_DOWNLOADS)
                with patch("socket.getaddrinfo", return_value=[]) as dns:
                    result = await asyncio.wait_for(asyncio.get_running_loop().getaddrinfo("review.invalid", 80), 1)
                    self.assertEqual(result, [])
                    dns.assert_called_once()
        finally:
            self.store._lock.release()
            responses = await asyncio.gather(*requests)
        self.assertTrue(all(response.status_code == 200 for response in responses))
        self.assertEqual(self.store._active_downloads, 0)
        self.assertEqual(self.store._pins, {})

    async def test_stopping_keeps_archive_owned_until_pinned_download_closes(self):
        self.persist([self.now])
        view = self.store.open_download(self.now)
        self.store.stop()
        replacement = DecisionTraceStore(self.store.directory)
        try:
            self.assertFalse(await replacement.run_worker(replacement.flush, []))
            self.assertFalse(self.store._closed.is_set())
            await view.async_close()
            self.assertTrue(await asyncio.to_thread(self.store._closed.wait, 5))
            self.assertTrue(await replacement.run_worker(replacement.flush, []))
            self.assertEqual(len(replacement._committed), 1)
        finally:
            await view.async_close()
            replacement.stop()
            self.assertTrue(await asyncio.to_thread(replacement._closed.wait, 5))

    async def test_storage_unavailable_and_open_failure_return_503(self):
        self.store._ready = False
        self.assertEqual((await self.ticket()).status_code, 503)
        self.store._ready = True
        with patch.object(self.store, "open_download", side_effect=OSError("test open error")), self.assertLogs(level="ERROR"):
            response = await self.client.get("/api/decision_trace/24h/download", headers={"x-api-key": "test-only-key"})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers["cache-control"], "no-store")

    async def test_download_filters_current_cutoff_without_flush(self):
        cutoff = self.now - timedelta(hours=24)
        timestamps = [cutoff - timedelta(seconds=1), cutoff, cutoff + timedelta(seconds=1)]
        self.persist(timestamps, now=self.now - timedelta(hours=1))
        view = self.store.open_download(self.now)
        records = [json.loads(line) for line in b"".join(view.chunks()).splitlines()]
        self.assertEqual([record["ts"] for record in records], [at.isoformat() for at in timestamps[1:]])
        self.assertEqual(self.store._pins, {})

    async def test_chunks_are_bounded_and_later_appends_are_excluded(self):
        self.persist([self.now], payload="x" * (CHUNK_BYTES * 3))
        view = self.store.open_download(self.now)
        self.persist([self.now + timedelta(seconds=1)])
        chunks = list(view.chunks())
        self.assertTrue(all(len(chunk) <= CHUNK_BYTES for chunk in chunks))
        self.assertEqual(len(b"".join(chunks).splitlines()), 1)
        self.assertTrue(all(handle.closed for _, handle, _ in view.files))

    async def test_pruning_and_append_continue_without_waiting_for_slow_download(self):
        cutoff = self.now - timedelta(hours=24)
        self.persist([cutoff - timedelta(hours=1), cutoff - timedelta(seconds=1), cutoff],
                     now=self.now - timedelta(hours=2))
        view = self.store.open_download(self.now)
        # Prune skips pinned segments, avoiding Windows open-file replacement
        # failures. It resumes on the next pass after the download closes.
        self.assertTrue(await asyncio.wait_for(asyncio.to_thread(self.store.flush, [], self.now), 5))
        downloaded = [json.loads(line) for line in b"".join(view.chunks()).splitlines()]
        self.assertEqual(len(downloaded), 1)
        self.assertTrue(self.store.flush([], self.now))
        self.assertEqual(len(list(self.store.directory.glob("*.jsonl"))), 1)
        self.assertEqual(self.store._pins, {})

    async def test_failed_open_cleans_previously_opened_handles(self):
        self.persist([self.now - timedelta(hours=1), self.now])
        opened = []
        real_open = Path.open
        calls = 0

        def failing_open(path, *args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("test second file open failed")
            handle = real_open(path, *args, **kwargs)
            opened.append(handle)
            return handle

        with patch.object(Path, "open", new=failing_open):
            with self.assertRaises(OSError):
                self.store.open_download(self.now)
        self.assertTrue(all(handle.closed for handle in opened))
        self.assertEqual(self.store._pins, {})

    async def test_disconnect_closes_handles_even_before_first_body_chunk(self):
        self.persist([self.now])
        for disconnect_at_start in (False, True):
            with self.subTest(disconnect_at_start=disconnect_at_start):
                view = self.store.open_download(self.now)
                response = api._TraceDownloadResponse(view, media_type="application/x-ndjson")
                body_sent = asyncio.Event()

                async def receive():
                    await body_sent.wait()
                    return {"type": "http.disconnect"}

                async def send(message):
                    if (message["type"] == "http.response.start" and disconnect_at_start) or message["type"] == "http.response.body":
                        body_sent.set()
                        await asyncio.Event().wait()

                await asyncio.wait_for(response({"type": "http", "asgi": {"spec_version": "2.0"}}, receive, send), 5)
                self.assertTrue(all(handle.closed for _, handle, _ in view.files))
                self.assertEqual(self.store._pins, {})

    async def test_send_error_also_closes_handles(self):
        self.persist([self.now])
        view = self.store.open_download(self.now)
        response = api._TraceDownloadResponse(view, media_type="application/x-ndjson")

        async def send(_):
            raise OSError("test disconnected send")

        async def receive():
            await asyncio.Event().wait()

        with self.assertRaises(Exception):
            await response({"type": "http", "asgi": {"spec_version": "2.4"}}, receive, send)
        self.assertTrue(all(handle.closed for _, handle, _ in view.files))
        self.assertEqual(self.store._pins, {})

    async def test_disconnect_during_worker_open_does_not_abandon_handles(self):
        self.persist([self.now])
        started, release, closed = threading.Event(), threading.Event(), threading.Event()
        views = []
        original = self.store.open_download

        def slow_open(now, reserved=False, deadline=None):
            started.set()
            if not release.wait(5):
                raise RuntimeError("test open worker not released")
            view = original(now, reserved, deadline)
            views.append(view)
            original_close = view.close

            def close():
                original_close()
                closed.set()

            view.close = close
            return view

        request = SimpleNamespace(app=self.app, client=SimpleNamespace(host="127.0.0.1"), headers={})
        with patch.object(self.store, "open_download", side_effect=slow_open):
            task = asyncio.create_task(api.download_decision_trace_24h(request))
            try:
                self.assertTrue(await asyncio.to_thread(started.wait, 5))
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task
            finally:
                release.set()
                self.assertTrue(await asyncio.to_thread(closed.wait, 5))
        self.assertEqual(self.store._pins, {})
        self.assertTrue(all(handle.closed for _, handle, _ in views[0].files))

    async def test_stalled_download_has_two_minute_limit_and_releases_all_pins(self):
        self.assertEqual(DOWNLOAD_SECONDS, 120)
        self.persist([self.now])
        # Exercise actual response cancellation at both header and body sends,
        # using a short deadline rather than making the test wait two minutes.
        for stalled_message in ("http.response.start", "http.response.body"):
            with self.subTest(stalled_message=stalled_message):
                with patch("app.decision_trace_store.DOWNLOAD_SECONDS", 0.05):
                    view = self.store.open_download(self.now)
                response = api._TraceDownloadResponse(view, media_type="application/x-ndjson")
                stalled = asyncio.Event()

                async def receive():
                    await asyncio.Event().wait()

                async def send(message):
                    if message["type"] == stalled_message:
                        stalled.set()
                        await asyncio.Event().wait()

                started_at = asyncio.get_running_loop().time()
                with self.assertRaises(TimeoutError):
                    await asyncio.wait_for(response(
                        {"type": "http", "asgi": {"spec_version": "2.4"}}, receive, send
                    ), 5)
                # Distinguish our 50 ms lifetime from the outer test watchdog.
                self.assertLess(asyncio.get_running_loop().time() - started_at, 2)
                self.assertTrue(stalled.is_set())
                self.assertTrue(all(handle.closed for _, handle, _ in view.files))
                self.assertEqual(self.store._pins, {})
                self.assertEqual(self.store._active_downloads, 0)

    async def test_overlapping_downloads_cannot_transfer_expired_segment_pins(self):
        self.persist([self.now])
        current = self.store.open_download(self.now)
        try:
            for hour in range(1, 73):
                at = self.now + timedelta(hours=hour)
                self.persist([at], now=at)
                self.store._clock_now.return_value = 7200 + hour * 3600.0
                replacement = self.store.open_download(at)
                try:
                    cutoff = at - timedelta(hours=24)
                    self.assertLessEqual(len(replacement.files), MAX_DOWNLOAD_SEGMENTS)
                    self.assertTrue(all(
                        datetime.strptime(path.stem, "%Y%m%dT%H").replace(tzinfo=timezone.utc)
                        + timedelta(hours=1) > cutoff for path, _, _ in replacement.files
                    ))
                    self.assertEqual(self.store._active_downloads, 2)
                except BaseException:
                    replacement.close()
                    raise
                current.close()
                current = replacement
                # Newly expired files may await this pass, but cannot carry
                # their pins into the next download as in the review probe.
                self.assertTrue(self.store.flush([], at))
                self.assertLessEqual(len(self.store._lengths), MAX_DOWNLOAD_SEGMENTS)
                self.assertLessEqual(len(self.store._pins), MAX_DOWNLOAD_SEGMENTS)
            records = b"".join(current.chunks()).splitlines()
            self.assertGreater(len(records), 0)
            self.assertLessEqual(len(records), 25)
        finally:
            current.close()
        self.assertEqual(self.store._pins, {})
        self.assertEqual(self.store._active_downloads, 0)

    async def test_resource_pressure_rejects_download_before_pinning_handles(self):
        self.persist([self.now])
        path = self.store._path(self.now)
        self.store._lengths[path] = MAX_DOWNLOAD_BYTES + 1
        with patch.object(Path, "open", side_effect=AssertionError("archive handle opened")):
            # Keep status saving outside the probe's file-open prohibition.
            with patch.object(self.store, "_save_status"):
                with self.assertRaisesRegex(OSError, "resource limits"):
                    self.store.open_download(self.now)
        self.assertEqual(self.store._pins, {})
        self.assertEqual(self.store._active_downloads, 0)

    async def test_opening_timeout_releases_reservation_when_worker_finishes(self):
        self.persist([self.now])
        started, release, finished = threading.Event(), threading.Event(), threading.Event()
        original = self.store.open_download

        def delayed_open(now, reserved=False, deadline=None):
            started.set()
            try:
                if not release.wait(5):
                    raise RuntimeError("test opening worker was not released")
                return original(now, reserved, deadline)
            finally:
                finished.set()

        request = SimpleNamespace(app=self.app, client=SimpleNamespace(host="127.0.0.1"), headers={})
        with patch("app.decision_trace_store.DOWNLOAD_SECONDS", 0.05), patch.object(
            self.store, "open_download", side_effect=delayed_open
        ):
            task = asyncio.create_task(api.download_decision_trace_24h(request))
            try:
                self.assertTrue(await asyncio.to_thread(started.wait, 5))
                with self.assertRaises(api.HTTPException) as error:
                    await asyncio.wait_for(task, 5)
                self.assertEqual(error.exception.status_code, 504)
            finally:
                release.set()
                self.assertTrue(await asyncio.to_thread(finished.wait, 5))
        # The worker wrapper releases admission even after its caller timed out.
        self.assertEqual(self.store._active_downloads, 0)
        self.assertEqual(self.store._pins, {})

