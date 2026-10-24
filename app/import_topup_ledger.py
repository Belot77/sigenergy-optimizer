"""Loss-aware import-cost capture with event-loop-owned reconciliation state."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
from datetime import datetime
import json
import math
from typing import Any
from uuid import uuid4

from .state_store import StateStore


@dataclass(frozen=True)
class _Sample:
    now: datetime
    source: str
    daily_kwh: float | None
    active: bool
    permission_known: bool


@dataclass(frozen=True)
class _PendingInterval:
    # Serialized once: a retry cannot inherit later tariff, trust or identity.
    payload_json: str

    def payload(self) -> dict[str, Any]:
        return json.loads(self.payload_json)


class ImportTopupLedger:
    """Separate observed measurement progress from acknowledged durable progress."""

    def __init__(self, store: StateStore, *, started_at: datetime, source: str,
                 pending_limit: int = 256, deferred: bool = False) -> None:
        if started_at.utcoffset() is None:
            raise ValueError("Import ledger needs an aware local time")
        if pending_limit < 1:
            raise ValueError("Import ledger pending limit must be positive")
        self.store = store
        self._source = source
        self._session_id = uuid4().hex
        self._sequence = 0
        self._last: _Sample | None = None
        self._applied_active = False
        self._import_tail_pending = False
        self._pending: deque[_PendingInterval] = deque()
        self._pending_limit = pending_limit
        self._unknown_days = {started_at.date().isoformat(): "startup_or_legacy_history"}
        self._unknown_revision = 1
        self._queued_unknown_revision = 0
        self._checkpoint_loaded = False
        self._snapshot_retained = False
        self._deferred = deferred
        self._observation_generation = 0
        self._summary_cache = None

    @staticmethod
    def _finite(value: Any) -> float | None:
        try:
            result = float(value)
        except (TypeError, ValueError, OverflowError):
            return None
        return result if math.isfinite(result) else None

    def _mark_unknown(self, day: str, reason: str) -> None:
        if day not in self._unknown_days:
            self._unknown_days[day] = reason
            self._unknown_revision += 1

    def _load_checkpoint(self, day: str) -> None:
        if self._checkpoint_loaded or self._deferred:
            return
        try:
            previous = self.store.get_optimizer_import_checkpoint()
            if previous is not None:
                previous_day = str(previous["date"])
                datetime.fromisoformat(previous_day)
                # A new process cannot recover an uncaptured interval's tariff.
                self._mark_unknown(previous_day, "restart_gap")
        except Exception:
            self._mark_unknown(day, "checkpoint_unavailable")
            return
        self._checkpoint_loaded = True

    def _check_source(self, source: str, day: str) -> None:
        if source != self._source:
            self._mark_unknown(day, "measurement_source_changed")
            if self._last is not None:
                self._mark_unknown(self._last.now.date().isoformat(), "measurement_source_changed")

    def begin_capture(self) -> None:
        self._observation_generation += 1
        self._summary_cache = None
        self._snapshot_retained = False

    @property
    def snapshot_retained(self) -> bool:
        return self._snapshot_retained

    def record(self, *, now: datetime, source: str, daily_import_kwh: Any,
               grid_import_kw: Any, import_price: Any, price_trusted: bool,
               import_active: bool, permission_known: bool = True) -> None:
        self.begin_capture()
        try:
            self._record(now=now, source=source, daily_import_kwh=daily_import_kwh,
                         grid_import_kw=grid_import_kw, import_price=import_price,
                         price_trusted=price_trusted, import_active=import_active,
                         permission_known=permission_known)
        except Exception:
            if not self.snapshot_retained:
                self.invalidate(now, "interval_snapshot_unretained")
            raise

    def _record(self, *, now: datetime, source: str, daily_import_kwh: Any,
                grid_import_kw: Any, import_price: Any, price_trusted: bool,
                import_active: bool, permission_known: bool) -> None:
        if now.utcoffset() is None:
            raise ValueError("Import ledger needs an aware local time")
        day = now.date().isoformat()
        self._load_checkpoint(day)
        self._check_source(source, day)
        daily = self._finite(daily_import_kwh)
        if daily is None or daily < 0:
            daily = None
            self._mark_unknown(day, "import_counter_unavailable")
        current = _Sample(now, source, daily, bool(import_active), bool(permission_known))
        if not current.permission_known:
            self._mark_unknown(day, "import_permission_unproven")
        previous = self._last
        import_kwh = 0.0
        complete_days: list[str] = []
        energy_source = "inactive"
        same_basis = previous is not None and previous.source == source
        same_day = same_basis and previous.now.date() == now.date()
        elapsed = (now - previous.now).total_seconds() if previous is not None else 0.0
        continuous = same_basis and 0 <= elapsed <= 300

        if previous is not None and (elapsed < 0 or elapsed > 300):
            self._mark_unknown(day, "observation_gap_or_clock_change")
            self._mark_unknown(previous.now.date().isoformat(), "observation_gap_or_clock_change")
        if previous is None:
            self._mark_unknown(day, "missing_initial_boundary")
        elif not same_day:
            # Only an observed inactive boundary proves a new day without an
            # unpriced import interval. Never subtract different-day meters.
            if (continuous and previous.permission_known and current.permission_known
                    and not previous.active and not current.active and daily is not None):
                complete_days.append(day)
            else:
                self._mark_unknown(day, "unproven_day_or_source_boundary")
                self._mark_unknown(previous.now.date().isoformat(), "unproven_day_or_source_boundary")
        elif daily is None or previous.daily_kwh is None or daily < previous.daily_kwh:
            self._mark_unknown(day, "import_counter_reset_or_unavailable")

        measured_active = bool(current.active or (previous is not None and previous.active)
                               or self._import_tail_pending)
        if measured_active:
            energy_source = "unproven_boundary"
            if same_day and daily is not None and previous.daily_kwh is not None:
                import_kwh = max(0.0, daily - previous.daily_kwh)
                energy_source = "daily_import_delta"
            # Preserve the existing same-source/day fallback and 300s ceiling.
            if same_day and import_kwh <= 0.0:
                power = self._finite(grid_import_kw)
                if power is not None:
                    import_kwh = max(0.0, power) * max(0.0, min(elapsed, 300.0)) / 3600.0
                    energy_source = "grid_import_power_integral"
                else:
                    self._mark_unknown(day, "import_power_unavailable")

        if not math.isfinite(import_kwh):
            self._mark_unknown(day, "interval_energy_unrepresentable")
            import_kwh = 0.0
            energy_source = "unrepresentable_interval"
        if self._import_tail_pending:
            # Confirmed closure can leave import between the last measurement
            # and the close command. Price that tail once at the next read.
            current = replace(current, active=self._applied_active)
            self._import_tail_pending = False
        else:
            self._applied_active = current.active
        self._last = current
        self._source = source
        # No repeated inactive writes are needed when identity/day/ownership and
        # coverage are unchanged. The in-memory measurement boundary still moves.
        needs_event = bool(
            measured_active or previous is None or previous.active or not same_day
            or self._unknown_revision != self._queued_unknown_revision
        )
        if not needs_event:
            self._snapshot_retained = True  # No accounting interval was omitted.
            self.flush()
            return

        self._persist_interval(current, import_kwh=import_kwh,
                               import_price=import_price, price_trusted=price_trusted,
                               energy_source=energy_source, complete_days=complete_days)

    @property
    def has_pending(self) -> bool:
        return bool(self._pending)

    @property
    def import_active(self) -> bool:
        return bool(self._applied_active or self._import_tail_pending)

    @property
    def permission_known(self) -> bool:
        return bool(self._last is not None and self._last.permission_known)

    def invalidate(self, now: datetime, reason: str, *, permission_unknown: bool = False) -> None:
        self._observation_generation += 1
        self._summary_cache = None
        if (permission_unknown or reason == "application_not_confirmed") and self._last is not None:
            self._last = replace(self._last, permission_known=False)
        self._mark_unknown(now.date().isoformat(), reason)
        if self._last is not None:
            self._mark_unknown(self._last.now.date().isoformat(), reason)

    def set_permission(self, *, now: datetime, source: str, import_active: bool) -> None:
        """Change the next interval's owner only after confirmed application.

        Retain the actual measurement timestamp; a command is not new telemetry.
        """
        self.begin_capture()
        try:
            self._set_permission(now=now, source=source, import_active=import_active)
        except Exception:
            if not self.snapshot_retained:
                self.invalidate(now, "permission_snapshot_unretained")
            raise

    def _set_permission(self, *, now: datetime, source: str, import_active: bool) -> None:
        self._check_source(source, now.date().isoformat())
        if self._last is None:
            self.invalidate(now, "missing_initial_boundary")
            return
        if (self._last.active == bool(import_active) and self._last.permission_known
                and self._unknown_revision == self._queued_unknown_revision):
            self._snapshot_retained = True
            self.flush()
            return
        if self._applied_active and not import_active:
            self._import_tail_pending = True
        self._applied_active = bool(import_active)
        self._last = replace(self._last, active=bool(import_active), permission_known=True)
        self._persist_interval(self._last, import_kwh=0.0, import_price=None,
                               price_trusted=False, energy_source="permission_boundary",
                               complete_days=[], permission_changed_at=now.isoformat())

    def _persist_interval(self, current: _Sample, *, import_kwh: float,
                          import_price: Any, price_trusted: bool, energy_source: str,
                          complete_days: list[str], permission_changed_at: str | None = None) -> None:
        now, source = current.now, current.source
        day = now.date().isoformat()
        price = self._finite(import_price)
        trusted = bool(price_trusted and price is not None)
        self._sequence += 1
        payload = {
            "event_id": f"{self._session_id}:{self._sequence}",
            "date": day, "ts": now.isoformat(), "import_kwh": import_kwh,
            "import_price": price if trusted else None, "price_trusted": trusted,
            "energy_source": energy_source,
            "checkpoint": {
                "source": source, "date": day, "ts": now.isoformat(),
                "daily_import_kwh": current.daily_kwh, "import_active": current.active,
                "permission_known": current.permission_known,
                "import_tail_pending": self._import_tail_pending,
                "session_id": self._session_id, "sequence": self._sequence,
            },
            "unknown_days": dict(self._unknown_days),
            "complete_days": complete_days,
            "permission_changed_at": permission_changed_at,
        }
        pending = _PendingInterval(json.dumps(payload, sort_keys=True, allow_nan=False))
        if len(self._pending) >= self._pending_limit:
            try:
                self.flush()
                if len(self._pending) >= self._pending_limit:
                    raise RuntimeError("Import interval queue full")
            except Exception:
                # The current snapshot cannot be retained within the bound.
                # Its day stays unknown even if every older pending write clears.
                self._mark_unknown(day, "pending_interval_overflow")
                raise
        self._pending.append(pending)
        self._snapshot_retained = True
        self._queued_unknown_revision = self._unknown_revision
        self.flush()

    def flush(self) -> None:
        if self._deferred:
            return
        while self._pending:
            pending = self._pending[0]
            self.store.record_optimizer_import_interval(pending.payload())
            # A raised/lost acknowledgement leaves the identical event queued.
            self._pending.popleft()

    def reconciliation_snapshot(self, day: str, source: str):
        """Only immutable values cross to the DB worker; never this ledger."""
        key = self._cache_key(day, source)
        return (key, tuple(item.payload_json for item in list(self._pending)[:16]),
                not self._checkpoint_loaded)

    def _cache_key(self, day: str, source: str):
        return (self._observation_generation, self._unknown_revision, day, source, self._sequence)

    def accept_reconciliation(self, key, result) -> None:
        acknowledged, checkpoint, checkpoint_read, summary, successful = result
        if not successful:
            self._summary_cache = None
        for event_id in acknowledged:
            if not self._pending or self._pending[0].payload()["event_id"] != event_id:
                break
            self._pending.popleft()
        if checkpoint_read and not self._checkpoint_loaded:
            if checkpoint is not None:
                previous_day = str(checkpoint["date"])
                datetime.fromisoformat(previous_day)
                self._mark_unknown(previous_day, "restart_gap")
            self._checkpoint_loaded = True
        # A late acknowledgement may retire an exact head, but cannot restore
        # trust after any intervening capture/permission/identity transition.
        if (successful and not self._pending and not self._import_tail_pending
                and key == self._cache_key(key[2], key[3])):
            self._summary_cache = (key, dict(summary))

    @staticmethod
    def _unknown_summary(day: str) -> dict[str, Any]:
        return {
            "date": day, "today_import_topup_kwh": 0.0,
            "today_highest_actual_import_price": None,
            "import_cost_export_floor": None, "import_cost_floor_trusted": False,
            "import_cost_floor_unknown": True, "import_history_complete": False,
            "import_history_reason": "history_unavailable",
        }

    def summary(self, day: str, *, source: str,
                observed_at: datetime | None = None) -> dict[str, Any]:
        if observed_at is not None:
            if observed_at.utcoffset() is None:
                raise ValueError("Import ledger needs an aware local time")
            if self._last is None:
                self._mark_unknown(day, "missing_current_process_boundary")
            else:
                elapsed = (observed_at - self._last.now).total_seconds()
                if elapsed < 0 or elapsed > 300:
                    self._mark_unknown(day, "observation_gap_or_clock_change")
                    self._mark_unknown(self._last.now.date().isoformat(), "observation_gap_or_clock_change")
        self._load_checkpoint(day)
        self._check_source(source, day)
        try:
            if self._deferred:
                if self._summary_cache is None or self._summary_cache[0] != self._cache_key(day, source):
                    return self._unknown_summary(day)
                result = dict(self._summary_cache[1])
            else:
                result = dict(self.store.optimizer_import_topup_summary(day))
        except Exception:
            return self._unknown_summary(day)
        pending = any(item.payload()["date"] == day for item in self._pending)
        reason = self._unknown_days.get(day)
        if reason is None and pending:
            reason = "interval_reconciliation_pending"
        if reason is None and self._import_tail_pending:
            reason = "import_tail_measurement_pending"
        complete = bool(result.get("import_history_complete", False) and reason is None)
        if not complete:
            result["import_history_complete"] = False
            result["import_history_reason"] = reason or result.get("import_history_reason") or "history_unverified"
            result["import_cost_floor_unknown"] = True
            result["import_cost_floor_trusted"] = False
        return result
