from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from datetime import datetime

from app.config import Settings
from app.models import Decision, SolarState
from app.optimizer import SigEnergyOptimizer


class _DummyHA:
    pass


class _RecordingHA:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, object]] = []

    async def select_option(self, entity_id: str, value: str) -> bool:
        self.calls.append(("select_option", entity_id, value))
        return True

    async def set_number(self, entity_id: str, value: float) -> bool:
        self.calls.append(("set_number", entity_id, value))
        return True

    async def turn_on(self, entity_id: str) -> bool:
        self.calls.append(("turn_on", entity_id, True))
        return True

    async def set_input_text(self, entity_id: str, value: str) -> bool:
        self.calls.append(("set_input_text", entity_id, value))
        return True

    async def set_input_number(self, entity_id: str, value: float) -> bool:
        self.calls.append(("set_input_number", entity_id, value))
        return True

    async def get_state_value(self, entity_id: str, default: object = "") -> object:
        self.calls.append(("get_state_value", entity_id, default))
        return default


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
    def _state(**overrides: float | bool | str | None) -> SolarState:
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

    def _breathe_probe_state(self, now_ts: float, **overrides: float | bool | str | None) -> SolarState:
        values: dict[str, float | bool | str | None] = {
            "battery_soc": 100.0,
            "feedin_price": 0.08,
            "feedin_price_cents": 8.0,
            "pv_kw": 1.0,
            "solar_power_now_kw": 1.0,
            "load_kw": 1.0,
            "battery_power_sensor_kw": 0.0,
            "sun_above_horizon": True,
            "next_sunrise_ts": now_ts + (10.0 * 3600),
            "next_sunset_ts": now_ts + (6.0 * 3600),
            "hours_to_sunrise": 10.0,
            "hours_to_sunset": 6.0,
            "current_ems_mode": "Maximum Self Consumption",
            "current_export_limit": 0.01,
            "current_import_limit": 0.0,
            "current_pv_max_power_limit": 25.0,
        }
        values.update(overrides)
        return self._state(**values)

    @staticmethod
    def _previous_breathe_probe_decision(export_limit: float = 1.0) -> Decision:
        return Decision(
            ems_mode="Maximum Self Consumption",
            export_limit=export_limit,
            trace_gates={"pv_surplus_breathe_probe_active": True},
            trace_values={
                "pv_surplus_initiation_source": "full_battery_breathe_probe",
                "pv_surplus_probe_export_cap_kw": export_limit,
            },
        )

    @staticmethod
    def _seed_breathe_probe_state(
        optimizer: SigEnergyOptimizer,
        now_ts: float,
        export_limit: float = 1.0,
    ) -> None:
        optimizer._record_pv_discovery_state(
            "full_battery_breathe_probe",
            export_limit,
            now_ts,
        )

    def _run_measured_carveout_seed(
        self,
        optimizer: SigEnergyOptimizer,
        now_ts: float,
    ) -> Decision:
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 1.0
        state = self._breathe_probe_state(
            now_ts,
            pv_kw=1.9,
            solar_power_now_kw=5.3,
            load_kw=0.9,
            battery_power_sensor_kw=-0.01,
            current_export_limit=0.01,
            grid_export_power_kw=0.0,
        )
        return optimizer._decide(state)

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

    @staticmethod
    def _record_import_topup(
        optimizer: SigEnergyOptimizer,
        *,
        import_kwh: float,
        import_price: float | None,
        price_trusted: bool = True,
    ) -> None:
        date = datetime.now(optimizer._tz).date().isoformat()
        optimizer._state_store.record_optimizer_import_topup(
            date=date,
            ts=f"{date}T09:00:00",
            import_kwh=import_kwh,
            import_price=import_price,
            price_trusted=price_trusted,
        )

    def test_winter_evening_good_tomorrow_still_blocks_cheap_battery_export(self) -> None:
        optimizer = self._optimizer()
        state = self._state()

        advisory = self._advisory(optimizer, state, desired_export_limit=5.0)

        self.assertTrue(advisory["export_value_gate_would_block"])
        self.assertFalse(advisory["export_value_gate_would_allow"])
        self.assertGreater(float(advisory["stored_energy_value_floor"]), state.feedin_price)
        self.assertIn("would block export", str(advisory["export_value_gate_reason"]).lower())

    def test_import_topup_today_at_16c_blocks_battery_export_at_8c(self) -> None:
        optimizer = self._optimizer()
        self._record_import_topup(optimizer, import_kwh=1.25, import_price=0.16)
        state = self._state(
            battery_soc=100.0,
            current_price=0.03,
            current_price_cents=3.0,
            feedin_price=0.08,
            feedin_price_cents=8.0,
        )

        advisory = self._advisory(optimizer, state, desired_export_limit=5.0)

        self.assertTrue(advisory["export_value_gate_would_block"])
        self.assertFalse(advisory["export_value_gate_would_allow"])
        self.assertEqual(advisory["export_value_gate_block_reason"], "price_below_import_cost_floor")
        self.assertAlmostEqual(float(advisory["today_import_topup_kwh"]), 1.25, places=3)
        self.assertAlmostEqual(float(advisory["today_highest_actual_import_price"]), 0.16, places=4)
        self.assertAlmostEqual(float(advisory["import_cost_export_floor"]), 0.16, places=4)
        self.assertAlmostEqual(float(advisory["effective_battery_export_floor"]), 0.16, places=4)
        self.assertIn("today's highest actual optimizer import cost", str(advisory["export_value_gate_reason"]))

    def test_no_import_topup_today_preserves_existing_stored_energy_floor(self) -> None:
        optimizer = self._optimizer(
            export_value_gate_winter_premium=0.0,
            export_value_gate_safety_margin=0.01,
        )
        state = self._state(
            battery_soc=78.0,
            current_price=0.10,
            current_price_cents=10.0,
            feedin_price=0.16,
            feedin_price_cents=16.0,
            forecast_tomorrow_kwh=80.0,
        )

        advisory = self._advisory(
            optimizer,
            state,
            desired_export_limit=5.0,
            sunrise_soc_target=20.0,
            soc_required=18.0,
        )

        self.assertIsNone(advisory["import_cost_export_floor"])
        self.assertAlmostEqual(
            float(advisory["effective_battery_export_floor"]),
            float(advisory["stored_energy_value_floor"]),
            places=4,
        )

    def test_battery_export_allowed_only_when_fit_meets_effective_import_floor(self) -> None:
        optimizer = self._optimizer()
        self._record_import_topup(optimizer, import_kwh=0.75, import_price=0.16)
        below = self._state(
            battery_soc=100.0,
            current_price=0.03,
            current_price_cents=3.0,
            feedin_price=0.15,
            feedin_price_cents=15.0,
        )
        meets = self._state(
            battery_soc=100.0,
            current_price=0.03,
            current_price_cents=3.0,
            feedin_price=0.17,
            feedin_price_cents=17.0,
        )

        blocked = self._advisory(optimizer, below, desired_export_limit=5.0)
        allowed = self._advisory(optimizer, meets, desired_export_limit=5.0)

        self.assertTrue(blocked["export_value_gate_would_block"])
        self.assertEqual(blocked["export_value_gate_block_reason"], "price_below_import_cost_floor")
        self.assertTrue(allowed["export_value_gate_would_allow"])
        self.assertFalse(allowed["export_value_gate_would_block"])

    def test_untrusted_import_topup_blocks_battery_export_until_day_resets(self) -> None:
        optimizer = self._optimizer()
        self._record_import_topup(optimizer, import_kwh=0.5, import_price=None, price_trusted=False)
        state = self._state(
            battery_soc=100.0,
            feedin_price=0.90,
            feedin_price_cents=90.0,
        )

        advisory = self._advisory(optimizer, state, desired_export_limit=5.0)

        self.assertTrue(advisory["export_value_gate_would_block"])
        self.assertEqual(advisory["export_value_gate_block_reason"], "import_cost_floor_untrusted")
        self.assertFalse(advisory["import_cost_floor_trusted"])

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

    def test_dry_run_only_would_block_keeps_actuator_outputs_unchanged(self) -> None:
        now_ts = datetime.now().timestamp()
        baseline_optimizer = self._optimizer(
            export_value_gate_enabled=False,
            export_value_gate_dry_run=False,
            export_value_gate_enforce=False,
        )
        dry_run_optimizer = self._optimizer(
            export_value_gate_enabled=False,
            export_value_gate_dry_run=True,
            export_value_gate_enforce=False,
        )
        state = self._state(
            battery_soc=100.0,
            battery_capacity_kwh=40.3,
            available_discharge_energy_kwh=40.3,
            forecast_tomorrow_kwh=80.0,
            feedin_price=0.09,
            feedin_price_cents=9.0,
            pv_kw=2.1,
            solar_power_now_kw=4.4,
            load_kw=0.9,
            ess_max_discharge_kw=100.0,
            price_is_actual=True,
            next_sunrise_ts=now_ts + (10.0 * 3600),
            next_sunset_ts=now_ts + (6.0 * 3600),
            hours_to_sunrise=10.0,
            hours_to_sunset=6.0,
            sun_above_horizon=True,
            current_ems_mode="Maximum Self Consumption",
            current_export_limit=0.0,
            current_import_limit=0.0,
            current_pv_max_power_limit=25.0,
        )

        baseline = baseline_optimizer._decide(state)
        dry_run = dry_run_optimizer._decide(state)

        self.assertTrue(dry_run.export_value_gate_would_block)
        self.assertEqual(baseline.export_limit, dry_run.export_limit)
        self.assertEqual(baseline.ems_mode, dry_run.ems_mode)

    def test_enforcement_true_and_would_block_vetoes_export_and_sets_safe_ems(self) -> None:
        now_ts = datetime.now().timestamp()
        non_enforcing_optimizer = self._optimizer(
            export_value_gate_enabled=True,
            export_value_gate_dry_run=True,
            export_value_gate_enforce=False,
        )
        enforcing_optimizer = self._optimizer(
            export_value_gate_enabled=True,
            export_value_gate_dry_run=True,
            export_value_gate_enforce=True,
        )
        state = self._state(
            battery_soc=100.0,
            battery_capacity_kwh=40.3,
            available_discharge_energy_kwh=40.3,
            forecast_tomorrow_kwh=80.0,
            feedin_price=0.09,
            feedin_price_cents=9.0,
            pv_kw=2.1,
            solar_power_now_kw=4.4,
            load_kw=0.9,
            ess_max_discharge_kw=100.0,
            price_is_actual=True,
            next_sunrise_ts=now_ts + (10.0 * 3600),
            next_sunset_ts=now_ts + (6.0 * 3600),
            hours_to_sunrise=10.0,
            hours_to_sunset=6.0,
            sun_above_horizon=True,
            current_ems_mode="Maximum Self Consumption",
            current_export_limit=0.0,
            current_import_limit=0.0,
            current_pv_max_power_limit=25.0,
        )

        baseline = non_enforcing_optimizer._decide(state)
        enforced = enforcing_optimizer._decide(state)

        self.assertGreater(baseline.export_limit, 0.0)
        self.assertTrue(enforced.export_value_gate_would_block)
        self.assertEqual(enforced.export_limit, 0.0)
        self.assertNotIn("Discharging", enforced.ems_mode)
        self.assertIn("vetoed", enforced.export_reason.lower())
        self.assertIn("enforced veto", enforced.export_value_gate_reason.lower())
        self.assertTrue(bool(enforced.trace_gates.get("export_value_gate_vetoed")))

    def test_enforcement_true_and_would_allow_preserves_export_behaviour(self) -> None:
        now_ts = datetime.now().timestamp()
        advisory_optimizer = self._optimizer(
            export_value_gate_enabled=True,
            export_value_gate_dry_run=True,
            export_value_gate_enforce=False,
            export_spike_threshold=0.60,
        )
        enforcing_optimizer = self._optimizer(
            export_value_gate_enabled=True,
            export_value_gate_dry_run=True,
            export_value_gate_enforce=True,
            export_spike_threshold=0.60,
        )
        state = self._state(
            battery_soc=80.0,
            battery_capacity_kwh=30.0,
            available_discharge_energy_kwh=24.0,
            feedin_price=0.85,
            feedin_price_cents=85.0,
            price_spike_active=True,
            price_is_actual=True,
            pv_kw=2.5,
            solar_power_now_kw=3.5,
            load_kw=0.8,
            ess_max_discharge_kw=25.0,
            next_sunrise_ts=now_ts + (8.0 * 3600),
            next_sunset_ts=now_ts + (5.0 * 3600),
            hours_to_sunrise=8.0,
            hours_to_sunset=5.0,
            sun_above_horizon=True,
            current_ems_mode="Maximum Self Consumption",
            current_export_limit=0.0,
            current_import_limit=0.0,
            current_pv_max_power_limit=25.0,
        )

        advisory = advisory_optimizer._decide(state)
        enforced = enforcing_optimizer._decide(state)

        self.assertTrue(advisory.export_value_gate_would_allow)
        self.assertTrue(enforced.export_value_gate_would_allow)
        self.assertEqual(advisory.export_limit, enforced.export_limit)
        self.assertEqual(advisory.ems_mode, enforced.ems_mode)
        self.assertFalse(bool(enforced.trace_gates.get("export_value_gate_vetoed")))

    def test_reason_text_uses_cents_per_kwh_units(self) -> None:
        optimizer = self._optimizer()
        state = self._state(feedin_price=0.05, feedin_price_cents=5.0)

        advisory = self._advisory(optimizer, state, desired_export_limit=5.0)

        reason = str(advisory["export_value_gate_reason"])
        self.assertIn("c/kWh", reason)
        self.assertIn("feed-in price", reason.lower())

    def test_enforcement_carveout_allows_pv_surplus_only_export_without_veto(self) -> None:
        now_ts = datetime.now().timestamp()
        enforcing_optimizer = self._optimizer(
            export_value_gate_enabled=True,
            export_value_gate_dry_run=True,
            export_value_gate_enforce=True,
        )
        enforcing_optimizer._is_evening_or_night = lambda _now: False
        state = self._state(
            battery_soc=100.0,
            battery_capacity_kwh=30.0,
            available_discharge_energy_kwh=30.0,
            current_price=0.30,
            current_price_cents=30.0,
            feedin_price=0.05,
            feedin_price_cents=5.0,
            pv_kw=3.0,
            solar_power_now_kw=3.0,
            load_kw=0.8,
            battery_power_sensor_kw=0.0,
            forecast_tomorrow_kwh=2.0,
            ess_max_discharge_kw=25.0,
            price_is_actual=True,
            next_sunrise_ts=now_ts + (10.0 * 3600),
            next_sunset_ts=now_ts + (6.0 * 3600),
            hours_to_sunrise=10.0,
            hours_to_sunset=6.0,
            sun_above_horizon=True,
            current_ems_mode="Maximum Self Consumption",
            current_export_limit=0.0,
            current_import_limit=0.0,
            current_pv_max_power_limit=25.0,
        )

        decision = enforcing_optimizer._decide(state)

        self.assertTrue(decision.export_value_gate_would_allow)
        self.assertFalse(decision.export_value_gate_would_block)
        self.assertFalse(bool(decision.trace_gates.get("export_value_gate_vetoed")))
        self.assertTrue(bool(decision.trace_gates.get("export_value_gate_pv_surplus_carveout_active")))
        self.assertEqual("pv_surplus_only", decision.trace_values.get("export_value_gate_export_type"))
        self.assertFalse(bool(decision.trace_gates.get("export_value_gate_applies_to_export_type")))
        self.assertTrue(bool(decision.trace_gates.get("export_value_gate_bypassed_for_pv_surplus_only")))
        self.assertIn("confirmed PV-only", str(decision.trace_values.get("export_classification_reason", "")))
        self.assertGreater(decision.export_limit, 0.0)
        self.assertLessEqual(
            float(decision.export_limit),
            float(decision.trace_values.get("export_value_gate_pv_surplus_kw", 0.0)) + 1e-6,
        )

    def test_enforcement_keeps_veto_for_battery_backed_export_when_not_full(self) -> None:
        now_ts = datetime.now().timestamp()
        enforcing_optimizer = self._optimizer(
            export_value_gate_enabled=True,
            export_value_gate_dry_run=True,
            export_value_gate_enforce=True,
        )
        enforcing_optimizer._is_evening_or_night = lambda _now: False
        state = self._state(
            battery_soc=98.0,
            battery_capacity_kwh=40.3,
            available_discharge_energy_kwh=39.5,
            current_price=0.30,
            current_price_cents=30.0,
            feedin_price=0.05,
            feedin_price_cents=5.0,
            pv_kw=2.1,
            solar_power_now_kw=4.4,
            load_kw=0.9,
            forecast_tomorrow_kwh=80.0,
            ess_max_discharge_kw=100.0,
            price_is_actual=True,
            next_sunrise_ts=now_ts + (10.0 * 3600),
            next_sunset_ts=now_ts + (6.0 * 3600),
            hours_to_sunrise=10.0,
            hours_to_sunset=6.0,
            sun_above_horizon=True,
            current_ems_mode="Maximum Self Consumption",
            current_export_limit=0.0,
            current_import_limit=0.0,
            current_pv_max_power_limit=25.0,
        )

        decision = enforcing_optimizer._decide(state)

        self.assertFalse(bool(decision.trace_gates.get("export_value_gate_pv_surplus_carveout_active")))
        self.assertNotEqual("pv_surplus_only", decision.trace_values.get("export_value_gate_export_type"))
        if decision.export_value_gate_would_block:
            self.assertTrue(bool(decision.trace_gates.get("export_value_gate_vetoed")))
            self.assertEqual(decision.export_limit, 0.0)

    def test_dry_run_carveout_conditions_do_not_change_actuator_outputs(self) -> None:
        now_ts = datetime.now().timestamp()
        baseline_optimizer = self._optimizer(
            export_value_gate_enabled=False,
            export_value_gate_dry_run=False,
            export_value_gate_enforce=False,
        )
        dry_run_optimizer = self._optimizer(
            export_value_gate_enabled=False,
            export_value_gate_dry_run=True,
            export_value_gate_enforce=False,
        )
        baseline_optimizer._is_evening_or_night = lambda _now: False
        dry_run_optimizer._is_evening_or_night = lambda _now: False
        state = self._state(
            battery_soc=100.0,
            battery_capacity_kwh=30.0,
            available_discharge_energy_kwh=30.0,
            current_price=0.30,
            current_price_cents=30.0,
            feedin_price=0.05,
            feedin_price_cents=5.0,
            pv_kw=3.0,
            solar_power_now_kw=3.0,
            load_kw=0.8,
            battery_power_sensor_kw=0.0,
            forecast_tomorrow_kwh=2.0,
            ess_max_discharge_kw=25.0,
            price_is_actual=True,
            next_sunrise_ts=now_ts + (10.0 * 3600),
            next_sunset_ts=now_ts + (6.0 * 3600),
            hours_to_sunrise=10.0,
            hours_to_sunset=6.0,
            sun_above_horizon=True,
            current_ems_mode="Maximum Self Consumption",
            current_export_limit=0.0,
            current_import_limit=0.0,
            current_pv_max_power_limit=25.0,
        )

        baseline = baseline_optimizer._decide(state)
        dry_run = dry_run_optimizer._decide(state)

        self.assertTrue(bool(dry_run.trace_gates.get("export_value_gate_pv_surplus_carveout_active")))
        self.assertEqual(baseline.ems_mode, dry_run.ems_mode)
        self.assertEqual(baseline.export_limit, dry_run.export_limit)
        self.assertEqual(baseline.import_limit, dry_run.import_limit)
        self.assertEqual(baseline.pv_max_power_limit, dry_run.pv_max_power_limit)
        self.assertEqual(baseline.ess_charge_limit, dry_run.ess_charge_limit)
        self.assertEqual(baseline.ess_discharge_limit, dry_run.ess_discharge_limit)

    def test_pv_surplus_export_initiation_opens_export_from_no_live_export(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            export_value_gate_enabled=True,
            export_value_gate_dry_run=True,
            export_value_gate_enforce=True,
        )
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 0.0
        state = self._state(
            battery_soc=100.0,
            battery_capacity_kwh=30.0,
            available_discharge_energy_kwh=30.0,
            current_price=0.30,
            current_price_cents=30.0,
            feedin_price=0.04,
            feedin_price_cents=4.0,
            pv_kw=3.0,
            solar_power_now_kw=3.0,
            load_kw=0.0,
            battery_power_sensor_kw=0.0,
            forecast_tomorrow_kwh=2.0,
            ess_max_discharge_kw=25.0,
            price_is_actual=True,
            next_sunrise_ts=now_ts + (10.0 * 3600),
            next_sunset_ts=now_ts + (6.0 * 3600),
            hours_to_sunrise=10.0,
            hours_to_sunset=6.0,
            sun_above_horizon=True,
            current_ems_mode="Maximum Self Consumption",
            current_export_limit=0.0,
            current_import_limit=0.0,
            current_pv_max_power_limit=25.0,
        )

        decision = optimizer._decide(state)

        self.assertLessEqual(float(decision.trace_values.get("desired_export_limit_pre_value_gate", 1.0)), 0.01)
        self.assertTrue(bool(decision.trace_gates.get("export_value_gate_pv_surplus_initiated_active")))
        self.assertFalse(bool(decision.trace_gates.get("export_value_gate_pv_surplus_carveout_active")))
        self.assertEqual("pv_surplus_only", decision.trace_values.get("export_value_gate_export_type"))
        self.assertFalse(bool(decision.trace_gates.get("export_value_gate_applies_to_export_type")))
        self.assertTrue(bool(decision.trace_gates.get("export_value_gate_bypassed_for_pv_surplus_only")))
        self.assertGreater(decision.export_limit, 0.0)
        self.assertLessEqual(
            float(decision.export_limit),
            float(decision.trace_values.get("export_value_gate_pv_surplus_kw", 0.0)) + 1e-6,
        )
        self.assertFalse(bool(decision.trace_gates.get("export_value_gate_vetoed")))

    def test_pv_surplus_export_initiation_does_not_open_when_battery_below_99(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            export_value_gate_enabled=True,
            export_value_gate_dry_run=True,
            export_value_gate_enforce=True,
        )
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 0.0
        state = self._state(
            battery_soc=98.0,
            feedin_price=0.04,
            feedin_price_cents=4.0,
            pv_kw=3.0,
            load_kw=0.0,
            sun_above_horizon=True,
            next_sunrise_ts=now_ts + (10.0 * 3600),
            next_sunset_ts=now_ts + (6.0 * 3600),
            hours_to_sunrise=10.0,
            hours_to_sunset=6.0,
        )

        decision = optimizer._decide(state)

        self.assertFalse(bool(decision.trace_gates.get("export_value_gate_pv_surplus_initiated_active")))
        self.assertEqual("no_live_export", decision.trace_values.get("export_value_gate_export_type"))
        self.assertFalse(bool(decision.trace_gates.get("export_value_gate_applies_to_export_type")))
        self.assertIn("export limit closed", str(decision.trace_values.get("export_classification_reason", "")))
        self.assertLessEqual(decision.export_limit, 0.01)

    def test_pv_surplus_export_initiation_does_not_open_on_negative_fit(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            export_value_gate_enabled=True,
            export_value_gate_dry_run=True,
            export_value_gate_enforce=True,
        )
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 0.0
        state = self._state(
            battery_soc=100.0,
            feedin_price=-0.01,
            feedin_price_cents=-1.0,
            pv_kw=3.0,
            load_kw=0.0,
            sun_above_horizon=True,
            next_sunrise_ts=now_ts + (10.0 * 3600),
            next_sunset_ts=now_ts + (6.0 * 3600),
            hours_to_sunrise=10.0,
            hours_to_sunset=6.0,
        )

        decision = optimizer._decide(state)

        self.assertFalse(bool(decision.trace_gates.get("export_value_gate_pv_surplus_initiated_active")))
        self.assertEqual("no_live_export", decision.trace_values.get("export_value_gate_export_type"))
        self.assertLessEqual(decision.export_limit, 0.01)

    def test_pv_surplus_export_initiation_does_not_open_at_night(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            export_value_gate_enabled=True,
            export_value_gate_dry_run=True,
            export_value_gate_enforce=True,
        )
        optimizer._is_evening_or_night = lambda _now: True
        optimizer._desired_export_limit = lambda *args, **kwargs: 0.0
        state = self._state(
            battery_soc=100.0,
            feedin_price=0.04,
            feedin_price_cents=4.0,
            pv_kw=3.0,
            load_kw=0.0,
            sun_above_horizon=False,
            next_sunrise_ts=now_ts + (10.0 * 3600),
            next_sunset_ts=now_ts + (6.0 * 3600),
            hours_to_sunrise=10.0,
            hours_to_sunset=6.0,
        )

        decision = optimizer._decide(state)

        self.assertFalse(bool(decision.trace_gates.get("export_value_gate_pv_surplus_initiated_active")))
        self.assertEqual("no_live_export", decision.trace_values.get("export_value_gate_export_type"))
        self.assertLessEqual(decision.export_limit, 0.01)

    def test_pv_surplus_export_initiation_does_not_open_when_surplus_zero(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            export_value_gate_enabled=True,
            export_value_gate_dry_run=True,
            export_value_gate_enforce=True,
        )
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 0.0
        state = self._state(
            battery_soc=100.0,
            feedin_price=0.04,
            feedin_price_cents=4.0,
            pv_kw=1.0,
            load_kw=1.0,
            sun_above_horizon=True,
            next_sunrise_ts=now_ts + (10.0 * 3600),
            next_sunset_ts=now_ts + (6.0 * 3600),
            hours_to_sunrise=10.0,
            hours_to_sunset=6.0,
        )

        decision = optimizer._decide(state)

        self.assertFalse(bool(decision.trace_gates.get("export_value_gate_pv_surplus_initiated_active")))
        self.assertEqual("no_live_export", decision.trace_values.get("export_value_gate_export_type"))
        self.assertLessEqual(decision.export_limit, 0.01)

    def test_pv_surplus_export_initiation_does_not_open_at_99_when_topoff_target_100(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            export_value_gate_enabled=True,
            export_value_gate_dry_run=True,
            export_value_gate_enforce=True,
            daytime_topup_max_soc=100.0,
        )
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 0.0
        state = self._state(
            battery_soc=99.0,
            feedin_price=0.08,
            feedin_price_cents=8.0,
            pv_kw=3.0,
            load_kw=0.0,
            battery_power_sensor_kw=0.0,
            sun_above_horizon=True,
            next_sunrise_ts=now_ts + (10.0 * 3600),
            next_sunset_ts=now_ts + (6.0 * 3600),
            hours_to_sunrise=10.0,
            hours_to_sunset=6.0,
            current_ems_mode="Maximum Self Consumption",
        )

        decision = optimizer._decide(state)

        self.assertFalse(bool(decision.trace_gates.get("export_value_gate_pv_surplus_initiated_active")))
        self.assertTrue(bool(decision.trace_gates.get("pv_surplus_topoff_block_active")))
        self.assertFalse(bool(decision.trace_gates.get("topoff_target_met")))
        self.assertEqual(100.0, decision.trace_values.get("topoff_target_soc"))
        self.assertIn("below top-off target 100.0%", decision.export_value_gate_reason)
        self.assertLessEqual(decision.export_limit, 0.01)

    def test_true_pv_surplus_export_allowed_below_import_floor_after_topoff(self) -> None:
        from app.optimizer import DISCHARGE_MODES

        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            export_value_gate_enabled=True,
            export_value_gate_dry_run=True,
            export_value_gate_enforce=True,
            daytime_topup_max_soc=100.0,
        )
        self._record_import_topup(optimizer, import_kwh=1.0, import_price=0.16)
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 0.0
        state = self._state(
            battery_soc=100.0,
            feedin_price=0.08,
            feedin_price_cents=8.0,
            pv_kw=3.0,
            load_kw=0.0,
            battery_power_sensor_kw=0.0,
            sun_above_horizon=True,
            next_sunrise_ts=now_ts + (10.0 * 3600),
            next_sunset_ts=now_ts + (6.0 * 3600),
            hours_to_sunrise=10.0,
            hours_to_sunset=6.0,
            current_ems_mode="Maximum Self Consumption",
        )

        decision = optimizer._decide(state)

        self.assertTrue(bool(decision.trace_gates.get("topoff_target_met")))
        self.assertTrue(bool(decision.trace_gates.get("pv_surplus_only_proven")))
        self.assertTrue(bool(decision.trace_gates.get("pv_surplus_export_allowed_below_import_floor")))
        self.assertTrue(bool(decision.trace_gates.get("export_value_gate_pv_surplus_initiated_active")))
        self.assertFalse(bool(decision.trace_gates.get("export_value_gate_vetoed")))
        self.assertNotIn(decision.ems_mode, DISCHARGE_MODES)
        self.assertEqual("pv_surplus_only", decision.trace_values.get("export_value_gate_export_type"))
        self.assertLessEqual(
            float(decision.export_limit),
            float(decision.trace_values.get("measured_pv_surplus_kw", 0.0)) + 1e-6,
        )

    def test_hard_import_cost_guard_blocks_automatic_export_when_enforcement_disabled(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            export_value_gate_enabled=False,
            export_value_gate_dry_run=False,
            export_value_gate_enforce=False,
        )
        self._record_import_topup(optimizer, import_kwh=1.0, import_price=0.16)
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 2.0
        state = self._state(
            battery_soc=100.0,
            feedin_price=0.08,
            feedin_price_cents=8.0,
            pv_kw=0.0,
            load_kw=0.0,
            battery_power_sensor_kw=-0.2,
            sun_above_horizon=True,
            next_sunrise_ts=now_ts + (10.0 * 3600),
            next_sunset_ts=now_ts + (6.0 * 3600),
            hours_to_sunrise=10.0,
            hours_to_sunset=6.0,
            current_ems_mode="Maximum Self Consumption",
        )

        decision = optimizer._decide(state)

        self.assertFalse(bool(decision.trace_gates.get("export_value_gate_enforcement_active")))
        self.assertTrue(bool(decision.trace_gates.get("actual_import_cost_guard_active")))
        self.assertTrue(bool(decision.trace_gates.get("actual_import_cost_guard_blocking")))
        self.assertTrue(bool(decision.trace_gates.get("automatic_export_blocked_below_actual_import_cost")))
        self.assertEqual(0.0, decision.export_limit)
        self.assertIn("actual import-cost guard", decision.export_reason)

    def test_true_pv_surplus_below_import_floor_allowed_when_enforcement_disabled(self) -> None:
        from app.optimizer import DISCHARGE_MODES

        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            export_value_gate_enabled=False,
            export_value_gate_dry_run=False,
            export_value_gate_enforce=False,
            daytime_topup_max_soc=100.0,
        )
        self._record_import_topup(optimizer, import_kwh=1.0, import_price=0.16)
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 0.0
        state = self._state(
            battery_soc=100.0,
            feedin_price=0.08,
            feedin_price_cents=8.0,
            pv_kw=3.0,
            load_kw=0.0,
            battery_power_sensor_kw=0.0,
            sun_above_horizon=True,
            next_sunrise_ts=now_ts + (10.0 * 3600),
            next_sunset_ts=now_ts + (6.0 * 3600),
            hours_to_sunrise=10.0,
            hours_to_sunset=6.0,
            current_ems_mode="Maximum Self Consumption",
        )

        decision = optimizer._decide(state)

        self.assertFalse(bool(decision.trace_gates.get("export_value_gate_enforcement_active")))
        self.assertTrue(bool(decision.trace_gates.get("actual_import_cost_guard_active")))
        self.assertFalse(bool(decision.trace_gates.get("actual_import_cost_guard_blocking")))
        self.assertTrue(bool(decision.trace_gates.get("pv_surplus_only_proven")))
        self.assertTrue(bool(decision.trace_gates.get("pv_surplus_export_allowed_below_import_floor")))
        self.assertEqual("pv_surplus_only", decision.trace_values.get("export_value_gate_export_type"))
        self.assertFalse(bool(decision.trace_gates.get("export_value_gate_applies_to_export_type")))
        self.assertTrue(bool(decision.trace_gates.get("export_value_gate_bypassed_for_pv_surplus_only")))
        self.assertIn("confirmed PV-only", str(decision.trace_values.get("export_classification_reason", "")))
        self.assertNotIn(decision.ems_mode, DISCHARGE_MODES)
        self.assertLessEqual(
            float(decision.export_limit),
            float(decision.trace_values.get("measured_pv_surplus_kw", 0.0)) + 1e-6,
        )

    def test_estimated_pv_surplus_initiation_opens_conservative_probe(self) -> None:
        from app.optimizer import DISCHARGE_MODES

        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(daytime_topup_max_soc=100.0)
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 0.0
        state = self._state(
            battery_soc=100.0,
            feedin_price=0.08,
            feedin_price_cents=8.0,
            pv_kw=1.0,
            solar_power_now_kw=3.0,
            load_kw=1.0,
            battery_power_sensor_kw=0.0,
            sun_above_horizon=True,
            next_sunrise_ts=now_ts + (10.0 * 3600),
            next_sunset_ts=now_ts + (6.0 * 3600),
            hours_to_sunrise=10.0,
            hours_to_sunset=6.0,
            current_ems_mode="Maximum Self Consumption",
        )

        decision = optimizer._decide(state)

        self.assertTrue(bool(decision.trace_gates.get("pv_surplus_estimated_init_enabled")))
        self.assertTrue(bool(decision.trace_gates.get("pv_surplus_estimated_init_active")))
        self.assertEqual("estimated", decision.trace_values.get("pv_surplus_initiation_source"))
        self.assertEqual("pv_surplus_only", decision.trace_values.get("export_value_gate_export_type"))
        self.assertFalse(bool(decision.trace_gates.get("export_value_gate_applies_to_export_type")))
        self.assertIn("estimated_probe", str(decision.trace_values.get("export_classification_reason", "")))
        self.assertGreater(decision.export_limit, 0.0)
        self.assertLessEqual(
            float(decision.export_limit),
            float(decision.trace_values.get("estimated_pv_surplus_kw", 0.0)) + 1e-6,
        )
        self.assertLessEqual(float(decision.export_limit), 0.5 + 1e-6)
        self.assertNotIn(decision.ems_mode, DISCHARGE_MODES)

    def test_estimated_pv_surplus_initiation_requires_positive_fit(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(daytime_topup_max_soc=100.0)
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 0.0
        state = self._state(
            battery_soc=100.0,
            feedin_price=0.0,
            feedin_price_cents=0.0,
            pv_kw=1.0,
            solar_power_now_kw=3.0,
            load_kw=1.0,
            battery_power_sensor_kw=0.0,
            sun_above_horizon=True,
            next_sunrise_ts=now_ts + (10.0 * 3600),
            next_sunset_ts=now_ts + (6.0 * 3600),
            hours_to_sunrise=10.0,
            hours_to_sunset=6.0,
            current_ems_mode="Maximum Self Consumption",
        )

        decision = optimizer._decide(state)

        self.assertFalse(bool(decision.trace_gates.get("pv_surplus_estimated_init_active")))
        self.assertEqual("none", decision.trace_values.get("pv_surplus_initiation_source"))
        self.assertLessEqual(decision.export_limit, 0.01)

    def test_estimated_pv_surplus_initiation_requires_topoff_target(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(daytime_topup_max_soc=100.0)
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 0.0
        state = self._state(
            battery_soc=99.0,
            feedin_price=0.08,
            feedin_price_cents=8.0,
            pv_kw=1.0,
            solar_power_now_kw=3.0,
            load_kw=1.0,
            battery_power_sensor_kw=0.0,
            sun_above_horizon=True,
            next_sunrise_ts=now_ts + (10.0 * 3600),
            next_sunset_ts=now_ts + (6.0 * 3600),
            hours_to_sunrise=10.0,
            hours_to_sunset=6.0,
            current_ems_mode="Maximum Self Consumption",
        )

        decision = optimizer._decide(state)

        self.assertFalse(bool(decision.trace_gates.get("topoff_target_met")))
        self.assertFalse(bool(decision.trace_gates.get("pv_surplus_estimated_init_active")))
        self.assertLessEqual(decision.export_limit, 0.01)

    def test_estimated_pv_surplus_initiation_skips_manual_force_mode(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(daytime_topup_max_soc=100.0)
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 0.0
        cfg = optimizer.cfg
        state = self._state(
            sigenergy_mode=cfg.full_export_option,
            battery_soc=100.0,
            feedin_price=0.08,
            feedin_price_cents=8.0,
            pv_kw=1.0,
            solar_power_now_kw=3.0,
            load_kw=1.0,
            battery_power_sensor_kw=0.0,
            sun_above_horizon=True,
            next_sunrise_ts=now_ts + (10.0 * 3600),
            next_sunset_ts=now_ts + (6.0 * 3600),
            hours_to_sunrise=10.0,
            hours_to_sunset=6.0,
            current_ems_mode="Maximum Self Consumption",
            current_export_limit=0.01,
            current_import_limit=0.01,
            current_pv_max_power_limit=25.0,
            current_ess_charge_limit=21.0,
            current_ess_discharge_limit=24.0,
        )

        decision = optimizer._decide(state)
        optimizer._freeze_decision_to_live_mode(state, decision, cfg.full_export_option)

        self.assertFalse(bool(decision.trace_gates.get("pv_surplus_estimated_init_active")))
        self.assertEqual("none", decision.trace_values.get("pv_surplus_initiation_source"))
        self.assertGreater(decision.export_limit, 0.0)

    def test_estimated_pv_surplus_initiation_disabled_keeps_export_closed(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            daytime_topup_max_soc=100.0,
            pv_surplus_estimated_init_enabled=False,
        )
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 0.0
        state = self._state(
            battery_soc=100.0,
            feedin_price=0.08,
            feedin_price_cents=8.0,
            pv_kw=1.0,
            solar_power_now_kw=3.0,
            load_kw=1.0,
            battery_power_sensor_kw=0.0,
            sun_above_horizon=True,
            next_sunrise_ts=now_ts + (10.0 * 3600),
            next_sunset_ts=now_ts + (6.0 * 3600),
            hours_to_sunrise=10.0,
            hours_to_sunset=6.0,
            current_ems_mode="Maximum Self Consumption",
        )

        decision = optimizer._decide(state)

        self.assertFalse(bool(decision.trace_gates.get("pv_surplus_estimated_init_enabled")))
        self.assertFalse(bool(decision.trace_gates.get("pv_surplus_estimated_init_active")))
        self.assertLessEqual(decision.export_limit, 0.01)

    def test_full_battery_breathe_probe_opens_tiny_hidden_pv_probe(self) -> None:
        from app.optimizer import DISCHARGE_MODES

        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(daytime_topup_max_soc=100.0)
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 0.0
        state = self._breathe_probe_state(now_ts)

        decision = optimizer._decide(state)

        max_probe_kw = max(
            float(optimizer.cfg.morning_slow_export_probe_step_kw),
            float(optimizer.cfg.min_grid_transfer_kw),
        )
        self.assertTrue(bool(decision.trace_gates.get("export_value_gate_pv_surplus_initiated_active")))
        self.assertTrue(bool(decision.trace_gates.get("pv_surplus_breathe_probe_active")))
        self.assertFalse(bool(decision.trace_gates.get("pv_surplus_estimated_init_active")))
        self.assertEqual("full_battery_breathe_probe", decision.trace_values.get("pv_surplus_initiation_source"))
        self.assertEqual("pv_surplus_only", decision.trace_values.get("export_value_gate_export_type"))
        self.assertGreater(decision.export_limit, 0.0)
        self.assertLessEqual(decision.export_limit, max_probe_kw + 1e-6)
        self.assertLessEqual(decision.export_limit, float(optimizer.cfg.export_limit_low) + 1e-6)
        self.assertEqual(decision.export_limit, decision.trace_values.get("pv_surplus_probe_export_cap_kw"))
        self.assertTrue(optimizer._full_battery_breathe_probe_active)
        self.assertEqual(decision.export_limit, optimizer._full_battery_breathe_probe_cap_kw)
        self.assertTrue(bool(decision.trace_gates.get("pv_surplus_breathe_probe_state_active")))
        self.assertEqual(
            decision.export_limit,
            decision.trace_values.get("pv_surplus_breathe_probe_state_cap_kw"),
        )
        self.assertLess(float(decision.trace_values.get("measured_pv_surplus_kw", 0.0)), optimizer.cfg.min_grid_transfer_kw)
        self.assertLess(float(decision.trace_values.get("estimated_pv_surplus_kw", 0.0)), optimizer.cfg.min_grid_transfer_kw)
        self.assertNotIn(decision.ems_mode, DISCHARGE_MODES)
        self.assertIn("full-battery hidden-PV breathe probe", str(decision.trace_values.get("pv_surplus_estimated_init_reason", "")))

    def test_full_battery_breathe_probe_continues_and_ramps_from_open_export(self) -> None:
        from app.optimizer import DISCHARGE_MODES

        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            daytime_topup_max_soc=100.0,
            morning_slow_export_probe_step_kw=1.0,
        )
        optimizer._last_decision = self._previous_breathe_probe_decision(export_limit=1.0)
        self._seed_breathe_probe_state(optimizer, now_ts, export_limit=1.0)
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 0.0
        state = self._breathe_probe_state(
            now_ts,
            pv_kw=1.3,
            solar_power_now_kw=1.3,
            load_kw=0.9,
            current_export_limit=1.0,
            grid_export_power_kw=1.0,
        )

        decision = optimizer._decide(state)

        self.assertTrue(bool(decision.trace_gates.get("pv_surplus_breathe_probe_active")))
        self.assertTrue(bool(decision.trace_gates.get("pv_surplus_breathe_probe_continuation_active")))
        self.assertEqual("full_battery_breathe_probe", decision.trace_values.get("pv_surplus_initiation_source"))
        self.assertEqual("pv_surplus_only", decision.trace_values.get("export_value_gate_export_type"))
        self.assertGreater(decision.export_limit, state.current_export_limit)
        self.assertLessEqual(
            decision.export_limit,
            state.current_export_limit + optimizer.cfg.morning_slow_export_probe_step_kw + 1e-6,
        )
        self.assertLessEqual(decision.export_limit, state.grid_export_power_kw + optimizer.cfg.morning_slow_export_probe_step_kw + 1e-6)
        self.assertEqual(decision.export_limit, decision.trace_values.get("pv_surplus_probe_export_cap_kw"))
        self.assertNotIn(decision.ems_mode, DISCHARGE_MODES)
        self.assertIn("continuing PV-surplus/breathe discovery", str(decision.trace_values.get("pv_surplus_estimated_init_reason", "")))

    def test_full_battery_breathe_probe_continues_when_desired_export_already_open_with_hidden_surplus(self) -> None:
        from app.optimizer import DISCHARGE_MODES

        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            daytime_topup_max_soc=100.0,
            export_value_gate_enabled=True,
            export_value_gate_dry_run=True,
            export_value_gate_enforce=True,
        )
        self._record_import_topup(optimizer, import_kwh=1.0, import_price=0.23)
        optimizer._last_decision = self._previous_breathe_probe_decision(export_limit=1.0)
        self._seed_breathe_probe_state(optimizer, now_ts, export_limit=1.0)
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 5.0
        state = self._breathe_probe_state(
            now_ts,
            battery_soc=100.0,
            feedin_price=0.08,
            feedin_price_cents=8.0,
            pv_kw=0.9,
            solar_power_now_kw=6.0,
            load_kw=0.9,
            battery_power_sensor_kw=-0.01,
            current_export_limit=1.0,
            grid_export_power_kw=0.0,
        )

        decision = optimizer._decide(state)

        self.assertTrue(bool(decision.trace_gates.get("pv_only_discharge_ok")))
        self.assertTrue(bool(decision.trace_gates.get("pv_surplus_breathe_probe_active")))
        self.assertTrue(bool(decision.trace_gates.get("pv_surplus_breathe_probe_continuation_active")))
        self.assertEqual("full_battery_breathe_probe", decision.trace_values.get("pv_surplus_initiation_source"))
        self.assertEqual("pv_surplus_only", decision.trace_values.get("export_value_gate_export_type"))
        self.assertTrue(bool(decision.trace_gates.get("pv_surplus_export_allowed_below_import_floor")))
        self.assertFalse(bool(decision.trace_gates.get("export_value_gate_vetoed")))
        self.assertFalse(bool(decision.trace_gates.get("actual_import_cost_guard_blocking")))
        self.assertGreater(decision.export_limit, 0.0)
        self.assertLessEqual(
            decision.export_limit,
            1.0 + max(optimizer.cfg.morning_slow_export_probe_step_kw, optimizer.cfg.min_grid_transfer_kw) + 1e-6,
        )
        self.assertNotIn(decision.ems_mode, DISCHARGE_MODES)
        reason = str(decision.trace_values.get("pv_surplus_estimated_init_reason", ""))
        self.assertIn("continuing PV-surplus/breathe discovery", reason)
        self.assertNotIn("live export is already open", reason)

    def test_full_battery_breathe_probe_internal_state_continues_live_open_export(self) -> None:
        from app.optimizer import DISCHARGE_MODES

        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            daytime_topup_max_soc=100.0,
            export_value_gate_enabled=True,
            export_value_gate_dry_run=True,
            export_value_gate_enforce=True,
        )
        self._record_import_topup(optimizer, import_kwh=1.0, import_price=0.23)
        self._seed_breathe_probe_state(optimizer, now_ts, export_limit=1.0)
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 5.0
        state = self._breathe_probe_state(
            now_ts,
            battery_soc=100.0,
            feedin_price=0.08,
            feedin_price_cents=8.0,
            pv_kw=0.9,
            solar_power_now_kw=5.3,
            load_kw=0.9,
            battery_power_sensor_kw=-0.01,
            current_export_limit=1.0,
            grid_export_power_kw=1.0,
        )

        decision = optimizer._decide(state)

        self.assertTrue(bool(decision.trace_gates.get("pv_only_discharge_ok")))
        self.assertTrue(bool(decision.trace_gates.get("pv_surplus_breathe_probe_active")))
        self.assertTrue(bool(decision.trace_gates.get("pv_surplus_breathe_probe_continuation_active")))
        self.assertTrue(bool(decision.trace_gates.get("pv_surplus_breathe_probe_state_active")))
        self.assertEqual("full_battery_breathe_probe", decision.trace_values.get("pv_surplus_initiation_source"))
        self.assertEqual("pv_surplus_only", decision.trace_values.get("export_value_gate_export_type"))
        self.assertTrue(bool(decision.trace_gates.get("pv_surplus_export_allowed_below_import_floor")))
        self.assertFalse(bool(decision.trace_gates.get("export_value_gate_vetoed")))
        self.assertFalse(bool(decision.trace_gates.get("actual_import_cost_guard_blocking")))
        self.assertGreater(decision.export_limit, 0.0)
        self.assertLessEqual(
            decision.export_limit,
            1.0 + max(optimizer.cfg.morning_slow_export_probe_step_kw, optimizer.cfg.min_grid_transfer_kw) + 1e-6,
        )
        self.assertEqual(
            decision.export_limit,
            decision.trace_values.get("pv_surplus_breathe_probe_state_cap_kw"),
        )
        self.assertNotIn(decision.ems_mode, DISCHARGE_MODES)
        self.assertTrue(optimizer._full_battery_breathe_probe_active)
        reason = str(decision.trace_values.get("pv_surplus_estimated_init_reason", ""))
        self.assertIn("continuing PV-surplus/breathe discovery", reason)
        self.assertNotIn("live export is already open", reason)

    def test_stale_pv_discovery_state_cannot_continue_from_last_decision_trace(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(daytime_topup_max_soc=100.0)
        optimizer._last_decision = self._previous_breathe_probe_decision(export_limit=1.5)
        optimizer._record_pv_discovery_state(
            "full_battery_breathe_probe",
            1.5,
            now_ts - 301.0,
        )
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 0.0
        state = self._breathe_probe_state(
            now_ts,
            pv_kw=1.3,
            solar_power_now_kw=1.3,
            load_kw=0.9,
            current_export_limit=1.0,
            grid_export_power_kw=1.0,
        )

        decision = optimizer._decide(state)

        self.assertFalse(optimizer._pv_discovery_active)
        self.assertFalse(optimizer._full_battery_breathe_probe_active)
        self.assertFalse(bool(decision.trace_gates.get("pv_only_discovery_active")))
        self.assertFalse(bool(decision.trace_gates.get("pv_only_discovery_state_active")))
        self.assertFalse(bool(decision.trace_gates.get("pv_surplus_breathe_probe_active")))
        self.assertFalse(bool(decision.trace_gates.get("pv_surplus_breathe_probe_continuation_active")))
        self.assertEqual("none", decision.trace_values.get("pv_surplus_initiation_source"))
        self.assertEqual(0.0, float(decision.trace_values.get("pv_surplus_probe_export_cap_kw", 0.0)))
        self.assertEqual(0.0, float(decision.trace_values.get("pv_only_discovery_cap_kw", 0.0)))
        self.assertEqual(0.0, decision.export_limit)

    def test_full_battery_breathe_probe_continuation_capped_by_export_limit_low(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            daytime_topup_max_soc=100.0,
            export_limit_low=1.2,
            morning_slow_export_probe_step_kw=1.0,
        )
        optimizer._last_decision = self._previous_breathe_probe_decision(export_limit=1.0)
        self._seed_breathe_probe_state(optimizer, now_ts, export_limit=1.0)
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 0.0
        state = self._breathe_probe_state(
            now_ts,
            pv_kw=1.3,
            solar_power_now_kw=1.3,
            load_kw=0.9,
            current_export_limit=1.0,
            grid_export_power_kw=1.2,
        )

        decision = optimizer._decide(state)

        self.assertTrue(bool(decision.trace_gates.get("pv_surplus_breathe_probe_continuation_active")))
        self.assertEqual("full_battery_breathe_probe", decision.trace_values.get("pv_surplus_initiation_source"))
        self.assertLessEqual(decision.export_limit, optimizer.cfg.export_limit_low + 1e-6)
        self.assertEqual(1.2, decision.export_limit)

    def test_full_battery_breathe_probe_blocked_when_battery_discharge_measured(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(daytime_topup_max_soc=100.0)
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 0.0
        state = self._breathe_probe_state(
            now_ts,
            battery_power_sensor_kw=-0.2,
        )

        decision = optimizer._decide(state)

        self.assertFalse(bool(decision.trace_gates.get("pv_surplus_breathe_probe_active")))
        self.assertFalse(bool(decision.trace_gates.get("export_value_gate_pv_surplus_initiated_active")))
        self.assertEqual("none", decision.trace_values.get("pv_surplus_initiation_source"))
        self.assertLessEqual(decision.export_limit, 0.01)

    def test_full_battery_breathe_probe_below_import_floor_allowed_only_when_safe(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(daytime_topup_max_soc=100.0)
        self._record_import_topup(optimizer, import_kwh=1.0, import_price=0.16)
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 0.0
        state = self._breathe_probe_state(now_ts)

        decision = optimizer._decide(state)

        self.assertTrue(bool(decision.trace_gates.get("actual_import_cost_guard_active")))
        self.assertFalse(bool(decision.trace_gates.get("actual_import_cost_guard_blocking")))
        self.assertTrue(bool(decision.trace_gates.get("pv_surplus_breathe_probe_active")))
        self.assertTrue(bool(decision.trace_gates.get("pv_surplus_export_allowed_below_import_floor")))
        self.assertEqual("pv_surplus_only", decision.trace_values.get("export_value_gate_export_type"))
        self.assertFalse(bool(decision.trace_gates.get("export_value_gate_applies_to_export_type")))
        self.assertIn("full_battery_breathe_probe", str(decision.trace_values.get("export_classification_reason", "")))
        self.assertGreater(decision.export_limit, 0.0)

    def test_measured_pv_surplus_carveout_seeds_breathe_discovery_state(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            daytime_topup_max_soc=100.0,
            export_value_gate_enabled=True,
            export_value_gate_dry_run=True,
            export_value_gate_enforce=True,
        )
        self._record_import_topup(optimizer, import_kwh=1.0, import_price=0.23)

        decision = self._run_measured_carveout_seed(optimizer, now_ts)

        self.assertFalse(bool(decision.trace_gates.get("export_value_gate_pv_surplus_initiated_active")))
        self.assertTrue(bool(decision.trace_gates.get("export_value_gate_pv_surplus_carveout_active")))
        self.assertTrue(bool(decision.trace_gates.get("pv_surplus_export_allowed_below_import_floor")))
        self.assertEqual("none", decision.trace_values.get("pv_surplus_initiation_source"))
        self.assertEqual("pv_surplus_only", decision.trace_values.get("export_value_gate_export_type"))
        self.assertTrue(optimizer._full_battery_breathe_probe_active)
        self.assertEqual("pv_surplus_carveout", optimizer._full_battery_breathe_probe_source)
        self.assertTrue(bool(decision.trace_gates.get("pv_surplus_breathe_probe_state_active")))
        self.assertTrue(bool(decision.trace_gates.get("pv_surplus_breathe_probe_state_from_carveout")))
        self.assertEqual("pv_surplus_carveout", decision.trace_values.get("pv_surplus_breathe_probe_state_source"))
        self.assertEqual(decision.export_limit, decision.trace_values.get("pv_surplus_breathe_probe_state_cap_kw"))

    def test_measured_carveout_state_continues_live_open_export_as_pv_only(self) -> None:
        from app.optimizer import DISCHARGE_MODES

        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            daytime_topup_max_soc=100.0,
            export_value_gate_enabled=True,
            export_value_gate_dry_run=True,
            export_value_gate_enforce=True,
        )
        self._record_import_topup(optimizer, import_kwh=1.0, import_price=0.23)
        seed_decision = self._run_measured_carveout_seed(optimizer, now_ts)
        self.assertTrue(bool(seed_decision.trace_gates.get("pv_surplus_breathe_probe_state_from_carveout")))

        optimizer._desired_export_limit = lambda *args, **kwargs: 5.0
        state = self._breathe_probe_state(
            now_ts,
            battery_soc=100.0,
            feedin_price=0.08,
            feedin_price_cents=8.0,
            pv_kw=1.9,
            solar_power_now_kw=5.3,
            load_kw=0.9,
            battery_power_sensor_kw=-0.01,
            current_export_limit=1.0,
            grid_export_power_kw=1.0,
        )

        decision = optimizer._decide(state)

        self.assertTrue(bool(decision.trace_gates.get("pv_surplus_breathe_probe_active")))
        self.assertTrue(bool(decision.trace_gates.get("pv_surplus_breathe_probe_continuation_active")))
        self.assertTrue(bool(decision.trace_gates.get("pv_surplus_breathe_probe_state_active")))
        self.assertEqual("pv_surplus_discovery", decision.trace_values.get("pv_surplus_initiation_source"))
        self.assertEqual("pv_surplus_only", decision.trace_values.get("export_value_gate_export_type"))
        self.assertFalse(bool(decision.trace_gates.get("export_value_gate_applies_to_export_type")))
        self.assertTrue(bool(decision.trace_gates.get("pv_surplus_export_allowed_below_import_floor")))
        self.assertFalse(bool(decision.trace_gates.get("export_value_gate_vetoed")))
        self.assertFalse(bool(decision.trace_gates.get("actual_import_cost_guard_blocking")))
        self.assertGreater(float(decision.trace_values.get("pv_surplus_probe_export_cap_kw", 0.0)), 0.0)
        self.assertGreater(decision.export_limit, 0.0)
        self.assertLessEqual(
            decision.export_limit,
            1.0 + max(optimizer.cfg.morning_slow_export_probe_step_kw, optimizer.cfg.min_grid_transfer_kw) + 1e-6,
        )
        self.assertNotIn(decision.ems_mode, DISCHARGE_MODES)
        reason = str(decision.trace_values.get("pv_surplus_estimated_init_reason", ""))
        self.assertIn("continuing PV-surplus/breathe discovery", reason)
        self.assertNotIn("live export is already open", reason)

    def test_pv_only_discovery_estimated_probe_records_state_and_continues(self) -> None:
        from app.optimizer import DISCHARGE_MODES

        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            daytime_topup_max_soc=100.0,
            export_value_gate_enabled=True,
            export_value_gate_dry_run=True,
            export_value_gate_enforce=True,
        )
        self._record_import_topup(optimizer, import_kwh=1.0, import_price=0.23)
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 0.0
        seed_state = self._breathe_probe_state(
            now_ts,
            pv_kw=0.9,
            solar_power_now_kw=5.5,
            load_kw=0.9,
            battery_power_sensor_kw=-0.01,
            current_export_limit=0.01,
            grid_export_power_kw=0.0,
        )

        seed_decision = optimizer._decide(seed_state)

        self.assertTrue(bool(seed_decision.trace_gates.get("pv_only_discovery_active")))
        self.assertTrue(bool(seed_decision.trace_gates.get("pv_surplus_estimated_init_active")))
        self.assertEqual("estimated_probe", seed_decision.trace_values.get("pv_only_discovery_source"))
        self.assertEqual("estimated_probe", optimizer._pv_discovery_source)
        self.assertTrue(optimizer._pv_discovery_active)
        self.assertGreater(optimizer._pv_discovery_cap_kw, 0.0)
        self.assertEqual("pv_surplus_only", seed_decision.trace_values.get("export_value_gate_export_type"))
        self.assertFalse(bool(seed_decision.trace_gates.get("actual_import_cost_guard_blocking")))
        self.assertNotIn(seed_decision.ems_mode, DISCHARGE_MODES)

        optimizer._desired_export_limit = lambda *args, **kwargs: 5.0
        next_state = self._breathe_probe_state(
            now_ts + 60.0,
            pv_kw=1.9,
            solar_power_now_kw=5.5,
            load_kw=0.9,
            battery_power_sensor_kw=-0.01,
            current_export_limit=seed_decision.export_limit,
            grid_export_power_kw=seed_decision.export_limit,
        )

        decision = optimizer._decide(next_state)

        self.assertTrue(bool(decision.trace_gates.get("pv_only_discovery_active")))
        self.assertTrue(bool(decision.trace_gates.get("pv_surplus_breathe_probe_continuation_active")))
        self.assertEqual("pv_surplus_discovery", decision.trace_values.get("pv_surplus_initiation_source"))
        self.assertEqual("pv_surplus_discovery", decision.trace_values.get("pv_only_discovery_source"))
        self.assertEqual("pv_surplus_only", decision.trace_values.get("export_value_gate_export_type"))
        self.assertTrue(bool(decision.trace_gates.get("pv_surplus_export_allowed_below_import_floor")))
        self.assertFalse(bool(decision.trace_gates.get("export_value_gate_applies_to_export_type")))
        self.assertFalse(bool(decision.trace_gates.get("export_value_gate_vetoed")))
        self.assertFalse(bool(decision.trace_gates.get("actual_import_cost_guard_blocking")))
        self.assertGreater(decision.export_limit, 0.0)
        self.assertLessEqual(
            decision.export_limit,
            seed_decision.export_limit
            + max(optimizer.cfg.morning_slow_export_probe_step_kw, optimizer.cfg.min_grid_transfer_kw)
            + 1e-6,
        )
        self.assertNotIn(decision.ems_mode, DISCHARGE_MODES)
        self.assertIn("PV-only discovery/ramp", str(decision.trace_values.get("pv_surplus_estimated_init_reason", "")))

    def test_untrusted_import_cost_does_not_block_safe_pv_only_discovery(self) -> None:
        from app.optimizer import DISCHARGE_MODES

        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            daytime_topup_max_soc=100.0,
            export_value_gate_enabled=True,
            export_value_gate_dry_run=True,
            export_value_gate_enforce=True,
        )
        self._record_import_topup(
            optimizer,
            import_kwh=0.5,
            import_price=None,
            price_trusted=False,
        )
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 0.0
        state = self._breathe_probe_state(
            now_ts,
            pv_kw=0.9,
            solar_power_now_kw=5.5,
            load_kw=0.9,
            battery_power_sensor_kw=-0.01,
            current_export_limit=0.01,
            grid_export_power_kw=0.0,
        )

        decision = optimizer._decide(state)

        self.assertTrue(bool(decision.trace_gates.get("import_cost_floor_unknown")))
        self.assertTrue(bool(decision.trace_gates.get("actual_import_cost_guard_active")))
        self.assertFalse(bool(decision.trace_gates.get("actual_import_cost_guard_applies_to_export_type")))
        self.assertTrue(bool(decision.trace_gates.get("actual_import_cost_guard_bypassed_for_pv_surplus_only")))
        self.assertFalse(bool(decision.trace_gates.get("actual_import_cost_guard_blocking")))
        self.assertFalse(bool(decision.trace_gates.get("export_value_gate_vetoed")))
        self.assertEqual("pv_surplus_only", decision.trace_values.get("export_value_gate_export_type"))
        self.assertGreater(decision.export_limit, 0.0)
        self.assertNotIn(decision.ems_mode, DISCHARGE_MODES)
        reason = str(decision.trace_values.get("actual_import_cost_guard_reason", ""))
        self.assertIn("bypassed: confirmed PV-only surplus/discovery export", reason)
        self.assertNotIn("unavailable or untrusted", reason)

    def test_pv_only_discovery_state_real_discharge_clears_and_blocks(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            daytime_topup_max_soc=100.0,
            export_value_gate_enabled=True,
            export_value_gate_dry_run=True,
            export_value_gate_enforce=True,
        )
        self._record_import_topup(optimizer, import_kwh=1.0, import_price=0.23)
        optimizer._record_pv_discovery_state("estimated_probe", 1.0, now_ts)
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 1.0
        state = self._breathe_probe_state(
            now_ts + 60.0,
            pv_kw=1.9,
            solar_power_now_kw=5.3,
            load_kw=0.9,
            battery_power_sensor_kw=-0.2,
            current_export_limit=1.0,
            grid_export_power_kw=1.0,
        )

        decision = optimizer._decide(state)

        self.assertFalse(bool(decision.trace_gates.get("pv_only_discovery_active")))
        self.assertFalse(bool(decision.trace_gates.get("pv_only_discovery_state_active")))
        self.assertEqual("battery_backed", decision.trace_values.get("export_value_gate_export_type"))
        self.assertTrue(bool(decision.trace_gates.get("actual_import_cost_guard_blocking")))
        self.assertEqual(0.0, decision.export_limit)
        self.assertFalse(optimizer._pv_discovery_active)

    def test_untrusted_import_cost_blocks_discovery_when_battery_discharge_is_real(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            daytime_topup_max_soc=100.0,
            export_value_gate_enabled=True,
            export_value_gate_dry_run=True,
            export_value_gate_enforce=True,
        )
        self._record_import_topup(
            optimizer,
            import_kwh=0.5,
            import_price=None,
            price_trusted=False,
        )
        optimizer._record_pv_discovery_state("estimated_probe", 1.0, now_ts)
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 1.0
        state = self._breathe_probe_state(
            now_ts + 60.0,
            pv_kw=1.9,
            solar_power_now_kw=5.3,
            load_kw=0.9,
            battery_power_sensor_kw=-0.2,
            current_export_limit=1.0,
            grid_export_power_kw=1.0,
        )

        decision = optimizer._decide(state)

        self.assertFalse(bool(decision.trace_gates.get("pv_only_discovery_active")))
        self.assertEqual("battery_backed", decision.trace_values.get("export_value_gate_export_type"))
        self.assertTrue(bool(decision.trace_gates.get("actual_import_cost_guard_applies_to_export_type")))
        self.assertFalse(bool(decision.trace_gates.get("actual_import_cost_guard_bypassed_for_pv_surplus_only")))
        self.assertTrue(bool(decision.trace_gates.get("actual_import_cost_guard_blocking")))
        self.assertEqual(0.0, decision.export_limit)
        self.assertIn("unavailable or untrusted", decision.trace_values.get("actual_import_cost_guard_reason"))

    def test_measured_carveout_state_real_discharge_clears_and_blocks(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            daytime_topup_max_soc=100.0,
            export_value_gate_enabled=True,
            export_value_gate_dry_run=True,
            export_value_gate_enforce=True,
        )
        self._record_import_topup(optimizer, import_kwh=1.0, import_price=0.23)
        self._run_measured_carveout_seed(optimizer, now_ts)
        self.assertTrue(optimizer._full_battery_breathe_probe_active)

        optimizer._desired_export_limit = lambda *args, **kwargs: 1.0
        state = self._breathe_probe_state(
            now_ts,
            pv_kw=1.9,
            solar_power_now_kw=5.3,
            load_kw=0.9,
            battery_power_sensor_kw=-0.2,
            current_export_limit=1.0,
            grid_export_power_kw=1.0,
        )

        decision = optimizer._decide(state)

        self.assertFalse(bool(decision.trace_gates.get("pv_only_discharge_ok")))
        self.assertFalse(bool(decision.trace_gates.get("pv_surplus_breathe_probe_active")))
        self.assertEqual("battery_backed", decision.trace_values.get("export_value_gate_export_type"))
        self.assertTrue(bool(decision.trace_gates.get("export_value_gate_applies_to_export_type")))
        self.assertTrue(bool(decision.trace_gates.get("actual_import_cost_guard_blocking")))
        self.assertEqual(0.0, decision.export_limit)
        self.assertFalse(optimizer._full_battery_breathe_probe_active)
        self.assertFalse(bool(decision.trace_gates.get("pv_surplus_breathe_probe_state_active")))

    def test_measured_carveout_state_unknown_battery_flow_clears_and_blocks(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            daytime_topup_max_soc=100.0,
            export_value_gate_enabled=True,
            export_value_gate_dry_run=True,
            export_value_gate_enforce=True,
        )
        self._record_import_topup(optimizer, import_kwh=1.0, import_price=0.23)
        self._run_measured_carveout_seed(optimizer, now_ts)
        self.assertTrue(optimizer._full_battery_breathe_probe_active)

        optimizer._desired_export_limit = lambda *args, **kwargs: 1.0
        state = self._breathe_probe_state(
            now_ts,
            pv_kw=1.9,
            solar_power_now_kw=5.3,
            load_kw=0.9,
            battery_power_sensor_kw=None,
            grid_import_power_kw=None,
            grid_export_power_kw=1.0,
            current_export_limit=1.0,
        )

        decision = optimizer._decide(state)

        self.assertFalse(bool(decision.trace_gates.get("pv_only_discharge_ok")))
        self.assertFalse(bool(decision.trace_gates.get("pv_surplus_breathe_probe_active")))
        self.assertEqual("unknown_or_mixed", decision.trace_values.get("export_value_gate_export_type"))
        self.assertTrue(bool(decision.trace_gates.get("export_value_gate_applies_to_export_type")))
        self.assertTrue(bool(decision.trace_gates.get("export_value_gate_vetoed")))
        self.assertTrue(bool(decision.trace_gates.get("actual_import_cost_guard_blocking")))
        self.assertEqual(0.0, decision.export_limit)
        self.assertFalse(optimizer._full_battery_breathe_probe_active)
        self.assertFalse(bool(decision.trace_gates.get("pv_surplus_breathe_probe_state_active")))

    def test_full_battery_breathe_probe_next_tick_discharge_triggers_hard_guard(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(daytime_topup_max_soc=100.0)
        self._record_import_topup(optimizer, import_kwh=1.0, import_price=0.16)
        optimizer._last_decision = self._previous_breathe_probe_decision(export_limit=0.5)
        self._seed_breathe_probe_state(optimizer, now_ts, export_limit=0.5)
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 0.5
        state = self._breathe_probe_state(
            now_ts,
            battery_power_sensor_kw=-0.2,
            current_export_limit=0.5,
        )

        decision = optimizer._decide(state)

        self.assertFalse(bool(decision.trace_gates.get("pv_surplus_breathe_probe_active")))
        self.assertFalse(bool(decision.trace_gates.get("pv_surplus_only_proven")))
        self.assertEqual("battery_backed", decision.trace_values.get("export_value_gate_export_type"))
        self.assertTrue(bool(decision.trace_gates.get("export_value_gate_applies_to_export_type")))
        self.assertTrue(bool(decision.trace_gates.get("actual_import_cost_guard_blocking")))
        self.assertEqual(0.0, decision.export_limit)
        self.assertFalse(optimizer._full_battery_breathe_probe_active)
        self.assertFalse(bool(decision.trace_gates.get("pv_surplus_breathe_probe_state_active")))

    def test_full_battery_breathe_probe_continuation_blocked_when_battery_discharge_unknown(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(daytime_topup_max_soc=100.0)
        optimizer._last_decision = self._previous_breathe_probe_decision(export_limit=1.0)
        self._seed_breathe_probe_state(optimizer, now_ts, export_limit=1.0)
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 0.0
        state = self._breathe_probe_state(
            now_ts,
            battery_power_sensor_kw=None,
            grid_import_power_kw=None,
            grid_export_power_kw=1.0,
            current_export_limit=1.0,
        )

        decision = optimizer._decide(state)

        self.assertFalse(bool(decision.trace_gates.get("pv_only_discharge_ok")))
        self.assertFalse(bool(decision.trace_gates.get("pv_surplus_breathe_probe_active")))
        self.assertFalse(bool(decision.trace_gates.get("pv_surplus_breathe_probe_continuation_active")))
        self.assertEqual("none", decision.trace_values.get("pv_surplus_initiation_source"))
        self.assertEqual(0.0, decision.export_limit)
        self.assertFalse(optimizer._full_battery_breathe_probe_active)
        self.assertFalse(bool(decision.trace_gates.get("pv_surplus_breathe_probe_state_active")))

    def test_full_battery_breathe_probe_continuation_requires_grid_export_evidence(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(daytime_topup_max_soc=100.0)
        optimizer._last_decision = self._previous_breathe_probe_decision(export_limit=1.0)
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 0.0
        state = self._breathe_probe_state(
            now_ts,
            current_export_limit=1.0,
            grid_export_power_kw=0.0,
        )

        decision = optimizer._decide(state)

        self.assertFalse(bool(decision.trace_gates.get("pv_surplus_breathe_probe_active")))
        self.assertFalse(bool(decision.trace_gates.get("pv_surplus_breathe_probe_continuation_active")))
        self.assertEqual("none", decision.trace_values.get("pv_surplus_initiation_source"))
        self.assertEqual(0.0, decision.export_limit)

    def test_full_battery_breathe_probe_continuation_blocked_on_zero_fit(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(daytime_topup_max_soc=100.0)
        optimizer._last_decision = self._previous_breathe_probe_decision(export_limit=1.0)
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 0.0
        state = self._breathe_probe_state(
            now_ts,
            feedin_price=0.0,
            feedin_price_cents=0.0,
            current_export_limit=1.0,
            grid_export_power_kw=1.0,
        )

        decision = optimizer._decide(state)

        self.assertFalse(bool(decision.trace_gates.get("pv_surplus_breathe_probe_active")))
        self.assertFalse(bool(decision.trace_gates.get("pv_surplus_breathe_probe_continuation_active")))
        self.assertEqual("no_live_export", decision.trace_values.get("export_value_gate_export_type"))
        self.assertEqual(0.0, decision.export_limit)

    def test_full_battery_breathe_probe_continuation_blocked_in_manual_force_mode(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(daytime_topup_max_soc=100.0)
        optimizer._last_decision = self._previous_breathe_probe_decision(export_limit=1.0)
        self._seed_breathe_probe_state(optimizer, now_ts, export_limit=1.0)
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 0.0
        cfg = optimizer.cfg
        state = self._breathe_probe_state(
            now_ts,
            sigenergy_mode=cfg.full_export_option,
            current_export_limit=1.0,
            grid_export_power_kw=1.0,
            current_ess_charge_limit=21.0,
            current_ess_discharge_limit=24.0,
        )

        decision = optimizer._decide(state)
        optimizer._freeze_decision_to_live_mode(state, decision, cfg.full_export_option)

        self.assertFalse(bool(decision.trace_gates.get("pv_surplus_breathe_probe_active")))
        self.assertFalse(bool(decision.trace_gates.get("pv_surplus_breathe_probe_continuation_active")))
        self.assertEqual("none", decision.trace_values.get("pv_surplus_initiation_source"))
        self.assertGreater(decision.export_limit, 0.0)
        self.assertFalse(optimizer._full_battery_breathe_probe_active)
        self.assertFalse(bool(decision.trace_gates.get("pv_surplus_breathe_probe_state_active")))

    def test_full_battery_breathe_probe_blocked_when_battery_discharge_unknown(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(daytime_topup_max_soc=100.0)
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 0.0
        state = self._breathe_probe_state(
            now_ts,
            battery_power_sensor_kw=None,
            grid_import_power_kw=None,
            grid_export_power_kw=None,
        )

        decision = optimizer._decide(state)

        self.assertFalse(bool(decision.trace_gates.get("pv_only_discharge_ok")))
        self.assertFalse(bool(decision.trace_gates.get("pv_surplus_breathe_probe_active")))
        self.assertEqual("none", decision.trace_values.get("pv_surplus_initiation_source"))
        self.assertLessEqual(decision.export_limit, 0.01)

    def test_full_battery_breathe_probe_blocked_below_topoff_target(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(daytime_topup_max_soc=100.0)
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 0.0
        state = self._breathe_probe_state(
            now_ts,
            battery_soc=99.0,
        )

        decision = optimizer._decide(state)

        self.assertFalse(bool(decision.trace_gates.get("topoff_target_met")))
        self.assertFalse(bool(decision.trace_gates.get("pv_surplus_breathe_probe_active")))
        self.assertLessEqual(decision.export_limit, 0.01)

    def test_full_battery_breathe_probe_blocked_on_zero_fit(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(daytime_topup_max_soc=100.0)
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 0.0
        state = self._breathe_probe_state(
            now_ts,
            feedin_price=0.0,
            feedin_price_cents=0.0,
        )

        decision = optimizer._decide(state)

        self.assertFalse(bool(decision.trace_gates.get("pv_surplus_breathe_probe_active")))
        self.assertEqual("no_live_export", decision.trace_values.get("export_value_gate_export_type"))
        self.assertLessEqual(decision.export_limit, 0.01)

    def test_full_battery_breathe_probe_blocked_at_night(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(daytime_topup_max_soc=100.0)
        optimizer._is_evening_or_night = lambda _now: True
        optimizer._desired_export_limit = lambda *args, **kwargs: 0.0
        state = self._breathe_probe_state(
            now_ts,
            sun_above_horizon=False,
        )

        decision = optimizer._decide(state)

        self.assertFalse(bool(decision.trace_gates.get("pv_surplus_breathe_probe_active")))
        self.assertEqual("no_live_export", decision.trace_values.get("export_value_gate_export_type"))
        self.assertLessEqual(decision.export_limit, 0.01)

    def test_full_battery_breathe_probe_blocked_in_manual_force_mode(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(daytime_topup_max_soc=100.0)
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 0.0
        cfg = optimizer.cfg
        state = self._breathe_probe_state(
            now_ts,
            sigenergy_mode=cfg.full_export_option,
            current_ess_charge_limit=21.0,
            current_ess_discharge_limit=24.0,
        )

        decision = optimizer._decide(state)
        optimizer._freeze_decision_to_live_mode(state, decision, cfg.full_export_option)

        self.assertFalse(bool(decision.trace_gates.get("pv_surplus_breathe_probe_active")))
        self.assertEqual("none", decision.trace_values.get("pv_surplus_initiation_source"))
        self.assertGreater(decision.export_limit, 0.0)

    def test_estimated_pv_surplus_below_import_floor_allowed_only_when_safe(self) -> None:
        from app.optimizer import DISCHARGE_MODES

        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(daytime_topup_max_soc=100.0)
        self._record_import_topup(optimizer, import_kwh=1.0, import_price=0.16)
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 0.0
        state = self._state(
            battery_soc=100.0,
            feedin_price=0.08,
            feedin_price_cents=8.0,
            pv_kw=1.0,
            solar_power_now_kw=3.0,
            load_kw=1.0,
            battery_power_sensor_kw=0.0,
            sun_above_horizon=True,
            next_sunrise_ts=now_ts + (10.0 * 3600),
            next_sunset_ts=now_ts + (6.0 * 3600),
            hours_to_sunrise=10.0,
            hours_to_sunset=6.0,
            current_ems_mode="Maximum Self Consumption",
        )

        decision = optimizer._decide(state)

        self.assertTrue(bool(decision.trace_gates.get("actual_import_cost_guard_active")))
        self.assertFalse(bool(decision.trace_gates.get("actual_import_cost_guard_blocking")))
        self.assertTrue(bool(decision.trace_gates.get("pv_surplus_estimated_init_active")))
        self.assertTrue(bool(decision.trace_gates.get("pv_surplus_export_allowed_below_import_floor")))
        self.assertGreater(decision.export_limit, 0.0)
        self.assertLessEqual(
            float(decision.export_limit),
            float(decision.trace_values.get("estimated_pv_surplus_kw", 0.0)) + 1e-6,
        )
        self.assertNotIn(decision.ems_mode, DISCHARGE_MODES)

    def test_estimated_pv_surplus_battery_discharge_triggers_hard_guard(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(daytime_topup_max_soc=100.0)
        self._record_import_topup(optimizer, import_kwh=1.0, import_price=0.16)
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 2.0
        state = self._state(
            battery_soc=100.0,
            feedin_price=0.08,
            feedin_price_cents=8.0,
            pv_kw=1.0,
            solar_power_now_kw=3.0,
            load_kw=1.0,
            battery_power_sensor_kw=-0.2,
            sun_above_horizon=True,
            next_sunrise_ts=now_ts + (10.0 * 3600),
            next_sunset_ts=now_ts + (6.0 * 3600),
            hours_to_sunrise=10.0,
            hours_to_sunset=6.0,
            current_ems_mode="Maximum Self Consumption",
        )

        decision = optimizer._decide(state)

        self.assertFalse(bool(decision.trace_gates.get("pv_surplus_estimated_init_active")))
        self.assertFalse(bool(decision.trace_gates.get("pv_surplus_only_proven")))
        self.assertTrue(bool(decision.trace_gates.get("actual_import_cost_guard_blocking")))
        self.assertEqual(0.0, decision.export_limit)

    def test_manual_force_export_exempt_from_hard_import_cost_guard(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            export_value_gate_enabled=False,
            export_value_gate_dry_run=False,
            export_value_gate_enforce=False,
        )
        self._record_import_topup(optimizer, import_kwh=1.0, import_price=0.16)
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 2.0
        cfg = optimizer.cfg
        state = self._state(
            sigenergy_mode=cfg.full_export_option,
            battery_soc=100.0,
            feedin_price=0.08,
            feedin_price_cents=8.0,
            pv_kw=0.0,
            load_kw=0.0,
            battery_power_sensor_kw=-0.2,
            sun_above_horizon=True,
            next_sunrise_ts=now_ts + (10.0 * 3600),
            next_sunset_ts=now_ts + (6.0 * 3600),
            hours_to_sunrise=10.0,
            hours_to_sunset=6.0,
            current_ems_mode="Maximum Self Consumption",
            current_export_limit=0.01,
            current_import_limit=0.01,
            current_pv_max_power_limit=25.0,
            current_ess_charge_limit=21.0,
            current_ess_discharge_limit=24.0,
        )

        decision = optimizer._decide(state)
        optimizer._freeze_decision_to_live_mode(state, decision, cfg.full_export_option)

        self.assertFalse(bool(decision.trace_gates.get("actual_import_cost_guard_active")))
        self.assertFalse(bool(decision.trace_gates.get("actual_import_cost_guard_blocking")))
        self.assertGreater(decision.export_limit, 0.0)
        self.assertIn("manual mode", str(decision.trace_values.get("actual_import_cost_guard_reason", "")).lower())

    def test_positive_untrusted_import_blocks_hard_guard_conservatively(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            export_value_gate_enabled=False,
            export_value_gate_dry_run=False,
            export_value_gate_enforce=False,
        )
        self._record_import_topup(
            optimizer,
            import_kwh=0.5,
            import_price=None,
            price_trusted=False,
        )
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 2.0
        state = self._state(
            battery_soc=100.0,
            feedin_price=0.08,
            feedin_price_cents=8.0,
            pv_kw=0.0,
            load_kw=0.0,
            battery_power_sensor_kw=-0.2,
            sun_above_horizon=True,
            next_sunrise_ts=now_ts + (10.0 * 3600),
            next_sunset_ts=now_ts + (6.0 * 3600),
            hours_to_sunrise=10.0,
            hours_to_sunset=6.0,
            current_ems_mode="Maximum Self Consumption",
        )

        decision = optimizer._decide(state)

        self.assertTrue(bool(decision.trace_gates.get("import_cost_floor_unknown")))
        self.assertTrue(bool(decision.trace_gates.get("actual_import_cost_guard_active")))
        self.assertEqual("battery_backed", decision.trace_values.get("export_value_gate_export_type"))
        self.assertTrue(bool(decision.trace_gates.get("actual_import_cost_guard_applies_to_export_type")))
        self.assertFalse(bool(decision.trace_gates.get("actual_import_cost_guard_bypassed_for_pv_surplus_only")))
        self.assertTrue(bool(decision.trace_gates.get("actual_import_cost_guard_blocking")))
        self.assertEqual(0.0, decision.export_limit)
        self.assertIn("unavailable or untrusted", decision.trace_values.get("actual_import_cost_guard_reason"))

    def test_untrusted_import_cost_blocks_unknown_or_mixed_export(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            export_value_gate_enabled=False,
            export_value_gate_dry_run=False,
            export_value_gate_enforce=False,
        )
        self._record_import_topup(
            optimizer,
            import_kwh=0.5,
            import_price=None,
            price_trusted=False,
        )
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 2.0
        state = self._state(
            battery_soc=100.0,
            feedin_price=0.08,
            feedin_price_cents=8.0,
            pv_kw=1.0,
            solar_power_now_kw=5.0,
            load_kw=0.5,
            battery_power_sensor_kw=None,
            grid_import_power_kw=None,
            grid_export_power_kw=None,
            sun_above_horizon=True,
            next_sunrise_ts=now_ts + (10.0 * 3600),
            next_sunset_ts=now_ts + (6.0 * 3600),
            hours_to_sunrise=10.0,
            hours_to_sunset=6.0,
            current_ems_mode="Maximum Self Consumption",
        )

        decision = optimizer._decide(state)

        self.assertTrue(bool(decision.trace_gates.get("import_cost_floor_unknown")))
        self.assertEqual("unknown_or_mixed", decision.trace_values.get("export_value_gate_export_type"))
        self.assertTrue(bool(decision.trace_gates.get("actual_import_cost_guard_applies_to_export_type")))
        self.assertFalse(bool(decision.trace_gates.get("actual_import_cost_guard_bypassed_for_pv_surplus_only")))
        self.assertTrue(bool(decision.trace_gates.get("actual_import_cost_guard_blocking")))
        self.assertEqual(0.0, decision.export_limit)
        self.assertIn("unavailable or untrusted", decision.trace_values.get("actual_import_cost_guard_reason"))

    def test_pv_surplus_carveout_does_not_apply_when_battery_discharge_is_measured(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            export_value_gate_enabled=True,
            export_value_gate_dry_run=True,
            export_value_gate_enforce=True,
            daytime_topup_max_soc=100.0,
        )
        self._record_import_topup(optimizer, import_kwh=1.0, import_price=0.16)
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 2.0
        state = self._state(
            battery_soc=100.0,
            feedin_price=0.08,
            feedin_price_cents=8.0,
            pv_kw=3.0,
            load_kw=0.0,
            battery_power_sensor_kw=-0.2,
            sun_above_horizon=True,
            next_sunrise_ts=now_ts + (10.0 * 3600),
            next_sunset_ts=now_ts + (6.0 * 3600),
            hours_to_sunrise=10.0,
            hours_to_sunset=6.0,
            current_ems_mode="Maximum Self Consumption",
        )

        decision = optimizer._decide(state)

        self.assertFalse(bool(decision.trace_gates.get("pv_surplus_only_proven")))
        self.assertFalse(bool(decision.trace_gates.get("export_value_gate_pv_surplus_carveout_active")))
        self.assertFalse(bool(decision.trace_gates.get("pv_surplus_export_allowed_below_import_floor")))
        self.assertEqual("battery_backed", decision.trace_values.get("export_value_gate_export_type"))
        self.assertTrue(bool(decision.trace_gates.get("export_value_gate_applies_to_export_type")))
        self.assertTrue(bool(decision.trace_gates.get("export_value_gate_vetoed")))
        self.assertEqual(0.0, decision.export_limit)

    def test_manual_mode_still_pauses_optimizer_writes_when_enforcement_enabled(self) -> None:
        cfg = Settings(export_value_gate_enabled=True, export_value_gate_enforce=True)
        ha = _RecordingHA()
        optimizer = SigEnergyOptimizer(ha, cfg)
        self._optimizers.append(optimizer)
        state = self._state(
            sigenergy_mode=cfg.manual_option,
            current_ems_mode="Maximum Self Consumption",
            current_export_limit=0.01,
            current_import_limit=0.01,
            current_pv_max_power_limit=25.0,
            current_ess_charge_limit=21.0,
            current_ess_discharge_limit=24.0,
        )
        decision = optimizer._decide(state)
        optimizer._freeze_decision_to_live_mode(state, decision, cfg.manual_option)

        asyncio.run(optimizer._apply(state, decision))

        self.assertEqual(ha.calls, [])
        self.assertIn("optimizer writes paused", decision.outcome_reason)

    def test_hidden_pv_diagnostics_populate_when_estimated_exceeds_measured(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            export_value_gate_enabled=True,
            export_value_gate_dry_run=True,
            export_value_gate_enforce=True,
        )
        optimizer._is_evening_or_night = lambda _now: False
        state = self._state(
            battery_soc=100.0,
            feedin_price=0.04,
            feedin_price_cents=4.0,
            pv_kw=1.4,
            solar_power_now_kw=3.6,
            load_kw=1.0,
            sun_above_horizon=True,
            current_pv_max_power_limit=3.0,
            next_sunrise_ts=now_ts + (10.0 * 3600),
            next_sunset_ts=now_ts + (6.0 * 3600),
            hours_to_sunrise=10.0,
            hours_to_sunset=6.0,
        )

        decision = optimizer._decide(state)

        self.assertGreater(float(decision.trace_values.get("estimated_pv_surplus_kw", 0.0)), float(decision.trace_values.get("measured_pv_surplus_kw", 0.0)))
        self.assertGreater(float(decision.trace_values.get("hidden_pv_surplus_kw", 0.0)), 0.0)
        self.assertTrue(bool(decision.trace_gates.get("hidden_pv_possible")))
        self.assertIn("diagnostic", str(decision.trace_values.get("curtailment_diagnostic_reason", "")).lower())

    def test_hidden_pv_possible_does_not_change_live_export_limit(self) -> None:
        now_ts = datetime.now().timestamp()
        baseline_optimizer = self._optimizer(
            export_value_gate_enabled=False,
            export_value_gate_dry_run=False,
            export_value_gate_enforce=False,
        )
        baseline_optimizer._is_evening_or_night = lambda _now: False
        diag_optimizer = self._optimizer(
            export_value_gate_enabled=True,
            export_value_gate_dry_run=True,
            export_value_gate_enforce=False,
        )
        diag_optimizer._is_evening_or_night = lambda _now: False
        state = self._state(
            battery_soc=100.0,
            feedin_price=0.04,
            feedin_price_cents=4.0,
            pv_kw=1.4,
            solar_power_now_kw=3.6,
            load_kw=1.0,
            sun_above_horizon=True,
            current_pv_max_power_limit=3.0,
            next_sunrise_ts=now_ts + (10.0 * 3600),
            next_sunset_ts=now_ts + (6.0 * 3600),
            hours_to_sunrise=10.0,
            hours_to_sunset=6.0,
        )

        baseline = baseline_optimizer._decide(state)
        diag = diag_optimizer._decide(state)

        self.assertTrue(bool(diag.trace_gates.get("hidden_pv_possible")))
        self.assertEqual(baseline.export_limit, diag.export_limit)
        self.assertEqual(baseline.ems_mode, diag.ems_mode)
        self.assertEqual(baseline.import_limit, diag.import_limit)

    def test_hidden_pv_diagnostics_do_not_convert_export_type_to_pv_surplus_only(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            export_value_gate_enabled=True,
            export_value_gate_dry_run=True,
            export_value_gate_enforce=True,
        )
        optimizer._is_evening_or_night = lambda _now: False
        state = self._state(
            battery_soc=100.0,
            feedin_price=0.08,
            feedin_price_cents=8.0,
            pv_kw=1.4,
            solar_power_now_kw=3.6,
            load_kw=1.0,
            sun_above_horizon=True,
            current_pv_max_power_limit=3.0,
            next_sunrise_ts=now_ts + (10.0 * 3600),
            next_sunset_ts=now_ts + (6.0 * 3600),
            hours_to_sunrise=10.0,
            hours_to_sunset=6.0,
        )

        decision = optimizer._decide(state)

        self.assertTrue(bool(decision.trace_gates.get("hidden_pv_possible")))
        self.assertNotEqual("pv_surplus_only", decision.trace_values.get("export_value_gate_export_type"))
        self.assertFalse(bool(decision.trace_gates.get("export_value_gate_pv_surplus_initiated_active")))

    def test_pv_surplus_initiation_still_requires_measured_surplus_not_estimated(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            export_value_gate_enabled=True,
            export_value_gate_dry_run=True,
            export_value_gate_enforce=True,
        )
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 0.0
        state = self._state(
            battery_soc=100.0,
            feedin_price=0.04,
            feedin_price_cents=4.0,
            pv_kw=1.0,
            solar_power_now_kw=3.5,
            load_kw=0.9,
            sun_above_horizon=True,
            current_pv_max_power_limit=3.0,
            next_sunrise_ts=now_ts + (10.0 * 3600),
            next_sunset_ts=now_ts + (6.0 * 3600),
            hours_to_sunrise=10.0,
            hours_to_sunset=6.0,
        )

        decision = optimizer._decide(state)

        self.assertGreater(float(decision.trace_values.get("estimated_pv_surplus_kw", 0.0)), float(decision.trace_values.get("measured_pv_surplus_kw", 0.0)))
        self.assertFalse(bool(decision.trace_gates.get("export_value_gate_pv_surplus_initiated_active")))
        self.assertEqual("no_live_export", decision.trace_values.get("export_value_gate_export_type"))
        self.assertLessEqual(float(decision.export_limit), 0.01)


if __name__ == "__main__":
    unittest.main()
