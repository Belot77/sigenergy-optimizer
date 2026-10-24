from __future__ import annotations

import json
import math
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
                CREATE TABLE IF NOT EXISTS optimizer_import_topup (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  date TEXT NOT NULL,
                  ts TEXT NOT NULL,
                  import_kwh REAL NOT NULL DEFAULT 0.0,
                  import_price REAL,
                  price_trusted INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_oit_date ON optimizer_import_topup(date)"
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS optimizer_import_interval (
                  event_id TEXT PRIMARY KEY,
                  date TEXT NOT NULL,
                  ts TEXT NOT NULL,
                  import_kwh REAL NOT NULL,
                  import_price REAL,
                  price_trusted INTEGER NOT NULL,
                  payload_json TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_oii_date ON optimizer_import_interval(date)"
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS optimizer_import_checkpoint (
                  singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                  event_id TEXT NOT NULL,
                  checkpoint_json TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS optimizer_import_coverage (
                  date TEXT PRIMARY KEY,
                  unknown INTEGER NOT NULL,
                  reason TEXT NOT NULL
                )
                """
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

    def record_optimizer_import_topup(
        self,
        *,
        date: str,
        ts: str,
        import_kwh: float,
        import_price: float | None,
        price_trusted: bool,
    ) -> None:
        stored_import_price: float | None = None
        if import_price is not None:
            try:
                price_candidate = float(import_price)
                if math.isfinite(price_candidate):
                    stored_import_price = price_candidate
            except (TypeError, ValueError, OverflowError):
                pass
        stored_price_trusted = bool(price_trusted and stored_import_price is not None)

        with self._lock:
            try:
                self._conn.execute(
                    """
                    INSERT INTO optimizer_import_topup
                      (date, ts, import_kwh, import_price, price_trusted)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        date,
                        ts,
                        max(0.0, float(import_kwh or 0.0)),
                        stored_import_price,
                        1 if stored_price_trusted else 0,
                    ),
                )
                self._conn.commit()
            except BaseException:
                self._conn.rollback()
                raise

    def record_optimizer_import_interval(self, event: dict[str, Any]) -> None:
        """Atomically append one immutable interval and advance its coverage/checkpoint."""
        # Freeze the caller's payload before acquiring the lock. Reject non-finite
        # JSON numbers rather than silently changing a retried interval's evidence.
        payload_json = json.dumps(event, separators=(",", ":"), sort_keys=True, allow_nan=False)
        payload = json.loads(payload_json)
        event_id = payload["event_id"]
        import_kwh = payload["import_kwh"]
        import_price = payload["import_price"]
        if not isinstance(event_id, str) or not event_id:
            raise ValueError("Interval event_id must be a nonempty string")
        if isinstance(import_kwh, bool) or not isinstance(import_kwh, (int, float)) or import_kwh < 0:
            raise ValueError("Interval import_kwh must be finite and nonnegative")
        if import_price is not None and (
            isinstance(import_price, bool) or not isinstance(import_price, (int, float))
        ):
            raise ValueError("Interval import_price must be finite or None")
        if not isinstance(payload["price_trusted"], bool):
            raise ValueError("Interval price_trusted must be boolean")
        if payload["price_trusted"] and import_price is None:
            raise ValueError("Trusted interval requires an import price")
        checkpoint_json = json.dumps(
            payload["checkpoint"], separators=(",", ":"), sort_keys=True, allow_nan=False,
        )
        with self._lock:
            try:
                self._conn.execute("BEGIN")
                existing = self._conn.execute(
                    "SELECT payload_json FROM optimizer_import_interval WHERE event_id = ?",
                    (event_id,),
                ).fetchone()
                if existing is not None:
                    if existing[0] != payload_json:
                        raise ValueError("Interval event_id was reused with a different payload")
                    # An acknowledged replay must not rewind a later checkpoint.
                    self._conn.rollback()
                    return
                self._conn.execute(
                    """INSERT INTO optimizer_import_interval
                       (event_id, date, ts, import_kwh, import_price, price_trusted, payload_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (event_id, payload["date"], payload["ts"], import_kwh,
                     import_price, int(payload["price_trusted"]), payload_json),
                )
                self._conn.execute(
                    """INSERT INTO optimizer_import_checkpoint (singleton, event_id, checkpoint_json)
                       VALUES (1, ?, ?)
                       ON CONFLICT(singleton) DO UPDATE SET
                         event_id = excluded.event_id, checkpoint_json = excluded.checkpoint_json""",
                    (event_id, checkpoint_json),
                )
                for day, reason in payload["unknown_days"].items():
                    self._conn.execute(
                        """INSERT INTO optimizer_import_coverage (date, unknown, reason)
                           VALUES (?, 1, ?)
                           ON CONFLICT(date) DO UPDATE SET unknown = 1,
                             reason = CASE WHEN optimizer_import_coverage.unknown = 1
                               THEN optimizer_import_coverage.reason ELSE excluded.reason END""",
                        (day, reason),
                    )
                for day in payload["complete_days"]:
                    self._conn.execute(
                        """INSERT OR IGNORE INTO optimizer_import_coverage (date, unknown, reason)
                           VALUES (?, 0, 'continuous_coverage')""",
                        (day,),
                    )
                if payload["date"] not in payload["complete_days"]:
                    self._conn.execute(
                        """INSERT OR IGNORE INTO optimizer_import_coverage (date, unknown, reason)
                           VALUES (?, 1, 'coverage_not_proven')""",
                        (payload["date"],),
                    )
                self._conn.commit()
            except BaseException:
                # A commit that succeeded before raising is reconciled by the
                # stable event ID on retry; rollback also removes precommit rows.
                self._conn.rollback()
                raise

    def get_optimizer_import_checkpoint(self) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT event_id, checkpoint_json FROM optimizer_import_checkpoint WHERE singleton = 1"
            ).fetchone()
        if row is None:
            return None
        checkpoint = json.loads(row[1])
        return {**checkpoint, "event_id": row[0]}

    def optimizer_import_topup_summary(self, date: str) -> dict[str, Any]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT import_kwh, import_price, price_trusted
                FROM optimizer_import_topup WHERE date = ?
                UNION ALL
                SELECT import_kwh, import_price, price_trusted
                FROM optimizer_import_interval WHERE date = ?
                """,
                (date, date),
            ).fetchall()
            coverage = self._conn.execute(
                "SELECT unknown, reason FROM optimizer_import_coverage WHERE date = ?",
                (date,),
            ).fetchone()

        total_import_kwh = 0.0
        highest_actual_import_price: float | None = None
        has_untrusted_import = False

        significant_import_kwh = 0.01

        for import_kwh_raw, import_price_raw, price_trusted_raw in rows:
            import_kwh = max(0.0, float(import_kwh_raw or 0.0))
            total_import_kwh += import_kwh
            if import_kwh < significant_import_kwh:
                continue
            price_trusted = bool(price_trusted_raw)
            if not price_trusted:
                has_untrusted_import = True
                continue
            if import_price_raw is None:
                has_untrusted_import = True
                continue
            try:
                import_price = float(import_price_raw)
            except (TypeError, ValueError, OverflowError):
                has_untrusted_import = True
                continue
            if not math.isfinite(import_price):
                has_untrusted_import = True
                continue
            if highest_actual_import_price is None or import_price > highest_actual_import_price:
                highest_actual_import_price = import_price

        import_history_complete = bool(coverage is not None and not coverage[0])
        import_cost_floor_unknown = bool(
            has_untrusted_import or (coverage is not None and coverage[0])
        )
        import_cost_floor_trusted = not import_cost_floor_unknown
        return {
            "date": date,
            "today_import_topup_kwh": round(total_import_kwh, 3),
            "today_highest_actual_import_price": highest_actual_import_price,
            "import_cost_export_floor": highest_actual_import_price,
            "import_cost_floor_trusted": import_cost_floor_trusted,
            "import_cost_floor_unknown": import_cost_floor_unknown,
            "import_history_complete": import_history_complete,
            "import_history_reason": coverage[1] if coverage is not None else "coverage_not_recorded",
        }

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
