from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from app.models import BATTERY_EXPORT, EXPORT_BLOCKED, MSC_SURPLUS_CEILING
from app.optimizer import MODE_CMD_CHARGE_PV, MODE_MAX_SELF
from haos49_characterization_helpers import Haos49CharacterizationCase, RecordingHA


_MISSING = object()
_DEFAULT_REPORTED_AT = object()


class _ReportMetadataHA(RecordingHA):
    """Recording HA double with optional live state-report metadata."""

    def __init__(self) -> None:
        super().__init__()
        self.report_metadata: dict[str, dict[str, object]] = {}

    async def get_state_report_metadata(
        self,
        entity_ids: list[str],
    ) -> dict[str, dict[str, object]]:
        return {
            entity_id: self.report_metadata[entity_id]
            for entity_id in entity_ids
            if entity_id in self.report_metadata
        }


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
        updated_at: datetime | None = None,
        reported_at: datetime | str | None | object = _DEFAULT_REPORTED_AT,
    ) -> dict[str, object]:
        observed = observed_at or when
        updated = updated_at or observed
        entity = {
            "state": state,
            "attributes": dict(attributes or {}),
            "last_updated": datetime.fromtimestamp(
                updated.timestamp(),
                timezone.utc,
            ).isoformat(),
        }
        reported = observed if reported_at is _DEFAULT_REPORTED_AT else reported_at
        if reported is not _MISSING:
            entity["last_reported"] = (
                datetime.fromtimestamp(reported.timestamp(), timezone.utc).isoformat()
                if isinstance(reported, datetime)
                else reported
            )
        return entity

    def _read_and_decide(
        self,
        *,
        when: datetime | None = None,
        battery_soc_state: object = "60.0",
        battery_soc_observed_at: datetime | None = None,
        battery_soc_updated_at: datetime | None = None,
        battery_soc_reported_at: datetime | str | None | object = _DEFAULT_REPORTED_AT,
        battery_soc_enriched_reported_at: datetime | None = None,
        capacity_state: object = "30.0",
        capacity_observed_at: datetime | None = None,
        capacity_reported_at: datetime | str | None | object = _DEFAULT_REPORTED_AT,
        capacity_unit: object = "kWh",
        available_energy_state: object = "18.0",
        available_energy_unit: object = "kWh",
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
        forecast_today_observed_at: datetime | None = None,
        forecast_today_reported_at: datetime | str | None | object = _DEFAULT_REPORTED_AT,
        solcast_detailed: list[dict[str, object]] | None = None,
        **settings_overrides: object,
    ):
        when = when or self.FIXED_AFTERNOON
        ha = _ReportMetadataHA()
        optimizer = self.optimizer(ha=ha, **settings_overrides)
        # These fixtures express policy times as naive host-local datetimes.
        optimizer._tz = timezone(when.astimezone().utcoffset() or timedelta())
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
                observed_at=forecast_today_observed_at,
                reported_at=forecast_today_reported_at,
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
                updated_at=battery_soc_updated_at,
                reported_at=battery_soc_reported_at,
            )
        if capacity_state is not _MISSING:
            capacity_attributes = (
                {}
                if capacity_unit is _MISSING
                else {"unit_of_measurement": capacity_unit}
            )
            states[cfg.rated_capacity_sensor] = self._entity(
                capacity_state,
                when,
                capacity_attributes,
                observed_at=capacity_observed_at,
                reported_at=capacity_reported_at,
            )
        if available_energy_state is not _MISSING:
            available_energy_attributes = (
                {}
                if available_energy_unit is _MISSING
                else {"unit_of_measurement": available_energy_unit}
            )
            states[cfg.available_discharge_sensor] = self._entity(
                available_energy_state,
                when,
                available_energy_attributes,
                observed_at=available_energy_observed_at,
            )

        for entity_id, entity in states.items():
            entity["entity_id"] = entity_id

        if (
            battery_soc_enriched_reported_at is not None
            and cfg.battery_soc_sensor in states
        ):
            soc_entity = states[cfg.battery_soc_sensor]
            ha.report_metadata[cfg.battery_soc_sensor] = {
                "entity_id": cfg.battery_soc_sensor,
                "state": soc_entity["state"],
                "last_updated": soc_entity["last_updated"],
                "last_reported": datetime.fromtimestamp(
                    battery_soc_enriched_reported_at.timestamp(),
                    timezone.utc,
                ).isoformat(),
            }

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
        midnight = when.replace(hour=0, minute=0, second=0, microsecond=0)
        forecast: list[dict[str, object]] = []
        for half_hour in range(48):
            period_start = midnight + timedelta(minutes=30 * half_hour)
            productive = 8 <= period_start.hour < 17
            forecast.append(
                {
                    "period_start": datetime.fromtimestamp(
                        period_start.timestamp(),
                        timezone.utc,
                    ).isoformat(),
                    "pv_estimate": pv_estimate if productive else 0.0,
                }
            )
        return forecast

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

    def test_unenriched_stable_high_soc_remains_stale_and_cannot_export(self) -> None:
        _optimizer, state, decision = self._read_and_decide(
            battery_soc_state="95.0",
            battery_soc_observed_at=self.FIXED_AFTERNOON - timedelta(hours=2),
            available_energy_state="28.5",
            feedin_state="1.10",
            pv_kw=4.0,
            load_kw=1.0,
        )
        self.assertFalse(bool(state.battery_soc_trusted))
        self.assertFalse(bool(decision.trace_gates.get("battery_soc_trusted")))
        self.assertNotEqual(BATTERY_EXPORT, decision.export_intent)
        self.assertEqual("none", decision.trace_values.get("battery_export_owner"))

    def test_matching_fresh_report_metadata_proves_stable_soc_current(self) -> None:
        stale_snapshot_timestamp = self.FIXED_AFTERNOON - timedelta(hours=2)
        _optimizer, state, decision = self._read_and_decide(
            battery_soc_state="95.0",
            battery_soc_observed_at=stale_snapshot_timestamp,
            battery_soc_enriched_reported_at=self.FIXED_AFTERNOON,
            available_energy_state="28.5",
            feedin_state="1.10",
            pv_kw=4.0,
            load_kw=1.0,
        )
        self.assertTrue(bool(state.battery_soc_trusted))
        self.assertTrue(bool(decision.trace_gates.get("battery_soc_trusted")))
        self.assertEqual(BATTERY_EXPORT, decision.export_intent)
        self.assertEqual("high_price", decision.trace_values.get("battery_export_owner"))

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
    def test_unchanged_old_valid_capacity_remains_trusted(self) -> None:
        _optimizer, state, decision = self._read_and_decide(
            battery_soc_state="30.0",
            capacity_state="40.3",
            capacity_observed_at=self.FIXED_AFTERNOON - timedelta(days=1),
            available_energy_state="0.0",
            price_state="0.01",
            price_is_estimate=True,
            feedin_state="0.0",
            forecast_remaining_kwh=0.0,
        )
        self.assertEqual(40.3, state.battery_capacity_kwh)
        self.assertTrue(bool(state.battery_capacity_trusted))
        self.assertTrue(bool(decision.trace_gates.get("battery_capacity_trusted")))
        self.assertEqual(2.0, decision.import_limit)
        self.assertEqual(MODE_CMD_CHARGE_PV, decision.ems_mode)
        self.assertEqual("cheap_topup_import", decision.trace_values.get("import_branch"))

    def test_invalid_capacity_snapshots_remain_untrusted(self) -> None:
        cases = (
            ("missing", _MISSING, "kWh"),
            ("unavailable", "unavailable", "kWh"),
            ("unknown", "unknown", "kWh"),
            ("none", "none", "kWh"),
            ("blank", "", "kWh"),
            ("non_numeric", "forty", "kWh"),
            ("nan", "nan", "kWh"),
            ("positive_infinity", "inf", "kWh"),
            ("negative_infinity", "-inf", "kWh"),
            ("zero", "0.0", "kWh"),
            ("negative", "-1.0", "kWh"),
            ("missing_unit", "40.3", _MISSING),
            ("unsupported_unit", "40.3", "MJ"),
        )
        for label, raw_capacity, capacity_unit in cases:
            with self.subTest(case=label):
                _optimizer, state, decision = self._read_and_decide(
                    battery_soc_state="30.0",
                    capacity_state=raw_capacity,
                    capacity_unit=capacity_unit,
                    available_energy_state="0.0",
                    price_state="0.01",
                    price_is_estimate=True,
                    feedin_state="0.0",
                    forecast_remaining_kwh=0.0,
                )
                self.assertFalse(bool(state.battery_capacity_trusted))
                self.assertFalse(
                    bool(decision.trace_gates.get("battery_capacity_trusted"))
                )
                self.assertEqual(0.0, decision.import_limit)
                self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
                self.assertNotEqual(
                    "cheap_topup_import",
                    decision.trace_values.get("import_branch"),
                )

    def test_supported_capacity_units_normalize_to_kwh(self) -> None:
        cases = (
            ("Wh", "40300", 40.3),
            ("kWh", "40.3", 40.3),
            ("MWh", "0.0403", 40.3),
        )
        for unit, raw_capacity, expected_kwh in cases:
            with self.subTest(unit=unit):
                _optimizer, state, decision = self._read_and_decide(
                    capacity_state=raw_capacity,
                    capacity_unit=unit,
                )
                self.assertAlmostEqual(expected_kwh, state.battery_capacity_kwh)
                self.assertTrue(bool(state.battery_capacity_trusted))
                self.assertTrue(
                    bool(decision.trace_gates.get("battery_capacity_trusted"))
                )

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
        _optimizer, state, decision = self._read_and_decide(
            when=self.MORNING,
            battery_soc_state="80.0",
            capacity_state=_MISSING,
            available_energy_state="10.0",
            feedin_state="0.05",
            solcast_detailed=self._morning_forecast(self.MORNING, 10.0),
            morning_dump_enabled=True,
        )
        self.assertFalse(bool(state.battery_capacity_trusted))
        self.assertTrue(bool(state.available_discharge_energy_trusted))
        self.assertFalse(bool(decision.trace_gates.get("morning_dump_active")))
        self.assertNotEqual(BATTERY_EXPORT, decision.export_intent)
        self.assertEqual("none", decision.trace_values.get("battery_export_owner"))

    def test_supported_available_energy_units_normalize_to_kwh(self) -> None:
        cases = (
            ("Wh", "18000", 18.0),
            ("kWh", "18.0", 18.0),
            ("MWh", "0.018", 18.0),
            (" kWH ", "18.0", 18.0),
        )
        for unit, raw_energy, expected_kwh in cases:
            with self.subTest(unit=unit):
                _optimizer, state, decision = self._read_and_decide(
                    capacity_state="30.0",
                    available_energy_state=raw_energy,
                    available_energy_unit=unit,
                )
                self.assertAlmostEqual(
                    expected_kwh,
                    state.available_discharge_energy_kwh,
                )
                self.assertTrue(bool(state.available_discharge_energy_trusted))
                self.assertTrue(
                    bool(
                        decision.trace_gates.get(
                            "available_discharge_energy_trusted"
                        )
                    )
                )
                self.assertAlmostEqual(
                    12.0,
                    decision.trace_values.get("bat_fill_need_kwh"),
                )

    def test_invalid_available_energy_value_or_unit_fails_closed(self) -> None:
        cases = (
            ("missing_unit", "18.0", _MISSING),
            ("unsupported_unit", "18.0", "MJ"),
            ("ambiguous_unit", "18.0", "kWh/Wh"),
            ("malformed_unit", "18.0", ["kWh"]),
            ("negative", "-0.01", "kWh"),
            ("non_numeric", "eighteen", "kWh"),
            ("nan", "nan", "kWh"),
            ("positive_infinity", "inf", "kWh"),
            ("negative_infinity", "-inf", "kWh"),
        )
        for label, raw_energy, unit in cases:
            with self.subTest(case=label):
                _optimizer, state, decision = self._read_and_decide(
                    capacity_state="30.0",
                    available_energy_state=raw_energy,
                    available_energy_unit=unit,
                )
                self.assertEqual(0.0, state.available_discharge_energy_kwh)
                self.assertFalse(bool(state.available_discharge_energy_trusted))
                self.assertFalse(
                    bool(
                        decision.trace_gates.get(
                            "available_discharge_energy_trusted"
                        )
                    )
                )
                self.assertEqual(
                    30.0,
                    decision.trace_values.get("bat_fill_need_kwh"),
                )

    def test_available_energy_materially_above_capacity_fails_closed(self) -> None:
        _optimizer, state, decision = self._read_and_decide(
            capacity_state="30.0",
            available_energy_state="30.02",
        )
        self.assertEqual(0.0, state.available_discharge_energy_kwh)
        self.assertFalse(bool(state.available_discharge_energy_trusted))
        self.assertEqual(30.0, decision.trace_values.get("bat_fill_need_kwh"))

    def test_available_energy_capacity_tolerance_boundary_is_clamped(self) -> None:
        _optimizer, state, decision = self._read_and_decide(
            capacity_state="30.0",
            available_energy_state="30.01",
        )
        self.assertEqual(30.0, state.available_discharge_energy_kwh)
        self.assertTrue(bool(state.available_discharge_energy_trusted))
        self.assertEqual(0.0, decision.trace_values.get("bat_fill_need_kwh"))

    def test_available_energy_above_capacity_tolerance_fails_closed(self) -> None:
        _optimizer, state, decision = self._read_and_decide(
            capacity_state="30.0",
            available_energy_state="30.0101",
        )
        self.assertEqual(0.0, state.available_discharge_energy_kwh)
        self.assertFalse(bool(state.available_discharge_energy_trusted))
        self.assertEqual(30.0, decision.trace_values.get("bat_fill_need_kwh"))

    def test_untrusted_available_energy_cannot_authorize_morning_dump(self) -> None:
        _optimizer, _state, decision = self._read_and_decide(
            when=self.MORNING,
            battery_soc_state="80.0",
            capacity_state="30.0",
            available_energy_state="24.0",
            available_energy_unit="MJ",
            feedin_state="0.05",
            solcast_detailed=self._morning_forecast(self.MORNING, 10.0),
            morning_dump_enabled=True,
        )
        self.assertFalse(bool(decision.trace_gates.get("morning_dump_active")))
        self.assertNotEqual(BATTERY_EXPORT, decision.export_intent)
        self.assertEqual("none", decision.trace_values.get("battery_export_owner"))

    def test_untrusted_available_energy_cannot_enlarge_solar_override_cap(self) -> None:
        common = {
            "battery_soc_state": "95.0",
            "capacity_state": "30.0",
            "available_energy_state": "18.0",
            "feedin_state": "0.20",
            "pv_kw": 4.0,
            "load_kw": 1.0,
            "forecast_remaining_kwh": 100.0,
        }
        _optimizer, _valid_state, valid_decision = self._read_and_decide(**common)
        _optimizer, _invalid_state, invalid_decision = self._read_and_decide(
            **common,
            available_energy_unit="MJ",
        )

        self.assertTrue(bool(valid_decision.trace_gates.get("export_solar_override")))
        self.assertEqual(
            "solar_override",
            valid_decision.trace_values.get("battery_export_owner"),
        )
        self.assertEqual(BATTERY_EXPORT, valid_decision.export_intent)
        self.assertFalse(bool(invalid_decision.trace_gates.get("export_solar_override")))
        self.assertNotEqual(BATTERY_EXPORT, invalid_decision.export_intent)
        self.assertEqual(
            "none",
            invalid_decision.trace_values.get("battery_export_owner"),
        )
        invalid_deliberate_export_cap = (
            invalid_decision.export_limit
            if invalid_decision.export_intent == BATTERY_EXPORT
            else 0.0
        )
        self.assertLessEqual(
            invalid_deliberate_export_cap,
            valid_decision.export_limit,
        )

    def test_untrusted_available_energy_cannot_activate_morning_slow(self) -> None:
        common = {
            "when": self.MORNING.replace(hour=8),
            "capacity_state": "30.0",
            "available_energy_state": "18.0",
            "feedin_state": "0.05",
            "forecast_remaining_kwh": 100.0,
            "morning_slow_charge_enabled": True,
        }
        _optimizer, _valid_state, valid_decision = self._read_and_decide(**common)
        _optimizer, _invalid_state, invalid_decision = self._read_and_decide(
            **common,
            available_energy_unit="MJ",
        )

        self.assertTrue(
            bool(valid_decision.trace_gates.get("morning_slow_charge_active"))
        )
        self.assertFalse(
            bool(invalid_decision.trace_gates.get("morning_slow_charge_active"))
        )

    def test_untrusted_available_energy_cannot_activate_evening_boost(self) -> None:
        common = {
            "when": self.EVENING,
            "battery_soc_state": "80.0",
            "capacity_state": "30.0",
            "available_energy_state": "18.0",
            "feedin_state": "0.15",
            "forecast_tomorrow_kwh": 120.0,
            "solcast_detailed": self._morning_forecast(self.EVENING, 10.0),
            "evening_boost_enabled": True,
            "evening_boost_min_tomorrow_forecast_kwh": 100.0,
        }
        _optimizer, _valid_state, valid_decision = self._read_and_decide(**common)
        _optimizer, _invalid_state, invalid_decision = self._read_and_decide(
            **common,
            available_energy_unit="MJ",
        )

        self.assertTrue(
            bool(valid_decision.trace_gates.get("evening_export_boost_active"))
        )
        self.assertFalse(
            bool(invalid_decision.trace_gates.get("evening_export_boost_active"))
        )

    def test_stale_high_available_energy_cannot_authorize_morning_dump(self) -> None:
        _optimizer, state, decision = self._read_and_decide(
            when=self.MORNING,
            battery_soc_state="80.0",
            capacity_state="30.0",
            available_energy_state="30.0",
            available_energy_observed_at=self.MORNING - timedelta(hours=2),
            feedin_state="0.05",
            solcast_detailed=self._morning_forecast(self.MORNING, 10.0),
            morning_dump_enabled=True,
        )
        self.assertFalse(bool(state.available_discharge_energy_trusted))
        self.assertFalse(
            bool(decision.trace_gates.get("available_discharge_energy_trusted"))
        )
        self.assertFalse(bool(decision.trace_gates.get("morning_dump_active")))
        self.assertNotEqual(BATTERY_EXPORT, decision.export_intent)
        self.assertEqual("none", decision.trace_values.get("battery_export_owner"))

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

    def test_live_regression_combination_preserves_owned_morning_dump(self) -> None:
        old_dynamic_timestamp = self.MORNING - timedelta(hours=2)
        old_capacity_timestamp = self.MORNING - timedelta(days=1)
        _optimizer, state, decision = self._read_and_decide(
            when=self.MORNING,
            battery_soc_state="47.1",
            battery_soc_observed_at=old_dynamic_timestamp,
            battery_soc_reported_at=_MISSING,
            battery_soc_enriched_reported_at=self.MORNING,
            capacity_state="40.3",
            capacity_observed_at=old_capacity_timestamp,
            capacity_reported_at=_MISSING,
            available_energy_state="19.77",
            forecast_today_observed_at=old_dynamic_timestamp,
            forecast_today_reported_at=_MISSING,
            feedin_state="0.05",
            solcast_detailed=self._morning_forecast(self.MORNING, 10.0),
            morning_dump_enabled=True,
        )

        self.assertTrue(bool(state.battery_soc_trusted))
        self.assertTrue(bool(state.battery_capacity_trusted))
        self.assertTrue(bool(state.available_discharge_energy_trusted))
        self.assertFalse(bool(state.forecast_today_observation_trusted))
        self.assertTrue(
            bool(decision.trace_gates.get("solcast_detailed_source_trusted"))
        )
        self.assertTrue(
            bool(decision.trace_gates.get("morning_dump_detailed_coverage"))
        )
        self.assertTrue(bool(decision.trace_gates.get("morning_dump_active")))
        self.assertEqual(BATTERY_EXPORT, decision.export_intent)
        self.assertEqual("morning_dump", decision.trace_values.get("battery_export_owner"))


if __name__ == "__main__":
    import unittest

    unittest.main()
