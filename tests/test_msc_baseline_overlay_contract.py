from __future__ import annotations

import asyncio
import unittest
from datetime import datetime, timedelta

from app.optimizer import (
    DISCHARGE_MODES,
    MODE_CMD_CHARGE_GRID,
    MODE_CMD_DISCHARGE_PV,
    MODE_MAX_SELF,
)
from haos49_characterization_helpers import (
    Haos49CharacterizationCase,
    RecordingHA,
)


class ScriptedReadbackHA(RecordingHA):
    """Recording double whose service success and later readback are independent."""

    def __init__(self, readbacks: dict[str, list[object]]) -> None:
        super().__init__(settle_numbers=False, settle_selects=False)
        self._readbacks = {entity_id: list(values) for entity_id, values in readbacks.items()}

    async def get_state_value(self, entity_id: str, default: object = "") -> object:
        self.calls.append(("get_state_value", entity_id, default))
        queued = self._readbacks.get(entity_id, [])
        if queued:
            observed = queued.pop(0)
            self.state_values[entity_id] = observed
            return observed
        return self.state_values.get(entity_id, default)


class MscBaselineOverlayContractTests(Haos49CharacterizationCase):
    """Future MSC baseline; current haos53 is expected to fail architecture cases."""

    def assert_contract_outputs(
        self,
        decision,
        expected: tuple[str, float, float, float],
    ) -> None:
        self.assertEqual(
            expected,
            (
                decision.ems_mode,
                decision.export_limit,
                decision.import_limit,
                decision.pv_max_power_limit,
            ),
        )

    def assert_msc_surplus_permission(
        self,
        decision,
        *,
        export_ceiling: float,
    ) -> None:
        """Assert that an open ceiling is PV permission, not discharge intent."""
        self.assert_contract_outputs(
            decision,
            (MODE_MAX_SELF, export_ceiling, 0.0, 25.0),
        )
        self.assertGreater(decision.export_limit, 0.01)
        self.assertNotIn(decision.ems_mode, DISCHARGE_MODES)
        self.assertEqual(
            "pv_surplus_only",
            decision.trace_values.get("export_value_gate_export_type"),
        )

    def _ordinary_state(self, battery_soc: float, **overrides: object):
        values: dict[str, object] = {
            "battery_soc": battery_soc,
            "available_discharge_energy_kwh": 30.0 * battery_soc / 100.0,
            "battery_power_sensor_kw": 0.0,
            "feedin_price": 0.15,
            "feedin_price_cents": 15.0,
            "pv_kw": 4.0,
            "solar_power_now_kw": 4.0,
            "load_kw": 1.0,
            "current_ems_mode": MODE_MAX_SELF,
            "ems_mode_observed": True,
            "current_export_limit": 0.01,
            "grid_export_power_kw": 0.0,
        }
        values.update(overrides)
        return self.state(self.FIXED_AFTERNOON, **values)

    def _full_opportunity(self, **overrides: object):
        values: dict[str, object] = {
            "battery_soc": 100.0,
            "available_discharge_energy_kwh": 30.0,
            "battery_power_sensor_kw": 0.0,
            "feedin_price": 0.15,
            "feedin_price_cents": 15.0,
            "pv_kw": 6.0,
            "solar_power_now_kw": 6.0,
            "load_kw": 1.0,
            "current_export_limit": 0.01,
        }
        values.update(overrides)
        return self.state(self.FIXED_AFTERNOON, **values)

    def _poor_forecast_ordinary_surplus(self, battery_soc: float):
        return self._ordinary_state(
            battery_soc,
            feedin_price=0.12,
            feedin_price_cents=12.0,
            pv_kw=8.2,
            solar_power_now_kw=8.2,
            load_kw=1.0,
            forecast_remaining_kwh=1.0,
            forecast_today_kwh=1.0,
            forecast_tomorrow_kwh=5.0,
            current_ems_mode=MODE_MAX_SELF,
            ems_mode_observed=True,
            current_export_limit=0.01,
        )

    def _assert_normal_baseline(self, battery_soc: float) -> None:
        optimizer = self.optimizer()
        state = self._ordinary_state(battery_soc)

        decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

        self.assert_msc_surplus_permission(
            decision,
            export_ceiling=25.0,
        )
        self.assertEqual(0.0, state.grid_export_power_kw)

    def test_normal_msc_baseline_at_low_soc(self) -> None:
        self._assert_normal_baseline(20.0)

    def test_normal_msc_baseline_at_medium_soc(self) -> None:
        self._assert_normal_baseline(60.0)

    def test_normal_msc_baseline_at_high_soc(self) -> None:
        self._assert_normal_baseline(95.0)

    def test_normal_msc_baseline_at_full_soc(self) -> None:
        self._assert_normal_baseline(100.0)

    def test_normal_msc_baseline_uses_configured_high_ceiling(self) -> None:
        optimizer = self.optimizer(export_limit_high=18.0)
        state = self._ordinary_state(60.0)

        decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

        self.assert_msc_surplus_permission(
            decision,
            export_ceiling=18.0,
        )

    def test_poor_forecast_ordinary_surplus_has_no_100_percent_discontinuity(
        self,
    ) -> None:
        for battery_soc in (95.7, 100.0):
            with self.subTest(battery_soc=battery_soc):
                optimizer = self.optimizer()
                state = self._poor_forecast_ordinary_surplus(battery_soc)

                decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

                self.assertTrue(state.sigenergy_mode_observed)
                self.assertTrue(state.ems_mode_observed)
                self.assertTrue(
                    bool(decision.trace_gates.get("observed_automated_control_mode"))
                )
                self.assertEqual(
                    battery_soc == 100.0,
                    bool(decision.trace_gates.get("topoff_target_met")),
                )
                for gate in (
                    "morning_dump_active",
                    "morning_slow_charge_active",
                    "evening_export_boost_active",
                    "export_spike_active",
                    "positive_fit_override",
                    "solar_surplus_bypass",
                    "export_solar_override",
                ):
                    self.assertFalse(bool(decision.trace_gates.get(gate)), gate)
                self.assert_msc_surplus_permission(
                    decision,
                    export_ceiling=optimizer.cfg.export_limit_high,
                )
                self.assertGreater(
                    decision.export_limit,
                    state.pv_kw - state.load_kw,
                    "The high value is a ceiling; MSC, not the ceiling, controls dispatch.",
                )

    def test_cheap_fit_at_99_9_percent_preserves_fixed_topoff_contract(self) -> None:
        optimizer = self.optimizer()
        state = self._full_opportunity(
            battery_soc=99.9,
            available_discharge_energy_kwh=29.97,
            feedin_price=0.095,
            feedin_price_cents=9.5,
            battery_power_sensor_kw=0.0,
            current_ems_mode=MODE_MAX_SELF,
            ems_mode_observed=True,
            current_export_limit=0.01,
        )

        decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

        self.assert_contract_outputs(
            decision,
            (MODE_MAX_SELF, 0.0, 0.0, 25.0),
        )
        self.assertNotIn(decision.ems_mode, DISCHARGE_MODES)
        self.assertEqual(0.0, decision.trace_values.get("export_tier_limit"))
        self.assertFalse(bool(decision.trace_gates.get("topoff_target_met")))
        self.assertFalse(
            bool(decision.trace_gates.get("pv_only_msc_high_ceiling_active"))
        )
        self.assertFalse(decision.requires_verified_msc_before_export)

    def test_cheap_fit_at_100_percent_uses_only_verified_msc_stage_2(self) -> None:
        optimizer = self.optimizer()
        state = self._full_opportunity(
            battery_soc=100.0,
            available_discharge_energy_kwh=30.0,
            feedin_price=0.095,
            feedin_price_cents=9.5,
            battery_power_sensor_kw=0.0,
            current_ems_mode=MODE_MAX_SELF,
            ems_mode_observed=True,
            current_export_limit=0.01,
        )

        decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

        self.assertEqual(0.0, decision.trace_values.get("export_tier_limit"))
        self.assertTrue(bool(decision.trace_gates.get("topoff_target_met")))
        self.assertTrue(bool(decision.trace_gates.get("pv_only_discharge_ok")))
        self.assertTrue(
            bool(decision.trace_gates.get("pv_only_msc_high_ceiling_active"))
        )
        self.assertEqual(
            "msc_full_battery_high_ceiling",
            decision.trace_values.get("pv_surplus_initiation_source"),
        )
        self.assert_msc_surplus_permission(
            decision,
            export_ceiling=optimizer.cfg.export_limit_high,
        )
        self.assertTrue(decision.requires_verified_msc_before_export)

    def test_cheap_fit_at_100_percent_closes_on_material_discharge(self) -> None:
        optimizer = self.optimizer()
        state = self._full_opportunity(
            battery_soc=100.0,
            available_discharge_energy_kwh=30.0,
            feedin_price=0.095,
            feedin_price_cents=9.5,
            battery_power_sensor_kw=-0.2,
            current_ems_mode=MODE_MAX_SELF,
            ems_mode_observed=True,
            current_export_limit=25.0,
        )

        decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

        self.assert_contract_outputs(
            decision,
            (MODE_MAX_SELF, 0.0, 0.0, 25.0),
        )
        self.assertNotIn(decision.ems_mode, DISCHARGE_MODES)
        self.assertEqual(0.0, decision.trace_values.get("export_tier_limit"))
        self.assertEqual(
            0.2,
            decision.trace_values.get("battery_discharge_kw_for_pv_only"),
        )
        self.assertEqual(
            0.1,
            decision.trace_values.get("pv_only_discharge_tolerance_kw"),
        )
        self.assertFalse(bool(decision.trace_gates.get("pv_only_discharge_ok")))
        self.assertFalse(
            bool(decision.trace_gates.get("pv_only_msc_high_ceiling_active"))
        )
        self.assertFalse(decision.requires_verified_msc_before_export)

    def test_unobserved_automated_mode_cannot_open_normal_ceiling(self) -> None:
        optimizer = self.optimizer()
        state = self._full_opportunity(
            sigenergy_mode=optimizer.cfg.automated_option,
            sigenergy_mode_observed=False,
            current_ems_mode=MODE_MAX_SELF,
            ems_mode_observed=True,
            current_export_limit=25.0,
        )

        decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

        self.assertLess(decision.export_limit, optimizer.cfg.export_limit_high)

    def test_unavailable_unknown_malformed_or_different_ems_closes_ceiling(self) -> None:
        cases = (
            "unavailable",
            "unknown",
            "malformed-mode",
            MODE_CMD_DISCHARGE_PV,
        )

        for raw_mode in cases:
            with self.subTest(raw_mode=raw_mode):
                ha = RecordingHA()
                optimizer = self.optimizer(ha)
                ha.states = {
                    optimizer.cfg.sigenergy_mode_select: {
                        "state": optimizer.cfg.automated_option,
                        "attributes": {},
                    },
                    optimizer.cfg.ems_mode_select: {
                        "state": raw_mode,
                        "attributes": {},
                    },
                }

                parsed = asyncio.run(optimizer._read_state())
                state = self._full_opportunity(
                    sigenergy_mode=parsed.sigenergy_mode,
                    sigenergy_mode_observed=parsed.sigenergy_mode_observed,
                    current_ems_mode=parsed.current_ems_mode,
                    ems_mode_observed=parsed.ems_mode_observed,
                    current_export_limit=25.0,
                )
                decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

                self.assertTrue(parsed.sigenergy_mode_observed)
                self.assertFalse(
                    parsed.ems_mode_observed
                    and parsed.current_ems_mode == MODE_MAX_SELF
                )
                self.assert_contract_outputs(
                    decision,
                    (MODE_MAX_SELF, 0.0, 0.0, 25.0),
                )

    def test_successful_msc_request_is_not_observation(self) -> None:
        ha = RecordingHA(settle_numbers=False, settle_selects=False)
        optimizer = self.optimizer(ha)
        ha.state_values = {
            optimizer.cfg.ems_mode_select: MODE_CMD_DISCHARGE_PV,
            optimizer.cfg.grid_export_limit: 0.01,
        }
        first_state = self._ordinary_state(
            95.7,
            current_ems_mode=MODE_CMD_DISCHARGE_PV,
            ems_mode_observed=True,
            current_export_limit=0.01,
        )
        first = self.decide(optimizer, first_state, self.FIXED_AFTERNOON)

        asyncio.run(optimizer._apply(first_state, first))

        self.assertIn(
            ("select_option", optimizer.cfg.ems_mode_select, MODE_MAX_SELF),
            ha.calls,
        )
        self.assertEqual(
            MODE_CMD_DISCHARGE_PV,
            ha.state_values[optimizer.cfg.ems_mode_select],
        )
        self.assertFalse(
            any(
                call[0] == "set_number"
                and call[1] == optimizer.cfg.grid_export_limit
                and float(call[2]) > 0.011
                for call in ha.calls
            )
        )
        optimizer._last_state = first_state
        optimizer._last_decision = first

        later_unverified = self._ordinary_state(
            95.7,
            current_ems_mode=MODE_CMD_DISCHARGE_PV,
            ems_mode_observed=True,
            current_export_limit=0.01,
        )
        second = self.decide(optimizer, later_unverified, self.FIXED_AFTERNOON)

        self.assert_contract_outputs(
            second,
            (MODE_MAX_SELF, 0.0, 0.0, 25.0),
        )

    def test_return_from_discharge_waits_for_observed_close_before_requesting_msc(
        self,
    ) -> None:
        ha = RecordingHA(settle_numbers=False, settle_selects=False)
        optimizer = self.optimizer(ha)
        ha.state_values = {
            optimizer.cfg.ems_mode_select: MODE_CMD_DISCHARGE_PV,
            optimizer.cfg.grid_export_limit: 12.0,
        }
        state = self._ordinary_state(
            95.7,
            current_ems_mode=MODE_CMD_DISCHARGE_PV,
            ems_mode_observed=True,
            current_export_limit=12.0,
        )
        decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

        self.assert_contract_outputs(
            decision,
            (MODE_MAX_SELF, 0.0, 0.0, 25.0),
        )
        asyncio.run(optimizer._apply(state, decision))

        close_call = ("set_number", optimizer.cfg.grid_export_limit, 0.01)
        msc_call = ("select_option", optimizer.cfg.ems_mode_select, MODE_MAX_SELF)
        self.assertIn(close_call, ha.calls)
        self.assertNotIn(msc_call, ha.calls)
        self.assertEqual(12.0, ha.state_values[optimizer.cfg.grid_export_limit])

    def test_exact_msc_does_not_reopen_before_export_is_observed_closed(self) -> None:
        ha = RecordingHA(settle_numbers=False, settle_selects=False)
        optimizer = self.optimizer(ha)
        ha.state_values = {
            optimizer.cfg.ems_mode_select: MODE_CMD_DISCHARGE_PV,
            optimizer.cfg.grid_export_limit: 12.0,
        }
        first_state = self._ordinary_state(
            95.7,
            current_ems_mode=MODE_CMD_DISCHARGE_PV,
            ems_mode_observed=True,
            current_export_limit=12.0,
        )
        first = self.decide(optimizer, first_state, self.FIXED_AFTERNOON)
        asyncio.run(optimizer._apply(first_state, first))
        optimizer._last_state = first_state
        optimizer._last_decision = first

        ha.state_values[optimizer.cfg.ems_mode_select] = MODE_MAX_SELF
        msc_but_still_open = self._ordinary_state(
            95.7,
            current_ems_mode=MODE_MAX_SELF,
            ems_mode_observed=True,
            current_export_limit=12.0,
        )
        second = self.decide(optimizer, msc_but_still_open, self.FIXED_AFTERNOON)

        self.assert_contract_outputs(
            second,
            (MODE_MAX_SELF, 0.0, 0.0, 25.0),
        )

    def test_later_exact_msc_after_observed_close_reopens_normal_ceiling(self) -> None:
        ha = RecordingHA(settle_numbers=False, settle_selects=False)
        optimizer = self.optimizer(ha)
        ha.state_values = {
            optimizer.cfg.ems_mode_select: MODE_CMD_DISCHARGE_PV,
            optimizer.cfg.grid_export_limit: 0.01,
        }
        first_state = self._ordinary_state(
            95.7,
            current_ems_mode=MODE_CMD_DISCHARGE_PV,
            ems_mode_observed=True,
            current_export_limit=0.01,
        )
        first = self.decide(optimizer, first_state, self.FIXED_AFTERNOON)
        asyncio.run(optimizer._apply(first_state, first))
        first_cycle_calls = list(ha.calls)
        optimizer._last_state = first_state
        optimizer._last_decision = first

        ha.state_values = {
            optimizer.cfg.ems_mode_select: MODE_MAX_SELF,
            optimizer.cfg.grid_export_limit: 0.01,
        }
        verified = self._ordinary_state(
            95.7,
            current_ems_mode=MODE_MAX_SELF,
            ems_mode_observed=True,
            current_export_limit=0.01,
        )
        second = self.decide(optimizer, verified, self.FIXED_AFTERNOON)

        self.assert_msc_surplus_permission(
            second,
            export_ceiling=25.0,
        )
        second_cycle_start = len(ha.calls)
        asyncio.run(optimizer._apply(verified, second))
        second_cycle_calls = ha.calls[second_cycle_start:]

        high_export_call = (
            "set_number",
            optimizer.cfg.grid_export_limit,
            25.0,
        )
        self.assertNotIn(high_export_call, first_cycle_calls)
        self.assertIn(high_export_call, second_cycle_calls)
        high_export_index = second_cycle_calls.index(high_export_call)
        self.assertTrue(
            any(
                call[0] == "get_state_value"
                and call[1] == optimizer.cfg.ems_mode_select
                and index < high_export_index
                for index, call in enumerate(second_cycle_calls)
            )
        )

    def test_deliberate_export_target_settles_before_discharge_mode(self) -> None:
        ha = ScriptedReadbackHA({})
        optimizer = self.optimizer(ha)
        ha._readbacks[optimizer.cfg.grid_export_limit] = [12.0]
        ha.state_values = {
            optimizer.cfg.ems_mode_select: MODE_MAX_SELF,
            optimizer.cfg.grid_export_limit: 25.0,
        }
        state = self.state(
            self.FIXED_AFTERNOON,
            battery_soc=95.0,
            available_discharge_energy_kwh=28.5,
            battery_power_sensor_kw=-0.2,
            feedin_price=1.10,
            feedin_price_cents=110.0,
            pv_kw=0.0,
            solar_power_now_kw=0.0,
            load_kw=0.0,
            ess_max_discharge_kw=12.0,
            current_export_limit=25.0,
            current_ems_mode=MODE_MAX_SELF,
        )
        decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

        self.assert_contract_outputs(
            decision,
            (MODE_CMD_DISCHARGE_PV, 12.0, 0.0, 25.0),
        )
        asyncio.run(optimizer._apply(state, decision))

        export_call = ("set_number", optimizer.cfg.grid_export_limit, 12.0)
        mode_call = (
            "select_option",
            optimizer.cfg.ems_mode_select,
            MODE_CMD_DISCHARGE_PV,
        )
        export_index = ha.calls.index(export_call)
        mode_index = ha.calls.index(mode_call)
        self.assertTrue(
            any(
                call[0] == "get_state_value"
                and call[1] == optimizer.cfg.grid_export_limit
                and export_index < index < mode_index
                for index, call in enumerate(ha.calls)
            )
        )

    def test_reserve_and_forecast_guards_block_deliberate_battery_export(
        self,
    ) -> None:
        cases = (
            (
                "reserve_floor",
                {
                    "battery_soc": 20.0,
                    "available_discharge_energy_kwh": 6.0,
                    "forecast_remaining_kwh": 100.0,
                },
            ),
            (
                "insufficient_remaining_forecast",
                {
                    "battery_soc": 60.0,
                    "available_discharge_energy_kwh": 18.0,
                    "forecast_remaining_kwh": 1.0,
                },
            ),
        )
        for name, guarded_values in cases:
            with self.subTest(name=name):
                optimizer = self.optimizer()
                state = self.state(
                    self.FIXED_AFTERNOON,
                    battery_power_sensor_kw=-0.2,
                    feedin_price=1.10,
                    feedin_price_cents=110.0,
                    pv_kw=0.0,
                    solar_power_now_kw=0.0,
                    load_kw=1.0,
                    **guarded_values,
                )

                decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

                self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
                self.assertNotIn(decision.ems_mode, DISCHARGE_MODES)
                self.assertLessEqual(decision.export_limit, 0.01)

    def _assert_demand_window_baseline(self, pv_kw: float) -> None:
        when = datetime(2026, 1, 15, 17, 30)
        optimizer = self.optimizer()
        state = self.state(
            when,
            battery_soc=60.0,
            available_discharge_energy_kwh=18.0,
            battery_power_sensor_kw=0.0,
            current_price=0.30,
            current_price_cents=30.0,
            feedin_price=0.15,
            feedin_price_cents=15.0,
            pv_kw=pv_kw,
            solar_power_now_kw=pv_kw,
            load_kw=1.0,
            current_ems_mode=MODE_MAX_SELF,
            ems_mode_observed=True,
            current_export_limit=0.01,
            demand_window_active=True,
        )

        decision = self.decide(optimizer, state, when)

        self.assert_msc_surplus_permission(
            decision,
            export_ceiling=25.0,
        )

    def test_demand_window_with_little_pv_blocks_only_import(self) -> None:
        self._assert_demand_window_baseline(0.2)

    def test_demand_window_with_strong_pv_blocks_only_import(self) -> None:
        self._assert_demand_window_baseline(5.0)

    def test_import_overlay_policy_remains_independent_of_msc_baseline(self) -> None:
        optimizer = self.optimizer()
        state = self.state(
            self.FIXED_AFTERNOON,
            battery_soc=30.0,
            available_discharge_energy_kwh=9.0,
            current_price=-0.35,
            current_price_cents=-35.0,
            price_is_actual=True,
            feedin_price=0.0,
            feedin_price_cents=0.0,
            pv_kw=0.0,
            solar_power_now_kw=0.0,
            load_kw=1.0,
            forecast_remaining_kwh=0.0,
        )

        decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

        self.assertEqual(MODE_CMD_CHARGE_GRID, decision.ems_mode)
        self.assertEqual(25.0, decision.import_limit)
        self.assertEqual(0.0, decision.export_limit)
        self.assertNotIn(decision.ems_mode, DISCHARGE_MODES)

    def test_negative_or_below_minimum_fit_closes_export_without_discharge(self) -> None:
        for fit, fit_cents in ((-0.01, -1.0), (0.009, 0.9)):
            with self.subTest(fit_cents=fit_cents):
                optimizer = self.optimizer()
                state = self._full_opportunity(
                    feedin_price=fit,
                    feedin_price_cents=fit_cents,
                    current_ems_mode=MODE_MAX_SELF,
                    ems_mode_observed=True,
                    current_export_limit=25.0,
                )

                decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

                self.assert_contract_outputs(
                    decision,
                    (MODE_MAX_SELF, 0.0, 0.0, 25.0),
                )

    def test_deliberate_export_contexts_remain_distinct_from_msc_baseline(
        self,
    ) -> None:
        morning_when = datetime(2026, 1, 15, 6, 0)
        morning_detail = [
            {
                "period_start": (morning_when + timedelta(hours=hours)).isoformat(),
                "pv_estimate": 10.0,
            }
            for hours in (3, 5, 7, 9, 11)
        ]
        morning_optimizer = self.optimizer(morning_dump_enabled=True)
        morning_state = self.state(
            morning_when,
            sun_above_horizon=False,
            battery_soc=80.0,
            available_discharge_energy_kwh=24.0,
            feedin_price=0.05,
            feedin_price_cents=5.0,
            load_kw=1.0,
            solcast_detailed=morning_detail,
        )

        evening_when = datetime(2026, 1, 15, 17, 30)
        evening_optimizer = self.optimizer(
            evening_boost_enabled=True,
            evening_boost_min_tomorrow_forecast_kwh=100.0,
        )
        evening_state = self.state(
            evening_when,
            battery_soc=80.0,
            available_discharge_energy_kwh=24.0,
            feedin_price=0.15,
            feedin_price_cents=15.0,
            load_kw=0.0,
            solcast_detailed=[
                {
                    "period_start": datetime(2026, 1, 15, 16, 0).isoformat(),
                    "pv_estimate": 2.0,
                }
            ],
            forecast_tomorrow_kwh=120.0,
        )

        spike_when = datetime(2026, 1, 15, 2, 0)
        spike_optimizer = self.optimizer(export_spike_threshold=0.60)
        spike_state = self.state(
            spike_when,
            sun_above_horizon=False,
            battery_soc=95.0,
            available_discharge_energy_kwh=28.5,
            battery_power_sensor_kw=-0.2,
            feedin_price=0.65,
            feedin_price_cents=65.0,
            price_spike_active=True,
            pv_kw=0.0,
            solar_power_now_kw=0.0,
            load_kw=1.0,
        )

        cases = (
            ("morning_dump", morning_optimizer, morning_state, morning_when),
            ("evening_boost", evening_optimizer, evening_state, evening_when),
            ("price_spike", spike_optimizer, spike_state, spike_when),
        )
        for name, optimizer, state, when in cases:
            with self.subTest(name=name):
                decision = self.decide(optimizer, state, when)

                self.assertEqual(MODE_CMD_DISCHARGE_PV, decision.ems_mode)
                self.assertGreater(decision.export_limit, 0.01)
                self.assertLessEqual(
                    decision.export_limit,
                    optimizer.cfg.export_limit_high,
                )


if __name__ == "__main__":
    unittest.main()
