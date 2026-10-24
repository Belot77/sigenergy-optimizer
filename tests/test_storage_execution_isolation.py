"""O15 uses synthetic stores only; no HA or on-disk runtime data."""
import asyncio
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
import sqlite3
import threading
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI, HTTPException

from app import main
from app.config import Settings
from app.import_topup_ledger import ImportTopupLedger
from app.models import BATTERY_EXPORT
from app.optimizer import SigEnergyOptimizer, _ActuatorApplicationResult
from app.routers import api
from app.state_store import StateStore
from app.storage_worker import StorageWorker, StorageUnavailable


BASE = datetime(2026, 1, 15, tzinfo=timezone.utc)
DAY = BASE.date().isoformat()
SOURCE = "synthetic|UTC"


def capture(ledger, when, total=0, *, price=0.05, active=False, source=SOURCE):
    ledger.record(now=when, source=source, daily_import_kwh=total,
                  grid_import_kw=0, import_price=price, price_trusted=True,
                  import_active=active)


async def reconcile(ledger, worker, day=DAY, source=SOURCE):
    key, payloads, checkpoint = ledger.reconciliation_snapshot(day, source)
    result = await worker.call("ledger_snapshot", payloads, day, checkpoint, accounting=True)
    ledger.accept_reconciliation(key, result)
    return result


async def covered_ledger(worker, *, pending_limit=256):
    before = BASE - timedelta(seconds=1)
    ledger = ImportTopupLedger(None, started_at=before, source=SOURCE,
                               deferred=True, pending_limit=pending_limit)
    capture(ledger, before)
    capture(ledger, BASE)
    await reconcile(ledger, worker)
    assert ledger.summary(DAY, source=SOURCE)["import_history_complete"]
    return ledger


def test_real_price_api_does_not_stall_heartbeat_on_storage():
    async def scenario():
        class SlowOptimizer:
            def price_tracking_events(self, **kwargs):
                time.sleep(0.15)
                return []

            async def storage_call(self, operation, *args, **kwargs):
                # Runtime bridge must be used by the real API route.
                await asyncio.sleep(0.15)
                return []

        request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(optimizer=SlowOptimizer())))
        started = time.monotonic()
        async def heartbeat():
            await asyncio.sleep(0.02)
            return time.monotonic() - started
        beat = asyncio.create_task(heartbeat())
        await asyncio.sleep(0)
        with patch.object(api, "_require_config_read_auth"):
            assert await api.price_tracking(request) == {"rows": []}
        assert await beat < 0.08
    asyncio.run(scenario())


def test_worker_timeout_retains_single_running_job_and_bounds_admission():
    async def scenario():
        entered, release = threading.Event(), threading.Event()
        calls = []
        class Store:
            def read(self):
                calls.append(threading.get_ident())
                entered.set()
                release.wait(2)
                return 42
            def close(self):
                calls.append(threading.get_ident())
        worker = await StorageWorker.open(Store, capacity=2)
        try:
            first = worker.submit("read", accounting=True)
            await asyncio.sleep(0.02)
            assert entered.is_set()
            try:
                await worker.wait(first, timeout=0.01)
                assert False, "blocked job must time out"
            except StorageUnavailable:
                pass
            second = worker.submit("read")
            try:
                worker.submit("read")
                assert False, "bounded service must reject overload"
            except StorageUnavailable:
                pass
            assert len(calls) == 1
            release.set()
            assert await worker.wait(first) == 42
            assert await worker.wait(second) == 42
        finally:
            release.set()
            await worker.close()
        assert len(set(calls)) == 1
    asyncio.run(scenario())


@pytest.mark.parametrize("fault", ["insert", "commit-before", "commit-after", "query"])
def test_worker_fault_retry_keeps_original_price_and_exact_once(fault):
    from test_import_topup_interval_store import FaultConnection
    async def scenario():
        def factory():
            store = StateStore(":memory:")
            store._conn = FaultConnection(store._conn, None)
            return store
        worker = await StorageWorker.open(factory)
        try:
            ledger = await covered_ledger(worker)
            # Inject the one-shot fault on the worker through a test-only store
            # method; tests never share its connection back to the event loop.
            capture(ledger, BASE + timedelta(minutes=1), 1, price=0.4, active=True)
            with patch.object(StorageWorker, "_ledger_snapshot", wraps=StorageWorker._ledger_snapshot) as operation:
                original = operation._mock_wraps
                def fail(store, *args):
                    if fault == "query":
                        with patch.object(store, "optimizer_import_topup_summary",
                                          side_effect=sqlite3.OperationalError("synthetic query failure")):
                            return original(store, *args)
                    store._conn.fault = fault
                    return original(store, *args)
                operation.side_effect = fail
                result = await reconcile(ledger, worker)
            assert not result[-1]
            assert ledger.summary(DAY, source=SOURCE)["import_cost_floor_unknown"]
            capture(ledger, BASE + timedelta(minutes=2), 2, price=0.05, active=True)
            await reconcile(ledger, worker)
            summary = ledger.summary(DAY, source=SOURCE)
            assert summary["import_history_complete"]
            assert summary["today_import_topup_kwh"] == 2
            assert summary["today_highest_actual_import_price"] == 0.4
        finally:
            await worker.close()
    asyncio.run(scenario())


@pytest.mark.parametrize("blocked", [False, True])
def test_runtime_real_tick_captures_cost_before_decision_without_stalling_ha(blocked):
    from test_four_tier_battery_export import FourTierDecisionTests
    from test_import_topup_decision_integrity import measured
    case = FourTierDecisionTests()
    case.setUp()
    baseline = case.optimizer(max_battery_soc=100)
    when = datetime.fromtimestamp(case.FIXED_AFTERNOON.timestamp(), tz=baseline._tz)
    before = when.replace(hour=0, minute=0, second=0) - timedelta(seconds=1)
    pause, release = threading.Event(), threading.Event()
    loop_thread = threading.get_ident()
    store_threads = []
    class Store(StateStore):
        def __init__(self):
            store_threads.append(threading.get_ident())
            super().__init__(":memory:")
        def optimizer_import_topup_summary(self, day):
            store_threads.append(threading.get_ident())
            if pause.is_set():
                release.wait(2)
            return super().optimizer_import_topup_summary(day)
        def close(self):
            store_threads.append(threading.get_ident())
            super().close()

    async def scenario():
        worker = await StorageWorker.open(Store)
        try:
            with case.optimizer_time(before):
                opt = SigEnergyOptimizer(baseline.ha, baseline.cfg.model_copy(), storage_worker=worker)
            ledger, source = opt._import_topup_ledger, opt._import_topup_source()
            current = before
            while current < when - timedelta(minutes=2):
                capture(ledger, current, source=source)
                current = min(current + timedelta(seconds=1 if current == before else 300), when - timedelta(minutes=2))
            capture(ledger, current, source=source)
            with case.optimizer_time(current):
                await opt._reconcile_import_storage()
                assert not opt._optimizer_import_topup_summary_today()["import_cost_floor_unknown"]

            async def run_tick(at, total, price):
                state = measured(case, at, total=total, price=price)
                seen = []
                async def apply(_state, decision):
                    assert threading.get_ident() == loop_thread
                    seen.append(decision)
                    return _ActuatorApplicationResult(succeeded=True, automatic_application_completed=True)
                with ExitStack() as stack:
                    stack.enter_context(case.optimizer_time(at))
                    stack.enter_context(patch.object(opt, "_read_state", AsyncMock(return_value=state)))
                    stack.enter_context(patch.object(opt, "_apply", apply))
                    stack.enter_context(patch.object(opt, "_evaluate_hvac_solar_permission", return_value=None))
                    for name in ("_publish_hvac_solar_permission", "_handle_notifications", "_handle_daily_summaries"):
                        stack.enter_context(patch.object(opt, name, AsyncMock(return_value=True)))
                    for name in ("_record_application_trace", "_accumulate_history"):
                        stack.enter_context(patch.object(opt, name))
                    # Audit and price persistence retain their real runtime paths.
                    await opt._tick()
                return seen[0]

            healthy = await run_tick(current, 0, 0.05)
            assert healthy.export_intent == BATTERY_EXPORT
            ledger.set_permission(now=current, source=source, import_active=True)
            capture(ledger, when - timedelta(minutes=1), 1, price=0.05, active=True, source=source)
            if blocked:
                pause.set()
            started = time.monotonic()
            async def heartbeat():
                await asyncio.sleep(0.02)
                return time.monotonic() - started
            beat = asyncio.create_task(heartbeat())
            decision = await run_tick(when, 2, 0.4)
            assert await beat < 0.08
            assert decision.export_intent != BATTERY_EXPORT
            assert decision.export_limit == 0
            if blocked:
                assert time.monotonic() - started < 0.15
                assert decision.trace_gates["import_cost_floor_unknown"]
                assert ledger.has_pending
            # The application still established its new permission on the loop.
            assert ledger.permission_known
            release.set()
            if opt._ledger_job is not None:
                await asyncio.shield(opt._ledger_job)
                await asyncio.sleep(0)
            with case.optimizer_time(when):
                await opt._reconcile_import_storage()
            summary = await worker.call("optimizer_import_topup_summary", when.date().isoformat())
            assert summary["today_import_topup_kwh"] == 2
            assert summary["today_highest_actual_import_price"] == 0.4
        finally:
            release.set()
            await worker.close()
        assert len(set(store_threads)) == 1
        assert loop_thread not in store_threads
    try:
        asyncio.run(scenario())
    finally:
        case.tearDown()


@pytest.mark.parametrize("failure", ["factory", "timeout", "cancel"])
def test_startup_failure_or_cancellation_keeps_event_loop_responsive_and_closes_on_worker(failure):
    async def scenario():
        entered, release, closed = threading.Event(), threading.Event(), threading.Event()
        thread_ids = []
        class Store:
            def close(self):
                thread_ids.append(threading.get_ident())
                closed.set()
        def factory():
            thread_ids.append(threading.get_ident())
            entered.set()
            if failure == "factory":
                raise sqlite3.OperationalError("synthetic startup failure")
            release.wait(2)
            return Store()
        task = asyncio.create_task(StorageWorker.open(factory, timeout=0.03))
        await asyncio.sleep(0.01)
        assert entered.is_set()
        if failure == "cancel":
            task.cancel()
        with pytest.raises((sqlite3.OperationalError, StorageUnavailable, asyncio.CancelledError)):
            await task
        release.set()
        if failure != "factory":
            for _ in range(30):
                if closed.is_set():
                    break
                await asyncio.sleep(0.01)
            assert closed.is_set()
            assert len(set(thread_ids)) == 1
        assert threading.get_ident() not in thread_ids
    asyncio.run(scenario())


@pytest.mark.parametrize("failure", ["startup", "body", "cancel"])
def test_main_lifespan_closes_ha_and_storage_on_all_exit_paths(failure):
    async def scenario():
        ha = SimpleNamespace(close=AsyncMock())
        storage = SimpleNamespace(close=AsyncMock())
        @main.asynccontextmanager
        async def inner(*args):
            yield
        with (patch.object(main, "HAClient", return_value=ha),
              patch.object(main.StorageWorker, "open", AsyncMock(side_effect=OSError("synthetic")
                           if failure == "startup" else None, return_value=storage)),
              patch.object(main, "_optimizer_lifespan", inner)):
            with pytest.raises((OSError, RuntimeError, asyncio.CancelledError)):
                async with main.lifespan(FastAPI()):
                    if failure == "cancel":
                        raise asyncio.CancelledError()
                    raise RuntimeError("synthetic lifespan body")
        ha.close.assert_awaited_once()
        if failure != "startup":
            storage.close.assert_awaited_once()
    asyncio.run(scenario())


@pytest.mark.parametrize("boundary", ["capture", "permission", "invalidate", "source-revert", "midnight"])
def test_late_ack_retires_exact_head_without_restoring_old_trust(boundary):
    async def scenario():
        worker = await StorageWorker.open(lambda: StateStore(":memory:"))
        try:
            ledger = await covered_ledger(worker)
            capture(ledger, BASE + timedelta(seconds=1), 1, active=True)
            key, payloads, checkpoint = ledger.reconciliation_snapshot(DAY, SOURCE)
            result = await worker.call("ledger_snapshot", payloads, DAY, checkpoint, accounting=True)
            if boundary == "capture":
                capture(ledger, BASE + timedelta(seconds=2), 2, active=True)
            elif boundary == "permission":
                ledger.set_permission(now=BASE + timedelta(seconds=2), source=SOURCE, import_active=True)
            elif boundary == "invalidate":
                ledger.invalidate(BASE, "same_reason")
                key, payloads, checkpoint = ledger.reconciliation_snapshot(DAY, SOURCE)
                result = await worker.call("ledger_snapshot", payloads, DAY, checkpoint, accounting=True)
                ledger.invalidate(BASE, "same_reason")
            elif boundary == "source-revert":
                ledger.invalidate(BASE, "identity", permission_unknown=True)
                ledger.invalidate(BASE, "identity", permission_unknown=True)
            else:
                capture(ledger, BASE + timedelta(days=1), 0)
            ledger.accept_reconciliation(key, result)
            summary = ledger.summary(DAY, source=SOURCE)
            assert summary["import_cost_floor_unknown"]
            assert ledger._summary_cache is None
            assert all(item.payload()["event_id"] not in result[0] for item in ledger._pending)
            # Re-delivery of an old ack must not remove a newer queue head.
            remaining = tuple(ledger._pending)
            ledger.accept_reconciliation(key, result)
            assert tuple(ledger._pending) == remaining
        finally:
            await worker.close()
    asyncio.run(scenario())


def test_deferred_batch_and_pending_overflow_bounds_and_unknown_recovery():
    async def scenario():
        worker = await StorageWorker.open(lambda: StateStore(":memory:"))
        try:
            ledger = await covered_ledger(worker, pending_limit=20)
            for second in range(1, 21):
                capture(ledger, BASE + timedelta(seconds=second), second, active=True)
            with pytest.raises(RuntimeError):
                capture(ledger, BASE + timedelta(seconds=21), 21, active=True)
            assert len(ledger._pending) == 20
            _, payloads, _ = ledger.reconciliation_snapshot(DAY, SOURCE)
            assert len(payloads) == 16
            await reconcile(ledger, worker)
            assert len(ledger._pending) == 4
            await reconcile(ledger, worker)
            assert not ledger.has_pending
            assert ledger.summary(DAY, source=SOURCE)["import_cost_floor_unknown"]
            capture(ledger, BASE + timedelta(seconds=22), 22, active=True)
            await reconcile(ledger, worker)
            summary = await worker.call("optimizer_import_topup_summary", DAY)
            assert summary["import_cost_floor_unknown"]
        finally:
            await worker.close()
    asyncio.run(scenario())


def test_shutdown_cancels_queued_jobs_but_never_closes_active_connection():
    async def scenario():
        entered, release, closed = threading.Event(), threading.Event(), threading.Event()
        threads = []
        class Store:
            def __init__(self):
                threads.append(threading.get_ident())
            def write(self):
                threads.append(threading.get_ident())
                entered.set()
                release.wait(2)
                return "committed"
            def close(self):
                threads.append(threading.get_ident())
                closed.set()
        worker = await StorageWorker.open(Store)
        active = worker.submit("write")
        queued = worker.submit("write")
        await asyncio.sleep(0.02)
        assert entered.is_set()
        await worker.close(timeout=0.01)
        assert not closed.is_set()
        assert queued.cancelled()
        with pytest.raises(StorageUnavailable):
            worker.submit("write")
        release.set()
        assert await worker.wait(active) == "committed"
        await worker.wait(worker._closed)
        assert closed.is_set()
        assert len(set(threads)) == 1
    asyncio.run(scenario())


def test_cancelled_waiter_does_not_cancel_or_duplicate_accepted_mutation():
    async def scenario():
        release = threading.Event()
        writes = []
        class Store:
            def write(self):
                release.wait(2)
                writes.append(1)
            def close(self):
                pass
        worker = await StorageWorker.open(Store)
        future = worker.submit("write")
        waiter = asyncio.create_task(worker.wait(future))
        await asyncio.sleep(0.02)
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter
        assert not future.cancelled()
        release.set()
        await worker.wait(future)
        await worker.close()
        assert writes == [1]
    asyncio.run(scenario())


def test_api_overload_reserved_accounting_and_unconfirmed_mutation():
    async def scenario():
        release = threading.Event()
        class Store:
            def read(self):
                release.wait(2)
                return []
            def save_threshold_preset(self, *args):
                release.wait(2)
            def close(self):
                pass
        worker = await StorageWorker.open(Store, capacity=2)
        opt = SimpleNamespace(storage_call=worker.call)
        request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(optimizer=opt)))
        try:
            first = worker.submit("read")
            # Ordinary work cannot occupy the reserved accounting slot.
            with patch.object(api, "_require_config_read_auth"), pytest.raises(HTTPException) as overloaded:
                await api.price_tracking(request)
            assert overloaded.value.status_code == 503
            assert overloaded.value.detail["outcome"] == "NOT_ACCEPTED"
            accounting = worker.submit("read", accounting=True)
            release.set()
            await worker.wait(first)
            await worker.wait(accounting)
            release.clear()
            with pytest.raises(HTTPException) as timed_out:
                await api._storage_call(request, "save_threshold_preset", "unused", "example", {})
            assert timed_out.value.status_code == 503
            assert timed_out.value.detail["outcome"] == "UNCONFIRMED"
        finally:
            release.set()
            await worker.close()
    asyncio.run(scenario())


@pytest.mark.parametrize("boundary", ["configuration", "manual", "ess"])
def test_real_runtime_identity_and_direct_control_retire_delayed_summary(boundary):
    import httpx
    from test_config_activation_authority_race import _app, _auth_settings
    from test_four_tier_battery_export import FourTierDecisionTests
    from test_import_topup_decision_integrity import measured
    from app.optimizer import MODE_MAX_SELF

    case = FourTierDecisionTests()
    case.setUp()
    baseline = case.optimizer(max_battery_soc=100)
    when = datetime.fromtimestamp(case.FIXED_AFTERNOON.timestamp(), tz=baseline._tz)
    before = when.replace(hour=0, minute=0, second=0) - timedelta(seconds=1)
    pause, release, entered = threading.Event(), threading.Event(), threading.Event()
    class Store(StateStore):
        def optimizer_import_topup_summary(self, day):
            if pause.is_set():
                entered.set()
                release.wait(2)
            return super().optimizer_import_topup_summary(day)

    async def scenario():
        worker = await StorageWorker.open(lambda: Store(":memory:"))
        try:
            with case.optimizer_time(before):
                opt = SigEnergyOptimizer(baseline.ha, baseline.cfg.model_copy(), storage_worker=worker)
            ledger, source = opt._import_topup_ledger, opt._import_topup_source()
            current = before
            while current < when:
                capture(ledger, current, source=source)
                current = min(current + timedelta(seconds=1 if current == before else 300), when)
            capture(ledger, when, source=source)
            with case.optimizer_time(when):
                await opt._reconcile_import_storage()
                assert not opt._optimizer_import_topup_summary_today()["import_cost_floor_unknown"]
                capture(ledger, when, 1, active=True, source=source)
                old_ids = {item.payload()["event_id"] for item in ledger._pending}
                pause.set()
                outstanding = asyncio.create_task(opt._reconcile_import_storage())
                await asyncio.sleep(0.02)
                assert entered.is_set()
                started = time.monotonic()
                if boundary == "configuration":
                    old = opt.cfg.daily_import_energy
                    async with opt.configuration_transaction():
                        opt.cfg.daily_import_energy = old + "_replacement"
                    async with opt.configuration_transaction():
                        opt.cfg.daily_import_energy = old
                elif boundary == "manual":
                    state = measured(case, when, total=1, price=0.05)
                    with (patch.object(opt, "_read_state", AsyncMock(return_value=state)),
                          patch.object(opt, "_wait_for_exact_entity_state", AsyncMock(return_value=True))):
                        await opt.apply_manual_mode(opt.cfg.full_import_option)
                        await opt.apply_manual_mode(opt.cfg.block_flow_option)
                        await opt.apply_manual_mode(opt.cfg.automated_option)
                else:
                    rig = SimpleNamespace(opt=opt, ha=opt.ha)
                    transport = httpx.ASGITransport(app=_app(rig), client=("198.51.100.14", 12345))
                    with patch.object(api, "settings", _auth_settings()):
                        async with httpx.AsyncClient(transport=transport, base_url="http://synthetic.invalid") as client:
                            for limit in (4.0, 0.0):
                                response = await client.post("/api/set_ess", headers={"x-api-key": "synthetic-o14-key-for-offline-tests"}, json={
                                    "ems_mode": MODE_MAX_SELF, "grid_export_limit": 0.0,
                                    "grid_import_limit": limit, "pv_max_power_limit": 25.0,
                                })
                                assert response.status_code == 200, response.text
                assert time.monotonic() - started < 0.15
                assert not ledger.permission_known
                assert opt._optimizer_import_topup_summary_today()["import_cost_floor_unknown"]
                release.set()
                await outstanding
                if opt._ledger_job is not None:
                    await asyncio.shield(opt._ledger_job)
                    await asyncio.sleep(0)
                assert not ({item.payload()["event_id"] for item in ledger._pending} & old_ids)
                assert ledger._summary_cache is None
                assert opt._optimizer_import_topup_summary_today()["import_cost_floor_unknown"]
                await opt._reconcile_import_storage()
                assert opt._optimizer_import_topup_summary_today()["import_cost_floor_unknown"]
        finally:
            release.set()
            await worker.close()
    try:
        asyncio.run(scenario())
    finally:
        case.tearDown()


@pytest.mark.parametrize("failed", [False, True])
def test_price_tracking_markers_advance_only_after_successful_worker_ack(failed):
    async def scenario():
        entered, release = threading.Event(), threading.Event()
        class Store(StateStore):
            def record_price_event(self, **payload):
                entered.set()
                release.wait(2)
                if failed:
                    raise sqlite3.OperationalError("synthetic price failure")
                return super().record_price_event(**payload)
        worker = await StorageWorker.open(lambda: Store(":memory:"))
        try:
            opt = SigEnergyOptimizer(SimpleNamespace(), Settings(_env_file=None), storage_worker=worker)
            state = SimpleNamespace(grid_import_power_kw=1.0, grid_export_power_kw=0.0,
                                    current_price=0.1, feedin_price=0.2, battery_soc=80)
            opt._record_price_tracking(state)
            job = opt._price_job
            await asyncio.sleep(0.02)
            assert entered.is_set()
            assert opt._last_tracked_block is None
            opt._record_price_tracking(state)
            assert opt._price_job is job
            release.set()
            if failed:
                with pytest.raises(sqlite3.OperationalError):
                    await job
            else:
                await job
            await asyncio.sleep(0)
            assert opt._price_job is None
            assert (opt._last_tracked_block is None) is failed
        finally:
            release.set()
            await worker.close()
    asyncio.run(scenario())


def test_real_state_store_initialization_failure_closes_partial_connection_on_worker():
    async def scenario():
        closed = []
        original = sqlite3.connect
        class Connection:
            def __init__(self, *args, **kwargs):
                self.connection = original(*args, **kwargs)
            def execute(self, *args):
                raise sqlite3.OperationalError("synthetic schema failure")
            def close(self):
                closed.append(threading.get_ident())
                self.connection.close()
        with patch("app.state_store.sqlite3.connect", Connection):
            with pytest.raises(sqlite3.OperationalError):
                await StorageWorker.open(lambda: StateStore(":memory:"))
        assert len(closed) == 1
        assert threading.get_ident() not in closed
    asyncio.run(scenario())


def test_query_failure_without_new_capture_retires_previously_trusted_cache():
    async def scenario():
        worker = await StorageWorker.open(lambda: StateStore(":memory:"))
        try:
            ledger = await covered_ledger(worker)
            key, _, _ = ledger.reconciliation_snapshot(DAY, SOURCE)
            ledger.accept_reconciliation(key, ((), None, True, None, False))
            assert ledger.summary(DAY, source=SOURCE)["import_cost_floor_unknown"]
        finally:
            await worker.close()
    asyncio.run(scenario())


@pytest.mark.parametrize("operation", ["daily", "history"])
def test_both_estimated_earnings_fallbacks_use_owned_worker_without_stalling_loop(operation):
    from app.earnings import EarningsService
    async def scenario():
        class Store(StateStore):
            def daily_earnings_summary(self, day):
                time.sleep(0.12)
                return super().daily_earnings_summary(day)
        worker = await StorageWorker.open(lambda: Store(":memory:"))
        try:
            service = EarningsService(SimpleNamespace(), Settings(_env_file=None, earnings_source="estimated"), worker, timezone.utc)
            started = time.monotonic()
            async def heartbeat():
                await asyncio.sleep(0.02)
                return time.monotonic() - started
            beat = asyncio.create_task(heartbeat())
            if operation == "daily":
                result = await service.daily_summary(DAY)
                assert result["is_estimated"]
            else:
                result = await service.history(1)
                assert result["source_key"] == "estimated"
            assert await beat < 0.08
        finally:
            await worker.close()
    asyncio.run(scenario())
