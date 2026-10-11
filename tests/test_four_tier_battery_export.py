from __future__ import annotations

import asyncio
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import ValidationError

from app.config import Settings
from app.optimizer import BATTERY_EXPORT, MODE_CMD_DISCHARGE_PV, MODE_MAX_SELF
from app.routers import api
from haos49_characterization_helpers import Haos49CharacterizationCase, RecordingHA
import test_api_validation as api_helpers


KEYS = tuple(f"battery_export_min_soc_{tier}" for tier in ("low", "medium", "high", "spike"))


class FourTierConfigTests(unittest.TestCase):
    def test_defaults_and_independent_environment_round_trip(self):
        with patch.dict("os.environ", {}, clear=True):
            cfg = Settings(_env_file=None)
            self.assertEqual([100, 40, 20, 10], [getattr(cfg, k) for k in KEYS])
            for key, value in zip(KEYS, (0, 100, 75.5, 95)):
                with self.subTest(key=key), patch.dict("os.environ", {key.upper(): str(value)}):
                    self.assertEqual(value, getattr(Settings(_env_file=None), key))
                    self.assertEqual(key.upper(), api._config_key_to_env_var(key))

    def test_model_and_single_and_batch_api_reject_invalid_without_mutation(self):
        for key in KEYS:
            for value in (True, False, -0.1, 100.1, float("nan"), float("inf"), -float("inf"), "bad", None):
                with self.subTest(key=key, value=value):
                    with self.assertRaises(ValidationError):
                        Settings(_env_file=None, **{key: value})
                    for batch in (False, True):
                        cfg = Settings(_env_file=None)
                        original = getattr(cfg, key)
                        request = api_helpers.ApiValidationTests._request(cfg)
                        item = api.ConfigUpdateRequest(key=key, value=value)
                        with self.assertRaises(HTTPException):
                            if batch:
                                asyncio.run(api.update_config_batch(request, api.ConfigBatchUpdateRequest(
                                    updates=[api.ConfigUpdateRequest(key="forecast_safety_charging", value=9), item],
                                )))
                            else:
                                asyncio.run(api.update_config(request, item))
                        self.assertEqual(original, getattr(cfg, key))
                        self.assertNotEqual(9, cfg.forecast_safety_charging)

    def test_api_accepts_unordered_floors_and_preserves_persistence(self):
        cfg = Settings(_env_file=None)
        request = api_helpers.ApiValidationTests._request(cfg)
        values = dict(zip(KEYS, (0, 100, 75.5, 95)))
        with patch("app.routers.api._persist_config_keys_to_env", return_value=list(KEYS)) as persist:
            result = asyncio.run(api.update_config_batch(request, api.ConfigBatchUpdateRequest(
                updates=[api.ConfigUpdateRequest(key=k, value=v) for k, v in values.items()],
                persist=True,
            )))
        self.assertTrue(result["ok"])
        self.assertEqual(values, {k: getattr(cfg, k) for k in KEYS})
        persist.assert_called_once_with(cfg, list(KEYS), values)
        result = asyncio.run(api.get_config(request))
        for key, value in values.items():
            self.assertEqual(value, result[key])

    def test_ui_and_environment_expose_each_floor_once(self):
        root = Path(__file__).resolve().parents[1]
        ui = (root / "templates/index.html").read_text(encoding="utf-8")
        example = (root / ".env.example").read_text(encoding="utf-8")
        for key, default in zip(KEYS, (100, 40, 20, 10)):
            self.assertEqual(1, ui.count(f"['{key}',"))
            self.assertIn(f"{key.upper()}={default}.0", example)


class FourTierDecisionTests(Haos49CharacterizationCase):
    def tier_state(self, fit=0.4, soc=70.0, **overrides):
        values = dict(
            battery_soc=soc, available_discharge_energy_kwh=soc * 0.3,
            feedin_price=fit, feedin_price_cents=fit * 100,
            pv_kw=10.0, solar_power_now_kw=10.0, load_kw=1.0,
        )
        values.update(overrides)
        return self.state(self.FIXED_AFTERNOON, **values)

    def decision(self, optimizer, **values):
        return self.decide(optimizer, self.tier_state(**values), self.FIXED_AFTERNOON)

    def test_price_boundaries_select_exactly_one_tier(self):
        optimizer = self.optimizer(max_battery_soc=100, export_spike_threshold=0.6)
        for fit, spike, tier, floor in (
            (0.099, False, "low", 100), (0.10, False, "low", 100),
            (0.1999, False, "low", 100), (0.20, False, "medium", 40),
            (0.9999, False, "medium", 40), (1.0, False, "high", 20),
            (0.5999, True, "medium", 40), (0.6, True, "spike", 10),
            (1.5, True, "spike", 10),
        ):
            with self.subTest(fit=fit, spike=spike):
                d = self.decision(optimizer, fit=fit, price_spike_active=spike)
                self.assertEqual(tier, d.trace_values["battery_export_tier"])
                self.assertEqual(floor, d.trace_values["battery_export_selected_soc_floor"])

    def test_each_selected_floor_is_strict_and_never_falls_back(self):
        for tier, fit, spike in (("medium", 0.4, False), ("high", 1.1, False), ("spike", 1.1, True)):
            optimizer = self.optimizer(
                max_battery_soc=100, export_spike_threshold=0.6,
                allow_low_medium_export_positive_fit=True,
                allow_positive_fit_battery_discharging=True,
                **{key: 0 for key in KEYS},
            )
            setattr(optimizer.cfg, f"battery_export_min_soc_{tier}", 70)
            for soc in (69.9, 70):
                with self.subTest(tier=tier, soc=soc):
                    d = self.decision(optimizer, fit=fit, soc=soc, price_spike_active=spike)
                    self.assertFalse(d.trace_values["battery_export_candidate_eligible"])
                    self.assertEqual("selected_soc_floor", d.trace_values["battery_export_rejection"])
                    self.assertNotEqual(BATTERY_EXPORT, d.export_intent)
            d = self.decision(optimizer, fit=fit, soc=71, price_spike_active=spike)
            self.assertEqual(BATTERY_EXPORT, d.export_intent)
            self.assertEqual(tier, d.trace_values["battery_export_tier"])

    def test_medium_keeps_interpolation_soc_scale_headroom_divisor_boost_and_rounding(self):
        # 0.60 -> tier 18.5. (60-40)% of 30 kWh / 3 h * 1.222 = 2.444 -> 2.4.
        optimizer = self.optimizer(max_battery_soc=100)
        d = self.decision(optimizer, fit=0.6, soc=60)
        self.assertEqual(18.5, d.trace_values["export_tier_limit"])
        self.assertEqual(2.4, d.export_limit)
        self.assertEqual("medium_price", d.trace_values["battery_export_final_owner"])
        self.assertEqual(MODE_CMD_DISCHARGE_PV, d.ems_mode)

    def test_spike_full_power_and_hardware_bound_remain_separate(self):
        for full, cap, expected in ((False, 40, 25), (True, 40, 30), (True, 7.239, 7.23)):
            optimizer = self.optimizer(export_spike_threshold=0.6, export_spike_full_power=full, cap_total_import=30)
            d = self.decision(optimizer, fit=0.7, soc=95, price_spike_active=True,
                              ess_max_discharge_kw=40, grid_export_limit_entity_max_kw=cap)
            self.assertEqual(expected, d.export_limit)
            self.assertEqual("export_spike", d.trace_values["battery_export_final_owner"])

    def test_low_battery_export_is_disabled_despite_persisted_floors_and_opt_ins(self):
        for floor in (0, 90, 100):
            for fit in (0.05, 0.15, 0.1999):
                for soc in (90.1, 100):
                    with self.subTest(floor=floor, fit=fit, soc=soc):
                        optimizer = self.optimizer(
                            battery_export_min_soc_low=floor,
                            allow_low_medium_export_positive_fit=True,
                            allow_positive_fit_battery_discharging=True,
                        )
                        d = self.decision(optimizer, fit=fit, soc=soc)
                        self.assertEqual("low", d.trace_values["battery_export_tier"])
                        self.assertEqual("low_battery_export_disabled_by_policy", d.trace_values["battery_export_rejection"])
                        self.assertFalse(d.trace_values["battery_export_proposal_qualified"])
                        self.assertFalse(d.trace_values["battery_export_candidate_eligible"])
                        self.assertFalse(d.trace_values["morning_preempted"])
                        self.assertFalse(d.trace_gates["positive_fit_battery_export_authorized"])
                        self.assertEqual("none", d.trace_values["battery_export_owner"])
                        self.assertEqual("none", d.trace_values["battery_export_final_owner"])
                        self.assertEqual("MSC_SURPLUS_CEILING", d.export_intent)
                        self.assertEqual(MODE_MAX_SELF, d.ems_mode)

    def test_disabled_low_does_not_displace_genuinely_eligible_morning_slow(self):
        optimizer = self.optimizer(
            battery_export_min_soc_low=0,
            allow_low_medium_export_positive_fit=True,
            allow_positive_fit_battery_discharging=True,
            morning_slow_charge_enabled=True,
            morning_slow_charge_until="16:00",
            morning_slow_charge_rate_kw=3.7,
        )
        d = self.decision(optimizer, fit=0.15, battery_capacity_trusted=True,
                          forecast_remaining_observation_trusted=True)
        self.assertTrue(d.morning_slow_charge_active)
        self.assertEqual(3.7, d.ess_charge_limit)
        self.assertEqual(MODE_MAX_SELF, d.ems_mode)
        self.assertFalse(d.trace_values["morning_preempted"])
        self.assertEqual("none", d.trace_values["battery_export_owner"])
        self.assertNotEqual(BATTERY_EXPORT, d.export_intent)

    def test_ordinary_positive_fit_msc_never_manufactures_battery_sale(self):
        optimizer = self.optimizer(allow_low_medium_export_positive_fit=True)
        for discharge, export in ((0, 0), (-2, 0), (-2, 2)):
            d = self.decision(optimizer, fit=0.05, soc=95,
                              battery_power_sensor_kw=discharge, grid_export_power_kw=export)
            self.assertNotEqual(BATTERY_EXPORT, d.export_intent)
            self.assertEqual("none", d.trace_values["battery_export_final_owner"])
            if export:
                self.assertEqual(0, d.export_limit)

    def test_high_and_spike_preempt_each_morning_owner_only_with_valid_candidate(self):
        for policy in ("dump", "slow_charge"):
            for spike in (False, True):
                with self.subTest(policy=policy, spike=spike):
                    optimizer = self.optimizer(
                        export_spike_threshold=0.6,
                        morning_slow_charge_enabled=policy == "slow_charge",
                        morning_slow_charge_until="16:00",
                        morning_slow_charge_rate_kw=3.7,
                    )
                    if policy == "dump":
                        optimizer._morning_dump_active = lambda *a, **kw: True
                    else:
                        baseline = self.decision(
                            optimizer, fit=0.15, battery_capacity_trusted=True,
                            forecast_remaining_observation_trusted=True,
                        )
                        self.assertTrue(baseline.morning_slow_charge_active)
                        self.assertEqual(3.7, baseline.ess_charge_limit)
                        self.assertEqual(MODE_MAX_SELF, baseline.ems_mode)
                        self.assertNotEqual(BATTERY_EXPORT, baseline.export_intent)
                    d = self.decision(
                        optimizer, fit=1.1, price_spike_active=spike,
                        battery_capacity_trusted=True,
                        forecast_remaining_observation_trusted=True,
                    )
                    self.assertTrue(d.trace_values["morning_preempted"])
                    self.assertFalse(d.morning_dump_active)
                    self.assertFalse(d.morning_slow_charge_active)
                    self.assertEqual(BATTERY_EXPORT, d.export_intent)
                    self.assertGreater(d.export_limit, 0)

    def test_rejected_high_spike_candidate_keeps_eligible_morning_slow_ownership_and_charge_rate(self):
        cases = (
            ({"battery_soc_trusted": False}, {}, "untrusted_soc_or_capacity"),
            ({"battery_capacity_trusted": False}, {}, "untrusted_soc_or_capacity"),
            ({"soc": 20}, {}, "selected_soc_floor"),
            ({"grid_export_limit_entity_max_kw": 0.01}, {}, "high_price_or_spike"),
            ({}, {"today_highest_actual_import_price": 2}, "actual_import_cost"),
            ({}, {"import_cost_floor_unknown": True}, "actual_import_cost"),
        )
        for spike in (False, True):
            for values, summary, reason in cases:
                with self.subTest(spike=spike, reason=reason, values=values):
                    optimizer = self.optimizer(
                        export_spike_threshold=0.6,
                        morning_slow_charge_enabled=True,
                        morning_slow_charge_until="16:00",
                        morning_slow_charge_rate_kw=3.7,
                    )
                    with patch.object(optimizer, "_optimizer_import_topup_summary_today", return_value=summary):
                        d = self.decision(
                            optimizer, fit=1.1, price_spike_active=spike,
                            forecast_remaining_observation_trusted=True,
                            **{"battery_capacity_trusted": True, **values},
                        )
                    self.assertFalse(d.trace_values["morning_preempted"])
                    if values.get("battery_capacity_trusted") is False:
                        # The independent capacity guard rejects Morning itself;
                        # rejection of a tier cannot restore that unsafe ownership.
                        self.assertFalse(d.morning_slow_charge_active)
                        self.assertFalse(d.trace_values["morning_preemption_requested"])
                        self.assertEqual(optimizer.cfg.ess_charge_limit_value, d.ess_charge_limit)
                        self.assertEqual(0.0, d.export_limit)
                        self.assertNotEqual(BATTERY_EXPORT, d.export_intent)
                    else:
                        self.assertTrue(d.morning_slow_charge_active)
                        self.assertTrue(d.trace_values["morning_preemption_requested"])
                        self.assertEqual(3.7, d.ess_charge_limit)
                    self.assertEqual(MODE_MAX_SELF, d.ems_mode)
                    expected_reason = "protected_soc_floor" if spike and values.get("soc") == 20 else reason
                    self.assertEqual(expected_reason, d.trace_values["battery_export_rejection"])

    def test_untrusted_remaining_forecast_disables_morning_and_high_spike_use_independent_guards(self):
        for spike in (False, True):
            # The existing daytime full-target exception permits High/Spike at
            # 70% with a 50% target and measured PV surplus. At a 100% target,
            # remaining-forecast evidence is required and export must close.
            for target, permitted in ((50, True), (100, False)):
                with self.subTest(spike=spike, target=target):
                    optimizer = self.optimizer(
                        export_spike_threshold=0.6, max_battery_soc=target,
                        morning_slow_charge_enabled=True,
                        morning_slow_charge_until="16:00",
                        morning_slow_charge_rate_kw=3.7,
                    )
                    d = self.decision(
                        optimizer, fit=1.1, price_spike_active=spike,
                        battery_capacity_trusted=True,
                        forecast_remaining_observation_trusted=False,
                    )
                    self.assertFalse(d.morning_slow_charge_active)
                    self.assertFalse(d.trace_values["morning_preemption_requested"])
                    self.assertFalse(d.trace_values["morning_preempted"])
                    self.assertEqual(optimizer.cfg.ess_charge_limit_value, d.ess_charge_limit)
                    self.assertEqual(not permitted, d.trace_gates["export_blocked_for_forecast"])
                    if permitted:
                        self.assertEqual(BATTERY_EXPORT, d.export_intent)
                        self.assertEqual("export_spike" if spike else "high_price",
                                         d.trace_values["battery_export_final_owner"])
                        self.assertEqual(MODE_CMD_DISCHARGE_PV, d.ems_mode)
                        self.assertEqual(25.0, d.export_limit)
                    else:
                        self.assertEqual("EXPORT_BLOCKED", d.export_intent)
                        self.assertEqual("none", d.trace_values["battery_export_final_owner"])
                        self.assertEqual(MODE_MAX_SELF, d.ems_mode)
                        self.assertEqual(0.0, d.export_limit)
                        self.assertEqual("untrusted_forecast_or_reserve_evidence",
                                         d.trace_values["battery_export_rejection"])

    def test_spike_cannot_bypass_protected_floor_or_telemetry(self):
        optimizer = self.optimizer(export_spike_threshold=0.6, battery_export_min_soc_spike=0)
        for values in (
            {"soc": 20}, {"battery_soc_trusted": False}, {"battery_capacity_trusted": False},
            {"available_discharge_energy_trusted": False},
            {"forecast_remaining_observation_trusted": False, "soc": 40},
            {"forecast_tomorrow_observation_trusted": False, "soc": 100,
             "pv_kw": 0, "solar_power_now_kw": 0},
            {"sigenergy_mode_observed": False},
        ):
            with self.subTest(values=values):
                d = self.decision(optimizer, fit=1.1, price_spike_active=True, **values)
                self.assertNotEqual(BATTERY_EXPORT, d.export_intent)
                self.assertFalse(d.trace_values["morning_preempted"])

    def test_untrusted_tomorrow_retains_high_spike_near_full_measured_pv_cap(self):
        for spike in (False, True):
            optimizer = self.optimizer(export_spike_threshold=0.6)
            for soc, expected in ((98, 25), (99, 5), (100, 5)):
                with self.subTest(spike=spike, soc=soc):
                    d = self.decision(optimizer, fit=1.1, soc=soc,
                                      price_spike_active=spike, pv_kw=6,
                                      solar_power_now_kw=20,
                                      forecast_tomorrow_observation_trusted=False)
                    self.assertEqual(expected, d.export_limit)
                    self.assertEqual(BATTERY_EXPORT, d.export_intent)
                    self.assertEqual("export_spike" if spike else "high_price",
                                     d.trace_values["battery_export_final_owner"])
            d = self.decision(optimizer, fit=1.1, soc=100, price_spike_active=spike,
                              forecast_tomorrow_observation_trusted=False,
                              pv_power_trusted=False)
            self.assertEqual(0, d.export_limit)
            self.assertNotEqual(BATTERY_EXPORT, d.export_intent)

    def test_unobserved_authority_preserves_only_qualified_high_spike_provenance(self):
        for spike, owner in ((False, "high_price"), (True, "export_spike")):
            for values, summary, expected_owner in (
                ({}, {}, owner),
                ({"soc": 20}, {}, "none"),
                ({"battery_soc_trusted": False}, {}, "none"),
                ({"battery_capacity_trusted": False}, {}, "none"),
                ({"available_discharge_energy_trusted": False}, {}, "none"),
                ({"forecast_remaining_observation_trusted": False}, {}, "none"),
                ({"grid_export_limit_entity_max_kw": 0.01}, {}, "none"),
                ({}, {"today_highest_actual_import_price": 2}, owner),
                ({}, {"import_cost_floor_unknown": True}, owner),
            ):
                with self.subTest(spike=spike, values=values, summary=summary):
                    ha = RecordingHA()
                    optimizer = self.optimizer(ha, export_spike_threshold=0.6)
                    state = self.tier_state(fit=1.1, sigenergy_mode_observed=False,
                                            price_spike_active=spike, pv_kw=0,
                                            solar_power_now_kw=0, **values)
                    with patch.object(optimizer, "_optimizer_import_topup_summary_today", return_value=summary):
                        d = self.decide(optimizer, state, self.FIXED_AFTERNOON)
                    self.assertEqual(expected_owner, d.trace_values["battery_export_owner"])
                    self.assertEqual("none", d.trace_values["battery_export_final_owner"])
                    self.assertFalse(d.trace_values["battery_export_candidate_eligible"])
                    self.assertFalse(d.trace_values["morning_preempted"])
                    self.assertFalse(d.trace_gates["explicit_battery_export_owner_active"])
                    self.assertEqual("EXPORT_BLOCKED", d.trace_values["requested_export_intent"])
                    self.assertEqual("EXPORT_BLOCKED", d.export_intent)
                    self.assertEqual(MODE_MAX_SELF, d.ems_mode)
                    self.assertEqual(0.0, d.export_limit)
                    asyncio.run(optimizer._apply(state, d))
                    self.assertEqual([], ha.calls)

    def test_medium_cannot_preempt_morning_and_value_gate_stays_advisory(self):
        optimizer = self.optimizer(max_battery_soc=100, export_value_gate_enabled=True,
                                   export_value_gate_enforce=True, export_value_gate_min_floor=99)
        d = self.decision(optimizer)
        self.assertEqual(BATTERY_EXPORT, d.export_intent)
        self.assertFalse(d.trace_gates["export_value_gate_enforcement_active"])
        optimizer._morning_slow_charge_active = lambda *a, **kw: True
        d = self.decision(optimizer)
        self.assertTrue(d.morning_slow_charge_active)
        self.assertFalse(d.trace_values["morning_preempted"])
        self.assertEqual(MODE_MAX_SELF, d.ems_mode)
