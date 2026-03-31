from __future__ import annotations
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from ..config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

_POWER_LIMIT_MAX_KW: float = 100.0  # absolute hard cap for ESS/PV limits
_MASKED_KEYS: set[str] = {"ha_token", "ui_api_key"}
_CHART_RESAMPLE_MS = 300000


def _opt(request: Request):
    return request.app.state.optimizer


def _ha(request: Request):
    return request.app.state.ha


def _is_loopback_client(request: Request) -> bool:
    host = request.client.host if request.client else ""
    return host in {"127.0.0.1", "::1", "localhost"}


def _has_forwarded_client_headers(request: Request) -> bool:
    return any(
        request.headers.get(h)
        for h in ("forwarded", "x-forwarded-for", "x-real-ip")
    )


def _require_mutation_auth(request: Request) -> None:
    # Preserve zero-config local UX while requiring a key for remote clients.
    allow_loopback = (
        settings.allow_loopback_without_api_key
        and not settings.require_api_key_for_all_mutations
    )
    if (
        allow_loopback
        and _is_loopback_client(request)
        and not _has_forwarded_client_headers(request)
    ):
        return

    api_key = settings.ui_api_key.strip()
    if not api_key:
        raise HTTPException(status_code=403, detail="Remote control disabled (set UI_API_KEY to enable)")

    provided = request.headers.get("x-api-key", "").strip()
    if provided != api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")


def _require_config_read_auth(request: Request) -> None:
    if _is_loopback_client(request):
        return
    if settings.require_api_key_for_config_read:
        _require_mutation_auth(request)


def _allowed_manual_modes(cfg: Any) -> set[str]:
    return {
        str(getattr(cfg, "automated_option", "Automated")),
        str(getattr(cfg, "full_export_option", "Force Full Export")),
        str(getattr(cfg, "full_import_option", "Force Full Import")),
        str(getattr(cfg, "full_import_pv_option", "Force Full Import + PV")),
        str(getattr(cfg, "block_flow_option", "Prevent Import & Export")),
        str(getattr(cfg, "manual_option", "Manual")),
    }


def _state_power_caps_kw(opt: Any) -> tuple[float, float]:
    if hasattr(opt, "get_power_caps_kw"):
        try:
            return opt.get_power_caps_kw()
        except Exception:
            pass

    s = opt.last_state

    def _valid_cap(v: Any) -> bool:
        return isinstance(v, (int, float)) and 0 < float(v) < 999

    fallback = float(settings.ess_limit_fallback_kw)
    if not (0 < fallback <= _POWER_LIMIT_MAX_KW):
        fallback = min(max(fallback, 1.0), _POWER_LIMIT_MAX_KW)

    charge_cap = fallback
    discharge_cap = fallback
    if s:
        if _valid_cap(getattr(s, "ess_max_charge_kw", None)):
            charge_cap = float(s.ess_max_charge_kw)
        if _valid_cap(getattr(s, "ess_max_discharge_kw", None)):
            discharge_cap = float(s.ess_max_discharge_kw)
    return charge_cap, discharge_cap


def _coerce_config_value(cfg: Any, key: str, raw: Any) -> Any:
    current = getattr(cfg, key)
    current_type = type(current)

    if current_type is bool:
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, (int, float)):
            return raw != 0
        if isinstance(raw, str):
            v = raw.strip().lower()
            if v in {"true", "1", "yes", "on"}:
                return True
            if v in {"false", "0", "no", "off", ""}:
                return False
        raise ValueError(f"Invalid boolean value for {key}: {raw!r}")

    return current_type(raw)


def _config_key_to_env_var(key: str) -> str:
    return key.upper()


def _to_env_literal(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    return str(value)


def _persist_config_keys_to_env(cfg: Any, keys: list[str]) -> list[str]:
    env_path = Path(".env")
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []

    updates: dict[str, str] = {}
    for key in keys:
        if not hasattr(cfg, key):
            raise ValueError(f"Unknown config key: {key}")
        value = getattr(cfg, key)
        if key in _MASKED_KEYS and value == "****":
            raise ValueError(f"Refusing to persist masked value for {key}")
        updates[_config_key_to_env_var(key)] = _to_env_literal(value)

    if not updates:
        return []

    remaining = set(updates.keys())
    out: list[str] = []
    for line in lines:
        replaced = False
        for env_key, env_val in updates.items():
            if re.match(rf"^\s*{re.escape(env_key)}\s*=", line):
                out.append(f"{env_key}={env_val}")
                remaining.discard(env_key)
                replaced = True
                break
        if not replaced:
            out.append(line)

    for env_key in sorted(remaining):
        out.append(f"{env_key}={updates[env_key]}")

    env_path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
    return sorted(updates.keys())


def _serialize_forecast_curve(entries: Any, time_key: str, value_key: str) -> list[dict[str, Any]]:
    curve: list[dict[str, Any]] = []
    if not isinstance(entries, list):
        return curve

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        ts = entry.get(time_key)
        if not ts:
            continue
        try:
            value = float(entry.get(value_key, 0))
        except Exception:
            continue
        curve.append({"t": ts, "value": value})

    return curve


def _today_bounds_local() -> tuple[datetime, datetime]:
    now = datetime.now().astimezone()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def _parse_history_groups(groups: Any) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    if not isinstance(groups, list):
        return out
    for group in groups:
        if not isinstance(group, list) or not group:
            continue
        entity_id = None
        items: list[dict[str, Any]] = []
        for item in group:
            if not isinstance(item, dict):
                continue
            entity_id = entity_id or item.get("entity_id")
            items.append(item)
        if entity_id:
            out[entity_id] = items
    return out


def _history_ts_ms(item: dict[str, Any]) -> int | None:
    raw = item.get("last_changed") or item.get("last_updated")
    if not raw:
        return None
    try:
        return int(datetime.fromisoformat(str(raw).replace("Z", "+00:00")).timestamp() * 1000)
    except Exception:
        return None


def _history_float(item: dict[str, Any]) -> float | None:
    raw = item.get("state")
    try:
        return float(raw)
    except Exception:
        return None


def _history_kw(item: dict[str, Any], *, solar_now: bool = False) -> float | None:
    value = _history_float(item)
    if value is None:
        return None
    unit = str(item.get("attributes", {}).get("unit_of_measurement", "")).lower()
    if unit == "w":
        return value / 1000
    if unit == "kw":
        return value
    if solar_now:
        return value / 1000 if value > 100 else value
    return value / 1000 if value > 100 else value


def _build_series(points: list[dict[str, Any]], value_fn) -> list[dict[str, Any]]:
    series: list[dict[str, Any]] = []
    for item in points:
        ts = _history_ts_ms(item)
        value = value_fn(item)
        if ts is None or value is None:
            continue
        series.append({"t": ts, "value": value})
    return series


def _merge_points(*series_lists: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[int, dict[str, Any]] = {}
    for series in series_lists:
        for item in series:
            ts = item.get("t")
            if isinstance(ts, int):
                merged[ts] = item
    return [merged[ts] for ts in sorted(merged.keys())]


def _to_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def _resample_combined_rows(
    rows: list[dict[str, Any]],
    keys: list[str],
    start_ms: int,
    end_ms: int,
    step_ms: int = _CHART_RESAMPLE_MS,
) -> list[dict[str, Any]]:
    if not rows:
        return []

    sorted_rows = sorted(
        [row for row in rows if isinstance(row.get("t"), int)],
        key=lambda row: row["t"],
    )
    if not sorted_rows:
        return []

    idx = 0
    latest: dict[str, Any] = {key: None for key in keys}
    out: list[dict[str, Any]] = []

    for ts in range(start_ms, end_ms + 1, step_ms):
        while idx < len(sorted_rows) and sorted_rows[idx]["t"] <= ts:
            row = sorted_rows[idx]
            for key in keys:
                value = row.get(key)
                if value is not None:
                    latest[key] = value
            idx += 1
        out.append({"t": ts, **latest})

    return out


async def _history_backfill(request: Request) -> dict[str, Any]:
    opt = _opt(request)
    ha = _ha(request)
    cfg = opt.cfg
    start, end = _today_bounds_local()
    start_ms = _to_ms(start)
    end_ms = _to_ms(end)
    entity_ids = [
        cfg.battery_soc_sensor,
        cfg.min_soc_to_sunrise_helper,
        cfg.pv_power_sensor,
        cfg.solar_power_now_sensor,
        cfg.consumed_power_sensor,
        cfg.price_sensor,
        cfg.feedin_sensor,
    ]
    if cfg.grid_import_power_sensor:
        entity_ids.append(cfg.grid_import_power_sensor)
    if cfg.grid_export_power_sensor:
        entity_ids.append(cfg.grid_export_power_sensor)
    history = await ha.get_history_period(start_time=start, end_time=end, entity_ids=entity_ids)
    by_entity = _parse_history_groups(history)

    battery_series = _build_series(by_entity.get(cfg.battery_soc_sensor, []), _history_float)
    min_soc_series = _build_series(by_entity.get(cfg.min_soc_to_sunrise_helper, []), _history_float)
    pv_series = _build_series(by_entity.get(cfg.pv_power_sensor, []), _history_kw)
    pv_forecast_series = _build_series(by_entity.get(cfg.solar_power_now_sensor, []), lambda item: _history_kw(item, solar_now=True))
    grid_import_series = _build_series(by_entity.get(cfg.grid_import_power_sensor, []), _history_kw) if cfg.grid_import_power_sensor else []
    grid_export_series = _build_series(by_entity.get(cfg.grid_export_power_sensor, []), _history_kw) if cfg.grid_export_power_sensor else []
    load_series = _build_series(by_entity.get(cfg.consumed_power_sensor, []), _history_kw)
    import_price_series = _build_series(by_entity.get(cfg.price_sensor, []), _history_float)
    feedin_price_series = _build_series(by_entity.get(cfg.feedin_sensor, []), _history_float)

    power_timestamps = sorted({
        item["t"]
        for series in (battery_series, min_soc_series, pv_series, pv_forecast_series, grid_import_series, grid_export_series, load_series)
        for item in series
    })
    power_lookup = {
        "battery": {item["t"]: item["value"] for item in battery_series},
        "minSoc": {item["t"]: item["value"] for item in min_soc_series},
        "pv": {item["t"]: item["value"] for item in pv_series},
        "pvForecast": {item["t"]: item["value"] for item in pv_forecast_series},
        "imp": {item["t"]: item["value"] for item in grid_import_series},
        "exp": {item["t"]: item["value"] for item in grid_export_series},
        "load": {item["t"]: item["value"] for item in load_series},
    }
    power = [
        {
            "t": ts,
            "battery": power_lookup["battery"].get(ts),
            "minSoc": power_lookup["minSoc"].get(ts),
            "pv": power_lookup["pv"].get(ts),
            "pvForecast": power_lookup["pvForecast"].get(ts),
            "imp": power_lookup["imp"].get(ts),
            "exp": power_lookup["exp"].get(ts),
            "load": power_lookup["load"].get(ts),
        }
        for ts in power_timestamps
    ]

    price = [
        {
            "t": ts,
            "imp": imp.get("value"),
            "fit": fit.get("value"),
        }
        for ts, imp, fit in [
            (
                item["t"],
                item,
                next((x for x in feedin_price_series if x["t"] == item["t"]), {"value": None}),
            )
            for item in import_price_series
        ]
    ]
    feedin_only = [
        {"t": item["t"], "imp": None, "fit": item["value"]}
        for item in feedin_price_series
        if not any(existing["t"] == item["t"] for existing in price)
    ]
    price = _merge_points(price, feedin_only)

    memory_power = getattr(opt, "_chart_history_power", [])
    memory_price = getattr(opt, "_chart_history_price", [])
    merged_power = _merge_points(power, memory_power)
    merged_price = _merge_points(price, memory_price)
    return {
        "power": _resample_combined_rows(
            merged_power,
            ["battery", "minSoc", "pv", "pvForecast", "imp", "exp", "load"],
            start_ms,
            end_ms,
        ),
        "price": _resample_combined_rows(
            merged_price,
            ["imp", "fit"],
            start_ms,
            end_ms,
        ),
    }


@router.get("/status")
async def get_status(request: Request) -> dict[str, Any]:
    opt = _opt(request)
    ha = _ha(request)
    cfg = opt.cfg
    connected = await ha.ping()
    s = opt.last_state
    d = opt.last_decision
    return {
        "connected": connected,
        "ws_connected": opt.ws_connected,
        "config_time_warnings": getattr(opt, "config_time_warnings", []),
        "last_update": s.timestamp.isoformat() if s else None,
        "battery_soc": s.battery_soc if s else None,
        "pv_kw": s.pv_kw if s else None,
        "load_kw": s.load_kw if s else None,
        "grid_import_power_kw": s.grid_import_power_kw if s else None,
        "grid_export_power_kw": s.grid_export_power_kw if s else None,
        "feedin_price": s.feedin_price if s else None,
        "current_price": s.current_price if s else None,
        "feedin_price_cents": s.feedin_price_cents if s else None,
        "current_price_cents": s.current_price_cents if s else None,
        "solar_power_now_kw": s.solar_power_now_kw if s else None,
        "ems_mode": d.ems_mode if d else None,
        "export_limit": d.export_limit if d else None,
        "import_limit": d.import_limit if d else None,
        "effective_export_setpoint": (0.01 if d and d.export_limit <= 0 else (d.export_limit if d else None)),
        "effective_import_setpoint": (0.01 if d and d.import_limit <= 0 else (d.import_limit if d else None)),
        "pv_max_power_limit": d.pv_max_power_limit if d else None,
        "battery_eta": d.battery_eta_formatted if d else None,
        "battery_power_kw": d.battery_power_kw if d else None,
        "outcome_reason": d.outcome_reason if d else None,
        "is_evening_or_night": d.is_evening_or_night if d else None,
        "morning_dump_active": d.morning_dump_active if d else None,
        "standby_holdoff_active": d.standby_holdoff_active if d else None,
        "morning_slow_charge_active": d.morning_slow_charge_active if d else None,
        "evening_export_boost_active": d.evening_export_boost_active if d else None,
        "solar_surplus_bypass": d.solar_surplus_bypass if d else None,
        "pv_safeguard_active": d.pv_safeguard_active if d else None,
        "battery_full_safeguard": d.battery_full_safeguard if d else None,
        "export_spike_active": d.export_spike_active if d else None,
        "sunrise_soc_target": d.sunrise_soc_target if d else None,
        "min_soc_to_sunrise": d.min_soc_to_sunrise if d else None,
        "forecast_remaining": s.forecast_remaining_kwh if s else None,
        "forecast_today": s.forecast_today_kwh if s else None,
        "forecast_tomorrow": s.forecast_tomorrow_kwh if s else None,
        "price_forecast_curve": _serialize_forecast_curve(
            s.price_forecast_entries if s else [],
            cfg.price_forecast_time_key,
            cfg.price_forecast_value_key,
        ),
        "feedin_forecast_curve": _serialize_forecast_curve(
            s.feedin_forecast_entries if s else [],
            cfg.price_forecast_time_key,
            cfg.feedin_forecast_value_key,
        ),
        "demand_window": s.demand_window_active if s else None,
        "price_spike": s.price_spike_active if s else None,
        "ha_control_enabled": s.ha_control_enabled if s else None,
        "price_is_estimated": s.price_is_estimated if s else None,
        "daily_export_kwh": s.daily_export_kwh if s else None,
        "daily_import_kwh": s.daily_import_kwh if s else None,
        "daily_pv_kwh": s.daily_pv_kwh if s else None,
        "daily_load_kwh": s.daily_load_kwh if s else None,
        "daily_battery_charge_kwh": s.daily_battery_charge_kwh if s else None,
        "daily_battery_discharge_kwh": s.daily_battery_discharge_kwh if s else None,
        "sigenergy_mode": s.sigenergy_mode if s else None,
        "export_reason": d.export_reason if d else None,
        "import_reason": d.import_reason if d else None,
        "battery_capacity_kwh": s.battery_capacity_kwh if s else None,
        "ess_max_charge_kw": s.ess_max_charge_kw if s else None,
        "ess_max_discharge_kw": s.ess_max_discharge_kw if s else None,
        "sun_elevation": s.sun_elevation if s else None,
        "hours_to_sunrise": d.hours_to_sunrise if d else None,
        "hours_to_sunset": s.hours_to_sunset if s else None,
    }


@router.post("/run_cycle")
async def run_cycle(request: Request) -> dict[str, Any]:
    _require_mutation_auth(request)
    opt = _opt(request)
    d = await opt.run_once()
    return {
        "ok": True,
        "ems_mode": d.ems_mode,
        "export_limit": d.export_limit,
        "import_limit": d.import_limit,
        "outcome_reason": d.outcome_reason,
    }


class ModeRequest(BaseModel):
    mode: str


@router.post("/set_mode")
async def set_mode(request: Request, body: ModeRequest) -> dict[str, Any]:
    _require_mutation_auth(request)
    opt = _opt(request)
    cfg = opt.cfg
    if body.mode not in _allowed_manual_modes(cfg):
        raise HTTPException(status_code=400, detail=f"Unsupported mode: {body.mode}")
    try:
        await opt.apply_manual_mode(body.mode)
        return {"ok": True, "mode": body.mode}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


class ESSRequest(BaseModel):
    ems_mode: str
    grid_export_limit: float
    grid_import_limit: float
    pv_max_power_limit: float
    ha_control: Optional[bool] = None


@router.post("/set_ess")
async def set_ess(request: Request, body: ESSRequest) -> dict[str, Any]:
    _require_mutation_auth(request)
    opt = _opt(request)
    ha = _ha(request)
    cfg = opt.cfg
    charge_cap_kw, discharge_cap_kw = _state_power_caps_kw(opt)
    pv_cap_kw = max(charge_cap_kw, discharge_cap_kw)
    for name, number, cap in [
        ("grid_export_limit", body.grid_export_limit, discharge_cap_kw),
        ("grid_import_limit", body.grid_import_limit, charge_cap_kw),
        ("pv_max_power_limit", body.pv_max_power_limit, pv_cap_kw),
    ]:
        if not (0.0 <= number <= cap):
            raise HTTPException(
                status_code=400,
                detail=f"{name} value {number} kW is outside allowed range 0–{cap:.2f} kW",
            )
    try:
        await ha.select_option(cfg.ems_mode_select, body.ems_mode)
        await ha.set_number(cfg.grid_export_limit, body.grid_export_limit)
        await ha.set_number(cfg.grid_import_limit, body.grid_import_limit)
        await ha.set_number(cfg.pv_max_power_limit, body.pv_max_power_limit)
        if body.ha_control is not None:
            if body.ha_control:
                await ha.turn_on(cfg.ha_control_switch)
            else:
                await ha.turn_off(cfg.ha_control_switch)
        return {"ok": True}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/config")
async def get_config(request: Request) -> dict[str, Any]:
    cfg = _opt(request).cfg
    data = cfg.dict()
    for key in _MASKED_KEYS:
        if key in data:
            data[key] = "****"
    return data


class ConfigUpdateRequest(BaseModel):
    key: str
    value: Any
    persist: bool = False


class ConfigBatchUpdateRequest(BaseModel):
    updates: list[ConfigUpdateRequest]
    persist: bool = False


@router.post("/config")
async def update_config(request: Request, body: ConfigUpdateRequest) -> dict[str, Any]:
    _require_mutation_auth(request)
    cfg = _opt(request).cfg
    if not hasattr(cfg, body.key):
        raise HTTPException(status_code=400, detail=f"Unknown config key: {body.key}")
    try:
        coerced = _coerce_config_value(cfg, body.key, body.value)
        setattr(cfg, body.key, coerced)
        opt = _opt(request)
        if hasattr(opt, "refresh_config_time_warnings"):
            opt.refresh_config_time_warnings()
        persisted_keys: list[str] = []
        if body.persist:
            persisted_keys = _persist_config_keys_to_env(cfg, [body.key])
        safe_value = "****" if body.key in _MASKED_KEYS else getattr(cfg, body.key)
        return {
            "ok": True,
            "key": body.key,
            "value": safe_value,
            "persisted": body.persist,
            "persisted_keys": persisted_keys,
        }
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/config/batch")
async def update_config_batch(request: Request, body: ConfigBatchUpdateRequest) -> dict[str, Any]:
    _require_mutation_auth(request)
    cfg = _opt(request).cfg

    if not body.updates:
        return {"ok": True, "updated": {}}

    coerced_updates: dict[str, Any] = {}
    for item in body.updates:
        if not hasattr(cfg, item.key):
            raise HTTPException(status_code=400, detail=f"Unknown config key: {item.key}")
        try:
            coerced_updates[item.key] = _coerce_config_value(cfg, item.key, item.value)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    for key, value in coerced_updates.items():
        setattr(cfg, key, value)

    opt = _opt(request)
    if hasattr(opt, "refresh_config_time_warnings"):
        opt.refresh_config_time_warnings()

    persisted_keys: list[str] = []
    if body.persist:
        persisted_keys = _persist_config_keys_to_env(cfg, list(coerced_updates.keys()))

    safe_updated = {k: ("****" if k in _MASKED_KEYS else v) for k, v in coerced_updates.items()}
    return {
        "ok": True,
        "updated": safe_updated,
        "persisted": body.persist,
        "persisted_keys": persisted_keys,
    }


# ── In-process log ring buffer ────────────────────────────────────────────────
import logging as _logging
import collections as _collections
import csv as _csv
import io as _io
from fastapi.responses import StreamingResponse, PlainTextResponse

_LOG_BUFFER: _collections.deque = _collections.deque(maxlen=500)

class _UILogHandler(_logging.Handler):
    def emit(self, record):
        try:
            _LOG_BUFFER.appendleft(self.format(record))
        except Exception:
            pass

_handler = _UILogHandler()
_handler.setFormatter(_logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s", datefmt="%Y-%m-%dT%H:%M:%S"))
_handler._sigenergy_ui_log_handler = True
_root_logger = _logging.getLogger()
if not any(getattr(h, "_sigenergy_ui_log_handler", False) for h in _root_logger.handlers):
    _root_logger.addHandler(_handler)
if _root_logger.level == _logging.NOTSET or _root_logger.level > _logging.INFO:
    _root_logger.setLevel(_logging.INFO)


@router.get("/logs")
async def get_logs(request: Request, n: int = 200) -> PlainTextResponse:
    lines = list(_LOG_BUFFER)[:n]
    return PlainTextResponse("\n".join(lines))


@router.get("/history")
async def get_history(request: Request) -> dict[str, Any]:
    """Return chart history backfilled from Home Assistant recorder plus runtime memory."""
    try:
        return await _history_backfill(request)
    except Exception as exc:
        logger.warning("History backfill failed, falling back to in-memory history: %s", exc)
        opt = _opt(request)
        return {
            "power": getattr(opt, "_chart_history_power", []),
            "price": getattr(opt, "_chart_history_price", []),
        }


@router.get("/export_csv")
async def export_csv(request: Request) -> StreamingResponse:
    """Download current entities as CSV."""
    opt = _opt(request)
    cfg = opt.cfg
    s = opt.last_state
    d = opt.last_decision
    if not s:
        raise HTTPException(status_code=503, detail="No data yet")

    rows = [
        ["key", "entity", "value", "unit"],
        ["battery_soc", cfg.battery_soc_sensor, s.battery_soc, "%"],
        ["pv_power", cfg.pv_power_sensor, s.pv_kw, "kW"],
        ["load_power", cfg.consumed_power_sensor, s.load_kw, "kW"],
        ["price", cfg.price_sensor, s.current_price, "$/kWh"],
        ["feedin", cfg.feedin_sensor, s.feedin_price, "$/kWh"],
        ["mode", cfg.ems_mode_select, s.current_ems_mode, ""],
        ["grid_export_limit", cfg.grid_export_limit, s.current_export_limit, "kW"],
        ["grid_import_limit", cfg.grid_import_limit, s.current_import_limit, "kW"],
        ["pv_max_power_limit", cfg.pv_max_power_limit, s.current_pv_max_power_limit, "kW"],
        ["forecast_today", cfg.forecast_today_sensor, s.forecast_today_kwh, "kWh"],
        ["forecast_tomorrow", cfg.forecast_tomorrow_sensor, s.forecast_tomorrow_kwh, "kWh"],
        ["forecast_remaining", cfg.forecast_remaining_sensor, s.forecast_remaining_kwh, "kWh"],
        ["daily_export", cfg.daily_export_energy, s.daily_export_kwh, "kWh"],
        ["daily_import", cfg.daily_import_energy, s.daily_import_kwh, "kWh"],
        ["daily_pv", cfg.daily_pv_energy, s.daily_pv_kwh, "kWh"],
        ["daily_load", cfg.daily_load_energy, s.daily_load_kwh, "kWh"],
        ["sunrise_soc_target", "calculated", d.sunrise_soc_target if d else "", "%"],
        ["min_soc_to_sunrise", "calculated", d.min_soc_to_sunrise if d else "", "%"],
        ["outcome_reason", "calculated", d.outcome_reason if d else "", ""],
    ]

    buf = _io.StringIO()
    writer = _csv.writer(buf)
    writer.writerows(rows)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sigenergy_entities.csv"},
    )
