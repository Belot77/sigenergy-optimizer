from __future__ import annotations
import asyncio
import logging
import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Request, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

_POWER_LIMIT_MAX_KW: float = 100.0  # absolute hard cap for ESS/PV limits
_MASKED_KEYS: set[str] = {"ha_token", "ui_api_key"}
_CHART_RESAMPLE_MS = 300000
_THRESHOLD_PRESET_KEYS: tuple[str, ...] = (
    "export_threshold_low",
    "export_threshold_medium",
    "export_threshold_high",
    "export_limit_low",
    "export_limit_medium",
    "export_limit_high",
    "import_threshold_low",
    "import_threshold_medium",
    "import_threshold_high",
    "import_limit_low",
    "import_limit_medium",
    "import_limit_high",
)
_TIME_KEYS: set[str] = {
    "daily_summary_time",
    "morning_summary_time",
    "standby_holdoff_end_time",
    "morning_slow_charge_until",
}


def _opt(request: Request):
    return request.app.state.optimizer


def _ha(request: Request):
    return request.app.state.ha


def _actor_from_request(request: Request) -> str:
    if _is_ha_ingress_request(request):
        return "ha_ingress_ui"
    if _is_loopback_client(request) and not _has_forwarded_client_headers(request):
        return "local_loopback"
    forwarded = request.headers.get("x-forwarded-for") or request.headers.get("x-real-ip")
    if forwarded:
        return f"remote:{str(forwarded).split(',')[0].strip()}"
    host = request.client.host if request.client else "unknown"
    return f"remote:{host}"


def _source_from_request(request: Request) -> str:
    if _is_ha_ingress_request(request):
        return "ui_manual"
    if _is_loopback_client(request) and not _has_forwarded_client_headers(request):
        return "local_api"
    return "api_client"


def _record_audit(
    request: Request,
    *,
    action: str,
    result: str,
    target_key: str | None = None,
    old_value: Any = None,
    new_value: Any = None,
    details: Any = None,
) -> None:
    try:
        _opt(request).record_audit_event(
            action=action,
            source=_source_from_request(request),
            actor=_actor_from_request(request),
            result=result,
            target_key=target_key,
            old_value=old_value,
            new_value=new_value,
            details=details,
        )
    except Exception:
        logger.exception("Failed to record audit event for action %s", action)


def _validation_exception(field_errors: list[dict[str, str]]) -> HTTPException:
    return HTTPException(
        status_code=422,
        detail={
            "message": "Validation failed",
            "field_errors": field_errors,
        },
    )


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


def _validate_config_value(cfg: Any, key: str, value: Any) -> str | None:
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return "must be a finite number"
    if key in _TIME_KEYS and not _is_valid_time(str(value)):
        return "must be HH:MM or HH:MM:SS"
    if key.endswith("_limit") or key.endswith("_limit_low") or key.endswith("_limit_medium") or key.endswith("_limit_high"):
        if isinstance(value, (int, float)) and not (0 <= float(value) <= _POWER_LIMIT_MAX_KW):
            return f"must be between 0 and {_POWER_LIMIT_MAX_KW}"
    if key.endswith("_threshold") or "threshold" in key:
        if isinstance(value, (int, float)) and not (-10 <= float(value) <= 10):
            return "threshold appears out of expected range"
    return None


def _sanitize_preset_payload(payload: dict[str, Any]) -> dict[str, float]:
    clean: dict[str, float] = {}
    for key in _THRESHOLD_PRESET_KEYS:
        if key not in payload:
            continue
        value = payload.get(key)
        if value is None:
            continue
        num = float(value)
        if math.isnan(num) or math.isinf(num):
            raise ValueError(f"Invalid numeric value for {key}")
        clean[key] = num
    if not clean:
        raise ValueError("Preset payload must include at least one threshold field")
    return clean


def _is_loopback_client(request: Request) -> bool:
    host = request.client.host if request.client else ""
    return host in {"127.0.0.1", "::1", "localhost"}


def _has_forwarded_client_headers(request: Request) -> bool:
    return any(
        request.headers.get(h)
        for h in ("forwarded", "x-forwarded-for", "x-real-ip")
    )


def _is_ha_ingress_request(request: Request) -> bool:
    # Home Assistant ingress proxied requests include ingress-specific headers.
    # Treat these as trusted local UI traffic unless strict API-key mode is enabled.
    return bool(
        request.headers.get("x-ingress-path")
        or request.headers.get("x-hassio")
        or request.headers.get("x-home-assistant")
    )


def _require_mutation_auth(request: Request) -> None:
    # Preserve zero-config local UX while requiring a key for remote clients.
    allow_loopback = (
        settings.allow_loopback_without_api_key
        and not settings.require_api_key_for_all_mutations
    )
    if (
        allow_loopback
        and (
            (_is_loopback_client(request) and not _has_forwarded_client_headers(request))
            or _is_ha_ingress_request(request)
        )
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


def _effective_mode_label(opt: Any, s: Any, cfg: Any) -> str:
    override = str(getattr(opt, "_manual_mode_override", "") or "")
    if override:
        return override
    if s:
        return str(getattr(s, "sigenergy_mode", "") or "")
    return str(getattr(cfg, "automated_option", "Automated"))


def _manual_display_targets(opt: Any, s: Any, mode: str, cfg: Any) -> dict[str, Any] | None:
    if mode in {str(getattr(cfg, "automated_option", "Automated")), str(getattr(cfg, "manual_option", "Manual")), ""}:
        return None
    target_builder = getattr(opt, "_manual_mode_targets", None)
    if callable(target_builder):
        try:
            return target_builder(
                mode,
                s,
                include_block_flow_ess_limits=(mode == str(getattr(cfg, "block_flow_option", "Prevent Import & Export"))),
            )
        except Exception:
            return None
    return None


def _live_battery_power_kw(s: Any, d: Any, manual_targets: dict[str, Any] | None = None) -> float | None:
    if not s:
        return d.battery_power_kw if d else None

    direct = getattr(s, "battery_power_sensor_kw", None)
    grid_import = getattr(s, "grid_import_power_kw", None)
    grid_export = getattr(s, "grid_export_power_kw", None)

    pv_kw = float(getattr(s, "pv_kw", 0.0) or 0.0)
    load_kw = float(getattr(s, "load_kw", 0.0) or 0.0)
    current_import_limit = float(getattr(s, "current_import_limit", 0.0) or 0.0)
    current_export_limit = float(getattr(s, "current_export_limit", 0.0) or 0.0)
    if manual_targets:
        current_import_limit = float(manual_targets.get("grid_import_limit", current_import_limit) or 0.0)
        current_export_limit = float(manual_targets.get("grid_export_limit", current_export_limit) or 0.0)

    if grid_import is not None and grid_export is not None:
        measured_balance = max(float(getattr(s, "pv_kw", 0.0) or 0.0), 0.0)
        measured_balance += max(float(grid_import or 0.0), 0.0)
        measured_balance -= max(float(grid_export or 0.0), 0.0)
        measured_balance -= max(load_kw, 0.0)

        if direct is not None:
            direct_val = float(direct)
            if abs(measured_balance - direct_val) > 1.5:
                return measured_balance
            return direct_val
        return measured_balance

    # When grid power telemetry is unavailable, approximate battery flow from
    # local power balance only in near-blocked grid mode to avoid large drift.
    if current_import_limit <= 0.11 and current_export_limit <= 0.11:
        fallback_balance = pv_kw - load_kw
        if direct is not None:
            direct_val = float(direct)
            if abs(fallback_balance - direct_val) > 1.5:
                return fallback_balance
            return direct_val
        return fallback_balance

    if direct is not None:
        return float(direct)

    return d.battery_power_kw if d else None


def _live_outcome_reason(mode: str, d: Any, cfg: Any) -> str | None:
    if mode and mode not in {str(getattr(cfg, "automated_option", "Automated")), ""}:
        return f"Manual mode active ({mode}); optimizer writes paused"
    return d.outcome_reason if d else None


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
    data_age_seconds: float | None = None
    stale_data = True
    if s:
        data_age_seconds = (datetime.now(timezone.utc) - s.timestamp.astimezone(timezone.utc)).total_seconds()
        stale_data = data_age_seconds > max(45, int(settings.poll_interval_seconds) * 2)
    effective_mode = _effective_mode_label(opt, s, cfg)
    manual_active = effective_mode not in {str(getattr(cfg, "automated_option", "Automated")), ""}
    manual_targets = _manual_display_targets(opt, s, effective_mode, cfg) if manual_active else None
    battery_power_kw = _live_battery_power_kw(s, d, manual_targets)
    outcome_reason = _live_outcome_reason(effective_mode, d, cfg)
    def _manual_float(key: str, fallback: Any) -> Any:
        if not manual_targets:
            return fallback
        raw = manual_targets.get(key)
        if raw is None:
            return fallback
        try:
            return float(raw)
        except (TypeError, ValueError):
            return fallback

    display_ems_mode = manual_targets.get("ems_mode") if manual_targets else (s.current_ems_mode if s else (d.ems_mode if d else None))
    display_export_limit = _manual_float("grid_export_limit", s.current_export_limit if s else (d.export_limit if d else None))
    display_import_limit = _manual_float("grid_import_limit", s.current_import_limit if s else (d.import_limit if d else None))
    display_pv_max = _manual_float("pv_max_power_limit", s.current_pv_max_power_limit if s else (d.pv_max_power_limit if d else None))
    display_ess_charge = _manual_float("ess_charge_limit", s.current_ess_charge_limit if s else (d.ess_charge_limit if d else None))
    display_ess_discharge = _manual_float("ess_discharge_limit", s.current_ess_discharge_limit if s else (d.ess_discharge_limit if d else None))
    return {
        "runtime_signature": getattr(opt, "runtime_signature", "unknown"),
        "morning_slow_charge_runtime_disabled": bool(
            getattr(opt, "_morning_slow_charge_runtime_disabled", False)
        ),
        "connected": connected,
        "ws_connected": opt.ws_connected,
        "stale_data": stale_data,
        "data_age_seconds": data_age_seconds,
        "config_time_warnings": getattr(opt, "config_time_warnings", []),
        "last_update": s.timestamp.isoformat() if s else None,
        "battery_soc": s.battery_soc if s else None,
        "available_discharge_energy_kwh": s.available_discharge_energy_kwh if s else None,
        "pv_kw": s.pv_kw if s else None,
        "load_kw": s.load_kw if s else None,
        "grid_import_power_kw": s.grid_import_power_kw if s else None,
        "grid_export_power_kw": s.grid_export_power_kw if s else None,
        "battery_power_sensor_kw": s.battery_power_sensor_kw if s else None,
        "feedin_price": s.feedin_price if s else None,
        "current_price": s.current_price if s else None,
        "feedin_price_cents": s.feedin_price_cents if s else None,
        "current_price_cents": s.current_price_cents if s else None,
        "solar_power_now_kw": s.solar_power_now_kw if s else None,
        "ems_mode": display_ems_mode,
        "export_limit": display_export_limit,
        "import_limit": display_import_limit,
        "effective_export_setpoint": (
            0.01 if display_export_limit is not None and float(display_export_limit) <= 0 else display_export_limit
        ),
        "effective_import_setpoint": (
            0.01 if display_import_limit is not None and float(display_import_limit) <= 0 else display_import_limit
        ),
        "pv_max_power_limit": display_pv_max,
        "ess_charge_limit": display_ess_charge,
        "ess_discharge_limit": display_ess_discharge,
        "battery_eta": d.battery_eta_formatted if d else None,
        "battery_power_kw": battery_power_kw,
        "outcome_reason": outcome_reason,
        "is_evening_or_night": (d.is_evening_or_night if d else None) if not manual_active else False,
        "morning_dump_active": (d.morning_dump_active if d else None) if not manual_active else False,
        "standby_holdoff_active": (d.standby_holdoff_active if d else None) if not manual_active else False,
        "morning_slow_charge_active": (d.morning_slow_charge_active if d else None) if not manual_active else False,
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
        "solar_forecast_curve": _serialize_forecast_curve(
            s.solcast_detailed if s else [],
            "period_start",
            "pv_estimate",
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
        "sigenergy_mode": effective_mode,
        "next_sunrise_ts": datetime.fromtimestamp(s.next_sunrise_ts, tz=timezone.utc).isoformat() if s and s.next_sunrise_ts else None,
        "next_sunset_ts": datetime.fromtimestamp(s.next_sunset_ts, tz=timezone.utc).isoformat() if s and s.next_sunset_ts else None,
        "export_reason": d.export_reason if d else None,
        "import_reason": d.import_reason if d else None,
        "battery_capacity_kwh": s.battery_capacity_kwh if s else None,
        "ess_max_charge_kw": s.ess_max_charge_kw if s else None,
        "ess_max_discharge_kw": s.ess_max_discharge_kw if s else None,
        "sun_elevation": s.sun_elevation if s else None,
        "hours_to_sunrise": d.hours_to_sunrise if d else None,
        "hours_to_sunset": s.hours_to_sunset if s else None,
        "last_cycle_started": opt.last_cycle_started.isoformat() if getattr(opt, "last_cycle_started", None) else None,
        "last_cycle_completed": opt.last_cycle_completed.isoformat() if getattr(opt, "last_cycle_completed", None) else None,
        "last_cycle_error": getattr(opt, "last_cycle_error", ""),
    }


@router.get("/health")
async def health(request: Request) -> JSONResponse:
    opt = _opt(request)
    completed = getattr(opt, "last_cycle_completed", None)
    err = getattr(opt, "last_cycle_error", "")
    stale = True
    if completed:
        age = (datetime.now(timezone.utc) - completed).total_seconds()
        stale = age > max(60, int(settings.poll_interval_seconds) * 4)
    status = "healthy"
    if err or stale:
        status = "degraded"
    payload = {
        "status": status,
        "ws_connected": opt.ws_connected,
        "stale": stale,
        "last_cycle_completed": completed.isoformat() if completed else None,
        "last_error": err,
    }
    return JSONResponse(payload, status_code=200 if status == "healthy" else 503)


@router.get("/price_tracking")
async def price_tracking(request: Request, date: Optional[str] = None, limit: int = 2000) -> dict[str, Any]:
    _require_config_read_auth(request)
    limit = max(1, min(limit, 20000))
    rows = _opt(request).price_tracking_events(date=date, limit=limit)
    return {"rows": rows}


@router.get("/daily_earnings")
async def daily_earnings(request: Request, date: Optional[str] = None) -> dict[str, Any]:
    _require_config_read_auth(request)
    return await _opt(request).daily_earnings_summary(date=date)


@router.get("/earnings_history")
async def earnings_history(request: Request, days: int = 7) -> dict[str, Any]:
    _require_config_read_auth(request)
    return await _opt(request).earnings_history(days=days)


@router.post("/run_cycle")
async def run_cycle(request: Request) -> dict[str, Any]:
    _require_mutation_auth(request)
    opt = _opt(request)
    d = await opt.run_once()
    _record_audit(
        request,
        action="run_cycle",
        result="ok",
        new_value={
            "ems_mode": d.ems_mode,
            "export_limit": d.export_limit,
            "import_limit": d.import_limit,
        },
    )
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
    old_mode = opt.last_state.sigenergy_mode if opt.last_state else None
    try:
        await opt.apply_manual_mode(body.mode)
        _record_audit(
            request,
            action="set_mode",
            result="ok",
            target_key="sigenergy_mode",
            old_value=old_mode,
            new_value=body.mode,
        )
        return {"ok": True, "mode": body.mode}
    except Exception as exc:
        _record_audit(
            request,
            action="set_mode",
            result="error",
            target_key="sigenergy_mode",
            old_value=old_mode,
            new_value=body.mode,
            details={"error": str(exc)},
        )
        raise HTTPException(status_code=500, detail=str(exc))


class ESSRequest(BaseModel):
    ems_mode: str
    grid_export_limit: float
    grid_import_limit: float
    pv_max_power_limit: float
    ha_control: Optional[bool] = None
    ess_charge_limit: Optional[float] = None
    ess_discharge_limit: Optional[float] = None


@router.post("/set_ess")
async def set_ess(request: Request, body: ESSRequest) -> dict[str, Any]:
    _require_mutation_auth(request)
    opt = _opt(request)
    ha = _ha(request)
    cfg = opt.cfg
    charge_cap_kw, discharge_cap_kw = _state_power_caps_kw(opt)
    pv_cap_kw = max(charge_cap_kw, discharge_cap_kw)
    field_errors: list[dict[str, str]] = []
    for name, number, cap in [
        ("grid_export_limit", body.grid_export_limit, discharge_cap_kw),
        ("grid_import_limit", body.grid_import_limit, charge_cap_kw),
        ("pv_max_power_limit", body.pv_max_power_limit, pv_cap_kw),
    ]:
        if not (0.0 <= number <= cap):
            field_errors.append(
                {
                    "key": name,
                    "error": f"value {number} kW is outside allowed range 0-{cap:.2f} kW",
                }
            )
    for name, number, cap in [
        ("ess_charge_limit", body.ess_charge_limit, charge_cap_kw),
        ("ess_discharge_limit", body.ess_discharge_limit, discharge_cap_kw),
    ]:
        if number is not None and not (0.0 <= number <= cap):
            field_errors.append(
                {
                    "key": name,
                    "error": f"value {number} kW is outside allowed range 0-{cap:.2f} kW",
                }
            )
    if field_errors:
        _record_audit(
            request,
            action="set_ess",
            result="validation_error",
            details={"field_errors": field_errors},
        )
        raise _validation_exception(field_errors)

    old_values = {
        "ems_mode": opt.last_decision.ems_mode if opt.last_decision else None,
        "grid_export_limit": opt.last_decision.export_limit if opt.last_decision else None,
        "grid_import_limit": opt.last_decision.import_limit if opt.last_decision else None,
        "pv_max_power_limit": opt.last_decision.pv_max_power_limit if opt.last_decision else None,
    }
    try:
        await ha.select_option(cfg.ems_mode_select, body.ems_mode)
        await ha.set_number(cfg.grid_export_limit, body.grid_export_limit)
        await ha.set_number(cfg.grid_import_limit, body.grid_import_limit)
        await ha.set_number(cfg.pv_max_power_limit, body.pv_max_power_limit)
        if body.ess_charge_limit is not None:
            await ha.set_number(cfg.ess_max_charging_limit, body.ess_charge_limit)
        if body.ess_discharge_limit is not None:
            await ha.set_number(cfg.ess_max_discharging_limit, body.ess_discharge_limit)
        if body.ha_control is not None:
            if body.ha_control:
                await ha.turn_on(cfg.ha_control_switch)
            else:
                await ha.turn_off(cfg.ha_control_switch)
        mode_from_entity = str(await ha.get_state_value(cfg.sigenergy_mode_select, "") or "")
        current_mode = mode_from_entity or _effective_mode_label(opt, opt.last_state, cfg)
        if current_mode == str(getattr(cfg, "block_flow_option", "Prevent Import & Export")):
            set_overrides = getattr(opt, "set_manual_ess_overrides", None)
            if callable(set_overrides):
                set_overrides(
                    charge_kw=body.ess_charge_limit,
                    discharge_kw=body.ess_discharge_limit,
                )
        _record_audit(
            request,
            action="set_ess",
            result="ok",
            old_value=old_values,
            new_value=body.model_dump(),
        )
        return {"ok": True}
    except Exception as exc:
        _record_audit(
            request,
            action="set_ess",
            result="error",
            old_value=old_values,
            new_value=body.model_dump(),
            details={"error": str(exc)},
        )
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


@router.get("/entities/search")
async def search_entities(request: Request, q: str = "", limit: int = 200, domains: str = "") -> dict[str, Any]:
    _require_config_read_auth(request)
    domain_list = [d.strip().lower() for d in domains.split(",") if d.strip()] if domains else []
    rows = await _ha(request).search_entities(query=q, limit=limit, domains=domain_list)
    return {"rows": rows}


@router.websocket("/ws")
async def ws_status(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            opt = websocket.app.state.optimizer
            s = opt.last_state
            d = opt.last_decision
            effective_mode = _effective_mode_label(opt, s, opt.cfg)
            manual_active = effective_mode not in {str(getattr(opt.cfg, "automated_option", "Automated")), ""}
            manual_targets = _manual_display_targets(opt, s, effective_mode, opt.cfg) if manual_active else None
            battery_power_kw = _live_battery_power_kw(s, d, manual_targets)
            outcome_reason = _live_outcome_reason(effective_mode, d, opt.cfg)

            def _manual_float(key: str, fallback: Any) -> Any:
                if not manual_targets:
                    return fallback
                raw = manual_targets.get(key)
                if raw is None:
                    return fallback
                try:
                    return float(raw)
                except (TypeError, ValueError):
                    return fallback

            display_ems_mode = manual_targets.get("ems_mode") if manual_targets else (s.current_ems_mode if s else (d.ems_mode if d else None))
            display_export_limit = _manual_float("grid_export_limit", s.current_export_limit if s else (d.export_limit if d else None))
            display_import_limit = _manual_float("grid_import_limit", s.current_import_limit if s else (d.import_limit if d else None))
            display_pv_max = _manual_float("pv_max_power_limit", s.current_pv_max_power_limit if s else (d.pv_max_power_limit if d else None))
            display_ess_charge = _manual_float("ess_charge_limit", s.current_ess_charge_limit if s else (d.ess_charge_limit if d else None))
            display_ess_discharge = _manual_float("ess_discharge_limit", s.current_ess_discharge_limit if s else (d.ess_discharge_limit if d else None))
            await websocket.send_json(
                {
                    "ws_connected": opt.ws_connected,
                    "last_update": s.timestamp.isoformat() if s else None,
                    "battery_soc": s.battery_soc if s else None,
                    "available_discharge_energy_kwh": s.available_discharge_energy_kwh if s else None,
                    "pv_kw": s.pv_kw if s else None,
                    "load_kw": s.load_kw if s else None,
                    "grid_import_power_kw": s.grid_import_power_kw if s else None,
                    "grid_export_power_kw": s.grid_export_power_kw if s else None,
                    "battery_power_sensor_kw": s.battery_power_sensor_kw if s else None,
                    "solar_power_now_kw": s.solar_power_now_kw if s else None,
                    "forecast_remaining": s.forecast_remaining_kwh if s else None,
                    "current_price": s.current_price if s else None,
                    "feedin_price": s.feedin_price if s else None,
                    "forecast_today": s.forecast_today_kwh if s else None,
                    "daily_export_kwh": s.daily_export_kwh if s else None,
                    "daily_import_kwh": s.daily_import_kwh if s else None,
                    "daily_pv_kwh": s.daily_pv_kwh if s else None,
                    "daily_load_kwh": s.daily_load_kwh if s else None,
                    "daily_battery_charge_kwh": s.daily_battery_charge_kwh if s else None,
                    "daily_battery_discharge_kwh": s.daily_battery_discharge_kwh if s else None,
                    "next_sunrise_ts": datetime.fromtimestamp(s.next_sunrise_ts, tz=timezone.utc).isoformat() if s and s.next_sunrise_ts else None,
                    "next_sunset_ts": datetime.fromtimestamp(s.next_sunset_ts, tz=timezone.utc).isoformat() if s and s.next_sunset_ts else None,
                    "sigenergy_mode": effective_mode,
                    "ha_control_enabled": s.ha_control_enabled if s else None,
                    "ems_mode": display_ems_mode,
                    "export_limit": display_export_limit,
                    "import_limit": display_import_limit,
                    "pv_max_power_limit": display_pv_max,
                    "ess_charge_limit": display_ess_charge,
                    "ess_discharge_limit": display_ess_discharge,
                    "ess_max_charge_kw": s.ess_max_charge_kw if s else None,
                    "ess_max_discharge_kw": s.ess_max_discharge_kw if s else None,
                    "battery_power_kw": battery_power_kw,
                    "sunrise_soc_target": (d.sunrise_soc_target if d else None) if not manual_active else None,
                    "morning_slow_charge_active": (d.morning_slow_charge_active if d else None) if not manual_active else False,
                    "outcome_reason": outcome_reason,
                    "last_cycle_started": opt.last_cycle_started.isoformat() if getattr(opt, "last_cycle_started", None) else None,
                    "last_cycle_completed": opt.last_cycle_completed.isoformat() if getattr(opt, "last_cycle_completed", None) else None,
                    "last_cycle_error": getattr(opt, "last_cycle_error", ""),
                }
            )
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        return


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
    old_value = getattr(cfg, body.key)
    try:
        coerced = _coerce_config_value(cfg, body.key, body.value)
        err = _validate_config_value(cfg, body.key, coerced)
        if err:
            _record_audit(
                request,
                action="config_update",
                result="validation_error",
                target_key=body.key,
                old_value=old_value,
                new_value=body.value,
                details={"field_errors": [{"key": body.key, "error": err}]},
            )
            raise _validation_exception([{"key": body.key, "error": err}])
        setattr(cfg, body.key, coerced)
        opt = _opt(request)
        if hasattr(opt, "refresh_config_time_warnings"):
            opt.refresh_config_time_warnings()
        persisted_keys: list[str] = []
        if body.persist:
            persisted_keys = _persist_config_keys_to_env(cfg, [body.key])
        safe_value = "****" if body.key in _MASKED_KEYS else getattr(cfg, body.key)
        _record_audit(
            request,
            action="config_update",
            result="ok",
            target_key=body.key,
            old_value="****" if body.key in _MASKED_KEYS else old_value,
            new_value=safe_value,
            details={"persisted": body.persist, "persisted_keys": persisted_keys},
        )
        return {
            "ok": True,
            "key": body.key,
            "value": safe_value,
            "persisted": body.persist,
            "persisted_keys": persisted_keys,
        }

    except (ValueError, TypeError) as exc:
        _record_audit(
            request,
            action="config_update",
            result="validation_error",
            target_key=body.key,
            old_value="****" if body.key in _MASKED_KEYS else old_value,
            new_value="****" if body.key in _MASKED_KEYS else body.value,
            details={"error": str(exc)},
        )
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        _record_audit(
            request,
            action="config_update",
            result="error",
            target_key=body.key,
            old_value="****" if body.key in _MASKED_KEYS else old_value,
            new_value="****" if body.key in _MASKED_KEYS else body.value,
            details={"error": str(exc)},
        )
        raise HTTPException(status_code=500, detail=str(exc))


class ThresholdPresetRequest(BaseModel):
    name: str
    payload: dict[str, Any]


@router.get("/audit")
async def audit_events(request: Request, limit: int = 200) -> dict[str, Any]:
    _require_config_read_auth(request)
    rows = _opt(request).audit_events(limit=limit)
    return {"rows": rows}


@router.get("/presets")
async def list_presets(request: Request) -> dict[str, Any]:
    _require_config_read_auth(request)
    return {"presets": _opt(request).list_threshold_presets()}


@router.post("/presets")
async def save_preset(request: Request, body: ThresholdPresetRequest) -> dict[str, Any]:
    _require_mutation_auth(request)
    try:
        payload = _sanitize_preset_payload(body.payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    _opt(request).save_threshold_preset(body.name, payload)
    _record_audit(
        request,
        action="save_preset",
        result="ok",
        target_key=body.name,
        new_value=payload,
    )
    return {"ok": True, "name": body.name.strip(), "payload": payload}


@router.get("/presets/{name}")
async def get_preset(request: Request, name: str) -> dict[str, Any]:
    _require_config_read_auth(request)
    preset = _opt(request).get_threshold_preset(name)
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")
    return {"preset": preset}


@router.delete("/presets/{name}")
async def delete_preset(request: Request, name: str) -> dict[str, Any]:
    _require_mutation_auth(request)
    deleted = _opt(request).delete_threshold_preset(name)
    _record_audit(
        request,
        action="delete_preset",
        result="ok" if deleted else "not_found",
        target_key=name,
    )
    return {"ok": True, "deleted": deleted}


@router.post("/config/batch")
async def update_config_batch(request: Request, body: ConfigBatchUpdateRequest) -> dict[str, Any]:
    _require_mutation_auth(request)
    cfg = _opt(request).cfg

    if not body.updates:
        return {"ok": True, "updated": {}}

    coerced_updates: dict[str, Any] = {}
    field_errors: list[dict[str, str]] = []
    for item in body.updates:
        if not hasattr(cfg, item.key):
            field_errors.append({"key": item.key, "error": "Unknown config key"})
            continue
        try:
            coerced = _coerce_config_value(cfg, item.key, item.value)
            err = _validate_config_value(cfg, item.key, coerced)
            if err:
                field_errors.append({"key": item.key, "error": err})
            else:
                coerced_updates[item.key] = coerced
        except Exception as exc:
            field_errors.append({"key": item.key, "error": str(exc)})

    if field_errors:
        _record_audit(
            request,
            action="config_batch_update",
            result="validation_error",
            details={"field_errors": field_errors},
        )
        raise _validation_exception(field_errors)

    old_values = {
        k: ("****" if k in _MASKED_KEYS else getattr(cfg, k))
        for k in coerced_updates.keys()
    }

    for key, value in coerced_updates.items():
        setattr(cfg, key, value)

    opt = _opt(request)
    if hasattr(opt, "refresh_config_time_warnings"):
        opt.refresh_config_time_warnings()

    persisted_keys: list[str] = []
    if body.persist:
        persisted_keys = _persist_config_keys_to_env(cfg, list(coerced_updates.keys()))

    safe_updated = {k: ("****" if k in _MASKED_KEYS else v) for k, v in coerced_updates.items()}
    _record_audit(
        request,
        action="config_batch_update",
        result="ok",
        old_value=old_values,
        new_value=safe_updated,
        details={"persisted": body.persist, "persisted_keys": persisted_keys},
    )
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


@router.get("/logs/download")
async def download_logs(request: Request, n: int = 500) -> PlainTextResponse:
    lines = list(_LOG_BUFFER)[: max(1, min(int(n), 5000))]
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return PlainTextResponse(
        "\n".join(lines),
        headers={"Content-Disposition": f"attachment; filename=sigenergy_logs_{ts}.log"},
    )


@router.get("/decision_trace")
async def get_decision_trace(request: Request, limit: int = 200) -> dict[str, Any]:
    _require_config_read_auth(request)
    rows = _opt(request).decision_trace(limit=max(1, min(int(limit), 2000)))
    return {"rows": rows}


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
