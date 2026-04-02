"""
SigEnergy Optimizer — core decision engine.

This module is a faithful Python translation of the ~3400-line YAML blueprint
automation (sigenergy_optimiser.yaml).  Every decision variable from the
original Jinja2 template block is now a typed Python method or property.

Architecture:
  - SigEnergyOptimizer.run_forever()  — polling loop
  - SigEnergyOptimizer._read_state()  — bulk-read all HA entities
  - SigEnergyOptimizer._decide()      — pure decision logic, no side effects
  - SigEnergyOptimizer._apply()       — push decisions to HA via REST
"""
from __future__ import annotations

import asyncio
from collections import deque
import logging
import os
from datetime import datetime, time, timedelta, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import Settings
from .ha_client import HAClient
from .models import Decision, SolarState
from .state_store import StateStore

logger = logging.getLogger(__name__)

# EMS mode string constants
MODE_MAX_SELF = "Maximum Self Consumption"
MODE_CMD_DISCHARGE_PV = "Command Discharging (PV First)"
MODE_CMD_DISCHARGE_ESS = "Command Discharging (ESS First)"
MODE_CMD_CHARGE_PV = "Command Charging (PV First)"
MODE_CMD_CHARGE_GRID = "Command Charging (Grid First)"

DISCHARGE_MODES = {MODE_CMD_DISCHARGE_PV, MODE_CMD_DISCHARGE_ESS}
CHARGE_MODES = {MODE_CMD_CHARGE_PV, MODE_CMD_CHARGE_GRID}

# Manual mode labels for the mode select entity
AUTOMATED_MODES = {"Automated"}

# Maximum time between full cycles even when WebSocket is quiet (safety net)
_HEARTBEAT_INTERVAL = 60  # seconds

# Minimum gap between back-to-back rapid triggers (debounce)
_DEBOUNCE_SECONDS = 3.0

# Config attribute names whose entity IDs should trigger immediate cycles
_TRIGGER_ENTITY_ATTRS = [
    "pv_power_sensor",
    "consumed_power_sensor",
    "battery_soc_sensor",
    "price_sensor",
    "feedin_sensor",
    "demand_window_sensor",
    "price_spike_sensor",
    "sigenergy_mode_select",
]

_POWER_LIMIT_MAX_KW = 100.0


class SigEnergyOptimizer:
    def __init__(self, ha: HAClient, cfg: Settings) -> None:
        self.ha = ha
        self.cfg = cfg
        self._last_state: Optional[SolarState] = None
        self._last_decision: Optional[Decision] = None
        self._last_daily_summary_date: Optional[datetime] = None
        self._last_morning_summary_date: Optional[datetime] = None
        self._running = False
        self._ws_connected = False
        self._prev_demand_window: bool = False
        self._config_time_warnings: list[str] = self._validate_time_config()
        self._sensor_parse_warning_cache: dict[tuple[str, str], float] = {}
        self._holdoff_entry_floor: Optional[float] = None  # Stable SoC floor for holdoff window
        self._last_hw_charge_cap_kw: Optional[float] = None
        self._last_hw_discharge_cap_kw: Optional[float] = None
        self._last_cycle_started: Optional[datetime] = None
        self._last_cycle_completed: Optional[datetime] = None
        self._last_cycle_error: str = ""
        self._notif_export_active: Optional[bool] = None
        self._last_export_start_notice_at: Optional[datetime] = None
        tz_name = os.environ.get("TZ", "Australia/Adelaide")
        try:
            self._tz = ZoneInfo(tz_name)
        except ZoneInfoNotFoundError:
            logger.warning("Timezone '%s' not found; falling back to UTC", tz_name)
            self._tz = timezone.utc
        self._last_tracked_block: Optional[int] = None
        self._last_tracked_import_kw: float = -999.0
        self._last_tracked_export_kw: float = -999.0
        self._last_tracked_import_price: Optional[float] = None
        self._last_tracked_feedin_price: Optional[float] = None
        db_path = os.environ.get("STATE_DB_PATH", "/data/optimizer_state.db")
        self._state_store = StateStore(db_path)
        self._decision_trace: deque[dict[str, Any]] = deque(maxlen=1000)

        # Shared queue — HAWebSocketClient puts entity_ids here; we consume them
        self.trigger_queue: asyncio.Queue = asyncio.Queue(maxsize=64)
        self._watch_entities: set[str] = set()

    # ------------------------------------------------------------------
    # Public accessors for the web UI
    # ------------------------------------------------------------------

    @property
    def last_state(self) -> Optional[SolarState]:
        return self._last_state

    @property
    def last_decision(self) -> Optional[Decision]:
        return self._last_decision

    @property
    def ws_connected(self) -> bool:
        return self._ws_connected

    @property
    def last_cycle_started(self) -> Optional[datetime]:
        return self._last_cycle_started

    @property
    def last_cycle_completed(self) -> Optional[datetime]:
        return self._last_cycle_completed

    @property
    def last_cycle_error(self) -> str:
        return self._last_cycle_error

    @property
    def config_time_warnings(self) -> list[str]:
        return self._config_time_warnings

    def refresh_config_time_warnings(self) -> None:
        self._config_time_warnings = self._validate_time_config()

    @staticmethod
    def _valid_hw_cap_kw(v: Any) -> bool:
        return isinstance(v, (int, float)) and 0 < float(v) < 999

    def get_power_caps_kw(self, s: Optional[SolarState] = None) -> tuple[float, float]:
        fallback = float(self.cfg.ess_limit_fallback_kw)
        if not (0 < fallback <= _POWER_LIMIT_MAX_KW):
            fallback = min(max(fallback, 1.0), _POWER_LIMIT_MAX_KW)

        state = s if s is not None else self._last_state

        charge_cap = fallback
        discharge_cap = fallback

        if state and self._valid_hw_cap_kw(state.ess_max_charge_kw):
            charge_cap = float(state.ess_max_charge_kw)
        elif self._valid_hw_cap_kw(self._last_hw_charge_cap_kw):
            charge_cap = float(self._last_hw_charge_cap_kw)

        if state and self._valid_hw_cap_kw(state.ess_max_discharge_kw):
            discharge_cap = float(state.ess_max_discharge_kw)
        elif self._valid_hw_cap_kw(self._last_hw_discharge_cap_kw):
            discharge_cap = float(self._last_hw_discharge_cap_kw)

        return charge_cap, discharge_cap

    def _validate_time_config(self) -> list[str]:
        warnings: list[str] = []
        for field in (
            "daily_summary_time",
            "morning_summary_time",
            "standby_holdoff_end_time",
            "morning_slow_charge_until",
        ):
            value = getattr(self.cfg, field, "")
            if not self._is_valid_time(value):
                warnings.append(f"{field}={value!r} is invalid (expected HH:MM or HH:MM:SS)")
        if warnings:
            for msg in warnings:
                logger.warning("Config time validation: %s", msg)
        return warnings

    @staticmethod
    def _is_valid_time(value: str) -> bool:
        try:
            parts = str(value).split(":")
            if len(parts) not in (2, 3):
                return False
            h, m = int(parts[0]), int(parts[1])
            s = int(parts[2]) if len(parts) == 3 else 0
            return 0 <= h <= 23 and 0 <= m <= 59 and 0 <= s <= 59
        except (ValueError, TypeError):
            return False

    def _warn_parse_issue(self, entity_id: str, raw_value: str, label: str) -> None:
        now_ts = datetime.now().timestamp()
        cache_key = (entity_id, raw_value)
        last_ts = self._sensor_parse_warning_cache.get(cache_key)
        # Rate-limit repeated malformed payload logs to keep signal useful.
        if last_ts is not None and now_ts - last_ts < 300:
            return

        # Prune stale entries and cap memory growth for long-lived processes.
        cutoff = now_ts - 1800  # keep last 30 minutes
        if len(self._sensor_parse_warning_cache) > 512:
            self._sensor_parse_warning_cache = {
                k: ts for k, ts in self._sensor_parse_warning_cache.items() if ts >= cutoff
            }

        if len(self._sensor_parse_warning_cache) > 512:
            newest = sorted(
                self._sensor_parse_warning_cache.items(),
                key=lambda item: item[1],
                reverse=True,
            )[:512]
            self._sensor_parse_warning_cache = dict(newest)

        self._sensor_parse_warning_cache[cache_key] = now_ts

        if len(self._sensor_parse_warning_cache) > 512:
            newest = sorted(
                self._sensor_parse_warning_cache.items(),
                key=lambda item: item[1],
                reverse=True,
            )[:512]
            self._sensor_parse_warning_cache = dict(newest)

        logger.warning("%s sensor %s returned non-numeric state %r; using safe defaults", label, entity_id, raw_value)

    def get_watch_entities(self) -> set[str]:
        """Return the set of entity IDs the WS client should subscribe to."""
        if not self._watch_entities:
            self._watch_entities = {
                getattr(self.cfg, attr)
                for attr in _TRIGGER_ENTITY_ATTRS
                if getattr(self.cfg, attr, "")
            }
        return self._watch_entities

    def on_ws_connect(self) -> None:
        self._ws_connected = True
        logger.info("WebSocket connected — event-driven mode active")

    def on_ws_disconnect(self) -> None:
        self._ws_connected = False
        logger.warning("WebSocket disconnected — heartbeat fallback active")

    # ------------------------------------------------------------------
    # Background loop (event-driven + heartbeat fallback)
    # ------------------------------------------------------------------

    async def run_forever(self) -> None:
        """
        Event-driven main loop.

        Waits on trigger_queue for entity_ids pushed by HAWebSocketClient.
        Rapid bursts are debounced so we don't thrash when a sensor updates
        every second. A heartbeat fires every _HEARTBEAT_INTERVAL seconds
        regardless, so we always converge even if WS events are missed.

        Falls back gracefully to pure heartbeat polling when the WebSocket
        is disconnected — no separate code path needed.
        """
        self._running = True
        last_tick_ts = 0.0
        last_heartbeat_ts = 0.0

        logger.info(
            "Optimizer event loop started (debounce=%.0fs, heartbeat=%ds)",
            _DEBOUNCE_SECONDS, _HEARTBEAT_INTERVAL,
        )

        # One immediate startup tick
        try:
            await self._tick()
            last_tick_ts = datetime.now().timestamp()
            last_heartbeat_ts = last_tick_ts
        except Exception as exc:
            logger.exception("Startup tick failed: %s", exc)

        while self._running:
            now = datetime.now().timestamp()
            time_since_heartbeat = now - last_heartbeat_ts
            wait_max = max(0.01, _HEARTBEAT_INTERVAL - time_since_heartbeat)

            try:
                entity_id = await asyncio.wait_for(
                    self.trigger_queue.get(),
                    timeout=wait_max,
                )
                self.trigger_queue.task_done()

                # Minute tick from WS time_changed event
                if entity_id == "__time_changed__":
                    if datetime.now().timestamp() - last_tick_ts >= _HEARTBEAT_INTERVAL - 1:
                        logger.debug("Heartbeat tick (WS time_changed)")
                        await self._safe_tick()
                        last_tick_ts = last_heartbeat_ts = datetime.now().timestamp()
                    continue

                # Real entity state change — drain burst then run
                logger.debug("Event-driven tick triggered by: %s", entity_id)
                await self._drain_queue(_DEBOUNCE_SECONDS)
                await self._safe_tick()
                last_tick_ts = last_heartbeat_ts = datetime.now().timestamp()

            except asyncio.TimeoutError:
                # No WS events — heartbeat tick
                logger.debug("Heartbeat tick (timeout, ws=%s)", self._ws_connected)
                await self._safe_tick()
                last_tick_ts = last_heartbeat_ts = datetime.now().timestamp()

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception("Event loop error: %s", exc)
                await asyncio.sleep(5)

    async def _drain_queue(self, window: float) -> None:
        """Consume all queued items within `window` seconds to collapse a burst into one tick."""
        deadline = asyncio.get_event_loop().time() + window
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                break
            try:
                item = await asyncio.wait_for(self.trigger_queue.get(), timeout=remaining)
                self.trigger_queue.task_done()
            except asyncio.TimeoutError:
                break

    async def _safe_tick(self) -> None:
        self._last_cycle_started = datetime.now(timezone.utc)
        try:
            await self._tick()
            self._last_cycle_error = ""
            self._last_cycle_completed = datetime.now(timezone.utc)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._last_cycle_error = str(exc)
            self._last_cycle_completed = datetime.now(timezone.utc)
            logger.exception("Optimizer tick failed: %s", exc)

    async def run_once(self) -> Decision:
        """Run a single optimisation cycle and return the decision (for manual trigger)."""
        await self._tick()
        return self._last_decision

    async def _tick(self) -> None:
        prev_decision = self._last_decision
        prev_state = self._last_state
        state = await self._read_state()
        self._last_state = state
        decision = self._decide(state)
        self._last_decision = decision
        await self._apply(state, decision)
        self._record_automation_audit(state, decision, prev_decision)
        self._record_decision_trace(state, decision)
        await self._handle_notifications(state, decision, prev_decision, prev_state)
        await self._handle_daily_summaries(state, decision)
        self._accumulate_history(state, decision)
        self._record_price_tracking(state)

    def _record_price_tracking(self, s: SolarState) -> None:
        now = datetime.now(self._tz)
        now_block = int(now.timestamp()) // 300
        import_kw = max(0.0, float(s.grid_import_power_kw or 0.0))
        export_kw = max(0.0, float(s.grid_export_power_kw or 0.0))
        import_price = s.current_price if s.current_price is not None else None
        feedin_price = s.feedin_price if s.feedin_price is not None else None
        should_record = False
        if self._last_tracked_block is None or now_block != self._last_tracked_block:
            should_record = True
        if abs(import_kw - self._last_tracked_import_kw) >= 0.25:
            should_record = True
        if abs(export_kw - self._last_tracked_export_kw) >= 0.25:
            should_record = True
        if import_price is not None and import_price != self._last_tracked_import_price:
            should_record = True
        if feedin_price is not None and feedin_price != self._last_tracked_feedin_price:
            should_record = True
        if not should_record:
            return
        block_start = datetime.fromtimestamp(now_block * 300, tz=self._tz).replace(second=0, microsecond=0)
        self._state_store.record_price_event(
            ts=now.isoformat(timespec="seconds"),
            block_ts=block_start.isoformat(timespec="seconds"),
            grid_import_kw=import_kw,
            grid_export_kw=export_kw,
            import_price=import_price,
            feedin_price=feedin_price,
            battery_soc=float(s.battery_soc),
        )
        self._last_tracked_block = now_block
        self._last_tracked_import_kw = import_kw
        self._last_tracked_export_kw = export_kw
        self._last_tracked_import_price = import_price
        self._last_tracked_feedin_price = feedin_price
        if now.hour == 0 and now.minute < 10:
            self._state_store.purge_old_price_tracking(retain_days=14)

    def price_tracking_events(self, date: str | None = None, limit: int = 2000) -> list[dict[str, Any]]:
        return self._state_store.get_price_events(date=date, limit=limit)

    def daily_earnings_summary(self, date: str | None = None) -> dict[str, Any]:
        target_date = date or datetime.now(self._tz).date().isoformat()
        return self._state_store.daily_earnings_summary(target_date)

    def earnings_history(self, days: int = 7) -> dict[str, Any]:
        days = max(1, min(days, 30))
        today = datetime.now(self._tz).date()
        out = []
        for i in range(days):
            d = (today - timedelta(days=i)).isoformat()
            s = self._state_store.daily_earnings_summary(d)
            out.append(
                {
                    "date": d,
                    "import_kwh": s.get("total_import_kwh", 0.0),
                    "export_kwh": s.get("total_export_kwh", 0.0),
                    "import_costs": s.get("import_costs", 0.0),
                    "export_earnings": s.get("export_earnings", 0.0),
                    "net": s.get("net", 0.0),
                }
            )
        return {"days": out}

    def audit_events(self, limit: int = 200) -> list[dict[str, Any]]:
        return self._state_store.get_audit_events(limit=limit)

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
        self._state_store.record_audit_event(
            action=action,
            source=source,
            actor=actor,
            result=result,
            target_key=target_key,
            old_value=old_value,
            new_value=new_value,
            details=details,
        )

    def list_threshold_presets(self) -> list[dict[str, Any]]:
        return self._state_store.list_threshold_presets()

    def get_threshold_preset(self, name: str) -> dict[str, Any] | None:
        return self._state_store.get_threshold_preset(name)

    def save_threshold_preset(self, name: str, payload: dict[str, Any]) -> None:
        self._state_store.save_threshold_preset(name, payload)

    def delete_threshold_preset(self, name: str) -> bool:
        return self._state_store.delete_threshold_preset(name)

    def decision_trace(self, limit: int = 200) -> list[dict[str, Any]]:
        n = max(1, min(int(limit), 2000))
        return list(self._decision_trace)[:n]

    def _record_decision_trace(self, s: SolarState, d: Decision) -> None:
        gates = d.trace_gates if isinstance(d.trace_gates, dict) else {}
        values = d.trace_values if isinstance(d.trace_values, dict) else {}
        self._decision_trace.appendleft(
            {
                "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "summary": {
                    "ems_mode": d.ems_mode,
                    "export_limit_kw": d.export_limit,
                    "import_limit_kw": d.import_limit,
                    "pv_max_power_limit_kw": d.pv_max_power_limit,
                    "ess_charge_limit_kw": d.ess_charge_limit,
                    "ess_discharge_limit_kw": d.ess_discharge_limit,
                    "outcome_reason": d.outcome_reason,
                },
                "state": {
                    "battery_soc": s.battery_soc,
                    "pv_kw": s.pv_kw,
                    "load_kw": s.load_kw,
                    "grid_import_power_kw": s.grid_import_power_kw,
                    "grid_export_power_kw": s.grid_export_power_kw,
                    "current_price": s.current_price,
                    "feedin_price": s.feedin_price,
                    "forecast_remaining_kwh": s.forecast_remaining_kwh,
                    "forecast_today_kwh": s.forecast_today_kwh,
                    "forecast_tomorrow_kwh": s.forecast_tomorrow_kwh,
                },
                "gates": gates,
                "values": values,
            }
        )

    def _record_automation_audit(self, s: SolarState, d: Decision, prev: Optional[Decision]) -> None:
        cfg = self.cfg
        if s.sigenergy_mode not in {cfg.automated_option, ""}:
            return
        if prev is None:
            return

        def _changed(a: float | None, b: float | None, tol: float = 0.1) -> bool:
            try:
                return abs(float(a) - float(b)) > tol
            except Exception:
                return a != b

        changed_keys: list[str] = []
        if prev.ems_mode != d.ems_mode:
            changed_keys.append("ems_mode")
        if _changed(prev.export_limit, d.export_limit):
            changed_keys.append("export_limit")
        if _changed(prev.import_limit, d.import_limit):
            changed_keys.append("import_limit")
        if _changed(prev.pv_max_power_limit, d.pv_max_power_limit):
            changed_keys.append("pv_max_power_limit")
        if _changed(prev.ess_charge_limit, d.ess_charge_limit):
            changed_keys.append("ess_charge_limit")
        if _changed(prev.ess_discharge_limit, d.ess_discharge_limit):
            changed_keys.append("ess_discharge_limit")

        if not changed_keys:
            return

        self.record_audit_event(
            action="optimizer_apply",
            source="optimizer_cycle",
            actor="system:optimizer",
            result="ok",
            old_value={
                "ems_mode": prev.ems_mode,
                "export_limit": prev.export_limit,
                "import_limit": prev.import_limit,
                "pv_max_power_limit": prev.pv_max_power_limit,
                "ess_charge_limit": prev.ess_charge_limit,
                "ess_discharge_limit": prev.ess_discharge_limit,
            },
            new_value={
                "ems_mode": d.ems_mode,
                "export_limit": d.export_limit,
                "import_limit": d.import_limit,
                "pv_max_power_limit": d.pv_max_power_limit,
                "ess_charge_limit": d.ess_charge_limit,
                "ess_discharge_limit": d.ess_discharge_limit,
            },
            details={
                "initiator": "system",
                "changed_keys": changed_keys,
                "reason": d.outcome_reason,
            },
        )

    def _accumulate_history(self, s, d) -> None:
        import time as _time
        if not hasattr(self, "_chart_history_power"):
            self._chart_history_power = []
            self._chart_history_price = []
        now_ms = int(_time.time() * 1000)
        cutoff = now_ms - 86_400_000
        self._chart_history_power.append({
            "t": now_ms, "battery": s.battery_soc, "pv": s.pv_kw,
            "load": s.load_kw, "exp": s.grid_export_power_kw,
            "imp": s.grid_import_power_kw, "minSoc": d.min_soc_to_sunrise,
            "pvForecast": s.solar_power_now_kw,
        })
        self._chart_history_price.append({"t": now_ms, "imp": s.current_price, "fit": s.feedin_price})
        self._chart_history_power = [x for x in self._chart_history_power if x["t"] >= cutoff]
        self._chart_history_price = [x for x in self._chart_history_price if x["t"] >= cutoff]

    # ------------------------------------------------------------------
    # 1. Read all HA entities into a SolarState snapshot
    # ------------------------------------------------------------------

    async def _read_state(self) -> SolarState:
        cfg = self.cfg
        s = SolarState()

        # ---- bulk fetch -----------------------------------------------
        entity_ids = [
            cfg.pv_power_sensor, cfg.consumed_power_sensor, cfg.battery_soc_sensor,
            cfg.rated_capacity_sensor, cfg.available_discharge_sensor,
            cfg.ess_rated_discharge_power_sensor, cfg.ess_rated_charge_power_sensor,
            cfg.sun_entity, cfg.price_sensor, cfg.feedin_sensor,
            cfg.demand_window_sensor, cfg.price_spike_sensor,
            cfg.price_forecast_sensor, cfg.feedin_forecast_sensor,
            cfg.forecast_remaining_sensor, cfg.forecast_today_sensor,
            cfg.forecast_tomorrow_sensor, cfg.solar_power_now_sensor,
            cfg.daily_export_energy, cfg.daily_import_energy, cfg.daily_load_energy,
            cfg.daily_pv_energy, cfg.daily_battery_charge_energy, cfg.daily_battery_discharge_energy,
            cfg.grid_export_limit, cfg.grid_import_limit, cfg.pv_max_power_limit,
            cfg.ems_mode_select, cfg.ha_control_switch,
            cfg.export_session_start, cfg.import_session_start,
            cfg.last_export_notification, cfg.last_import_notification,
            cfg.sigenergy_mode_select,
        ]
        if cfg.grid_import_power_sensor:
            entity_ids.append(cfg.grid_import_power_sensor)
        if cfg.grid_export_power_sensor:
            entity_ids.append(cfg.grid_export_power_sensor)
        bulk = await self.ha.bulk_states(entity_ids)

        def _fv(eid: str, default: float = 0.0) -> float:
            obj = bulk.get(eid)
            if not obj:
                return default
            try:
                return float(obj["state"])
            except (TypeError, ValueError):
                return default

        def _sv(eid: str, default: str = "") -> str:
            obj = bulk.get(eid)
            if not obj:
                return default
            v = obj.get("state", "")
            return v if v not in {"unknown", "unavailable", "none", ""} else default

        def _bv(eid: str) -> bool:
            return _sv(eid, "off").lower() in ("on", "true", "1")

        def _attr(eid: str, attr: str, default=None):
            obj = bulk.get(eid)
            if not obj:
                return default
            return obj.get("attributes", {}).get(attr, default)

        # ---- PV / battery ---------------------------------------------
        pv_raw = _fv(cfg.pv_power_sensor)
        s.pv_kw = pv_raw / 1000 if pv_raw > 100 else pv_raw

        load_raw = _fv(cfg.consumed_power_sensor)
        s.load_kw = load_raw / 1000 if load_raw > 100 else load_raw
        if cfg.grid_import_power_sensor:
            grid_import_raw = _fv(cfg.grid_import_power_sensor)
            s.grid_import_power_kw = grid_import_raw / 1000 if grid_import_raw > 100 else grid_import_raw
        if cfg.grid_export_power_sensor:
            grid_export_raw = _fv(cfg.grid_export_power_sensor)
            s.grid_export_power_kw = grid_export_raw / 1000 if grid_export_raw > 100 else grid_export_raw

        s.battery_soc = max(0.0, min(100.0, _fv(cfg.battery_soc_sensor)))

        cap_raw = _fv(cfg.rated_capacity_sensor, 10.0)
        cap_uom = (_attr(cfg.rated_capacity_sensor, "unit_of_measurement") or "kwh").lower()
        if cap_uom == "wh":
            s.battery_capacity_kwh = cap_raw / 1000
        elif cap_raw < 1.0 and cap_raw > 0:
            s.battery_capacity_kwh = cap_raw * 1000
        else:
            s.battery_capacity_kwh = cap_raw if cap_raw > 0 else 10.0

        s.available_discharge_energy_kwh = _fv(cfg.available_discharge_sensor)

        def _kw_from_sensor(raw: float) -> float:
            if raw <= 0:
                return 999.0
            return raw / 1000 if raw >= 1000 else raw

        s.ess_max_discharge_kw = _kw_from_sensor(_fv(cfg.ess_rated_discharge_power_sensor))
        s.ess_max_charge_kw = _kw_from_sensor(_fv(cfg.ess_rated_charge_power_sensor))
        if self._valid_hw_cap_kw(s.ess_max_charge_kw):
            self._last_hw_charge_cap_kw = float(s.ess_max_charge_kw)
        if self._valid_hw_cap_kw(s.ess_max_discharge_kw):
            self._last_hw_discharge_cap_kw = float(s.ess_max_discharge_kw)

        # ---- Grid limits / EMS mode -----------------------------------
        s.current_export_limit = _fv(cfg.grid_export_limit)
        s.current_import_limit = _fv(cfg.grid_import_limit)
        s.current_pv_max_power_limit = _fv(cfg.pv_max_power_limit)
        s.current_ems_mode = _sv(cfg.ems_mode_select, MODE_MAX_SELF)
        s.ha_control_enabled = _bv(cfg.ha_control_switch)

        # ---- Prices ---------------------------------------------------
        price_obj = bulk.get(cfg.price_sensor, {})
        price_state = price_obj.get("state", "") if price_obj else ""
        price_is_estimate = str(_attr(cfg.price_sensor, "estimate") or "false").lower() == "true"
        price_available = price_state not in {"unknown", "unavailable", "none", ""}

        if price_available:
            try:
                raw_price = float(price_state)
                s.price_is_actual = not price_is_estimate
                s.price_is_estimated = price_is_estimate
                s.current_price = raw_price
                s.current_price_cents = raw_price * cfg.price_multiplier
            except (TypeError, ValueError):
                self._warn_parse_issue(cfg.price_sensor, str(price_state), "Price")
                s.current_price = 1.0
                s.current_price_cents = 1.0 * cfg.price_multiplier
        else:
            s.current_price = 1.0
            s.current_price_cents = 1.0 * cfg.price_multiplier

        fit_state = _sv(cfg.feedin_sensor, "")
        fit_available = fit_state != ""
        if fit_available:
            try:
                s.feedin_price = float(fit_state)
                s.feedin_price_cents = s.feedin_price * cfg.price_multiplier
            except (TypeError, ValueError):
                self._warn_parse_issue(cfg.feedin_sensor, str(fit_state), "FIT")
                s.feedin_price = -999.0
                s.feedin_price_cents = -999.0
                fit_available = False
        else:
            s.feedin_price = -999.0
            s.feedin_price_cents = -999.0

        s.price_is_negative = s.price_is_actual and s.current_price < 0
        s.feedin_is_negative = fit_available and s.feedin_price < 0
        s.price_spike_active = _bv(cfg.price_spike_sensor)
        s.demand_window_active = _bv(cfg.demand_window_sensor)

        # ---- Forecasts ------------------------------------------------
        s.forecast_remaining_kwh = _fv(cfg.forecast_remaining_sensor)
        s.forecast_today_kwh = _fv(cfg.forecast_today_sensor)
        s.forecast_tomorrow_kwh = _fv(cfg.forecast_tomorrow_sensor)

        solar_raw = _fv(cfg.solar_power_now_sensor)
        # Solcast power_now can return Watts (e.g. 554 W) or kW (e.g. 0.554 kW).
        # Values > 100 are assumed to be in Watts and converted; <= 100 assumed already kW.
        s.solar_power_now_kw = solar_raw / 1000 if solar_raw > 100 else solar_raw

        s.solcast_detailed = _attr(cfg.forecast_today_sensor, "detailedForecast") or []
        s.price_forecast_entries = _attr(cfg.price_forecast_sensor, cfg.price_forecast_attribute) or []
        s.feedin_forecast_entries = _attr(cfg.feedin_forecast_sensor, cfg.feedin_forecast_attribute) or []

        # ---- Sun ------------------------------------------------------
        s.sun_elevation = float(_attr(cfg.sun_entity, "elevation") or 0)
        s.sun_above_horizon = _sv(cfg.sun_entity, "below_horizon") == "above_horizon"

        def _ts(attr: str) -> Optional[float]:
            v = _attr(cfg.sun_entity, attr)
            if not v:
                return None
            try:
                return datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp()
            except Exception:
                return None

        s.next_sunrise_ts = _ts("next_rising")
        s.next_sunset_ts = _ts("next_setting")

        now_ts = datetime.now().timestamp()
        if s.next_sunrise_ts:
            raw_h = (s.next_sunrise_ts - now_ts) / 3600
            s.hours_to_sunrise = max(0.0, raw_h)
        if s.next_sunset_ts:
            s.hours_to_sunset = max(0.0, (s.next_sunset_ts - now_ts) / 3600)

        # ---- Daily totals / session tracking --------------------------
        s.daily_export_kwh = _fv(cfg.daily_export_energy)
        s.daily_import_kwh = _fv(cfg.daily_import_energy)
        s.daily_load_kwh = _fv(cfg.daily_load_energy)
        s.daily_pv_kwh = _fv(cfg.daily_pv_energy)
        s.daily_battery_charge_kwh = _fv(cfg.daily_battery_charge_energy)
        s.daily_battery_discharge_kwh = _fv(cfg.daily_battery_discharge_energy)
        s.export_session_start_kwh = _fv(cfg.export_session_start)
        s.import_session_start_kwh = _fv(cfg.import_session_start)
        s.last_export_notification = _sv(cfg.last_export_notification, "stopped")
        s.last_import_notification = _sv(cfg.last_import_notification, "stopped")

        # ---- Mode select ----------------------------------------------
        s.sigenergy_mode = _sv(cfg.sigenergy_mode_select, "Automated")

        return s

    # ------------------------------------------------------------------
    # 2. Pure decision logic
    # ------------------------------------------------------------------

    def _decide(self, s: SolarState) -> Decision:
        """Translate the full YAML variable block into a Decision object."""
        cfg = self.cfg
        d = Decision()
        now = datetime.now()
        now_ts = now.timestamp()

        # ---- Time windows -------------------------------------------
        day_start_ts, day_end_ts = self._day_window(s)
        is_evening_or_night = now_ts < day_start_ts or now_ts > day_end_ts
        d.is_evening_or_night = is_evening_or_night

        sunset_ts = s.next_sunset_ts or (now_ts + 86400)
        sunrise_ts = s.next_sunrise_ts or (now_ts + 86400)
        if s.sun_above_horizon:
            actual_sunrise_ts = sunrise_ts - 86400
        else:
            actual_sunrise_ts = sunrise_ts

        hours_to_sunrise = s.hours_to_sunrise
        hours_to_sunset = s.hours_to_sunset
        close_to_sunset = hours_to_sunset <= cfg.sunset_export_grace_hours
        d.hours_to_sunrise = hours_to_sunrise

        # ---- Re-derive price flags (in case s came from a test, not _read_state) ----
        s.price_is_negative = s.price_is_actual and s.current_price < 0
        s.feedin_is_negative = s.feedin_price not in (-999.0,) and s.feedin_price < 0

        # ---- Battery capacity helpers --------------------------------
        cap = s.battery_capacity_kwh
        bat_fill_need_kwh = max(0.0, cap - s.available_discharge_energy_kwh)

        # ---- Sunrise SoC target (dynamic calculation) ----------------
        soc_required = self._battery_soc_required_to_sunrise(s)
        d.battery_soc_required_to_sunrise = soc_required
        sunrise_soc_target = max(soc_required, cfg.sunrise_reserve_soc)
        d.sunrise_soc_target = sunrise_soc_target
        sunrise_fill_need_kwh = max(0.0, cap * ((sunrise_soc_target - s.battery_soc) / 100))
        d.min_soc_to_sunrise = soc_required

        # ---- Price forecasts -----------------------------------------
        negative_price_before_cutoff = self._negative_price_before_cutoff(s, now_ts)

        # ---- Productive solar window ---------------------------------
        productive_solar_end_ts = self._productive_solar_end_ts(s, sunset_ts, now_ts)

        # ---- Morning dump -------------------------------------------
        morning_dump_start_ts, morning_dump_end_ts = self._morning_dump_window(s, actual_sunrise_ts)
        morning_dump_active = self._morning_dump_active(
            s, morning_dump_start_ts, morning_dump_end_ts,
            productive_solar_end_ts, bat_fill_need_kwh, now_ts
        )
        within_morning_grace = (
            cfg.morning_dump_enabled
            and morning_dump_end_ts is not None
            and now_ts >= morning_dump_end_ts
            and now_ts < morning_dump_end_ts + 7200
        )

        d.morning_dump_active = morning_dump_active

        # ---- Morning slow charge ------------------------------------
        morning_slow_charge_end_ts = (
            (sunset_ts - cfg.morning_slow_charge_sunset_cutoff * 3600)
            if sunset_ts else now_ts
        )
        morning_slow_charge_active = self._morning_slow_charge_active(
            s, now, now_ts, morning_slow_charge_end_ts
        )
        d.morning_slow_charge_active = morning_slow_charge_active

        # ---- Standby holdoff ----------------------------------------
        battery_can_reach_from_pv = (
            s.forecast_remaining_kwh >= sunrise_fill_need_kwh * cfg.forecast_safety_charging
        )
        standby_holdoff_active = (
            cfg.standby_holdoff_enabled
            and s.forecast_today_kwh >= cfg.pv_forecast_holdoff_kwh
            and negative_price_before_cutoff
            and now < self._today_at(cfg.standby_holdoff_end_time)
            and s.current_price > cfg.import_threshold_low
            and battery_can_reach_from_pv
        )
        d.standby_holdoff_active = standby_holdoff_active
        
        # Store holdoff floor at entry to prevent drift from forecast updates mid-holdoff
        prev_holdoff = self._last_decision and self._last_decision.standby_holdoff_active
        if standby_holdoff_active and not prev_holdoff:
            # Holdoff just became active — snapshot the SoC floor
            soc_required = self._battery_soc_required_to_sunrise(s)
            holdoff_sunrise_target = max(soc_required, cfg.sunrise_reserve_soc)
            self._holdoff_entry_floor = holdoff_sunrise_target + cfg.soc_hysteresis
        elif not standby_holdoff_active:
            # Holdoff expired — clear the stored floor
            self._holdoff_entry_floor = None

        # ---- Evening boost ------------------------------------------
        evening_export_boost_active = self._evening_export_boost_active(
            s, now_ts, productive_solar_end_ts, sunrise_soc_target, bat_fill_need_kwh
        )
        d.evening_export_boost_active = evening_export_boost_active

        # ---- Effective min SoC for export ---------------------------
        if is_evening_or_night:
            relaxed = sunrise_soc_target - cfg.sunrise_export_relax_percent
            effective_min_soc = max(relaxed, cfg.sunrise_reserve_soc)
        else:
            effective_min_soc = cfg.min_soc_floor

        export_sunrise_guard_active = is_evening_or_night
        export_min_soc = effective_min_soc
        if export_sunrise_guard_active:
            export_min_soc = max(effective_min_soc, soc_required)

        # ---- Export flags -------------------------------------------
        export_spike_active = (
            s.price_spike_active
            and s.feedin_price >= cfg.export_spike_threshold
        )
        d.export_spike_active = export_spike_active

        positive_fit_override = (
            cfg.allow_low_medium_export_positive_fit
            and s.feedin_price >= 0.01
        )

        solar_potential_kw = max(s.pv_kw, s.solar_power_now_kw)
        pv_surplus = max(solar_potential_kw - s.load_kw, 0.0)
        pv_surplus_actual = max(s.pv_kw - s.load_kw, 0.0)

        export_solar_override = (
            s.feedin_price > 0
            and s.feedin_price >= cfg.export_threshold_medium
            and s.battery_soc >= cfg.max_battery_soc
            and not is_evening_or_night
            and pv_surplus > cfg.min_grid_transfer_kw
            and (
                s.forecast_remaining_kwh >= bat_fill_need_kwh * 1.25
                or bat_fill_need_kwh <= 0
            )
        )

        # ---- PV safeguard -------------------------------------------
        full_export_override_check = (
            s.battery_soc >= cfg.max_battery_soc
            and not is_evening_or_night
            and pv_surplus > cfg.min_grid_transfer_kw
        )
        est_load_kwh = s.load_kw * hours_to_sunset
        net_forecast = s.forecast_remaining_kwh - est_load_kwh
        tomorrow_kwh = s.forecast_tomorrow_kwh
        low_today = s.forecast_remaining_kwh > 0 and net_forecast <= bat_fill_need_kwh * cfg.forecast_safety_charging
        low_tomorrow = is_evening_or_night and tomorrow_kwh < cap * cfg.forecast_safety_charging
        pv_safeguard_active = (
            not full_export_override_check
            and not positive_fit_override
            and (low_today or low_tomorrow)
        )
        d.pv_safeguard_active = pv_safeguard_active

        # ---- Solar surplus bypass -----------------------------------
        solar_surplus_bypass = self._solar_surplus_bypass(
            s, morning_slow_charge_active, cap, pv_surplus_actual,
            prev_desired_mode=self._last_decision.ems_mode if self._last_decision else "",
        )
        d.solar_surplus_bypass = solar_surplus_bypass

        # ---- Battery full safeguard ---------------------------------
        battery_full_safeguard_block = self._battery_full_safeguard_block(
            s, now_ts, sunset_ts, bat_fill_need_kwh, is_evening_or_night
        )
        d.battery_full_safeguard = battery_full_safeguard_block

        # ---- Export blocked for forecast ----------------------------
        export_blocked_for_forecast = self._export_blocked_for_forecast(
            s, pv_surplus, is_evening_or_night, bat_fill_need_kwh,
            hours_to_sunset, close_to_sunset
        )
        export_forecast_guard = self._export_forecast_guard(
            s, sunrise_fill_need_kwh, is_evening_or_night,
            evening_export_boost_active, close_to_sunset
        )
        export_blocked_effective = export_blocked_for_forecast

        # ---- Export tier limit (kW cap based on price) --------------
        export_tier_limit = self._export_tier_limit(
            s, export_spike_active, export_solar_override,
            pv_safeguard_active, evening_export_boost_active,
            solar_surplus_bypass
        )

        # ---- Morning dump limit -------------------------------------
        morning_dump_limit = min(cfg.export_limit_high, s.ess_max_discharge_kw)

        # ---- Desired export limit -----------------------------------
        desired_export_limit = self._desired_export_limit(
            s, export_spike_active, export_solar_override,
            export_blocked_effective, export_forecast_guard,
            export_min_soc, positive_fit_override, solar_surplus_bypass,
            evening_export_boost_active, morning_dump_active, morning_dump_limit,
            battery_full_safeguard_block,
            export_tier_limit, hours_to_sunrise, cap,
            # Use forecast-based surplus (solar_potential_kw − load) so the morning
            # slow-charge export branch sees uncurtailed PV potential rather than the
            # inverter-curtailed measured output, which causes a self-locking feedback
            # loop where low export limit → low pv_kw reading → low export limit.
            pv_surplus, is_evening_or_night, morning_slow_charge_active,
            within_morning_grace,
        )
        d.export_limit = desired_export_limit

        # ---- Import limit (grid_limit_base → desired_import_limit) --
        desired_import_limit = self._desired_import_limit(
            s, morning_dump_active, demand_window_active=s.demand_window_active,
            standby_holdoff_active=standby_holdoff_active,
            feedin_price_ok=(s.feedin_price >= cfg.export_threshold_low),
            pv_surplus=pv_surplus_actual,
        )
        d.import_limit = desired_import_limit

        # ---- Desired EMS mode ---------------------------------------
        desired_ems_mode = self._desired_ems_mode(
            s, morning_dump_active, standby_holdoff_active, export_solar_override,
            desired_export_limit, desired_import_limit, export_min_soc,
            sunrise_soc_target, within_morning_grace,
            export_blocked_for_forecast, is_evening_or_night,
        )
        d.ems_mode = desired_ems_mode

        # ---- Battery-only mode → cap PV max power -------------------
        battery_only_mode = (
            desired_ems_mode == MODE_MAX_SELF
            and desired_export_limit == 0
            and desired_import_limit == 0
            and (is_evening_or_night or standby_holdoff_active)
        )
        desired_pv_max = self._desired_pv_max_power(
            s, standby_holdoff_active, battery_only_mode,
            morning_dump_active, morning_slow_charge_active,
            desired_export_limit,
        )
        d.pv_max_power_limit = desired_pv_max

        # ---- ESS charge / discharge limits --------------------------
        d.ess_charge_limit = self._desired_ess_charge_limit(
            s, desired_import_limit, morning_slow_charge_active,
            desired_export_limit, pv_surplus_actual
        )
        d.ess_discharge_limit = self._desired_ess_discharge_limit(
            s, standby_holdoff_active, positive_fit_override,
            evening_export_boost_active
        )

        # ---- Needs HA control auto-enable? --------------------------
        d.needs_ha_control_switch = (
            cfg.auto_enable_ha_control
            and not s.ha_control_enabled
            and (
                s.feedin_is_negative
                or desired_export_limit > 0
                or desired_import_limit > 0
                or s.current_ems_mode != desired_ems_mode
            )
        )

        # ---- Battery ETA -------------------------------------------
        # Keep holdoff sentinel (0.01 kW) out of analytical flow/ETA math.
        effective_import_for_math = 0.0 if desired_import_limit <= 0.011 else desired_import_limit
        battery_power_kw = (s.pv_kw + (effective_import_for_math - desired_export_limit) - s.load_kw)
        d.battery_power_kw = battery_power_kw
        d.battery_eta_formatted = self._battery_eta(s, battery_power_kw)

        # ---- Reason strings -----------------------------------------
        d.export_reason = self._export_reason(
            s, export_spike_active, export_solar_override, morning_dump_active,
            export_blocked_effective, export_forecast_guard, export_min_soc,
            pv_safeguard_active, export_tier_limit, morning_slow_charge_active,
            solar_surplus_bypass, evening_export_boost_active,
            battery_full_safeguard_block, desired_export_limit, positive_fit_override,
        )
        d.import_reason = self._import_reason(
            s, morning_dump_active, standby_holdoff_active,
            sunrise_soc_target, desired_import_limit, pv_surplus_actual
        )
        eta_label = ""
        if d.battery_eta_formatted not in ("idle", "Full", "Empty"):
            if battery_power_kw > 0.1:
                eta_label = f"Bat→Full:{d.battery_eta_formatted}"
            elif battery_power_kw < -0.1:
                eta_label = f"Bat→Empty:{d.battery_eta_formatted}"
        parts = [d.export_reason, d.import_reason]
        if eta_label:
            parts.append(eta_label)
        if s.price_is_estimated:
            parts.append("*est")
        d.outcome_reason = "; ".join(p for p in parts if p and p != "n/a")

        export_branch = "normal_tier"
        if morning_dump_active:
            export_branch = "morning_dump"
        elif morning_slow_charge_active:
            export_branch = "morning_slow_charge"
        elif export_spike_active:
            export_branch = "export_spike"
        elif export_solar_override:
            export_branch = "solar_override"
        elif solar_surplus_bypass:
            export_branch = "solar_surplus_bypass"
        elif battery_full_safeguard_block:
            export_branch = "battery_full_safeguard_block"
        elif export_blocked_effective or export_forecast_guard:
            export_branch = "forecast_guard_block"
        elif desired_export_limit <= 0:
            export_branch = "blocked_or_zero"

        import_branch = "blocked"
        if morning_dump_active:
            import_branch = "morning_dump_block"
        elif s.demand_window_active:
            import_branch = "demand_window_block"
        elif standby_holdoff_active:
            import_branch = "standby_holdoff_block"
        elif desired_import_limit > 0 and s.price_is_negative:
            import_branch = "negative_price_import"
        elif desired_import_limit > 0:
            import_branch = "cheap_topup_import"

        d.trace_gates = {
            "is_evening_or_night": is_evening_or_night,
            "close_to_sunset": close_to_sunset,
            "within_morning_grace": within_morning_grace,
            "morning_dump_active": morning_dump_active,
            "morning_slow_charge_active": morning_slow_charge_active,
            "standby_holdoff_active": standby_holdoff_active,
            "negative_price_before_cutoff": negative_price_before_cutoff,
            "battery_can_reach_from_pv": battery_can_reach_from_pv,
            "evening_export_boost_active": evening_export_boost_active,
            "export_spike_active": export_spike_active,
            "positive_fit_override": positive_fit_override,
            "export_solar_override": export_solar_override,
            "pv_safeguard_active": pv_safeguard_active,
            "solar_surplus_bypass": solar_surplus_bypass,
            "battery_full_safeguard_block": battery_full_safeguard_block,
            "export_blocked_for_forecast": export_blocked_for_forecast,
            "export_forecast_guard": export_forecast_guard,
            "export_blocked_effective": export_blocked_effective,
            "battery_only_mode": battery_only_mode,
            "needs_ha_control_switch": d.needs_ha_control_switch,
            "demand_window_active": s.demand_window_active,
            "price_is_negative": s.price_is_negative,
            "feedin_is_negative": s.feedin_is_negative,
        }
        d.trace_values = {
            "battery_soc": s.battery_soc,
            "current_price": s.current_price,
            "feedin_price": s.feedin_price,
            "pv_kw": s.pv_kw,
            "load_kw": s.load_kw,
            "grid_import_power_kw": s.grid_import_power_kw,
            "grid_export_power_kw": s.grid_export_power_kw,
            "pv_surplus_actual": pv_surplus_actual,
            "pv_surplus_estimated": pv_surplus,
            "cap_kwh": cap,
            "bat_fill_need_kwh": bat_fill_need_kwh,
            "soc_required": soc_required,
            "sunrise_soc_target": sunrise_soc_target,
            "sunrise_fill_need_kwh": sunrise_fill_need_kwh,
            "hours_to_sunrise": hours_to_sunrise,
            "hours_to_sunset": hours_to_sunset,
            "export_min_soc": export_min_soc,
            "export_tier_limit": export_tier_limit,
            "morning_dump_limit": morning_dump_limit,
            "desired_export_limit": desired_export_limit,
            "desired_import_limit": desired_import_limit,
            "desired_ems_mode": desired_ems_mode,
            "desired_pv_max": desired_pv_max,
            "effective_import_for_math": effective_import_for_math,
            "battery_power_kw": battery_power_kw,
            "ess_charge_limit": d.ess_charge_limit,
            "ess_discharge_limit": d.ess_discharge_limit,
            "holdoff_entry_floor": self._holdoff_entry_floor,
            "current_export_limit": s.current_export_limit,
            "current_import_limit": s.current_import_limit,
            "current_pv_max_power_limit": s.current_pv_max_power_limit,
            "current_ems_mode": s.current_ems_mode,
            "export_branch": export_branch,
            "import_branch": import_branch,
            "cfg_morning_slow_charge_enabled": cfg.morning_slow_charge_enabled,
            "cfg_morning_slow_charge_rate_kw": cfg.morning_slow_charge_rate_kw,
            "cfg_morning_slow_export_start_margin_kw": cfg.morning_slow_export_start_margin_kw,
            "cfg_morning_slow_export_stop_margin_kw": cfg.morning_slow_export_stop_margin_kw,
            "cfg_morning_slow_export_ramp_up_step_kw": cfg.morning_slow_export_ramp_up_step_kw,
            "cfg_morning_slow_export_ramp_down_step_kw": cfg.morning_slow_export_ramp_down_step_kw,
            "cfg_morning_slow_export_probe_enabled": cfg.morning_slow_export_probe_enabled,
            "cfg_morning_slow_export_probe_step_kw": cfg.morning_slow_export_probe_step_kw,
            "cfg_morning_slow_export_probe_saturation_margin_kw": cfg.morning_slow_export_probe_saturation_margin_kw,
            "cfg_target_battery_charge": cfg.target_battery_charge,
            "cfg_max_price_threshold": cfg.max_price_threshold,
            "cfg_export_threshold_low": cfg.export_threshold_low,
            "cfg_export_threshold_medium": cfg.export_threshold_medium,
            "cfg_export_threshold_high": cfg.export_threshold_high,
            "cfg_export_limit_low": cfg.export_limit_low,
            "cfg_export_limit_medium": cfg.export_limit_medium,
            "cfg_export_limit_high": cfg.export_limit_high,
            "cfg_min_export_target_soc": cfg.min_export_target_soc,
            "cfg_min_soc_floor": cfg.min_soc_floor,
            "cfg_sunrise_export_relax_percent": cfg.sunrise_export_relax_percent,
            "cfg_pv_max_power_normal": cfg.pv_max_power_normal,
        }

        return d

    # ------------------------------------------------------------------
    # 3. Apply decisions to Home Assistant
    # ------------------------------------------------------------------

    async def _apply(self, s: SolarState, d: Decision) -> None:
        cfg = self.cfg

        # If in a manual mode, skip optimizer actions
        if s.sigenergy_mode not in {cfg.automated_option, ""}:
            logger.debug("Manual mode active (%s), skipping apply", s.sigenergy_mode)
            return

        ha = self.ha
        effective_ha_control = s.ha_control_enabled or d.needs_ha_control_switch

        # Auto-enable HA control switch if needed
        if d.needs_ha_control_switch and not s.ha_control_enabled:
            logger.info("Auto-enabling HA control switch")
            await ha.turn_on(cfg.ha_control_switch)

        if not effective_ha_control:
            return

        # EMS mode
        if s.current_ems_mode != d.ems_mode:
            logger.info("EMS mode: %s → %s", s.current_ems_mode, d.ems_mode)
            await ha.select_option(cfg.ems_mode_select, d.ems_mode)

        # Export limit
        near_zero = 0.011
        export_val = d.export_limit if d.export_limit > 0 else 0.01
        export_turning_on = s.current_export_limit <= near_zero and export_val > near_zero
        export_turning_off = s.current_export_limit > near_zero and export_val <= near_zero
        if abs(export_val - s.current_export_limit) >= cfg.min_change_threshold or export_turning_on or export_turning_off:
            await ha.set_number(cfg.grid_export_limit, export_val)

        # Import limit
        import_val = 0.01 if d.import_limit == 0 else d.import_limit
        if standby := d.standby_holdoff_active:
            import_val = 0.01
        import_turning_on = s.current_import_limit <= near_zero and import_val > near_zero
        import_turning_off = s.current_import_limit > near_zero and import_val <= near_zero
        if abs(import_val - s.current_import_limit) >= cfg.min_change_threshold or import_turning_on or import_turning_off:
            await ha.set_number(cfg.grid_import_limit, import_val)

        # ESS charge / discharge limits
        if cfg.ess_max_charging_limit:
            await ha.set_number(cfg.ess_max_charging_limit, d.ess_charge_limit)
        if cfg.ess_max_discharging_limit and not d.morning_slow_charge_active:
            await ha.set_number(cfg.ess_max_discharging_limit, d.ess_discharge_limit)

        # PV max power limit
        if abs(d.pv_max_power_limit - s.current_pv_max_power_limit) > 0.05:
            await ha.set_number(cfg.pv_max_power_limit, d.pv_max_power_limit)

        # Reason text helper
        reason = d.outcome_reason[:250]
        if reason:
            await ha.set_input_text(cfg.reason_text_helper, reason)

        # Min SoC to sunrise helper — clamp to 100 for HA entity bounds; raw value may
        # exceed 100 when overnight load exceeds full battery capacity, which is valid
        # for internal logic but rejected by input_number entities with max: 100.
        await ha.set_input_number(cfg.min_soc_to_sunrise_helper, min(d.min_soc_to_sunrise, 100.0))

        logger.debug(
            "Applied: mode=%s exp=%.1f imp=%.1f pv=%.1f | %s",
            d.ems_mode, d.export_limit, d.import_limit, d.pv_max_power_limit,
            d.outcome_reason[:80]
        )

    # ------------------------------------------------------------------
    # 4. Manual mode application (mirrors sigenergy_manual_control.yaml)
    # ------------------------------------------------------------------

    async def apply_manual_mode(self, mode_label: str) -> None:
        """Push EMS settings for a manual mode selection."""
        cfg = self.cfg
        ha = self.ha

        # Update the input_select in HA
        await ha.select_option(cfg.sigenergy_mode_select, mode_label)

        if mode_label == cfg.automated_option:
            # Re-enable the optimiser (nothing else needed — next tick applies)
            logger.info("Mode → Automated")
            return

        # All manual modes disable the optimizer for one cycle
        # (the next _apply will skip because sigenergy_mode != "Automated")
        logger.info("Manual mode → %s", mode_label)

        if mode_label == cfg.manual_option:
            return  # just disables optimizer, no limit changes

        # Resolve rated limits from live state, then last-known-good cache.
        import_cap, export_cap = self.get_power_caps_kw(self._last_state)

        block = cfg.block_flow_limit_value
        pv_max = cfg.pv_max_power_value
        ess_charge = cfg.ess_charge_limit_value
        ess_discharge = cfg.ess_discharge_limit_value

        if mode_label == cfg.full_export_option:
            await ha.select_option(cfg.ems_mode_select, MODE_CMD_DISCHARGE_PV)
            await ha.set_number(cfg.grid_export_limit, export_cap)
            await ha.set_number(cfg.grid_import_limit, block)
        elif mode_label == cfg.full_import_option:
            await ha.select_option(cfg.ems_mode_select, MODE_CMD_CHARGE_GRID)
            await ha.set_number(cfg.grid_export_limit, block)
            await ha.set_number(cfg.grid_import_limit, import_cap)
        elif mode_label == cfg.full_import_pv_option:
            await ha.select_option(cfg.ems_mode_select, MODE_CMD_CHARGE_PV)
            await ha.set_number(cfg.grid_export_limit, block)
            await ha.set_number(cfg.grid_import_limit, import_cap)
        elif mode_label == cfg.block_flow_option:
            await ha.select_option(cfg.ems_mode_select, MODE_MAX_SELF)
            await ha.set_number(cfg.grid_export_limit, block)
            await ha.set_number(cfg.grid_import_limit, block)

        if cfg.ess_max_charging_limit:
            await ha.set_number(cfg.ess_max_charging_limit, ess_charge)
        if cfg.ess_max_discharging_limit:
            await ha.set_number(cfg.ess_max_discharging_limit, ess_discharge)
        await ha.set_number(cfg.pv_max_power_limit, pv_max)

    # ------------------------------------------------------------------
    # Notification helpers
    # ------------------------------------------------------------------

    async def _handle_notifications(self, s: SolarState, d: Decision, prev: Optional[Decision], prev_state: Optional[SolarState] = None) -> None:
        cfg = self.cfg
        if not cfg.notification_service:
            return

        notify = lambda title, msg: self.ha.send_notification(cfg.notification_service, title, msg)
        if prev is None:
            self._notif_export_active = d.export_limit > 0.011
            self._prev_demand_window = s.demand_window_active
            return

        export_session_kwh = max(0.0, s.daily_export_kwh - s.export_session_start_kwh)
        import_session_kwh = max(0.0, s.daily_import_kwh - s.import_session_start_kwh)

        # Debounce export start notifications so tiny control flaps do not spam users.
        export_near_zero = 0.011
        export_active_now = d.export_limit > export_near_zero
        export_active_prev = self._notif_export_active
        if export_active_prev is None:
            export_active_prev = prev.export_limit > export_near_zero
        export_started = (not export_active_prev) and export_active_now
        export_stopped = export_active_prev and (not export_active_now)
        self._notif_export_active = export_active_now

        # Export started
        if export_started:
            await self.ha.set_input_number(cfg.export_session_start, s.daily_export_kwh)
            await self.ha.logbook_log("SigEnergy Export",
                f"Export ENABLED → {d.export_limit:.1f} kW  FIT={s.feedin_price:.3f} $/kWh")
            now = datetime.now(timezone.utc)
            last_notice = self._last_export_start_notice_at
            if last_notice and (now - last_notice) < timedelta(minutes=20):
                logger.debug("Suppressing duplicate export started notification within cooldown window")
            else:
                self._last_export_start_notice_at = now
                if s.last_export_notification != "started":
                    if cfg.notify_export_started_stopped:
                        await notify("📤 SigEnergy: Export Started",
                            f"💲 FIT: {s.feedin_price:.3f} $/kWh\n"
                            f"⚡ Limit: {d.export_limit:.1f} kW\n"
                            f"🔋 Battery: {s.battery_soc:.0f}%\n"
                            f"🌙 Night: {d.is_evening_or_night}")
                    await self.ha.set_input_text(cfg.last_export_notification, "started")

        # Export stopped
        if export_stopped:
            await self.ha.logbook_log("SigEnergy Export",
                f"Export DISABLED → Session {export_session_kwh:.3f} kWh  FIT={s.feedin_price:.3f} $/kWh")
            if s.last_export_notification != "stopped":
                if cfg.notify_export_started_stopped:
                    await notify("🛑 SigEnergy: Export Stopped",
                        f"📤 Session: {export_session_kwh:.3f} kWh\n"
                        f"📈 Daily Total: {s.daily_export_kwh:.3f} kWh\n"
                        f"🔋 Battery: {s.battery_soc:.0f}%\n"
                        f"💲 FIT: {s.feedin_price:.3f} $/kWh")
                await self.ha.set_input_text(cfg.last_export_notification, "stopped")

        # Import started/stopped use near-zero semantics because holdoff mode uses 0.01
        near_zero = 0.011
        prev_import_active = prev.import_limit > near_zero
        now_import_active = d.import_limit > near_zero

        # Import started
        if not prev_import_active and now_import_active:
            await self.ha.set_input_number(cfg.import_session_start, s.daily_import_kwh)
            await self.ha.logbook_log("SigEnergy Import",
                f"Import ENABLED → {d.import_limit:.1f} kW  Price={s.current_price}")
            if s.last_import_notification != "started":
                if cfg.notify_import_started_stopped:
                    await notify("⚡ SigEnergy: Import Started",
                        f"💲 Price: {s.current_price:.3f} $/kWh\n"
                        f"📥 Limit: {d.import_limit:.1f} kW\n"
                        f"🔋 Battery: {s.battery_soc:.0f}%\n"
                        f"🌙 Night: {d.is_evening_or_night}")
                await self.ha.set_input_text(cfg.last_import_notification, "started")

        # Import stopped
        if prev_import_active and not now_import_active:
            await self.ha.logbook_log("SigEnergy Import",
                f"Import DISABLED → Session {import_session_kwh:.3f} kWh")
            if s.last_import_notification != "stopped":
                if cfg.notify_import_started_stopped:
                    await notify("🛑 SigEnergy: Import Stopped",
                        f"📥 Session: {import_session_kwh:.3f} kWh\n"
                        f"📈 Daily Total: {s.daily_import_kwh:.3f} kWh\n"
                        f"💲 Last price: ${s.current_price:.3f}/kWh\n"
                        f"🔋 Battery: {s.battery_soc:.0f}%")
                await self.ha.set_input_text(cfg.last_import_notification, "stopped")

        # Battery alerts
        prev_soc_was_ok = prev_state is None or prev_state.battery_soc >= d.battery_soc_required_to_sunrise
        if cfg.notify_battery_alerts and s.battery_soc < d.battery_soc_required_to_sunrise and prev_soc_was_ok:
            await notify("⚠️ Battery below reserve SoC",
                f"Battery below reserve ({d.battery_soc_required_to_sunrise:.0f}%): {s.battery_soc:.0f}%")

        if cfg.notify_battery_alerts and s.battery_soc <= 1 and (prev_state is None or prev_state.battery_soc > 1):
            await notify("🪫 Battery Empty!", f"Battery SoC: {s.battery_soc:.0f}%")

        if cfg.notify_battery_alerts and s.battery_soc >= 99 and (prev_state is None or prev_state.battery_soc < 99):
            await notify("🔋 Battery Full!", f"Battery SoC: {s.battery_soc:.0f}%")

        if cfg.notify_price_spike_alert and s.price_spike_active and (not prev or not prev.export_spike_active):
            await notify("📈 Price Spike Active",
                f"Buy: ${s.current_price:.3f}/kWh\nFIT: ${s.feedin_price:.3f}/kWh")

        if cfg.notify_demand_window_alert and s.demand_window_active and not self._prev_demand_window:
            await notify("⏱️ Demand Window In Effect",
                "Demand window active; import is blocked until it ends.")
        self._prev_demand_window = s.demand_window_active

    async def _handle_daily_summaries(self, s: SolarState, d: Decision) -> None:
        cfg = self.cfg
        if not cfg.notification_service:
            return
        now = datetime.now()
        notify = lambda title, msg: self.ha.send_notification(cfg.notification_service, title, msg)

        if cfg.notify_daily_summary:
            t = self._today_at(cfg.daily_summary_time)
            if abs((now - t).total_seconds()) < cfg.poll_interval_seconds:
                if self._last_daily_summary_date != now.date():
                    self._last_daily_summary_date = now.date()
                    await notify("☀️ SigEnergy Summary",
                        f"🔌 Use: {s.daily_load_kwh:.2f} kWh\n"
                        f"☀️ PV: {s.daily_pv_kwh:.2f} kWh\n"
                        f"🔋 Batt: +{s.daily_battery_charge_kwh:.2f} / -{s.daily_battery_discharge_kwh:.2f} kWh\n"
                        f"📥 Import: {s.daily_import_kwh:.2f} kWh\n"
                        f"📤 Export: {s.daily_export_kwh:.2f} kWh\n"
                        f"🔚 SoC: {s.battery_soc:.0f}%")

        if cfg.notify_morning_summary:
            t = self._today_at(cfg.morning_summary_time)
            if abs((now - t).total_seconds()) < cfg.poll_interval_seconds:
                if self._last_morning_summary_date != now.date():
                    self._last_morning_summary_date = now.date()
                    await notify("🌅 SigEnergy Morning",
                        f"☀️ PV forecast today: {s.forecast_today_kwh:.1f} kWh\n"
                        f"🔋 Batt discharge so far: {s.daily_battery_discharge_kwh:.2f} kWh\n"
                        f"🔚 SoC: {s.battery_soc:.0f}%")

    # ==================================================================
    # Private calculation helpers (pure functions; no I/O)
    # ==================================================================

    @staticmethod
    def _today_at(time_str: str) -> datetime:
        """Return today's date combined with a HH:MM or HH:MM:SS string."""
        try:
            parts = time_str.split(":")
            h, m = int(parts[0]), int(parts[1])
            s = int(parts[2]) if len(parts) > 2 else 0
            return datetime.now().replace(hour=h, minute=m, second=s, microsecond=0)
        except (ValueError, IndexError, AttributeError):
            logger.warning("Invalid time string in config: %r — using end of day", time_str)
            return datetime.now().replace(hour=23, minute=59, second=59, microsecond=0)

    def _day_window(self, s: SolarState):
        """Return (day_start_ts, day_end_ts) in Unix seconds."""
        now_ts = datetime.now().timestamp()
        sunrise_ts = s.next_sunrise_ts or now_ts
        if s.sun_above_horizon:
            actual_sunrise = sunrise_ts - 86400
        else:
            actual_sunrise = sunrise_ts
        day_start = actual_sunrise + 3600

        sunset_ts = s.next_sunset_ts or now_ts
        day_end = sunset_ts - self.cfg.evening_mode_hours_before_sunset * 3600
        return day_start, day_end

    def _battery_soc_required_to_sunrise(self, s: SolarState) -> float:
        """Dynamic overnight SoC target based on current load until sunrise."""
        cfg = self.cfg
        cap = s.battery_capacity_kwh
        sunrise_ts = s.next_sunrise_ts
        if not sunrise_ts:
            return cfg.night_reserve_soc + cfg.night_reserve_buffer

        now_ts = datetime.now().timestamp()
        sunset_ts = s.next_sunset_ts or now_ts
        if s.sun_above_horizon:
            start_ts = sunset_ts
        else:
            start_ts = now_ts

        target_ts = sunrise_ts + 3600
        hours = max(0.0, (target_ts - start_ts) / 3600)
        load_kw = s.load_kw
        energy_need_kwh = load_kw * hours * cfg.sunrise_safety_factor
        need_pct = (energy_need_kwh / cap) * 100 if cap > 0 else 0
        target = need_pct + cfg.sunrise_buffer_percent
        return max(target, cfg.sunrise_reserve_soc)

    def _negative_price_forecast_ahead(self, s: SolarState, now_ts: float) -> bool:
        cutoff = now_ts + self.cfg.negative_price_forecast_lookahead_hours * 3600
        for f in s.price_forecast_entries:
            if not isinstance(f, dict):
                continue
            try:
                ts = self._parse_ts(f.get(self.cfg.price_forecast_time_key, ""))
                price = float(f.get(self.cfg.price_forecast_value_key, 0))
                if ts and ts <= cutoff and price < 0:
                    return True
            except Exception:
                pass
        return False

    def _negative_price_before_cutoff(self, s: SolarState, now_ts: float) -> bool:
        cutoff_dt = self._today_at(self.cfg.standby_holdoff_end_time)
        if datetime.now() >= cutoff_dt:
            return False
        cutoff_ts = cutoff_dt.timestamp()
        for f in s.price_forecast_entries:
            if not isinstance(f, dict):
                continue
            try:
                ts = self._parse_ts(f.get(self.cfg.price_forecast_time_key, ""))
                price = float(f.get(self.cfg.price_forecast_value_key, 0))
                if ts and ts <= cutoff_ts and price < 0:
                    return True
            except Exception:
                pass
        return False

    def _productive_solar_end_ts(self, s: SolarState, sunset_ts: float, now_ts: float) -> Optional[float]:
        cfg = self.cfg
        threshold = cfg.productive_solar_threshold_kw
        forecasts = s.solcast_detailed
        if not forecasts:
            return None
        found = None
        for f in reversed(forecasts):
            if not isinstance(f, dict):
                continue
            try:
                f_ts = self._parse_ts(f.get("period_start", ""))
                pv_kw = float(f.get("pv_estimate", 0))
                if f_ts and f_ts <= sunset_ts and pv_kw >= threshold:
                    found = f_ts
                    break
            except Exception:
                pass
        return found

    def _morning_dump_window(self, s: SolarState, actual_sunrise_ts: float):
        cfg = self.cfg
        day_start = actual_sunrise_ts + 3600
        hours_before = cfg.morning_dump_hours_before_sunrise
        dump_start = day_start - hours_before * 3600
        dump_end = actual_sunrise_ts + 3600
        return dump_start, dump_end

    def _morning_dump_active(self, s: SolarState, dump_start, dump_end,
                              productive_solar_end_ts, bat_fill_need_kwh, now_ts) -> bool:
        cfg = self.cfg
        if not cfg.morning_dump_enabled:
            return False
        if dump_start is None or dump_end is None:
            return False
        if not (dump_start <= now_ts <= dump_end):
            return False

        # Check forecast can refill
        ns_total = 0.0
        for f in s.solcast_detailed:
            if not isinstance(f, dict):
                continue
            try:
                f_ts = self._parse_ts(f.get("period_start", ""))
                pv_kw = float(f.get("pv_estimate", 0))
                if f_ts and dump_end <= f_ts < (productive_solar_end_ts or now_ts + 86400):
                    ns_total += pv_kw * cfg.solcast_forecast_period_hours
            except Exception:
                pass
        load_need = ((productive_solar_end_ts or now_ts + 86400) - dump_end) / 3600 * s.load_kw
        return ns_total >= (bat_fill_need_kwh + load_need) * cfg.forecast_safety_charging

    def _morning_slow_charge_active(self, s: SolarState, now: datetime,
                                     now_ts: float, slow_end_ts: float) -> bool:
        cfg = self.cfg
        if not cfg.morning_slow_charge_enabled:
            return False
        target_dt = self._today_at(cfg.morning_slow_charge_until)
        if now >= target_dt or now.hour < 5:
            return False
        if not s.sun_above_horizon and now.hour < 7:
            return False
        if s.feedin_price <= cfg.morning_slow_charge_min_feedin_price:
            return False

        # Forecast check
        target_ts = target_dt.timestamp()
        ns_total = 0.0
        for f in s.solcast_detailed:
            if not isinstance(f, dict):
                continue
            try:
                f_ts = self._parse_ts(f.get("period_start", ""))
                pv_kw = float(f.get("pv_estimate", 0))
                if f_ts and target_ts <= f_ts < slow_end_ts:
                    ns_total += pv_kw * cfg.solcast_forecast_period_hours
            except Exception:
                pass
        cap = s.battery_capacity_kwh
        bat_fill_need = max(0.0, cap - s.available_discharge_energy_kwh)
        load_need = ((slow_end_ts - target_ts) / 3600) * cfg.morning_slow_charge_base_load_kw
        return ns_total >= (bat_fill_need + load_need) * cfg.forecast_safety_charging

    def _evening_export_boost_active(self, s: SolarState, now_ts: float,
                                      productive_solar_end_ts, sunrise_soc_target, bat_fill_need_kwh) -> bool:
        cfg = self.cfg
        if not cfg.evening_boost_enabled:
            return False
        if productive_solar_end_ts is None or now_ts < productive_solar_end_ts:
            return False
        midnight = (datetime.now() + timedelta(days=1)).replace(hour=0, minute=0, second=0).timestamp()
        if now_ts >= midnight:
            return False

        overnight_covered = s.battery_soc > (sunrise_soc_target + 10)
        tomorrow_will_refill = (
            s.forecast_tomorrow_kwh >= bat_fill_need_kwh * cfg.forecast_safety_export
        )
        # Check no high FIT forecast overnight
        tomorrow_6am = (datetime.now() + timedelta(days=1)).replace(hour=6, minute=0, second=0).timestamp()
        no_high_fit = True
        for f in s.feedin_forecast_entries:
            if not isinstance(f, dict):
                continue
            try:
                ts = self._parse_ts(f.get(cfg.price_forecast_time_key, ""))
                price = float(f.get(cfg.feedin_forecast_value_key, 0))
                if ts and now_ts <= ts <= tomorrow_6am and price >= cfg.export_threshold_medium:
                    no_high_fit = False
                    break
            except Exception:
                pass
        return no_high_fit and overnight_covered and tomorrow_will_refill

    def _solar_surplus_bypass(self, s: SolarState, morning_slow_charge_active: bool,
                               cap: float, pv_surplus: float, prev_desired_mode: str = "") -> bool:
        cfg = self.cfg
        if not cfg.solar_surplus_bypass_enabled or morning_slow_charge_active:
            return False
        start_thresh = cap * cfg.solar_surplus_start_multiplier
        stop_thresh = cap * cfg.solar_surplus_stop_multiplier
        pv_over_load = pv_surplus > cfg.solar_surplus_min_pv_margin
        start_ok = s.forecast_remaining_kwh >= start_thresh
        continue_ok = (
            s.forecast_remaining_kwh >= stop_thresh
            and (s.current_ems_mode in DISCHARGE_MODES or prev_desired_mode in DISCHARGE_MODES)
        )
        return pv_over_load and (start_ok or continue_ok)

    def _battery_full_safeguard_block(self, s: SolarState, now_ts: float,
                                       sunset_ts: float, bat_fill_need_kwh: float,
                                       is_evening_or_night: bool) -> bool:
        cfg = self.cfg
        if not cfg.battery_full_safeguard_enabled or is_evening_or_night:
            return False
        if bat_fill_need_kwh <= 0:
            return False
        target_ts = sunset_ts - cfg.battery_full_hours_before_sunset * 3600
        if now_ts >= target_ts:
            return True

        # Forecast check
        ns_total = 0.0
        max_charge_kw = s.ess_max_charge_kw if 0 < s.ess_max_charge_kw < 999 else cfg.ess_charge_limit_value
        for f in s.solcast_detailed:
            if not isinstance(f, dict):
                continue
            try:
                f_ts = self._parse_ts(f.get("period_start", ""))
                pv_kw = float(f.get("pv_estimate", 0))
                if f_ts and now_ts <= f_ts < target_ts:
                    net = max(pv_kw - s.load_kw, 0.0)
                    usable = min(net, max_charge_kw) * cfg.solcast_forecast_period_hours
                    ns_total += usable
            except Exception:
                pass
        return (ns_total * cfg.battery_full_forecast_multiplier) < bat_fill_need_kwh

    def _export_blocked_for_forecast(self, s: SolarState, pv_surplus: float,
                                      is_evening_or_night: bool, bat_fill_need_kwh: float,
                                      hours_to_sunset: float, close_to_sunset: bool) -> bool:
        cfg = self.cfg
        if s.battery_soc >= cfg.export_guard_relax_soc or close_to_sunset:
            return False
        allow_full = (
            s.battery_soc >= cfg.max_battery_soc
            and not is_evening_or_night
            and pv_surplus > cfg.min_grid_transfer_kw
        )
        if is_evening_or_night or allow_full or s.forecast_remaining_kwh == 0:
            return False
        est_load = s.load_kw * hours_to_sunset
        net_fc = s.forecast_remaining_kwh - est_load
        return net_fc < bat_fill_need_kwh * cfg.forecast_safety_export

    def _export_forecast_guard(self, s: SolarState, sunrise_fill_need_kwh: float,
                                is_evening_or_night: bool, evening_boost: bool,
                                close_to_sunset: bool) -> bool:
        cfg = self.cfg
        if s.battery_soc >= cfg.export_guard_relax_soc or close_to_sunset:
            return False
        if is_evening_or_night:
            floor = cfg.evening_aggressive_floor if evening_boost else cfg.min_export_target_soc
            return s.battery_soc < floor
        if sunrise_fill_need_kwh <= 0:
            return False
        required = sunrise_fill_need_kwh * cfg.forecast_safety_export
        return s.forecast_remaining_kwh < required

    def _export_tier_limit(self, s: SolarState, spike: bool, solar_override: bool,
                            pv_safeguard: bool, boost: bool, surplus_bypass: bool) -> float:
        cfg = self.cfg
        fit = s.feedin_price
        bsoc = s.battery_soc
        below_boost_floor = bsoc < cfg.evening_aggressive_floor
        below_target = bsoc < cfg.min_export_target_soc

        if spike:
            return cfg.export_limit_high
        if solar_override:
            return cfg.export_limit_high
        if bsoc >= 99 and fit >= 0.01:
            return cfg.export_limit_high
        if fit < cfg.export_threshold_low:
            return 0.0
        if fit >= cfg.export_threshold_high:
            return cfg.export_limit_high
        if fit >= cfg.export_threshold_medium:
            if pv_safeguard:
                return 0.0
            frac = (fit - cfg.export_threshold_medium) / (cfg.export_threshold_high - cfg.export_threshold_medium)
            return cfg.export_limit_medium + frac * (cfg.export_limit_high - cfg.export_limit_medium)
        # low tier
        if boost and not below_boost_floor:
            frac = (fit - cfg.export_threshold_low) / max(cfg.export_threshold_medium - cfg.export_threshold_low, 0.001)
            return cfg.export_limit_low + frac * (cfg.export_limit_medium - cfg.export_limit_low)
        if (below_target or pv_safeguard) and not surplus_bypass:
            return 0.0
        frac = (fit - cfg.export_threshold_low) / max(cfg.export_threshold_medium - cfg.export_threshold_low, 0.001)
        return cfg.export_limit_low + frac * (cfg.export_limit_medium - cfg.export_limit_low)

    def _desired_export_limit(self, s: SolarState, spike: bool, solar_override: bool,
                               export_blocked: bool, forecast_guard: bool,
                               export_min_soc: float, positive_fit_override: bool,
                               surplus_bypass: bool, evening_boost: bool,
                               morning_dump: bool, morning_dump_limit: float,
                               battery_full_safeguard_block: bool,
                               tier_limit: float, hours_to_sunrise: float,
                               cap: float, pv_surplus: float,
                               is_evening_or_night: bool,
                               morning_slow_charge_active: bool,
                               within_morning_grace: bool) -> float:
        cfg = self.cfg
        fit_cents = s.feedin_price_cents
        bsoc = s.battery_soc

        if fit_cents < 1:
            return 0.0

        high_price = s.feedin_price >= cfg.export_threshold_high

        if battery_full_safeguard_block and not (high_price or spike):
            return 0.0

        effective_export_floor = cfg.evening_aggressive_floor if evening_boost else cfg.min_export_target_soc

        # No PV surplus during daytime → no export
        if (pv_surplus == 0 and not is_evening_or_night and not high_price
                and not spike and not evening_boost):
            return 0.0

        if morning_dump:
            return morning_dump_limit

        if s.price_is_negative or s.feedin_is_negative:
            return 0.0

        if (bsoc < effective_export_floor and not within_morning_grace
                and not morning_slow_charge_active and not surplus_bypass):
            return 0.0

        if (export_blocked or forecast_guard) and not surplus_bypass:
            return 0.0

        bypass_min_soc = high_price or spike or surplus_bypass or positive_fit_override
        if not bypass_min_soc and bsoc <= export_min_soc:
            if not (morning_slow_charge_active and pv_surplus >= cfg.morning_slow_charge_rate_kw + cfg.min_grid_transfer_kw):
                return 0.0

        # Morning slow charge with PV surplus
        if morning_slow_charge_active:
            start_threshold = cfg.morning_slow_charge_rate_kw + cfg.morning_slow_export_start_margin_kw
            stop_threshold = cfg.morning_slow_charge_rate_kw + cfg.morning_slow_export_stop_margin_kw
            current_export = s.current_export_limit if s.current_export_limit > 0.05 else 0.0
            measured_export = max(0.0, float(s.grid_export_power_kw or 0.0))
            export_is_open = current_export >= cfg.min_grid_transfer_kw
            has_surplus_window = pv_surplus >= start_threshold or (export_is_open and pv_surplus >= stop_threshold)
            if not has_surplus_window:
                return 0.0

            # Export can use PV left after honoring slow-charge target; avoid double-subtracting min transfer.
            available = max(pv_surplus - cfg.morning_slow_charge_rate_kw, 0.0)
            raw_limit = min(available, s.ess_max_discharge_kw)

            # Anti-curtailment probe: if export is already saturated at its own cap,
            # gently nudge the cap upward so PV can reveal hidden headroom.
            probe_enabled = bool(cfg.morning_slow_export_probe_enabled)
            saturation_margin = max(0.05, cfg.morning_slow_export_probe_saturation_margin_kw)
            probe_step = max(0.1, cfg.morning_slow_export_probe_step_kw)
            near_export_cap = measured_export >= max(cfg.min_grid_transfer_kw, current_export - saturation_margin)
            no_grid_import_pressure = (s.grid_import_power_kw is None) or (float(s.grid_import_power_kw) <= 0.2)
            if probe_enabled and export_is_open and near_export_cap and no_grid_import_pressure:
                raw_limit = max(raw_limit, current_export + probe_step)

            raw_limit = min(raw_limit, s.ess_max_discharge_kw)
            if raw_limit <= 0:
                return 0.0
            if raw_limit < cfg.min_grid_transfer_kw:
                raw_limit = cfg.min_grid_transfer_kw

            # Smooth morning slow-charge export setpoint changes to reduce oscillation.
            if current_export <= 0:
                return round(raw_limit, 1)
            if raw_limit > current_export:
                ramped = min(raw_limit, current_export + cfg.morning_slow_export_ramp_up_step_kw)
            else:
                ramped = max(raw_limit, current_export - cfg.morning_slow_export_ramp_down_step_kw)
            return round(max(ramped, 0.0), 1)

        if high_price or spike:
            cap_val = min(tier_limit, cfg.export_limit_high)
            if spike and cfg.export_spike_full_power:
                cap_val = max(tier_limit, cfg.cap_total_import)
            limit = min(cap_val, s.ess_max_discharge_kw)
            return max(cfg.min_grid_transfer_kw, round(limit, 1)) if limit > 0 else 0.0

        if positive_fit_override:
            eff_tier = tier_limit if tier_limit > 0 else cfg.export_limit_low
            limit = min(eff_tier, s.ess_max_discharge_kw)
            return max(cfg.min_grid_transfer_kw, round(limit, 1)) if limit > 0 else 0.0

        if tier_limit <= 0:
            return 0.0

        # Scale by SoC headroom
        diff = bsoc - export_min_soc
        span = max(self._export_soc_span_dynamic(s, hours_to_sunrise, is_evening_or_night, cap), 0.1)
        scale_soc = max(0.0, min(1.0, diff / span))

        if solar_override:
            surplus_kw = max(s.pv_kw - s.load_kw, 0.0)
            override_cap = min(surplus_kw, cfg.export_limit_high, tier_limit)
            limit = min(override_cap, s.ess_max_discharge_kw)
            return round(limit, 1) if limit > 0 else 0.0

        hours = max(hours_to_sunrise, 0.01)
        discharge_window = max(cfg.export_discharge_window_hours, 1.0)
        hours_div = min(hours, discharge_window)
        headroom_kwh = (diff / 100) * cap
        safe_kw_base = headroom_kwh / max(hours_div, 1.0)
        boost_fac = min(1.5, 1 + (tier_limit / max(cfg.export_limit_high, 1.0)) * 0.3)
        safe_kw = safe_kw_base * boost_fac
        safe_cap = min(safe_kw, tier_limit)
        raw_limit = tier_limit * scale_soc * 0.9
        final_limit = min(raw_limit, safe_cap)
        limit = min(final_limit, s.ess_max_discharge_kw)

        # PV surplus cap during normal daytime
        if not is_evening_or_night and not high_price and not spike:
            if bsoc >= 99:
                pv_surplus_full = max(max(s.pv_kw, s.solar_power_now_kw) - s.load_kw, 0.0)
                limit = min(limit, pv_surplus_full)
            else:
                raw_surplus = max(s.pv_kw - s.load_kw, 0.0)
                max_charge = cfg.target_battery_charge
                charge_priority = 0 if surplus_bypass else (max_charge if bsoc < 98 else 0)
                pv_surplus_net = max(raw_surplus - charge_priority, 0.0)
                limit = min(limit, pv_surplus_net)

        if limit <= 0:
            return 0.0
        if limit < cfg.min_grid_transfer_kw:
            return cfg.min_grid_transfer_kw
        return round(limit, 1)

    def _desired_import_limit(self, s: SolarState, morning_dump_active: bool,
                               demand_window_active: bool, standby_holdoff_active: bool,
                               feedin_price_ok: bool,
                               pv_surplus: float) -> float:
        cfg = self.cfg
        if morning_dump_active or demand_window_active:
            return 0.0
        if standby_holdoff_active:
            return 0.0

        # Negative price → full import
        if s.price_is_negative and s.current_price <= cfg.import_threshold_low:
            rated = s.ess_max_charge_kw
            if s.current_price <= cfg.import_threshold_high:
                return min(cfg.import_limit_high, rated)
            if s.current_price <= cfg.import_threshold_medium:
                return min(cfg.import_limit_medium, rated)
            return min(cfg.import_limit_low, rated)

        # Positive FIT → block import
        if feedin_price_ok:
            return 0.0

        # Price too high or battery at max
        if s.current_price > cfg.max_price_threshold:
            return 0.0

        # Battery full for topup
        if s.battery_soc >= cfg.daytime_topup_max_soc:
            return 0.0

        # PV sufficient
        if pv_surplus >= cfg.target_battery_charge:
            return 0.0

        # Cheap top-up
        if s.current_price <= cfg.max_price_threshold:
            return min(cfg.target_battery_charge, s.ess_max_charge_kw, cfg.cap_total_import)

        return 0.0

    def _desired_ems_mode(self, s: SolarState, morning_dump: bool, standby_holdoff: bool,
                           export_solar_override: bool, desired_export: float,
                           desired_import: float, export_min_soc: float,
                           sunrise_soc_target: float, within_morning_grace: bool,
                           export_blocked_forecast: bool,
                           is_evening_or_night: bool) -> str:
        cfg = self.cfg
        bsoc = s.battery_soc
        currently_discharging = s.current_ems_mode in DISCHARGE_MODES
        currently_charging = s.current_ems_mode in CHARGE_MODES

        def _charge_mode():
            if within_morning_grace and s.pv_kw < s.load_kw * 0.5:
                return MODE_MAX_SELF
            return MODE_CMD_CHARGE_PV

        if morning_dump:
            return MODE_CMD_DISCHARGE_PV
        if s.demand_window_active:
            return MODE_CMD_DISCHARGE_PV if desired_export > 0 else MODE_MAX_SELF
        if standby_holdoff and desired_export == 0:
            # Use stored floor from holdoff entry to avoid drift from forecast updates
            holdoff_discharge_floor = self._holdoff_entry_floor or (sunrise_soc_target + cfg.soc_hysteresis)
            return MODE_MAX_SELF if bsoc < holdoff_discharge_floor else MODE_CMD_DISCHARGE_PV
        if desired_import > 0 and not s.price_is_negative:
            return _charge_mode()
        if export_solar_override:
            return MODE_CMD_DISCHARGE_PV
        if s.price_is_negative and s.current_price <= cfg.import_threshold_low:
            return MODE_CMD_CHARGE_GRID
        if s.feedin_is_negative:
            return MODE_MAX_SELF
        if desired_export > 0:
            return MODE_CMD_DISCHARGE_PV
        if not export_blocked_forecast and bsoc > export_min_soc + cfg.soc_hysteresis:
            pv_surplus = max(s.pv_kw - s.load_kw, 0.0)
            if pv_surplus == 0 and not is_evening_or_night:
                return MODE_MAX_SELF
            if currently_discharging and s.feedin_price >= cfg.export_threshold_low * cfg.export_hysteresis_percent:
                return MODE_CMD_DISCHARGE_PV
            if s.feedin_price >= cfg.export_threshold_low:
                return MODE_CMD_DISCHARGE_PV
            return MODE_MAX_SELF
        # Cheap import conditions
        grid_limit_base = self._grid_limit_base(s, standby_holdoff)
        if (grid_limit_base > 0
                and s.feedin_price < cfg.export_threshold_low - cfg.price_hysteresis
                and bsoc < cfg.max_battery_soc - cfg.soc_hysteresis):
            return _charge_mode()
        if (currently_charging and grid_limit_base > 0
                and s.feedin_price < cfg.export_threshold_low + cfg.price_hysteresis
                and bsoc < cfg.max_battery_soc):
            return _charge_mode()
        return MODE_MAX_SELF

    def _grid_limit_base(self, s: SolarState, standby_holdoff_active: bool) -> float:
        """Determines base import limit before adjustments."""
        cfg = self.cfg
        price = s.current_price
        fit = s.feedin_price
        bsoc = s.battery_soc

        spike_low_soc = s.price_spike_active and bsoc < cfg.export_spike_min_soc
        if s.demand_window_active:
            return 0.0
        if price <= cfg.import_threshold_high and s.price_is_actual:
            return min(cfg.import_limit_high, s.ess_max_charge_kw)
        if price <= cfg.import_threshold_medium and s.price_is_actual:
            return min(cfg.import_limit_medium, s.ess_max_charge_kw)
        if price <= cfg.import_threshold_low and s.price_is_actual:
            return min(cfg.import_limit_low, s.ess_max_charge_kw)
        if standby_holdoff_active:
            return 0.0
        if spike_low_soc:
            return 0.0
        if fit >= cfg.export_threshold_low:
            return 0.0
        # Cheap topup
        if (price <= cfg.max_price_threshold
                and bsoc < cfg.daytime_topup_max_soc
                and s.forecast_remaining_kwh < s.battery_capacity_kwh * cfg.forecast_safety_charging):
            surplus = max(s.pv_kw - s.load_kw, 0.0)
            if surplus < cfg.target_battery_charge:
                return min(cfg.target_battery_charge, cfg.cap_total_import)
        return 0.0

    def _desired_pv_max_power(self, s: SolarState, standby_holdoff: bool,
                               battery_only: bool, morning_dump: bool,
                               morning_slow_charge: bool, desired_export: float) -> float:
        cfg = self.cfg
        cover_load = min(s.load_kw * 1.2, cfg.pv_max_power_normal)
        cover_load = max(round(cover_load, 0), 0.1)

        if s.price_is_negative and s.current_price <= cfg.import_threshold_low:
            return 0.1
        if s.feedin_is_negative and s.battery_soc >= 99:
            # FIT is negative and battery is full: curtail PV to approximately cover load only.
            return max(cover_load, 0.1)
        if standby_holdoff and desired_export == 0:
            return max(cover_load, 0.1)
        if battery_only:
            return max(cover_load, 0.1)
        if morning_dump:
            return cfg.pv_max_power_normal
        if morning_slow_charge and cfg.slow_charge_holdoff:
            load_kw = s.load_kw
            cap = load_kw + cfg.slow_charge_limit_kw
            cap = min(cap, cfg.pv_max_power_normal)
            pv_surplus = max(s.pv_kw - load_kw, 0.0)
            if pv_surplus >= cfg.min_grid_transfer_kw:
                return cfg.pv_max_power_normal
            return max(cap, 0.1)
        return cfg.pv_max_power_normal

    def _desired_ess_charge_limit(self, s: SolarState, desired_import: float,
                                   morning_slow_charge: bool, desired_export: float,
                                   pv_surplus: float) -> float:
        cfg = self.cfg
        hw_charge, _ = self.get_power_caps_kw(s)
        max_charge = max(0.1, hw_charge)
        if desired_import > 0:
            return min(max_charge, desired_import)
        if morning_slow_charge:
            slow = cfg.morning_slow_charge_rate_kw
            # Keep true slow-charge behavior; avoid charge spikes that collapse export.
            return round(min(slow, max_charge), 1)
        return max_charge

    def _desired_ess_discharge_limit(self, s: SolarState, standby_holdoff: bool,
                                      positive_fit_override: bool, evening_boost: bool) -> float:
        cfg = self.cfg
        _, hw_discharge = self.get_power_caps_kw(s)
        max_dis = max(0.1, hw_discharge)
        if s.price_is_negative and s.current_price <= cfg.import_threshold_low:
            return 0.01
        if positive_fit_override and s.battery_soc < cfg.min_export_target_soc:
            if evening_boost and s.battery_soc >= cfg.evening_aggressive_floor:
                return max_dis
            return 0.01
        if positive_fit_override:
            return max_dis if cfg.allow_positive_fit_battery_discharging else 0.01
        return max_dis

    def _export_soc_span_dynamic(self, s: SolarState, hours_to_sunrise: float,
                                  is_evening_or_night: bool, cap: float) -> float:
        if is_evening_or_night:
            span = (hours_to_sunrise * s.load_kw / max(cap, 0.1)) * 100
            return max(4.0, min(span, 25.0))
        return self.cfg.export_soc_span_day

    def _battery_eta(self, s: SolarState, battery_power_kw: float) -> str:
        bsoc = s.battery_soc
        if bsoc >= 100:
            return "Full"
        if bsoc <= 0:
            return "Empty"
        power_abs = abs(battery_power_kw)
        if power_abs < 0.2:
            return "idle"
        cap = s.battery_capacity_kwh
        if battery_power_kw > 0:
            soc_gap = 100 - bsoc
            if soc_gap <= 0:
                return "Full"
            mins = (cap * soc_gap / 100) / power_abs * 60
        else:
            avail = s.available_discharge_energy_kwh
            if avail <= 0:
                return "Empty"
            mins = avail / power_abs * 60
        if mins > 48 * 60:
            return "idle"
        mins = max(1, round(mins))
        if mins >= 1440:
            d = mins // 1440
            h = (mins % 1440) // 60
            return f"{d}d{h}h"
        if mins >= 60:
            h = mins // 60
            m = mins % 60
            return f"{h}h{m}m"
        return f"{mins}m"

    def _export_reason(self, s: SolarState, spike: bool, solar_override: bool,
                        morning_dump: bool, export_blocked: bool, forecast_guard: bool,
                        export_min_soc: float, pv_safeguard: bool, tier_limit: float,
                        morning_slow_charge: bool, surplus_bypass: bool, evening_boost: bool,
                        safeguard: bool, desired_export: float,
                        positive_fit_override: bool) -> str:
        cfg = self.cfg
        fit = s.feedin_price_cents
        c = s.current_price_cents
        fit_d = f"{fit:.0f}" if abs(fit) >= 1 else f"{fit:.1f}"
        c_d = f"{c:.0f}" if abs(c) >= 1 else f"{c:.1f}"
        est = "*" if s.price_is_estimated else ""
        ex_low = cfg.export_threshold_low * cfg.price_multiplier
        ex_low_d = f"{ex_low:.0f}" if abs(ex_low) >= 1 else f"{ex_low:.1f}"
        measured_export = s.grid_export_power_kw if isinstance(s.grid_export_power_kw, (int, float)) else None
        actual_export = max(float(measured_export), 0.0) if measured_export is not None else max(s.pv_kw - s.load_kw, 0.0)
        target_export = max(float(desired_export or 0.0), 0.0)
        export_kw_label = f"{actual_export:.1f}kW"
        if target_export > 0.01 and abs(actual_export - target_export) >= 0.2:
            export_kw_label = f"{actual_export:.1f}kW (set {target_export:.1f})"

        if s.price_is_negative:
            return f"Export blocked, price is negative ({c_d}¢{est})"
        if s.feedin_price_cents < 1:
            return f"Export blocked, FIT zero/negative ({fit_d}¢{est})"
        if safeguard and not (s.feedin_price >= cfg.export_threshold_high or spike):
            return f"Export blocked, saving for sunset ({s.battery_soc:.0f}% < 100%)"
        if morning_dump:
            return f"Exporting {export_kw_label}, Morning dump @ {fit_d}¢{est}, {s.battery_soc:.0f}%"
        if s.feedin_price >= cfg.export_threshold_high:
            return f"Exporting {export_kw_label}, High tier @ {fit_d}¢{est}"
        if spike:
            return f"Exporting {export_kw_label}, Spike @ {fit_d}¢{est}"
        if solar_override:
            return f"Exporting {export_kw_label}, Solar override{est}"
        if morning_slow_charge:
            return f"Exporting {export_kw_label}, Slow charge"
        if surplus_bypass:
            if actual_export <= 0.05:
                return f"Solar bypass active, waiting for surplus ({s.forecast_remaining_kwh:.1f}kWh left){est}"
            return f"Exporting {export_kw_label}, Solar bypass ({s.forecast_remaining_kwh:.1f}kWh left){est}"
        if (export_blocked or forecast_guard) and not surplus_bypass:
            return "Export blocked, low forecast"
        if s.battery_soc <= export_min_soc:
            return f"Export blocked, at {export_min_soc:.0f}% floor"
        effective_floor = cfg.evening_aggressive_floor if evening_boost else cfg.min_export_target_soc
        if s.battery_soc < effective_floor:
            return f"Export blocked, below {effective_floor:.0f}% target"
        if s.battery_soc >= 99 and s.feedin_price >= 0.01:
            return f"Exporting {export_kw_label}, Full battery @ {fit_d}¢{est}"
        if tier_limit <= 0:
            if pv_safeguard:
                return "Export blocked, forecast protection"
            return f"Export blocked, FIT {fit_d}¢{est} < {ex_low_d}¢"
        if s.feedin_price >= cfg.export_threshold_medium:
            return f"Exporting {export_kw_label}, Med tier @ {fit_d}¢{est}"
        if evening_boost:
            return f"Exporting {export_kw_label}, Low tier (boost) @ {fit_d}¢{est}"
        return f"Exporting {export_kw_label}, Low tier @ {fit_d}¢{est}"

    def _import_reason(self, s: SolarState, morning_dump: bool, standby_holdoff: bool,
                        sunrise_soc_target: float, desired_import: float,
                        pv_surplus: float) -> str:
        cfg = self.cfg
        c = s.current_price_cents
        c_d = f"{c:.0f}" if abs(c) >= 1 else f"{c:.1f}"
        est = "*" if s.price_is_estimated else ""
        ex_low = cfg.export_threshold_low * cfg.price_multiplier
        ex_low_d = f"{ex_low:.0f}" if abs(ex_low) >= 1 else f"{ex_low:.1f}"
        fit = s.feedin_price_cents
        fit_d = f"{fit:.0f}" if abs(fit) >= 1 else f"{fit:.1f}"

        if morning_dump:
            return "Import blocked, morning dump"
        if s.demand_window_active:
            return "Import blocked, demand window"
        if standby_holdoff:
            return "Import blocked, charge holdoff"
        if not (s.price_is_actual or s.price_is_estimated):
            return "Import blocked, price N/A"
        if s.price_is_actual and s.current_price <= 0:
            if s.current_price < 0:
                return f"Importing, paid price={c_d}¢"
            return "Importing, FREE"
        if s.feedin_price >= cfg.export_threshold_low:
            return f"Import blocked, FIT {fit_d}¢{est} > export min {ex_low_d}¢"
        if s.current_price > cfg.max_price_threshold and s.battery_soc >= sunrise_soc_target:
            return f"Import blocked, price too high ({c_d}¢{est})"
        if desired_import <= 0:
            if s.current_price > cfg.max_price_threshold:
                return f"Import blocked, price too high ({c_d}¢{est})"
            if s.battery_soc >= cfg.daytime_topup_max_soc:
                return "Import blocked, battery full"
            if pv_surplus >= cfg.target_battery_charge:
                return "Import blocked, PV sufficient"
            return "Import blocked, forecast sufficient"
        if s.price_is_negative:
            return f"Importing, paid price={c_d}¢"
        return f"Importing, cheap {c_d}¢{est}"

    @staticmethod
    def _parse_ts(value) -> Optional[float]:
        if not value:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            pass
        try:
            s = str(value).replace("Z", "+00:00")
            return datetime.fromisoformat(s).timestamp()
        except Exception:
            return None
