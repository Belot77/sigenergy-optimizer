from __future__ import annotations

import json
import sqlite3
import threading
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


class StateStore:
    def __init__(self, db_path: str) -> None:
        path = Path(db_path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS price_tracking (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  ts TEXT NOT NULL,
                  block_ts TEXT NOT NULL,
                  grid_import_kw REAL NOT NULL DEFAULT 0.0,
                  grid_export_kw REAL NOT NULL DEFAULT 0.0,
                  import_price REAL,
                  feedin_price REAL,
                  battery_soc REAL
                )
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_pt_block_ts ON price_tracking(block_ts)"
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_log (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  ts TEXT NOT NULL,
                  action TEXT NOT NULL,
                  source TEXT,
                  actor TEXT,
                  target_key TEXT,
                  old_value TEXT,
                  new_value TEXT,
                  result TEXT,
                  details TEXT
                )
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(ts)"
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS threshold_presets (
                  name TEXT PRIMARY KEY,
                  payload_json TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                )
                """
            )
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    @staticmethod
    def _json_dump(value: Any) -> str:
        return json.dumps(value, separators=(",", ":"), sort_keys=True)

    @staticmethod
    def _json_load(value: str | None) -> Any:
        if not value:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None

    def purge_old_price_tracking(self, retain_days: int = 14) -> int:
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM price_tracking WHERE ts < datetime('now', ?)",
                (f"-{retain_days} days",),
            )
            self._conn.commit()
            return cur.rowcount

    def record_price_event(
        self,
        ts: str,
        block_ts: str,
        grid_import_kw: float,
        grid_export_kw: float,
        import_price: float | None,
        feedin_price: float | None,
        battery_soc: float | None,
    ) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO price_tracking
                  (ts, block_ts, grid_import_kw, grid_export_kw, import_price, feedin_price, battery_soc)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (ts, block_ts, grid_import_kw, grid_export_kw, import_price, feedin_price, battery_soc),
            )
            self._conn.commit()

    def get_price_events(self, date: str | None = None, limit: int = 2000) -> list[dict[str, Any]]:
        with self._lock:
            if date:
                rows = self._conn.execute(
                    """SELECT ts, block_ts, grid_import_kw, grid_export_kw,
                              import_price, feedin_price, battery_soc
                       FROM price_tracking
                       WHERE block_ts LIKE ?
                       ORDER BY ts ASC LIMIT ?""",
                    (f"{date}%", limit),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    """SELECT ts, block_ts, grid_import_kw, grid_export_kw,
                              import_price, feedin_price, battery_soc
                       FROM price_tracking
                       ORDER BY ts DESC LIMIT ?""",
                    (limit,),
                ).fetchall()
        return [
            {
                "ts": r[0],
                "block_ts": r[1],
                "grid_import_kw": r[2],
                "grid_export_kw": r[3],
                "import_price": r[4],
                "feedin_price": r[5],
                "battery_soc": r[6],
            }
            for r in rows
        ]

    def daily_earnings_summary(self, date: str) -> dict[str, Any]:
        events = self.get_price_events(date=date, limit=20000)
        if not events:
            return {
                "date": date,
                "total_import_kwh": 0.0,
                "total_export_kwh": 0.0,
                "import_costs": 0.0,
                "export_earnings": 0.0,
                "net": 0.0,
                "blocks": [],
            }

        by_block: dict[str, list[dict]] = defaultdict(list)
        for e in events:
            by_block[e["block_ts"]].append(e)

        block_summaries = []
        total_import_kwh = 0.0
        total_export_kwh = 0.0
        total_import_costs = 0.0
        total_export_earnings = 0.0

        for block_ts in sorted(by_block):
            recs = sorted(by_block[block_ts], key=lambda x: x["ts"])
            try:
                block_start = datetime.fromisoformat(block_ts)
            except ValueError:
                continue
            block_end = block_start + timedelta(minutes=5)

            weighted_import = 0.0
            weighted_export = 0.0
            total_weight = 0.0
            block_import_price: float | None = None
            block_feedin_price: float | None = None

            for i, rec in enumerate(recs):
                try:
                    rec_ts = datetime.fromisoformat(rec["ts"])
                except ValueError:
                    continue
                next_ts = datetime.fromisoformat(recs[i + 1]["ts"]) if i + 1 < len(recs) else block_end
                seg_start = block_start if i == 0 else rec_ts
                seg_end = min(next_ts, block_end)
                duration = (seg_end - seg_start).total_seconds()
                if duration <= 0:
                    continue
                weighted_import += rec["grid_import_kw"] * duration
                weighted_export += rec["grid_export_kw"] * duration
                total_weight += duration
                if rec["import_price"] is not None:
                    block_import_price = rec["import_price"]
                if rec["feedin_price"] is not None:
                    block_feedin_price = rec["feedin_price"]

            if total_weight > 0:
                avg_import_kw = weighted_import / total_weight
                avg_export_kw = weighted_export / total_weight
                block_h = total_weight / 3600.0
            else:
                avg_import_kw = recs[0]["grid_import_kw"]
                avg_export_kw = recs[0]["grid_export_kw"]
                block_h = 5.0 / 60.0

            import_kwh = avg_import_kw * block_h
            export_kwh = avg_export_kw * block_h
            ip = block_import_price or 0.0
            fp = block_feedin_price or 0.0
            block_import_cost = import_kwh * ip
            block_export_earning = export_kwh * fp

            total_import_kwh += import_kwh
            total_export_kwh += export_kwh
            total_import_costs += block_import_cost
            total_export_earnings += block_export_earning

            block_summaries.append(
                {
                    "block_ts": block_ts,
                    "import_kwh": round(import_kwh, 4),
                    "export_kwh": round(export_kwh, 4),
                    "import_price": block_import_price,
                    "feedin_price": block_feedin_price,
                    "import_costs": round(block_import_cost, 4),
                    "export_earnings": round(block_export_earning, 4),
                    "net": round(block_export_earning - block_import_cost, 4),
                }
            )

        net = total_export_earnings - total_import_costs
        return {
            "date": date,
            "total_import_kwh": round(total_import_kwh, 3),
            "total_export_kwh": round(total_export_kwh, 3),
            "import_costs": round(total_import_costs, 4),
            "export_earnings": round(total_export_earnings, 4),
            "net": round(net, 4),
            "blocks": block_summaries,
        }

    def record_audit_event(
        self,
        *,
        action: str,
        source: str,
        actor: str,
        result: str,
        target_key: str | None = None,
        old_value: Any = None,
        new_value: Any = None,
        details: Any = None,
    ) -> None:
        ts = datetime.now().isoformat(timespec="seconds")
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO audit_log
                  (ts, action, source, actor, target_key, old_value, new_value, result, details)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ts,
                    action,
                    source,
                    actor,
                    target_key,
                    self._json_dump(old_value),
                    self._json_dump(new_value),
                    result,
                    self._json_dump(details),
                ),
            )
            self._conn.commit()

    def get_audit_events(self, limit: int = 200) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT ts, action, source, actor, target_key, old_value, new_value, result, details
                FROM audit_log
                ORDER BY ts DESC
                LIMIT ?
                """,
                (max(1, min(limit, 2000)),),
            ).fetchall()
        return [
            {
                "ts": r[0],
                "action": r[1],
                "source": r[2],
                "actor": r[3],
                "target_key": r[4],
                "old_value": self._json_load(r[5]),
                "new_value": self._json_load(r[6]),
                "result": r[7],
                "details": self._json_load(r[8]),
            }
            for r in rows
        ]

    def save_threshold_preset(self, name: str, payload: dict[str, Any]) -> None:
        cleaned = name.strip()
        if not cleaned:
            raise ValueError("Preset name is required")
        ts = datetime.now().isoformat(timespec="seconds")
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO threshold_presets (name, payload_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                  payload_json = excluded.payload_json,
                  updated_at = excluded.updated_at
                """,
                (cleaned, self._json_dump(payload), ts),
            )
            self._conn.commit()

    def get_threshold_preset(self, name: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT name, payload_json, updated_at FROM threshold_presets WHERE name = ?",
                (name.strip(),),
            ).fetchone()
        if not row:
            return None
        return {
            "name": row[0],
            "payload": self._json_load(row[1]) or {},
            "updated_at": row[2],
        }

    def list_threshold_presets(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT name, payload_json, updated_at FROM threshold_presets ORDER BY name ASC"
            ).fetchall()
        return [
            {
                "name": r[0],
                "payload": self._json_load(r[1]) or {},
                "updated_at": r[2],
            }
            for r in rows
        ]

    def delete_threshold_preset(self, name: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM threshold_presets WHERE name = ?",
                (name.strip(),),
            )
            self._conn.commit()
            return cur.rowcount > 0