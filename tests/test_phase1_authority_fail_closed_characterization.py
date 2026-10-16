from __future__ import annotations

import asyncio
import unittest
from datetime import datetime, timedelta, timezone

import pytest

from app.models import Decision, SolarState
from app.optimizer import (
    DISCHARGE_MODES,
    MODE_CMD_CHARGE_GRID,
    MODE_CMD_CHARGE_PV,
    MODE_CMD_DISCHARGE_PV,
    MODE_MAX_SELF,
)
from haos49_characterization_helpers import (
    Haos49CharacterizationCase,
    RecordingHA,
)
from test_control_authority_safety_characterization import _Rig


@pytest.fixture
def authority_rig():
    rig = _Rig()
    try:
        yield rig
    finally:
        rig.case.tearDown()


def test_contradictory_export_metadata_cannot_settle_discharge_target(authority_rig):
    rig = authority_rig
    rig.automated()
    cfg = rig.opt.cfg
    rig.ha.observe(cfg.grid_export_limit, 25.0)

    async def contradictory_report(ha, method, entity, value):
        if entity == cfg.grid_export_limit and value == 5.0:
            rig.clock.advance()
            ha.observe(entity, 5.0)  # Later REST snapshot appears to settle.
            rig.clock.advance()
            ha.metadata[entity].update(
                state="25.0", last_updated=rig.clock.now.isoformat(),
                last_reported=rig.clock.now.isoformat(),
            )

    rig.ha.on_write = contradictory_report
    state = rig.state(current_export_limit=25.0, demand_window_active=True)
    decision = rig.discharge()
    decision.ess_charge_limit = 0.01
    decision.ess_discharge_limit = 0.01
    result = rig.apply(state, decision)

    assert ("set_number", cfg.grid_export_limit, 5.0) in rig.ha.calls
    assert not any(method == "select_option" and value in DISCHARGE_MODES
                   for method, entity, value in rig.ha.calls if entity == cfg.ems_mode_select)
    assert not result.succeeded
    assert result.fallback_attempted
    for entity in (cfg.grid_import_limit, cfg.ess_max_charging_limit,
                   cfg.ess_max_discharging_limit):
        assert ("set_number", entity, 0.01) in rig.ha.calls


def _pending_force_reports(rig, evidence="unchanged", *, settle_ems=True):
    cfg = rig.opt.cfg
    rig.opt.cfg.ess_limit_fallback_kw = 25.0
    rig.automated()
    original_change = rig.clock.now
    for rows in (rig.ha.reports, rig.ha.metadata):
        rows[cfg.sigenergy_mode_select]["last_changed"] = original_change.isoformat()
    rig.read()
    rig.clock.advance()

    async def report(ha, method, entity, value):
        rig.clock.advance()
        if entity == cfg.sigenergy_mode_select:
            if evidence in {"Manual", "Automated"}:
                # The Force selection really occurs before a newer external
                # transition, including a genuine handback to Automated.
                ha.observe(entity, value)
                rig.clock.advance()
                ha.observe(entity, evidence)
                changed = rig.clock.now.isoformat()
            else:
                ha.observe(entity, "unavailable" if evidence == "unavailable" else cfg.automated_option,
                           updated=original_change if evidence == "unchanged" else rig.clock.now)
                changed = original_change.isoformat()
                if evidence == "malformed_change":
                    changed = "not-a-timestamp"
                elif evidence == "future_change":
                    changed = (rig.clock.now + timedelta(seconds=1)).isoformat()
                elif evidence == "equal_request":
                    changed = datetime.fromtimestamp(rig.opt._manual_mode_requested_at
                                                     or rig.clock.now.timestamp() - 1,
                                                     timezone.utc).isoformat()
            for rows in (ha.reports, ha.metadata):
                if evidence != "missing_change":
                    rows[entity]["last_changed"] = changed
            if evidence == "metadata_conflict":
                ha.metadata[entity]["state"] = cfg.manual_option
        elif entity != cfg.ems_mode_select or settle_ems:
            ha.observe(entity, value)

    rig.ha.on_write = report


@pytest.mark.parametrize("mode,ems,export_kw,import_kw", [
    ("Force Full Export", MODE_CMD_DISCHARGE_PV, 25.0, 0.01),
    ("Force Full Import", MODE_CMD_CHARGE_GRID, 0.01, 25.0),
    ("Force Full Import + PV", MODE_CMD_CHARGE_PV, 0.01, 25.0),
    ("Prevent Import & Export", MODE_MAX_SELF, 0.01, 0.01),
])
def test_unchanged_automated_report_preserves_pending_force_targets(
    authority_rig, mode, ems, export_kw, import_kw,
):
    rig = authority_rig
    _pending_force_reports(rig)
    cfg = rig.opt.cfg
    rig.clock.run(rig.opt.apply_manual_mode(mode))
    assert rig.opt._manual_mode_override == mode
    assert ("select_option", cfg.ems_mode_select, ems) in rig.ha.calls
    for entity, value in ((cfg.grid_export_limit, export_kw), (cfg.grid_import_limit, import_kw),
                          (cfg.pv_max_power_limit, cfg.pv_max_power_value),
                          (cfg.ess_max_charging_limit, 25.0), (cfg.ess_max_discharging_limit, 25.0)):
        assert ("set_number", entity, value) in rig.ha.calls


@pytest.mark.parametrize("selection", ["Manual", "Automated"])
def test_verified_newer_selector_transition_supersedes_force_visibly(authority_rig, selection):
    rig = authority_rig
    _pending_force_reports(rig, selection)
    with pytest.raises(RuntimeError, match="superseded"):
        rig.clock.run(rig.opt.apply_manual_mode(rig.opt.cfg.full_export_option))
    assert rig.opt._manual_mode_override is None
    assert rig.writes() == []


@pytest.mark.parametrize("evidence", [
    "attribute_update", "missing_change", "malformed_change", "future_change",
    "equal_request", "metadata_conflict", "unavailable",
])
def test_ambiguous_selector_evidence_keeps_force_and_blocks_stale_auto(authority_rig, evidence):
    rig = authority_rig
    _pending_force_reports(rig, evidence)
    pending_auto = rig.state(current_export_limit=25.0)
    rig.clock.run(rig.opt.apply_manual_mode(rig.opt.cfg.full_export_option))
    assert rig.opt._manual_mode_override == rig.opt.cfg.full_export_option
    assert ("select_option", rig.opt.cfg.ems_mode_select, MODE_CMD_DISCHARGE_PV) in rig.ha.calls
    boundary = len(rig.ha.calls)
    result = rig.apply(pending_auto, rig.discharge())
    assert not result.succeeded
    assert rig.ha.calls[boundary:] == []


def test_pending_force_unsettled_ems_failure_is_visible(authority_rig):
    rig = authority_rig
    _pending_force_reports(rig, settle_ems=False)
    with pytest.raises(RuntimeError, match="target writes failed.*ems_mode"):
        rig.clock.run(rig.opt.apply_manual_mode(rig.opt.cfg.full_export_option))
    assert rig.opt._manual_mode_override == rig.opt.cfg.full_export_option


@pytest.mark.parametrize("newer", ["Automated", "Manual", "Force Full Import"])
def test_newer_authenticated_request_supersedes_prior_force(authority_rig, newer):
    rig = authority_rig
    _pending_force_reports(rig)
    rig.clock.run(rig.opt.apply_manual_mode(rig.opt.cfg.full_export_option))
    rig.clock.run(rig.opt.apply_manual_mode(newer))
    assert rig.opt._manual_mode_override == (None if newer == "Automated" else newer)


class Phase1AuthorityFailClosedCharacterizationTests(Haos49CharacterizationCase):
    def _read_operator_mode(
        self,
        optimizer,
        ha: RecordingHA,
        raw_state: str | None,
        *,
        last_mode: str | None = None,
    ) -> tuple[str, bool]:
        if last_mode is not None:
            optimizer._last_state = SolarState(sigenergy_mode=last_mode)
        ha.states = {}
        if raw_state is not None:
            ha.states[optimizer.cfg.sigenergy_mode_select] = {
                "state": raw_state,
                "attributes": {},
            }
        parsed = asyncio.run(optimizer._read_state())
        return parsed.sigenergy_mode, parsed.sigenergy_mode_observed

    def _read_demand_window(
        self,
        optimizer,
        ha: RecordingHA,
        raw_state: str | None,
    ) -> tuple[bool, bool]:
        ha.states = {}
        if raw_state is not None:
            observed_at = datetime.fromtimestamp(
                self.FIXED_AFTERNOON.timestamp(),
                timezone.utc,
            ).isoformat()
            ha.states[optimizer.cfg.demand_window_sensor] = {
                "state": raw_state,
                "attributes": {},
                "last_updated": observed_at,
                "last_reported": observed_at,
            }
        with self.optimizer_time(self.FIXED_AFTERNOON):
            state = asyncio.run(optimizer._read_state())
        return state.demand_window_active, state.demand_window_observed

    @staticmethod
    def _automatic_actuator_calls(optimizer, calls):
        cfg = optimizer.cfg
        number_entities = {
            cfg.grid_export_limit,
            cfg.grid_import_limit,
            cfg.ess_max_charging_limit,
            cfg.ess_max_discharging_limit,
            cfg.pv_max_power_limit,
        }
        return [
            call
            for call in calls
            if (
                call[0] == "select_option"
                and call[1] == cfg.ems_mode_select
            )
            or (
                call[0] == "set_number"
                and call[1] in number_entities
            )
        ]

    @staticmethod
    def _permissive_import_calls(optimizer, calls):
        cfg = optimizer.cfg
        return [
            call
            for call in calls
            if (
                call[0] == "select_option"
                and call[1] == cfg.ems_mode_select
                and call[2] == MODE_CMD_CHARGE_GRID
            )
            or (
                call[0] == "set_number"
                and call[1] == cfg.grid_import_limit
                and float(call[2]) > 0.011
            )
        ]

    @staticmethod
    def _permissive_export_calls(optimizer, calls):
        cfg = optimizer.cfg
        return [
            call
            for call in calls
            if (
                call[0] == "select_option"
                and call[1] == cfg.ems_mode_select
                and call[2] in DISCHARGE_MODES
            )
            or (
                call[0] == "set_number"
                and call[1] == cfg.grid_export_limit
                and float(call[2]) > 0.011
            )
        ]

    def _negative_import_state(self, mode: str, observed: bool):
        return self.state(
            self.FIXED_AFTERNOON,
            sigenergy_mode=mode,
            sigenergy_mode_observed=observed,
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

    def _high_price_export_state(self, mode: str, observed: bool):
        return self.state(
            self.FIXED_AFTERNOON,
            sigenergy_mode=mode,
            sigenergy_mode_observed=observed,
            battery_soc=95.0,
            available_discharge_energy_kwh=28.5,
            battery_power_sensor_kw=-0.2,
            current_price=0.30,
            current_price_cents=30.0,
            price_is_actual=True,
            feedin_price=1.0,
            feedin_price_cents=100.0,
            pv_kw=0.0,
            solar_power_now_kw=0.0,
            load_kw=1.0,
            forecast_remaining_kwh=100.0,
            ess_max_discharge_kw=1.4,
        )

    def test_cold_unobserved_operator_mode_cannot_open_import_or_select_grid_first(self) -> None:
        for raw_state in (None, "unavailable"):
            with self.subTest(raw_state=raw_state):
                ha = RecordingHA()
                optimizer = self.optimizer(ha)
                mode, observed = self._read_operator_mode(optimizer, ha, raw_state)
                state = self._negative_import_state(mode, observed)
                decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

                self.assertEqual(optimizer.cfg.automated_option, mode)
                self.assertFalse(observed)
                asyncio.run(optimizer._apply(state, decision))

                self.assertEqual(
                    [],
                    self._permissive_import_calls(optimizer, ha.calls),
                    "unobserved operator ownership must not authorize import opening or Grid First",
                )

    def test_cold_unobserved_operator_mode_cannot_authorize_high_price_battery_export(self) -> None:
        for raw_state in (None, "unavailable"):
            with self.subTest(raw_state=raw_state):
                ha = RecordingHA()
                optimizer = self.optimizer(ha)
                mode, observed = self._read_operator_mode(optimizer, ha, raw_state)
                state = self._high_price_export_state(mode, observed)
                decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

                self.assertEqual("high_price", decision.trace_values["battery_export_owner"])
                self.assertFalse(observed)
                asyncio.run(optimizer._apply(state, decision))

                self.assertEqual(
                    [],
                    self._permissive_export_calls(optimizer, ha.calls),
                    "unobserved operator ownership must not authorize export opening or discharge EMS",
                )

    def test_last_known_automated_then_unavailable_cannot_retain_permissive_authority(self) -> None:
        cases = (
            ("negative_import", self._negative_import_state, self._permissive_import_calls),
            ("high_price_export", self._high_price_export_state, self._permissive_export_calls),
        )
        for name, state_factory, forbidden_calls in cases:
            with self.subTest(path=name):
                ha = RecordingHA()
                optimizer = self.optimizer(ha)
                mode, observed = self._read_operator_mode(
                    optimizer,
                    ha,
                    "unavailable",
                    last_mode=optimizer.cfg.automated_option,
                )
                state = state_factory(mode, observed)
                decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

                self.assertEqual(optimizer.cfg.automated_option, mode)
                self.assertFalse(observed)
                asyncio.run(optimizer._apply(state, decision))

                self.assertEqual(
                    [],
                    forbidden_calls(optimizer, ha.calls),
                    "cached Automated text is not observed operator authority",
                )

    def test_warm_cached_manual_and_force_modes_remain_user_owned_when_selector_is_unavailable(self) -> None:
        for mode_kind in ("manual", "force"):
            with self.subTest(mode_kind=mode_kind):
                ha = RecordingHA()
                optimizer = self.optimizer(ha)
                expected_mode = (
                    optimizer.cfg.manual_option
                    if mode_kind == "manual"
                    else optimizer.cfg.full_export_option
                )
                mode, observed = self._read_operator_mode(
                    optimizer,
                    ha,
                    "unavailable",
                    last_mode=expected_mode,
                )
                state = self.state(
                    self.FIXED_AFTERNOON,
                    sigenergy_mode=mode,
                    sigenergy_mode_observed=observed,
                )
                if mode_kind == "force":
                    targets = optimizer._manual_mode_targets(mode, state)
                    assert targets is not None
                    state.current_ems_mode = str(targets["ems_mode"])
                    state.current_export_limit = float(targets["grid_export_limit"])
                    state.current_import_limit = float(targets["grid_import_limit"])
                    state.current_pv_max_power_limit = float(targets["pv_max_power_limit"])
                    state.current_ess_charge_limit = float(targets["ess_charge_limit"])
                    state.current_ess_discharge_limit = float(targets["ess_discharge_limit"])

                decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)
                optimizer._freeze_decision_to_live_mode(state, decision, mode)
                asyncio.run(optimizer._apply(state, decision))

                self.assertEqual(expected_mode, mode)
                self.assertFalse(observed)
                self.assertEqual([], ha.calls)

    def test_demand_window_unknown_states_fail_closed_for_all_qualifying_import_prices(self) -> None:
        price_cases = (
            ("trusted_negative", -0.35),
            ("exact_zero", 0.0),
            ("cheap_positive_topup", 0.01),
        )
        demand_cases = (
            ("observed_on", "on", True),
            ("observed_off", "off", False),
            ("unavailable", "unavailable", True),
            ("unknown", "unknown", True),
            ("missing", None, True),
        )
        for price_name, price in price_cases:
            for demand_name, raw_demand, must_block in demand_cases:
                with self.subTest(price=price_name, demand=demand_name):
                    ha = RecordingHA()
                    optimizer = self.optimizer(ha)
                    parsed_active, parsed_observed = self._read_demand_window(
                        optimizer,
                        ha,
                        raw_demand,
                    )
                    state = self.state(
                        self.FIXED_AFTERNOON,
                        demand_window_active=parsed_active,
                        demand_window_observed=parsed_observed,
                        battery_soc=30.0,
                        available_discharge_energy_kwh=9.0,
                        current_price=price,
                        current_price_cents=price * 100.0,
                        price_is_actual=True,
                        feedin_price=0.0,
                        feedin_price_cents=0.0,
                        pv_kw=0.0,
                        solar_power_now_kw=0.0,
                        load_kw=1.0,
                        forecast_remaining_kwh=0.0,
                    )

                    decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

                    if must_block:
                        self.assertEqual(
                            0.0,
                            decision.import_limit,
                            "Demand Window uncertainty must retain import blocking",
                        )
                    else:
                        self.assertGreater(
                            decision.import_limit,
                            0.011,
                            "an observed OFF Demand Window may permit ordinary import policy",
                        )

    def test_successful_ha_control_request_does_not_grant_same_cycle_actuator_authority(self) -> None:
        ha = RecordingHA(settle_switch=False, turn_on_result=True)
        optimizer = self.optimizer(ha)
        ha._record_state_value(optimizer.cfg.sigenergy_mode_select, optimizer.cfg.automated_option)
        ha._record_state_value(optimizer.cfg.ha_control_switch, "off")

        cycle_1_state = self._negative_import_state(
            optimizer.cfg.automated_option,
            True,
        )
        cycle_1_state.ha_control_enabled = False
        cycle_1_state.ha_control_switch_available = True
        cycle_1_state.ha_control_switch_state = "off"
        cycle_1_decision = self.decide(optimizer, cycle_1_state, self.FIXED_AFTERNOON)
        self.assertTrue(cycle_1_decision.needs_ha_control_switch)
        asyncio.run(optimizer._apply(cycle_1_state, cycle_1_decision))
        cycle_1_calls = list(ha.calls)

        ha.calls.clear()
        # The second cycle receives an actual current ON report, independently
        # of turn_on's successful return in the first cycle.
        ha._record_state_value(optimizer.cfg.ha_control_switch, "on")
        cycle_2_state = self._negative_import_state(
            optimizer.cfg.automated_option,
            True,
        )
        cycle_2_state.ha_control_enabled = True
        cycle_2_state.ha_control_switch_available = True
        cycle_2_state.ha_control_switch_state = "on"
        cycle_2_decision = self.decide(optimizer, cycle_2_state, self.FIXED_AFTERNOON)
        asyncio.run(optimizer._apply(cycle_2_state, cycle_2_decision))
        cycle_2_calls = list(ha.calls)

        self.assertIn(
            ("turn_on", optimizer.cfg.ha_control_switch, True),
            cycle_1_calls,
        )
        self.assertEqual(
            [],
            self._automatic_actuator_calls(optimizer, cycle_1_calls),
            "service success is not observed HA-control authority",
        )
        self.assertFalse(any(call[0] == "turn_on" for call in cycle_2_calls))
        self.assertIn(
            ("select_option", optimizer.cfg.ems_mode_select, MODE_CMD_CHARGE_GRID),
            cycle_2_calls,
        )
        self.assertIn(
            ("set_number", optimizer.cfg.grid_import_limit, 25.0),
            cycle_2_calls,
        )

    def _read_unknown_grid_limit(self, optimizer, ha, entity_id, raw_state):
        ha.states = {}
        if raw_state is not None:
            ha.states[entity_id] = {
                "state": raw_state,
                "attributes": {},
            }
        parsed = asyncio.run(optimizer._read_state())
        # These tests isolate grid-position trust under verified ownership.
        ha._record_state_value(optimizer.cfg.sigenergy_mode_select, optimizer.cfg.automated_option)
        ha._record_state_value(optimizer.cfg.ha_control_switch, "on")
        return parsed

    def _closed_decision(self) -> Decision:
        return Decision(
            ems_mode=MODE_MAX_SELF,
            export_limit=0.0,
            import_limit=0.0,
            pv_max_power_limit=25.0,
            ess_charge_limit=25.0,
            ess_discharge_limit=25.0,
        )

    def test_unknown_current_export_limit_does_not_suppress_safety_close_request(self) -> None:
        unknown_states = (None, "unavailable", "unknown", "nan")
        for raw_state in unknown_states:
            with self.subTest(raw_state=raw_state):
                ha = RecordingHA()
                optimizer = self.optimizer(
                    ha,
                    ess_max_charging_limit="",
                    ess_max_discharging_limit="",
                )
                parsed = self._read_unknown_grid_limit(
                    optimizer,
                    ha,
                    optimizer.cfg.grid_export_limit,
                    raw_state,
                )
                state = self.state(
                    self.FIXED_AFTERNOON,
                    current_export_limit=parsed.current_export_limit,
                    current_export_limit_observed=parsed.current_export_limit_observed,
                    current_import_limit=0.01,
                    ha_control_enabled=True,
                    ha_control_switch_available=True,
                    ha_control_switch_state="on",
                )

                asyncio.run(optimizer._apply(state, self._closed_decision()))

                self.assertEqual(0.0, parsed.current_export_limit)
                self.assertFalse(parsed.current_export_limit_observed)
                self.assertIn(
                    ("set_number", optimizer.cfg.grid_export_limit, 0.01),
                    ha.calls,
                    "an unknown export reading cannot prove the actuator is already closed",
                )

    def test_unknown_current_import_limit_does_not_suppress_safety_close_request(self) -> None:
        unknown_states = (None, "unavailable", "unknown", "nan")
        for raw_state in unknown_states:
            with self.subTest(raw_state=raw_state):
                ha = RecordingHA()
                optimizer = self.optimizer(
                    ha,
                    ess_max_charging_limit="",
                    ess_max_discharging_limit="",
                )
                parsed = self._read_unknown_grid_limit(
                    optimizer,
                    ha,
                    optimizer.cfg.grid_import_limit,
                    raw_state,
                )
                state = self.state(
                    self.FIXED_AFTERNOON,
                    current_export_limit=0.01,
                    current_import_limit=parsed.current_import_limit,
                    current_import_limit_observed=parsed.current_import_limit_observed,
                    ha_control_enabled=True,
                    ha_control_switch_available=True,
                    ha_control_switch_state="on",
                )

                asyncio.run(optimizer._apply(state, self._closed_decision()))

                self.assertEqual(0.0, parsed.current_import_limit)
                self.assertFalse(parsed.current_import_limit_observed)
                self.assertIn(
                    ("set_number", optimizer.cfg.grid_import_limit, 0.01),
                    ha.calls,
                    "an unknown import reading cannot prove the actuator is already closed",
                )

    def test_unknown_current_export_limit_does_not_authorize_permissive_open(self) -> None:
        unknown_states = (None, "unavailable", "unknown", "nan")
        for raw_state in unknown_states:
            with self.subTest(raw_state=raw_state):
                ha = RecordingHA()
                optimizer = self.optimizer(
                    ha,
                    ess_max_charging_limit="",
                    ess_max_discharging_limit="",
                )
                parsed = self._read_unknown_grid_limit(
                    optimizer,
                    ha,
                    optimizer.cfg.grid_export_limit,
                    raw_state,
                )
                state = self.state(
                    self.FIXED_AFTERNOON,
                    current_export_limit=parsed.current_export_limit,
                    current_export_limit_observed=parsed.current_export_limit_observed,
                    current_import_limit=0.01,
                    ha_control_enabled=True,
                    ha_control_switch_available=True,
                    ha_control_switch_state="on",
                )
                decision = Decision(
                    ems_mode=MODE_MAX_SELF,
                    export_limit=25.0,
                    import_limit=0.0,
                    pv_max_power_limit=25.0,
                    ess_charge_limit=25.0,
                    ess_discharge_limit=25.0,
                )

                self.assertTrue(state.sigenergy_mode_observed)
                self.assertTrue(state.ha_control_enabled)
                self.assertFalse(parsed.current_export_limit_observed)
                asyncio.run(optimizer._apply(state, decision))

                permissive_export_calls = [
                    call
                    for call in ha.calls
                    if call[0] == "set_number"
                    and call[1] == optimizer.cfg.grid_export_limit
                    and float(call[2]) > 0.011
                ]
                self.assertEqual(
                    [],
                    permissive_export_calls,
                    "unknown export telemetry cannot itself authorize opening export",
                )

    def test_unknown_current_import_limit_does_not_authorize_permissive_open(self) -> None:
        unknown_states = (None, "unavailable", "unknown", "nan")
        for raw_state in unknown_states:
            with self.subTest(raw_state=raw_state):
                ha = RecordingHA()
                optimizer = self.optimizer(
                    ha,
                    ess_max_charging_limit="",
                    ess_max_discharging_limit="",
                )
                parsed = self._read_unknown_grid_limit(
                    optimizer,
                    ha,
                    optimizer.cfg.grid_import_limit,
                    raw_state,
                )
                state = self.state(
                    self.FIXED_AFTERNOON,
                    current_export_limit=0.01,
                    current_import_limit=parsed.current_import_limit,
                    current_import_limit_observed=parsed.current_import_limit_observed,
                    ha_control_enabled=True,
                    ha_control_switch_available=True,
                    ha_control_switch_state="on",
                )
                decision = Decision(
                    ems_mode=MODE_MAX_SELF,
                    export_limit=0.0,
                    import_limit=25.0,
                    pv_max_power_limit=25.0,
                    ess_charge_limit=25.0,
                    ess_discharge_limit=25.0,
                )

                self.assertTrue(state.sigenergy_mode_observed)
                self.assertTrue(state.ha_control_enabled)
                self.assertFalse(parsed.current_import_limit_observed)
                asyncio.run(optimizer._apply(state, decision))

                permissive_import_calls = [
                    call
                    for call in ha.calls
                    if call[0] == "set_number"
                    and call[1] == optimizer.cfg.grid_import_limit
                    and float(call[2]) > 0.011
                ]
                self.assertEqual(
                    [],
                    permissive_import_calls,
                    "unknown import telemetry cannot itself authorize opening import",
                )

    def test_trusted_finite_grid_limits_retain_normal_deadband(self) -> None:
        ha = RecordingHA()
        optimizer = self.optimizer(
            ha,
            ess_max_charging_limit="",
            ess_max_discharging_limit="",
        )
        state = self.state(
            self.FIXED_AFTERNOON,
            current_export_limit=10.0,
            current_import_limit=10.0,
            current_export_limit_observed=True,
            current_import_limit_observed=True,
            ha_control_enabled=True,
            ha_control_switch_available=True,
            ha_control_switch_state="on",
        )
        decision = Decision(
            ems_mode=MODE_MAX_SELF,
            export_limit=10.05,
            import_limit=10.05,
            pv_max_power_limit=25.0,
            ess_charge_limit=25.0,
            ess_discharge_limit=25.0,
        )

        asyncio.run(optimizer._apply(state, decision))

        grid_limit_calls = [
            call
            for call in ha.calls
            if call[0] == "set_number"
            and call[1]
            in {
                optimizer.cfg.grid_export_limit,
                optimizer.cfg.grid_import_limit,
            }
        ]
        self.assertEqual([], grid_limit_calls)


if __name__ == "__main__":
    unittest.main()
