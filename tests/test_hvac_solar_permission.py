from __future__ import annotations

import os
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, Mock

from app.config import Settings
from app.ha_client import HAClient
from app.models import (
    Decision,
    HVACObservedValue,
    HVACSolarInputContext,
    HVACSolarPermissionResult,
    SolarState,
)
from app.optimizer import (
    MODE_CMD_CHARGE_GRID,
    MODE_CMD_DISCHARGE_PV,
    MODE_MAX_SELF,
    SigEnergyOptimizer,
)


class _HTTPResponse:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    def raise_for_status(self) -> None:
        if self.error is not None:
            raise self.error


class _RecordingHTTPClient:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def post(self, path: str, *, json: dict[str, Any]) -> _HTTPResponse:
        self.calls.append((path, json))
        return _HTTPResponse(self.error)


class _PublishingHA:
    def __init__(
        self,
        *,
        publish_result: bool = True,
        events: list[str] | None = None,
    ) -> None:
        self.publish_result = publish_result
        self.events = events
        self.publications: list[tuple[str, str, dict[str, Any]]] = []

    async def set_state(
        self,
        entity_id: str,
        state: str,
        attributes: dict[str, Any],
    ) -> bool:
        if self.events is not None:
            self.events.append("publish")
        self.publications.append((entity_id, state, attributes))
        return self.publish_result


class _BulkStateHA(_PublishingHA):
    def __init__(self, states: dict[str, dict[str, Any]]) -> None:
        super().__init__()
        self.states = states

    async def bulk_states(self, entity_ids: list[str]) -> dict[str, dict[str, Any]]:
        return {entity_id: self.states[entity_id] for entity_id in entity_ids if entity_id in self.states}


def _fresh(value: float | str | bool) -> HVACObservedValue:
    return HVACObservedValue(value=value, available=True, fresh=True)


def _stale(value: float | str | bool) -> HVACObservedValue:
    return HVACObservedValue(value=value, available=True, fresh=False)


class HAClientStatePublicationTests(unittest.IsolatedAsyncioTestCase):
    async def test_ha_client_state_publication_success(self) -> None:
        http = _RecordingHTTPClient()
        client = HAClient.__new__(HAClient)
        client._client = http

        result = await client.set_state(
            "sensor.sigenergy_hvac_solar_permission",
            "start",
            {"reason_code": "measured_opportunity_start"},
        )

        self.assertTrue(result)
        self.assertEqual(
            http.calls,
            [
                (
                    "/api/states/sensor.sigenergy_hvac_solar_permission",
                    {
                        "state": "start",
                        "attributes": {"reason_code": "measured_opportunity_start"},
                    },
                )
            ],
        )

    async def test_ha_client_state_publication_failure_returns_false(self) -> None:
        http = _RecordingHTTPClient(RuntimeError("HTTP 503"))
        client = HAClient.__new__(HAClient)
        client._client = http

        with self.assertLogs("app.ha_client", level="WARNING"):
            result = await client.set_state(
                "sensor.sigenergy_hvac_solar_permission",
                "unavailable",
                {"reason_code": "optimizer_cycle_error"},
            )

        self.assertFalse(result)


class HVACSolarPermissionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._old_state_db_path = os.environ.get("STATE_DB_PATH")
        os.environ["STATE_DB_PATH"] = os.path.join(self._tmp.name, "state.db")
        self.optimizers: list[SigEnergyOptimizer] = []

    def tearDown(self) -> None:
        for optimizer in self.optimizers:
            optimizer._state_store.close()
        if self._old_state_db_path is None:
            os.environ.pop("STATE_DB_PATH", None)
        else:
            os.environ["STATE_DB_PATH"] = self._old_state_db_path
        self._tmp.cleanup()

    def _optimizer(
        self,
        ha: _PublishingHA | None = None,
        **overrides: Any,
    ) -> SigEnergyOptimizer:
        cfg = Settings(_env_file=None, **overrides)
        optimizer = SigEnergyOptimizer(ha or _PublishingHA(), cfg)
        self.optimizers.append(optimizer)
        return optimizer

    @staticmethod
    def _inputs(
        *,
        pv_kw: float = 2.0,
        load_kw: float = 0.5,
        battery_power_kw: float | None = 0.0,
        grid_import_kw: float | None = 0.0,
        grid_export_kw: float | None = 0.0,
        solar_power_now_kw: float = 2.0,
        sun_above_horizon: bool = True,
        control_mode: str = "Automated",
        observed_ems_mode: str = MODE_MAX_SELF,
        observed_export_limit_kw: float = 25.0,
    ) -> HVACSolarInputContext:
        return HVACSolarInputContext(
            pv_power=_fresh(pv_kw),
            load_power=_fresh(load_kw),
            battery_power=(
                _fresh(battery_power_kw)
                if battery_power_kw is not None
                else HVACObservedValue()
            ),
            grid_import_power=(
                _fresh(grid_import_kw)
                if grid_import_kw is not None
                else HVACObservedValue()
            ),
            grid_export_power=(
                _fresh(grid_export_kw)
                if grid_export_kw is not None
                else HVACObservedValue()
            ),
            solar_power_now=_fresh(solar_power_now_kw),
            sun_above_horizon=_fresh(sun_above_horizon),
            control_mode=_fresh(control_mode),
            observed_ems_mode=_fresh(observed_ems_mode),
            observed_export_limit=_fresh(observed_export_limit_kw),
        )

    @staticmethod
    def _state(inputs: HVACSolarInputContext, **overrides: Any) -> SolarState:
        state = SolarState(
            pv_kw=float(inputs.pv_power.value or 0.0),
            load_kw=float(inputs.load_power.value or 0.0),
            battery_power_sensor_kw=(
                float(inputs.battery_power.value)
                if inputs.battery_power.available
                else None
            ),
            grid_import_power_kw=(
                float(inputs.grid_import_power.value)
                if inputs.grid_import_power.available
                else None
            ),
            grid_export_power_kw=(
                float(inputs.grid_export_power.value)
                if inputs.grid_export_power.available
                else None
            ),
            solar_power_now_kw=float(inputs.solar_power_now.value or 0.0),
            sun_above_horizon=bool(inputs.sun_above_horizon.value),
            current_ems_mode=str(inputs.observed_ems_mode.value or MODE_MAX_SELF),
            current_export_limit=float(inputs.observed_export_limit.value or 0.0),
            sigenergy_mode=str(inputs.control_mode.value or "Automated"),
            hvac_solar_inputs=inputs,
        )
        for key, value in overrides.items():
            setattr(state, key, value)
        return state

    @staticmethod
    def _decision(**overrides: Any) -> Decision:
        decision = Decision(
            ems_mode=MODE_MAX_SELF,
            export_limit=25.0,
            import_limit=0.0,
            pv_max_power_limit=25.0,
        )
        for key, value in overrides.items():
            setattr(decision, key, value)
        return decision

    def _evaluate(
        self,
        optimizer: SigEnergyOptimizer,
        inputs: HVACSolarInputContext,
        *,
        previous: HVACSolarPermissionResult | None = None,
        decision: Decision | None = None,
        effective_mode: str = "Automated",
        evaluated_at: datetime | None = None,
        **state_overrides: Any,
    ):
        return optimizer._evaluate_hvac_solar_permission(
            self._state(inputs, **state_overrides),
            decision or self._decision(),
            effective_mode=effective_mode,
            previous_result=previous,
            evaluated_at=evaluated_at,
        )

    @staticmethod
    def _ha_state(
        value: Any,
        updated_at: datetime,
        *,
        reported_at: datetime | None = None,
    ) -> dict[str, Any]:
        state = {
            "state": str(value),
            "attributes": {},
            "last_updated": updated_at.isoformat(),
        }
        if reported_at is not None:
            state["last_reported"] = reported_at.isoformat()
        return state

    def _bulk_states(
        self,
        cfg: Settings,
        *,
        updated_at: datetime,
    ) -> dict[str, dict[str, Any]]:
        return {
            cfg.pv_power_sensor: self._ha_state(0.0, updated_at),
            cfg.consumed_power_sensor: self._ha_state(0.0, updated_at),
            cfg.battery_power_sensor: self._ha_state(0.0, updated_at),
            cfg.grid_import_power_sensor: self._ha_state(0.0, updated_at),
            cfg.grid_export_power_sensor: self._ha_state(0.0, updated_at),
            cfg.solar_power_now_sensor: self._ha_state(0.0, updated_at),
            cfg.sun_entity: self._ha_state("above_horizon", updated_at),
            cfg.sigenergy_mode_select: self._ha_state(cfg.automated_option, updated_at),
            cfg.ems_mode_select: self._ha_state(MODE_MAX_SELF, updated_at),
            cfg.grid_export_limit: self._ha_state(cfg.export_limit_high, updated_at),
        }

    def _prepare_tick(
        self,
        optimizer: SigEnergyOptimizer,
        state: SolarState,
        decision: Decision,
        *,
        events: list[str] | None = None,
        inverter_calls: list[tuple[str, float]] | None = None,
    ) -> None:
        optimizer._read_state = AsyncMock(return_value=state)
        optimizer._decide = Mock(return_value=decision)

        async def _apply(_state: SolarState, _decision: Decision) -> None:
            if events is not None:
                events.append("apply")
            if inverter_calls is not None:
                inverter_calls.extend(
                    [
                        ("grid_export", _decision.export_limit),
                        ("grid_import", _decision.import_limit),
                        ("pv_max", _decision.pv_max_power_limit),
                    ]
                )

        optimizer._apply = AsyncMock(side_effect=_apply)
        optimizer._record_automation_audit = Mock()
        optimizer._record_decision_trace = Mock()
        optimizer._handle_notifications = AsyncMock()
        optimizer._handle_daily_summaries = AsyncMock()
        optimizer._accumulate_history = Mock()
        optimizer._record_price_tracking = Mock()

    async def test_exact_entity_id_and_required_attributes(self) -> None:
        ha = _PublishingHA()
        optimizer = self._optimizer(ha)
        result = self._evaluate(optimizer, self._inputs())

        self.assertTrue(await optimizer._publish_hvac_solar_permission(result))

        self.assertEqual(len(ha.publications), 1)
        entity_id, state, attrs = ha.publications[0]
        self.assertEqual(entity_id, "sensor.sigenergy_hvac_solar_permission")
        self.assertEqual(state, "start")
        self.assertEqual(
            set(attrs),
            {
                "reason_code",
                "source",
                "scope",
                "contract_version",
                "soc_policy_included",
                "consumer_safety_overlay_required",
                "controls_hvac_directly",
                "estimated_opportunity_usable",
                "estimated_opportunity_rejection_reason",
                "export_constraint_active",
                "control_mode",
                "data_fresh",
                "measured_opportunity_kw",
                "estimated_opportunity_kw",
                "hidden_opportunity_kw",
                "start_threshold_kw",
                "continue_threshold_kw",
                "battery_discharge_kw",
                "battery_flow_source",
                "observed_ems_mode",
                "desired_ems_mode",
                "previous_permission",
                "desired_export_limit_kw",
                "observed_export_limit_kw",
                "evaluated_at",
                "expires_at",
            },
        )

    async def test_hvac_settings_normalize_invalid_thresholds(self) -> None:
        cfg = Settings(
            _env_file=None,
            hvac_solar_start_kw=-1.0,
            hvac_solar_continue_kw=5.0,
            hvac_solar_battery_discharge_tolerance_kw=-0.1,
            hvac_solar_hidden_margin_kw=float("nan"),
            hvac_solar_data_max_age_seconds=float("inf"),
            hvac_solar_forecast_max_age_seconds=float("inf"),
        )

        self.assertEqual(cfg.hvac_solar_start_kw, 1.0)
        self.assertEqual(cfg.hvac_solar_continue_kw, 1.0)
        self.assertEqual(cfg.hvac_solar_battery_discharge_tolerance_kw, 0.0)
        self.assertEqual(cfg.hvac_solar_hidden_margin_kw, 0.2)
        self.assertEqual(cfg.hvac_solar_data_max_age_seconds, 120.0)
        self.assertEqual(cfg.hvac_solar_forecast_max_age_seconds, 600.0)

        optimizer = self._optimizer(
            hvac_solar_start_kw=0.0,
            hvac_solar_continue_kw=0.0,
        )
        result = self._evaluate(
            optimizer,
            self._inputs(pv_kw=0.0, load_kw=0.0, solar_power_now_kw=0.0),
        )
        self.assertEqual(optimizer.cfg.hvac_solar_start_kw, 1.0)
        self.assertEqual(optimizer.cfg.hvac_solar_continue_kw, 0.5)
        self.assertEqual(result.state, "blocked")
        self.assertEqual(result.reason_code, "insufficient_measured_surplus")

    async def test_measured_opportunity_produces_start(self) -> None:
        optimizer = self._optimizer()
        result = self._evaluate(optimizer, self._inputs(pv_kw=2.0, load_kw=0.5))

        self.assertEqual(result.state, "start")
        self.assertEqual(result.reason_code, "measured_opportunity_start")
        self.assertEqual(result.source, "measured")
        self.assertEqual(result.measured_opportunity_kw, 1.5)


    async def test_estimated_hidden_opportunity_is_diagnostic_only(self) -> None:
        optimizer = self._optimizer()
        daylight = self._inputs(
            pv_kw=0.5,
            load_kw=0.5,
            solar_power_now_kw=2.0,
            sun_above_horizon=True,
        )
        below_horizon = replace(
            daylight,
            sun_above_horizon=_fresh(False),
        )

        for inputs in (daylight, below_horizon):
            with self.subTest(sun_above_horizon=inputs.sun_above_horizon.value):
                result = self._evaluate(optimizer, inputs)

                self.assertEqual(result.state, "blocked")
                self.assertEqual(
                    result.reason_code,
                    "insufficient_measured_surplus",
                )
                self.assertEqual(result.source, "none")
                self.assertEqual(result.measured_opportunity_kw, 0.0)
                self.assertEqual(result.estimated_opportunity_kw, 1.5)

    async def test_previous_successful_permission_continues_at_lower_threshold(self) -> None:
        optimizer = self._optimizer()
        inputs = self._inputs(pv_kw=1.0, load_kw=0.4, solar_power_now_kw=1.0)
        previous = self._evaluate(optimizer, self._inputs())

        result = self._evaluate(optimizer, inputs, previous=previous)

        self.assertEqual(result.state, "continue")
        self.assertEqual(result.reason_code, "measured_opportunity_continue")

    async def test_no_prior_permission_at_continuation_level_is_blocked(self) -> None:
        optimizer = self._optimizer()
        inputs = self._inputs(pv_kw=1.0, load_kw=0.4, solar_power_now_kw=1.0)

        result = self._evaluate(optimizer, inputs)

        self.assertEqual(result.state, "blocked")
        self.assertEqual(result.reason_code, "insufficient_measured_surplus")

    async def test_opportunity_below_continue_is_blocked(self) -> None:
        optimizer = self._optimizer()
        inputs = self._inputs(pv_kw=0.6, load_kw=0.3, solar_power_now_kw=0.6)
        previous = self._evaluate(optimizer, self._inputs())

        result = self._evaluate(optimizer, inputs, previous=previous)

        self.assertEqual(result.state, "blocked")
        self.assertEqual(result.reason_code, "insufficient_measured_surplus")


    async def test_measured_continue_is_not_promoted_by_estimate(self) -> None:
        optimizer = self._optimizer()
        previous = self._evaluate(optimizer, self._inputs())
        inputs = self._inputs(
            pv_kw=1.0,
            load_kw=0.4,
            solar_power_now_kw=2.0,
            sun_above_horizon=True,
        )

        result = self._evaluate(optimizer, inputs, previous=previous)

        self.assertEqual(result.state, "continue")
        self.assertEqual(result.source, "measured")
        self.assertEqual(
            result.reason_code,
            "measured_opportunity_continue",
        )
        self.assertEqual(result.measured_opportunity_kw, 0.6)
        self.assertEqual(result.estimated_opportunity_kw, 1.6)

    async def test_measured_grants_ignore_missing_or_stale_estimated_evidence(self) -> None:
        optimizer = self._optimizer()
        previous = self._evaluate(optimizer, self._inputs())
        estimated_variants = (
            HVACObservedValue(),
            _stale(2.0),
        )
        for solar_observation in estimated_variants:
            with self.subTest(solar_observation=solar_observation):
                measured_start = replace(
                    self._inputs(pv_kw=2.0, load_kw=0.5),
                    solar_power_now=solar_observation,
                )
                measured_continue = replace(
                    self._inputs(pv_kw=1.0, load_kw=0.4),
                    solar_power_now=solar_observation,
                )

                start_result = self._evaluate(optimizer, measured_start)
                continue_result = self._evaluate(
                    optimizer,
                    measured_continue,
                    previous=previous,
                )

                self.assertEqual((start_result.state, start_result.source), ("start", "measured"))
                self.assertEqual(
                    (continue_result.state, continue_result.source),
                    ("continue", "measured"),
                )

    async def test_missing_required_data_produces_unavailable(self) -> None:
        cfg = Settings(_env_file=None)
        now = datetime.now(timezone.utc)
        states = self._bulk_states(cfg, updated_at=now)
        states.pop(cfg.pv_power_sensor)
        optimizer = self._optimizer(_BulkStateHA(states))

        state = await optimizer._read_state()
        result = self._evaluate(optimizer, state.hvac_solar_inputs)

        self.assertEqual(result.state, "unavailable")
        self.assertEqual(result.reason_code, "required_data_unavailable")

    async def test_stale_live_pv_load_and_battery_data_produce_unavailable(self) -> None:
        cfg = Settings(_env_file=None, hvac_solar_data_max_age_seconds=120.0)
        now = datetime.now(timezone.utc)
        for entity_id in (
            cfg.pv_power_sensor,
            cfg.consumed_power_sensor,
            cfg.battery_power_sensor,
        ):
            with self.subTest(entity_id=entity_id):
                states = self._bulk_states(cfg, updated_at=now)
                states[entity_id] = self._ha_state(
                    0.0,
                    now,
                    reported_at=now - timedelta(seconds=121),
                )
                if entity_id == cfg.battery_power_sensor:
                    states.pop(cfg.grid_import_power_sensor)
                    states.pop(cfg.grid_export_power_sensor)
                optimizer = self._optimizer(
                    _BulkStateHA(states),
                    hvac_solar_data_max_age_seconds=120.0,
                )

                state = await optimizer._read_state()
                result = self._evaluate(optimizer, state.hvac_solar_inputs)

                self.assertEqual(result.state, "unavailable")
                self.assertEqual(result.reason_code, "required_data_stale")
                self.assertFalse(result.data_fresh)

    async def test_solcast_300_seconds_old_uses_forecast_freshness_window(self) -> None:
        cfg = Settings(
            _env_file=None,
            hvac_solar_data_max_age_seconds=120.0,
            hvac_solar_forecast_max_age_seconds=600.0,
        )
        now = datetime.now(timezone.utc)
        states = self._bulk_states(cfg, updated_at=now)
        states[cfg.solar_power_now_sensor] = self._ha_state(
            2.0,
            now - timedelta(seconds=300),
            reported_at=now - timedelta(seconds=300),
        )
        optimizer = self._optimizer(
            _BulkStateHA(states),
            hvac_solar_data_max_age_seconds=120.0,
            hvac_solar_forecast_max_age_seconds=600.0,
        )

        state = await optimizer._read_state()

        self.assertTrue(state.hvac_solar_inputs.solar_power_now.fresh)
        self.assertFalse(state.hvac_solar_inputs.pv_power.value)
        self.assertFalse(state.hvac_solar_inputs.load_power.value)


    async def test_accepted_300_second_solcast_evidence_is_diagnostic_only(
        self,
    ) -> None:
        cfg = Settings(
            _env_file=None,
            hvac_solar_data_max_age_seconds=120.0,
            hvac_solar_forecast_max_age_seconds=600.0,
        )
        now = datetime.now(timezone.utc)
        states = self._bulk_states(cfg, updated_at=now)
        states[cfg.solar_power_now_sensor] = self._ha_state(
            2.0,
            now,
            reported_at=now - timedelta(seconds=300),
        )
        optimizer = self._optimizer(
            _BulkStateHA(states),
            hvac_solar_data_max_age_seconds=120.0,
            hvac_solar_forecast_max_age_seconds=600.0,
        )

        state = await optimizer._read_state()
        result = self._evaluate(optimizer, state.hvac_solar_inputs)

        self.assertTrue(state.hvac_solar_inputs.solar_power_now.fresh)
        self.assertEqual(result.state, "blocked")
        self.assertEqual(
            result.reason_code,
            "insufficient_measured_surplus",
        )
        self.assertEqual(result.source, "none")
        self.assertEqual(result.measured_opportunity_kw, 0.0)
        self.assertEqual(result.estimated_opportunity_kw, 2.0)
        self.assertTrue(result.data_fresh)


    async def test_stale_solcast_remains_diagnostic_only(self) -> None:
        cfg = Settings(
            _env_file=None,
            hvac_solar_data_max_age_seconds=120.0,
            hvac_solar_forecast_max_age_seconds=600.0,
        )
        now = datetime.now(timezone.utc)
        states = self._bulk_states(cfg, updated_at=now)
        states[cfg.solar_power_now_sensor] = self._ha_state(
            2.0,
            now,
            reported_at=now - timedelta(seconds=601),
        )
        optimizer = self._optimizer(
            _BulkStateHA(states),
            hvac_solar_data_max_age_seconds=120.0,
            hvac_solar_forecast_max_age_seconds=600.0,
        )

        state = await optimizer._read_state()
        result = self._evaluate(optimizer, state.hvac_solar_inputs)

        self.assertFalse(state.hvac_solar_inputs.solar_power_now.fresh)
        self.assertEqual(result.state, "blocked")
        self.assertEqual(
            result.reason_code,
            "insufficient_measured_surplus",
        )
        self.assertEqual(result.source, "none")
        self.assertEqual(result.measured_opportunity_kw, 0.0)
        self.assertIsNone(result.estimated_opportunity_kw)
        self.assertTrue(result.data_fresh)

    async def test_recent_last_reported_overrides_old_last_updated(self) -> None:
        cfg = Settings(_env_file=None, hvac_solar_data_max_age_seconds=120.0)
        now = datetime.now(timezone.utc)
        states = self._bulk_states(cfg, updated_at=now)
        states[cfg.pv_power_sensor] = self._ha_state(
            0.0,
            now - timedelta(days=1),
            reported_at=now,
        )
        optimizer = self._optimizer(_BulkStateHA(states))

        state = await optimizer._read_state()
        result = self._evaluate(optimizer, state.hvac_solar_inputs)

        self.assertTrue(state.hvac_solar_inputs.pv_power.fresh)
        self.assertEqual(result.state, "blocked")
        self.assertTrue(result.data_fresh)

    async def test_unchanged_valid_control_mode_helper_is_current(self) -> None:
        cfg = Settings(_env_file=None, hvac_solar_data_max_age_seconds=120.0)
        now = datetime.now(timezone.utc)
        states = self._bulk_states(cfg, updated_at=now)
        states[cfg.sigenergy_mode_select] = self._ha_state(
            cfg.automated_option,
            now - timedelta(days=30),
        )
        optimizer = self._optimizer(_BulkStateHA(states))

        state = await optimizer._read_state()
        result = self._evaluate(optimizer, state.hvac_solar_inputs)

        self.assertTrue(state.hvac_solar_inputs.control_mode.fresh)
        self.assertEqual(state.hvac_solar_inputs.control_mode.value, cfg.automated_option)
        self.assertEqual(result.state, "blocked")
        self.assertNotEqual(result.reason_code, "required_data_stale")

    async def test_unchanged_valid_observed_ems_mode_is_current(self) -> None:
        cfg = Settings(
            _env_file=None,
            hvac_solar_data_max_age_seconds=120.0,
        )
        now = datetime.now(timezone.utc)
        states = self._bulk_states(cfg, updated_at=now)
        states[cfg.ems_mode_select] = self._ha_state(
            MODE_MAX_SELF,
            now - timedelta(days=1),
        )
        optimizer = self._optimizer(_BulkStateHA(states))

        state = await optimizer._read_state()
        result = self._evaluate(
            optimizer,
            state.hvac_solar_inputs,
        )

        self.assertTrue(
            state.hvac_solar_inputs.observed_ems_mode.fresh
        )
        self.assertEqual(
            state.hvac_solar_inputs.observed_ems_mode.value,
            MODE_MAX_SELF,
        )
        self.assertEqual(result.state, "blocked")
        self.assertEqual(
            result.reason_code,
            "insufficient_measured_surplus",
        )

    async def test_old_device_last_reported_remains_stale(self) -> None:
        cfg = Settings(_env_file=None, hvac_solar_data_max_age_seconds=120.0)
        now = datetime.now(timezone.utc)
        states = self._bulk_states(cfg, updated_at=now)
        states[cfg.pv_power_sensor] = self._ha_state(
            0.0,
            now,
            reported_at=now - timedelta(seconds=121),
        )
        optimizer = self._optimizer(_BulkStateHA(states))

        state = await optimizer._read_state()
        result = self._evaluate(optimizer, state.hvac_solar_inputs)

        self.assertFalse(state.hvac_solar_inputs.pv_power.fresh)
        self.assertEqual(result.state, "unavailable")
        self.assertEqual(result.reason_code, "required_data_stale")

    async def test_last_updated_fallback_is_used_without_last_reported(self) -> None:
        cfg = Settings(_env_file=None, hvac_solar_data_max_age_seconds=120.0)
        now = datetime.now(timezone.utc)
        states = self._bulk_states(cfg, updated_at=now)
        self.assertNotIn("last_reported", states[cfg.pv_power_sensor])
        optimizer = self._optimizer(_BulkStateHA(states))

        state = await optimizer._read_state()
        result = self._evaluate(optimizer, state.hvac_solar_inputs)

        self.assertTrue(state.hvac_solar_inputs.pv_power.fresh)
        self.assertNotEqual(result.state, "unavailable")

    async def test_legitimate_fresh_zero_values_are_available(self) -> None:
        cfg = Settings(_env_file=None)
        now = datetime.now(timezone.utc)
        states = self._bulk_states(cfg, updated_at=now)
        optimizer = self._optimizer(_BulkStateHA(states))

        state = await optimizer._read_state()
        result = self._evaluate(optimizer, state.hvac_solar_inputs)

        self.assertEqual(result.state, "blocked")
        self.assertEqual(result.reason_code, "insufficient_measured_surplus")
        self.assertTrue(result.data_fresh)

    async def test_negative_fit_alone_does_not_block_permission(self) -> None:
        optimizer = self._optimizer()

        result = self._evaluate(
            optimizer,
            self._inputs(pv_kw=2.0, load_kw=0.5),
            feedin_price=-0.25,
            feedin_price_cents=-25.0,
            feedin_is_negative=True,
        )

        self.assertEqual(result.state, "start")
        self.assertNotIn("fit", result.reason_code)

    async def test_export_constraint_alone_neither_blocks_nor_starts(self) -> None:
        optimizer = self._optimizer()
        constrained = self._decision(export_limit=0.0)
        with_opportunity = self._evaluate(
            optimizer,
            self._inputs(pv_kw=2.0, load_kw=0.5),
            decision=constrained,
        )
        without_opportunity = self._evaluate(
            optimizer,
            self._inputs(pv_kw=0.0, load_kw=0.0, solar_power_now_kw=0.0),
            decision=constrained,
        )

        self.assertTrue(with_opportunity.export_constraint_active)
        self.assertEqual(with_opportunity.state, "start")
        self.assertEqual(without_opportunity.state, "blocked")
        self.assertEqual(without_opportunity.reason_code, "insufficient_measured_surplus")

    async def test_zero_grid_export_alone_neither_blocks_nor_starts(self) -> None:
        optimizer = self._optimizer()
        with_opportunity = self._evaluate(
            optimizer,
            self._inputs(pv_kw=2.0, load_kw=0.5, grid_export_kw=0.0),
        )
        without_opportunity = self._evaluate(
            optimizer,
            self._inputs(
                pv_kw=0.0,
                load_kw=0.0,
                solar_power_now_kw=0.0,
                grid_export_kw=0.0,
            ),
        )

        self.assertEqual(with_opportunity.state, "start")
        self.assertEqual(without_opportunity.state, "blocked")

    async def test_normal_pv_max_alone_does_not_start_permission(self) -> None:
        optimizer = self._optimizer()
        result = self._evaluate(
            optimizer,
            self._inputs(pv_kw=0.0, load_kw=0.0, solar_power_now_kw=0.0),
            decision=self._decision(pv_max_power_limit=25.0),
        )

        self.assertEqual(result.state, "blocked")
        self.assertEqual(result.reason_code, "insufficient_measured_surplus")

    async def test_battery_discharge_above_tolerance_blocks(self) -> None:
        optimizer = self._optimizer()
        result = self._evaluate(
            optimizer,
            self._inputs(battery_power_kw=-0.11),
        )

        self.assertEqual(result.state, "blocked")
        self.assertEqual(result.reason_code, "battery_discharging")
        self.assertAlmostEqual(result.battery_discharge_kw or 0.0, 0.11)

    async def test_unknown_battery_flow_produces_unavailable(self) -> None:
        optimizer = self._optimizer()
        result = self._evaluate(
            optimizer,
            self._inputs(
                battery_power_kw=None,
                grid_import_kw=None,
                grid_export_kw=None,
            ),
        )

        self.assertEqual(result.state, "unavailable")
        self.assertEqual(result.reason_code, "battery_flow_unavailable")

    async def test_battery_flow_prefers_direct_and_requires_complete_grid_fallback(self) -> None:
        optimizer = self._optimizer()
        direct = self._evaluate(
            optimizer,
            self._inputs(
                battery_power_kw=0.0,
                grid_import_kw=0.0,
                grid_export_kw=5.0,
            ),
        )
        fallback = self._evaluate(
            optimizer,
            self._inputs(
                battery_power_kw=None,
                grid_import_kw=0.0,
                grid_export_kw=0.0,
            ),
        )
        incomplete = self._evaluate(
            optimizer,
            self._inputs(
                battery_power_kw=None,
                grid_import_kw=0.0,
                grid_export_kw=None,
            ),
        )

        self.assertEqual((direct.state, direct.battery_flow_source), ("start", "direct_battery_sensor"))
        self.assertEqual((fallback.state, fallback.battery_flow_source), ("start", "measured_grid_flow"))
        self.assertEqual(incomplete.reason_code, "battery_flow_unavailable")

    async def test_invalid_required_state_and_timestamp_forms_are_unavailable(self) -> None:
        cfg = Settings(_env_file=None)
        now = datetime.now(timezone.utc)
        for invalid_state in ("unknown", "unavailable", "none", "", "not-a-number"):
            with self.subTest(invalid_state=invalid_state):
                states = self._bulk_states(cfg, updated_at=now)
                states[cfg.pv_power_sensor] = self._ha_state(invalid_state, now)
                optimizer = self._optimizer(_BulkStateHA(states))
                state = await optimizer._read_state()
                result = self._evaluate(optimizer, state.hvac_solar_inputs)
                self.assertEqual(result.state, "unavailable")
                self.assertEqual(result.reason_code, "required_data_unavailable")

        for invalid_timestamp in (None, "not-a-timestamp"):
            with self.subTest(invalid_timestamp=invalid_timestamp):
                states = self._bulk_states(cfg, updated_at=now)
                states[cfg.pv_power_sensor]["last_updated"] = invalid_timestamp
                optimizer = self._optimizer(_BulkStateHA(states))
                state = await optimizer._read_state()
                result = self._evaluate(optimizer, state.hvac_solar_inputs)
                self.assertEqual(result.state, "unavailable")
                self.assertEqual(result.reason_code, "required_data_stale")

    async def test_control_and_ems_trust_fail_closed(self) -> None:
        optimizer = self._optimizer()
        base = self._inputs()
        cases = (
            (
                "missing control",
                replace(base, control_mode=HVACObservedValue()),
                "control_mode_unavailable",
            ),
            (
                "stale control",
                replace(base, control_mode=_stale("Automated")),
                "required_data_stale",
            ),
            (
                "unrecognised control",
                replace(base, control_mode=_fresh("Unexpected")),
                "control_mode_unavailable",
            ),
            (
                "missing EMS",
                replace(base, observed_ems_mode=HVACObservedValue()),
                "ems_mode_unavailable",
            ),
            (
                "stale EMS",
                replace(base, observed_ems_mode=_stale(MODE_MAX_SELF)),
                "required_data_stale",
            ),
            (
                "unrecognised EMS",
                replace(base, observed_ems_mode=_fresh("Unexpected")),
                "ems_mode_unavailable",
            ),
        )
        for label, inputs, reason in cases:
            with self.subTest(label=label):
                result = self._evaluate(optimizer, inputs)
                self.assertEqual(result.state, "unavailable")
                self.assertEqual(result.reason_code, reason)

    async def test_manual_and_forced_control_modes_block(self) -> None:
        optimizer = self._optimizer()
        modes = (
            optimizer.cfg.full_export_option,
            optimizer.cfg.full_import_option,
            optimizer.cfg.full_import_pv_option,
            optimizer.cfg.block_flow_option,
            optimizer.cfg.manual_option,
        )
        for mode in modes:
            with self.subTest(mode=mode):
                result = self._evaluate(
                    optimizer,
                    self._inputs(control_mode=mode),
                    effective_mode=mode,
                )
                self.assertEqual(result.state, "blocked")
                self.assertEqual(result.reason_code, "control_mode_not_automated")

    async def test_watch_entities_include_permission_critical_inputs(self) -> None:
        optimizer = self._optimizer()

        watched = optimizer.get_watch_entities()

        self.assertTrue(
            {
                optimizer.cfg.battery_power_sensor,
                optimizer.cfg.grid_import_power_sensor,
                optimizer.cfg.grid_export_power_sensor,
                optimizer.cfg.solar_power_now_sensor,
                optimizer.cfg.sun_entity,
                optimizer.cfg.ems_mode_select,
                optimizer.cfg.grid_export_limit,
            }.issubset(watched)
        )

    async def test_unsafe_observed_ems_blocks(self) -> None:
        optimizer = self._optimizer()
        discharging = self._evaluate(
            optimizer,
            self._inputs(observed_ems_mode=MODE_CMD_DISCHARGE_PV),
        )
        charging = self._evaluate(
            optimizer,
            self._inputs(observed_ems_mode=MODE_CMD_CHARGE_GRID),
        )

        self.assertEqual(discharging.reason_code, "ems_discharging")
        self.assertEqual(charging.reason_code, "ems_mode_not_solar_safe")
        self.assertEqual((discharging.state, charging.state), ("blocked", "blocked"))

    async def test_unsafe_intended_ems_blocks(self) -> None:
        optimizer = self._optimizer()
        discharging = self._evaluate(
            optimizer,
            self._inputs(),
            decision=self._decision(ems_mode=MODE_CMD_DISCHARGE_PV),
        )
        charging = self._evaluate(
            optimizer,
            self._inputs(),
            decision=self._decision(ems_mode=MODE_CMD_CHARGE_GRID),
        )

        self.assertEqual(discharging.reason_code, "ems_discharge_requested")
        self.assertEqual(charging.reason_code, "ems_mode_not_solar_safe")
        self.assertEqual((discharging.state, charging.state), ("blocked", "blocked"))

    async def test_publication_failure_does_not_fail_tick_or_alter_apply(self) -> None:
        events: list[str] = []
        ha = _PublishingHA(publish_result=False, events=events)
        optimizer = self._optimizer(ha)
        state = self._state(self._inputs())
        decision = self._decision()
        self._prepare_tick(optimizer, state, decision, events=events)

        with self.assertLogs("app.optimizer", level="WARNING"):
            await optimizer._tick()

        self.assertEqual(events, ["apply", "publish"])
        optimizer._apply.assert_awaited_once_with(state, decision)
        self.assertIsNone(optimizer._last_published_hvac_solar_permission_result)

    async def test_failed_publication_does_not_replace_last_successful_result(self) -> None:
        ha = _PublishingHA()
        optimizer = self._optimizer(ha)
        start_result = self._evaluate(optimizer, self._inputs())
        self.assertTrue(await optimizer._publish_hvac_solar_permission(start_result))
        retained = optimizer._last_published_hvac_solar_permission_result

        blocked_result = self._evaluate(
            optimizer,
            self._inputs(pv_kw=0.0, load_kw=0.0, solar_power_now_kw=0.0),
            previous=retained,
        )
        ha.publish_result = False

        with self.assertLogs("app.optimizer", level="WARNING"):
            self.assertFalse(await optimizer._publish_hvac_solar_permission(blocked_result))

        lower = self._inputs(pv_kw=1.0, load_kw=0.4, solar_power_now_kw=1.0)
        next_result = self._evaluate(
            optimizer,
            lower,
            previous=optimizer._last_published_hvac_solar_permission_result,
        )
        self.assertIs(optimizer._last_published_hvac_solar_permission_result, retained)
        self.assertEqual(next_result.state, "continue")

    async def test_unexpired_successfully_published_start_permits_continuation(self) -> None:
        optimizer = self._optimizer()
        evaluated_at = datetime(2026, 8, 4, 1, 0, tzinfo=timezone.utc)
        start_result = self._evaluate(
            optimizer,
            self._inputs(),
            evaluated_at=evaluated_at,
        )

        self.assertTrue(await optimizer._publish_hvac_solar_permission(start_result))

        lower = self._inputs(pv_kw=1.0, load_kw=0.4, solar_power_now_kw=1.0)
        next_result = self._evaluate(
            optimizer,
            lower,
            previous=optimizer._last_published_hvac_solar_permission_result,
            evaluated_at=evaluated_at + timedelta(seconds=60),
        )
        self.assertIs(optimizer._last_published_hvac_solar_permission_result, start_result)
        self.assertEqual(next_result.state, "continue")

    async def test_expired_successfully_published_start_does_not_continue(self) -> None:
        optimizer = self._optimizer(hvac_solar_data_max_age_seconds=120.0)
        evaluated_at = datetime(2026, 8, 4, 1, 0, tzinfo=timezone.utc)
        start_result = self._evaluate(
            optimizer,
            self._inputs(),
            evaluated_at=evaluated_at,
        )
        self.assertTrue(await optimizer._publish_hvac_solar_permission(start_result))

        result = self._evaluate(
            optimizer,
            self._inputs(pv_kw=1.0, load_kw=0.4, solar_power_now_kw=1.0),
            previous=optimizer._last_published_hvac_solar_permission_result,
            evaluated_at=evaluated_at + timedelta(seconds=121),
        )

        self.assertEqual(result.state, "blocked")
        self.assertEqual(result.reason_code, "insufficient_measured_surplus")
        self.assertEqual(result.previous_permission, "start")

    async def test_successful_blocked_or_unavailable_publication_resets_continuation(self) -> None:
        for replacement_state in ("blocked", "unavailable"):
            with self.subTest(replacement_state=replacement_state):
                optimizer = self._optimizer()
                start_result = self._evaluate(optimizer, self._inputs())
                self.assertTrue(await optimizer._publish_hvac_solar_permission(start_result))

                if replacement_state == "blocked":
                    replacement_result = self._evaluate(
                        optimizer,
                        self._inputs(pv_kw=0.0, load_kw=0.0, solar_power_now_kw=0.0),
                        previous=optimizer._last_published_hvac_solar_permission_result,
                    )
                else:
                    replacement_result = optimizer._hvac_solar_cycle_error_result()
                self.assertEqual(replacement_result.state, replacement_state)
                self.assertTrue(
                    await optimizer._publish_hvac_solar_permission(replacement_result)
                )

                result = self._evaluate(
                    optimizer,
                    self._inputs(pv_kw=1.0, load_kw=0.4, solar_power_now_kw=1.0),
                    previous=optimizer._last_published_hvac_solar_permission_result,
                )
                self.assertEqual(result.state, "blocked")
                self.assertEqual(result.reason_code, "insufficient_measured_surplus")

    async def test_optimizer_cycle_failure_best_effort_publishes_unavailable(self) -> None:
        ha = _PublishingHA()
        optimizer = self._optimizer(ha)
        optimizer._read_state = AsyncMock(side_effect=RuntimeError("read failed"))

        with self.assertLogs("app.optimizer", level="ERROR"):
            await optimizer._safe_tick()

        self.assertEqual(len(ha.publications), 1)
        self.assertEqual(ha.publications[0][1], "unavailable")
        self.assertEqual(ha.publications[0][2]["reason_code"], "optimizer_cycle_error")

    async def test_startup_failure_publishes_unavailable(self) -> None:
        ha = _PublishingHA()
        optimizer = self._optimizer(ha)

        async def _fail_startup_read() -> SolarState:
            optimizer._running = False
            raise RuntimeError("startup read failed")

        optimizer._read_state = _fail_startup_read
        with self.assertLogs("app.optimizer", level="ERROR"):
            await optimizer.run_forever()

        self.assertEqual(len(ha.publications), 1)
        self.assertEqual(ha.publications[0][2]["reason_code"], "optimizer_cycle_error")

    async def test_run_once_failure_publishes_unavailable_and_reraises(self) -> None:
        ha = _PublishingHA()
        optimizer = self._optimizer(ha)
        original = RuntimeError("run once failed")
        optimizer._read_state = AsyncMock(side_effect=original)

        with self.assertRaises(RuntimeError) as raised:
            await optimizer.run_once()

        self.assertIs(raised.exception, original)
        self.assertEqual(len(ha.publications), 1)
        self.assertEqual(ha.publications[0][1], "unavailable")

    async def test_no_other_synthetic_entity_is_published(self) -> None:
        ha = _PublishingHA()
        optimizer = self._optimizer(ha)
        state = self._state(self._inputs())
        decision = self._decision()
        self._prepare_tick(optimizer, state, decision)

        await optimizer._tick()

        self.assertEqual(
            [publication[0] for publication in ha.publications],
            ["sensor.sigenergy_hvac_solar_permission"],
        )

    async def test_existing_inverter_writes_are_unchanged_by_publication(self) -> None:
        events: list[str] = []
        inverter_calls: list[tuple[str, float]] = []
        ha = _PublishingHA(events=events)
        optimizer = self._optimizer(ha)
        state = self._state(self._inputs())
        decision = self._decision(export_limit=7.0, import_limit=3.0, pv_max_power_limit=25.0)
        self._prepare_tick(
            optimizer,
            state,
            decision,
            events=events,
            inverter_calls=inverter_calls,
        )

        await optimizer._tick()

        self.assertEqual(events, ["apply", "publish"])
        self.assertEqual(
            inverter_calls,
            [("grid_export", 7.0), ("grid_import", 3.0), ("pv_max", 25.0)],
        )

    async def test_expires_at_uses_live_data_window_not_forecast_window(self) -> None:
        optimizer = self._optimizer(
            hvac_solar_data_max_age_seconds=120.0,
            hvac_solar_forecast_max_age_seconds=600.0,
        )
        evaluated_at = datetime(2026, 8, 4, 1, 2, 3, tzinfo=timezone.utc)

        result = optimizer._evaluate_hvac_solar_permission(
            self._state(self._inputs()),
            self._decision(),
            effective_mode=optimizer.cfg.automated_option,
            previous_result=None,
            evaluated_at=evaluated_at,
        )
        attrs = result.attributes()

        self.assertGreater(result.expires_at, result.evaluated_at)
        self.assertEqual(result.expires_at - result.evaluated_at, timedelta(seconds=120))
        self.assertIn("evaluated_at", attrs)
        self.assertIn("expires_at", attrs)

    async def test_confirmed_live_regression_uses_measured_opportunity_only(self) -> None:
        optimizer = self._optimizer()
        result = self._evaluate(
            optimizer,
            self._inputs(
                pv_kw=1.7,
                load_kw=0.9,
                battery_power_kw=0.8,
                solar_power_now_kw=5.2,
            ),
        )

        self.assertEqual(result.state, "blocked")
        self.assertEqual(result.reason_code, "insufficient_measured_surplus")
        self.assertEqual(result.source, "none")
        self.assertAlmostEqual(result.measured_opportunity_kw or 0.0, 0.8)
        self.assertAlmostEqual(result.estimated_opportunity_kw or 0.0, 4.3)

        attrs = result.attributes()
        self.assertFalse(attrs["estimated_opportunity_usable"])
        self.assertEqual(
            attrs["estimated_opportunity_rejection_reason"],
            "diagnostics_only",
        )

    async def test_solcast_only_opportunity_cannot_authorize_start_or_continue(
        self,
    ) -> None:
        optimizer = self._optimizer()
        previous = self._evaluate(optimizer, self._inputs())

        start_case = self._evaluate(
            optimizer,
            self._inputs(
                pv_kw=0.9,
                load_kw=0.9,
                solar_power_now_kw=5.2,
            ),
        )
        continue_case = self._evaluate(
            optimizer,
            self._inputs(
                pv_kw=0.8,
                load_kw=0.4,
                solar_power_now_kw=2.0,
            ),
            previous=previous,
        )

        self.assertEqual(start_case.state, "blocked")
        self.assertEqual(
            start_case.reason_code,
            "insufficient_measured_surplus",
        )
        self.assertEqual(continue_case.state, "blocked")
        self.assertEqual(
            continue_case.reason_code,
            "insufficient_measured_surplus",
        )

    async def test_measured_continue_is_not_promoted_by_solcast(self) -> None:
        optimizer = self._optimizer()
        previous = self._evaluate(optimizer, self._inputs())

        result = self._evaluate(
            optimizer,
            self._inputs(
                pv_kw=1.0,
                load_kw=0.4,
                solar_power_now_kw=2.0,
            ),
            previous=previous,
        )

        self.assertEqual(result.state, "continue")
        self.assertEqual(result.reason_code, "measured_opportunity_continue")
        self.assertEqual(result.source, "measured")

    async def test_missing_or_stale_solcast_remains_diagnostic_only(self) -> None:
        optimizer = self._optimizer()

        for solar_observation in (
            HVACObservedValue(),
            _stale(5.2),
        ):
            with self.subTest(solar_observation=solar_observation):
                inputs = replace(
                    self._inputs(
                        pv_kw=1.1,
                        load_kw=0.9,
                        solar_power_now_kw=5.2,
                    ),
                    solar_power_now=solar_observation,
                )

                result = self._evaluate(optimizer, inputs)

                self.assertEqual(result.state, "blocked")
                self.assertEqual(
                    result.reason_code,
                    "insufficient_measured_surplus",
                )
                self.assertTrue(result.data_fresh)

                attrs = result.attributes()
                self.assertFalse(attrs["estimated_opportunity_usable"])
                self.assertEqual(
                    attrs["estimated_opportunity_rejection_reason"],
                    "diagnostics_only",
                )

    async def test_restart_does_not_recreate_continue_from_ha_entity(self) -> None:
        cfg = Settings(_env_file=None)
        now = datetime.now(timezone.utc)
        ha = _BulkStateHA(
            {
                cfg.hvac_solar_permission_entity: self._ha_state(
                    "continue",
                    now,
                )
            }
        )
        optimizer = self._optimizer(ha)

        self.assertIsNone(
            optimizer._last_published_hvac_solar_permission_result
        )

        result = self._evaluate(
            optimizer,
            self._inputs(
                pv_kw=1.0,
                load_kw=0.4,
                solar_power_now_kw=2.0,
            ),
        )

        self.assertEqual(result.state, "blocked")
        self.assertEqual(
            result.reason_code,
            "insufficient_measured_surplus",
        )

    async def test_contract_scope_attributes_are_published_for_all_states(
        self,
    ) -> None:
        optimizer = self._optimizer()
        expected = {
            "scope": "solar_target_opportunity_only",
            "contract_version": "hvac_solar_permission_v2",
            "soc_policy_included": False,
            "consumer_safety_overlay_required": True,
            "controls_hvac_directly": False,
            "estimated_opportunity_usable": False,
            "estimated_opportunity_rejection_reason": "diagnostics_only",
        }

        results = (
            self._evaluate(optimizer, self._inputs()),
            optimizer._hvac_solar_cycle_error_result(),
        )

        for result in results:
            with self.subTest(state=result.state):
                attrs = result.attributes()
                for key, value in expected.items():
                    self.assertIn(key, attrs)
                    self.assertEqual(attrs[key], value)

if __name__ == "__main__":
    unittest.main()
