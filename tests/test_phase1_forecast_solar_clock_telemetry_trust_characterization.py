from __future__ import annotations

import asyncio
from datetime import datetime, time, timedelta, timezone

from app.models import BATTERY_EXPORT, EXPORT_BLOCKED
from app.optimizer import MODE_CMD_CHARGE_GRID, MODE_MAX_SELF
from haos49_characterization_helpers import Haos49CharacterizationCase, RecordingHA


_MISSING = object()


class Phase1ForecastSolarClockTelemetryTrustCharacterizationTests(
    Haos49CharacterizationCase
):
    """Package 4D characterization before production telemetry-trust repair."""

    MORNING = datetime(2026, 1, 15, 6, 0, 0)
    HOLD_OFF_MORNING = datetime(2026, 1, 15, 8, 0, 0)
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

    @staticmethod
    def _default_sun_times(when: datetime, sun_above_horizon: bool) -> tuple[str, str]:
        if sun_above_horizon:
            sunrise = datetime.combine(when.date() + timedelta(days=1), time(7, 0))
        else:
            sunrise = datetime.combine(when.date(), time(7, 0))
            if sunrise <= when:
                sunrise += timedelta(days=1)
        sunset = datetime.combine(when.date(), time(18, 0))
        if sunset <= when:
            sunset += timedelta(days=1)
        return sunrise.isoformat(), sunset.isoformat()

    def _states(
        self,
        optimizer,
        *,
        when: datetime,
        forecast_remaining_state: object = "100.0",
        forecast_remaining_observed_at: datetime | None = None,
        forecast_today_state: object = "100.0",
        forecast_today_observed_at: datetime | None = None,
        forecast_tomorrow_state: object = "100.0",
        forecast_tomorrow_observed_at: datetime | None = None,
        detailed_forecast: object = _MISSING,
        sun_state: object = _MISSING,
        sun_observed_at: datetime | None = None,
        next_rising: object = _MISSING,
        next_setting: object = _MISSING,
        battery_soc: float = 60.0,
        available_discharge_kwh: float = 18.0,
        pv_kw: float = 0.0,
        load_kw: float = 1.0,
        current_price: float = 0.30,
        feedin_price: float = 0.0,
        include_negative_price_forecast: bool = False,
    ) -> dict[str, dict[str, object]]:
        cfg = optimizer.cfg
        inferred_above = 7 <= when.hour < 18
        sunrise_default, sunset_default = self._default_sun_times(when, inferred_above)
        resolved_sun_state = (
            "above_horizon" if inferred_above else "below_horizon"
        ) if sun_state is _MISSING else sun_state
        resolved_rising = sunrise_default if next_rising is _MISSING else next_rising
        resolved_setting = sunset_default if next_setting is _MISSING else next_setting
        sun_attributes: dict[str, object] = {"elevation": 45.0 if inferred_above else -5.0}
        if resolved_rising is not None:
            sun_attributes["next_rising"] = resolved_rising
        if resolved_setting is not None:
            sun_attributes["next_setting"] = resolved_setting

        today_attributes: dict[str, object] = {}
        if detailed_forecast is not _MISSING:
            today_attributes["detailedForecast"] = detailed_forecast

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
                resolved_sun_state,
                when,
                sun_attributes,
                observed_at=sun_observed_at,
            ),
            cfg.price_sensor: self._entity(
                current_price,
                when,
                {"estimate": False},
            ),
            cfg.feedin_sensor: self._entity(feedin_price, when),
            cfg.demand_window_sensor: self._entity("off", when),
            cfg.price_spike_sensor: self._entity("off", when),
            cfg.solar_power_now_sensor: self._entity(pv_kw, when),
            cfg.grid_export_limit: self._entity(0.01, when, {"max": 25.0}),
            cfg.grid_import_limit: self._entity(0.01, when, {"max": 25.0}),
            cfg.pv_max_power_limit: self._entity(25.0, when, {"max": 25.0}),
            cfg.ems_mode_select: self._entity(MODE_MAX_SELF, when),
            cfg.ha_control_switch: self._entity("on", when),
            cfg.sigenergy_mode_select: self._entity(cfg.automated_option, when),
        }
        forecast_inputs = (
            (
                cfg.forecast_remaining_sensor,
                forecast_remaining_state,
                forecast_remaining_observed_at,
                {},
            ),
            (
                cfg.forecast_today_sensor,
                forecast_today_state,
                forecast_today_observed_at,
                today_attributes,
            ),
            (
                cfg.forecast_tomorrow_sensor,
                forecast_tomorrow_state,
                forecast_tomorrow_observed_at,
                {},
            ),
        )
        for entity_id, raw_state, observed_at, attributes in forecast_inputs:
            if raw_state is not _MISSING:
                states[entity_id] = self._entity(
                    raw_state,
                    when,
                    attributes,
                    observed_at=observed_at,
                )
        if include_negative_price_forecast:
            states[cfg.price_forecast_sensor] = self._entity(
                "available",
                when,
                {
                    cfg.price_forecast_attribute: [
                        {
                            cfg.price_forecast_time_key: (
                                when + timedelta(hours=1)
                            ).isoformat(),
                            cfg.price_forecast_value_key: -0.20,
                        }
                    ]
                },
            )
        return states

    def _read_and_decide(
        self,
        *,
        when: datetime | None = None,
        settings: dict[str, object] | None = None,
        **state_overrides: object,
    ):
        when = when or self.FIXED_AFTERNOON
        ha = RecordingHA()
        optimizer = self.optimizer(ha=ha, **dict(settings or {}))
        ha.states = self._states(optimizer, when=when, **state_overrides)
        with self.optimizer_time(when):
            state = asyncio.run(optimizer._read_state())
            decision = optimizer._decide(state)
        return optimizer, state, decision

    @staticmethod
    def _morning_detail(when: datetime, pv_estimate: object = 10.0) -> list[dict[str, object]]:
        return [
            {
                "period_start": (when + timedelta(hours=hours)).isoformat(),
                "pv_estimate": pv_estimate,
            }
            for hours in (3, 5, 7, 9, 11)
        ]

    # Aggregate forecast trust and genuine-zero controls.
    def test_invalid_aggregate_forecasts_collapse_to_numeric_zero(self) -> None:
        names = (
            ("forecast_remaining_state", "forecast_remaining_kwh"),
            ("forecast_today_state", "forecast_today_kwh"),
            ("forecast_tomorrow_state", "forecast_tomorrow_kwh"),
        )
        for input_name, state_name in names:
            for raw_value in (_MISSING, "unavailable", "unknown", "nan", "inf", "-inf"):
                with self.subTest(input_name=input_name, raw_value=raw_value):
                    _optimizer, state, _decision = self._read_and_decide(
                        **{input_name: raw_value}
                    )
                    self.assertEqual(0.0, getattr(state, state_name))

    def test_stale_finite_aggregate_forecasts_remain_usable_scalars(self) -> None:
        stale_at = self.FIXED_AFTERNOON - timedelta(hours=2)
        _optimizer, state, _decision = self._read_and_decide(
            forecast_remaining_state="80.0",
            forecast_remaining_observed_at=stale_at,
            forecast_today_state="90.0",
            forecast_today_observed_at=stale_at,
            forecast_tomorrow_state="110.0",
            forecast_tomorrow_observed_at=stale_at,
        )
        self.assertEqual((80.0, 90.0, 110.0), (
            state.forecast_remaining_kwh,
            state.forecast_today_kwh,
            state.forecast_tomorrow_kwh,
        ))
        self.assertFalse(hasattr(state, "forecast_remaining_trusted"))
        self.assertFalse(hasattr(state, "forecast_today_trusted"))
        self.assertFalse(hasattr(state, "forecast_tomorrow_trusted"))

    def test_fresh_zero_and_unavailable_forecasts_are_not_distinguishable_in_state(self) -> None:
        _optimizer, fresh, _decision = self._read_and_decide(
            forecast_remaining_state="0.0",
            forecast_today_state="0.0",
            forecast_tomorrow_state="0.0",
        )
        _optimizer, unavailable, _decision = self._read_and_decide(
            forecast_remaining_state="unavailable",
            forecast_today_state="unavailable",
            forecast_tomorrow_state="unavailable",
        )
        self.assertEqual((0.0, 0.0, 0.0), (
            fresh.forecast_remaining_kwh,
            fresh.forecast_today_kwh,
            fresh.forecast_tomorrow_kwh,
        ))
        self.assertEqual(
            (
                fresh.forecast_remaining_kwh,
                fresh.forecast_today_kwh,
                fresh.forecast_tomorrow_kwh,
            ),
            (
                unavailable.forecast_remaining_kwh,
                unavailable.forecast_today_kwh,
                unavailable.forecast_tomorrow_kwh,
            ),
        )

    def test_stale_remaining_forecast_cannot_enable_solar_surplus_bypass(self) -> None:
        stale_at = self.FIXED_AFTERNOON - timedelta(hours=2)
        _optimizer, _state, decision = self._read_and_decide(
            forecast_remaining_state="100.0",
            forecast_remaining_observed_at=stale_at,
            battery_soc=80.0,
            available_discharge_kwh=24.0,
            pv_kw=6.0,
            load_kw=1.0,
            feedin_price=0.05,
            settings={"solar_surplus_bypass_enabled": True},
        )
        self.assertFalse(decision.solar_surplus_bypass)

    def test_stale_today_forecast_cannot_activate_standby_holdoff(self) -> None:
        stale_at = self.HOLD_OFF_MORNING - timedelta(hours=2)
        _optimizer, _state, decision = self._read_and_decide(
            when=self.HOLD_OFF_MORNING,
            forecast_today_state="100.0",
            forecast_today_observed_at=stale_at,
            forecast_remaining_state="100.0",
            include_negative_price_forecast=True,
            battery_soc=90.0,
            available_discharge_kwh=27.0,
            settings={
                "standby_holdoff_enabled": True,
                "standby_holdoff_end_time": "11:00",
                "pv_forecast_holdoff_kwh": 50.0,
            },
        )
        self.assertFalse(decision.standby_holdoff_active)

    # Morning Dump and detailed forecast trust.
    def test_stale_detailed_forecast_source_cannot_authorize_morning_dump(self) -> None:
        stale_at = self.MORNING - timedelta(hours=2)
        _optimizer, _state, decision = self._read_and_decide(
            when=self.MORNING,
            forecast_today_observed_at=stale_at,
            detailed_forecast=self._morning_detail(self.MORNING),
            battery_soc=80.0,
            available_discharge_kwh=24.0,
            feedin_price=0.05,
            settings={"morning_dump_enabled": True},
        )
        self.assertFalse(decision.morning_dump_active)

    def test_nonfinite_positive_detailed_forecast_cannot_authorize_morning_dump(self) -> None:
        detail = self._morning_detail(self.MORNING)
        detail[0]["pv_estimate"] = "inf"
        _optimizer, _state, decision = self._read_and_decide(
            when=self.MORNING,
            detailed_forecast=detail,
            battery_soc=80.0,
            available_discharge_kwh=24.0,
            feedin_price=0.05,
            settings={"morning_dump_enabled": True},
        )
        self.assertFalse(decision.morning_dump_active)

    def test_missing_empty_invalid_and_nonpositive_detail_are_conservative_for_dump(self) -> None:
        cases = (
            _MISSING,
            [],
            ["invalid"],
            [{"period_start": "bad", "pv_estimate": 100.0}],
            [{"period_start": (self.MORNING + timedelta(hours=3)).isoformat(), "pv_estimate": "nan"}],
            [{"period_start": (self.MORNING + timedelta(hours=3)).isoformat(), "pv_estimate": "-inf"}],
        )
        for detail in cases:
            with self.subTest(detail=detail):
                _optimizer, _state, decision = self._read_and_decide(
                    when=self.MORNING,
                    detailed_forecast=detail,
                    battery_soc=80.0,
                    available_discharge_kwh=24.0,
                    feedin_price=0.05,
                    settings={"morning_dump_enabled": True},
                )
                self.assertFalse(decision.morning_dump_active)

    def test_previous_day_detailed_points_do_not_authorize_morning_dump(self) -> None:
        detail = [
            {
                "period_start": (self.MORNING - timedelta(days=1, hours=-3)).isoformat(),
                "pv_estimate": 100.0,
            }
        ]
        _optimizer, _state, decision = self._read_and_decide(
            when=self.MORNING,
            detailed_forecast=detail,
            battery_soc=80.0,
            available_discharge_kwh=24.0,
            feedin_price=0.05,
            settings={"morning_dump_enabled": True},
        )
        self.assertFalse(decision.morning_dump_active)

    def test_partial_horizon_can_satisfy_dump_energy_without_coverage_provenance(self) -> None:
        detail = [
            {
                "period_start": (self.MORNING + timedelta(hours=3)).isoformat(),
                "pv_estimate": 100.0,
            },
            {
                "period_start": (self.MORNING + timedelta(hours=11)).isoformat(),
                "pv_estimate": 1.0,
            },
        ]
        _optimizer, state, decision = self._read_and_decide(
            when=self.MORNING,
            detailed_forecast=detail,
            battery_soc=80.0,
            available_discharge_kwh=24.0,
            feedin_price=0.05,
            settings={"morning_dump_enabled": True},
        )
        self.assertEqual(detail, state.solcast_detailed)
        self.assertTrue(decision.morning_dump_active)

    def test_morning_dump_retains_deliberate_owner_and_fifteen_percent_floor(self) -> None:
        settings = {"morning_dump_enabled": True, "morning_dump_min_soc": 15.0}
        _optimizer, _state, allowed = self._read_and_decide(
            when=self.MORNING,
            detailed_forecast=self._morning_detail(self.MORNING),
            battery_soc=80.0,
            available_discharge_kwh=24.0,
            feedin_price=0.05,
            settings=settings,
        )
        _optimizer, _state, floored = self._read_and_decide(
            when=self.MORNING,
            detailed_forecast=self._morning_detail(self.MORNING),
            battery_soc=15.0,
            available_discharge_kwh=4.5,
            feedin_price=0.05,
            settings=settings,
        )
        self.assertTrue(allowed.morning_dump_active)
        self.assertEqual(BATTERY_EXPORT, allowed.export_intent)
        self.assertEqual("morning_dump", allowed.trace_values.get("battery_export_owner"))
        self.assertFalse(floored.morning_dump_active)

    # Evening Boost forecast trust.
    def test_stale_tomorrow_forecast_cannot_authorize_evening_boost(self) -> None:
        stale_at = self.EVENING - timedelta(hours=2)
        _optimizer, _state, decision = self._read_and_decide(
            when=self.EVENING,
            forecast_tomorrow_state="120.0",
            forecast_tomorrow_observed_at=stale_at,
            detailed_forecast=[
                {
                    "period_start": datetime(2026, 1, 15, 16, 0).isoformat(),
                    "pv_estimate": 2.0,
                }
            ],
            battery_soc=80.0,
            available_discharge_kwh=24.0,
            load_kw=0.0,
            feedin_price=0.15,
            settings={
                "evening_boost_enabled": True,
                "evening_boost_min_tomorrow_forecast_kwh": 100.0,
            },
        )
        self.assertFalse(decision.evening_export_boost_active)

    def test_invalid_tomorrow_forecast_is_conservative_for_evening_boost(self) -> None:
        for raw_value in (_MISSING, "unavailable", "unknown", "nan", "inf", "-inf", "0.0"):
            with self.subTest(raw_value=raw_value):
                _optimizer, state, decision = self._read_and_decide(
                    when=self.EVENING,
                    forecast_tomorrow_state=raw_value,
                    detailed_forecast=[
                        {
                            "period_start": datetime(2026, 1, 15, 16, 0).isoformat(),
                            "pv_estimate": 2.0,
                        }
                    ],
                    battery_soc=80.0,
                    available_discharge_kwh=24.0,
                    load_kw=0.0,
                    feedin_price=0.15,
                    settings={
                        "evening_boost_enabled": True,
                        "evening_boost_min_tomorrow_forecast_kwh": 100.0,
                    },
                )
                self.assertEqual(0.0, state.forecast_tomorrow_kwh)
                self.assertFalse(decision.evening_export_boost_active)

    def test_fresh_positive_tomorrow_forecast_preserves_evening_boost(self) -> None:
        _optimizer, _state, decision = self._read_and_decide(
            when=self.EVENING,
            forecast_tomorrow_state="120.0",
            detailed_forecast=[
                {
                    "period_start": datetime(2026, 1, 15, 16, 0).isoformat(),
                    "pv_estimate": 2.0,
                }
            ],
            battery_soc=80.0,
            available_discharge_kwh=24.0,
            load_kw=0.0,
            feedin_price=0.15,
            settings={
                "evening_boost_enabled": True,
                "evening_boost_min_tomorrow_forecast_kwh": 100.0,
            },
        )
        self.assertTrue(decision.evening_export_boost_active)
        self.assertEqual(
            "evening_export_boost",
            decision.trace_values.get("battery_export_owner"),
        )

    # Forecast Safety Charging directionality.
    def test_invalid_remaining_forecast_pushes_cheap_topup_conservatively_toward_charge(self) -> None:
        for raw_value in (_MISSING, "unavailable", "unknown", "nan", "inf", "-inf", "0.0"):
            with self.subTest(raw_value=raw_value):
                optimizer, state, _decision = self._read_and_decide(
                    forecast_remaining_state=raw_value,
                    battery_soc=40.0,
                    current_price=0.03,
                    feedin_price=0.0,
                    pv_kw=0.0,
                    load_kw=1.0,
                    settings={"max_price_threshold": 0.05},
                )
                self.assertEqual(0.0, state.forecast_remaining_kwh)
                limit = optimizer._grid_limit_base(
                    state,
                    False,
                    import_price_trusted=True,
                    feedin_price_trusted=True,
                    battery_soc_trusted=True,
                    battery_capacity_trusted=True,
                )
                self.assertGreater(limit, 0.0)

    def test_stale_high_remaining_forecast_can_suppress_forecast_safety_topup(self) -> None:
        stale_at = self.FIXED_AFTERNOON - timedelta(hours=2)
        optimizer, state, _decision = self._read_and_decide(
            forecast_remaining_state="100.0",
            forecast_remaining_observed_at=stale_at,
            battery_soc=40.0,
            current_price=0.03,
            feedin_price=0.0,
        )
        limit = optimizer._grid_limit_base(
            state,
            False,
            import_price_trusted=True,
            feedin_price_trusted=True,
            battery_soc_trusted=True,
            battery_capacity_trusted=True,
        )
        self.assertEqual(0.0, limit)

    # Detailed forecast and time provenance limitations.
    def test_detailed_forecast_retains_points_but_loses_source_provenance(self) -> None:
        detail = self._morning_detail(self.MORNING)
        stale_at = self.MORNING - timedelta(hours=2)
        _optimizer, state, _decision = self._read_and_decide(
            when=self.MORNING,
            forecast_today_observed_at=stale_at,
            detailed_forecast=detail,
        )
        self.assertEqual(detail, state.solcast_detailed)
        self.assertFalse(hasattr(state, "solcast_detailed_trusted"))
        self.assertFalse(hasattr(state, "solcast_detailed_observed_at"))
        self.assertFalse(hasattr(state, "solcast_horizon_complete"))

    def test_missing_and_empty_detailed_forecast_are_not_distinguishable(self) -> None:
        _optimizer, missing, _decision = self._read_and_decide(
            detailed_forecast=_MISSING
        )
        _optimizer, empty, _decision = self._read_and_decide(detailed_forecast=[])
        self.assertEqual([], missing.solcast_detailed)
        self.assertEqual(missing.solcast_detailed, empty.solcast_detailed)

    def test_forecast_point_time_is_retained_but_issue_time_and_coverage_are_absent(self) -> None:
        point = {
            "period_start": (self.MORNING + timedelta(hours=3)).isoformat(),
            "pv_estimate": 5.0,
        }
        _optimizer, state, _decision = self._read_and_decide(
            when=self.MORNING,
            detailed_forecast=[point],
        )
        self.assertEqual(point["period_start"], state.solcast_detailed[0]["period_start"])
        self.assertNotIn("issued_at", state.solcast_detailed[0])
        self.assertNotIn("forecast_day", state.solcast_detailed[0])
        self.assertFalse(hasattr(state, "solcast_horizon_start"))
        self.assertFalse(hasattr(state, "solcast_horizon_end"))

    # Solar clock / sunset trust.
    def test_missing_or_malformed_sunrise_cannot_authorize_morning_dump(self) -> None:
        for raw_sunrise in (None, "unavailable", "unknown", "not-a-timestamp"):
            with self.subTest(raw_sunrise=raw_sunrise):
                _optimizer, _state, decision = self._read_and_decide(
                    when=self.MORNING,
                    sun_state="above_horizon",
                    next_rising=raw_sunrise,
                    detailed_forecast=self._morning_detail(self.MORNING),
                    battery_soc=80.0,
                    available_discharge_kwh=24.0,
                    feedin_price=0.05,
                    settings={"morning_dump_enabled": True},
                )
                self.assertFalse(decision.morning_dump_active)

    def test_missing_or_prior_day_sunset_cannot_create_permissive_close_to_sunset(self) -> None:
        for raw_sunset in (None, "unavailable", "unknown", "not-a-timestamp", "2026-01-14T18:00:00"):
            with self.subTest(raw_sunset=raw_sunset):
                _optimizer, _state, decision = self._read_and_decide(
                    next_setting=raw_sunset,
                    forecast_remaining_state="1.0",
                    battery_soc=60.0,
                    available_discharge_kwh=18.0,
                    feedin_price=1.10,
                    settings={"export_threshold_high": 1.0},
                )
                self.assertFalse(bool(decision.trace_gates.get("close_to_sunset")))
                self.assertEqual(EXPORT_BLOCKED, decision.export_intent)

    def test_stale_sun_entity_cannot_establish_close_to_sunset_permission(self) -> None:
        stale_at = self.FIXED_AFTERNOON - timedelta(hours=2)
        _optimizer, _state, decision = self._read_and_decide(
            sun_observed_at=stale_at,
            next_setting=(self.FIXED_AFTERNOON + timedelta(hours=1)).isoformat(),
            forecast_remaining_state="1.0",
            battery_soc=60.0,
            available_discharge_kwh=18.0,
            feedin_price=1.10,
            settings={"export_threshold_high": 1.0},
        )
        self.assertFalse(bool(decision.trace_gates.get("close_to_sunset")))
        self.assertEqual(EXPORT_BLOCKED, decision.export_intent)

    def test_valid_current_day_sunset_preserves_existing_close_to_sunset_edge(self) -> None:
        near_sunset = datetime(2026, 1, 15, 17, 0, 0)
        _optimizer, state, decision = self._read_and_decide(
            when=near_sunset,
            next_setting=datetime(2026, 1, 15, 18, 0, 0).isoformat(),
        )
        self.assertEqual(1.0, state.hours_to_sunset)
        self.assertTrue(bool(decision.trace_gates.get("close_to_sunset")))

    def test_future_wrong_day_sunset_is_accepted_without_day_alignment_provenance(self) -> None:
        wrong_day = datetime(2026, 1, 16, 18, 0, 0)
        _optimizer, state, decision = self._read_and_decide(
            next_setting=wrong_day.isoformat()
        )
        self.assertEqual(wrong_day.timestamp(), state.next_sunset_ts)
        self.assertGreater(state.hours_to_sunset, 24.0)
        self.assertFalse(bool(decision.trace_gates.get("close_to_sunset")))
        self.assertFalse(hasattr(state, "solar_clock_trusted"))

    def test_solar_clock_retains_parsed_values_but_loses_entity_freshness(self) -> None:
        stale_at = self.FIXED_AFTERNOON - timedelta(hours=2)
        sunrise = datetime(2026, 1, 16, 7, 0, 0)
        sunset = datetime(2026, 1, 15, 18, 0, 0)
        _optimizer, state, _decision = self._read_and_decide(
            sun_observed_at=stale_at,
            next_rising=sunrise.isoformat(),
            next_setting=sunset.isoformat(),
        )
        self.assertEqual(sunrise.timestamp(), state.next_sunrise_ts)
        self.assertEqual(sunset.timestamp(), state.next_sunset_ts)
        self.assertFalse(hasattr(state, "sun_observed_at"))
        self.assertFalse(hasattr(state, "sun_clock_fresh"))

    # Branch-specific independence: forecast/sun trust must not be a global veto.
    def test_untrusted_forecast_and_solar_clock_do_not_veto_negative_price_grid_charge(self) -> None:
        optimizer, _state, decision = self._read_and_decide(
            forecast_remaining_state="unavailable",
            forecast_today_state="nan",
            forecast_tomorrow_state="inf",
            detailed_forecast=_MISSING,
            sun_state="unavailable",
            next_rising=None,
            next_setting=None,
            battery_soc=40.0,
            available_discharge_kwh=12.0,
            current_price=-0.10,
            feedin_price=0.0,
        )
        self.assertEqual(MODE_CMD_CHARGE_GRID, decision.ems_mode)
        self.assertEqual(
            min(optimizer.cfg.import_limit_high, 25.0),
            decision.import_limit,
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
