"""Calculate Solar Bypass energy and timing budgets from qualified inputs."""

from __future__ import annotations

import math


def _solar_surplus_finite_number(name: str, value: object) -> float:
    """Return one finite numeric helper input without permissive coercion."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{name} must be finite")
    return numeric


def _solar_surplus_energy_budget(
    *,
    remaining_forecast_kwh: float,
    current_load_kw: float,
    hours_to_sunset: float,
    rated_capacity_kwh: float,
    battery_soc_pct: float,
    safety_factor: float,
) -> dict[str, float | bool]:
    """Calculate the future Solar Surplus aggregate energy proof in kWh."""
    forecast_kwh = _solar_surplus_finite_number(
        "remaining_forecast_kwh",
        remaining_forecast_kwh,
    )
    load_kw = _solar_surplus_finite_number("current_load_kw", current_load_kw)
    remaining_hours = _solar_surplus_finite_number(
        "hours_to_sunset",
        hours_to_sunset,
    )
    capacity_kwh = _solar_surplus_finite_number(
        "rated_capacity_kwh",
        rated_capacity_kwh,
    )
    soc_pct = _solar_surplus_finite_number("battery_soc_pct", battery_soc_pct)
    factor = _solar_surplus_finite_number("safety_factor", safety_factor)

    if forecast_kwh < 0.0:
        raise ValueError("remaining_forecast_kwh must be non-negative")
    if load_kw < 0.0:
        raise ValueError("current_load_kw must be non-negative")
    if remaining_hours < 0.0:
        raise ValueError("hours_to_sunset must be non-negative")
    if capacity_kwh <= 0.0:
        raise ValueError("rated_capacity_kwh must be greater than zero")
    if not 0.0 <= soc_pct <= 100.0:
        raise ValueError("battery_soc_pct must be between 0 and 100")
    if factor < 1.0:
        raise ValueError("safety_factor must be greater than or equal to 1.0")

    remaining_load_kwh = load_kw * remaining_hours
    fill_need_kwh = capacity_kwh * max(100.0 - soc_pct, 0.0) / 100.0
    required_energy_kwh = remaining_load_kwh + fill_need_kwh
    protected_requirement_kwh = factor * required_energy_kwh
    raw_exportable_kwh = forecast_kwh - protected_requirement_kwh
    # Preserve the strict mathematical ``> 0`` policy at decimal equality;
    # binary floating-point round-off must not manufacture export permission.
    if math.isclose(raw_exportable_kwh, 0.0, rel_tol=0.0, abs_tol=1e-12):
        raw_exportable_kwh = 0.0
    calculated = (
        remaining_load_kwh,
        fill_need_kwh,
        required_energy_kwh,
        protected_requirement_kwh,
        raw_exportable_kwh,
    )
    if not all(math.isfinite(value) for value in calculated):
        raise ValueError("solar surplus energy calculation must remain finite")

    return {
        "remaining_forecast_kwh": forecast_kwh,
        "remaining_load_kwh": remaining_load_kwh,
        "fill_need_kwh": fill_need_kwh,
        "required_energy_kwh": required_energy_kwh,
        "protected_requirement_kwh": protected_requirement_kwh,
        "raw_exportable_kwh": raw_exportable_kwh,
        "exportable_kwh": max(0.0, raw_exportable_kwh),
        "budget_passed": raw_exportable_kwh > 0.0,
    }


def _solar_surplus_timing_budget(
    detailed_periods: list[tuple[float, float]],
    *,
    forecast_period_hours: float,
    now_ts: float,
    sunset_ts: float,
    current_load_kw: float,
    charge_capability_kw: float,
    fill_need_kwh: float,
    safety_factor: float,
) -> dict[str, float | bool]:
    """Calculate chargeable detailed-PV opportunity before sunset."""
    load_kw = _solar_surplus_finite_number("current_load_kw", current_load_kw)
    charge_cap_kw = _solar_surplus_finite_number(
        "charge_capability_kw",
        charge_capability_kw,
    )
    fill_kwh = _solar_surplus_finite_number("fill_need_kwh", fill_need_kwh)
    factor = _solar_surplus_finite_number("safety_factor", safety_factor)

    if load_kw < 0.0:
        raise ValueError("current_load_kw must be non-negative")
    if charge_cap_kw <= 0.0:
        raise ValueError("charge_capability_kw must be greater than zero")
    if fill_kwh < 0.0:
        raise ValueError("fill_need_kwh must be non-negative")
    if factor < 1.0:
        raise ValueError("safety_factor must be greater than or equal to 1.0")

    if fill_kwh == 0.0:
        return {
            "fill_need_kwh": 0.0,
            "timed_charge_opportunity_kwh": 0.0,
            "safe_timed_charge_opportunity_kwh": 0.0,
            "timing_passed": True,
        }

    period_hours = _solar_surplus_finite_number(
        "forecast_period_hours",
        forecast_period_hours,
    )
    window_start_ts = _solar_surplus_finite_number("now_ts", now_ts)
    window_end_ts = _solar_surplus_finite_number("sunset_ts", sunset_ts)
    if period_hours <= 0.0:
        raise ValueError("forecast_period_hours must be greater than zero")
    if window_end_ts <= window_start_ts:
        raise ValueError("sunset_ts must be greater than now_ts")
    period_seconds = period_hours * 3600.0
    if not math.isfinite(period_seconds):
        raise ValueError("forecast period duration must remain finite")

    timed_charge_opportunity_kwh = 0.0
    for period in detailed_periods:
        if not isinstance(period, (tuple, list)) or len(period) != 2:
            raise ValueError("detailed periods must contain (start_ts, pv_kw) pairs")
        period_start_ts = _solar_surplus_finite_number("period_start_ts", period[0])
        pv_kw = _solar_surplus_finite_number("pv_kw", period[1])
        if pv_kw < 0.0:
            raise ValueError("pv_kw must be non-negative")

        period_end_ts = period_start_ts + period_seconds
        if not math.isfinite(period_end_ts):
            raise ValueError("forecast period end must remain finite")
        overlap_start_ts = max(period_start_ts, window_start_ts)
        overlap_end_ts = min(period_end_ts, window_end_ts)
        overlap_seconds = max(0.0, overlap_end_ts - overlap_start_ts)
        if overlap_seconds == 0.0:
            continue

        chargeable_pv_kw = min(max(pv_kw - load_kw, 0.0), charge_cap_kw)
        timed_charge_opportunity_kwh += chargeable_pv_kw * overlap_seconds / 3600.0
        if not math.isfinite(timed_charge_opportunity_kwh):
            raise ValueError("timed charge opportunity must remain finite")

    safe_timed_charge_opportunity_kwh = timed_charge_opportunity_kwh / factor
    if not math.isfinite(safe_timed_charge_opportunity_kwh):
        raise ValueError("safe timed charge opportunity must remain finite")
    return {
        "fill_need_kwh": fill_kwh,
        "timed_charge_opportunity_kwh": timed_charge_opportunity_kwh,
        "safe_timed_charge_opportunity_kwh": safe_timed_charge_opportunity_kwh,
        "timing_passed": safe_timed_charge_opportunity_kwh >= fill_kwh,
    }
