"""Bounded, passive diagnostic summaries for MSC settlement attempts.

This module has no Home Assistant or application dependencies. It records only
allowlisted scalar states, timestamps, finite numbers, and reason codes.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import math
import re


_ALLOWED_LABELS = frozenset({"msc", "export"})
_ALLOWED_PHASES = frozenset({"primary", "fallback", "close", "maintenance", "msc"})
_ALLOWED_OUTCOMES = frozenset({
    "accepted", "rejected", "pending", "failed", "succeeded", "exception", "cancelled",
})
_ALLOWED_STATUSES = frozenset({
    "succeeded", "failed", "pending", "exception", "cancelled", "unreported",
})
_ALLOWED_REASONS = frozenset({
    "missing", "unavailable", "metadata_conflict", "invalid_timestamp", "future",
    "stale", "pre_request", "equal_request", "state_mismatch", "target_mismatch",
    "accepted", "timeout", "read_failed", "unknown", "report_regression", "clock_regression",
})
_ALLOWED_STATES = frozenset({
    "Maximum Self Consumption", "Command Discharging (PV First)",
    "Command Discharging (ESS First)", "Command Charging (PV First)",
    "Command Charging (Grid First)", "Automated", "Manual", "Force",
    "Unknown", "unknown", "unavailable", "none", "ON", "OFF", "on", "off", "true", "false", "enabled", "disabled",
})
_ALLOWED_METADATA_STATUSES = frozenset({
    "accepted", "missing", "metadata_conflict", "invalid_timestamp", "read_failed",
})
_ALLOWED_OBSERVATION_FIELDS = frozenset({
    "state", "value", "available", "last_reported", "last_updated", "last_changed", "timestamp",
    "metadata_status", "_msc_metadata_status",
})
_MAX_ENTRIES = 12
_MAX_ABS_NUMBER = 1e15


def _finite_number(value: object) -> bool:
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value) and abs(value) <= _MAX_ABS_NUMBER
    except (OverflowError, TypeError, ValueError):
        return False


def _aware_datetime(value: object) -> datetime | None:
    """Parse only aware datetimes and bounded aware ISO timestamp strings."""
    try:
        if type(value) is datetime:
            parsed = value
        elif type(value) is str and 1 <= len(value) <= 64:
            text = value[:-1] + "+00:00" if value.endswith("Z") else value
            parsed = datetime.fromisoformat(text)
        else:
            return None
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _timestamp(value: object) -> str | int | float | None:
    """Return finite seconds or a normalized aware ISO timestamp."""
    if type(value) is datetime:
        parsed = _aware_datetime(value)
        if parsed is not None:
            return parsed.isoformat(timespec="microseconds").replace("+00:00", "Z")
        return None
    if type(value) is str:
        parsed = _aware_datetime(value)
        if parsed is None:
            return None
        return parsed.isoformat(timespec="microseconds").replace("+00:00", "Z")
    if _finite_number(value):
        return value
    return None


def _scalar(value: object) -> bool | int | float | str | None:
    if type(value) is bool:
        return value
    if _finite_number(value):
        return value
    if type(value) is str:
        if value in _ALLOWED_STATES:
            return value
        if 1 <= len(value) <= 32 and re.fullmatch(
            r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", value,
        ):
            try:
                number = float(value)
            except (OverflowError, ValueError):
                return None
            return number if math.isfinite(number) and abs(number) <= _MAX_ABS_NUMBER else None
    return None


def _timestamp_reason_flags(obj: object, boundary: object, observed_at: object, reason: object) -> list[str]:
    flags = []
    try:
        if type(reason) is str and reason in {"future", "invalid_timestamp"}:
            flags.append(reason)
        if any(value is not None and _timestamp(value) is None for value in (boundary, observed_at)):
            if "invalid_timestamp" not in flags:
                flags.append("invalid_timestamp")
        if type(obj) is not dict:
            return flags
        observed = _aware_datetime(observed_at)
        for key in ("last_reported", "last_updated", "last_changed", "timestamp"):
            if key not in obj or obj[key] is None:
                continue
            parsed = _aware_datetime(obj[key])
            if parsed is None:
                if "invalid_timestamp" not in flags:
                    flags.append("invalid_timestamp")
            elif observed is not None and parsed > observed and "future" not in flags:
                flags.append("future")
        metadata = dict.get(obj, "_msc_metadata_status", dict.get(obj, "metadata_status"))
        if metadata == "invalid_timestamp" and "invalid_timestamp" not in flags:
            flags.append("invalid_timestamp")
    except Exception:
        return flags
    return flags


def _outcome(value: object) -> bool | str | None:
    if type(value) is bool:
        return value
    if type(value) is str and value in _ALLOWED_OUTCOMES:
        return value
    return None


def _safe_object(value: object) -> dict:
    """Copy a plain mapping's approved state and timestamp fields only."""
    if type(value) is not dict:
        return {}
    result = {}
    try:
        for key, item in dict.items(value):
            if type(key) is not str or key not in _ALLOWED_OBSERVATION_FIELDS:
                continue
            safe = _timestamp(item) if key in {
                "last_reported", "last_updated", "last_changed", "timestamp",
            } else _scalar(item)
            if key in {"metadata_status", "_msc_metadata_status"}:
                continue
            if safe is not None:
                result[key] = safe
        metadata_key = "_msc_metadata_status" if "_msc_metadata_status" in value else "metadata_status"
        metadata_status = dict.get(value, metadata_key)
        if type(metadata_status) is str and metadata_status in _ALLOWED_METADATA_STATUSES:
            result["metadata_status"] = metadata_status
    except Exception:
        return {}
    return result


def _bounded_append(items: list[dict], item: dict) -> None:
    """Keep the first half and a rolling latest half of this bounded stream."""
    if len(items) < _MAX_ENTRIES:
        items.append(item)
        return
    split = _MAX_ENTRIES // 2
    items[:] = items[:split] + items[split + 1:] + [item]


class MscSettlementEvidence:
    """Store process-local, non-authoritative evidence for one attempt at a time."""

    def __init__(self) -> None:
        self._attempt = 0
        self._started = False
        self._finished = False
        self._status = "unreported"
        self._request_count = 0
        self._observation_count = 0
        self._first_request_at = None
        self._latest_request_at = None
        self._first_observation_at = None
        self._latest_observation_at = None
        self._requests: list[dict] = []
        self._observations: list[dict] = []
        self._request_counts = {label: 0 for label in sorted(_ALLOWED_LABELS)}
        self._observation_counts = {label: 0 for label in sorted(_ALLOWED_LABELS)}
        self._observation_reason_counts: dict[str, int] = {}

    def start(self) -> None:
        """Begin a new in-memory attempt, discarding prior attempt details."""
        try:
            self._attempt += 1
            self._started = True
            self._finished = False
            self._status = "unreported"
            self._request_count = 0
            self._observation_count = 0
            self._first_request_at = None
            self._latest_request_at = None
            self._first_observation_at = None
            self._latest_observation_at = None
            self._requests = []
            self._observations = []
            self._request_counts = {label: 0 for label in sorted(_ALLOWED_LABELS)}
            self._observation_counts = {label: 0 for label in sorted(_ALLOWED_LABELS)}
            self._observation_reason_counts = {}
        except Exception:
            # Diagnostics must not escape into a control caller.
            return

    def _ensure_started(self) -> None:
        if not self._started:
            self.start()

    def record_request(
        self,
        label: str,
        phase: str,
        target: object,
        requested_at: object,
        outcome: object = None,
    ) -> None:
        """Record an allowlisted actuator request summary, never its payload."""
        try:
            if self._finished or type(label) is not str or label not in _ALLOWED_LABELS:
                return
            if type(phase) is not str or phase not in _ALLOWED_PHASES:
                return
            self._ensure_started()
            stamp = _timestamp(requested_at)
            entry = {
                "label": label,
                "phase": phase,
                "target": _scalar(target),
                "requested_at": stamp,
                "outcome": _outcome(outcome),
            }
            self._request_count += 1
            self._request_counts[label] += 1
            if self._first_request_at is None:
                self._first_request_at = stamp
            self._latest_request_at = stamp
            _bounded_append(self._requests, entry)
        except Exception:
            return

    def record_observation(
        self,
        label: str,
        phase: str,
        expected: object,
        boundary: object,
        obj: object,
        observed_at: object,
        outcome: object,
        reason: object = None,
    ) -> None:
        """Record allowlisted observed state and report metadata only."""
        try:
            if self._finished or type(label) is not str or label not in _ALLOWED_LABELS:
                return
            if type(phase) is not str or phase not in _ALLOWED_PHASES:
                return
            self._ensure_started()
            safe_reason = reason if type(reason) is str and reason in _ALLOWED_REASONS else "unknown"
            stamp = _timestamp(observed_at)
            entry = {
                "label": label,
                "phase": phase,
                "expected": _scalar(expected),
                "boundary": _timestamp(boundary),
                "observed": _safe_object(obj),
                "observed_at": stamp,
                "reason_flags": _timestamp_reason_flags(obj, boundary, observed_at, reason),
                "outcome": _outcome(outcome),
                "reason": safe_reason,
            }
            self._observation_count += 1
            self._observation_counts[label] += 1
            self._observation_reason_counts[safe_reason] = (
                self._observation_reason_counts.get(safe_reason, 0) + 1
            )
            if self._first_observation_at is None:
                self._first_observation_at = stamp
            self._latest_observation_at = stamp
            _bounded_append(self._observations, entry)
        except Exception:
            return

    def finish(self, status: str) -> dict:
        """Mark the attempt complete and return a detached, safe snapshot."""
        try:
            self._ensure_started()
            self._status = status if type(status) is str and status in _ALLOWED_STATUSES else "unreported"
            self._finished = True
        except Exception:
            pass
        return self.snapshot()

    def snapshot(self) -> dict:
        """Return bounded diagnostics without exposing mutable internal state."""
        try:
            return deepcopy({
                "attempt": self._attempt,
                "started": self._started,
                "finished": self._finished,
                "status": self._status,
                "request_count": self._request_count,
                "observation_count": self._observation_count,
                "request_counts": self._request_counts,
                "observation_counts": self._observation_counts,
                "observation_reason_counts": self._observation_reason_counts,
                "first_request_at": self._first_request_at,
                "latest_request_at": self._latest_request_at,
                "first_observation_at": self._first_observation_at,
                "latest_observation_at": self._latest_observation_at,
                "requests": self._requests,
                "observations": self._observations,
            })
        except Exception:
            return {"attempt": 0, "status": "unreported", "requests": [], "observations": []}