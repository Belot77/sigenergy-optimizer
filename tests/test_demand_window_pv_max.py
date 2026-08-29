from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta

from app.config import Settings
from app.models import SolarState
from app.optimizer import MODE_MAX_SELF, SigEnergyOptimizer


class _DummyHA:
    pass


class DemandWindowPVMaxTests(unittest.TestCase):
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
            "pv_max_power_normal": 25.0,
        }
        values.update(overrides)
        optimizer = SigEnergyOptimizer(_DummyHA(), Settings(**values))
        self._optimizers.append(optimizer)
        return optimizer

    @staticmethod
    def _state(
        now_ts: float,
        *,
        demand_window_active: bool,
        near_sunset: bool,
        **overrides: object,
    ) -> SolarState:
        hours_to_sunset = 0.5 if near_sunset else 6.0
        state = SolarState(
            sigenergy_mode="Automated",
            sigenergy_mode_observed=True,
            current_ems_mode=MODE_MAX_SELF,
            ems_mode_observed=True,
            battery_soc=60.0,
            battery_capacity_kwh=30.0,
            available_discharge_energy_kwh=18.0,
            battery_power_sensor_kw=-0.4,
            current_price=0.30,
            current_price_cents=30.0,
            price_is_actual=True,
            feedin_price=0.0,
            feedin_price_cents=0.0,
            load_kw=1.4,
            pv_kw=1.0,
            solar_power_now_kw=4.0,
            ess_max_charge_kw=25.0,
            ess_max_discharge_kw=25.0,
            forecast_remaining_kwh=0.0,
            forecast_today_kwh=0.0,
            forecast_tomorrow_kwh=0.0,
            next_sunrise_ts=now_ts + (14.0 * 3600),
            next_sunset_ts=now_ts + (hours_to_sunset * 3600),
            hours_to_sunrise=14.0,
            hours_to_sunset=hours_to_sunset,
            sun_above_horizon=True,
            demand_window_active=demand_window_active,
            current_export_limit=0.0,
            current_import_limit=0.0,
            current_pv_max_power_limit=2.0,
        )
        for key, value in overrides.items():
            setattr(state, key, value)
        return state

    def test_evening_demand_window_keeps_normal_pv_max_through_decide(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer()
        state = self._state(
            now_ts,
            demand_window_active=True,
            near_sunset=True,
        )

        decision = optimizer._decide(state)

        self.assertTrue(bool(decision.trace_gates.get("is_evening_or_night")))
        self.assertTrue(bool(decision.trace_gates.get("demand_window_active")))
        self.assertEqual(0.0, decision.export_limit)
        self.assertEqual(0.0, decision.import_limit)
        self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
        self.assertFalse(bool(decision.trace_gates.get("battery_only_mode")))
        self.assertEqual(optimizer.cfg.pv_max_power_normal, decision.pv_max_power_limit)
        self.assertEqual(
            optimizer.cfg.pv_max_power_normal,
            decision.trace_values.get("desired_pv_max_limit_kw"),
        )
        self.assertEqual("demand_window_block", decision.trace_values.get("import_branch"))

    def test_ordinary_nighttime_closed_flow_restores_normal_pv_max_through_decide(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer()
        state = self._state(
            now_ts,
            demand_window_active=False,
            near_sunset=False,
            sun_above_horizon=False,
            next_sunset_ts=now_ts + (20.0 * 3600),
            hours_to_sunset=20.0,
        )

        decision = optimizer._decide(state)

        self.assertTrue(bool(decision.trace_gates.get("is_evening_or_night")))
        self.assertFalse(bool(decision.trace_gates.get("demand_window_active")))
        self.assertEqual(0.0, decision.export_limit)
        self.assertEqual(0.0, decision.import_limit)
        self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
        self.assertFalse(bool(decision.trace_gates.get("battery_only_mode")))
        self.assertEqual("current_pv_max_below_normal", decision.trace_values.get("pv_cap_reason"))
        self.assertEqual(optimizer.cfg.pv_max_power_normal, decision.pv_max_power_limit)
        self.assertEqual(
            optimizer.cfg.pv_max_power_normal,
            decision.trace_values.get("desired_pv_max_limit_kw"),
        )

    def test_demand_window_does_not_override_standby_holdoff_pv_cap(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            standby_holdoff_enabled=True,
            pv_forecast_holdoff_kwh=120.0,
        )
        optimizer._today_at = lambda _time: datetime.now() + timedelta(hours=1)
        state = self._state(
            now_ts,
            demand_window_active=True,
            near_sunset=False,
            forecast_remaining_kwh=150.0,
            forecast_today_kwh=150.0,
            price_forecast_entries=[
                {"start_time": now_ts, "per_kwh": -0.10},
            ],
            current_pv_max_power_limit=25.0,
        )

        decision = optimizer._decide(state)

        self.assertFalse(bool(decision.trace_gates.get("is_evening_or_night")))
        self.assertTrue(bool(decision.trace_gates.get("demand_window_active")))
        self.assertTrue(bool(decision.trace_gates.get("standby_holdoff_active")))
        self.assertEqual(0.0, decision.export_limit)
        self.assertEqual(0.0, decision.import_limit)
        self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
        self.assertFalse(bool(decision.trace_gates.get("battery_only_mode")))
        self.assertEqual("standby_holdoff_active", decision.trace_values.get("pv_cap_reason"))
        self.assertEqual(2.0, decision.pv_max_power_limit)


if __name__ == "__main__":
    unittest.main()
