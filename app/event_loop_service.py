"""
Event loop service — async background loop helpers for SigEnergyOptimizer.

Extracted from optimizer.py to keep the orchestration concern separate.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .optimizer import SigEnergyOptimizer

logger = logging.getLogger(__name__)

# Maximum time between full cycles even when WebSocket is quiet (safety net)
_HEARTBEAT_INTERVAL = 60  # seconds

# Minimum gap between back-to-back rapid triggers (debounce)
_DEBOUNCE_SECONDS = 3.0


async def drain_queue(optimizer: "SigEnergyOptimizer", window: float) -> None:
    """Consume all queued items within `window` seconds to collapse a burst into one tick."""
    deadline = asyncio.get_event_loop().time() + window
    while True:
        remaining = deadline - asyncio.get_event_loop().time()
        if remaining <= 0:
            break
        try:
            await asyncio.wait_for(optimizer.trigger_queue.get(), timeout=remaining)
            optimizer.trigger_queue.task_done()
        except asyncio.TimeoutError:
            break


async def safe_tick(optimizer: "SigEnergyOptimizer") -> None:
    """Run one optimizer tick, recording cycle timestamps and swallowing non-cancel errors."""
    optimizer._last_cycle_started = datetime.now(timezone.utc)
    try:
        await optimizer._tick()
        optimizer._last_cycle_error = ""
        optimizer._last_cycle_completed = datetime.now(timezone.utc)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        optimizer._last_cycle_error = str(exc)
        optimizer._last_cycle_completed = datetime.now(timezone.utc)
        logger.exception("Optimizer tick failed: %s", exc)


async def run_event_loop(optimizer: "SigEnergyOptimizer") -> None:
    """
    Event-driven main loop.

    Waits on trigger_queue for entity_ids pushed by HAWebSocketClient.
    Rapid bursts are debounced so we don't thrash when a sensor updates
    every second. A heartbeat fires every _HEARTBEAT_INTERVAL seconds
    regardless, so we always converge even if WS events are missed.

    Falls back gracefully to pure heartbeat polling when the WebSocket
    is disconnected — no separate code path needed.
    """
    optimizer._running = True
    last_tick_ts = 0.0
    last_heartbeat_ts = 0.0

    logger.info(
        "Optimizer event loop started (debounce=%.0fs, heartbeat=%ds)",
        _DEBOUNCE_SECONDS, _HEARTBEAT_INTERVAL,
    )

    # One immediate startup tick
    try:
        await optimizer._tick()
        last_tick_ts = datetime.now().timestamp()
        last_heartbeat_ts = last_tick_ts
    except Exception as exc:
        logger.exception("Startup tick failed: %s", exc)

    while optimizer._running:
        now = datetime.now().timestamp()
        time_since_heartbeat = now - last_heartbeat_ts
        wait_max = max(0.01, _HEARTBEAT_INTERVAL - time_since_heartbeat)

        try:
            entity_id = await asyncio.wait_for(
                optimizer.trigger_queue.get(),
                timeout=wait_max,
            )
            optimizer.trigger_queue.task_done()

            # Minute tick from WS time_changed event
            if entity_id == "__time_changed__":
                if datetime.now().timestamp() - last_tick_ts >= _HEARTBEAT_INTERVAL - 1:
                    logger.debug("Heartbeat tick (WS time_changed)")
                    await safe_tick(optimizer)
                    last_tick_ts = last_heartbeat_ts = datetime.now().timestamp()
                continue

            # Real entity state change — drain burst then run
            logger.debug("Event-driven tick triggered by: %s", entity_id)
            await drain_queue(optimizer, _DEBOUNCE_SECONDS)
            await safe_tick(optimizer)
            last_tick_ts = last_heartbeat_ts = datetime.now().timestamp()

        except asyncio.TimeoutError:
            # No WS events — heartbeat tick
            logger.debug("Heartbeat tick (timeout, ws=%s)", optimizer._ws_connected)
            await safe_tick(optimizer)
            last_tick_ts = last_heartbeat_ts = datetime.now().timestamp()

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Event loop error: %s", exc)
            await asyncio.sleep(5)
