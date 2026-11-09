from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import WebSocketDisconnect

from app.config import Settings
from app.models import Decision, HVACObservedValue, HVACSolarInputContext, SolarState
from app.optimizer import SigEnergyOptimizer
from app.routers.api import get_status, ws_status


NOW = datetime(2026, 1, 15, 2, 0, tzinfo=timezone.utc)
POWER_ROWS = ("grid_export", "grid_import", "ess_charge")


def _reported(value: float, *, age: float = 12.0) -> HVACObservedValue:
    return HVACObservedValue(
        value=value,
        available=True,
        fresh=True,
        observed_at_ts=(NOW - timedelta(seconds=age)).timestamp(),
    )


class DashboardPowerStatusTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.opt = SigEnergyOptimizer.__new__(SigEnergyOptimizer)
        self.opt.cfg = Settings(
            _env_file=None,
            hvac_solar_data_max_age_seconds=120.0,
            block_flow_limit_value=0.01,
            ess_charge_limit_value=25.0,
            ess_discharge_limit_value=25.0,
        )
        self.opt._ws_connected = True
        self.opt._manual_mode_override = ""
        self.opt._manual_ess_charge_override_kw = None
        self.opt._manual_ess_discharge_override_kw = None
        self.opt._last_decision = Decision(
            export_limit=7.5,
            import_limit=0.0,
            ess_charge_limit=11.5,
            battery_power_kw=19.2,
            trace_gates={"observed_automated_control_mode": True},
        )
        self.opt._last_state = SolarState(
            timestamp=NOW - timedelta(seconds=10),
            sigenergy_mode=self.opt.cfg.automated_option,
            sigenergy_mode_observed=True,
            current_export_limit=5.5,
            current_import_limit=0.0,
            current_import_limit_observed=True,
            current_import_limit_observation=_reported(0.0),
            current_ess_charge_limit=9.5,
            current_ess_charge_limit_observation=_reported(9.5),
            grid_export_power_kw=3.5,
            grid_import_power_kw=0.0,
            battery_power_sensor_kw=-2.5,
            ess_max_charge_kw=25.0,
            ess_max_discharge_kw=25.0,
            hvac_solar_inputs=HVACSolarInputContext(
                control_mode=HVACObservedValue(
                    value=self.opt.cfg.automated_option, available=True, fresh=True,
                ),
                observed_export_limit=_reported(5.5),
                grid_export_power=_reported(3.5),
                grid_import_power=_reported(0.0),
                battery_power=_reported(-2.5),
                live_snapshot=True,
            ),
        )

    async def _status(self) -> dict:
        app = SimpleNamespace(
            state=SimpleNamespace(
                optimizer=self.opt, ha=SimpleNamespace(ping=AsyncMock(return_value=True))
            )
        )
        websocket = SimpleNamespace(
            app=app,
            accept=AsyncMock(),
            send_json=AsyncMock(side_effect=WebSocketDisconnect()),
        )
        with patch("app.routers.api.datetime", wraps=datetime) as clock:
            clock.now.return_value = NOW
            rest = await get_status(SimpleNamespace(app=app))
            await ws_status(websocket)

        websocket.accept.assert_awaited_once()
        websocket.send_json.assert_awaited_once()
        frame = websocket.send_json.await_args.args[0]
        for key in (
            "power_status", "sigenergy_mode", "export_limit", "import_limit",
            "ess_charge_limit", "grid_export_power_kw", "grid_import_power_kw",
            "battery_power_sensor_kw", "battery_power_kw",
        ):
            self.assertEqual(rest[key], frame[key], key)
        return rest

    def _assert_row(self, status, name, target, source, limit, limit_status, power, power_status):
        self.assertEqual(
            status["power_status"][name],
            {
                "target_kw": target,
                "target_source": source,
                "ha_limit_kw": limit,
                "ha_limit_status": limit_status,
                "measured_power_kw": power,
                "measured_power_status": power_status,
            },
        )

    async def test_automated_targets_readbacks_and_measured_values_are_independent(self) -> None:
        status = await self._status()

        self.assertEqual(status["power_status"]["snapshot_age_seconds"], 10.0)
        self._assert_row(status, "grid_export", 7.5, "optimizer", 5.5, "reported", 3.5, "reported")
        self._assert_row(status, "grid_import", 0.0, "optimizer", 0.0, "reported", 0.0, "reported")
        self._assert_row(status, "ess_charge", 11.5, "optimizer", 9.5, "reported", -2.5, "reported")
        self.assertEqual(status["export_limit"], 5.5)
        self.assertEqual(status["effective_import_setpoint"], 0.01)
        self.assertEqual(status["battery_power_sensor_kw"], -2.5)

    async def test_force_and_prevent_display_existing_preset_targets(self) -> None:
        for mode, export in (
            (self.opt.cfg.full_export_option, 25.0),
            (self.opt.cfg.block_flow_option, 0.01),
        ):
            with self.subTest(mode=mode):
                self.opt._manual_mode_override = mode
                status = await self._status()

                self.assertEqual(status["sigenergy_mode"], mode)
                self._assert_row(status, "grid_export", export, "preset", 5.5, "reported", 3.5, "reported")
                self._assert_row(status, "grid_import", 0.01, "preset", 0.0, "reported", 0.0, "reported")
                self._assert_row(status, "ess_charge", 25.0, "preset", 9.5, "reported", -2.5, "reported")
                self.assertEqual(status["export_limit"], export)
                self.assertEqual(status["import_limit"], 0.01)
                self.assertEqual(status["ess_charge_limit"], 25.0)

    async def test_stale_unverified_and_unavailable_observations_have_no_value(self) -> None:
        state = self.opt.last_state
        state.current_import_limit_observed = False
        state.current_import_limit_observation = replace(_reported(0.0, age=121), fresh=False)
        state.current_ess_charge_limit_observation = _reported(float("nan"))
        state.hvac_solar_inputs = replace(
            state.hvac_solar_inputs,
            observed_export_limit=_reported(5.5, age=121),
            grid_export_power=replace(_reported(3.5), observed_at_ts=None),
            grid_import_power=HVACObservedValue(),
            battery_power=HVACObservedValue(),
        )

        status = await self._status()

        self._assert_row(status, "grid_export", 7.5, "optimizer", None, "stale", None, "unverified")
        self._assert_row(status, "grid_import", 0.0, "optimizer", None, "stale", None, "unavailable")
        self._assert_row(status, "ess_charge", 11.5, "optimizer", None, "unverified", None, "unavailable")
        self.assertEqual(status["grid_import_power_kw"], 0.0)
        self.assertEqual(status["battery_power_sensor_kw"], -2.5)

    async def test_old_snapshot_cannot_supply_current_observations(self) -> None:
        state = self.opt.last_state
        state.timestamp = NOW - timedelta(seconds=70)
        state.current_import_limit_observation = _reported(0.0, age=72)
        state.current_ess_charge_limit_observation = _reported(9.5, age=72)
        state.hvac_solar_inputs = HVACSolarInputContext(
            observed_export_limit=_reported(5.5, age=72),
            grid_export_power=_reported(3.5, age=72),
            grid_import_power=_reported(0.0, age=72),
            battery_power=_reported(-2.5, age=72),
            live_snapshot=True,
        )

        with patch("app.routers.api.settings.poll_interval_seconds", 30):
            status = await self._status()

        self.assertEqual(status["power_status"]["snapshot_age_seconds"], 70.0)
        for name in POWER_ROWS:
            row = status["power_status"][name]
            self.assertIsNone(row["ha_limit_kw"], name)
            self.assertEqual(row["ha_limit_status"], "stale", name)
            self.assertIsNone(row["measured_power_kw"], name)
            self.assertEqual(row["measured_power_status"], "stale", name)

    async def test_manual_and_previous_manual_decision_have_no_automated_target(self) -> None:
        self.opt._manual_mode_override = self.opt.cfg.manual_option
        manual = await self._status()
        self.opt._manual_mode_override = ""
        self.opt.last_decision.trace_gates["observed_automated_control_mode"] = False
        returned_to_auto = await self._status()

        for status in (manual, returned_to_auto):
            self._assert_row(status, "grid_export", None, None, 5.5, "reported", 3.5, "reported")
            self._assert_row(status, "grid_import", None, None, 0.0, "reported", 0.0, "reported")
            self._assert_row(status, "ess_charge", None, None, 9.5, "reported", -2.5, "reported")

    async def test_missing_snapshot_does_not_reuse_automated_decision_as_evidence(self) -> None:
        self.opt._last_state = None

        status = await self._status()

        self.assertIsNone(status["power_status"]["snapshot_age_seconds"])
        for name in POWER_ROWS:
            self._assert_row(status, name, None, None, None, "unavailable", None, "unavailable")
        self.assertEqual(status["export_limit"], 7.5)
        self.assertEqual(status["battery_power_kw"], 19.2)

    async def test_cached_or_overwritten_automated_mode_does_not_supply_target(self) -> None:
        state = self.opt.last_state
        state.sigenergy_mode_observed = False
        cached = await self._status()

        state.sigenergy_mode_observed = True
        state.hvac_solar_inputs = replace(
            state.hvac_solar_inputs,
            control_mode=replace(
                state.hvac_solar_inputs.control_mode, value=self.opt.cfg.manual_option,
            ),
        )
        overwritten = await self._status()

        for status in (cached, overwritten):
            self.assertEqual(status["sigenergy_mode"], self.opt.cfg.automated_option)
            self._assert_row(status, "grid_export", None, None, 5.5, "reported", 3.5, "reported")

    async def test_read_state_retains_the_import_limit_report_without_actuation(self) -> None:
        from haos49_characterization_helpers import Haos49CharacterizationCase, RecordingHA

        fixture = Haos49CharacterizationCase("runTest")
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        optimizer = fixture.optimizer()
        entity = optimizer.cfg.grid_import_limit
        report_time = NOW - timedelta(seconds=5)
        ha = RecordingHA({entity: {
            "state": "0.0",
            "attributes": {},
            "last_updated": report_time.isoformat(),
            "last_reported": report_time.isoformat(),
        }})
        optimizer.ha = ha

        with fixture.optimizer_time(NOW):
            state = await optimizer._read_state()

        self.assertEqual(state.current_import_limit_observation, _reported(0.0, age=5))
        self.assertTrue(state.current_import_limit_observed)
        self.assertEqual(state.current_import_limit, 0.0)
        self.assertEqual(ha.calls, [])
