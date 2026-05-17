from __future__ import annotations

from datetime import datetime
from typing import Any


def price_tracking_events(optimizer, date: str | None = None, limit: int = 2000) -> list[dict[str, Any]]:
    return optimizer._state_store.get_price_events(date=date, limit=limit)


async def daily_earnings_summary(optimizer, date: str | None = None) -> dict[str, Any]:
    target_date = date or datetime.now(optimizer._tz).date().isoformat()
    return await optimizer._earnings.daily_summary(target_date)


async def earnings_history(optimizer, days: int = 7) -> dict[str, Any]:
    return await optimizer._earnings.history(days)


def audit_events(optimizer, limit: int = 200) -> list[dict[str, Any]]:
    return optimizer._state_store.get_audit_events(limit=limit)


def record_audit_event(
    optimizer,
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
    optimizer._state_store.record_audit_event(
        action=action,
        source=source,
        actor=actor,
        result=result,
        target_key=target_key,
        old_value=old_value,
        new_value=new_value,
        details=details,
    )


def list_threshold_presets(optimizer) -> list[dict[str, Any]]:
    return optimizer._state_store.list_threshold_presets()


def get_threshold_preset(optimizer, name: str) -> dict[str, Any] | None:
    return optimizer._state_store.get_threshold_preset(name)


def save_threshold_preset(optimizer, name: str, payload: dict[str, Any]) -> None:
    optimizer._state_store.save_threshold_preset(name, payload)


def delete_threshold_preset(optimizer, name: str) -> bool:
    return optimizer._state_store.delete_threshold_preset(name)


def decision_trace(optimizer, limit: int = 200) -> list[dict[str, Any]]:
    n = max(1, min(int(limit), 2000))
    return list(optimizer._decision_trace)[:n]