from __future__ import annotations

import os
import tempfile
import unittest

from app.config import Settings
from app.models import SolarState
from app.optimizer import SigEnergyOptimizer


class _DummyHA:
    pass


class NegativeFitPVCurtailmentTests(unittest.TestCase):
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

    def _optimizer(self) -> SigEnergyOptimizer:
        optimizer = SigEnergyOptimizer(_DummyHA(), Settings())
        self._optimizers.append(optimizer)
        return optimizer

    def test_default_pv_export_topoff_requires_100_percent(self) -> None:
        optimizer = self._optimizer()

        self.assertEqual(50.0, optimizer.cfg.daytime_topup_max_soc)
        self.assertEqual(100.0, optimizer._topoff_target_soc())

    def test_negative_fit_full_battery_keeps_normal_pv_max(self) -> None:
        optimizer = self._optimizer()
        state = SolarState(
            battery_soc=100.0,
            battery_capacity_kwh=40.3,
            current_price=0.093,
            current_price_cents=9.3,
            feedin_price=-0.008,
            feedin_price_cents=-0.8,
            feedin_is_negative=True,
            load_kw=1.1,
            pv_kw=0.7,
            solar_power_now_kw=2.7,
            ess_max_discharge_kw=25.0,
            forecast_tomorrow_kwh=77.0,
            hours_to_sunrise=15.0,
            next_sunrise_ts=15.0 * 3600,
            next_sunset_ts=2.0 * 3600,
            sun_above_horizon=True,
        )

        desired_pv_max = optimizer._desired_pv_max_power(
            state,
            standby_holdoff=False,
            morning_dump=False,
            morning_slow_charge=False,
            desired_export=0.0,
        )

        self.assertEqual(
            optimizer.cfg.pv_max_power_normal,
            desired_pv_max,
        )


if __name__ == "__main__":
    unittest.main()
