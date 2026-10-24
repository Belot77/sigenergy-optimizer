"""SQLite interval integrity tests; every connection is isolated in memory."""
from __future__ import annotations

from copy import deepcopy
import sqlite3

import pytest

from app.state_store import StateStore


@pytest.fixture
def store():
    value = StateStore(":memory:")
    try:
        yield value
    finally:
        value.close()


def event(sequence=1, **changes):
    value = {
        "event_id": f"session-a:{sequence}", "date": "2026-10-24",
        "ts": f"2026-10-24T10:{sequence:02d}:00+11:00",
        "import_kwh": 1.0, "import_price": 0.4, "price_trusted": True,
        "checkpoint": {
            "source": "sensor.synthetic_daily_import", "date": "2026-10-24",
            "ts": f"2026-10-24T10:{sequence:02d}:00+11:00", "daily_import_kwh": 10.0 + sequence,
            "import_active": True, "session_id": "session-a", "sequence": sequence,
        },
        "unknown_days": {}, "complete_days": ["2026-10-24"],
    }
    value.update(changes)
    return value


class FaultConnection:
    """Forward to real SQLite; inject once at the actual storage boundary."""
    def __init__(self, connection, fault):
        self.connection = connection
        self.fault = fault
        self.rollback_calls = 0

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def execute(self, sql, *args):
        if self.fault == "insert" and "INSERT INTO optimizer_import_interval" in sql:
            self.fault = None
            raise sqlite3.OperationalError("synthetic insert failure")
        if self.fault == "legacy-insert" and "INSERT INTO optimizer_import_topup" in sql:
            self.fault = None
            raise sqlite3.OperationalError("synthetic legacy insert failure")
        if self.fault == "query" and "FROM optimizer_import_topup" in sql:
            self.fault = None
            raise sqlite3.OperationalError("synthetic query failure")
        return self.connection.execute(sql, *args)

    def commit(self):
        fault, self.fault = self.fault, None
        if fault == "commit-before":
            raise sqlite3.OperationalError("synthetic precommit failure")
        self.connection.commit()
        if fault == "commit-after":
            raise sqlite3.OperationalError("synthetic ambiguous commit")

    def rollback(self):
        self.rollback_calls += 1
        return self.connection.rollback()


@pytest.mark.parametrize("fault", ["insert", "commit-before"])
def test_failed_interval_write_has_no_phantom_or_later_commit(store, fault):
    value = event()
    proxy = store._conn = FaultConnection(store._conn, fault)
    with pytest.raises(sqlite3.OperationalError):
        store.record_optimizer_import_interval(value)
    assert proxy.rollback_calls == 1
    assert not proxy.in_transaction
    assert store.get_optimizer_import_checkpoint() is None
    assert store.optimizer_import_topup_summary(value["date"])["today_import_topup_kwh"] == 0.0
    # An unrelated successful operation cannot accidentally commit the failed row.
    store.record_price_event("2026-10-24T10:00:00", "2026-10-24T10:00:00", 0, 0, 0.1, 0.1, 80)
    assert store.optimizer_import_topup_summary(value["date"])["today_import_topup_kwh"] == 0.0
    store.record_optimizer_import_interval(value)
    assert store.optimizer_import_topup_summary(value["date"])["today_import_topup_kwh"] == 1.0
    assert store.get_optimizer_import_checkpoint() == {**value["checkpoint"], "event_id": value["event_id"]}


def test_commit_then_raise_reconciles_exactly_once(store):
    value = event()
    proxy = store._conn = FaultConnection(store._conn, "commit-after")
    with pytest.raises(sqlite3.OperationalError):
        store.record_optimizer_import_interval(value)
    assert proxy.rollback_calls == 1
    assert not proxy.in_transaction
    assert store.optimizer_import_topup_summary(value["date"])["today_import_topup_kwh"] == 1.0
    store.record_optimizer_import_interval(deepcopy(value))
    assert proxy.rollback_calls == 2
    assert store.optimizer_import_topup_summary(value["date"])["today_import_topup_kwh"] == 1.0
    assert store.get_optimizer_import_checkpoint()["event_id"] == value["event_id"]


def test_matching_replay_cannot_rewind_checkpoint_or_require_commit(store):
    first, later = event(), event(2, import_price=0.05)
    store.record_optimizer_import_interval(first)
    store.record_optimizer_import_interval(later)
    proxy = store._conn = FaultConnection(store._conn, "commit-before")
    store.record_optimizer_import_interval(first)
    assert proxy.fault == "commit-before", "readback replay must not commit"
    assert store.get_optimizer_import_checkpoint()["sequence"] == 2
    assert store.optimizer_import_topup_summary(first["date"])["today_import_topup_kwh"] == 2.0


@pytest.mark.parametrize("change", ["energy", "price", "trust", "checkpoint", "coverage"])
def test_event_id_reuse_requires_identical_entire_payload(store, change):
    original = event()
    store.record_optimizer_import_interval(original)
    altered = deepcopy(original)
    if change == "energy":
        altered["import_kwh"] = 2.0
    elif change == "price":
        altered["import_price"] = 0.05
    elif change == "trust":
        altered["price_trusted"] = False
    elif change == "checkpoint":
        altered["checkpoint"]["daily_import_kwh"] = 99.0
    else:
        altered["unknown_days"] = {original["date"]: "changed_coverage"}
    with pytest.raises(ValueError, match="different payload"):
        store.record_optimizer_import_interval(altered)
    assert not store._conn.in_transaction
    assert store.get_optimizer_import_checkpoint()["daily_import_kwh"] == 11.0
    summary = store.optimizer_import_topup_summary(original["date"])
    assert summary["today_import_topup_kwh"] == 1.0
    assert summary["today_highest_actual_import_price"] == 0.4
    assert summary["import_history_complete"]


def test_coverage_is_atomic_sticky_and_separate_from_price_trust(store):
    day = "2026-10-24"
    store.record_optimizer_import_interval(event())
    assert store.optimizer_import_topup_summary(day)["import_history_complete"]
    store.record_optimizer_import_interval(event(2, unknown_days={day: "lost_interval"}))
    store.record_optimizer_import_interval(event(3))
    summary = store.optimizer_import_topup_summary(day)
    assert not summary["import_history_complete"]
    assert summary["import_history_reason"] == "lost_interval"
    assert summary["import_cost_floor_unknown"]
    assert not summary["import_cost_floor_trusted"]
    assert summary["today_highest_actual_import_price"] == 0.4


def test_unspecified_day_defaults_unknown_but_existing_complete_day_is_retained(store):
    store.record_optimizer_import_interval(event(complete_days=[]))
    summary = store.optimizer_import_topup_summary("2026-10-24")
    assert not summary["import_history_complete"]
    assert summary["import_cost_floor_unknown"]
    next_day = "2026-10-25"
    store.record_optimizer_import_interval(event(2, date=next_day, complete_days=[next_day]))
    store.record_optimizer_import_interval(event(3, date=next_day, complete_days=[]))
    assert store.optimizer_import_topup_summary(next_day)["import_history_complete"]


def test_legacy_aggregation_and_tiny_import_policy_are_preserved(store):
    day = "2026-10-24"
    store.record_optimizer_import_topup(date=day, ts="2026-10-24T09:00:00", import_kwh=1.0,
                                       import_price=0.4, price_trusted=True)
    legacy = store.optimizer_import_topup_summary(day)
    assert legacy["import_cost_floor_trusted"]
    assert not legacy["import_history_complete"]
    assert legacy["import_history_reason"] == "coverage_not_recorded"
    store.record_optimizer_import_interval(event(import_price=0.05))
    store.record_optimizer_import_interval(event(2, import_kwh=0.009, import_price=None, price_trusted=False))
    summary = store.optimizer_import_topup_summary(day)
    assert summary["today_import_topup_kwh"] == 2.009
    assert summary["today_highest_actual_import_price"] == 0.4
    assert summary["import_cost_floor_trusted"]
    assert summary["import_history_complete"]
    assert store._conn.execute("SELECT COUNT(*) FROM optimizer_import_topup").fetchone()[0] == 1
    store.record_optimizer_import_interval(event(3, import_kwh=0.01, import_price=None, price_trusted=False))
    assert store.optimizer_import_topup_summary(day)["import_cost_floor_unknown"]


@pytest.mark.parametrize("fault", ["legacy-insert", "commit-before"])
def test_legacy_write_failure_rolls_back_before_other_commit(store, fault):
    store._conn = FaultConnection(store._conn, fault)
    with pytest.raises(sqlite3.OperationalError):
        store.record_optimizer_import_topup(date="2026-10-24", ts="now", import_kwh=1.0,
                                           import_price=0.4, price_trusted=True)
    assert not store._conn.in_transaction
    store.record_price_event("now", "now", 0, 0, 0.1, 0.1, 80)
    assert store.optimizer_import_topup_summary("2026-10-24")["today_import_topup_kwh"] == 0.0


def test_summary_query_failure_is_visible_instead_of_trusted_empty_history(store):
    store._conn = FaultConnection(store._conn, "query")
    with pytest.raises(sqlite3.OperationalError, match="query failure"):
        store.optimizer_import_topup_summary("2026-10-24")


@pytest.mark.parametrize("changes", [{"import_kwh": -1}, {"import_kwh": float("nan")},
                                     {"import_price": float("inf")}, {"import_price": None}])
def test_invalid_interval_cannot_partially_update_store(store, changes):
    with pytest.raises(ValueError):
        store.record_optimizer_import_interval(event(**changes))
    assert not store._conn.in_transaction
    assert store.get_optimizer_import_checkpoint() is None
