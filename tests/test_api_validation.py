from __future__ import annotations

import asyncio
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import ValidationError

from app.config import Settings
from app.routers.api import (
    ConfigBatchUpdateRequest,
    ConfigUpdateRequest,
    _config_key_to_env_var,
    _sanitize_preset_payload,
    _validate_config_value,
    get_config,
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
    def test_forecast_observation_age_default_and_persistence_key_are_unchanged(self):
        self.assertEqual(600.0, Settings().hvac_solar_forecast_max_age_seconds)
        self.assertEqual("HVAC_SOLAR_FORECAST_MAX_AGE_SECONDS", _config_key_to_env_var("hvac_solar_forecast_max_age_seconds"))
        self.assertEqual("SOLCAST_API_LAST_POLLED_SENSOR", _config_key_to_env_var("solcast_api_last_polled_sensor"))

    def test_forecast_observation_age_single_and_batch_reject_invalid_atomically(self):
        key = "hvac_solar_forecast_max_age_seconds"
        for value in (0, -1, float("nan"), float("inf"), -float("inf"), "bad"):
            for batch in (False, True):
                with self.subTest(value=value, batch=batch):
                    cfg = Settings()
                    old = cfg.forecast_safety_charging
                    with self.assertRaises(HTTPException):
                        if batch:
                            self._batch_update(cfg, [("forecast_safety_charging", 1.5), (key, value)])
                        else:
                            self._single_update(cfg, key, value)
                    self.assertEqual(600.0, getattr(cfg, key))
                    self.assertEqual(old, cfg.forecast_safety_charging)

    def test_forecast_observation_age_runtime_updates_and_persistence(self):
        cfg = Settings()
        key = "hvac_solar_forecast_max_age_seconds"
        self._single_update(cfg, key, 601.5)
        self.assertEqual(601.5, getattr(cfg, key))
        self._batch_update(cfg, [(key, 720)])
        with patch("app.routers.api._persist_config_keys_to_env", return_value=[key]) as persist:
            asyncio.run(update_config(self._request(cfg), ConfigUpdateRequest(key=key, value=800, persist=True)))
        persist.assert_called_once_with(cfg, [key], {key: 800.0})
        self.assertEqual(800.0, getattr(cfg, key))

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

    def test_evening_boost_min_feedin_price_api_accepts_floor_and_higher(self) -> None:
        cfg = Settings(evening_boost_min_feedin_price=0.01)

        floor_response = self._single_update(
            cfg,
            "evening_boost_min_feedin_price",
            0.01,
        )
        positive_response = self._single_update(
            cfg,
            "evening_boost_min_feedin_price",
            0.025,
        )

        self.assertTrue(floor_response["ok"])
        self.assertTrue(positive_response["ok"])
        self.assertEqual(0.025, cfg.evening_boost_min_feedin_price)

    def test_evening_boost_min_feedin_price_api_rejects_below_floor_and_nonfinite_without_mutation(
        self,
    ) -> None:
        invalid_values = (
            (0.009, "must be greater than or equal to 0.01"),
            (0.0, "must be greater than or equal to 0.01"),
            (-0.001, "must be greater than or equal to 0.01"),
            (float("nan"), "must be a finite number"),
            (float("inf"), "must be a finite number"),
            (float("-inf"), "must be a finite number"),
        )
        for value, expected_error in invalid_values:
            with self.subTest(value=value):
                cfg = Settings(evening_boost_min_feedin_price=0.01)

                with self.assertRaises(HTTPException) as raised:
                    self._single_update(
                        cfg,
                        "evening_boost_min_feedin_price",
                        value,
                    )

                self.assertEqual(422, raised.exception.status_code)
                self.assertEqual(
                    {
                        "message": "Validation failed",
                        "field_errors": [
                            {
                                "key": "evening_boost_min_feedin_price",
                                "error": expected_error,
                            }
                        ],
                    },
                    raised.exception.detail,
                )
                self.assertEqual(0.01, cfg.evening_boost_min_feedin_price)

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

    def test_solar_surplus_forecast_safety_factor_default_is_1_20(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            cfg = Settings(_env_file=None)

        self.assertEqual(1.20, cfg.solar_surplus_forecast_safety_factor)

    def test_solar_surplus_forecast_safety_factor_loads_expected_env_key(self) -> None:
        with patch.dict(
            "os.environ",
            {"SOLAR_SURPLUS_FORECAST_SAFETY_FACTOR": "1.35"},
            clear=True,
        ):
            cfg = Settings(_env_file=None)

        self.assertEqual(1.35, cfg.solar_surplus_forecast_safety_factor)

    def test_solar_surplus_forecast_safety_factor_model_accepts_valid_values(self) -> None:
        for value in (1.0, 1.25, 1_000_000.0):
            with self.subTest(value=value):
                cfg = Settings(solar_surplus_forecast_safety_factor=value)
                self.assertEqual(value, cfg.solar_surplus_forecast_safety_factor)

    def test_solar_surplus_forecast_safety_factor_model_rejects_invalid_values(self) -> None:
        for value in (
            0.99,
            float("nan"),
            float("inf"),
            float("-inf"),
            "not-a-number",
            True,
        ):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    Settings(solar_surplus_forecast_safety_factor=value)

    def test_single_solar_surplus_forecast_safety_factor_accepts_valid_value(self) -> None:
        cfg = Settings(solar_surplus_forecast_safety_factor=1.20)

        response = self._single_update(
            cfg,
            "solar_surplus_forecast_safety_factor",
            1.25,
        )

        self.assertTrue(response["ok"])
        self.assertEqual(1.25, cfg.solar_surplus_forecast_safety_factor)

    def test_single_solar_surplus_forecast_safety_factor_accepts_exactly_one(self) -> None:
        cfg = Settings(solar_surplus_forecast_safety_factor=1.20)

        response = self._single_update(
            cfg,
            "solar_surplus_forecast_safety_factor",
            1.0,
        )

        self.assertTrue(response["ok"])
        self.assertEqual(1.0, cfg.solar_surplus_forecast_safety_factor)

    def test_single_solar_surplus_forecast_safety_factor_rejects_below_one_without_mutation(self) -> None:
        cfg = Settings(solar_surplus_forecast_safety_factor=1.20)

        with self.assertRaises(HTTPException) as raised:
            self._single_update(
                cfg,
                "solar_surplus_forecast_safety_factor",
                0.99,
            )

        self.assertEqual(422, raised.exception.status_code)
        self.assertEqual(1.20, cfg.solar_surplus_forecast_safety_factor)

    def test_single_solar_surplus_forecast_safety_factor_rejects_nonfinite_without_mutation(self) -> None:
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                cfg = Settings(solar_surplus_forecast_safety_factor=1.20)

                with self.assertRaises(HTTPException) as raised:
                    self._single_update(
                        cfg,
                        "solar_surplus_forecast_safety_factor",
                        value,
                    )

                self.assertEqual(422, raised.exception.status_code)
                self.assertEqual(1.20, cfg.solar_surplus_forecast_safety_factor)

    def test_single_solar_surplus_forecast_safety_factor_rejects_non_numeric_without_mutation(self) -> None:
        for value in ("not-a-number", True):
            with self.subTest(value=value):
                cfg = Settings(solar_surplus_forecast_safety_factor=1.20)

                with self.assertRaises(HTTPException) as raised:
                    self._single_update(
                        cfg,
                        "solar_surplus_forecast_safety_factor",
                        value,
                    )

                self.assertEqual(400, raised.exception.status_code)
                self.assertEqual(1.20, cfg.solar_surplus_forecast_safety_factor)

    def test_batch_invalid_solar_surplus_forecast_safety_factor_is_atomic(self) -> None:
        cfg = Settings(
            export_limit_low=5.0,
            solar_surplus_forecast_safety_factor=1.20,
        )

        with self.assertRaises(HTTPException) as raised:
            self._batch_update(
                cfg,
                [
                    ("export_limit_low", 3.0),
                    ("solar_surplus_forecast_safety_factor", 0.99),
                ],
            )

        self.assertEqual(422, raised.exception.status_code)
        self.assertEqual(5.0, cfg.export_limit_low)
        self.assertEqual(1.20, cfg.solar_surplus_forecast_safety_factor)

    def test_solar_surplus_forecast_safety_factor_persists_with_expected_env_key(self) -> None:
        cfg = Settings(solar_surplus_forecast_safety_factor=1.20)
        request = self._request(cfg)
        env_key = "SOLAR_SURPLUS_FORECAST_SAFETY_FACTOR"

        self.assertEqual(
            env_key,
            _config_key_to_env_var("solar_surplus_forecast_safety_factor"),
        )
        with patch(
            "app.routers.api._persist_config_keys_to_env",
            return_value=[env_key],
        ) as persist:
            response = asyncio.run(
                update_config(
                    request,
                    ConfigUpdateRequest(
                        key="solar_surplus_forecast_safety_factor",
                        value=1.25,
                        persist=True,
                    ),
                )
            )

        persist.assert_called_once_with(
            cfg,
            ["solar_surplus_forecast_safety_factor"],
            {"solar_surplus_forecast_safety_factor": 1.25},
        )
        self.assertEqual(1.25, cfg.solar_surplus_forecast_safety_factor)
        self.assertTrue(response["persisted"])
        self.assertEqual([env_key], response["persisted_keys"])

    def test_morning_slow_physical_export_settings_default_disabled(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            cfg = Settings(_env_file=None)

        self.assertEqual(0.0, cfg.grid_connection_export_limit_kw)
        self.assertEqual(0.0, cfg.morning_slow_physical_export_headroom_kw)

    def test_morning_slow_physical_export_settings_load_expected_env_keys(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "GRID_CONNECTION_EXPORT_LIMIT_KW": "15.0",
                "MORNING_SLOW_PHYSICAL_EXPORT_HEADROOM_KW": "0.5",
            },
            clear=True,
        ):
            cfg = Settings(_env_file=None)

        self.assertEqual(15.0, cfg.grid_connection_export_limit_kw)
        self.assertEqual(0.5, cfg.morning_slow_physical_export_headroom_kw)

    def test_morning_slow_physical_export_model_accepts_disabled_partial_and_site_pair(self) -> None:
        for physical_limit_kw, headroom_kw in (
            (0.0, 0.0),
            (15.0, 0.0),
            (0.0, 0.5),
            (15.0, 0.5),
        ):
            with self.subTest(
                physical_limit_kw=physical_limit_kw,
                headroom_kw=headroom_kw,
            ):
                cfg = Settings(
                    grid_connection_export_limit_kw=physical_limit_kw,
                    morning_slow_physical_export_headroom_kw=headroom_kw,
                )
                self.assertEqual(
                    physical_limit_kw,
                    cfg.grid_connection_export_limit_kw,
                )
                self.assertEqual(
                    headroom_kw,
                    cfg.morning_slow_physical_export_headroom_kw,
                )

    def test_morning_slow_physical_export_model_rejects_invalid_values(self) -> None:
        invalid_pairs = (
            (-0.1, 0.0),
            (0.0, -0.1),
            (15.0, 15.0),
            (15.0, 15.1),
            (float("nan"), 0.0),
            (float("inf"), 0.0),
            (True, 0.0),
            (15.0, True),
        )
        for physical_limit_kw, headroom_kw in invalid_pairs:
            with self.subTest(
                physical_limit_kw=physical_limit_kw,
                headroom_kw=headroom_kw,
            ):
                with self.assertRaises(ValidationError):
                    Settings(
                        grid_connection_export_limit_kw=physical_limit_kw,
                        morning_slow_physical_export_headroom_kw=headroom_kw,
                    )

    def test_single_morning_slow_physical_export_updates_preserve_partial_disablement(self) -> None:
        cfg = Settings()

        first = self._single_update(
            cfg,
            "morning_slow_physical_export_headroom_kw",
            "0.5",
        )
        second = self._single_update(
            cfg,
            "grid_connection_export_limit_kw",
            "15.0",
        )

        self.assertTrue(first["ok"])
        self.assertTrue(second["ok"])
        self.assertEqual(15.0, cfg.grid_connection_export_limit_kw)
        self.assertEqual(0.5, cfg.morning_slow_physical_export_headroom_kw)

    def test_single_morning_slow_physical_export_rejects_invalid_without_mutation(self) -> None:
        for key, value in (
            ("grid_connection_export_limit_kw", -0.1),
            ("morning_slow_physical_export_headroom_kw", -0.1),
            ("morning_slow_physical_export_headroom_kw", 15.0),
            ("morning_slow_physical_export_headroom_kw", 15.1),
        ):
            with self.subTest(key=key, value=value):
                cfg = Settings(
                    grid_connection_export_limit_kw=15.0,
                    morning_slow_physical_export_headroom_kw=0.5,
                )

                with self.assertRaises(HTTPException) as raised:
                    self._single_update(cfg, key, value)

                self.assertEqual(422, raised.exception.status_code)
                self.assertEqual(15.0, cfg.grid_connection_export_limit_kw)
                self.assertEqual(
                    0.5,
                    cfg.morning_slow_physical_export_headroom_kw,
                )

    def test_batch_morning_slow_physical_export_accepts_and_persists_site_pair(self) -> None:
        cfg = Settings()
        request = self._request(cfg)
        expected_env_keys = [
            "GRID_CONNECTION_EXPORT_LIMIT_KW",
            "MORNING_SLOW_PHYSICAL_EXPORT_HEADROOM_KW",
        ]

        with patch(
            "app.routers.api._persist_config_keys_to_env",
            return_value=expected_env_keys,
        ) as persist:
            response = asyncio.run(
                update_config_batch(
                    request,
                    ConfigBatchUpdateRequest(
                        updates=[
                            ConfigUpdateRequest(
                                key="grid_connection_export_limit_kw",
                                value=15.0,
                            ),
                            ConfigUpdateRequest(
                                key="morning_slow_physical_export_headroom_kw",
                                value=0.5,
                            ),
                        ],
                        persist=True,
                    ),
                )
            )

        persist.assert_called_once_with(
            cfg,
            [
                "grid_connection_export_limit_kw",
                "morning_slow_physical_export_headroom_kw",
            ],
            {
                "grid_connection_export_limit_kw": 15.0,
                "morning_slow_physical_export_headroom_kw": 0.5,
            },
        )
        self.assertEqual(15.0, cfg.grid_connection_export_limit_kw)
        self.assertEqual(0.5, cfg.morning_slow_physical_export_headroom_kw)
        self.assertEqual(expected_env_keys, response["persisted_keys"])
        round_trip = asyncio.run(get_config(request))
        self.assertEqual(15.0, round_trip["grid_connection_export_limit_kw"])
        self.assertEqual(
            0.5,
            round_trip["morning_slow_physical_export_headroom_kw"],
        )

    def test_single_morning_slow_physical_export_updates_persist_expected_env_keys(self) -> None:
        cfg = Settings()
        request = self._request(cfg)

        with patch(
            "app.routers.api._persist_config_keys_to_env",
            side_effect=[
                ["GRID_CONNECTION_EXPORT_LIMIT_KW"],
                ["MORNING_SLOW_PHYSICAL_EXPORT_HEADROOM_KW"],
            ],
        ) as persist:
            limit_response = asyncio.run(
                update_config(
                    request,
                    ConfigUpdateRequest(
                        key="grid_connection_export_limit_kw",
                        value=15.0,
                        persist=True,
                    ),
                )
            )
            headroom_response = asyncio.run(
                update_config(
                    request,
                    ConfigUpdateRequest(
                        key="morning_slow_physical_export_headroom_kw",
                        value=0.5,
                        persist=True,
                    ),
                )
            )

        self.assertEqual(2, persist.call_count)
        persist.assert_any_call(
            cfg,
            ["grid_connection_export_limit_kw"],
            {"grid_connection_export_limit_kw": 15.0},
        )
        persist.assert_any_call(
            cfg,
            ["morning_slow_physical_export_headroom_kw"],
            {"morning_slow_physical_export_headroom_kw": 0.5},
        )
        self.assertEqual(
            ["GRID_CONNECTION_EXPORT_LIMIT_KW"],
            limit_response["persisted_keys"],
        )
        self.assertEqual(
            ["MORNING_SLOW_PHYSICAL_EXPORT_HEADROOM_KW"],
            headroom_response["persisted_keys"],
        )
        self.assertEqual(15.0, cfg.grid_connection_export_limit_kw)
        self.assertEqual(0.5, cfg.morning_slow_physical_export_headroom_kw)

    def test_batch_morning_slow_physical_export_rejects_invalid_pair_atomically(self) -> None:
        cfg = Settings(
            export_limit_low=5.0,
            grid_connection_export_limit_kw=15.0,
            morning_slow_physical_export_headroom_kw=0.5,
        )

        with self.assertRaises(HTTPException) as raised:
            self._batch_update(
                cfg,
                [
                    ("export_limit_low", 3.0),
                    ("grid_connection_export_limit_kw", 10.0),
                    ("morning_slow_physical_export_headroom_kw", 10.0),
                ],
            )

        self.assertEqual(422, raised.exception.status_code)
        self.assertEqual(5.0, cfg.export_limit_low)
        self.assertEqual(15.0, cfg.grid_connection_export_limit_kw)
        self.assertEqual(0.5, cfg.morning_slow_physical_export_headroom_kw)

    def test_morning_slow_physical_export_ui_and_env_wording_distinguish_ceiling(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        template = (project_root / "templates" / "index.html").read_text(
            encoding="utf-8"
        )
        env_example = (project_root / ".env.example").read_text(encoding="utf-8")

        self.assertIn("Physical Grid Connection Export Limit kW", template)
        self.assertIn("not the Sigenergy export-control ceiling", template)
        self.assertIn("GRID_CONNECTION_EXPORT_LIMIT_KW=0.0", env_example)
        self.assertIn(
            "MORNING_SLOW_PHYSICAL_EXPORT_HEADROOM_KW=0.0",
            env_example,
        )

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
