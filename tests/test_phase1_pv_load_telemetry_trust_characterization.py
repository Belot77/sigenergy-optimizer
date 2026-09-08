from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from app.models import BATTERY_EXPORT, EXPORT_BLOCKED, MSC_SURPLUS_CEILING
from app.optimizer import MODE_MAX_SELF
from haos49_characterization_helpers import Haos49CharacterizationCase, RecordingHA


_MISSING = object()


class Phase1PVLoadTelemetryTrustCharacterizationTests(Haos49CharacterizationCase):
    """Package 4C characterization before production telemetry-trust repair."""

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

    def _states(
        self,
        optimizer,
        *,
        when: datetime,
        pv_state: object = "6.0",
        pv_observed_at: datetime | None = None,
        load_state: object = "1.0",
        load_observed_at: datetime | None = None,
        battery_power_state: object = "0.0",
        battery_power_observed_at: datetime | None = None,
        grid_export_kw: float = 0.0,
        grid_export_limit_kw: float = 0.01,
        battery_soc: float = 100.0,
        feedin_price: float = 0.095,
        forecast_remaining_kwh: float = 100.0,
    ) -> dict[str, dict[str, object]]:
        cfg = optimizer.cfg
        states: dict[str, dict[str, object]] = {
            cfg.battery_power_sensor: self._entity(
                battery_power_state,
                when,
                observed_at=battery_power_observed_at,
            ),
            cfg.grid_import_power_sensor: self._entity(0.0, when),
            cfg.grid_export_power_sensor: self._entity(grid_export_kw, when),
            cfg.battery_soc_sensor: self._entity(battery_soc, when),
            cfg.rated_capacity_sensor: self._entity(
                30.0,
                when,
                {"unit_of_measurement": "kWh"},
            ),
            cfg.available_discharge_sensor: self._entity(
                30.0,
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
                    "next_rising": (when + timedelta(hours=16)).isoformat(),
                    "next_setting": (when + timedelta(hours=4)).isoformat(),
                },
            ),
            cfg.price_sensor: self._entity(0.30, when, {"estimate": False}),
            cfg.feedin_sensor: self._entity(feedin_price, when),
            cfg.demand_window_sensor: self._entity("off", when),
            cfg.price_spike_sensor: self._entity("off", when),
            cfg.forecast_remaining_sensor: self._entity(
                forecast_remaining_kwh,
                when,
            ),
            cfg.forecast_today_sensor: self._entity(
                100.0,
                when,
                {"detailedForecast": []},
            ),
            cfg.forecast_tomorrow_sensor: self._entity(100.0, when),
            # Forecast/solar-clock trust is Package 4D. Keep it finite and neutral.
            cfg.solar_power_now_sensor: self._entity(0.0, when),
            cfg.grid_export_limit: self._entity(
                grid_export_limit_kw,
                when,
                {"max": 25.0},
            ),
            cfg.grid_import_limit: self._entity(0.01, when, {"max": 25.0}),
            cfg.pv_max_power_limit: self._entity(25.0, when, {"max": 25.0}),
            cfg.ems_mode_select: self._entity(MODE_MAX_SELF, when),
            cfg.ha_control_switch: self._entity("on", when),
            cfg.sigenergy_mode_select: self._entity(cfg.automated_option, when),
        }
        if pv_state is not _MISSING:
            states[cfg.pv_power_sensor] = self._entity(
                pv_state,
                when,
                observed_at=pv_observed_at,
            )
        if load_state is not _MISSING:
            states[cfg.consumed_power_sensor] = self._entity(
                load_state,
                when,
                observed_at=load_observed_at,
            )
        return states

    def _read_and_decide(
        self,
        *,
        optimizer=None,
        ha=None,
        when: datetime | None = None,
        **state_overrides: object,
    ):
        when = when or self.FIXED_AFTERNOON
        ha = ha or RecordingHA()
        optimizer = optimizer or self.optimizer(
            ha=ha,
            solar_surplus_bypass_enabled=False,
        )
        ha.states = self._states(optimizer, when=when, **state_overrides)
        with self.optimizer_time(when):
            state = asyncio.run(optimizer._read_state())
            decision = optimizer._decide(state)
        return optimizer, state, decision

    @staticmethod
    def _evaluate_hvac(optimizer, state, decision, *, previous=None):
        return optimizer._evaluate_hvac_solar_permission(
            state,
            decision,
            effective_mode=optimizer.cfg.automated_option,
            previous_result=previous,
            evaluated_at=datetime.fromtimestamp(
                state.timestamp.timestamp(),
                timezone.utc,
            ),
        )

    # Invalid PV is currently converted to a conservative scalar zero. The HVAC
    # wrapper retains the fact that no usable observation exists.
    def test_invalid_pv_fallback_is_conservative_for_exact_full_permission(self) -> None:
        for raw_pv in (_MISSING, "unavailable", "unknown", "nan", "inf", "-inf"):
            with self.subTest(raw_pv=raw_pv):
                _optimizer, state, decision = self._read_and_decide(
                    pv_state=raw_pv,
                )
                self.assertEqual(0.0, state.pv_kw)
                self.assertFalse(state.hvac_solar_inputs.pv_power.available)
                self.assertFalse(
                    bool(decision.trace_gates.get("pv_only_msc_high_ceiling_active"))
                )

    # Desired 4C contract: the load fallback must not serve as evidence of zero load.
    def test_invalid_load_cannot_establish_exact_full_pv_only_permission(self) -> None:
        for raw_load in (
            _MISSING,
            "unavailable",
            "unknown",
            "nan",
            "inf",
            "-inf",
        ):
            with self.subTest(raw_load=raw_load):
                _optimizer, state, decision = self._read_and_decide(
                    load_state=raw_load,
                )
                self.assertEqual(0.0, state.load_kw)
                self.assertFalse(state.hvac_solar_inputs.load_power.available)
                self.assertFalse(
                    bool(decision.trace_gates.get("pv_only_msc_high_ceiling_active")),
                    "synthetic zero load must not prove an exact-full PV-only opportunity",
                )
                self.assertEqual(EXPORT_BLOCKED, decision.export_intent)

    # The scalar control path retains stale values even though the observation
    # wrappers correctly mark them stale.
    def test_stale_pv_or_load_cannot_establish_exact_full_pv_only_permission(self) -> None:
        stale_at = self.FIXED_AFTERNOON - timedelta(hours=2)
        cases = (
            {"pv_state": "6.0", "pv_observed_at": stale_at},
            {"load_state": "0.0", "load_observed_at": stale_at},
        )
        for overrides in cases:
            with self.subTest(overrides=overrides):
                _optimizer, state, decision = self._read_and_decide(**overrides)
                reading = (
                    state.hvac_solar_inputs.pv_power
                    if "pv_observed_at" in overrides
                    else state.hvac_solar_inputs.load_power
                )
                self.assertTrue(reading.available)
                self.assertFalse(reading.fresh)
                self.assertFalse(
                    bool(decision.trace_gates.get("pv_only_msc_high_ceiling_active")),
                    "stale PV/load evidence must not prove the exact-full exception",
                )

    def test_untrusted_pv_or_load_cannot_activate_solar_surplus_bypass(self) -> None:
        stale_at = self.FIXED_AFTERNOON - timedelta(hours=2)
        cases = (
            {"pv_state": "6.0", "pv_observed_at": stale_at},
            {"load_state": _MISSING},
            {"load_state": "0.0", "load_observed_at": stale_at},
        )
        for overrides in cases:
            with self.subTest(overrides=overrides):
                ha = RecordingHA()
                optimizer = self.optimizer(
                    ha=ha,
                    solar_surplus_bypass_enabled=True,
                )
                _optimizer, _state, decision = self._read_and_decide(
                    optimizer=optimizer,
                    ha=ha,
                    battery_soc=60.0,
                    **overrides,
                )
                self.assertFalse(
                    decision.solar_surplus_bypass,
                    "untrusted PV/load must not establish measured surplus",
                )

    # Genuine zeros remain distinct observations; whether a branch qualifies is
    # then determined by the real zero rather than by telemetry failure.
    def test_genuine_fresh_zero_pv_is_available_and_conservative(self) -> None:
        _optimizer, state, decision = self._read_and_decide(pv_state="0.0")
        self.assertEqual(0.0, state.pv_kw)
        self.assertTrue(state.hvac_solar_inputs.pv_power.available)
        self.assertTrue(state.hvac_solar_inputs.pv_power.fresh)
        self.assertFalse(
            bool(decision.trace_gates.get("pv_only_msc_high_ceiling_active"))
        )

    def test_genuine_fresh_zero_load_remains_valid_permission_evidence(self) -> None:
        optimizer, state, decision = self._read_and_decide(load_state="0.0")
        self.assertEqual(0.0, state.load_kw)
        self.assertTrue(state.hvac_solar_inputs.load_power.available)
        self.assertTrue(state.hvac_solar_inputs.load_power.fresh)
        self.assertTrue(
            bool(decision.trace_gates.get("pv_only_msc_high_ceiling_active"))
        )
        self.assertEqual(MSC_SURPLUS_CEILING, decision.export_intent)
        self.assertEqual(optimizer.cfg.export_limit_high, decision.export_limit)

    def test_genuine_fresh_positive_pv_and_load_preserve_exact_full_permission(self) -> None:
        optimizer, _state, decision = self._read_and_decide(
            pv_state="6.0",
            load_state="1.0",
        )
        self.assertTrue(
            bool(decision.trace_gates.get("pv_only_msc_high_ceiling_active"))
        )
        self.assertEqual(MSC_SURPLUS_CEILING, decision.export_intent)
        self.assertEqual(optimizer.cfg.export_limit_high, decision.export_limit)

    # Ordinary economic MSC ownership is flow-proven and intentionally does not
    # require measured PV/load surplus in the current contract.
    def test_untrusted_pv_and_load_do_not_globally_block_ordinary_msc(self) -> None:
        optimizer, _state, decision = self._read_and_decide(
            pv_state=_MISSING,
            load_state=_MISSING,
            battery_soc=60.0,
            feedin_price=0.15,
        )
        self.assertTrue(
            bool(decision.trace_gates.get("ordinary_msc_surplus_ceiling_active"))
        )
        self.assertEqual(MSC_SURPLUS_CEILING, decision.export_intent)
        self.assertEqual(optimizer.cfg.export_limit_high, decision.export_limit)
        self.assertEqual("none", decision.trace_values.get("battery_export_owner"))

    def test_untrusted_pv_and_load_do_not_block_independent_high_price_owner(self) -> None:
        _optimizer, _state, decision = self._read_and_decide(
            pv_state=_MISSING,
            load_state=_MISSING,
            battery_soc=95.0,
            feedin_price=1.10,
        )
        self.assertEqual(BATTERY_EXPORT, decision.export_intent)
        self.assertEqual("high_price", decision.trace_values.get("battery_export_owner"))

    # HVAC already consumes the trusted wrappers rather than the fallback scalars.
    def test_hvac_invalid_pv_or_load_cannot_create_solar_permission(self) -> None:
        for sensor, raw_value in (
            ("pv", _MISSING),
            ("pv", "unavailable"),
            ("pv", "unknown"),
            ("pv", "nan"),
            ("pv", "inf"),
            ("pv", "-inf"),
            ("load", _MISSING),
            ("load", "unavailable"),
            ("load", "unknown"),
            ("load", "nan"),
            ("load", "inf"),
            ("load", "-inf"),
        ):
            with self.subTest(sensor=sensor, raw_value=raw_value):
                overrides = {
                    "pv_state" if sensor == "pv" else "load_state": raw_value
                }
                optimizer, state, decision = self._read_and_decide(**overrides)
                result = self._evaluate_hvac(optimizer, state, decision)
                self.assertEqual("unavailable", result.state)
                self.assertEqual("required_data_unavailable", result.reason_code)
                self.assertFalse(result.data_fresh)

    def test_hvac_stale_pv_or_load_cannot_create_solar_permission(self) -> None:
        stale_at = self.FIXED_AFTERNOON - timedelta(hours=2)
        for overrides in (
            {"pv_observed_at": stale_at},
            {"load_observed_at": stale_at},
        ):
            with self.subTest(overrides=overrides):
                optimizer, state, decision = self._read_and_decide(**overrides)
                result = self._evaluate_hvac(optimizer, state, decision)
                self.assertEqual("unavailable", result.state)
                self.assertEqual("required_data_stale", result.reason_code)
                self.assertFalse(result.data_fresh)

    def test_hvac_untrusted_load_cannot_retain_previous_permission(self) -> None:
        optimizer, state, decision = self._read_and_decide()
        previous = self._evaluate_hvac(optimizer, state, decision)
        self.assertEqual("start", previous.state)

        optimizer, unavailable_state, unavailable_decision = self._read_and_decide(
            optimizer=optimizer,
            ha=optimizer.ha,
            load_state=_MISSING,
        )
        result = self._evaluate_hvac(
            optimizer,
            unavailable_state,
            unavailable_decision,
            previous=previous,
        )
        self.assertEqual("unavailable", result.state)
        self.assertEqual("required_data_unavailable", result.reason_code)

    def test_live_snapshot_retains_freshness_but_not_per_sensor_timestamps(self) -> None:
        skewed_at = self.FIXED_AFTERNOON - timedelta(seconds=100)
        _optimizer, state, _decision = self._read_and_decide(
            pv_observed_at=skewed_at,
        )
        self.assertTrue(state.hvac_solar_inputs.pv_power.fresh)
        self.assertTrue(state.hvac_solar_inputs.load_power.fresh)
        self.assertFalse(hasattr(state.hvac_solar_inputs.pv_power, "observed_at"))
        self.assertFalse(hasattr(state.hvac_solar_inputs.load_power, "observed_at"))

    def test_skewed_flow_evidence_does_not_override_fresh_direct_battery_sensor(self) -> None:
        skewed_at = self.FIXED_AFTERNOON - timedelta(seconds=100)
        _optimizer, state, decision = self._read_and_decide(
            pv_state="4.8",
            pv_observed_at=skewed_at,
            load_state="1.0",
            battery_power_state="-0.006",
            grid_export_kw=5.0,
            grid_export_limit_kw=25.0,
        )
        derived_discharge = max(
            0.0,
            -(state.pv_kw - 5.0 - state.load_kw),
        )
        self.assertAlmostEqual(1.2, derived_discharge)
        self.assertAlmostEqual(
            0.006,
            decision.trace_values.get("battery_discharge_kw_for_pv_only"),
        )
        self.assertEqual(
            "direct_battery_sensor",
            decision.trace_values.get("battery_flow_source_for_pv_only"),
        )
        self.assertTrue(
            bool(decision.trace_gates.get("pv_only_msc_high_ceiling_active"))
        )

    def test_observational_flapping_reproduces_open_close_open_from_skewed_snapshot(
        self,
    ) -> None:
        when = self.FIXED_AFTERNOON
        ha = RecordingHA()
        optimizer = self.optimizer(
            ha=ha,
            solar_surplus_bypass_enabled=False,
        )
        stale_direct_at = when - timedelta(hours=2)
        sequence = (
            {
                "pv_state": "6.0",
                "load_state": "1.0",
                "grid_export_kw": 5.0,
                "grid_export_limit_kw": 25.0,
            },
            {
                "pv_state": "4.8",
                "pv_observed_at": when - timedelta(seconds=100),
                "load_state": "1.0",
                "grid_export_kw": 5.0,
                "grid_export_limit_kw": 25.0,
            },
            {
                "pv_state": "6.0",
                "load_state": "1.0",
                "grid_export_kw": 0.0,
                "grid_export_limit_kw": 0.01,
            },
        )
        states = []
        decisions = []
        for snapshot in sequence:
            optimizer, state, decision = self._read_and_decide(
                optimizer=optimizer,
                ha=ha,
                when=when,
                battery_power_state="-0.006",
                battery_power_observed_at=stale_direct_at,
                **snapshot,
            )
            states.append(state)
            decisions.append(decision)
            optimizer._last_state = state
            optimizer._last_decision = decision

        self.assertEqual([25.0, 0.0, 25.0], [d.export_limit for d in decisions])
        self.assertEqual(
            [
                MSC_SURPLUS_CEILING,
                EXPORT_BLOCKED,
                MSC_SURPLUS_CEILING,
            ],
            [d.export_intent for d in decisions],
        )
        self.assertEqual(
            [
                "battery_within_tolerance",
                "simultaneous_battery_discharge_and_grid_export",
                "battery_within_tolerance",
            ],
            [
                d.trace_values.get("ordinary_msc_flow_classification")
                for d in decisions
            ],
        )
        self.assertEqual(
            ["measured_grid_flow", "measured_grid_flow", "measured_grid_flow"],
            [
                d.trace_values.get("battery_flow_source_for_pv_only")
                for d in decisions
            ],
        )
        self.assertAlmostEqual(-0.006, states[1].battery_power_sensor_kw)
        self.assertAlmostEqual(
            1.2,
            decisions[1].trace_values.get("battery_discharge_kw_for_pv_only"),
        )
        self.assertTrue(states[1].hvac_solar_inputs.pv_power.fresh)
        self.assertTrue(states[1].hvac_solar_inputs.load_power.fresh)


if __name__ == "__main__":
    import unittest

    unittest.main()
