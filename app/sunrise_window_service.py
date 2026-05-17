from __future__ import annotations

from datetime import datetime

from .models import SolarState


def today_at(optimizer, time_str: str) -> datetime:
    """Return today's date combined with a HH:MM or HH:MM:SS string."""
    try:
        parts = time_str.split(":")
        h, m = int(parts[0]), int(parts[1])
        s = int(parts[2]) if len(parts) > 2 else 0
        now = optimizer._now()
        return now.replace(hour=h, minute=m, second=s, microsecond=0)
    except (ValueError, IndexError, AttributeError):
        import logging

        logger = logging.getLogger(__name__)
        logger.warning("Invalid time string in config: %r - using end of day", time_str)
        now = optimizer._now()
        return now.replace(hour=23, minute=59, second=59, microsecond=0)


def day_window(optimizer, s: SolarState) -> tuple[float, float]:
    """Return (day_start_ts, day_end_ts) in Unix seconds."""
    now_ts = optimizer._now().timestamp()
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

    now_ts = optimizer._now().timestamp()
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