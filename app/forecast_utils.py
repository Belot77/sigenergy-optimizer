from __future__ import annotations

from typing import Any


UNAVAILABLE_STATES = {"unknown", "unavailable", "none", ""}


def forecast_attr_candidates(preferred_attr: str | None = None) -> list[str]:
    candidates: list[str] = []
    for attr in (preferred_attr, "detailedForecast", "forecasts", "forecast", "detailedHourly"):
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


def primary_entity_from_detailed(entity_id: str | None) -> str | None:
    if not entity_id:
        return None
    suffix = "_detailed"
    if entity_id.endswith(suffix):
        return entity_id[: -len(suffix)]
    return None


def forecast_entity_candidates(primary_entity: str | None, explicit_entity: str | None) -> list[str]:
    candidates: list[str] = []
    if primary_entity:
        candidates.append(f"{primary_entity}_detailed")
    if explicit_entity:
        candidates.append(explicit_entity)
    derived_primary = primary_entity_from_detailed(explicit_entity)
    if derived_primary:
        candidates.append(derived_primary)
    if primary_entity:
        candidates.append(primary_entity)

    seen: set[str] = set()
    unique: list[str] = []
    for entity_id in candidates:
        if entity_id and entity_id not in seen:
            seen.add(entity_id)
            unique.append(entity_id)
    return unique


def _has_forecast_attribute(attrs: dict[str, Any], attr_candidates: list[str]) -> bool:
    for attr_name in attr_candidates:
        entries = attrs.get(attr_name)
        if isinstance(entries, list) and entries:
            return True
    return False


def extract_forecast_entries(
    bulk: dict[str, Any],
    *,
    primary_entity: str,
    explicit_entity: str,
    preferred_attr: str,
    preferred_time_key: str,
    preferred_value_key: str,
    diagnostics: dict[str, Any] | None = None,
) -> list[Any]:
    entity_candidates = forecast_entity_candidates(primary_entity, explicit_entity)
    attr_candidates = forecast_attr_candidates(preferred_attr)
    time_candidates = forecast_time_candidates(preferred_time_key)
    value_candidates = forecast_value_candidates(preferred_value_key)

    if diagnostics is not None:
        diagnostics.clear()
        diagnostics.update({
            "entities_tried": list(entity_candidates),
            "attributes_tried": list(attr_candidates),
            "time_keys_tried": list(time_candidates),
            "value_keys_tried": list(value_candidates),
            "missing_entities": [],
            "unavailable_entities": [],
            "attempts": [],
            "selected_entity": None,
            "selected_attribute": None,
            "valid_points": 0,
            "failure_reason": "",
        })

    best_entries: list[Any] = []
    best_score = -1

    for entity_id in entity_candidates:
        obj = bulk.get(entity_id)
        if not obj:
            if diagnostics is not None:
                diagnostics["missing_entities"].append(entity_id)
            continue
        attrs = obj.get("attributes", {}) or {}
        state = str(obj.get("state", "")).lower()
        if state in UNAVAILABLE_STATES and not _has_forecast_attribute(attrs, attr_candidates):
            if diagnostics is not None:
                diagnostics["unavailable_entities"].append(entity_id)
            continue
        for attr_name in attr_candidates:
            entries = attrs.get(attr_name)
            if not isinstance(entries, list) or not entries:
                if diagnostics is not None:
                    diagnostics["attempts"].append({
                        "entity": entity_id,
                        "attribute": attr_name,
                        "entries": 0,
                        "valid_points": 0,
                    })
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
            if diagnostics is not None:
                diagnostics["attempts"].append({
                    "entity": entity_id,
                    "attribute": attr_name,
                    "entries": len(entries),
                    "valid_points": valid_points,
                })
            score += valid_points
            if valid_points and score > best_score:
                best_entries = entries
                best_score = score
                if diagnostics is not None:
                    diagnostics["selected_entity"] = entity_id
                    diagnostics["selected_attribute"] = attr_name
                    diagnostics["valid_points"] = valid_points

    if diagnostics is not None and not best_entries:
        diagnostics["failure_reason"] = "no forecast entries contained both a supported time key and value key"
    return best_entries
