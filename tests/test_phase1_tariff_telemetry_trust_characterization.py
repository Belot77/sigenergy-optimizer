from __future__ import annotations

import asyncio
import math
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.models import BATTERY_EXPORT, EXPORT_BLOCKED, MSC_SURPLUS_CEILING, Decision, SolarState
from app.optimizer import (
    MODE_CMD_CHARGE_GRID,
    MODE_CMD_CHARGE_PV,
    MODE_CMD_DISCHARGE_PV,
    MODE_MAX_SELF,
)
from haos49_characterization_helpers import Haos49CharacterizationCase, RecordingHA


_MISSING = object()


class Phase1TariffTelemetryTrustCharacterizationTests(Haos49CharacterizationCase):
    """Desired Package 4A tariff-trust contract before production repair."""

    MORNING = datetime(2026, 1, 15, 8, 0, 0)

    @staticmethod
    def _entity(
        state: object,
        when: datetime,
        attributes: dict[str, object] | None = None,
    ) -> dict[str, object]:
        observed_at = datetime.fromtimestamp(when.timestamp(), timezone.utc)
        return {
            "state": state,
            "attributes": dict(attributes or {}),
            "last_reported": observed_at.isoformat(),
        }

    def _read_and_decide(
        self,
        *,
        when: datetime | None = None,
        price_state: object = "0.30",
        feedin_state: object = "0.0",
        price_is_estimate: bool = False,
        price_spike_state: str = "off",
        include_negative_price_forecast: bool = False,
        battery_soc: float = 60.0,
        available_discharge_kwh: float = 18.0,
        pv_kw: float = 0.0,
        load_kw: float = 1.0,
        forecast_remaining_kwh: float = 100.0,
        **settings_overrides: object,
    ):
        when = when or self.FIXED_AFTERNOON
        ha = RecordingHA()
        optimizer = self.optimizer(ha=ha, **settings_overrides)
        cfg = optimizer.cfg

        states: dict[str, dict[str, object]] = {
            cfg.pv_power_sensor: self._entity(pv_kw, when),
            cfg.consumed_power_sensor: self._entity(load_kw, when),
            cfg.battery_power_sensor: self._entity(0.0, when),
            cfg.grid_import_power_sensor: self._entity(0.0, when),
            cfg.grid_export_power_sensor: self._entity(0.0, when),
            cfg.battery_soc_sensor: self._entity(battery_soc, when),
            cfg.rated_capacity_sensor: self._entity(
                30.0,
                when,
                {"unit_of_measurement": "kWh"},
            ),
            cfg.available_discharge_sensor: self._entity(
                available_discharge_kwh,
                when,
                {"unit_of_measurement": "kWh"},
            ),
            cfg.ess_rated_discharge_power_sensor: self._entity(25.0, when),
            cfg.ess_rated_charge_power_sensor: self._entity(25.0, when),
            cfg.sun_entity: self._entity(
                "above_horizon",
                when,
                {
                    "elevation": 45.0,
                    "next_rising": (when + timedelta(hours=17)).isoformat(),
                    "next_setting": (when + timedelta(hours=4)).isoformat(),
                },
            ),
            cfg.demand_window_sensor: self._entity("off", when),
            cfg.price_spike_sensor: self._entity(price_spike_state, when),
            cfg.forecast_remaining_sensor: self._entity(forecast_remaining_kwh, when),
            cfg.forecast_today_sensor: self._entity(
                100.0,
                when,
                {"detailedForecast": []},
            ),
            cfg.forecast_tomorrow_sensor: self._entity(100.0, when),
            cfg.solar_power_now_sensor: self._entity(pv_kw, when),
            cfg.grid_export_limit: self._entity(0.01, when, {"max": 25.0}),
            cfg.grid_import_limit: self._entity(0.01, when, {"max": 25.0}),
            cfg.pv_max_power_limit: self._entity(25.0, when, {"max": 25.0}),
            cfg.ems_mode_select: self._entity(MODE_MAX_SELF, when),
            cfg.ha_control_switch: self._entity("on", when),
            cfg.sigenergy_mode_select: self._entity(cfg.automated_option, when),
        }
        if price_state is not _MISSING:
            states[cfg.price_sensor] = self._entity(
                price_state,
                when,
                {"estimate": price_is_estimate},
            )
        if feedin_state is not _MISSING:
            states[cfg.feedin_sensor] = self._entity(feedin_state, when)
        if include_negative_price_forecast:
            states[cfg.price_forecast_sensor] = self._entity(
                "available",
                when,
                {
                    cfg.price_forecast_attribute: [
                        {
                            cfg.price_forecast_time_key: (when + timedelta(hours=1)).isoformat(),
                            cfg.price_forecast_value_key: -0.20,
                        }
                    ]
                },
            )

        ha.states = states
        with self.optimizer_time(when):
            state = asyncio.run(optimizer._read_state())
            decision = optimizer._decide(state)
        return optimizer, state, decision

    def _assert_nonfinite_import_price_fails_closed(self, raw_price: str) -> None:
        optimizer, state, decision = self._read_and_decide(
            price_state=raw_price,
            feedin_state="0.0",
            battery_soc=30.0,
            available_discharge_kwh=9.0,
            pv_kw=0.0,
            load_kw=1.0,
            forecast_remaining_kwh=0.0,
        )

        self.assertEqual(
            (
                False,
                False,
                False,
                0.0,
                MODE_MAX_SELF,
                optimizer.cfg.pv_max_power_normal,
                optimizer.get_power_caps_kw(state)[1],
            ),
            (
                state.price_is_actual,
                state.price_is_estimated,
                decision.trace_gates.get("price_is_negative"),
                decision.import_limit,
                decision.ems_mode,
                decision.pv_max_power_limit,
                decision.ess_discharge_limit,
            ),
        )

    def test_nan_actual_import_price_cannot_authorize_import(self) -> None:
        self._assert_nonfinite_import_price_fails_closed("nan")

    def test_positive_infinity_actual_import_price_cannot_authorize_import(self) -> None:
        self._assert_nonfinite_import_price_fails_closed("+inf")

    def test_negative_infinity_actual_import_price_cannot_authorize_import(self) -> None:
        self._assert_nonfinite_import_price_fails_closed("-inf")

    def _assert_nonfinite_feedin_fails_closed(
        self,
        raw_feedin: str,
        *,
        price_spike_state: str = "off",
    ) -> None:
        optimizer, state, decision = self._read_and_decide(
            price_state="0.30",
            feedin_state=raw_feedin,
            price_spike_state=price_spike_state,
            battery_soc=95.0,
            available_discharge_kwh=28.5,
            pv_kw=4.0,
            load_kw=1.0,
            allow_low_medium_export_positive_fit=True,
            allow_positive_fit_battery_discharging=True,
            export_spike_threshold=0.60,
        )

        self.assertEqual(
            (
                True,
                False,
                False,
                "none",
                EXPORT_BLOCKED,
                0.0,
                MODE_MAX_SELF,
                optimizer.get_power_caps_kw(state)[1],
            ),
            (
                math.isfinite(decision.export_limit),
                decision.trace_gates.get("positive_fit_override"),
                decision.trace_gates.get("export_spike_active"),
                decision.trace_values.get("battery_export_owner"),
                decision.export_intent,
                decision.export_limit,
                decision.ems_mode,
                decision.ess_discharge_limit,
            ),
        )

    def test_nan_feedin_price_cannot_create_export_ownership(self) -> None:
        self._assert_nonfinite_feedin_fails_closed("nan")

    def test_positive_infinity_feedin_price_cannot_create_export_ownership(self) -> None:
        self._assert_nonfinite_feedin_fails_closed("+inf")

    def test_negative_infinity_feedin_price_cannot_create_export_ownership(self) -> None:
        self._assert_nonfinite_feedin_fails_closed("-inf")

    def test_positive_infinity_feedin_price_cannot_create_spike_owner(self) -> None:
        self._assert_nonfinite_feedin_fails_closed(
            "+inf",
            price_spike_state="on",
        )

    def test_nan_feedin_price_cannot_activate_morning_slow(self) -> None:
        optimizer, state, decision = self._read_and_decide(
            when=self.MORNING,
            price_state="0.30",
            feedin_state="nan",
            battery_soc=60.0,
            available_discharge_kwh=18.0,
            pv_kw=0.0,
            load_kw=1.0,
            forecast_remaining_kwh=100.0,
            morning_slow_charge_enabled=True,
            morning_slow_charge_until="11:00",
            morning_slow_charge_min_feedin_price=0.01,
            morning_slow_charge_base_load_kw=0.0,
        )

        self.assertEqual(
            (
                False,
                "none",
                EXPORT_BLOCKED,
                0.0,
                MODE_MAX_SELF,
                optimizer.get_power_caps_kw(state)[1],
            ),
            (
                decision.morning_slow_charge_active,
                decision.trace_values.get("battery_export_owner"),
                decision.export_intent,
                decision.export_limit,
                decision.ems_mode,
                decision.ess_discharge_limit,
            ),
        )

    def _assert_untrusted_current_price_does_not_activate_holdoff(
        self,
        price_state: object,
    ) -> None:
        optimizer, _state, decision = self._read_and_decide(
            when=self.MORNING,
            price_state=price_state,
            feedin_state="0.0",
            include_negative_price_forecast=True,
            battery_soc=90.0,
            available_discharge_kwh=27.0,
            forecast_remaining_kwh=100.0,
            standby_holdoff_enabled=True,
            standby_holdoff_end_time="11:00",
            pv_forecast_holdoff_kwh=50.0,
        )

        self.assertEqual(
            (
                False,
                0.0,
                MODE_MAX_SELF,
                optimizer.cfg.pv_max_power_normal,
            ),
            (
                decision.standby_holdoff_active,
                decision.import_limit,
                decision.ems_mode,
                decision.pv_max_power_limit,
            ),
        )

    def test_missing_current_price_cannot_activate_standby_holdoff(self) -> None:
        self._assert_untrusted_current_price_does_not_activate_holdoff(_MISSING)

    def test_unavailable_current_price_cannot_activate_standby_holdoff(self) -> None:
        self._assert_untrusted_current_price_does_not_activate_holdoff("unavailable")

    def _assert_untrusted_feedin_does_not_authorize_cheap_positive_import(
        self,
        feedin_state: object,
    ) -> None:
        optimizer, state, decision = self._read_and_decide(
            price_state="0.01",
            feedin_state=feedin_state,
            battery_soc=30.0,
            available_discharge_kwh=9.0,
            pv_kw=0.0,
            load_kw=1.0,
            forecast_remaining_kwh=0.0,
        )

        self.assertEqual(
            (
                0.0,
                MODE_MAX_SELF,
                optimizer.get_power_caps_kw(state)[0],
            ),
            (
                decision.import_limit,
                decision.ems_mode,
                decision.ess_charge_limit,
            ),
        )

    def test_missing_feedin_cannot_authorize_cheap_positive_import(self) -> None:
        self._assert_untrusted_feedin_does_not_authorize_cheap_positive_import(_MISSING)

    def test_unavailable_feedin_cannot_authorize_cheap_positive_import(self) -> None:
        self._assert_untrusted_feedin_does_not_authorize_cheap_positive_import("unavailable")

    def _assert_optimizer_tracking_rejects_nonfinite_price(self, price: float) -> None:
        optimizer = self.optimizer()
        now = datetime(2026, 1, 15, 9, 0, 0)
        state = SolarState(
            current_price=price,
            price_is_actual=True,
            daily_import_kwh=1.0,
        )
        decision = Decision(import_limit=2.0)
        optimizer._last_optimizer_import_daily_kwh = 0.0
        optimizer._last_optimizer_import_track_at = now - timedelta(minutes=5)

        with patch.object(
            optimizer._state_store,
            "record_optimizer_import_topup",
            wraps=optimizer._state_store.record_optimizer_import_topup,
        ) as record:
            optimizer._record_optimizer_import_topup(state, decision, now)

        self.assertEqual(
            (False, None),
            (
                record.call_args.kwargs["price_trusted"],
                record.call_args.kwargs["import_price"],
            ),
        )

    def test_nan_import_price_is_not_recorded_as_trusted_cost(self) -> None:
        self._assert_optimizer_tracking_rejects_nonfinite_price(math.nan)

    def test_positive_infinity_import_price_is_not_recorded_as_trusted_cost(self) -> None:
        self._assert_optimizer_tracking_rejects_nonfinite_price(math.inf)

    def test_negative_infinity_import_price_is_not_recorded_as_trusted_cost(self) -> None:
        self._assert_optimizer_tracking_rejects_nonfinite_price(-math.inf)

    def _assert_state_store_defensively_rejects_nonfinite_price(
        self,
        price: float,
        date: str,
    ) -> None:
        optimizer = self.optimizer()
        optimizer._state_store.record_optimizer_import_topup(
            date=date,
            ts=f"{date}T09:00:00+10:00",
            import_kwh=1.0,
            import_price=price,
            price_trusted=True,
        )

        summary = optimizer._state_store.optimizer_import_topup_summary(date)

        self.assertEqual(
            (None, False, True),
            (
                summary["import_cost_export_floor"],
                summary["import_cost_floor_trusted"],
                summary["import_cost_floor_unknown"],
            ),
        )

    def test_state_store_defensively_rejects_nan_trusted_price(self) -> None:
        self._assert_state_store_defensively_rejects_nonfinite_price(
            math.nan,
            "2026-01-15",
        )

    def test_state_store_defensively_rejects_positive_infinity_trusted_price(self) -> None:
        self._assert_state_store_defensively_rejects_nonfinite_price(
            math.inf,
            "2026-01-16",
        )

    def test_state_store_defensively_rejects_negative_infinity_trusted_price(self) -> None:
        self._assert_state_store_defensively_rejects_nonfinite_price(
            -math.inf,
            "2026-01-17",
        )

    def test_fresh_finite_estimated_positive_price_preserves_cheap_topup(self) -> None:
        optimizer, state, decision = self._read_and_decide(
            price_state="0.01",
            price_is_estimate=True,
            feedin_state="0.0",
            battery_soc=30.0,
            available_discharge_kwh=9.0,
            pv_kw=0.0,
            load_kw=1.0,
            forecast_remaining_kwh=0.0,
        )

        self.assertFalse(state.price_is_actual)
        self.assertTrue(state.price_is_estimated)
        self.assertEqual(2.0, decision.import_limit)
        self.assertEqual(MODE_CMD_CHARGE_PV, decision.ems_mode)
        self.assertEqual(2.0, decision.ess_charge_limit)
        self.assertEqual(optimizer.get_power_caps_kw(state)[1], decision.ess_discharge_limit)

    def test_fresh_finite_actual_negative_price_preserves_grid_charge(self) -> None:
        optimizer, state, decision = self._read_and_decide(
            price_state="-0.35",
            feedin_state="0.0",
            battery_soc=30.0,
            available_discharge_kwh=9.0,
            pv_kw=0.0,
            load_kw=1.0,
            forecast_remaining_kwh=0.0,
        )

        self.assertTrue(state.price_is_actual)
        self.assertTrue(decision.trace_gates.get("price_is_negative"))
        self.assertEqual(optimizer.get_power_caps_kw(state)[0], decision.import_limit)
        self.assertEqual(MODE_CMD_CHARGE_GRID, decision.ems_mode)
        self.assertEqual(0.1, decision.pv_max_power_limit)
        self.assertEqual(0.01, decision.ess_discharge_limit)

    def test_fresh_finite_positive_fit_preserves_positive_fit_battery_owner(self) -> None:
        optimizer, state, decision = self._read_and_decide(
            price_state="0.30",
            feedin_state="0.05",
            battery_soc=95.0,
            available_discharge_kwh=28.5,
            pv_kw=4.0,
            load_kw=1.0,
            allow_low_medium_export_positive_fit=True,
            allow_positive_fit_battery_discharging=True,
        )

        self.assertEqual("positive_fit_override", decision.trace_values.get("battery_export_owner"))
        self.assertEqual(BATTERY_EXPORT, decision.export_intent)
        self.assertGreater(decision.export_limit, 0.01)
        self.assertEqual(MODE_CMD_DISCHARGE_PV, decision.ems_mode)
        self.assertEqual(optimizer.get_power_caps_kw(state)[1], decision.ess_discharge_limit)

    def test_fresh_finite_morning_slow_fit_preserves_package2_semantics(self) -> None:
        optimizer, state, decision = self._read_and_decide(
            when=self.MORNING,
            price_state="0.30",
            feedin_state="0.15",
            battery_soc=95.0,
            available_discharge_kwh=28.5,
            pv_kw=3.2,
            load_kw=1.1,
            forecast_remaining_kwh=100.0,
            morning_slow_charge_enabled=True,
            morning_slow_charge_until="11:00",
            morning_slow_charge_min_feedin_price=0.01,
            morning_slow_charge_base_load_kw=0.0,
        )

        self.assertTrue(decision.morning_slow_charge_active)
        self.assertEqual("none", decision.trace_values.get("battery_export_owner"))
        self.assertEqual(MSC_SURPLUS_CEILING, decision.export_intent)
        self.assertGreater(decision.export_limit, 0.01)
        self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
        self.assertEqual(optimizer.cfg.morning_slow_charge_rate_kw, decision.ess_charge_limit)
        self.assertEqual(optimizer.get_power_caps_kw(state)[1], decision.ess_discharge_limit)

    def test_fresh_finite_optimizer_import_cost_remains_trusted(self) -> None:
        optimizer = self.optimizer()
        now = datetime(2026, 1, 15, 9, 0, 0)
        state = SolarState(
            current_price=0.16,
            price_is_actual=True,
            daily_import_kwh=1.0,
        )
        decision = Decision(import_limit=2.0)
        optimizer._last_optimizer_import_daily_kwh = 0.0
        optimizer._last_optimizer_import_track_at = now - timedelta(minutes=5)

        optimizer._record_optimizer_import_topup(state, decision, now)
        summary = optimizer._state_store.optimizer_import_topup_summary("2026-01-15")

        self.assertEqual(0.16, summary["import_cost_export_floor"])
        self.assertTrue(summary["import_cost_floor_trusted"])
        self.assertFalse(summary["import_cost_floor_unknown"])
