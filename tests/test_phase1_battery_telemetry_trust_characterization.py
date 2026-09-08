from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from app.models import BATTERY_EXPORT, EXPORT_BLOCKED, MSC_SURPLUS_CEILING
from app.optimizer import MODE_CMD_CHARGE_PV, MODE_MAX_SELF
from haos49_characterization_helpers import Haos49CharacterizationCase, RecordingHA


_MISSING = object()


class Phase1BatteryTelemetryTrustCharacterizationTests(Haos49CharacterizationCase):
    """Desired Package 4B battery-telemetry trust contract before repair."""

    MORNING = datetime(2026, 1, 15, 6, 0, 0)
    EVENING = datetime(2026, 1, 15, 17, 30, 0)

    @staticmethod
    def _entity(
        state: object,
        when: datetime,
        attributes: dict[str, object] | None = None,
        *,
        observed_at: datetime | None = None,
    ) -> dict[str, object]:
        reported = observed_at or when
        reported_utc = datetime.fromtimestamp(reported.timestamp(), timezone.utc)
        return {
            "state": state,
            "attributes": dict(attributes or {}),
            "last_reported": reported_utc.isoformat(),
        }

    def _read_and_decide(
        self,
        *,
        when: datetime | None = None,
        battery_soc_state: object = "60.0",
        battery_soc_observed_at: datetime | None = None,
        capacity_state: object = "30.0",
        capacity_observed_at: datetime | None = None,
        available_energy_state: object = "18.0",
        available_energy_observed_at: datetime | None = None,
        price_state: object = "0.30",
        price_is_estimate: bool = False,
        feedin_state: object = "0.0",
        price_spike_state: str = "off",
        pv_kw: float = 0.0,
        load_kw: float = 1.0,
        battery_power_kw: float = 0.0,
        grid_export_kw: float = 0.0,
        forecast_remaining_kwh: float = 100.0,
        forecast_tomorrow_kwh: float = 100.0,
        solcast_detailed: list[dict[str, object]] | None = None,
        **settings_overrides: object,
    ):
        when = when or self.FIXED_AFTERNOON
        ha = RecordingHA()
        optimizer = self.optimizer(ha=ha, **settings_overrides)
        cfg = optimizer.cfg

        states: dict[str, dict[str, object]] = {
            cfg.pv_power_sensor: self._entity(pv_kw, when),
            cfg.consumed_power_sensor: self._entity(load_kw, when),
            cfg.battery_power_sensor: self._entity(battery_power_kw, when),
            cfg.grid_import_power_sensor: self._entity(0.0, when),
            cfg.grid_export_power_sensor: self._entity(grid_export_kw, when),
            cfg.ess_rated_discharge_power_sensor: self._entity(25.0, when),
            cfg.ess_rated_charge_power_sensor: self._entity(25.0, when),
            cfg.sun_entity: self._entity(
                "above_horizon" if when.hour >= 7 else "below_horizon",
                when,
                {
                    "elevation": 45.0 if when.hour >= 7 else -5.0,
                    "next_rising": (when + timedelta(hours=1)).isoformat(),
                    "next_setting": (when + timedelta(hours=12)).isoformat(),
                },
            ),
            cfg.price_sensor: self._entity(
                price_state,
                when,
                {"estimate": price_is_estimate},
            ),
            cfg.feedin_sensor: self._entity(feedin_state, when),
            cfg.demand_window_sensor: self._entity("off", when),
            cfg.price_spike_sensor: self._entity(price_spike_state, when),
            cfg.forecast_remaining_sensor: self._entity(forecast_remaining_kwh, when),
            cfg.forecast_today_sensor: self._entity(
                100.0,
                when,
                {"detailedForecast": list(solcast_detailed or [])},
            ),
            cfg.forecast_tomorrow_sensor: self._entity(forecast_tomorrow_kwh, when),
            cfg.solar_power_now_sensor: self._entity(pv_kw, when),
            cfg.grid_export_limit: self._entity(0.01, when, {"max": 25.0}),
            cfg.grid_import_limit: self._entity(0.01, when, {"max": 25.0}),
            cfg.pv_max_power_limit: self._entity(25.0, when, {"max": 25.0}),
            cfg.ems_mode_select: self._entity(MODE_MAX_SELF, when),
            cfg.ha_control_switch: self._entity("on", when),
            cfg.sigenergy_mode_select: self._entity(cfg.automated_option, when),
        }
        if battery_soc_state is not _MISSING:
            states[cfg.battery_soc_sensor] = self._entity(
                battery_soc_state,
                when,
                observed_at=battery_soc_observed_at,
            )
        if capacity_state is not _MISSING:
            states[cfg.rated_capacity_sensor] = self._entity(
                capacity_state,
                when,
                {"unit_of_measurement": "kWh"},
                observed_at=capacity_observed_at,
            )
        if available_energy_state is not _MISSING:
            states[cfg.available_discharge_sensor] = self._entity(
                available_energy_state,
                when,
                {"unit_of_measurement": "kWh"},
                observed_at=available_energy_observed_at,
            )

        ha.states = states
        with self.optimizer_time(when):
            state = asyncio.run(optimizer._read_state())
            decision = optimizer._decide(state)
        return optimizer, state, decision

    def _assert_no_positive_price_topup(self, raw_soc: object, **overrides: object) -> None:
        _optimizer, _state, decision = self._read_and_decide(
            battery_soc_state=raw_soc,
            available_energy_state="0.0",
            price_state="0.01",
            price_is_estimate=True,
            feedin_state="0.0",
            forecast_remaining_kwh=0.0,
            **overrides,
        )
        self.assertEqual(0.0, decision.import_limit)
        self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
        self.assertNotEqual("cheap_topup_import", decision.trace_values.get("import_branch"))

    def _assert_no_deliberate_export(self, **overrides: object) -> None:
        _optimizer, _state, decision = self._read_and_decide(**overrides)
        self.assertNotEqual(BATTERY_EXPORT, decision.export_intent)
        self.assertEqual("none", decision.trace_values.get("battery_export_owner"))

    @staticmethod
    def _morning_forecast(when: datetime, pv_estimate: float) -> list[dict[str, object]]:
        return [
            {
                "period_start": (when + timedelta(hours=hours)).isoformat(),
                "pv_estimate": pv_estimate,
            }
            for hours in (3, 5, 7, 9, 11)
        ]

    # Unavailable and non-finite SoC must not become a permissive synthetic 0%.
    def test_missing_soc_cannot_authorize_positive_price_topup(self) -> None:
        self._assert_no_positive_price_topup(_MISSING)

    def test_unavailable_soc_cannot_authorize_positive_price_topup(self) -> None:
        self._assert_no_positive_price_topup("unavailable")

    def test_unknown_soc_cannot_authorize_positive_price_topup(self) -> None:
        self._assert_no_positive_price_topup("unknown")

    def test_nan_soc_cannot_authorize_positive_price_topup(self) -> None:
        self._assert_no_positive_price_topup("nan")

    def test_positive_infinity_soc_cannot_authorize_positive_price_topup(self) -> None:
        self._assert_no_positive_price_topup("inf")

    def test_negative_infinity_soc_cannot_authorize_positive_price_topup(self) -> None:
        self._assert_no_positive_price_topup("-inf")

    # Finite but invalid SoC must not be clamped into trusted boundary evidence.
    def test_below_range_soc_cannot_authorize_positive_price_topup(self) -> None:
        self._assert_no_positive_price_topup("-1.0")

    def test_above_range_soc_cannot_establish_exact_full_pv_permission(self) -> None:
        _optimizer, _state, decision = self._read_and_decide(
            battery_soc_state="101.0",
            available_energy_state="30.0",
            feedin_state="0.095",
            pv_kw=6.0,
            load_kw=1.0,
        )
        self.assertFalse(bool(decision.trace_gates.get("topoff_target_met")))
        self.assertFalse(bool(decision.trace_gates.get("pv_only_msc_high_ceiling_active")))
        self.assertEqual(EXPORT_BLOCKED, decision.export_intent)
        self.assertLessEqual(decision.export_limit, 0.01)

    # SoC freshness currently has live metadata available but no decision provenance.
    def test_stale_low_soc_cannot_authorize_positive_price_topup(self) -> None:
        self._assert_no_positive_price_topup(
            "30.0",
            battery_soc_observed_at=self.FIXED_AFTERNOON - timedelta(hours=2),
        )

    def test_stale_high_soc_cannot_authorize_deliberate_high_price_export(self) -> None:
        self._assert_no_deliberate_export(
            battery_soc_state="95.0",
            battery_soc_observed_at=self.FIXED_AFTERNOON - timedelta(hours=2),
            available_energy_state="28.5",
            feedin_state="1.10",
            pv_kw=4.0,
            load_kw=1.0,
        )

    # Unknown SoC is already conservative for representative deliberate owners.
    def test_unavailable_soc_does_not_authorize_high_price_export(self) -> None:
        self._assert_no_deliberate_export(
            battery_soc_state="unavailable",
            available_energy_state="0.0",
            feedin_state="1.10",
            pv_kw=4.0,
            load_kw=1.0,
        )

    def test_unavailable_soc_does_not_authorize_morning_dump(self) -> None:
        self._assert_no_deliberate_export(
            when=self.MORNING,
            battery_soc_state="unavailable",
            available_energy_state="0.0",
            feedin_state="0.05",
            solcast_detailed=self._morning_forecast(self.MORNING, 10.0),
            morning_dump_enabled=True,
        )

    def test_unavailable_soc_does_not_authorize_evening_boost(self) -> None:
        self._assert_no_deliberate_export(
            when=self.EVENING,
            battery_soc_state="unavailable",
            available_energy_state="0.0",
            feedin_state="0.15",
            forecast_tomorrow_kwh=120.0,
            evening_boost_enabled=True,
            evening_boost_min_tomorrow_forecast_kwh=100.0,
        )

    # Genuine boundary observations remain valid controls.
    def test_genuine_finite_zero_soc_remains_observed_as_zero(self) -> None:
        _optimizer, state, _decision = self._read_and_decide(battery_soc_state="0.0")
        self.assertEqual(0.0, state.battery_soc)

    def test_genuine_finite_100_soc_preserves_exact_full_pv_permission(self) -> None:
        optimizer, state, decision = self._read_and_decide(
            battery_soc_state="100.0",
            available_energy_state="30.0",
            feedin_state="0.095",
            pv_kw=6.0,
            load_kw=1.0,
        )
        self.assertEqual(100.0, state.battery_soc)
        self.assertTrue(bool(decision.trace_gates.get("topoff_target_met")))
        self.assertTrue(bool(decision.trace_gates.get("pv_only_msc_high_ceiling_active")))
        self.assertEqual(MSC_SURPLUS_CEILING, decision.export_intent)
        self.assertEqual(optimizer.cfg.export_limit_high, decision.export_limit)
        self.assertEqual(MODE_MAX_SELF, decision.ems_mode)

    def test_unavailable_and_nonfinite_soc_do_not_establish_exact_full(self) -> None:
        for raw_soc in (_MISSING, "unavailable", "unknown", "nan", "inf", "-inf"):
            with self.subTest(raw_soc=raw_soc):
                _optimizer, _state, decision = self._read_and_decide(
                    battery_soc_state=raw_soc,
                    available_energy_state="30.0",
                    feedin_state="0.095",
                    pv_kw=6.0,
                    load_kw=1.0,
                )
                self.assertFalse(bool(decision.trace_gates.get("topoff_target_met")))
                self.assertFalse(
                    bool(decision.trace_gates.get("pv_only_msc_high_ceiling_active"))
                )

    # Unknown SoC must not globally seize an unrelated trusted MSC surplus ceiling.
    def test_unknown_soc_does_not_block_ordinary_trusted_msc_surplus(self) -> None:
        optimizer, _state, decision = self._read_and_decide(
            battery_soc_state="unavailable",
            available_energy_state="0.0",
            feedin_state="0.15",
            pv_kw=4.0,
            load_kw=1.0,
            battery_power_kw=0.0,
            grid_export_kw=0.0,
        )
        self.assertEqual(MSC_SURPLUS_CEILING, decision.export_intent)
        self.assertEqual(optimizer.cfg.export_limit_high, decision.export_limit)
        self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
        self.assertEqual("none", decision.trace_values.get("battery_export_owner"))

    # Capacity and available-energy trust matters only where it changes eligibility.
    def test_missing_capacity_cannot_authorize_positive_price_topup(self) -> None:
        _optimizer, state, decision = self._read_and_decide(
            battery_soc_state="30.0",
            capacity_state=_MISSING,
            available_energy_state="0.0",
            price_state="0.01",
            price_is_estimate=True,
            feedin_state="0.0",
            forecast_remaining_kwh=0.0,
        )
        self.assertEqual(
            0.0,
            decision.import_limit,
            f"missing capacity was represented as {state.battery_capacity_kwh} kWh",
        )
        self.assertEqual(MODE_MAX_SELF, decision.ems_mode)

    def test_missing_capacity_cannot_authorize_morning_dump(self) -> None:
        self._assert_no_deliberate_export(
            when=self.MORNING,
            battery_soc_state="80.0",
            capacity_state=_MISSING,
            available_energy_state="10.0",
            feedin_state="0.05",
            solcast_detailed=self._morning_forecast(self.MORNING, 10.0),
            morning_dump_enabled=True,
        )

    def test_stale_high_available_energy_cannot_authorize_morning_dump(self) -> None:
        self._assert_no_deliberate_export(
            when=self.MORNING,
            battery_soc_state="80.0",
            capacity_state="30.0",
            available_energy_state="30.0",
            available_energy_observed_at=self.MORNING - timedelta(hours=2),
            feedin_state="0.05",
            solcast_detailed=self._morning_forecast(self.MORNING, 10.0),
            morning_dump_enabled=True,
        )

    def test_missing_available_energy_fallback_is_conservative_for_morning_dump(self) -> None:
        _optimizer, state, decision = self._read_and_decide(
            when=self.MORNING,
            battery_soc_state="80.0",
            capacity_state="30.0",
            available_energy_state=_MISSING,
            feedin_state="0.05",
            solcast_detailed=self._morning_forecast(self.MORNING, 1.0),
            morning_dump_enabled=True,
        )
        self.assertEqual(0.0, state.available_discharge_energy_kwh)
        self.assertEqual(30.0, decision.trace_values.get("bat_fill_need_kwh"))
        self.assertFalse(bool(decision.trace_gates.get("morning_dump_active")))
        self.assertNotEqual(BATTERY_EXPORT, decision.export_intent)

    def test_fresh_capacity_and_available_energy_preserve_morning_dump_control(self) -> None:
        _optimizer, state, decision = self._read_and_decide(
            when=self.MORNING,
            battery_soc_state="80.0",
            capacity_state="30.0",
            available_energy_state="24.0",
            feedin_state="0.05",
            solcast_detailed=self._morning_forecast(self.MORNING, 10.0),
            morning_dump_enabled=True,
        )
        self.assertEqual(30.0, state.battery_capacity_kwh)
        self.assertEqual(24.0, state.available_discharge_energy_kwh)
        self.assertTrue(bool(decision.trace_gates.get("morning_dump_active")))
        self.assertEqual(BATTERY_EXPORT, decision.export_intent)
        self.assertEqual("morning_dump", decision.trace_values.get("battery_export_owner"))


if __name__ == "__main__":
    import unittest

    unittest.main()
