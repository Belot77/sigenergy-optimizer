from __future__ import annotations

import asyncio
from datetime import datetime

from app.models import (
    Decision,
    EXPORT_BLOCKED,
    HVACObservedValue,
    HVACSolarInputContext,
    MSC_SURPLUS_CEILING,
)
from app.optimizer import MODE_MAX_SELF
from haos49_characterization_helpers import (
    Haos49CharacterizationCase,
    RecordingHA,
)


class Phase1ChatterReopenCharacterizationTests(Haos49CharacterizationCase):
    """Package 5 Morning Slow chatter repair and preserved flow protections."""

    MORNING = datetime(2026, 1, 15, 9, 0, 0)

    @staticmethod
    def _observed(
        value: float | str | bool | None,
        *,
        available: bool = True,
        fresh: bool = True,
    ) -> HVACObservedValue:
        return HVACObservedValue(value=value, available=available, fresh=fresh)

    def _live_inputs(
        self,
        *,
        pv_kw: float,
        load_kw: float,
        battery_power_kw: float,
        grid_export_kw: float,
        grid_import_kw: float = 0.0,
        battery_observation: HVACObservedValue | None = None,
        grid_export_observation: HVACObservedValue | None = None,
        grid_import_observation: HVACObservedValue | None = None,
        pv_observation: HVACObservedValue | None = None,
        load_observation: HVACObservedValue | None = None,
    ) -> HVACSolarInputContext:
        return HVACSolarInputContext(
            pv_power=pv_observation or self._observed(pv_kw),
            load_power=load_observation or self._observed(load_kw),
            battery_power=battery_observation
            or self._observed(battery_power_kw),
            grid_import_power=grid_import_observation
            or self._observed(grid_import_kw),
            grid_export_power=grid_export_observation
            or self._observed(grid_export_kw),
            solar_power_now=self._observed(pv_kw),
            sun_above_horizon=self._observed(True),
            control_mode=self._observed("Automated"),
            observed_ems_mode=self._observed(MODE_MAX_SELF),
            observed_export_limit=self._observed(25.0),
            live_snapshot=True,
        )

    def _optimizer(self, *, morning_slow: bool, ha: object | None = None):
        return self.optimizer(
            ha,
            morning_slow_charge_enabled=morning_slow,
            morning_slow_charge_rate_kw=2.0,
            min_grid_transfer_kw=0.5,
        )

    def _state(
        self,
        *,
        morning_slow: bool,
        battery_discharge_kw: float,
        grid_export_kw: float = 0.0,
        grid_import_kw: float = 0.0,
        pv_kw: float = 4.2,
        load_kw: float = 1.0,
        current_export_limit: float = 25.0,
        inputs: HVACSolarInputContext | None = None,
        derived_power_flow_coherent: bool | None = True,
    ):
        when = self.MORNING if morning_slow else self.FIXED_AFTERNOON
        return self.state(
            when,
            battery_soc=14.5 if morning_slow else 60.0,
            available_discharge_energy_kwh=4.35 if morning_slow else 18.0,
            battery_power_sensor_kw=-battery_discharge_kw,
            pv_kw=pv_kw,
            solar_power_now_kw=pv_kw,
            load_kw=load_kw,
            grid_import_power_kw=grid_import_kw,
            grid_export_power_kw=grid_export_kw,
            current_export_limit=current_export_limit,
            current_export_limit_observed=True,
            current_import_limit=0.01,
            current_import_limit_observed=True,
            feedin_price=0.15,
            feedin_price_cents=15.0,
            forecast_remaining_kwh=100.0,
            pv_power_trusted=True,
            load_power_trusted=True,
            derived_power_flow_coherent=derived_power_flow_coherent,
            hvac_solar_inputs=inputs
            or self._live_inputs(
                pv_kw=pv_kw,
                load_kw=load_kw,
                battery_power_kw=-battery_discharge_kw,
                grid_export_kw=grid_export_kw,
                grid_import_kw=grid_import_kw,
            ),
        )

    def _decide(self, optimizer, state, *, morning_slow: bool):
        when = self.MORNING if morning_slow else self.FIXED_AFTERNOON
        return self.decide(optimizer, state, when)

    def _assert_common_flow_provenance(self, decision) -> None:
        self.assertTrue(decision.trace_gates["observed_automated_control_mode"])
        self.assertTrue(decision.trace_gates["ems_mode_observed"])
        self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
        self.assertEqual(0.1, decision.trace_values["pv_only_discharge_tolerance_kw"])
        self.assertEqual(
            0.5,
            decision.trace_values["ordinary_msc_meaningful_export_threshold_kw"],
        )
        self.assertEqual("none", decision.trace_values["battery_export_owner"])

    def test_morning_slow_uses_trusted_ordinary_msc_flow_across_battery_tolerance(
        self,
    ) -> None:
        cases = (
            (0.0, "battery_within_tolerance"),
            (0.094, "battery_within_tolerance"),
            (0.099999, "battery_within_tolerance"),
            (0.1, "battery_within_tolerance"),
            (0.100001, "load_serving_battery_discharge"),
            (0.101, "load_serving_battery_discharge"),
            (0.2, "load_serving_battery_discharge"),
        )
        for discharge_kw, expected_classification in cases:
            with self.subTest(discharge_kw=discharge_kw):
                optimizer = self._optimizer(morning_slow=True)
                state = self._state(
                    morning_slow=True,
                    battery_discharge_kw=discharge_kw,
                )

                decision = self._decide(optimizer, state, morning_slow=True)

                self._assert_common_flow_provenance(decision)
                self.assertTrue(decision.morning_slow_charge_active)
                self.assertEqual(
                    "direct_battery_sensor",
                    decision.trace_values["battery_flow_source_for_pv_only"],
                )
                self.assertAlmostEqual(
                    discharge_kw,
                    decision.trace_values["battery_discharge_kw_for_pv_only"],
                )
                self.assertEqual(
                    "morning_slow_pv_high",
                    decision.trace_values["initial_desired_export_source"],
                )
                self.assertEqual(
                    expected_classification,
                    decision.trace_values["ordinary_msc_flow_classification"],
                )
                self.assertTrue(decision.trace_gates["ordinary_msc_flow_safe"])
                self.assertFalse(
                    decision.trace_gates["pv_only_branch_battery_safety_blocked"]
                )
                self.assertTrue(
                    decision.trace_gates["pv_only_branch_high_ceiling_active"]
                )
                self.assertEqual(
                    optimizer.cfg.export_limit_high,
                    decision.export_limit,
                )
                self.assertEqual(MSC_SURPLUS_CEILING, decision.export_intent)

    def test_alternating_fresh_values_remain_at_high_ceiling_with_or_without_memory(
        self,
    ) -> None:
        for remember_decisions in (False, True):
            with self.subTest(remember_decisions=remember_decisions):
                optimizer = self._optimizer(morning_slow=True)
                discharge_values = (0.094, 0.101, 0.094, 0.101)
                observed_ceilings = (25.0, 25.0, 0.01, 25.0)
                requested_ceilings: list[float] = []

                for discharge_kw, observed_ceiling in zip(
                    discharge_values,
                    observed_ceilings,
                    strict=True,
                ):
                    state = self._state(
                        morning_slow=True,
                        battery_discharge_kw=discharge_kw,
                        current_export_limit=observed_ceiling,
                    )
                    decision = self._decide(optimizer, state, morning_slow=True)
                    requested_ceilings.append(decision.export_limit)
                    if remember_decisions:
                        optimizer._last_state = state
                        optimizer._last_decision = decision

                self.assertEqual([25.0, 25.0, 25.0, 25.0], requested_ceilings)

    def test_previous_decision_owner_and_ceiling_do_not_delay_morning_slow_reopen(
        self,
    ) -> None:
        closed_optimizer = self._optimizer(morning_slow=True)
        closed_state = self._state(
            morning_slow=True,
            battery_discharge_kw=0.101,
            grid_export_kw=0.5,
        )
        closed_decision = self._decide(
            closed_optimizer,
            closed_state,
            morning_slow=True,
        )

        ordinary_optimizer = self._optimizer(morning_slow=False)
        ordinary_state = self._state(
            morning_slow=False,
            battery_discharge_kw=0.2,
        )
        ordinary_open = self._decide(
            ordinary_optimizer,
            ordinary_state,
            morning_slow=False,
        )

        prior_cases = (
            ("none", None, 0.0),
            ("morning_slow_closed", closed_decision, 0.01),
            ("ordinary_msc_open", ordinary_open, 12.0),
            (
                "solar_surplus_owner",
                Decision(
                    solar_surplus_bypass=True,
                    trace_gates={"pv_only_branch_high_ceiling_active": True},
                    trace_values={"pv_only_branch_source": "solar_surplus_bypass"},
                ),
                25.0,
            ),
        )
        for name, previous_decision, observed_ceiling in prior_cases:
            with self.subTest(name=name):
                optimizer = self._optimizer(morning_slow=True)
                optimizer._last_decision = previous_decision
                state = self._state(
                    morning_slow=True,
                    battery_discharge_kw=0.101,
                    current_export_limit=observed_ceiling,
                )

                decision = self._decide(optimizer, state, morning_slow=True)

                self.assertEqual(optimizer.cfg.export_limit_high, decision.export_limit)
                self.assertEqual(MSC_SURPLUS_CEILING, decision.export_intent)
                self.assertEqual(
                    name == "solar_surplus_owner",
                    decision.trace_gates["previous_cycle_solar_surplus_policy_owned"],
                )

    def test_failed_close_settlement_does_not_create_a_pure_decision_reopen_hold(
        self,
    ) -> None:
        ha = RecordingHA(
            state_values={},
            settle_numbers=False,
            settle_selects=False,
        )
        optimizer = self._optimizer(morning_slow=True, ha=ha)
        closing_state = self._state(
            morning_slow=True,
            battery_discharge_kw=0.101,
            grid_export_kw=0.5,
            current_export_limit=25.0,
        )
        closing_decision = self._decide(
            optimizer,
            closing_state,
            morning_slow=True,
        )

        application_result = asyncio.run(
            optimizer._apply(closing_state, closing_decision)
        )
        optimizer._last_state = closing_state
        optimizer._last_decision = closing_decision
        reopening_state = self._state(
            morning_slow=True,
            battery_discharge_kw=0.101,
            current_export_limit=25.0,
        )
        reopening_decision = self._decide(
            optimizer,
            reopening_state,
            morning_slow=True,
        )

        self.assertFalse(application_result.succeeded)
        self.assertIn("observed readback remains open", application_result.error)
        self.assertEqual(optimizer.cfg.export_limit_high, reopening_decision.export_limit)
        self.assertEqual(MSC_SURPLUS_CEILING, reopening_decision.export_intent)

    def test_morning_slow_allows_material_load_serving_discharge_below_export_threshold(
        self,
    ) -> None:
        optimizer = self._optimizer(morning_slow=True)
        state = self._state(
            morning_slow=True,
            battery_discharge_kw=1.0,
            grid_export_kw=0.499999,
        )

        decision = self._decide(optimizer, state, morning_slow=True)

        self.assertEqual(
            "load_serving_battery_discharge",
            decision.trace_values["ordinary_msc_flow_classification"],
        )
        self.assertTrue(decision.trace_gates["ordinary_msc_flow_safe"])
        self.assertFalse(
            decision.trace_gates["pv_only_branch_battery_safety_blocked"]
        )
        self.assertEqual(optimizer.cfg.export_limit_high, decision.export_limit)
        self.assertEqual(MSC_SURPLUS_CEILING, decision.export_intent)

    def test_morning_slow_pv_below_load_closes_before_the_pv_only_battery_gate(
        self,
    ) -> None:
        cases = (
            (0.05, 1.0, 1.05, "battery_within_tolerance"),
            (0.1, 1.0, 1.1, "battery_within_tolerance"),
            (0.100001, 1.0, 1.100001, "load_serving_battery_discharge"),
            (0.2, 1.0, 1.2, "load_serving_battery_discharge"),
            (1.0, 1.6, 2.6, "load_serving_battery_discharge"),
            (3.2, 1.6, 4.7, "load_serving_battery_discharge"),
        )
        for discharge_kw, pv_kw, load_kw, classification in cases:
            with self.subTest(discharge_kw=discharge_kw):
                optimizer = self._optimizer(morning_slow=True)
                state = self._state(
                    morning_slow=True,
                    battery_discharge_kw=discharge_kw,
                    grid_export_kw=0.0,
                    pv_kw=pv_kw,
                    load_kw=load_kw,
                )

                decision = self._decide(optimizer, state, morning_slow=True)

                self.assertEqual(
                    classification,
                    decision.trace_values["ordinary_msc_flow_classification"],
                )
                self.assertEqual(
                    classification == "load_serving_battery_discharge",
                    decision.trace_gates[
                        "ordinary_msc_load_serving_battery_discharge"
                    ],
                )
                self.assertTrue(decision.trace_gates["ordinary_msc_flow_safe"])
                self.assertFalse(
                    decision.trace_gates["pv_only_branch_high_ceiling_requested"]
                )
                self.assertFalse(
                    decision.trace_gates["pv_only_branch_battery_safety_blocked"]
                )
                self.assertEqual(
                    "closed_no_daytime_pv",
                    decision.trace_values["initial_desired_export_source"],
                )
                self.assertEqual(
                    "closed_no_daytime_pv",
                    decision.trace_values["desired_export_source"],
                )
                self.assertEqual(
                    "blocked_or_zero",
                    decision.trace_values["export_branch"],
                )
                self.assertEqual(0.0, decision.export_limit)
                self.assertEqual(EXPORT_BLOCKED, decision.export_intent)
                self.assertEqual("none", decision.trace_values["battery_export_owner"])

    def test_ordinary_msc_allows_same_load_serving_classification_below_export_threshold(
        self,
    ) -> None:
        cases = (
            (0.100001, 0.0, 1.0, 1.100001),
            (0.2, 0.2, 1.0, 1.0),
            (1.0, 0.49, 1.6, 2.11),
            (3.2, 0.0, 1.6, 4.7),
        )
        for discharge_kw, export_kw, pv_kw, load_kw in cases:
            with self.subTest(discharge_kw=discharge_kw, export_kw=export_kw):
                optimizer = self._optimizer(morning_slow=False)
                state = self._state(
                    morning_slow=False,
                    battery_discharge_kw=discharge_kw,
                    grid_export_kw=export_kw,
                    pv_kw=pv_kw,
                    load_kw=load_kw,
                )

                decision = self._decide(optimizer, state, morning_slow=False)

                self._assert_common_flow_provenance(decision)
                self.assertEqual(
                    "load_serving_battery_discharge",
                    decision.trace_values["ordinary_msc_flow_classification"],
                )
                self.assertTrue(decision.trace_gates["ordinary_msc_flow_safe"])
                self.assertEqual(
                    "ordinary_msc_surplus_ceiling",
                    decision.trace_values["desired_export_source"],
                )
                self.assertEqual(
                    "ordinary_msc_surplus_ceiling",
                    decision.trace_values["export_branch"],
                )
                self.assertEqual(optimizer.cfg.export_limit_high, decision.export_limit)
                self.assertEqual(MSC_SURPLUS_CEILING, decision.export_intent)

    def test_meaningful_grid_export_boundary_controls_simultaneous_classification(
        self,
    ) -> None:
        cases = (
            (0.1, 1.837, "battery_within_tolerance", True),
            (0.100001, 0.499999, "load_serving_battery_discharge", True),
            (
                0.100001,
                0.5,
                "simultaneous_battery_discharge_and_grid_export",
                False,
            ),
            (
                0.273,
                1.837,
                "simultaneous_battery_discharge_and_grid_export",
                False,
            ),
            (
                3.2,
                0.5,
                "simultaneous_battery_discharge_and_grid_export",
                False,
            ),
            (3.2, 0.499999, "load_serving_battery_discharge", True),
        )
        for morning_slow in (False, True):
            for discharge_kw, export_kw, classification, expected_safe in cases:
                with self.subTest(
                    morning_slow=morning_slow,
                    discharge_kw=discharge_kw,
                    export_kw=export_kw,
                ):
                    optimizer = self._optimizer(morning_slow=morning_slow)
                    state = self._state(
                        morning_slow=morning_slow,
                        battery_discharge_kw=discharge_kw,
                        grid_export_kw=export_kw,
                    )

                    decision = self._decide(
                        optimizer,
                        state,
                        morning_slow=morning_slow,
                    )

                    self.assertEqual(
                        classification,
                        decision.trace_values["ordinary_msc_flow_classification"],
                    )
                    self.assertEqual(
                        expected_safe,
                        decision.trace_gates["ordinary_msc_flow_safe"],
                    )
                    self.assertEqual(
                        not expected_safe,
                        decision.trace_gates[
                            "ordinary_msc_simultaneous_battery_discharge_and_grid_export"
                        ],
                    )
                    self.assertEqual(
                        optimizer.cfg.export_limit_high if expected_safe else 0.0,
                        decision.export_limit,
                    )
                    self.assertEqual(
                        MSC_SURPLUS_CEILING if expected_safe else EXPORT_BLOCKED,
                        decision.export_intent,
                    )

    def test_battery_flow_trust_uses_direct_then_coherent_derived_then_unknown(
        self,
    ) -> None:
        unavailable = self._observed(None, available=False, fresh=False)
        stale = self._observed(-0.2, available=True, fresh=False)
        cases = (
            (
                "direct_unavailable_and_derivation_incomplete",
                self._live_inputs(
                    pv_kw=4.2,
                    load_kw=1.0,
                    battery_power_kw=-0.2,
                    grid_export_kw=0.0,
                    battery_observation=unavailable,
                    grid_import_observation=unavailable,
                ),
                True,
                "unknown",
                None,
                False,
            ),
            (
                "direct_stale_and_derivation_incomplete",
                self._live_inputs(
                    pv_kw=4.2,
                    load_kw=1.0,
                    battery_power_kw=-0.2,
                    grid_export_kw=0.0,
                    battery_observation=stale,
                    grid_import_observation=unavailable,
                ),
                True,
                "unknown",
                None,
                False,
            ),
            (
                "direct_unavailable_and_derived_incoherent",
                self._live_inputs(
                    pv_kw=0.8,
                    load_kw=1.0,
                    battery_power_kw=-0.2,
                    grid_export_kw=0.0,
                    battery_observation=unavailable,
                ),
                False,
                "unknown",
                None,
                False,
            ),
            (
                "direct_stale_but_coherent_derived_available",
                self._live_inputs(
                    pv_kw=0.8,
                    load_kw=1.0,
                    battery_power_kw=-0.2,
                    grid_export_kw=0.0,
                    battery_observation=stale,
                ),
                True,
                "measured_grid_flow",
                0.2,
                True,
            ),
        )
        for name, inputs, coherent, source, discharge_kw, expected_safe in cases:
            with self.subTest(name=name):
                optimizer = self._optimizer(morning_slow=False)
                state = self._state(
                    morning_slow=False,
                    battery_discharge_kw=0.2,
                    pv_kw=0.8,
                    load_kw=1.0,
                    inputs=inputs,
                    derived_power_flow_coherent=coherent,
                )

                decision = self._decide(optimizer, state, morning_slow=False)

                self.assertEqual(
                    source,
                    decision.trace_values["battery_flow_source_for_pv_only"],
                )
                if discharge_kw is None:
                    self.assertIsNone(
                        decision.trace_values["battery_discharge_kw_for_pv_only"]
                    )
                else:
                    self.assertAlmostEqual(
                        discharge_kw,
                        decision.trace_values["battery_discharge_kw_for_pv_only"],
                    )
                self.assertEqual(
                    expected_safe,
                    decision.trace_gates["ordinary_msc_flow_safe"],
                )
                self.assertEqual(
                    "load_serving_battery_discharge" if expected_safe else "unknown",
                    decision.trace_values["ordinary_msc_flow_classification"],
                )
                self.assertEqual(
                    optimizer.cfg.export_limit_high if expected_safe else 0.0,
                    decision.export_limit,
                )

    def test_unknown_battery_flow_blocks_otherwise_eligible_morning_slow_ceiling(
        self,
    ) -> None:
        unavailable = self._observed(None, available=False, fresh=False)
        inputs = self._live_inputs(
            pv_kw=4.2,
            load_kw=1.0,
            battery_power_kw=-0.2,
            grid_export_kw=0.0,
            battery_observation=unavailable,
            grid_import_observation=unavailable,
        )
        optimizer = self._optimizer(morning_slow=True)
        state = self._state(
            morning_slow=True,
            battery_discharge_kw=0.2,
            inputs=inputs,
        )

        decision = self._decide(optimizer, state, morning_slow=True)

        self.assertTrue(
            decision.trace_gates["pv_only_branch_high_ceiling_requested"]
        )
        self.assertEqual(
            "unknown",
            decision.trace_values["ordinary_msc_flow_classification"],
        )
        self.assertFalse(decision.trace_gates["ordinary_msc_flow_safe"])
        self.assertTrue(
            decision.trace_gates["pv_only_branch_battery_safety_blocked"]
        )
        self.assertEqual(0.0, decision.export_limit)
        self.assertEqual(EXPORT_BLOCKED, decision.export_intent)

    def test_untrusted_grid_export_flow_fails_closed_despite_trusted_battery_flow(
        self,
    ) -> None:
        cases = (
            self._observed(None, available=False, fresh=False),
            self._observed(0.0, available=True, fresh=False),
            self._observed(float("nan"), available=True, fresh=True),
        )
        for morning_slow in (False, True):
            for grid_export_observation in cases:
                with self.subTest(
                    morning_slow=morning_slow,
                    observation=grid_export_observation,
                ):
                    inputs = self._live_inputs(
                        pv_kw=4.2,
                        load_kw=1.0,
                        battery_power_kw=0.0,
                        grid_export_kw=0.0,
                        grid_export_observation=grid_export_observation,
                    )
                    optimizer = self._optimizer(morning_slow=morning_slow)
                    state = self._state(
                        morning_slow=morning_slow,
                        battery_discharge_kw=0.0,
                        inputs=inputs,
                    )

                    decision = self._decide(
                        optimizer,
                        state,
                        morning_slow=morning_slow,
                    )

                    self.assertEqual(
                        "direct_battery_sensor",
                        decision.trace_values["battery_flow_source_for_pv_only"],
                    )
                    self.assertEqual(
                        "unknown",
                        decision.trace_values["ordinary_msc_grid_export_source"],
                    )
                    self.assertIsNone(
                        decision.trace_values["ordinary_msc_grid_export_kw"]
                    )
                    self.assertFalse(
                        decision.trace_gates["ordinary_msc_flow_trusted"]
                    )
                    self.assertFalse(decision.trace_gates["ordinary_msc_flow_safe"])
                    self.assertEqual(
                        "unknown",
                        decision.trace_values["ordinary_msc_flow_classification"],
                    )
                    if morning_slow:
                        self.assertTrue(
                            decision.trace_gates[
                                "pv_only_branch_battery_safety_blocked"
                            ]
                        )
                    self.assertEqual(0.0, decision.export_limit)
                    self.assertEqual(EXPORT_BLOCKED, decision.export_intent)
