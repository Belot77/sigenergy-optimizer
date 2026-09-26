from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

from app.models import (
    BATTERY_EXPORT,
    EXPORT_BLOCKED,
    HVACObservedValue,
    HVACSolarInputContext,
    MSC_SURPLUS_CEILING,
)
from app.optimizer import (
    DISCHARGE_MODES,
    MODE_CMD_DISCHARGE_PV,
    MODE_MAX_SELF,
)
from haos49_characterization_helpers import Haos49CharacterizationCase


class Phase1NearFullPvOnlySafeguardCharacterizationTests(
    Haos49CharacterizationCase
):
    """Characterize the .60 near-full Solar Surplus safeguard conflict."""

    maxDiff = None
    WHEN = datetime(2026, 1, 15, 14, 0, 0)
    CAPACITY_KWH = 40.3
    PV_KW = 11.45
    LOAD_KW = 1.10
    BATTERY_CHARGE_KW = 10.35
    HIGH_CEILING_KW = 25.0

    @staticmethod
    def _observed(
        value: float | str | None,
        *,
        available: bool = True,
        fresh: bool = True,
    ) -> HVACObservedValue:
        return HVACObservedValue(
            value=value,
            available=available,
            fresh=fresh,
        )

    def _live_context(
        self,
        *,
        pv_kw: float | None = None,
        load_kw: float | None = None,
        battery_power_kw: float | None = None,
        grid_export_kw: float | None = 0.0,
    ) -> HVACSolarInputContext:
        pv = self.PV_KW if pv_kw is None else pv_kw
        load = self.LOAD_KW if load_kw is None else load_kw
        battery = (
            self.BATTERY_CHARGE_KW
            if battery_power_kw is None
            else battery_power_kw
        )
        return HVACSolarInputContext(
            pv_power=self._observed(pv),
            load_power=self._observed(load),
            battery_power=self._observed(battery),
            grid_import_power=self._observed(0.0),
            grid_export_power=self._observed(grid_export_kw),
            solar_power_now=self._observed(pv),
            sun_above_horizon=self._observed(True),
            control_mode=self._observed("Automated"),
            observed_ems_mode=self._observed(MODE_MAX_SELF),
            observed_export_limit=self._observed(0.01),
            live_snapshot=True,
        )

    def _detailed_forecast(
        self,
        pv_kw: float = 20.0,
        *,
        when: datetime | None = None,
    ) -> list[dict[str, object]]:
        anchor = when or self.WHEN
        return [
            {
                "period_start": datetime.fromtimestamp(
                    (anchor + timedelta(minutes=30 * index)).timestamp(),
                    tz=timezone.utc,
                ).isoformat(),
                "pv_estimate": pv_kw,
            }
            for index in range(8)
        ]

    def _optimizer(self, **overrides: object):
        values: dict[str, object] = {
            "solar_surplus_bypass_enabled": True,
            "solar_surplus_forecast_safety_factor": 1.20,
            "battery_full_safeguard_enabled": True,
            "battery_full_hours_before_sunset": 2.0,
            "battery_full_forecast_multiplier": 0.8,
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

    def _state(
        self,
        *,
        battery_soc: float = 97.2,
        available_energy_trusted: bool = True,
        when: datetime | None = None,
        **overrides: object,
    ):
        at = when or self.WHEN
        available_energy_kwh = (
            self.CAPACITY_KWH * battery_soc / 100.0
            if available_energy_trusted
            else 0.0
        )
        values: dict[str, object] = {
            "sigenergy_mode": "Automated",
            "sigenergy_mode_observed": True,
            "current_ems_mode": MODE_MAX_SELF,
            "ems_mode_observed": True,
            "battery_soc": battery_soc,
            "battery_soc_trusted": True,
            "battery_capacity_kwh": self.CAPACITY_KWH,
            "battery_capacity_trusted": True,
            "available_discharge_energy_kwh": available_energy_kwh,
            "available_discharge_energy_trusted": available_energy_trusted,
            "battery_power_sensor_kw": self.BATTERY_CHARGE_KW,
            "pv_kw": self.PV_KW,
            "pv_power_trusted": True,
            "load_kw": self.LOAD_KW,
            "load_power_trusted": True,
            "pv_load_observations_coherent": True,
            "pv_load_observation_span_seconds": 1.0,
            "solar_power_now_kw": self.PV_KW,
            "feedin_price": 0.0789,
            "feedin_price_cents": 7.89,
            "forecast_remaining_kwh": 30.0,
            "forecast_remaining_observation_trusted": True,
            "forecast_today_kwh": 30.0,
            "forecast_today_observation_trusted": True,
            "forecast_tomorrow_kwh": 60.0,
            "forecast_tomorrow_observation_trusted": True,
            "sun_above_horizon": True,
            "sun_state_observation_trusted": True,
            "next_sunset_ts": (at + timedelta(hours=4.0)).timestamp(),
            "sunset_observation_trusted": True,
            "hours_to_sunset": 4.0,
            "solcast_detailed": self._detailed_forecast(when=at),
            "solcast_detailed_source_trusted": True,
            "ess_max_charge_kw": self.HIGH_CEILING_KW,
            "ess_max_discharge_kw": self.HIGH_CEILING_KW,
            "ess_charge_limit_entity_max_kw": self.HIGH_CEILING_KW,
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
            "hvac_solar_inputs": self._live_context(),
        }
        values.update(overrides)
        return self.state(at, **values)

    def _decide(self, optimizer, **state_overrides: object):
        state = self._state(**state_overrides)
        return state, self.decide(optimizer, state, self.WHEN)

    @staticmethod
    def _rounded(value: object, places: int = 4) -> float:
        return round(float(value), places)

    def test_incident_94_and_97_2_percent_use_soc_headroom_for_qualified_solar(
        self,
    ) -> None:
        """Synthetic legacy refill need must not veto qualified PV-only Solar."""
        for battery_soc in (94.0, 97.2):
            with self.subTest(battery_soc=battery_soc):
                optimizer = self._optimizer()
                state, decision = self._decide(
                    optimizer,
                    battery_soc=battery_soc,
                    available_energy_trusted=False,
                )
                expected_headroom = round(
                    self.CAPACITY_KWH * (100.0 - battery_soc) / 100.0,
                    4,
                )
                actual = {
                    "soc_headroom_kwh": self._rounded(
                        decision.trace_values["solar_fill_need_to_full_kwh"]
                    ),
                    "legacy_fill_need_kwh": self._rounded(
                        decision.trace_values["bat_fill_need_kwh"],
                        1,
                    ),
                    "solar_qualified": decision.solar_surplus_bypass,
                    "battery_full_safeguard_raw": decision.battery_full_safeguard,
                    "soc_headroom_safeguard": decision.trace_gates[
                        "battery_full_safeguard_soc_headroom_block"
                    ],
                    "effective_export_safeguard": decision.trace_gates[
                        "battery_full_safeguard_effective_export_block"
                    ],
                    "solar_exception": decision.trace_gates[
                        "battery_full_safeguard_solar_exception_active"
                    ],
                    "initial_source": decision.trace_values[
                        "initial_desired_export_source"
                    ],
                    "export_limit_kw": decision.export_limit,
                    "export_intent": decision.export_intent,
                    "solar_final_owner": decision.solar_surplus_policy_active,
                    "ems_mode": decision.ems_mode,
                    "pv_max_kw": decision.pv_max_power_limit,
                    "battery_export_owner": decision.trace_values[
                        "battery_export_owner"
                    ],
                    "observed_export_limit_kw": state.current_export_limit,
                }
                expected = {
                    "soc_headroom_kwh": expected_headroom,
                    "legacy_fill_need_kwh": self.CAPACITY_KWH,
                    "solar_qualified": True,
                    "battery_full_safeguard_raw": True,
                    "soc_headroom_safeguard": False,
                    "effective_export_safeguard": False,
                    "solar_exception": True,
                    "initial_source": "solar_surplus_pv_high",
                    "export_limit_kw": self.HIGH_CEILING_KW,
                    "export_intent": MSC_SURPLUS_CEILING,
                    "solar_final_owner": True,
                    "ems_mode": MODE_MAX_SELF,
                    "pv_max_kw": self.HIGH_CEILING_KW,
                    "battery_export_owner": "none",
                    "observed_export_limit_kw": 0.01,
                }

                self.assertEqual(
                    expected,
                    actual,
                    "Trusted SoC proves the small remaining headroom and every Solar "
                    "gate passes; only the synthetic legacy refill value closes the "
                    "otherwise safe MSC ceiling.",
                )

    def test_available_energy_trust_transition_does_not_flap_qualified_solar(
        self,
    ) -> None:
        """A trust transition alone must not flap a qualified Solar ceiling."""
        optimizer = self._optimizer()
        decisions = []
        for available_energy_trusted in (True, False, True):
            _state, decision = self._decide(
                optimizer,
                available_energy_trusted=available_energy_trusted,
            )
            decisions.append(decision)
            optimizer._last_decision = decision

        actual = {
            "solar_qualified": [d.solar_surplus_bypass for d in decisions],
            "raw_safeguard": [d.battery_full_safeguard for d in decisions],
            "effective_export_safeguard": [
                d.trace_gates["battery_full_safeguard_effective_export_block"]
                for d in decisions
            ],
            "solar_exception": [
                d.trace_gates["battery_full_safeguard_solar_exception_active"]
                for d in decisions
            ],
            "export_limit_kw": [d.export_limit for d in decisions],
            "export_intent": [d.export_intent for d in decisions],
            "final_solar_owner": [
                d.solar_surplus_policy_active for d in decisions
            ],
        }
        expected = {
            "solar_qualified": [True, True, True],
            "raw_safeguard": [False, True, False],
            "effective_export_safeguard": [False, False, False],
            "solar_exception": [False, True, False],
            "export_limit_kw": [self.HIGH_CEILING_KW] * 3,
            "export_intent": [MSC_SURPLUS_CEILING] * 3,
            "final_solar_owner": [True, True, True],
        }

        self.assertEqual(
            expected,
            actual,
            "The availability sensor trust transition must not be the sole cause "
            "of a safe Solar Surplus ceiling flap.",
        )

    def test_untrusted_available_energy_never_substitutes_for_solar_qualification(
        self,
    ) -> None:
        cases = (
            (
                "aggregate_budget",
                {"forecast_remaining_kwh": 5.0},
                "solar_energy_budget_passed",
            ),
            (
                "detailed_timing",
                {"solcast_detailed": self._detailed_forecast(1.2)},
                "solar_timing_passed",
            ),
            (
                "measured_surplus",
                {
                    "pv_kw": 1.5,
                    "solar_power_now_kw": 1.5,
                    "battery_power_sensor_kw": 0.4,
                    "hvac_solar_inputs": self._live_context(
                        pv_kw=1.5,
                        battery_power_kw=0.4,
                    ),
                },
                "solar_measured_surplus_gate",
            ),
            (
                "operator_ownership",
                {"sigenergy_mode_observed": False},
                "observed_automated_control_mode",
            ),
            (
                "msc_ownership",
                {"ems_mode_observed": False},
                "observed_max_self_consumption",
            ),
        )

        for label, overrides, failed_gate in cases:
            with self.subTest(gate=label):
                _state, decision = self._decide(
                    self._optimizer(),
                    available_energy_trusted=False,
                    **overrides,
                )

                self.assertFalse(bool(decision.trace_gates[failed_gate]))
                self.assertTrue(decision.battery_full_safeguard)
                self.assertFalse(
                    decision.trace_gates[
                        "battery_full_safeguard_solar_exception_active"
                    ]
                )
                self.assertFalse(decision.solar_surplus_policy_active)
                self.assertEqual(EXPORT_BLOCKED, decision.export_intent)
                self.assertEqual(0.0, decision.export_limit)
                self.assertEqual("none", decision.trace_values["battery_export_owner"])

    def test_battery_charging_and_genuine_surplus_remain_pv_only(self) -> None:
        state, decision = self._decide(self._optimizer())

        self.assertGreater(state.battery_power_sensor_kw, 0.0)
        self.assertGreater(state.pv_kw - state.load_kw, 0.5)
        self.assertTrue(decision.solar_surplus_policy_active)
        self.assertEqual(self.HIGH_CEILING_KW, decision.export_limit)
        self.assertEqual(MSC_SURPLUS_CEILING, decision.export_intent)
        self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
        self.assertNotIn(decision.ems_mode, DISCHARGE_MODES)
        self.assertEqual("none", decision.trace_values["battery_export_owner"])

    def test_simultaneous_battery_discharge_and_grid_export_is_not_pv_only(
        self,
    ) -> None:
        live_context = self._live_context(
            battery_power_kw=-1.0,
            grid_export_kw=1.0,
        )
        _state, decision = self._decide(
            self._optimizer(),
            available_energy_trusted=False,
            battery_power_sensor_kw=-1.0,
            grid_export_power_kw=1.0,
            hvac_solar_inputs=live_context,
        )

        self.assertTrue(decision.solar_surplus_bypass)
        self.assertTrue(decision.battery_full_safeguard)
        self.assertFalse(
            decision.trace_gates["battery_full_safeguard_solar_exception_active"]
        )
        self.assertFalse(decision.trace_gates["pv_only_discharge_ok"])
        self.assertTrue(
            decision.trace_gates[
                "ordinary_msc_simultaneous_battery_discharge_and_grid_export"
            ]
        )
        self.assertFalse(decision.solar_surplus_policy_active)
        self.assertEqual(EXPORT_BLOCKED, decision.export_intent)
        self.assertEqual(0.0, decision.export_limit)
        self.assertEqual("none", decision.trace_values["battery_export_owner"])
        self.assertEqual(MODE_MAX_SELF, decision.ems_mode)

    def test_flow_classifier_distinguishes_load_serving_discharge_from_grid_export(
        self,
    ) -> None:
        results = {}
        for label, grid_export_kw in (
            ("load_serving", 0.0),
            ("stored_energy_export", 1.0),
        ):
            with self.subTest(flow=label):
                live_context = self._live_context(
                    battery_power_kw=-1.0,
                    grid_export_kw=grid_export_kw,
                )
                _state, decision = self._decide(
                    self._optimizer(),
                    battery_power_sensor_kw=-1.0,
                    grid_export_power_kw=grid_export_kw,
                    hvac_solar_inputs=live_context,
                )
                results[label] = {
                    "classification": decision.trace_values[
                        "ordinary_msc_flow_classification"
                    ],
                    "safe": decision.trace_gates["ordinary_msc_flow_safe"],
                }

        self.assertEqual(
            {
                "load_serving": {
                    "classification": "load_serving_battery_discharge",
                    "safe": True,
                },
                "stored_energy_export": {
                    "classification": (
                        "simultaneous_battery_discharge_and_grid_export"
                    ),
                    "safe": False,
                },
            },
            results,
        )

    def test_missing_stale_or_incoherent_flow_evidence_cannot_gain_exception(
        self,
    ) -> None:
        base = self._live_context()
        cases = (
            (
                "pv_untrusted",
                {
                    "pv_power_trusted": False,
                    "hvac_solar_inputs": replace(
                        base,
                        pv_power=self._observed(
                            self.PV_KW,
                            available=False,
                            fresh=False,
                        ),
                    ),
                },
            ),
            (
                "battery_and_grid_missing",
                {
                    "battery_power_sensor_kw": None,
                    "grid_export_power_kw": None,
                    "hvac_solar_inputs": replace(
                        base,
                        battery_power=self._observed(
                            None,
                            available=False,
                            fresh=False,
                        ),
                        grid_export_power=self._observed(
                            None,
                            available=False,
                            fresh=False,
                        ),
                    ),
                },
            ),
            (
                "derived_grid_flow_stale",
                {
                    "battery_power_sensor_kw": None,
                    "hvac_solar_inputs": replace(
                        base,
                        battery_power=self._observed(
                            None,
                            available=False,
                            fresh=False,
                        ),
                        grid_export_power=self._observed(0.0, fresh=False),
                    ),
                },
            ),
            (
                "derived_flow_incoherent",
                {
                    "battery_power_sensor_kw": None,
                    "derived_power_flow_coherent": False,
                    "hvac_solar_inputs": replace(
                        base,
                        battery_power=self._observed(
                            None,
                            available=False,
                            fresh=False,
                        ),
                    ),
                },
            ),
        )

        for label, overrides in cases:
            with self.subTest(evidence=label):
                _state, decision = self._decide(
                    self._optimizer(),
                    available_energy_trusted=False,
                    **overrides,
                )

                self.assertTrue(decision.battery_full_safeguard)
                self.assertFalse(
                    decision.trace_gates[
                        "battery_full_safeguard_solar_exception_active"
                    ]
                )
                self.assertFalse(decision.solar_surplus_policy_active)
                self.assertEqual(EXPORT_BLOCKED, decision.export_intent)
                self.assertEqual(0.0, decision.export_limit)
                self.assertEqual("none", decision.trace_values["battery_export_owner"])
                self.assertNotIn(decision.ems_mode, DISCHARGE_MODES)

    def test_manual_and_force_modes_retain_observed_operator_owned_actuators(
        self,
    ) -> None:
        for mode, live_ems, live_export_limit in (
            ("Manual", MODE_MAX_SELF, 3.0),
            ("Force Full Export", MODE_CMD_DISCHARGE_PV, 7.0),
        ):
            with self.subTest(mode=mode):
                optimizer = self._optimizer()
                state = self._state(
                    sigenergy_mode=mode,
                    current_ems_mode=live_ems,
                    current_export_limit=live_export_limit,
                )
                decision = self.decide(optimizer, state, self.WHEN)

                self.assertFalse(decision.solar_surplus_policy_active)
                self.assertFalse(
                    decision.trace_gates["observed_automated_control_mode"]
                )

                optimizer._freeze_decision_to_live_mode(state, decision, mode)

                self.assertFalse(decision.solar_surplus_policy_active)
                self.assertEqual(live_export_limit, decision.export_limit)
                self.assertEqual(live_ems, decision.ems_mode)
                self.assertIn("optimizer writes paused", decision.outcome_reason)

    def test_deliberate_battery_export_and_exact_full_cheap_fit_remain_distinct(
        self,
    ) -> None:
        _state, deliberate = self._decide(
            self._optimizer(),
            available_energy_trusted=False,
            feedin_price=1.20,
            feedin_price_cents=120.0,
        )

        self.assertEqual(BATTERY_EXPORT, deliberate.export_intent)
        self.assertEqual("high_price", deliberate.trace_values["battery_export_owner"])
        self.assertIn(deliberate.ems_mode, DISCHARGE_MODES)
        self.assertFalse(deliberate.solar_surplus_policy_active)

        exact_full_context = self._live_context(
            pv_kw=1.4,
            load_kw=1.0,
            battery_power_kw=0.0,
            grid_export_kw=0.0,
        )
        _state, exact_full = self._decide(
            self._optimizer(),
            battery_soc=100.0,
            available_energy_trusted=False,
            feedin_price=0.03,
            feedin_price_cents=3.0,
            pv_kw=1.4,
            solar_power_now_kw=1.4,
            load_kw=1.0,
            battery_power_sensor_kw=0.0,
            hvac_solar_inputs=exact_full_context,
        )

        self.assertFalse(exact_full.solar_surplus_bypass)
        self.assertTrue(exact_full.trace_gates["pv_only_msc_high_ceiling_active"])
        self.assertEqual(
            "msc_full_battery_high_ceiling",
            exact_full.trace_values["pv_surplus_initiation_source"],
        )
        self.assertEqual(MSC_SURPLUS_CEILING, exact_full.export_intent)
        self.assertEqual("none", exact_full.trace_values["battery_export_owner"])
        self.assertEqual(MODE_MAX_SELF, exact_full.ems_mode)

    def test_morning_and_demand_owners_keep_their_independent_actuators(self) -> None:
        morning_slow_optimizer = self._optimizer(
            morning_slow_charge_enabled=True,
            morning_slow_charge_rate_kw=3.7,
        )
        morning_slow_optimizer._morning_slow_charge_active = (
            lambda *args, **kwargs: True
        )
        _state, morning_slow = self._decide(morning_slow_optimizer)

        self.assertTrue(morning_slow.morning_slow_charge_active)
        self.assertFalse(morning_slow.solar_surplus_policy_active)
        self.assertEqual(3.7, morning_slow.ess_charge_limit)
        self.assertEqual(MODE_MAX_SELF, morning_slow.ems_mode)
        self.assertEqual("morning_slow_charge", morning_slow.trace_values["export_branch"])

        morning_dump_optimizer = self._optimizer(
            battery_full_safeguard_enabled=False,
            morning_dump_enabled=True,
        )
        morning_dump_optimizer._morning_dump_active = lambda *args, **kwargs: True
        morning = datetime(2026, 1, 15, 6, 0, 0)
        morning_dump_state = self._state(when=morning)
        morning_dump = self.decide(
            morning_dump_optimizer,
            morning_dump_state,
            morning,
        )

        self.assertTrue(morning_dump.morning_dump_active)
        self.assertFalse(morning_dump.solar_surplus_policy_active)
        self.assertEqual(BATTERY_EXPORT, morning_dump.export_intent)
        self.assertEqual(
            "morning_dump",
            morning_dump.trace_values["battery_export_owner"],
        )
        self.assertIn(morning_dump.ems_mode, DISCHARGE_MODES)

        _state, demand_window = self._decide(
            self._optimizer(),
            demand_window_active=True,
            demand_window_observed=True,
        )

        self.assertTrue(demand_window.solar_surplus_policy_active)
        self.assertEqual(MSC_SURPLUS_CEILING, demand_window.export_intent)
        self.assertEqual(self.HIGH_CEILING_KW, demand_window.export_limit)
        self.assertEqual(0.0, demand_window.import_limit)
        self.assertEqual(
            "demand_window_block",
            demand_window.trace_values["import_branch"],
        )
        self.assertEqual(self.HIGH_CEILING_KW, demand_window.pv_max_power_limit)

    def test_solar_ceiling_is_request_intent_not_observed_flow_or_discharge(self) -> None:
        state, decision = self._decide(self._optimizer())

        self.assertEqual(0.01, state.current_export_limit)
        self.assertEqual(0.0, state.grid_export_power_kw)
        self.assertEqual(self.HIGH_CEILING_KW, decision.export_limit)
        self.assertEqual(
            MSC_SURPLUS_CEILING,
            decision.trace_values["requested_export_intent"],
        )
        self.assertEqual(MSC_SURPLUS_CEILING, decision.export_intent)
        self.assertTrue(decision.requires_verified_msc_before_export)
        self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
        self.assertNotIn(decision.ems_mode, DISCHARGE_MODES)
        self.assertEqual(self.HIGH_CEILING_KW, decision.pv_max_power_limit)
        self.assertEqual("none", decision.trace_values["battery_export_owner"])
