from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from .models import Decision, SolarState

logger = logging.getLogger(__name__)


async def handle_notifications(
    optimizer,
    s: SolarState,
    d: Decision,
    prev: Optional[Decision],
    prev_state: Optional[SolarState] = None,
) -> None:
    cfg = optimizer.cfg
    if not cfg.notification_service:
        return

    notify = lambda title, msg: optimizer.ha.send_notification(cfg.notification_service, title, msg)
    if prev is None:
        optimizer._notif_export_active = d.export_limit > 0.011
        optimizer._prev_demand_window = s.demand_window_active
        optimizer._battery_full_alert_armed = s.battery_soc < 98.0
        optimizer._battery_empty_alert_armed = s.battery_soc > 2.0
        return

    export_session_kwh = max(0.0, s.daily_export_kwh - s.export_session_start_kwh)
    import_session_kwh = max(0.0, s.daily_import_kwh - s.import_session_start_kwh)

    # Debounce export start notifications so tiny control flaps do not spam users.
    export_near_zero = 0.011
    export_active_now = d.export_limit > export_near_zero
    export_active_prev = optimizer._notif_export_active
    if export_active_prev is None:
        export_active_prev = prev.export_limit > export_near_zero
    export_started = (not export_active_prev) and export_active_now
    export_stopped = export_active_prev and (not export_active_now)
    optimizer._notif_export_active = export_active_now

    # Export started
    if export_started:
        await optimizer.ha.set_input_number(cfg.export_session_start, s.daily_export_kwh)
        await optimizer.ha.logbook_log(
            "SigEnergy Export",
            f"Export ENABLED → {d.export_limit:.1f} kW  FIT={s.feedin_price:.3f} $/kWh",
        )
        now = datetime.now(timezone.utc)
        last_notice = optimizer._last_export_start_notice_at
        if last_notice and (now - last_notice) < timedelta(minutes=20):
            logger.debug("Suppressing duplicate export started notification within cooldown window")
        else:
            optimizer._last_export_start_notice_at = now
            if s.last_export_notification != "started":
                if cfg.notify_export_started_stopped:
                    await notify(
                        "📤 SigEnergy: Export Started",
                        f"💲 FIT: {s.feedin_price:.3f} $/kWh\n"
                        f"⚡ Limit: {d.export_limit:.1f} kW\n"
                        f"🔋 Battery: {s.battery_soc:.0f}%\n"
                        f"🌙 Night: {d.is_evening_or_night}",
                    )
                await optimizer.ha.set_input_text(cfg.last_export_notification, "started")

    # Export stopped
    if export_stopped:
        await optimizer.ha.logbook_log(
            "SigEnergy Export",
            f"Export DISABLED → Session {export_session_kwh:.3f} kWh  FIT={s.feedin_price:.3f} $/kWh",
        )
        if s.last_export_notification != "stopped":
            if cfg.notify_export_started_stopped:
                await notify(
                    "🛑 SigEnergy: Export Stopped",
                    f"📤 Session: {export_session_kwh:.3f} kWh\n"
                    f"📈 Daily Total: {s.daily_export_kwh:.3f} kWh\n"
                    f"🔋 Battery: {s.battery_soc:.0f}%\n"
                    f"💲 FIT: {s.feedin_price:.3f} $/kWh",
                )
            await optimizer.ha.set_input_text(cfg.last_export_notification, "stopped")

    # Import started/stopped use near-zero semantics because holdoff mode uses 0.01
    near_zero = 0.011
    prev_import_active = prev.import_limit > near_zero
    now_import_active = d.import_limit > near_zero

    # Import started
    if not prev_import_active and now_import_active:
        await optimizer.ha.set_input_number(cfg.import_session_start, s.daily_import_kwh)
        await optimizer.ha.logbook_log(
            "SigEnergy Import",
            f"Import ENABLED → {d.import_limit:.1f} kW  Price={s.current_price}",
        )
        if s.last_import_notification != "started":
            if cfg.notify_import_started_stopped:
                await notify(
                    "⚡ SigEnergy: Import Started",
                    f"💲 Price: {s.current_price:.3f} $/kWh\n"
                    f"📥 Limit: {d.import_limit:.1f} kW\n"
                    f"🔋 Battery: {s.battery_soc:.0f}%\n"
                    f"🌙 Night: {d.is_evening_or_night}",
                )
            await optimizer.ha.set_input_text(cfg.last_import_notification, "started")

    # Import stopped
    if prev_import_active and not now_import_active:
        await optimizer.ha.logbook_log(
            "SigEnergy Import",
            f"Import DISABLED → Session {import_session_kwh:.3f} kWh",
        )
        if s.last_import_notification != "stopped":
            if cfg.notify_import_started_stopped:
                await notify(
                    "🛑 SigEnergy: Import Stopped",
                    f"📥 Session: {import_session_kwh:.3f} kWh\n"
                    f"📈 Daily Total: {s.daily_import_kwh:.3f} kWh\n"
                    f"💲 Last price: ${s.current_price:.3f}/kWh\n"
                    f"🔋 Battery: {s.battery_soc:.0f}%",
                )
            await optimizer.ha.set_input_text(cfg.last_import_notification, "stopped")

    # Battery alerts
    prev_soc_was_ok = prev_state is None or prev_state.battery_soc >= d.battery_soc_required_to_sunrise
    if cfg.notify_battery_alerts and s.battery_soc < d.battery_soc_required_to_sunrise and prev_soc_was_ok:
        await notify(
            "⚠️ Battery below reserve SoC",
            f"Battery below reserve ({d.battery_soc_required_to_sunrise:.0f}%): {s.battery_soc:.0f}%",
        )

    # Battery full/empty anti-spam:
    # - Hysteresis arming avoids repeated alerts when SoC hovers around thresholds.
    # - Cooldown avoids notification floods from noisy sensors or restart loops.
    if s.battery_soc <= 97.0:
        optimizer._battery_full_alert_armed = True
    if s.battery_soc >= 3.0:
        optimizer._battery_empty_alert_armed = True

    now_utc = datetime.now(timezone.utc)
    alert_cooldown = timedelta(minutes=180)

    full_cooldown_ok = (
        optimizer._last_battery_full_notice_at is None
        or (now_utc - optimizer._last_battery_full_notice_at) >= alert_cooldown
    )
    empty_cooldown_ok = (
        optimizer._last_battery_empty_notice_at is None
        or (now_utc - optimizer._last_battery_empty_notice_at) >= alert_cooldown
    )

    if cfg.notify_battery_alerts and optimizer._battery_empty_alert_armed and s.battery_soc <= 1.0 and empty_cooldown_ok:
        await notify("🪫 Battery Empty!", f"Battery SoC: {s.battery_soc:.0f}%")
        optimizer._battery_empty_alert_armed = False
        optimizer._last_battery_empty_notice_at = now_utc

    if cfg.notify_battery_alerts and optimizer._battery_full_alert_armed and s.battery_soc >= 99.0 and full_cooldown_ok:
        await notify("🔋 Battery Full!", f"Battery SoC: {s.battery_soc:.0f}%")
        optimizer._battery_full_alert_armed = False
        optimizer._last_battery_full_notice_at = now_utc

    if cfg.notify_price_spike_alert and s.price_spike_active and (not prev or not prev.export_spike_active):
        await notify(
            "📈 Price Spike Active",
            f"Buy: ${s.current_price:.3f}/kWh\nFIT: ${s.feedin_price:.3f}/kWh",
        )

    if cfg.notify_demand_window_alert and s.demand_window_active and not optimizer._prev_demand_window:
        await notify(
            "⏱️ Demand Window In Effect",
            "Demand window active; import is blocked until it ends.",
        )
    optimizer._prev_demand_window = s.demand_window_active


async def handle_daily_summaries(optimizer, s: SolarState, d: Decision) -> None:
    cfg = optimizer.cfg
    if not cfg.notification_service:
        return
    now = datetime.now()
    notify = lambda title, msg: optimizer.ha.send_notification(cfg.notification_service, title, msg)

    if cfg.notify_daily_summary:
        t = optimizer._today_at(cfg.daily_summary_time)
        if abs((now - t).total_seconds()) < cfg.poll_interval_seconds:
            if optimizer._last_daily_summary_date != now.date():
                optimizer._last_daily_summary_date = now.date()
                await notify(
                    "☀️ SigEnergy Summary",
                    f"🔌 Use: {s.daily_load_kwh:.2f} kWh\n"
                    f"☀️ PV: {s.daily_pv_kwh:.2f} kWh\n"
                    f"🔋 Batt: +{s.daily_battery_charge_kwh:.2f} / -{s.daily_battery_discharge_kwh:.2f} kWh\n"
                    f"📥 Import: {s.daily_import_kwh:.2f} kWh\n"
                    f"📤 Export: {s.daily_export_kwh:.2f} kWh\n"
                    f"🔚 SoC: {s.battery_soc:.0f}%",
                )

    if cfg.notify_morning_summary:
        t = optimizer._today_at(cfg.morning_summary_time)
        if abs((now - t).total_seconds()) < cfg.poll_interval_seconds:
            if optimizer._last_morning_summary_date != now.date():
                optimizer._last_morning_summary_date = now.date()
                await notify(
                    "🌅 SigEnergy Morning",
                    f"☀️ PV forecast today: {s.forecast_today_kwh:.1f} kWh\n"
                    f"🔋 Batt discharge so far: {s.daily_battery_discharge_kwh:.2f} kWh\n"
                    f"🔚 SoC: {s.battery_soc:.0f}%",
                )
