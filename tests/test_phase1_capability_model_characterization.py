from __future__ import annotations

import asyncio
import math
import os
import tempfile
import unittest
from typing import Any

from app.config import Settings
from app.models import Decision, SolarState
from app.optimizer import (
    MODE_CMD_CHARGE_GRID,
    MODE_CMD_CHARGE_PV,
    MODE_CMD_DISCHARGE_PV,
    MODE_MAX_SELF,
    SigEnergyOptimizer,
)


class _BulkHA:
    def __init__(self, states: dict[str, dict[str, Any]] | None = None) -> None:
        self.states = states or {}

    async def bulk_states(self, _entity_ids: list[str]) -> dict[str, dict[str, Any]]:
        return self.states


class _RecordingHA(_BulkHA):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[str, str, object]] = []
        self.state_values: dict[str, object] = {}

    async def select_option(self, entity_id: str, option: str) -> bool:
        self.calls.append(("select_option", entity_id, option))
        self.state_values[entity_id] = option
        return True

    async def set_number(self, entity_id: str, value: float) -> bool:
        self.calls.append(("set_number", entity_id, value))
        return True

    async def get_state_value(self, entity_id: str, default: object = None) -> object:
        return self.state_values.get(entity_id, default)


class Phase1CapabilityModelCharacterizationTests(unittest.TestCase):
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

    def optimizer(self, ha: _BulkHA | None = None, **overrides: object) -> SigEnergyOptimizer:
        optimizer = SigEnergyOptimizer(ha or _BulkHA(), Settings(**overrides))
        self.optimizers.append(optimizer)
        return optimizer

    @staticmethod
    def entity(state: object, *, maximum: object | None = None) -> dict[str, Any]:
        attributes: dict[str, object] = {}
        if maximum is not None:
            attributes["max"] = maximum
        return {"state": str(state), "attributes": attributes}

    def read_capability_state(
        self,
        *,
        export_state: object = 5.0,
        import_state: object = 5.0,
        pv_state: object = 5.0,
        charge_state: object = 5.0,
        discharge_state: object = 5.0,
        export_max: object | None = 10.0,
        import_max: object | None = 11.0,
        pv_max: object | None = 12.0,
        charge_max: object | None = 13.0,
        discharge_max: object | None = 14.0,
        rated_charge: object = 15.0,
        rated_discharge: object = 16.0,
    ) -> tuple[SigEnergyOptimizer, SolarState]:
        cfg = Settings()
        states = {
            cfg.grid_export_limit: self.entity(export_state, maximum=export_max),
            cfg.grid_import_limit: self.entity(import_state, maximum=import_max),
            cfg.pv_max_power_limit: self.entity(pv_state, maximum=pv_max),
            cfg.ess_max_charging_limit: self.entity(charge_state, maximum=charge_max),
            cfg.ess_max_discharging_limit: self.entity(
                discharge_state, maximum=discharge_max
            ),
            cfg.ess_rated_charge_power_sensor: self.entity(rated_charge),
            cfg.ess_rated_discharge_power_sensor: self.entity(rated_discharge),
        }
        optimizer = self.optimizer(_BulkHA(states))
        return optimizer, asyncio.run(optimizer._read_state())

    def test_read_path_separates_current_setpoints_from_available_entity_maxima(self) -> None:
        _optimizer, state = self.read_capability_state()

        self.assertEqual(5.0, state.current_export_limit)
        self.assertEqual(5.0, state.current_import_limit)
        self.assertEqual(5.0, state.current_pv_max_power_limit)
        self.assertEqual(5.0, state.current_ess_charge_limit)
        self.assertEqual(5.0, state.current_ess_discharge_limit)
        self.assertEqual(10.0, state.grid_export_limit_entity_max_kw)
        self.assertEqual(13.0, state.ess_charge_limit_entity_max_kw)
        self.assertEqual(14.0, state.ess_discharge_limit_entity_max_kw)
        self.assertFalse(hasattr(state, "grid_import_limit_entity_max_kw"))
        self.assertFalse(hasattr(state, "pv_max_power_limit_entity_max_kw"))

    def test_entity_max_metadata_validation_matches_each_capability_domain(self) -> None:
        cases = (
            ("missing", None, None, None),
            ("non_numeric", "bad", None, None),
            ("nan", math.nan, None, None),
            ("positive_infinity", math.inf, None, None),
            ("negative_infinity", -math.inf, None, None),
            ("negative", -1.0, None, None),
            ("zero", 0.0, 0.0, None),
            ("over_global_power_limit", 101.0, None, None),
        )
        for label, raw_max, expected_export, expected_ess in cases:
            with self.subTest(case=label):
                _optimizer, state = self.read_capability_state(
                    export_max=raw_max,
                    charge_max=raw_max,
                    discharge_max=raw_max,
                )
                if expected_export is None:
                    self.assertIsNone(state.grid_export_limit_entity_max_kw)
                else:
                    self.assertEqual(expected_export, state.grid_export_limit_entity_max_kw)
                if expected_ess is None:
                    self.assertIsNone(state.ess_charge_limit_entity_max_kw)
                    self.assertIsNone(state.ess_discharge_limit_entity_max_kw)
                else:
                    self.assertEqual(expected_ess, state.ess_charge_limit_entity_max_kw)
                    self.assertEqual(expected_ess, state.ess_discharge_limit_entity_max_kw)

    def test_unavailable_number_sources_cannot_supply_retained_max_attributes(self) -> None:
        optimizer, state = self.read_capability_state(
            export_state="unavailable",
            charge_state="unavailable",
            discharge_state="unavailable",
            export_max=10.0,
            charge_max=11.0,
            discharge_max=12.0,
        )

        self.assertFalse(state.current_export_limit_observed)
        self.assertEqual(0.0, state.current_ess_charge_limit)
        self.assertEqual(0.0, state.current_ess_discharge_limit)
        self.assertIsNone(state.grid_export_limit_entity_max_kw)
        self.assertIsNone(state.ess_charge_limit_entity_max_kw)
        self.assertIsNone(state.ess_discharge_limit_entity_max_kw)
        self.assertEqual((15.0, 16.0), optimizer.get_power_caps_kw(state))
        self.assertEqual(25.0, optimizer._bounded_pv_only_high_ceiling(state)[0])

    def test_rated_ess_sensor_sentinel_and_implausible_value_behavior(self) -> None:
        cases = (
            ("missing_or_zero", 0.0, 999.0, 30.0),
            ("negative", -1.0, 999.0, 30.0),
            ("nan", math.nan, 999.0, 30.0),
            ("positive_infinity", math.inf, 999.0, 30.0),
            ("negative_infinity", -math.inf, 999.0, 30.0),
            ("sentinel", 999.0, 999.0, 30.0),
            ("above_sanity_ceiling", 101.0, 101.0, 30.0),
            ("legacy_gap_rejected", 998.0, 998.0, 30.0),
            ("watts_heuristic", 1000.0, 1.0, 1.0),
        )
        for label, raw, expected_stored, expected_effective in cases:
            with self.subTest(case=label):
                optimizer, state = self.read_capability_state(
                    export_max=None,
                    charge_max=None,
                    discharge_max=None,
                    rated_charge=raw,
                    rated_discharge=raw,
                )
                self.assertEqual(expected_stored, state.ess_max_charge_kw)
                self.assertEqual(expected_stored, state.ess_max_discharge_kw)
                self.assertEqual(
                    (expected_effective, expected_effective),
                    optimizer.get_power_caps_kw(state),
                )

    def test_smaller_of_simultaneous_current_ess_cap_sources_wins(self) -> None:
        optimizer = self.optimizer(ess_limit_fallback_kw=30.0)
        state = SolarState(
            ess_max_charge_kw=10.0,
            ess_max_discharge_kw=12.0,
            ess_charge_limit_entity_max_kw=20.0,
            ess_discharge_limit_entity_max_kw=25.0,
        )

        self.assertEqual((10.0, 12.0), optimizer.get_power_caps_kw(state))

    def test_only_trusted_current_ratings_update_capability_caches(self) -> None:
        cfg = Settings()
        ha = _BulkHA(
            {
                cfg.ess_rated_charge_power_sensor: self.entity(21.0),
                cfg.ess_rated_discharge_power_sensor: self.entity(22.0),
            }
        )
        optimizer = self.optimizer(ha, ess_limit_fallback_kw=30.0)

        trusted_state = asyncio.run(optimizer._read_state())
        self.assertEqual((21.0, 22.0), optimizer.get_power_caps_kw(trusted_state))
        self.assertEqual(21.0, optimizer._last_hw_charge_cap_kw)
        self.assertEqual(22.0, optimizer._last_hw_discharge_cap_kw)

        ha.states = {
            cfg.ess_rated_charge_power_sensor: self.entity(998.0),
            cfg.ess_rated_discharge_power_sensor: self.entity(101.0),
        }
        invalid_state = asyncio.run(optimizer._read_state())

        self.assertEqual(998.0, invalid_state.ess_max_charge_kw)
        self.assertEqual(101.0, invalid_state.ess_max_discharge_kw)
        self.assertEqual(21.0, optimizer._last_hw_charge_cap_kw)
        self.assertEqual(22.0, optimizer._last_hw_discharge_cap_kw)
        self.assertEqual((21.0, 22.0), optimizer.get_power_caps_kw(invalid_state))

    def test_cached_ratings_are_used_after_current_evidence_disappears(self) -> None:
        cfg = Settings()
        ha = _BulkHA(
            {
                cfg.ess_rated_charge_power_sensor: self.entity(21.0),
                cfg.ess_rated_discharge_power_sensor: self.entity(22.0),
            }
        )
        optimizer = self.optimizer(ha, ess_limit_fallback_kw=30.0)
        asyncio.run(optimizer._read_state())

        ha.states = {
            cfg.ess_rated_charge_power_sensor: self.entity("unavailable"),
            cfg.ess_rated_discharge_power_sensor: self.entity("unknown"),
        }
        unavailable_state = asyncio.run(optimizer._read_state())

        self.assertEqual((21.0, 22.0), optimizer.get_power_caps_kw(unavailable_state))

    def test_configured_ess_fallback_follows_current_and_cached_evidence(self) -> None:
        optimizer = self.optimizer(
            ess_limit_fallback_kw=30.0,
            ess_charge_limit_value=25.0,
            ess_discharge_limit_value=25.0,
        )
        state = SolarState()

        self.assertEqual((30.0, 30.0), optimizer.get_power_caps_kw(state))
        self.assertEqual(
            25.0,
            optimizer._desired_ess_charge_limit(
                state,
                desired_import=0.0,
                morning_slow_charge=False,
                desired_export=0.0,
                pv_surplus=0.0,
            ),
        )
        self.assertEqual(
            25.0,
            optimizer._desired_ess_discharge_limit(
                state,
                standby_holdoff=False,
                positive_fit_owns_live_battery_export=False,
                evening_boost=False,
            ),
        )

    def test_configured_ess_fallback_can_supply_a_legitimate_force_request(self) -> None:
        ha = _BulkHA()
        optimizer = self.optimizer(
            ha,
            ess_limit_fallback_kw=30.0,
            ess_charge_limit_value=25.0,
            ess_discharge_limit_value=25.0,
        )

        full_export = optimizer._manual_mode_targets(
            optimizer.cfg.full_export_option,
            SolarState(),
        )

        assert full_export is not None
        self.assertEqual(30.0, full_export["ess_discharge_limit"])

        cfg = optimizer.cfg
        ha.states = {
            cfg.ess_max_charging_limit: self.entity(5.0),
            cfg.ess_max_discharging_limit: self.entity(5.0),
            cfg.ess_rated_charge_power_sensor: self.entity(150.0),
            cfg.ess_rated_discharge_power_sensor: self.entity(160.0),
        }
        asyncio.run(optimizer._read_state())
        ha.states[cfg.ess_rated_charge_power_sensor] = self.entity("unavailable")
        ha.states[cfg.ess_rated_discharge_power_sensor] = self.entity("unavailable")
        unavailable_state = asyncio.run(optimizer._read_state())

        self.assertEqual((30.0, 30.0), optimizer.get_power_caps_kw(unavailable_state))
        cached_full_import = optimizer._manual_mode_targets(
            cfg.full_import_option,
            unavailable_state,
        )
        cached_full_export = optimizer._manual_mode_targets(
            cfg.full_export_option,
            unavailable_state,
        )
        assert cached_full_import is not None
        assert cached_full_export is not None
        self.assertEqual(150.0, cached_full_import["grid_import_limit"])
        self.assertEqual(150.0, cached_full_import["ess_charge_limit"])
        self.assertEqual(160.0, cached_full_export["grid_export_limit"])
        self.assertEqual(160.0, cached_full_export["ess_discharge_limit"])

    def test_grid_export_pv_only_ceiling_honors_smaller_observed_entity_max(self) -> None:
        optimizer = self.optimizer(export_limit_high=25.0)
        state = SolarState(grid_export_limit_entity_max_kw=10.0)

        ceiling, authoritative_cap = optimizer._bounded_pv_only_high_ceiling(state)

        self.assertEqual(10.0, authoritative_cap)
        self.assertEqual(10.0, ceiling)

    def test_grid_export_cap_is_quantized_down_before_serialization(self) -> None:
        optimizer = self.optimizer(export_limit_high=25.0)
        state = SolarState(grid_export_limit_entity_max_kw=10.129)

        ceiling, authoritative_cap = optimizer._bounded_pv_only_high_ceiling(state)

        self.assertEqual(10.129, authoritative_cap)
        self.assertEqual(10.12, ceiling)

    def test_missing_grid_export_cap_preserves_configured_ceiling(self) -> None:
        optimizer = self.optimizer(export_limit_high=25.0)

        ceiling, authoritative_cap = optimizer._bounded_pv_only_high_ceiling(
            SolarState(grid_export_limit_entity_max_kw=None)
        )

        self.assertIsNone(authoritative_cap)
        self.assertEqual(25.0, ceiling)

    def test_grid_export_smaller_trusted_cap_bounds_high_price_request(self) -> None:
        optimizer = self.optimizer(export_limit_high=25.0)
        state = SolarState(
            battery_soc=100.0,
            battery_capacity_kwh=40.0,
            ess_max_discharge_kw=25.0,
            feedin_price=2.0,
            feedin_price_cents=200.0,
            forecast_tomorrow_kwh=200.0,
            grid_export_limit_entity_max_kw=10.0,
        )

        request = optimizer._desired_export_limit(
            state,
            False,
            False,
            False,
            False,
            20.0,
            False,
            False,
            False,
            False,
            25.0,
            False,
            25.0,
            10.0,
            40.0,
            0.0,
            True,
            False,
            False,
            feedin_price_trusted=True,
        )

        self.assertLessEqual(float(request), 10.0)

    def test_grid_import_has_no_observed_max_and_reuses_ess_charge_rating(self) -> None:
        optimizer = self.optimizer(import_limit_high=25.0)
        state = SolarState(
            current_import_limit=5.0,
            ess_max_charge_kw=10.0,
            current_price=-1.0,
            price_is_negative=True,
        )

        request = optimizer._desired_import_limit(
            state,
            False,
            False,
            False,
            True,
            True,
            False,
            0.0,
            battery_soc_trusted=True,
            battery_capacity_trusted=True,
        )

        self.assertFalse(hasattr(state, "grid_import_limit_entity_max_kw"))
        self.assertEqual(10.0, request)
        self.assertNotEqual(state.current_import_limit, request)

    def test_ess_charge_smaller_trusted_cap_bounds_configured_baseline(self) -> None:
        optimizer = self.optimizer(
            ess_limit_fallback_kw=20.0,
            ess_charge_limit_value=25.0,
        )
        state = SolarState(
            ess_max_charge_kw=10.0,
            ess_charge_limit_entity_max_kw=10.0,
            current_ess_charge_limit=5.0,
        )

        effective_cap = optimizer.get_power_caps_kw(state)[0]
        request = optimizer._desired_ess_charge_limit(
            state,
            desired_import=0.0,
            morning_slow_charge=False,
            desired_export=0.0,
            pv_surplus=0.0,
        )

        self.assertEqual(10.0, effective_cap)
        self.assertEqual(10.0, request)

    def test_ess_discharge_smaller_trusted_cap_bounds_configured_baseline(self) -> None:
        optimizer = self.optimizer(
            ess_limit_fallback_kw=20.0,
            ess_discharge_limit_value=25.0,
        )
        state = SolarState(
            ess_max_discharge_kw=10.0,
            ess_discharge_limit_entity_max_kw=10.0,
            current_ess_discharge_limit=5.0,
        )

        effective_cap = optimizer.get_power_caps_kw(state)[1]
        request = optimizer._desired_ess_discharge_limit(
            state,
            standby_holdoff=False,
            positive_fit_owns_live_battery_export=False,
            evening_boost=False,
        )

        self.assertEqual(10.0, effective_cap)
        self.assertEqual(10.0, request)

    def test_pv_uses_configured_command_without_observed_hardware_max_domain(self) -> None:
        optimizer = self.optimizer(pv_max_power_normal=25.0)
        state = SolarState(
            current_pv_max_power_limit=5.0,
            load_kw=1.0,
        )

        request = optimizer._desired_pv_max_power(
            state,
            standby_holdoff=False,
            morning_dump=False,
            morning_slow_charge=False,
            desired_export=0.0,
        )

        self.assertFalse(hasattr(state, "pv_max_power_limit_entity_max_kw"))
        self.assertEqual(25.0, request)
        self.assertNotEqual(state.current_pv_max_power_limit, request)

    def test_current_setpoints_do_not_become_automatic_hardware_capabilities(self) -> None:
        optimizer = self.optimizer(
            ess_charge_limit_value=25.0,
            ess_discharge_limit_value=25.0,
        )
        state = SolarState(
            current_export_limit=0.0,
            current_import_limit=5.0,
            current_pv_max_power_limit=5.0,
            current_ess_charge_limit=5.0,
            current_ess_discharge_limit=5.0,
            ess_charge_limit_entity_max_kw=25.0,
            ess_discharge_limit_entity_max_kw=25.0,
        )

        self.assertEqual((25.0, 25.0), optimizer.get_power_caps_kw(state))
        self.assertEqual(25.0, optimizer._bounded_pv_only_high_ceiling(state)[0])

    def test_force_presets_preserve_legacy_targets_with_smaller_trusted_caps(self) -> None:
        optimizer = self.optimizer(
            ess_limit_fallback_kw=30.0,
            ess_charge_limit_value=25.0,
            ess_discharge_limit_value=25.0,
            pv_max_power_value=30.0,
        )
        state = SolarState(
            grid_export_limit_entity_max_kw=7.0,
            ess_charge_limit_entity_max_kw=10.0,
            ess_discharge_limit_entity_max_kw=11.0,
            current_pv_max_power_limit=5.0,
        )

        full_export = optimizer._manual_mode_targets(optimizer.cfg.full_export_option, state)
        full_import = optimizer._manual_mode_targets(optimizer.cfg.full_import_option, state)
        full_import_pv = optimizer._manual_mode_targets(
            optimizer.cfg.full_import_pv_option,
            state,
        )

        assert full_export is not None
        assert full_import is not None
        assert full_import_pv is not None
        self.assertEqual(
            {
                "ems_mode": MODE_CMD_DISCHARGE_PV,
                "grid_export_limit": 25.0,
                "grid_import_limit": 0.01,
                "pv_max_power_limit": 30.0,
                "ess_charge_limit": 25.0,
                "ess_discharge_limit": 25.0,
            },
            full_export,
        )
        for targets, mode in (
            (full_import, MODE_CMD_CHARGE_GRID),
            (full_import_pv, MODE_CMD_CHARGE_PV),
        ):
            self.assertEqual(mode, targets["ems_mode"])
            self.assertEqual(0.01, targets["grid_export_limit"])
            self.assertEqual(25.0, targets["grid_import_limit"])
            self.assertEqual(30.0, targets["pv_max_power_limit"])
            self.assertEqual(25.0, targets["ess_charge_limit"])
            self.assertEqual(25.0, targets["ess_discharge_limit"])

        filtered_cases = (
            ("unavailable_entity", "unavailable", 40.0, 41.0),
            ("above_automated_ceiling", 5.0, 150.0, 160.0),
        )
        for label, entity_state, charge_max, discharge_max in filtered_cases:
            with self.subTest(case=label):
                read_optimizer, read_state = self.read_capability_state(
                    charge_state=entity_state,
                    discharge_state=entity_state,
                    charge_max=charge_max,
                    discharge_max=discharge_max,
                )
                self.assertIsNone(read_state.ess_charge_limit_entity_max_kw)
                self.assertIsNone(read_state.ess_discharge_limit_entity_max_kw)
                self.assertEqual(
                    (15.0, 16.0),
                    read_optimizer.get_power_caps_kw(read_state),
                )

                filtered_full_import = read_optimizer._manual_mode_targets(
                    read_optimizer.cfg.full_import_option,
                    read_state,
                )
                filtered_full_export = read_optimizer._manual_mode_targets(
                    read_optimizer.cfg.full_export_option,
                    read_state,
                )
                assert filtered_full_import is not None
                assert filtered_full_export is not None
                self.assertEqual(
                    charge_max,
                    filtered_full_import["grid_import_limit"],
                )
                self.assertEqual(
                    discharge_max,
                    filtered_full_export["grid_export_limit"],
                )

        ha = _RecordingHA()
        apply_optimizer = self.optimizer(
            ha,
            ess_limit_fallback_kw=30.0,
            ess_charge_limit_value=25.0,
            ess_discharge_limit_value=25.0,
        )
        cfg = apply_optimizer.cfg
        apply_state = SolarState(
            sigenergy_mode=cfg.full_import_option,
            current_ems_mode=MODE_MAX_SELF,
            current_export_limit=5.0,
            current_import_limit=5.0,
            current_pv_max_power_limit=5.0,
            current_ess_charge_limit=5.0,
            current_ess_discharge_limit=5.0,
            grid_export_limit_entity_max_kw=7.0,
            ess_charge_limit_entity_max_kw=10.0,
            ess_discharge_limit_entity_max_kw=11.0,
        )

        result = asyncio.run(apply_optimizer._apply(apply_state, Decision()))

        self.assertTrue(result.succeeded)
        self.assertIn(("set_number", cfg.grid_export_limit, 0.01), ha.calls)
        self.assertIn(("set_number", cfg.grid_import_limit, 25.0), ha.calls)
        self.assertIn(("set_number", cfg.ess_max_charging_limit, 25.0), ha.calls)
        self.assertIn(("set_number", cfg.ess_max_discharging_limit, 25.0), ha.calls)

    def test_block_flow_and_manual_ess_overrides_preserve_legacy_targets(self) -> None:
        optimizer = self.optimizer(
            ess_limit_fallback_kw=30.0,
            ess_charge_limit_value=25.0,
            ess_discharge_limit_value=25.0,
        )
        state = SolarState(
            ess_charge_limit_entity_max_kw=10.0,
            ess_discharge_limit_entity_max_kw=11.0,
        )

        block_flow = optimizer._manual_mode_targets(
            optimizer.cfg.block_flow_option,
            state,
            include_block_flow_ess_limits=True,
        )
        assert block_flow is not None
        self.assertEqual(
            {
                "ems_mode": MODE_MAX_SELF,
                "grid_export_limit": 0.01,
                "grid_import_limit": 0.01,
                "pv_max_power_limit": 30.0,
                "ess_charge_limit": 25.0,
                "ess_discharge_limit": 25.0,
            },
            block_flow,
        )

        optimizer.set_manual_ess_overrides(charge_kw=37.0, discharge_kw=38.0)
        overridden = optimizer._manual_mode_targets(
            optimizer.cfg.block_flow_option,
            state,
            include_block_flow_ess_limits=True,
        )

        assert overridden is not None
        self.assertEqual(37.0, overridden["ess_charge_limit"])
        self.assertEqual(38.0, overridden["ess_discharge_limit"])

    def test_plain_manual_freeze_preserves_observed_setpoints_without_normalizing(self) -> None:
        optimizer = self.optimizer()
        state = SolarState(
            current_ems_mode=MODE_MAX_SELF,
            current_export_limit=1.0,
            current_import_limit=2.0,
            current_pv_max_power_limit=3.0,
            current_ess_charge_limit=4.0,
            current_ess_discharge_limit=5.0,
            ess_charge_limit_entity_max_kw=10.0,
            ess_discharge_limit_entity_max_kw=10.0,
        )
        decision = Decision()

        optimizer._freeze_decision_to_live_mode(
            state,
            decision,
            optimizer.cfg.manual_option,
        )

        self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
        self.assertEqual(1.0, decision.export_limit)
        self.assertEqual(2.0, decision.import_limit)
        self.assertEqual(3.0, decision.pv_max_power_limit)
        self.assertEqual(4.0, decision.ess_charge_limit)
        self.assertEqual(5.0, decision.ess_discharge_limit)


if __name__ == "__main__":
    unittest.main()
