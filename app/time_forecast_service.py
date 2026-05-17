from __future__ import annotations

from typing import Optional

from .models import SolarState
from .sunrise_window_service import (
    today_at as today_at_service,
    day_window as day_window_service,
    battery_soc_required_to_sunrise as battery_soc_required_to_sunrise_service,
)
from .forecast_policy_service import (
    negative_price_forecast_ahead as negative_price_forecast_ahead_service,
    negative_price_before_cutoff as negative_price_before_cutoff_service,
    productive_solar_end_ts as productive_solar_end_ts_service,
)


def today_at(optimizer, time_str: str) -> datetime:
    return today_at_service(optimizer, time_str)


def day_window(optimizer, s: SolarState) -> tuple[float, float]:
    return day_window_service(optimizer, s)


def battery_soc_required_to_sunrise(optimizer, s: SolarState) -> float:
    return battery_soc_required_to_sunrise_service(optimizer, s)


def negative_price_forecast_ahead(optimizer, s: SolarState, now_ts: float) -> bool:
    return negative_price_forecast_ahead_service(optimizer, s, now_ts)


def negative_price_before_cutoff(optimizer, s: SolarState, now_ts: float) -> bool:
    return negative_price_before_cutoff_service(optimizer, s, now_ts)


def productive_solar_end_ts(optimizer, s: SolarState, sunset_ts: float, now_ts: float) -> Optional[float]:
    return productive_solar_end_ts_service(optimizer, s, sunset_ts, now_ts)
