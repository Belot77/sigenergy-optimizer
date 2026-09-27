from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models import BATTERY_EXPORT, EXPORT_BLOCKED, MSC_SURPLUS_CEILING
from app.optimizer import DISCHARGE_MODES, MODE_MAX_SELF
from haos49_characterization_helpers import Haos49CharacterizationCase


class SolarSurplusEntryStabilityCharacterizationTests(Haos49CharacterizationCase):
    """Characterize current Solar entry and the proposed 60-second policy."""

    WHEN = datetime(2026, 1, 15, 14, 0, 0)
    ENTRY_DELAY_SECONDS = 60.0
    HIGH_CEILING_KW = 25.0

    def _optimizer(self, **overrides: object):
        values: dict[str, object] = {
            "solar_surplus_bypass_enabled": True,
            "solar_surplus_forecast_safety_factor": 1.20,
            "battery_full_safeguard_enabled": False,
            "morning_dump_enabled": False,
            "morning_slow_charge_enabled": False,
            "evening_boost_enabled": False,
            "standby_holdoff_enabled": False,
            "allow_low_medium_export_positive_fit": False,
            "allow_positive_fit_battery_discharging": False,
            "export_value_gate_enabled": False,
            "export_value_gate_dry_run": False,
            "export_value_gate_enforce": False,
            "export_threshold_low": 0.10,
            "export_threshold_medium": 0.20,
            "export_threshold_high": 1.00,
            "export_limit_high": self.HIGH_CEILING_KW,
            "pv_max_power_normal": self.HIGH_CEILING_KW,
            "min_grid_transfer_kw": 0.5,
            "ess_charge_limit_value": self.HIGH_CEILING_KW,
            "ess_discharge_limit_value": self.HIGH_CEILING_KW,
        }
        values.update(overrides)
        return self.optimizer(**values)

    @staticmethod
    def _detailed_forecast(
        when: datetime,
        *,
        pv_kw: float = 5.0,
    ) -> list[dict[str, object]]:
        return [
            {
                "period_start": datetime.fromtimestamp(
                    (when + timedelta(minutes=30 * index)).timestamp(),
                    tz=timezone.utc,
                ).isoformat(),
                "pv_estimate": pv_kw,
            }
            for index in range(8)
        ]

    def _state(self, when: datetime, **overrides: object):
        values: dict[str, object] = {
            "sigenergy_mode": "Automated",
            "sigenergy_mode_observed": True,
            "current_ems_mode": MODE_MAX_SELF,
            "ems_mode_observed": True,
            "battery_soc": 80.0,
            "battery_soc_trusted": True,
            "battery_capacity_kwh": 10.0,
            "battery_capacity_trusted": True,
            "available_discharge_energy_kwh": 8.0,
            "available_discharge_energy_trusted": True,
            "battery_power_sensor_kw": 0.0,
            "pv_kw": 2.0,
            "pv_power_trusted": True,
            "load_kw": 1.0,
            "load_power_trusted": True,
            "pv_load_observations_coherent": True,
            "pv_load_observation_span_seconds": 1.0,
            "solar_power_now_kw": 2.0,
            "feedin_price": 0.01,
            "feedin_price_cents": 1.0,
            "forecast_remaining_kwh": 20.0,
            "forecast_remaining_observation_trusted": True,
            "forecast_today_kwh": 20.0,
            "forecast_today_observation_trusted": True,
            "forecast_tomorrow_kwh": 30.0,
            "forecast_tomorrow_observation_trusted": True,
            "sun_above_horizon": True,
            "sun_state_observation_trusted": True,
            "next_sunset_ts": (when + timedelta(hours=4)).timestamp(),
            "sunset_observation_trusted": True,
            "hours_to_sunset": 4.0,
            "solcast_detailed": self._detailed_forecast(when),
            "solcast_detailed_source_trusted": True,
            "ess_max_charge_kw": 5.0,
            "ess_max_discharge_kw": self.HIGH_CEILING_KW,
            "ess_charge_limit_entity_max_kw": 5.0,
            "ess_discharge_limit_entity_max_kw": self.HIGH_CEILING_KW,
            "grid_export_limit_entity_max_kw": self.HIGH_CEILING_KW,
            "grid_import_power_kw": 0.0,
            "grid_export_power_kw": 0.0,
            "derived_power_flow_coherent": True,
            "derived_power_flow_span_seconds": 1.0,
            "current_export_limit": 0.01,
            "current_export_limit_observed": True,
            "current_import_limit": 0.01,
            "current_import_limit_observed": True,
            "current_pv_max_power_limit": self.HIGH_CEILING_KW,
            "current_ess_charge_limit": self.HIGH_CEILING_KW,
            "current_ess_discharge_limit": self.HIGH_CEILING_KW,
            "demand_window_active": False,
            "demand_window_observed": True,
        }
        values.update(overrides)
        return self.state(when, **values)

    def _cycle(
        self,
        optimizer,
        elapsed_seconds: float,
        *,
        remember: bool = True,
        base_when: datetime | None = None,
        operator_mode: str | None = None,
        **state_overrides: object,
    ):
        when = (base_when or self.WHEN) + timedelta(seconds=elapsed_seconds)
        state = self._state(when, **state_overrides)
        decision = self.decide(optimizer, state, when)
        if operator_mode is not None:
            optimizer._freeze_decision_to_live_mode(state, decision, operator_mode)
        if remember:
            optimizer._last_decision = decision
        return decision

    def _qualify_to_delay(self, optimizer):
        self._cycle(optimizer, 0.0)
        return self._cycle(optimizer, self.ENTRY_DELAY_SECONDS)

    def test_existing_alternating_budget_evidence_opens_immediately_each_time(self) -> None:
        optimizer = self._optimizer()

        decisions = [
            self._cycle(optimizer, 0.0, forecast_remaining_kwh=20.0),
            self._cycle(optimizer, 10.0, forecast_remaining_kwh=7.2),
            self._cycle(optimizer, 20.0, forecast_remaining_kwh=20.0),
            self._cycle(optimizer, 30.0, forecast_remaining_kwh=0.0),
            self._cycle(optimizer, 40.0, forecast_remaining_kwh=20.0),
        ]

        self.assertEqual(
            [True, False, True, False, True],
            [decision.solar_surplus_policy_active for decision in decisions],
        )
        self.assertEqual(
            [
                "active_final_solar_surplus_owner",
                "energy_budget_not_positive",
                "active_final_solar_surplus_owner",
                "energy_budget_not_positive",
                "active_final_solar_surplus_owner",
            ],
            [decision.trace_values["solar_surplus_fail_reason"] for decision in decisions],
        )

    def test_proposed_continuous_entry_waits_for_60_elapsed_seconds(self) -> None:
        optimizer = self._optimizer()

        decisions = [
            self._cycle(optimizer, 0.0),
            self._cycle(optimizer, 59.999),
            self._cycle(optimizer, 60.0),
        ]

        self.assertEqual(
            [False, False, True],
            [decision.solar_surplus_policy_active for decision in decisions],
        )
        self.assertEqual(
            1,
            sum(decision.solar_surplus_policy_active for decision in decisions),
        )

    def test_proposed_short_failure_closes_and_restarts_full_entry_delay(self) -> None:
        optimizer = self._optimizer()
        qualified = self._qualify_to_delay(optimizer)
        failed = self._cycle(optimizer, 61.0, forecast_remaining_kwh=7.2)
        retry = self._cycle(optimizer, 62.0)
        still_pending = self._cycle(optimizer, 121.999)
        reopened = self._cycle(optimizer, 122.0)

        self.assertTrue(qualified.solar_surplus_policy_active)
        self.assertFalse(failed.solar_surplus_policy_active)
        self.assertEqual(EXPORT_BLOCKED, failed.export_intent)
        self.assertEqual(
            [False, False, True],
            [
                retry.solar_surplus_policy_active,
                still_pending.solar_surplus_policy_active,
                reopened.solar_surplus_policy_active,
            ],
        )

    def test_proposed_invalid_evidence_resets_pending_qualification(self) -> None:
        invalid_cases = {
            "timing": {"solcast_detailed_source_trusted": False},
            "telemetry": {"pv_power_trusted": False},
            "forecast": {"forecast_remaining_observation_trusted": False},
            "unsafe_flow": {"battery_power_sensor_kw": -0.2},
        }

        for label, invalid_overrides in invalid_cases.items():
            with self.subTest(label=label):
                optimizer = self._optimizer()
                self._cycle(optimizer, 0.0)
                failed = self._cycle(optimizer, 30.0, **invalid_overrides)
                retry = self._cycle(optimizer, 31.0)

                self.assertFalse(failed.solar_surplus_policy_active)
                self.assertFalse(retry.solar_surplus_policy_active)

    def test_proposed_owners_block_and_reset_pending_acquisition(self) -> None:
        manual_modes = ("Manual", "Force Full Export")
        for mode in manual_modes:
            with self.subTest(owner=mode):
                optimizer = self._optimizer()
                first = self._cycle(optimizer, 0.0, operator_mode=mode)
                held = self._cycle(optimizer, 60.0, operator_mode=mode)
                released = self._cycle(optimizer, 61.0)

                self.assertFalse(first.solar_surplus_policy_active)
                self.assertFalse(held.solar_surplus_policy_active)
                self.assertFalse(released.solar_surplus_policy_active)

        with self.subTest(owner="morning_slow"):
            optimizer = self._optimizer(
                morning_slow_charge_enabled=True,
                morning_slow_charge_rate_kw=2.0,
            )
            optimizer._morning_slow_charge_active = lambda *args, **kwargs: True
            first = self._cycle(optimizer, 0.0)
            held = self._cycle(optimizer, 60.0)
            optimizer._morning_slow_charge_active = lambda *args, **kwargs: False
            released = self._cycle(optimizer, 61.0)

            self.assertFalse(first.solar_surplus_policy_active)
            self.assertFalse(held.solar_surplus_policy_active)
            self.assertFalse(released.solar_surplus_policy_active)

        with self.subTest(owner="morning_dump"):
            optimizer = self._optimizer(morning_dump_enabled=True)
            optimizer._morning_dump_active = lambda *args, **kwargs: True
            morning = datetime(2026, 1, 15, 6, 0, 0)
            first = self._cycle(optimizer, 0.0, base_when=morning)
            held = self._cycle(optimizer, 60.0, base_when=morning)
            optimizer._morning_dump_active = lambda *args, **kwargs: False
            released = self._cycle(optimizer, 61.0, base_when=morning)

            self.assertFalse(first.solar_surplus_policy_active)
            self.assertFalse(held.solar_surplus_policy_active)
            self.assertFalse(released.solar_surplus_policy_active)

        with self.subTest(owner="competing_deliberate_export"):
            optimizer = self._optimizer()
            first = self._cycle(
                optimizer,
                0.0,
                feedin_price=1.20,
                feedin_price_cents=120.0,
            )
            held = self._cycle(
                optimizer,
                60.0,
                feedin_price=1.20,
                feedin_price_cents=120.0,
            )
            released = self._cycle(optimizer, 61.0)

            self.assertEqual(BATTERY_EXPORT, first.export_intent)
            self.assertEqual(BATTERY_EXPORT, held.export_intent)
            self.assertFalse(released.solar_surplus_policy_active)

    def test_proposed_restart_backward_and_stale_time_cannot_satisfy_entry(self) -> None:
        with self.subTest(clock_case="restart"):
            pending = self._optimizer()
            self._cycle(pending, 0.0)
            restarted = self._optimizer()
            after_restart = self._cycle(restarted, 60.0)
            self.assertFalse(after_restart.solar_surplus_policy_active)

        with self.subTest(clock_case="backward"):
            monotonic = self._optimizer()
            self._cycle(monotonic, 0.0)
            self._cycle(monotonic, 60.0)
            backward = self._cycle(monotonic, 59.0)
            self.assertFalse(backward.solar_surplus_policy_active)

        with self.subTest(clock_case="stale"):
            stale = self._optimizer()
            self._cycle(stale, 0.0)
            stale_timestamp = self._cycle(stale, 60.0, timestamp=self.WHEN)
            self.assertFalse(stale_timestamp.solar_surplus_policy_active)

    def test_active_solar_closes_immediately_for_each_invalid_evidence(self) -> None:
        invalid_cases = {
            "zero_budget": {"forecast_remaining_kwh": 7.2},
            "timing": {"solcast_detailed_source_trusted": False},
            "telemetry": {"load_power_trusted": False},
            "forecast": {"forecast_remaining_observation_trusted": False},
            "unsafe_flow": {"battery_power_sensor_kw": -0.2},
            "competing_policy": {
                "feedin_price": 1.20,
                "feedin_price_cents": 120.0,
            },
        }

        for label, invalid_overrides in invalid_cases.items():
            with self.subTest(label=label):
                optimizer = self._optimizer()
                active = self._qualify_to_delay(optimizer)
                failed = self._cycle(optimizer, 61.0, **invalid_overrides)

                self.assertTrue(active.solar_surplus_policy_active)
                self.assertFalse(failed.solar_surplus_policy_active)

        with self.subTest(label="operator_ownership_loss"):
            optimizer = self._optimizer()
            active = self._qualify_to_delay(optimizer)
            failed = self._cycle(
                optimizer,
                61.0,
                operator_mode=optimizer.cfg.manual_option,
            )

            self.assertTrue(active.solar_surplus_policy_active)
            self.assertFalse(failed.solar_surplus_policy_active)

    def test_failure_closes_immediately_and_consumes_new_forecast_next_cycle(self) -> None:
        optimizer = self._optimizer()
        active = self._qualify_to_delay(optimizer)
        failed = self._cycle(
            optimizer,
            61.0,
            forecast_remaining_kwh=7.2,
            current_export_limit=self.HIGH_CEILING_KW,
            current_export_limit_observed=True,
        )

        self.assertTrue(active.solar_surplus_policy_active)
        self.assertFalse(failed.solar_surplus_policy_active)
        self.assertEqual("energy_budget_not_positive", failed.trace_values["solar_surplus_fail_reason"])
        self.assertEqual(EXPORT_BLOCKED, failed.export_intent)
        self.assertEqual(0.0, failed.export_limit)
        self.assertEqual(MODE_MAX_SELF, failed.ems_mode)
        self.assertEqual("none", failed.trace_values["battery_export_owner"])

    def test_strict_positive_budget_and_measured_surplus_hysteresis_remain(self) -> None:
        equality = self._cycle(
            self._optimizer(),
            0.0,
            forecast_remaining_kwh=7.2,
        )

        optimizer = self._optimizer()
        self._qualify_to_delay(optimizer)
        continued = self._cycle(
            optimizer,
            61.0,
            pv_kw=1.200001,
            solar_power_now_kw=1.200001,
        )
        stopped = self._cycle(
            optimizer,
            62.0,
            pv_kw=1.2,
            solar_power_now_kw=1.2,
        )
        cannot_reenter = self._cycle(
            optimizer,
            123.0,
            pv_kw=1.3,
            solar_power_now_kw=1.3,
        )

        self.assertFalse(equality.solar_surplus_policy_active)
        self.assertEqual(0.0, equality.trace_values["solar_raw_exportable_energy_kwh"])
        self.assertTrue(continued.solar_surplus_policy_active)
        self.assertEqual(0.2, continued.trace_values["solar_surplus_threshold_kw"])
        self.assertFalse(stopped.solar_surplus_policy_active)
        self.assertFalse(cannot_reenter.solar_surplus_policy_active)
        self.assertEqual(0.5, cannot_reenter.trace_values["solar_surplus_threshold_kw"])

    def test_ordinary_msc_eligibility_is_independent_of_solar_acquisition(self) -> None:
        optimizer = self._optimizer(
            allow_low_medium_export_positive_fit=True,
            allow_positive_fit_battery_discharging=False,
        )
        decision = self._cycle(
            optimizer,
            0.0,
            feedin_price=0.20,
            feedin_price_cents=20.0,
            pv_kw=1.4,
            solar_power_now_kw=1.4,
        )

        self.assertFalse(decision.solar_surplus_policy_active)
        self.assertTrue(decision.trace_gates["ordinary_msc_surplus_ceiling_active"])
        self.assertEqual(MSC_SURPLUS_CEILING, decision.export_intent)
        self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
        self.assertEqual("none", decision.trace_values["battery_export_owner"])

    def test_proposed_near_full_94_and_97_2_percent_wait_then_remain_pv_only(self) -> None:
        for battery_soc in (94.0, 97.2):
            with self.subTest(battery_soc=battery_soc):
                optimizer = self._optimizer(
                    battery_full_safeguard_enabled=True,
                    battery_full_hours_before_sunset=2.0,
                    battery_full_forecast_multiplier=0.8,
                )
                near_full = {
                    "battery_soc": battery_soc,
                    "battery_capacity_kwh": 40.3,
                    "available_discharge_energy_kwh": 0.0,
                    "available_discharge_energy_trusted": False,
                    "battery_power_sensor_kw": 10.35,
                    "pv_kw": 11.45,
                    "solar_power_now_kw": 11.45,
                    "load_kw": 1.10,
                    "feedin_price": 0.0789,
                    "feedin_price_cents": 7.89,
                    "forecast_remaining_kwh": 30.0,
                    "forecast_today_kwh": 30.0,
                    "forecast_tomorrow_kwh": 60.0,
                    "ess_max_charge_kw": self.HIGH_CEILING_KW,
                    "ess_charge_limit_entity_max_kw": self.HIGH_CEILING_KW,
                }
                before_delay = self._cycle(optimizer, 0.0, **near_full)
                after_delay = self._cycle(
                    optimizer,
                    60.0,
                    solcast_detailed=self._detailed_forecast(
                        self.WHEN + timedelta(seconds=60),
                        pv_kw=20.0,
                    ),
                    **near_full,
                )

                self.assertFalse(before_delay.solar_surplus_policy_active)
                self.assertTrue(after_delay.solar_surplus_policy_active)
                self.assertEqual(MSC_SURPLUS_CEILING, after_delay.export_intent)
                self.assertEqual(MODE_MAX_SELF, after_delay.ems_mode)
                self.assertNotIn(after_delay.ems_mode, DISCHARGE_MODES)
                self.assertEqual("none", after_delay.trace_values["battery_export_owner"])
                self.assertEqual("solar_surplus_pv_high", after_delay.trace_values["desired_export_source"])
                self.assertEqual(self.HIGH_CEILING_KW, after_delay.pv_max_power_limit)

    def test_qualified_final_intent_remains_msc_without_battery_export_owner(self) -> None:
        decision = self._qualify_to_delay(self._optimizer())

        self.assertTrue(decision.solar_surplus_policy_active)
        self.assertEqual(MSC_SURPLUS_CEILING, decision.export_intent)
        self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
        self.assertNotIn(decision.ems_mode, DISCHARGE_MODES)
        self.assertEqual("none", decision.trace_values["battery_export_owner"])
        self.assertEqual("solar_surplus_pv_high", decision.trace_values["desired_export_source"])
        self.assertEqual(self.HIGH_CEILING_KW, decision.pv_max_power_limit)
