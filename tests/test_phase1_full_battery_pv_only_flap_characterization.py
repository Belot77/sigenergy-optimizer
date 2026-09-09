from __future__ import annotations

from dataclasses import replace

from app.models import (
    EXPORT_BLOCKED,
    HVACObservedValue,
    HVACSolarInputContext,
    MSC_SURPLUS_CEILING,
)
from app.optimizer import MODE_MAX_SELF
from haos49_characterization_helpers import Haos49CharacterizationCase


class Phase1FullBatteryPvOnlyFlapCharacterizationTests(
    Haos49CharacterizationCase
):
    """Characterize the current exact-full PV-only evidence-source flap."""

    DIRECT_BATTERY_POWER_KW = -0.007
    PV_POWER_KW = 6.0
    LOAD_POWER_KW = 1.0
    GRID_IMPORT_POWER_KW = 0.0
    GRID_EXPORT_POWER_KW = 5.75
    DERIVED_BATTERY_DISCHARGE_KW = 0.75

    @staticmethod
    def _observed(value: float) -> HVACObservedValue:
        return HVACObservedValue(value=value, available=True, fresh=True)

    def _fresh_live_context(self) -> HVACSolarInputContext:
        return HVACSolarInputContext(
            pv_power=self._observed(self.PV_POWER_KW),
            load_power=self._observed(self.LOAD_POWER_KW),
            battery_power=self._observed(self.DIRECT_BATTERY_POWER_KW),
            grid_import_power=self._observed(self.GRID_IMPORT_POWER_KW),
            grid_export_power=self._observed(self.GRID_EXPORT_POWER_KW),
            live_snapshot=True,
        )

    def _full_battery_msc_state(
        self,
        live_context: HVACSolarInputContext,
    ):
        return self.state(
            self.FIXED_AFTERNOON,
            battery_soc=100.0,
            battery_soc_trusted=True,
            battery_capacity_kwh=40.0,
            battery_capacity_trusted=True,
            available_discharge_energy_kwh=40.0,
            available_discharge_energy_trusted=True,
            current_price=0.189,
            current_price_cents=18.9,
            price_is_actual=True,
            feedin_price=0.0789,
            feedin_price_cents=7.89,
            pv_kw=self.PV_POWER_KW,
            pv_power_trusted=True,
            solar_power_now_kw=self.PV_POWER_KW,
            load_kw=self.LOAD_POWER_KW,
            load_power_trusted=True,
            battery_power_sensor_kw=self.DIRECT_BATTERY_POWER_KW,
            grid_import_power_kw=self.GRID_IMPORT_POWER_KW,
            grid_export_power_kw=self.GRID_EXPORT_POWER_KW,
            derived_power_flow_coherent=True,
            derived_power_flow_span_seconds=1.0,
            current_ems_mode=MODE_MAX_SELF,
            ems_mode_observed=True,
            current_export_limit=0.01,
            current_export_limit_observed=True,
            current_import_limit=0.0,
            current_import_limit_observed=True,
            current_pv_max_power_limit=25.0,
            current_ess_charge_limit=100.0,
            current_ess_discharge_limit=100.0,
            grid_export_limit_entity_max_kw=25.0,
            ess_max_charge_kw=100.0,
            ess_max_discharge_kw=100.0,
            ess_charge_limit_entity_max_kw=100.0,
            ess_discharge_limit_entity_max_kw=100.0,
            demand_window_active=False,
            demand_window_observed=True,
            hvac_solar_inputs=live_context,
        )

    def test_direct_freshness_alone_reproduces_25_0_25_0_flap(self) -> None:
        optimizer = self.optimizer(
            export_threshold_low=0.08,
            export_limit_high=25.0,
            min_grid_transfer_kw=1.0,
            pv_max_power_normal=25.0,
            ess_charge_limit_value=100.0,
            ess_discharge_limit_value=100.0,
            ess_limit_fallback_kw=100.0,
        )
        fresh_context = self._fresh_live_context()
        stale_context = replace(
            fresh_context,
            battery_power=replace(fresh_context.battery_power, fresh=False),
        )
        contexts = (fresh_context, stale_context, fresh_context, stale_context)

        # Replacing only the battery observation proves every independent fallback
        # observation and its value/trust state remain identical across the sequence.
        self.assertEqual(
            fresh_context,
            replace(stale_context, battery_power=fresh_context.battery_power),
        )
        self.assertTrue(fresh_context.battery_power.available)
        self.assertTrue(fresh_context.battery_power.fresh)
        self.assertTrue(stale_context.battery_power.available)
        self.assertFalse(stale_context.battery_power.fresh)

        expected_sources = (
            "direct_battery_sensor",
            "measured_grid_flow",
            "direct_battery_sensor",
            "measured_grid_flow",
        )
        expected_discharges = (0.007, 0.75, 0.007, 0.75)
        expected_exports = (25.0, 0.0, 25.0, 0.0)
        expected_branches = (
            "msc_full_battery_high_ceiling",
            "blocked_or_zero",
            "msc_full_battery_high_ceiling",
            "blocked_or_zero",
        )
        expected_classifications = (
            "battery_within_tolerance",
            "simultaneous_battery_discharge_and_grid_export",
            "battery_within_tolerance",
            "simultaneous_battery_discharge_and_grid_export",
        )

        decisions = []
        helper_results = []
        for cycle, context in enumerate(contexts, start=1):
            state = self._full_battery_msc_state(context)
            helper_results.append(
                optimizer._battery_discharge_kw_for_pv_only_check(state)
            )
            decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)
            decisions.append(decision)

            self.assertTrue(state.sigenergy_mode_observed, cycle)
            self.assertEqual(optimizer.cfg.automated_option, state.sigenergy_mode, cycle)
            self.assertTrue(state.ems_mode_observed, cycle)
            self.assertEqual(MODE_MAX_SELF, state.current_ems_mode, cycle)
            self.assertEqual(MODE_MAX_SELF, decision.ems_mode, cycle)
            self.assertEqual(25.0, decision.pv_max_power_limit, cycle)
            self.assertEqual(100.0, decision.ess_charge_limit, cycle)
            self.assertEqual(100.0, decision.ess_discharge_limit, cycle)
            self.assertTrue(bool(decision.trace_gates.get("topoff_target_met")), cycle)
            self.assertEqual(0.0, decision.trace_values.get("export_tier_limit"), cycle)
            self.assertEqual("closed_tier", decision.trace_values.get("desired_export_source"), cycle)
            self.assertEqual("none", decision.trace_values.get("battery_export_owner"), cycle)
            self.assertEqual(1.0, decision.trace_values.get("ordinary_msc_meaningful_export_threshold_kw"), cycle)
            self.assertEqual(5.75, decision.trace_values.get("ordinary_msc_grid_export_kw"), cycle)
            self.assertEqual(
                "direct_grid_export_sensor",
                decision.trace_values.get("ordinary_msc_grid_export_source"),
                cycle,
            )
            self.assertTrue(bool(decision.trace_gates.get("ordinary_msc_flow_trusted")), cycle)
            for inactive_gate in (
                "morning_dump_active",
                "morning_slow_charge_active",
                "demand_window_active",
                "export_spike_active",
                "positive_fit_override",
                "evening_export_boost_active",
                "export_solar_override",
                "solar_surplus_bypass",
                "battery_full_safeguard_block",
                "explicit_battery_export_owner_active",
            ):
                self.assertFalse(bool(decision.trace_gates.get(inactive_gate)), (cycle, inactive_gate))

            optimizer._last_state = state
            optimizer._last_decision = decision

        self.assertEqual(expected_sources, tuple(source for _, source in helper_results))
        self.assertEqual(
            expected_sources,
            tuple(
                decision.trace_values.get("battery_flow_source_for_pv_only")
                for decision in decisions
            ),
        )
        for expected, (observed, _) in zip(expected_discharges, helper_results):
            self.assertAlmostEqual(expected, observed)
        for expected, decision in zip(expected_discharges, decisions):
            self.assertAlmostEqual(
                expected,
                decision.trace_values.get("battery_discharge_kw_for_pv_only"),
            )

        # The fallback balance is 6.0 + 0.0 - 5.75 - 1.0 = -0.75 kW;
        # the safety helper exposes its magnitude as 0.75 kW discharge.
        fallback_battery_power_kw = (
            self.PV_POWER_KW
            + max(self.GRID_IMPORT_POWER_KW, 0.0)
            - max(self.GRID_EXPORT_POWER_KW, 0.0)
            - self.LOAD_POWER_KW
        )
        self.assertAlmostEqual(-0.75, fallback_battery_power_kw)
        self.assertAlmostEqual(
            self.DERIVED_BATTERY_DISCHARGE_KW,
            max(0.0, -fallback_battery_power_kw),
        )
        self.assertTrue(
            all(
                observation.available and observation.fresh
                for observation in (
                    stale_context.grid_import_power,
                    stale_context.grid_export_power,
                    stale_context.pv_power,
                    stale_context.load_power,
                )
            )
        )

        self.assertEqual(expected_exports, tuple(d.export_limit for d in decisions))
        self.assertEqual(
            expected_branches,
            tuple(d.trace_values.get("export_branch") for d in decisions),
        )
        self.assertEqual(
            expected_classifications,
            tuple(
                d.trace_values.get("ordinary_msc_flow_classification")
                for d in decisions
            ),
        )
        self.assertEqual(
            (True, False, True, False),
            tuple(bool(d.trace_gates.get("pv_only_discharge_ok")) for d in decisions),
        )
        self.assertEqual(
            (True, False, True, False),
            tuple(
                bool(d.trace_gates.get("pv_only_msc_transition_ready"))
                for d in decisions
            ),
        )
        self.assertEqual(
            (True, False, True, False),
            tuple(
                bool(d.trace_gates.get("pv_only_msc_high_ceiling_active"))
                for d in decisions
            ),
        )
        self.assertEqual(
            (False, True, False, True),
            tuple(
                bool(
                    d.trace_gates.get(
                        "ordinary_msc_simultaneous_battery_discharge_and_grid_export"
                    )
                )
                for d in decisions
            ),
        )
        self.assertEqual(
            (
                "msc_full_battery_high_ceiling",
                "none",
                "msc_full_battery_high_ceiling",
                "none",
            ),
            tuple(
                d.trace_values.get("pv_surplus_initiation_source")
                for d in decisions
            ),
        )
        self.assertEqual(
            (
                MSC_SURPLUS_CEILING,
                EXPORT_BLOCKED,
                MSC_SURPLUS_CEILING,
                EXPORT_BLOCKED,
            ),
            tuple(d.export_intent for d in decisions),
        )

    def test_fresh_direct_load_serving_discharge_exposes_exact_full_gate_mismatch(
        self,
    ) -> None:
        optimizer = self.optimizer(
            export_threshold_low=0.10,
            export_limit_high=25.0,
            min_grid_transfer_kw=1.0,
            pv_max_power_normal=25.0,
            ess_charge_limit_value=100.0,
            ess_discharge_limit_value=100.0,
            ess_limit_fallback_kw=100.0,
        )
        base_context = self._fresh_live_context()
        cases = (
            (
                "within_tolerance",
                -0.005,
                0.0,
                "battery_within_tolerance",
                False,
                False,
                True,
                True,
                25.0,
                "msc_full_battery_high_ceiling",
                MSC_SURPLUS_CEILING,
            ),
            (
                "material_load_serving_zero_export",
                -1.629,
                0.0,
                "load_serving_battery_discharge",
                True,
                False,
                True,
                False,
                0.0,
                "blocked_or_zero",
                EXPORT_BLOCKED,
            ),
            (
                "material_simultaneous_meaningful_export",
                -1.629,
                1.0,
                "simultaneous_battery_discharge_and_grid_export",
                False,
                True,
                False,
                False,
                0.0,
                "blocked_or_zero",
                EXPORT_BLOCKED,
            ),
        )

        stable_policy_inputs = None
        decisions = {}
        for (
            name,
            direct_battery_power_kw,
            grid_export_power_kw,
            expected_classification,
            expected_load_serving,
            expected_simultaneous,
            expected_flow_safe,
            expected_pv_only_discharge_ok,
            expected_export_limit,
            expected_export_branch,
            expected_export_intent,
        ) in cases:
            with self.subTest(name=name):
                context = replace(
                    base_context,
                    battery_power=self._observed(direct_battery_power_kw),
                    grid_export_power=self._observed(grid_export_power_kw),
                )
                self.assertEqual(
                    base_context,
                    replace(
                        context,
                        battery_power=base_context.battery_power,
                        grid_export_power=base_context.grid_export_power,
                    ),
                )

                state = self._full_battery_msc_state(context)
                state.feedin_price = 0.0664
                state.feedin_price_cents = 6.64
                state.battery_power_sensor_kw = direct_battery_power_kw
                state.grid_export_power_kw = grid_export_power_kw
                decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)
                decisions[name] = decision

                policy_inputs = (
                    state.battery_soc,
                    state.sigenergy_mode,
                    state.sigenergy_mode_observed,
                    state.current_ems_mode,
                    state.ems_mode_observed,
                    state.current_price,
                    state.feedin_price,
                    state.pv_kw,
                    state.load_kw,
                    decision.pv_max_power_limit,
                    decision.ess_charge_limit,
                    decision.ess_discharge_limit,
                )
                if stable_policy_inputs is None:
                    stable_policy_inputs = policy_inputs
                else:
                    self.assertEqual(stable_policy_inputs, policy_inputs)

                self.assertTrue(context.battery_power.available)
                self.assertTrue(context.battery_power.fresh)
                self.assertEqual(
                    "direct_battery_sensor",
                    decision.trace_values.get("battery_flow_source_for_pv_only"),
                )
                self.assertAlmostEqual(
                    max(0.0, -direct_battery_power_kw),
                    decision.trace_values.get("battery_discharge_kw_for_pv_only"),
                )
                self.assertEqual(
                    1.0,
                    decision.trace_values.get(
                        "ordinary_msc_meaningful_export_threshold_kw"
                    ),
                )
                self.assertEqual(
                    grid_export_power_kw,
                    decision.trace_values.get("ordinary_msc_grid_export_kw"),
                )
                self.assertEqual(
                    expected_classification,
                    decision.trace_values.get("ordinary_msc_flow_classification"),
                )
                self.assertEqual(
                    expected_load_serving,
                    bool(
                        decision.trace_gates.get(
                            "ordinary_msc_load_serving_battery_discharge"
                        )
                    ),
                )
                self.assertEqual(
                    expected_simultaneous,
                    bool(
                        decision.trace_gates.get(
                            "ordinary_msc_simultaneous_battery_discharge_and_grid_export"
                        )
                    ),
                )
                self.assertEqual(
                    expected_flow_safe,
                    bool(decision.trace_gates.get("ordinary_msc_flow_safe")),
                )
                self.assertEqual(
                    expected_pv_only_discharge_ok,
                    bool(decision.trace_gates.get("pv_only_discharge_ok")),
                )
                self.assertEqual(
                    expected_pv_only_discharge_ok,
                    bool(decision.trace_gates.get("pv_only_msc_transition_ready")),
                )
                self.assertEqual(
                    expected_pv_only_discharge_ok,
                    bool(decision.trace_gates.get("pv_only_msc_high_ceiling_active")),
                )
                self.assertEqual(expected_export_limit, decision.export_limit)
                self.assertEqual(
                    expected_export_branch,
                    decision.trace_values.get("export_branch"),
                )
                self.assertEqual(expected_export_intent, decision.export_intent)
                self.assertEqual(
                    "closed_tier",
                    decision.trace_values.get("desired_export_source"),
                )
                self.assertEqual(
                    "none",
                    decision.trace_values.get("battery_export_owner"),
                )
                for inactive_gate in (
                    "morning_dump_active",
                    "morning_slow_charge_active",
                    "demand_window_active",
                    "export_spike_active",
                    "positive_fit_override",
                    "evening_export_boost_active",
                    "export_solar_override",
                    "solar_surplus_bypass",
                    "battery_full_safeguard_block",
                    "explicit_battery_export_owner_active",
                ):
                    self.assertFalse(
                        bool(decision.trace_gates.get(inactive_gate)),
                        (name, inactive_gate),
                    )

                optimizer._last_state = state
                optimizer._last_decision = decision

        load_serving = decisions["material_load_serving_zero_export"]
        self.assertTrue(
            bool(load_serving.trace_gates.get("ordinary_msc_flow_safe"))
        )
        self.assertFalse(bool(load_serving.trace_gates.get("pv_only_discharge_ok")))
        self.assertEqual(0.0, load_serving.export_limit)

        simultaneous = decisions["material_simultaneous_meaningful_export"]
        self.assertFalse(
            bool(simultaneous.trace_gates.get("ordinary_msc_flow_safe"))
        )
        self.assertEqual(EXPORT_BLOCKED, simultaneous.export_intent)
