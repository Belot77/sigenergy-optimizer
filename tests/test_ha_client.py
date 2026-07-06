from __future__ import annotations

import unittest
from typing import Any

from app.ha_client import HAClient


class RecordingHAClient(HAClient):
    def __init__(self, result: bool = True, *, raise_error: bool = False) -> None:
        self.calls: list[tuple[str, str, dict[str, Any]]] = []
        self.result = result
        self.raise_error = raise_error

    async def call_service(self, domain: str, service: str, data: dict[str, Any]) -> bool:
        self.calls.append((domain, service, data))
        if self.raise_error:
            raise RuntimeError("service unavailable")
        return self.result


class HAClientNotificationTests(unittest.IsolatedAsyncioTestCase):
    async def test_notify_entity_uses_send_message_target(self) -> None:
        ha = RecordingHAClient()

        ok = await ha.send_notification(
            "notify.dave_pixel",
            "Sig Opt test",
            "Test from Home Assistant notify.send_message",
        )

        self.assertTrue(ok)
        self.assertEqual(
            ha.calls,
            [
                (
                    "notify",
                    "send_message",
                    {
                        "entity_id": "notify.dave_pixel",
                        "title": "Sig Opt test",
                        "message": "Test from Home Assistant notify.send_message",
                    },
                )
            ],
        )

    async def test_legacy_non_notify_service_still_splits_domain_and_service(self) -> None:
        ha = RecordingHAClient()

        ok = await ha.send_notification(
            "persistent_notification.create",
            "Sig Opt test",
            "Legacy service path",
        )

        self.assertTrue(ok)
        self.assertEqual(
            ha.calls,
            [
                (
                    "persistent_notification",
                    "create",
                    {
                        "title": "Sig Opt test",
                        "message": "Legacy service path",
                    },
                )
            ],
        )

    async def test_failed_notification_returns_false_and_logs_warning(self) -> None:
        ha = RecordingHAClient(result=False)

        with self.assertLogs("app.ha_client", level="WARNING") as logs:
            ok = await ha.send_notification("notify.dave_pixel", "Title", "Message")

        self.assertFalse(ok)
        self.assertIn("Notification via notify.send_message to notify.dave_pixel failed", "\n".join(logs.output))

    async def test_notification_call_exception_returns_false_and_logs_error(self) -> None:
        ha = RecordingHAClient(raise_error=True)

        with self.assertLogs("app.ha_client", level="ERROR") as logs:
            ok = await ha.send_notification("notify.dave_pixel", "Title", "Message")

        self.assertFalse(ok)
        self.assertIn("Notification via notify.send_message to notify.dave_pixel failed", "\n".join(logs.output))


if __name__ == "__main__":
    unittest.main()
