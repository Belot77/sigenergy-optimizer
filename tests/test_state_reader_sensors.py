from __future__ import annotations

import types
import unittest

from app.config import Settings
from app.state_reader import read_state_snapshot


class _BulkHA:
    def __init__(self, bulk: dict[str, dict]) -> None:
        self._bulk = bulk
        self.requests: list[list[str]] = []

    async def bulk_states(self, entity_ids: list[str]) -> dict[str, dict]:
        self.requests.append(list(entity_ids))
        return self._bulk


class StateReaderSensorTests(unittest.IsolatedAsyncioTestCase):
    def _optimizer(self, bulk: dict[str, dict], **cfg_overrides):
        cfg = Settings(
            grid_import_power_sensor="sensor.grid_import_power",
            grid_export_power_sensor="sensor.grid_export_power",
            **cfg_overrides,
        )
        return types.SimpleNamespace(
            cfg=cfg,
            ha=_BulkHA(bulk),
            _last_state=None,
            _manual_mode_override=None,
            _last_hw_charge_cap_kw=None,
            _last_hw_discharge_cap_kw=None,
            _valid_hw_cap_kw=lambda value: isinstance(value, (int, float)) and 0 < float(value) < 900,
            _warn_parse_issue=lambda *args, **kwargs: None,
        )

    async def test_populates_import_and_export_independently_from_separate_sensors(self) -> None:
        optimizer = self._optimizer(
            {
                "sensor.grid_import_power": {"state": "1200", "attributes": {}},
                "sensor.grid_export_power": {"state": "450", "attributes": {}},
            }
        )

        state = await read_state_snapshot(optimizer, mode_max_self="Maximum Self Consumption")

        self.assertEqual(state.grid_import_power_kw, 1.2)
        self.assertEqual(state.grid_export_power_kw, 0.45)

    async def test_does_not_assume_single_signed_grid_sensor(self) -> None:
        optimizer = self._optimizer(
            {
                "sensor.grid_import_power": {"state": "2.5", "attributes": {}},
                "sensor.grid_export_power": {"state": "300", "attributes": {}},
            }
        )

        state = await read_state_snapshot(optimizer, mode_max_self="Maximum Self Consumption")

        self.assertEqual(state.grid_import_power_kw, 2.5)
        self.assertEqual(state.grid_export_power_kw, 0.3)
        self.assertGreater(state.grid_import_power_kw, 0)
        self.assertGreater(state.grid_export_power_kw, 0)


if __name__ == "__main__":
    unittest.main()