from __future__ import annotations

import unittest
from datetime import datetime

from app.optimizer import (
    MODE_CMD_CHARGE_GRID,
    MODE_CMD_CHARGE_PV,
    MODE_CMD_DISCHARGE_PV,
    MODE_MAX_SELF,
)
from haos49_characterization_helpers import Haos49CharacterizationCase


class Haos49NormalCharacterizationTests(Haos49CharacterizationCase):
    def assert_control_outputs(
        self,
        decision,
        *,
        ems_mode: str,
        export_limit: float,
        import_limit: float,
        pv_max_power_limit: float = 25.0,
        ess_charge_limit: float = 25.0,
        ess_discharge_limit: float = 25.0,
    ) -> None:
        self.assertEqual(
            (
                ems_mode,
                export_limit,
                import_limit,
                pv_max_power_limit,
                ess_charge_limit,
                ess_discharge_limit,
            ),
            (
                decision.ems_mode,
                decision.export_limit,
                decision.import_limit,
                decision.pv_max_power_limit,
                decision.ess_charge_limit,
                decision.ess_discharge_limit,
            ),
        )

    @staticmethod
    def ordinary_export_state_values(**overrides: object) -> dict[str, object]:
        values: dict[str, object] = {
            "battery_soc": 95.0,
            "available_discharge_energy_kwh": 28.5,
            "feedin_price": 0.15,
            "feedin_price_cents": 15.0,
            "pv_kw": 0.0,
            "solar_power_now_kw": 0.0,
            "load_kw": 1.0,
        }
        values.update(overrides)
        return values

    def test_overnight_pre_sunrise_and_sunrise_boundary_keep_ordinary_msc_ceiling(self) -> None:
        cases = (
            ("overnight", datetime(2026, 1, 15, 2, 0), 0.0, 5.0),
            ("pre_sunrise", datetime(2026, 1, 15, 6, 30), 0.0, 0.5),
            ("sunrise_boundary", datetime(2026, 1, 15, 7, 0), 1.5, 24.0),
        )

        for name, when, pv_kw, hours_to_sunrise in cases:
            with self.subTest(name=name):
                optimizer = self.optimizer()
                state = self.state(
                    when,
                    sun_above_horizon=name == "sunrise_boundary",
                    **self.ordinary_export_state_values(
                        pv_kw=pv_kw,
                        solar_power_now_kw=pv_kw,
                    ),
                )

                decision = self.decide(optimizer, state, when)

                self.assert_control_outputs(
                    decision,
                    ems_mode=MODE_MAX_SELF,
                    export_limit=25.0,
                    import_limit=0.0,
                )
                self.assertTrue(decision.trace_gates["is_evening_or_night"])
                self.assertFalse(decision.trace_gates["close_to_sunset"])
                self.assertEqual("ordinary_msc_surplus_ceiling", decision.trace_values["export_branch"])
                self.assertEqual("blocked", decision.trace_values["import_branch"])
                self.assertEqual(8.5, decision.trace_values["export_tier_limit"])
                self.assertEqual(25.0, decision.trace_values["desired_export_limit"])
                self.assertEqual(hours_to_sunrise, decision.trace_values["hours_to_sunrise"])

    def test_sunrise_plus_one_hour_enters_day_policy(self) -> None:
        when = datetime(2026, 1, 15, 8, 0)
        optimizer = self.optimizer()
        state = self.state(
            when,
            **self.ordinary_export_state_values(
                pv_kw=4.0,
                solar_power_now_kw=4.0,
            ),
        )

        decision = self.decide(optimizer, state, when)

        self.assert_control_outputs(
            decision,
            ems_mode=MODE_MAX_SELF,
            export_limit=25.0,
            import_limit=0.0,
        )
        self.assertFalse(decision.trace_gates["is_evening_or_night"])
        self.assertFalse(decision.trace_gates["close_to_sunset"])
        self.assertEqual("ordinary_msc_surplus_ceiling", decision.trace_values["export_branch"])
        self.assertEqual(3.0, decision.trace_values["pv_surplus_actual"])
        self.assertEqual(25.0, decision.trace_values["desired_export_limit"])

    def test_afternoon_and_approaching_sunset_keep_ordinary_msc_ceiling(self) -> None:
        cases = (
            ("afternoon", datetime(2026, 1, 15, 14, 0), 4.0, False, False),
            ("approaching_sunset", datetime(2026, 1, 15, 17, 30), 1.5, True, True),
        )

        for name, when, pv_kw, is_night, close_to_sunset in cases:
            with self.subTest(name=name):
                optimizer = self.optimizer()
                state = self.state(
                    when,
                    **self.ordinary_export_state_values(
                        pv_kw=pv_kw,
                        solar_power_now_kw=pv_kw,
                    ),
                )

                decision = self.decide(optimizer, state, when)

                self.assert_control_outputs(
                    decision,
                    ems_mode=MODE_MAX_SELF,
                    export_limit=25.0,
                    import_limit=0.0,
                )
                self.assertEqual(is_night, decision.trace_gates["is_evening_or_night"])
                self.assertEqual(close_to_sunset, decision.trace_gates["close_to_sunset"])
                self.assertEqual("ordinary_msc_surplus_ceiling", decision.trace_values["export_branch"])
                self.assertEqual(25.0, decision.trace_values["desired_export_limit"])
                self.assertEqual(4.0 if name == "afternoon" else 0.5, decision.trace_values["hours_to_sunset"])

    def test_low_medium_and_high_soc_share_ordinary_msc_baseline(self) -> None:
        cases = (
            ("low", 20.0, 6.0, MODE_MAX_SELF, 25.0, 0.0),
            ("medium", 60.0, 18.0, MODE_MAX_SELF, 25.0, 0.0),
            ("high", 95.0, 28.5, MODE_MAX_SELF, 25.0, 8.5),
        )

        for name, soc, available_kwh, ems_mode, export_limit, tier_limit in cases:
            with self.subTest(name=name):
                optimizer = self.optimizer()
                state = self.state(
                    self.FIXED_AFTERNOON,
                    battery_soc=soc,
                    available_discharge_energy_kwh=available_kwh,
                    feedin_price=0.15,
                    feedin_price_cents=15.0,
                    pv_kw=4.0,
                    solar_power_now_kw=4.0,
                    load_kw=1.0,
                )

                decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

                self.assert_control_outputs(
                    decision,
                    ems_mode=ems_mode,
                    export_limit=export_limit,
                    import_limit=0.0,
                )
                self.assertEqual("ordinary_msc_surplus_ceiling", decision.trace_values["export_branch"])
                self.assertEqual(tier_limit, decision.trace_values["export_tier_limit"])
                self.assertEqual(ems_mode, decision.trace_values["desired_ems_mode"])
                self.assertEqual(export_limit, decision.trace_values["desired_export_limit"])
                self.assertFalse(decision.trace_gates["topoff_target_met"])

    def test_full_battery_observed_msc_uses_high_export_ceiling(self) -> None:
        optimizer = self.optimizer()
        state = self.state(
            self.FIXED_AFTERNOON,
            battery_soc=100.0,
            available_discharge_energy_kwh=30.0,
            battery_power_sensor_kw=0.0,
            feedin_price=0.15,
            feedin_price_cents=15.0,
            pv_kw=4.0,
            solar_power_now_kw=4.0,
            load_kw=1.0,
        )

        decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

        self.assert_control_outputs(
            decision,
            ems_mode=MODE_MAX_SELF,
            export_limit=25.0,
            import_limit=0.0,
        )
        self.assertTrue(decision.trace_gates["topoff_target_met"])
        self.assertTrue(decision.trace_gates["pv_only_msc_transition_ready"])
        self.assertTrue(decision.trace_gates["pv_only_msc_high_ceiling_active"])
        self.assertTrue(decision.requires_verified_msc_before_export)
        self.assertEqual("msc_full_battery_high_ceiling", decision.trace_values["export_branch"])
        self.assertEqual(25.0, decision.trace_values["pv_only_msc_high_ceiling_kw"])
        self.assertEqual(MODE_MAX_SELF, decision.trace_values["desired_ems_mode"])

    def test_negative_fit_and_subcent_fit_close_export(self) -> None:
        cases = (
            ("negative", -0.01, -1.0, True),
            ("subcent", 0.009, 0.9, False),
        )

        for name, fit, fit_cents, is_negative in cases:
            with self.subTest(name=name):
                optimizer = self.optimizer()
                state = self.state(
                    self.FIXED_AFTERNOON,
                    **self.ordinary_export_state_values(
                        feedin_price=fit,
                        feedin_price_cents=fit_cents,
                        pv_kw=4.0,
                        solar_power_now_kw=4.0,
                    ),
                )

                decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

                self.assert_control_outputs(
                    decision,
                    ems_mode=MODE_MAX_SELF,
                    export_limit=0.0,
                    import_limit=0.0,
                )
                self.assertEqual(is_negative, decision.trace_gates["feedin_is_negative"])
                self.assertEqual("blocked_or_zero", decision.trace_values["export_branch"])
                self.assertEqual(0.0, decision.trace_values["export_tier_limit"])
                self.assertEqual(fit, decision.trace_values["feedin_price"])

    def test_one_to_nine_point_nine_cent_fit_stays_below_export_tier(self) -> None:
        for fit, fit_cents in ((0.01, 1.0), (0.05, 5.0), (0.099, 9.9)):
            with self.subTest(fit_cents=fit_cents):
                optimizer = self.optimizer()
                state = self.state(
                    self.FIXED_AFTERNOON,
                    **self.ordinary_export_state_values(
                        feedin_price=fit,
                        feedin_price_cents=fit_cents,
                        pv_kw=4.0,
                        solar_power_now_kw=4.0,
                    ),
                )

                decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

                self.assert_control_outputs(
                    decision,
                    ems_mode=MODE_MAX_SELF,
                    export_limit=0.0,
                    import_limit=0.0,
                )
                self.assertFalse(decision.trace_gates["feedin_is_negative"])
                self.assertEqual("blocked_or_zero", decision.trace_values["export_branch"])
                self.assertEqual(0.0, decision.trace_values["export_tier_limit"])
                self.assertEqual(fit, decision.trace_values["feedin_price"])

    def test_ten_cent_fit_enters_normal_low_export_tier(self) -> None:
        optimizer = self.optimizer()
        state = self.state(
            self.FIXED_AFTERNOON,
            **self.ordinary_export_state_values(
                feedin_price=0.10,
                feedin_price_cents=10.0,
                pv_kw=4.0,
                solar_power_now_kw=4.0,
            ),
        )

        decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

        self.assert_control_outputs(
            decision,
            ems_mode=MODE_MAX_SELF,
            export_limit=25.0,
            import_limit=0.0,
        )
        self.assertEqual("ordinary_msc_surplus_ceiling", decision.trace_values["export_branch"])
        self.assertEqual(5.0, decision.trace_values["export_tier_limit"])
        self.assertEqual(25.0, decision.trace_values["desired_export_limit"])
        self.assertFalse(decision.trace_gates["export_spike_active"])

    def test_high_price_battery_export_and_spike_use_full_limit(self) -> None:
        when = datetime(2026, 1, 15, 2, 0)
        cases = (
            ("high_price", 1.00, 100.0, False, "high_price"),
            ("spike", 0.65, 65.0, True, "export_spike"),
        )

        for name, fit, fit_cents, spike, export_branch in cases:
            with self.subTest(name=name):
                optimizer = self.optimizer(export_spike_threshold=0.60)
                state = self.state(
                    when,
                    sun_above_horizon=False,
                    **self.ordinary_export_state_values(
                        feedin_price=fit,
                        feedin_price_cents=fit_cents,
                        price_spike_active=spike,
                        battery_power_sensor_kw=-0.2,
                    ),
                )

                decision = self.decide(optimizer, state, when)

                self.assert_control_outputs(
                    decision,
                    ems_mode=MODE_CMD_DISCHARGE_PV,
                    export_limit=25.0,
                    import_limit=0.0,
                )
                self.assertTrue(decision.trace_gates["is_evening_or_night"])
                self.assertEqual(spike, decision.trace_gates["export_spike_active"])
                self.assertEqual(export_branch, decision.trace_values["export_branch"])
                self.assertEqual("battery_backed", decision.trace_values["export_value_gate_export_type"])
                self.assertEqual(25.0, decision.trace_values["export_tier_limit"])
                self.assertEqual(25.0, decision.trace_values["desired_export_limit"])

    def test_high_price_and_spike_do_not_export_battery_at_reserve_floor(self) -> None:
        for name, fit, fit_cents, spike, branch in (
            ("high_price", 1.10, 110.0, False, "blocked_or_zero"),
            ("spike", 0.65, 65.0, True, "blocked_or_zero"),
        ):
            with self.subTest(name=name):
                optimizer = self.optimizer(export_spike_threshold=0.60)
                state = self.state(
                    self.FIXED_AFTERNOON,
                    battery_soc=20.0,
                    available_discharge_energy_kwh=6.0,
                    battery_power_sensor_kw=-0.2,
                    feedin_price=fit,
                    feedin_price_cents=fit_cents,
                    price_spike_active=spike,
                    pv_kw=0.0,
                    solar_power_now_kw=0.0,
                    load_kw=1.0,
                )

                decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

                self.assert_control_outputs(
                    decision,
                    ems_mode=MODE_MAX_SELF,
                    export_limit=0.0,
                    import_limit=0.0,
                )
                self.assertEqual(branch, decision.trace_values["export_branch"])
                self.assertEqual(20.0, decision.trace_values["export_min_soc"])
                self.assertEqual("no_live_export", decision.trace_values["export_value_gate_export_type"])
                self.assertEqual(0.0, decision.trace_values["desired_export_limit"])

    def test_negative_import_price_uses_grid_first_and_suppresses_pv(self) -> None:
        optimizer = self.optimizer()
        state = self.state(
            self.FIXED_AFTERNOON,
            battery_soc=30.0,
            available_discharge_energy_kwh=9.0,
            current_price=-0.35,
            current_price_cents=-35.0,
            feedin_price=0.0,
            feedin_price_cents=0.0,
            pv_kw=0.0,
            solar_power_now_kw=0.0,
            load_kw=1.0,
            forecast_remaining_kwh=0.0,
        )

        decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

        self.assert_control_outputs(
            decision,
            ems_mode=MODE_CMD_CHARGE_GRID,
            export_limit=0.0,
            import_limit=25.0,
            pv_max_power_limit=0.1,
            ess_charge_limit=25.0,
            ess_discharge_limit=0.01,
        )
        self.assertTrue(decision.trace_gates["price_is_negative"])
        self.assertEqual("negative_price_import", decision.trace_values["import_branch"])
        self.assertEqual(25.0, decision.trace_values["desired_import_limit"])
        self.assertEqual("desired_pv_max_below_normal", decision.trace_values["pv_cap_reason"])

    def test_cheap_grid_topup_uses_charge_pv_and_matches_ess_charge_limit(self) -> None:
        optimizer = self.optimizer()
        state = self.state(
            self.FIXED_AFTERNOON,
            battery_soc=30.0,
            available_discharge_energy_kwh=9.0,
            current_price=0.01,
            current_price_cents=1.0,
            feedin_price=0.0,
            feedin_price_cents=0.0,
            pv_kw=0.0,
            solar_power_now_kw=0.0,
            load_kw=1.0,
            forecast_remaining_kwh=0.0,
        )

        decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

        self.assert_control_outputs(
            decision,
            ems_mode=MODE_CMD_CHARGE_PV,
            export_limit=0.0,
            import_limit=2.0,
            ess_charge_limit=2.0,
        )
        self.assertFalse(decision.trace_gates["price_is_negative"])
        self.assertTrue(decision.trace_gates["export_forecast_guard"])
        self.assertEqual("blocked_or_zero", decision.trace_values["export_branch"])
        self.assertEqual("cheap_topup_import", decision.trace_values["import_branch"])
        self.assertEqual(2.0, decision.trace_values["desired_import_limit"])
        self.assertEqual(2.0, decision.trace_values["ess_charge_limit"])

    def test_strong_pv_blocks_cheap_topup_despite_high_charge_demand(self) -> None:
        optimizer = self.optimizer()
        state = self.state(
            self.FIXED_AFTERNOON,
            battery_soc=30.0,
            available_discharge_energy_kwh=9.0,
            current_price=0.01,
            current_price_cents=1.0,
            feedin_price=0.0,
            feedin_price_cents=0.0,
            pv_kw=5.0,
            solar_power_now_kw=5.0,
            load_kw=1.0,
            forecast_remaining_kwh=0.0,
        )

        decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

        self.assert_control_outputs(
            decision,
            ems_mode=MODE_MAX_SELF,
            export_limit=0.0,
            import_limit=0.0,
        )
        self.assertEqual("blocked_or_zero", decision.trace_values["export_branch"])
        self.assertEqual("blocked", decision.trace_values["import_branch"])
        self.assertEqual(4.0, decision.trace_values["pv_surplus_actual"])
        self.assertEqual(0.0, decision.trace_values["desired_import_limit"])
        self.assertIn("PV sufficient", decision.import_reason)

    def test_poor_tomorrow_forecast_differs_at_99_and_100_percent_soc(self) -> None:
        cases = (
            ("ninety_nine", 99.0, 29.7, -0.2, MODE_MAX_SELF, 25.0, False, "ordinary_msc_surplus_ceiling"),
            ("full", 100.0, 30.0, 0.0, MODE_MAX_SELF, 25.0, True, "msc_full_battery_high_ceiling"),
        )

        for name, soc, available_kwh, battery_flow, ems_mode, export_limit, high_ceiling, branch in cases:
            with self.subTest(name=name):
                optimizer = self.optimizer()
                state = self.state(
                    self.FIXED_AFTERNOON,
                    battery_soc=soc,
                    available_discharge_energy_kwh=available_kwh,
                    battery_power_sensor_kw=battery_flow,
                    feedin_price=0.15,
                    feedin_price_cents=15.0,
                    pv_kw=6.0,
                    solar_power_now_kw=6.0,
                    load_kw=1.0,
                    forecast_tomorrow_kwh=0.0,
                )

                decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

                self.assert_control_outputs(
                    decision,
                    ems_mode=ems_mode,
                    export_limit=export_limit,
                    import_limit=0.0,
                )
                self.assertEqual(high_ceiling, decision.trace_gates["topoff_target_met"])
                self.assertEqual(high_ceiling, decision.trace_gates["pv_only_msc_high_ceiling_active"])
                self.assertEqual(branch, decision.trace_values["export_branch"])
                self.assertEqual(
                    "pv_surplus_only",
                    decision.trace_values["export_value_gate_export_type"],
                )
                self.assertEqual(5.0, decision.trace_values["pv_surplus_actual"])
                self.assertEqual(export_limit, decision.trace_values["desired_export_limit"])
                if high_ceiling:
                    self.assertIn("PV-only MSC ceiling active", decision.export_reason)
                else:
                    self.assertIn("Ordinary MSC surplus ceiling active", decision.export_reason)

    def test_demand_window_little_and_strong_pv_keep_normal_pv_max(self) -> None:
        when = datetime(2026, 1, 15, 17, 30)

        for name, pv_kw, measured_surplus in (
            ("little_pv", 0.2, 0.0),
            ("strong_pv", 5.0, 4.0),
        ):
            with self.subTest(name=name):
                optimizer = self.optimizer()
                state = self.state(
                    when,
                    battery_soc=60.0,
                    available_discharge_energy_kwh=18.0,
                    current_price=0.30,
                    current_price_cents=30.0,
                    feedin_price=0.0,
                    feedin_price_cents=0.0,
                    pv_kw=pv_kw,
                    solar_power_now_kw=pv_kw,
                    load_kw=1.0,
                    current_pv_max_power_limit=25.0,
                    demand_window_active=True,
                )

                decision = self.decide(optimizer, state, when)

                self.assert_control_outputs(
                    decision,
                    ems_mode=MODE_MAX_SELF,
                    export_limit=0.0,
                    import_limit=0.0,
                )
                self.assertTrue(decision.trace_gates["is_evening_or_night"])
                self.assertTrue(decision.trace_gates["demand_window_active"])
                self.assertFalse(decision.trace_gates["battery_only_mode"])
                self.assertEqual("demand_window_block", decision.trace_values["import_branch"])
                self.assertEqual(25.0, decision.trace_values["desired_pv_max_limit_kw"])
                self.assertEqual(measured_surplus, decision.trace_values["pv_surplus_actual"])

    def test_demand_window_exit_restores_ordinary_evening_pv_cap(self) -> None:
        when = datetime(2026, 1, 15, 17, 30)
        optimizer = self.optimizer()
        demand_state = self.state(
            when,
            battery_soc=60.0,
            available_discharge_energy_kwh=18.0,
            feedin_price=0.0,
            feedin_price_cents=0.0,
            pv_kw=0.2,
            solar_power_now_kw=0.2,
            load_kw=1.0,
            demand_window_active=True,
        )
        demand_decision = self.decide(optimizer, demand_state, when)
        optimizer._last_decision = demand_decision
        normal_state = self.state(
            when,
            battery_soc=60.0,
            available_discharge_energy_kwh=18.0,
            feedin_price=0.0,
            feedin_price_cents=0.0,
            pv_kw=0.2,
            solar_power_now_kw=0.2,
            load_kw=1.0,
            demand_window_active=False,
        )

        decision = self.decide(optimizer, normal_state, when)

        self.assert_control_outputs(
            decision,
            ems_mode=MODE_MAX_SELF,
            export_limit=0.0,
            import_limit=0.0,
            pv_max_power_limit=25.0,
        )
        self.assertFalse(decision.trace_gates["demand_window_active"])
        self.assertFalse(decision.trace_gates["battery_only_mode"])
        self.assertEqual("blocked", decision.trace_values["import_branch"])
        self.assertEqual("none", decision.trace_values["pv_cap_reason"])
        self.assertEqual(25.0, decision.trace_values["desired_pv_max_limit_kw"])


if __name__ == "__main__":
    unittest.main()
