from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from .models import Decision, SolarState


def record_price_tracking(optimizer, s: SolarState) -> None:
    now = datetime.now(optimizer._tz)
    now_block = int(now.timestamp()) // 300
    import_kw = max(0.0, float(s.grid_import_power_kw or 0.0))
    export_kw = max(0.0, float(s.grid_export_power_kw or 0.0))
    import_price = s.current_price if s.current_price is not None else None
    feedin_price = s.feedin_price if s.feedin_price is not None else None
    should_record = False
    if optimizer._last_tracked_block is None or now_block != optimizer._last_tracked_block:
        should_record = True
    if abs(import_kw - optimizer._last_tracked_import_kw) >= 0.25:
        should_record = True
    if abs(export_kw - optimizer._last_tracked_export_kw) >= 0.25:
        should_record = True
    if import_price is not None and import_price != optimizer._last_tracked_import_price:
        should_record = True
    if feedin_price is not None and feedin_price != optimizer._last_tracked_feedin_price:
        should_record = True
    if not should_record:
        return
    block_start = datetime.fromtimestamp(now_block * 300, tz=optimizer._tz).replace(second=0, microsecond=0)
    optimizer._state_store.record_price_event(
        ts=now.isoformat(timespec="seconds"),
        block_ts=block_start.isoformat(timespec="seconds"),
        grid_import_kw=import_kw,
        grid_export_kw=export_kw,
        import_price=import_price,
        feedin_price=feedin_price,
        battery_soc=float(s.battery_soc),
    )
    optimizer._last_tracked_block = now_block
    optimizer._last_tracked_import_kw = import_kw
    optimizer._last_tracked_export_kw = export_kw
    optimizer._last_tracked_import_price = import_price
    optimizer._last_tracked_feedin_price = feedin_price
    if now.hour == 0 and now.minute < 10:
        optimizer._state_store.purge_old_price_tracking(retain_days=60)


def record_decision_trace(optimizer, s: SolarState, d: Decision) -> None:
    gates = d.trace_gates if isinstance(d.trace_gates, dict) else {}
    values = d.trace_values if isinstance(d.trace_values, dict) else {}
    optimizer._decision_trace.appendleft(
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


def record_automation_audit(
    optimizer,
    s: SolarState,
    d: Decision,
    prev: Optional[Decision],
) -> None:
    cfg = optimizer.cfg
    effective_mode = optimizer._manual_mode_override or s.sigenergy_mode
    if effective_mode not in {cfg.automated_option, ""}:
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

    optimizer.record_audit_event(
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


def accumulate_history(optimizer, s, d) -> None:
    import time as _time

    if not hasattr(optimizer, "_chart_history_power"):
        optimizer._chart_history_power = []
        optimizer._chart_history_price = []
    now_ms = int(_time.time() * 1000)
    cutoff = now_ms - 86_400_000
    optimizer._chart_history_power.append(
        {
            "t": now_ms,
            "battery": s.battery_soc,
            "pv": s.pv_kw,
            "load": s.load_kw,
            "exp": s.grid_export_power_kw,
            "imp": s.grid_import_power_kw,
            "minSoc": d.min_soc_to_sunrise,
            "pvForecast": s.solar_power_now_kw,
        }
    )
    optimizer._chart_history_price.append({"t": now_ms, "imp": s.current_price, "fit": s.feedin_price})
    optimizer._chart_history_power = [x for x in optimizer._chart_history_power if x["t"] >= cutoff]
    optimizer._chart_history_price = [x for x in optimizer._chart_history_price if x["t"] >= cutoff]
