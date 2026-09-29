from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from app.config import Settings
from app.models import BATTERY_EXPORT, EXPORT_BLOCKED
from app.optimizer import (
    MODE_CMD_CHARGE_GRID,
    MODE_CMD_CHARGE_PV,
    MODE_CMD_DISCHARGE_PV,
    MODE_MAX_SELF,
)
from app.routers.api import _coerce_config_value, _validate_config_value
from haos49_characterization_helpers import Haos49CharacterizationCase


ROOT = Path(__file__).resolve().parents[1]


class EveningBoostFitDecouplingCharacterizationTests(Haos49CharacterizationCase):
    EVENING = datetime(2026, 1, 15, 17, 30)

    def _optimizer(self, *, minimum_fit: float = 0.01, **overrides: object):
        optimizer = self.optimizer(
            evening_boost_enabled=True,
            evening_boost_min_feedin_price=minimum_fit,
            **overrides,
        )
        optimizer._evening_export_boost_active = lambda *args, **kwargs: True
        return optimizer

    def _state(self, optimizer, fit: float, **overrides: object):
        values: dict[str, object] = {
            "battery_soc": 80.0,
            "available_discharge_energy_kwh": 24.0,
            "feedin_price": fit,
            "feedin_price_cents": fit * 100.0,
            "load_kw": 0.0,
        }
        values.update(overrides)
        return self.state(self.EVENING, **values)

    def test_default_setting_is_one_cent_per_kwh(self) -> None:
        cfg = Settings(_env_file=None)

        self.assertEqual(0.01, cfg.evening_boost_min_feedin_price)

    def test_setting_accepts_floor_and_higher_values(self) -> None:
        for value in (0.01, 0.025):
            with self.subTest(value=value):
                cfg = Settings(
                    _env_file=None,
                    evening_boost_min_feedin_price=value,
                )
                self.assertEqual(value, cfg.evening_boost_min_feedin_price)

    def test_setting_rejects_below_floor_direct_and_environment_values(self) -> None:
        for value in (0.009, 0.0, -0.001):
            with self.subTest(source="direct", value=value):
                with self.assertRaises(ValidationError):
                    Settings(
                        _env_file=None,
                        evening_boost_min_feedin_price=value,
                    )

            with self.subTest(source="environment", value=value):
                with patch.dict(
                    "os.environ",
                    {"EVENING_BOOST_MIN_FEEDIN_PRICE": str(value)},
                    clear=True,
                ):
                    with self.assertRaises(ValidationError):
                        Settings(_env_file=None)

    def test_setting_and_api_validation_reject_nonfinite_values(self) -> None:
        cfg = Settings(_env_file=None)

        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    Settings(
                        _env_file=None,
                        evening_boost_min_feedin_price=value,
                    )
                self.assertEqual(
                    "must be a finite number",
                    _validate_config_value(
                        cfg,
                        "evening_boost_min_feedin_price",
                        value,
                    ),
                )

    def test_api_coercion_and_validation_accept_floor_and_higher_values(self) -> None:
        cfg = Settings(_env_file=None)

        self.assertEqual(
            0.025,
            _coerce_config_value(
                cfg,
                "evening_boost_min_feedin_price",
                "0.025",
            ),
        )
        self.assertIsNone(
            _validate_config_value(
                cfg,
                "evening_boost_min_feedin_price",
                0.025,
            )
        )
        self.assertIsNone(
            _validate_config_value(
                cfg,
                "evening_boost_min_feedin_price",
                0.01,
            )
        )

    def test_api_validation_explicitly_rejects_values_below_floor(self) -> None:
        cfg = Settings(_env_file=None)

        for value in (0.009, 0.0, -0.001):
            with self.subTest(value=value):
                self.assertEqual(
                    "must be greater than or equal to 0.01",
                    _validate_config_value(
                        cfg,
                        "evening_boost_min_feedin_price",
                        value,
                    ),
                )

    def test_setting_is_exposed_in_ui_and_environment_example(self) -> None:
        template = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        env_example = (ROOT / ".env.example").read_text(encoding="utf-8")

        self.assertIn("['evening_boost_min_feedin_price'", template)
        self.assertIn("evening_boost_min_feedin_price:", template)
        self.assertIn("EVENING_BOOST_MIN_FEEDIN_PRICE=0.01", env_example)

    def test_evening_boost_acquires_and_retains_battery_export_below_ordinary_tier(self) -> None:
        optimizer = self._optimizer(minimum_fit=0.01)
        self.assertGreater(optimizer.cfg.export_threshold_low, 0.08)

        acquired = self.decide(optimizer, self._state(optimizer, 0.08), self.EVENING)

        self.assertTrue(acquired.evening_export_boost_active)
        self.assertGreater(acquired.export_limit, 0.01)
        self.assertEqual(BATTERY_EXPORT, acquired.export_intent)
        self.assertEqual(
            "evening_export_boost",
            acquired.trace_values.get("battery_export_owner"),
        )
        self.assertEqual(MODE_CMD_DISCHARGE_PV, acquired.ems_mode)

        optimizer._last_decision = acquired
        retained_state = self._state(
            optimizer,
            0.08,
            current_ems_mode=MODE_CMD_DISCHARGE_PV,
            current_export_limit=acquired.export_limit,
        )
        retained = self.decide(optimizer, retained_state, self.EVENING)

        self.assertGreater(retained.export_limit, 0.01)
        self.assertEqual(BATTERY_EXPORT, retained.export_intent)
        self.assertEqual(
            "evening_export_boost",
            retained.trace_values.get("battery_export_owner"),
        )

    def test_fit_below_configured_evening_minimum_does_not_grant_boost(self) -> None:
        optimizer = self._optimizer(minimum_fit=0.08)

        decision = self.decide(optimizer, self._state(optimizer, 0.07), self.EVENING)

        self.assertFalse(decision.evening_export_boost_active)
        self.assertNotEqual(BATTERY_EXPORT, decision.export_intent)
        self.assertEqual("none", decision.trace_values.get("battery_export_owner"))

    def test_fit_equal_to_configured_evening_minimum_is_eligible(self) -> None:
        optimizer = self._optimizer(minimum_fit=0.08)

        decision = self.decide(optimizer, self._state(optimizer, 0.08), self.EVENING)

        self.assertTrue(decision.evening_export_boost_active)
        self.assertGreater(decision.export_limit, 0.01)
        self.assertEqual(BATTERY_EXPORT, decision.export_intent)
        self.assertEqual(
            "evening_export_boost",
            decision.trace_values.get("battery_export_owner"),
        )

    def test_exact_one_cent_can_activate_with_explicit_battery_owner(self) -> None:
        optimizer = self._optimizer(minimum_fit=0.01)

        decision = self.decide(optimizer, self._state(optimizer, 0.01), self.EVENING)

        self.assertTrue(decision.evening_export_boost_active)
        self.assertGreater(decision.export_limit, 0.01)
        self.assertEqual(BATTERY_EXPORT, decision.export_intent)
        self.assertEqual(
            "evening_export_boost",
            decision.trace_values.get("battery_export_owner"),
        )

    def test_sub_one_cent_remains_closed_without_battery_owner(self) -> None:
        optimizer = self._optimizer(minimum_fit=0.01)

        decision = self.decide(optimizer, self._state(optimizer, 0.005), self.EVENING)

        self.assertFalse(decision.evening_export_boost_active)
        self.assertEqual(0.0, decision.export_limit)
        self.assertEqual(EXPORT_BLOCKED, decision.export_intent)
        self.assertEqual("none", decision.trace_values.get("battery_export_owner"))
        self.assertEqual(
            "closed_fit_below_minimum",
            decision.trace_values.get("desired_export_source"),
        )

    def test_ordinary_positive_fit_below_ordinary_tier_gains_no_battery_owner(self) -> None:
        optimizer = self.optimizer(
            evening_boost_enabled=False,
            allow_low_medium_export_positive_fit=False,
        )

        decision = self.decide(
            optimizer,
            self.state(
                self.EVENING,
                battery_soc=95.0,
                available_discharge_energy_kwh=28.5,
                feedin_price=0.08,
                feedin_price_cents=8.0,
                load_kw=0.0,
            ),
            self.EVENING,
        )

        self.assertEqual(EXPORT_BLOCKED, decision.export_intent)
        self.assertEqual("none", decision.trace_values.get("battery_export_owner"))
        self.assertNotIn(decision.ems_mode, {MODE_CMD_DISCHARGE_PV})

    def test_untrusted_available_energy_still_blocks_evening_boost(self) -> None:
        optimizer = self._optimizer()

        decision = self.decide(
            optimizer,
            self._state(
                optimizer,
                0.08,
                available_discharge_energy_trusted=False,
            ),
            self.EVENING,
        )

        self.assertFalse(decision.evening_export_boost_active)
        self.assertEqual(EXPORT_BLOCKED, decision.export_intent)

    def test_refill_feasibility_still_blocks_evening_boost(self) -> None:
        optimizer = self.optimizer(
            evening_boost_enabled=True,
            evening_boost_min_feedin_price=0.01,
            evening_boost_min_tomorrow_forecast_kwh=20.0,
            evening_boost_forecast_safety=1.1,
        )
        state = self._state(
            optimizer,
            0.08,
            available_discharge_energy_kwh=0.0,
            forecast_tomorrow_kwh=30.0,
            solcast_detailed=[
                {
                    "period_start": datetime(2026, 1, 15, 16, 0).isoformat(),
                    "pv_estimate": 2.0,
                }
            ],
        )

        decision = self.decide(optimizer, state, self.EVENING)

        self.assertFalse(decision.evening_export_boost_active)
        self.assertEqual(EXPORT_BLOCKED, decision.export_intent)

    def test_actual_import_cost_guard_still_vetoes_evening_boost(self) -> None:
        optimizer = self._optimizer()
        date = self.EVENING.date().isoformat()
        optimizer._state_store.record_optimizer_import_topup(
            date=date,
            ts=f"{date}T09:00:00",
            import_kwh=1.0,
            import_price=0.16,
            price_trusted=True,
        )

        decision = self.decide(optimizer, self._state(optimizer, 0.08), self.EVENING)

        self.assertTrue(decision.evening_export_boost_active)
        self.assertTrue(
            bool(decision.trace_gates.get("actual_import_cost_guard_blocking"))
        )
        self.assertEqual(0.0, decision.export_limit)
        self.assertEqual(EXPORT_BLOCKED, decision.export_intent)
        self.assertEqual(MODE_MAX_SELF, decision.ems_mode)

    def test_demand_window_blocks_import_without_stealing_evening_export_owner(self) -> None:
        optimizer = self._optimizer()

        decision = self.decide(
            optimizer,
            self._state(
                optimizer,
                0.08,
                demand_window_active=True,
                demand_window_observed=True,
            ),
            self.EVENING,
        )

        self.assertEqual(0.0, decision.import_limit)
        self.assertGreater(decision.export_limit, 0.01)
        self.assertEqual(BATTERY_EXPORT, decision.export_intent)
        self.assertEqual(
            "evening_export_boost",
            decision.trace_values.get("battery_export_owner"),
        )

    def test_manual_and_force_target_maps_are_unchanged(self) -> None:
        optimizer = self._optimizer()
        cfg = optimizer.cfg
        state = self._state(optimizer, 0.08)
        expected = {
            cfg.full_export_option: (
                MODE_CMD_DISCHARGE_PV,
                25.0,
                0.01,
                30.0,
                25.0,
                25.0,
            ),
            cfg.full_import_option: (
                MODE_CMD_CHARGE_GRID,
                0.01,
                25.0,
                30.0,
                25.0,
                25.0,
            ),
            cfg.full_import_pv_option: (
                MODE_CMD_CHARGE_PV,
                0.01,
                25.0,
                30.0,
                25.0,
                25.0,
            ),
            cfg.block_flow_option: (
                MODE_MAX_SELF,
                0.01,
                0.01,
                30.0,
                25.0,
                25.0,
            ),
        }

        for mode, outputs in expected.items():
            with self.subTest(mode=mode):
                targets = optimizer._manual_mode_targets(
                    mode,
                    state,
                    include_block_flow_ess_limits=True,
                )
                self.assertIsNotNone(targets)
                assert targets is not None
                self.assertEqual(
                    outputs,
                    (
                        targets["ems_mode"],
                        targets["grid_export_limit"],
                        targets["grid_import_limit"],
                        targets["pv_max_power_limit"],
                        targets["ess_charge_limit"],
                        targets["ess_discharge_limit"],
                    ),
                )
        self.assertIsNone(optimizer._manual_mode_targets(cfg.manual_option, state))
