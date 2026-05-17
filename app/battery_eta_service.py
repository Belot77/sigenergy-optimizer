from __future__ import annotations

from .models import SolarState


def battery_eta(s, battery_power_kw: float) -> str:
    bsoc = s.battery_soc
    if bsoc >= 100:
        return "Full"
    if bsoc <= 0:
        return "Empty"
    power_abs = abs(battery_power_kw)
    if power_abs < 0.2:
        return "idle"
    cap = s.battery_capacity_kwh
    if battery_power_kw > 0:
        soc_gap = 100 - bsoc
        if soc_gap <= 0:
            return "Full"
        mins = (cap * soc_gap / 100) / power_abs * 60
    else:
        avail = s.available_discharge_energy_kwh
        if avail <= 0:
            return "Empty"
        mins = avail / power_abs * 60
    if mins > 48 * 60:
        return "idle"
    mins = max(1, round(mins))
    if mins >= 1440:
        d = mins // 1440
        h = (mins % 1440) // 60
        return f"{d}d{h}h"
    if mins >= 60:
        h = mins // 60
        m = mins % 60
        return f"{h}h{m}m"
    return f"{mins}m"