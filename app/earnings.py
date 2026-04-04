from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

from .config import Settings
from .ha_client import HAClient, UNAVAILABLE
from .state_store import StateStore


@dataclass(frozen=True)
class EarningsSource:
    key: str
    label: str
    mode: str
    import_energy_entity: str
    export_energy_entity: str
    import_value_entity: str
    export_value_entity: str


def _parse_iso_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in UNAVAILABLE:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _is_available_state(row: dict[str, Any] | None) -> bool:
    if not row:
        return False
    return str(row.get("state", "")).strip().lower() not in UNAVAILABLE


def _normalize_daily_summary(
    *,
    day: str,
    source: EarningsSource,
    import_kwh: float,
    export_kwh: float,
    import_costs: float,
    export_earnings: float,
) -> dict[str, Any]:
    net = export_earnings - import_costs
    return {
        "date": day,
        "source_key": source.key,
        "source_label": source.label,
        "is_estimated": source.key == "estimated",
        "total_import_kwh": round(import_kwh, 3),
        "total_export_kwh": round(export_kwh, 3),
        "import_costs": round(import_costs, 4),
        "export_earnings": round(export_earnings, 4),
        "net": round(net, 4),
        "blocks": [],
    }


def _series_by_entity(history_rows: list[Any], entity_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for idx, series in enumerate(history_rows or []):
        if not isinstance(series, list):
            continue
        entity_id = entity_ids[idx] if idx < len(entity_ids) else None
        for item in series:
            if isinstance(item, dict) and item.get("entity_id"):
                entity_id = str(item.get("entity_id"))
                break
        if entity_id:
            out[str(entity_id)] = [item for item in series if isinstance(item, dict)]
    return out


def _last_numeric_before(series: list[dict[str, Any]], boundary: datetime) -> float | None:
    candidate: float | None = None
    for item in series:
        ts = _parse_iso_timestamp(item.get("last_updated") or item.get("last_changed"))
        if ts is None or ts >= boundary:
            continue
        value = _to_float(item.get("state"))
        if value is not None:
            candidate = value
    return candidate


def _latest_numeric_in_window(series: list[dict[str, Any]], start: datetime, end: datetime) -> float | None:
    candidate: float | None = None
    candidate_ts: datetime | None = None
    for item in series:
        ts = _parse_iso_timestamp(item.get("last_updated") or item.get("last_changed"))
        if ts is None or ts < start or ts >= end:
            continue
        value = _to_float(item.get("state"))
        if value is None:
            continue
        if candidate_ts is None or ts >= candidate_ts:
            candidate = value
            candidate_ts = ts
    return candidate


def _cumulative_delta(series: list[dict[str, Any]], start: datetime, end: datetime) -> float | None:
    start_value = _last_numeric_before(series, start)
    end_value = _last_numeric_before(series, end)
    if end_value is None:
        end_value = _latest_numeric_in_window(series, start, end)
    if start_value is None and end_value is not None:
        start_value = _latest_numeric_in_window(series, start - timedelta(days=2), start)
    if start_value is None or end_value is None:
        return None
    return end_value - start_value


def summarize_daily_source(
    source: EarningsSource,
    day: str,
    by_entity: dict[str, list[dict[str, Any]]],
    tzinfo,
) -> dict[str, Any] | None:
    day_date = date.fromisoformat(day)
    day_start = datetime.combine(day_date, time.min, tzinfo=tzinfo)
    day_end = day_start + timedelta(days=1)

    import_series = by_entity.get(source.import_energy_entity, [])
    export_series = by_entity.get(source.export_energy_entity, [])
    import_value_series = by_entity.get(source.import_value_entity, [])
    export_value_series = by_entity.get(source.export_value_entity, [])

    import_kwh = _latest_numeric_in_window(import_series, day_start, day_end)
    export_kwh = _latest_numeric_in_window(export_series, day_start, day_end)
    import_costs = _latest_numeric_in_window(import_value_series, day_start, day_end)
    export_earnings = _latest_numeric_in_window(export_value_series, day_start, day_end)

    if all(v is None for v in (import_kwh, export_kwh, import_costs, export_earnings)):
        return None

    return _normalize_daily_summary(
        day=day,
        source=source,
        import_kwh=import_kwh or 0.0,
        export_kwh=export_kwh or 0.0,
        import_costs=import_costs or 0.0,
        export_earnings=export_earnings or 0.0,
    )


def summarize_cumulative_source(
    source: EarningsSource,
    day: str,
    by_entity: dict[str, list[dict[str, Any]]],
    tzinfo,
) -> dict[str, Any] | None:
    day_date = date.fromisoformat(day)
    day_start = datetime.combine(day_date, time.min, tzinfo=tzinfo)
    day_end = day_start + timedelta(days=1)

    import_kwh_delta = _cumulative_delta(by_entity.get(source.import_energy_entity, []), day_start, day_end)
    export_kwh_delta = _cumulative_delta(by_entity.get(source.export_energy_entity, []), day_start, day_end)
    import_value_delta = _cumulative_delta(by_entity.get(source.import_value_entity, []), day_start, day_end)
    export_value_delta = _cumulative_delta(by_entity.get(source.export_value_entity, []), day_start, day_end)

    if all(v is None for v in (import_kwh_delta, export_kwh_delta, import_value_delta, export_value_delta)):
        return None

    return _normalize_daily_summary(
        day=day,
        source=source,
        import_kwh=import_kwh_delta or 0.0,
        export_kwh=export_kwh_delta or 0.0,
        import_costs=import_value_delta or 0.0,
        export_earnings=-(export_value_delta or 0.0),
    )


class EarningsService:
    def __init__(self, ha: HAClient, cfg: Settings, state_store: StateStore, tzinfo) -> None:
        self._ha = ha
        self._cfg = cfg
        self._state_store = state_store
        self._tz = tzinfo

    def _estimated_source(self) -> EarningsSource:
        return EarningsSource(
            key="estimated",
            label="Estimated From Sampled Power",
            mode="estimated",
            import_energy_entity="",
            export_energy_entity="",
            import_value_entity="",
            export_value_entity="",
        )

    def _source_definitions(self) -> list[EarningsSource]:
        out: list[EarningsSource] = []
        if all(
            [
                self._cfg.earnings_import_energy_entity,
                self._cfg.earnings_export_energy_entity,
                self._cfg.earnings_import_value_entity,
                self._cfg.earnings_export_value_entity,
            ]
        ):
            out.append(
                EarningsSource(
                    key="custom",
                    label="Configured Earnings Sensors",
                    mode=self._cfg.earnings_custom_mode,
                    import_energy_entity=self._cfg.earnings_import_energy_entity,
                    export_energy_entity=self._cfg.earnings_export_energy_entity,
                    import_value_entity=self._cfg.earnings_import_value_entity,
                    export_value_entity=self._cfg.earnings_export_value_entity,
                )
            )

        out.append(
            EarningsSource(
                key="amber_balance",
                label="Amber Balance",
                mode="cumulative",
                import_energy_entity=self._cfg.amber_balance_import_kwh_entity,
                export_energy_entity=self._cfg.amber_balance_export_kwh_entity,
                import_value_entity=self._cfg.amber_balance_import_value_entity,
                export_value_entity=self._cfg.amber_balance_export_value_entity,
            )
        )
        out.append(
            EarningsSource(
                key="sigenergy_daily",
                label="Sigenergy Daily Totals",
                mode="daily",
                import_energy_entity=self._cfg.daily_import_energy,
                export_energy_entity=self._cfg.daily_export_energy,
                import_value_entity=self._cfg.daily_import_cost_entity,
                export_value_entity=self._cfg.daily_export_compensation_entity,
            )
        )
        return out

    async def _resolve_source(self) -> EarningsSource:
        source_pref = str(self._cfg.earnings_source or "auto").strip().lower()
        if source_pref == "estimated":
            return self._estimated_source()

        defs = self._source_definitions()
        if source_pref != "auto":
            defs = [src for src in defs if src.key == source_pref]
        entity_ids = []
        for src in defs:
            entity_ids.extend(
                [
                    src.import_energy_entity,
                    src.export_energy_entity,
                    src.import_value_entity,
                    src.export_value_entity,
                ]
            )
        entity_ids = [entity_id for entity_id in entity_ids if entity_id]
        current = await self._ha.bulk_states(entity_ids) if entity_ids else {}
        for src in defs:
            if all(
                _is_available_state(current.get(entity_id))
                for entity_id in [
                    src.import_energy_entity,
                    src.export_energy_entity,
                    src.import_value_entity,
                    src.export_value_entity,
                ]
            ):
                return src
        return self._estimated_source()

    def _annotate_estimated(self, summary: dict[str, Any], day: str) -> dict[str, Any]:
        out = dict(summary)
        out["date"] = day
        out["source_key"] = "estimated"
        out["source_label"] = "Estimated From Sampled Power"
        out["is_estimated"] = True
        return out

    async def _fetch_history(self, source: EarningsSource, start: datetime, end: datetime) -> dict[str, list[dict[str, Any]]]:
        entity_ids = [
            source.import_energy_entity,
            source.export_energy_entity,
            source.import_value_entity,
            source.export_value_entity,
        ]
        lookback = timedelta(days=2) if source.mode == "cumulative" else timedelta(minutes=1)
        rows = await self._ha.get_history_period(start - lookback, end, entity_ids)
        return _series_by_entity(rows, entity_ids)

    async def daily_summary(self, day: str) -> dict[str, Any]:
        source = await self._resolve_source()
        if source.mode == "estimated":
            return self._annotate_estimated(self._state_store.daily_earnings_summary(day), day)

        day_date = date.fromisoformat(day)
        start = datetime.combine(day_date, time.min, tzinfo=self._tz)
        end = start + timedelta(days=1)
        by_entity = await self._fetch_history(source, start, end)
        summary = (
            summarize_daily_source(source, day, by_entity, self._tz)
            if source.mode == "daily"
            else summarize_cumulative_source(source, day, by_entity, self._tz)
        )
        if summary is None:
            return self._annotate_estimated(self._state_store.daily_earnings_summary(day), day)
        return summary

    async def history(self, days: int) -> dict[str, Any]:
        days = max(1, min(days, 30))
        today = datetime.now(self._tz).date()
        source = await self._resolve_source()
        if source.mode == "estimated":
            out = []
            for i in range(days):
                day = (today - timedelta(days=i)).isoformat()
                summary = self._annotate_estimated(self._state_store.daily_earnings_summary(day), day)
                out.append(
                    {
                        "date": day,
                        "source_key": summary["source_key"],
                        "source_label": summary["source_label"],
                        "import_kwh": summary.get("total_import_kwh", 0.0),
                        "export_kwh": summary.get("total_export_kwh", 0.0),
                        "import_costs": summary.get("import_costs", 0.0),
                        "export_earnings": summary.get("export_earnings", 0.0),
                        "net": summary.get("net", 0.0),
                    }
                )
            return {"source_key": "estimated", "source_label": "Estimated From Sampled Power", "days": out}

        earliest = today - timedelta(days=days - 1)
        start = datetime.combine(earliest, time.min, tzinfo=self._tz)
        end = datetime.combine(today + timedelta(days=1), time.min, tzinfo=self._tz)
        by_entity = await self._fetch_history(source, start, end)

        out = []
        for i in range(days):
            day = (today - timedelta(days=i)).isoformat()
            summary = (
                summarize_daily_source(source, day, by_entity, self._tz)
                if source.mode == "daily"
                else summarize_cumulative_source(source, day, by_entity, self._tz)
            )
            if summary is None:
                summary = self._annotate_estimated(self._state_store.daily_earnings_summary(day), day)
            out.append(
                {
                    "date": day,
                    "source_key": summary["source_key"],
                    "source_label": summary["source_label"],
                    "import_kwh": summary.get("total_import_kwh", 0.0),
                    "export_kwh": summary.get("total_export_kwh", 0.0),
                    "import_costs": summary.get("import_costs", 0.0),
                    "export_earnings": summary.get("export_earnings", 0.0),
                    "net": summary.get("net", 0.0),
                }
            )
        return {"source_key": source.key, "source_label": source.label, "days": out}