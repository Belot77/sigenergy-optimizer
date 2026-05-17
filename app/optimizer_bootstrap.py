from __future__ import annotations

import asyncio
import logging
import os
from collections import deque
from datetime import datetime, timezone
from typing import Any, Optional, Union
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .earnings import EarningsService
from .models import Decision, SolarState
from .state_store import StateStore

logger = logging.getLogger(__name__)

_POWER_LIMIT_MAX_KW = 100.0
_RUNTIME_SIGNATURE = "2.3.0-haos21"


def initialize_runtime_state(optimizer) -> None:
    optimizer._last_state: Optional[SolarState] = None
    optimizer._last_decision: Optional[Decision] = None
    optimizer._last_daily_summary_date: Optional[datetime] = None
    optimizer._last_morning_summary_date: Optional[datetime] = None
    optimizer._running = False
    optimizer._ws_connected = False
    optimizer._prev_demand_window = False
    optimizer._config_time_warnings = optimizer._validate_time_config()
    optimizer._sensor_parse_warning_cache: dict[tuple[str, str], float] = {}
    optimizer._holdoff_entry_floor: Optional[float] = None
    optimizer._last_hw_charge_cap_kw: Optional[float] = None
    optimizer._last_hw_discharge_cap_kw: Optional[float] = None
    optimizer._last_cycle_started: Optional[datetime] = None
    optimizer._last_cycle_completed: Optional[datetime] = None
    optimizer._last_cycle_error = ""
    optimizer._notif_export_active: Optional[bool] = None
    optimizer._last_export_start_notice_at: Optional[datetime] = None
    optimizer._battery_full_alert_armed = True
    optimizer._battery_empty_alert_armed = True
    optimizer._last_battery_full_notice_at: Optional[datetime] = None
    optimizer._last_battery_empty_notice_at: Optional[datetime] = None
    optimizer._manual_mode_override: Optional[str] = None
    optimizer._manual_ess_charge_override_kw: Optional[float] = None
    optimizer._manual_ess_discharge_override_kw: Optional[float] = None
    optimizer._morning_slow_charge_runtime_disabled = False
    optimizer._morning_slow_disable_logged = False
    logger.warning(
        "Runtime signature=%s morning_slow_charge_runtime_disabled=%s",
        _RUNTIME_SIGNATURE,
        optimizer._morning_slow_charge_runtime_disabled,
    )
    tz_name = os.environ.get("TZ", "Australia/Adelaide")
    optimizer._tz: Union[ZoneInfo, timezone]
    try:
        optimizer._tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        logger.warning("Timezone '%s' not found; falling back to UTC", tz_name)
        optimizer._tz = timezone.utc
    optimizer._last_tracked_block: Optional[int] = None
    optimizer._last_tracked_import_kw = -999.0
    optimizer._last_tracked_export_kw = -999.0
    optimizer._last_tracked_import_price: Optional[float] = None
    optimizer._last_tracked_feedin_price: Optional[float] = None
    db_path = os.environ.get("STATE_DB_PATH", "/data/optimizer_state.db")
    optimizer._state_store = StateStore(db_path)
    optimizer._earnings = EarningsService(optimizer.ha, optimizer.cfg, optimizer._state_store, optimizer._tz)
    optimizer._decision_trace: deque[dict[str, Any]] = deque(maxlen=1000)
    optimizer._control_lock = asyncio.Lock()
    optimizer.trigger_queue: asyncio.Queue = asyncio.Queue(maxsize=64)
    optimizer._watch_entities: set[str] = set()
