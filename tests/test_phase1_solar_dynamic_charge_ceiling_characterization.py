from __future__ import annotations

from datetime import datetime, timedelta, timezone
from dataclasses import replace

from app.models import MSC_SURPLUS_CEILING
from app.optimizer import DISCHARGE_MODES, MODE_MAX_SELF
from haos49_characterization_helpers import Haos49CharacterizationCase


class Phase1SolarDynamicChargeCeilingCharacterizationTests(
    Haos49CharacterizationCase
):
    """Desired Solar charge ownership before the production implementation."""

    WHEN = datetime(2026, 1, 15, 14, 0, 0)
    PERIOD_HOURS = 0.5
    NORMAL_CHARGE_KW = 5.0
    SAFETY_FACTOR = 1.20

    def _optimizer(self, **overrides: object):
        values: dict[str, object] = {
            "solar_surplus_bypass_enabled": True,
            "solar_surplus_forecast_safety_factor": self.SAFETY_FACTOR,
            "battery_full_safeguard_enabled": False,
            "morning_dump_enabled": False,
            "morning_slow_charge_enabled": False,
            "evening_boost_enabled": False,
            "standby_holdoff_enabled": False,
            "allow_low_medium_export_positive_fit": False,
            "export_value_gate_enabled": False,
            "export_value_gate_dry_run": False,
            "export_value_gate_enforce": False,
            "export_limit_high": 25.0,
            "pv_max_power_normal": 25.0,
            "ess_charge_limit_value": self.NORMAL_CHARGE_KW,
        }
        values.update(overrides)
        return self.optimizer(**values)

    def _detailed_forecast(
        self,
        pv_values: list[float],
        *,
        when: datetime | None = None,
    ) -> list[dict[str, object]]:
        anchor = when or self.WHEN
        return [
            {
                "period_start": datetime.fromtimestamp(
                    (
                        anchor
                        + timedelta(hours=index * self.PERIOD_HOURS)
                    ).timestamp(),
                    tz=timezone.utc,
                ).isoformat(),
                "pv_estimate": pv_kw,
            }
            for index, pv_kw in enumerate(pv_values)
        ]

    def _state(
        self,
        *,
        when: datetime | None = None,
        forecast_pv_kw: list[float] | None = None,
        **overrides: object,
    ):
        at = when or self.WHEN
        detailed_pv = forecast_pv_kw or [6.0] + [3.0] * 7
        hours_to_sunset = len(detailed_pv) * self.PERIOD_HOURS
        values: dict[str, object] = {
            "sigenergy_mode": "Automated",
            "sigenergy_mode_observed": True,
            "current_ems_mode": MODE_MAX_SELF,
            "ems_mode_observed": True,
            "battery_soc": 60.0,
            "battery_soc_trusted": True,
            "battery_capacity_kwh": 10.0,
            "battery_capacity_trusted": True,
            "available_discharge_energy_kwh": 6.0,
            "available_discharge_energy_trusted": True,
            "battery_power_sensor_kw": 0.0,
            "pv_kw": 6.0,
            "pv_power_trusted": True,
            "load_kw": 1.0,
            "load_power_trusted": True,
            "pv_load_observations_coherent": True,
            "solar_power_now_kw": 6.0,
            "feedin_price": 0.05,
            "feedin_price_cents": 5.0,
            "forecast_remaining_kwh": 40.0,
            "forecast_remaining_observation_trusted": True,
            "forecast_today_kwh": 40.0,
            "forecast_today_observation_trusted": True,
            "forecast_tomorrow_kwh": 30.0,
            "forecast_tomorrow_observation_trusted": True,
            "sun_above_horizon": True,
            "sun_state_observation_trusted": True,
            "next_sunset_ts": (at + timedelta(hours=hours_to_sunset)).timestamp(),
            "sunset_observation_trusted": True,
            "hours_to_sunset": hours_to_sunset,
            "solcast_detailed": self._detailed_forecast(detailed_pv, when=at),
            "solcast_detailed_source_trusted": True,
            "solcast_provider_polled": datetime.fromtimestamp(
                at.timestamp() - 1, timezone.utc,
            ).isoformat(),
            "solcast_provider_next_update": datetime.fromtimestamp(
                at.timestamp() + 3600, timezone.utc,
            ).isoformat(),
            "solcast_provider_source": (
                "sensor.solcast_pv_forecast_forecast_today",
                "sensor.solcast_pv_forecast_api_last_polled",
            ),
            "solcast_provider_epoch": 0,
            "solcast_provider_continuity": True,
            "ess_max_charge_kw": self.NORMAL_CHARGE_KW,
            "ess_charge_limit_entity_max_kw": self.NORMAL_CHARGE_KW,
            "ess_max_discharge_kw": 25.0,
            "grid_export_limit_entity_max_kw": 25.0,
            "grid_import_power_kw": 0.0,
            "grid_export_power_kw": 0.0,
            "current_export_limit": 0.01,
            "current_export_limit_observed": True,
            "current_import_limit": 0.01,
            "current_import_limit_observed": True,
            "current_pv_max_power_limit": 25.0,
            "current_ess_charge_limit": self.NORMAL_CHARGE_KW,
            "current_ess_discharge_limit": 25.0,
            "demand_window_observed": True,
        }
        values.update(overrides)
        return self.state(at, **values)

    def _decide(
        self,
        optimizer,
        *,
        when: datetime | None = None,
        forecast_pv_kw: list[float] | None = None,
        **state_overrides: object,
    ):
        at = when or self.WHEN
        state = self._state(
            when=at,
            forecast_pv_kw=forecast_pv_kw,
            **state_overrides,
        )
        # These calculation/ownership protections run with a proven provider
        # generation. Bootstrap and lifecycle failures have their own suite.
        if not optimizer._solar_provider_baselined:
            baseline = replace(state, solcast_provider_polled=datetime.fromtimestamp(
                at.timestamp() - 60, timezone.utc,
            ).isoformat())
            with self.optimizer_time(at):
                optimizer._update_solar_provider(baseline, at.timestamp())
        return self.decide(optimizer, state, at)

    def test_active_solar_owns_zero_ceiling_when_future_opportunity_is_abundant(
        self,
    ) -> None:
        decision = self._decide(
            self._optimizer(),
            forecast_pv_kw=[6.0] + [3.0] * 7,
        )

        self.assertTrue(decision.solar_surplus_policy_active)
        self.assertEqual(MSC_SURPLUS_CEILING, decision.export_intent)
        self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
        self.assertNotIn(decision.ems_mode, DISCHARGE_MODES)
        self.assertEqual("none", decision.trace_values["battery_export_owner"])
        self.assertEqual(25.0, decision.export_limit)
        self.assertEqual(25.0, decision.pv_max_power_limit)
        self.assertEqual(0.0, decision.ess_charge_limit)

    def test_future_opportunity_recomputes_the_ceiling_without_a_timer(self) -> None:
        optimizer = self._optimizer()

        abundant = self._decide(
            optimizer,
            forecast_pv_kw=[6.0] + [3.0] * 7,
        )
        optimizer._last_decision = abundant
        moderate = self._decide(
            optimizer,
            forecast_pv_kw=[6.0] + [2.2] * 7,
        )
        optimizer._last_decision = moderate
        limited = self._decide(
            optimizer,
            forecast_pv_kw=[6.0] + [1.8] * 7,
        )

        self.assertAlmostEqual(0.0, abundant.ess_charge_limit, places=2)
        self.assertAlmostEqual(1.2, moderate.ess_charge_limit, places=2)
        self.assertAlmostEqual(4.0, limited.ess_charge_limit, places=2)
        self.assertLess(abundant.ess_charge_limit, moderate.ess_charge_limit)
        self.assertLess(moderate.ess_charge_limit, limited.ess_charge_limit)

    def test_approaching_deadline_raises_ceiling_toward_required_rate(self) -> None:
        near_deadline = datetime(2026, 1, 15, 17, 30, 0)

        decision = self._decide(
            self._optimizer(),
            when=near_deadline,
            forecast_pv_kw=[6.0],
            battery_soc=80.0,
            available_discharge_energy_kwh=8.0,
        )

        self.assertTrue(decision.solar_surplus_policy_active)
        self.assertAlmostEqual(4.8, decision.ess_charge_limit, places=2)
        self.assertLessEqual(decision.ess_charge_limit, self.NORMAL_CHARGE_KW)

    def test_trusted_normal_capability_is_the_dynamic_ceiling_upper_bound(self) -> None:
        decision = self._decide(
            self._optimizer(),
            forecast_pv_kw=[6.0, 5.6] + [1.0] * 6,
        )

        self.assertTrue(decision.solar_surplus_policy_active)
        self.assertAlmostEqual(self.NORMAL_CHARGE_KW, decision.ess_charge_limit)
        self.assertLessEqual(decision.ess_charge_limit, self.NORMAL_CHARGE_KW)
        self.assertTrue(decision.trace_gates["solar_charge_ceiling_owned"])

    def test_solar_inactive_relinquishes_the_ceiling_in_the_next_decision(self) -> None:
        optimizer = self._optimizer()
        active = self._decide(
            optimizer,
            forecast_pv_kw=[6.0] + [3.0] * 7,
        )
        optimizer._last_decision = active

        inactive = self._decide(
            optimizer,
            forecast_pv_kw=[6.0] + [3.0] * 7,
            pv_kw=1.2,
            solar_power_now_kw=1.2,
        )

        self.assertFalse(inactive.solar_surplus_policy_active)
        self.assertEqual(self.NORMAL_CHARGE_KW, inactive.ess_charge_limit)
        self.assertEqual("normal", inactive.trace_values["ess_charge_limit_owner"])
        self.assertFalse(inactive.trace_gates.get("solar_charge_ceiling_owned", False))
        self.assertEqual(0.0, active.ess_charge_limit)

    def test_grid_import_charge_owner_outranks_zero_and_positive_solar_requests(self) -> None:
        for import_kw, future_pv_kw, solar_kw in ((2.0, 3.0, 0.0), (3.5, 2.6, 2.0)):
            with self.subTest(import_kw=import_kw, solar_kw=solar_kw):
                optimizer = self._optimizer(target_battery_charge=import_kw)
                state_values = {
                    "battery_soc": 45.0,
                    "available_discharge_energy_kwh": 4.5,
                    "pv_kw": 2.0,
                    "solar_power_now_kw": 2.0,
                    "forecast_pv_kw": [6.0] + [future_pv_kw] * 7,
                }
                solar = self._decide(optimizer, **state_values)
                importing = self._decide(
                    optimizer, **state_values,
                    current_price=0.01, current_price_cents=1.0,
                )

                # With no import owner, the same forecast permits zero or a
                # reduced charge ceiling. Numeric equality cannot identify owner.
                self.assertEqual(0.0, solar.import_limit)
                self.assertEqual(solar_kw, solar.ess_charge_limit)
                self.assertEqual("solar_surplus", solar.trace_values["ess_charge_limit_owner"])
                self.assertTrue(importing.solar_surplus_policy_active)
                self.assertEqual("cheap_topup_import", importing.trace_values["import_branch"])
                self.assertEqual(import_kw, importing.import_limit)
                self.assertEqual(import_kw, importing.ess_charge_limit)
                self.assertEqual("grid_import", importing.trace_values["ess_charge_limit_owner"])
                self.assertFalse(importing.trace_gates["solar_charge_ceiling_owned"])
                self.assertEqual(MSC_SURPLUS_CEILING, importing.export_intent)
                self.assertEqual(MODE_MAX_SELF, importing.ems_mode)
                self.assertNotIn(importing.ems_mode, DISCHARGE_MODES)
                self.assertEqual("none", importing.trace_values["battery_export_owner"])
                self.assertEqual(25.0, importing.export_limit)
                self.assertEqual(25.0, importing.pv_max_power_limit)

    def test_grid_import_charge_owner_acquires_and_releases_without_stale_limits(self) -> None:
        optimizer = self._optimizer()
        state_values = {
            "battery_soc": 45.0,
            "available_discharge_energy_kwh": 4.5,
            "pv_kw": 2.0,
            "solar_power_now_kw": 2.0,
        }
        solar = self._decide(optimizer, **state_values)
        optimizer._last_decision = solar
        importing = self._decide(
            optimizer, **state_values,
            current_price=0.01, current_price_cents=1.0,
            current_ess_charge_limit=solar.ess_charge_limit,
        )
        optimizer._last_decision = importing
        released = self._decide(
            optimizer, **state_values,
            current_ess_charge_limit=importing.ess_charge_limit,
        )

        self.assertEqual(0.0, solar.ess_charge_limit)
        self.assertEqual(2.0, importing.import_limit)
        self.assertEqual(2.0, importing.ess_charge_limit)
        self.assertEqual("grid_import", importing.trace_values["ess_charge_limit_owner"])
        self.assertFalse(importing.trace_gates["solar_charge_ceiling_owned"])
        self.assertIsNone(importing.trace_values["solar_charge_ceiling_requested_kw"])
        self.assertEqual(0.0, released.import_limit)
        self.assertEqual(0.0, released.ess_charge_limit)
        self.assertTrue(released.solar_surplus_policy_active)
        self.assertTrue(released.trace_gates["solar_charge_ceiling_owned"])
        self.assertEqual("solar_surplus", released.trace_values["ess_charge_limit_owner"])

    def test_grid_import_charge_owner_survives_loss_of_solar_evidence(self) -> None:
        cases = (
            {"forecast_today_observation_trusted": False},
            {"solcast_detailed_source_trusted": False},
            {"solcast_detailed": []},
            {"forecast_remaining_observation_trusted": False},
        )
        for evidence in cases:
            with self.subTest(evidence=evidence):
                optimizer = self._optimizer()
                state_values = {
                    "battery_soc": 45.0,
                    "available_discharge_energy_kwh": 4.5,
                    "pv_kw": 2.0,
                    "solar_power_now_kw": 2.0,
                    "current_price": 0.01,
                    "current_price_cents": 1.0,
                }
                importing = self._decide(optimizer, **state_values)
                optimizer._last_decision = importing
                lost_evidence = self._decide(
                    optimizer, **state_values, **evidence,
                    current_ess_charge_limit=importing.ess_charge_limit,
                )

                self.assertEqual(2.0, lost_evidence.import_limit)
                self.assertEqual(2.0, lost_evidence.ess_charge_limit)
                self.assertEqual("grid_import", lost_evidence.trace_values["ess_charge_limit_owner"])
                self.assertFalse(lost_evidence.trace_gates["solar_charge_ceiling_owned"])
                self.assertEqual(importing.ess_charge_limit, lost_evidence.ess_charge_limit)

    def test_morning_slow_remains_the_charging_owner(self) -> None:
        optimizer = self._optimizer(
            morning_slow_charge_enabled=True,
            morning_slow_charge_rate_kw=2.0,
        )
        optimizer._morning_slow_charge_active = lambda *args, **kwargs: True

        decision = self._decide(optimizer)

        self.assertTrue(decision.morning_slow_charge_active)
        self.assertTrue(decision.trace_gates["morning_slow_genuinely_owns_charging"])
        self.assertFalse(decision.solar_surplus_policy_active)
        self.assertEqual(2.0, decision.ess_charge_limit)
        self.assertEqual("morning_slow", decision.trace_values["ess_charge_limit_owner"])
        self.assertFalse(decision.trace_gates.get("solar_charge_ceiling_owned", False))

    def test_manual_and_force_modes_keep_the_live_charge_limit(self) -> None:
        for mode_attr in ("manual_option", "full_export_option"):
            with self.subTest(mode=mode_attr):
                optimizer = self._optimizer()
                state = self._state(current_ess_charge_limit=4.5)
                decision = self.decide(optimizer, state, self.WHEN)

                optimizer._freeze_decision_to_live_mode(
                    state,
                    decision,
                    getattr(optimizer.cfg, mode_attr),
                )

                self.assertFalse(decision.solar_surplus_policy_active)
                self.assertEqual(4.5, decision.ess_charge_limit)
                self.assertFalse(
                    decision.trace_gates.get("solar_charge_ceiling_owned", False)
                )

    def test_untrusted_or_missing_evidence_never_reduces_the_charge_limit(self) -> None:
        gapped = self._detailed_forecast([6.0] + [3.0] * 7)
        del gapped[3]
        cases = (
            ("untrusted_detail", {"solcast_detailed_source_trusted": False}),
            ("missing_detail", {"solcast_detailed": []}),
            ("gapped_detail", {"solcast_detailed": gapped}),
            ("untrusted_load", {"load_power_trusted": False}),
            ("untrusted_soc", {"battery_soc_trusted": False}),
            (
                "untrusted_capability",
                {
                    "ess_max_charge_kw": 999.0,
                    "ess_charge_limit_entity_max_kw": None,
                },
            ),
        )

        for label, overrides in cases:
            with self.subTest(label=label):
                decision = self._decide(self._optimizer(), **overrides)

                self.assertFalse(decision.solar_surplus_policy_active)
                self.assertEqual(self.NORMAL_CHARGE_KW, decision.ess_charge_limit)
                self.assertFalse(
                    decision.trace_gates.get("solar_charge_ceiling_owned", False)
                )

    def test_stale_detailed_parent_does_not_revoke_verified_provider_charge_authority(
        self,
    ) -> None:
        decision = self._decide(
            self._optimizer(),
            forecast_today_observation_trusted=False,
        )

        # Parent observation trust remains false, while verified provider
        # freshness controls only the separate dynamic charge authority.
        self.assertTrue(decision.solar_surplus_policy_active)
        self.assertEqual(0.0, decision.ess_charge_limit)
        self.assertTrue(decision.trace_gates["solar_charge_ceiling_owned"])
        self.assertFalse(decision.trace_gates["forecast_today_observation_trusted"])

    def test_demand_window_keeps_import_ownership_during_solar_charge_control(
        self,
    ) -> None:
        decision = self._decide(
            self._optimizer(),
            demand_window_active=True,
            demand_window_observed=True,
        )

        self.assertTrue(decision.solar_surplus_policy_active)
        self.assertEqual(0.0, decision.import_limit)
        self.assertEqual("demand_window_block", decision.trace_values["import_branch"])
        self.assertEqual(0.0, decision.ess_charge_limit)
        self.assertEqual("none", decision.trace_values["battery_export_owner"])

    def test_trace_explains_the_dynamic_charge_request(self) -> None:
        decision = self._decide(
            self._optimizer(),
            forecast_pv_kw=[6.0] + [2.2] * 7,
        )

        self.assertTrue(decision.trace_gates["solar_charge_ceiling_evidence_trusted"])
        self.assertTrue(decision.trace_gates["solar_charge_ceiling_owned"])
        self.assertEqual("solar_surplus", decision.trace_values["ess_charge_limit_owner"])
        self.assertAlmostEqual(
            1.2,
            decision.trace_values["solar_charge_ceiling_requested_kw"],
            places=2,
        )
        self.assertAlmostEqual(
            4.8,
            decision.trace_values["solar_charge_ceiling_protected_fill_need_kwh"],
            places=2,
        )
        self.assertAlmostEqual(
            4.2,
            decision.trace_values["solar_charge_ceiling_future_opportunity_kwh"],
            places=2,
        )
        self.assertAlmostEqual(
            0.6,
            decision.trace_values["solar_charge_ceiling_required_now_kwh"],
            places=2,
        )
        self.assertAlmostEqual(
            self.PERIOD_HOURS,
            decision.trace_values["solar_charge_ceiling_current_window_hours"],
            places=2,
        )
        self.assertEqual(
            "present_charging_required_for_fill_trajectory",
            decision.trace_values["solar_charge_ceiling_reason"],
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
