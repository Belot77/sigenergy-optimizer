from __future__ import annotations

import asyncio
from datetime import datetime

from app.models import (
    BATTERY_EXPORT,
    Decision,
    HVACObservedValue,
    HVACSolarInputContext,
    MSC_SURPLUS_CEILING,
)
from haos49_characterization_helpers import (
    Haos49CharacterizationCase,
    RecordingHA,
)


class NotificationRecordingHA(RecordingHA):
    def __init__(self) -> None:
        super().__init__()
        self.notifications: list[tuple[str, str, str]] = []
        self.logbook_entries: list[tuple[str, str]] = []

    async def send_notification(self, service: str, title: str, message: str) -> bool:
        self.notifications.append((service, title, message))
        return True

    async def logbook_log(self, name: str, message: str) -> bool:
        self.logbook_entries.append((name, message))
        return True


class ExportNotificationTests(Haos49CharacterizationCase):
    NOW = datetime(2026, 1, 15, 14, 0, 0)

    def _optimizer(self) -> tuple[object, NotificationRecordingHA]:
        ha = NotificationRecordingHA()
        optimizer = self.optimizer(
            ha,
            notification_service="notify.test",
            notify_export_started_stopped=True,
            notify_import_started_stopped=False,
            notify_battery_alerts=False,
            notify_price_spike_alert=False,
            notify_demand_window_alert=False,
            min_grid_transfer_kw=1.0,
        )
        return optimizer, ha

    @staticmethod
    def _observation(
        value: float | None,
        *,
        available: bool = True,
        fresh: bool = True,
    ) -> HVACObservedValue:
        return HVACObservedValue(value=value, available=available, fresh=fresh)

    def _state(
        self,
        measured_export_kw: float,
        *,
        battery_power_kw: float = 0.0,
        export_observation: HVACObservedValue | None = None,
        last_export_notification: str = "stopped",
        sigenergy_mode: str = "Automated",
    ):
        return self.state(
            self.NOW,
            sigenergy_mode=sigenergy_mode,
            grid_export_power_kw=measured_export_kw,
            battery_power_sensor_kw=battery_power_kw,
            last_export_notification=last_export_notification,
            hvac_solar_inputs=HVACSolarInputContext(
                grid_export_power=export_observation
                or self._observation(measured_export_kw),
                live_snapshot=True,
            ),
        )

    @staticmethod
    def _decision(
        export_limit: float,
        *,
        export_intent: str = MSC_SURPLUS_CEILING,
    ) -> Decision:
        return Decision(
            export_limit=export_limit,
            import_limit=0.01,
            export_intent=export_intent,
        )

    @staticmethod
    def _run(optimizer, state, decision, previous, previous_state=None) -> None:
        asyncio.run(
            optimizer._handle_notifications(
                state,
                decision,
                previous,
                previous_state,
            )
        )

    @staticmethod
    def _export_titles(ha: NotificationRecordingHA) -> list[str]:
        return [title for _, title, _ in ha.notifications if "Export" in title]

    def test_permission_only_ceiling_open_close_and_load_serving_discharge_are_silent(
        self,
    ) -> None:
        optimizer, ha = self._optimizer()
        closed = self._decision(0.01)
        open_ceiling = self._decision(25.0)

        initial_state = self._state(0.0, battery_power_kw=-1.4)
        self._run(optimizer, initial_state, closed, None)
        self._run(
            optimizer,
            self._state(0.05, battery_power_kw=-1.4),
            open_ceiling,
            closed,
            initial_state,
        )
        self._run(
            optimizer,
            self._state(0.0, battery_power_kw=-1.3),
            closed,
            open_ceiling,
        )

        self.assertEqual([], self._export_titles(ha))
        self.assertEqual([], ha.logbook_entries)
        self.assertFalse(
            any(call[1] == optimizer.cfg.export_session_start for call in ha.calls)
        )

    def test_trusted_meaningful_export_emits_one_start_and_one_stop(self) -> None:
        optimizer, ha = self._optimizer()
        decision = self._decision(25.0)

        initial_state = self._state(0.0)
        self._run(optimizer, initial_state, decision, None)
        started_state = self._state(1.0)
        self._run(optimizer, started_state, decision, decision, initial_state)
        self._run(
            optimizer,
            self._state(4.0, last_export_notification="started"),
            decision,
            decision,
            started_state,
        )
        stopped_state = self._state(
            0.2,
            last_export_notification="started",
        )
        self._run(optimizer, stopped_state, decision, decision)
        self._run(
            optimizer,
            self._state(0.0, last_export_notification="stopped"),
            decision,
            decision,
            stopped_state,
        )

        self.assertEqual(
            ["📤 SigEnergy: Export Started", "🛑 SigEnergy: Export Stopped"],
            self._export_titles(ha),
        )
        self.assertEqual(2, len(ha.logbook_entries))

    def test_untrusted_export_telemetry_cannot_create_edges(self) -> None:
        optimizer, ha = self._optimizer()
        decision = self._decision(25.0)

        initial_state = self._state(0.0)
        self._run(optimizer, initial_state, decision, None)
        stale_high = self._state(
            5.0,
            export_observation=self._observation(5.0, fresh=False),
        )
        self._run(optimizer, stale_high, decision, decision, initial_state)
        self.assertEqual([], self._export_titles(ha))

        active_state = self._state(2.0)
        self._run(optimizer, active_state, decision, decision, stale_high)
        stale_zero = self._state(
            0.0,
            export_observation=self._observation(0.0, fresh=False),
            last_export_notification="started",
        )
        self._run(optimizer, stale_zero, decision, decision, active_state)
        self.assertEqual(["📤 SigEnergy: Export Started"], self._export_titles(ha))

        self._run(
            optimizer,
            self._state(0.0, last_export_notification="started"),
            decision,
            decision,
            stale_zero,
        )
        self.assertEqual(
            ["📤 SigEnergy: Export Started", "🛑 SigEnergy: Export Stopped"],
            self._export_titles(ha),
        )

    def test_deliberate_battery_export_and_manual_mode_use_physical_export(self) -> None:
        for name, mode, intent in (
            ("battery_export", "Automated", BATTERY_EXPORT),
            ("manual_full_export", "Full Export", MSC_SURPLUS_CEILING),
        ):
            with self.subTest(name=name):
                optimizer, ha = self._optimizer()
                decision = self._decision(25.0, export_intent=intent)
                initial_state = self._state(0.0, sigenergy_mode=mode)
                self._run(optimizer, initial_state, decision, None)
                self._run(
                    optimizer,
                    self._state(
                        3.0,
                        battery_power_kw=-2.0,
                        sigenergy_mode=mode,
                    ),
                    decision,
                    decision,
                    initial_state,
                )

                self.assertEqual(
                    ["📤 SigEnergy: Export Started"],
                    self._export_titles(ha),
                )
