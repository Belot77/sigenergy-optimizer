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

    def test_extract_supports_v2_primary_sensor_detailed_forecast(self) -> None:
        bulk = {
            "sensor.amber_express_home_general_price": {
                "state": "0.25",
                "attributes": {
                    "detailedForecast": [
                        {"time": "2026-05-18T18:00:00+10:00", "value": 0.25},
                        {"time": "2026-05-18T18:30:00+10:00", "value": 0.27},
                    ]
                },
            }
        }

        entries = extract_forecast_entries(
            bulk,
            primary_entity="sensor.amber_express_home_general_price",
            explicit_entity="sensor.amber_express_home_general_price_detailed",
            preferred_attr="forecasts",
            preferred_time_key="start_time",
            preferred_value_key="per_kwh",
        )

        self.assertEqual(len(entries), 2)
        self.assertEqual(forecast_entry_time(entries[0], "start_time"), "2026-05-18T18:00:00+10:00")
        self.assertEqual(forecast_entry_value(entries[0], "per_kwh"), 0.25)

    def test_extract_derives_primary_from_missing_detailed_entity(self) -> None:
        bulk = {
            "sensor.amber_express_home_feed_in_price": {
                "state": "0.08",
                "attributes": {
                    "detailedForecast": [
                        {"time": "2026-05-18T19:00:00+10:00", "value": 0.08},
                    ]
                },
            }
        }

        diagnostics: dict = {}
        entries = extract_forecast_entries(
            bulk,
            primary_entity="",
            explicit_entity="sensor.amber_express_home_feed_in_price_detailed",
            preferred_attr="forecasts",
            preferred_time_key="start_time",
            preferred_value_key="per_kwh",
            diagnostics=diagnostics,
        )

        self.assertEqual(len(entries), 1)
        self.assertEqual(diagnostics["selected_entity"], "sensor.amber_express_home_feed_in_price")
        self.assertIn("sensor.amber_express_home_feed_in_price_detailed", diagnostics["missing_entities"])

    def test_extract_falls_back_from_configured_forecasts_to_detailed_forecast(self) -> None:
        bulk = {
            "sensor.amber_express_home_general_price_detailed": {
                "state": "0.16",
                "attributes": {
                    "detailedForecast": [
                        {"time": "2026-05-18T20:00:00+10:00", "value": 0.16},
                    ]
                },
            }
        }

        entries = extract_forecast_entries(
            bulk,
            primary_entity="sensor.amber_express_home_general_price",
            explicit_entity="sensor.amber_express_home_general_price_detailed",
            preferred_attr="forecasts",
            preferred_time_key="start_time",
            preferred_value_key="per_kwh",
        )

        self.assertEqual(len(entries), 1)
        self.assertEqual(forecast_entry_time(entries[0], "start_time"), "2026-05-18T20:00:00+10:00")
        self.assertEqual(forecast_entry_value(entries[0], "per_kwh"), 0.16)

    def test_extract_bad_forecast_data_fails_safely_with_diagnostics(self) -> None:
        bulk = {
            "sensor.amber_express_home_general_price": {
                "state": "0.30",
                "attributes": {
                    "detailedForecast": [
                        {"unexpected_time": "2026-05-18T21:00:00+10:00", "unexpected_value": 0.30},
                    ]
                },
            }
        }

        diagnostics: dict = {}
        entries = extract_forecast_entries(
            bulk,
            primary_entity="sensor.amber_express_home_general_price",
            explicit_entity="sensor.amber_express_home_general_price_detailed",
            preferred_attr="forecasts",
            preferred_time_key="start_time",
            preferred_value_key="per_kwh",
            diagnostics=diagnostics,
        )

        self.assertEqual(entries, [])
        self.assertIsNone(diagnostics["selected_entity"])
        self.assertIn("detailedForecast", diagnostics["attributes_tried"])
        self.assertIn("time", diagnostics["time_keys_tried"])
        self.assertIn("value", diagnostics["value_keys_tried"])
        self.assertIn("no forecast entries", diagnostics["failure_reason"])

    def test_serialize_forecast_curve_uses_fallback_keys(self) -> None:
        curve = _serialize_forecast_curve(
            [{"time": "2026-05-18T17:30:00+10:00", "value": 0.38}],
            "start_time",
            "per_kwh",
        )

        self.assertEqual(curve, [{"t": "2026-05-18T17:30:00+10:00", "value": 0.38}])


if __name__ == "__main__":
    unittest.main()
