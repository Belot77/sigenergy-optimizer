"""Application-boundary trace regressions using fake HA and temporary storage."""

from __future__ import annotations

import asyncio
import json
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from app.config import Settings
from app.models import Decision
from app.optimizer import MODE_CMD_DISCHARGE_PV, MODE_MAX_SELF, _ActuatorApplicationResult
from haos49_characterization_helpers import Haos49CharacterizationCase


class DecisionTraceApplicationOutcomeTests(Haos49CharacterizationCase):
    def setUp(self) -> None:
        environment = patch.dict(os.environ, {}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        settings = patch(
            "haos49_characterization_helpers.Settings",
            side_effect=lambda **values: Settings(_env_file=None, **values),
        )
        settings.start()
        self.addCleanup(settings.stop)
        super().setUp()

    def cycle(self, result=None, *, real_apply=False, state_overrides=None):
        optimizer = self.optimizer()
        state = self.state(self.FIXED_AFTERNOON, **(state_overrides or {}))
        previous = Decision(outcome_reason="previous committed decision")
        previous_state = self.state(self.FIXED_AFTERNOON, battery_soc=55.0)
        requested = Decision(
            ems_mode=MODE_MAX_SELF,
            export_limit=0.0,
            import_limit=0.0,
            pv_max_power_limit=25.0,
            ess_charge_limit=0.0,
            ess_discharge_limit=0.0,
            outcome_reason="attempted decision",
        )
        optimizer._last_decision = previous
        optimizer._last_state = previous_state
        optimizer._read_state = AsyncMock(return_value=state)
        optimizer._decide = Mock(return_value=requested)
        if not real_apply:
            optimizer._apply = AsyncMock(return_value=result)
        optimizer._evaluate_hvac_solar_permission = Mock(return_value=object())
        optimizer._publish_hvac_solar_permission = AsyncMock()
        optimizer._record_automation_audit = Mock()
        optimizer._handle_notifications = AsyncMock()
        optimizer._handle_daily_summaries = AsyncMock()
        optimizer._accumulate_history = Mock()
        optimizer._record_price_tracking = Mock()
        return optimizer, state, requested, previous, previous_state

    def only_row(self, optimizer):
        rows = optimizer.decision_trace()
        self.assertEqual(1, len(rows))
        return rows[0]

    def assert_not_committed(self, optimizer, previous, previous_state):
        self.assertIs(previous, optimizer._last_decision)
        self.assertIs(previous_state, optimizer._last_state)
        optimizer._record_automation_audit.assert_not_called()
        optimizer._handle_notifications.assert_not_awaited()
        optimizer._accumulate_history.assert_not_called()

    def test_success_records_one_application_outcome_and_commits(self):
        optimizer, state, requested, _, _ = self.cycle(
            _ActuatorApplicationResult(succeeded=True),
        )
        asyncio.run(optimizer._tick())
        row = self.only_row(optimizer)
        self.assertEqual("succeeded", row["application"]["status"])
        self.assertIs(True, row["application"]["succeeded"])
        self.assertEqual("attempted decision", row["summary"]["outcome_reason"])
        self.assertIs(requested, optimizer._last_decision)
        self.assertIs(state, optimizer._last_state)
        self.assertEqual([], optimizer.ha.calls)

    def test_failed_results_record_fallback_without_committing(self):
        for fallback in (None, False, True):
            with self.subTest(fallback_succeeded=fallback):
                result = _ActuatorApplicationResult(
                    succeeded=False,
                    error="test-only sensitive application detail",
                    fallback_attempted=fallback is not None,
                    fallback_succeeded=fallback,
                )
                optimizer, _, requested, previous, previous_state = self.cycle(result)
                # A stale pending gate must not relabel an actual failure.
                requested.trace_gates["msc_transition_pending"] = True
                requested.trace_values["msc_transition_phase"] = "close"
                with self.assertRaisesRegex(RuntimeError, "sensitive application detail"):
                    asyncio.run(optimizer._tick())
                row = self.only_row(optimizer)
                self.assertEqual("failed", row["application"]["status"])
                self.assertIs(fallback, row["application"]["fallback_succeeded"])
                self.assertEqual(fallback is not None, row["application"]["fallback_attempted"])
                self.assertIsNone(row["application"]["transition_phase"])
                self.assertNotIn("sensitive application detail", json.dumps(row))
                self.assert_not_committed(optimizer, previous, previous_state)
                self.assertEqual([], optimizer.ha.calls)

    def test_real_pending_transition_is_recorded_without_promoting_decision(self):
        optimizer, _, _, previous, previous_state = self.cycle(
            real_apply=True,
            state_overrides={
                "current_ems_mode": MODE_CMD_DISCHARGE_PV,
                "current_export_limit": 25.0,
            },
        )
        optimizer._read_control_authority = AsyncMock(return_value=(
            SimpleNamespace(available=True, fresh=True, value="Automated"), "on",
        ))
        with self.assertRaisesRegex(RuntimeError, "awaiting later trusted close observation"):
            asyncio.run(optimizer._tick())
        row = self.only_row(optimizer)
        self.assertEqual("pending", row["application"]["status"])
        self.assertEqual("close", row["application"]["transition_phase"])
        self.assertIs(False, row["application"]["succeeded"])
        self.assertTrue(row["gates"]["msc_transition_pending"])
        self.assert_not_committed(optimizer, previous, previous_state)
        self.assertTrue(optimizer.ha.calls)  # Fake restrictions only.
        self.assertFalse(any(call[0] == "select_option" for call in optimizer.ha.calls))

    def test_pending_phase_is_allowlisted(self):
        for phase in ("close", "msc", "test-only sensitive phase"):
            with self.subTest(phase=phase):
                optimizer, _, requested, _, _ = self.cycle(
                    _ActuatorApplicationResult(succeeded=False, transition_pending=True),
                )
                requested.trace_values["msc_transition_phase"] = phase
                with self.assertRaises(RuntimeError):
                    asyncio.run(optimizer._tick())
                application = self.only_row(optimizer)["application"]
                self.assertEqual("pending", application["status"])
                self.assertEqual(phase if phase in ("close", "msc") else "unknown",
                                 application["transition_phase"])
                self.assertNotIn("sensitive", json.dumps(application))

    def test_application_exception_is_recorded_without_message_and_reraised(self):
        optimizer, _, _, previous, previous_state = self.cycle()
        error = ValueError("test-only sensitive exception detail")
        optimizer._apply.side_effect = error
        with self.assertRaises(ValueError) as caught:
            asyncio.run(optimizer._tick())
        self.assertIs(error, caught.exception)
        row = self.only_row(optimizer)
        self.assertEqual("exception", row["application"]["status"])
        self.assertIsNone(row["application"]["succeeded"])
        self.assertNotIn("sensitive exception detail", json.dumps(row))
        self.assert_not_committed(optimizer, previous, previous_state)

    def test_trace_failure_cannot_break_success_or_mask_application_error(self):
        for application_fails in (False, True):
            with self.subTest(application_fails=application_fails):
                optimizer, _, requested, previous, previous_state = self.cycle(
                    _ActuatorApplicationResult(succeeded=True),
                )
                optimizer._record_decision_trace = Mock(
                    side_effect=RuntimeError("test-only sensitive recorder detail"),
                )
                error = ValueError("original application failure")
                if application_fails:
                    optimizer._apply.side_effect = error
                with self.assertLogs("app.optimizer", level="WARNING") as logs:
                    if application_fails:
                        with self.assertRaises(ValueError) as caught:
                            asyncio.run(optimizer._tick())
                        self.assertIs(error, caught.exception)
                        self.assert_not_committed(optimizer, previous, previous_state)
                    else:
                        asyncio.run(optimizer._tick())
                        self.assertIs(requested, optimizer._last_decision)
                self.assertNotIn("sensitive recorder detail", " ".join(logs.output))
                self.assertEqual(1, optimizer._record_decision_trace.call_count)

    def test_later_hook_failure_keeps_one_application_success_record(self):
        for hook in ("_record_automation_audit", "_handle_notifications"):
            with self.subTest(hook=hook):
                optimizer, _, requested, _, _ = self.cycle(
                    _ActuatorApplicationResult(succeeded=True),
                )
                getattr(optimizer, hook).side_effect = RuntimeError("later hook failed")
                with self.assertRaisesRegex(RuntimeError, "later hook failed"):
                    asyncio.run(optimizer._tick())
                self.assertEqual("succeeded", self.only_row(optimizer)["application"]["status"])
                self.assertIs(requested, optimizer._last_decision)

    def test_cancellation_during_application_still_propagates_without_completed_row(self):
        optimizer, _, _, previous, _ = self.cycle()
        optimizer._apply.side_effect = asyncio.CancelledError()
        with self.assertRaises(asyncio.CancelledError):
            asyncio.run(optimizer._tick())
        self.assertEqual([], optimizer.decision_trace())
        self.assertIs(previous, optimizer._last_decision)
        optimizer._handle_notifications.assert_not_awaited()

    def test_legacy_unreported_result_keeps_existing_commit_behavior(self):
        optimizer, _, requested, _, _ = self.cycle(None)
        asyncio.run(optimizer._tick())
        application = self.only_row(optimizer)["application"]
        self.assertEqual("unreported", application["status"])
        self.assertIsNone(application["succeeded"])
        self.assertIs(requested, optimizer._last_decision)

    def test_read_failure_before_application_does_not_fabricate_a_decision(self):
        optimizer, _, _, previous, previous_state = self.cycle()
        optimizer._read_state.side_effect = RuntimeError("read failed")
        with self.assertRaisesRegex(RuntimeError, "read failed"):
            asyncio.run(optimizer._tick())
        self.assertEqual([], optimizer.decision_trace())
        optimizer._apply.assert_not_awaited()
        self.assert_not_committed(optimizer, previous, previous_state)

    def test_direct_recorder_keeps_legacy_shape_without_application_metadata(self):
        optimizer, state, requested, _, _ = self.cycle()
        optimizer._record_decision_trace(state, requested)
        self.assertEqual({"ts", "summary", "state", "gates", "values"},
                         set(self.only_row(optimizer)))
