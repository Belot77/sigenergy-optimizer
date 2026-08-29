from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from app.config import Settings
from app.models import Decision, SolarState
from app.optimizer import MODE_MAX_SELF, SigEnergyOptimizer
from app.routers.api import _validate_config_value


class _DummyHA:
    pass


class Haos52ControlCleanupTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._old_state_db_path = os.environ.get("STATE_DB_PATH")
        os.environ["STATE_DB_PATH"] = os.path.join(self._tmp.name, "state.db")
        self._optimizers: list[SigEnergyOptimizer] = []

    def tearDown(self) -> None:
        for optimizer in self._optimizers:
            optimizer._state_store.close()
        if self._old_state_db_path is None:
            os.environ.pop("STATE_DB_PATH", None)
        else:
            os.environ["STATE_DB_PATH"] = self._old_state_db_path
        self._tmp.cleanup()

    def _optimizer(self, **overrides: object) -> SigEnergyOptimizer:
        values: dict[str, object] = {
            "battery_full_safeguard_enabled": False,
            "evening_boost_enabled": False,
            "morning_dump_enabled": False,
            "morning_slow_charge_enabled": False,
            "solar_surplus_bypass_enabled": False,
            "standby_holdoff_enabled": False,
        }
        values.update(overrides)
        optimizer = SigEnergyOptimizer(_DummyHA(), Settings(**values))
        self._optimizers.append(optimizer)
        return optimizer

    def test_morning_dump_hard_minimum_blocks_start_and_continue(self) -> None:
        default_optimizer = self._optimizer()
        self.assertEqual(30.0, default_optimizer.cfg.morning_dump_min_soc)

        optimizer = self._optimizer(
            morning_dump_enabled=True,
            morning_dump_min_soc=42.0,
        )
        now_ts = datetime.now().timestamp()
        state = SolarState(
            battery_soc=42.1,
            load_kw=0.0,
            solcast_detailed=[
                {"period_start": now_ts + 1200, "pv_estimate": 100.0},
            ],
        )

        def active() -> bool:
            return optimizer._morning_dump_active(
                state,
                dump_start=now_ts - 60,
                dump_end=now_ts + 600,
                productive_solar_end_ts=now_ts + 3600,
                bat_fill_need_kwh=10.0,
                now_ts=now_ts,
            )

        self.assertTrue(active())
        # A prior active decision must not create a continuation exemption.
        optimizer._last_decision = Decision(morning_dump_active=True)
        for blocked_soc in (42.0, 41.9):
            with self.subTest(battery_soc=blocked_soc):
                state.battery_soc = blocked_soc
                self.assertFalse(active())

    def test_morning_dump_minimum_soc_rejects_out_of_range_values(self) -> None:
        for valid_soc in (0.0, 100.0):
            with self.subTest(valid_soc=valid_soc):
                self.assertEqual(
                    valid_soc,
                    Settings(morning_dump_min_soc=valid_soc).morning_dump_min_soc,
                )
                self.assertIsNone(
                    _validate_config_value(
                        Settings(),
                        "morning_dump_min_soc",
                        valid_soc,
                    )
                )

        for invalid_soc in (-0.1, 100.1):
            with self.subTest(invalid_soc=invalid_soc):
                with self.assertRaises(ValidationError):
                    Settings(morning_dump_min_soc=invalid_soc)
                self.assertEqual(
                    "must be between 0 and 100",
                    _validate_config_value(
                        Settings(),
                        "morning_dump_min_soc",
                        invalid_soc,
                    ),
                )

    def test_morning_dump_legacy_key_ui_matches_window_implementation(self) -> None:
        optimizer = self._optimizer(morning_dump_hours_before_sunrise=0.5)
        sunrise_ts = 1_800_000_000.0

        dump_start, dump_end = optimizer._morning_dump_window(SolarState(), sunrise_ts)

        self.assertEqual(sunrise_ts + 1800, dump_start)
        self.assertEqual(sunrise_ts + 3600, dump_end)
        html = (Path(__file__).parents[1] / "templates" / "index.html").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "['morning_dump_hours_before_sunrise', 'Window Duration (Ends 1 Hour After Sunrise)'",
            html,
        )
        self.assertIn(
            "0.5 starts 30 minutes after sunrise and can run for up to 30 minutes",
            html,
        )

    def test_morning_slow_charge_minimum_feedin_price_is_inclusive(self) -> None:
        optimizer = self._optimizer(
            morning_slow_charge_enabled=True,
            morning_slow_charge_until="11:00",
            morning_slow_charge_min_feedin_price=0.01,
            morning_slow_charge_base_load_kw=0.0,
        )
        now = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
        now_ts = now.timestamp()
        state = SolarState(
            battery_capacity_kwh=10.0,
            available_discharge_energy_kwh=10.0,
            forecast_remaining_kwh=0.0,
            sun_above_horizon=True,
            feedin_price=0.01,
        )

        self.assertTrue(
            optimizer._morning_slow_charge_active(
                state,
                now,
                now_ts,
                slow_end_ts=now_ts + 3600,
            )
        )
        state.feedin_price = 0.0099
        self.assertFalse(
            optimizer._morning_slow_charge_active(
                state,
                now,
                now_ts,
                slow_end_ts=now_ts + 3600,
            )
        )

    def test_nighttime_soc_guard_reports_target_without_changing_policy(self) -> None:
        optimizer = self._optimizer(
            min_export_target_soc=90.0,
            export_guard_relax_soc=95.0,
        )
        now_ts = datetime.now().timestamp()
        state = SolarState(
            sigenergy_mode="Automated",
            sigenergy_mode_observed=True,
            current_ems_mode=MODE_MAX_SELF,
            ems_mode_observed=True,
            battery_soc=50.0,
            battery_capacity_kwh=30.0,
            available_discharge_energy_kwh=15.0,
            battery_power_sensor_kw=-0.4,
            current_price=0.30,
            current_price_cents=30.0,
            price_is_actual=True,
            feedin_price=0.15,
            feedin_price_cents=15.0,
            load_kw=1.0,
            pv_kw=0.0,
            solar_power_now_kw=0.0,
            ess_max_charge_kw=25.0,
            ess_max_discharge_kw=25.0,
            forecast_remaining_kwh=0.0,
            forecast_today_kwh=0.0,
            forecast_tomorrow_kwh=100.0,
            next_sunrise_ts=now_ts + (10.0 * 3600),
            next_sunset_ts=now_ts + (20.0 * 3600),
            hours_to_sunrise=10.0,
            hours_to_sunset=20.0,
            sun_above_horizon=False,
            current_export_limit=0.0,
            current_import_limit=0.0,
            current_pv_max_power_limit=25.0,
        )

        decision = optimizer._decide(state)

        self.assertEqual(0.0, decision.export_limit)
        self.assertTrue(decision.is_evening_or_night)
        self.assertTrue(bool(decision.trace_gates.get("export_forecast_guard")))
        self.assertFalse(bool(decision.trace_gates.get("export_blocked_for_forecast")))
        self.assertEqual(
            "closed_below_export_floor",
            decision.trace_values.get("desired_export_source"),
        )
        self.assertEqual("Export blocked, below 90% target", decision.export_reason)
        self.assertNotIn("low forecast", decision.export_reason.lower())

    def test_daytime_forecast_block_still_reports_low_forecast(self) -> None:
        optimizer = self._optimizer(min_export_target_soc=90.0)
        state = SolarState(
            battery_soc=50.0,
            current_price=0.30,
            current_price_cents=30.0,
            feedin_price=0.15,
            feedin_price_cents=15.0,
        )

        reason = optimizer._export_reason(
            state,
            spike=False,
            solar_override=False,
            morning_dump=False,
            export_blocked=True,
            forecast_guard=False,
            is_evening_or_night=False,
            export_min_soc=20.0,
            pv_safeguard=False,
            tier_limit=5.0,
            morning_slow_charge=False,
            surplus_bypass=False,
            evening_boost=False,
            safeguard=False,
            desired_export=0.0,
            positive_fit_override=False,
        )

        self.assertEqual("Export blocked, low forecast", reason)

    def test_negative_import_price_pv_cap_remains_separate(self) -> None:
        optimizer = self._optimizer(pv_max_power_normal=25.0)
        state = SolarState(
            current_price=-0.20,
            price_is_negative=True,
            load_kw=1.0,
        )

        desired_pv_max = optimizer._desired_pv_max_power(
            state,
            standby_holdoff=False,
            morning_dump=False,
            morning_slow_charge=False,
            desired_export=0.0,
        )

        self.assertEqual(0.1, desired_pv_max)


if __name__ == "__main__":
    unittest.main()
