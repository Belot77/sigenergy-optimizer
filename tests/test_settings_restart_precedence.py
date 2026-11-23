"""Offline tests for Home Assistant add-on ownership of configuration fields."""

import asyncio
import json

import httpx
import pytest
from dotenv.parser import parse_stream

from app.routers import api
from test_config_activation_authority_race import _API_KEY, _app, _auth_settings, rig
from test_settings_persistence import _run_startup_settings


MANAGED_ENV = "SIGENERGY_HAOS_MANAGED_SETTINGS"
MANAGED_FIELD = "grid_export_limit"
MANAGED_KEY = "GRID_EXPORT_LIMIT"
EDITABLE_FIELD = "grid_import_limit"
AUTH_HEADERS = {"x-api-key": _API_KEY}


def _config_client(rig, monkeypatch):
    settings = _auth_settings()
    settings.require_api_key_for_config_read = True
    monkeypatch.setattr(api, "settings", settings)
    transport = httpx.ASGITransport(app=_app(rig), client=("198.51.100.14", 12345))
    return httpx.AsyncClient(
        transport=transport, base_url="http://managed-settings.invalid", headers=AUTH_HEADERS,
    )


def test_bootstrap_exports_names_only_and_removing_override_allows_dashboard_save(
    rig, tmp_path, monkeypatch, capsys,
):
    target = tmp_path / ".env"
    template = tmp_path / ".env.example"
    options = tmp_path / "options.json"
    template.write_text("GRID_EXPORT_LIMIT=number.seed_limit\n", encoding="utf-8")
    options.write_text(json.dumps({
        "ha_token": "synthetic-standard-option-value",
        "extra_env": (
            "# IGNORED_COMMENT=synthetic-comment\n"
            "grid_export_limit = number.override_limit\n"
            "GRID_EXPORT_LIMIT=number.latest_override\n"
            "UNRECOGNIZED_OPTION=synthetic-unknown-value\n"
            "INVALID-OPTION=synthetic-invalid-value\n"
            "WITHOUT_EQUALS\n"
        ),
    }), encoding="utf-8")
    _run_startup_settings(target, template, options)
    first_boot_keys = capsys.readouterr().out.strip()
    assert first_boot_keys == "GRID_EXPORT_LIMIT,UNRECOGNIZED_OPTION"
    assert "GRID_EXPORT_LIMIT=number.latest_override\n" in target.read_text(encoding="utf-8")

    monkeypatch.setenv(MANAGED_ENV, first_boot_keys)
    monkeypatch.chdir(tmp_path)

    async def run():
        async with _config_client(rig, monkeypatch) as client:
            before_restart = await client.get("/api/config")
            assert before_restart.status_code == 200
            assert before_restart.json()["_haos_managed_fields"] == [MANAGED_FIELD]

        options.write_text(json.dumps({"extra_env": ""}), encoding="utf-8")
        _run_startup_settings(target, template, options)
        next_boot_keys = capsys.readouterr().out.strip()
        assert next_boot_keys == ""
        monkeypatch.setenv(MANAGED_ENV, next_boot_keys)

        saved_value = "number.dashboard_limit"
        async with _config_client(rig, monkeypatch) as restarted_client:
            after_restart = await restarted_client.get("/api/config")
            assert after_restart.status_code == 200
            assert after_restart.json()["_haos_managed_fields"] == []
            response = await restarted_client.post("/api/config", json={
                "key": MANAGED_FIELD, "value": saved_value, "persist": True,
            })
        assert response.status_code == 200, response.text
        assert getattr(rig.opt.cfg, MANAGED_FIELD) == saved_value
        assert f"{MANAGED_KEY}={saved_value}\n" in target.read_text(encoding="utf-8")

    asyncio.run(run())


def test_restart_replaces_alternate_managed_key_spellings_without_rewriting_multiline_value(
    tmp_path, capsys,
):
    target = tmp_path / ".env"
    options = tmp_path / "options.json"
    other_binding = "OTHER='first\nexport_limit_low=15\nlast'\n"
    target.write_text(
        other_binding + "export export_limit_low=12\n'ExPoRt_LiMiT_LoW'=13\n",
        encoding="utf-8",
    )
    options.write_text(json.dumps({"extra_env": "EXPORT_LIMIT_LOW=8"}), encoding="utf-8")

    _run_startup_settings(target, tmp_path / ".env.example", options)

    assert capsys.readouterr().out.strip() == "EXPORT_LIMIT_LOW"
    with target.open(encoding="utf-8") as env_file:
        bindings = list(parse_stream(env_file))
    managed_values = [
        binding.value for binding in bindings
        if binding.key and binding.key.upper() == "EXPORT_LIMIT_LOW"
    ]
    assert managed_values and all(value == "8" for value in managed_values)
    other_bindings = [binding for binding in bindings if binding.key == "OTHER"]
    assert [binding.original.string for binding in other_bindings] == [other_binding]


@pytest.mark.parametrize("persist", [False, True], ids=["transient", "persisted"])
@pytest.mark.parametrize("batch", [False, True], ids=["single", "mixed-batch"])
def test_managed_config_update_never_writes_or_activates(
    rig, tmp_path, monkeypatch, persist, batch,
):
    monkeypatch.setenv(MANAGED_ENV, MANAGED_KEY)
    monkeypatch.chdir(tmp_path)
    old_managed_value = getattr(rig.opt.cfg, MANAGED_FIELD)
    old_editable_value = getattr(rig.opt.cfg, EDITABLE_FIELD)
    proof = {old_managed_value: (0.01, 123.0, True)}
    rig.opt._number_settlement_requests = proof.copy()
    target = tmp_path / ".env"
    original = f"{MANAGED_KEY}={old_managed_value}\n"
    target.write_text(original, encoding="utf-8")
    managed_update = {"key": MANAGED_FIELD, "value": "number.changed_export"}

    if batch:
        path = "/api/config/batch"
        body = {"updates": [
            {"key": EDITABLE_FIELD, "value": "number.changed_import"},
            managed_update,
        ], "persist": persist}
    else:
        path = "/api/config"
        body = {**managed_update, "persist": persist}

    async def run():
        async with _config_client(rig, monkeypatch) as client:
            return await client.post(path, json=body)

    response = asyncio.run(run())
    assert response.status_code == 422, response.text
    errors = response.json()["detail"]["field_errors"]
    assert [error["key"] for error in errors] == [MANAGED_FIELD]
    assert "extra_env" in errors[0]["error"]
    assert "restart" in errors[0]["error"].lower()
    assert target.read_text(encoding="utf-8") == original
    assert list(tmp_path.iterdir()) == [target]
    assert getattr(rig.opt.cfg, MANAGED_FIELD) == old_managed_value
    assert getattr(rig.opt.cfg, EDITABLE_FIELD) == old_editable_value
    assert rig.opt._number_settlement_requests == proof
    assert not rig.opt._control_lock.locked()
