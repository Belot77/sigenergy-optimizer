"""Combined O14/O16 accounting boundaries, synthetic control services only."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.models import BATTERY_EXPORT
from app.optimizer import MODE_CMD_CHARGE_GRID, MODE_MAX_SELF
from app.routers import api
from test_config_activation_authority_race import _app, _auth_settings
from test_config_activation_transactions import _change
from test_import_topup_decision_integrity import context, measured
from import_topup_coverage_helpers import seed_complete_import_history


@pytest.mark.parametrize("name", [
    "daily_import_energy", "grid_import_power_sensor", "price_sensor",
    "sigenergy_mode_select", "ha_control_switch", "ems_mode_select",
    "grid_import_limit", "automated_option", "full_import_option",
])
def test_identity_change_and_revert_cannot_hide_an_accounting_gap(context, name):
    case, optimizer, when = context
    old = getattr(optimizer.cfg, name)
    replacement = old + "_replacement"
    rig = SimpleNamespace(opt=optimizer, ha=optimizer.ha)

    async def run():
        with patch.object(api, "settings", _auth_settings()):
            first = await _change(rig, {name: replacement})
            assert first.status_code == 200
            assert not optimizer._import_topup_ledger.permission_known
            second = await _change(rig, {name: old})
            assert second.status_code == 200

    with case.optimizer_time(when):
        assert not optimizer._optimizer_import_topup_summary_today()["import_cost_floor_unknown"]
        asyncio.run(run())
        assert optimizer._optimizer_import_topup_summary_today()["import_cost_floor_unknown"]
        # Decision-only policy: the invalidated history remains unknown, while
        # no acknowledged priced import supplies an economic export floor.
        decision = optimizer._decide(measured(case, when, total=1, price=0.4))
        assert decision.trace_gates["import_cost_floor_unknown"]
        assert not decision.trace_gates["actual_import_cost_guard_blocking"]
        assert "warning" in decision.trace_values["actual_import_cost_guard_reason"].lower()
        assert decision.export_intent == BATTERY_EXPORT


def test_unchanged_identity_and_unrelated_tuning_preserve_accounting(context):
    case, optimizer, when = context

    async def run():
        async with optimizer.configuration_transaction():
            optimizer.cfg.daily_import_energy = optimizer.cfg.daily_import_energy
            optimizer.cfg.export_threshold_high += 0.01

    with case.optimizer_time(when):
        asyncio.run(run())
        assert optimizer._import_topup_ledger.permission_known
        assert not optimizer._optimizer_import_topup_summary_today()["import_cost_floor_unknown"]


def test_back_to_back_force_import_block_and_auto_keep_unobserved_cost_unknown(context):
    case, optimizer, when = context
    state = measured(case, when, total=0, price=0.4)

    async def run():
        # Settlement is simulated; real request/target/ledger paths remain active.
        with (patch.object(optimizer, "_read_state", AsyncMock(return_value=state)),
              patch.object(optimizer, "_wait_for_exact_entity_state", AsyncMock(return_value=True))):
            await optimizer.apply_manual_mode(optimizer.cfg.full_import_option)
            state.daily_import_meter_value = state.daily_import_kwh = 1.0
            await optimizer.apply_manual_mode(optimizer.cfg.block_flow_option)
            await optimizer.apply_manual_mode(optimizer.cfg.automated_option)

    with case.optimizer_time(when):
        asyncio.run(run())
        assert not optimizer._import_topup_ledger.permission_known
        assert optimizer._optimizer_import_topup_summary_today()["import_cost_floor_unknown"]
        decision = optimizer._decide(measured(case, when, total=1, price=0.4))
        assert decision.trace_gates["import_cost_floor_unknown"]
        assert not decision.trace_gates["actual_import_cost_guard_blocking"]
        assert "warning" in decision.trace_values["actual_import_cost_guard_reason"].lower()
        assert decision.export_intent == BATTERY_EXPORT
    import_writes = [call for call in optimizer.ha.calls if call[0] == "set_number" and call[1] == optimizer.cfg.grid_import_limit]
    assert any(call[2] > 0.011 for call in import_writes)
    assert any(call[2] <= 0.011 for call in import_writes)


@pytest.mark.parametrize("invalid", [False, True], ids=["accepted", "validation-rejected"])
def test_direct_ess_import_changes_invalidate_only_after_validation(context, invalid):
    case, optimizer, when = context
    rig = SimpleNamespace(opt=optimizer, ha=optimizer.ha)

    async def run():
        transport = httpx.ASGITransport(app=_app(rig), client=("198.51.100.14", 12345))
        with patch.object(api, "settings", _auth_settings()):
            async with httpx.AsyncClient(transport=transport, base_url="http://combined.invalid") as client:
                responses = []
                for limit in ((1000.0,) if invalid else (4.0, 0.0)):
                    responses.append(await client.post("/api/set_ess", headers={"x-api-key": "synthetic-o14-key-for-offline-tests"}, json={
                        "ems_mode": MODE_CMD_CHARGE_GRID if limit else MODE_MAX_SELF,
                        "grid_export_limit": 0.0, "grid_import_limit": limit, "pv_max_power_limit": 25.0,
                    }))
                return responses

    with case.optimizer_time(when):
        responses = asyncio.run(run())
        assert all(response.status_code == (422 if invalid else 200) for response in responses), [r.text for r in responses]
        summary = optimizer._optimizer_import_topup_summary_today()
        assert summary["import_cost_floor_unknown"] is (not invalid)
        assert optimizer._import_topup_ledger.permission_known is invalid


@pytest.mark.parametrize("boundary", ["configuration", "manual"])
def test_unobserved_boundary_cannot_certify_inactive_midnight(context, boundary):
    case, optimizer, _ = context
    before = datetime(2026, 1, 15, 23, 59, 59, tzinfo=optimizer._tz)
    seed_complete_import_history(optimizer, before)

    async def change():
        if boundary == "manual":
            await optimizer.apply_manual_mode(optimizer.cfg.automated_option)
        else:
            old = optimizer.cfg.daily_import_energy
            async with optimizer.configuration_transaction():
                optimizer.cfg.daily_import_energy = old + "_new"
            async with optimizer.configuration_transaction():
                optimizer.cfg.daily_import_energy = old

    with case.optimizer_time(before):
        asyncio.run(change())
    after = before + timedelta(seconds=1)
    optimizer._record_optimizer_import_topup(measured(case, after, total=0, price=0.4), None, after)
    ledger = optimizer._import_topup_ledger
    assert ledger.summary(after.date().isoformat(), source=optimizer._import_topup_source())["import_cost_floor_unknown"]
