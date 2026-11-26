from __future__ import annotations

import json
import unittest
from datetime import datetime
from typing import Any

import httpx

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


class SolarProviderHandoffWitnessTests(unittest.IsolatedAsyncioTestCase):
    entities = ("sensor.solcast_today", "sensor.solcast_last_polled")

    def _row(self, entity_id: str) -> dict[str, str]:
        return {
            "entity_id": entity_id,
            "state": "65.31" if entity_id == self.entities[0] else "2026-11-24T00:24:36+00:00",
            "context_id": f"{entity_id}-context",
            "last_changed": "2026-11-24T00:24:36+00:00",
            "last_updated": "2026-11-24T00:24:36.001+00:00",
            "last_reported": "2026-11-24T01:45:30Z",
            "entry_id": "solcast-entry",
            "domain": "solcast_solar",
            "entry_state": "loaded",
            "version": "4.6.1",
            "device_id": "solcast-device",
        }

    async def _request(self, response, read):
        requests = []

        def handle(request):
            requests.append(request)
            if isinstance(response, Exception):
                raise response
            return response

        client = HAClient("http://home-assistant.invalid", "test-token")
        await client.close()
        async with httpx.AsyncClient(
            base_url="http://home-assistant.invalid",
            transport=httpx.MockTransport(handle),
        ) as mock_client:
            client._client = mock_client
            result = await read(client)
        return result, requests

    async def _read(self, response, entities=None):
        return await self._request(
            response, lambda client: client.get_solar_provider_handoff_witness(entities or self.entities),
        )

    async def test_reads_complete_native_witness_in_one_read_only_request(self):
        rows = [self._row(entity_id) for entity_id in reversed(self.entities)]
        rows[0]["version"] = "v4.6.1"
        result, requests = await self._read(httpx.Response(200, json=rows))

        self.assertEqual(len(requests), 1)
        request = requests[0]
        self.assertEqual((request.method, request.url.path), ("POST", "/api/template"))
        template = json.loads(request.content)["template"]
        for fragment in (
            *self.entities,
            "entity.context.id",
            "entity.last_reported.isoformat()",
            "entity.attributes.get('restored')",
            "('solcast_solar', entry) in identifiers",
            "config_entry_attr(entry, 'state')",
            "device_attr(device, 'sw_version')",
        ):
            self.assertIn(fragment, template)
        expected = {
            row["entity_id"]: {
                key: value for key, value in row.items() if key != "entity_id"
            }
            for row in rows
        }
        expected[self.entities[1]]["version"] = "4.6.1"
        self.assertEqual(result, expected)

    async def test_normalizes_and_preserves_solcast_device_versions_without_allowlist(self):
        for version in ("4.6.3", "4.6.4", "4.6.5", "9.0.0-preview"):
            with self.subTest(version=version):
                rows = [
                    {**self._row(entity_id), "version": reported}
                    for entity_id, reported in zip(self.entities, (version, f" v{version} "), strict=True)
                ]
                result, _ = await self._read(httpx.Response(200, json=rows))

                self.assertEqual({entity: row["version"] for entity, row in result.items()}, {
                    entity: version for entity in self.entities
                })

    async def test_rejects_incomplete_or_conflicting_evidence(self):
        first, second = [self._row(entity_id) for entity_id in self.entities]
        cases = (
            [first],
            [first, first],
            [first, second, second],
            [first, {**second, "entity_id": "sensor.other"}],
            [first, {**second, "entry_id": "other-entry"}],
            [first, {**second, "device_id": "other-device"}],
            [first, {**second, "domain": "template"}],
            [first, {**second, "entry_state": "setup_retry"}],
            [first, {**second, "version": "4.6.2"}],
            [first, {**second, "version": "4.6.3"}],
            [{**first, "version": "4.6.3"}, {**second, "version": "v4.6.4"}],
            [{**first, "version": "v4.6.5"}, {**second, "version": "4.7.0"}],
            [{**first, "version": " v "}, {**second, "version": "v"}],
            [{**first, "version": "unknown"}, {**second, "version": "unknown"}],
            [{**first, "version": "4.6.5\npreview"}, {**second, "version": "4.6.5\npreview"}],
            [first, {**second, "state": "unavailable"}],
            [first, {**second, "context_id": ""}],
            [first, {**second, "last_changed": "2026-11-24T00:24:36"}],
            [first, {**second, "last_changed": "2026-11-24T00:25:36Z"}],
            [first, {**second, "last_reported": "2026-11-24T00:24:35Z"}],
            [first, {**second, "last_reported": "invalid"}],
        )
        for rows in cases:
            with self.subTest(rows=rows):
                result, _ = await self._read(httpx.Response(200, json=rows))
                self.assertEqual(result, {})

    async def test_rejects_failed_template_requests(self):
        for response, reason in (
            (httpx.Response(403), "template_http_status_403"),
            (httpx.Response(200, text="invalid JSON"), "invalid_template_data"),
            (httpx.ReadTimeout("no response"), "template_request_failed"),
        ):
            with self.subTest(response=response):
                with self.assertLogs("app.ha_client", level="INFO") as logs:
                    result, requests = await self._read(response)
                self.assertEqual(result, {})
                self.assertEqual(len(requests), 1)
                self.assertEqual([record.getMessage() for record in logs.records], [
                    f"Solar restart handoff witness: {reason}"
                ])

    async def test_rejects_non_sensor_or_duplicate_ids_before_request(self):
        for entities in (
            (self.entities[0], "switch.other"),
            (self.entities[0], self.entities[0]),
            (self.entities[0], "sensor.other' %}"),
        ):
            with self.subTest(entities=entities):
                result, requests = await self._read(httpx.Response(200), entities)
                self.assertEqual(result, {})
                self.assertEqual(requests, [])


    async def test_config_entry_lookup_requires_one_loaded_solcast_entry(self):
        entry = {"entry_id": "solcast-entry", "domain": "solcast_solar", "state": "loaded"}

        entry_id, requests = await self._request(
            httpx.Response(200, json=[entry]), HAClient.get_loaded_solcast_entry_id,
        )

        self.assertEqual(entry_id, "solcast-entry")
        self.assertEqual(len(requests), 1)
        request = requests[0]
        self.assertEqual((request.method, request.url.path), ("GET", "/api/config/config_entries/entry"))
        self.assertEqual(dict(request.url.params), {"domain": "solcast_solar"})

        for invalid_entries in (
            [],
            [entry, {**entry, "entry_id": "another-entry", "state": "not_loaded"}],
            [{"domain": "solcast_solar", "state": "loaded"}],
            [{**entry, "entry_id": "solcast-entry "}],
            [{**entry, "domain": "template"}],
            [{**entry, "state": "setup_retry"}],
            {"entries": [entry]},
        ):
            with self.subTest(entries=invalid_entries):
                invalid, _ = await self._request(
                    httpx.Response(200, json=invalid_entries), HAClient.get_loaded_solcast_entry_id,
                )
                self.assertIsNone(invalid)

    async def test_reads_solcast_cache_only_for_exact_aggregate_utc_interval(self):
        # The interval crosses the Sydney daylight-saving fold.
        start = datetime.fromisoformat("2026-04-05T02:30:00+11:00")
        end = datetime.fromisoformat("2026-04-05T02:00:00+10:00")
        periods = [{"period_start": "2026-04-05T02:30:00+11:00", "pv_estimate": 0.3}]
        payload = {"changed_states": [], "service_response": {"data": periods}}

        result, requests = await self._request(
            httpx.Response(200, json=payload),
            lambda client: client.query_solcast_cached_forecast(start, end),
        )

        self.assertEqual(result, periods)
        self.assertEqual(len(requests), 1)
        request = requests[0]
        self.assertEqual((request.method, request.url.path), ("POST", "/api/services/solcast_solar/query_forecast_data"))
        self.assertIn("return_response", request.url.params)
        self.assertEqual(
            json.loads(request.content),
            {
                "start_date_time": "2026-04-04T15:30:00+00:00",
                "end_date_time": "2026-04-04T16:00:00+00:00",
                "site": "all",
                "undampened": False,
            },
        )
        for invalid_start, invalid_end in ((start, start), (end, start), (start.replace(tzinfo=None), end)):
            result, requests = await self._request(
                httpx.Response(200, json=payload),
                lambda client: client.query_solcast_cached_forecast(invalid_start, invalid_end),
            )
            self.assertIsNone(result)
            self.assertEqual(requests, [])

    async def test_cache_query_rejects_absent_or_malformed_responses(self):
        start = datetime.fromisoformat("2026-11-26T01:00:00+00:00")
        end = datetime.fromisoformat("2026-11-26T02:00:00+00:00")
        for response in (
            httpx.Response(404, json={"message": "service absent"}),
            httpx.Response(200, text="invalid JSON"),
            httpx.Response(200, json={"data": [{}]}),
            httpx.Response(200, json={"changed_states": [], "service_response": [{}]}),
            httpx.Response(200, json={"changed_states": [], "service_response": {"data": []}}),
            httpx.Response(200, json={"changed_states": [], "service_response": {"data": [1.25]}}),
            httpx.Response(200, json={"changed_states": [{"entity_id": "sensor.forecast"}], "service_response": {
                "data": [{"period_start": "2026-11-26T01:00:00+00:00", "pv_estimate": 0.3}],
            }}),
            httpx.ReadTimeout("no response"),
        ):
            with self.subTest(response=response):
                result, requests = await self._request(
                    response, lambda client: client.query_solcast_cached_forecast(start, end),
                )
                self.assertIsNone(result)
                self.assertEqual(len(requests), 1)


if __name__ == "__main__":
    unittest.main()
