"""One lifecycle-owned DB thread with bounded, non-waiting admission.

Timeouts detach a waiter, never cancel a running SQLite call or create another
worker. A daemon thread bounds asynchronous shutdown waiting; OS I/O cannot be killed.
"""
from __future__ import annotations

import asyncio
from collections import deque
from concurrent.futures import Future
from copy import deepcopy
import json
import logging
import threading


logger = logging.getLogger(__name__)


class StorageUnavailable(RuntimeError):
    def __init__(self, message, *, unconfirmed=False):
        super().__init__(message)
        self.unconfirmed = unconfirmed


class StorageWorker:
    def __init__(self, factory, *, capacity=8):
        if capacity < 2:
            raise ValueError("Storage capacity must reserve an accounting slot")
        self._factory = factory
        self._capacity = capacity
        self._condition = threading.Condition()
        self._queue = deque()
        self._outstanding = 0
        self._ordinary = 0
        self._stopping = False
        self._ready = Future()
        self._closed = Future()
        self._thread = threading.Thread(target=self._run, name="optimizer-storage", daemon=True)
        self._thread.start()

    @classmethod
    async def open(cls, factory, *, capacity=8, timeout=2.0):
        worker = cls(factory, capacity=capacity)
        try:
            await worker.wait(worker._ready, timeout=timeout)
        except BaseException:
            await worker.close(timeout=0.05)
            raise
        return worker

    def submit(self, operation, *args, accounting=False, **kwargs):
        # Copies cross the ownership boundary; callers cannot mutate a queued
        # preset/audit payload while the worker is using it.
        args, kwargs = deepcopy((args, kwargs))
        future = Future()
        with self._condition:
            if (self._stopping or self._outstanding >= self._capacity
                    or (not accounting and self._ordinary >= self._capacity - 1)):
                raise StorageUnavailable("Storage busy or stopping")
            self._outstanding += 1
            self._ordinary += int(not accounting)
            self._queue.append((future, operation, args, kwargs, accounting))
            self._condition.notify()
        return future

    @staticmethod
    async def wait(future, *, timeout=0.25):
        wrapped = asyncio.wrap_future(future)
        # Observe detached exceptions without cancelling the actual job.
        wrapped.add_done_callback(lambda done: None if done.cancelled() else done.exception())
        try:
            return await asyncio.wait_for(asyncio.shield(wrapped), timeout)
        except asyncio.TimeoutError as exc:
            raise StorageUnavailable("Storage outcome unconfirmed after timeout", unconfirmed=True) from exc

    async def call(self, operation, *args, **kwargs):
        future = self.submit(operation, *args, **kwargs)
        try:
            return await self.wait(future)
        except StorageUnavailable:
            raise
        except Exception as exc:
            raise StorageUnavailable("Storage operation failed", unconfirmed=True) from exc

    async def close(self, *, timeout=0.25):
        with self._condition:
            self._stopping = True
            while self._queue:
                future, _, _, _, accounting = self._queue.popleft()
                future.cancel()
                self._outstanding -= 1
                self._ordinary -= int(not accounting)
            self._condition.notify()
        try:
            await self.wait(self._closed, timeout=timeout)
        except StorageUnavailable:
            pass  # Active call retains ownership and closes on its eventual return.

    @staticmethod
    def _ledger_snapshot(store, payloads, day, load_checkpoint):
        acknowledged = []
        checkpoint = None
        checkpoint_read = not load_checkpoint
        try:
            if load_checkpoint:
                checkpoint = store.get_optimizer_import_checkpoint()
                checkpoint_read = True
            for payload in payloads:
                event = json.loads(payload)
                store.record_optimizer_import_interval(event)
                acknowledged.append(event["event_id"])
            summary = store.optimizer_import_topup_summary(day)
            return tuple(acknowledged), checkpoint, checkpoint_read, summary, True
        except Exception:
            logger.warning("Import accounting database operation failed; reconciliation remains pending")
            # Earlier committed events can be acknowledged; the failed event
            # retains its exact original payload for idempotent retry.
            return tuple(acknowledged), checkpoint, checkpoint_read, None, False

    def _run(self):
        store = None
        try:
            store = self._factory()
            self._ready.set_result(None)
            while True:
                with self._condition:
                    while not self._queue and not self._stopping:
                        self._condition.wait()
                    if self._stopping:
                        break
                    future, operation, args, kwargs, accounting = self._queue.popleft()
                try:
                    if future.set_running_or_notify_cancel():
                        if operation == "ledger_snapshot":
                            result = self._ledger_snapshot(store, *args, **kwargs)
                        else:
                            result = getattr(store, operation)(*args, **kwargs)
                        future.set_result(deepcopy(result))
                except BaseException as exc:
                    logger.warning("Storage operation failed: %s", operation)
                    future.set_exception(exc)
                finally:
                    with self._condition:
                        self._outstanding -= 1
                        self._ordinary -= int(not accounting)
        except BaseException as exc:
            if not self._ready.done():
                self._ready.set_exception(exc)
        finally:
            try:
                if store is not None:
                    store.close()
            except Exception:
                logger.warning("Storage connection close failed")
            finally:
                self._closed.set_result(None)
