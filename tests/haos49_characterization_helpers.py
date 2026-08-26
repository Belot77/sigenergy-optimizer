from __future__ import annotations

import os
import tempfile
import unittest
from contextlib import contextmanager
from datetime import datetime, time, timedelta
from unittest.mock import patch

from app.config import Settings
from app.models import SolarState
from app.optimizer import MODE_MAX_SELF, SigEnergyOptimizer


class RecordingHA:
    """Small HA double for decision/readback sequencing characterization."""

    def __init__(
        self,
        states: dict[str, dict[str, object]] | None = None,
        *,
        state_values: dict[str, object] | None = None,
        settle_numbers: bool = True,
        settle_selects: bool = True,
        settle_switch: bool = False,
        turn_on_result: bool = True,
    ) -> None:
        self.states = dict(states or {})
        self.state_values = dict(state_values or {})
        self.settle_numbers = settle_numbers
        self.settle_selects = settle_selects
        self.settle_switch = settle_switch
        self.turn_on_result = turn_on_result
        self.calls: list[tuple[str, str, object]] = []

    async def bulk_states(self, entity_ids: list[str]) -> dict[str, dict[str, object]]:
        return {
            entity_id: self.states[entity_id]
            for entity_id in entity_ids
            if entity_id in self.states
        }

    async def turn_on(self, entity_id: str) -> bool:
        self.calls.append(("turn_on", entity_id, True))
        if self.turn_on_result and self.settle_switch:
            self.state_values[entity_id] = "on"
        return self.turn_on_result

    async def select_option(self, entity_id: str, value: str) -> bool:
        self.calls.append(("select_option", entity_id, value))
        if self.settle_selects:
            self.state_values[entity_id] = value
        return True

    async def set_number(self, entity_id: str, value: float) -> bool:
        self.calls.append(("set_number", entity_id, value))
        if self.settle_numbers:
            self.state_values[entity_id] = value
        return True

    async def set_input_text(self, entity_id: str, value: str) -> bool:
        self.calls.append(("set_input_text", entity_id, value))
        return True

    async def set_input_number(self, entity_id: str, value: float) -> bool:
        self.calls.append(("set_input_number", entity_id, value))
        return True

    async def get_state_value(self, entity_id: str, default: object = "") -> object:
        self.calls.append(("get_state_value", entity_id, default))
        return self.state_values.get(entity_id, default)


class Haos49CharacterizationCase(unittest.TestCase):
    """Shared deterministic fixture; production behavior remains unmodified."""

    FIXED_AFTERNOON = datetime(2026, 1, 15, 14, 0, 0)

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

    def optimizer(
        self,
        ha: object | None = None,
        **overrides: object,
    ) -> SigEnergyOptimizer:
        values: dict[str, object] = {
            "battery_full_safeguard_enabled": False,
            "evening_boost_enabled": False,
            "morning_dump_enabled": False,
            "morning_slow_charge_enabled": False,
            "solar_surplus_bypass_enabled": False,
            "standby_holdoff_enabled": False,
            "export_value_gate_enabled": False,
            "export_value_gate_dry_run": False,
            "export_value_gate_enforce": False,
            "allow_low_medium_export_positive_fit": False,
            "export_threshold_low": 0.10,
            "export_threshold_medium": 0.20,
            "export_threshold_high": 1.00,
            "export_limit_low": 5.0,
            "export_limit_medium": 12.0,
            "export_limit_high": 25.0,
            "min_export_target_soc": 90.0,
            "min_soc_floor": 20.0,
            "sunrise_reserve_soc": 20.0,
            "target_battery_charge": 2.0,
            "daytime_topup_max_soc": 50.0,
            "min_grid_transfer_kw": 0.5,
            "pv_max_power_normal": 25.0,
            "ess_charge_limit_value": 25.0,
            "ess_discharge_limit_value": 25.0,
        }
        values.update(overrides)
        optimizer = SigEnergyOptimizer(ha or RecordingHA(), Settings(**values))
        self._optimizers.append(optimizer)
        return optimizer

    @staticmethod
    def state(
        when: datetime,
        *,
        sun_above_horizon: bool = True,
        **overrides: object,
    ) -> SolarState:
        sunrise_date = when.date() + (timedelta(days=1) if sun_above_horizon else timedelta())
        next_sunrise = datetime.combine(sunrise_date, time(7, 0))
        next_sunset = datetime.combine(when.date(), time(18, 0))
        if when >= next_sunset:
            next_sunset += timedelta(days=1)

        state = SolarState(
            sigenergy_mode="Automated",
            sigenergy_mode_observed=True,
            current_ems_mode=MODE_MAX_SELF,
            ems_mode_observed=True,
            battery_soc=60.0,
            battery_capacity_kwh=30.0,
            available_discharge_energy_kwh=18.0,
            battery_power_sensor_kw=0.0,
            grid_import_power_kw=0.0,
            grid_export_power_kw=0.0,
            current_price=0.30,
            current_price_cents=30.0,
            price_is_actual=True,
            feedin_price=0.0,
            feedin_price_cents=0.0,
            load_kw=1.0,
            pv_kw=0.0,
            solar_power_now_kw=0.0,
            ess_max_charge_kw=25.0,
            ess_max_discharge_kw=25.0,
            forecast_remaining_kwh=100.0,
            forecast_today_kwh=100.0,
            forecast_tomorrow_kwh=100.0,
            next_sunrise_ts=next_sunrise.timestamp(),
            next_sunset_ts=next_sunset.timestamp(),
            hours_to_sunrise=max((next_sunrise - when).total_seconds() / 3600.0, 0.0),
            hours_to_sunset=max((next_sunset - when).total_seconds() / 3600.0, 0.0),
            sun_above_horizon=sun_above_horizon,
            current_export_limit=0.01,
            current_import_limit=0.01,
            current_pv_max_power_limit=25.0,
            current_ess_charge_limit=25.0,
            current_ess_discharge_limit=25.0,
            ha_control_enabled=True,
            ha_control_switch_available=True,
            ha_control_switch_state="on",
            timestamp=when,
        )
        for key, value in overrides.items():
            setattr(state, key, value)
        return state

    @staticmethod
    @contextmanager
    def optimizer_time(when: datetime):
        class FixedDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                if tz is None:
                    return cls.fromtimestamp(when.timestamp())
                return cls.fromtimestamp(when.timestamp(), tz)

        with patch("app.optimizer.datetime", FixedDateTime):
            yield

    def decide(
        self,
        optimizer: SigEnergyOptimizer,
        state: SolarState,
        when: datetime,
    ):
        with self.optimizer_time(when):
            return optimizer._decide(state)
