from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import ValidationError

from app.config import Settings
from app.routers.api import (
    ConfigBatchUpdateRequest,
    ConfigUpdateRequest,
    _config_key_to_env_var,
    _solar_surplus_status,
    get_config,
    update_config,
    update_config_batch,
)


ROOT = Path(__file__).resolve().parents[1]
MARGIN_KEY = "solar_surplus_fill_deadline_margin_minutes"
MARGIN_ENV = "SOLAR_SURPLUS_FILL_DEADLINE_MARGIN_MINUTES"


class SolarFillDeadlineConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.environment = patch.dict("os.environ", {}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    @staticmethod
    def settings(**updates: object) -> Settings:
        return Settings(_env_file=None, **updates)

    @staticmethod
    def request(cfg: Settings) -> SimpleNamespace:
        optimizer = SimpleNamespace(
            cfg=cfg,
            record_audit_event=lambda **event: None,
            refresh_config_time_warnings=lambda: None,
        )
        return SimpleNamespace(
            app=SimpleNamespace(state=SimpleNamespace(optimizer=optimizer)),
            client=SimpleNamespace(host="127.0.0.1"),
            headers={},
        )

    def test_defaults_keep_solar_margin_separate_from_forecast_and_physical_limit(self):
        cfg = self.settings()
        self.assertEqual(60.0, getattr(cfg, MARGIN_KEY))
        self.assertEqual(1.20, cfg.solar_surplus_forecast_safety_factor)
        self.assertEqual(0.0, cfg.grid_connection_export_limit_kw)
        self.assertEqual(0.0, cfg.morning_slow_physical_export_headroom_kw)

    def test_environment_loads_dedicated_key_and_preserves_morning_slow(self):
        with patch.dict("os.environ", {MARGIN_ENV: "90.5"}):
            cfg = self.settings(morning_slow_charge_sunset_cutoff=3.0)
        self.assertEqual(90.5, getattr(cfg, MARGIN_KEY))
        self.assertEqual(3.0, cfg.morning_slow_charge_sunset_cutoff)
        self.assertEqual(MARGIN_ENV, _config_key_to_env_var(MARGIN_KEY))

    def test_model_accepts_zero_fractional_and_large_finite_margins(self):
        for value in (0.0, 60.0, 60.5, 10_000.0):
            with self.subTest(value=value):
                cfg = self.settings(**{MARGIN_KEY: value})
                self.assertEqual(value, getattr(cfg, MARGIN_KEY))

    def test_model_rejects_negative_nonfinite_boolean_and_nonnumeric_margins(self):
        for value in (-0.01, float("nan"), float("inf"), -float("inf"), True, False, "bad"):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    self.settings(**{MARGIN_KEY: value})

    def test_single_and_batch_runtime_updates_are_readable_and_persist_expected_key(self):
        cfg = self.settings()
        request = self.request(cfg)
        for batch, value in ((False, "0"), (True, "90.5")):
            with self.subTest(batch=batch):
                with patch(
                    "app.routers.api._persist_config_keys_to_env",
                    return_value=[MARGIN_ENV],
                ) as persist:
                    update = ConfigUpdateRequest(key=MARGIN_KEY, value=value, persist=True)
                    if batch:
                        response = asyncio.run(update_config_batch(
                            request,
                            ConfigBatchUpdateRequest(updates=[update], persist=True),
                        ))
                    else:
                        response = asyncio.run(update_config(request, update))
                persist.assert_called_once_with(cfg, [MARGIN_KEY], {MARGIN_KEY: float(value)})
                self.assertTrue(response["ok"])
                self.assertEqual([MARGIN_ENV], response["persisted_keys"])
                self.assertEqual(float(value), getattr(cfg, MARGIN_KEY))
                self.assertEqual(float(value), asyncio.run(get_config(request))[MARGIN_KEY])
                self.assertEqual(1.20, cfg.solar_surplus_forecast_safety_factor)
                self.assertEqual(1.0, cfg.morning_slow_charge_sunset_cutoff)
                self.assertEqual(0.0, cfg.grid_connection_export_limit_kw)

    def test_invalid_single_and_batch_updates_do_not_mutate_or_persist(self):
        for value in (-1, float("nan"), float("inf"), -float("inf"), True, False, "bad"):
            for batch in (False, True):
                with self.subTest(value=value, batch=batch):
                    cfg = self.settings()
                    request = self.request(cfg)
                    update = ConfigUpdateRequest(key=MARGIN_KEY, value=value, persist=True)
                    with patch("app.routers.api._persist_config_keys_to_env") as persist:
                        with self.assertRaises(HTTPException) as raised:
                            if batch:
                                asyncio.run(update_config_batch(
                                    request,
                                    ConfigBatchUpdateRequest(
                                        updates=[
                                            ConfigUpdateRequest(key="forecast_safety_charging", value=1.5),
                                            update,
                                        ],
                                        persist=True,
                                    ),
                                ))
                            else:
                                asyncio.run(update_config(request, update))
                    expected_status = 422 if batch or not isinstance(value, (bool, str)) else 400
                    self.assertEqual(expected_status, raised.exception.status_code)
                    self.assertEqual(60.0, getattr(cfg, MARGIN_KEY))
                    self.assertEqual(1.25, cfg.forecast_safety_charging)
                    persist.assert_not_called()

    def test_ui_describes_independent_fill_margin_and_shared_physical_evidence(self):
        template = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        self.assertTrue(
            f"['{MARGIN_KEY}', 'Solar Fill Deadline Margin (minutes)', 'number', '1']" in template,
            "Solar settings must expose the dedicated fill deadline margin",
        )
        help_line = next(line for line in template.splitlines() if line.strip().startswith(f"{MARGIN_KEY}:"))
        for wording in ("same-day sunset", "60", "0", "Morning Slow", "normal safe MSC charging"):
            with self.subTest(wording=wording):
                self.assertIn(wording, help_line)
        physical_help = next(line for line in template.splitlines() if line.strip().startswith("grid_connection_export_limit_kw:"))
        self.assertIn("Solar", physical_help)
        self.assertIn("Morning Slow", physical_help)
        self.assertIn("not the Sigenergy export-control ceiling", physical_help)
        self.assertIn("0", physical_help)

    def test_example_environment_keeps_approved_defaults(self):
        example = (ROOT / ".env.example").read_text(encoding="utf-8")
        self.assertTrue(f"{MARGIN_ENV}=60" in example, "Example must include the 60-minute default")
        self.assertIn("SOLAR_SURPLUS_FORECAST_SAFETY_FACTOR=1.20", example)
        self.assertIn("GRID_CONNECTION_EXPORT_LIMIT_KW=0.0", example)
        self.assertIn("MORNING_SLOW_PHYSICAL_EXPORT_HEADROOM_KW=0.0", example)

    def test_status_copies_fill_deadline_and_relief_evidence_without_recalculation(self):
        trace_values = {
            "solar_charge_ceiling_baseline_kw": 1.25,
            "solar_charge_ceiling_fill_deadline_ts": 1791356400.0,
            "solar_charge_ceiling_fill_deadline_margin_minutes": 60.0,
            "solar_charge_ceiling_requested_kw": 2.05,
            "solar_physical_relief_kw": 0.8,
            "solar_physical_relief_reason": "confirmed_saturation_increase",
            "solar_physical_relief_export_kw": 14.95,
            "solar_physical_relief_limit_kw": 15.0,
            "solar_physical_relief_confirmations": 1,
        }
        decision = SimpleNamespace(
            solar_surplus_policy_active=True,
            trace_values=trace_values,
            trace_gates={
                "solar_physical_relief_active": True,
                "solar_physical_relief_flow_trusted": True,
            },
        )
        diagnostics = _solar_surplus_status(decision, manual_active=False)["solar_surplus_diagnostics"]
        for key, value in trace_values.items():
            with self.subTest(key=key):
                self.assertEqual(value, diagnostics[key])
        self.assertIs(diagnostics["solar_physical_relief_active"], True)
        self.assertIs(diagnostics["solar_physical_relief_flow_trusted"], True)

    def test_missing_status_evidence_is_nullable_and_manual_suppresses_relief_active(self):
        diagnostics = _solar_surplus_status(None, manual_active=False)["solar_surplus_diagnostics"]
        self.assertIsNone(diagnostics["solar_charge_ceiling_baseline_kw"])
        self.assertIsNone(diagnostics["solar_charge_ceiling_fill_deadline_ts"])
        self.assertIsNone(diagnostics["solar_physical_relief_active"])
        decision = SimpleNamespace(
            solar_surplus_policy_active=True,
            trace_values={"solar_physical_relief_kw": 0.4},
            trace_gates={"solar_physical_relief_active": True},
        )
        diagnostics = _solar_surplus_status(decision, manual_active=True)["solar_surplus_diagnostics"]
        self.assertIs(diagnostics["solar_physical_relief_active"], False)


if __name__ == "__main__":
    unittest.main()
