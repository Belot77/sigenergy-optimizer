from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from app.config import Settings
from app.ha_ws_client import HAWebSocketClient
from app.optimizer import SigEnergyOptimizer, _TRIGGER_ENTITY_ATTRS


class OptimizerEventLoopResponsivenessTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _optimizer() -> SigEnergyOptimizer:
        optimizer = object.__new__(SigEnergyOptimizer)
        optimizer.trigger_queue = asyncio.Queue(maxsize=64)
        optimizer._running = False
        optimizer._ws_connected = True
        optimizer._tick = AsyncMock()
        optimizer._safe_tick = AsyncMock()
        return optimizer

    async def test_first_real_event_waits_for_predecision_debounce(self) -> None:
        optimizer = self._optimizer()
        optimizer.trigger_queue.put_nowait("sensor.price")
        debounce_entered = asyncio.Event()
        release_debounce = asyncio.Event()

        async def hold_debounce(window: float) -> None:
            self.assertEqual(window, 3.0)
            debounce_entered.set()
            await release_debounce.wait()

        async def stop_after_event_tick() -> None:
            optimizer._running = False

        optimizer._drain_queue = AsyncMock(side_effect=hold_debounce)
        optimizer._safe_tick.side_effect = stop_after_event_tick

        run_task = asyncio.create_task(optimizer.run_forever())
        await asyncio.wait_for(debounce_entered.wait(), timeout=0.25)

        optimizer._tick.assert_awaited_once()
        optimizer._safe_tick.assert_not_awaited()

        release_debounce.set()
        await asyncio.wait_for(run_task, timeout=0.25)

        optimizer._drain_queue.assert_awaited_once_with(3.0)
        optimizer._safe_tick.assert_awaited_once()

    async def test_multiple_events_inside_debounce_produce_one_cycle(self) -> None:
        optimizer = self._optimizer()
        optimizer.trigger_queue.put_nowait("sensor.price")

        async def add_burst() -> None:
            await asyncio.sleep(0.005)
            optimizer.trigger_queue.put_nowait("sensor.pv")
            await asyncio.sleep(0.005)
            optimizer.trigger_queue.put_nowait("sensor.load")
            optimizer.trigger_queue.put_nowait("__time_changed__")

        async def stop_after_event_tick() -> None:
            optimizer._running = False

        optimizer._safe_tick.side_effect = stop_after_event_tick

        with patch("app.optimizer._DEBOUNCE_SECONDS", 0.1):
            await asyncio.wait_for(
                asyncio.gather(optimizer.run_forever(), add_burst()),
                timeout=0.5,
            )

        optimizer._safe_tick.assert_awaited_once()
        self.assertTrue(optimizer.trigger_queue.empty())

    async def test_continuous_burst_cannot_extend_fixed_debounce_window(self) -> None:
        optimizer = self._optimizer()
        optimizer.trigger_queue.put_nowait("sensor.price")
        producer_still_running_at_tick = False

        async def continuous_burst() -> None:
            for index in range(20):
                await asyncio.sleep(0.005)
                optimizer.trigger_queue.put_nowait(f"sensor.burst_{index}")

        producer_task = asyncio.create_task(continuous_burst())

        async def stop_after_event_tick() -> None:
            nonlocal producer_still_running_at_tick
            producer_still_running_at_tick = not producer_task.done()
            optimizer._running = False

        optimizer._safe_tick.side_effect = stop_after_event_tick

        try:
            with patch("app.optimizer._DEBOUNCE_SECONDS", 0.03):
                await asyncio.wait_for(optimizer.run_forever(), timeout=0.25)
        finally:
            producer_task.cancel()
            await asyncio.gather(producer_task, return_exceptions=True)

        optimizer._safe_tick.assert_awaited_once()
        self.assertTrue(producer_still_running_at_tick)

    async def test_event_after_completed_cycle_gets_next_bounded_window(self) -> None:
        optimizer = self._optimizer()
        optimizer.trigger_queue.put_nowait("sensor.price")
        tick_times: list[float] = []
        debounce_seconds = 0.03

        async def event_tick() -> None:
            tick_times.append(asyncio.get_running_loop().time())
            if len(tick_times) == 1:
                optimizer.trigger_queue.put_nowait("sensor.after_cycle")
            else:
                optimizer._running = False

        optimizer._safe_tick.side_effect = event_tick

        with patch("app.optimizer._DEBOUNCE_SECONDS", debounce_seconds):
            await asyncio.wait_for(optimizer.run_forever(), timeout=0.25)

        self.assertEqual(len(tick_times), 2)
        self.assertGreaterEqual(tick_times[1] - tick_times[0], debounce_seconds * 0.75)

    async def test_time_changed_heartbeat_still_ticks_when_due(self) -> None:
        optimizer = self._optimizer()
        optimizer.trigger_queue.put_nowait("__time_changed__")

        async def stop_after_heartbeat() -> None:
            optimizer._running = False

        optimizer._safe_tick.side_effect = stop_after_heartbeat

        with patch("app.optimizer._HEARTBEAT_INTERVAL", 1):
            await asyncio.wait_for(optimizer.run_forever(), timeout=0.25)

        optimizer._safe_tick.assert_awaited_once()

    async def test_timeout_heartbeat_still_ticks_without_ws_events(self) -> None:
        optimizer = self._optimizer()

        async def stop_after_heartbeat() -> None:
            optimizer._running = False

        optimizer._safe_tick.side_effect = stop_after_heartbeat

        with patch("app.optimizer._HEARTBEAT_INTERVAL", 0.01):
            await asyncio.wait_for(optimizer.run_forever(), timeout=0.25)

        optimizer._safe_tick.assert_awaited_once()

    async def test_startup_tick_remains_immediate(self) -> None:
        optimizer = self._optimizer()

        async def stop_after_startup() -> None:
            optimizer._running = False

        optimizer._tick.side_effect = stop_after_startup

        await asyncio.wait_for(optimizer.run_forever(), timeout=0.25)

        optimizer._tick.assert_awaited_once()
        optimizer._safe_tick.assert_not_awaited()


class HAWebSocketResponsivenessTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _client(
        queue: asyncio.Queue | None = None,
        watched: set[str] | None = None,
    ) -> tuple[HAWebSocketClient, asyncio.Queue]:
        trigger_queue = queue or asyncio.Queue(maxsize=8)
        client = HAWebSocketClient(
            "http://homeassistant.invalid",
            "test-token",
            trigger_queue,
            watched or {"sensor.watched"},
        )
        return client, trigger_queue

    @staticmethod
    def _message(
        *,
        entity_id: str = "sensor.watched",
        old_state: object = None,
        new_state: object = None,
    ) -> dict:
        return {
            "type": "event",
            "event": {
                "event_type": "state_changed",
                "data": {
                    "entity_id": entity_id,
                    "old_state": old_state,
                    "new_state": new_state,
                },
            },
        }

    async def test_watched_state_value_change_enqueues(self) -> None:
        client, queue = self._client()

        await client._handle_message(
            self._message(
                old_state={"state": "1", "attributes": {}},
                new_state={"state": "2", "attributes": {}},
            )
        )

        self.assertEqual(queue.get_nowait(), "sensor.watched")

    async def test_watched_attributes_only_change_enqueues(self) -> None:
        client, queue = self._client()

        await client._handle_message(
            self._message(
                old_state={"state": "5", "attributes": {"forecast": [1]}},
                new_state={"state": "5", "attributes": {"forecast": [2]}},
            )
        )

        self.assertEqual(queue.get_nowait(), "sensor.watched")

    async def test_metadata_only_change_does_not_enqueue(self) -> None:
        client, queue = self._client()

        await client._handle_message(
            self._message(
                old_state={
                    "state": "5",
                    "attributes": {"forecast": [1]},
                    "last_updated": "2026-01-01T00:00:00+00:00",
                },
                new_state={
                    "state": "5",
                    "attributes": {"forecast": [1]},
                    "last_updated": "2026-01-01T00:00:01+00:00",
                },
            )
        )

        self.assertTrue(queue.empty())

    async def test_missing_old_or_new_state_enqueues_conservatively(self) -> None:
        for old_state, new_state in (
            (None, {"state": "5", "attributes": {}}),
            ({"state": "5", "attributes": {}}, None),
        ):
            with self.subTest(old_state=old_state, new_state=new_state):
                client, queue = self._client()

                await client._handle_message(
                    self._message(old_state=old_state, new_state=new_state)
                )

                self.assertEqual(queue.get_nowait(), "sensor.watched")

    async def test_unwatched_entity_does_not_enqueue(self) -> None:
        client, queue = self._client()

        await client._handle_message(
            self._message(
                entity_id="sensor.unwatched",
                old_state={"state": "1", "attributes": {}},
                new_state={"state": "2", "attributes": {}},
            )
        )

        self.assertTrue(queue.empty())

    async def test_queue_full_handling_remains_non_blocking(self) -> None:
        queue: asyncio.Queue = asyncio.Queue(maxsize=1)
        queue.put_nowait("existing")
        client, _ = self._client(queue=queue)

        await asyncio.wait_for(
            client._handle_message(
                self._message(
                    old_state={"state": "1", "attributes": {}},
                    new_state={"state": "2", "attributes": {}},
                )
            ),
            timeout=0.1,
        )

        self.assertEqual(queue.qsize(), 1)
        self.assertEqual(queue.get_nowait(), "existing")


class WatchEntityResponsivenessTests(unittest.TestCase):
    @staticmethod
    def _watched() -> tuple[Settings, set[str]]:
        optimizer = object.__new__(SigEnergyOptimizer)
        optimizer.cfg = Settings(_env_file=None)
        optimizer._watch_entities = set()
        return optimizer.cfg, optimizer.get_watch_entities()

    def test_existing_instantaneous_control_entities_remain_watched(self) -> None:
        cfg, watched = self._watched()
        attributes = {
            "pv_power_sensor",
            "consumed_power_sensor",
            "battery_power_sensor",
            "grid_import_power_sensor",
            "grid_export_power_sensor",
            "solar_power_now_sensor",
            "battery_soc_sensor",
            "price_sensor",
            "feedin_sensor",
            "sun_entity",
            "sigenergy_mode_select",
            "ems_mode_select",
            "grid_export_limit",
            "grid_import_limit",
            "pv_max_power_limit",
            "ess_max_charging_limit",
            "ess_max_discharging_limit",
            "ha_control_switch",
            "demand_window_sensor",
            "price_spike_sensor",
        }

        expected = {
            getattr(cfg, attribute)
            for attribute in attributes
            if getattr(cfg, attribute)
        }
        self.assertTrue(expected.issubset(watched))

    def test_decision_relevant_existing_forecast_entities_are_watched(self) -> None:
        cfg, watched = self._watched()
        attributes = {
            "forecast_remaining_sensor",
            "forecast_today_sensor",
            "forecast_tomorrow_sensor",
            "price_forecast_sensor",
            "feedin_forecast_sensor",
        }

        self.assertTrue({getattr(cfg, attribute) for attribute in attributes}.issubset(watched))

    def test_existing_battery_capability_entities_are_watched(self) -> None:
        cfg, watched = self._watched()
        attributes = {
            "rated_capacity_sensor",
            "available_discharge_sensor",
            "ess_rated_discharge_power_sensor",
            "ess_rated_charge_power_sensor",
        }

        self.assertTrue({getattr(cfg, attribute) for attribute in attributes}.issubset(watched))

    def test_watch_set_contains_only_configured_entity_ids(self) -> None:
        cfg, watched = self._watched()
        configured = {
            getattr(cfg, attribute)
            for attribute in _TRIGGER_ENTITY_ATTRS
            if getattr(cfg, attribute, "")
        }

        self.assertEqual(watched, configured)


if __name__ == "__main__":
    unittest.main()
