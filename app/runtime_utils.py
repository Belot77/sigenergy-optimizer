"""Runtime utility helpers extracted from optimizer.py."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


def valid_hw_cap_kw(v: Any) -> bool:
    return isinstance(v, (int, float)) and 0 < float(v) < 999


def get_power_caps_kw(optimizer, power_limit_max_kw: float, s=None) -> tuple[float, float]:
    fallback = float(optimizer.cfg.ess_limit_fallback_kw)
    if not (0 < fallback <= power_limit_max_kw):
        fallback = min(max(fallback, 1.0), power_limit_max_kw)

    state = s if s is not None else optimizer._last_state

    charge_cap = fallback
    discharge_cap = fallback

    configured_charge_baseline = max(0.1, float(optimizer.cfg.ess_charge_limit_value))
    configured_discharge_baseline = max(0.1, float(optimizer.cfg.ess_discharge_limit_value))

    if state and valid_hw_cap_kw(state.ess_charge_limit_entity_max_kw):
        charge_cap = float(state.ess_charge_limit_entity_max_kw)
    elif state and valid_hw_cap_kw(state.ess_max_charge_kw):
        charge_cap = float(state.ess_max_charge_kw)
    elif valid_hw_cap_kw(optimizer._last_hw_charge_cap_kw):
        charge_cap = float(optimizer._last_hw_charge_cap_kw)

    if state and valid_hw_cap_kw(state.ess_discharge_limit_entity_max_kw):
        discharge_cap = float(state.ess_discharge_limit_entity_max_kw)
    elif state and valid_hw_cap_kw(state.ess_max_discharge_kw):
        discharge_cap = float(state.ess_max_discharge_kw)
    elif valid_hw_cap_kw(optimizer._last_hw_discharge_cap_kw):
        discharge_cap = float(optimizer._last_hw_discharge_cap_kw)

    charge_cap = max(charge_cap, configured_charge_baseline)
    discharge_cap = max(discharge_cap, configured_discharge_baseline)
    return charge_cap, discharge_cap


def validate_time_config(optimizer) -> list[str]:
    warnings: list[str] = []
    for field in (
        "daily_summary_time",
        "morning_summary_time",
        "standby_holdoff_end_time",
        "morning_slow_charge_until",
    ):
        value = getattr(optimizer.cfg, field, "")
        if not is_valid_time(value):
            warnings.append(f"{field}={value!r} is invalid (expected HH:MM or HH:MM:SS)")
    if warnings:
        for msg in warnings:
            logger.warning("Config time validation: %s", msg)
    return warnings


def is_valid_time(value: str) -> bool:
    try:
        parts = str(value).split(":")
        if len(parts) not in (2, 3):
            return False
        h, m = int(parts[0]), int(parts[1])
        s = int(parts[2]) if len(parts) == 3 else 0
        return 0 <= h <= 23 and 0 <= m <= 59 and 0 <= s <= 59
    except (ValueError, TypeError):
        return False


def warn_parse_issue(optimizer, entity_id: str, raw_value: str, label: str) -> None:
    now_ts = datetime.now().timestamp()
    cache_key = (entity_id, raw_value)
    last_ts = optimizer._sensor_parse_warning_cache.get(cache_key)
    if last_ts is not None and now_ts - last_ts < 300:
        return

    cutoff = now_ts - 1800
    if len(optimizer._sensor_parse_warning_cache) > 512:
        optimizer._sensor_parse_warning_cache = {
            k: ts for k, ts in optimizer._sensor_parse_warning_cache.items() if ts >= cutoff
        }

    if len(optimizer._sensor_parse_warning_cache) > 512:
        newest = sorted(
            optimizer._sensor_parse_warning_cache.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:512]
        optimizer._sensor_parse_warning_cache = dict(newest)

    optimizer._sensor_parse_warning_cache[cache_key] = now_ts

    if len(optimizer._sensor_parse_warning_cache) > 512:
        newest = sorted(
            optimizer._sensor_parse_warning_cache.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:512]
        optimizer._sensor_parse_warning_cache = dict(newest)

    logger.warning("%s sensor %s returned non-numeric state %r; using safe defaults", label, entity_id, raw_value)


def parse_ts(value) -> Optional[float]:
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
