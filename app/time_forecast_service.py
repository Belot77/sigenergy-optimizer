from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from .models import SolarState

logger = logging.getLogger(__name__)


def today_at(time_str: str) -> datetime:
    """Return today's date combined with a HH:MM or HH:MM:SS string."""
    try:
        parts = time_str.split(":")
        h, m = int(parts[0]), int(parts[1])
        s = int(parts[2]) if len(parts) > 2 else 0
        return datetime.now().replace(hour=h, minute=m, second=s, microsecond=0)
    except (ValueError, IndexError, AttributeError):
        logger.warning("Invalid time string in config: %r - using end of day", time_str)
        return datetime.now().replace(hour=23, minute=59, second=59, microsecond=0)


def day_window(optimizer, s: SolarState) -> tuple[float, float]:
    """Return (day_start_ts, day_end_ts) in Unix seconds."""
    now_ts = datetime.now().timestamp()
    sunrise_ts = s.next_sunrise_ts or now_ts
    if s.sun_above_horizon:
        actual_sunrise = sunrise_ts - 86400
    else:
        actual_sunrise = sunrise_ts
    day_start = actual_sunrise + 3600

    sunset_ts = s.next_sunset_ts or now_ts
    day_end = sunset_ts - optimizer.cfg.evening_mode_hours_before_sunset * 3600
    return day_start, day_end


def battery_soc_required_to_sunrise(optimizer, s: SolarState) -> float:
    """Dynamic overnight SoC target based on current load until sunrise."""
    cfg = optimizer.cfg
    cap = s.battery_capacity_kwh
    sunrise_ts = s.next_sunrise_ts
    if not sunrise_ts:
        return cfg.night_reserve_soc + cfg.night_reserve_buffer

    now_ts = datetime.now().timestamp()
    sunset_ts = s.next_sunset_ts or now_ts
    if s.sun_above_horizon:
        start_ts = sunset_ts
    else:
        start_ts = now_ts

    target_ts = sunrise_ts + 3600
    hours = max(0.0, (target_ts - start_ts) / 3600)
    load_kw = s.load_kw
    energy_need_kwh = load_kw * hours * cfg.sunrise_safety_factor
    need_pct = (energy_need_kwh / cap) * 100 if cap > 0 else 0
    target = need_pct + cfg.sunrise_buffer_percent
    return max(target, cfg.sunrise_reserve_soc)


def negative_price_forecast_ahead(optimizer, s: SolarState, now_ts: float) -> bool:
    cutoff = now_ts + optimizer.cfg.negative_price_forecast_lookahead_hours * 3600
    for f in s.price_forecast_entries:
        if not isinstance(f, dict):
            continue
        try:
            ts = optimizer._parse_ts(f.get(optimizer.cfg.price_forecast_time_key, ""))
            price = float(f.get(optimizer.cfg.price_forecast_value_key, 0))
            if ts and ts <= cutoff and price < 0:
                return True
        except Exception:
            pass
    return False


def negative_price_before_cutoff(optimizer, s: SolarState, now_ts: float) -> bool:
    cutoff_dt = optimizer._today_at(optimizer.cfg.standby_holdoff_end_time)
    if datetime.now() >= cutoff_dt:
        return False
    cutoff_ts = cutoff_dt.timestamp()
    for f in s.price_forecast_entries:
        if not isinstance(f, dict):
            continue
        try:
            ts = optimizer._parse_ts(f.get(optimizer.cfg.price_forecast_time_key, ""))
            price = float(f.get(optimizer.cfg.price_forecast_value_key, 0))
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
