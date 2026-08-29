from __future__ import annotations

import os
import tempfile
import unittest

from app.config import Settings
from app.models import SolarState
from app.optimizer import SigEnergyOptimizer


class _DummyHA:
    pass


class PVSurplusHotfixTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db = os.environ.get("STATE_DB_PATH")
        os.environ["STATE_DB_PATH"] = os.path.join(self.tmp.name, "state.db")
        self.optimizers: list[SigEnergyOptimizer] = []

    def tearDown(self) -> None:
        for optimizer in self.optimizers:
            optimizer._state_store.close()
        if self.old_db is None:
            os.environ.pop("STATE_DB_PATH", None)
        else:
            os.environ["STATE_DB_PATH"] = self.old_db
        self.tmp.cleanup()

    def optimizer(self, **overrides: object) -> SigEnergyOptimizer:
        values: dict[str, object] = {
            "export_threshold_low": 0.10,
            "export_threshold_medium": 0.20,
            "export_threshold_high": 1.00,
            "export_limit_low": 5.0,
            "export_limit_medium": 12.0,
            "export_limit_high": 25.0,
            "min_export_target_soc": 90.0,
            "min_grid_transfer_kw": 0.5,
            "morning_slow_charge_rate_kw": 3.7,
        }
        values.update(overrides)
        optimizer = SigEnergyOptimizer(_DummyHA(), Settings(**values))
        self.optimizers.append(optimizer)
        return optimizer

    @staticmethod
    def state(*, fit: float, pv: float, load: float) -> SolarState:
        return SolarState(
            battery_soc=27.5,
            battery_capacity_kwh=40.3,
            feedin_price=fit,
            feedin_price_cents=fit * 100.0,
            pv_kw=pv,
            load_kw=load,
            solar_power_now_kw=12.3,
            ess_max_charge_kw=100.0,
            ess_max_discharge_kw=100.0,
            forecast_tomorrow_kwh=111.0,
            grid_import_power_kw=0.0,
            grid_export_power_kw=0.0,
            current_export_limit=0.01,
        )

    def desired_export(
        self,
        optimizer: SigEnergyOptimizer,
        state: SolarState,
        *,
        morning_slow: bool = False,
        solar_bypass: bool = False,
        tier_limit: float = 0.0,
        estimated_surplus: float = 11.0,
    ) -> float:
        return optimizer._desired_export_limit(
            state,
            False,   # spike
            False,   # solar_override
            False,   # export_blocked
            False,   # forecast_guard
            20.0,    # export_min_soc
            False,   # positive_fit_override
            solar_bypass,
            False,   # evening_boost
            False,   # morning_dump
            optimizer.cfg.export_limit_high,
            False,   # battery_full_safeguard_block
            tier_limit,
            20.0,    # hours_to_sunrise
            state.battery_capacity_kwh,
            estimated_surplus,
            False,   # is_evening_or_night
            morning_slow,
            False,   # within_morning_grace
        )

    def test_morning_slow_charge_uses_configured_charge_rate(self) -> None:
        optimizer = self.optimizer(morning_slow_charge_rate_kw=3.7)
        state = self.state(fit=0.015, pv=10.0, load=1.0)

        limit = optimizer._desired_ess_charge_limit(
            state,
            desired_import=0.0,
            morning_slow_charge=True,
            desired_export=25.0,
            pv_surplus=9.0,
        )

        self.assertEqual(limit, 3.7)

    def test_morning_slow_charge_opens_configured_high_export_ceiling(self) -> None:
        optimizer = self.optimizer(export_limit_high=19.3)
        state = self.state(fit=0.015, pv=7.2, load=1.3)

        limit = self.desired_export(
            optimizer,
            state,
            morning_slow=True,
            estimated_surplus=11.0,
        )

        self.assertEqual(limit, optimizer.cfg.export_limit_high)

    def test_solar_bypass_opens_high_ceiling_once_price_threshold_is_met(self) -> None:
        optimizer = self.optimizer(export_limit_high=21.7)
        state = self.state(fit=0.12, pv=6.0, load=1.0)

        limit = self.desired_export(
            optimizer,
            state,
            solar_bypass=True,
            tier_limit=optimizer.cfg.export_limit_low,
            estimated_surplus=10.0,
        )

        self.assertEqual(limit, optimizer.cfg.export_limit_high)

    def test_morning_slow_charge_respects_export_entity_maximum(self) -> None:
        optimizer = self.optimizer(export_limit_high=25.0)
        state = self.state(fit=0.015, pv=10.0, load=1.0)
        state.grid_export_limit_entity_max_kw = 18.069

        limit = self.desired_export(
            optimizer,
            state,
            morning_slow=True,
            estimated_surplus=12.0,
        )

        self.assertEqual(limit, 18.06)
        self.assertLessEqual(limit, state.grid_export_limit_entity_max_kw)

    def test_solar_bypass_respects_fractional_export_entity_maximum(self) -> None:
        optimizer = self.optimizer(export_limit_high=25.0)
        state = self.state(fit=0.12, pv=10.0, load=1.0)
        state.grid_export_limit_entity_max_kw = 18.069

        limit = self.desired_export(
            optimizer,
            state,
            solar_bypass=True,
            tier_limit=optimizer.cfg.export_limit_low,
            estimated_surplus=12.0,
        )

        self.assertEqual(limit, 18.06)
        self.assertLessEqual(limit, state.grid_export_limit_entity_max_kw)

    def test_solar_bypass_still_exports_nothing_below_price_threshold(self) -> None:
        optimizer = self.optimizer()
        state = self.state(
            fit=optimizer.cfg.export_threshold_low - 0.001,
            pv=10.0,
            load=1.0,
        )
        tier_limit = optimizer._export_tier_limit(
            state,
            False,
            False,
            False,
            False,
            True,
        )
        self.assertEqual(tier_limit, 0.0)

        limit = self.desired_export(
            optimizer,
            state,
            solar_bypass=True,
            tier_limit=tier_limit,
            estimated_surplus=11.0,
        )

        self.assertEqual(limit, 0.0)

    def test_solar_bypass_hysteresis_continues_under_msc(self) -> None:
        optimizer = self.optimizer(
            solar_surplus_start_multiplier=2.0,
            solar_surplus_stop_multiplier=1.25,
        )
        state = self.state(fit=0.12, pv=8.0, load=1.0)
        state.forecast_remaining_kwh = 50.0

        self.assertFalse(
            optimizer._solar_surplus_bypass(
                state,
                False,
                40.0,
                7.0,
                previously_active=False,
            )
        )
        self.assertTrue(
            optimizer._solar_surplus_bypass(
                state,
                False,
                40.0,
                7.0,
                previously_active=True,
            )
        )


if __name__ == "__main__":
    unittest.main()
