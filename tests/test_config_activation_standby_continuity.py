from __future__ import annotations

import asyncio
from datetime import datetime

from app.optimizer import MODE_CMD_DISCHARGE_PV, MODE_MAX_SELF
import test_haos49_special_mode_characterization as standby_fixtures


def test_standby_entry_floor_survives_repeated_configuration_identity_activations() -> None:
    case = standby_fixtures.Haos49SpecialModeCharacterizationTests()
    case.setUp()
    try:
        when = datetime(2026, 1, 15, 9, 0)
        optimizer = case._standby_optimizer(when)
        common = {
            "battery_soc": 80.0,
            "available_discharge_energy_kwh": 24.0,
            "current_price": 0.30,
            "current_price_cents": 30.0,
            "feedin_price": 0.05,
            "feedin_price_cents": 5.0,
            "load_kw": 1.0,
        }

        entry = case.decide(
            optimizer,
            case.state(
                when,
                **common,
                forecast_remaining_kwh=100.0,
                forecast_today_kwh=100.0,
            ),
            when,
        )
        assert entry.trace_gates["standby_holdoff_active"]
        entry_floor = optimizer._holdoff_entry_floor
        assert entry_floor is not None
        optimizer._last_decision = entry

        async def activate(name: str, value: str) -> None:
            async with optimizer.configuration_transaction():
                setattr(optimizer.cfg, name, value)

        asyncio.run(activate("sigenergy_mode_select", "input_select.updated_owner"))
        assert optimizer._configuration_holdoff_continuity
        # Two activations with no intervening decision must retain continuity.
        assert optimizer._last_decision is None
        asyncio.run(activate("ha_control_switch", "switch.first_updated_remote_ems"))
        assert optimizer._configuration_holdoff_continuity
        assert optimizer._holdoff_entry_floor == entry_floor

        middle = case.decide(
            optimizer,
            case.state(
                when,
                **{**common, "load_kw": 3.5},
                forecast_remaining_kwh=90.0,
                forecast_today_kwh=90.0,
            ),
            when,
        )
        assert middle.trace_gates["standby_holdoff_active"]
        assert middle.trace_values["holdoff_entry_floor"] == entry_floor
        assert optimizer._holdoff_entry_floor == entry_floor
        optimizer._last_decision = middle

        asyncio.run(activate("ha_control_switch", "switch.updated_remote_ems"))
        assert optimizer._configuration_holdoff_continuity

        latest = case.decide(
            optimizer,
            case.state(
                when,
                **{**common, "load_kw": 6.0},
                forecast_remaining_kwh=75.0,
                forecast_today_kwh=75.0,
            ),
            when,
        )
        assert latest.trace_gates["standby_holdoff_active"]
        assert latest.trace_values["holdoff_entry_floor"] == entry_floor
        assert optimizer._holdoff_entry_floor == entry_floor
        optimizer._last_decision = latest

        exited = case.decide(
            optimizer,
            case.state(
                when,
                **{**common, "current_ems_mode": MODE_CMD_DISCHARGE_PV},
                forecast_remaining_kwh=0.0,
                forecast_today_kwh=0.0,
            ),
            when,
        )

        assert exited.ems_mode == MODE_MAX_SELF
        assert not exited.trace_gates["standby_holdoff_active"]
        assert optimizer._holdoff_entry_floor is None
        assert optimizer._configuration_holdoff_continuity is False
        assert exited.trace_values["holdoff_entry_floor"] is None
    finally:
        case.tearDown()
