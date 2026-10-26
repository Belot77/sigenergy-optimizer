from __future__ import annotations

import asyncio
import copy
import json
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.models import HVACObservedValue, SolarState
from haos49_characterization_helpers import RecordingHA


class SolarAllocationEvidenceTests(unittest.TestCase):
    """Passive evidence characterization; no actuator or live HA calls."""

    def setUp(self) -> None:
        # Composition keeps pytest from collecting the helper TestCase's tests.
        from test_phase1_solar_physical_relief_characterization import (
            SolarPhysicalReliefCharacterizationTests as _PhysicalReliefFixture,
        )

        self.fixture = _PhysicalReliefFixture("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)

    def test_charge_limit_readback_observation_preserves_provenance_and_legacy_value(self):
        self.assertEqual(
            HVACObservedValue(), SolarState().current_ess_charge_limit_observation,
        )

        optimizer = self.fixture._optimizer()
        ha = RecordingHA()
        optimizer.ha = ha
        entity = optimizer.cfg.ess_max_charging_limit
        now = self.fixture.WHEN
        fresh_stamp = now.timestamp()
        stale_stamp = fresh_stamp - optimizer.cfg.hvac_solar_data_max_age_seconds - 1

        cases = (
            ("fresh", "21.0", fresh_stamp, True, True, fresh_stamp),
            ("fresh_zero", "0.0", fresh_stamp, True, True, fresh_stamp),
            ("stale", "21.0", stale_stamp, True, False, stale_stamp),
            ("missing_provenance", "21.0", None, True, False, None),
            ("nonfinite", "nan", fresh_stamp, False, False, None),
        )
        for label, raw_value, stamp, available, fresh, reported_at in cases:
            with self.subTest(case=label):
                state_row = {"state": raw_value, "attributes": {}}
                if stamp is not None:
                    source_time = datetime.fromtimestamp(stamp, timezone.utc).isoformat()
                    state_row.update(last_updated=source_time, last_reported=source_time)
                ha.states[entity] = state_row
                with self.fixture.optimizer_time(now):
                    state = asyncio.run(optimizer._read_state())

                observation = state.current_ess_charge_limit_observation
                self.assertEqual(available, observation.available)
                self.assertEqual(fresh, observation.fresh)
                self.assertEqual(reported_at, observation.observed_at_ts)
                if available:
                    expected = 0.0 if label == "fresh_zero" else 21.0
                    self.assertEqual(expected, observation.value)
                    # The old setting readback remains available independently
                    # of whether its metadata proves that it is fresh.
                    self.assertEqual(expected, state.current_ess_charge_limit)
                else:
                    self.assertIsNone(observation.value)

    def _set_flow(self, state, *, stamp: float, pv: float, load: float,
                  grid_import: float, grid_export: float, battery: float):
        state.pv_kw = pv
        state.load_kw = load
        state.grid_import_power_kw = grid_import
        state.grid_export_power_kw = grid_export
        state.battery_power_sensor_kw = battery
        inputs = state.hvac_solar_inputs
        state.hvac_solar_inputs = replace(
            inputs,
            pv_power=replace(inputs.pv_power, value=pv, observed_at_ts=stamp),
            load_power=replace(inputs.load_power, value=load, observed_at_ts=stamp),
            grid_import_power=replace(
                inputs.grid_import_power, value=grid_import, observed_at_ts=stamp,
            ),
            grid_export_power=replace(
                inputs.grid_export_power, value=grid_export, observed_at_ts=stamp,
            ),
            battery_power=replace(
                inputs.battery_power, value=battery, observed_at_ts=stamp,
            ),
        )
        return state

    def test_trace_keeps_request_readback_and_physical_feedback_evidence_separate(self):
        fixture = self.fixture
        optimizer = fixture._optimizer()
        fixture._ramp(optimizer, 2)
        # Establish the provider fixture and a first current-time decision.
        state, _ = fixture._decision(optimizer, 5)

        # A synthetic strict-balance rejection follows an acknowledged 0.8 kW
        # relief command. The direct battery sensor is separately reported.
        stamp = fixture.WHEN.timestamp() + 5
        state = self._set_flow(
            state, stamp=stamp, pv=16.026, load=1.049,
            grid_import=0.0, grid_export=15.051, battery=0.002,
        )
        state.current_ess_charge_limit = 21.0
        state.current_ess_charge_limit_observation = HVACObservedValue(
            value=21.0, available=True, fresh=True, observed_at_ts=stamp,
        )
        decision = fixture.decide(
            optimizer, state, fixture.WHEN + timedelta(seconds=5),
        )

        self.assertEqual(0.0, decision.ess_charge_limit)
        self.assertEqual([], optimizer.ha.calls)
        optimizer._record_application_trace(state, decision)
        row = optimizer.decision_trace(limit=1)[0]
        allocation = row["charge_allocation"]

        self.assertEqual("pre_application", allocation["snapshot_phase"])
        self.assertEqual(state.timestamp.isoformat(), allocation["snapshot_timestamp"])
        self.assertEqual(0.0, row["summary"]["ess_charge_limit_kw"])
        readback = allocation["ess_charge_limit_readback"]
        self.assertEqual(21.0, readback["value_kw"])
        self.assertTrue(readback["available"])
        self.assertTrue(readback["fresh"])
        self.assertEqual(stamp, readback["reported_at_ts"])

        flows = allocation["flows"]
        self.assertEqual(stamp, flows["pv"]["reported_at_ts"])
        self.assertEqual(stamp, flows["load"]["reported_at_ts"])
        self.assertEqual(stamp, flows["grid_import"]["reported_at_ts"])
        self.assertEqual(stamp, flows["grid_export"]["reported_at_ts"])
        self.assertEqual(0.002, flows["battery"]["value_kw"])
        self.assertEqual(stamp, flows["battery"]["reported_at_ts"])
        self.assertAlmostEqual(-0.074, allocation["derived_balance_kw"])

        before = allocation["solar_feedback_before_evaluation"]
        self.assertEqual(0.8, before["command_kw"])
        self.assertEqual(fixture.WHEN.timestamp() + 4, before["acknowledged_at_ts"])
        recorded = allocation["solar_feedback_at_recording"]
        self.assertIsNone(recorded["command_kw"])
        self.assertIsNone(recorded["acknowledged_at_ts"])
        json.dumps(row, allow_nan=False)

    def test_observation_metadata_is_passive_for_existing_decision_and_writes(self):
        fixture = self.fixture
        optimizer = fixture._optimizer()
        state = fixture._flow_state(0)
        state.current_ess_charge_limit = 21.0
        state.current_ess_charge_limit_observation = HVACObservedValue(
            value=21.0, available=True, fresh=True,
            observed_at_ts=fixture.WHEN.timestamp(),
        )
        first = fixture.decide(optimizer, state, fixture.WHEN)
        first_controls = (
            first.ems_mode, first.export_limit, first.import_limit,
            first.pv_max_power_limit, first.ess_charge_limit, first.export_intent,
            first.solar_surplus_policy_active, first.trace_gates.copy(),
        )

        state.current_ess_charge_limit_observation = HVACObservedValue()
        second = fixture.decide(optimizer, state, fixture.WHEN)
        second_controls = (
            second.ems_mode, second.export_limit, second.import_limit,
            second.pv_max_power_limit, second.ess_charge_limit, second.export_intent,
            second.solar_surplus_policy_active, second.trace_gates.copy(),
        )
        self.assertEqual(first_controls, second_controls)
        self.assertEqual([], optimizer.ha.calls)

    def test_trace_preserves_distinct_source_reports_without_mutating_snapshot(self):
        fixture = self.fixture
        optimizer = fixture._optimizer()
        state = fixture._flow_state(0)
        fields = (
            "pv_power", "load_power", "grid_import_power",
            "grid_export_power", "battery_power",
        )
        timestamps = (10.25, 11.5, 12.75, 14.0, 15.125)
        reported_observations = {}
        for name, stamp in zip(fields, timestamps):
            original = getattr(state.hvac_solar_inputs, name)
            reported_observations[name] = replace(original, observed_at_ts=stamp)
            setattr(
                state, "hvac_solar_inputs",
                replace(state.hvac_solar_inputs,
                        **{name: reported_observations[name]}),
            )

        before = state.hvac_solar_inputs
        optimizer._record_decision_trace(state, fixture._decision(
            optimizer, 0,
        )[1])
        row = optimizer.decision_trace(limit=1)[0]
        allocation = row["charge_allocation"]
        self.assertEqual(
            list(timestamps),
            [allocation["flows"][name]["reported_at_ts"] for name in (
                "pv", "load", "grid_import", "grid_export", "battery",
            )],
        )
        self.assertIs(before, state.hvac_solar_inputs)
        for name, observation in reported_observations.items():
            # Frozen observation objects and their source provenance are reused.
            self.assertEqual(observation, getattr(state.hvac_solar_inputs, name))

    def test_balance_is_diagnostic_only_for_complete_finite_nonnegative_flows(self):
        fixture = self.fixture
        optimizer = fixture._optimizer()
        state = fixture._flow_state(0)
        values = {"pv_power": 16.026, "load_power": 1.049,
                  "grid_import_power": 0.0, "grid_export_power": 15.051}

        def evidence(overrides=None):
            overrides = overrides or {}
            for name, value in values.items():
                observation = HVACObservedValue(
                    value=value, available=True, fresh=True,
                    observed_at_ts=fixture.WHEN.timestamp(),
                )
                if name in overrides:
                    observation = overrides[name]
                state.hvac_solar_inputs = replace(
                    state.hvac_solar_inputs, **{name: observation},
                )
            return optimizer._charge_allocation_trace_evidence(state, {})

        complete = evidence()
        self.assertAlmostEqual(-0.074, complete["derived_balance_kw"])
        stale = evidence({"pv_power": HVACObservedValue(
            value=16.026, available=True, fresh=False, observed_at_ts=1.0,
        )})
        self.assertFalse(stale["flows"]["pv"]["fresh"])
        self.assertAlmostEqual(-0.074, stale["derived_balance_kw"])

        invalid = (
            (HVACObservedValue(), None, False),
            (HVACObservedValue(value=16.026, available=False, fresh=True),
             16.026, False),
            (HVACObservedValue(value=float("nan"), available=True, fresh=True),
             None, False),
            (HVACObservedValue(value=True, available=True, fresh=True), None, False),
            (HVACObservedValue(value=-1.0, available=True, fresh=True), -1.0, True),
        )
        for observation, expected_value, expected_available in invalid:
            with self.subTest(observation=observation):
                unavailable = evidence({"pv_power": observation})
                self.assertIsNone(unavailable["derived_balance_kw"])
                self.assertEqual(expected_value, unavailable["flows"]["pv"]["value_kw"])
                self.assertEqual(expected_available, unavailable["flows"]["pv"]["available"])

        overflow = evidence({
            "pv_power": HVACObservedValue(value=1e308, available=True, fresh=True),
            "grid_import_power": HVACObservedValue(value=1e308, available=True, fresh=True),
        })
        self.assertIsNone(overflow["derived_balance_kw"])

    def test_unknown_readback_does_not_fall_back_to_legacy_zero(self):
        fixture = self.fixture
        optimizer = fixture._optimizer()
        state = fixture._flow_state(0)
        self.assertEqual(0.0, state.current_ess_charge_limit)
        state.current_ess_charge_limit_observation = HVACObservedValue()
        optimizer._record_decision_trace(state, fixture._decision(optimizer, 0)[1])
        row = optimizer.decision_trace(limit=1)[0]
        readback = row["charge_allocation"]["ess_charge_limit_readback"]
        self.assertIsNone(readback["value_kw"])
        self.assertFalse(readback["available"])
        json.dumps(row, allow_nan=False)

    def test_evidence_trace_failure_does_not_disrupt_commit_or_rollback(self):
        from test_decision_trace_application_outcomes import (
            DecisionTraceApplicationOutcomeTests as _OutcomeFixture,
        )
        from app.optimizer import _ActuatorApplicationResult

        fixture = _OutcomeFixture("runTest")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.addCleanup(fixture.tearDown)
        cases = (
            ("success", _ActuatorApplicationResult(succeeded=True)),
            ("failure", _ActuatorApplicationResult(
                succeeded=False, error="test-only actuator failure",
            )),
        )
        for label, result in cases:
            with self.subTest(outcome=label):
                optimizer, state, requested, previous, previous_state = fixture.cycle(result)
                with patch.object(
                    optimizer, "_charge_allocation_trace_evidence",
                    side_effect=RuntimeError("test-only evidence failure detail"),
                ):
                    if label == "failure":
                        with self.assertRaisesRegex(RuntimeError, "test-only actuator failure"):
                            asyncio.run(optimizer._tick())
                        fixture.assert_not_committed(optimizer, previous, previous_state)
                    else:
                        asyncio.run(optimizer._tick())
                        self.assertIs(requested, optimizer._last_decision)
                        self.assertIs(state, optimizer._last_state)
                        optimizer._record_automation_audit.assert_called_once()
                        optimizer._handle_notifications.assert_awaited_once()
                # Trace diagnostics fail closed: no malformed row and no error text leak.
                self.assertEqual([], optimizer.decision_trace())
                self.assertNotIn(
                    "test-only evidence failure detail",
                    json.dumps(optimizer.decision_trace()),
                )

    def test_archive_preserves_new_evidence_and_leaves_historical_rows_without_it(self):
        from test_decision_trace_store import (
            DecisionTraceStoreTests as _ArchiveFixture, NOW,
        )

        archive = _ArchiveFixture("runTest")
        archive.setUp()
        self.addCleanup(archive.doCleanups)
        self.addCleanup(archive.tearDown)
        optimizer = self.fixture._optimizer()
        state, decision = self.fixture._decision(optimizer, 0)
        optimizer._record_application_trace(state, decision)
        current = copy.deepcopy(optimizer.decision_trace(limit=1)[0])
        current["ts"] = NOW.isoformat(timespec="seconds")
        historical = copy.deepcopy(current)
        historical.pop("charge_allocation")
        historical["summary"]["outcome_reason"] = "synthetic historical row"
        archive.rows.extendleft([historical, current])
        before = copy.deepcopy(list(archive.rows))

        self.assertTrue(archive.flush())
        self.assertTrue(archive.flush())
        records = archive.records()
        self.assertEqual(2, len(records))
        self.assertNotIn("charge_allocation", records[0])
        self.assertEqual(current["charge_allocation"], records[1]["charge_allocation"])
        self.assertEqual(before, list(archive.rows))
        json.dumps(records, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
