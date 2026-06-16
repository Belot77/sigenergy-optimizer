from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.state_store import StateStore


class StateStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self._tmp.name) / "state.db")
        self.store = StateStore(self.db_path)

    def tearDown(self) -> None:
        self.store.close()
        self._tmp.cleanup()

    def test_audit_round_trip(self) -> None:
        self.store.record_audit_event(
            action="config_update",
            source="api",
            actor="127.0.0.1",
            result="ok",
            target_key="export_limit_low",
            old_value={"value": 3.0},
            new_value={"value": 4.0},
            details={"note": "unit-test"},
        )
        rows = self.store.get_audit_events(limit=10)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["action"], "config_update")
        self.assertEqual(rows[0]["target_key"], "export_limit_low")
        self.assertEqual(rows[0]["old_value"], {"value": 3.0})
        self.assertEqual(rows[0]["new_value"], {"value": 4.0})

    def test_threshold_preset_crud(self) -> None:
        payload = {
            "export_threshold_low": 0.1,
            "import_threshold_low": 0.0,
            "export_limit_low": 3.0,
            "import_limit_low": 5.0,
        }
        self.store.save_threshold_preset("MyPreset", payload)
        one = self.store.get_threshold_preset("MyPreset")
        self.assertIsNotNone(one)
        self.assertEqual(one["name"], "MyPreset")
        self.assertEqual(one["payload"]["export_limit_low"], 3.0)

        listed = self.store.list_threshold_presets()
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["name"], "MyPreset")

        deleted = self.store.delete_threshold_preset("MyPreset")
        self.assertTrue(deleted)
        self.assertIsNone(self.store.get_threshold_preset("MyPreset"))

    def test_optimizer_import_topup_floor_uses_highest_actual_price_not_average(self) -> None:
        date = "2026-06-16"
        self.store.record_optimizer_import_topup(
            date=date,
            ts="2026-06-16T09:00:00+10:00",
            import_kwh=1.0,
            import_price=0.12,
            price_trusted=True,
        )
        self.store.record_optimizer_import_topup(
            date=date,
            ts="2026-06-16T10:00:00+10:00",
            import_kwh=0.5,
            import_price=0.16,
            price_trusted=True,
        )
        self.store.record_optimizer_import_topup(
            date=date,
            ts="2026-06-16T11:00:00+10:00",
            import_kwh=2.0,
            import_price=0.10,
            price_trusted=True,
        )

        summary = self.store.optimizer_import_topup_summary(date)

        self.assertAlmostEqual(summary["today_import_topup_kwh"], 3.5, places=3)
        self.assertAlmostEqual(summary["today_highest_actual_import_price"], 0.16, places=4)
        self.assertAlmostEqual(summary["import_cost_export_floor"], 0.16, places=4)
        self.assertTrue(summary["import_cost_floor_trusted"])

    def test_optimizer_import_topup_floor_persists_and_resets_by_day(self) -> None:
        first_day = "2026-06-16"
        next_day = "2026-06-17"
        self.store.record_optimizer_import_topup(
            date=first_day,
            ts="2026-06-16T09:00:00+10:00",
            import_kwh=1.0,
            import_price=0.16,
            price_trusted=True,
        )
        self.store.record_optimizer_import_topup(
            date=next_day,
            ts="2026-06-17T09:00:00+10:00",
            import_kwh=0.25,
            import_price=None,
            price_trusted=False,
        )

        self.store.close()
        self.store = StateStore(self.db_path)

        first_summary = self.store.optimizer_import_topup_summary(first_day)
        next_summary = self.store.optimizer_import_topup_summary(next_day)

        self.assertAlmostEqual(first_summary["import_cost_export_floor"], 0.16, places=4)
        self.assertTrue(first_summary["import_cost_floor_trusted"])
        self.assertIsNone(next_summary["import_cost_export_floor"])
        self.assertFalse(next_summary["import_cost_floor_trusted"])
        self.assertTrue(next_summary["import_cost_floor_unknown"])

    def test_zero_or_tiny_untrusted_import_does_not_poison_import_floor(self) -> None:
        date = "2026-06-16"
        self.store.record_optimizer_import_topup(
            date=date,
            ts="2026-06-16T09:00:00+10:00",
            import_kwh=0.0,
            import_price=None,
            price_trusted=False,
        )
        self.store.record_optimizer_import_topup(
            date=date,
            ts="2026-06-16T09:01:00+10:00",
            import_kwh=0.005,
            import_price=None,
            price_trusted=False,
        )

        summary = self.store.optimizer_import_topup_summary(date)

        self.assertAlmostEqual(summary["today_import_topup_kwh"], 0.005, places=3)
        self.assertIsNone(summary["import_cost_export_floor"])
        self.assertTrue(summary["import_cost_floor_trusted"])
        self.assertFalse(summary["import_cost_floor_unknown"])


if __name__ == "__main__":
    unittest.main()
