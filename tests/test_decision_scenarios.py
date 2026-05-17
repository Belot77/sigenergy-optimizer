from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.config import Settings
from app.models import SolarState
from app.optimizer import MODE_CMD_CHARGE_GRID, MODE_CMD_DISCHARGE_PV, MODE_MAX_SELF, SigEnergyOptimizer


class _DummyHA:
    pass


def _fixed_datetime(now: datetime) -> type[datetime]:
    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return now
            return now.astimezone(tz)

    return _FixedDateTime


class DecisionScenarioTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._optimizers: list[SigEnergyOptimizer] = []
        self._old_state_db_path = os.environ.get("STATE_DB_PATH")
        os.environ["STATE_DB_PATH"] = os.path.join(self._tmp.name, "state.db")

    def tearDown(self) -> None:
        for optimizer in self._optimizers:
            optimizer._state_store.close()
        if self._old_state_db_path is None:
            os.environ.pop("STATE_DB_PATH", None)
        else:
            os.environ["STATE_DB_PATH"] = self._old_state_db_path
        self._tmp.cleanup()

    def _optimizer(self, **overrides: float | str | bool) -> SigEnergyOptimizer:
        optimizer = SigEnergyOptimizer(_DummyHA(), Settings(**overrides))
        self._optimizers.append(optimizer)
        return optimizer

    @staticmethod
    def _state(now: datetime, sun_above_horizon: bool, **overrides: float | str | bool | None | list) -> SolarState:
        if sun_above_horizon:
            today_sunrise = now.replace(hour=6, minute=30, second=0, microsecond=0)
            today_sunset = now.replace(hour=18, minute=0, second=0, microsecond=0)
            next_sunrise = today_sunrise + timedelta(days=1)
            next_sunset = today_sunset
        else:
            tomorrow = now + timedelta(days=1)
            next_sunrise = tomorrow.replace(hour=6, minute=30, second=0, microsecond=0)
            next_sunset = tomorrow.replace(hour=18, minute=0, second=0, microsecond=0)

        defaults = {
            "pv_kw": 4.0 if sun_above_horizon else 0.0,
            "load_kw": 1.5,
            "battery_soc": 50.0,
            "battery_capacity_kwh": 10.0,
            "available_discharge_energy_kwh": 5.0,
            "ess_max_discharge_kw": 8.0,
            "ess_max_charge_kw": 8.0,
            "current_export_limit": 0.0,
            "current_import_limit": 0.0,
            "current_pv_max_power_limit": 25.0,
            "current_ess_charge_limit": 8.0,
            "current_ess_discharge_limit": 8.0,
            "current_ems_mode": MODE_MAX_SELF,
            "ha_control_enabled": True,
            "current_price": 0.20,
            "current_price_cents": 20.0,
            "feedin_price": 0.05,
            "feedin_price_cents": 5.0,
            "price_is_actual": True,
            "forecast_remaining_kwh": 12.0,
            "forecast_today_kwh": 20.0,
            "forecast_tomorrow_kwh": 20.0,
            "solar_power_now_kw": 4.0 if sun_above_horizon else 0.0,
            "sun_above_horizon": sun_above_horizon,
            "next_sunrise_ts": next_sunrise.timestamp(),
            "next_sunset_ts": next_sunset.timestamp(),
            "hours_to_sunrise": max((next_sunrise - now).total_seconds() / 3600, 0.0),
            "hours_to_sunset": max((next_sunset - now).total_seconds() / 3600, 0.0),
            "sigenergy_mode": "Automated",
            "solcast_detailed": [],
            "price_forecast_entries": [],
            "feedin_forecast_entries": [],
        }
        defaults.update(overrides)
        return SolarState(**defaults)

    def test_export_blocked_for_forecast_relaxes_close_to_sunset(self) -> None:
        optimizer = self._optimizer()
        now = datetime(2026, 4, 5, 16, 30, tzinfo=timezone.utc)
        state = self._state(
            now,
            sun_above_horizon=True,
            battery_soc=80.0,
            available_discharge_energy_kwh=4.0,
            load_kw=2.0,
            forecast_remaining_kwh=1.0,
        )

        blocked_before_grace = optimizer._export_blocked_for_forecast(
            state,
            pv_surplus=0.0,
            is_evening_or_night=False,
            bat_fill_need_kwh=6.0,
            hours_to_sunset=3.0,
            close_to_sunset=False,
        )
        blocked_inside_grace = optimizer._export_blocked_for_forecast(
            state,
            pv_surplus=0.0,
            is_evening_or_night=False,
            bat_fill_need_kwh=6.0,
            hours_to_sunset=1.5,
            close_to_sunset=True,
        )

        self.assertTrue(blocked_before_grace)
        self.assertFalse(blocked_inside_grace)

    def test_night_export_respects_dynamic_sunrise_reserve(self) -> None:
        optimizer = self._optimizer(min_export_target_soc=20.0)
        now = datetime(2026, 4, 5, 22, 0, tzinfo=timezone.utc)
        state = self._state(
            now,
            sun_above_horizon=False,
            battery_soc=45.0,
            battery_capacity_kwh=10.0,
            available_discharge_energy_kwh=4.5,
            load_kw=0.6,
            feedin_price=0.25,
            feedin_price_cents=25.0,
        )

        with patch("app.optimizer.datetime", _fixed_datetime(now)):
            decision = optimizer._decide(state)

        self.assertEqual(decision.export_limit, 0.0)
        self.assertGreater(decision.trace_values["export_min_soc"], optimizer.cfg.sunrise_reserve_soc)
        self.assertIn("floor", decision.export_reason)

    def test_decide_negative_price_night_imports_at_charge_cap(self) -> None:
        optimizer = self._optimizer()
        now = datetime(2026, 4, 5, 22, 0, tzinfo=timezone.utc)
        state = self._state(
            now,
            sun_above_horizon=False,
            battery_soc=20.0,
            current_price=-0.05,
            current_price_cents=-5.0,
            feedin_price=0.0,
            feedin_price_cents=0.0,
            ess_max_charge_kw=8.0,
            forecast_remaining_kwh=0.0,
            forecast_today_kwh=0.0,
        )

        with patch("app.optimizer.datetime", _fixed_datetime(now)):
            decision = optimizer._decide(state)

        self.assertEqual(decision.import_limit, 8.0)
        self.assertEqual(decision.export_limit, 0.0)
        self.assertEqual(decision.ems_mode, MODE_CMD_CHARGE_GRID)
        self.assertEqual(decision.pv_max_power_limit, 0.1)
        self.assertIn("paid price", decision.import_reason)

    def test_decide_daytime_standby_holdoff_blocks_import_and_curtailed_pv(self) -> None:
        optimizer = self._optimizer()
        now = datetime(2026, 4, 5, 9, 0, tzinfo=timezone.utc)
        state = self._state(
            now,
            sun_above_horizon=True,
            battery_soc=40.0,
            load_kw=1.0,
            pv_kw=2.0,
            solar_power_now_kw=2.0,
            current_price=0.20,
            current_price_cents=20.0,
            feedin_price=0.0,
            feedin_price_cents=0.0,
            forecast_remaining_kwh=180.0,
            forecast_today_kwh=200.0,
            price_forecast_entries=[
                {"start_time": (now + timedelta(minutes=30)).timestamp(), "per_kwh": -0.05}
            ],
        )

        with patch("app.optimizer.datetime", _fixed_datetime(now)):
            decision = optimizer._decide(state)

        self.assertTrue(decision.standby_holdoff_active)
        self.assertEqual(decision.import_limit, 0.0)
        self.assertEqual(decision.ems_mode, MODE_MAX_SELF)
        self.assertEqual(decision.pv_max_power_limit, 1.0)
        self.assertIn("charge holdoff", decision.import_reason)

    def test_decide_high_fit_daytime_exports_at_discharge_cap(self) -> None:
        optimizer = self._optimizer()
        now = datetime(2026, 4, 5, 13, 0, tzinfo=timezone.utc)
        state = self._state(
            now,
            sun_above_horizon=True,
            pv_kw=8.0,
            solar_power_now_kw=8.0,
            load_kw=1.0,
            battery_soc=100.0,
            available_discharge_energy_kwh=10.0,
            feedin_price=1.20,
            feedin_price_cents=120.0,
            current_price=0.30,
            current_price_cents=30.0,
            ess_max_discharge_kw=8.0,
            forecast_remaining_kwh=30.0,
        )

        with patch("app.optimizer.datetime", _fixed_datetime(now)):
            decision = optimizer._decide(state)

        self.assertEqual(decision.export_limit, 8.0)
        self.assertEqual(decision.import_limit, 0.0)
        self.assertEqual(decision.ems_mode, MODE_CMD_DISCHARGE_PV)
        self.assertIn("High tier", decision.export_reason)

    def test_decide_demand_window_blocks_import_but_keeps_export_when_fit_is_high(self) -> None:
        optimizer = self._optimizer()
        now = datetime(2026, 4, 5, 13, 0, tzinfo=timezone.utc)
        state = self._state(
            now,
            sun_above_horizon=True,
            pv_kw=7.0,
            solar_power_now_kw=7.0,
            load_kw=1.0,
            battery_soc=100.0,
            available_discharge_energy_kwh=10.0,
            feedin_price=1.10,
            feedin_price_cents=110.0,
            demand_window_active=True,
        )

        with patch("app.optimizer.datetime", _fixed_datetime(now)):
            decision = optimizer._decide(state)

        self.assertEqual(decision.import_limit, 0.0)
        self.assertGreater(decision.export_limit, 0.0)
        self.assertEqual(decision.ems_mode, MODE_CMD_DISCHARGE_PV)
        self.assertEqual(decision.trace_values["import_branch"], "demand_window_block")
        self.assertIn("demand window", decision.import_reason)

    def test_decide_cheap_topup_imports_when_price_is_low_and_fit_is_unattractive(self) -> None:
        optimizer = self._optimizer()
        now = datetime(2026, 4, 5, 11, 0, tzinfo=timezone.utc)
        state = self._state(
            now,
            sun_above_horizon=True,
            battery_soc=15.0,
            pv_kw=0.2,
            solar_power_now_kw=0.2,
            load_kw=1.5,
            current_price=0.01,
            current_price_cents=1.0,
            feedin_price=0.0,
            feedin_price_cents=0.0,
            ess_max_charge_kw=6.0,
            forecast_remaining_kwh=2.0,
        )

        with patch("app.optimizer.datetime", _fixed_datetime(now)):
            decision = optimizer._decide(state)

        self.assertEqual(decision.import_limit, 2.0)
        self.assertEqual(decision.ems_mode, "Command Charging (PV First)")
        self.assertIn("cheap", decision.import_reason)

    def test_decide_negative_fi_t_with_full_battery_curtails_pv_to_cover_load(self) -> None:
        optimizer = self._optimizer()
        now = datetime(2026, 4, 5, 12, 30, tzinfo=timezone.utc)
        state = self._state(
            now,
            sun_above_horizon=True,
            pv_kw=5.0,
            solar_power_now_kw=5.0,
            load_kw=1.8,
            battery_soc=100.0,
            available_discharge_energy_kwh=10.0,
            current_price=0.20,
            current_price_cents=20.0,
            feedin_price=-0.05,
            feedin_price_cents=-5.0,
        )

        with patch("app.optimizer.datetime", _fixed_datetime(now)):
            decision = optimizer._decide(state)

        self.assertEqual(decision.export_limit, 0.0)
        self.assertEqual(decision.import_limit, 0.0)
        self.assertEqual(decision.ems_mode, MODE_MAX_SELF)
        self.assertEqual(decision.pv_max_power_limit, 2.0)
        self.assertIn("negative", decision.export_reason)

    def test_decide_solar_surplus_bypass_exports_real_pv_excess_at_low_soc(self) -> None:
        optimizer = self._optimizer(
            min_export_target_soc=90.0,
            battery_full_safeguard_enabled=False,
            export_threshold_low=0.10,
            export_threshold_medium=0.20,
            export_threshold_high=1.00,
        )
        now = datetime(2026, 4, 5, 14, 0, tzinfo=timezone.utc)
        state = self._state(
            now,
            sun_above_horizon=True,
            pv_kw=6.5,
            solar_power_now_kw=6.5,
            load_kw=1.0,
            battery_soc=35.0,
            available_discharge_energy_kwh=3.5,
            feedin_price=0.12,
            feedin_price_cents=12.0,
            forecast_remaining_kwh=25.0,
            current_ems_mode=MODE_CMD_DISCHARGE_PV,
        )

        with patch("app.optimizer.datetime", _fixed_datetime(now)):
            decision = optimizer._decide(state)

        self.assertTrue(decision.solar_surplus_bypass)
        self.assertGreater(decision.export_limit, 0.0)
        self.assertLessEqual(decision.export_limit, 5.5)
        self.assertIn("Solar bypass", decision.export_reason)

    def test_decide_battery_full_safeguard_blocks_export_before_sunset(self) -> None:
        optimizer = self._optimizer(battery_full_hours_before_sunset=2.0)
        now = datetime(2026, 4, 5, 13, 0, tzinfo=timezone.utc)
        future_slot = (now + timedelta(minutes=30)).isoformat()
        state = self._state(
            now,
            sun_above_horizon=True,
            pv_kw=1.0,
            solar_power_now_kw=1.0,
            load_kw=2.0,
            battery_soc=75.0,
            battery_capacity_kwh=10.0,
            available_discharge_energy_kwh=2.0,
            feedin_price=0.30,
            feedin_price_cents=30.0,
            ess_max_charge_kw=3.0,
            forecast_remaining_kwh=2.0,
            solcast_detailed=[{"period_start": future_slot, "pv_estimate": 1.0}],
        )

        with patch("app.optimizer.datetime", _fixed_datetime(now)):
            decision = optimizer._decide(state)

        self.assertTrue(decision.battery_full_safeguard)
        self.assertEqual(decision.export_limit, 0.0)
        self.assertIn("saving for sunset", decision.export_reason)

    def test_morning_slow_charge_becomes_active_with_enough_forecast_and_positive_fit(self) -> None:
        optimizer = self._optimizer(
            morning_slow_charge_enabled=True,
            morning_slow_charge_until="11:00",
            morning_slow_charge_rate_kw=2.0,
            morning_slow_charge_min_feedin_price=0.05,
            battery_full_safeguard_enabled=False,
            export_threshold_low=0.10,
            export_threshold_medium=0.20,
        )
        now = datetime(2026, 4, 5, 8, 30, tzinfo=timezone.utc)
        state = self._state(
            now,
            sun_above_horizon=True,
            pv_kw=4.5,
            solar_power_now_kw=4.5,
            load_kw=1.0,
            battery_soc=40.0,
            battery_capacity_kwh=10.0,
            available_discharge_energy_kwh=4.0,
            feedin_price=0.10,
            feedin_price_cents=10.0,
            forecast_remaining_kwh=25.0,
            current_export_limit=0.0,
            grid_export_power_kw=0.0,
        )

        with patch("app.optimizer.datetime", _fixed_datetime(now)):
            decision = optimizer._decide(state)

        self.assertTrue(decision.morning_slow_charge_active)
        self.assertEqual(decision.ess_charge_limit, 2.0)
        self.assertEqual(decision.export_limit, 1.5)
        self.assertIn("Slow charge", decision.export_reason)

    def test_morning_slow_charge_ramps_export_up_from_existing_limit(self) -> None:
        optimizer = self._optimizer(
            morning_slow_charge_enabled=True,
            morning_slow_charge_until="11:00",
            morning_slow_charge_rate_kw=2.0,
            morning_slow_charge_min_feedin_price=0.05,
            morning_slow_export_ramp_up_step_kw=0.8,
            battery_full_safeguard_enabled=False,
        )
        now = datetime(2026, 4, 5, 8, 45, tzinfo=timezone.utc)
        state = self._state(
            now,
            sun_above_horizon=True,
            pv_kw=5.0,
            solar_power_now_kw=5.0,
            load_kw=1.0,
            battery_soc=45.0,
            battery_capacity_kwh=10.0,
            available_discharge_energy_kwh=4.5,
            feedin_price=0.10,
            feedin_price_cents=10.0,
            forecast_remaining_kwh=16.0,
            current_export_limit=1.0,
            grid_export_power_kw=0.9,
        )

        with patch("app.optimizer.datetime", _fixed_datetime(now)):
            decision = optimizer._decide(state)

        self.assertTrue(decision.morning_slow_charge_active)
        self.assertEqual(decision.export_limit, 1.8)

    def test_morning_slow_charge_stays_off_when_runtime_disabled(self) -> None:
        optimizer = self._optimizer(morning_slow_charge_enabled=True)
        optimizer._morning_slow_charge_runtime_disabled = True
        now = datetime(2026, 4, 5, 8, 30, tzinfo=timezone.utc)
        state = self._state(
            now,
            sun_above_horizon=True,
            feedin_price=0.10,
            forecast_remaining_kwh=20.0,
        )

        with patch("app.optimizer.datetime", _fixed_datetime(now)):
            decision = optimizer._decide(state)

        self.assertFalse(decision.morning_slow_charge_active)


if __name__ == "__main__":
    unittest.main()