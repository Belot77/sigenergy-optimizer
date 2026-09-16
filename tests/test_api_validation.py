from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from app.config import Settings
from app.routers.api import (
    ConfigBatchUpdateRequest,
    ConfigUpdateRequest,
    _sanitize_preset_payload,
    _validate_config_value,
    update_config,
    update_config_batch,
)


class _DummyCfg:
    daily_summary_time = "23:55"


class _DummyOptimizer:
    def __init__(self, cfg: Settings) -> None:
        self.cfg = cfg
        self.audit_events: list[dict[str, object]] = []
        self.config_warnings_refreshed = False

    def record_audit_event(self, **event: object) -> None:
        self.audit_events.append(event)

    def refresh_config_time_warnings(self) -> None:
        self.config_warnings_refreshed = True


class ApiValidationTests(unittest.TestCase):
    @staticmethod
    def _request(cfg: Settings) -> SimpleNamespace:
        optimizer = _DummyOptimizer(cfg)
        return SimpleNamespace(
            app=SimpleNamespace(
                state=SimpleNamespace(optimizer=optimizer),
            ),
            client=SimpleNamespace(host="127.0.0.1"),
            headers={},
        )

    def _single_update(
        self,
        cfg: Settings,
        key: str,
        value: object,
    ) -> dict[str, object]:
        return asyncio.run(
            update_config(
                self._request(cfg),
                ConfigUpdateRequest(key=key, value=value),
            )
        )

    def _batch_update(
        self,
        cfg: Settings,
        updates: list[tuple[str, object]],
    ) -> dict[str, object]:
        return asyncio.run(
            update_config_batch(
                self._request(cfg),
                ConfigBatchUpdateRequest(
                    updates=[
                        ConfigUpdateRequest(key=key, value=value)
                        for key, value in updates
                    ]
                ),
            )
        )

    def test_validate_config_value_time(self) -> None:
        cfg = _DummyCfg()
        err = _validate_config_value(cfg, "daily_summary_time", "25:99")
        self.assertIsNotNone(err)

    def test_validate_config_value_limit_range(self) -> None:
        cfg = _DummyCfg()
        err = _validate_config_value(cfg, "export_limit_low", 9999)
        self.assertIsNotNone(err)

    def test_sanitize_preset_payload_rejects_empty(self) -> None:
        with self.assertRaises(ValueError):
            _sanitize_preset_payload({})

    def test_sanitize_preset_payload_allows_known_keys(self) -> None:
        payload = _sanitize_preset_payload(
            {
                "export_limit_low": 3,
                "import_limit_low": 5,
                "unknown_key": 999,
            }
        )
        self.assertIn("export_limit_low", payload)
        self.assertIn("import_limit_low", payload)
        self.assertNotIn("unknown_key", payload)

    def test_single_solar_surplus_stop_margin_accepts_valid_value(self) -> None:
        cfg = Settings(
            solar_surplus_min_pv_margin=0.5,
            solar_surplus_stop_pv_margin=0.2,
        )

        response = self._single_update(
            cfg,
            "solar_surplus_stop_pv_margin",
            0.3,
        )

        self.assertTrue(response["ok"])
        self.assertEqual(0.3, cfg.solar_surplus_stop_pv_margin)

    def test_single_runtime_only_update_preserves_existing_behavior(self) -> None:
        cfg = Settings(export_limit_low=5.0)

        response = self._single_update(cfg, "export_limit_low", "3.5")

        self.assertEqual(3.5, cfg.export_limit_low)
        self.assertEqual(
            {
                "ok": True,
                "key": "export_limit_low",
                "value": 3.5,
                "persisted": False,
                "persisted_keys": [],
            },
            response,
        )

    def test_single_persistent_update_commits_runtime_after_persistence(self) -> None:
        cfg = Settings(export_limit_low=5.0)
        request = self._request(cfg)

        with patch(
            "app.routers.api._persist_config_keys_to_env",
            return_value=["EXPORT_LIMIT_LOW"],
        ) as persist:
            response = asyncio.run(
                update_config(
                    request,
                    ConfigUpdateRequest(
                        key="export_limit_low",
                        value="3.5",
                        persist=True,
                    ),
                )
            )

        persist.assert_called_once_with(
            cfg,
            ["export_limit_low"],
            {"export_limit_low": 3.5},
        )
        self.assertEqual(3.5, cfg.export_limit_low)
        self.assertTrue(response["persisted"])
        self.assertEqual(["EXPORT_LIMIT_LOW"], response["persisted_keys"])

    def test_single_persistence_failure_leaves_runtime_unchanged(self) -> None:
        cfg = Settings(export_limit_low=5.0)
        request = self._request(cfg)

        with patch(
            "app.routers.api._persist_config_keys_to_env",
            side_effect=OSError("persistence unavailable"),
        ):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(
                    update_config(
                        request,
                        ConfigUpdateRequest(
                            key="export_limit_low",
                            value=3.5,
                            persist=True,
                        ),
                    )
                )

        self.assertEqual(500, raised.exception.status_code)
        self.assertEqual(5.0, cfg.export_limit_low)
        self.assertFalse(request.app.state.optimizer.config_warnings_refreshed)

    def test_batch_persistence_failure_leaves_all_runtime_values_unchanged(self) -> None:
        cfg = Settings(export_limit_low=5.0, import_limit_low=6.0)
        request = self._request(cfg)

        with patch(
            "app.routers.api._persist_config_keys_to_env",
            side_effect=OSError("persistence unavailable"),
        ):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(
                    update_config_batch(
                        request,
                        ConfigBatchUpdateRequest(
                            updates=[
                                ConfigUpdateRequest(key="export_limit_low", value=3.0),
                                ConfigUpdateRequest(key="import_limit_low", value=4.0),
                            ],
                            persist=True,
                        ),
                    )
                )

        self.assertEqual(500, raised.exception.status_code)
        self.assertEqual(5.0, cfg.export_limit_low)
        self.assertEqual(6.0, cfg.import_limit_low)
        self.assertFalse(request.app.state.optimizer.config_warnings_refreshed)

    def test_batch_persistent_update_preserves_reported_keys(self) -> None:
        cfg = Settings(export_limit_low=5.0, import_limit_low=6.0)
        request = self._request(cfg)

        with patch(
            "app.routers.api._persist_config_keys_to_env",
            return_value=["EXPORT_LIMIT_LOW", "IMPORT_LIMIT_LOW"],
        ):
            response = asyncio.run(
                update_config_batch(
                    request,
                    ConfigBatchUpdateRequest(
                        updates=[
                            ConfigUpdateRequest(key="export_limit_low", value=3.0),
                            ConfigUpdateRequest(key="import_limit_low", value=4.0),
                        ],
                        persist=True,
                    ),
                )
            )

        self.assertEqual(3.0, cfg.export_limit_low)
        self.assertEqual(4.0, cfg.import_limit_low)
        self.assertTrue(response["persisted"])
        self.assertEqual(
            ["EXPORT_LIMIT_LOW", "IMPORT_LIMIT_LOW"],
            response["persisted_keys"],
        )

    def test_batch_validation_failure_leaves_runtime_untouched(self) -> None:
        cfg = Settings(export_limit_low=5.0, import_limit_low=6.0)

        with self.assertRaises(HTTPException) as raised:
            self._batch_update(
                cfg,
                [
                    ("export_limit_low", 3.0),
                    ("import_limit_low", "not-a-number"),
                ],
            )

        self.assertEqual(422, raised.exception.status_code)
        self.assertEqual(5.0, cfg.export_limit_low)
        self.assertEqual(6.0, cfg.import_limit_low)

    def test_masked_placeholder_is_rejected_without_mutation_or_persistence(self) -> None:
        for batch in (False, True):
            with self.subTest(batch=batch):
                cfg = Settings(ha_token="real-token")
                request = self._request(cfg)
                with patch("app.routers.api._persist_config_keys_to_env") as persist:
                    with self.assertRaises(HTTPException) as raised:
                        if batch:
                            asyncio.run(
                                update_config_batch(
                                    request,
                                    ConfigBatchUpdateRequest(
                                        updates=[
                                            ConfigUpdateRequest(
                                                key="ha_token",
                                                value="****",
                                            )
                                        ],
                                        persist=True,
                                    ),
                                )
                            )
                        else:
                            asyncio.run(
                                update_config(
                                    request,
                                    ConfigUpdateRequest(
                                        key="ha_token",
                                        value="****",
                                        persist=True,
                                    ),
                                )
                            )

                self.assertEqual(422, raised.exception.status_code)
                self.assertEqual("real-token", cfg.ha_token)
                persist.assert_not_called()
                event = request.app.state.optimizer.audit_events[-1]
                if not batch:
                    self.assertEqual("****", event["old_value"])
                    self.assertEqual("****", event["new_value"])

    def test_secret_update_audit_remains_masked(self) -> None:
        cfg = Settings(ha_token="old-token")
        request = self._request(cfg)

        response = asyncio.run(
            update_config(
                request,
                ConfigUpdateRequest(key="ha_token", value="new-token"),
            )
        )

        event = request.app.state.optimizer.audit_events[-1]
        self.assertEqual("****", response["value"])
        self.assertEqual("****", event["old_value"])
        self.assertEqual("****", event["new_value"])

    def test_remote_config_update_still_requires_authentication(self) -> None:
        cfg = Settings(export_limit_low=5.0)
        request = self._request(cfg)
        request.client.host = "192.0.2.10"

        with self.assertRaises(HTTPException) as raised:
            asyncio.run(
                update_config(
                    request,
                    ConfigUpdateRequest(key="export_limit_low", value=3.0),
                )
            )

        self.assertIn(raised.exception.status_code, {401, 403})
        self.assertEqual(5.0, cfg.export_limit_low)

    def test_single_solar_surplus_stop_margin_rejects_negative_value(self) -> None:
        cfg = Settings(
            solar_surplus_min_pv_margin=0.5,
            solar_surplus_stop_pv_margin=0.2,
        )

        with self.assertRaises(HTTPException) as raised:
            self._single_update(cfg, "solar_surplus_stop_pv_margin", -0.1)

        self.assertEqual(422, raised.exception.status_code)
        self.assertEqual(0.2, cfg.solar_surplus_stop_pv_margin)

    def test_single_solar_surplus_stop_margin_rejects_value_above_start(self) -> None:
        cfg = Settings(
            solar_surplus_min_pv_margin=0.5,
            solar_surplus_stop_pv_margin=0.2,
        )

        with self.assertRaises(HTTPException) as raised:
            self._single_update(cfg, "solar_surplus_stop_pv_margin", 0.6)

        self.assertEqual(422, raised.exception.status_code)
        self.assertEqual(0.2, cfg.solar_surplus_stop_pv_margin)

    def test_single_solar_surplus_stop_margin_rejects_nonfinite_values(self) -> None:
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                cfg = Settings(
                    solar_surplus_min_pv_margin=0.5,
                    solar_surplus_stop_pv_margin=0.2,
                )

                with self.assertRaises(HTTPException) as raised:
                    self._single_update(cfg, "solar_surplus_stop_pv_margin", value)

                self.assertEqual(422, raised.exception.status_code)
                self.assertEqual(0.2, cfg.solar_surplus_stop_pv_margin)

    def test_batch_solar_surplus_margins_use_final_pair_regardless_of_order(self) -> None:
        cfg = Settings(
            solar_surplus_min_pv_margin=0.5,
            solar_surplus_stop_pv_margin=0.2,
        )

        response = self._batch_update(
            cfg,
            [
                ("solar_surplus_stop_pv_margin", 0.7),
                ("solar_surplus_min_pv_margin", 0.8),
            ],
        )

        self.assertTrue(response["ok"])
        self.assertEqual(0.8, cfg.solar_surplus_min_pv_margin)
        self.assertEqual(0.7, cfg.solar_surplus_stop_pv_margin)

    def test_batch_solar_surplus_margins_reject_invalid_final_pair_atomically(self) -> None:
        cfg = Settings(
            export_limit_low=5.0,
            solar_surplus_min_pv_margin=0.5,
            solar_surplus_stop_pv_margin=0.2,
        )

        with self.assertRaises(HTTPException) as raised:
            self._batch_update(
                cfg,
                [
                    ("export_limit_low", 3.0),
                    ("solar_surplus_stop_pv_margin", 0.45),
                    ("solar_surplus_min_pv_margin", 0.4),
                ],
            )

        self.assertEqual(422, raised.exception.status_code)
        self.assertEqual(5.0, cfg.export_limit_low)
        self.assertEqual(0.5, cfg.solar_surplus_min_pv_margin)
        self.assertEqual(0.2, cfg.solar_surplus_stop_pv_margin)

    def test_batch_lowering_start_margin_below_existing_stop_is_rejected(self) -> None:
        cfg = Settings(
            solar_surplus_min_pv_margin=0.5,
            solar_surplus_stop_pv_margin=0.2,
        )

        with self.assertRaises(HTTPException) as raised:
            self._batch_update(
                cfg,
                [("solar_surplus_min_pv_margin", 0.1)],
            )

        self.assertEqual(422, raised.exception.status_code)
        self.assertEqual(0.5, cfg.solar_surplus_min_pv_margin)
        self.assertEqual(0.2, cfg.solar_surplus_stop_pv_margin)


if __name__ == "__main__":
    unittest.main()
