from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

import httpx
from fastapi import FastAPI

from app.routers import api


TRACE_PATH = "/api/decision_trace"
PREVIEW_PATH = f"{TRACE_PATH}/preview"
HEADERS = {"x-api-key": "test-only-key"}
NOW = datetime(2026, 1, 15, 2, 0, tzinfo=timezone.utc)


class DecisionTracePreviewTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.rows: list[dict] = []
        self.decision_trace = Mock(side_effect=lambda limit: self.rows[:limit])
        app = FastAPI()
        app.state.optimizer = SimpleNamespace(decision_trace=self.decision_trace)
        app.include_router(api.router, prefix="/api")
        settings = SimpleNamespace(
            ui_api_key=HEADERS["x-api-key"], require_api_key_for_config_read=True,
            allow_loopback_without_api_key=True, require_api_key_for_all_mutations=True,
        )
        auth_patch = patch.object(api, "settings", settings)
        auth_patch.start()
        self.addCleanup(auth_patch.stop)
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, client=("203.0.113.8", 1234)),
            base_url="http://test",
        )
        self.addAsyncCleanup(self.client.aclose)

    async def test_500_large_rows_keep_preview_small_and_full_export_complete(self) -> None:
        payload = "trace details " * 750
        for index in range(500):
            self.rows.append({
                "ts": (NOW - timedelta(seconds=index)).isoformat(),
                "summary": {
                    "ems_mode": "Maximum Self Consumption",
                    "outcome_reason": "verified forecast allows charge",
                    "export_limit_kw": 0,
                    "ess_charge_limit_kw": 5.25,
                },
                "application": {"status": "applied", "details": payload},
                "state": {"diagnostic": payload},
                "values": {
                    "solar_provider_state": "VALID",
                    "solar_provider_reason": "provider_clean_restart_revalidated",
                    "solar_provider_verified_polled": NOW.isoformat(),
                    "solar_provider_deadline": (NOW + timedelta(minutes=30)).isoformat(),
                    "internal": payload,
                },
                "gates": {"sample": True},
            })

        preview = await self.client.get(PREVIEW_PATH, headers=HEADERS)
        self.assertEqual(preview.status_code, 200)
        self.assertLess(len(preview.content), 12_000)
        rows = preview.json()["rows"]
        self.assertEqual(len(rows), 20)
        self.assertEqual([row["ts"] for row in rows], [row["ts"] for row in self.rows[:20]])
        self.assertEqual(rows[0], {
            "ts": NOW.isoformat(),
            "ems_mode": "Maximum Self Consumption",
            "outcome_reason": "verified forecast allows charge",
            "export_limit_kw": 0,
            "ess_charge_limit_kw": 5.25,
            "application_status": "applied",
            "solar_provider_state": "VALID",
            "solar_provider_reason": "provider_clean_restart_revalidated",
            "solar_provider_verified_polled": NOW.isoformat(),
            "solar_provider_deadline": (NOW + timedelta(minutes=30)).isoformat(),
        })

        wrapped = await self.client.get(TRACE_PATH, params={"limit": 1}, headers=HEADERS)
        self.assertEqual(wrapped.json(), {"rows": self.rows[:1]})
        export = await self.client.get(TRACE_PATH, params={"limit": 500, "as_array": "true"}, headers=HEADERS)
        self.assertEqual(export.status_code, 200)
        self.assertEqual(export.json(), self.rows)
        self.assertGreater(len(export.content), 10_000_000)
        self.assertEqual(self.decision_trace.call_args_list, [call(limit=20), call(limit=1), call(limit=500)])

    async def test_preview_bounds_text_and_discards_invalid_values(self) -> None:
        self.rows.extend([
            {
                "ts": "t" * 1_000,
                "summary": {
                    "ems_mode": {"nested": "ignored"},
                    "outcome_reason": "c" * 10_000,
                    "export_limit_kw": float("inf"),
                    "ess_charge_limit_kw": 1 << 4096,
                },
                "application": "invalid",
                "values": {
                    "solar_provider_state": "v" * 1_000,
                    "solar_provider_verified_polled": ["invalid"],
                },
            },
            {"summary": {"export_limit_kw": True, "ess_charge_limit_kw": "22"}, "values": None},
        ])
        result = await self.client.get(PREVIEW_PATH, headers=HEADERS)
        self.assertEqual(result.status_code, 200)
        first, second = result.json()["rows"]
        self.assertEqual(first.pop("ts"), "t" * 80)
        self.assertEqual(first.pop("outcome_reason"), "c" * 240)
        self.assertEqual(first.pop("solar_provider_state"), "v" * 80)
        self.assertTrue(all(value is None for value in first.values()))
        self.assertTrue(all(value is None for value in second.values()))

    async def test_trace_endpoints_share_read_authorization_and_limits(self) -> None:
        for url in (PREVIEW_PATH, TRACE_PATH, f"{TRACE_PATH}?as_array=true"):
            with self.subTest(url=url):
                denied = await self.client.get(url, headers={"x-ingress-path": "/forged"})
                self.assertEqual(denied.status_code, 401)
        self.decision_trace.assert_not_called()

        preview = await self.client.get(PREVIEW_PATH, headers=HEADERS)
        self.assertEqual(preview.json(), {"rows": []})
        maximum = await self.client.get(TRACE_PATH, params={"limit": 4000, "as_array": "true"}, headers=HEADERS)
        self.assertEqual(maximum.json(), [])
        minimum = await self.client.get(TRACE_PATH, params={"limit": -5}, headers=HEADERS)
        self.assertEqual(minimum.json(), {"rows": []})
        self.assertEqual(self.decision_trace.call_args_list, [call(limit=20), call(limit=2000), call(limit=1)])
