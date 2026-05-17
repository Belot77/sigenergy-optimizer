from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.config import Settings
from app.models import SolarState
from app.optimizer import MODE_CMD_CHARGE_GRID, MODE_CMD_DISCHARGE_PV, MODE_MAX_SELF, SigEnergyOptimizer


def _fixed_datetime(now: datetime) -> type[datetime]:
    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return now
            return now.astimezone(tz)

    return _FixedDateTime


class _RecordingHA:
    def __init__(self) -> None:
        self.state_values: dict[str, str | float] = {}
        self.select_calls: list[tuple[str, str]] = []
        self.number_calls: list[tuple[str, float]] = []

    async def get_state_value(self, entity_id: str, default=""):
        return self.state_values.get(entity_id, default)

    async def select_option(self, entity_id: str, value: str) -> bool:
        self.select_calls.append((entity_id, value))
        self.state_values[entity_id] = value
        return True

    async def set_number(self, entity_id: str, value: float) -> bool:
        self.number_calls.append((entity_id, float(value)))
        self.state_values[entity_id] = float(value)
        return True

    async def turn_on(self, entity_id: str) -> bool:
        self.state_values[entity_id] = "on"
        return True


class ManualModePrecedenceTests(unittest.IsolatedAsyncioTestCase):
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

    def _optimizer(self, ha: _RecordingHA, **overrides: float | str | bool) -> SigEnergyOptimizer:
        optimizer = SigEnergyOptimizer(ha, Settings(**overrides))
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
            "ess_max_discharge_kw": 7.0,
            "ess_max_charge_kw": 6.0,
            "current_export_limit": 0.0,
            "current_import_limit": 0.0,
            "current_pv_max_power_limit": 25.0,
            "current_ess_charge_limit": 6.0,
            "current_ess_discharge_limit": 7.0,
            "current_ems_mode": MODE_MAX_SELF,
            "ha_control_enabled": True,
            "current_price": 0.20,
            "current_price_cents": 20.0,
            "feedin_price": 0.05,
            "feedin_price_cents": 5.0,
            "price_is_actual": True,
            "forecast_remaining_kwh": 20.0,
            "forecast_today_kwh": 20.0,
            "forecast_tomorrow_kwh": 20.0,
            "solar_power_now_kw": 4.0 if sun_above_horizon else 0.0,
            "sun_above_horizon": sun_above_horizon,
            "next_sunrise_ts": next_sunrise.timestamp(),
            "next_sunset_ts": next_sunset.timestamp(),
            "hours_to_sunrise": max((next_sunrise - now).total_seconds() / 3600, 0.0),
            "hours_to_sunset": max((next_sunset - now).total_seconds() / 3600, 0.0),
            "sigenergy_mode": "Automated",
        }
        defaults.update(overrides)
        return SolarState(**defaults)

    async def test_tick_freezes_decision_and_reapplies_manual_targets(self) -> None:
        ha = _RecordingHA()
        optimizer = self._optimizer(
            ha,
            pv_max_power_value=30.0,
            ess_charge_limit_value=6.0,
            ess_discharge_limit_value=7.0,
        )
        now = datetime(2026, 4, 5, 10, 0, tzinfo=timezone.utc)
        state = self._state(
            now,
            sun_above_horizon=True,
            current_ems_mode=MODE_MAX_SELF,
            current_export_limit=0.0,
            current_import_limit=0.0,
            current_pv_max_power_limit=25.0,
            current_ess_charge_limit=6.0,
            current_ess_discharge_limit=7.0,
            ess_charge_limit_entity_max_kw=6.0,
            ess_discharge_limit_entity_max_kw=7.0,
        )
        optimizer._manual_mode_override = optimizer.cfg.full_export_option

        async def _fake_read_state() -> SolarState:
            return state

        optimizer._read_state = _fake_read_state  # type: ignore[method-assign]

        with patch("app.optimizer.datetime", _fixed_datetime(now)):
            await optimizer._tick()

        self.assertEqual(optimizer.last_decision.ems_mode, MODE_MAX_SELF)
        self.assertEqual(optimizer.last_decision.export_limit, 0.0)
        self.assertEqual(
            optimizer.last_decision.outcome_reason,
            f"Manual mode active ({optimizer.cfg.full_export_option}); optimizer writes paused",
        )
        self.assertIn((optimizer.cfg.ems_mode_select, MODE_CMD_DISCHARGE_PV), ha.select_calls)

        number_writes = dict(ha.number_calls)
        self.assertEqual(number_writes[optimizer.cfg.grid_export_limit], 7.0)
        self.assertEqual(number_writes[optimizer.cfg.grid_import_limit], optimizer.cfg.block_flow_limit_value)
        self.assertEqual(number_writes[optimizer.cfg.pv_max_power_limit], optimizer.cfg.pv_max_power_value)

    async def test_tick_uses_automated_decision_when_no_manual_override(self) -> None:
        ha = _RecordingHA()
        optimizer = self._optimizer(ha)
        now = datetime(2026, 4, 5, 22, 0, tzinfo=timezone.utc)
        state = self._state(
            now,
            sun_above_horizon=False,
            battery_soc=20.0,
            current_price=-0.05,
            current_price_cents=-5.0,
            feedin_price=0.0,
            feedin_price_cents=0.0,
            forecast_remaining_kwh=0.0,
            forecast_today_kwh=0.0,
            ess_max_charge_kw=6.0,
        )

        async def _fake_read_state() -> SolarState:
            return state

        async def _noop_apply(_state: SolarState, _decision) -> None:
            return None

        optimizer._read_state = _fake_read_state  # type: ignore[method-assign]
        optimizer._apply = _noop_apply  # type: ignore[method-assign]

        with patch("app.optimizer.datetime", _fixed_datetime(now)):
            await optimizer._tick()

        self.assertEqual(optimizer.last_decision.ems_mode, MODE_CMD_CHARGE_GRID)
        self.assertEqual(optimizer.last_decision.import_limit, 6.0)
        self.assertNotIn("Manual mode active", optimizer.last_decision.outcome_reason)


if __name__ == "__main__":
    unittest.main()