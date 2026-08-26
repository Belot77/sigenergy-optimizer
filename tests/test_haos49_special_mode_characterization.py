from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from app.optimizer import MODE_CMD_DISCHARGE_PV, MODE_MAX_SELF
from haos49_characterization_helpers import Haos49CharacterizationCase


class Haos49SpecialModeCharacterizationTests(Haos49CharacterizationCase):
    def assert_outputs(
        self,
        decision,
        expected: tuple[str, float, float, float, float, float],
    ) -> None:
        self.assertEqual(
            expected,
            (
                decision.ems_mode,
                decision.export_limit,
                decision.import_limit,
                decision.pv_max_power_limit,
                decision.ess_charge_limit,
                decision.ess_discharge_limit,
            ),
        )

    def test_morning_dump_uses_full_deliberate_discharge_outputs(self) -> None:
        when = datetime(2026, 1, 15, 6, 0)
        optimizer = self.optimizer(morning_dump_enabled=True)
        optimizer._morning_dump_active = lambda *args, **kwargs: True
        state = self.state(
            when,
            sun_above_horizon=False,
            battery_soc=80.0,
            available_discharge_energy_kwh=24.0,
            feedin_price=0.05,
            feedin_price_cents=5.0,
            load_kw=1.0,
        )

        decision = self.decide(optimizer, state, when)

        self.assert_outputs(
            decision,
            (MODE_CMD_DISCHARGE_PV, 25.0, 0.0, 25.0, 25.0, 25.0),
        )
        self.assertTrue(decision.trace_gates["morning_dump_active"])
        self.assertEqual("morning_dump", decision.trace_values["export_branch"])
        self.assertEqual("morning_dump_block", decision.trace_values["import_branch"])
        self.assertEqual(25.0, decision.trace_values["morning_dump_limit"])

    def test_morning_dump_exit_recovers_to_closed_msc(self) -> None:
        when = datetime(2026, 1, 15, 6, 0)
        optimizer = self.optimizer(morning_dump_enabled=True)
        optimizer._morning_dump_active = lambda *args, **kwargs: False
        state = self.state(
            when,
            sun_above_horizon=False,
            battery_soc=80.0,
            available_discharge_energy_kwh=24.0,
            feedin_price=0.05,
            feedin_price_cents=5.0,
            current_ems_mode=MODE_CMD_DISCHARGE_PV,
            current_export_limit=25.0,
            load_kw=1.0,
        )

        decision = self.decide(optimizer, state, when)

        self.assert_outputs(decision, (MODE_MAX_SELF, 0.0, 0.0, 1.0, 25.0, 25.0))
        self.assertFalse(decision.trace_gates["morning_dump_active"])
        self.assertTrue(decision.trace_gates["battery_only_mode"])
        self.assertEqual("forecast_guard_block", decision.trace_values["export_branch"])
        self.assertEqual("blocked", decision.trace_values["import_branch"])

    def test_morning_slow_charge_ramps_export_and_limits_ess_charge(self) -> None:
        when = datetime(2026, 1, 15, 9, 0)
        optimizer = self.optimizer(
            morning_slow_charge_enabled=True,
            morning_slow_charge_rate_kw=2.0,
            morning_slow_export_ramp_up_step_kw=0.8,
        )
        optimizer._morning_slow_charge_active = lambda *args, **kwargs: True
        state = self.state(
            when,
            battery_soc=80.0,
            available_discharge_energy_kwh=24.0,
            feedin_price=0.15,
            feedin_price_cents=15.0,
            pv_kw=7.0,
            solar_power_now_kw=7.0,
            load_kw=1.0,
            current_export_limit=1.0,
            grid_export_power_kw=1.0,
        )

        decision = self.decide(optimizer, state, when)

        self.assert_outputs(
            decision,
            (MODE_CMD_DISCHARGE_PV, 1.8, 0.0, 25.0, 2.0, 25.0),
        )
        self.assertTrue(decision.trace_gates["morning_slow_charge_active"])
        self.assertEqual("morning_slow_charge", decision.trace_values["export_branch"])
        self.assertEqual("blocked", decision.trace_values["import_branch"])
        self.assertEqual(2.0, decision.trace_values["ess_charge_limit"])

    def test_morning_slow_exit_needs_fit_below_hysteresis_to_recover_msc(self) -> None:
        when = datetime(2026, 1, 15, 9, 0)
        cases = (
            ("same_fit", 0.15, 15.0, MODE_CMD_DISCHARGE_PV),
            ("below_hysteresis", 0.07, 7.0, MODE_MAX_SELF),
        )
        for name, fit, fit_cents, expected_mode in cases:
            with self.subTest(name=name):
                optimizer = self.optimizer(morning_slow_charge_enabled=True)
                optimizer._morning_slow_charge_active = lambda *args, **kwargs: False
                state = self.state(
                    when,
                    battery_soc=80.0,
                    available_discharge_energy_kwh=24.0,
                    feedin_price=fit,
                    feedin_price_cents=fit_cents,
                    pv_kw=7.0,
                    solar_power_now_kw=7.0,
                    load_kw=1.0,
                    current_ems_mode=MODE_CMD_DISCHARGE_PV,
                    current_export_limit=1.8,
                    grid_export_power_kw=1.0,
                )

                decision = self.decide(optimizer, state, when)

                self.assert_outputs(
                    decision,
                    (expected_mode, 0.0, 0.0, 25.0, 25.0, 25.0),
                )
                self.assertFalse(decision.trace_gates["morning_slow_charge_active"])
                self.assertEqual("blocked_or_zero", decision.trace_values["export_branch"])
                self.assertEqual(expected_mode, decision.trace_values["desired_ems_mode"])

    def _standby_optimizer(self, when: datetime):
        optimizer = self.optimizer(
            standby_holdoff_enabled=True,
            pv_forecast_holdoff_kwh=50.0,
        )
        optimizer._negative_price_before_cutoff = lambda *args, **kwargs: True
        optimizer._today_at = lambda _value: when + timedelta(hours=1)
        return optimizer

    def test_standby_holdoff_uses_snapshotted_floor_for_high_and_low_soc(self) -> None:
        when = datetime(2026, 1, 15, 9, 0)
        for name, soc, available, expected_mode in (
            ("above_floor", 80.0, 24.0, MODE_CMD_DISCHARGE_PV),
            ("below_floor", 20.0, 6.0, MODE_MAX_SELF),
        ):
            with self.subTest(name=name):
                optimizer = self._standby_optimizer(when)
                state = self.state(
                    when,
                    battery_soc=soc,
                    available_discharge_energy_kwh=available,
                    current_price=0.30,
                    current_price_cents=30.0,
                    feedin_price=0.05,
                    feedin_price_cents=5.0,
                    load_kw=1.0,
                    forecast_remaining_kwh=100.0,
                    forecast_today_kwh=100.0,
                )

                decision = self.decide(optimizer, state, when)

                self.assert_outputs(
                    decision,
                    (expected_mode, 0.0, 0.0, 1.0, 25.0, 25.0),
                )
                self.assertTrue(decision.trace_gates["standby_holdoff_active"])
                self.assertEqual("blocked_or_zero", decision.trace_values["export_branch"])
                self.assertEqual("standby_holdoff_block", decision.trace_values["import_branch"])
                self.assertIsNotNone(optimizer._holdoff_entry_floor)
                self.assertEqual(
                    optimizer._holdoff_entry_floor,
                    decision.trace_values["holdoff_entry_floor"],
                )
                comparison = soc > optimizer._holdoff_entry_floor
                self.assertEqual(expected_mode == MODE_CMD_DISCHARGE_PV, comparison)

    def test_standby_holdoff_exit_clears_floor_and_recovers_msc(self) -> None:
        when = datetime(2026, 1, 15, 9, 0)
        optimizer = self._standby_optimizer(when)
        common = {
            "battery_soc": 80.0,
            "available_discharge_energy_kwh": 24.0,
            "current_price": 0.30,
            "current_price_cents": 30.0,
            "feedin_price": 0.05,
            "feedin_price_cents": 5.0,
            "load_kw": 1.0,
        }
        active = self.decide(
            optimizer,
            self.state(
                when,
                **common,
                forecast_remaining_kwh=100.0,
                forecast_today_kwh=100.0,
            ),
            when,
        )
        optimizer._last_decision = active
        self.assertIsNotNone(optimizer._holdoff_entry_floor)
        exit_state = self.state(
            when,
            **common,
            forecast_remaining_kwh=0.0,
            forecast_today_kwh=0.0,
            current_ems_mode=MODE_CMD_DISCHARGE_PV,
        )

        decision = self.decide(optimizer, exit_state, when)

        self.assert_outputs(decision, (MODE_MAX_SELF, 0.0, 0.0, 25.0, 25.0, 25.0))
        self.assertFalse(decision.trace_gates["standby_holdoff_active"])
        self.assertIsNone(optimizer._holdoff_entry_floor)
        self.assertIsNone(decision.trace_values["holdoff_entry_floor"])
        self.assertEqual("blocked", decision.trace_values["import_branch"])

    def test_evening_boost_uses_discharge_but_reports_normal_tier_branch(self) -> None:
        when = datetime(2026, 1, 15, 17, 30)
        optimizer = self.optimizer(evening_boost_enabled=True)
        optimizer._evening_export_boost_active = lambda *args, **kwargs: True
        state = self.state(
            when,
            battery_soc=80.0,
            available_discharge_energy_kwh=24.0,
            feedin_price=0.15,
            feedin_price_cents=15.0,
            load_kw=0.0,
        )

        decision = self.decide(optimizer, state, when)

        self.assert_outputs(
            decision,
            (MODE_CMD_DISCHARGE_PV, 6.6, 0.0, 25.0, 25.0, 25.0),
        )
        self.assertTrue(decision.trace_gates["evening_export_boost_active"])
        self.assertEqual("normal_tier", decision.trace_values["export_branch"])
        self.assertEqual(8.5, decision.trace_values["export_tier_limit"])

    def test_evening_boost_exit_needs_fit_below_hysteresis_to_recover_msc(self) -> None:
        when = datetime(2026, 1, 15, 17, 30)
        cases = (
            ("same_fit", 0.15, 15.0, MODE_CMD_DISCHARGE_PV, 25.0),
            ("below_hysteresis", 0.07, 7.0, MODE_MAX_SELF, 0.1),
        )
        for name, fit, fit_cents, expected_mode, expected_pv_max in cases:
            with self.subTest(name=name):
                optimizer = self.optimizer(evening_boost_enabled=True)
                optimizer._evening_export_boost_active = lambda *args, **kwargs: False
                state = self.state(
                    when,
                    battery_soc=80.0,
                    available_discharge_energy_kwh=24.0,
                    feedin_price=fit,
                    feedin_price_cents=fit_cents,
                    load_kw=0.0,
                    current_ems_mode=MODE_CMD_DISCHARGE_PV,
                    current_export_limit=6.6,
                )

                decision = self.decide(optimizer, state, when)

                self.assert_outputs(
                    decision,
                    (expected_mode, 0.0, 0.0, expected_pv_max, 25.0, 25.0),
                )
                self.assertFalse(decision.trace_gates["evening_export_boost_active"])
                self.assertEqual("blocked_or_zero", decision.trace_values["export_branch"])
                self.assertEqual(
                    expected_mode == MODE_MAX_SELF,
                    decision.trace_gates["battery_only_mode"],
                )

    def test_real_morning_dump_window_activates_then_expires(self) -> None:
        active_when = datetime(2026, 1, 15, 6, 0)
        detailed = [
            {
                "period_start": (active_when + timedelta(hours=hours)).isoformat(),
                "pv_estimate": 10.0,
            }
            for hours in (3, 5, 7, 9, 11)
        ]
        optimizer = self.optimizer(morning_dump_enabled=True)
        active_state = self.state(
            active_when,
            sun_above_horizon=False,
            battery_soc=80.0,
            available_discharge_energy_kwh=24.0,
            feedin_price=0.05,
            feedin_price_cents=5.0,
            load_kw=1.0,
            solcast_detailed=detailed,
        )

        active = self.decide(optimizer, active_state, active_when)

        self.assert_outputs(
            active,
            (MODE_CMD_DISCHARGE_PV, 25.0, 0.0, 25.0, 25.0, 25.0),
        )
        self.assertTrue(active.trace_gates["morning_dump_active"])

        exit_when = datetime(2026, 1, 15, 8, 1)
        exit_state = self.state(
            exit_when,
            battery_soc=80.0,
            available_discharge_energy_kwh=24.0,
            feedin_price=0.05,
            feedin_price_cents=5.0,
            load_kw=1.0,
            solcast_detailed=detailed,
            current_ems_mode=MODE_CMD_DISCHARGE_PV,
            current_export_limit=25.0,
        )
        exited = self.decide(optimizer, exit_state, exit_when)

        self.assert_outputs(exited, (MODE_MAX_SELF, 0.0, 0.0, 25.0, 25.0, 25.0))
        self.assertFalse(exited.trace_gates["morning_dump_active"])

    def test_real_morning_slow_time_gate_activates_then_expires(self) -> None:
        active_when = datetime(2026, 1, 15, 9, 0)
        optimizer = self.optimizer(
            morning_slow_charge_enabled=True,
            morning_slow_charge_rate_kw=2.0,
            morning_slow_export_ramp_up_step_kw=0.8,
        )
        common = {
            "battery_soc": 80.0,
            "available_discharge_energy_kwh": 24.0,
            "feedin_price": 0.15,
            "feedin_price_cents": 15.0,
            "pv_kw": 7.0,
            "solar_power_now_kw": 7.0,
            "load_kw": 1.0,
            "forecast_remaining_kwh": 100.0,
        }
        active_state = self.state(
            active_when,
            **common,
            current_export_limit=1.0,
            grid_export_power_kw=1.0,
        )

        active = self.decide(optimizer, active_state, active_when)

        self.assert_outputs(
            active,
            (MODE_CMD_DISCHARGE_PV, 1.8, 0.0, 25.0, 2.0, 25.0),
        )
        self.assertTrue(active.trace_gates["morning_slow_charge_active"])

        exit_when = datetime(2026, 1, 15, 11, 1)
        exit_state = self.state(
            exit_when,
            **common,
            current_ems_mode=MODE_CMD_DISCHARGE_PV,
            current_export_limit=1.8,
            grid_export_power_kw=1.0,
        )
        exited = self.decide(optimizer, exit_state, exit_when)

        self.assert_outputs(
            exited,
            (MODE_CMD_DISCHARGE_PV, 0.0, 0.0, 25.0, 25.0, 25.0),
        )
        self.assertFalse(exited.trace_gates["morning_slow_charge_active"])

    def test_real_evening_boost_forecast_gate_activates_then_deactivates(self) -> None:
        when = datetime(2026, 1, 15, 17, 30)
        optimizer = self.optimizer(
            evening_boost_enabled=True,
            evening_boost_min_tomorrow_forecast_kwh=100.0,
        )
        detailed = [
            {
                "period_start": datetime(2026, 1, 15, 16, 0).isoformat(),
                "pv_estimate": 2.0,
            }
        ]
        common = {
            "battery_soc": 80.0,
            "available_discharge_energy_kwh": 24.0,
            "feedin_price": 0.15,
            "feedin_price_cents": 15.0,
            "load_kw": 0.0,
            "solcast_detailed": detailed,
        }
        active_state = self.state(
            when,
            **common,
            forecast_tomorrow_kwh=120.0,
        )

        active = self.decide(optimizer, active_state, when)

        self.assert_outputs(
            active,
            (MODE_CMD_DISCHARGE_PV, 6.6, 0.0, 25.0, 25.0, 25.0),
        )
        self.assertTrue(active.trace_gates["evening_export_boost_active"])

        exit_state = self.state(
            when,
            **common,
            forecast_tomorrow_kwh=99.0,
            current_ems_mode=MODE_CMD_DISCHARGE_PV,
            current_export_limit=6.6,
        )
        exited = self.decide(optimizer, exit_state, when)

        self.assert_outputs(
            exited,
            (MODE_CMD_DISCHARGE_PV, 0.0, 0.0, 25.0, 25.0, 25.0),
        )
        self.assertFalse(exited.trace_gates["evening_export_boost_active"])


if __name__ == "__main__":
    unittest.main()
