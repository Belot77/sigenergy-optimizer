from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from app.config import Settings
from app.models import SolarState
from app.optimizer import SigEnergyOptimizer


class _DummyHA:
    pass


class EveningBoostGateTests(unittest.TestCase):
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

    def _optimizer(self, minimum_tomorrow_forecast_kwh: float) -> SigEnergyOptimizer:
        cfg = Settings(
            evening_boost_enabled=True,
            evening_boost_min_tomorrow_forecast_kwh=minimum_tomorrow_forecast_kwh,
            evening_boost_forecast_safety=1.1,
        )
        optimizer = SigEnergyOptimizer(_DummyHA(), cfg)
        optimizer._tz = timezone.utc
        self._optimizers.append(optimizer)
        return optimizer

    def test_evening_boost_stays_off_below_user_minimum_forecast(self) -> None:
        optimizer = self._optimizer(minimum_tomorrow_forecast_kwh=100.0)
        now = datetime.now()
        state = SolarState(
            battery_soc=85.0,
            forecast_tomorrow_kwh=95.0,
            feedin_forecast_entries=[],
        )

        active = optimizer._evening_export_boost_active(
            state,
            now.timestamp(),
            (now - timedelta(minutes=30)).timestamp(),
            sunrise_soc_target=60.0,
            bat_fill_need_kwh=20.0,
        )

        self.assertFalse(active)

    def test_evening_boost_can_activate_once_user_minimum_is_met(self) -> None:
        optimizer = self._optimizer(minimum_tomorrow_forecast_kwh=100.0)
        now = datetime.now()
        state = SolarState(
            battery_soc=85.0,
            forecast_tomorrow_kwh=120.0,
            feedin_forecast_entries=[],
        )

        active = optimizer._evening_export_boost_active(
            state,
            now.timestamp(),
            (now - timedelta(minutes=30)).timestamp(),
            sunrise_soc_target=60.0,
            bat_fill_need_kwh=20.0,
        )

        self.assertTrue(active)

    def test_evening_boost_stays_off_when_tomorrow_cannot_refill_battery(self) -> None:
        optimizer = self._optimizer(minimum_tomorrow_forecast_kwh=20.0)
        now = datetime(2026, 1, 15, 19, 18, tzinfo=timezone.utc)
        state = SolarState(
            battery_soc=85.0,
            forecast_tomorrow_kwh=30.0,
            feedin_forecast_entries=[],
        )

        active = optimizer._evening_export_boost_active(
            state,
            now.timestamp(),
            (now - timedelta(hours=2)).timestamp(),
            sunrise_soc_target=60.0,
            bat_fill_need_kwh=30.0,
        )

        self.assertFalse(active)

    def test_evening_boost_stays_off_for_high_overnight_fit(self) -> None:
        optimizer = self._optimizer(minimum_tomorrow_forecast_kwh=100.0)
        now = datetime(2026, 1, 15, 19, 18, tzinfo=timezone.utc)
        state = SolarState(
            battery_soc=85.0,
            forecast_tomorrow_kwh=120.0,
            feedin_forecast_entries=[
                {
                    optimizer.cfg.price_forecast_time_key: (
                        now + timedelta(hours=2)
                    ).isoformat(),
                    optimizer.cfg.feedin_forecast_value_key: (
                        optimizer.cfg.export_threshold_medium
                    ),
                }
            ],
        )

        active = optimizer._evening_export_boost_active(
            state,
            now.timestamp(),
            (now - timedelta(hours=2)).timestamp(),
            sunrise_soc_target=60.0,
            bat_fill_need_kwh=20.0,
        )

        self.assertFalse(active)

    def test_evening_boost_stays_off_after_productive_day_midnight(self) -> None:
        optimizer = self._optimizer(minimum_tomorrow_forecast_kwh=100.0)
        now = datetime(2026, 1, 16, 0, 1, tzinfo=timezone.utc)
        state = SolarState(
            battery_soc=85.0,
            forecast_tomorrow_kwh=120.0,
            feedin_forecast_entries=[],
        )

        active = optimizer._evening_export_boost_active(
            state,
            now.timestamp(),
            datetime(2026, 1, 15, 16, 30, tzinfo=timezone.utc).timestamp(),
            sunrise_soc_target=60.0,
            bat_fill_need_kwh=20.0,
        )

        self.assertFalse(active)


if __name__ == "__main__":
    unittest.main()
