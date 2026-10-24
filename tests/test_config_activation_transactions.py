"""O14 transaction, identity-evidence and independent ownership regressions."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest

from app.optimizer import MODE_MAX_SELF, _MscTransition
from app.routers import api
from test_config_activation_authority_race import _app, _auth_settings, _post, rig


def test_config_activation_cannot_split_authenticated_ess_target_bindings(rig):
    async def run():
        entered = asyncio.Event()
        release = asyncio.Event()
        config_requested = asyncio.Event()
        original_auth = api._require_mutation_auth
        old_export = rig.opt.cfg.grid_export_limit
        new_export = "number.o14_new_export"
        old_ems = rig.opt.cfg.ems_mode_select

        def checked_auth(request):
            original_auth(request)
            if request.url.path == "/api/config":
                config_requested.set()

        async def pause_first_ems(_ha, method, entity, value):
            if method == "select_option" and entity == old_ems:
                entered.set()
                await release.wait()

        rig.ha.on_write = pause_first_ems
        transport = httpx.ASGITransport(app=_app(rig), client=("198.51.100.14", 12345))
        tasks = []
        with (
            patch.object(api, "settings", _auth_settings()),
            patch.object(api, "_require_mutation_auth", checked_auth),
        ):
            async with httpx.AsyncClient(transport=transport, base_url="http://o14.invalid") as client:
                operation = asyncio.create_task(client.post(
                    "/api/set_ess",
                    headers={"x-api-key": "synthetic-o14-key-for-offline-tests"},
                    json={"ems_mode": MODE_MAX_SELF, "grid_export_limit": 4.0,
                          "grid_import_limit": 0.0, "pv_max_power_limit": 25.0},
                ))
                tasks.append(operation)
                try:
                    await asyncio.wait_for(entered.wait(), timeout=3.0)
                    update = asyncio.create_task(_post(client, {"grid_export_limit": new_export}, batch=False))
                    tasks.append(update)
                    await asyncio.wait_for(config_requested.wait(), timeout=3.0)
                    release.set()
                    response, config_response = await asyncio.wait_for(
                        asyncio.gather(operation, update), timeout=5.0,
                    )
                finally:
                    release.set()
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
                    rig.ha.on_write = None
        assert response.status_code == config_response.status_code == 200
        assert rig.opt.cfg.grid_export_limit == new_export
        assert not [call for call in rig.ha.calls if call[0] == "set_number" and call[1] == new_export], rig.ha.calls
        assert ("set_number", old_export, 4.0) in rig.ha.calls

    asyncio.run(run())


@pytest.fixture(autouse=True)
def mutation_auth_settings():
    with patch.object(api, "settings", _auth_settings()):
        yield


async def _change(rig, updates, *, batch=False, persist=False):
    transport = httpx.ASGITransport(app=_app(rig), client=("198.51.100.14", 12345))
    async with httpx.AsyncClient(transport=transport, base_url="http://o14.invalid") as client:
        if persist:
            key, value = next(iter(updates.items()))
            return await client.post(
                "/api/config/batch" if batch else "/api/config",
                headers={"x-api-key": "synthetic-o14-key-for-offline-tests"},
                json=({"updates": [{"key": key, "value": value}], "persist": True}
                      if batch else {"key": key, "value": value, "persist": True}),
            )
        return await _post(client, updates, batch=batch)

@pytest.mark.parametrize("batch", [False, True], ids=["single", "batch"])
def test_waiting_config_cancellation_does_not_activate_or_persist(rig, batch):
    async def run():
        attempted = asyncio.Event()
        original_auth = api._require_mutation_auth
        old = rig.opt.cfg.grid_export_limit
        proof = {old: (0.01, 123.0, True)}
        rig.opt._number_settlement_requests = proof.copy()

        def checked_auth(request):
            original_auth(request)
            attempted.set()

        with (patch.object(api, "_require_mutation_auth", checked_auth),
              patch.object(api, "_persist_config_keys_to_env") as persist):
            async with rig.opt._control_lock:
                task = asyncio.create_task(_change(
                    rig, {"grid_export_limit": "number.o14_cancelled"}, batch=batch, persist=True,
                ))
                try:
                    await asyncio.wait_for(attempted.wait(), timeout=3.0)
                    assert rig.opt.cfg.grid_export_limit == old
                    persist.assert_not_called()
                    task.cancel()
                    with pytest.raises(asyncio.CancelledError):
                        await task
                finally:
                    if not task.done():
                        task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
            assert not rig.opt._control_lock.locked()
            assert rig.opt.cfg.grid_export_limit == old
            assert rig.opt._number_settlement_requests == proof
            persist.assert_not_called()
            # A cancelled waiter must not poison subsequent activation.
            response = await _change(rig, {"grid_export_limit": "number.o14_after_cancel"}, batch=batch)
            assert response.status_code == 200

    asyncio.run(run())


@pytest.mark.parametrize("batch", [False, True], ids=["single", "batch"])
def test_failed_persistence_leaves_active_configuration_and_proof_unchanged(rig, batch):
    old = rig.opt.cfg.grid_export_limit
    proof = {old: (0.01, 123.0, True)}
    rig.opt._number_settlement_requests = proof.copy()
    with patch.object(api, "_persist_config_keys_to_env", side_effect=OSError("synthetic write failure")):
        response = asyncio.run(_change(
            rig, {"grid_export_limit": "number.o14_unpersisted"}, batch=batch, persist=True,
        ))
    assert response.status_code == 500
    assert rig.opt.cfg.grid_export_limit == old
    assert rig.opt._number_settlement_requests == proof
    assert not rig.opt._control_lock.locked()


def test_queued_config_validation_uses_preceding_activated_values(rig):
    rig.opt.cfg.solar_surplus_min_pv_margin = 0.5
    rig.opt.cfg.solar_surplus_stop_pv_margin = 0.2

    async def run():
        original_auth = api._require_mutation_auth
        attempts = asyncio.Queue()

        def checked_auth(request):
            original_auth(request)
            attempts.put_nowait(True)

        with patch.object(api, "_require_mutation_auth", checked_auth):
            async with rig.opt._control_lock:
                first = asyncio.create_task(_change(rig, {"solar_surplus_stop_pv_margin": 0.4}))
                await asyncio.wait_for(attempts.get(), timeout=3.0)
                second = asyncio.create_task(_change(rig, {"solar_surplus_min_pv_margin": 0.3}, batch=True))
                await asyncio.wait_for(attempts.get(), timeout=3.0)
                assert rig.opt.cfg.solar_surplus_stop_pv_margin == 0.2
            try:
                responses = await asyncio.wait_for(asyncio.gather(first, second), timeout=5.0)
            finally:
                for task in (first, second):
                    if not task.done():
                        task.cancel()
                await asyncio.gather(first, second, return_exceptions=True)
        assert [response.status_code for response in responses] == [200, 422]
        assert rig.opt.cfg.solar_surplus_min_pv_margin == 0.5
        assert rig.opt.cfg.solar_surplus_stop_pv_margin == 0.4

    asyncio.run(run())


def test_identity_activation_retires_old_proof_but_preserves_operator_and_pending_safety(rig):
    opt = rig.opt
    old_export = opt.cfg.grid_export_limit
    watches = opt.get_watch_entities()
    old_transition = _MscTransition(
        phase="msc", close_requested_at=1.0, close_request_state=rig.state(),
        msc_requested_at=2.0, msc_request_state=rig.state(),
    )
    opt._msc_transition = old_transition
    opt._msc_baseline_established = True
    opt._number_settlement_requests[old_export] = (0.01, 1.0, True)
    opt._last_state = rig.state()
    opt._last_decision = SimpleNamespace(standby_holdoff_active=True)
    opt._holdoff_entry_floor = 43.0
    opt._manual_mode_override = opt.cfg.full_export_option
    opt._manual_mode_requested_at = 1.5
    opt._manual_ess_charge_override_kw = 3.0
    opt._manual_ess_discharge_override_kw = 4.0
    opt._last_hw_charge_cap_kw = 9.0
    opt._last_legacy_manual_charge_cap_kw = 8.0
    old_boost_generation = opt._evening_boost_reentry.generation
    opt._solar_dip_proof = object()
    opt._solar_dip_recheck_at = 100.0

    response = asyncio.run(_change(rig, {"grid_export_limit": "number.o14_new_export"}))
    assert response.status_code == 200
    assert not opt._number_settlement_requests
    assert not opt._msc_baseline_established
    assert opt._msc_transition is not None and opt._msc_transition is not old_transition
    assert opt._msc_transition.phase == "close"
    assert opt._msc_transition.close_requested_at is None
    assert opt._msc_transition.msc_requested_at is None
    assert opt._last_state is opt._last_decision is None
    assert opt._solar_dip_proof is opt._solar_dip_recheck_at is None
    assert opt._evening_boost_reentry.generation > old_boost_generation
    assert opt._manual_mode_override == opt.cfg.full_export_option
    assert opt._manual_mode_requested_at == 1.5
    assert (opt._manual_ess_charge_override_kw, opt._manual_ess_discharge_override_kw) == (3.0, 4.0)
    assert opt._holdoff_entry_floor == 43.0
    assert opt._configuration_holdoff_continuity
    assert opt._last_hw_charge_cap_kw == 9.0
    assert opt._last_legacy_manual_charge_cap_kw == 8.0
    assert opt.get_watch_entities() is watches
    assert "number.o14_new_export" in watches and old_export not in watches


@pytest.mark.parametrize("updates", [None, {"solar_surplus_min_pv_margin": 0.6}], ids=["no-op", "policy-only"])
def test_unchanged_evidence_identity_keeps_existing_proof(rig, updates):
    opt = rig.opt
    proof = {opt.cfg.grid_export_limit: (0.01, 123.0, True)}
    opt._number_settlement_requests = proof.copy()
    old_state = opt._last_state = rig.state()
    generation = opt._evening_boost_reentry.generation
    response = asyncio.run(_change(rig, updates or {"grid_export_limit": opt.cfg.grid_export_limit}))
    assert response.status_code == 200
    assert opt._number_settlement_requests == proof
    assert opt._last_state is old_state
    assert opt._evening_boost_reentry.generation == generation


def test_changed_cap_identity_cannot_reuse_previous_sensor_capacity(rig):
    opt = rig.opt
    opt._last_hw_charge_cap_kw = 9.0
    opt._last_legacy_manual_charge_cap_kw = 8.0
    opt._last_hw_discharge_cap_kw = 7.0
    response = asyncio.run(_change(rig, {"ess_rated_charge_power_sensor": "sensor.o14_new_charge_cap"}))
    assert response.status_code == 200
    assert opt._last_hw_charge_cap_kw is opt._last_legacy_manual_charge_cap_kw is None
    assert opt._last_hw_discharge_cap_kw == 7.0


def test_new_selector_history_cannot_cancel_pending_force_but_later_selection_can(rig):
    opt = rig.opt
    now = datetime.now(timezone.utc)
    request_at = (now - timedelta(seconds=20)).timestamp()
    opt._manual_mode_override = opt.cfg.full_export_option
    opt._manual_mode_requested_at = request_at
    opt._manual_ess_discharge_override_kw = 4.0
    response = asyncio.run(_change(rig, {"sigenergy_mode_select": "input_select.o14_rebound_owner"}))
    assert response.status_code == 200
    activation = opt._control_identity_activated_at
    assert activation > request_at

    def report(changed_at, reported_at):
        row = {
            "entity_id": opt.cfg.sigenergy_mode_select, "state": opt.cfg.automated_option,
            "attributes": {}, "last_changed": changed_at.isoformat(),
            "last_updated": changed_at.isoformat(), "last_reported": reported_at.isoformat(),
        }
        rig.ha.reports[opt.cfg.sigenergy_mode_select] = row.copy()
        rig.ha.metadata[opt.cfg.sigenergy_mode_select] = row.copy()

    # Fresh reports of a selector's historical value do not prove a new choice.
    report(now - timedelta(seconds=10), datetime.now(timezone.utc))
    asyncio.run(opt._read_control_authority())
    assert opt._manual_mode_override == opt.cfg.full_export_option
    assert opt._manual_mode_requested_at == request_at
    assert opt._manual_ess_discharge_override_kw == 4.0
    # A verified operator selection after activation may supersede that request.
    changed = datetime.now(timezone.utc)
    assert changed.timestamp() > activation
    report(changed, changed)
    asyncio.run(opt._read_control_authority())
    assert opt._manual_mode_override is None
    assert opt._manual_mode_requested_at is None
    assert opt._manual_ess_discharge_override_kw is None


@pytest.mark.parametrize("change", ["rename", "swap"], ids=["renamed-label", "swapped-label-meaning"])
def test_queued_manual_mode_rejects_changed_configuration_interpretation(rig, change):
    async def run():
        cfg = rig.opt.cfg
        requested_mode = cfg.full_export_option
        updates = ({"full_export_option": "Force New Export"} if change == "rename" else {
            "full_export_option": cfg.full_import_option,
            "full_import_option": cfg.full_export_option,
        })
        transport = httpx.ASGITransport(app=_app(rig), client=("198.51.100.14", 12345))
        attempts = asyncio.Queue()
        original_auth = api._require_mutation_auth

        def checked_auth(request):
            original_auth(request)
            attempts.put_nowait(request.url.path)

        tasks = []
        with patch.object(api, "_require_mutation_auth", checked_auth):
            async with httpx.AsyncClient(transport=transport, base_url="http://o14.invalid") as client:
                try:
                    async with rig.opt._control_lock:
                        config = asyncio.create_task(_post(client, updates, batch=True))
                        tasks.append(config)
                        assert await asyncio.wait_for(attempts.get(), timeout=3.0) == "/api/config/batch"
                        manual = asyncio.create_task(client.post(
                            "/api/set_mode", json={"mode": requested_mode},
                            headers={"x-api-key": "synthetic-o14-key-for-offline-tests"},
                        ))
                        tasks.append(manual)
                        assert await asyncio.wait_for(attempts.get(), timeout=3.0) == "/api/set_mode"
                    config_response, manual_response = await asyncio.wait_for(
                        asyncio.gather(config, manual), timeout=5.0,
                    )
                finally:
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
        assert config_response.status_code == 200
        assert manual_response.status_code == 500
        assert not rig.ha.calls, rig.ha.calls
        assert rig.opt._manual_mode_override is None

    asyncio.run(run())


@pytest.mark.parametrize("path", ["/api/config", "/api/config/batch", "/api/set_ess"])
def test_queued_mutation_rechecks_revoked_key_before_activation_or_write(rig, path):
    async def run():
        attempted = asyncio.Event()
        original_auth = api._require_mutation_auth
        transport = httpx.ASGITransport(app=_app(rig), client=("198.51.100.14", 12345))
        old_export = rig.opt.cfg.grid_export_limit
        item = {"key": "grid_export_limit", "value": "number.o14_revoked"}
        bodies = {
            "/api/config": {**item, "persist": False},
            "/api/config/batch": {"updates": [item], "persist": False},
            "/api/set_ess": {"ems_mode": MODE_MAX_SELF, "grid_export_limit": 4.0,
                             "grid_import_limit": 0.0, "pv_max_power_limit": 25.0},
        }

        def checked_auth(request):
            original_auth(request)
            attempted.set()

        with patch.object(api, "_require_mutation_auth", checked_auth):
            async with httpx.AsyncClient(transport=transport, base_url="http://o14.invalid") as client:
                async with rig.opt._control_lock:
                    task = asyncio.create_task(client.post(
                        path, json=bodies[path],
                        headers={"x-api-key": "synthetic-o14-key-for-offline-tests"},
                    ))
                    await asyncio.wait_for(attempted.wait(), timeout=3.0)
                    api.settings.ui_api_key = "synthetic-replacement-key"
                try:
                    response = await asyncio.wait_for(task, timeout=3.0)
                finally:
                    if not task.done():
                        task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
        assert response.status_code == 401
        assert rig.opt.cfg.grid_export_limit == old_export
        assert not rig.ha.calls

    asyncio.run(run())
