from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime

from app.config import Settings
from app.models import SolarState
from app.optimizer import SigEnergyOptimizer


class _DummyHA:
    pass


class ExportValueGateAdvisoryTests(unittest.TestCase):
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

    def _optimizer(self, **overrides: float | bool) -> SigEnergyOptimizer:
        values: dict[str, float | bool] = {
            "export_threshold_low": 0.08,
            "export_threshold_medium": 0.20,
            "export_threshold_high": 1.00,
            "export_limit_low": 5.0,
            "export_limit_medium": 12.0,
            "export_limit_high": 25.0,
            "min_export_target_soc": 35.0,
            "sunrise_reserve_soc": 25.0,
            "export_value_gate_min_floor": 35.0,
            "export_value_gate_manual_import_premium": 0.08,
            "export_value_gate_winter_premium": 0.03,
            "export_value_gate_cooling_premium": 0.0,
            "export_value_gate_safety_margin": 0.02,
            "export_value_gate_useful_solar_offset_hours": 1.75,
            "min_grid_transfer_kw": 0.5,
        }
        values.update(overrides)
        cfg = Settings(**values)
        optimizer = SigEnergyOptimizer(_DummyHA(), cfg)
        self._optimizers.append(optimizer)
        return optimizer

    @staticmethod
    def _state(**overrides: float | bool | None) -> SolarState:
        state = SolarState(
            battery_soc=72.0,
            battery_capacity_kwh=30.0,
            current_price=0.30,
            current_price_cents=30.0,
            feedin_price=0.08,
            feedin_price_cents=8.0,
            load_kw=0.8,
            pv_kw=0.0,
            solar_power_now_kw=0.0,
            ess_max_discharge_kw=25.0,
            forecast_tomorrow_kwh=73.0,
            hours_to_sunrise=14.0,
            next_sunrise_ts=14.0 * 3600,
            next_sunset_ts=2.0 * 3600,
            sun_above_horizon=False,
        )
        for key, value in overrides.items():
            setattr(state, key, value)
        return state

    def _advisory(
        self,
        optimizer: SigEnergyOptimizer,
        state: SolarState,
        *,
        desired_export_limit: float,
        sunrise_soc_target: float = 28.0,
        soc_required: float = 28.0,
        productive_solar_end_ts: float | None = -1800.0,
        now_ts: float = 0.0,
        export_spike_active: bool = False,
    ) -> dict[str, float | bool | str]:
        return optimizer._export_value_gate_advisory(
            state,
            desired_export_limit=desired_export_limit,
            sunrise_soc_target=sunrise_soc_target,
            soc_required=soc_required,
            productive_solar_end_ts=productive_solar_end_ts,
            now_ts=now_ts,
            export_spike_active=export_spike_active,
        )

    def test_winter_evening_good_tomorrow_still_blocks_cheap_battery_export(self) -> None:
        optimizer = self._optimizer()
        state = self._state()

        advisory = self._advisory(optimizer, state, desired_export_limit=5.0)

        self.assertTrue(advisory["export_value_gate_would_block"])
        self.assertFalse(advisory["export_value_gate_would_allow"])
        self.assertGreater(float(advisory["stored_energy_value_floor"]), state.feedin_price)
        self.assertIn("would block export", str(advisory["export_value_gate_reason"]))

    def test_spike_override_allows_only_when_surplus_exists_above_protected_reserve(self) -> None:
        optimizer = self._optimizer(export_spike_threshold=0.60)
        state = self._state(feedin_price=0.85, feedin_price_cents=85.0, battery_soc=80.0)

        advisory = self._advisory(
            optimizer,
            state,
            desired_export_limit=10.0,
            export_spike_active=True,
        )

        self.assertTrue(advisory["export_value_gate_would_allow"])
        self.assertFalse(advisory["export_value_gate_would_block"])
        self.assertGreater(float(advisory["export_surplus_soc"]), 0.0)

    def test_below_protected_reserve_blocks_export(self) -> None:
        optimizer = self._optimizer()
        state = self._state(battery_soc=30.0)

        advisory = self._advisory(optimizer, state, desired_export_limit=5.0)

        self.assertTrue(advisory["export_value_gate_would_block"])
        self.assertLessEqual(float(advisory["export_surplus_soc"]), 0.05)
        self.assertIn("protected reserve", str(advisory["export_value_gate_reason"]))

    def test_summer_like_case_can_be_advisory_allowed_when_surplus_exists(self) -> None:
        optimizer = self._optimizer(
            export_value_gate_winter_premium=0.0,
            export_value_gate_safety_margin=0.01,
        )
        state = self._state(
            battery_soc=78.0,
            battery_capacity_kwh=40.0,
            current_price=0.10,
            current_price_cents=10.0,
            feedin_price=0.16,
            feedin_price_cents=16.0,
            load_kw=0.3,
            forecast_tomorrow_kwh=80.0,
            next_sunrise_ts=8.0 * 3600,
            hours_to_sunrise=8.0,
        )

        advisory = self._advisory(
            optimizer,
            state,
            desired_export_limit=5.0,
            sunrise_soc_target=20.0,
            soc_required=18.0,
        )

        self.assertTrue(advisory["export_value_gate_would_allow"])
        self.assertFalse(advisory["export_value_gate_would_block"])
        self.assertGreater(float(advisory["export_surplus_soc"]), 0.0)

    def test_advisory_dry_run_does_not_change_live_desired_export_limit(self) -> None:
        optimizer = self._optimizer()
        state = self._state(
            battery_soc=100.0,
            battery_capacity_kwh=40.3,
            forecast_tomorrow_kwh=80.0,
            feedin_price=0.09,
            feedin_price_cents=9.0,
            pv_kw=2.1,
            solar_power_now_kw=4.4,
            load_kw=0.9,
            ess_max_discharge_kw=100.0,
            sun_above_horizon=True,
        )

        desired = optimizer._desired_export_limit(
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
        advisory = self._advisory(optimizer, state, desired_export_limit=desired)

        self.assertEqual(desired, 3.5)
        self.assertTrue(advisory["export_value_gate_would_block"])
        self.assertFalse(advisory["export_value_gate_would_allow"])

    def test_advisory_defaults_do_not_change_live_actuator_outputs(self) -> None:
        default_optimizer = self._optimizer()
        disabled_optimizer = self._optimizer(
            export_value_gate_enabled=False,
            export_value_gate_dry_run=False,
            export_value_gate_enforce=False,
        )
        now_ts = datetime.now().timestamp()
        state = self._state(
            battery_soc=72.0,
            battery_capacity_kwh=30.0,
            available_discharge_energy_kwh=21.6,
            current_price=0.30,
            current_price_cents=30.0,
            price_is_actual=True,
            feedin_price=0.08,
            feedin_price_cents=8.0,
            load_kw=0.8,
            pv_kw=0.0,
            solar_power_now_kw=0.0,
            forecast_remaining_kwh=0.0,
            forecast_today_kwh=8.0,
            forecast_tomorrow_kwh=73.0,
            ess_max_charge_kw=25.0,
            ess_max_discharge_kw=25.0,
            next_sunrise_ts=now_ts + (14.0 * 3600),
            next_sunset_ts=now_ts + (18.0 * 3600),
            hours_to_sunrise=14.0,
            hours_to_sunset=18.0,
            sun_above_horizon=False,
            current_ems_mode="Maximum Self Consumption",
            current_export_limit=0.0,
            current_import_limit=0.0,
            current_pv_max_power_limit=25.0,
        )

        default_decision = default_optimizer._decide(state)
        disabled_decision = disabled_optimizer._decide(state)

        self.assertEqual(default_decision.ems_mode, disabled_decision.ems_mode)
        self.assertEqual(default_decision.export_limit, disabled_decision.export_limit)
        self.assertEqual(default_decision.import_limit, disabled_decision.import_limit)
        self.assertEqual(default_decision.pv_max_power_limit, disabled_decision.pv_max_power_limit)
        self.assertEqual(default_decision.ess_charge_limit, disabled_decision.ess_charge_limit)
        self.assertEqual(default_decision.ess_discharge_limit, disabled_decision.ess_discharge_limit)

    def test_config_defaults_are_non_enforcing(self) -> None:
        cfg = Settings()

        self.assertFalse(cfg.export_value_gate_enabled)
        self.assertTrue(cfg.export_value_gate_dry_run)
        self.assertFalse(cfg.export_value_gate_enforce)


if __name__ == "__main__":
    unittest.main()