from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from app.models import BATTERY_EXPORT, MSC_SURPLUS_CEILING
from app.optimizer import DISCHARGE_MODES, MODE_MAX_SELF
from haos49_characterization_helpers import Haos49CharacterizationCase


class SolarBudgetCyclingCharacterizationTests(Haos49CharacterizationCase):
    WHEN = datetime(2026, 1, 15, 14, 0, 0)

    def _decision(self, optimizer, when: datetime, load_kw: float):
        state = self.state(
            when,
            sigenergy_mode_observed=True,
            current_ems_mode=MODE_MAX_SELF,
            ems_mode_observed=True,
            battery_soc=80.0,
            battery_soc_trusted=True,
            battery_capacity_kwh=10.0,
            battery_capacity_trusted=True,
            available_discharge_energy_kwh=8.0,
            available_discharge_energy_trusted=True,
            pv_kw=10.0,
            pv_power_trusted=True,
            load_kw=load_kw,
            load_power_trusted=True,
            pv_load_observations_coherent=True,
            solar_power_now_kw=10.0,
            feedin_price=0.01,
            feedin_price_cents=1.0,
            forecast_remaining_kwh=7.5,
            forecast_remaining_observation_trusted=True,
            forecast_today_kwh=20.0,
            forecast_today_observation_trusted=True,
            sun_above_horizon=True,
            sun_state_observation_trusted=True,
            next_sunset_ts=(when + timedelta(hours=4)).timestamp(),
            sunset_observation_trusted=True,
            hours_to_sunset=4.0,
            solcast_detailed=[
                {
                    "period_start": datetime.fromtimestamp(
                        (when + timedelta(minutes=30 * i)).timestamp(), timezone.utc,
                    ).isoformat(),
                    "pv_estimate": 5.0,
                }
                for i in range(8)
            ],
            solcast_detailed_source_trusted=True,
            ess_max_charge_kw=5.0,
            ess_max_discharge_kw=25.0,
            grid_export_limit_entity_max_kw=25.0,
            grid_export_power_kw=0.0,
            grid_import_power_kw=0.0,
            current_export_limit=0.01,
            current_export_limit_observed=True,
            current_import_limit=0.01,
            current_import_limit_observed=True,
            current_pv_max_power_limit=25.0,
            current_ess_charge_limit=25.0,
            current_ess_discharge_limit=25.0,
            demand_window_observed=True,
        )
        state.solcast_provider_source = (
            optimizer.cfg.forecast_today_sensor,
            optimizer.cfg.solcast_api_last_polled_sensor,
        )
        state.solcast_provider_epoch = optimizer._solar_provider_epoch
        state.solcast_provider_continuity = True
        state.solcast_provider_polled = datetime.fromtimestamp(
            when.timestamp() - 1, timezone.utc,
        ).isoformat()
        state.solcast_provider_next_update = datetime.fromtimestamp(
            when.timestamp() + 3600, timezone.utc,
        ).isoformat()
        if not optimizer._solar_provider_baselined:
            baseline = replace(
                state,
                solcast_provider_polled=datetime.fromtimestamp(
                    when.timestamp() - 60, timezone.utc,
                ).isoformat(),
            )
            with self.optimizer_time(when):
                optimizer._update_solar_provider(baseline, when.timestamp())
        return self.decide(optimizer, state, when)

    def test_load_only_budget_crossing_releases_and_restores_solar_owner(self) -> None:
        optimizer = self.optimizer(
            solar_surplus_bypass_enabled=True,
            solar_surplus_forecast_safety_factor=1.20,
            solar_surplus_fill_deadline_margin_minutes=0.0,
            battery_full_safeguard_enabled=False,
            morning_dump_enabled=False,
            morning_slow_charge_enabled=False,
            evening_boost_enabled=False,
            standby_holdoff_enabled=False,
            export_limit_high=25.0,
            pv_max_power_normal=25.0,
        )

        active = self._decision(optimizer, self.WHEN, 1.0)
        optimizer._last_decision = active
        deficit = self._decision(optimizer, self.WHEN + timedelta(minutes=1), 1.1)
        optimizer._last_decision = deficit
        recovered = self._decision(optimizer, self.WHEN + timedelta(minutes=2), 1.0)

        self.assertTrue(active.solar_surplus_policy_active, active.trace_values.get("solar_surplus_fail_reason"))
        self.assertTrue(active.trace_gates["solar_charge_ceiling_owned"])
        self.assertEqual(MSC_SURPLUS_CEILING, active.export_intent)
        self.assertEqual("none", active.trace_values["battery_export_owner"])
        self.assertGreater(active.trace_values["solar_raw_exportable_energy_kwh"], 0.0)
        self.assertGreater(
            active.trace_values["solar_measured_pv_surplus_kw"],
            active.trace_values["solar_surplus_threshold_kw"],
        )

        self.assertFalse(deficit.solar_surplus_policy_active)
        self.assertFalse(deficit.trace_gates["solar_charge_ceiling_owned"])
        self.assertLess(deficit.trace_values["solar_raw_exportable_energy_kwh"], 0.0)
        self.assertEqual(
            active.trace_values["solar_remaining_forecast_kwh"],
            deficit.trace_values["solar_remaining_forecast_kwh"],
        )
        self.assertEqual(
            active.trace_values["solar_fill_need_to_full_kwh"],
            deficit.trace_values["solar_fill_need_to_full_kwh"],
        )
        self.assertEqual("none", deficit.trace_values["battery_export_owner"])
        self.assertNotEqual(BATTERY_EXPORT, deficit.export_intent)
        self.assertNotIn(deficit.ems_mode, DISCHARGE_MODES)
        self.assertGreater(
            deficit.trace_values["solar_measured_pv_surplus_kw"],
            deficit.trace_values["solar_surplus_threshold_kw"],
        )

        self.assertTrue(recovered.solar_surplus_policy_active)
        self.assertTrue(recovered.trace_gates["solar_charge_ceiling_owned"])
        self.assertEqual(MSC_SURPLUS_CEILING, recovered.export_intent)
        self.assertEqual(MODE_MAX_SELF, recovered.ems_mode)
        self.assertGreater(recovered.trace_values["solar_raw_exportable_energy_kwh"], 0.0)


if __name__ == "__main__":
    unittest.main()
