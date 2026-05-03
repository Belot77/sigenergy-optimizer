"""
Coverage-filling tests for manual_mode_service, decision_guards, and
limit_calculator uncovered paths.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from app.config import Settings
from app.models import Decision, SolarState
from app.optimizer import SigEnergyOptimizer
from app.manual_mode_service import manual_mode_targets, freeze_decision_to_live_mode
from app.decision_guards import (
    morning_dump_active,
    morning_slow_charge_active,
    evening_export_boost_active,
    solar_surplus_bypass,
    battery_full_safeguard_block,
    export_blocked_for_forecast,
    export_forecast_guard,
)
from app.limit_calculator import (
    desired_export_limit,
    desired_import_limit,
    desired_ems_mode,
)


class _DummyHA:
    pass


class _OptimizerFixture(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._optimizers: list[SigEnergyOptimizer] = []
        self._old_db = os.environ.get("STATE_DB_PATH")
        os.environ["STATE_DB_PATH"] = os.path.join(self._tmp.name, "state.db")

    def tearDown(self) -> None:
        for opt in self._optimizers:
            opt._state_store.close()
        if self._old_db is None:
            os.environ.pop("STATE_DB_PATH", None)
        else:
            os.environ["STATE_DB_PATH"] = self._old_db
        self._tmp.cleanup()

    def _make_optimizer(self, **cfg_overrides) -> SigEnergyOptimizer:
        cfg = Settings(**cfg_overrides)
        opt = SigEnergyOptimizer(_DummyHA(), cfg)
        self._optimizers.append(opt)
        return opt


# ---------------------------------------------------------------------------
# manual_mode_service — manual_mode_targets routing
# ---------------------------------------------------------------------------

class TestManualModeTargets(_OptimizerFixture):
    _MODES = dict(
        mode_max_self="Maximum Self Consumption",
        mode_cmd_discharge_pv="Command Discharging (PV First)",
        mode_cmd_charge_grid="Command Charging (Grid First)",
        mode_cmd_charge_pv="Command Charging (PV First)",
    )

    def _targets(self, mode_label: str, **kwargs):
        opt = self._make_optimizer()
        return manual_mode_targets(opt, mode_label, **self._MODES, **kwargs)

    def test_automated_option_returns_none(self):
        opt = self._make_optimizer()
        result = manual_mode_targets(opt, opt.cfg.automated_option, **self._MODES)
        self.assertIsNone(result)

    def test_manual_option_returns_none(self):
        opt = self._make_optimizer()
        result = manual_mode_targets(opt, opt.cfg.manual_option, **self._MODES)
        self.assertIsNone(result)

    def test_empty_label_returns_none(self):
        self.assertIsNone(self._targets(""))

    def test_full_export_option_sets_discharge_mode(self):
        result = self._targets("Force Full Export")
        self.assertIsNotNone(result)
        self.assertEqual(result["ems_mode"], "Command Discharging (PV First)")
        self.assertAlmostEqual(float(result["grid_import_limit"]), 0.01, places=2)

    def test_full_import_option_sets_charge_grid_mode(self):
        result = self._targets("Force Full Import")
        self.assertIsNotNone(result)
        self.assertEqual(result["ems_mode"], "Command Charging (Grid First)")
        self.assertAlmostEqual(float(result["grid_export_limit"]), 0.01, places=2)

    def test_full_import_pv_option_sets_charge_pv_mode(self):
        result = self._targets("Force Full Import + PV")
        self.assertIsNotNone(result)
        self.assertEqual(result["ems_mode"], "Command Charging (PV First)")

    def test_block_flow_option_sets_max_self_and_blocks_grid(self):
        result = self._targets("Prevent Import & Export")
        self.assertIsNotNone(result)
        self.assertEqual(result["ems_mode"], "Maximum Self Consumption")
        self.assertAlmostEqual(float(result["grid_export_limit"]), 0.01, places=2)
        self.assertAlmostEqual(float(result["grid_import_limit"]), 0.01, places=2)

    def test_block_flow_includes_ess_limits_when_flag_set(self):
        result = self._targets("Prevent Import & Export", include_block_flow_ess_limits=True)
        self.assertIn("ess_charge_limit", result)
        self.assertIn("ess_discharge_limit", result)

    def test_block_flow_excludes_ess_limits_by_default(self):
        result = self._targets("Prevent Import & Export")
        self.assertNotIn("ess_charge_limit", result)

    def test_unknown_mode_returns_none(self):
        result = self._targets("Something Else")
        self.assertIsNone(result)

    def test_manual_ess_overrides_applied_on_block_flow(self):
        opt = self._make_optimizer()
        opt._manual_ess_charge_override_kw = 3.0
        opt._manual_ess_discharge_override_kw = 4.0
        result = manual_mode_targets(
            opt, "Prevent Import & Export",
            include_block_flow_ess_limits=True,
            **self._MODES,
        )
        self.assertEqual(result["ess_charge_limit"], 3.0)
        self.assertEqual(result["ess_discharge_limit"], 4.0)


class TestFreezeDecisionToLiveMode(unittest.TestCase):
    def test_decision_fields_overwritten_from_state(self):
        state = SolarState(
            current_ems_mode="Command Discharging (PV First)",
            current_export_limit=10.0,
            current_import_limit=0.01,
            current_pv_max_power_limit=25.0,
            current_ess_charge_limit=20.0,
            current_ess_discharge_limit=18.0,
        )
        d = Decision()
        freeze_decision_to_live_mode(state, d, "Force Full Export")
        self.assertEqual(d.ems_mode, "Command Discharging (PV First)")
        self.assertEqual(d.export_limit, 10.0)
        self.assertEqual(d.import_limit, 0.01)
        self.assertIn("Manual mode active", d.export_reason)

    def test_ess_limits_fall_back_to_decision_when_state_is_none(self):
        state = SolarState(
            current_ems_mode="Maximum Self Consumption",
            current_export_limit=5.0,
            current_import_limit=5.0,
            current_pv_max_power_limit=25.0,
            current_ess_charge_limit=None,
            current_ess_discharge_limit=None,
        )
        d = Decision()
        d.ess_charge_limit = 7.0
        d.ess_discharge_limit = 8.0
        freeze_decision_to_live_mode(state, d, "Manual")
        self.assertEqual(d.ess_charge_limit, 7.0)
        self.assertEqual(d.ess_discharge_limit, 8.0)


# ---------------------------------------------------------------------------
# decision_guards — uncovered branches
# ---------------------------------------------------------------------------

class TestMorningDumpActive(_OptimizerFixture):
    def test_disabled_by_config_returns_false(self):
        opt = self._make_optimizer(morning_dump_enabled=False)
        s = SolarState()
        result = morning_dump_active(opt, s, 100.0, 200.0, 300.0, 5.0, 150.0)
        self.assertFalse(result)

    def test_none_dump_window_returns_false(self):
        opt = self._make_optimizer(morning_dump_enabled=True)
        s = SolarState()
        self.assertFalse(morning_dump_active(opt, s, None, None, None, 5.0, 0.0))

    def test_outside_dump_window_returns_false(self):
        opt = self._make_optimizer(morning_dump_enabled=True)
        s = SolarState()
        self.assertFalse(morning_dump_active(opt, s, 500.0, 600.0, None, 5.0, 400.0))

    def test_inside_window_with_insufficient_forecast_returns_false(self):
        opt = self._make_optimizer(
            morning_dump_enabled=True,
            forecast_safety_charging=1.0,
            solcast_forecast_period_hours=0.5,
        )
        now_ts = 1000.0
        dump_end = 1200.0
        solar_end = 1800.0
        # solcast has no entries → ns_total = 0, so can't refill
        s = SolarState(solcast_detailed=[], load_kw=0.5)
        self.assertFalse(morning_dump_active(opt, s, 900.0, dump_end, solar_end, 5.0, now_ts))


class TestMorningSlowChargeActive(_OptimizerFixture):
    def test_disabled_by_config_returns_false(self):
        opt = self._make_optimizer(morning_slow_charge_enabled=False)
        now = datetime(2026, 5, 4, 8, 0, 0)
        s = SolarState()
        self.assertFalse(morning_slow_charge_active(opt, s, now, now.timestamp(), now.timestamp() + 3600))

    def test_runtime_disabled_returns_false(self):
        opt = self._make_optimizer(morning_slow_charge_enabled=True)
        opt._morning_slow_charge_runtime_disabled = True
        now = datetime(2026, 5, 4, 8, 0, 0)
        s = SolarState()
        self.assertFalse(morning_slow_charge_active(opt, s, now, now.timestamp(), now.timestamp() + 3600))

    def test_past_slow_charge_cutoff_returns_false(self):
        opt = self._make_optimizer(
            morning_slow_charge_enabled=True,
            morning_slow_charge_until="07:00",
        )
        # now = 08:00, past cutoff
        fixed = datetime(2026, 5, 4, 8, 0, 0)
        with patch("app.optimizer.datetime") as mock_dt:
            mock_dt.now.return_value = fixed
            s = SolarState(sun_above_horizon=True, feedin_price=0.15, forecast_remaining_kwh=10.0,
                           battery_capacity_kwh=10.0, available_discharge_energy_kwh=5.0, load_kw=0.3)
            now_ts = fixed.timestamp()
            result = morning_slow_charge_active(opt, s, fixed, now_ts, now_ts + 3600)
        self.assertFalse(result)


class TestEveningExportBoostActive(_OptimizerFixture):
    def test_disabled_by_config_returns_false(self):
        opt = self._make_optimizer(evening_boost_enabled=False)
        s = SolarState(battery_soc=40.0)
        self.assertFalse(evening_export_boost_active(opt, s, 0.0, None, 30.0, 5.0))

    def test_already_above_floor_soc_returns_false(self):
        opt = self._make_optimizer(
            evening_boost_enabled=True,
            evening_aggressive_floor=35.0,
        )
        s = SolarState(battery_soc=40.0)
        self.assertFalse(evening_export_boost_active(opt, s, 0.0, None, 30.0, 0.0))

    def test_below_floor_with_no_solar_end_returns_false(self):
        opt = self._make_optimizer(
            evening_boost_enabled=True,
            evening_aggressive_floor=35.0,
        )
        # productive_solar_end_ts=None means solar already done
        s = SolarState(battery_soc=20.0)
        result = evening_export_boost_active(opt, s, 0.0, None, 30.0, 5.0)
        self.assertFalse(result)


class TestSolarSurplusBypass(_OptimizerFixture):
    def test_disabled_by_config_returns_false(self):
        opt = self._make_optimizer(solar_surplus_bypass_enabled=False)
        s = SolarState(pv_kw=10.0, load_kw=1.0)
        self.assertFalse(solar_surplus_bypass(opt, s, False, 25.0, 5.0))

    def test_morning_slow_charge_active_returns_false(self):
        opt = self._make_optimizer(solar_surplus_bypass_enabled=True)
        s = SolarState(pv_kw=10.0, load_kw=1.0)
        self.assertFalse(solar_surplus_bypass(opt, s, True, 25.0, 5.0))

    def test_surplus_exceeds_start_threshold_returns_true(self):
        opt = self._make_optimizer(
            solar_surplus_bypass_enabled=True,
            solar_surplus_start_multiplier=2.0,
            solar_surplus_min_pv_margin=0.5,
        )
        # start_thresh = cap(2.0) * multiplier(2.0) = 4.0
        # forecast_remaining=5.0 >= 4.0 → start_ok=True; pv_surplus=5.0 > 0.5 → True
        s = SolarState(pv_kw=6.0, load_kw=1.0, forecast_remaining_kwh=5.0)
        result = solar_surplus_bypass(opt, s, False, 2.0, 5.0, prev_desired_mode="")
        self.assertTrue(result)


class TestBatteryFullSafeguardBlock(_OptimizerFixture):
    def test_disabled_by_config_returns_false(self):
        opt = self._make_optimizer(battery_full_safeguard_enabled=False)
        s = SolarState(battery_soc=60.0)
        self.assertFalse(battery_full_safeguard_block(opt, s, 0.0, 3600.0, 2.0, False))

    def test_evening_or_night_always_false(self):
        opt = self._make_optimizer(battery_full_safeguard_enabled=True)
        s = SolarState(battery_soc=60.0)
        self.assertFalse(battery_full_safeguard_block(opt, s, 0.0, 3600.0, 2.0, True))

    def test_battery_already_full_no_block(self):
        """If bat_fill_need_kwh <= 0 the battery is full; safeguard should not block."""
        opt = self._make_optimizer(
            battery_full_safeguard_enabled=True,
            battery_full_hours_before_sunset=2.0,
            battery_full_forecast_multiplier=0.8,
        )
        s = SolarState(
            battery_soc=100.0,
            battery_capacity_kwh=10.0,
            available_discharge_energy_kwh=10.0,
        )
        now_ts = 1000.0
        sunset_ts = now_ts + 10 * 3600
        result = battery_full_safeguard_block(opt, s, now_ts, sunset_ts, 0.0, False)
        self.assertFalse(result)


class TestExportBlockedForForecast(_OptimizerFixture):
    def test_evening_returns_false(self):
        opt = self._make_optimizer()
        s = SolarState(battery_soc=60.0, forecast_remaining_kwh=5.0)
        self.assertFalse(export_blocked_for_forecast(opt, s, 5.0, True, 2.0, 2.0, False))

    def test_daytime_high_forecast_not_blocked(self):
        opt = self._make_optimizer(
            pv_forecast_holdoff_kwh=50.0,
            standby_holdoff_enabled=True,
        )
        s = SolarState(
            battery_soc=40.0,
            forecast_remaining_kwh=100.0,
            available_discharge_energy_kwh=5.0,
            battery_capacity_kwh=10.0,
        )
        result = export_blocked_for_forecast(opt, s, 0.0, False, 5.0, 3.0, False)
        self.assertFalse(result)


class TestExportForecastGuard(_OptimizerFixture):
    def test_evening_boost_lowers_floor_to_aggressive_floor(self):
        # During evening is_evening_or_night=True, evening_boost means use evening_aggressive_floor
        # bsoc=80 vs evening_aggressive_floor=35 → bsoc > floor → NOT blocked
        opt = self._make_optimizer(evening_aggressive_floor=35.0)
        s = SolarState(battery_soc=80.0, forecast_remaining_kwh=5.0)
        result = export_forecast_guard(opt, s, 10.0, True, True, False)
        self.assertFalse(result)

    def test_evening_no_boost_uses_min_export_target_soc(self):
        # bsoc=80 vs min_export_target_soc=90 → bsoc < floor → blocked
        opt = self._make_optimizer(evening_aggressive_floor=35.0, min_export_target_soc=90.0)
        s = SolarState(battery_soc=80.0, forecast_remaining_kwh=5.0)
        result = export_forecast_guard(opt, s, 10.0, True, False, False)
        self.assertTrue(result)

    def test_close_to_sunset_blocks_guard(self):
        opt = self._make_optimizer()
        s = SolarState(battery_soc=80.0, forecast_remaining_kwh=5.0)
        result = export_forecast_guard(opt, s, 10.0, False, False, True)
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# limit_calculator — desired_export_limit / desired_import_limit / desired_ems_mode
# ---------------------------------------------------------------------------

def _default_state(**kwargs) -> SolarState:
    defaults = dict(
        battery_soc=60.0,
        feedin_price=0.20,
        feedin_price_cents=20.0,
        feedin_is_negative=False,
        current_price=0.25,
        current_price_cents=25.0,
        price_is_negative=False,
        pv_kw=5.0,
        load_kw=1.5,
        battery_capacity_kwh=10.0,
        available_discharge_energy_kwh=6.0,
        forecast_remaining_kwh=10.0,
    )
    defaults.update(kwargs)
    return SolarState(**defaults)


class TestDesiredExportLimit(_OptimizerFixture):
    def _export(self, s, **flags):
        opt = self._make_optimizer(
            min_export_target_soc=90.0,
            evening_aggressive_floor=35.0,
            export_threshold_high=1.0,
        )
        defaults = dict(
            spike=False, solar_override=False, export_blocked=False,
            forecast_guard=False, export_min_soc=20.0, positive_fit_override=False,
            surplus_bypass=False, evening_boost=False, morning_dump=False,
            morning_dump_limit=10.0, battery_full_safeguard_block=False,
            tier_limit=12.0, hours_to_sunrise=8.0, cap=25.0, pv_surplus=3.0,
            is_evening_or_night=False, morning_slow_charge_active=False,
            within_morning_grace=False,
        )
        defaults.update(flags)
        return desired_export_limit(opt, s, **defaults)

    def test_zero_fit_returns_zero(self):
        s = _default_state(feedin_price_cents=0.5)
        self.assertEqual(self._export(s), 0.0)

    def test_negative_price_returns_zero(self):
        s = _default_state(price_is_negative=True)
        self.assertEqual(self._export(s), 0.0)

    def test_battery_safeguard_blocks_non_high_price(self):
        s = _default_state(feedin_price=0.20)
        result = self._export(s, battery_full_safeguard_block=True)
        self.assertEqual(result, 0.0)

    def test_battery_safeguard_allows_high_price(self):
        # High FIT overrides the safeguard block; need bsoc above min_export_target_soc (90)
        s = _default_state(feedin_price=1.50, feedin_price_cents=150.0, battery_soc=95.0)
        result = self._export(s, battery_full_safeguard_block=True, tier_limit=25.0, is_evening_or_night=True)
        self.assertGreater(result, 0.0)

    def test_no_pv_surplus_daytime_non_spike_returns_zero(self):
        s = _default_state()
        result = self._export(s, pv_surplus=0.0, is_evening_or_night=False, spike=False)
        self.assertEqual(result, 0.0)

    def test_morning_dump_returns_dump_limit(self):
        s = _default_state()
        result = self._export(s, morning_dump=True, morning_dump_limit=8.0, pv_surplus=0.0, is_evening_or_night=True)
        self.assertEqual(result, 8.0)

    def test_export_blocked_returns_zero(self):
        s = _default_state()
        result = self._export(s, export_blocked=True, surplus_bypass=False)
        self.assertEqual(result, 0.0)

    def test_below_soc_floor_returns_zero(self):
        s = _default_state(battery_soc=15.0)
        result = self._export(s, export_min_soc=20.0, pv_surplus=0.0, is_evening_or_night=True)
        self.assertEqual(result, 0.0)


class TestDesiredImportLimit(_OptimizerFixture):
    def _import(self, s, **flags):
        opt = self._make_optimizer(
            import_limit_high=30.0,
            import_limit_medium=30.0,
            import_limit_low=30.0,
            max_price_threshold=0.015,
            target_battery_charge=2.0,
            cap_total_import=30.0,
        )
        defaults = dict(
            morning_dump_active=False,
            demand_window_active=False,
            standby_holdoff_active=False,
            feedin_price_ok=False,
            pv_surplus=0.0,
        )
        defaults.update(flags)
        return desired_import_limit(opt, s, **defaults)

    def test_morning_dump_returns_zero(self):
        s = _default_state()
        self.assertEqual(self._import(s, morning_dump_active=True), 0.0)

    def test_demand_window_returns_zero(self):
        s = _default_state()
        self.assertEqual(self._import(s, demand_window_active=True), 0.0)

    def test_standby_holdoff_returns_zero(self):
        s = _default_state()
        self.assertEqual(self._import(s, standby_holdoff_active=True), 0.0)

    def test_feedin_price_ok_returns_zero(self):
        s = _default_state()
        self.assertEqual(self._import(s, feedin_price_ok=True), 0.0)

    def test_high_price_blocks_import(self):
        s = _default_state(current_price=0.50, battery_soc=40.0)
        result = self._import(s)
        self.assertEqual(result, 0.0)

    def test_cheap_price_allows_import(self):
        s = _default_state(
            current_price=-0.30,
            current_price_cents=-30.0,
            price_is_negative=True,
            battery_soc=40.0,
        )
        result = self._import(s)
        self.assertGreater(result, 0.0)


class TestDesiredEmsMode(_OptimizerFixture):
    def _mode(self, s, **flags):
        opt = self._make_optimizer(
            min_soc_floor=20.0,
            night_reserve_soc=30.0,
        )
        defaults = dict(
            morning_dump=False, standby_holdoff=False, export_solar_override=False,
            desired_export=0.0, desired_import=0.0, export_min_soc=20.0,
            sunrise_soc_target=30.0, within_morning_grace=False,
            export_blocked_forecast=False, is_evening_or_night=False,
        )
        defaults.update(flags)
        return desired_ems_mode(opt, s, **defaults)

    def test_morning_dump_returns_discharge_pv(self):
        s = _default_state(battery_soc=60.0)
        result = self._mode(s, morning_dump=True, desired_export=10.0)
        self.assertIn("Discharging", result)

    def test_standby_holdoff_low_soc_returns_max_self(self):
        # bsoc < holdoff_discharge_floor → hold in max self-consumption, not discharge
        s = _default_state(battery_soc=15.0)
        result = self._mode(s, standby_holdoff=True, sunrise_soc_target=30.0)
        self.assertEqual(result, "Maximum Self Consumption")

    def test_active_export_returns_discharge_mode(self):
        s = _default_state(battery_soc=95.0, feedin_price=0.20)
        result = self._mode(s, desired_export=10.0, is_evening_or_night=False, export_solar_override=True)
        self.assertIn("Discharging", result)

    def test_active_import_returns_charge_mode(self):
        s = _default_state(battery_soc=30.0, current_price=-0.10)
        result = self._mode(s, desired_import=15.0)
        self.assertIn("Charging", result)

    def test_default_idle_returns_max_self(self):
        # With zero pv_surplus and not evening, desired_ems_mode should hold in max self-consumption
        s = _default_state(battery_soc=60.0, pv_kw=0.0, load_kw=1.5, feedin_price=0.20)
        result = self._mode(s)
        self.assertEqual(result, "Maximum Self Consumption")


if __name__ == "__main__":
    unittest.main()
