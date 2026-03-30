from __future__ import annotations
import logging
import re
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from ..config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

_POWER_LIMIT_MAX_KW: float = 100.0  # absolute hard cap for ESS/PV limits
_MASKED_KEYS: set[str] = {"ha_token", "ui_api_key"}


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


@router.get("/status")
async def get_status(request: Request) -> dict[str, Any]:
    opt = _opt(request)
    ha = _ha(request)
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
    _require_config_read_auth(request)
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
if not any(getattr(h, "_sigenergy_ui_log_handler", False) for h in _logging.getLogger().handlers):
    _logging.getLogger().addHandler(_handler)


@router.get("/logs")
async def get_logs(request: Request, n: int = 200) -> PlainTextResponse:
    lines = list(_LOG_BUFFER)[:n]
    return PlainTextResponse("\n".join(lines))


@router.get("/history")
async def get_history(request: Request) -> dict[str, Any]:
    """Return rolling in-memory history for chart backfill."""
    opt = _opt(request)
    return {
        "power": getattr(opt, "_chart_history_power", []),
        "price": getattr(opt, "_chart_history_price", []),
    }


@router.get("/export_csv")
async def export_csv(request: Request) -> StreamingResponse:
    """Download current entities as CSV."""
    opt = _opt(request)
    s = opt.last_state
    d = opt.last_decision
    if not s:
        raise HTTPException(status_code=503, detail="No data yet")

    rows = [
        ["key", "entity", "value", "unit"],
        ["battery_soc", "sensor.sigen_plant_battery_state_of_charge", s.battery_soc, "%"],
        ["pv_power", "sensor.sigen_plant_pv_power", s.pv_kw, "kW"],
        ["load_power", "sensor.sigen_plant_consumed_power", s.load_kw, "kW"],
        ["price", "sensor.amber_general_price", s.current_price, "$/kWh"],
        ["feedin", "sensor.amber_feed_in_price", s.feedin_price, "$/kWh"],
        ["mode", "select.sigen_plant_remote_ems_control_mode", s.current_ems_mode, ""],
        ["grid_export_limit", "number.sigen_plant_grid_export_limitation", s.current_export_limit, "kW"],
        ["grid_import_limit", "number.sigen_plant_grid_import_limitation", s.current_import_limit, "kW"],
        ["pv_max_power_limit", "number.sigen_plant_pv_max_power_limit", s.current_pv_max_power_limit, "kW"],
        ["forecast_today", "sensor.solcast_pv_forecast_forecast_today", s.forecast_today_kwh, "kWh"],
        ["forecast_tomorrow", "sensor.solcast_pv_forecast_forecast_tomorrow", s.forecast_tomorrow_kwh, "kWh"],
        ["forecast_remaining", "sensor.solcast_pv_forecast_forecast_remaining_today", s.forecast_remaining_kwh, "kWh"],
        ["daily_export", "sensor.sigen_plant_daily_grid_export_energy", s.daily_export_kwh, "kWh"],
        ["daily_import", "sensor.sigen_plant_daily_grid_import_energy", s.daily_import_kwh, "kWh"],
        ["daily_pv", "sensor.sigen_plant_daily_pv_generation", s.daily_pv_kwh, "kWh"],
        ["daily_load", "sensor.sigen_plant_daily_load_consumption", s.daily_load_kwh, "kWh"],
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
