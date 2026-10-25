from __future__ import annotations

import unittest
from copy import deepcopy

from app.solar_reentry import SolarReentryGuard


class SolarReentryQualificationTests(unittest.TestCase):
    CONTEXT = ("source-generation", "local-day", "owner-identity")

    def setUp(self) -> None:
        self.guard = SolarReentryGuard()
        self.guard.arm("budget_failed")

    def evaluate(self, seconds, *, reports=None, mono=None, **overrides):
        values = {
            "candidate": True,
            "reports": reports if reports is not None else (1000.0 + seconds,) * 2,
            "now_ts": 1000.0 + seconds,
            "now_mono": 500.0 + seconds if mono is None else mono,
            "context": self.CONTEXT,
        }
        values.update(overrides)
        return self.guard.evaluate(**values)

    def qualify(self):
        self.assertFalse(self.evaluate(0))
        self.assertTrue(self.evaluate(30))

    def current(self, *, seconds=30, **overrides):
        values = {
            "generation": self.guard.generation,
            "reports": self.guard.reports,
            "now_ts": 1000.0 + seconds,
            "now_mono": 500.0 + seconds,
            "context": self.CONTEXT,
        }
        values.update(overrides)
        return self.guard.current(**values)

    def test_unarmed_guard_preserves_initial_admission(self):
        guard = SolarReentryGuard()
        self.assertTrue(guard.evaluate(
            candidate=False, reports=None, now_ts=float("nan"),
            now_mono=float("nan"), context=self.CONTEXT,
        ))
        self.assertFalse(guard.required)
        self.assertEqual("idle", guard.phase)
        self.assertEqual(0, guard.generation)

    def test_exact_source_and_monotonic_minimum(self):
        self.assertFalse(self.evaluate(0))
        self.assertFalse(self.evaluate(29.999))
        self.assertTrue(self.evaluate(30))
        self.assertTrue(self.guard.required)
        self.assertEqual("qualified", self.guard.phase)

    def test_source_span_alone_does_not_replace_monotonic_elapsed(self):
        self.assertFalse(self.evaluate(0))
        self.assertFalse(self.evaluate(30, mono=529.999))
        self.assertFalse(self.evaluate(31, reports=(1030.0, 1030.0), mono=530.0))
        self.assertTrue(self.evaluate(31, mono=531.0))

    def test_cached_reports_cannot_mature_qualification(self):
        self.assertFalse(self.evaluate(0))
        for seconds in (10, 30, 60):
            self.assertFalse(self.evaluate(seconds, reports=(1000.0, 1000.0)))
        self.assertEqual("qualifying", self.guard.phase)
        self.assertFalse(self.evaluate(60.001, reports=(1000.0, 1000.0)))
        self.assertEqual("closed", self.guard.phase)

    def test_each_stream_must_span_thirty_seconds(self):
        for lagging_stream in (0, 1):
            with self.subTest(stream=lagging_stream):
                self.guard = SolarReentryGuard()
                self.guard.arm("budget_failed")
                self.assertFalse(self.evaluate(0))
                reports = [1030.0, 1030.0]
                reports[lagging_stream] = 1029.999
                self.assertFalse(self.evaluate(30, reports=tuple(reports)))
                self.assertTrue(self.evaluate(31, reports=(1030.0, 1030.0)))

    def test_independently_advancing_streams_can_complete_interval(self):
        self.assertFalse(self.evaluate(0))
        self.assertFalse(self.evaluate(30, reports=(1030.0, 1020.0)))
        self.assertTrue(self.evaluate(31, reports=(1030.0, 1031.0)))

    def test_exact_sixty_second_gap_and_age_are_allowed(self):
        self.assertFalse(self.evaluate(0))
        self.assertTrue(self.evaluate(60))
        self.assertTrue(self.evaluate(120, reports=(1060.0, 1060.0)))
        self.assertTrue(self.current(seconds=120))
        self.assertFalse(self.current(seconds=120.001))

    def test_source_gap_above_sixty_starts_new_full_interval(self):
        self.assertFalse(self.evaluate(0))
        generation = self.guard.generation
        self.assertFalse(self.evaluate(60.001))
        self.assertGreater(self.guard.generation, generation)
        self.assertEqual("qualifying", self.guard.phase)
        self.assertFalse(self.evaluate(90.0))
        self.assertTrue(self.evaluate(90.001))

    def test_one_stream_gap_cannot_be_hidden_by_other_stream_advances(self):
        for lagging_stream in (0, 1):
            with self.subTest(stream=lagging_stream):
                self.guard = SolarReentryGuard()
                self.guard.arm("budget_failed")
                self.assertFalse(self.evaluate(0))
                for seconds in (20, 40, 60):
                    reports = [1000.0 + seconds] * 2
                    reports[lagging_stream] = 1000.0
                    self.assertFalse(self.evaluate(seconds, reports=tuple(reports)))
                self.assertFalse(self.evaluate(61))
                self.assertEqual("qualifying", self.guard.phase)
                self.assertTrue(self.evaluate(91))

    def test_per_stream_local_advance_gap_also_resets(self):
        self.assertFalse(self.evaluate(0))
        # Source timestamps span only thirty seconds, but local receipt of a
        # new report was absent for over sixty seconds.
        self.assertFalse(self.evaluate(30, mono=560.001))
        self.assertEqual("qualifying", self.guard.phase)
        self.assertFalse(self.evaluate(59.999, mono=590.0))
        self.assertTrue(self.evaluate(60, mono=590.001))

    def test_candidate_failure_clears_qualified_proof_but_preserves_latch(self):
        self.qualify()
        old_generation = self.guard.generation
        self.assertFalse(self.evaluate(31, candidate=False))
        self.assertTrue(self.guard.required)
        self.assertEqual("closed", self.guard.phase)
        self.assertGreater(self.guard.generation, old_generation)
        self.assertFalse(self.guard.commit(old_generation))
        self.assertFalse(self.evaluate(32))
        self.assertFalse(self.evaluate(61))
        self.assertTrue(self.evaluate(62))

    def test_missing_malformed_future_nonfinite_and_stale_reports_fail_closed(self):
        bad_reports = (
            None, (), (1000.0,), (1000.0, 1000.0, 1000.0),
            [1000.0, 1000.0], (True, 1000.0), ("1000", 1000.0),
            (float("nan"), 1000.0), (1000.0, float("inf")),
            (10 ** 1000, 1000.0),
            (1000.001, 1000.0), (1000.0, 939.999),
        )
        for reports in bad_reports:
            with self.subTest(reports=reports):
                self.guard = SolarReentryGuard()
                self.guard.arm("budget_failed")
                self.assertFalse(self.guard.evaluate(
                    candidate=True, reports=reports, now_ts=1000.0,
                    now_mono=500.0, context=self.CONTEXT,
                ))
                self.assertTrue(self.guard.required)
                self.assertEqual("closed", self.guard.phase)

    def test_report_regression_rejects_replayed_timestamps_after_reset(self):
        self.qualify()
        self.assertFalse(self.evaluate(31, reports=(1029.0, 1031.0)))
        self.assertEqual("report_regressed", self.guard.reason)
        self.assertFalse(self.evaluate(32, reports=(1029.0, 1032.0)))
        self.assertEqual("closed", self.guard.phase)
        self.assertFalse(self.evaluate(33))
        self.assertTrue(self.evaluate(63))

    def test_wall_or_monotonic_regression_rejects_tick_without_reseeding(self):
        for clock in ("now_ts", "now_mono"):
            with self.subTest(clock=clock):
                self.guard = SolarReentryGuard()
                self.guard.arm("budget_failed")
                self.qualify()
                values = {clock: 1029.0 if clock == "now_ts" else 529.0}
                self.assertFalse(self.evaluate(31, **values))
                self.assertEqual("clock_regressed", self.guard.reason)
                self.assertIsNone(self.guard.reports)
                self.assertFalse(self.evaluate(32))
                self.assertFalse(self.evaluate(61))
                self.assertTrue(self.evaluate(62))

    def test_nonfinite_clocks_cannot_retain_qualified_proof(self):
        for clock in ("now_ts", "now_mono"):
            for value in (float("nan"), float("inf"), True):
                with self.subTest(clock=clock, value=value):
                    self.guard = SolarReentryGuard()
                    self.guard.arm("budget_failed")
                    self.qualify()
                    self.assertFalse(self.evaluate(31, **{clock: value}))
                    self.assertEqual("closed", self.guard.phase)

    def test_context_change_starts_full_interval_and_retires_old_high_water(self):
        self.qualify()
        old_generation = self.guard.generation
        context = ("new-source", "same-day", "new-owner-identity")
        self.assertFalse(self.evaluate(31, reports=(1020.0, 1020.0), context=context))
        self.assertGreater(self.guard.generation, old_generation)
        self.assertEqual((1020.0, 1020.0), self.guard.reports)
        self.assertFalse(self.evaluate(60, context=context))
        self.assertTrue(self.evaluate(61, context=context))

    def test_arm_and_reset_preserve_required_latch(self):
        self.qualify()
        generation = self.guard.generation
        self.guard.reset("authority_lost")
        self.assertTrue(self.guard.required)
        self.assertEqual("closed", self.guard.phase)
        self.assertGreater(self.guard.generation, generation)
        self.assertIsNone(self.guard.reports)
        self.assertFalse(self.guard.commit(generation))
        generation = self.guard.generation
        self.guard.arm("new_budget_exit")
        self.assertTrue(self.guard.required)
        self.assertGreater(self.guard.generation, generation)

    def test_commit_requires_matching_qualified_generation(self):
        self.assertFalse(self.guard.commit(self.guard.generation))
        self.qualify()
        generation = self.guard.generation
        self.assertFalse(self.guard.commit(generation - 1))
        self.assertTrue(self.guard.required)
        self.assertTrue(self.guard.commit(generation))
        self.assertFalse(self.guard.required)
        self.assertEqual(generation, self.guard.generation)
        self.assertEqual("idle", self.guard.phase)
        self.assertFalse(self.guard.commit(generation))

    def test_dispatch_check_is_readonly_and_rejects_wrong_generation_or_context(self):
        self.qualify()
        snapshot = deepcopy(self.guard)
        self.assertTrue(self.current())
        self.assertFalse(self.current(generation=self.guard.generation - 1))
        self.assertFalse(self.current(context=("different",)))
        self.assertFalse(self.current(reports=(1031.0, 1031.0)))
        self.assertFalse(self.current(now_ts=1029.0))
        self.assertFalse(self.current(now_mono=529.0))
        self.assertEqual(snapshot, self.guard)

    def test_qualified_proof_expires_when_either_stream_stops_advancing(self):
        self.qualify()
        self.assertTrue(self.evaluate(60, reports=(1060.0, 1030.0)))
        self.assertTrue(self.evaluate(90, reports=(1090.0, 1030.0)))
        self.assertFalse(self.evaluate(90.001, reports=(1090.001, 1030.0)))
        self.assertTrue(self.guard.required)
        self.assertEqual("closed", self.guard.phase)

    def test_reset_invalidates_inflight_dispatch_and_commit(self):
        self.qualify()
        generation = self.guard.generation
        self.guard.reset("application_cancelled")
        self.assertFalse(self.current(generation=generation))
        self.assertFalse(self.guard.commit(generation))

    def test_diagnostics_explain_pending_span_without_mutating_proof(self):
        self.assertFalse(self.evaluate(0))
        self.assertFalse(self.evaluate(20))
        snapshot = deepcopy(self.guard)
        values = self.guard.diagnostics("solar_budget_reentry")
        self.assertTrue(values["solar_budget_reentry_required"])
        self.assertEqual("qualifying", values["solar_budget_reentry_state"])
        self.assertEqual(1000.0, values["solar_budget_reentry_first_pv_report_ts"])
        self.assertEqual(1020.0, values["solar_budget_reentry_last_load_report_ts"])
        self.assertEqual(20.0, values["solar_budget_reentry_qualifying_seconds"])
        self.assertEqual(snapshot, self.guard)
