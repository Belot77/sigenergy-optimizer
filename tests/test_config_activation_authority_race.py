"""Offline O14 regressions: configuration activation across authority-read awaits.

Safety assertions deliberately fail on the .76 baseline when stale entity
identity evidence authorizes an EMS command. Real API handlers, authentication,
control locking and application code run against synthetic HA and ASGI doubles.
No production startup, network transport or persistent configuration is used.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest
from fastapi import FastAPI

from app.optimizer import MODE_CMD_CHARGE_GRID, MODE_MAX_SELF
from app.routers import api
from test_control_authority_safety_characterization import _Rig


_API_KEY = "synthetic-o14-key-for-offline-tests"
_NEW_SELECTOR = "input_select.o14_new_owner"
_NEW_SWITCH = "switch.o14_new_remote"
_NEW_EMS = "select.o14_new_ems"


@pytest.fixture
def rig():
    value = _Rig()
    # Use fresh real-clock reports; event handshakes need no patched loop clock.
    value.clock.now = datetime.now(timezone.utc)
    value.automated()
    try:
        yield value
    finally:
        value.case.tearDown()


def _identities(rig):
    cfg = rig.opt.cfg
    return (cfg.sigenergy_mode_select, cfg.ha_control_switch, cfg.ems_mode_select)


def _seed_replacement(rig, *, owner="Manual", remote="off"):
    # Service acceptance never mutates these independent observed reports.
    rig.ha.observe(_NEW_SELECTOR, owner)
    rig.ha.observe(_NEW_SWITCH, remote)
    rig.ha.observe(_NEW_EMS, MODE_MAX_SELF)


def _grid_first_decision(rig):
    return rig.decision(ems_mode=MODE_CMD_CHARGE_GRID, import_limit=4.0)


def _app(rig):
    app = FastAPI()
    app.state.optimizer = rig.opt
    app.state.ha = rig.ha
    app.include_router(api.router, prefix="/api")
    return app


def _auth_settings():
    return SimpleNamespace(
        ui_api_key=_API_KEY,
        allow_loopback_without_api_key=False,
        require_api_key_for_all_mutations=True,
    )


async def _post(client, updates, *, batch, valid_key=True):
    if batch:
        body = {"updates": [{"key": key, "value": value} for key, value in updates.items()], "persist": False}
        path = "/api/config/batch"
    else:
        assert len(updates) == 1
        key, value = next(iter(updates.items()))
        body = {"key": key, "value": value, "persist": False}
        path = "/api/config"
    return await client.post(
        path, json=body,
        headers={"x-api-key": _API_KEY if valid_key else "synthetic-wrong-key"},
    )


async def _apply_in_control_transaction(rig):
    # _tick and manual application hold this same production lock.
    async with rig.opt._control_lock:
        return await rig.opt._apply(rig.state(), _grid_first_decision(rig))


async def _race(rig, updates, *, batch, valid_key=True):
    entered = asyncio.Event()
    release = asyncio.Event()
    auth_attempted = asyncio.Event()
    old = _identities(rig)
    authority_reads = 0
    suspended_entities = None
    activation_index = None
    activated_while_awaiting = False
    real_auth = api._require_mutation_auth

    def checked_auth(request):
        try:
            real_auth(request)
        finally:
            # The caller regains control after this request completes or reaches
            # its next await, including a future serialized config activation.
            auth_attempted.set()

    async def pause_pre_dispatch(_ha, entities):
        nonlocal authority_reads, suspended_entities
        if tuple(entities) != old[:2]:
            return
        authority_reads += 1
        if authority_reads == 2:
            suspended_entities = tuple(entities)
            entered.set()
            await release.wait()

    rig.ha.on_read = pause_pre_dispatch
    transport = httpx.ASGITransport(app=_app(rig), client=("198.51.100.14", 12345))
    tasks = []
    with (
        patch.object(api, "settings", _auth_settings()),
        patch.object(api, "_require_mutation_auth", checked_auth),
    ):
        async with httpx.AsyncClient(transport=transport, base_url="http://o14.invalid") as client:
            async def update():
                nonlocal activation_index
                response = await _post(client, updates, batch=batch, valid_key=valid_key)
                if response.status_code == 200:
                    activation_index = len(rig.ha.calls)
                return response

            operation = asyncio.create_task(_apply_in_control_transaction(rig))
            tasks.append(operation)
            try:
                await asyncio.wait_for(entered.wait(), timeout=3.0)
                assert suspended_entities == old[:2]
                assert rig.opt._control_lock.locked()
                request = asyncio.create_task(update())
                tasks.append(request)
                await asyncio.wait_for(auth_attempted.wait(), timeout=3.0)
                activated_while_awaiting = _identities(rig) != old
                release.set()
                outcome, response = await asyncio.wait_for(
                    asyncio.gather(operation, request), timeout=5.0,
                )
            finally:
                release.set()
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                rig.ha.on_read = None

    return SimpleNamespace(
        old=old, current=_identities(rig), response=response, outcome=outcome,
        activation_index=activation_index,
        activated_while_awaiting=activated_while_awaiting,
        suspended_entities=suspended_entities,
    )


_CASES = [
    pytest.param(False, {"sigenergy_mode_select": _NEW_SELECTOR}, "Manual", id="single-selector-manual"),
    pytest.param(True, {"sigenergy_mode_select": _NEW_SELECTOR}, "Force Full Export", id="batch-selector-force"),
    pytest.param(False, {"ha_control_switch": _NEW_SWITCH}, "Manual", id="single-remote-off"),
    pytest.param(True, {"ha_control_switch": _NEW_SWITCH}, "Manual", id="batch-remote-off"),
    pytest.param(True, {
        "sigenergy_mode_select": _NEW_SELECTOR,
        "ha_control_switch": _NEW_SWITCH,
        "ems_mode_select": _NEW_EMS,
    }, "Force Full Export", id="batch-owner-remote-ems"),
]


@pytest.mark.parametrize("batch,updates,new_owner", _CASES)
def test_activated_manual_or_off_identity_cannot_use_old_authority_for_ems(
    rig, batch, updates, new_owner,
):
    _seed_replacement(rig, owner=new_owner)
    result = asyncio.run(_race(rig, updates, batch=batch))
    assert result.response.status_code == 200, result.response.text
    for key, value in updates.items():
        assert getattr(rig.opt.cfg, key) == value
    assert result.activation_index is not None
    # A safe future transaction lock may activate after application completes;
    # identity revalidation may instead cancel application before dispatch.
    # Neither implementation may issue Grid First after the new owner/OFF gate
    # has become active. Inspect raw commands, including old and new EMS IDs.
    forbidden = [
        call for call in rig.ha.calls[result.activation_index:]
        if call[0] == "select_option" and call[2] == MODE_CMD_CHARGE_GRID
    ]
    assert not forbidden, (
        f"old authority authorized EMS after config activation: {forbidden}; "
        f"activated_during_await={result.activated_while_awaiting}; "
        f"old={result.old}; current={result.current}; "
        f"later_application_succeeded={result.outcome.succeeded}"
    )


@pytest.mark.parametrize("batch", [False, True], ids=["single", "batch"])
def test_unchanged_identity_still_allows_intended_grid_first(rig, batch):
    result = asyncio.run(_race(
        rig, {"sigenergy_mode_select": rig.opt.cfg.sigenergy_mode_select}, batch=batch,
    ))
    assert result.response.status_code == 200
    assert result.current == result.old
    assert result.outcome.succeeded
    assert ("select_option", result.old[2], MODE_CMD_CHARGE_GRID) in rig.ha.calls
    assert ("set_number", rig.opt.cfg.grid_import_limit, 4.0) in rig.ha.calls


@pytest.mark.parametrize("batch", [False, True], ids=["single", "batch"])
def test_bad_api_key_cannot_change_identity_during_authority_await(rig, batch):
    _seed_replacement(rig)
    result = asyncio.run(_race(
        rig, {"sigenergy_mode_select": _NEW_SELECTOR}, batch=batch, valid_key=False,
    ))
    assert result.response.status_code == 401
    assert result.current == result.old
    assert result.activation_index is None
    assert result.outcome.succeeded
    assert ("select_option", result.old[2], MODE_CMD_CHARGE_GRID) in rig.ha.calls


@pytest.mark.parametrize("owner", ["Manual", "Force Full Export"])
def test_identity_activated_before_transaction_blocks_stale_automated_state(rig, owner):
    _seed_replacement(rig, owner=owner)

    async def run():
        transport = httpx.ASGITransport(app=_app(rig), client=("198.51.100.14", 12345))
        with patch.object(api, "settings", _auth_settings()):
            async with httpx.AsyncClient(transport=transport, base_url="http://o14.invalid") as client:
                response = await _post(client, {"sigenergy_mode_select": _NEW_SELECTOR}, batch=False)
                assert response.status_code == 200
            return await _apply_in_control_transaction(rig)

    result = asyncio.run(run())
    assert not result.succeeded
    assert not [call for call in rig.ha.calls if call[0] in {"set_number", "select_option", "turn_on"}]


def test_fresh_replacement_automated_on_identity_can_apply_normally(rig):
    _seed_replacement(rig, owner=rig.opt.cfg.automated_option, remote="on")

    async def run():
        transport = httpx.ASGITransport(app=_app(rig), client=("198.51.100.14", 12345))
        with patch.object(api, "settings", _auth_settings()):
            async with httpx.AsyncClient(transport=transport, base_url="http://o14.invalid") as client:
                response = await _post(client, {
                    "sigenergy_mode_select": _NEW_SELECTOR,
                    "ha_control_switch": _NEW_SWITCH,
                    "ems_mode_select": _NEW_EMS,
                }, batch=True)
                assert response.status_code == 200
            return await _apply_in_control_transaction(rig)

    result = asyncio.run(run())
    assert result.succeeded
    assert ("select_option", _NEW_EMS, MODE_CMD_CHARGE_GRID) in rig.ha.calls
    assert ("set_number", rig.opt.cfg.grid_import_limit, 4.0) in rig.ha.calls
