from __future__ import annotations

from datetime import timedelta

from app.models import (
    BATTERY_EXPORT,
    EXPORT_BLOCKED,
    HVACObservedValue,
    HVACSolarInputContext,
    MSC_SURPLUS_CEILING,
)
from app.optimizer import MODE_CMD_CHARGE_PV, MODE_CMD_DISCHARGE_PV, MODE_MAX_SELF
from haos49_characterization_helpers import Haos49CharacterizationCase


class Phase1D2PowerScalarTrustTests(Haos49CharacterizationCase):
    def _state_with_power_trust(
        self,
        *,
        pv_kw: float,
        load_kw: float,
        solar_power_now_kw: float,
        pv_trusted: bool = True,
        load_trusted: bool = True,
        solar_available: bool = True,
        solar_fresh: bool = True,
        battery_soc: float = 100.0,
        feedin_price: float = 0.25,
        current_ems_mode: str = MODE_CMD_CHARGE_PV,
        **overrides: object,
    ):
        power_context = HVACSolarInputContext(
            pv_power=HVACObservedValue(
                value=pv_kw,
                available=True,
                fresh=pv_trusted,
            ),
            load_power=HVACObservedValue(
                value=load_kw,
                available=True,
                fresh=load_trusted,
            ),
            battery_power=HVACObservedValue(
                value=0.0,
                available=True,
                fresh=True,
            ),
            grid_import_power=HVACObservedValue(
                value=0.0,
                available=True,
                fresh=True,
            ),
            grid_export_power=HVACObservedValue(
                value=0.0,
                available=True,
                fresh=True,
            ),
            solar_power_now=HVACObservedValue(
                value=solar_power_now_kw,
                available=solar_available,
                fresh=solar_fresh,
            ),
            observed_ems_mode=HVACObservedValue(
                value=current_ems_mode,
                available=True,
                fresh=True,
            ),
            observed_export_limit=HVACObservedValue(
                value=0.01,
                available=True,
                fresh=True,
            ),
            live_snapshot=True,
        )
        values: dict[str, object] = {
            "battery_soc": battery_soc,
            "available_discharge_energy_kwh": 30.0 * battery_soc / 100.0,
            "battery_soc_trusted": True,
            "battery_capacity_trusted": True,
            "available_discharge_energy_trusted": True,
            "feedin_price": feedin_price,
            "feedin_price_cents": feedin_price * 100.0,
            "pv_kw": pv_kw,
            "load_kw": load_kw,
            "solar_power_now_kw": solar_power_now_kw,
            "pv_power_trusted": pv_trusted,
            "load_power_trusted": load_trusted,
            "forecast_remaining_kwh": 100.0,
            "forecast_remaining_observation_trusted": True,
            "current_ems_mode": current_ems_mode,
            "ems_mode_observed": True,
            "current_export_limit": 0.01,
            "current_export_limit_observed": True,
            "hvac_solar_inputs": power_context,
        }
        values.update(overrides)
        return self.state(self.FIXED_AFTERNOON, **values)

    def test_stale_or_unavailable_solcast_cannot_create_solar_override(self) -> None:
        optimizer = self.optimizer()
        for name, available, fresh in (
            ("stale", True, False),
            ("unavailable", False, False),
        ):
            with self.subTest(name=name):
                state = self._state_with_power_trust(
                    pv_kw=1.4,
                    load_kw=1.0,
                    solar_power_now_kw=6.0,
                    solar_available=available,
                    solar_fresh=fresh,
                )
                decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

                self.assertFalse(
                    bool(decision.trace_gates.get("solar_power_now_trusted"))
                )
                self.assertFalse(
                    bool(decision.trace_gates.get("export_solar_override"))
                )
                self.assertEqual("none", decision.trace_values["battery_export_owner"])
                self.assertNotEqual(BATTERY_EXPORT, decision.export_intent)
                self.assertNotEqual(MODE_CMD_DISCHARGE_PV, decision.ems_mode)

    def test_fresh_solcast_retains_solar_override_behavior(self) -> None:
        optimizer = self.optimizer()
        state = self._state_with_power_trust(
            pv_kw=1.4,
            load_kw=1.0,
            solar_power_now_kw=6.0,
        )

        decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

        self.assertTrue(bool(decision.trace_gates["solar_power_now_trusted"]))
        self.assertTrue(bool(decision.trace_gates["export_solar_override"]))
        self.assertEqual("solar_override", decision.trace_values["battery_export_owner"])
        self.assertEqual(BATTERY_EXPORT, decision.export_intent)
        self.assertEqual(MODE_CMD_DISCHARGE_PV, decision.ems_mode)
        self.assertAlmostEqual(0.4, decision.export_limit)

    def test_untrusted_pv_or_load_cannot_create_solar_override(self) -> None:
        optimizer = self.optimizer()
        cases = (
            ("pv", False, True),
            ("load", True, False),
        )
        for name, pv_trusted, load_trusted in cases:
            with self.subTest(name=name):
                state = self._state_with_power_trust(
                    pv_kw=2.0,
                    load_kw=1.0,
                    solar_power_now_kw=0.0,
                    pv_trusted=pv_trusted,
                    load_trusted=load_trusted,
                )
                decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

                self.assertFalse(
                    bool(decision.trace_gates.get("export_solar_override"))
                )
                self.assertEqual("none", decision.trace_values["battery_export_owner"])
                self.assertNotEqual(BATTERY_EXPORT, decision.export_intent)
                self.assertNotEqual(MODE_CMD_DISCHARGE_PV, decision.ems_mode)

        trusted_state = self._state_with_power_trust(
            pv_kw=2.0,
            load_kw=1.0,
            solar_power_now_kw=0.0,
        )
        trusted = self.decide(optimizer, trusted_state, self.FIXED_AFTERNOON)
        self.assertTrue(bool(trusted.trace_gates["export_solar_override"]))
        self.assertEqual("solar_override", trusted.trace_values["battery_export_owner"])
        self.assertEqual(BATTERY_EXPORT, trusted.export_intent)
        self.assertEqual(MODE_CMD_DISCHARGE_PV, trusted.ems_mode)

    def test_untrusted_pv_or_load_cannot_enlarge_near_floor_export_cap(self) -> None:
        optimizer = self.optimizer(
            allow_low_medium_export_positive_fit=True,
            allow_positive_fit_battery_discharging=True,
        )
        for name, pv_trusted, load_trusted in (
            ("pv", False, True),
            ("load", True, False),
        ):
            with self.subTest(name=name):
                state = self._state_with_power_trust(
                    pv_kw=6.0,
                    load_kw=1.0,
                    solar_power_now_kw=0.0,
                    pv_trusted=pv_trusted,
                    load_trusted=load_trusted,
                    battery_soc=optimizer.cfg.min_export_target_soc,
                    feedin_price=0.05,
                    current_ems_mode=MODE_MAX_SELF,
                )
                decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

                self.assertEqual(0.0, decision.export_limit)
                self.assertEqual(EXPORT_BLOCKED, decision.export_intent)
                self.assertFalse(
                    bool(
                        decision.trace_gates.get(
                            "explicit_battery_export_owner_active"
                        )
                    )
                )
                self.assertNotEqual(MODE_CMD_DISCHARGE_PV, decision.ems_mode)

        trusted_state = self._state_with_power_trust(
            pv_kw=6.0,
            load_kw=1.0,
            solar_power_now_kw=0.0,
            battery_soc=optimizer.cfg.min_export_target_soc,
            feedin_price=0.05,
            current_ems_mode=MODE_MAX_SELF,
        )
        trusted = self.decide(optimizer, trusted_state, self.FIXED_AFTERNOON)
        self.assertGreater(trusted.export_limit, 0.01)
        self.assertEqual(BATTERY_EXPORT, trusted.export_intent)
        self.assertEqual(
            "positive_fit_override",
            trusted.trace_values["battery_export_owner"],
        )

    def test_untrusted_load_cannot_clear_battery_full_safeguard(self) -> None:
        optimizer = self.optimizer(
            battery_full_safeguard_enabled=True,
            battery_full_hours_before_sunset=1.0,
        )
        detailed = [
            {
                "period_start": (
                    self.FIXED_AFTERNOON + timedelta(minutes=30)
                ).isoformat(),
                "pv_estimate": 10.0,
            }
        ]
        stale_load = self._state_with_power_trust(
            pv_kw=6.0,
            load_kw=0.0,
            solar_power_now_kw=6.0,
            load_trusted=False,
            battery_soc=95.0,
            feedin_price=0.15,
            current_ems_mode=MODE_MAX_SELF,
            available_discharge_energy_kwh=29.0,
            solcast_detailed=detailed,
        )
        fresh_load = self._state_with_power_trust(
            pv_kw=6.0,
            load_kw=0.0,
            solar_power_now_kw=6.0,
            battery_soc=95.0,
            feedin_price=0.15,
            current_ems_mode=MODE_MAX_SELF,
            available_discharge_energy_kwh=29.0,
            solcast_detailed=detailed,
        )

        stale_decision = self.decide(
            optimizer,
            stale_load,
            self.FIXED_AFTERNOON,
        )
        fresh_decision = self.decide(
            optimizer,
            fresh_load,
            self.FIXED_AFTERNOON,
        )

        self.assertTrue(stale_decision.battery_full_safeguard)
        self.assertEqual(0.0, stale_decision.export_limit)
        self.assertEqual(EXPORT_BLOCKED, stale_decision.export_intent)
        self.assertFalse(fresh_decision.battery_full_safeguard)
        self.assertEqual(MSC_SURPLUS_CEILING, fresh_decision.export_intent)

    def test_exact_full_and_solar_surplus_remain_pv_only(self) -> None:
        exact_full_optimizer = self.optimizer()
        exact_full_state = self._state_with_power_trust(
            pv_kw=0.2,
            load_kw=1.0,
            solar_power_now_kw=20.0,
            solar_fresh=False,
            feedin_price=0.095,
            current_ems_mode=MODE_MAX_SELF,
        )
        exact_full = self.decide(
            exact_full_optimizer,
            exact_full_state,
            self.FIXED_AFTERNOON,
        )
        self.assertTrue(
            bool(exact_full.trace_gates["pv_only_msc_high_ceiling_active"])
        )
        self.assertEqual(MSC_SURPLUS_CEILING, exact_full.export_intent)
        self.assertEqual("none", exact_full.trace_values["battery_export_owner"])
        self.assertEqual(MODE_MAX_SELF, exact_full.ems_mode)

        surplus_optimizer = self.optimizer(solar_surplus_bypass_enabled=True)
        surplus_state = self._state_with_power_trust(
            pv_kw=2.0,
            load_kw=1.0,
            solar_power_now_kw=20.0,
            solar_fresh=False,
            battery_soc=60.0,
            feedin_price=0.12,
            current_ems_mode=MODE_MAX_SELF,
        )
        surplus = self.decide(
            surplus_optimizer,
            surplus_state,
            self.FIXED_AFTERNOON,
        )
        self.assertTrue(surplus.solar_surplus_bypass)
        self.assertEqual(MSC_SURPLUS_CEILING, surplus.export_intent)
        self.assertEqual("none", surplus.trace_values["battery_export_owner"])
        self.assertEqual(MODE_MAX_SELF, surplus.ems_mode)


if __name__ == "__main__":
    import unittest

    unittest.main()
