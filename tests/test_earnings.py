from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta, timezone

from app.earnings import EarningsSource, _cumulative_delta, _is_plausible_summary, preferred_auto_source_keys, summarize_cumulative_source, summarize_daily_source, summarize_lagged_daily_source, summarize_shifted_cumulative_source


TZ = timezone(timedelta(hours=10, minutes=30))


class EarningsTests(unittest.TestCase):
    def test_auto_source_prefers_sigenergy_for_today(self) -> None:
        today = date(2026, 4, 4)
        self.assertEqual(
            preferred_auto_source_keys(today, today),
            ["sigenergy_daily", "estimated", "amber_balance"],
        )

    def test_auto_source_prefers_amber_for_history(self) -> None:
        self.assertEqual(
            preferred_auto_source_keys(date(2026, 4, 3), date(2026, 4, 4)),
            ["amber_balance", "sigenergy_daily", "estimated"],
        )

    def test_cumulative_delta_handles_counter_reset(self) -> None:
        series = [
            {"state": "111.73", "last_updated": "2026-04-02T09:22:55+10:30"},
            {"state": "0.00", "last_updated": "2026-04-03T09:22:55+10:30"},
        ]
        start = datetime.fromisoformat("2026-04-02T00:00:00+10:30")
        end = datetime.fromisoformat("2026-04-03T23:59:59+10:30")
        self.assertEqual(_cumulative_delta(series, start, end), 0.0)

    def test_shifted_cumulative_amber_source_shifts_values_forward_one_day(self) -> None:
        source = EarningsSource(
            key="amber_balance",
            label="Amber Balance",
            mode="cumulative_shifted",
            import_energy_entity="sensor.import_kwh",
            export_energy_entity="sensor.export_kwh",
            import_value_entity="sensor.import",
            export_value_entity="sensor.export",
        )
        by_entity = {
            "sensor.import_kwh": [
                {"entity_id": "sensor.import_kwh", "state": "0.00", "last_updated": "2026-04-03T09:22:55+10:30"},
                {"entity_id": "sensor.import_kwh", "state": "1.63", "last_updated": "2026-04-04T09:22:55+10:30"},
            ],
            "sensor.export_kwh": [
                {"entity_id": "sensor.export_kwh", "state": "111.73", "last_updated": "2026-04-03T09:22:55+10:30"},
                {"entity_id": "sensor.export_kwh", "state": "171.96", "last_updated": "2026-04-04T09:22:55+10:30"},
            ],
            "sensor.import": [
                {"entity_id": "sensor.import", "state": "0.00", "last_updated": "2026-04-03T09:22:55+10:30"},
                {"entity_id": "sensor.import", "state": "0.32", "last_updated": "2026-04-04T09:22:55+10:30"},
            ],
            "sensor.export": [
                {"entity_id": "sensor.export", "state": "-7.55", "last_updated": "2026-04-03T09:22:55+10:30"},
                {"entity_id": "sensor.export", "state": "-10.38", "last_updated": "2026-04-04T09:22:55+10:30"},
            ],
        }
        summary = summarize_shifted_cumulative_source(source, "2026-04-03", by_entity, TZ)
        self.assertIsNotNone(summary)
        self.assertAlmostEqual(summary["total_import_kwh"], 1.63, places=3)
        self.assertAlmostEqual(summary["total_export_kwh"], 60.23, places=3)
        self.assertAlmostEqual(summary["import_costs"], 0.32, places=4)
        self.assertAlmostEqual(summary["export_earnings"], 2.83, places=4)

    def test_plausibility_rejects_large_or_negative_values(self) -> None:
        self.assertFalse(_is_plausible_summary({"total_import_kwh": -1, "total_export_kwh": 1, "import_costs": 1, "export_earnings": 1}))
        self.assertFalse(_is_plausible_summary({"total_import_kwh": 1, "total_export_kwh": 500, "import_costs": 1, "export_earnings": 1}))
        self.assertTrue(_is_plausible_summary({"total_import_kwh": 1, "total_export_kwh": 50, "import_costs": 1, "export_earnings": 1}))

    def test_cumulative_amber_source_uses_daily_deltas(self) -> None:
        source = EarningsSource(
            key="amber_balance",
            label="Amber Balance",
            mode="cumulative",
            import_energy_entity="sensor.import_kwh",
            export_energy_entity="sensor.export_kwh",
            import_value_entity="sensor.import",
            export_value_entity="sensor.export",
        )
        by_entity = {
            "sensor.import_kwh": [
                {"entity_id": "sensor.import_kwh", "state": "0.00", "last_updated": "2026-04-02T23:59:00+10:30"},
                {"entity_id": "sensor.import_kwh", "state": "1.63", "last_updated": "2026-04-03T23:50:00+10:30"},
            ],
            "sensor.export_kwh": [
                {"entity_id": "sensor.export_kwh", "state": "111.73", "last_updated": "2026-04-02T23:59:00+10:30"},
                {"entity_id": "sensor.export_kwh", "state": "171.96", "last_updated": "2026-04-03T23:50:00+10:30"},
            ],
            "sensor.import": [
                {"entity_id": "sensor.import", "state": "0.00", "last_updated": "2026-04-02T23:59:00+10:30"},
                {"entity_id": "sensor.import", "state": "0.32", "last_updated": "2026-04-03T23:50:00+10:30"},
            ],
            "sensor.export": [
                {"entity_id": "sensor.export", "state": "-7.55", "last_updated": "2026-04-02T23:59:00+10:30"},
                {"entity_id": "sensor.export", "state": "-10.38", "last_updated": "2026-04-03T23:50:00+10:30"},
            ],
        }

        summary = summarize_cumulative_source(source, "2026-04-03", by_entity, TZ)
        self.assertIsNotNone(summary)
        self.assertEqual(summary["source_key"], "amber_balance")
        self.assertAlmostEqual(summary["total_import_kwh"], 1.63, places=3)
        self.assertAlmostEqual(summary["total_export_kwh"], 60.23, places=3)
        self.assertAlmostEqual(summary["import_costs"], 0.32, places=4)
        self.assertAlmostEqual(summary["export_earnings"], 2.83, places=4)
        self.assertAlmostEqual(summary["net"], 2.51, places=4)

    def test_daily_sigenergy_source_uses_latest_value_in_day(self) -> None:
        source = EarningsSource(
            key="sigenergy_daily",
            label="Sigenergy Daily Totals",
            mode="daily",
            import_energy_entity="sensor.daily_import",
            export_energy_entity="sensor.daily_export",
            import_value_entity="sensor.daily_import_cost",
            export_value_entity="sensor.daily_export_comp",
        )
        by_entity = {
            "sensor.daily_import": [
                {"entity_id": "sensor.daily_import", "state": "5.0", "last_updated": "2026-04-04T08:00:00+10:30"},
                {"entity_id": "sensor.daily_import", "state": "20.84", "last_updated": "2026-04-04T17:06:34+10:30"},
            ],
            "sensor.daily_export": [
                {"entity_id": "sensor.daily_export", "state": "0.4", "last_updated": "2026-04-04T17:29:37+10:30"},
            ],
            "sensor.daily_import_cost": [
                {"entity_id": "sensor.daily_import_cost", "state": "2.614666", "last_updated": "2026-04-04T17:06:34+10:30"},
            ],
            "sensor.daily_export_comp": [
                {"entity_id": "sensor.daily_export_comp", "state": "0.014719", "last_updated": "2026-04-04T17:29:37+10:30"},
            ],
        }

        summary = summarize_daily_source(source, "2026-04-04", by_entity, TZ)
        self.assertIsNotNone(summary)
        self.assertEqual(summary["source_key"], "sigenergy_daily")
        self.assertAlmostEqual(summary["total_import_kwh"], 20.84, places=3)
        self.assertAlmostEqual(summary["total_export_kwh"], 0.4, places=3)
        self.assertAlmostEqual(summary["import_costs"], 2.6147, places=4)
        self.assertAlmostEqual(summary["export_earnings"], 0.0147, places=4)

    def test_lagged_daily_amber_source_shifts_to_prior_day(self) -> None:
        source = EarningsSource(
            key="amber_balance",
            label="Amber Balance",
            mode="daily_lagged",
            import_energy_entity="sensor.import_kwh",
            export_energy_entity="sensor.export_kwh",
            import_value_entity="sensor.import",
            export_value_entity="sensor.export",
        )
        by_entity = {
            "sensor.import_kwh": [
                {"entity_id": "sensor.import_kwh", "state": "0.00", "last_updated": "2026-04-03T09:22:55+10:30"},
                {"entity_id": "sensor.import_kwh", "state": "1.63", "last_updated": "2026-04-04T09:22:55+10:30"},
            ],
            "sensor.export_kwh": [
                {"entity_id": "sensor.export_kwh", "state": "47.96", "last_updated": "2026-04-03T09:22:55+10:30"},
                {"entity_id": "sensor.export_kwh", "state": "60.23", "last_updated": "2026-04-04T09:22:55+10:30"},
            ],
            "sensor.import": [
                {"entity_id": "sensor.import", "state": "0.00", "last_updated": "2026-04-03T09:22:55+10:30"},
                {"entity_id": "sensor.import", "state": "0.32", "last_updated": "2026-04-04T09:22:55+10:30"},
            ],
            "sensor.export": [
                {"entity_id": "sensor.export", "state": "-2.75", "last_updated": "2026-04-03T09:22:55+10:30"},
                {"entity_id": "sensor.export", "state": "-2.83", "last_updated": "2026-04-04T09:22:55+10:30"},
            ],
        }

        summary = summarize_lagged_daily_source(source, "2026-04-03", by_entity, TZ)
        self.assertIsNotNone(summary)
        self.assertEqual(summary["date"], "2026-04-03")
        self.assertAlmostEqual(summary["total_import_kwh"], 1.63, places=3)
        self.assertAlmostEqual(summary["total_export_kwh"], 60.23, places=3)
        self.assertAlmostEqual(summary["import_costs"], 0.32, places=4)
        self.assertAlmostEqual(summary["export_earnings"], 2.83, places=4)


if __name__ == "__main__":
    unittest.main()