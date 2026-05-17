from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_TRIGGER_ENTITY_ATTRS = [
    "pv_power_sensor",
    "consumed_power_sensor",
    "battery_soc_sensor",
    "price_sensor",
    "feedin_sensor",
    "demand_window_sensor",
    "price_spike_sensor",
    "sigenergy_mode_select",
]


def get_watch_entities(optimizer) -> set[str]:
    """Return the set of entity IDs the WS client should subscribe to."""
    if not optimizer._watch_entities:
        optimizer._watch_entities = {
            getattr(optimizer.cfg, attr)
            for attr in _TRIGGER_ENTITY_ATTRS
            if getattr(optimizer.cfg, attr, "")
        }
    return optimizer._watch_entities


def on_ws_connect(optimizer) -> None:
    optimizer._ws_connected = True
    logger.info("WebSocket connected — event-driven mode active")


def on_ws_disconnect(optimizer) -> None:
    optimizer._ws_connected = False
    logger.warning("WebSocket disconnected — heartbeat fallback active")