"""
Home Assistant WebSocket client.

Implements the HA WebSocket API:
  wss://homeassistant.local/api/websocket

Protocol:
  1. HA sends  {"type": "auth_required"}
  2. Client sends {"type": "auth", "access_token": "..."}
  3. HA sends  {"type": "auth_ok"}  (or auth_invalid)
  4. Client subscribes to state_changed events
  5. HA sends event messages whenever any entity state changes

This module is entirely independent of the REST client. It runs as its own
asyncio task and delivers entity_id strings to a shared asyncio.Queue that
the optimizer watches. On disconnect it reconnects with exponential backoff.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Callable, Optional

import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

logger = logging.getLogger(__name__)

# Reconnection backoff: starts at 2s, caps at 60s
_BACKOFF_INIT = 2.0
_BACKOFF_MAX = 60.0
_BACKOFF_FACTOR = 1.5


class HAWebSocketClient:
    """
    Subscribes to HA state_changed events via WebSocket and puts the changed
    entity_id into `trigger_queue` so the optimizer can react immediately.

    Also calls `on_connect` / `on_disconnect` callbacks to let the UI show
    connection state.
    """

    def __init__(
        self,
        ha_url: str,
        token: str,
        trigger_queue: asyncio.Queue,
        watch_entities: set[str],
        on_connect: Optional[Callable] = None,
        on_disconnect: Optional[Callable] = None,
    ) -> None:
        # Convert http(s):// → ws(s)://
        self._ws_url = ha_url.rstrip("/").replace("https://", "wss://").replace("http://", "ws://") + "/api/websocket"
        self._token = token
        self._queue = trigger_queue
        self._watch = watch_entities
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect
        self._msg_id = 0
        self._connected = False
        self._running = False

    @property
    def connected(self) -> bool:
        return self._connected

    def _next_id(self) -> int:
        self._msg_id += 1
        return self._msg_id

    async def run_forever(self) -> None:
        """Connect, subscribe, and reconnect on any failure."""
        self._running = True
        backoff = _BACKOFF_INIT
        while self._running:
            try:
                await self._connect_and_listen()
                backoff = _BACKOFF_INIT  # reset on clean exit
            except asyncio.CancelledError:
                logger.info("WebSocket client cancelled")
                raise
            except Exception as exc:
                logger.warning("WebSocket error: %s — reconnecting in %.0fs", exc, backoff)
            finally:
                self._connected = False
                if self._on_disconnect:
                    self._on_disconnect()
            await asyncio.sleep(backoff)
            backoff = min(backoff * _BACKOFF_FACTOR, _BACKOFF_MAX)

    async def _connect_and_listen(self) -> None:
        logger.info("Connecting to HA WebSocket: %s", self._ws_url)
        async with websockets.connect(
            self._ws_url,
            ping_interval=30,
            ping_timeout=10,
            close_timeout=5,
            max_size=10 * 1024 * 1024,  # 10 MB — large attribute payloads
        ) as ws:
            # ---- Authenticate ----------------------------------------
            await self._authenticate(ws)
            self._connected = True
            if self._on_connect:
                self._on_connect()
            logger.info("WebSocket authenticated — subscribing to state_changed events")

            # ---- Subscribe to state_changed events -------------------
            sub_id = self._next_id()
            await ws.send(json.dumps({
                "id": sub_id,
                "type": "subscribe_events",
                "event_type": "state_changed",
            }))
            sub_result = json.loads(await ws.recv())
            if sub_result.get("success") is False:
                raise RuntimeError(f"Subscribe failed: {sub_result}")
            logger.info("Subscribed to state_changed (sub_id=%d)", sub_id)

            # ---- Also subscribe to time_changed for minute ticks -----
            time_id = self._next_id()
            await ws.send(json.dumps({
                "id": time_id,
                "type": "subscribe_events",
                "event_type": "time_changed",
            }))
            await ws.recv()  # consume result

            # ---- Event loop ------------------------------------------
            async for raw in ws:
                if not self._running:
                    break
                await self._handle_message(json.loads(raw))

    async def _authenticate(self, ws) -> None:
        # Receive auth_required
        msg = json.loads(await ws.recv())
        if msg.get("type") != "auth_required":
            raise RuntimeError(f"Expected auth_required, got: {msg.get('type')}")

        # Send token
        await ws.send(json.dumps({"type": "auth", "access_token": self._token}))

        # Receive auth result
        result = json.loads(await ws.recv())
        if result.get("type") == "auth_invalid":
            raise RuntimeError("HA WebSocket authentication failed — check HA_TOKEN")
        if result.get("type") != "auth_ok":
            raise RuntimeError(f"Unexpected auth response: {result}")

    async def _handle_message(self, msg: dict) -> None:
        if msg.get("type") != "event":
            return

        event = msg.get("event", {})
        event_type = event.get("event_type")

        # ---- state_changed: check if it's one of our watched entities --
        if event_type == "state_changed":
            data = event.get("data", {})
            entity_id = data.get("entity_id", "")
            if entity_id in self._watch:
                new_state = data.get("new_state") or {}
                old_state = data.get("old_state") or {}
                new_val = new_state.get("state", "")
                old_val = old_state.get("state", "")
                if new_val != old_val:
                    logger.debug("WS trigger: %s  %s → %s", entity_id, old_val[:20], new_val[:20])
                    # Non-blocking put; if queue is full just skip (optimizer will catch it on heartbeat)
                    try:
                        self._queue.put_nowait(entity_id)
                    except asyncio.QueueFull:
                        pass

        # ---- time_changed: fire a heartbeat every minute ---------------
        elif event_type == "time_changed":
            try:
                self._queue.put_nowait("__time_changed__")
            except asyncio.QueueFull:
                pass

    def stop(self) -> None:
        self._running = False
