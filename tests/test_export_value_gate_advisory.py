from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from datetime import datetime

from app.config import Settings
from app.models import (
    Decision,
    HVACObservedValue,
    HVACSolarInputContext,
    SolarState,
)
from app.optimizer import (
    DISCHARGE_MODES,
    MODE_CMD_CHARGE_GRID,
    MODE_CMD_CHARGE_PV,
    MODE_CMD_DISCHARGE_PV,
    MODE_MAX_SELF,
    SigEnergyOptimizer,
)


class _DummyHA:
    pass


class _RecordingHA:
    def __init__(
        self,
        state_values: dict[str, object] | None = None,
        *,
        failed_select_values: set[str] | None = None,
        settle_numbers: bool = True,
        settle_selects: bool = True,
    ) -> None:
        self.calls: list[tuple[str, str, object]] = []
        self.state_values = dict(state_values or {})
        self.failed_select_values = set(failed_select_values or set())
        self.settle_numbers = settle_numbers
        self.settle_selects = settle_selects

    async def select_option(self, entity_id: str, value: str) -> bool:
        self.calls.append(("select_option", entity_id, value))
        if value in self.failed_select_values:
            return False
        if self.settle_selects:
            self.state_values[entity_id] = value
        return True

    async def set_number(self, entity_id: str, value: float) -> bool:
        self.calls.append(("set_number", entity_id, value))
        if self.settle_numbers:
            self.state_values[entity_id] = value
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
        return self.state_values.get(entity_id, default)


class _BulkStateHA:
    def __init__(self, states: dict[str, dict[str, object]]) -> None:
        self.states = states

    async def bulk_states(self, entity_ids: list[str]) -> dict[str, dict[str, object]]:
        return {
            entity_id: self.states[entity_id]
            for entity_id in entity_ids
            if entity_id in self.states
        }


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

    def _optimizer(
        self,
        ha: object | None = None,
        **overrides: object,
    ) -> SigEnergyOptimizer:
        values: dict[str, object] = {
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
        optimizer = SigEnergyOptimizer(ha or _DummyHA(), cfg)
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

    def _qualifying_full_battery_msc_state(
        self,
        optimizer: SigEnergyOptimizer,
        now_ts: float,
        **overrides: float | bool | str | None,
    ) -> SolarState:
        values: dict[str, float | bool | str | None] = {
            "sigenergy_mode": optimizer.cfg.automated_option,
            "sigenergy_mode_observed": True,
            "battery_soc": 100.0,
            "battery_capacity_kwh": 30.0,
            "available_discharge_energy_kwh": 30.0,
            "feedin_price": 0.08,
            "feedin_price_cents": 8.0,
            "pv_kw": 2.4,
            "solar_power_now_kw": 2.4,
            "load_kw": 1.0,
            "battery_power_sensor_kw": -0.01,
            "grid_import_power_kw": 0.0,
            "grid_export_power_kw": 0.0,
            "forecast_tomorrow_kwh": 73.0,
            "ess_max_discharge_kw": 40.0,
            "price_is_actual": True,
            "sun_above_horizon": True,
            "next_sunrise_ts": now_ts + (10.0 * 3600),
            "next_sunset_ts": now_ts + (6.0 * 3600),
            "hours_to_sunrise": 10.0,
            "hours_to_sunset": 6.0,
            "current_ems_mode": MODE_MAX_SELF,
            "ems_mode_observed": True,
            "current_export_limit": 0.01,
            "current_import_limit": 0.0,
            "current_pv_max_power_limit": 25.0,
        }
        values.update(overrides)
        return self._state(**values)

    def _qualifying_solar_bypass_state(
        self,
        optimizer: SigEnergyOptimizer,
        now_ts: float,
        **overrides: float | bool | str | None,
    ) -> SolarState:
        values: dict[str, float | bool | str | None] = {
            "sigenergy_mode": optimizer.cfg.automated_option,
            "sigenergy_mode_observed": True,
            "battery_soc": 72.0,
            "battery_capacity_kwh": 30.0,
            "available_discharge_energy_kwh": 21.6,
            "current_price": 0.30,
            "current_price_cents": 30.0,
            "feedin_price": 0.10,
            "feedin_price_cents": 10.0,
            "pv_kw": 6.0,
            "solar_power_now_kw": 6.0,
            "load_kw": 1.0,
            "battery_power_sensor_kw": 0.0,
            "grid_import_power_kw": 0.0,
            "grid_export_power_kw": 0.0,
            "forecast_remaining_kwh": 70.0,
            "forecast_tomorrow_kwh": 73.0,
            "ess_max_charge_kw": 25.0,
            "ess_max_discharge_kw": 25.0,
            "price_is_actual": True,
            "sun_above_horizon": True,
            "next_sunrise_ts": now_ts + (10.0 * 3600),
            "next_sunset_ts": now_ts + (6.0 * 3600),
            "hours_to_sunrise": 10.0,
            "hours_to_sunset": 6.0,
            "current_ems_mode": MODE_MAX_SELF,
            "ems_mode_observed": True,
            "current_export_limit": 0.01,
            "current_import_limit": 0.0,
            "current_pv_max_power_limit": 25.0,
        }
        values.update(overrides)
        return self._state(**values)

    def _assert_legacy_discovery_inactive(self, decision: Decision) -> None:
        for gate in (
            "pv_surplus_estimated_init_active",
            "pv_surplus_breathe_probe_active",
            "pv_surplus_breathe_probe_continuation_active",
            "pv_only_discovery_active",
            "pv_only_discovery_continuation_active",
            "pv_only_discovery_state_active",
            "pv_only_discovery_state_fresh",
            "pv_surplus_breathe_probe_state_active",
            "pv_surplus_breathe_probe_state_fresh",
            "pv_surplus_breathe_probe_state_from_carveout",
            "pv_surplus_discovery_state_from_controller",
        ):
            self.assertFalse(bool(decision.trace_gates.get(gate)), gate)
        self.assertEqual("none", decision.trace_values.get("pv_only_discovery_source"))
        self.assertEqual(0.0, decision.trace_values.get("pv_only_discovery_cap_kw"))
        self.assertEqual(0.0, decision.trace_values.get("pv_surplus_probe_export_cap_kw"))
        self.assertIn(
            "diagnostic-only",
            str(decision.trace_values.get("pv_only_discovery_reason", "")),
        )

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

    def test_enforce_flag_remains_advisory_when_value_gate_would_block(self) -> None:
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
        for field in (
            "export_limit",
            "import_limit",
            "pv_max_power_limit",
            "ess_charge_limit",
            "ess_discharge_limit",
            "ems_mode",
        ):
            self.assertEqual(getattr(baseline, field), getattr(enforced, field), field)
        self.assertTrue(bool(enforced.trace_gates.get("export_value_gate_enforce")))
        self.assertFalse(bool(enforced.trace_gates.get("export_value_gate_enforcement_active")))
        self.assertFalse(bool(enforced.trace_gates.get("export_value_gate_vetoed")))
        self.assertEqual("Advisory only", enforced.trace_values.get("export_value_gate_mode"))
        self.assertIn("would block", enforced.export_value_gate_reason.lower())

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

    def test_qualifying_full_battery_msc_sets_high_export_ceiling_directly(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(daytime_topup_max_soc=100.0)
        optimizer._is_evening_or_night = lambda _now: False
        state = self._qualifying_full_battery_msc_state(optimizer, now_ts)

        decision = optimizer._decide(state)

        self.assertTrue(bool(decision.trace_gates.get("pv_only_msc_high_ceiling_active")))
        self.assertEqual("msc_full_battery_high_ceiling", decision.trace_values.get("pv_surplus_initiation_source"))
        self.assertEqual(optimizer.cfg.export_limit_high, decision.export_limit)
        self.assertTrue(decision.requires_verified_msc_before_export)
        self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
        self.assertNotIn(decision.ems_mode, DISCHARGE_MODES)
        self.assertFalse(bool(decision.trace_gates.get("pv_surplus_breathe_probe_continuation_active")))
        self.assertIn("ceiling", decision.export_reason.lower())

    def test_full_battery_msc_high_ceiling_stays_closed_at_evening_or_night(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            daytime_topup_max_soc=100.0,
            sunrise_reserve_soc=100.0,
        )
        state = self._qualifying_full_battery_msc_state(
            optimizer,
            now_ts,
            feedin_price=0.01,
            feedin_price_cents=1.0,
            next_sunset_ts=now_ts + (0.5 * 3600),
            hours_to_sunset=0.5,
        )

        decision = optimizer._decide(state)

        self.assertTrue(bool(decision.trace_gates.get("is_evening_or_night")))
        self.assertTrue(bool(decision.trace_gates.get("sigenergy_mode_observed")))
        self.assertTrue(bool(decision.trace_gates.get("ems_mode_observed")))
        self.assertTrue(bool(decision.trace_gates.get("topoff_target_met")))
        self.assertTrue(bool(decision.trace_gates.get("pv_only_discharge_ok")))
        self.assertTrue(bool(decision.trace_gates.get("pv_only_ems_safe")))
        self.assertFalse(bool(decision.trace_gates.get("pv_only_msc_transition_ready")))
        self.assertFalse(bool(decision.trace_gates.get("pv_only_msc_stage1_active")))
        self.assertFalse(bool(decision.trace_gates.get("pv_only_msc_high_ceiling_active")))
        self.assertFalse(bool(decision.trace_gates.get("export_value_gate_pv_surplus_initiated_active")))
        self.assertEqual("none", decision.trace_values.get("pv_surplus_initiation_source"))
        self.assertEqual("no_live_export", decision.trace_values.get("export_value_gate_export_type"))
        self.assertEqual(0.0, decision.export_limit)
        self.assertNotEqual(optimizer.cfg.export_limit_high, decision.export_limit)
        self.assertFalse(decision.requires_verified_msc_before_export)
        self._assert_legacy_discovery_inactive(decision)

    def test_msc_high_ceiling_classifies_pv_only_above_measured_surplus(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(daytime_topup_max_soc=100.0)
        optimizer._is_evening_or_night = lambda _now: False
        state = self._qualifying_full_battery_msc_state(
            optimizer,
            now_ts,
            pv_kw=2.4,
            solar_power_now_kw=2.4,
            load_kw=1.0,
        )

        decision = optimizer._decide(state)

        measured_surplus = float(decision.trace_values.get("measured_pv_surplus_kw", 0.0))
        self.assertEqual(1.4, measured_surplus)
        self.assertEqual(25.0, decision.export_limit)
        self.assertGreater(decision.export_limit, measured_surplus)
        self.assertEqual("pv_surplus_only", decision.trace_values.get("export_value_gate_export_type"))
        self.assertFalse(bool(decision.trace_gates.get("export_value_gate_applies_to_export_type")))
        self.assertIn(
            "maximum self consumption export ceiling",
            str(decision.trace_values.get("export_classification_reason", "")).lower(),
        )

    def test_measured_pv_only_transition_above_low_cap_keeps_safe_classification(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            daytime_topup_max_soc=100.0,
            export_limit_low=5.0,
            export_limit_high=25.0,
        )
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 6.0
        state = self._qualifying_full_battery_msc_state(
            optimizer,
            now_ts,
            current_ems_mode=MODE_CMD_CHARGE_PV,
            sigenergy_mode_observed=False,
            pv_kw=9.0,
            solar_power_now_kw=9.0,
            load_kw=1.0,
        )

        decision = optimizer._decide(state)

        self.assertFalse(bool(decision.trace_gates.get("pv_only_msc_high_ceiling_active")))
        self.assertGreater(decision.export_limit, optimizer.cfg.export_limit_low)
        self.assertEqual(6.0, decision.export_limit)
        self.assertEqual("pv_surplus_only", decision.trace_values.get("export_value_gate_export_type"))
        self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
        self.assertNotIn(decision.ems_mode, DISCHARGE_MODES)

    def test_full_battery_msc_high_ceiling_requires_fit_at_least_one_cent(self) -> None:
        now_ts = datetime.now().timestamp()
        cases = (
            (0.0, 0.0, False),
            (0.001, 0.1, False),
            (0.005, 0.5, False),
            (0.0099, 0.99, False),
            (0.01, 1.0, True),
        )

        for feedin_price, feedin_price_cents, eligible in cases:
            with self.subTest(feedin_price_cents=feedin_price_cents):
                optimizer = self._optimizer(daytime_topup_max_soc=100.0)
                optimizer._is_evening_or_night = lambda _now: False
                state = self._qualifying_full_battery_msc_state(
                    optimizer,
                    now_ts,
                    feedin_price=feedin_price,
                    feedin_price_cents=feedin_price_cents,
                )

                decision = optimizer._decide(state)

                self.assertEqual(
                    eligible,
                    bool(decision.trace_gates.get("pv_only_msc_high_ceiling_active")),
                )
                if eligible:
                    self.assertEqual(optimizer.cfg.export_limit_high, decision.export_limit)
                    self.assertEqual("pv_surplus_only", decision.trace_values.get("export_value_gate_export_type"))
                else:
                    self.assertLessEqual(decision.export_limit, 0.01)
                    self.assertEqual("no_live_export", decision.trace_values.get("export_value_gate_export_type"))

    def test_full_battery_msc_high_ceiling_respects_fractional_grid_export_entity_cap(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(daytime_topup_max_soc=100.0, export_limit_high=25.0)
        optimizer._is_evening_or_night = lambda _now: False
        state = self._qualifying_full_battery_msc_state(
            optimizer,
            now_ts,
            ess_max_discharge_kw=5.0,
            grid_export_limit_entity_max_kw=18.069,
        )

        decision = optimizer._decide(state)

        self.assertTrue(bool(decision.trace_gates.get("pv_only_msc_high_ceiling_active")))
        self.assertEqual(18.06, decision.export_limit)
        self.assertLessEqual(decision.export_limit, 18.069)
        self.assertEqual(18.069, decision.trace_values.get("pv_only_msc_authoritative_cap_kw"))
        self.assertEqual(18.06, decision.trace_values.get("pv_only_msc_high_ceiling_kw"))

    def test_material_battery_discharge_removes_pv_only_high_without_blocking_independent_export(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(daytime_topup_max_soc=100.0)
        optimizer._is_evening_or_night = lambda _now: False
        state = self._qualifying_full_battery_msc_state(
            optimizer,
            now_ts,
            battery_power_sensor_kw=-0.2,
        )

        decision = optimizer._decide(state)

        self.assertFalse(bool(decision.trace_gates.get("pv_only_discharge_ok")))
        self.assertFalse(bool(decision.trace_gates.get("pv_only_msc_high_ceiling_active")))
        self.assertFalse(bool(decision.trace_gates.get("pv_only_msc_stage1_active")))
        self.assertEqual("battery_backed", decision.trace_values.get("export_value_gate_export_type"))
        self.assertGreater(decision.export_limit, 0.01)
        self.assertIn(decision.ems_mode, DISCHARGE_MODES)
        self.assertFalse(decision.requires_verified_msc_before_export)

    def test_unknown_battery_flow_removes_pv_only_high_and_uses_ordinary_policy(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(daytime_topup_max_soc=100.0)
        optimizer._is_evening_or_night = lambda _now: False
        state = self._qualifying_full_battery_msc_state(
            optimizer,
            now_ts,
            battery_power_sensor_kw=None,
            grid_import_power_kw=None,
            grid_export_power_kw=None,
        )

        decision = optimizer._decide(state)

        self.assertFalse(bool(decision.trace_gates.get("pv_only_discharge_ok")))
        self.assertEqual("unknown", decision.trace_values.get("battery_flow_source_for_pv_only"))
        self.assertFalse(bool(decision.trace_gates.get("pv_only_msc_high_ceiling_active")))
        self.assertFalse(bool(decision.trace_gates.get("pv_only_msc_stage1_active")))
        self.assertEqual("unknown_or_mixed", decision.trace_values.get("export_value_gate_export_type"))
        self.assertTrue(bool(decision.trace_gates.get("export_value_gate_applies_to_export_type")))
        self.assertGreater(decision.export_limit, 0.01)
        self.assertFalse(decision.requires_verified_msc_before_export)

    def test_nonfinite_battery_flow_is_unknown_and_cannot_qualify_msc_transition(self) -> None:
        now_ts = datetime.now().timestamp()
        cases = (
            ("direct_nan", {"battery_power_sensor_kw": float("nan")}),
            ("direct_pos_inf", {"battery_power_sensor_kw": float("inf")}),
            ("direct_neg_inf", {"battery_power_sensor_kw": float("-inf")}),
            (
                "derived_import_nan",
                {"battery_power_sensor_kw": None, "grid_import_power_kw": float("nan")},
            ),
            (
                "derived_export_pos_inf",
                {"battery_power_sensor_kw": None, "grid_export_power_kw": float("inf")},
            ),
            (
                "derived_import_neg_inf",
                {"battery_power_sensor_kw": None, "grid_import_power_kw": float("-inf")},
            ),
        )

        for name, overrides in cases:
            with self.subTest(name=name):
                optimizer = self._optimizer(daytime_topup_max_soc=100.0)
                optimizer._is_evening_or_night = lambda _now: False
                optimizer._desired_export_limit = lambda *args, **kwargs: 0.0
                state = self._qualifying_full_battery_msc_state(
                    optimizer,
                    now_ts,
                    **overrides,
                )

                decision = optimizer._decide(state)

                self.assertEqual("unknown", decision.trace_values.get("battery_flow_source_for_pv_only"))
                self.assertFalse(bool(decision.trace_gates.get("pv_only_discharge_ok")))
                self.assertFalse(bool(decision.trace_gates.get("pv_only_msc_transition_ready")))
                self.assertFalse(bool(decision.trace_gates.get("pv_only_msc_stage1_active")))
                self.assertFalse(bool(decision.trace_gates.get("pv_only_msc_high_ceiling_active")))
                self.assertLessEqual(decision.export_limit, 0.01)
                self._assert_legacy_discovery_inactive(decision)

    def test_live_pv_only_flow_requires_fresh_available_evidence(self) -> None:
        optimizer = self._optimizer()
        state = self._state(
            battery_power_sensor_kw=None,
            grid_import_power_kw=0.0,
            grid_export_power_kw=0.0,
            pv_kw=0.0,
            load_kw=0.0,
        )

        cases = (
            (
                "stale_direct",
                HVACSolarInputContext(
                    battery_power=HVACObservedValue(
                        value=0.0,
                        available=True,
                        fresh=False,
                    ),
                    live_snapshot=True,
                ),
                None,
                "unknown",
            ),
            (
                "synthetic_zero_pv_load",
                HVACSolarInputContext(
                    grid_import_power=HVACObservedValue(
                        value=0.0,
                        available=True,
                        fresh=True,
                    ),
                    grid_export_power=HVACObservedValue(
                        value=0.0,
                        available=True,
                        fresh=True,
                    ),
                    live_snapshot=True,
                ),
                None,
                "unknown",
            ),
            (
                "fresh_derived",
                HVACSolarInputContext(
                    pv_power=HVACObservedValue(value=6.0, available=True, fresh=True),
                    load_power=HVACObservedValue(value=1.0, available=True, fresh=True),
                    grid_import_power=HVACObservedValue(
                        value=0.0,
                        available=True,
                        fresh=True,
                    ),
                    grid_export_power=HVACObservedValue(
                        value=5.0,
                        available=True,
                        fresh=True,
                    ),
                    live_snapshot=True,
                ),
                0.0,
                "measured_grid_flow",
            ),
        )

        for name, inputs, expected_discharge, expected_source in cases:
            with self.subTest(name=name):
                state.hvac_solar_inputs = inputs
                discharge, source = optimizer._battery_discharge_kw_for_pv_only_check(
                    state
                )
                self.assertEqual(expected_discharge, discharge)
                self.assertEqual(expected_source, source)

    def test_unavailable_live_pv_and_load_cannot_open_morning_high_ceiling(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            battery_full_safeguard_enabled=False,
            morning_slow_charge_rate_kw=3.7,
        )
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._morning_slow_charge_active = lambda *args, **kwargs: True
        state = self._qualifying_full_battery_msc_state(
            optimizer,
            now_ts,
            pv_kw=0.0,
            solar_power_now_kw=7.0,
            load_kw=0.0,
            battery_power_sensor_kw=None,
            grid_import_power_kw=0.0,
            grid_export_power_kw=0.0,
        )
        state.hvac_solar_inputs = HVACSolarInputContext(
            grid_import_power=HVACObservedValue(
                value=0.0,
                available=True,
                fresh=True,
            ),
            grid_export_power=HVACObservedValue(
                value=0.0,
                available=True,
                fresh=True,
            ),
            live_snapshot=True,
        )

        decision = optimizer._decide(state)

        self.assertTrue(bool(decision.trace_gates.get("pv_only_branch_high_ceiling_requested")))
        self.assertTrue(bool(decision.trace_gates.get("pv_only_branch_battery_safety_blocked")))
        self.assertEqual("unknown", decision.trace_values.get("battery_flow_source_for_pv_only"))
        self.assertNotEqual(optimizer.cfg.export_limit_high, decision.export_limit)
        self.assertFalse(decision.requires_verified_msc_before_export)

    def test_full_battery_msc_high_ceiling_requires_fixed_100_percent_topoff(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(daytime_topup_max_soc=50.0)
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 0.0
        state = self._qualifying_full_battery_msc_state(
            optimizer,
            now_ts,
            battery_soc=99.9,
        )

        decision = optimizer._decide(state)

        self.assertEqual(100.0, decision.trace_values.get("topoff_target_soc"))
        self.assertFalse(bool(decision.trace_gates.get("topoff_target_met")))
        self.assertFalse(bool(decision.trace_gates.get("pv_only_msc_high_ceiling_active")))
        self.assertLessEqual(decision.export_limit, 0.01)

    def test_nonfinite_soc_cannot_meet_full_battery_topoff(self) -> None:
        now_ts = datetime.now().timestamp()
        for battery_soc in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(battery_soc=battery_soc):
                optimizer = self._optimizer(daytime_topup_max_soc=100.0)
                optimizer._is_evening_or_night = lambda _now: False
                optimizer._desired_export_limit = lambda *args, **kwargs: 0.0
                state = self._qualifying_full_battery_msc_state(
                    optimizer,
                    now_ts,
                    battery_soc=battery_soc,
                )

                decision = optimizer._decide(state)

                self.assertFalse(bool(decision.trace_gates.get("topoff_target_met")))
                self.assertFalse(bool(decision.trace_gates.get("pv_only_msc_transition_ready")))
                self.assertFalse(bool(decision.trace_gates.get("pv_only_msc_high_ceiling_active")))
                self.assertLessEqual(decision.export_limit, 0.01)

    def test_discharge_ems_context_cannot_masquerade_as_pv_only_msc_ceiling(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            daytime_topup_max_soc=100.0,
            export_value_gate_enabled=True,
            export_value_gate_dry_run=True,
            export_value_gate_enforce=True,
        )
        self._record_import_topup(optimizer, import_kwh=1.0, import_price=0.16)
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 2.0
        state = self._qualifying_full_battery_msc_state(
            optimizer,
            now_ts,
            current_ems_mode=MODE_CMD_DISCHARGE_PV,
        )

        decision = optimizer._decide(state)

        self.assertFalse(bool(decision.trace_gates.get("pv_only_ems_safe")))
        self.assertFalse(bool(decision.trace_gates.get("pv_only_msc_high_ceiling_active")))
        self.assertTrue(bool(decision.trace_gates.get("pv_only_msc_stage1_active")))
        self.assertEqual("no_live_export", decision.trace_values.get("export_value_gate_export_type"))
        self.assertFalse(bool(decision.trace_gates.get("actual_import_cost_guard_applies_to_export_type")))
        self.assertFalse(bool(decision.trace_gates.get("actual_import_cost_guard_blocking")))
        self.assertFalse(bool(decision.trace_gates.get("actual_import_cost_guard_bypassed_for_pv_surplus_only")))
        self.assertEqual(0.0, decision.export_limit)
        self.assertEqual(MODE_MAX_SELF, decision.ems_mode)

    def test_unknown_ems_context_fails_closed_for_pv_only_export(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(daytime_topup_max_soc=100.0)
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 0.0
        state = self._qualifying_full_battery_msc_state(
            optimizer,
            now_ts,
            current_ems_mode="",
            ems_mode_observed=False,
        )

        decision = optimizer._decide(state)

        self.assertFalse(bool(decision.trace_gates.get("pv_only_ems_safe")))
        self.assertFalse(bool(decision.trace_gates.get("pv_only_msc_high_ceiling_active")))
        self.assertTrue(bool(decision.trace_gates.get("pv_only_msc_stage1_active")))
        self.assertFalse(bool(decision.trace_gates.get("export_value_gate_pv_surplus_initiated_active")))
        self.assertEqual("no_live_export", decision.trace_values.get("export_value_gate_export_type"))
        self.assertLessEqual(decision.export_limit, 0.01)
        self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
        self._assert_legacy_discovery_inactive(decision)

    def test_full_battery_msc_high_ceiling_requires_explicit_automated_mode(self) -> None:
        now_ts = datetime.now().timestamp()

        for mode_attr in (
            "manual_option",
            "full_export_option",
            "full_import_option",
            "full_import_pv_option",
            "block_flow_option",
        ):
            with self.subTest(mode_attr=mode_attr):
                optimizer = self._optimizer(daytime_topup_max_soc=100.0)
                optimizer._is_evening_or_night = lambda _now: False
                optimizer._desired_export_limit = lambda *args, **kwargs: 0.0
                mode_label = str(getattr(optimizer.cfg, mode_attr))
                state = self._qualifying_full_battery_msc_state(
                    optimizer,
                    now_ts,
                    sigenergy_mode=mode_label,
                )

                decision = optimizer._decide(state)

                self.assertFalse(bool(decision.trace_gates.get("pv_only_msc_high_ceiling_active")))
                optimizer._freeze_decision_to_live_mode(state, decision, mode_label)
                self.assertEqual(state.current_export_limit, decision.export_limit)
                self.assertNotEqual(optimizer.cfg.export_limit_high, decision.export_limit)

    def test_value_and_import_cost_gates_bypass_safe_msc_ceiling_without_surplus_clamp(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            daytime_topup_max_soc=100.0,
            export_value_gate_enabled=True,
            export_value_gate_dry_run=True,
            export_value_gate_enforce=True,
        )
        self._record_import_topup(optimizer, import_kwh=1.0, import_price=0.16)
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 0.0
        state = self._qualifying_full_battery_msc_state(optimizer, now_ts)

        decision = optimizer._decide(state)

        measured_surplus = float(decision.trace_values.get("measured_pv_surplus_kw", 0.0))
        self.assertEqual(optimizer.cfg.export_limit_high, decision.export_limit)
        self.assertGreater(decision.export_limit, measured_surplus)
        self.assertEqual("pv_surplus_only", decision.trace_values.get("export_value_gate_export_type"))
        self.assertTrue(decision.export_value_gate_would_allow)
        self.assertFalse(decision.export_value_gate_would_block)
        self.assertFalse(bool(decision.trace_gates.get("export_value_gate_vetoed")))
        self.assertFalse(bool(decision.trace_gates.get("export_value_gate_pv_surplus_carveout_active")))
        self.assertTrue(bool(decision.trace_gates.get("export_value_gate_bypassed_for_pv_surplus_only")))
        self.assertTrue(bool(decision.trace_gates.get("actual_import_cost_guard_active")))
        self.assertFalse(bool(decision.trace_gates.get("actual_import_cost_guard_blocking")))
        self.assertTrue(bool(decision.trace_gates.get("actual_import_cost_guard_bypassed_for_pv_surplus_only")))

    def test_stage1_closes_export_and_commands_msc_then_stage2_opens_directly(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(daytime_topup_max_soc=100.0)
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._last_decision = Decision(
            export_limit=1.0,
            trace_gates={"pv_surplus_breathe_probe_active": True},
            trace_values={"pv_surplus_initiation_source": "estimated"},
        )
        stage1_state = self._qualifying_full_battery_msc_state(
            optimizer,
            now_ts,
            current_ems_mode=MODE_CMD_CHARGE_PV,
            ems_mode_observed=True,
        )

        stage1 = optimizer._decide(stage1_state)

        self.assertGreater(
            float(stage1.trace_values.get("desired_export_limit_pre_value_gate", 0.0)),
            0.01,
        )
        self.assertTrue(bool(stage1.trace_gates.get("pv_only_msc_transition_ready")))
        self.assertTrue(bool(stage1.trace_gates.get("pv_only_msc_stage1_active")))
        self.assertFalse(bool(stage1.trace_gates.get("pv_only_msc_high_ceiling_active")))
        self.assertEqual(0.0, stage1.export_limit)
        self.assertEqual(MODE_MAX_SELF, stage1.ems_mode)
        self.assertFalse(stage1.requires_verified_msc_before_export)
        self._assert_legacy_discovery_inactive(stage1)

        optimizer._last_decision = stage1
        stage2_state = self._qualifying_full_battery_msc_state(
            optimizer,
            now_ts + 60.0,
            current_ems_mode=MODE_MAX_SELF,
            ems_mode_observed=True,
            current_export_limit=0.01,
        )
        stage2 = optimizer._decide(stage2_state)

        self.assertFalse(bool(stage2.trace_gates.get("pv_only_msc_stage1_active")))
        self.assertTrue(bool(stage2.trace_gates.get("pv_only_msc_high_ceiling_active")))
        self.assertEqual(25.0, stage2.export_limit)
        self.assertEqual(MODE_MAX_SELF, stage2.ems_mode)
        self.assertTrue(stage2.requires_verified_msc_before_export)
        self._assert_legacy_discovery_inactive(stage2)

    def test_unavailable_helper_fallback_cannot_qualify_either_msc_stage(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(daytime_topup_max_soc=100.0)
        optimizer._is_evening_or_night = lambda _now: False
        state = self._qualifying_full_battery_msc_state(
            optimizer,
            now_ts,
            sigenergy_mode=optimizer.cfg.automated_option,
            sigenergy_mode_observed=False,
        )

        decision = optimizer._decide(state)

        self.assertFalse(bool(decision.trace_gates.get("sigenergy_mode_observed")))
        self.assertFalse(bool(decision.trace_gates.get("pv_only_msc_transition_ready")))
        self.assertFalse(bool(decision.trace_gates.get("pv_only_msc_stage1_active")))
        self.assertFalse(bool(decision.trace_gates.get("pv_only_msc_high_ceiling_active")))
        self.assertFalse(decision.requires_verified_msc_before_export)
        self.assertNotEqual(
            "msc_full_battery_high_ceiling",
            decision.trace_values.get("pv_surplus_initiation_source"),
        )
        self._assert_legacy_discovery_inactive(decision)

    def test_read_state_distinguishes_fallback_mode_from_genuine_observations(self) -> None:
        ha = _BulkStateHA({})
        optimizer = self._optimizer(ha=ha)
        cfg = optimizer.cfg
        optimizer._last_state = SolarState(sigenergy_mode=cfg.automated_option)
        ha.states = {
            cfg.sigenergy_mode_select: {
                "state": "unavailable",
                "attributes": {},
            },
            cfg.ems_mode_select: {
                "state": MODE_MAX_SELF,
                "attributes": {},
            },
            cfg.grid_export_limit: {
                "state": "0.01",
                "attributes": {"max": "18.069"},
            },
            cfg.battery_soc_sensor: {
                "state": "nan",
                "attributes": {},
            },
            cfg.battery_power_sensor: {
                "state": "+inf",
                "attributes": {},
            },
        }

        unavailable_helper_state = asyncio.run(optimizer._read_state())

        self.assertTrue(unavailable_helper_state.hvac_solar_inputs.live_snapshot)
        self.assertEqual(cfg.automated_option, unavailable_helper_state.sigenergy_mode)
        self.assertFalse(unavailable_helper_state.sigenergy_mode_observed)
        self.assertEqual(MODE_MAX_SELF, unavailable_helper_state.current_ems_mode)
        self.assertTrue(unavailable_helper_state.ems_mode_observed)
        self.assertEqual(18.069, unavailable_helper_state.grid_export_limit_entity_max_kw)
        self.assertEqual(0.0, unavailable_helper_state.battery_soc)
        self.assertIsNone(unavailable_helper_state.battery_power_sensor_kw)
        self.assertIsNone(unavailable_helper_state.grid_import_power_kw)
        self.assertIsNone(unavailable_helper_state.grid_export_power_kw)
        self.assertEqual(
            (None, "unknown"),
            optimizer._battery_discharge_kw_for_pv_only_check(unavailable_helper_state),
        )

        for raw_soc in ("nan", "+inf", "-inf"):
            with self.subTest(raw_soc=raw_soc):
                ha.states[cfg.battery_soc_sensor]["state"] = raw_soc
                invalid_soc_state = asyncio.run(optimizer._read_state())
                self.assertEqual(0.0, invalid_soc_state.battery_soc)

        ha.states[cfg.sigenergy_mode_select]["state"] = cfg.automated_option
        exact_helper_state = asyncio.run(optimizer._read_state())

        self.assertEqual(cfg.automated_option, exact_helper_state.sigenergy_mode)
        self.assertTrue(exact_helper_state.sigenergy_mode_observed)

    def test_prior_high_and_stale_trace_cannot_reopen_at_subcent_fit(self) -> None:
        now_ts = datetime.now().timestamp()
        for feedin_price, feedin_price_cents in (
            (0.0, 0.0),
            (0.001, 0.1),
            (0.005, 0.5),
            (0.0099, 0.99),
        ):
            with self.subTest(feedin_price_cents=feedin_price_cents):
                optimizer = self._optimizer(daytime_topup_max_soc=100.0)
                optimizer._is_evening_or_night = lambda _now: False
                prior_high = optimizer._decide(
                    self._qualifying_full_battery_msc_state(optimizer, now_ts)
                )
                self.assertEqual(25.0, prior_high.export_limit)
                optimizer._last_decision = prior_high

                stale_cycle = optimizer._decide(
                    self._qualifying_full_battery_msc_state(
                        optimizer,
                        now_ts + 60.0,
                        feedin_price=feedin_price,
                        feedin_price_cents=feedin_price_cents,
                        current_export_limit=25.0,
                    )
                )
                self.assertEqual(0.0, stale_cycle.export_limit)
                self.assertFalse(bool(stale_cycle.trace_gates.get("pv_only_msc_stage1_active")))
                self.assertFalse(bool(stale_cycle.trace_gates.get("pv_only_msc_high_ceiling_active")))
                self.assertEqual("no_live_export", stale_cycle.trace_values.get("export_value_gate_export_type"))
                self._assert_legacy_discovery_inactive(stale_cycle)

                optimizer._last_decision = stale_cycle
                retry_cycle = optimizer._decide(
                    self._qualifying_full_battery_msc_state(
                        optimizer,
                        now_ts + 120.0,
                        feedin_price=feedin_price,
                        feedin_price_cents=feedin_price_cents,
                        current_export_limit=0.01,
                    )
                )
                self.assertEqual(0.0, retry_cycle.export_limit)
                self._assert_legacy_discovery_inactive(retry_cycle)

    def test_multi_cycle_transition_has_no_probe_ramp_veto_retry_flapping(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(daytime_topup_max_soc=100.0)
        optimizer._is_evening_or_night = lambda _now: False
        scenarios = (
            {"current_ems_mode": MODE_CMD_CHARGE_PV, "current_export_limit": 0.01},
            {"current_ems_mode": MODE_CMD_CHARGE_PV, "current_export_limit": 0.01},
            {"current_ems_mode": MODE_MAX_SELF, "current_export_limit": 0.01},
            {"current_ems_mode": MODE_CMD_DISCHARGE_PV, "current_export_limit": 25.0},
            {
                "current_ems_mode": MODE_MAX_SELF,
                "current_export_limit": 25.0,
                "feedin_price": 0.0099,
                "feedin_price_cents": 0.99,
            },
            {
                "current_ems_mode": MODE_MAX_SELF,
                "current_export_limit": 0.01,
                "feedin_price": 0.0099,
                "feedin_price_cents": 0.99,
            },
        )
        limits: list[float] = []
        decisions: list[Decision] = []
        for cycle, overrides in enumerate(scenarios):
            decision = optimizer._decide(
                self._qualifying_full_battery_msc_state(
                    optimizer,
                    now_ts + cycle * 60.0,
                    **overrides,
                )
            )
            limits.append(decision.export_limit)
            decisions.append(decision)
            self._assert_legacy_discovery_inactive(decision)
            optimizer._last_decision = decision

        self.assertEqual([0.0, 0.0, 25.0, 0.0, 0.0, 0.0], limits)
        self.assertTrue(bool(decisions[3].trace_gates.get("pv_only_msc_stage1_active")))
        self.assertEqual(MODE_MAX_SELF, decisions[3].ems_mode)

    def test_apply_reasserts_and_confirms_msc_before_opening_high_ceiling(self) -> None:
        now_ts = datetime.now().timestamp()
        ha = _RecordingHA()
        optimizer = self._optimizer(ha=ha, daytime_topup_max_soc=100.0)
        optimizer._is_evening_or_night = lambda _now: False
        state = self._qualifying_full_battery_msc_state(
            optimizer,
            now_ts,
            current_export_limit=25.0,
            ha_control_enabled=True,
            ha_control_switch_available=True,
            ha_control_switch_state="on",
        )
        decision = optimizer._decide(state)
        self.assertTrue(decision.requires_verified_msc_before_export)
        ha.state_values = {
            optimizer.cfg.ems_mode_select: MODE_CMD_DISCHARGE_PV,
            optimizer.cfg.grid_export_limit: 25.0,
        }

        asyncio.run(optimizer._apply(state, decision))

        control_calls = [
            call
            for call in ha.calls
            if call[1] in {
                optimizer.cfg.ems_mode_select,
                optimizer.cfg.grid_export_limit,
            }
        ]
        select_index = control_calls.index(
            ("select_option", optimizer.cfg.ems_mode_select, MODE_MAX_SELF)
        )
        close_index = control_calls.index(
            ("set_number", optimizer.cfg.grid_export_limit, 0.01)
        )
        close_readback_index = next(
            index
            for index, call in enumerate(control_calls)
            if index > close_index
            and call[0] == "get_state_value"
            and call[1] == optimizer.cfg.grid_export_limit
        )
        readback_index = next(
            index
            for index, call in enumerate(control_calls)
            if index > select_index
            and call == ("get_state_value", optimizer.cfg.ems_mode_select, "")
        )
        export_index = control_calls.index(
            ("set_number", optimizer.cfg.grid_export_limit, 25.0)
        )
        self.assertLess(close_index, close_readback_index)
        self.assertLess(close_readback_index, select_index)
        self.assertLess(select_index, readback_index)
        self.assertLess(readback_index, export_index)

    def test_morning_and_solar_apply_corrects_small_entity_over_cap_drift(self) -> None:
        now_ts = datetime.now().timestamp()
        for branch in ("morning_slow_charge", "solar_surplus_bypass"):
            with self.subTest(branch=branch):
                ha = _RecordingHA()
                optimizer = self._optimizer(
                    ha=ha,
                    battery_full_safeguard_enabled=False,
                    export_limit_high=25.0,
                    morning_slow_charge_rate_kw=3.7,
                )
                optimizer._is_evening_or_night = lambda _now: False
                if branch == "morning_slow_charge":
                    optimizer._morning_slow_charge_active = lambda *args, **kwargs: True
                    state = self._qualifying_full_battery_msc_state(
                        optimizer,
                        now_ts,
                        pv_kw=7.0,
                        solar_power_now_kw=7.0,
                        load_kw=1.0,
                        current_export_limit=18.07,
                        grid_export_limit_entity_max_kw=18.069,
                        ha_control_enabled=True,
                        ha_control_switch_available=True,
                        ha_control_switch_state="on",
                    )
                else:
                    state = self._qualifying_solar_bypass_state(
                        optimizer,
                        now_ts,
                        current_export_limit=18.07,
                        grid_export_limit_entity_max_kw=18.069,
                        ha_control_enabled=True,
                        ha_control_switch_available=True,
                        ha_control_switch_state="on",
                    )
                decision = optimizer._decide(state)
                self.assertEqual(18.06, decision.export_limit)
                self.assertTrue(decision.requires_verified_msc_before_export)
                ha.state_values = {
                    optimizer.cfg.ems_mode_select: MODE_MAX_SELF,
                    optimizer.cfg.grid_export_limit: 18.07,
                }

                asyncio.run(optimizer._apply(state, decision))

                select_call = (
                    "select_option",
                    optimizer.cfg.ems_mode_select,
                    MODE_MAX_SELF,
                )
                lower_call = (
                    "set_number",
                    optimizer.cfg.grid_export_limit,
                    18.06,
                )
                self.assertIn(lower_call, ha.calls)
                self.assertLess(ha.calls.index(select_call), ha.calls.index(lower_call))
                self.assertTrue(
                    any(
                        call[0] == "get_state_value"
                        and call[1] == optimizer.cfg.grid_export_limit
                        for call in ha.calls[ha.calls.index(lower_call) + 1 :]
                    )
                )

    def test_unsettled_small_over_cap_correction_enters_safe_fallback(self) -> None:
        now_ts = datetime.now().timestamp()
        ha = _RecordingHA(settle_numbers=False)
        optimizer = self._optimizer(
            ha=ha,
            battery_full_safeguard_enabled=False,
            export_limit_high=25.0,
            morning_slow_charge_rate_kw=3.7,
        )
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._morning_slow_charge_active = lambda *args, **kwargs: True
        state = self._qualifying_full_battery_msc_state(
            optimizer,
            now_ts,
            pv_kw=7.0,
            solar_power_now_kw=7.0,
            load_kw=1.0,
            current_export_limit=18.07,
            grid_export_limit_entity_max_kw=18.069,
            ha_control_enabled=True,
            ha_control_switch_available=True,
            ha_control_switch_state="on",
        )
        decision = optimizer._decide(state)
        self.assertEqual(18.06, decision.export_limit)
        ha.state_values = {
            optimizer.cfg.ems_mode_select: MODE_MAX_SELF,
            optimizer.cfg.grid_export_limit: 18.07,
        }
        wait_calls: list[tuple[str, float, float]] = []

        async def reject_unsettled(
            entity_id: str,
            maximum: float,
            *,
            timeout_s: float,
            tolerance: float = 0.011,
        ) -> bool:
            wait_calls.append((entity_id, maximum, tolerance))
            return False

        optimizer._wait_for_number_at_most = reject_unsettled

        asyncio.run(optimizer._apply(state, decision))

        target_call = ("set_number", optimizer.cfg.grid_export_limit, 18.06)
        fallback_close = ("set_number", optimizer.cfg.grid_export_limit, 0.01)
        self.assertIn(target_call, ha.calls)
        self.assertIn(fallback_close, ha.calls)
        self.assertLess(ha.calls.index(target_call), ha.calls.index(fallback_close))
        self.assertEqual(
            [(optimizer.cfg.grid_export_limit, 18.06, 0.001)],
            wait_calls,
        )

    def test_msc_reassert_without_confirmed_readback_never_writes_high_ceiling(self) -> None:
        now_ts = datetime.now().timestamp()
        ha = _RecordingHA(
            state_values={},
            settle_selects=False,
        )
        optimizer = self._optimizer(ha=ha, daytime_topup_max_soc=100.0)
        optimizer._is_evening_or_night = lambda _now: False
        state = self._qualifying_full_battery_msc_state(
            optimizer,
            now_ts,
            current_export_limit=25.0,
            ha_control_enabled=True,
            ha_control_switch_available=True,
            ha_control_switch_state="on",
        )
        decision = optimizer._decide(state)
        self.assertTrue(decision.requires_verified_msc_before_export)
        ha.state_values = {
            optimizer.cfg.ems_mode_select: MODE_CMD_DISCHARGE_PV,
            optimizer.cfg.grid_export_limit: 25.0,
        }

        asyncio.run(optimizer._apply(state, decision))

        export_writes = [
            float(call[2])
            for call in ha.calls
            if call[0] == "set_number"
            and call[1] == optimizer.cfg.grid_export_limit
        ]
        self.assertIn(0.01, export_writes)
        self.assertFalse(any(value > 0.011 for value in export_writes))

    def test_prior_high_to_material_discharge_lowers_export_before_discharge_ems(self) -> None:
        now_ts = datetime.now().timestamp()
        ha = _RecordingHA()
        optimizer = self._optimizer(ha=ha, daytime_topup_max_soc=100.0)
        optimizer._is_evening_or_night = lambda _now: False
        prior_high = optimizer._decide(
            self._qualifying_full_battery_msc_state(optimizer, now_ts)
        )
        self.assertEqual(25.0, prior_high.export_limit)
        optimizer._last_decision = prior_high
        state = self._qualifying_full_battery_msc_state(
            optimizer,
            now_ts + 60.0,
            battery_power_sensor_kw=-0.2,
            ess_max_discharge_kw=12.0,
            current_export_limit=25.0,
            ha_control_enabled=True,
            ha_control_switch_available=True,
            ha_control_switch_state="on",
        )
        decision = optimizer._decide(state)

        self.assertFalse(bool(decision.trace_gates.get("pv_only_msc_high_ceiling_active")))
        self.assertFalse(bool(decision.trace_gates.get("pv_only_msc_stage1_active")))
        self.assertEqual("battery_backed", decision.trace_values.get("export_value_gate_export_type"))
        self.assertEqual(1.4, decision.export_limit)
        self.assertIn(decision.ems_mode, DISCHARGE_MODES)
        self.assertFalse(decision.requires_verified_msc_before_export)
        ha.state_values = {
            optimizer.cfg.ems_mode_select: MODE_MAX_SELF,
            optimizer.cfg.grid_export_limit: 25.0,
        }

        asyncio.run(optimizer._apply(state, decision))

        lower_call = ("set_number", optimizer.cfg.grid_export_limit, 1.4)
        discharge_call = ("select_option", optimizer.cfg.ems_mode_select, decision.ems_mode)
        self.assertLess(ha.calls.index(lower_call), ha.calls.index(discharge_call))
        self.assertTrue(
            any(
                call[0] == "get_state_value"
                and call[1] == optimizer.cfg.grid_export_limit
                for call in ha.calls[: ha.calls.index(discharge_call)]
            )
        )

    def test_prior_high_to_unknown_flow_lowers_export_before_ordinary_discharge_policy(self) -> None:
        now_ts = datetime.now().timestamp()
        ha = _RecordingHA()
        optimizer = self._optimizer(ha=ha, daytime_topup_max_soc=100.0)
        optimizer._is_evening_or_night = lambda _now: False
        prior_high = optimizer._decide(
            self._qualifying_full_battery_msc_state(optimizer, now_ts)
        )
        optimizer._last_decision = prior_high
        state = self._qualifying_full_battery_msc_state(
            optimizer,
            now_ts + 60.0,
            battery_power_sensor_kw=None,
            grid_import_power_kw=None,
            grid_export_power_kw=None,
            ess_max_discharge_kw=12.0,
            current_export_limit=25.0,
            ha_control_enabled=True,
            ha_control_switch_available=True,
            ha_control_switch_state="on",
        )
        decision = optimizer._decide(state)

        self.assertFalse(bool(decision.trace_gates.get("pv_only_msc_high_ceiling_active")))
        self.assertFalse(bool(decision.trace_gates.get("pv_only_msc_stage1_active")))
        self.assertEqual("unknown", decision.trace_values.get("battery_flow_source_for_pv_only"))
        self.assertEqual("unknown_or_mixed", decision.trace_values.get("export_value_gate_export_type"))
        self.assertEqual(1.4, decision.export_limit)
        self.assertIn(decision.ems_mode, DISCHARGE_MODES)
        self.assertFalse(decision.requires_verified_msc_before_export)
        ha.state_values = {
            optimizer.cfg.ems_mode_select: MODE_MAX_SELF,
            optimizer.cfg.grid_export_limit: 25.0,
        }

        asyncio.run(optimizer._apply(state, decision))

        lower_call = ("set_number", optimizer.cfg.grid_export_limit, 1.4)
        discharge_call = ("select_option", optimizer.cfg.ems_mode_select, decision.ems_mode)
        self.assertLess(ha.calls.index(lower_call), ha.calls.index(discharge_call))
        self._assert_legacy_discovery_inactive(decision)

    def test_unobserved_export_limit_is_written_and_settled_before_discharge_ems(self) -> None:
        now_ts = datetime.now().timestamp()
        ha = _RecordingHA()
        optimizer = self._optimizer(ha=ha, daytime_topup_max_soc=100.0)
        optimizer._is_evening_or_night = lambda _now: False
        state = self._qualifying_full_battery_msc_state(
            optimizer,
            now_ts,
            battery_power_sensor_kw=-0.2,
            current_export_limit=0.0,
            current_ems_mode=MODE_MAX_SELF,
            ha_control_enabled=True,
            ha_control_switch_available=True,
            ha_control_switch_state="on",
        )
        decision = optimizer._decide(state)
        self.assertIn(decision.ems_mode, DISCHARGE_MODES)
        self.assertEqual(1.4, decision.export_limit)
        ha.state_values = {
            optimizer.cfg.ems_mode_select: MODE_MAX_SELF,
            optimizer.cfg.grid_export_limit: 25.0,
        }

        asyncio.run(optimizer._apply(state, decision))

        export_call = ("set_number", optimizer.cfg.grid_export_limit, 1.4)
        discharge_call = ("select_option", optimizer.cfg.ems_mode_select, decision.ems_mode)
        self.assertLess(ha.calls.index(export_call), ha.calls.index(discharge_call))
        self.assertTrue(
            any(
                call[0] == "get_state_value"
                and call[1] == optimizer.cfg.grid_export_limit
                for call in ha.calls[: ha.calls.index(discharge_call)]
            )
        )

    def test_unsettled_lower_export_never_selects_discharge_ems(self) -> None:
        now_ts = datetime.now().timestamp()
        ha = _RecordingHA(settle_numbers=False)
        optimizer = self._optimizer(ha=ha, daytime_topup_max_soc=100.0)
        optimizer._is_evening_or_night = lambda _now: False
        prior_high = optimizer._decide(
            self._qualifying_full_battery_msc_state(optimizer, now_ts)
        )
        optimizer._last_decision = prior_high
        state = self._qualifying_full_battery_msc_state(
            optimizer,
            now_ts + 60.0,
            battery_power_sensor_kw=-0.2,
            current_export_limit=25.0,
            ha_control_enabled=True,
            ha_control_switch_available=True,
            ha_control_switch_state="on",
        )
        decision = optimizer._decide(state)
        self.assertIn(decision.ems_mode, DISCHARGE_MODES)
        ha.state_values = {
            optimizer.cfg.ems_mode_select: MODE_MAX_SELF,
            optimizer.cfg.grid_export_limit: 25.0,
        }

        asyncio.run(optimizer._apply(state, decision))

        self.assertNotIn(
            ("select_option", optimizer.cfg.ems_mode_select, decision.ems_mode),
            ha.calls,
        )
        self.assertIn(
            ("select_option", optimizer.cfg.ems_mode_select, MODE_MAX_SELF),
            ha.calls,
        )

    def test_morning_slow_charge_uses_configured_msc_high_ceiling(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            daytime_topup_max_soc=100.0,
            export_limit_high=19.3,
            morning_slow_charge_rate_kw=3.7,
            morning_slow_export_ramp_up_step_kw=0.1,
            morning_slow_export_probe_step_kw=0.1,
        )
        self._record_import_topup(optimizer, import_kwh=1.0, import_price=0.16)
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._morning_slow_charge_active = lambda *args, **kwargs: True
        state = self._qualifying_full_battery_msc_state(
            optimizer,
            now_ts,
            pv_kw=7.0,
            solar_power_now_kw=7.0,
            load_kw=1.0,
            current_export_limit=1.0,
            grid_export_power_kw=1.0,
            battery_power_sensor_kw=-0.1,
            current_ems_mode=MODE_CMD_DISCHARGE_PV,
        )

        decision = optimizer._decide(state)

        self.assertTrue(bool(decision.trace_gates.get("morning_slow_charge_active")))
        self.assertFalse(bool(decision.trace_gates.get("pv_only_msc_high_ceiling_active")))
        self.assertTrue(bool(decision.trace_gates.get("pv_only_branch_high_ceiling_active")))
        self.assertEqual("morning_slow_charge", decision.trace_values.get("export_branch"))
        self.assertEqual(optimizer.cfg.export_limit_high, decision.export_limit)
        self.assertGreater(decision.export_limit, state.pv_kw - state.load_kw)
        self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
        self.assertNotIn(decision.ems_mode, DISCHARGE_MODES)
        self.assertTrue(decision.requires_verified_msc_before_export)
        self.assertEqual(optimizer.cfg.morning_slow_charge_rate_kw, decision.ess_charge_limit)
        self.assertEqual("pv_surplus_only", decision.trace_values.get("export_value_gate_export_type"))
        self.assertTrue(bool(decision.trace_gates.get("actual_import_cost_guard_active")))
        self.assertFalse(bool(decision.trace_gates.get("actual_import_cost_guard_blocking")))
        self.assertTrue(bool(decision.trace_gates.get("actual_import_cost_guard_bypassed_for_pv_surplus_only")))

    def test_morning_slow_charge_full_decide_breaks_curtailed_pv_self_lock(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            battery_full_safeguard_enabled=False,
            export_limit_high=19.3,
            morning_slow_charge_rate_kw=2.0,
            morning_slow_export_ramp_up_step_kw=0.1,
            morning_slow_export_ramp_down_step_kw=0.1,
            morning_slow_export_probe_step_kw=0.1,
        )
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._morning_slow_charge_active = lambda *args, **kwargs: True
        state = self._qualifying_full_battery_msc_state(
            optimizer,
            now_ts,
            battery_soc=72.0,
            available_discharge_energy_kwh=21.6,
            pv_kw=6.0,
            solar_power_now_kw=12.0,
            load_kw=3.0,
            forecast_remaining_kwh=100.0,
            current_export_limit=1.0,
            grid_export_power_kw=1.0,
            battery_power_sensor_kw=-0.1,
            current_ems_mode=MODE_CMD_DISCHARGE_PV,
            grid_export_limit_entity_max_kw=18.069,
        )

        decision = optimizer._decide(state)

        self.assertTrue(decision.morning_slow_charge_active)
        self.assertEqual(
            optimizer.cfg.morning_slow_charge_rate_kw,
            decision.ess_charge_limit,
        )
        self.assertEqual(18.06, decision.export_limit)
        self.assertGreater(decision.export_limit, state.pv_kw - state.load_kw)
        self.assertGreater(
            decision.export_limit,
            state.current_export_limit
            + optimizer.cfg.morning_slow_export_ramp_up_step_kw,
        )
        self.assertNotEqual(
            state.current_export_limit + optimizer.cfg.morning_slow_export_probe_step_kw,
            decision.export_limit,
        )
        self.assertEqual(
            "morning_slow_pv_high",
            decision.trace_values.get("initial_desired_export_source"),
        )
        self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
        self.assertNotIn(decision.ems_mode, DISCHARGE_MODES)
        self.assertTrue(decision.requires_verified_msc_before_export)

    def test_morning_slow_charge_retains_priority_over_high_price_and_spike(self) -> None:
        now_ts = datetime.now().timestamp()
        cases = (
            (
                "high_price",
                {
                    "feedin_price": 1.20,
                    "feedin_price_cents": 120.0,
                    "price_spike_active": False,
                },
            ),
            (
                "spike",
                {
                    "feedin_price": 0.65,
                    "feedin_price_cents": 65.0,
                    "price_spike_active": True,
                },
            ),
        )

        for name, overrides in cases:
            with self.subTest(policy=name):
                optimizer = self._optimizer(
                    battery_full_safeguard_enabled=False,
                    export_threshold_high=1.0,
                    export_spike_threshold=0.60,
                    export_limit_high=18.7,
                    morning_slow_charge_rate_kw=3.7,
                )
                optimizer._is_evening_or_night = lambda _now: False
                optimizer._morning_slow_charge_active = lambda *args, **kwargs: True
                state = self._qualifying_full_battery_msc_state(
                    optimizer,
                    now_ts,
                    battery_soc=72.0,
                    available_discharge_energy_kwh=21.6,
                    pv_kw=6.0,
                    solar_power_now_kw=12.0,
                    load_kw=3.0,
                    forecast_remaining_kwh=100.0,
                    battery_power_sensor_kw=-0.1,
                    current_ems_mode=MODE_CMD_DISCHARGE_PV,
                    grid_export_limit_entity_max_kw=17.069,
                    **overrides,
                )

                decision = optimizer._decide(state)

                if name == "high_price":
                    self.assertGreaterEqual(
                        state.feedin_price,
                        optimizer.cfg.export_threshold_high,
                    )
                else:
                    self.assertTrue(decision.export_spike_active)
                self.assertEqual(
                    "morning_slow_pv_high",
                    decision.trace_values.get("initial_desired_export_source"),
                )
                self.assertEqual(
                    "morning_slow_charge",
                    decision.trace_values.get("pv_only_branch_source"),
                )
                self.assertEqual(17.06, decision.export_limit)
                self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
                self.assertNotIn(decision.ems_mode, DISCHARGE_MODES)
                self.assertEqual(
                    optimizer.cfg.morning_slow_charge_rate_kw,
                    decision.ess_charge_limit,
                )
                self.assertTrue(decision.requires_verified_msc_before_export)

    def test_morning_slow_charge_bypasses_ordinary_forecast_export_guards(self) -> None:
        now_ts = datetime.now().timestamp()
        for active_guard in (
            "export_blocked_for_forecast",
            "export_forecast_guard",
        ):
            with self.subTest(active_guard=active_guard):
                optimizer = self._optimizer(
                    battery_full_safeguard_enabled=False,
                    export_limit_high=19.3,
                    morning_slow_charge_rate_kw=3.7,
                )
                optimizer._morning_slow_charge_active = lambda *args, **kwargs: True
                optimizer._export_blocked_for_forecast = (
                    lambda *args, **kwargs: active_guard == "export_blocked_for_forecast"
                )
                optimizer._export_forecast_guard = (
                    lambda *args, **kwargs: active_guard == "export_forecast_guard"
                )
                state = self._qualifying_full_battery_msc_state(
                    optimizer,
                    now_ts,
                    battery_soc=72.0,
                    available_discharge_energy_kwh=21.6,
                    pv_kw=6.0,
                    solar_power_now_kw=12.0,
                    load_kw=3.0,
                    forecast_remaining_kwh=100.0,
                    current_export_limit=1.0,
                    grid_export_power_kw=1.0,
                    battery_power_sensor_kw=-0.1,
                    current_ems_mode=MODE_CMD_DISCHARGE_PV,
                    grid_export_limit_entity_max_kw=18.069,
                )

                decision = optimizer._decide(state)

                self.assertTrue(decision.morning_slow_charge_active)
                self.assertTrue(bool(decision.trace_gates.get(active_guard)))
                self.assertEqual(
                    "morning_slow_pv_high",
                    decision.trace_values.get("initial_desired_export_source"),
                )
                self.assertEqual(18.06, decision.export_limit)
                self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
                self.assertNotIn(decision.ems_mode, DISCHARGE_MODES)
                self.assertEqual(
                    optimizer.cfg.morning_slow_charge_rate_kw,
                    decision.ess_charge_limit,
                )
                self.assertTrue(decision.requires_verified_msc_before_export)

    def test_morning_slow_charge_bypasses_battery_full_export_safeguard(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            battery_full_safeguard_enabled=True,
            export_limit_high=19.3,
            morning_slow_charge_rate_kw=3.7,
        )
        optimizer._morning_slow_charge_active = lambda *args, **kwargs: True
        state = self._qualifying_full_battery_msc_state(
            optimizer,
            now_ts,
            battery_soc=72.0,
            available_discharge_energy_kwh=21.6,
            pv_kw=6.0,
            solar_power_now_kw=12.0,
            load_kw=3.0,
            forecast_remaining_kwh=100.0,
            current_export_limit=1.0,
            grid_export_power_kw=1.0,
            battery_power_sensor_kw=-0.1,
            current_ems_mode=MODE_CMD_DISCHARGE_PV,
            grid_export_limit_entity_max_kw=18.069,
        )

        decision = optimizer._decide(state)

        self.assertTrue(decision.morning_slow_charge_active)
        self.assertTrue(bool(decision.trace_gates.get("battery_full_safeguard_block")))
        self.assertEqual(
            "morning_slow_pv_high",
            decision.trace_values.get("initial_desired_export_source"),
        )
        self.assertEqual(18.06, decision.export_limit)
        self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
        self.assertNotIn(decision.ems_mode, DISCHARGE_MODES)
        self.assertEqual(
            optimizer.cfg.morning_slow_charge_rate_kw,
            decision.ess_charge_limit,
        )
        self.assertTrue(decision.requires_verified_msc_before_export)
        self.assertNotIn("saving for sunset", decision.export_reason.lower())

    def test_below_threshold_morning_slow_charge_stays_closed_under_msc(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            battery_full_safeguard_enabled=False,
            max_battery_soc=100.0,
            morning_slow_charge_rate_kw=3.7,
        )
        optimizer._morning_slow_charge_active = lambda *args, **kwargs: True
        state = self._qualifying_full_battery_msc_state(
            optimizer,
            now_ts,
            battery_soc=72.0,
            available_discharge_energy_kwh=21.6,
            pv_kw=3.0,
            solar_power_now_kw=3.0,
            load_kw=1.0,
            forecast_remaining_kwh=100.0,
            current_export_limit=0.01,
            grid_export_power_kw=0.0,
            battery_power_sensor_kw=-0.1,
            current_ems_mode=MODE_CMD_DISCHARGE_PV,
        )

        decision = optimizer._decide(state)

        self.assertTrue(decision.morning_slow_charge_active)
        self.assertFalse(bool(decision.trace_gates.get("export_solar_override")))
        self.assertGreaterEqual(
            state.feedin_price,
            optimizer.cfg.export_threshold_low,
        )
        self.assertGreater(
            state.battery_soc,
            float(decision.trace_values.get("export_min_soc", 0.0))
            + optimizer.cfg.soc_hysteresis,
        )
        self.assertEqual(
            "morning_slow_closed",
            decision.trace_values.get("initial_desired_export_source"),
        )
        self.assertEqual(0.0, decision.export_limit)
        self.assertTrue(bool(decision.trace_gates.get("pv_only_branch_zero_ceiling")))
        self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
        self.assertNotIn(decision.ems_mode, DISCHARGE_MODES)
        self.assertEqual(
            optimizer.cfg.morning_slow_charge_rate_kw,
            decision.ess_charge_limit,
        )
        self.assertFalse(decision.requires_verified_msc_before_export)

    def test_unobserved_automated_cannot_claim_closed_morning_msc_ownership(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            battery_full_safeguard_enabled=False,
            max_battery_soc=100.0,
            morning_slow_charge_rate_kw=3.7,
        )
        optimizer._morning_slow_charge_active = lambda *args, **kwargs: True
        state = self._qualifying_full_battery_msc_state(
            optimizer,
            now_ts,
            sigenergy_mode_observed=False,
            battery_soc=72.0,
            available_discharge_energy_kwh=21.6,
            pv_kw=3.0,
            solar_power_now_kw=3.0,
            load_kw=1.0,
            forecast_remaining_kwh=100.0,
            current_export_limit=0.01,
            grid_export_power_kw=0.0,
            battery_power_sensor_kw=-0.1,
            current_ems_mode=MODE_CMD_DISCHARGE_PV,
        )

        decision = optimizer._decide(state)

        self.assertFalse(
            bool(decision.trace_gates.get("observed_automated_control_mode"))
        )
        self.assertEqual(
            "morning_slow_closed",
            decision.trace_values.get("initial_desired_export_source"),
        )
        self.assertEqual(0.0, decision.export_limit)
        self.assertFalse(bool(decision.trace_gates.get("pv_only_branch_zero_ceiling")))
        self.assertFalse(
            bool(decision.trace_gates.get("pv_surplus_only_ems_safety_clamp"))
        )
        self.assertEqual(MODE_CMD_DISCHARGE_PV, decision.ems_mode)
        self.assertFalse(decision.requires_verified_msc_before_export)

    def test_negative_import_price_retains_priority_over_morning_slow_charge(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            battery_full_safeguard_enabled=False,
            morning_slow_charge_rate_kw=3.7,
        )
        optimizer._morning_slow_charge_active = lambda *args, **kwargs: True
        state = self._qualifying_full_battery_msc_state(
            optimizer,
            now_ts,
            battery_soc=72.0,
            available_discharge_energy_kwh=21.6,
            current_price=-0.10,
            current_price_cents=-10.0,
            price_is_actual=True,
            feedin_price=0.10,
            feedin_price_cents=10.0,
            pv_kw=6.0,
            solar_power_now_kw=12.0,
            load_kw=3.0,
            forecast_remaining_kwh=100.0,
            battery_power_sensor_kw=-0.1,
            current_ems_mode=MODE_CMD_DISCHARGE_PV,
        )

        decision = optimizer._decide(state)

        self.assertTrue(decision.morning_slow_charge_active)
        self.assertTrue(bool(decision.trace_gates.get("price_is_negative")))
        self.assertEqual(
            "closed_negative_price",
            decision.trace_values.get("initial_desired_export_source"),
        )
        self.assertEqual(0.0, decision.export_limit)
        self.assertGreater(decision.import_limit, 0.0)
        self.assertEqual(MODE_CMD_CHARGE_GRID, decision.ems_mode)
        self.assertEqual(decision.import_limit, decision.ess_charge_limit)
        self.assertNotEqual(
            optimizer.cfg.morning_slow_charge_rate_kw,
            decision.ess_charge_limit,
        )
        self.assertFalse(decision.requires_verified_msc_before_export)

    def test_solar_surplus_bypass_uses_configured_msc_high_ceiling(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            battery_full_safeguard_enabled=False,
            export_limit_high=18.7,
        )
        self._record_import_topup(optimizer, import_kwh=1.0, import_price=0.16)
        optimizer._is_evening_or_night = lambda _now: False
        state = self._qualifying_solar_bypass_state(
            optimizer,
            now_ts,
            battery_power_sensor_kw=-0.1,
            current_ems_mode=MODE_CMD_DISCHARGE_PV,
        )

        decision = optimizer._decide(state)

        self.assertTrue(bool(decision.trace_gates.get("solar_surplus_bypass")))
        self.assertTrue(bool(decision.trace_gates.get("solar_surplus_pv_only_high_ceiling_requested")))
        self.assertTrue(bool(decision.trace_gates.get("pv_only_branch_high_ceiling_active")))
        self.assertFalse(bool(decision.trace_gates.get("pv_only_branch_battery_safety_blocked")))
        self.assertEqual("solar_surplus_bypass", decision.trace_values.get("pv_only_branch_source"))
        self.assertEqual(optimizer.cfg.export_limit_high, decision.export_limit)
        self.assertGreater(decision.export_limit, state.pv_kw - state.load_kw)
        self.assertEqual("pv_surplus_only", decision.trace_values.get("export_value_gate_export_type"))
        self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
        self.assertNotIn(decision.ems_mode, DISCHARGE_MODES)
        self.assertTrue(decision.requires_verified_msc_before_export)
        self.assertTrue(bool(decision.trace_gates.get("actual_import_cost_guard_active")))
        self.assertFalse(bool(decision.trace_gates.get("actual_import_cost_guard_blocking")))
        self.assertTrue(bool(decision.trace_gates.get("actual_import_cost_guard_bypassed_for_pv_surplus_only")))

    def test_unsafe_morning_and_solar_ceiling_falls_back_to_independent_policy(self) -> None:
        now_ts = datetime.now().timestamp()
        unsafe_flows = (
            (
                "material_discharge",
                {
                    "battery_power_sensor_kw": -0.2,
                    "grid_import_power_kw": 0.0,
                    "grid_export_power_kw": 0.0,
                },
                "direct_battery_sensor",
                "battery_backed",
            ),
            (
                "unknown_flow",
                {
                    "battery_power_sensor_kw": None,
                    "grid_import_power_kw": None,
                    "grid_export_power_kw": None,
                },
                "unknown",
                "unknown_or_mixed",
            ),
        )

        for branch in ("morning_slow_charge", "solar_surplus_bypass"):
            for (
                flow_name,
                flow_overrides,
                expected_flow_source,
                expected_export_type,
            ) in unsafe_flows:
                for current_export_limit in (0.01, 25.0):
                    with self.subTest(
                        branch=branch,
                        flow=flow_name,
                        current_export_limit=current_export_limit,
                    ):
                        optimizer = self._optimizer(
                            battery_full_safeguard_enabled=False,
                            morning_slow_charge_rate_kw=3.7,
                        )
                        optimizer._is_evening_or_night = lambda _now: False
                        baseline_optimizer = self._optimizer(
                            battery_full_safeguard_enabled=False,
                            morning_slow_charge_rate_kw=3.7,
                            solar_surplus_bypass_enabled=(
                                branch != "solar_surplus_bypass"
                            ),
                        )
                        baseline_optimizer._is_evening_or_night = lambda _now: False
                        baseline_optimizer._morning_slow_charge_active = (
                            lambda *args, **kwargs: False
                        )
                        if branch == "morning_slow_charge":
                            optimizer._morning_slow_charge_active = lambda *args, **kwargs: True
                            state = self._qualifying_full_battery_msc_state(
                                optimizer,
                                now_ts,
                                pv_kw=7.0,
                                solar_power_now_kw=7.0,
                                load_kw=1.0,
                                current_export_limit=current_export_limit,
                                **flow_overrides,
                            )
                            baseline_state = self._qualifying_full_battery_msc_state(
                                baseline_optimizer,
                                now_ts,
                                pv_kw=7.0,
                                solar_power_now_kw=7.0,
                                load_kw=1.0,
                                current_export_limit=current_export_limit,
                                **flow_overrides,
                            )
                        else:
                            state = self._qualifying_solar_bypass_state(
                                optimizer,
                                now_ts,
                                current_export_limit=current_export_limit,
                                **flow_overrides,
                            )
                            baseline_state = self._qualifying_solar_bypass_state(
                                baseline_optimizer,
                                now_ts,
                                current_export_limit=current_export_limit,
                                **flow_overrides,
                            )

                        decision = optimizer._decide(state)
                        baseline_decision = baseline_optimizer._decide(baseline_state)

                        self.assertTrue(bool(decision.trace_gates.get("pv_only_branch_high_ceiling_requested")))
                        self.assertFalse(bool(decision.trace_gates.get("pv_only_branch_high_ceiling_active")))
                        self.assertTrue(bool(decision.trace_gates.get("pv_only_branch_battery_safety_blocked")))
                        self.assertFalse(bool(decision.trace_gates.get("pv_only_discharge_ok")))
                        self.assertEqual(
                            expected_flow_source,
                            decision.trace_values.get("battery_flow_source_for_pv_only"),
                        )
                        self.assertEqual(branch, decision.trace_values.get("pv_only_branch_source"))
                        self.assertEqual(
                            expected_export_type,
                            decision.trace_values.get("export_value_gate_export_type"),
                        )
                        self.assertGreater(baseline_decision.export_limit, 0.01)
                        self.assertEqual(
                            baseline_decision.export_limit,
                            decision.export_limit,
                        )
                        self.assertLess(decision.export_limit, optimizer.cfg.export_limit_high)
                        self.assertEqual(
                            "ordinary_tier",
                            decision.trace_values.get("desired_export_source"),
                        )
                        self.assertIn(decision.ems_mode, DISCHARGE_MODES)
                        self.assertFalse(decision.requires_verified_msc_before_export)
                        self.assertIn("independent", decision.export_reason.lower())

    def test_unsafe_pv_only_ceiling_closes_when_no_independent_policy_allows_export(self) -> None:
        now_ts = datetime.now().timestamp()
        for branch in ("morning_slow_charge", "solar_surplus_bypass"):
            with self.subTest(branch=branch):
                optimizer = self._optimizer(
                    battery_full_safeguard_enabled=False,
                    morning_slow_charge_rate_kw=3.7,
                )
                optimizer._is_evening_or_night = lambda _now: False
                if branch == "morning_slow_charge":
                    optimizer._morning_slow_charge_active = lambda *args, **kwargs: True
                    state = self._qualifying_full_battery_msc_state(
                        optimizer,
                        now_ts,
                        feedin_price=0.015,
                        feedin_price_cents=1.5,
                        battery_soc=20.0,
                        available_discharge_energy_kwh=6.0,
                        forecast_remaining_kwh=100.0,
                        pv_kw=7.0,
                        solar_power_now_kw=7.0,
                        load_kw=1.0,
                        battery_power_sensor_kw=None,
                        grid_import_power_kw=None,
                        grid_export_power_kw=None,
                        current_export_limit=25.0,
                    )
                else:
                    state = self._qualifying_solar_bypass_state(
                        optimizer,
                        now_ts,
                        battery_soc=20.0,
                        available_discharge_energy_kwh=6.0,
                        battery_power_sensor_kw=None,
                        grid_import_power_kw=None,
                        grid_export_power_kw=None,
                        current_export_limit=25.0,
                    )

                decision = optimizer._decide(state)

                self.assertTrue(bool(decision.trace_gates.get("pv_only_branch_high_ceiling_requested")))
                self.assertTrue(bool(decision.trace_gates.get("pv_only_branch_battery_safety_blocked")))
                self.assertEqual(0.0, decision.export_limit)
                self.assertEqual(
                    "no_live_export",
                    decision.trace_values.get("export_value_gate_export_type"),
                )
                self.assertTrue(
                    str(decision.trace_values.get("desired_export_source", "")).startswith(
                        "closed_"
                    )
                )
                self.assertFalse(decision.requires_verified_msc_before_export)
                self.assertIn("held closed", decision.export_reason.lower())

    def test_solar_bypass_eligibility_does_not_capture_high_price_battery_export(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(battery_full_safeguard_enabled=False)
        optimizer._is_evening_or_night = lambda _now: False
        state = self._qualifying_solar_bypass_state(
            optimizer,
            now_ts,
            feedin_price=1.20,
            feedin_price_cents=120.0,
            battery_power_sensor_kw=-0.2,
        )

        decision = optimizer._decide(state)

        self.assertTrue(bool(decision.trace_gates.get("solar_surplus_bypass")))
        self.assertFalse(bool(decision.trace_gates.get("solar_surplus_pv_only_high_ceiling_requested")))
        self.assertFalse(bool(decision.trace_gates.get("pv_only_branch_battery_safety_blocked")))
        self.assertEqual("battery_backed", decision.trace_values.get("export_value_gate_export_type"))
        self.assertGreater(decision.export_limit, 0.01)
        self.assertIn(decision.ems_mode, DISCHARGE_MODES)
        self.assertFalse(decision.requires_verified_msc_before_export)

    def test_solar_bypass_high_ceiling_defers_to_competing_export_policies(self) -> None:
        now_ts = datetime.now().timestamp()
        cases = (
            (
                "solar_override",
                {"battery_soc": 100.0, "available_discharge_energy_kwh": 30.0,
                 "feedin_price": 0.30, "feedin_price_cents": 30.0},
                "solar_override",
            ),
            (
                "demand_window",
                {"demand_window_active": True},
                "ordinary_tier",
            ),
            (
                "evening_boost",
                {},
                "ordinary_tier",
            ),
        )

        for name, overrides, expected_source in cases:
            with self.subTest(policy=name):
                optimizer = self._optimizer(battery_full_safeguard_enabled=False)
                optimizer._is_evening_or_night = lambda _now: False
                if name == "evening_boost":
                    optimizer._evening_export_boost_active = lambda *args, **kwargs: True
                state = self._qualifying_solar_bypass_state(
                    optimizer,
                    now_ts,
                    battery_power_sensor_kw=-0.2,
                    **overrides,
                )

                decision = optimizer._decide(state)

                self.assertTrue(bool(decision.trace_gates.get("solar_surplus_bypass")))
                self.assertTrue(bool(decision.trace_gates.get("pv_only_branch_policy_deferred")))
                self.assertFalse(bool(decision.trace_gates.get("solar_surplus_pv_only_high_ceiling_requested")))
                self.assertFalse(bool(decision.trace_gates.get("pv_only_branch_battery_safety_blocked")))
                self.assertEqual(
                    "solar_surplus_pv_high",
                    decision.trace_values.get("initial_desired_export_source"),
                )
                self.assertEqual(
                    expected_source,
                    decision.trace_values.get("desired_export_source"),
                )
                self.assertEqual(
                    "battery_backed",
                    decision.trace_values.get("export_value_gate_export_type"),
                )
                self.assertGreater(decision.export_limit, 0.01)
                self.assertLess(decision.export_limit, optimizer.cfg.export_limit_high)
                self.assertIn(decision.ems_mode, DISCHARGE_MODES)
                self.assertFalse(decision.requires_verified_msc_before_export)

    def test_zero_capped_solar_bypass_defers_to_competing_export_policies(self) -> None:
        now_ts = datetime.now().timestamp()
        cases = (
            (
                "solar_override",
                {
                    "battery_soc": 100.0,
                    "available_discharge_energy_kwh": 30.0,
                    "feedin_price": 0.30,
                    "feedin_price_cents": 30.0,
                },
                "solar_override",
            ),
            (
                "demand_window",
                {"demand_window_active": True},
                "ordinary_tier",
            ),
            (
                "evening_boost",
                {},
                "ordinary_tier",
            ),
        )

        for name, overrides, expected_source in cases:
            with self.subTest(policy=name):
                optimizer = self._optimizer(battery_full_safeguard_enabled=False)
                optimizer._is_evening_or_night = lambda _now: False
                if name == "evening_boost":
                    optimizer._evening_export_boost_active = lambda *args, **kwargs: True
                state = self._qualifying_solar_bypass_state(
                    optimizer,
                    now_ts,
                    battery_power_sensor_kw=-0.2,
                    grid_export_limit_entity_max_kw=0.01,
                    **overrides,
                )

                decision = optimizer._decide(state)

                self.assertTrue(decision.solar_surplus_bypass)
                self.assertTrue(bool(decision.trace_gates.get("pv_only_branch_policy_deferred")))
                self.assertEqual(
                    "solar_surplus_pv_closed",
                    decision.trace_values.get("initial_desired_export_source"),
                )
                self.assertEqual(
                    expected_source,
                    decision.trace_values.get("desired_export_source"),
                )
                self.assertFalse(
                    str(decision.trace_values.get("desired_export_source", "")).startswith(
                        "solar_surplus_"
                    )
                )
                self.assertFalse(bool(decision.trace_gates.get("pv_only_branch_zero_ceiling")))
                self.assertFalse(
                    bool(
                        decision.trace_gates.get(
                            "solar_surplus_pv_only_high_ceiling_requested"
                        )
                    )
                )
                self.assertFalse(
                    bool(decision.trace_gates.get("pv_only_branch_battery_safety_blocked"))
                )
                self.assertFalse(
                    bool(decision.trace_gates.get("pv_surplus_only_ems_safety_clamp"))
                )
                self.assertEqual(
                    "battery_backed",
                    decision.trace_values.get("export_value_gate_export_type"),
                )
                self.assertGreater(decision.export_limit, 0.01)
                self.assertIn(decision.ems_mode, DISCHARGE_MODES)
                self.assertNotEqual(MODE_MAX_SELF, decision.ems_mode)
                self.assertFalse(decision.requires_verified_msc_before_export)

    def test_solar_deferral_does_not_recalculate_higher_priority_positive_fit(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            allow_low_medium_export_positive_fit=True,
            battery_full_safeguard_enabled=False,
        )
        optimizer._is_evening_or_night = lambda _now: False
        state = self._qualifying_solar_bypass_state(
            optimizer,
            now_ts,
            battery_soc=20.0,
            available_discharge_energy_kwh=6.0,
            demand_window_active=True,
            pv_kw=12.0,
            solar_power_now_kw=12.0,
            load_kw=1.0,
        )

        decision = optimizer._decide(state)

        self.assertTrue(decision.solar_surplus_bypass)
        self.assertEqual(
            "positive_fit_override",
            decision.trace_values.get("initial_desired_export_source"),
        )
        self.assertFalse(bool(decision.trace_gates.get("pv_only_branch_policy_deferred")))
        self.assertEqual(
            "positive_fit_override",
            decision.trace_values.get("desired_export_source"),
        )
        self.assertAlmostEqual(6.2, decision.export_limit)

    def test_blocked_solar_bypass_cycle_does_not_seed_continuation_hysteresis(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            battery_full_safeguard_enabled=False,
            solar_surplus_start_multiplier=2.0,
            solar_surplus_stop_multiplier=1.25,
        )
        optimizer._is_evening_or_night = lambda _now: False
        blocked_state = self._qualifying_solar_bypass_state(
            optimizer,
            now_ts,
            forecast_remaining_kwh=70.0,
            battery_power_sensor_kw=-0.2,
            current_export_limit=25.0,
        )

        blocked = optimizer._decide(blocked_state)

        self.assertTrue(blocked.solar_surplus_bypass)
        self.assertTrue(bool(blocked.trace_gates.get("pv_only_branch_battery_safety_blocked")))
        self.assertFalse(bool(blocked.trace_gates.get("pv_only_branch_high_ceiling_active")))
        optimizer._last_decision = blocked

        continuation_state = self._qualifying_solar_bypass_state(
            optimizer,
            now_ts + 60.0,
            forecast_remaining_kwh=50.0,
            battery_power_sensor_kw=0.0,
            current_export_limit=0.01,
        )
        continuation = optimizer._decide(continuation_state)

        self.assertFalse(continuation.solar_surplus_bypass)
        self.assertFalse(bool(continuation.trace_gates.get("pv_only_branch_high_ceiling_requested")))
        self.assertNotEqual(optimizer.cfg.export_limit_high, continuation.export_limit)

    def test_zero_capped_solar_bypass_does_not_seed_continuation_hysteresis(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            battery_full_safeguard_enabled=False,
            solar_surplus_start_multiplier=2.0,
            solar_surplus_stop_multiplier=1.25,
        )
        optimizer._is_evening_or_night = lambda _now: False
        capped = optimizer._decide(
            self._qualifying_solar_bypass_state(
                optimizer,
                now_ts,
                forecast_remaining_kwh=70.0,
                grid_export_limit_entity_max_kw=0.01,
            )
        )

        self.assertTrue(capped.solar_surplus_bypass)
        self.assertEqual(0.0, capped.export_limit)
        self.assertFalse(bool(capped.trace_gates.get("pv_only_branch_high_ceiling_requested")))
        self.assertFalse(bool(capped.trace_gates.get("pv_only_branch_high_ceiling_active")))
        self.assertTrue(bool(capped.trace_gates.get("pv_only_branch_zero_ceiling")))
        self.assertEqual(MODE_MAX_SELF, capped.ems_mode)
        self.assertNotIn(capped.ems_mode, DISCHARGE_MODES)
        self.assertFalse(capped.requires_verified_msc_before_export)
        optimizer._last_decision = capped

        continuation = optimizer._decide(
            self._qualifying_solar_bypass_state(
                optimizer,
                now_ts + 60.0,
                forecast_remaining_kwh=50.0,
                grid_export_limit_entity_max_kw=25.0,
            )
        )

        self.assertFalse(continuation.solar_surplus_bypass)
        self.assertFalse(bool(continuation.trace_gates.get("pv_only_branch_high_ceiling_requested")))
        self.assertNotEqual(optimizer.cfg.export_limit_high, continuation.export_limit)

    def test_unobserved_automated_rejects_morning_and_solar_pv_only_high_ceiling(self) -> None:
        now_ts = datetime.now().timestamp()
        for branch in ("morning_slow_charge", "solar_surplus_bypass"):
            with self.subTest(branch=branch):
                optimizer = self._optimizer(
                    battery_full_safeguard_enabled=False,
                    morning_slow_charge_rate_kw=3.7,
                )
                optimizer._is_evening_or_night = lambda _now: False
                if branch == "morning_slow_charge":
                    optimizer._morning_slow_charge_active = lambda *args, **kwargs: True
                    state = self._qualifying_full_battery_msc_state(
                        optimizer,
                        now_ts,
                        battery_soc=20.0,
                        available_discharge_energy_kwh=6.0,
                        pv_kw=7.0,
                        solar_power_now_kw=7.0,
                        load_kw=1.0,
                        forecast_remaining_kwh=100.0,
                        sigenergy_mode_observed=False,
                    )
                else:
                    state = self._qualifying_solar_bypass_state(
                        optimizer,
                        now_ts,
                        battery_soc=20.0,
                        available_discharge_energy_kwh=6.0,
                        forecast_remaining_kwh=70.0,
                        sigenergy_mode_observed=False,
                    )

                decision = optimizer._decide(state)

                self.assertFalse(
                    bool(decision.trace_gates.get("observed_automated_control_mode"))
                )
                self.assertTrue(
                    bool(
                        decision.trace_gates.get(
                            "pv_only_branch_automated_ownership_blocked"
                        )
                    )
                )
                self.assertTrue(
                    bool(decision.trace_gates.get("pv_only_branch_high_ceiling_requested"))
                )
                self.assertFalse(
                    bool(decision.trace_gates.get("pv_only_branch_high_ceiling_active"))
                )
                self.assertTrue(
                    bool(decision.trace_gates.get("pv_only_branch_exception_rejected"))
                )
                self.assertEqual(branch, decision.trace_values.get("pv_only_branch_source"))
                self.assertLessEqual(decision.export_limit, 0.01)
                self.assertFalse(decision.requires_verified_msc_before_export)

    def test_unobserved_automated_rejection_preserves_ordinary_export_policy(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(battery_full_safeguard_enabled=False)
        optimizer._is_evening_or_night = lambda _now: False
        decision = optimizer._decide(
            self._qualifying_solar_bypass_state(
                optimizer,
                now_ts,
                sigenergy_mode_observed=False,
            )
        )

        self.assertTrue(decision.solar_surplus_bypass)
        self.assertEqual(
            "solar_surplus_pv_high",
            decision.trace_values.get("initial_desired_export_source"),
        )
        self.assertTrue(
            bool(decision.trace_gates.get("pv_only_branch_automated_ownership_blocked"))
        )
        self.assertTrue(bool(decision.trace_gates.get("pv_only_branch_exception_rejected")))
        self.assertFalse(bool(decision.trace_gates.get("pv_only_branch_high_ceiling_active")))
        self.assertEqual("ordinary_tier", decision.trace_values.get("desired_export_source"))
        self.assertGreater(decision.export_limit, 0.01)
        self.assertLess(decision.export_limit, optimizer.cfg.export_limit_high)
        self.assertIn(decision.ems_mode, DISCHARGE_MODES)
        self.assertFalse(decision.requires_verified_msc_before_export)

    def test_manual_and_force_solar_cycles_cannot_seed_automated_continuation(self) -> None:
        now_ts = datetime.now().timestamp()
        mode_attrs = (
            "manual_option",
            "full_export_option",
            "full_import_option",
            "full_import_pv_option",
            "block_flow_option",
        )

        for mode_attr in mode_attrs:
            with self.subTest(mode_attr=mode_attr):
                optimizer = self._optimizer(
                    battery_full_safeguard_enabled=False,
                    solar_surplus_start_multiplier=2.0,
                    solar_surplus_stop_multiplier=1.25,
                )
                optimizer._is_evening_or_night = lambda _now: False
                mode_label = str(getattr(optimizer.cfg, mode_attr))

                selected_mode_state = self._qualifying_solar_bypass_state(
                    optimizer,
                    now_ts,
                    battery_soc=20.0,
                    available_discharge_energy_kwh=6.0,
                    forecast_remaining_kwh=70.0,
                    sigenergy_mode=mode_label,
                    sigenergy_mode_observed=True,
                )
                selected_mode_decision = optimizer._decide(selected_mode_state)
                self.assertTrue(
                    bool(
                        selected_mode_decision.trace_gates.get(
                            "pv_only_branch_automated_ownership_blocked"
                        )
                    )
                )
                self.assertFalse(
                    bool(
                        selected_mode_decision.trace_gates.get(
                            "pv_only_branch_high_ceiling_active"
                        )
                    )
                )
                self.assertLessEqual(selected_mode_decision.export_limit, 0.01)

                optimizer._manual_mode_override = mode_label
                override_owned = optimizer._decide(
                    self._qualifying_solar_bypass_state(
                        optimizer,
                        now_ts + 5.0,
                        battery_soc=20.0,
                        available_discharge_energy_kwh=6.0,
                        forecast_remaining_kwh=70.0,
                        sigenergy_mode=optimizer.cfg.automated_option,
                        sigenergy_mode_observed=True,
                    )
                )
                self.assertTrue(
                    bool(
                        override_owned.trace_gates.get(
                            "pv_only_branch_automated_ownership_blocked"
                        )
                    )
                )
                self.assertFalse(
                    bool(
                        override_owned.trace_gates.get(
                            "pv_only_branch_high_ceiling_active"
                        )
                    )
                )
                self.assertLessEqual(override_owned.export_limit, 0.01)
                optimizer._manual_mode_override = None

                auto_looking_state = self._qualifying_solar_bypass_state(
                    optimizer,
                    now_ts + 10.0,
                    battery_soc=20.0,
                    available_discharge_energy_kwh=6.0,
                    forecast_remaining_kwh=70.0,
                    current_export_limit=1.7,
                    current_ems_mode=MODE_CMD_DISCHARGE_PV,
                    sigenergy_mode=optimizer.cfg.automated_option,
                    sigenergy_mode_observed=True,
                )
                frozen = optimizer._decide(auto_looking_state)
                self.assertTrue(
                    bool(frozen.trace_gates.get("pv_only_branch_high_ceiling_active"))
                )
                optimizer._freeze_decision_to_live_mode(
                    auto_looking_state,
                    frozen,
                    mode_label,
                )
                self.assertEqual(auto_looking_state.current_export_limit, frozen.export_limit)
                self.assertEqual(auto_looking_state.current_ems_mode, frozen.ems_mode)
                self.assertFalse(
                    bool(frozen.trace_gates.get("pv_only_branch_high_ceiling_active"))
                )
                self.assertFalse(
                    bool(frozen.trace_gates.get("observed_automated_control_mode"))
                )
                self.assertIn(
                    "not genuinely observed",
                    str(frozen.trace_values.get("pv_only_branch_safety_reason", "")),
                )
                self.assertFalse(frozen.requires_verified_msc_before_export)
                optimizer._last_decision = frozen

                returned_to_auto = optimizer._decide(
                    self._qualifying_solar_bypass_state(
                        optimizer,
                        now_ts + 60.0,
                        battery_soc=20.0,
                        available_discharge_energy_kwh=6.0,
                        forecast_remaining_kwh=50.0,
                        current_export_limit=0.01,
                        current_ems_mode=MODE_MAX_SELF,
                        sigenergy_mode=optimizer.cfg.automated_option,
                        sigenergy_mode_observed=True,
                    )
                )
                self.assertFalse(returned_to_auto.solar_surplus_bypass)
                self.assertFalse(
                    bool(
                        returned_to_auto.trace_gates.get(
                            "pv_only_branch_high_ceiling_requested"
                        )
                    )
                )
                self.assertLessEqual(returned_to_auto.export_limit, 0.01)
                self.assertFalse(returned_to_auto.requires_verified_msc_before_export)

    def test_genuinely_automated_solar_cycle_still_seeds_continuation(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            battery_full_safeguard_enabled=False,
            solar_surplus_start_multiplier=2.0,
            solar_surplus_stop_multiplier=1.25,
        )
        optimizer._is_evening_or_night = lambda _now: False
        first = optimizer._decide(
            self._qualifying_solar_bypass_state(
                optimizer,
                now_ts,
                battery_soc=20.0,
                available_discharge_energy_kwh=6.0,
                forecast_remaining_kwh=70.0,
                sigenergy_mode=optimizer.cfg.automated_option,
                sigenergy_mode_observed=True,
            )
        )
        self.assertTrue(bool(first.trace_gates.get("observed_automated_control_mode")))
        self.assertTrue(bool(first.trace_gates.get("pv_only_branch_high_ceiling_active")))
        self.assertEqual(optimizer.cfg.export_limit_high, first.export_limit)
        self.assertEqual(MODE_MAX_SELF, first.ems_mode)
        self.assertTrue(first.requires_verified_msc_before_export)
        optimizer._last_decision = first

        continued = optimizer._decide(
            self._qualifying_solar_bypass_state(
                optimizer,
                now_ts + 60.0,
                battery_soc=20.0,
                available_discharge_energy_kwh=6.0,
                forecast_remaining_kwh=50.0,
                sigenergy_mode=optimizer.cfg.automated_option,
                sigenergy_mode_observed=True,
            )
        )

        self.assertTrue(continued.solar_surplus_bypass)
        self.assertTrue(
            bool(continued.trace_gates.get("observed_automated_control_mode"))
        )
        self.assertTrue(
            bool(continued.trace_gates.get("pv_only_branch_high_ceiling_active"))
        )
        self.assertEqual(
            "solar_surplus_pv_high",
            continued.trace_values.get("initial_desired_export_source"),
        )
        self.assertEqual(optimizer.cfg.export_limit_high, continued.export_limit)
        self.assertEqual(MODE_MAX_SELF, continued.ems_mode)
        self.assertTrue(continued.requires_verified_msc_before_export)

    def test_zero_capped_morning_slow_charge_remains_closed_under_msc(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            battery_full_safeguard_enabled=False,
            morning_slow_charge_rate_kw=3.7,
        )
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._morning_slow_charge_active = lambda *args, **kwargs: True
        decision = optimizer._decide(
            self._qualifying_full_battery_msc_state(
                optimizer,
                now_ts,
                pv_kw=7.0,
                solar_power_now_kw=7.0,
                load_kw=1.0,
                grid_export_limit_entity_max_kw=0.01,
                current_ems_mode=MODE_CMD_DISCHARGE_PV,
            )
        )

        self.assertEqual(0.0, decision.export_limit)
        self.assertFalse(bool(decision.trace_gates.get("pv_only_branch_high_ceiling_requested")))
        self.assertTrue(bool(decision.trace_gates.get("pv_only_branch_zero_ceiling")))
        self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
        self.assertNotIn(decision.ems_mode, DISCHARGE_MODES)
        self.assertEqual(
            optimizer.cfg.morning_slow_charge_rate_kw,
            decision.ess_charge_limit,
        )
        self.assertFalse(decision.requires_verified_msc_before_export)

    def test_active_solar_bypass_maintenance_closes_high_ceiling_on_discharge(self) -> None:
        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            battery_full_safeguard_enabled=False,
            solar_surplus_start_multiplier=2.0,
            solar_surplus_stop_multiplier=1.25,
        )
        optimizer._is_evening_or_night = lambda _now: False
        active = optimizer._decide(
            self._qualifying_solar_bypass_state(
                optimizer,
                now_ts,
                forecast_remaining_kwh=70.0,
                battery_power_sensor_kw=0.0,
            )
        )
        self.assertTrue(bool(active.trace_gates.get("pv_only_branch_high_ceiling_active")))
        optimizer._last_decision = active

        unsafe = optimizer._decide(
            self._qualifying_solar_bypass_state(
                optimizer,
                now_ts + 60.0,
                forecast_remaining_kwh=50.0,
                battery_power_sensor_kw=-0.2,
                current_export_limit=25.0,
            )
        )

        self.assertTrue(unsafe.solar_surplus_bypass)
        self.assertTrue(bool(unsafe.trace_gates.get("pv_only_branch_high_ceiling_requested")))
        self.assertTrue(bool(unsafe.trace_gates.get("pv_only_branch_battery_safety_blocked")))
        self.assertLess(unsafe.export_limit, optimizer.cfg.export_limit_high)
        self.assertFalse(unsafe.requires_verified_msc_before_export)

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
            current_ems_mode=MODE_CMD_CHARGE_PV,
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

    def test_enforce_flag_does_not_veto_battery_backed_export_when_not_full(self) -> None:
        now_ts = datetime.now().timestamp()
        enforcing_optimizer = self._optimizer(
            export_value_gate_enabled=True,
            export_value_gate_dry_run=True,
            export_value_gate_enforce=True,
        )
        enforcing_optimizer._is_evening_or_night = lambda _now: False
        enforcing_optimizer._desired_export_limit = lambda *args, **kwargs: 2.0
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
            battery_power_sensor_kw=-0.2,
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
        self.assertEqual("battery_backed", decision.trace_values.get("export_value_gate_export_type"))
        self.assertTrue(decision.export_value_gate_would_block)
        self.assertFalse(bool(decision.trace_gates.get("export_value_gate_enforcement_active")))
        self.assertFalse(bool(decision.trace_gates.get("export_value_gate_vetoed")))
        self.assertEqual(2.0, decision.export_limit)
        self.assertIn(decision.ems_mode, DISCHARGE_MODES)

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
            current_ems_mode=MODE_CMD_CHARGE_PV,
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

    def test_measured_pv_surplus_already_open_uses_max_self_consumption(self) -> None:
        from app.optimizer import DISCHARGE_MODES, MODE_MAX_SELF

        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            daytime_topup_max_soc=100.0,
            export_value_gate_enabled=True,
            export_value_gate_dry_run=True,
            export_value_gate_enforce=True,
        )
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 1.0
        state = self._qualifying_full_battery_msc_state(
            optimizer,
            now_ts,
            battery_soc=100.0,
            feedin_price=0.50,
            feedin_price_cents=50.0,
            pv_kw=2.0,
            solar_power_now_kw=2.0,
            load_kw=1.0,
            battery_power_sensor_kw=0.0,
            current_export_limit=1.0,
            grid_export_power_kw=1.0,
            current_ems_mode=MODE_CMD_CHARGE_PV,
            sigenergy_mode_observed=False,
        )

        decision = optimizer._decide(state)

        self.assertEqual("pv_surplus_only", decision.trace_values.get("export_value_gate_export_type"))
        self.assertTrue(bool(decision.trace_gates.get("pv_surplus_only_proven")))
        self.assertFalse(bool(decision.trace_gates.get("export_value_gate_pv_surplus_initiated_active")))
        self.assertFalse(bool(decision.trace_gates.get("export_value_gate_pv_surplus_carveout_active")))
        self.assertGreater(decision.export_limit, 0.0)
        self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
        self.assertNotIn(decision.ems_mode, DISCHARGE_MODES)
        self.assertNotEqual(optimizer.cfg.full_export_option, decision.ems_mode)
        self.assertTrue(bool(decision.trace_gates.get("pv_surplus_only_ems_safety_clamp")))
        self.assertIn(
            "forced Maximum Self Consumption",
            str(decision.trace_values.get("pv_surplus_only_ems_safety_clamp_reason", "")),
        )

    def test_battery_backed_allowed_export_not_forced_by_pv_only_ems_clamp(self) -> None:
        from app.optimizer import MODE_CMD_DISCHARGE_PV

        now_ts = datetime.now().timestamp()
        optimizer = self._optimizer(
            export_value_gate_enabled=True,
            export_value_gate_dry_run=True,
            export_value_gate_enforce=True,
        )
        optimizer._is_evening_or_night = lambda _now: False
        optimizer._desired_export_limit = lambda *args, **kwargs: 2.0
        state = self._state(
            battery_soc=100.0,
            feedin_price=0.50,
            feedin_price_cents=50.0,
            pv_kw=0.0,
            solar_power_now_kw=0.0,
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

        self.assertEqual("battery_backed", decision.trace_values.get("export_value_gate_export_type"))
        self.assertTrue(decision.export_value_gate_would_allow)
        self.assertFalse(bool(decision.trace_gates.get("pv_surplus_only_ems_safety_clamp")))
        self.assertGreater(decision.export_limit, 0.0)
        self.assertEqual(MODE_CMD_DISCHARGE_PV, decision.ems_mode)

    def test_manual_force_full_export_target_still_uses_discharge_mode(self) -> None:
        optimizer = self._optimizer()
        state = self._state(
            current_export_limit=0.01,
            current_import_limit=0.01,
            current_pv_max_power_limit=25.0,
            current_ess_charge_limit=21.0,
            current_ess_discharge_limit=24.0,
        )

        targets = optimizer._manual_mode_targets(optimizer.cfg.full_export_option, state)

        self.assertIsNotNone(targets)
        assert targets is not None
        self.assertEqual(MODE_CMD_DISCHARGE_PV, targets["ems_mode"])
        self.assertEqual(25.0, targets["grid_export_limit"])
        self.assertEqual(optimizer.cfg.block_flow_limit_value, targets["grid_import_limit"])

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

    def test_measured_discharge_uses_independent_actual_import_cost_guard(self) -> None:
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
        self.assertFalse(bool(decision.trace_gates.get("export_value_gate_enforcement_active")))
        self.assertFalse(bool(decision.trace_gates.get("export_value_gate_vetoed")))
        self.assertTrue(bool(decision.trace_gates.get("actual_import_cost_guard_applies_to_export_type")))
        self.assertTrue(bool(decision.trace_gates.get("actual_import_cost_guard_blocking")))
        self.assertTrue(bool(decision.trace_gates.get("automatic_export_blocked_below_actual_import_cost")))
        self.assertEqual(0.0, decision.export_limit)
        self.assertIn("actual import-cost guard", decision.export_reason.lower())

    def test_manual_mode_still_pauses_optimizer_writes_when_enforcement_enabled(self) -> None:
        cfg = Settings(export_value_gate_enabled=True, export_value_gate_enforce=True)
        ha = _RecordingHA()
        optimizer = SigEnergyOptimizer(ha, cfg)
        self._optimizers.append(optimizer)
        now_ts = datetime.now().timestamp()
        optimizer._is_evening_or_night = lambda _now: False
        state = self._qualifying_full_battery_msc_state(
            optimizer,
            now_ts,
            sigenergy_mode=cfg.manual_option,
            current_export_limit=1.7,
            current_import_limit=0.2,
            current_pv_max_power_limit=25.0,
            current_ess_charge_limit=21.0,
            current_ess_discharge_limit=24.0,
        )
        decision = optimizer._decide(state)
        optimizer._freeze_decision_to_live_mode(state, decision, cfg.manual_option)

        asyncio.run(optimizer._apply(state, decision))

        self.assertFalse(bool(decision.trace_gates.get("pv_only_msc_high_ceiling_active")))
        self.assertEqual(state.current_export_limit, decision.export_limit)
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
