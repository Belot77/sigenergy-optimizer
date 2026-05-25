from __future__ import annotations

import os
import tempfile
import unittest

from app.config import Settings
from app.models import SolarState
from app.optimizer import SigEnergyOptimizer


class _DummyHA:
    pass


class PoorTomorrowExportTests(unittest.TestCase):
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

    def _optimizer(self) -> SigEnergyOptimizer:
        cfg = Settings(
            forecast_safety_charging=1.25,
            export_threshold_low=0.01,
            export_threshold_medium=0.2,
            export_threshold_high=1.0,
            export_limit_low=5.0,
            export_limit_medium=12.0,
            export_limit_high=25.0,
            min_grid_transfer_kw=0.5,
        )
        optimizer = SigEnergyOptimizer(_DummyHA(), cfg)
        self._optimizers.append(optimizer)
        return optimizer

    @staticmethod
    def _state(forecast_tomorrow_kwh: float) -> SolarState:
        return SolarState(
            battery_soc=100.0,
            battery_capacity_kwh=40.3,
            forecast_tomorrow_kwh=forecast_tomorrow_kwh,
            feedin_price=0.09,
            feedin_price_cents=9.0,
            pv_kw=2.1,
            solar_power_now_kw=4.4,
            load_kw=0.9,
            ess_max_discharge_kw=100.0,
            sun_above_horizon=True,
        )

    def _desired_export(self, optimizer: SigEnergyOptimizer, state: SolarState) -> float:
        return optimizer._desired_export_limit(
            state,
            spike=False,
            solar_override=False,
            export_blocked=False,
            forecast_guard=False,
            export_min_soc=20.0,
            positive_fit_override=False,
            surplus_bypass=False,
            evening_boost=False,
            morning_dump=False,
            morning_dump_limit=25.0,
            battery_full_safeguard_block=False,
            tier_limit=10.0,
            hours_to_sunrise=10.0,
            cap=state.battery_capacity_kwh,
            pv_surplus=3.5,
            is_evening_or_night=False,
            morning_slow_charge_active=False,
            within_morning_grace=False,
        )

    def test_low_tomorrow_forecast_caps_full_battery_export_to_measured_surplus(self) -> None:
        optimizer = self._optimizer()
        state = self._state(forecast_tomorrow_kwh=20.0)

        desired = self._desired_export(optimizer, state)

        self.assertEqual(desired, 1.2)

    def test_good_tomorrow_forecast_keeps_existing_full_battery_headroom_behavior(self) -> None:
        optimizer = self._optimizer()
        state = self._state(forecast_tomorrow_kwh=80.0)

        desired = self._desired_export(optimizer, state)

        self.assertEqual(desired, 3.5)


if __name__ == "__main__":
    unittest.main()
