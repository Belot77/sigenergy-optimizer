"""Versioned evidence for resuming a previously verified Solcast forecast."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass, fields
from datetime import date
from uuid import UUID


# Version 2 binds the native device ID and records the verified forecast's query bounds.
_SCHEMA_VERSION = 2
_MAX_RECEIPT_LENGTH = 2048
_CLOCK_SKEW_SECONDS = 5.0
_ENTITY_ID = re.compile(r"[a-z0-9_]+\.[a-z0-9_]+")
_SHA256_HEX = re.compile(r"[0-9a-f]{64}")


def _canonical_json(value: object) -> str:
    return json.dumps(value, allow_nan=False, sort_keys=True, separators=(",", ":"))


def evidence_digest(evidence: object) -> str:
    """Hash normalized, JSON-compatible evidence without persisting its contents."""
    return hashlib.sha256(_canonical_json(evidence).encode("utf-8")).hexdigest()


def _canonical_boot_id(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 36:
        return False
    try:
        parsed = UUID(value)
    except ValueError:
        return False
    return bool(parsed.int) and str(parsed) == value


def _finite_number(value: object) -> bool:
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _unique_fields(pairs: list[tuple[str, object]]) -> dict[str, object]:
    data = dict(pairs)
    if len(data) != len(pairs):
        raise ValueError("Duplicate handoff receipt field")
    return data


@dataclass(frozen=True)
class SolarProviderHandoff:
    boot_id: str
    source: tuple[str, str]
    day: str
    poll: float
    deadline: float
    forecast_start: float
    forecast_end: float
    forecast_digest: str
    witness_digest: str
    saved_wall: float
    saved_monotonic: float

    def __post_init__(self) -> None:
        if not _canonical_boot_id(self.boot_id):
            raise ValueError("Invalid handoff boot ID")
        if (
            not isinstance(self.source, tuple)
            or len(self.source) != 2
            or any(
                not isinstance(entity_id, str)
                or len(entity_id) > 255
                or _ENTITY_ID.fullmatch(entity_id) is None
                for entity_id in self.source
            )
            or self.source[0] == self.source[1]
        ):
            raise ValueError("Invalid handoff provider source")
        if not isinstance(self.day, str) or date.fromisoformat(self.day).isoformat() != self.day:
            raise ValueError("Invalid handoff local date")
        if any(
            not isinstance(digest, str) or _SHA256_HEX.fullmatch(digest) is None
            for digest in (self.forecast_digest, self.witness_digest)
        ):
            raise ValueError("Invalid handoff evidence digest")
        if not all(
            _finite_number(value)
            for value in (self.poll, self.deadline, self.saved_wall, self.saved_monotonic,
                          self.forecast_start, self.forecast_end)
        ) or not (0 < self.poll <= self.saved_wall < self.deadline and self.saved_monotonic >= 0):
            raise ValueError("Invalid handoff clock")
        if (
            not 0 < self.forecast_start <= self.saved_wall < self.forecast_end
            or (self.forecast_end - self.forecast_start) % 1800
        ):
            raise ValueError("Invalid handoff forecast range")

    @classmethod
    def from_json(cls, raw: str | None) -> SolarProviderHandoff | None:
        if not isinstance(raw, str) or not 0 < len(raw) <= _MAX_RECEIPT_LENGTH:
            return None
        try:
            data = json.loads(raw, object_pairs_hook=_unique_fields)
            expected_fields = {"schema_version", *(field.name for field in fields(cls))}
            if not isinstance(data, dict) or set(data) != expected_fields:
                return None
            version = data.pop("schema_version")
            if type(version) is not int or version != _SCHEMA_VERSION or not isinstance(data["source"], list):
                return None
            data["source"] = tuple(data["source"])
            return cls(**data)
        except (ValueError, RecursionError):
            return None

    def to_json(self) -> str:
        raw = _canonical_json({"schema_version": _SCHEMA_VERSION, **asdict(self)})
        if len(raw) > _MAX_RECEIPT_LENGTH:
            raise ValueError("Handoff receipt is too large")
        return raw

    def clock_is_current(self, boot_id: str | None, now_wall: float, now_monotonic: float) -> bool:
        """Require continuity of both clocks and enforce the original elapsed budget."""
        if (
            boot_id != self.boot_id
            or not _finite_number(now_wall)
            or not _finite_number(now_monotonic)
            or not self.saved_wall <= now_wall < self.deadline
        ):
            return False
        elapsed = now_monotonic - self.saved_monotonic
        return (
            0 <= elapsed < self.deadline - self.saved_wall
            and abs(now_wall - self.saved_wall - elapsed) <= _CLOCK_SKEW_SECONDS
        )
