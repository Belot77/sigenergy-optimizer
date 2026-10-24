"""O16 fault/recovery regressions using real SQLite and synthetic observations."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import sqlite3
from unittest.mock import patch

import pytest

from app.import_topup_ledger import ImportTopupLedger
from app.state_store import StateStore
from test_import_topup_interval_store import FaultConnection


BASE = datetime(2026, 1, 15, tzinfo=timezone.utc)
DAY = BASE.date().isoformat()
SOURCE = "sensor.synthetic_daily|sensor.synthetic_import_kw|UTC"


def observe(ledger, minute, total, *, price=0.4, trusted=True, active=True,
            source=SOURCE, power=0.0):
    ledger.record(
        now=BASE + timedelta(minutes=minute), source=source,
        daily_import_kwh=total, grid_import_kw=power, import_price=price,
        price_trusted=trusted, import_active=active,
    )


def healthy_ledger(store, **options):
    before = BASE - timedelta(seconds=1)
    ledger = ImportTopupLedger(store, started_at=before, source=SOURCE, **options)
    ledger.record(now=before, source=SOURCE, daily_import_kwh=0, grid_import_kw=0,
                  import_price=None, price_trusted=False, import_active=False)
    observe(ledger, 0, 0, active=False)
    assert ledger.summary(DAY, source=SOURCE)["import_history_complete"]
    return ledger


@pytest.fixture
def context():
    store = StateStore(":memory:")
    try:
        yield store, healthy_ledger(store)
    finally:
        store.close()


@pytest.mark.parametrize("fault", ["insert", "commit-before", "commit-after"])
def test_original_expensive_interval_survives_storage_failure_and_tariff_change(context, fault):
    store, ledger = context
    store._conn = FaultConnection(store._conn, fault)
    with pytest.raises(sqlite3.OperationalError):
        observe(ledger, 1, 1.0, price=0.4)
    pending = ledger.summary(DAY, source=SOURCE)
    assert pending["import_cost_floor_unknown"]
    assert not pending["import_history_complete"]
    observe(ledger, 2, 2.0, price=0.05)
    summary = ledger.summary(DAY, source=SOURCE)
    assert summary["today_import_topup_kwh"] == 2.0
    assert summary["today_highest_actual_import_price"] == 0.4
    assert summary["import_cost_floor_trusted"]
    assert summary["import_history_complete"]
    assert store.get_optimizer_import_checkpoint()["daily_import_kwh"] == 2.0


def test_failed_untrusted_interval_stays_untrusted_after_trusted_recovery(context):
    store, ledger = context
    store._conn = FaultConnection(store._conn, "insert")
    with pytest.raises(sqlite3.OperationalError):
        observe(ledger, 1, 1.0, price=None, trusted=False)
    observe(ledger, 2, 2.0, price=0.05)
    summary = ledger.summary(DAY, source=SOURCE)
    assert summary["today_import_topup_kwh"] == 2.0
    assert summary["import_history_complete"]
    assert summary["import_cost_floor_unknown"]
    assert not summary["import_cost_floor_trusted"]


def test_repeated_retries_keep_identical_event_payload_and_original_tariff(context):
    store, ledger = context
    original = store.record_optimizer_import_interval
    attempted = []
    failures = 3

    def fail_then_write(event):
        nonlocal failures
        attempted.append(deepcopy(event))
        if failures:
            failures -= 1
            raise sqlite3.OperationalError("synthetic repeated failure")
        return original(event)

    with patch.object(store, "record_optimizer_import_interval", fail_then_write):
        for minute, total, price in ((1, 1, 0.4), (2, 2, 0.05), (3, 3, 0.01)):
            with pytest.raises(sqlite3.OperationalError):
                observe(ledger, minute, total, price=price)
        ledger.flush()
    first_id = attempted[0]["event_id"]
    retries = [event for event in attempted if event["event_id"] == first_id]
    assert len(retries) == 4 and all(event == retries[0] for event in retries)
    summary = ledger.summary(DAY, source=SOURCE)
    assert summary["today_import_topup_kwh"] == 3.0
    assert summary["today_highest_actual_import_price"] == 0.4
    assert summary["import_cost_floor_trusted"]


def test_inactive_transition_does_not_drop_a_pending_import_interval(context):
    store, ledger = context
    store._conn = FaultConnection(store._conn, "insert")
    with pytest.raises(sqlite3.OperationalError):
        observe(ledger, 1, 1.0, price=0.4)
    observe(ledger, 2, 1.0, price=0.05, active=False)
    summary = ledger.summary(DAY, source=SOURCE)
    assert summary["today_import_topup_kwh"] == 1.0
    assert summary["today_highest_actual_import_price"] == 0.4
    assert summary["import_history_complete"]
    assert not store.get_optimizer_import_checkpoint()["import_active"]


def test_queue_overflow_stays_unknown_after_all_retained_intervals_reconcile():
    store = StateStore(":memory:")
    try:
        ledger = healthy_ledger(store, pending_limit=2)
        with patch.object(store, "record_optimizer_import_interval", side_effect=sqlite3.OperationalError("unavailable")):
            for minute in (1, 2, 3):
                with pytest.raises(sqlite3.OperationalError):
                    observe(ledger, minute, minute)
            assert len(ledger._pending) == 2
        # The third snapshot could not be retained. Recovering the first two is
        # insufficient to claim complete history, including after later writes.
        observe(ledger, 4, 3, active=False)
        observe(ledger, 5, 4, price=0.05)
        summary = ledger.summary(DAY, source=SOURCE)
        assert summary["today_import_topup_kwh"] == 3.0
        assert summary["import_cost_floor_unknown"]
        assert not summary["import_history_complete"]
        assert store.optimizer_import_topup_summary(DAY)["import_cost_floor_unknown"]
    finally:
        store.close()


def test_source_change_preserves_old_pending_payload_without_cross_meter_delta(context):
    store, ledger = context
    store._conn = FaultConnection(store._conn, "insert")
    with pytest.raises(sqlite3.OperationalError):
        observe(ledger, 1, 1, price=0.4)
    other = "sensor.replacement_daily|sensor.replacement_import_kw|UTC"
    # Unknown status applies even before the replacement's first capture.
    assert ledger.summary(DAY, source=other)["import_cost_floor_unknown"]
    observe(ledger, 2, 1000, source=other, price=0.05)
    summary = ledger.summary(DAY, source=other)
    assert summary["today_import_topup_kwh"] == 1.0
    assert summary["today_highest_actual_import_price"] == 0.4
    assert summary["import_cost_floor_unknown"]
    assert store.get_optimizer_import_checkpoint()["source"] == other


def test_counter_reset_does_not_create_a_cross_reset_energy_delta(context):
    store, ledger = context
    observe(ledger, 1, 10, active=False)
    observe(ledger, 2, 1, power=6)
    summary = ledger.summary(DAY, source=SOURCE)
    assert summary["today_import_topup_kwh"] == 0.1
    assert summary["import_cost_floor_unknown"]


@pytest.mark.parametrize("fault", ["insert", "commit-before", "commit-after"])
def test_restart_never_trusts_a_missing_failure_marker(context, fault):
    store, ledger = context
    store._conn = FaultConnection(store._conn, fault)
    with pytest.raises(sqlite3.OperationalError):
        observe(ledger, 1, 1, price=0.4)
    # Serialize SQLite into a fresh connection: RAM pending payloads are lost.
    image = store._conn.connection.serialize()
    restored = StateStore(":memory:")
    try:
        restored._conn.deserialize(image)
        restarted = ImportTopupLedger(restored, started_at=BASE + timedelta(minutes=2), source=SOURCE)
        assert restarted.summary(DAY, source=SOURCE)["import_cost_floor_unknown"]
        observe(restarted, 2, 2, price=0.05)
        after = restarted.summary(DAY, source=SOURCE)
        assert after["import_cost_floor_unknown"]
        assert not after["import_history_complete"]
        expected = 1.0 if fault == "commit-after" else 0.0
        assert after["today_import_topup_kwh"] == expected
    finally:
        restored.close()


@pytest.mark.parametrize("legacy", [False, True], ids=["empty-database", "legacy-price-rows"])
def test_startup_current_day_is_unknown_before_first_capture(legacy):
    store = StateStore(":memory:")
    try:
        if legacy:
            store.record_optimizer_import_topup(date=DAY, ts=BASE.isoformat(), import_kwh=1,
                                                import_price=0.4, price_trusted=True)
        ledger = ImportTopupLedger(store, started_at=BASE, source=SOURCE)
        summary = ledger.summary(DAY, source=SOURCE)
        assert summary["import_cost_floor_unknown"]
        assert not summary["import_history_complete"]
        assert summary["today_import_topup_kwh"] == (1.0 if legacy else 0.0)
    finally:
        store.close()


def test_continuous_inactive_midnight_can_establish_new_day(context):
    store, ledger = context
    # This fixture already crossed one observed inactive midnight.
    assert ledger.summary(DAY, source=SOURCE)["import_cost_floor_trusted"]
    # A long unobserved gap cannot establish the following day as complete.
    observe(ledger, 24 * 60, 0, active=False)
    following = (BASE + timedelta(days=1)).date().isoformat()
    assert ledger.summary(following, source=SOURCE)["import_cost_floor_unknown"]


def test_active_midnight_never_subtracts_different_day_counters():
    store = StateStore(":memory:")
    before = BASE - timedelta(seconds=1)
    try:
        ledger = ImportTopupLedger(store, started_at=before, source=SOURCE)
        ledger.record(now=before, source=SOURCE, daily_import_kwh=100, grid_import_kw=10,
                      import_price=0.4, price_trusted=True, import_active=True)
        observe(ledger, 0, 0.2, price=0.05, power=10)
        summary = ledger.summary(DAY, source=SOURCE)
        assert summary["today_import_topup_kwh"] == 0.0
        assert summary["import_cost_floor_unknown"]
        assert store.optimizer_import_topup_summary(before.date().isoformat())["import_cost_floor_unknown"]
    finally:
        store.close()


@pytest.mark.parametrize("seconds", [-1, 301])
def test_observation_gap_is_unknown_before_the_next_control_decision(context, seconds):
    store, ledger = context
    summary = ledger.summary(DAY, source=SOURCE, observed_at=BASE + timedelta(seconds=seconds))
    assert summary["import_cost_floor_unknown"]
    assert not summary["import_history_complete"]


def test_unavailable_query_returns_explicit_unknown_history(context):
    store, ledger = context
    with patch.object(store, "optimizer_import_topup_summary", side_effect=sqlite3.OperationalError("unavailable")):
        summary = ledger.summary(DAY, source=SOURCE)
    assert summary["import_cost_floor_unknown"]
    assert not summary["import_cost_floor_trusted"]
    assert summary["import_history_reason"] == "history_unavailable"


def test_repeated_inactive_observations_do_not_add_sql_writes(context):
    store, ledger = context
    with patch.object(store, "record_optimizer_import_interval", wraps=store.record_optimizer_import_interval) as write:
        observe(ledger, 1, 0, active=False)
        observe(ledger, 2, 0, active=False)
    write.assert_not_called()
    assert ledger.summary(DAY, source=SOURCE, observed_at=BASE + timedelta(minutes=2))["import_history_complete"]


@pytest.mark.parametrize("older_pending", [False, True])
def test_failure_before_snapshot_retention_is_unknown_even_with_older_pending(context, older_pending):
    store, ledger = context
    if older_pending:
        with patch.object(store, "record_optimizer_import_interval", side_effect=sqlite3.OperationalError("unavailable")):
            with pytest.raises(sqlite3.OperationalError):
                observe(ledger, 1, 1)
    with patch.object(ledger, "_persist_interval", side_effect=ValueError("synthetic prequeue failure")):
        with pytest.raises(ValueError):
            observe(ledger, 2, 2, price=0.05)
    ledger.flush()
    assert ledger.summary(DAY, source=SOURCE)["import_cost_floor_unknown"]
    observe(ledger, 3, 2, active=False)
    assert store.optimizer_import_topup_summary(DAY)["import_cost_floor_unknown"]


def test_unrepresentable_energy_is_explicit_unknown(context):
    store, ledger = context
    observe(ledger, 1, 0, power=1e308)
    summary = ledger.summary(DAY, source=SOURCE)
    assert summary["import_cost_floor_unknown"]
    assert summary["today_import_topup_kwh"] == 0.0


def test_confirmed_close_keeps_measured_import_tail_exactly_once(context):
    store, ledger = context
    observe(ledger, 1, 1, price=0.05)
    ledger.set_permission(now=BASE + timedelta(seconds=65), source=SOURCE, import_active=False)
    assert ledger.import_active
    assert ledger.summary(DAY, source=SOURCE)["import_cost_floor_unknown"]
    ledger.record(now=BASE + timedelta(seconds=70), source=SOURCE, daily_import_kwh=1.1,
                  grid_import_kw=0, import_price=0.4, price_trusted=True,
                  import_active=ledger.import_active, permission_known=ledger.permission_known)
    assert not ledger.import_active
    ledger.set_permission(now=BASE + timedelta(seconds=70), source=SOURCE, import_active=False)
    observe(ledger, 2, 1.1, active=False)
    summary = ledger.summary(DAY, source=SOURCE)
    assert summary["today_import_topup_kwh"] == 1.1
    assert summary["today_highest_actual_import_price"] == 0.4


def test_unconfirmed_application_cannot_certify_inactive_midnight():
    store = StateStore(":memory:")
    before = BASE - timedelta(seconds=1)
    try:
        ledger = ImportTopupLedger(store, started_at=before, source=SOURCE)
        ledger.record(now=before, source=SOURCE, daily_import_kwh=0, grid_import_kw=0,
                      import_price=0.1, price_trusted=True, import_active=False)
        ledger.invalidate(before, "application_not_confirmed")
        assert not ledger.permission_known
        ledger.record(now=BASE, source=SOURCE, daily_import_kwh=0, grid_import_kw=0,
                      import_price=0.1, price_trusted=True, import_active=ledger.import_active,
                      permission_known=ledger.permission_known)
        assert ledger.summary(DAY, source=SOURCE)["import_cost_floor_unknown"]
    finally:
        store.close()
