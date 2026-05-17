from __future__ import annotations

import os
import tempfile
import unittest

from app.config import Settings
from app.models import SolarState
from app.optimizer import SigEnergyOptimizer


class _DummyHA:
    pass


class OptimizerGuardTests(unittest.TestCase):
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
        cfg = Settings(**overrides)
        optimizer = SigEnergyOptimizer(_DummyHA(), cfg)
        self._optimizers.append(optimizer)
        return optimizer

    def test_power_caps_prefer_number_entity_max_over_dynamic_sensor_caps(self) -> None:
        optimizer = self._optimizer(
            ess_charge_limit_value=5.0,
            ess_discharge_limit_value=6.0,
        )
        state = SolarState(
            ess_charge_limit_entity_max_kw=12.0,
            ess_max_charge_kw=3.0,
            ess_discharge_limit_entity_max_kw=15.0,
            ess_max_discharge_kw=4.0,
        )

        charge_cap, discharge_cap = optimizer.get_power_caps_kw(state)

        self.assertEqual(charge_cap, 12.0)
        self.assertEqual(discharge_cap, 15.0)

    def test_power_caps_fall_back_to_cached_last_known_good_when_live_values_invalid(self) -> None:
        optimizer = self._optimizer(
            ess_charge_limit_value=5.0,
            ess_discharge_limit_value=6.0,
        )
        optimizer._last_hw_charge_cap_kw = 11.0
        optimizer._last_hw_discharge_cap_kw = 13.0
        state = SolarState(
            ess_charge_limit_entity_max_kw=0.0,
            ess_max_charge_kw=999.0,
            ess_discharge_limit_entity_max_kw=0.0,
            ess_max_discharge_kw=999.0,
        )

        charge_cap, discharge_cap = optimizer.get_power_caps_kw(state)

        self.assertEqual(charge_cap, 11.0)
        self.assertEqual(discharge_cap, 13.0)

    def test_power_caps_never_drop_below_configured_manual_baselines(self) -> None:
        optimizer = self._optimizer(
            ess_limit_fallback_kw=-5.0,
            ess_charge_limit_value=7.0,
            ess_discharge_limit_value=8.0,
        )

        charge_cap, discharge_cap = optimizer.get_power_caps_kw()

        self.assertEqual(charge_cap, 7.0)
        self.assertEqual(discharge_cap, 8.0)

    def test_valid_time_config_accepts_hh_mm_and_hh_mm_ss(self) -> None:
        optimizer = self._optimizer(
            daily_summary_time="23:55:30",
            morning_summary_time="07:30",
            standby_holdoff_end_time="11:00",
            morning_slow_charge_until="11:00:15",
        )

        self.assertEqual(optimizer.config_time_warnings, [])

    def test_invalid_time_config_collects_field_specific_warnings(self) -> None:
        optimizer = self._optimizer(
            daily_summary_time="25:99",
            morning_summary_time="07:30",
            standby_holdoff_end_time="bad",
            morning_slow_charge_until="11:00",
        )

        self.assertEqual(len(optimizer.config_time_warnings), 2)
        self.assertTrue(
            any("daily_summary_time" in warning for warning in optimizer.config_time_warnings)
        )
        self.assertTrue(
            any("standby_holdoff_end_time" in warning for warning in optimizer.config_time_warnings)
        )


if __name__ == "__main__":
    unittest.main()