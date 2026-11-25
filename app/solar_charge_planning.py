"""Calculate the Solar Bypass charge ceiling from qualified planning inputs."""

from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING


@dataclass(frozen=True)
class SolarChargePlan:
    requested_kw: float
    protected_fill_kwh: float
    future_opportunity_kwh: float
    required_now_kwh: float
    current_window_hours: float
    fill_progress_floor_kw: float
    fill_progress_hours: float
    trajectory_source: str


def plan_solar_charge(
    forecast_periods: list[tuple[float, float]],
    *,
    forecast_period_hours: float,
    now_ts: float,
    fill_deadline_ts: float,
    charge_capability_kw: float,
    normal_charge_request_kw: float,
    load_kw: float,
    safety_factor: float,
    battery_capacity_kwh: float,
    battery_soc_pct: float,
) -> SolarChargePlan | None:
    """Return a plan only when the forecast covers the exact remaining window."""
    # Decimal avoids rounding an exact 1.20 kW request up to 1.21 kW.
    period_seconds = Decimal(str(forecast_period_hours)) * 3600
    window_start = Decimal(str(now_ts))
    fill_deadline = Decimal(str(fill_deadline_ts))
    normal_cap = min(
        Decimal(str(charge_capability_kw)), Decimal(str(normal_charge_request_kw)),
    )
    load = Decimal(str(load_kw))
    protected_fill = (
        Decimal(str(safety_factor))
        * Decimal(str(battery_capacity_kwh))
        * (100 - Decimal(str(battery_soc_pct))) / 100
    )
    covered_until = window_start
    current_hours = Decimal(0)
    future_opportunity = Decimal(0)
    for start_ts, pv_kw in forecast_periods:
        start = Decimal(str(start_ts))
        end = min(start + period_seconds, fill_deadline)
        if end <= window_start or start >= fill_deadline:
            continue
        overlap_start = max(start, window_start)
        # A reduced charge ceiling requires contiguous coverage even when
        # export eligibility tolerates timestamp jitter.
        if overlap_start != covered_until:
            break
        hours = (end - overlap_start) / 3600
        if start <= window_start < end:
            current_hours = hours
        else:
            chargeable_kw = min(max(Decimal(str(pv_kw)) - load, Decimal(0)), normal_cap)
            future_opportunity += chargeable_kw * hours
        covered_until = end
    if covered_until != fill_deadline or current_hours <= 0:
        return None

    required_now = max(Decimal(0), protected_fill - future_opportunity)
    # Keep some present charging while partial even when later opportunity is ample.
    fill_progress_hours = (fill_deadline - window_start) / 3600
    fill_progress_floor = protected_fill / fill_progress_hours
    urgent_current_kw = required_now / current_hours
    trajectory_source = (
        "exact_full" if protected_fill == 0
        else "urgent_current_interval" if urgent_current_kw > fill_progress_floor
        else "fill_progress_floor"
    )
    requested = min(normal_cap, max(fill_progress_floor, urgent_current_kw))
    charge_step_kw = Decimal("0.01")
    requested = min(normal_cap, requested.quantize(charge_step_kw, rounding=ROUND_CEILING))
    return SolarChargePlan(
        requested_kw=float(requested),
        protected_fill_kwh=float(protected_fill),
        future_opportunity_kwh=float(future_opportunity),
        required_now_kwh=float(required_now),
        current_window_hours=float(current_hours),
        fill_progress_floor_kw=float(min(
            normal_cap, fill_progress_floor.quantize(charge_step_kw, rounding=ROUND_CEILING),
        )),
        fill_progress_hours=float(fill_progress_hours),
        trajectory_source=trajectory_source,
    )
