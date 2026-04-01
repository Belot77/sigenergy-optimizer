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


if __name__ == "__main__":
    unittest.main()
