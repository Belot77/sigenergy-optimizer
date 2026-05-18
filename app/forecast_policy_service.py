from __future__ import annotations

from typing import Optional

from .forecast_utils import forecast_entry_time, forecast_entry_value
from .models import SolarState


def negative_price_forecast_ahead(optimizer, s: SolarState, now_ts: float) -> bool:
    cutoff = now_ts + optimizer.cfg.negative_price_forecast_lookahead_hours * 3600
    for f in s.price_forecast_entries:
        if not isinstance(f, dict):
            continue
        try:
            ts = optimizer._parse_ts(forecast_entry_time(f, optimizer.cfg.price_forecast_time_key))
            price = forecast_entry_value(f, optimizer.cfg.price_forecast_value_key)
            if ts and ts <= cutoff and price < 0:
                return True
        except Exception:
            pass
    return False


def negative_price_before_cutoff(optimizer, s: SolarState, now_ts: float) -> bool:
    cutoff_dt = optimizer._today_at(optimizer.cfg.standby_holdoff_end_time)
    cutoff_ts = cutoff_dt.timestamp()
    if now_ts >= cutoff_ts:
        return False
    for f in s.price_forecast_entries:
        if not isinstance(f, dict):
            continue
        try:
            ts = optimizer._parse_ts(forecast_entry_time(f, optimizer.cfg.price_forecast_time_key))
            price = forecast_entry_value(f, optimizer.cfg.price_forecast_value_key)
            if ts and ts <= cutoff_ts and price < 0:
                return True
        except Exception:
            pass
    return False


def productive_solar_end_ts(optimizer, s: SolarState, sunset_ts: float, now_ts: float) -> Optional[float]:
    cfg = optimizer.cfg
    threshold = cfg.productive_solar_threshold_kw
    forecasts = s.solcast_detailed
    if not forecasts:
        return None
    found = None
    for f in reversed(forecasts):
        if not isinstance(f, dict):
            continue
        try:
            f_ts = optimizer._parse_ts(f.get("period_start", ""))
            pv_kw = float(f.get("pv_estimate", 0))
            if f_ts and f_ts <= sunset_ts and pv_kw >= threshold:
                found = f_ts
                break
        except Exception:
            pass
    return found