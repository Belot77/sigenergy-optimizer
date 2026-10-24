"""Offline source-peer trust checks; no HA clients, persistence or control writes."""
from __future__ import annotations

import asyncio
import json
import shlex
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
import uvicorn
from fastapi import FastAPI, WebSocketDisconnect

from app.routers import api


KEY = "synthetic-ingress-test-key"
PATH = {"x-ingress-path": "/api/hassio_ingress/synthetic/"}
ROOT = Path(__file__).resolve().parents[1]


class _Optimizer:
    def __init__(self):
        self.calls = 0
        self.audit = []
        self.cfg = SimpleNamespace(automated_option="Automated", dict=lambda: {"synthetic": True})
        self.last_state = None
        self.last_decision = None
        self.ws_connected = False

    async def run_once(self):
        self.calls += 1
        return SimpleNamespace(ems_mode="synthetic", export_limit=0, import_limit=0,
                               outcome_reason="offline only")

    def record_audit_event(self, **event):
        self.audit.append(event)


@pytest.fixture
def harness(monkeypatch):
    settings = SimpleNamespace(ui_api_key=KEY, allow_loopback_without_api_key=True,
                               require_api_key_for_all_mutations=False,
                               require_api_key_for_config_read=True)
    monkeypatch.setattr(api, "settings", settings)
    app = FastAPI()
    app.state.optimizer = _Optimizer()
    app.include_router(api.router, prefix="/api")
    return app, settings


def _request(app, host, headers, *, path="/api/run_cycle", method="POST"):
    async def run():
        peer = None if host is None else (host, 1234)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=peer),
                                    base_url="http://offline.test") as client:
            return await client.request(method, path, headers=headers)
    return asyncio.run(run())


CASES = [
    ("public-plain", "203.0.113.8", {}, True, False, KEY, 401),
    ("public-path", "203.0.113.8", PATH, True, False, KEY, 401),
    ("public-hassio", "203.0.113.8", {"x-hassio": "yes"}, True, False, KEY, 401),
    ("public-home-assistant-wrong-key", "203.0.113.8", {"x-home-assistant": "yes", "x-api-key": "wrong"}, True, False, KEY, 401),
    ("public-path-wrong-key", "203.0.113.8", {**PATH, "x-api-key": "wrong"}, True, False, KEY, 401),
    ("public-path-unconfigured-key", "203.0.113.8", PATH, True, False, "", 403),
    ("public-forwarded-ha-ip", "203.0.113.8", {**PATH, "x-forwarded-for": "172.30.32.2"}, True, False, KEY, 401),
    ("public-real-ha-ip", "203.0.113.8", {**PATH, "x-real-ip": "172.30.32.2"}, True, False, KEY, 401),
    ("ha-path", "172.30.32.2", PATH, True, False, "", 200),
    ("ha-forwarded-path", "172.30.32.2", {**PATH, "x-forwarded-for": "203.0.113.8"}, True, False, "", 200),
    ("ha-without-path", "172.30.32.2", {}, True, False, KEY, 401),
    ("ha-hassio-only", "172.30.32.2", {"x-hassio": "yes"}, True, False, KEY, 401),
    ("ha-home-assistant-only", "172.30.32.2", {"x-home-assistant": "yes"}, True, False, KEY, 401),
    ("ha-empty-path", "172.30.32.2", {"x-ingress-path": ""}, True, False, KEY, 401),
    ("ha-strict", "172.30.32.2", PATH, True, True, KEY, 401),
    ("ha-bypass-disabled", "172.30.32.2", PATH, False, False, KEY, 401),
    ("public-valid-key-strict", "203.0.113.8", {"x-api-key": KEY}, False, True, KEY, 200),
    ("loopback-plain", "127.0.0.1", {}, True, False, KEY, 200),
    ("loopback-forwarded", "127.0.0.1", {"x-forwarded-for": "203.0.113.8"}, True, False, KEY, 401),
    ("loopback-forwarded-path", "127.0.0.1", {**PATH, "x-forwarded-for": "203.0.113.8"}, True, False, KEY, 401),
    ("mapped-ha-dotted", "::ffff:172.30.32.2", PATH, True, False, "", 200),
    ("mapped-ha-hex", "::ffff:ac1e:2002", PATH, True, False, "", 200),
    ("mapped-public", "::ffff:203.0.113.8", PATH, True, False, KEY, 401),
    ("other-ipv6", "2001:db8::1", PATH, True, False, KEY, 401),
    ("malformed-host", "malformed-host", PATH, True, False, KEY, 401),
    ("absent-peer", None, PATH, True, False, KEY, 401),
]


@pytest.mark.parametrize("name,host,headers,allow,strict,key,status", CASES, ids=[c[0] for c in CASES])
def test_mutations_require_trusted_peer_or_valid_key(harness, name, host, headers, allow, strict, key, status):
    app, settings = harness
    settings.allow_loopback_without_api_key = allow
    settings.require_api_key_for_all_mutations = strict
    settings.ui_api_key = key
    response = _request(app, host, headers)
    assert response.status_code == status
    assert app.state.optimizer.calls == (1 if status == 200 else 0)
    assert len(app.state.optimizer.audit) == (1 if status == 200 else 0)


@pytest.mark.parametrize("host,headers,protected,status", [
    ("203.0.113.8", PATH, True, 401),
    ("203.0.113.8", {"x-hassio": "yes"}, True, 401),
    ("203.0.113.8", {"x-home-assistant": "yes"}, True, 401),
    ("203.0.113.8", {**PATH, "x-forwarded-for": "172.30.32.2"}, True, 401),
    ("172.30.32.2", PATH, True, 200),
    ("::ffff:172.30.32.2", PATH, True, 200),
    ("203.0.113.8", {"x-api-key": KEY}, True, 200),
    ("203.0.113.8", {}, False, 200),
])
def test_guarded_config_reads_share_trust_without_changing_optional_policy(harness, host, headers, protected, status):
    app, settings = harness
    settings.require_api_key_for_config_read = protected
    response = _request(app, host, headers, path="/api/config", method="GET")
    assert response.status_code == status
    assert app.state.optimizer.calls == 0


@pytest.mark.parametrize("host", ["", None, 123, "172.30.32.20", "172.30.32.2 ",
                                  "[172.30.32.2]", "::ffff:172.30.32.20"])
def test_malformed_or_different_peer_never_claims_ingress(host):
    request = SimpleNamespace(client=SimpleNamespace(host=host), headers=PATH)
    assert api._is_ha_ingress_request(request) is False


@pytest.mark.parametrize("host,headers,actor,source", [
    ("203.0.113.8", {**PATH, "x-api-key": KEY}, "remote:203.0.113.8", "api_client"),
    ("172.30.32.2", PATH, "ha_ingress_ui", "ui_manual"),
])
def test_audit_attribution_uses_same_ingress_boundary(harness, host, headers, actor, source):
    app, _ = harness
    assert _request(app, host, headers).status_code == 200
    event = app.state.optimizer.audit[-1]
    assert event["actor"] == actor
    assert event["source"] == source


def _launch_args(launcher):
    text = (ROOT / launcher).read_text(encoding="utf-8")
    if launcher == "Dockerfile":
        return json.loads(next(line[4:] for line in text.splitlines() if line.startswith('CMD ["uvicorn"')))
    return shlex.split(next(line[5:] for line in text.splitlines() if line.startswith("exec uvicorn ")))


@pytest.mark.parametrize("launcher", ["Dockerfile", "sigenergy_optimizer_addon/run.sh"])
@pytest.mark.parametrize("host,forwarded,status", [
    ("203.0.113.8", "172.30.32.2", 401),
    ("172.30.32.2", "203.0.113.8", 200),
])
def test_supported_launchers_preserve_transport_peer_even_with_wildcard_proxy_environment(harness, launcher, host, forwarded, status):
    app, _ = harness
    args = _launch_args(launcher)
    # Exercise the actual server middleware selection implied by each CLI,
    # including a hostile/overbroad FORWARDED_ALLOW_IPS equivalent.
    config = uvicorn.Config(app, proxy_headers="--no-proxy-headers" not in args,
                            forwarded_allow_ips="*", lifespan="off", log_config=None)
    config.load()
    response = _request(config.loaded_app, host, {**PATH, "x-forwarded-for": forwarded})
    assert response.status_code == status
    assert app.state.optimizer.calls == (1 if status == 200 else 0)


def test_status_websocket_remains_read_only_and_keeps_existing_public_policy(harness):
    app, settings = harness
    settings.require_api_key_for_all_mutations = True
    messages = []

    async def receive():
        return {"type": "websocket.connect"}

    async def send(message):
        messages.append(message)
        if message["type"] == "websocket.send":
            raise WebSocketDisconnect()

    scope = {"type": "websocket", "asgi": {"version": "3.0"}, "scheme": "ws",
             "path": "/api/ws", "raw_path": b"/api/ws", "query_string": b"",
             "headers": [], "client": ("203.0.113.8", 1234), "server": ("offline.test", 80),
             "subprotocols": []}
    asyncio.run(app(scope, receive, send))
    assert messages[0]["type"] == "websocket.accept"
    assert messages[1]["type"] == "websocket.send"
    assert json.loads(messages[1]["text"])["ws_connected"] is False
    assert app.state.optimizer.calls == 0
