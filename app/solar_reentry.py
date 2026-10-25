"""Process-local fresh-report qualification; callers retain policy ownership."""

from __future__ import annotations

import math
from dataclasses import dataclass, field


SOLAR_REENTRY_QUALIFICATION_SECONDS = 30.0
SOLAR_REENTRY_MAX_REPORT_GAP_SECONDS = 60.0


def _finite(value: object) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


@dataclass
class SolarReentryGuard:
    """Withhold reacquisition only after the caller arms its required latch.

    Both source streams must span the qualification interval independently.
    Cached reports can retain fresh qualified proof, but cannot mature it.
    A caller must commit a qualified generation only after its own complete
    automatic application; this helper never grants a control-policy owner.
    """

    required: bool = False
    generation: int = 0
    phase: str = "idle"
    reason: str = "initial_admission_unchanged"
    reports: tuple[float, float] | None = None
    context: tuple | None = None
    _first_reports: tuple[float, float] | None = field(default=None, repr=False)
    _started_monotonic: float | None = field(default=None, repr=False)
    _last_advance_monotonic: tuple[float, float] | None = field(default=None, repr=False)
    _last_clock: tuple[float, float] | None = field(default=None, repr=False)
    _identity_context: tuple | None = field(default=None, repr=False)
    _report_high_water: tuple[float, float] | None = field(default=None, repr=False)

    def reset(self, reason: str) -> None:
        """Retire proof while preserving any unfulfilled reacquisition latch."""
        self.generation += 1
        self.phase = "closed" if self.required else "idle"
        self.reason = reason
        self.reports = None
        self.context = None
        self._first_reports = None
        self._started_monotonic = None
        self._last_advance_monotonic = None

    def arm(self, cause: str) -> None:
        self.required = True
        self.reset(cause)

    @staticmethod
    def _reports_fresh(reports: object, now_ts: float) -> bool:
        return bool(
            isinstance(reports, tuple)
            and len(reports) == 2
            and all(
                _finite(stamp)
                and 0.0 <= now_ts - stamp <= SOLAR_REENTRY_MAX_REPORT_GAP_SECONDS
                for stamp in reports
            )
        )

    def _start(
        self, reports: tuple[float, float], now_mono: float, context: tuple,
    ) -> None:
        self.phase = "qualifying"
        self.reason = "qualifying_fresh_reports"
        self.reports = self._first_reports = reports
        self.context = context
        self._started_monotonic = now_mono
        self._last_advance_monotonic = (now_mono, now_mono)
        self._report_high_water = reports

    def evaluate(
        self, *, candidate: bool, reports: tuple[float, float] | None,
        now_ts: float, now_mono: float, context: tuple,
    ) -> bool:
        if not self.required:
            return True
        if not _finite(now_ts) or not _finite(now_mono):
            self.reset("clock_invalid")
            return False
        previous_clock = self._last_clock
        self._last_clock = (now_ts, now_mono)
        if previous_clock is not None and (
            now_ts < previous_clock[0] or now_mono < previous_clock[1]
        ):
            self.reset("clock_regressed")
            # A clock correction establishes a new timestamp epoch. Reject this
            # tick; a later credible observation must start a complete interval.
            self._report_high_water = None
            return False
        if context != self._identity_context:
            self.reset("context_changed")
            self._identity_context = context
            self._report_high_water = None
        if not candidate:
            self.reset("candidate_failed")
            return False
        if not self._reports_fresh(reports, now_ts):
            self.reset("reports_missing_invalid_future_or_stale")
            return False
        assert reports is not None
        if self._report_high_water is not None and any(
            new < old for new, old in zip(reports, self._report_high_water)
        ):
            self.reset("report_regressed")
            return False
        if self.reports is None:
            self._start(reports, now_mono, context)
            return False
        assert self._last_advance_monotonic is not None
        if any(
            new - old > SOLAR_REENTRY_MAX_REPORT_GAP_SECONDS
            or now_mono - advanced_at > SOLAR_REENTRY_MAX_REPORT_GAP_SECONDS
            for new, old, advanced_at in zip(
                reports, self.reports, self._last_advance_monotonic,
            )
        ):
            self.reset("advancing_report_gap")
            self._start(reports, now_mono, context)
            return False
        advances = tuple(new > old for new, old in zip(reports, self.reports))
        self._last_advance_monotonic = tuple(
            now_mono if advanced else old
            for advanced, old in zip(advances, self._last_advance_monotonic)
        )
        self.reports = self._report_high_water = reports
        if self.phase == "qualified":
            return True
        assert self._first_reports is not None
        assert self._started_monotonic is not None
        if (
            any(advances)
            and now_mono - self._started_monotonic >= SOLAR_REENTRY_QUALIFICATION_SECONDS
            and all(
                latest - first >= SOLAR_REENTRY_QUALIFICATION_SECONDS
                for latest, first in zip(reports, self._first_reports)
            )
        ):
            self.phase = "qualified"
            self.reason = "fresh_report_interval_qualified"
            return True
        self.reason = "qualifying_fresh_reports" if any(advances) else "waiting_for_new_reports"
        return False

    def current(
        self, *, generation: int, reports: tuple[float, float] | None,
        now_ts: float, now_mono: float, context: tuple,
    ) -> bool:
        """Read-only dispatch check for a still-pending qualified generation."""
        return bool(
            self.required and self.phase == "qualified"
            and generation == self.generation and context == self.context
            and reports == self.reports
            and _finite(now_ts) and _finite(now_mono)
            and self._last_clock is not None
            and now_ts >= self._last_clock[0] and now_mono >= self._last_clock[1]
            and self._reports_fresh(reports, now_ts)
            and self._last_advance_monotonic is not None
            and all(
                0.0 <= now_mono - advanced_at <= SOLAR_REENTRY_MAX_REPORT_GAP_SECONDS
                for advanced_at in self._last_advance_monotonic
            )
        )

    def commit(self, generation: int) -> bool:
        if not self.required or self.phase != "qualified" or generation != self.generation:
            return False
        self.required = False
        self.phase = "idle"
        self.reason = "qualified_application_committed"
        self.reports = None
        self.context = None
        self._first_reports = None
        self._started_monotonic = None
        self._last_advance_monotonic = None
        return True

    def diagnostics(self, prefix: str) -> dict[str, object]:
        return {
            f"{prefix}_required": self.required,
            f"{prefix}_generation": self.generation,
            f"{prefix}_state": self.phase,
            f"{prefix}_reason": self.reason,
            f"{prefix}_first_pv_report_ts": self._first_reports[0] if self._first_reports else None,
            f"{prefix}_first_load_report_ts": self._first_reports[1] if self._first_reports else None,
            f"{prefix}_last_pv_report_ts": self.reports[0] if self.reports else None,
            f"{prefix}_last_load_report_ts": self.reports[1] if self.reports else None,
            f"{prefix}_qualifying_seconds": (
                self._last_clock[1] - self._started_monotonic
                if self._last_clock is not None and self._started_monotonic is not None
                else 0.0
            ),
        }
