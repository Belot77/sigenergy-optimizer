from __future__ import annotations

import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from app.state_store import StateStore


class StateStoreTests(unittest.TestCase):
    handoff = '{"version":1}'

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

    def test_solar_provider_handoff_is_replaced_and_consumed_across_reopens(self) -> None:
        replacement = '{"version":1,"revision":"later"}'
        self.assertIsNone(self.store.take_solar_provider_handoff())
        self.store.save_solar_provider_handoff(self.handoff)
        self.store.save_solar_provider_handoff(replacement)
        self.store.close()
        self.store = StateStore(self.db_path)
        self.assertEqual(self.store.take_solar_provider_handoff(), replacement)
        self.store.close()
        self.store = StateStore(self.db_path)
        self.assertIsNone(self.store.take_solar_provider_handoff())

    def test_solar_provider_handoff_migrates_an_existing_database(self) -> None:
        preset = {"export_limit_low": 3.0}
        self.store.save_threshold_preset("Existing", preset)
        self.store.close()
        with closing(sqlite3.connect(self.db_path)) as previous, previous:
            previous.execute("DROP TABLE solar_provider_handoff")

        self.store = StateStore(self.db_path)
        self.assertIsNone(self.store.take_solar_provider_handoff())
        self.store.save_solar_provider_handoff(self.handoff)
        self.assertEqual(self.store.take_solar_provider_handoff(), self.handoff)
        self.assertEqual(self.store.get_threshold_preset("Existing")["payload"], preset)

    def test_failed_handoff_commits_roll_back_replacement_and_consumption(self) -> None:
        self.store.save_solar_provider_handoff(self.handoff)
        connection = self.store._conn
        connection.execute("PRAGMA foreign_keys=ON")
        connection.executescript("""
            CREATE TEMP TABLE handoff_test_parent (id INTEGER PRIMARY KEY);
            CREATE TEMP TABLE handoff_test_child (
              parent_id INTEGER REFERENCES handoff_test_parent(id) DEFERRABLE INITIALLY DEFERRED
            );
            CREATE TEMP TRIGGER handoff_test_reject_update AFTER UPDATE ON main.solar_provider_handoff
            BEGIN INSERT INTO handoff_test_child VALUES (1); END;
            CREATE TEMP TRIGGER handoff_test_reject_delete AFTER DELETE ON main.solar_provider_handoff
            BEGIN INSERT INTO handoff_test_child VALUES (1); END;
        """)
        with self.assertRaisesRegex(sqlite3.IntegrityError, "FOREIGN KEY"):
            self.store.save_solar_provider_handoff('{"version":1,"revision":"rejected"}')
        self.assertFalse(connection.in_transaction)
        with self.assertRaisesRegex(sqlite3.IntegrityError, "FOREIGN KEY"):
            self.store.take_solar_provider_handoff()
        self.assertFalse(connection.in_transaction)

        self.store.close()
        self.store = StateStore(self.db_path)
        self.assertEqual(self.store.take_solar_provider_handoff(), self.handoff)

    def test_two_connections_cannot_take_the_same_solar_provider_handoff(self) -> None:
        self.store.save_solar_provider_handoff(self.handoff)
        barrier = threading.Barrier(2)

        def take(store: StateStore) -> str | None:
            barrier.wait(timeout=5)
            return store.take_solar_provider_handoff()

        with closing(StateStore(self.db_path)) as other, ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(take, self.store)
            second = executor.submit(take, other)
            self.assertCountEqual([first.result(timeout=5), second.result(timeout=5)], [self.handoff, None])

    def test_solar_provider_host_boot_id_requires_a_canonical_linux_uuid(self) -> None:
        boot_id = "581c1e02-1b30-41d9-a5ec-2ccf68636727"
        for raw, expected in (
            (boot_id + "\n", boot_id),
            (boot_id.upper() + "\n", None),
            (boot_id + "x\n", None),
            ("unavailable\n", None),
        ):
            with self.subTest(raw=raw), patch.object(Path, "open", autospec=True, return_value=StringIO(raw)) as opened:
                self.assertEqual(self.store.solar_provider_host_boot_id(), expected)
                opened.assert_called_once_with(Path("/proc/sys/kernel/random/boot_id"), encoding="ascii")
        with patch.object(Path, "open", side_effect=FileNotFoundError):
            self.assertIsNone(self.store.solar_provider_host_boot_id())

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
