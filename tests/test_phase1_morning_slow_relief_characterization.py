from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models import (
    BATTERY_EXPORT,
    MSC_SURPLUS_CEILING,
    HVACObservedValue,
    HVACSolarInputContext,
)
from app.optimizer import MODE_CMD_CHARGE_GRID, MODE_CMD_DISCHARGE_PV, MODE_MAX_SELF
from haos49_characterization_helpers import Haos49CharacterizationCase


class Phase1MorningSlowReliefCharacterizationTests(Haos49CharacterizationCase):
    """Phase 1 Morning Slow relief and Morning Dump refill contract."""

    MORNING = datetime(2026, 1, 15, 9, 0, 0)
    SLOW_END = datetime(2026, 1, 15, 11, 0, 0)
    SUNSET = datetime(2026, 1, 15, 18, 0, 0)
    DUMP_TIME = datetime(2026, 1, 15, 6, 0, 0)

    @staticmethod
    def _observed(
        value: float | str | bool,
        *,
        fresh: bool = True,
        available: bool = True,
    ) -> HVACObservedValue:
        return HVACObservedValue(value=value, available=available, fresh=fresh)

    def _flow_inputs(
        self,
        *,
        pv_kw: float,
        load_kw: float,
        battery_charge_kw: float,
        grid_export_kw: float,
        export_fresh: bool = True,
        battery_fresh: bool = True,
    ) -> HVACSolarInputContext:
        return HVACSolarInputContext(
            pv_power=self._observed(pv_kw),
            load_power=self._observed(load_kw),
            battery_power=self._observed(
                battery_charge_kw,
                fresh=battery_fresh,
            ),
            grid_import_power=self._observed(0.0),
            grid_export_power=self._observed(
                grid_export_kw,
                fresh=export_fresh,
            ),
            solar_power_now=self._observed(pv_kw),
            sun_above_horizon=self._observed(True),
            control_mode=self._observed("Automated"),
            observed_ems_mode=self._observed(MODE_MAX_SELF),
            observed_export_limit=self._observed(25.0),
            live_snapshot=True,
        )

    def _optimizer(self, **overrides: object):
        values: dict[str, object] = {
            "morning_slow_charge_enabled": True,
            "morning_slow_charge_until": "11:00",
            "morning_slow_charge_rate_kw": 2.0,
            "morning_slow_charge_base_load_kw": 0.5,
            "morning_slow_charge_sunset_cutoff": 1.0,
            "grid_connection_export_limit_kw": 15.0,
            "morning_slow_physical_export_headroom_kw": 0.5,
            "forecast_safety_charging": 1.25,
            "ess_charge_limit_value": 10.0,
            "export_limit_high": 25.0,
            "pv_max_power_normal": 25.0,
        }
        values.update(overrides)
        optimizer = self.optimizer(**values)
        # These fixtures express policy times as naive host-local datetimes.
        optimizer._tz = timezone(
            self.MORNING.astimezone().utcoffset() or timedelta()
        )
        return optimizer

    def _detailed_forecast(
        self,
        optimizer,
        *,
        start: datetime,
        end: datetime,
        before_slow_end_pv_kw: float,
        after_slow_end_pv_kw: float,
    ) -> list[dict[str, object]]:
        period_seconds = optimizer.cfg.solcast_forecast_period_hours * 3600.0
        slow_end_ts = self.SLOW_END.timestamp()
        cursor = start.timestamp()
        end_ts = end.timestamp()
        periods: list[dict[str, object]] = []
        while cursor < end_ts:
            periods.append(
                {
                    "period_start": datetime.fromtimestamp(
                        cursor,
                        tz=timezone.utc,
                    ).isoformat(),
                    "pv_estimate": (
                        before_slow_end_pv_kw
                        if cursor < slow_end_ts
                        else after_slow_end_pv_kw
                    ),
                }
            )
            cursor += period_seconds
        return periods

    def _morning_state(
        self,
        optimizer,
        *,
        fill_need_kwh: float = 10.0,
        before_slow_end_pv_kw: float = 4.0,
        after_slow_end_pv_kw: float = 4.0,
        aggregate_remaining_kwh: float = 100.0,
        grid_export_kw: float = 8.0,
        battery_charge_kw: float = 2.0,
        detailed_source_trusted: bool = True,
        detailed_shape: str = "continuous",
        export_fresh: bool = True,
        battery_fresh: bool = True,
        capacity_trusted: bool = True,
        available_energy_trusted: bool = True,
        **overrides: object,
    ):
        capacity_kwh = 30.0
        available_kwh = capacity_kwh - fill_need_kwh
        load_kw = 1.0
        pv_kw = load_kw + grid_export_kw + battery_charge_kw
        state_values: dict[str, object] = {
            "battery_soc": available_kwh / capacity_kwh * 100.0,
            "battery_capacity_kwh": capacity_kwh,
            "available_discharge_energy_kwh": available_kwh,
            "battery_soc_trusted": True,
            "battery_capacity_trusted": capacity_trusted,
            "available_discharge_energy_trusted": available_energy_trusted,
            "battery_power_sensor_kw": battery_charge_kw,
            "pv_kw": pv_kw,
            "solar_power_now_kw": pv_kw,
            "load_kw": load_kw,
            "pv_power_trusted": True,
            "load_power_trusted": True,
            "pv_load_observations_coherent": True,
            "derived_power_flow_coherent": True,
            "grid_import_power_kw": 0.0,
            "grid_export_power_kw": grid_export_kw,
            "feedin_price": 0.15,
            "feedin_price_cents": 15.0,
            "forecast_remaining_kwh": aggregate_remaining_kwh,
            "forecast_remaining_observation_trusted": True,
            "forecast_today_kwh": aggregate_remaining_kwh,
            "forecast_today_observation_trusted": True,
            "forecast_tomorrow_kwh": 100.0,
            "forecast_tomorrow_observation_trusted": True,
            "solcast_detailed_source_trusted": detailed_source_trusted,
            "sun_state_observation_trusted": True,
            "sunrise_observation_trusted": True,
            "sunset_observation_trusted": True,
            "ess_max_charge_kw": 10.0,
            "ess_charge_limit_entity_max_kw": 10.0,
            "ess_max_discharge_kw": 10.0,
            "ess_discharge_limit_entity_max_kw": 10.0,
            "current_export_limit": 25.0,
            "current_export_limit_observed": True,
            "hvac_solar_inputs": self._flow_inputs(
                pv_kw=pv_kw,
                load_kw=load_kw,
                battery_charge_kw=battery_charge_kw,
                grid_export_kw=grid_export_kw,
                export_fresh=export_fresh,
                battery_fresh=battery_fresh,
            ),
        }
        state_values.update(overrides)
        state = self.state(self.MORNING, **state_values)
        periods = self._detailed_forecast(
            optimizer,
            start=self.MORNING,
            end=self.SUNSET,
            before_slow_end_pv_kw=before_slow_end_pv_kw,
            after_slow_end_pv_kw=after_slow_end_pv_kw,
        )
        if detailed_shape == "missing":
            periods = []
        elif detailed_shape == "gapped":
            del periods[len(periods) // 2]
        state.solcast_detailed = periods
        return state

    def _dump_state(
        self,
        optimizer,
        *,
        fill_need_kwh: float = 8.0,
        before_slow_end_pv_kw: float = 4.0,
        after_slow_end_pv_kw: float = 4.0,
        battery_soc: float = 80.0,
        detailed_source_trusted: bool = True,
        capacity_trusted: bool = True,
        available_energy_trusted: bool = True,
    ):
        capacity_kwh = 30.0
        state = self.state(
            self.DUMP_TIME,
            sun_above_horizon=False,
            battery_soc=battery_soc,
            battery_capacity_kwh=capacity_kwh,
            available_discharge_energy_kwh=capacity_kwh - fill_need_kwh,
            battery_soc_trusted=True,
            battery_capacity_trusted=capacity_trusted,
            available_discharge_energy_trusted=available_energy_trusted,
            battery_power_sensor_kw=0.0,
            pv_kw=0.0,
            solar_power_now_kw=0.0,
            load_kw=1.0,
            feedin_price=0.05,
            feedin_price_cents=5.0,
            forecast_remaining_kwh=100.0,
            forecast_remaining_observation_trusted=True,
            forecast_today_kwh=100.0,
            forecast_today_observation_trusted=True,
            forecast_tomorrow_kwh=100.0,
            forecast_tomorrow_observation_trusted=True,
            solcast_detailed_source_trusted=detailed_source_trusted,
            sun_state_observation_trusted=True,
            sunrise_observation_trusted=True,
            sunset_observation_trusted=True,
            ess_max_charge_kw=10.0,
            ess_charge_limit_entity_max_kw=10.0,
            ess_max_discharge_kw=10.0,
            ess_discharge_limit_entity_max_kw=10.0,
        )
        state.solcast_detailed = self._detailed_forecast(
            optimizer,
            start=self.DUMP_TIME,
            end=self.SUNSET,
            before_slow_end_pv_kw=before_slow_end_pv_kw,
            after_slow_end_pv_kw=after_slow_end_pv_kw,
        )
        return state

    def _assert_morning_slow_contract(
        self,
        optimizer,
        decision,
        *,
        expected_charge_limit_kw: float,
    ) -> None:
        self.assertTrue(decision.morning_slow_charge_active)
        self.assertTrue(decision.trace_gates["morning_slow_charge_active"])
        self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
        self.assertEqual(optimizer.cfg.export_limit_high, decision.export_limit)
        self.assertEqual(MSC_SURPLUS_CEILING, decision.export_intent)
        self.assertEqual(optimizer.cfg.pv_max_power_normal, decision.pv_max_power_limit)
        self.assertEqual(expected_charge_limit_kw, decision.ess_charge_limit)
        self.assertEqual("none", decision.trace_values["battery_export_owner"])
        self.assertNotEqual(BATTERY_EXPORT, decision.export_intent)
        self.assertFalse(decision.solar_surplus_policy_active)

    def test_comfortably_feasible_refill_keeps_normal_morning_slow_contract(self) -> None:
        optimizer = self._optimizer()
        state = self._morning_state(optimizer)

        decision = self.decide(optimizer, state, self.MORNING)

        self._assert_morning_slow_contract(
            optimizer,
            decision,
            expected_charge_limit_kw=2.0,
        )
        self.assertFalse(decision.trace_gates["morning_slow_forecast_refill_relief"])
        self.assertFalse(decision.trace_gates["morning_slow_physical_export_relief"])
        self.assertFalse(decision.trace_gates["morning_slow_charge_relief_active"])
        self.assertTrue(decision.trace_gates["morning_slow_refill_timing_evidence_trusted"])
        self.assertTrue(decision.trace_gates["morning_slow_refill_timing_feasible"])
        self.assertGreaterEqual(
            decision.trace_values["morning_slow_safe_timed_charge_opportunity_kwh"],
            decision.trace_values["morning_slow_refill_need_kwh"],
        )
        expected_deadline = state.next_sunset_ts - 3600.0
        self.assertEqual(
            expected_deadline,
            decision.trace_values["morning_slow_refill_deadline_ts"],
        )
        self.assertGreater(expected_deadline, self.SLOW_END.timestamp())

    def test_aggregate_energy_pass_can_fail_timed_refill_and_release_only_charge_cap(
        self,
    ) -> None:
        optimizer = self._optimizer()
        state = self._morning_state(
            optimizer,
            before_slow_end_pv_kw=20.0,
            after_slow_end_pv_kw=0.5,
            aggregate_remaining_kwh=100.0,
        )

        decision = self.decide(optimizer, state, self.MORNING)

        aggregate_requirement_kwh = (
            10.0
            + 8.0 * optimizer.cfg.morning_slow_charge_base_load_kw
        ) * optimizer.cfg.forecast_safety_charging
        self.assertGreater(state.forecast_remaining_kwh, aggregate_requirement_kwh)
        self.assertTrue(decision.trace_gates["morning_slow_refill_timing_evidence_trusted"])
        self.assertFalse(decision.trace_gates["morning_slow_refill_timing_feasible"])
        self.assertTrue(decision.trace_gates["morning_slow_forecast_refill_relief"])
        self.assertFalse(decision.trace_gates["morning_slow_physical_export_relief"])
        self.assertTrue(decision.trace_gates["morning_slow_charge_relief_active"])
        self.assertLess(
            decision.trace_values["morning_slow_safe_timed_charge_opportunity_kwh"],
            decision.trace_values["morning_slow_refill_need_kwh"],
        )
        self._assert_morning_slow_contract(
            optimizer,
            decision,
            expected_charge_limit_kw=10.0,
        )

    def test_normal_post_morning_slow_capability_counts_toward_refill(self) -> None:
        fill_need_kwh = 14.0
        optimizer = self._optimizer()
        state = self._morning_state(
            optimizer,
            fill_need_kwh=fill_need_kwh,
            before_slow_end_pv_kw=0.5,
            after_slow_end_pv_kw=4.0,
        )

        decision = self.decide(optimizer, state, self.MORNING)

        all_day_slow_safe_kwh = (
            6.0 * optimizer.cfg.morning_slow_charge_rate_kw
            / optimizer.cfg.forecast_safety_charging
        )
        self.assertLess(all_day_slow_safe_kwh, fill_need_kwh)
        self.assertTrue(decision.trace_gates["morning_slow_refill_timing_feasible"])
        self.assertFalse(decision.trace_gates["morning_slow_forecast_refill_relief"])
        self._assert_morning_slow_contract(
            optimizer,
            decision,
            expected_charge_limit_kw=2.0,
        )

    def test_refill_relief_is_not_authorized_without_greater_charge_opportunity(
        self,
    ) -> None:
        optimizer = self._optimizer()
        state = self._morning_state(
            optimizer,
            before_slow_end_pv_kw=0.5,
            after_slow_end_pv_kw=0.5,
            aggregate_remaining_kwh=100.0,
        )

        decision = self.decide(optimizer, state, self.MORNING)

        self.assertTrue(decision.trace_gates["morning_slow_refill_timing_evidence_trusted"])
        self.assertFalse(decision.trace_gates["morning_slow_refill_timing_feasible"])
        self.assertFalse(decision.trace_gates["morning_slow_refill_normal_only_feasible"])
        self.assertGreater(
            decision.trace_values["morning_slow_normal_charge_capability_kw"],
            decision.trace_values["morning_slow_slow_charge_capability_kw"],
        )
        self.assertEqual(
            decision.trace_values[
                "morning_slow_normal_only_safe_timed_charge_opportunity_kwh"
            ],
            decision.trace_values["morning_slow_safe_timed_charge_opportunity_kwh"],
        )
        self.assertFalse(decision.trace_gates["morning_slow_forecast_refill_relief"])
        self.assertFalse(decision.trace_gates["morning_slow_charge_relief_active"])
        self.assertEqual(2.0, decision.ess_charge_limit)

    def test_refill_relief_releases_slow_cap_even_when_normal_cannot_fully_refill(
        self,
    ) -> None:
        optimizer = self._optimizer()
        state = self._morning_state(
            optimizer,
            fill_need_kwh=25.0,
            before_slow_end_pv_kw=20.0,
            after_slow_end_pv_kw=0.5,
            aggregate_remaining_kwh=100.0,
        )

        decision = self.decide(optimizer, state, self.MORNING)

        self.assertTrue(decision.trace_gates["morning_slow_refill_timing_evidence_trusted"])
        self.assertFalse(decision.trace_gates["morning_slow_refill_timing_feasible"])
        self.assertFalse(decision.trace_gates["morning_slow_refill_normal_only_feasible"])
        self.assertGreater(
            decision.trace_values["morning_slow_normal_charge_capability_kw"],
            decision.trace_values["morning_slow_slow_charge_capability_kw"],
        )
        self.assertGreater(
            decision.trace_values[
                "morning_slow_normal_only_safe_timed_charge_opportunity_kwh"
            ],
            decision.trace_values["morning_slow_safe_timed_charge_opportunity_kwh"],
        )
        self.assertTrue(decision.trace_gates["morning_slow_forecast_refill_relief"])
        self.assertFalse(decision.trace_gates["morning_slow_physical_export_relief"])
        self.assertTrue(decision.trace_gates["morning_slow_charge_relief_active"])
        self.assertEqual(
            "refill_infeasible_even_at_normal_capability",
            decision.trace_values["morning_slow_refill_timing_reason"],
        )
        self._assert_morning_slow_contract(
            optimizer,
            decision,
            expected_charge_limit_kw=10.0,
        )

    def test_missing_untrusted_or_gapped_detail_cannot_authorize_refill_relief(self) -> None:
        cases = (
            ("missing", True, "missing"),
            ("stale_or_untrusted", False, "continuous"),
            ("gapped", True, "gapped"),
        )
        for name, source_trusted, shape in cases:
            with self.subTest(case=name):
                optimizer = self._optimizer()
                state = self._morning_state(
                    optimizer,
                    before_slow_end_pv_kw=20.0,
                    after_slow_end_pv_kw=0.5,
                    detailed_source_trusted=source_trusted,
                    detailed_shape=shape,
                )

                decision = self.decide(optimizer, state, self.MORNING)

                self.assertTrue(decision.morning_slow_charge_active)
                self.assertFalse(
                    decision.trace_gates["morning_slow_refill_timing_evidence_trusted"]
                )
                self.assertFalse(
                    decision.trace_gates["morning_slow_forecast_refill_relief"]
                )
                self.assertFalse(decision.trace_gates["morning_slow_charge_relief_active"])
                self.assertEqual(2.0, decision.ess_charge_limit)
                self.assertTrue(decision.trace_values["morning_slow_relief_reason"])

    def test_untrusted_capacity_or_available_energy_never_authorizes_refill_relief(
        self,
    ) -> None:
        for trust_override in (
            {"capacity_trusted": False},
            {"available_energy_trusted": False},
        ):
            with self.subTest(**trust_override):
                optimizer = self._optimizer()
                state = self._morning_state(
                    optimizer,
                    before_slow_end_pv_kw=20.0,
                    after_slow_end_pv_kw=0.5,
                    **trust_override,
                )

                decision = self.decide(optimizer, state, self.MORNING)

                self.assertFalse(
                    decision.trace_gates["morning_slow_forecast_refill_relief"]
                )
                self.assertFalse(decision.trace_gates["morning_slow_charge_relief_active"])

    def test_physical_relief_is_disabled_when_threshold_configuration_is_zero(self) -> None:
        optimizer = self._optimizer(
            grid_connection_export_limit_kw=0.0,
            morning_slow_physical_export_headroom_kw=0.0,
        )
        state = self._morning_state(
            optimizer,
            grid_export_kw=20.0,
            battery_charge_kw=2.0,
        )

        decision = self.decide(optimizer, state, self.MORNING)

        self.assertFalse(
            decision.trace_gates["morning_slow_physical_export_configured"]
        )
        self.assertFalse(decision.trace_gates["morning_slow_physical_export_relief"])
        self.assertEqual(2.0, decision.ess_charge_limit)

    def test_physical_entry_uses_trusted_actual_export_and_inclusive_threshold(self) -> None:
        cases = (
            ("below", 14.49, False, 2.0),
            ("at", 14.5, True, 10.0),
            ("above", 14.51, True, 10.0),
        )
        for name, export_kw, expected_relief, expected_charge_limit in cases:
            with self.subTest(case=name):
                optimizer = self._optimizer()
                state = self._morning_state(
                    optimizer,
                    grid_export_kw=export_kw,
                    battery_charge_kw=2.0,
                )

                decision = self.decide(optimizer, state, self.MORNING)

                self.assertEqual(
                    14.5,
                    decision.trace_values["morning_slow_physical_relief_threshold_kw"],
                )
                self.assertTrue(
                    decision.trace_gates["morning_slow_physical_export_flow_trusted"]
                )
                self.assertEqual(
                    expected_relief,
                    decision.trace_gates["morning_slow_physical_export_relief"],
                )
                self.assertEqual(
                    expected_relief,
                    decision.trace_gates["morning_slow_charge_relief_active"],
                )
                self._assert_morning_slow_contract(
                    optimizer,
                    decision,
                    expected_charge_limit_kw=expected_charge_limit,
                )

    def test_live_physical_relief_requires_coherent_derived_flow(self) -> None:
        optimizer = self._optimizer()
        state = self._morning_state(
            optimizer,
            grid_export_kw=15.0,
            battery_charge_kw=2.0,
            derived_power_flow_coherent=False,
        )

        decision = self.decide(optimizer, state, self.MORNING)

        self.assertFalse(
            decision.trace_gates["morning_slow_physical_export_flow_trusted"]
        )
        self.assertFalse(decision.trace_gates["morning_slow_physical_export_relief"])
        self.assertFalse(decision.trace_gates["morning_slow_charge_relief_active"])
        self.assertEqual(
            "physical_export_flow_untrusted",
            decision.trace_values["morning_slow_physical_export_reason"],
        )
        self.assertIsNone(decision.trace_values["morning_slow_actual_grid_export_kw"])
        self.assertIsNone(
            decision.trace_values["morning_slow_actual_battery_charge_kw"]
        )
        self.assertEqual(2.0, decision.ess_charge_limit)

    def test_live_physical_relief_uses_coherent_flow_over_direct_battery_reading(
        self,
    ) -> None:
        optimizer = self._optimizer()
        state = self._morning_state(
            optimizer,
            grid_export_kw=8.0,
            battery_charge_kw=2.0,
        )
        state.hvac_solar_inputs = self._flow_inputs(
            pv_kw=19.0,
            load_kw=1.0,
            battery_charge_kw=2.0,
            grid_export_kw=8.0,
        )

        decision = self.decide(optimizer, state, self.MORNING)

        self.assertTrue(
            decision.trace_gates["morning_slow_physical_export_flow_trusted"]
        )
        self.assertEqual(
            "coherent_measured_grid_flow",
            decision.trace_values["morning_slow_actual_grid_export_source"],
        )
        self.assertEqual(
            "coherent_measured_grid_flow",
            decision.trace_values["morning_slow_actual_battery_charge_source"],
        )
        self.assertEqual(
            10.0,
            decision.trace_values["morning_slow_actual_battery_charge_kw"],
        )
        self.assertEqual(
            16.0,
            decision.trace_values[
                "morning_slow_estimated_export_if_slow_cap_restored_kw"
            ],
        )
        self.assertTrue(decision.trace_gates["morning_slow_physical_export_relief"])
        self._assert_morning_slow_contract(
            optimizer,
            decision,
            expected_charge_limit_kw=10.0,
        )

    def test_counterfactual_restoration_prevents_chatter_then_clears_below_threshold(
        self,
    ) -> None:
        optimizer = self._optimizer()
        entry_state = self._morning_state(
            optimizer,
            grid_export_kw=15.0,
            battery_charge_kw=2.0,
        )
        entry = self.decide(optimizer, entry_state, self.MORNING)
        self.assertTrue(entry.trace_gates["morning_slow_physical_export_relief"])
        optimizer._last_state = entry_state
        optimizer._last_decision = entry

        unsafe_restore_state = self._morning_state(
            optimizer,
            grid_export_kw=8.0,
            battery_charge_kw=10.0,
        )
        unsafe_restore = self.decide(optimizer, unsafe_restore_state, self.MORNING)
        self.assertEqual(
            16.0,
            unsafe_restore.trace_values[
                "morning_slow_estimated_export_if_slow_cap_restored_kw"
            ],
        )
        self.assertTrue(
            unsafe_restore.trace_gates["morning_slow_physical_export_relief"]
        )
        self.assertEqual(10.0, unsafe_restore.ess_charge_limit)
        optimizer._last_state = unsafe_restore_state
        optimizer._last_decision = unsafe_restore

        exact_boundary_state = self._morning_state(
            optimizer,
            grid_export_kw=8.5,
            battery_charge_kw=8.0,
        )
        exact_boundary = self.decide(optimizer, exact_boundary_state, self.MORNING)
        self.assertEqual(
            14.5,
            exact_boundary.trace_values[
                "morning_slow_estimated_export_if_slow_cap_restored_kw"
            ],
        )
        self.assertTrue(exact_boundary.trace_gates["morning_slow_physical_export_relief"])
        optimizer._last_state = exact_boundary_state
        optimizer._last_decision = exact_boundary

        safe_restore_state = self._morning_state(
            optimizer,
            grid_export_kw=7.0,
            battery_charge_kw=5.0,
        )
        safe_restore = self.decide(optimizer, safe_restore_state, self.MORNING)
        self.assertEqual(
            10.0,
            safe_restore.trace_values[
                "morning_slow_estimated_export_if_slow_cap_restored_kw"
            ],
        )
        self.assertFalse(safe_restore.trace_gates["morning_slow_physical_export_relief"])
        self.assertFalse(safe_restore.trace_gates["morning_slow_charge_relief_active"])
        self.assertEqual(2.0, safe_restore.ess_charge_limit)

    def test_restart_reconstructs_relief_from_current_counterfactual_flow(self) -> None:
        optimizer = self._optimizer()
        self.assertIsNone(optimizer.last_decision)
        state = self._morning_state(
            optimizer,
            grid_export_kw=8.0,
            battery_charge_kw=10.0,
        )

        decision = self.decide(optimizer, state, self.MORNING)

        self.assertEqual(
            16.0,
            decision.trace_values[
                "morning_slow_estimated_export_if_slow_cap_restored_kw"
            ],
        )
        self.assertTrue(decision.trace_gates["morning_slow_physical_export_relief"])
        self.assertTrue(decision.trace_gates["morning_slow_charge_relief_active"])
        self.assertEqual(10.0, decision.ess_charge_limit)

    def test_untrusted_export_or_battery_flow_cannot_newly_activate_physical_relief(
        self,
    ) -> None:
        cases = (
            ("export_stale", False, True),
            ("battery_stale", True, False),
        )
        for name, export_fresh, battery_fresh in cases:
            with self.subTest(case=name):
                optimizer = self._optimizer()
                state = self._morning_state(
                    optimizer,
                    grid_export_kw=15.0,
                    battery_charge_kw=2.0,
                    export_fresh=export_fresh,
                    battery_fresh=battery_fresh,
                    derived_power_flow_coherent=battery_fresh,
                )

                decision = self.decide(optimizer, state, self.MORNING)

                self.assertFalse(
                    decision.trace_gates["morning_slow_physical_export_flow_trusted"]
                )
                self.assertFalse(
                    decision.trace_gates["morning_slow_physical_export_relief"]
                )
                self.assertFalse(decision.trace_gates["morning_slow_charge_relief_active"])
                self.assertEqual(2.0, decision.ess_charge_limit)

    def test_forecast_and_physical_relief_reasons_combine_with_or_semantics(self) -> None:
        cases = (
            ("neither", False, False),
            ("forecast_only", True, False),
            ("physical_only", False, True),
            ("both", True, True),
        )
        for name, forecast_relief, physical_relief in cases:
            with self.subTest(case=name):
                optimizer = self._optimizer()
                state = self._morning_state(
                    optimizer,
                    before_slow_end_pv_kw=20.0 if forecast_relief else 4.0,
                    after_slow_end_pv_kw=0.5 if forecast_relief else 4.0,
                    grid_export_kw=15.0 if physical_relief else 8.0,
                    battery_charge_kw=2.0,
                )

                decision = self.decide(optimizer, state, self.MORNING)

                self.assertEqual(
                    forecast_relief,
                    decision.trace_gates["morning_slow_forecast_refill_relief"],
                )
                self.assertEqual(
                    physical_relief,
                    decision.trace_gates["morning_slow_physical_export_relief"],
                )
                self.assertEqual(
                    forecast_relief or physical_relief,
                    decision.trace_gates["morning_slow_charge_relief_active"],
                )
                self.assertEqual(
                    10.0 if forecast_relief or physical_relief else 2.0,
                    decision.ess_charge_limit,
                )

    def test_negative_price_charge_owner_still_has_priority_over_morning_slow(self) -> None:
        optimizer = self._optimizer()
        state = self._morning_state(
            optimizer,
            before_slow_end_pv_kw=20.0,
            after_slow_end_pv_kw=0.5,
            grid_export_kw=15.0,
            current_price=-0.05,
            current_price_cents=-5.0,
            price_is_actual=True,
        )

        decision = self.decide(optimizer, state, self.MORNING)

        self.assertEqual(MODE_CMD_CHARGE_GRID, decision.ems_mode)
        self.assertEqual(10.0, decision.import_limit)
        self.assertEqual(10.0, decision.ess_charge_limit)
        self.assertEqual("negative_price_import", decision.trace_values["import_branch"])
        self.assertEqual("none", decision.trace_values["battery_export_owner"])

    def test_demand_window_keeps_import_ownership_during_charge_relief(self) -> None:
        optimizer = self._optimizer()
        state = self._morning_state(
            optimizer,
            grid_export_kw=15.0,
            demand_window_active=True,
            demand_window_observed=True,
        )

        decision = self.decide(optimizer, state, self.MORNING)

        self.assertTrue(decision.trace_gates["morning_slow_physical_export_relief"])
        self.assertTrue(decision.trace_gates["trusted_demand_window_active"])
        self.assertEqual(0.0, decision.import_limit)
        self.assertEqual("demand_window_block", decision.trace_values["import_branch"])
        self.assertEqual("none", decision.trace_values["battery_export_owner"])

    def test_morning_dump_with_feasible_piecewise_refill_remains_deliberate_export(
        self,
    ) -> None:
        optimizer = self._optimizer(
            morning_dump_enabled=True,
            morning_dump_min_soc=15.0,
        )
        state = self._dump_state(optimizer)

        decision = self.decide(optimizer, state, self.DUMP_TIME)

        self.assertTrue(decision.morning_dump_active)
        self.assertTrue(decision.trace_gates["morning_dump_active"])
        self.assertEqual(BATTERY_EXPORT, decision.export_intent)
        self.assertEqual("morning_dump", decision.trace_values["battery_export_owner"])
        self.assertEqual("morning_dump", decision.trace_values["export_branch"])
        self.assertEqual(MODE_CMD_DISCHARGE_PV, decision.ems_mode)

    def test_morning_dump_stops_when_timed_refill_is_infeasible(self) -> None:
        optimizer = self._optimizer(
            morning_dump_enabled=True,
            morning_dump_min_soc=15.0,
        )
        state = self._dump_state(
            optimizer,
            before_slow_end_pv_kw=20.0,
            after_slow_end_pv_kw=0.5,
        )

        decision = self.decide(optimizer, state, self.DUMP_TIME)

        self.assertFalse(decision.morning_dump_active)
        self.assertFalse(decision.trace_gates["morning_dump_active"])
        self.assertNotEqual(BATTERY_EXPORT, decision.export_intent)
        self.assertNotEqual("morning_dump", decision.trace_values["battery_export_owner"])

    def test_morning_dump_models_future_slow_cap_without_assuming_future_relief(self) -> None:
        state_kwargs = {
            "before_slow_end_pv_kw": 20.0,
            "after_slow_end_pv_kw": 0.5,
        }
        slow_optimizer = self._optimizer(
            morning_dump_enabled=True,
            morning_dump_min_soc=15.0,
        )
        slow_state = self._dump_state(slow_optimizer, **state_kwargs)
        slow_decision = self.decide(slow_optimizer, slow_state, self.DUMP_TIME)

        unrestricted_optimizer = self._optimizer(
            morning_dump_enabled=True,
            morning_dump_min_soc=15.0,
            morning_slow_charge_enabled=False,
        )
        unrestricted_state = self._dump_state(unrestricted_optimizer, **state_kwargs)
        unrestricted_decision = self.decide(
            unrestricted_optimizer,
            unrestricted_state,
            self.DUMP_TIME,
        )

        self.assertFalse(slow_decision.morning_dump_active)
        self.assertTrue(unrestricted_decision.morning_dump_active)
        self.assertEqual(BATTERY_EXPORT, unrestricted_decision.export_intent)
        self.assertEqual(
            "morning_dump",
            unrestricted_decision.trace_values["battery_export_owner"],
        )

    def test_morning_dump_hard_floor_is_preserved(self) -> None:
        optimizer = self._optimizer(
            morning_dump_enabled=True,
            morning_dump_min_soc=15.0,
        )
        state = self._dump_state(
            optimizer,
            fill_need_kwh=2.0,
            battery_soc=15.0,
        )

        decision = self.decide(optimizer, state, self.DUMP_TIME)

        self.assertFalse(decision.morning_dump_active)
        self.assertNotEqual(BATTERY_EXPORT, decision.export_intent)
        self.assertNotEqual("morning_dump", decision.trace_values["battery_export_owner"])

    def test_morning_dump_fails_closed_when_refill_evidence_is_untrusted(self) -> None:
        cases = (
            {"detailed_source_trusted": False},
            {"capacity_trusted": False},
            {"available_energy_trusted": False},
        )
        for trust_override in cases:
            with self.subTest(**trust_override):
                optimizer = self._optimizer(
                    morning_dump_enabled=True,
                    morning_dump_min_soc=15.0,
                )
                state = self._dump_state(optimizer, **trust_override)

                decision = self.decide(optimizer, state, self.DUMP_TIME)

                self.assertFalse(decision.morning_dump_active)
                self.assertFalse(decision.trace_gates["morning_dump_active"])
                self.assertNotEqual(BATTERY_EXPORT, decision.export_intent)
                self.assertNotEqual(
                    "morning_dump",
                    decision.trace_values["battery_export_owner"],
                )
