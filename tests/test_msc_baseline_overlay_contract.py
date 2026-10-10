from __future__ import annotations

import asyncio
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app import optimizer as optimizer_module
from app.optimizer import (
    DISCHARGE_MODES,
    MODE_CMD_CHARGE_GRID,
    MODE_CMD_DISCHARGE_PV,
    MODE_MAX_SELF,
)
from app.models import (
    BATTERY_EXPORT, Decision, EXPORT_BLOCKED, HVACObservedValue,
    HVACSolarInputContext, MSC_SURPLUS_CEILING,
)
import haos49_characterization_helpers as characterization_helpers
from haos49_characterization_helpers import (
    Haos49CharacterizationCase,
    RecordingHA,
)


class ScriptedReadbackHA(RecordingHA):
    """Recording double whose service success and later readback are independent."""

    def __init__(self, readbacks: dict[str, list[object]]) -> None:
        super().__init__(settle_numbers=False, settle_selects=False)
        self._readbacks = {entity_id: list(values) for entity_id, values in readbacks.items()}

    async def bulk_states(self, entity_ids: list[str]) -> dict[str, dict[str, object]]:
        for entity_id in entity_ids:
            queued = self._readbacks.get(entity_id, [])
            if queued:
                self._record_state_value(entity_id, queued.pop(0))
        return await super().bulk_states(entity_ids)

    async def get_state_value(self, entity_id: str, default: object = "") -> object:
        self.calls.append(("get_state_value", entity_id, default))
        queued = self._readbacks.get(entity_id, [])
        if queued:
            observed = queued.pop(0)
            self._record_state_value(entity_id, observed)
            return observed
        return self.state_values.get(entity_id, default)


class ClockedRecordingHA(RecordingHA):
    """Actuator reports follow the same simulated clock as their application."""

    def _record_state_value(self, entity_id: str, value: object) -> None:
        reported = optimizer_module.datetime.now(timezone.utc).isoformat()
        self.state_values[entity_id] = value
        self._state_value_metadata[entity_id] = {
            "last_updated": reported, "last_reported": reported,
        }


class LiveTransitionHA(RecordingHA):
    """Commands are accepted; only explicit telemetry reports change readback."""

    def __init__(self):
        super().__init__(settle_numbers=False, settle_selects=False)
        self.clock_utc = None
        self.report_after_select = None

    async def get_state_value(self, entity_id, default=""):
        if self.report_after_select is not None:
            report_entity, report_value = self.report_after_select
            if entity_id == report_entity and ("select_option", report_entity, report_value) in self.calls:
                # Explicitly scripted telemetry arrives on a later read, not as
                # a side effect of service acceptance. Unscripted requests never settle.
                self.clock_utc += timedelta(milliseconds=1)
                self.state_values[report_entity] = report_value
                reported = self.clock_utc.isoformat()
                self._state_value_metadata[report_entity] = {
                    "last_updated": reported, "last_reported": reported,
                }
                self.report_after_select = None
        return await super().get_state_value(entity_id, default)

    async def get_state_report_metadata(self, entity_ids):
        return {
            entity_id: {
                "entity_id": entity_id,
                "state": self.state_values[entity_id],
                **self._state_value_metadata[entity_id],
            }
            for entity_id in entity_ids
            if entity_id in self.state_values and entity_id in self._state_value_metadata
        }


@contextmanager
def later_msc_report_clock(ha, when):
    """Give these positive fixtures a later actuator report on one shared clock."""
    moment = [when.replace(tzinfo=timezone.utc) if when.tzinfo is None else when.astimezone(timezone.utc)]

    class ObservedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return moment[0].astimezone(tz) if tz else moment[0].replace(tzinfo=None)

    original_select = ha.select_option

    async def select_with_later_report(entity_id, value):
        # The request has already started. Advance time before the existing
        # actuator double independently records its successful state report.
        moment[0] += timedelta(milliseconds=1)
        return await original_select(entity_id, value)

    ha.select_option = select_with_later_report
    try:
        with patch("app.optimizer.datetime", ObservedDateTime), patch.object(
            characterization_helpers, "datetime", ObservedDateTime,
        ):
            yield
    finally:
        ha.select_option = original_select


async def establish_observed_msc_baseline(case, optimizer, ha, when) -> None:
    """Prepare ongoing MSC tests through real application, without a latch bypass.

    Startup already observes both closed export and exact MSC. Only after the
    live readback checks may application open the normal surplus ceiling. Solar
    feedback, provider expiry and injected actuator failures start after this.
    """
    optimizer.ha = ha
    cfg = optimizer.cfg
    state = case.state(when, current_ems_mode=MODE_MAX_SELF, current_export_limit=0.01)
    decision = Decision(
        ems_mode=MODE_MAX_SELF,
        export_limit=cfg.export_limit_high,
        export_intent=MSC_SURPLUS_CEILING,
        requires_verified_msc_before_export=True,
        import_limit=0.0,
        ess_charge_limit=cfg.ess_charge_limit_value,
        ess_discharge_limit=cfg.ess_discharge_limit_value,
        pv_max_power_limit=cfg.pv_max_power_normal,
    )
    with case.optimizer_time(when):
        ha._record_state_value(cfg.ems_mode_select, MODE_MAX_SELF)
        ha._record_state_value(cfg.grid_export_limit, 0.01)
        result = await optimizer._apply(state, decision)
    case.assertTrue(result.succeeded, result.error)
    case.assertIn(("set_number", cfg.grid_export_limit, cfg.export_limit_high), ha.calls)
    ha.calls.clear()


class MscBaselineOverlayContractTests(Haos49CharacterizationCase):
    """Future MSC baseline; current haos53 is expected to fail architecture cases."""

    def assert_contract_outputs(
        self,
        decision,
        expected: tuple[str, float, float, float],
    ) -> None:
        self.assertEqual(
            expected,
            (
                decision.ems_mode,
                decision.export_limit,
                decision.import_limit,
                decision.pv_max_power_limit,
            ),
        )

    def assert_msc_surplus_permission(
        self,
        decision,
        *,
        export_ceiling: float,
    ) -> None:
        """Assert that an open ceiling is PV permission, not discharge intent."""
        self.assert_contract_outputs(
            decision,
            (MODE_MAX_SELF, export_ceiling, 0.0, 25.0),
        )
        self.assertGreater(decision.export_limit, 0.01)
        self.assertNotIn(decision.ems_mode, DISCHARGE_MODES)
        self.assertEqual(
            "pv_surplus_only",
            decision.trace_values.get("export_value_gate_export_type"),
        )
        self.assertEqual(MSC_SURPLUS_CEILING, decision.export_intent)
        self.assertEqual(
            MSC_SURPLUS_CEILING,
            decision.trace_values.get("requested_export_intent"),
        )
        self.assertEqual(
            MSC_SURPLUS_CEILING,
            decision.trace_values.get("export_intent"),
        )
        self.assertEqual(
            "none",
            decision.trace_values.get("battery_export_owner"),
        )

    def _ordinary_state(
        self,
        battery_soc: float,
        *,
        when: datetime | None = None,
        **overrides: object,
    ):
        values: dict[str, object] = {
            "battery_soc": battery_soc,
            "available_discharge_energy_kwh": 30.0 * battery_soc / 100.0,
            "battery_power_sensor_kw": 0.0,
            "feedin_price": 0.15,
            "feedin_price_cents": 15.0,
            "pv_kw": 4.0,
            "solar_power_now_kw": 4.0,
            "load_kw": 1.0,
            "current_ems_mode": MODE_MAX_SELF,
            "ems_mode_observed": True,
            "current_export_limit": 0.01,
            "grid_export_power_kw": 0.0,
        }
        values.update(overrides)
        return self.state(when or self.FIXED_AFTERNOON, **values)

    def _full_opportunity(self, **overrides: object):
        values: dict[str, object] = {
            "battery_soc": 100.0,
            "available_discharge_energy_kwh": 30.0,
            "battery_power_sensor_kw": 0.0,
            "feedin_price": 0.15,
            "feedin_price_cents": 15.0,
            "pv_kw": 6.0,
            "solar_power_now_kw": 6.0,
            "load_kw": 1.0,
            "current_export_limit": 0.01,
        }
        values.update(overrides)
        return self.state(self.FIXED_AFTERNOON, **values)

    def _poor_forecast_ordinary_surplus(self, battery_soc: float):
        return self._ordinary_state(
            battery_soc,
            feedin_price=0.12,
            feedin_price_cents=12.0,
            pv_kw=8.2,
            solar_power_now_kw=8.2,
            load_kw=1.0,
            forecast_remaining_kwh=1.0,
            forecast_today_kwh=1.0,
            forecast_tomorrow_kwh=5.0,
            current_ems_mode=MODE_MAX_SELF,
            ems_mode_observed=True,
            current_export_limit=0.01,
        )

    def _assert_normal_baseline(self, battery_soc: float) -> None:
        optimizer = self.optimizer()
        state = self._ordinary_state(battery_soc)

        decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

        self.assert_msc_surplus_permission(
            decision,
            export_ceiling=25.0,
        )
        self.assertEqual(0.0, state.grid_export_power_kw)

    def test_normal_msc_baseline_at_low_soc(self) -> None:
        self._assert_normal_baseline(20.0)

    def test_normal_msc_baseline_at_medium_soc(self) -> None:
        self._assert_normal_baseline(60.0)

    def test_normal_msc_baseline_at_high_soc(self) -> None:
        self._assert_normal_baseline(95.0)

    def test_normal_msc_baseline_at_full_soc(self) -> None:
        self._assert_normal_baseline(100.0)

    def test_normal_msc_baseline_uses_configured_high_ceiling(self) -> None:
        optimizer = self.optimizer(export_limit_high=18.0)
        state = self._ordinary_state(60.0)

        decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

        self.assert_msc_surplus_permission(
            decision,
            export_ceiling=18.0,
        )

    def test_ordinary_load_serving_battery_discharge_keeps_daytime_msc_ceiling(
        self,
    ) -> None:
        optimizer = self.optimizer()
        state = self._ordinary_state(
            60.0,
            battery_power_sensor_kw=-1.0,
            grid_export_power_kw=0.0,
        )

        decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

        self.assert_msc_surplus_permission(
            decision,
            export_ceiling=optimizer.cfg.export_limit_high,
        )
        self.assertTrue(bool(decision.trace_gates.get("ordinary_msc_flow_trusted")))
        self.assertTrue(
            bool(
                decision.trace_gates.get(
                    "ordinary_msc_load_serving_battery_discharge"
                )
            )
        )
        self.assertFalse(
            bool(
                decision.trace_gates.get(
                    "ordinary_msc_simultaneous_battery_discharge_and_grid_export"
                )
            )
        )
        self.assertTrue(bool(decision.trace_gates.get("ordinary_msc_flow_safe")))
        self.assertEqual(
            "load_serving_battery_discharge",
            decision.trace_values.get("ordinary_msc_flow_classification"),
        )

    def test_ordinary_load_serving_battery_discharge_keeps_night_msc_ceiling(
        self,
    ) -> None:
        optimizer = self.optimizer()
        when = datetime(2026, 1, 15, 2, 0)
        state = self._ordinary_state(
            95.0,
            when=when,
            sun_above_horizon=False,
            pv_kw=0.0,
            solar_power_now_kw=0.0,
            load_kw=1.0,
            battery_power_sensor_kw=-1.0,
            grid_export_power_kw=0.0,
        )

        decision = self.decide(optimizer, state, when)

        self.assertTrue(bool(decision.trace_gates.get("is_evening_or_night")))
        self.assert_msc_surplus_permission(
            decision,
            export_ceiling=optimizer.cfg.export_limit_high,
        )
        self.assertTrue(
            bool(
                decision.trace_gates.get(
                    "ordinary_msc_load_serving_battery_discharge"
                )
            )
        )
        self.assertEqual(
            "load_serving_battery_discharge",
            decision.trace_values.get("ordinary_msc_flow_classification"),
        )

    def test_ordinary_simultaneous_battery_discharge_and_export_closes_ceiling(
        self,
    ) -> None:
        optimizer = self.optimizer()
        state = self._ordinary_state(
            60.0,
            battery_power_sensor_kw=-1.0,
            grid_export_power_kw=1.0,
        )

        decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

        self.assert_contract_outputs(
            decision,
            (MODE_MAX_SELF, 0.0, 0.0, 25.0),
        )
        self.assertEqual(EXPORT_BLOCKED, decision.export_intent)
        self.assertTrue(bool(decision.trace_gates.get("ordinary_msc_flow_trusted")))
        self.assertTrue(
            bool(
                decision.trace_gates.get(
                    "ordinary_msc_simultaneous_battery_discharge_and_grid_export"
                )
            )
        )
        self.assertFalse(bool(decision.trace_gates.get("ordinary_msc_flow_safe")))
        self.assertEqual(
            "simultaneous_battery_discharge_and_grid_export",
            decision.trace_values.get("ordinary_msc_flow_classification"),
        )

    def test_unknown_ordinary_battery_or_grid_flow_closes_ceiling(self) -> None:
        cases = (
            (
                "unknown_battery",
                {
                    "battery_power_sensor_kw": None,
                    "grid_import_power_kw": None,
                    "grid_export_power_kw": 0.0,
                },
            ),
            (
                "unknown_grid_export",
                {
                    "battery_power_sensor_kw": 0.0,
                    "grid_export_power_kw": None,
                },
            ),
        )
        for name, overrides in cases:
            with self.subTest(name=name):
                optimizer = self.optimizer()
                state = self._ordinary_state(60.0, **overrides)

                decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

                self.assert_contract_outputs(
                    decision,
                    (MODE_MAX_SELF, 0.0, 0.0, 25.0),
                )
                self.assertEqual(EXPORT_BLOCKED, decision.export_intent)
                self.assertFalse(
                    bool(decision.trace_gates.get("ordinary_msc_flow_trusted"))
                )
                self.assertFalse(
                    bool(decision.trace_gates.get("ordinary_msc_flow_safe"))
                )
                self.assertEqual(
                    "unknown",
                    decision.trace_values.get("ordinary_msc_flow_classification"),
                )

    def test_generic_ordinary_tier_remains_msc_surplus_ceiling_at_night(
        self,
    ) -> None:
        when = datetime(2026, 1, 15, 2, 0)
        for battery_soc in (95.0, 100.0):
            with self.subTest(battery_soc=battery_soc):
                optimizer = self.optimizer()
                state = self._ordinary_state(
                    battery_soc,
                    when=when,
                    sun_above_horizon=False,
                    pv_kw=0.0,
                    solar_power_now_kw=0.0,
                    load_kw=1.0,
                )

                decision = self.decide(optimizer, state, when)

                self.assertTrue(bool(decision.trace_gates.get("is_evening_or_night")))
                self.assertEqual(
                    "ordinary_tier",
                    decision.trace_values.get("initial_desired_export_source"),
                )
                self.assertEqual(
                    "ordinary_msc_surplus_ceiling",
                    decision.trace_values.get("desired_export_source"),
                )
                self.assertEqual(
                    "none",
                    decision.trace_values.get("battery_export_owner"),
                )
                self.assert_msc_surplus_permission(
                    decision,
                    export_ceiling=optimizer.cfg.export_limit_high,
                )
                self.assertNotEqual(BATTERY_EXPORT, decision.export_intent)

    def test_poor_forecast_ordinary_surplus_has_no_100_percent_discontinuity(
        self,
    ) -> None:
        for battery_soc in (95.7, 100.0):
            with self.subTest(battery_soc=battery_soc):
                optimizer = self.optimizer()
                state = self._poor_forecast_ordinary_surplus(battery_soc)

                decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

                self.assertTrue(state.sigenergy_mode_observed)
                self.assertTrue(state.ems_mode_observed)
                self.assertTrue(
                    bool(decision.trace_gates.get("observed_automated_control_mode"))
                )
                self.assertEqual(
                    battery_soc == 100.0,
                    bool(decision.trace_gates.get("topoff_target_met")),
                )
                for gate in (
                    "morning_dump_active",
                    "morning_slow_charge_active",
                    "evening_export_boost_active",
                    "export_spike_active",
                    "positive_fit_override",
                    "solar_surplus_bypass",
                    "export_solar_override",
                ):
                    self.assertFalse(bool(decision.trace_gates.get(gate)), gate)
                self.assert_msc_surplus_permission(
                    decision,
                    export_ceiling=optimizer.cfg.export_limit_high,
                )
                self.assertGreater(
                    decision.export_limit,
                    state.pv_kw - state.load_kw,
                    "The high value is a ceiling; MSC, not the ceiling, controls dispatch.",
                )

    def test_cheap_fit_at_99_9_percent_preserves_fixed_topoff_contract(self) -> None:
        optimizer = self.optimizer()
        state = self._full_opportunity(
            battery_soc=99.9,
            available_discharge_energy_kwh=29.97,
            feedin_price=0.095,
            feedin_price_cents=9.5,
            battery_power_sensor_kw=0.0,
            current_ems_mode=MODE_MAX_SELF,
            ems_mode_observed=True,
            current_export_limit=0.01,
        )

        decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

        self.assert_contract_outputs(
            decision,
            (MODE_MAX_SELF, 0.0, 0.0, 25.0),
        )
        self.assertNotIn(decision.ems_mode, DISCHARGE_MODES)
        self.assertEqual(0.0, decision.trace_values.get("export_tier_limit"))
        self.assertFalse(bool(decision.trace_gates.get("topoff_target_met")))
        self.assertFalse(
            bool(decision.trace_gates.get("pv_only_msc_high_ceiling_active"))
        )
        self.assertFalse(decision.requires_verified_msc_before_export)
        self.assertEqual(EXPORT_BLOCKED, decision.export_intent)

    def test_cheap_fit_at_100_percent_uses_only_verified_msc_stage_2(self) -> None:
        optimizer = self.optimizer()
        state = self._full_opportunity(
            battery_soc=100.0,
            available_discharge_energy_kwh=30.0,
            feedin_price=0.095,
            feedin_price_cents=9.5,
            battery_power_sensor_kw=0.0,
            current_ems_mode=MODE_MAX_SELF,
            ems_mode_observed=True,
            current_export_limit=0.01,
        )

        decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

        self.assertEqual(0.0, decision.trace_values.get("export_tier_limit"))
        self.assertTrue(bool(decision.trace_gates.get("topoff_target_met")))
        self.assertTrue(bool(decision.trace_gates.get("pv_only_discharge_ok")))
        self.assertTrue(
            bool(decision.trace_gates.get("pv_only_msc_high_ceiling_active"))
        )
        self.assertEqual(
            "msc_full_battery_high_ceiling",
            decision.trace_values.get("pv_surplus_initiation_source"),
        )
        self.assert_msc_surplus_permission(
            decision,
            export_ceiling=optimizer.cfg.export_limit_high,
        )
        self.assertTrue(decision.requires_verified_msc_before_export)

    def test_cheap_fit_at_100_percent_keeps_ceiling_for_load_serving_discharge(
        self,
    ) -> None:
        optimizer = self.optimizer()
        state = self._full_opportunity(
            battery_soc=100.0,
            available_discharge_energy_kwh=30.0,
            feedin_price=0.095,
            feedin_price_cents=9.5,
            battery_power_sensor_kw=-0.2,
            current_ems_mode=MODE_MAX_SELF,
            ems_mode_observed=True,
            current_export_limit=25.0,
        )

        decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

        self.assertEqual(0.0, decision.trace_values.get("export_tier_limit"))
        self.assertEqual(
            0.2,
            decision.trace_values.get("battery_discharge_kw_for_pv_only"),
        )
        self.assertEqual(
            0.1,
            decision.trace_values.get("pv_only_discharge_tolerance_kw"),
        )
        self.assertFalse(bool(decision.trace_gates.get("pv_only_discharge_ok")))
        self.assertTrue(bool(decision.trace_gates.get("ordinary_msc_flow_safe")))
        self.assertEqual(
            "load_serving_battery_discharge",
            decision.trace_values.get("ordinary_msc_flow_classification"),
        )
        self.assertTrue(
            bool(decision.trace_gates.get("pv_only_msc_high_ceiling_active"))
        )
        self.assert_msc_surplus_permission(
            decision,
            export_ceiling=optimizer.cfg.export_limit_high,
        )
        self.assertTrue(decision.requires_verified_msc_before_export)

    def test_unobserved_automated_mode_cannot_open_normal_ceiling(self) -> None:
        optimizer = self.optimizer()
        state = self._full_opportunity(
            sigenergy_mode=optimizer.cfg.automated_option,
            sigenergy_mode_observed=False,
            current_ems_mode=MODE_MAX_SELF,
            ems_mode_observed=True,
            current_export_limit=25.0,
        )

        decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

        self.assertLess(decision.export_limit, optimizer.cfg.export_limit_high)

    def test_unavailable_unknown_malformed_or_different_ems_closes_ceiling(self) -> None:
        cases = (
            "unavailable",
            "unknown",
            "malformed-mode",
            MODE_CMD_DISCHARGE_PV,
        )

        for raw_mode in cases:
            with self.subTest(raw_mode=raw_mode):
                ha = RecordingHA()
                optimizer = self.optimizer(ha)
                ha.states = {
                    optimizer.cfg.sigenergy_mode_select: {
                        "state": optimizer.cfg.automated_option,
                        "attributes": {},
                    },
                    optimizer.cfg.ems_mode_select: {
                        "state": raw_mode,
                        "attributes": {},
                    },
                }

                parsed = asyncio.run(optimizer._read_state())
                state = self._full_opportunity(
                    sigenergy_mode=parsed.sigenergy_mode,
                    sigenergy_mode_observed=parsed.sigenergy_mode_observed,
                    current_ems_mode=parsed.current_ems_mode,
                    ems_mode_observed=parsed.ems_mode_observed,
                    current_export_limit=25.0,
                )
                decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

                self.assertTrue(parsed.sigenergy_mode_observed)
                self.assertFalse(
                    parsed.ems_mode_observed
                    and parsed.current_ems_mode == MODE_MAX_SELF
                )
                self.assert_contract_outputs(
                    decision,
                    (MODE_MAX_SELF, 0.0, 0.0, 25.0),
                )

    def test_successful_msc_request_is_not_observation(self) -> None:
        ha = RecordingHA(settle_numbers=False, settle_selects=False)
        optimizer = self.optimizer(ha)
        ha.state_values = {
            optimizer.cfg.ems_mode_select: MODE_CMD_DISCHARGE_PV,
            optimizer.cfg.grid_export_limit: 0.01,
        }
        first_state = self._ordinary_state(
            95.7,
            current_ems_mode=MODE_CMD_DISCHARGE_PV,
            ems_mode_observed=True,
            current_export_limit=0.01,
        )
        first = self.decide(optimizer, first_state, self.FIXED_AFTERNOON)

        asyncio.run(optimizer._apply(first_state, first))

        self.assertIn(
            ("select_option", optimizer.cfg.ems_mode_select, MODE_MAX_SELF),
            ha.calls,
        )
        self.assertEqual(
            MODE_CMD_DISCHARGE_PV,
            ha.state_values[optimizer.cfg.ems_mode_select],
        )
        self.assertFalse(
            any(
                call[0] == "set_number"
                and call[1] == optimizer.cfg.grid_export_limit
                and float(call[2]) > 0.011
                for call in ha.calls
            )
        )
        optimizer._last_state = first_state
        optimizer._last_decision = first

        later_unverified = self._ordinary_state(
            95.7,
            current_ems_mode=MODE_CMD_DISCHARGE_PV,
            ems_mode_observed=True,
            current_export_limit=0.01,
        )
        second = self.decide(optimizer, later_unverified, self.FIXED_AFTERNOON)

        self.assert_contract_outputs(
            second,
            (MODE_MAX_SELF, 0.0, 0.0, 25.0),
        )

    def test_return_from_discharge_waits_for_observed_close_before_requesting_msc(
        self,
    ) -> None:
        ha = RecordingHA(settle_numbers=False, settle_selects=False)
        optimizer = self.optimizer(ha)
        ha.state_values = {
            optimizer.cfg.ems_mode_select: MODE_CMD_DISCHARGE_PV,
            optimizer.cfg.grid_export_limit: 12.0,
        }
        state = self._ordinary_state(
            95.7,
            current_ems_mode=MODE_CMD_DISCHARGE_PV,
            ems_mode_observed=True,
            current_export_limit=12.0,
        )
        decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

        self.assert_contract_outputs(
            decision,
            (MODE_MAX_SELF, 0.0, 0.0, 25.0),
        )
        asyncio.run(optimizer._apply(state, decision))

        close_call = ("set_number", optimizer.cfg.grid_export_limit, 0.01)
        msc_call = ("select_option", optimizer.cfg.ems_mode_select, MODE_MAX_SELF)
        self.assertIn(close_call, ha.calls)
        self.assertNotIn(msc_call, ha.calls)
        self.assertEqual(12.0, ha.state_values[optimizer.cfg.grid_export_limit])

    def test_exact_msc_does_not_reopen_before_export_is_observed_closed(self) -> None:
        ha = RecordingHA(settle_numbers=False, settle_selects=False)
        optimizer = self.optimizer(ha)
        ha.state_values = {
            optimizer.cfg.ems_mode_select: MODE_CMD_DISCHARGE_PV,
            optimizer.cfg.grid_export_limit: 12.0,
        }
        first_state = self._ordinary_state(
            95.7,
            current_ems_mode=MODE_CMD_DISCHARGE_PV,
            ems_mode_observed=True,
            current_export_limit=12.0,
        )
        first = self.decide(optimizer, first_state, self.FIXED_AFTERNOON)
        asyncio.run(optimizer._apply(first_state, first))
        optimizer._last_state = first_state
        optimizer._last_decision = first

        ha.state_values[optimizer.cfg.ems_mode_select] = MODE_MAX_SELF
        msc_but_still_open = self._ordinary_state(
            95.7,
            current_ems_mode=MODE_MAX_SELF,
            ems_mode_observed=True,
            current_export_limit=12.0,
        )
        second = self.decide(optimizer, msc_but_still_open, self.FIXED_AFTERNOON)

        self.assert_contract_outputs(
            second,
            (MODE_MAX_SELF, 0.0, 0.0, 25.0),
        )

    def _assert_pending_transition_preserves_pv_safety_owner(
        self, *, standby: bool,
    ) -> None:
        ha = RecordingHA(settle_numbers=False, settle_selects=False)
        optimizer = self.optimizer(
            ha,
            standby_holdoff_enabled=standby,
            standby_holdoff_end_time="23:59",
            pv_forecast_holdoff_kwh=120.0,
            ess_max_charging_limit="number.test_ess_charge",
            ess_max_discharging_limit="number.test_ess_discharge",
        )
        optimizer._tz = timezone.utc
        cfg = optimizer.cfg
        expected_pv_limit = 2.0 if standby else 0.1
        msc_call = ("select_option", cfg.ems_mode_select, MODE_MAX_SELF)
        close_call = ("set_number", cfg.grid_export_limit, 0.01)
        phases = (
            ("open", 12.0, True, MODE_CMD_DISCHARGE_PV, True, False),
            ("exact_msc_still_open", 12.0, True, MODE_MAX_SELF, True, False),
            ("untrusted_close", 0.01, False, MODE_MAX_SELF, True, False),
            ("untrusted_close_repeated", 0.01, False, MODE_MAX_SELF, False, False),
            ("closed", 0.01, True, MODE_CMD_DISCHARGE_PV, True, True),
            ("msc_unobserved", 0.01, True, MODE_MAX_SELF, False, True),
            ("msc_not_exact", 0.01, True, "Maximum Self", True, True),
        )
        for name, export_limit, export_observed, ems, ems_observed, request_msc in phases:
            with self.subTest(phase=name):
                state = self._ordinary_state(
                    60.0,
                    feedin_price=0.0,
                    feedin_price_cents=0.0,
                    current_price=0.30 if standby else -0.10,
                    current_price_cents=30.0 if standby else -10.0,
                    price_is_negative=not standby,
                    demand_window_active=True,
                    demand_window_observed=True,
                    load_kw=1.4,
                    forecast_today_kwh=150.0,
                    forecast_remaining_kwh=150.0,
                    price_forecast_source_trusted=True,
                    price_forecast_entries=[
                        {
                            "start_time": self.FIXED_AFTERNOON.timestamp() + 1800,
                            "per_kwh": -0.10,
                        },
                    ],
                    current_export_limit=export_limit,
                    current_export_limit_observed=export_observed,
                    current_ems_mode=ems,
                    ems_mode_observed=ems_observed,
                    current_import_limit=10.0,
                    current_ess_charge_limit=0.01,
                    current_ess_discharge_limit=25.0,
                    current_pv_max_power_limit=25.0,
                )
                ha._record_state_value(cfg.grid_export_limit, export_limit)
                ha._record_state_value(cfg.ems_mode_select, ems)
                decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

                self.assertEqual(standby, decision.standby_holdoff_active)
                self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
                self.assertEqual(0.0, decision.export_limit)
                self.assertEqual(0.0, decision.import_limit)
                self.assertEqual(expected_pv_limit, decision.pv_max_power_limit)
                if standby:
                    self.assertEqual(
                        "standby_holdoff_active",
                        decision.trace_values.get("pv_cap_reason"),
                    )

                call_start = len(ha.calls)
                result = asyncio.run(optimizer._apply(state, decision))
                cycle_calls = ha.calls[call_start:]

                self.assertFalse(result.succeeded)
                self.assertFalse(result.fallback_attempted)
                self.assertTrue(decision.trace_gates.get("msc_transition_pending"))
                self.assertIn(
                    ("set_number", cfg.pv_max_power_limit, expected_pv_limit),
                    cycle_calls,
                )
                self.assertIn(("set_number", cfg.grid_import_limit, 0.01), cycle_calls)
                self.assertIn(
                    ("set_number", cfg.ess_max_discharging_limit, 0.01),
                    cycle_calls,
                )
                self.assertEqual(request_msc, msc_call in cycle_calls)
                if not request_msc:
                    self.assertIn(close_call, cycle_calls)
                for method, entity_id, value in cycle_calls:
                    if method != "set_number":
                        continue
                    if entity_id in {
                        cfg.grid_export_limit,
                        cfg.grid_import_limit,
                        cfg.ess_max_discharging_limit,
                    }:
                        self.assertLessEqual(value, 0.01)
                    if entity_id == cfg.pv_max_power_limit:
                        self.assertLessEqual(value, expected_pv_limit)
                    self.assertNotEqual(cfg.ess_max_charging_limit, entity_id)
                optimizer._last_state = state
                optimizer._last_decision = decision

    def test_pending_msc_transition_preserves_standby_pv_restriction(self) -> None:
        self._assert_pending_transition_preserves_pv_safety_owner(standby=True)

    def test_pending_msc_transition_preserves_negative_price_pv_restriction(self) -> None:
        self._assert_pending_transition_preserves_pv_safety_owner(standby=False)

    def test_pending_transition_pv_restriction_survives_export_failure_and_fallback(self) -> None:
        for raises in (False, True):
            with self.subTest(export_close_raises=raises):
                class FailedFirstExportHA(RecordingHA):
                    export_entity = ""
                    failed = False

                    async def set_number(self, entity_id, value):
                        if entity_id == self.export_entity and not self.failed:
                            self.failed = True
                            self.calls.append(("set_number", entity_id, value))
                            if raises:
                                raise RuntimeError("export actuator unavailable")
                            return False
                        return await super().set_number(entity_id, value)

                ha = FailedFirstExportHA()
                optimizer = self.optimizer(ha)
                cfg = optimizer.cfg
                ha.export_entity = cfg.grid_export_limit
                state = self._ordinary_state(
                    60.0,
                    current_price=-0.10,
                    current_price_cents=-10.0,
                    price_is_negative=True,
                    demand_window_active=True,
                    demand_window_observed=True,
                    current_ems_mode=MODE_CMD_DISCHARGE_PV,
                    current_export_limit=12.0,
                    current_pv_max_power_limit=25.0,
                )
                decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)
                self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
                self.assertEqual(0.1, decision.pv_max_power_limit)

                with later_msc_report_clock(ha, self.FIXED_AFTERNOON):
                    result = asyncio.run(optimizer._apply(state, decision))

                self.assertFalse(result.succeeded)
                self.assertTrue(result.fallback_attempted)
                self.assertTrue(result.fallback_succeeded)
                pv_calls = [
                    value for method, entity_id, value in ha.calls
                    if method == "set_number" and entity_id == cfg.pv_max_power_limit
                ]
                self.assertEqual([0.1, 0.1], pv_calls)
                self.assertLess(
                    ha.calls.index(("set_number", cfg.pv_max_power_limit, 0.1)),
                    ha.calls.index(("select_option", cfg.ems_mode_select, MODE_MAX_SELF)),
                )
                self.assertIn(("set_number", cfg.grid_import_limit, 0.01), ha.calls)
                self.assertFalse(any(
                    method == "set_number" and entity_id == cfg.grid_export_limit and value > 0.011
                    for method, entity_id, value in ha.calls
                ))

    def test_settled_transition_discharge_failure_preserves_pv_safety_in_fallback(self) -> None:
        async def run(standby, fallback_settles):
            ha = ClockedRecordingHA()
            moment = [self.FIXED_AFTERNOON.replace(tzinfo=timezone.utc)]

            class ObservedDateTime(datetime):
                @classmethod
                def now(cls, tz=None):
                    return moment[0].astimezone(tz) if tz else moment[0].replace(tzinfo=None)

            original_select_option = ha.select_option

            async def later_msc_report(entity_id, value):
                # A genuine actuator report follows, rather than shares, the
                # command's frozen timestamp. Preserve all recovery assertions.
                moment[0] += timedelta(milliseconds=1)
                return await original_select_option(entity_id, value)

            ha.select_option = later_msc_report
            optimizer = self.optimizer(
                ha,
                standby_holdoff_enabled=standby,
                standby_holdoff_end_time="23:59",
                pv_forecast_holdoff_kwh=120.0,
                ess_max_discharging_limit="number.test_ess_discharge",
            )
            optimizer._tz = timezone.utc
            cfg = optimizer.cfg
            expected_pv_limit = 2.0 if standby else 0.1
            failure_injected = False
            original_set_number = ha.set_number

            async def fail_discharge_once(entity_id, value):
                nonlocal failure_injected
                if entity_id == cfg.ess_max_discharging_limit and not failure_injected:
                    failure_injected = True
                    ha.calls.append(("set_number", entity_id, value))
                    if not fallback_settles:
                        # The transition settled, but export subsequently drifts
                        # open and the fallback close is accepted without settling.
                        ha._record_state_value(cfg.grid_export_limit, 12.0)
                        ha.settle_numbers = False
                    return False
                return await original_set_number(entity_id, value)

            for second in range(3):
                when = self.FIXED_AFTERNOON + timedelta(seconds=second)
                ems = MODE_MAX_SELF if second == 2 else MODE_CMD_DISCHARGE_PV
                state = self._ordinary_state(
                    60.0,
                    when=when,
                    feedin_price=0.0,
                    feedin_price_cents=0.0,
                    current_price=0.30 if standby else -0.10,
                    current_price_cents=30.0 if standby else -10.0,
                    price_is_negative=not standby,
                    demand_window_active=True,
                    demand_window_observed=True,
                    load_kw=1.4,
                    forecast_today_kwh=150.0,
                    forecast_remaining_kwh=150.0,
                    price_forecast_source_trusted=True,
                    price_forecast_entries=[
                        {"start_time": when.timestamp() + 1800, "per_kwh": -0.10},
                    ],
                    current_ems_mode=ems,
                    current_export_limit=12.0 if second == 0 else 0.01,
                    current_import_limit=0.01,
                    current_pv_max_power_limit=25.0 if second == 0 else expected_pv_limit,
                )
                moment[0] = when.replace(tzinfo=timezone.utc)
                with patch("app.optimizer.datetime", ObservedDateTime):
                    ha._record_state_value(cfg.ems_mode_select, state.current_ems_mode)
                    ha._record_state_value(cfg.grid_export_limit, state.current_export_limit)
                    decision = self.decide(optimizer, state, when)
                    self.assertEqual(standby, decision.standby_holdoff_active)
                    self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
                    self.assertEqual(expected_pv_limit, decision.pv_max_power_limit)
                    if second == 2:
                        self.assertTrue(optimizer._msc_transition_observed(state))
                        ha.set_number = fail_discharge_once
                    call_start = len(ha.calls)
                    event_start = len(ha.events)
                    result = await optimizer._apply(state, decision)
                cycle_calls = ha.calls[call_start:]
                cycle_events = ha.events[event_start:]
                self.assertFalse(result.succeeded)
                if second < 2:
                    self.assertFalse(result.fallback_attempted)
                    self.assertEqual(
                        second == 1,
                        ("select_option", cfg.ems_mode_select, MODE_MAX_SELF) in cycle_calls,
                    )
                else:
                    self.assertTrue(failure_injected)
                    self.assertTrue(result.fallback_attempted)
                    self.assertEqual(fallback_settles, result.fallback_succeeded, result.error)
                    pv_calls = [
                        value for method, entity_id, value in cycle_calls
                        if method == "set_number" and entity_id == cfg.pv_max_power_limit
                    ]
                    self.assertTrue(pv_calls)
                    self.assertTrue(all(value <= expected_pv_limit for value in pv_calls), pv_calls)
                    self.assertLess(
                        cycle_events.index(("set_number", cfg.pv_max_power_limit, expected_pv_limit)),
                        cycle_events.index(("bulk_states", cfg.ems_mode_select, None)),
                    )
                    self.assertEqual(expected_pv_limit, ha.state_values[cfg.pv_max_power_limit])
                self.assertFalse(any(
                    method == "set_number" and entity_id == cfg.grid_export_limit and value > 0.011
                    for method, entity_id, value in cycle_calls
                ))
                optimizer._last_state = state
                optimizer._last_decision = decision

        for standby in (True, False):
            for fallback_settles in (True, False):
                with self.subTest(standby=standby, fallback_settles=fallback_settles):
                    asyncio.run(run(standby, fallback_settles))

    def test_fallback_recovery_requires_fresh_post_request_msc_provenance(self) -> None:
        async def run(scenario):
            moment = [self.FIXED_AFTERNOON.replace(tzinfo=timezone.utc)]

            class ObservedDateTime(datetime):
                @classmethod
                def now(cls, tz=None):
                    return moment[0].astimezone(tz) if tz else moment[0].replace(tzinfo=None)

            class FallbackObservationHA(ClockedRecordingHA):
                export_failed = False
                report = None

                async def set_number(self, entity_id, value):
                    if entity_id == cfg.grid_export_limit and not self.export_failed:
                        self.export_failed = True
                        self.calls.append(("set_number", entity_id, value))
                        return False
                    return await super().set_number(entity_id, value)

                async def select_option(self, entity_id, value):
                    self.calls.append(("select_option", entity_id, value))
                    requested_at = moment[0]
                    moment[0] += timedelta(seconds=1)
                    observed = (
                        "unavailable" if scenario == "unavailable"
                        else MODE_CMD_DISCHARGE_PV if scenario == "unsettled"
                        else MODE_MAX_SELF
                    )
                    reported_at = moment[0]
                    if scenario == "stale":
                        reported_at -= timedelta(hours=1)
                    elif scenario in {"cached_before_request", "failed_request", "uncorrelated"}:
                        reported_at = requested_at - timedelta(seconds=1)
                    elif scenario == "same_request_timestamp":
                        reported_at = requested_at
                    elif scenario == "future":
                        reported_at += timedelta(minutes=1)
                    updated_at = reported_at
                    if scenario == "fresh_unchanged_report":
                        updated_at -= timedelta(hours=1)
                    metadata = {
                        "last_updated": updated_at.isoformat(),
                        "last_reported": reported_at.isoformat(),
                    }
                    self.state_values[entity_id] = observed
                    self._state_value_metadata[entity_id] = (
                        {} if scenario == "missing_provenance" else metadata
                    )
                    self.report = {
                        "entity_id": "select.wrong_entity" if scenario == "uncorrelated" else entity_id,
                        "state": observed,
                        **metadata,
                    }
                    if scenario == "uncorrelated":
                        self.report["last_reported"] = moment[0].isoformat()
                    return scenario != "failed_request"

                async def get_state_report_metadata(self, entity_ids):
                    if scenario == "missing_provenance" or cfg.ems_mode_select not in entity_ids:
                        return {}
                    return {cfg.ems_mode_select: self.report}

            ha = FallbackObservationHA()
            optimizer = self.optimizer(
                ha,
                ess_max_charging_limit="number.test_ess_charge",
                ess_max_discharging_limit="number.test_ess_discharge",
            )
            cfg = optimizer.cfg
            # Bound timeout only; retain the production polling and trust checks.
            wait_for_exact = optimizer._wait_for_exact_entity_state

            async def short_wait(*args, **kwargs):
                kwargs["timeout_s"] = 0.01
                return await wait_for_exact(*args, **kwargs)

            optimizer._wait_for_exact_entity_state = short_wait
            state = self._ordinary_state(
                60.0,
                current_export_limit=12.0,
                current_import_limit=0.01,
                current_ess_charge_limit=0.01,
                current_ess_discharge_limit=0.01,
                demand_window_active=False,
                demand_window_observed=True,
            )
            decision = Decision(
                ems_mode=MODE_MAX_SELF, export_limit=0.0,
                export_intent=EXPORT_BLOCKED, import_limit=0.0,
                ess_charge_limit=25.0, ess_discharge_limit=25.0,
                pv_max_power_limit=25.0,
            )
            with patch("app.optimizer.datetime", ObservedDateTime):
                result = await optimizer._apply(state, decision)
                export_value, export_trusted = await optimizer._read_trusted_live_number(cfg.grid_export_limit)

            self.assertFalse(result.succeeded)
            self.assertTrue(result.fallback_attempted)
            self.assertTrue(export_trusted)
            self.assertEqual(0.01, export_value)
            fresh = scenario in {"fresh_changed_state", "fresh_unchanged_report"}
            recovery_entities = {
                cfg.grid_import_limit, cfg.ess_max_charging_limit,
                cfg.ess_max_discharging_limit, cfg.pv_max_power_limit,
            }
            recovered = {
                entity_id for method, entity_id, value in ha.calls
                if method == "set_number" and entity_id in recovery_entities and value > 0.011
            }
            self.assertEqual(recovery_entities if fresh else set(), recovered)
            self.assertEqual(fresh, result.fallback_succeeded, result.error)
            self.assertIn(("set_number", cfg.ess_max_discharging_limit, 0.01), ha.calls)
            self.assertFalse(any(
                method == "set_number" and entity_id == cfg.grid_export_limit and value > 0.011
                for method, entity_id, value in ha.calls
            ))

        for scenario in (
            "stale", "missing_provenance", "unavailable", "unsettled", "failed_request",
            "cached_before_request", "same_request_timestamp", "future", "uncorrelated",
            "fresh_changed_state", "fresh_unchanged_report",
        ):
            with self.subTest(scenario=scenario):
                asyncio.run(run(scenario))

    def _live_transition_optimizer(self, ha):
        return self.optimizer(
            ha,
            ess_max_charging_limit="number.test_ess_charge",
            ess_max_discharging_limit="number.test_ess_discharge",
        )

    async def _live_transition_cycle(
        self, optimizer, ha, second, ems, export, *,
        ems_second=None, export_second=None, owner=None, mode=None, discharge=False,
    ):
        """Supply the same timestamped reports to snapshot and live HA readback."""
        when = self.FIXED_AFTERNOON + timedelta(seconds=second)
        cfg = optimizer.cfg
        control_mode = mode or cfg.automated_option

        def report(entity_id, value, report_second):
            available = value is not None
            at = (self.FIXED_AFTERNOON + timedelta(seconds=report_second)).replace(tzinfo=timezone.utc)
            ha.state_values[entity_id] = value if available else "unavailable"
            ha._state_value_metadata[entity_id] = (
                {"last_updated": at.isoformat(), "last_reported": at.isoformat()}
                if available else {}
            )
            return HVACObservedValue(
                value=value, available=available,
                fresh=available and 0 <= second - report_second <= cfg.hvac_solar_data_max_age_seconds,
                observed_at_ts=at.timestamp() if available else None,
            )

        ems_report = report(cfg.ems_mode_select, ems, second if ems_second is None else ems_second)
        export_report = report(cfg.grid_export_limit, export, second if export_second is None else export_second)
        state = self._ordinary_state(
            95.7, when=when,
            sigenergy_mode=control_mode,
            current_ems_mode=ems or "unavailable",
            ems_mode_observed=ems_report.available and ems_report.fresh,
            current_export_limit=export if export is not None else 0.0,
            current_export_limit_observed=export_report.available and export_report.fresh,
            current_import_limit=0.01,
            current_import_limit_observed=True,
            demand_window_active=True,
            demand_window_observed=True,
            current_pv_max_power_limit=25.0,
            current_price=-0.10 if owner == "negative" else 0.30,
            price_is_negative=owner == "negative",
        )
        state.hvac_solar_inputs = HVACSolarInputContext(
            live_snapshot=True,
            control_mode=HVACObservedValue(
                value=control_mode, available=True, fresh=True,
                observed_at_ts=when.replace(tzinfo=timezone.utc).timestamp(),
            ),
            observed_ems_mode=ems_report,
            observed_export_limit=export_report,
        )
        # This is observation metadata populated by _read_state, not a latch.
        state._msc_ems_reported_at = ems_report.observed_at_ts
        pv_limit = 2.0 if owner == "standby" else 0.1 if owner == "negative" else 25.0
        decision = Decision(
            ems_mode=MODE_CMD_DISCHARGE_PV if discharge else MODE_MAX_SELF,
            export_limit=12.0 if discharge else 0.0 if owner else 25.0,
            export_intent=BATTERY_EXPORT if discharge else EXPORT_BLOCKED if owner else MSC_SURPLUS_CEILING,
            requires_verified_msc_before_export=not discharge and owner is None,
            import_limit=0.0,
            ess_charge_limit=25.0,
            ess_discharge_limit=25.0,
            pv_max_power_limit=pv_limit,
            standby_holdoff_active=owner == "standby",
        )
        ha.calls.clear()
        ha.clock_utc = when.replace(tzinfo=timezone.utc)

        class ObservedDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return cls.fromtimestamp(ha.clock_utc.timestamp(), tz)

        with patch("app.optimizer.datetime", ObservedDateTime):
            result = await optimizer._apply(state, decision)
        self.assertTrue(state.hvac_solar_inputs.live_snapshot)
        return result, list(ha.calls)

    def _assert_live_transition_restrictive(self, optimizer, result, calls, *, msc):
        cfg = optimizer.cfg
        self.assertFalse(result.succeeded)
        self.assertFalse(result.fallback_attempted)
        self.assertEqual(msc, ("select_option", cfg.ems_mode_select, MODE_MAX_SELF) in calls)
        if not msc:
            self.assertIn(("set_number", cfg.grid_export_limit, 0.01), calls)
        self.assertIn(("set_number", cfg.grid_import_limit, 0.01), calls)
        self.assertIn(("set_number", cfg.ess_max_discharging_limit, 0.01), calls)
        for method, entity_id, value in calls:
            if method != "set_number":
                continue
            self.assertNotEqual(cfg.ess_max_charging_limit, entity_id)
            if entity_id in {cfg.grid_export_limit, cfg.grid_import_limit, cfg.ess_max_discharging_limit}:
                self.assertLessEqual(value, 0.011)

    def test_live_multicycle_transition_loses_telemetry_then_recovers(self):
        async def run():
            ha = LiveTransitionHA()
            optimizer = self._live_transition_optimizer(ha)
            result, _ = await self._live_transition_cycle(
                optimizer, ha, -1, MODE_CMD_DISCHARGE_PV, 12.0, discharge=True,
            )
            self.assertTrue(result.succeeded, result.error)
            stages = (
                (0, MODE_CMD_DISCHARGE_PV, 12.0, {}, False),
                (1, MODE_CMD_DISCHARGE_PV, 0.01, {"export_second": 0}, False),
                (2, MODE_CMD_DISCHARGE_PV, 0.01, {}, True),
                (3, MODE_MAX_SELF, 0.01, {"ems_second": 2}, True),
                (4, None, 0.01, {}, True),
                (5, MODE_MAX_SELF, None, {}, False),
                (6, MODE_MAX_SELF, 0.01, {"export_second": 5}, False),
                (7, MODE_MAX_SELF, 0.01, {}, True),
                (8, MODE_MAX_SELF, 0.01, {"ems_second": -200}, True),
                (9, MODE_MAX_SELF, 0.01, {"ems_second": 7}, True),
            )
            for second, ems, export, metadata, msc in stages:
                result, calls = await self._live_transition_cycle(
                    optimizer, ha, second, ems, export, **metadata,
                )
                self._assert_live_transition_restrictive(optimizer, result, calls, msc=msc)
            result, calls = await self._live_transition_cycle(optimizer, ha, 10, MODE_MAX_SELF, 0.01)
            self.assertTrue(result.succeeded, result.error)
            self.assertIn(("set_number", optimizer.cfg.grid_export_limit, 25.0), calls)
            self.assertFalse(any(
                method == "set_number" and entity_id == optimizer.cfg.grid_import_limit and value > 0.011
                for method, entity_id, value in calls
            ))
        asyncio.run(run())

    def test_live_restart_during_unfinished_transition_requires_new_observations(self):
        async def run(restart_phase):
            ha = LiveTransitionHA()
            optimizer = self._live_transition_optimizer(ha)
            await self._live_transition_cycle(optimizer, ha, -1, MODE_CMD_DISCHARGE_PV, 12.0, discharge=True)
            result, calls = await self._live_transition_cycle(optimizer, ha, 0, MODE_CMD_DISCHARGE_PV, 12.0)
            self._assert_live_transition_restrictive(optimizer, result, calls, msc=False)
            if restart_phase == "msc_pending":
                result, calls = await self._live_transition_cycle(optimizer, ha, 1, MODE_CMD_DISCHARGE_PV, 0.01)
                self._assert_live_transition_restrictive(optimizer, result, calls, msc=True)

            # New process state; retain only the physical HA observations.
            optimizer = self._live_transition_optimizer(ha)
            export = 0.01 if restart_phase == "msc_pending" else 12.0 if restart_phase == "close_pending" else None
            result, calls = await self._live_transition_cycle(optimizer, ha, 2, MODE_CMD_DISCHARGE_PV, export)
            self._assert_live_transition_restrictive(optimizer, result, calls, msc=restart_phase == "msc_pending")
            result, calls = await self._live_transition_cycle(optimizer, ha, 3, MODE_CMD_DISCHARGE_PV, 0.01)
            self._assert_live_transition_restrictive(optimizer, result, calls, msc=True)
            request_second = 2 if restart_phase == "msc_pending" else 3
            result, calls = await self._live_transition_cycle(
                optimizer, ha, 4, MODE_MAX_SELF, 0.01, ems_second=request_second,
            )
            self._assert_live_transition_restrictive(optimizer, result, calls, msc=True)
            result, calls = await self._live_transition_cycle(optimizer, ha, 5, MODE_MAX_SELF, 0.01)
            self.assertTrue(result.succeeded, result.error)
            self.assertIn(("set_number", optimizer.cfg.grid_export_limit, 25.0), calls)

        for restart_phase in ("close_pending", "msc_pending", "telemetry_missing"):
            with self.subTest(restart_phase=restart_phase):
                asyncio.run(run(restart_phase))

    def test_live_transition_preserves_independent_pv_and_demand_window_owners(self):
        async def run(owner):
            ha = LiveTransitionHA()
            optimizer = self._live_transition_optimizer(ha)
            await self._live_transition_cycle(optimizer, ha, -1, MODE_CMD_DISCHARGE_PV, 12.0, discharge=True)
            for second, ems, export, msc in (
                (0, MODE_CMD_DISCHARGE_PV, 12.0, False),
                (1, MODE_CMD_DISCHARGE_PV, None, False),
                (2, MODE_CMD_DISCHARGE_PV, 0.01, True),
                (3, None, 0.01, True),
                (4, MODE_MAX_SELF, 0.01, True),
            ):
                result, calls = await self._live_transition_cycle(optimizer, ha, second, ems, export, owner=owner)
                if second < 4:
                    self._assert_live_transition_restrictive(optimizer, result, calls, msc=msc)
                else:
                    self.assertTrue(result.succeeded, result.error)
                limit = 2.0 if owner == "standby" else 0.1
                self.assertIn(("set_number", optimizer.cfg.pv_max_power_limit, limit), calls)
                for method, entity_id, value in calls:
                    if method == "set_number":
                        if entity_id == optimizer.cfg.pv_max_power_limit:
                            self.assertLessEqual(value, limit)
                        if entity_id in {optimizer.cfg.grid_import_limit, optimizer.cfg.grid_export_limit}:
                            self.assertLessEqual(value, 0.011)
        for owner in ("standby", "negative"):
            with self.subTest(owner=owner):
                asyncio.run(run(owner))

    def test_live_pending_transition_yields_to_manual_and_force(self):
        async def run(mode_name):
            ha = LiveTransitionHA()
            optimizer = self._live_transition_optimizer(ha)
            cfg = optimizer.cfg
            await self._live_transition_cycle(optimizer, ha, -1, MODE_CMD_DISCHARGE_PV, 12.0, discharge=True)
            result, calls = await self._live_transition_cycle(optimizer, ha, 0, MODE_CMD_DISCHARGE_PV, 12.0)
            self._assert_live_transition_restrictive(optimizer, result, calls, msc=False)
            mode = getattr(cfg, mode_name)
            if mode_name == "full_import_option":
                ha.report_after_select = (cfg.ems_mode_select, MODE_CMD_CHARGE_GRID)
            result, calls = await self._live_transition_cycle(optimizer, ha, 1, MODE_CMD_DISCHARGE_PV, 12.0, mode=mode)
            self.assertTrue(result.succeeded, result.error)
            self.assertNotIn(("select_option", cfg.ems_mode_select, MODE_MAX_SELF), calls)
            if mode_name == "manual_option":
                self.assertEqual([], calls)
            else:
                expected_ems = MODE_CMD_CHARGE_GRID if mode_name == "full_import_option" else MODE_CMD_DISCHARGE_PV
                self.assertIn(("select_option", cfg.ems_mode_select, expected_ems), calls)
        for mode_name in ("manual_option", "full_import_option", "full_export_option"):
            with self.subTest(mode=mode_name):
                asyncio.run(run(mode_name))

    def test_live_force_import_without_observed_settlement_remains_failed(self):
        async def run():
            ha = LiveTransitionHA()
            optimizer = self._live_transition_optimizer(ha)
            cfg = optimizer.cfg
            await self._live_transition_cycle(optimizer, ha, -1, MODE_CMD_DISCHARGE_PV, 12.0, discharge=True)
            result, calls = await self._live_transition_cycle(optimizer, ha, 0, MODE_CMD_DISCHARGE_PV, 12.0)
            self._assert_live_transition_restrictive(optimizer, result, calls, msc=False)
            # Accepted Force commands receive no subsequent physical EMS report.
            result, calls = await self._live_transition_cycle(
                optimizer, ha, 1, MODE_CMD_DISCHARGE_PV, 12.0, mode=cfg.full_import_option,
            )
            self.assertFalse(result.succeeded)
            self.assertFalse(result.fallback_attempted)
            self.assertIn("manual mode drift correction failed: ems_mode", result.error)
            self.assertIn(("select_option", cfg.ems_mode_select, MODE_CMD_CHARGE_GRID), calls)
            self.assertNotIn(("select_option", cfg.ems_mode_select, MODE_MAX_SELF), calls)
            self.assertEqual(MODE_CMD_DISCHARGE_PV, ha.state_values[cfg.ems_mode_select])
        asyncio.run(run())

    def test_later_exact_msc_after_observed_close_reopens_normal_ceiling(self) -> None:
        ha = RecordingHA(settle_numbers=False, settle_selects=False)
        optimizer = self.optimizer(ha)
        ha.state_values = {
            optimizer.cfg.ems_mode_select: MODE_CMD_DISCHARGE_PV,
            optimizer.cfg.grid_export_limit: 0.01,
        }
        first_state = self._ordinary_state(
            95.7,
            current_ems_mode=MODE_CMD_DISCHARGE_PV,
            ems_mode_observed=True,
            current_export_limit=0.01,
        )
        first = self.decide(optimizer, first_state, self.FIXED_AFTERNOON)
        # Model a later report deterministically, even on coarse host clocks.
        with self.optimizer_time(datetime.now() - timedelta(seconds=1)):
            asyncio.run(optimizer._apply(first_state, first))
        first_cycle_calls = list(ha.calls)
        optimizer._last_state = first_state
        optimizer._last_decision = first

        ha._record_state_value(optimizer.cfg.ems_mode_select, MODE_MAX_SELF)
        ha._record_state_value(optimizer.cfg.grid_export_limit, 0.01)
        verified = self._ordinary_state(
            95.7,
            current_ems_mode=MODE_MAX_SELF,
            ems_mode_observed=True,
            current_export_limit=0.01,
        )
        second = self.decide(optimizer, verified, self.FIXED_AFTERNOON)

        self.assert_msc_surplus_permission(
            second,
            export_ceiling=25.0,
        )
        second_cycle_start = len(ha.calls)
        asyncio.run(optimizer._apply(verified, second))
        second_cycle_calls = ha.calls[second_cycle_start:]

        high_export_call = (
            "set_number",
            optimizer.cfg.grid_export_limit,
            25.0,
        )
        self.assertNotIn(high_export_call, first_cycle_calls)
        self.assertIn(high_export_call, second_cycle_calls)
        high_export_index = second_cycle_calls.index(high_export_call)
        self.assertTrue(
            any(
                call[0] == "get_state_value"
                and call[1] == optimizer.cfg.ems_mode_select
                and index < high_export_index
                for index, call in enumerate(second_cycle_calls)
            )
        )

    def test_deliberate_export_target_settles_before_discharge_mode(self) -> None:
        ha = ScriptedReadbackHA({})
        optimizer = self.optimizer(ha)
        ha._readbacks[optimizer.cfg.grid_export_limit] = [12.0]
        ha.state_values = {
            optimizer.cfg.ems_mode_select: MODE_MAX_SELF,
            optimizer.cfg.grid_export_limit: 25.0,
        }
        state = self.state(
            self.FIXED_AFTERNOON,
            battery_soc=95.0,
            available_discharge_energy_kwh=28.5,
            battery_power_sensor_kw=-0.2,
            feedin_price=1.10,
            feedin_price_cents=110.0,
            pv_kw=0.0,
            solar_power_now_kw=0.0,
            load_kw=0.0,
            ess_max_discharge_kw=12.0,
            current_export_limit=25.0,
            current_ems_mode=MODE_MAX_SELF,
        )
        decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

        self.assert_contract_outputs(
            decision,
            (MODE_CMD_DISCHARGE_PV, 12.0, 0.0, 25.0),
        )
        self.assertEqual(BATTERY_EXPORT, decision.export_intent)
        self.assertEqual(
            "high_price",
            decision.trace_values.get("battery_export_owner"),
        )
        asyncio.run(optimizer._apply(state, decision))

        export_call = ("set_number", optimizer.cfg.grid_export_limit, 12.0)
        mode_call = (
            "select_option",
            optimizer.cfg.ems_mode_select,
            MODE_CMD_DISCHARGE_PV,
        )
        export_index = ha.calls.index(export_call)
        mode_index = ha.calls.index(mode_call)
        self.assertTrue(
            any(
                optimizer.cfg.grid_export_limit in entity_ids
                for entity_ids in ha.bulk_state_calls
            )
        )
        self.assertLess(export_index, mode_index)

    def test_reserve_and_forecast_guards_block_deliberate_battery_export(
        self,
    ) -> None:
        cases = (
            (
                "reserve_floor",
                {
                    "battery_soc": 20.0,
                    "available_discharge_energy_kwh": 6.0,
                    "forecast_remaining_kwh": 100.0,
                },
            ),
            (
                "insufficient_remaining_forecast",
                {
                    "battery_soc": 60.0,
                    "available_discharge_energy_kwh": 18.0,
                    "forecast_remaining_kwh": 1.0,
                },
            ),
        )
        for name, guarded_values in cases:
            with self.subTest(name=name):
                optimizer = self.optimizer()
                state = self.state(
                    self.FIXED_AFTERNOON,
                    battery_power_sensor_kw=-0.2,
                    feedin_price=1.10,
                    feedin_price_cents=110.0,
                    pv_kw=0.0,
                    solar_power_now_kw=0.0,
                    load_kw=1.0,
                    **guarded_values,
                )

                decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

                self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
                self.assertNotIn(decision.ems_mode, DISCHARGE_MODES)
                self.assertLessEqual(decision.export_limit, 0.01)

    def _assert_demand_window_baseline(self, pv_kw: float) -> None:
        when = datetime(2026, 1, 15, 17, 30)
        optimizer = self.optimizer()
        state = self.state(
            when,
            battery_soc=60.0,
            available_discharge_energy_kwh=18.0,
            battery_power_sensor_kw=0.0,
            current_price=0.30,
            current_price_cents=30.0,
            feedin_price=0.15,
            feedin_price_cents=15.0,
            pv_kw=pv_kw,
            solar_power_now_kw=pv_kw,
            load_kw=1.0,
            current_ems_mode=MODE_MAX_SELF,
            ems_mode_observed=True,
            current_export_limit=0.01,
            demand_window_active=True,
        )

        decision = self.decide(optimizer, state, when)

        self.assert_msc_surplus_permission(
            decision,
            export_ceiling=25.0,
        )

    def test_demand_window_with_little_pv_blocks_only_import(self) -> None:
        self._assert_demand_window_baseline(0.2)

    def test_demand_window_with_strong_pv_blocks_only_import(self) -> None:
        self._assert_demand_window_baseline(5.0)

    def test_import_overlay_policy_remains_independent_of_msc_baseline(self) -> None:
        optimizer = self.optimizer()
        state = self.state(
            self.FIXED_AFTERNOON,
            battery_soc=30.0,
            available_discharge_energy_kwh=9.0,
            current_price=-0.35,
            current_price_cents=-35.0,
            price_is_actual=True,
            feedin_price=0.0,
            feedin_price_cents=0.0,
            pv_kw=0.0,
            solar_power_now_kw=0.0,
            load_kw=1.0,
            forecast_remaining_kwh=0.0,
        )

        decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

        self.assertEqual(MODE_CMD_CHARGE_GRID, decision.ems_mode)
        self.assertEqual(25.0, decision.import_limit)
        self.assertEqual(0.0, decision.export_limit)
        self.assertNotIn(decision.ems_mode, DISCHARGE_MODES)

    def test_value_gate_enforce_setting_is_actuator_neutral_for_msc_baseline(
        self,
    ) -> None:
        advisory_optimizer = self.optimizer(
            export_value_gate_enabled=True,
            export_value_gate_dry_run=True,
            export_value_gate_enforce=False,
        )
        enforced_optimizer = self.optimizer(
            export_value_gate_enabled=True,
            export_value_gate_dry_run=True,
            export_value_gate_enforce=True,
        )
        state = self._ordinary_state(60.0)

        advisory = self.decide(advisory_optimizer, state, self.FIXED_AFTERNOON)
        enforced = self.decide(enforced_optimizer, state, self.FIXED_AFTERNOON)

        self.assertEqual(
            (
                advisory.ems_mode,
                advisory.export_limit,
                advisory.import_limit,
                advisory.pv_max_power_limit,
                advisory.ess_charge_limit,
                advisory.ess_discharge_limit,
                advisory.export_intent,
            ),
            (
                enforced.ems_mode,
                enforced.export_limit,
                enforced.import_limit,
                enforced.pv_max_power_limit,
                enforced.ess_charge_limit,
                enforced.ess_discharge_limit,
                enforced.export_intent,
            ),
        )
        self.assertFalse(
            bool(enforced.trace_gates.get("export_value_gate_enforcement_active"))
        )
        self.assertFalse(bool(enforced.trace_gates.get("export_value_gate_vetoed")))
        self.assert_msc_surplus_permission(
            enforced,
            export_ceiling=enforced_optimizer.cfg.export_limit_high,
        )

    def test_morning_slow_owns_charge_rate_not_export_ceiling_gating(self) -> None:
        when = datetime(2026, 1, 15, 9, 0)
        optimizer = self.optimizer(
            morning_slow_charge_enabled=True,
            morning_slow_charge_rate_kw=2.0,
            morning_slow_export_start_margin_kw=1.0,
        )
        state = self.state(
            when,
            battery_soc=95.0,
            available_discharge_energy_kwh=28.5,
            feedin_price=0.15,
            feedin_price_cents=15.0,
            pv_kw=3.2,
            solar_power_now_kw=3.2,
            load_kw=1.1,
            forecast_remaining_kwh=100.0,
            current_export_limit=0.01,
            grid_export_power_kw=0.0,
        )

        decision = self.decide(optimizer, state, when)

        self.assertTrue(bool(decision.trace_gates.get("morning_slow_charge_active")))
        self.assertLess(
            decision.trace_values.get("pv_surplus_actual"),
            optimizer.cfg.morning_slow_charge_rate_kw
            + optimizer.cfg.morning_slow_export_start_margin_kw,
        )
        self.assert_msc_surplus_permission(
            decision,
            export_ceiling=optimizer.cfg.export_limit_high,
        )
        self.assertEqual(optimizer.cfg.morning_slow_charge_rate_kw, decision.ess_charge_limit)
        self.assertEqual("morning_slow_charge", decision.trace_values.get("export_branch"))
        self.assertEqual("none", decision.trace_values.get("battery_export_owner"))
        self.assertNotEqual(BATTERY_EXPORT, decision.export_intent)

    def _morning_slow_low_soc_decision(
        self,
        pv_surplus_kw: float,
        **state_overrides: object,
    ):
        when = datetime(2026, 1, 15, 9, 0)
        optimizer = self.optimizer(
            morning_slow_charge_enabled=True,
            morning_slow_charge_rate_kw=2.0,
            min_grid_transfer_kw=1.0,
        )
        load_kw = 1.0
        state_values: dict[str, object] = {
            "battery_soc": 14.5,
            "available_discharge_energy_kwh": 4.35,
            "battery_power_sensor_kw": 2.0,
            "feedin_price": 0.15,
            "feedin_price_cents": 15.0,
            "pv_kw": load_kw + pv_surplus_kw,
            "solar_power_now_kw": load_kw + pv_surplus_kw,
            "load_kw": load_kw,
            "forecast_remaining_kwh": 100.0,
            "current_export_limit": 0.01,
            "grid_import_power_kw": 0.0,
            "grid_export_power_kw": 0.0,
        }
        state_values.update(state_overrides)
        state = self.state(when, **state_values)
        return optimizer, self.decide(optimizer, state, when)

    def _assert_morning_slow_low_soc_contract(self, optimizer, decision) -> None:
        self.assertTrue(bool(decision.trace_gates.get("morning_slow_charge_active")))
        self.assert_msc_surplus_permission(
            decision,
            export_ceiling=optimizer.cfg.export_limit_high,
        )
        self.assertEqual(2.0, decision.ess_charge_limit)
        self.assertEqual(optimizer.cfg.pv_max_power_normal, decision.pv_max_power_limit)
        self.assertEqual("none", decision.trace_values.get("battery_export_owner"))
        self.assertNotEqual(BATTERY_EXPORT, decision.export_intent)

    def test_morning_slow_low_soc_below_legacy_three_kw_gate_keeps_msc_ceiling(
        self,
    ) -> None:
        optimizer, decision = self._morning_slow_low_soc_decision(2.9)

        self.assertAlmostEqual(
            2.9,
            decision.trace_values.get("pv_surplus_estimated"),
        )
        self.assertLess(
            decision.trace_values.get("pv_surplus_estimated"),
            optimizer.cfg.morning_slow_charge_rate_kw
            + optimizer.cfg.min_grid_transfer_kw,
        )
        self._assert_morning_slow_low_soc_contract(optimizer, decision)

    def test_morning_slow_low_soc_above_legacy_three_kw_gate_keeps_same_msc_ceiling(
        self,
    ) -> None:
        optimizer, decision = self._morning_slow_low_soc_decision(3.1)

        self.assertAlmostEqual(
            3.1,
            decision.trace_values.get("pv_surplus_estimated"),
        )
        self.assertGreater(
            decision.trace_values.get("pv_surplus_estimated"),
            optimizer.cfg.morning_slow_charge_rate_kw
            + optimizer.cfg.min_grid_transfer_kw,
        )
        self._assert_morning_slow_low_soc_contract(optimizer, decision)

    def test_morning_slow_low_soc_unobserved_automated_remains_blocked(self) -> None:
        _optimizer, decision = self._morning_slow_low_soc_decision(
            3.1,
            sigenergy_mode_observed=False,
        )

        self.assertTrue(
            bool(decision.trace_gates.get("pv_only_branch_high_ceiling_requested"))
        )
        self.assertTrue(
            bool(decision.trace_gates.get("pv_only_branch_automated_ownership_blocked"))
        )
        self.assertEqual(0.0, decision.export_limit)
        self.assertEqual(EXPORT_BLOCKED, decision.export_intent)
        self.assertEqual("none", decision.trace_values.get("battery_export_owner"))
        self.assertNotEqual(BATTERY_EXPORT, decision.export_intent)

    def test_morning_slow_low_soc_simultaneous_or_unknown_flow_remains_blocked(
        self,
    ) -> None:
        cases = (
            (
                "simultaneous_discharge_and_export",
                {
                    "battery_power_sensor_kw": -0.2,
                    "grid_export_power_kw": 1.0,
                },
            ),
            (
                "unknown_flow",
                {
                    "battery_power_sensor_kw": None,
                    "grid_import_power_kw": None,
                    "grid_export_power_kw": None,
                },
            ),
        )

        for name, state_overrides in cases:
            with self.subTest(name=name):
                _optimizer, decision = self._morning_slow_low_soc_decision(
                    3.1,
                    **state_overrides,
                )

                self.assertTrue(
                    bool(decision.trace_gates.get("pv_only_branch_high_ceiling_requested"))
                )
                self.assertTrue(
                    bool(decision.trace_gates.get("pv_only_branch_battery_safety_blocked"))
                )
                self.assertEqual(0.0, decision.export_limit)
                self.assertEqual(EXPORT_BLOCKED, decision.export_intent)
                self.assertEqual("none", decision.trace_values.get("battery_export_owner"))
                self.assertNotEqual(BATTERY_EXPORT, decision.export_intent)

    def test_negative_or_below_minimum_fit_closes_export_without_discharge(self) -> None:
        for fit, fit_cents in ((-0.01, -1.0), (0.009, 0.9)):
            with self.subTest(fit_cents=fit_cents):
                optimizer = self.optimizer()
                state = self._full_opportunity(
                    feedin_price=fit,
                    feedin_price_cents=fit_cents,
                    current_ems_mode=MODE_MAX_SELF,
                    ems_mode_observed=True,
                    current_export_limit=25.0,
                )

                decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

                self.assert_contract_outputs(
                    decision,
                    (MODE_MAX_SELF, 0.0, 0.0, 25.0),
                )

    def test_deliberate_export_contexts_remain_distinct_from_msc_baseline(
        self,
    ) -> None:
        morning_when = datetime(2026, 1, 15, 6, 0)
        morning_detail = [
            {
                "period_start": (morning_when + timedelta(hours=hours)).isoformat(),
                "pv_estimate": 10.0,
            }
            for hours in (3, 5, 7, 9, 11)
        ]
        morning_optimizer = self.optimizer(morning_dump_enabled=True)
        morning_state = self.state(
            morning_when,
            sun_above_horizon=False,
            battery_soc=80.0,
            available_discharge_energy_kwh=24.0,
            feedin_price=0.05,
            feedin_price_cents=5.0,
            load_kw=1.0,
            solcast_detailed=morning_detail,
        )

        evening_when = datetime(2026, 1, 15, 17, 30)
        evening_optimizer = self.optimizer(
            evening_boost_enabled=True,
            evening_boost_min_tomorrow_forecast_kwh=100.0,
        )
        evening_state = self.state(
            evening_when,
            battery_soc=80.0,
            available_discharge_energy_kwh=24.0,
            feedin_price=0.15,
            feedin_price_cents=15.0,
            load_kw=0.0,
            solcast_detailed=[
                {
                    "period_start": datetime(2026, 1, 15, 16, 0).isoformat(),
                    "pv_estimate": 2.0,
                }
            ],
            forecast_tomorrow_kwh=120.0,
        )

        spike_when = datetime(2026, 1, 15, 2, 0)
        spike_optimizer = self.optimizer(export_spike_threshold=0.60)
        spike_state = self.state(
            spike_when,
            sun_above_horizon=False,
            battery_soc=95.0,
            available_discharge_energy_kwh=28.5,
            battery_power_sensor_kw=-0.2,
            feedin_price=0.65,
            feedin_price_cents=65.0,
            price_spike_active=True,
            pv_kw=0.0,
            solar_power_now_kw=0.0,
            load_kw=1.0,
        )

        cases = (
            (
                "morning_dump",
                morning_optimizer,
                morning_state,
                morning_when,
                "morning_dump",
            ),
            (
                "evening_boost",
                evening_optimizer,
                evening_state,
                evening_when,
                "evening_export_boost",
            ),
            (
                "price_spike",
                spike_optimizer,
                spike_state,
                spike_when,
                "export_spike",
            ),
        )
        for name, optimizer, state, when, owner in cases:
            with self.subTest(name=name):
                decision = self.decide(optimizer, state, when)

                self.assertEqual(MODE_CMD_DISCHARGE_PV, decision.ems_mode)
                self.assertGreater(decision.export_limit, 0.01)
                self.assertEqual(BATTERY_EXPORT, decision.export_intent)
                self.assertEqual(
                    owner,
                    decision.trace_values.get("battery_export_owner"),
                )
                self.assertLessEqual(
                    decision.export_limit,
                    optimizer.cfg.export_limit_high,
                )

    def test_exact_full_soc_does_not_override_high_price_battery_export_owner(
        self,
    ) -> None:
        optimizer = self.optimizer()
        state = self._ordinary_state(
            100.0,
            feedin_price=1.10,
            feedin_price_cents=110.0,
            battery_power_sensor_kw=0.0,
            pv_kw=6.0,
            solar_power_now_kw=6.0,
            load_kw=1.0,
        )

        decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

        self.assertTrue(bool(decision.trace_gates.get("topoff_target_met")))
        self.assertFalse(
            bool(decision.trace_gates.get("pv_only_msc_high_ceiling_active"))
        )
        self.assertEqual(
            "high_price_or_spike",
            decision.trace_values.get("desired_export_source"),
        )
        self.assertEqual("high_price", decision.trace_values.get("battery_export_owner"))
        self.assertEqual(BATTERY_EXPORT, decision.export_intent)
        self.assertEqual(MODE_CMD_DISCHARGE_PV, decision.ems_mode)
        self.assertGreater(decision.export_limit, 0.01)

    def test_explicit_positive_fit_battery_discharge_override_remains_deliberate(
        self,
    ) -> None:
        optimizer = self.optimizer(
            allow_low_medium_export_positive_fit=True,
            allow_positive_fit_battery_discharging=True,
        )
        state = self._ordinary_state(
            90.0,
            feedin_price=0.05,
            feedin_price_cents=5.0,
            pv_kw=4.0,
            solar_power_now_kw=4.0,
            load_kw=1.0,
        )

        decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

        self.assertEqual(
            "positive_fit_override",
            decision.trace_values.get("desired_export_source"),
        )
        self.assertEqual(
            "positive_fit_override",
            decision.trace_values.get("battery_export_owner"),
        )
        self.assertTrue(
            bool(
                decision.trace_gates.get(
                    "positive_fit_battery_export_authorized"
                )
            )
        )
        self.assertFalse(
            bool(
                decision.trace_gates.get(
                    "positive_fit_msc_surplus_policy_active"
                )
            )
        )
        self.assertEqual(BATTERY_EXPORT, decision.export_intent)
        self.assertEqual(
            BATTERY_EXPORT,
            decision.trace_values.get("requested_export_intent"),
        )
        self.assertEqual(MODE_CMD_DISCHARGE_PV, decision.ems_mode)
        self.assertEqual(5.0, decision.export_limit)
        self.assertEqual(25.0, decision.ess_discharge_limit)

    def test_positive_fit_policy_without_battery_discharge_uses_verified_msc_ceiling(
        self,
    ) -> None:
        optimizer = self.optimizer(
            allow_low_medium_export_positive_fit=True,
            allow_positive_fit_battery_discharging=False,
        )
        state = self._ordinary_state(
            90.0,
            feedin_price=0.05,
            feedin_price_cents=5.0,
            pv_kw=4.0,
            solar_power_now_kw=4.0,
            load_kw=1.0,
        )

        decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

        self.assertEqual(
            "positive_fit_override",
            decision.trace_values.get("initial_desired_export_source"),
        )
        self.assertEqual(
            "ordinary_msc_surplus_ceiling",
            decision.trace_values.get("desired_export_source"),
        )
        self.assertTrue(bool(decision.trace_gates.get("positive_fit_override")))
        self.assertFalse(
            bool(
                decision.trace_gates.get(
                    "positive_fit_battery_export_authorized"
                )
            )
        )
        self.assertTrue(
            bool(
                decision.trace_gates.get(
                    "positive_fit_msc_surplus_policy_active"
                )
            )
        )
        self.assert_msc_surplus_permission(
            decision,
            export_ceiling=optimizer.cfg.export_limit_high,
        )
        expected_discharge_cap = optimizer.get_power_caps_kw(state)[1]
        self.assertGreater(expected_discharge_cap, 0.01)
        self.assertEqual(expected_discharge_cap, decision.ess_discharge_limit)

    def test_positive_fit_policy_without_battery_discharge_preserves_load_serving_discharge(
        self,
    ) -> None:
        optimizer = self.optimizer(
            allow_low_medium_export_positive_fit=True,
            allow_positive_fit_battery_discharging=False,
        )
        state = self._ordinary_state(
            90.0,
            feedin_price=0.05,
            feedin_price_cents=5.0,
            battery_power_sensor_kw=-1.0,
            grid_export_power_kw=0.2,
        )

        decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

        self.assert_msc_surplus_permission(
            decision,
            export_ceiling=optimizer.cfg.export_limit_high,
        )
        self.assertEqual(
            "load_serving_battery_discharge",
            decision.trace_values.get("ordinary_msc_flow_classification"),
        )
        expected_discharge_cap = optimizer.get_power_caps_kw(state)[1]
        self.assertGreater(expected_discharge_cap, 0.01)
        self.assertEqual(expected_discharge_cap, decision.ess_discharge_limit)

    def test_positive_fit_policy_without_battery_discharge_closes_simultaneous_export_without_clamping_discharge(
        self,
    ) -> None:
        optimizer = self.optimizer(
            allow_low_medium_export_positive_fit=True,
            allow_positive_fit_battery_discharging=False,
        )
        state = self._ordinary_state(
            90.0,
            feedin_price=0.05,
            feedin_price_cents=5.0,
            battery_power_sensor_kw=-1.0,
            grid_export_power_kw=optimizer.cfg.min_grid_transfer_kw,
        )

        decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

        self.assert_contract_outputs(
            decision,
            (MODE_MAX_SELF, 0.0, 0.0, optimizer.cfg.pv_max_power_normal),
        )
        self.assertEqual(EXPORT_BLOCKED, decision.export_intent)
        self.assertEqual("none", decision.trace_values.get("battery_export_owner"))
        self.assertEqual(
            "simultaneous_battery_discharge_and_grid_export",
            decision.trace_values.get("ordinary_msc_flow_classification"),
        )
        expected_discharge_cap = optimizer.get_power_caps_kw(state)[1]
        self.assertGreater(expected_discharge_cap, 0.01)
        self.assertEqual(expected_discharge_cap, decision.ess_discharge_limit)

    def test_positive_fit_policy_without_battery_discharge_fails_closed_when_unverified(
        self,
    ) -> None:
        cases = (
            (
                "automated_unobserved",
                {"sigenergy_mode_observed": False},
            ),
            (
                "msc_unobserved",
                {"ems_mode_observed": False},
            ),
            (
                "battery_flow_unknown",
                {
                    "battery_power_sensor_kw": None,
                    "grid_import_power_kw": None,
                },
            ),
            (
                "grid_export_flow_unknown",
                {"grid_export_power_kw": None},
            ),
        )
        for name, overrides in cases:
            with self.subTest(name=name):
                optimizer = self.optimizer(
                    allow_low_medium_export_positive_fit=True,
                    allow_positive_fit_battery_discharging=False,
                )
                state = self._ordinary_state(
                    90.0,
                    feedin_price=0.05,
                    feedin_price_cents=5.0,
                    pv_kw=4.0,
                    solar_power_now_kw=4.0,
                    load_kw=1.0,
                    **overrides,
                )

                decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

                self.assertEqual(
                    "positive_fit_override",
                    decision.trace_values.get("initial_desired_export_source"),
                )
                self.assert_contract_outputs(
                    decision,
                    (MODE_MAX_SELF, 0.0, 0.0, 25.0),
                )
                self.assertEqual(EXPORT_BLOCKED, decision.export_intent)
                self.assertEqual(
                    EXPORT_BLOCKED,
                    decision.trace_values.get("requested_export_intent"),
                )
                self.assertEqual(
                    "none",
                    decision.trace_values.get("battery_export_owner"),
                )
                self.assertFalse(
                    bool(
                        decision.trace_gates.get(
                            "positive_fit_battery_export_authorized"
                        )
                    )
                )
                self.assertNotIn(decision.ems_mode, DISCHARGE_MODES)
                expected_discharge_cap = optimizer.get_power_caps_kw(state)[1]
                self.assertGreater(expected_discharge_cap, 0.01)
                self.assertEqual(
                    expected_discharge_cap,
                    decision.ess_discharge_limit,
                )

    def test_actual_import_cost_veto_does_not_inherit_positive_fit_discharge_clamp(
        self,
    ) -> None:
        optimizer = self.optimizer(
            allow_low_medium_export_positive_fit=True,
            allow_positive_fit_battery_discharging=False,
        )
        state = self._ordinary_state(
            95.0,
            feedin_price=1.10,
            feedin_price_cents=110.0,
            battery_power_sensor_kw=-0.2,
            pv_kw=0.0,
            solar_power_now_kw=0.0,
            load_kw=1.0,
        )
        original_advisory = optimizer._export_value_gate_advisory

        def import_cost_veto_advisory(*args, **kwargs):
            result = original_advisory(*args, **kwargs)
            result.update(
                {
                    "today_import_topup_kwh": 1.0,
                    "today_highest_actual_import_price": 1.20,
                    "import_cost_export_floor": 1.20,
                    "import_cost_floor_trusted": True,
                    "import_cost_floor_unknown": False,
                }
            )
            return result

        optimizer._export_value_gate_advisory = import_cost_veto_advisory

        decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

        self.assertTrue(bool(decision.trace_gates.get("positive_fit_override")))
        self.assertTrue(
            bool(decision.trace_gates.get("actual_import_cost_guard_blocking"))
        )
        self.assertEqual("high_price", decision.trace_values.get("battery_export_owner"))
        self.assert_contract_outputs(
            decision,
            (MODE_MAX_SELF, 0.0, 0.0, optimizer.cfg.pv_max_power_normal),
        )
        self.assertEqual(EXPORT_BLOCKED, decision.export_intent)
        expected_discharge_cap = optimizer.get_power_caps_kw(state)[1]
        self.assertGreater(expected_discharge_cap, 0.01)
        self.assertEqual(expected_discharge_cap, decision.ess_discharge_limit)

    def test_other_deliberate_export_owners_ignore_disabled_positive_fit_discharge(
        self,
    ) -> None:
        morning_when = datetime(2026, 1, 15, 6, 0)
        morning_optimizer = self.optimizer(
            morning_dump_enabled=True,
            allow_low_medium_export_positive_fit=True,
            allow_positive_fit_battery_discharging=False,
        )
        morning_state = self.state(
            morning_when,
            sun_above_horizon=False,
            battery_soc=80.0,
            available_discharge_energy_kwh=24.0,
            feedin_price=0.05,
            feedin_price_cents=5.0,
            load_kw=1.0,
            solcast_detailed=[
                {
                    "period_start": (morning_when + timedelta(hours=hours)).isoformat(),
                    "pv_estimate": 10.0,
                }
                for hours in (3, 5, 7, 9, 11)
            ],
        )

        high_price_optimizer = self.optimizer(
            allow_low_medium_export_positive_fit=True,
            allow_positive_fit_battery_discharging=False,
        )
        high_price_state = self._ordinary_state(
            95.0,
            feedin_price=1.10,
            feedin_price_cents=110.0,
            battery_power_sensor_kw=-0.2,
            pv_kw=0.0,
            solar_power_now_kw=0.0,
            load_kw=1.0,
        )

        spike_when = datetime(2026, 1, 15, 2, 0)
        spike_optimizer = self.optimizer(
            export_spike_threshold=0.60,
            allow_low_medium_export_positive_fit=True,
            allow_positive_fit_battery_discharging=False,
        )
        spike_state = self.state(
            spike_when,
            sun_above_horizon=False,
            battery_soc=95.0,
            available_discharge_energy_kwh=28.5,
            battery_power_sensor_kw=-0.2,
            feedin_price=0.65,
            feedin_price_cents=65.0,
            price_spike_active=True,
            pv_kw=0.0,
            solar_power_now_kw=0.0,
            load_kw=1.0,
        )

        cases = (
            (
                "morning_dump",
                morning_optimizer,
                morning_state,
                morning_when,
                "morning_dump",
            ),
            (
                "high_price",
                high_price_optimizer,
                high_price_state,
                self.FIXED_AFTERNOON,
                "high_price",
            ),
            (
                "export_spike",
                spike_optimizer,
                spike_state,
                spike_when,
                "export_spike",
            ),
        )
        for name, optimizer, state, when, expected_owner in cases:
            with self.subTest(owner=name):
                decision = self.decide(optimizer, state, when)

                self.assertTrue(bool(decision.trace_gates.get("positive_fit_override")))
                self.assertFalse(
                    bool(
                        decision.trace_gates.get(
                            "positive_fit_battery_export_authorized"
                        )
                    )
                )
                self.assertEqual(expected_owner, decision.trace_values.get("battery_export_owner"))
                self.assertEqual(BATTERY_EXPORT, decision.export_intent)
                self.assertEqual(MODE_CMD_DISCHARGE_PV, decision.ems_mode)
                self.assertGreater(decision.export_limit, 0.01)
                expected_discharge_cap = optimizer.get_power_caps_kw(state)[1]
                self.assertGreater(expected_discharge_cap, 0.01)
                self.assertEqual(
                    expected_discharge_cap,
                    decision.ess_discharge_limit,
                )

    def test_morning_slow_positive_fit_overlap_allows_load_serving_discharge(
        self,
    ) -> None:
        when = datetime(2026, 1, 15, 9, 0)
        optimizer = self.optimizer(
            morning_slow_charge_enabled=True,
            morning_slow_charge_rate_kw=2.0,
            min_grid_transfer_kw=1.0,
            allow_low_medium_export_positive_fit=True,
            allow_positive_fit_battery_discharging=False,
        )
        state = self.state(
            when,
            battery_soc=14.5,
            available_discharge_energy_kwh=4.35,
            battery_power_sensor_kw=-0.2,
            feedin_price=0.15,
            feedin_price_cents=15.0,
            pv_kw=4.1,
            solar_power_now_kw=4.1,
            load_kw=1.0,
            forecast_remaining_kwh=100.0,
            current_export_limit=0.01,
            grid_import_power_kw=0.0,
            grid_export_power_kw=0.0,
        )

        decision = self.decide(optimizer, state, when)

        self.assertTrue(bool(decision.trace_gates.get("morning_slow_charge_active")))
        self.assertFalse(
            bool(decision.trace_gates.get("pv_only_branch_battery_safety_blocked"))
        )
        self.assertEqual(
            "load_serving_battery_discharge",
            decision.trace_values.get("ordinary_msc_flow_classification"),
        )
        self.assert_msc_surplus_permission(
            decision,
            export_ceiling=optimizer.cfg.export_limit_high,
        )
        self.assertEqual(optimizer.cfg.morning_slow_charge_rate_kw, decision.ess_charge_limit)
        self.assertEqual("none", decision.trace_values.get("battery_export_owner"))
        self.assertNotEqual(BATTERY_EXPORT, decision.export_intent)

    def test_positive_fit_battery_export_enabled_retains_low_soc_export_guard(
        self,
    ) -> None:
        optimizer = self.optimizer(
            allow_low_medium_export_positive_fit=True,
            allow_positive_fit_battery_discharging=True,
        )
        state = self._ordinary_state(
            89.0,
            feedin_price=0.05,
            feedin_price_cents=5.0,
        )

        decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

        self.assertTrue(
            bool(
                decision.trace_gates.get(
                    "positive_fit_battery_export_authorized"
                )
            )
        )
        self.assert_contract_outputs(
            decision,
            (MODE_MAX_SELF, 0.0, 0.0, optimizer.cfg.pv_max_power_normal),
        )
        self.assertEqual(EXPORT_BLOCKED, decision.export_intent)
        self.assertEqual("none", decision.trace_values.get("battery_export_owner"))


if __name__ == "__main__":
    unittest.main()
