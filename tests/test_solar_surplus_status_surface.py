from __future__ import annotations

import asyncio
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from app.config import Settings
from app.models import Decision, SolarState
from app.routers.api import get_status


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = ROOT / "templates" / "index.html"


class _ConnectedHA:
    async def ping(self) -> bool:
        return True


class SolarSurplusStatusSurfaceTests(unittest.TestCase):
    def _status(
        self,
        *,
        decision: Decision | None,
        state: SolarState | None = None,
    ) -> dict[str, object]:
        cfg = Settings(_env_file=None)
        optimizer = SimpleNamespace(
            cfg=cfg,
            last_state=state,
            last_decision=decision,
            ws_connected=True,
            runtime_signature="test",
            config_time_warnings=[],
            _manual_mode_override="",
        )
        request = SimpleNamespace(
            app=SimpleNamespace(
                state=SimpleNamespace(optimizer=optimizer, ha=_ConnectedHA())
            )
        )
        return asyncio.run(get_status(request))

    @staticmethod
    def _decision_with_trace() -> Decision:
        return Decision(
            solar_surplus_bypass=True,
            solar_surplus_policy_active=True,
            trace_gates={
                "solar_surplus_enabled": True,
                "solar_fit_at_least_one_cent": True,
                "solar_energy_budget_passed": True,
                "solar_detailed_timing_required": True,
                "solcast_detailed_source_trusted": True,
                "solar_detailed_forecast_coverage": True,
                "solar_timing_passed": True,
                "previous_cycle_solar_surplus_policy_owned": False,
                "solar_pv_load_observations_coherent": True,
            },
            trace_values={
                "solar_surplus_fail_reason": "active_final_solar_surplus_owner",
                "solar_measured_pv_surplus_kw": 9.876,
                "solar_surplus_threshold_kw": 0.5,
                "solar_remaining_forecast_kwh": 123.456,
                "solar_expected_remaining_load_kwh": 7.89,
                "solar_fill_need_to_full_kwh": 4.56,
                "solar_forecast_safety_factor": 1.2,
                "solar_protected_required_energy_kwh": 14.94,
                "solar_raw_exportable_energy_kwh": 108.516,
                "solar_exportable_energy_kwh": 108.516,
                "solar_timed_charge_opportunity_kwh": 6.78,
                "solar_safe_timed_charge_opportunity_kwh": 5.65,
                "pv_load_observation_span_seconds": 1.25,
            },
        )

    def test_status_exposes_final_ownership_and_compatibility_field(self) -> None:
        status = self._status(decision=self._decision_with_trace())

        self.assertIs(status["solar_surplus_policy_active"], True)
        self.assertIs(status["solar_surplus_bypass"], True)
        diagnostics = status["solar_surplus_diagnostics"]
        self.assertIsInstance(diagnostics, dict)
        self.assertIs(diagnostics["policy_active"], True)

    def test_status_copies_budget_and_timing_trace_without_recalculation(self) -> None:
        status = self._status(decision=self._decision_with_trace())
        diagnostics = status["solar_surplus_diagnostics"]

        expected = {
            "measured_pv_surplus_kw": 9.876,
            "required_surplus_threshold_kw": 0.5,
            "remaining_forecast_kwh": 123.456,
            "expected_remaining_load_kwh": 7.89,
            "battery_fill_need_kwh": 4.56,
            "forecast_safety_factor": 1.2,
            "protected_requirement_kwh": 14.94,
            "raw_exportable_energy_kwh": 108.516,
            "exportable_energy_kwh": 108.516,
            "timed_charge_opportunity_kwh": 6.78,
            "safe_timed_charge_opportunity_kwh": 5.65,
            "pv_load_observation_span_seconds": 1.25,
        }
        for key, value in expected.items():
            with self.subTest(key=key):
                self.assertEqual(value, diagnostics[key])
        self.assertIs(diagnostics["energy_budget_passed"], True)
        self.assertIs(diagnostics["detailed_forecast_trusted"], True)
        self.assertIs(diagnostics["detailed_forecast_coverage"], True)
        self.assertIs(diagnostics["timing_passed"], True)

    def test_missing_trace_keys_are_nullable_and_do_not_crash_status(self) -> None:
        status = self._status(decision=Decision())
        diagnostics = status["solar_surplus_diagnostics"]

        self.assertIs(status["solar_surplus_policy_active"], False)
        self.assertIsNone(diagnostics["fail_reason"])
        self.assertIsNone(diagnostics["energy_budget_passed"])
        self.assertIsNone(diagnostics["remaining_forecast_kwh"])
        self.assertIsNone(diagnostics["timing_passed"])

    def test_missing_decision_has_safe_status_values(self) -> None:
        status = self._status(decision=None)
        diagnostics = status["solar_surplus_diagnostics"]

        self.assertIs(status["solar_surplus_policy_active"], False)
        self.assertIsNone(status["solar_surplus_bypass"])
        self.assertIs(diagnostics["policy_active"], False)
        self.assertIsNone(diagnostics["fit_at_least_one_cent"])
        self.assertIsNone(diagnostics["measured_pv_surplus_kw"])

    def test_manual_and_force_modes_suppress_stale_policy_ownership(self) -> None:
        for mode in ("Manual", "Force Full Export"):
            with self.subTest(mode=mode):
                state = SolarState(
                    sigenergy_mode=mode,
                    timestamp=datetime.now(timezone.utc),
                )

                status = self._status(
                    decision=self._decision_with_trace(),
                    state=state,
                )

                self.assertEqual(mode, status["sigenergy_mode"])
                self.assertIs(status["solar_surplus_policy_active"], False)
                self.assertIs(
                    status["solar_surplus_diagnostics"]["policy_active"],
                    False,
                )
                self.assertIs(status["solar_surplus_bypass"], True)

    def test_config_and_live_ui_use_redesigned_solar_wording(self) -> None:
        template = TEMPLATE_PATH.read_text(encoding="utf-8")

        for key in (
            "solar_surplus_bypass_enabled",
            "solar_surplus_forecast_safety_factor",
            "solar_surplus_start_multiplier",
            "solar_surplus_stop_multiplier",
            "solar_surplus_min_pv_margin",
            "solar_surplus_stop_pv_margin",
        ):
            with self.subTest(key=key):
                self.assertIn(f"['{key}'", template)

        self.assertIn("title:'Solar Surplus'", template)
        self.assertIn("Solar Surplus Enabled", template)
        self.assertIn("Legacy Start Multiplier (unused)", template)
        self.assertIn("Legacy Stop Multiplier (unused)", template)
        self.assertIn("Start PV Surplus Margin", template)
        self.assertIn("Continuation PV Surplus Margin", template)
        self.assertIn("Solar Surplus never deliberately discharges the battery", template)
        self.assertIn("1.00 uses the calculated energy requirement as-is", template)
        self.assertIn("does not use this value for eligibility", template)
        self.assertIn("Solar Surplus policy active", template)
        self.assertIn("physical export is not implied", template)
        self.assertIn("solar_surplus_diagnostics", template)


if __name__ == "__main__":
    unittest.main()
