from __future__ import annotations

import unittest

from app.forecast_utils import extract_forecast_entries, forecast_entry_time, forecast_entry_value
from app.routers.api import _serialize_forecast_curve


class ForecastUtilsTests(unittest.TestCase):
    def test_extract_prefers_detailed_primary_entity(self) -> None:
        bulk = {
            "sensor.amber_general_price": {
                "attributes": {
                    "forecasts": [
                        {"start_time": "2026-05-18T14:30:00+10:00", "per_kwh": 0.31},
                    ]
                }
            },
            "sensor.amber_general_price_detailed": {
                "attributes": {
                    "forecasts": [
                        {"start_time": "2026-05-18T14:30:00+10:00", "per_kwh": 0.31},
                        {"start_time": "2026-05-18T15:00:00+10:00", "per_kwh": 0.29},
                    ]
                }
            },
            "sensor.amber_general_forecast": {
                "attributes": {
                    "forecasts": [
                        {"start_time": "2026-05-18T14:30:00+10:00", "per_kwh": 0.28},
                    ]
                }
            },
        }

        entries = extract_forecast_entries(
            bulk,
            primary_entity="sensor.amber_general_price",
            explicit_entity="sensor.amber_general_forecast",
            preferred_attr="forecasts",
            preferred_time_key="start_time",
            preferred_value_key="per_kwh",
        )

        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[1]["per_kwh"], 0.29)

    def test_extract_falls_back_to_alternate_keys(self) -> None:
        bulk = {
            "sensor.amber_general_price_detailed": {
                "attributes": {
                    "forecast": [
                        {"time": "2026-05-18T17:00:00+10:00", "value": 0.42},
                    ]
                }
            }
        }

        entries = extract_forecast_entries(
            bulk,
            primary_entity="sensor.amber_general_price",
            explicit_entity="sensor.amber_general_forecast",
            preferred_attr="forecasts",
            preferred_time_key="start_time",
            preferred_value_key="per_kwh",
        )

        self.assertEqual(len(entries), 1)
        self.assertEqual(forecast_entry_time(entries[0], "start_time"), "2026-05-18T17:00:00+10:00")
        self.assertEqual(forecast_entry_value(entries[0], "per_kwh"), 0.42)

    def test_serialize_forecast_curve_uses_fallback_keys(self) -> None:
        curve = _serialize_forecast_curve(
            [{"time": "2026-05-18T17:30:00+10:00", "value": 0.38}],
            "start_time",
            "per_kwh",
        )

        self.assertEqual(curve, [{"t": "2026-05-18T17:30:00+10:00", "value": 0.38}])


if __name__ == "__main__":
    unittest.main()