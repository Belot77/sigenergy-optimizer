from __future__ import annotations

from typing import Any


def forecast_attr_candidates(preferred_attr: str | None = None) -> list[str]:
    candidates: list[str] = []
    for attr in (preferred_attr, "forecasts", "forecast", "detailedForecast", "detailedHourly"):
        if attr and attr not in candidates:
            candidates.append(attr)
    return candidates


def forecast_time_candidates(preferred_key: str | None = None) -> list[str]:
    candidates: list[str] = []
    for key in (preferred_key, "start_time", "time", "nem_time", "period_start"):
        if key and key not in candidates:
            candidates.append(key)
    return candidates


def forecast_value_candidates(preferred_key: str | None = None) -> list[str]:
    candidates: list[str] = []
    for key in (preferred_key, "per_kwh", "value"):
        if key and key not in candidates:
            candidates.append(key)
    return candidates


def forecast_entry_time(entry: Any, preferred_key: str | None = None) -> Any:
    if not isinstance(entry, dict):
        return None
    for key in forecast_time_candidates(preferred_key):
        value = entry.get(key)
        if value not in (None, ""):
            return value
    return None


def forecast_entry_value(entry: Any, preferred_key: str | None = None) -> float | None:
    if not isinstance(entry, dict):
        return None
    for key in forecast_value_candidates(preferred_key):
        try:
            value = entry.get(key)
            if value in (None, ""):
                continue
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def extract_forecast_entries(
    bulk: dict[str, Any],
    *,
    primary_entity: str,
    explicit_entity: str,
    preferred_attr: str,
    preferred_time_key: str,
    preferred_value_key: str,
) -> list[Any]:
    candidates: list[str] = []
    if primary_entity:
        candidates.append(f"{primary_entity}_detailed")
    candidates.extend([explicit_entity, primary_entity])

    seen: set[str] = set()
    best_entries: list[Any] = []
    best_score = -1

    for entity_id in candidates:
        if not entity_id or entity_id in seen:
            continue
        seen.add(entity_id)
        obj = bulk.get(entity_id)
        if not obj:
            continue
        attrs = obj.get("attributes", {})
        for attr_name in forecast_attr_candidates(preferred_attr):
            entries = attrs.get(attr_name)
            if not isinstance(entries, list) or not entries:
                continue
            score = 0
            if entity_id.endswith("_detailed"):
                score += 1000
            if entity_id == explicit_entity:
                score += 100
            if attr_name == preferred_attr:
                score += 10
            valid_points = 0
            for entry in entries:
                if forecast_entry_time(entry, preferred_time_key) is None:
                    continue
                if forecast_entry_value(entry, preferred_value_key) is None:
                    continue
                valid_points += 1
            score += valid_points
            if valid_points and score > best_score:
                best_entries = entries
                best_score = score

    return best_entries