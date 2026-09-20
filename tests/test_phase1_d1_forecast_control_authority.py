from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models import BATTERY_EXPORT, EXPORT_BLOCKED, MSC_SURPLUS_CEILING
from app.optimizer import MODE_MAX_SELF
from haos49_characterization_helpers import Haos49CharacterizationCase


class Phase1D1ForecastControlAuthorityTests(Haos49CharacterizationCase):
    MORNING = datetime(2026, 1, 15, 8, 0, 0)
    MIDDAY = datetime(2026, 1, 15, 12, 0, 0)

    def _forecast_state(
        self,
        when: datetime,
        *,
        remaining_trusted: bool = True,
        today_trusted: bool = True,
        tomorrow_trusted: bool = True,
        **overrides: object,
    ):
        values: dict[str, object] = {
            "battery_soc_trusted": True,
            "battery_capacity_trusted": True,
            "available_discharge_energy_trusted": True,
            "pv_power_trusted": True,
            "load_power_trusted": True,
            "forecast_remaining_kwh": 100.0,
            "forecast_today_kwh": 100.0,
            "forecast_tomorrow_kwh": 100.0,
            "forecast_remaining_observation_trusted": remaining_trusted,
            "forecast_today_observation_trusted": today_trusted,
            "forecast_tomorrow_observation_trusted": tomorrow_trusted,
            "current_ems_mode": MODE_MAX_SELF,
            "ems_mode_observed": True,
            "battery_power_sensor_kw": 0.0,
            "grid_export_power_kw": 0.0,
        }
        values.update(overrides)
        return self.state(when, **values)

    def test_morning_slow_requires_trusted_remaining_forecast(self) -> None:
        settings = {
            "morning_slow_charge_enabled": True,
            "morning_slow_charge_until": "11:00",
            "morning_slow_charge_min_feedin_price": 0.01,
            "morning_slow_charge_base_load_kw": 0.0,
            "morning_slow_charge_rate_kw": 2.0,
            "forecast_safety_charging": 1.0,
        }
        state_values = {
            "battery_soc": 66.0,
            "available_discharge_energy_kwh": 20.0,
            "forecast_remaining_kwh": 20.0,
            "feedin_price": 0.01,
            "feedin_price_cents": 1.0,
            "pv_kw": 4.0,
            "load_kw": 1.0,
        }

        trusted_optimizer = self.optimizer(**settings)
        trusted = self.decide(
            trusted_optimizer,
            self._forecast_state(
                self.MORNING,
                remaining_trusted=True,
                **state_values,
            ),
            self.MORNING,
        )
        untrusted_optimizer = self.optimizer(**settings)
        untrusted = self.decide(
            untrusted_optimizer,
            self._forecast_state(
                self.MORNING,
                remaining_trusted=False,
                **state_values,
            ),
            self.MORNING,
        )

        self.assertTrue(trusted.morning_slow_charge_active)
        self.assertEqual(2.0, trusted.ess_charge_limit)
        self.assertEqual(MSC_SURPLUS_CEILING, trusted.export_intent)
        self.assertEqual("none", trusted.trace_values["battery_export_owner"])
        self.assertFalse(untrusted.morning_slow_charge_active)
        self.assertFalse(
            bool(untrusted.trace_gates["forecast_remaining_observation_trusted"])
        )
        self.assertEqual(EXPORT_BLOCKED, untrusted.export_intent)
        self.assertEqual("none", untrusted.trace_values["battery_export_owner"])

    def test_untrusted_remaining_forecast_cannot_open_ownerless_ordinary_msc(self) -> None:
        state_values = {
            "battery_soc": 60.0,
            "available_discharge_energy_kwh": 18.0,
            "feedin_price": 0.15,
            "feedin_price_cents": 15.0,
            "pv_kw": 4.0,
            "load_kw": 1.0,
        }

        trusted_optimizer = self.optimizer(max_battery_soc=100.0)
        trusted = self.decide(
            trusted_optimizer,
            self._forecast_state(
                self.MIDDAY,
                remaining_trusted=True,
                **state_values,
            ),
            self.MIDDAY,
        )
        untrusted_optimizer = self.optimizer(max_battery_soc=100.0)
        untrusted = self.decide(
            untrusted_optimizer,
            self._forecast_state(
                self.MIDDAY,
                remaining_trusted=False,
                **state_values,
            ),
            self.MIDDAY,
        )

        self.assertEqual(MSC_SURPLUS_CEILING, trusted.export_intent)
        self.assertTrue(trusted.trace_gates["ordinary_msc_surplus_ceiling_active"])
        self.assertEqual("none", trusted.trace_values["battery_export_owner"])
        self.assertFalse(trusted.trace_gates["export_blocked_for_forecast"])
        self.assertFalse(trusted.trace_gates["export_forecast_guard"])
        self.assertEqual(EXPORT_BLOCKED, untrusted.export_intent)
        self.assertFalse(untrusted.trace_gates["ordinary_msc_surplus_ceiling_active"])
        self.assertTrue(untrusted.trace_gates["export_blocked_for_forecast"])
        self.assertEqual("none", untrusted.trace_values["battery_export_owner"])

    def test_untrusted_tomorrow_cannot_enlarge_high_price_or_spike_full_battery_cap(
        self,
    ) -> None:
        cases = (
            ("high_price", 1.20, False, "high_price"),
            ("spike", 0.60, True, "export_spike"),
        )
        for name, feedin_price, spike_active, expected_owner in cases:
            with self.subTest(name=name):
                settings = {"export_spike_threshold": 0.60}
                state_values = {
                    "battery_soc": 100.0,
                    "available_discharge_energy_kwh": 30.0,
                    "feedin_price": feedin_price,
                    "feedin_price_cents": feedin_price * 100.0,
                    "price_spike_active": spike_active,
                    "pv_kw": 6.0,
                    "load_kw": 1.0,
                }
                trusted_optimizer = self.optimizer(**settings)
                trusted = self.decide(
                    trusted_optimizer,
                    self._forecast_state(
                        self.FIXED_AFTERNOON,
                        tomorrow_trusted=True,
                        **state_values,
                    ),
                    self.FIXED_AFTERNOON,
                )
                untrusted_optimizer = self.optimizer(**settings)
                untrusted = self.decide(
                    untrusted_optimizer,
                    self._forecast_state(
                        self.FIXED_AFTERNOON,
                        tomorrow_trusted=False,
                        **state_values,
                    ),
                    self.FIXED_AFTERNOON,
                )

                self.assertEqual(BATTERY_EXPORT, trusted.export_intent)
                self.assertEqual(BATTERY_EXPORT, untrusted.export_intent)
                self.assertEqual(expected_owner, trusted.trace_values["battery_export_owner"])
                self.assertEqual(expected_owner, untrusted.trace_values["battery_export_owner"])
                self.assertGreater(trusted.export_limit, untrusted.export_limit)
                self.assertEqual(5.0, untrusted.export_limit)

    def test_untrusted_tomorrow_cannot_open_exact_full_msc_high_ceiling(self) -> None:
        state_values = {
            "battery_soc": 100.0,
            "available_discharge_energy_kwh": 30.0,
            "feedin_price": 0.095,
            "feedin_price_cents": 9.5,
            "pv_kw": 0.2,
            "load_kw": 1.0,
        }

        trusted_optimizer = self.optimizer()
        trusted = self.decide(
            trusted_optimizer,
            self._forecast_state(
                self.FIXED_AFTERNOON,
                tomorrow_trusted=True,
                **state_values,
            ),
            self.FIXED_AFTERNOON,
        )
        untrusted_optimizer = self.optimizer()
        untrusted = self.decide(
            untrusted_optimizer,
            self._forecast_state(
                self.FIXED_AFTERNOON,
                tomorrow_trusted=False,
                **state_values,
            ),
            self.FIXED_AFTERNOON,
        )

        self.assertTrue(trusted.trace_gates["pv_only_msc_high_ceiling_active"])
        self.assertEqual(MSC_SURPLUS_CEILING, trusted.export_intent)
        self.assertEqual("none", trusted.trace_values["battery_export_owner"])
        self.assertFalse(untrusted.trace_gates["pv_only_msc_high_ceiling_active"])
        self.assertEqual(EXPORT_BLOCKED, untrusted.export_intent)
        self.assertEqual("none", untrusted.trace_values["battery_export_owner"])

    def test_today_forecast_trust_continues_to_control_standby_holdoff(self) -> None:
        settings = {
            "standby_holdoff_enabled": True,
            "standby_holdoff_end_time": "11:00",
            "pv_forecast_holdoff_kwh": 50.0,
        }
        price_entry = {
            "start_time": (self.MORNING + timedelta(hours=1)).isoformat(),
            "per_kwh": -0.20,
        }
        state_values = {
            "battery_soc": 90.0,
            "available_discharge_energy_kwh": 27.0,
            "current_price": 0.30,
            "price_forecast_entries": [price_entry],
        }

        trusted_optimizer = self.optimizer(**settings)
        trusted_optimizer._tz = timezone(
            self.MORNING.astimezone().utcoffset() or timedelta()
        )
        trusted = self.decide(
            trusted_optimizer,
            self._forecast_state(
                self.MORNING,
                today_trusted=True,
                **state_values,
            ),
            self.MORNING,
        )
        untrusted_optimizer = self.optimizer(**settings)
        untrusted_optimizer._tz = timezone(
            self.MORNING.astimezone().utcoffset() or timedelta()
        )
        untrusted = self.decide(
            untrusted_optimizer,
            self._forecast_state(
                self.MORNING,
                today_trusted=False,
                **state_values,
            ),
            self.MORNING,
        )

        self.assertTrue(trusted.standby_holdoff_active)
        self.assertFalse(untrusted.standby_holdoff_active)


if __name__ == "__main__":
    import unittest

    unittest.main()
