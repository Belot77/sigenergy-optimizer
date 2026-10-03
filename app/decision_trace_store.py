"""Passive rolling decision diagnostics; never participates in optimizer control."""
from __future__ import annotations

import asyncio
import copy
import json
import logging
import math
import os
import secrets
import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, BinaryIO, Iterator

logger = logging.getLogger(__name__)
FLUSH_INTERVAL = 900
RETENTION = timedelta(hours=24)
CHUNK_BYTES = 64 * 1024
MAX_RECORD_BYTES = 1024 * 1024
TICKET_SECONDS = 60
MAX_TICKETS = 32
MAX_DOWNLOADS = 4
# Two minutes includes opening, reading and client backpressure. Local diagnostic
# downloads must not hold retention pins indefinitely; oversized views fail closed.
DOWNLOAD_SECONDS = 120
MAX_DOWNLOAD_BYTES = 256 * 1024 * 1024
MAX_DOWNLOAD_SEGMENTS = 25  # 24 hours can straddle 25 hourly segments.
DIAGNOSTIC_WORKERS = 3
MAX_PENDING_WORK = 16
CLOCK_JUMP_SECONDS = 300
STATUS_FILE = "archive-status.json"
GAP_REASONS = frozenset({"recorded_gap", "session_discontinuity", "missing_archive_status",
                         "unreadable_archive_status", "orphan_compaction", "clock_discontinuity",
                         "deque_overflow", "discarded_record"})


def _timestamp(row: dict[str, Any]) -> datetime:
    value = datetime.fromisoformat(row["ts"].replace("Z", "+00:00"))
    if value.tzinfo is None:
        raise ValueError("Trace timestamp must include timezone")
    return value.astimezone(timezone.utc)


def _identity(row: dict[str, Any]) -> tuple[str, int]:
    meta = row["_trace"]
    session, sequence = meta["session"], meta["sequence"]
    uuid.UUID(session)
    if type(sequence) is not int or sequence < 1:
        raise ValueError("Invalid trace sequence")
    return session, sequence


def _finite(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: _finite(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_finite(item) for item in value]
    return value


def _copy_row(row: dict[str, Any]) -> dict[str, Any]:
    # Current summary/state/gates/values contain scalar values. Copy those
    # dictionaries directly; deep-copy only nested extensions if present.
    copied = row.copy()
    for key, value in row.items():
        if isinstance(value, dict):
            field = value.copy()
            for name, item in value.items():
                if isinstance(item, (dict, list, tuple)):
                    field[name] = copy.deepcopy(item)
            copied[key] = field
        elif isinstance(value, (list, tuple)):
            copied[key] = copy.deepcopy(value)
    return copied


def _reject_constant(value: str) -> None:
    raise ValueError(f"Non-JSON numeric constant: {value}")


def _records(handle: BinaryIO, limit: int, discarded=None, check=None) -> Iterator[tuple[dict[str, Any], bytes]]:
    """Read complete, valid records with bounded memory, including corrupt files."""
    while handle.tell() < limit:
        if check:
            check()
        remaining = limit - handle.tell()
        line = handle.readline(min(MAX_RECORD_BYTES + 1, remaining))
        if not line:
            break
        if len(line) > MAX_RECORD_BYTES:
            while not line.endswith(b"\n") and handle.tell() < limit:
                if check:
                    check()
                line = handle.readline(min(CHUNK_BYTES, limit - handle.tell()))
            logger.warning("Decision trace: skipped oversized record")
            if discarded:
                discarded()
            continue
        if not line.endswith(b"\n"):
            logger.warning("Decision trace: discarded incomplete trailing record")
            if discarded:
                discarded()
            break
        try:
            row = json.loads(line, parse_constant=_reject_constant)
            _timestamp(row)
            _identity(row)
        except Exception:
            logger.warning("Decision trace: skipped malformed record")
            if discarded:
                discarded()
            continue
        yield row, line


class TraceDownload:
    """Pinned file handles and committed byte ranges, independent of later appends."""

    def __init__(self, store: DecisionTraceStore, files: list[tuple[Path, BinaryIO, int]],
                 cutoff: datetime, possible_gaps: bool, deadline: float) -> None:
        self.store = store
        self.files = files
        self.cutoff = cutoff
        self.possible_gaps = possible_gaps
        self.deadline = deadline
        self._closed = False
        self._close_complete = threading.Event()
        self._cancelled = threading.Event()
        self._read_lock = threading.Lock()

    def _check_deadline(self) -> None:
        if self._cancelled.is_set() or time.monotonic() >= self.deadline:
            raise TimeoutError("Decision trace download exceeded its two-minute lifetime")

    async def async_chunks(self):
        # An async iterator avoids StreamingResponse's shared thread pool.
        records = self.chunks()
        while True:
            self._check_deadline()
            chunk = await self.store.run_worker(next, records, None)
            if chunk is None:
                return
            yield chunk

    async def async_close(self) -> None:
        # Interrupt bounded reads cooperatively before enqueueing handle cleanup.
        self._cancelled.set()
        if self._close_complete.is_set():
            return
        try:
            await self.store.run_worker(self.close)
        except RuntimeError:
            # A completed last close may already have shut down the pool.
            if not self._close_complete.is_set():
                raise

    def chunks(self) -> Iterator[bytes]:
        try:
            for _, handle, limit in self.files:
                # Closing on disconnect can race an executor read. Each next()
                # holds only this download's lock, never the archive writer lock.
                records = _records(handle, limit, lambda: self.store._note_gap("discarded_record"),
                                   self._check_deadline)
                while True:
                    with self._read_lock:
                        if self._closed:
                            return
                        self._check_deadline()
                        record = next(records, None)
                    if record is None:
                        break
                    row, line = record
                    if _timestamp(row) >= self.cutoff:
                        for offset in range(0, len(line), CHUNK_BYTES):
                            self._check_deadline()
                            yield line[offset:offset + CHUNK_BYTES]
        except Exception:
            logger.exception("Decision trace download failed")
            raise
        finally:
            self.close()

    def close(self) -> None:
        self._cancelled.set()
        with self._read_lock:
            if self._closed:
                return
            self._closed = True
            for _, handle, _ in self.files:
                try:
                    handle.close()
                except Exception:
                    logger.exception("Decision trace download handle cleanup failed")
            # Keep duplicate closers waiting until pins/admission, as well as
            # handles, have been released by the first closer.
            with self.store._lock:
                for path, _, _ in self.files:
                    self.store._pins[path] -= 1
                    if not self.store._pins[path]:
                        del self.store._pins[path]
                try:
                    self.store._save_status()
                except Exception:
                    logger.exception("Decision trace download gap status could not be saved")
            self.store.release_download()
            self._close_complete.set()


class DecisionTraceStore:
    def __init__(self, directory: Path | str | None = None) -> None:
        db_path = Path(os.environ.get("STATE_DB_PATH", "/data/optimizer_state.db")).expanduser()
        self.directory = Path(directory) if directory is not None else db_path.parent / "decision_trace"
        self.session = str(uuid.uuid4())
        self._sequence = 0
        # Event-loop-owned observer: strong references prevent object-id reuse.
        self._observed: dict[int, tuple[dict[str, Any], int]] = {}
        self._anchor: dict[str, Any] | None = None
        self._gap_count = 0
        self._tickets: dict[str, float] = {}
        # Worker-owned archive state, shared only under the store lock.
        self._lock = threading.Lock()
        self._pins: dict[Path, int] = {}
        self._lengths: dict[Path, int] = {}
        self._ids: dict[Path, set[tuple[str, int]]] = {}
        self._committed: set[tuple[str, int]] = set()
        self._confirmed_sequences: frozenset[int] = frozenset()
        self._recovery_needed = True
        self._ready = False
        self._historical_gaps = False
        self._stopping = threading.Event()
        self._closed = threading.Event()
        self._owner_handle: BinaryIO | None = None
        self._work_slots = threading.BoundedSemaphore(MAX_PENDING_WORK)
        self._admission_lock = threading.Lock()
        self._active_downloads = 0
        self._stop_scheduled = False
        self._status_lock = threading.Lock()
        self._gap_reasons: set[str] = set()
        self._status_version = 0
        self._saved_status_version = -1
        self._status_loaded = False
        self._wall_reference: datetime | None = None
        self._monotonic_reference = 0.0
        self._clock_uncertain = False
        self._boot_id: str | None = None
        self._executor = ThreadPoolExecutor(max_workers=DIAGNOSTIC_WORKERS,
                                            thread_name_prefix="decision-trace")

    def submit_work(self, function, *args) -> Future:
        """Admission bounds the executor queue as well as its worker count."""
        if not self._work_slots.acquire(blocking=False):
            raise OSError("Decision trace workers are busy")
        try:
            future = self._executor.submit(function, *args)
        except Exception:
            self._work_slots.release()
            raise
        future.add_done_callback(self._work_done)
        return future

    def _work_done(self, future: Future) -> None:
        self._work_slots.release()
        if self._stopping.is_set():
            self._schedule_stop()

    async def run_worker(self, function, *args):
        # Cancellation of an await never cancels ownership of running work.
        future = asyncio.wrap_future(self.submit_work(function, *args))
        return await asyncio.shield(future)

    def reserve_download(self) -> float:
        with self._admission_lock:
            if self._stopping.is_set():
                raise OSError("Decision trace storage is stopping")
            if self._active_downloads >= MAX_DOWNLOADS:
                raise ValueError("Too many active trace downloads")
            self._active_downloads += 1
            return time.monotonic() + DOWNLOAD_SECONDS

    def release_download(self) -> None:
        with self._admission_lock:
            self._active_downloads -= 1
        if self._stopping.is_set():
            self._schedule_stop()

    @property
    def possible_gap(self) -> bool:
        with self._status_lock:
            return bool(self._gap_reasons)

    def _note_gap(self, reason: str) -> None:
        with self._status_lock:
            if reason not in self._gap_reasons:
                self._gap_reasons.add(reason)
                self._status_version += 1

    def _claim_archive(self) -> bool:
        if self._owner_handle is not None:
            return True
        self.directory.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(self.directory / ".archive.lock", os.O_CREAT | os.O_RDWR, 0o600)
        handle = os.fdopen(descriptor, "r+b")
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            return False
        self._owner_handle = handle
        return True

    def _load_status(self) -> None:
        if self._status_loaded:
            return
        path = self.directory / STATUS_FILE
        self._boot_id = self._boot_identity()
        has_archive = any(self.directory.glob("????????T??.jsonl"))
        try:
            with path.open("rb") as handle:
                status = json.loads(handle.read(4097))
            if not isinstance(status, dict) or type(status.get("possible_gap")) is not bool:
                raise ValueError("Invalid trace archive status")
            reasons = status.get("reasons", [])
            if not isinstance(reasons, list) or len(reasons) > len(GAP_REASONS) or any(
                not isinstance(reason, str) or reason not in GAP_REASONS for reason in reasons
            ) or status["possible_gap"] != bool(reasons):
                raise ValueError("Invalid trace archive gap reasons")
            if status["possible_gap"]:
                for reason in reasons or ["recorded_gap"]:
                    self._note_gap(reason)
            if status.get("last_session") != self.session:
                self._note_gap("session_discontinuity")
            clock = status.get("clock")
            if clock is None:
                # Legacy status cannot clear a previously recorded clock gap.
                self._clock_uncertain = has_archive or "clock_discontinuity" in reasons
            else:
                if not isinstance(clock, dict) or type(clock.get("uncertain")) is not bool:
                    raise ValueError("Invalid trace clock status")
                self._clock_uncertain = clock["uncertain"]
                anchor = clock.get("anchor")
                if anchor is not None:
                    self._wall_reference = _timestamp({"ts": anchor})
                    previous_monotonic = clock["monotonic"]
                    if (type(previous_monotonic) not in (float, int)
                            or not math.isfinite(previous_monotonic) or previous_monotonic < 0):
                        raise ValueError("Invalid trace clock anchor")
                    monotonic = self._clock_now()
                    if (self._boot_id is not None and clock.get("boot_id") == self._boot_id
                            and monotonic >= previous_monotonic):
                        # OS monotonic time survives application/container restarts
                        # on the same boot, including time spent stopped.
                        self._monotonic_reference = previous_monotonic
                    else:
                        # Reboot/unknown boot: downtime cannot be proved. Keep the
                        # persisted UTC anchor, never adopt the startup wall clock.
                        self._monotonic_reference = monotonic
                        self._clock_uncertain = True
                elif has_archive or self._clock_uncertain:
                    self._clock_uncertain = True
        except FileNotFoundError:
            if has_archive:
                self._note_gap("missing_archive_status")
                self._clock_uncertain = True
        except Exception:
            self._note_gap("unreadable_archive_status")
            self._clock_uncertain = True
            self._wall_reference = None
        if self._clock_uncertain:
            self._note_gap("clock_discontinuity")
        self._status_loaded = True

    def _save_status(self) -> None:
        with self._status_lock:
            version = self._status_version
            if version == self._saved_status_version:
                return
            status = {"possible_gap": bool(self._gap_reasons),
                      "reasons": sorted(self._gap_reasons), "last_session": self.session,
                      "clock": {"uncertain": self._clock_uncertain,
                                "anchor": self._wall_reference.isoformat() if self._wall_reference else None,
                                "monotonic": self._monotonic_reference, "boot_id": self._boot_id}}
        path = self.directory / STATUS_FILE
        temporary = path.with_suffix(".json.tmp")
        try:
            with temporary.open("w", encoding="utf-8") as handle:
                json.dump(status, handle, separators=(",", ":"))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            self._sync_directory(self.directory)
        finally:
            temporary.unlink(missing_ok=True)
        self._saved_status_version = version

    def _clean_orphan_temps(self) -> None:
        for path in self.directory.glob("*.tmp"):
            if path.name != STATUS_FILE + ".tmp":
                try:
                    hour = datetime.strptime(path.stem, "%Y%m%dT%H")
                    if path.name != hour.strftime("%Y%m%dT%H.tmp"):
                        continue
                except ValueError:
                    continue
            if path.is_symlink() or not path.is_file():
                continue
            self._note_gap("orphan_compaction")
            self._save_status()
            path.unlink(missing_ok=True)

    @staticmethod
    def _clock_now() -> float:
        return time.monotonic()

    @staticmethod
    def _boot_identity() -> str | None:
        # Worker only. Linux's boot UUID validates cross-process monotonic anchors;
        # other platforms/read failures conservatively cannot infer downtime.
        try:
            with Path("/proc/sys/kernel/random/boot_id").open(encoding="ascii") as handle:
                return str(uuid.UUID(handle.read(128).strip()))
        except (OSError, ValueError):
            return None

    def _checked_time(self, now: datetime) -> tuple[datetime, bool]:
        monotonic = self._clock_now()
        if self._wall_reference is None:
            if self._clock_uncertain:
                # Missing/corrupt clock evidence cannot authorize pruning/writes.
                return now, False
            expected = now
        else:
            expected = self._wall_reference + timedelta(seconds=monotonic - self._monotonic_reference)
        sane = (monotonic >= self._monotonic_reference
                and abs((now - expected).total_seconds()) <= CLOCK_JUMP_SECONDS)
        if sane:
            self._wall_reference, self._monotonic_reference = now, monotonic
            self._clock_uncertain = False
            with self._status_lock:
                self._status_version += 1
            return now, True
        if not self._clock_uncertain:
            self._clock_uncertain = True
            with self._status_lock:
                self._status_version += 1
        self._note_gap("clock_discontinuity")
        return expected, False

    @property
    def ready(self) -> bool:
        return self._ready and not self._stopping.is_set()

    def capture(self, optimizer: Any) -> list[dict[str, Any]]:
        """Event-loop only: snapshot/copy, with no serialization or filesystem IO."""
        if self._clock_uncertain:
            # Leave the live deque alone. No new observer identities or snapshots
            # accumulate while persistence is intentionally suspended.
            return []
        newest_first = optimizer.decision_trace(limit=1000)
        available = {id(row) for row in newest_first}
        lost_uncommitted = any(key not in available and sequence not in self._confirmed_sequences
                               for key, (_, sequence) in self._observed.items())
        if lost_uncommitted:
            self._gap_count += 1
            self._note_gap("deque_overflow")
            logger.warning("Decision trace: unpersisted cycles left the deque; archive may be incomplete")
        elif self._anchor is not None and newest_first and not any(
            row is self._anchor for row in newest_first
        ):
            self._gap_count += 1
            self._note_gap("deque_overflow")
            logger.warning("Decision trace: missing deque overlap; cycles may have been lost before persistence")
        elif self._anchor is None and len(newest_first) == 1000:
            self._gap_count += 1
            self._note_gap("deque_overflow")
            logger.warning("Decision trace: first snapshot fills deque; earlier cycles may be missing")
        observed: dict[int, tuple[dict[str, Any], int]] = {}
        copies = []
        for row in reversed(newest_first):
            previous = self._observed.get(id(row))
            if previous is not None and previous[0] is row:
                sequence = previous[1]
            else:
                self._sequence += 1
                sequence = self._sequence
            observed[id(row)] = (row, sequence)
            if sequence in self._confirmed_sequences:
                continue
            copied = _copy_row(row)
            copied["_trace"] = {"session": self.session, "sequence": sequence,
                                "possible_gap": self.possible_gap}
            copies.append(copied)
        self._observed = observed
        if newest_first:
            self._anchor = newest_first[0]
        return copies

    def stop(self) -> None:
        # No worker lock or final flush on the event-loop/shutdown path.
        self._stopping.set()
        self._tickets.clear()
        self._schedule_stop()

    def _schedule_stop(self) -> None:
        with self._admission_lock:
            if self._closed.is_set() or self._stop_scheduled or self._active_downloads:
                return
            self._stop_scheduled = True
        try:
            self.submit_work(self._finish_stop)
        except Exception:
            with self._admission_lock:
                self._stop_scheduled = False
            logger.exception("Decision trace worker cleanup could not be scheduled")

    def _finish_stop(self) -> None:
        # The OS lease outlives cancelled coroutines and all pinned downloads.
        with self._lock:
            if self._owner_handle is not None:
                self._owner_handle.close()
                self._owner_handle = None
            self._closed.set()
        self._executor.shutdown(wait=False)

    def issue_ticket(self) -> str:
        now = time.monotonic()
        self._tickets = {key: expiry for key, expiry in self._tickets.items() if expiry > now}
        if len(self._tickets) >= MAX_TICKETS:
            raise ValueError("Too many outstanding trace download tickets")
        ticket = secrets.token_urlsafe(32)
        self._tickets[ticket] = now + TICKET_SECONDS
        return ticket

    def consume_ticket(self, ticket: str) -> bool:
        expiry = self._tickets.pop(ticket, None)
        return expiry is not None and expiry > time.monotonic()

    def _path(self, timestamp: datetime) -> Path:
        return self.directory / (timestamp.strftime("%Y%m%dT%H") + ".jsonl")

    @staticmethod
    def _sync_directory(directory: Path) -> None:
        if os.name != "nt":
            descriptor = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)

    def _replace(self, path: Path, cutoff: datetime | None,
                 excluded: set[tuple[str, int]]) -> set[tuple[str, int]]:
        if self._pins.get(path):
            raise OSError("Trace segment is pinned by an active download")
        temporary = path.with_suffix(".tmp")
        identities: set[tuple[str, int]] = set()
        try:
            with path.open("rb") as source, temporary.open("wb") as target:
                for row, line in _records(source, path.stat().st_size,
                                          lambda: self._note_gap("discarded_record")):
                    identity = _identity(row)
                    timestamp = _timestamp(row)
                    if (identity not in excluded and identity not in identities
                            and self._path(timestamp) == path
                            and (cutoff is None or timestamp >= cutoff)):
                        target.write(line)
                        identities.add(identity)
                target.flush()
                os.fsync(target.fileno())
            # Persist any newly detected corruption before removing its evidence.
            self._save_status()
            os.replace(temporary, path)
            self._sync_directory(self.directory)
        finally:
            temporary.unlink(missing_ok=True)
        return identities

    def _recover(self) -> None:
        self._load_status()
        self._clean_orphan_temps()
        lengths: dict[Path, int] = {}
        identities: dict[Path, set[tuple[str, int]]] = {}
        committed: set[tuple[str, int]] = set()
        historical_gaps = False
        for path in sorted(self.directory.glob("????????T??.jsonl")):
            try:
                datetime.strptime(path.stem, "%Y%m%dT%H")
            except ValueError:
                logger.warning("Decision trace: ignored unrecognized segment filename")
                continue
            ids: set[tuple[str, int]] = set()
            valid_bytes = 0
            with path.open("rb") as handle:
                size = path.stat().st_size
                for row, line in _records(handle, size, lambda: self._note_gap("discarded_record")):
                    identity = _identity(row)
                    if identity in committed or identity in ids or self._path(_timestamp(row)) != path:
                        logger.warning("Decision trace: skipped duplicate/misplaced recovered record")
                        continue
                    ids.add(identity)
                    valid_bytes += len(line)
                    historical_gaps |= bool(row["_trace"].get("possible_gap"))
            if valid_bytes != size:
                self._note_gap("discarded_record")
                self._save_status()
                ids = self._replace(path, None, committed)
            # A complete line from an uncertain previous append is acknowledged
            # only after a successful fsync, never merely because it parses.
            with path.open("ab") as handle:
                handle.flush()
                os.fsync(handle.fileno())
            lengths[path] = path.stat().st_size
            identities[path] = ids
            committed.update(ids)
        self._sync_directory(self.directory)
        self._lengths, self._ids, self._committed = lengths, identities, committed
        self._confirm_sequences()
        self._historical_gaps = historical_gaps
        if historical_gaps:
            self._note_gap("recorded_gap")
        self._save_status()
        self._recovery_needed = False
        self._ready = True

    def _append(self, path: Path, records: list[tuple[tuple[str, int], bytes]]) -> None:
        with path.open("ab") as handle:
            for _, line in records:
                handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())
        self._sync_directory(self.directory)
        ids = {identity for identity, _ in records}
        self._lengths[path] = path.stat().st_size
        self._ids.setdefault(path, set()).update(ids)
        self._committed.update(ids)
        self._confirm_sequences()

    def _confirm_sequences(self) -> None:
        # Immutable publication lets capture detect evicted uncommitted rows
        # without ever taking the filesystem worker's lock on the event loop.
        self._confirmed_sequences = frozenset(sequence for session, sequence in self._committed
                                              if session == self.session)

    def _prune(self, cutoff: datetime) -> None:
        for path in list(self._lengths):
            if self._stopping.is_set():
                return
            # Windows cannot replace/delete open files. Pinning also makes the
            # stable download view portable; defer only those segments.
            if self._pins.get(path):
                continue
            hour = datetime.strptime(path.stem, "%Y%m%dT%H").replace(tzinfo=timezone.utc)
            if hour >= cutoff:
                continue
            try:
                old_ids = self._ids[path]
                if hour + timedelta(hours=1) <= cutoff:
                    path.unlink()
                    self._sync_directory(self.directory)
                    del self._lengths[path]
                    del self._ids[path]
                    self._committed.difference_update(old_ids)
                else:
                    new_ids = self._replace(path, cutoff, set())
                    self._ids[path] = new_ids
                    self._lengths[path] = path.stat().st_size
                    self._committed.difference_update(old_ids - new_ids)
            except Exception:
                self._recovery_needed = True
                logger.exception("Decision trace pruning failed; retrying on next pass")

    def flush(self, rows: list[dict[str, Any]], now: datetime | None = None) -> bool:
        """Worker only. Failures stay in diagnostics and never escape to control."""
        now = now or datetime.now(timezone.utc)
        try:
            with self._lock:
                if self._stopping.is_set():
                    return False
                if not self._claim_archive():
                    return False
                if self._recovery_needed:
                    self._recover()
                safe_now, sane = self._checked_time(now)
                self._save_status()
                if not sane:
                    # Preserve the archive and all existing indexes, but do not
                    # append or acknowledge cycles under an unresolved clock.
                    return True
                cutoff = safe_now - RETENTION
                batches: dict[Path, list[tuple[tuple[str, int], bytes]]] = {}
                pending: set[tuple[str, int]] = set()
                for row in rows:
                    try:
                        identity = _identity(row)
                        timestamp = _timestamp(row)
                        if timestamp > safe_now + timedelta(seconds=CLOCK_JUMP_SECONDS):
                            # Bad-clock rows may remain in the unchanged live
                            # deque after correction; do not create future files.
                            self._note_gap("discarded_record")
                            continue
                        if identity in self._committed or identity in pending or timestamp < cutoff:
                            continue
                        line = (json.dumps(_finite(row), separators=(",", ":"), allow_nan=False)
                                + "\n").encode("utf-8")
                        if len(line) > MAX_RECORD_BYTES:
                            raise ValueError("Trace record exceeds diagnostic size limit")
                        batches.setdefault(self._path(timestamp), []).append((identity, line))
                        pending.add(identity)
                    except Exception:
                        logger.exception("Decision trace serialization failed; row will be retried while available")
                for path, records in batches.items():
                    if self._stopping.is_set():
                        return False
                    self._append(path, records)
                if sane:
                    self._prune(cutoff)
                self._save_status()
                self._confirm_sequences()
                return True
        except Exception:
            self._recovery_needed = True
            logger.exception("Decision trace recovery/write failed; retrying on next pass")
            return False

    def open_download(self, now: datetime | None = None, reserved: bool = False,
                      deadline: float | None = None) -> TraceDownload:
        """Worker only; pin handles/ranges under lock, release before streaming."""
        files: list[tuple[Path, BinaryIO, int]] = []
        if not reserved:
            deadline = self.reserve_download()
        if deadline is None:
            deadline = time.monotonic() + DOWNLOAD_SECONDS
        try:
            with self._lock:
                if not self.ready:
                    raise OSError("Decision trace storage is not available")
                if time.monotonic() >= deadline:
                    raise TimeoutError("Decision trace download opening timed out")
                safe_now, _ = self._checked_time(now or datetime.now(timezone.utc))
                self._save_status()
                if self._clock_uncertain and self._wall_reference is None:
                    raise OSError("Decision trace clock anchor is unavailable")
                cutoff = safe_now - RETENTION
                eligible = []
                for path, length in sorted(self._lengths.items()):
                    hour = datetime.strptime(path.stem, "%Y%m%dT%H").replace(tzinfo=timezone.utc)
                    # Never transfer pins on wholly expired/future segments to a
                    # new view. Old downloads lose their own pins at the deadline.
                    if hour + timedelta(hours=1) <= cutoff or hour > safe_now:
                        continue
                    eligible.append((path, length))
                if (len(eligible) > MAX_DOWNLOAD_SEGMENTS
                        or sum(length for _, length in eligible) > MAX_DOWNLOAD_BYTES):
                    raise OSError("Decision trace download exceeds diagnostic resource limits")
                for path, length in eligible:
                    if time.monotonic() >= deadline:
                        raise TimeoutError("Decision trace download opening timed out")
                    files.append((path, path.open("rb"), length))
                if time.monotonic() >= deadline:
                    raise TimeoutError("Decision trace download opening timed out")
                for path, _, _ in files:
                    self._pins[path] = self._pins.get(path, 0) + 1
                return TraceDownload(self, files, cutoff, self.possible_gap, deadline)
        except Exception:
            for _, handle, _ in files:
                handle.close()
            if not reserved:
                self.release_download()
            raise

    async def run_forever(self, optimizer: Any) -> None:
        try:
            # Recover independently; no disk operation delays application startup.
            try:
                await self.run_worker(self.flush, [])
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Decision trace initialization failed; retrying on next interval")
            while not self._stopping.is_set():
                await asyncio.sleep(FLUSH_INTERVAL)
                try:
                    rows = self.capture(optimizer)
                    await self.run_worker(self.flush, rows)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("Decision trace pass failed; retrying on next interval")
        finally:
            self.stop()
