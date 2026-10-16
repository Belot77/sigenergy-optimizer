"""Stage A safety regressions against the committed production implementation.

Failures are intentional evidence of the documented defects, never xfail/skip.
HA reports are supplied independently: accepting a command changes no readback.
Only this module's clock/doubles are altered; shared fixtures remain read-only.
"""
from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.ha_client import HAClient
from app.models import BATTERY_EXPORT, MSC_SURPLUS_CEILING, Decision
from app.optimizer import DISCHARGE_MODES, MODE_CMD_DISCHARGE_PV, MODE_MAX_SELF
from app.routers.api import ESSRequest, set_ess
from haos49_characterization_helpers import Haos49CharacterizationCase, RecordingHA


class _Clock:
    def __init__(self):
        self.now = datetime(2026, 1, 15, 14, 0, tzinfo=timezone.utc)
        self.elapsed = 0.0

    def advance(self, seconds=1.0):
        self.now += timedelta(seconds=seconds)
        self.elapsed += seconds

    def run(self, awaitable):
        clock = self
        original_sleep = asyncio.sleep

        class ClockDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return clock.now.astimezone(tz) if tz else clock.now.replace(tzinfo=None)

        async def sleep(seconds):
            clock.advance(seconds)
            await original_sleep(0)

        async def run():
            with (
                patch("app.optimizer.datetime", ClockDateTime),
                patch("app.optimizer.asyncio.sleep", sleep),
                patch("app.optimizer.asyncio.get_running_loop",
                      return_value=SimpleNamespace(time=lambda: clock.elapsed)),
            ):
                return await awaitable

        return asyncio.run(run())


class _ObservedHA(RecordingHA):
    """Empty by default; tests must explicitly supply ownership and telemetry."""

    def __init__(self, clock):
        super().__init__(settle_numbers=False, settle_selects=False)
        self.clock = clock
        self.reports = {}
        self.metadata = {}
        self.timeline = []
        self.outcomes = {}
        self.on_read = None
        self.on_metadata = None
        self.on_write = None
        self.metadata_error = None

    def observe(self, entity, value, *, at=None, updated=None):
        at = at or self.clock.now
        row = {
            "entity_id": entity, "state": str(value), "attributes": {},
            "last_updated": (updated or at).isoformat(),
            "last_reported": at.isoformat(),
        }
        self.reports[entity] = row
        self.metadata[entity] = deepcopy(row)

    async def bulk_states(self, entities):
        self.timeline.append(("bulk", tuple(entities), None, self.clock.now.timestamp()))
        self.bulk_state_calls.append(list(entities))
        if self.on_read:
            await self.on_read(self, entities)
        return {entity: deepcopy(self.reports[entity]) for entity in entities
                if entity in self.reports}

    async def get_state_report_metadata(self, entities):
        self.timeline.append(("metadata", tuple(entities), None, self.clock.now.timestamp()))
        self.report_metadata_calls.append(list(entities))
        if self.on_metadata:
            await self.on_metadata(self, entities)
        if self.metadata_error:
            raise self.metadata_error
        return {entity: deepcopy(self.metadata[entity]) for entity in entities
                if entity in self.metadata}

    async def get_state_value(self, entity, default=""):
        self.timeline.append(("value", (entity,), None, self.clock.now.timestamp()))
        if self.on_read:
            await self.on_read(self, [entity])
        return self.reports.get(entity, {}).get("state", default)

    async def _command(self, method, entity, value):
        self.calls.append((method, entity, value))
        self.timeline.append((method, (entity,), value, self.clock.now.timestamp()))
        if self.on_write:
            await self.on_write(self, method, entity, value)
        queued = self.outcomes.get((method, entity), [])
        result = queued.pop(0) if queued else True
        if isinstance(result, BaseException):
            raise result
        return result

    async def set_number(self, entity, value):
        return await self._command("set_number", entity, value)

    async def select_option(self, entity, value):
        return await self._command("select_option", entity, value)

    async def turn_on(self, entity):
        return await self._command("turn_on", entity, True)


class _Rig:
    def __init__(self):
        self.case = Haos49CharacterizationCase()
        self.case.setUp()
        self.clock = _Clock()
        self.ha = _ObservedHA(self.clock)
        self.opt = self.case.optimizer(self.ha)

    def state(self, **changes):
        return self.case.state(self.clock.now.replace(tzinfo=None), **changes)

    def automated(self, *, switch="on"):
        cfg = self.opt.cfg
        for entity, value in (
            (cfg.sigenergy_mode_select, cfg.automated_option),
            (cfg.ha_control_switch, switch),
            (cfg.ems_mode_select, MODE_MAX_SELF),
            (cfg.grid_export_limit, 0.01),
            (cfg.grid_import_limit, 0.01),
        ):
            self.ha.observe(entity, value)

    def read(self):
        state = self.clock.run(self.opt._read_state())
        state.timestamp = self.clock.now.replace(tzinfo=None)
        return state

    def apply(self, state, decision):
        return self.clock.run(self.opt._apply(state, decision))

    @staticmethod
    def decision(**changes):
        values = dict(
            ems_mode=MODE_MAX_SELF, export_limit=0.0, import_limit=0.0,
            pv_max_power_limit=25.0, ess_charge_limit=25.0, ess_discharge_limit=25.0,
        )
        values.update(changes)
        return Decision(**values)

    def discharge(self):
        return self.decision(ems_mode=MODE_CMD_DISCHARGE_PV, export_limit=5.0,
                             export_intent=BATTERY_EXPORT)

    def writes(self):
        cfg = self.opt.cfg
        entities = {cfg.ems_mode_select, cfg.grid_export_limit, cfg.grid_import_limit,
                    cfg.ess_max_charging_limit, cfg.ess_max_discharging_limit,
                    cfg.pv_max_power_limit}
        return [call for call in self.ha.calls if call[1] in entities
                and call[0] in {"set_number", "select_option"}]

    def permissive(self):
        return [call for call in self.writes()
                if (call[0] == "set_number" and float(call[2]) > 0.011)
                or (call[0] == "select_option" and call[2] in DISCHARGE_MODES)]


def _assert_no_permissive_continuation(rig, boundary, *, pv_restriction=None):
    cfg = rig.opt.cfg
    number_entities = {
        cfg.grid_export_limit, cfg.grid_import_limit,
        cfg.ess_max_charging_limit, cfg.ess_max_discharging_limit,
        cfg.pv_max_power_limit,
    }
    unauthorized = []
    for method, entity, value in rig.ha.calls[boundary:]:
        if method == "set_number" and entity in number_entities:
            # Independent restrictive PV ownership may have a positive ceiling.
            ceiling = (pv_restriction if entity == cfg.pv_max_power_limit
                       and pv_restriction is not None else 0.011)
            if float(value) > ceiling:
                unauthorized.append((method, entity, value))
        elif method == "select_option" and entity == cfg.ems_mode_select:
            if value != MODE_MAX_SELF:
                unauthorized.append((method, entity, value))
        elif (method == "turn_on" and entity == cfg.ha_control_switch
              or method == "select_option" and entity == cfg.sigenergy_mode_select):
            unauthorized.append((method, entity, value))
    assert not unauthorized, f"unauthorized permissive continuation: {unauthorized}"


@pytest.fixture
def rig():
    value = _Rig()
    try:
        yield value
    finally:
        value.case.tearDown()


@pytest.mark.parametrize("domain", ["select", "input_select"])
def test_verified_automated_ownership_is_observed_for_both_selector_domains(rig, domain):
    rig.opt.cfg.sigenergy_mode_select = f"{domain}.stage_a_mode"
    rig.automated()
    # A persistent helper can remain unchanged for days with current report proof.
    if domain == "input_select":
        rig.ha.observe(rig.opt.cfg.sigenergy_mode_select, "Automated",
                       updated=rig.clock.now - timedelta(days=3))
    state = rig.read()
    assert state.sigenergy_mode == "Automated"
    assert state.sigenergy_mode_observed


@pytest.mark.parametrize("domain", ["select", "input_select"])
@pytest.mark.parametrize("chronology", ["future", "before_update", "malformed", "missing", "stale"])
def test_operator_evidence_requires_valid_chronology_and_device_freshness(rig, domain, chronology):
    rig.opt.cfg.sigenergy_mode_select = f"{domain}.stage_a_mode"
    rig.automated()
    entity = rig.opt.cfg.sigenergy_mode_select
    if chronology == "future":
        rig.ha.observe(entity, "Automated", at=rig.clock.now + timedelta(seconds=30))
    elif chronology == "before_update":
        rig.ha.observe(entity, "Automated", at=rig.clock.now - timedelta(seconds=1),
                       updated=rig.clock.now)
    elif chronology == "stale":
        rig.ha.observe(entity, "Automated", at=rig.clock.now - timedelta(seconds=121))
    else:
        for rows in (rig.ha.reports, rig.ha.metadata):
            if chronology == "missing":
                rows[entity].pop("last_updated")
                rows[entity].pop("last_reported")
            else:
                rows[entity]["last_updated"] = "bad timestamp"
                rows[entity]["last_reported"] = "bad timestamp"
    state = rig.read()
    if domain == "input_select" and chronology == "stale":
        # Persistent helpers remain current when genuinely read unchanged.
        assert state.sigenergy_mode_observed
    else:
        assert not state.sigenergy_mode_observed, "raw Automated text is not verified chronology"


@pytest.mark.parametrize("newer", ["Manual", "Force Full Export", "unavailable"])
def test_newer_contradictory_operator_metadata_revokes_stale_automated_evidence(rig, newer):
    rig.automated()
    entity = rig.opt.cfg.sigenergy_mode_select
    rig.clock.advance()
    rig.ha.observe(entity, newer)
    # REST completed first with the old value; the metadata read sees a newer state.
    old = rig.clock.now - timedelta(seconds=1)
    rig.ha.reports[entity] = dict(rig.ha.metadata[entity], state="Automated",
                                last_updated=old.isoformat(), last_reported=old.isoformat())
    state = rig.read()
    assert not (state.sigenergy_mode == "Automated" and state.sigenergy_mode_observed)


@pytest.mark.parametrize("unsupported", [False, True], ids=["metadata-outage", "unsupported-interface"])
def test_fresh_direct_helper_ownership_survives_optional_metadata_unavailability(rig, unsupported):
    rig.automated()
    assert rig.opt.cfg.sigenergy_mode_select.startswith("input_select.")
    if unsupported:
        rig.ha.get_state_report_metadata = None
    else:
        rig.ha.metadata_error = RuntimeError("simulated metadata outage")
    state = rig.read()
    # A successful current helper read is distinct from failed ownership refresh.
    assert state.sigenergy_mode == rig.opt.cfg.automated_option
    assert state.sigenergy_mode_observed


def test_missing_current_ownership_cannot_be_replaced_by_metadata_or_cached_mode(rig):
    rig.automated()
    initial = rig.read()
    assert initial.sigenergy_mode_observed
    rig.opt._last_state = initial
    entity = rig.opt.cfg.sigenergy_mode_select
    rig.ha.reports.pop(entity)  # Metadata still contains the earlier Automated row.
    assert rig.ha.metadata[entity]["state"] == rig.opt.cfg.automated_option
    current = rig.read()
    assert not current.sigenergy_mode_observed
    rig.apply(current, rig.discharge())
    assert rig.writes() == []


@pytest.mark.parametrize("mode", ["unavailable", "Manual", "Force Full Export"])
def test_unknown_or_operator_owned_selection_cannot_acquire_remote_ems(rig, mode):
    rig.automated(switch="off")
    rig.ha.observe(rig.opt.cfg.sigenergy_mode_select, mode)
    parsed = rig.read()
    state = rig.state(sigenergy_mode=parsed.sigenergy_mode,
                      sigenergy_mode_observed=parsed.sigenergy_mode_observed,
                      ha_control_enabled=False, ha_control_switch_state="off",
                      feedin_is_negative=True, feedin_price=-0.10, feedin_price_cents=-10.0)
    if mode == "Force Full Export":
        targets = rig.opt._manual_mode_targets(mode, state)
        for field, key in (("current_ems_mode", "ems_mode"),
                           ("current_export_limit", "grid_export_limit"),
                           ("current_import_limit", "grid_import_limit"),
                           ("current_pv_max_power_limit", "pv_max_power_limit"),
                           ("current_ess_charge_limit", "ess_charge_limit"),
                           ("current_ess_discharge_limit", "ess_discharge_limit")):
            setattr(state, field, targets[key])
    decision = rig.clock.run(_decide(rig.opt, state))
    if mode == "unavailable":
        assert decision.needs_ha_control_switch, "negative acquisition case must reach the enable path"
    rig.apply(state, decision)
    assert not any(call[0] == "turn_on" for call in rig.ha.calls)


async def _decide(opt, state):
    return opt._decide(state)


def test_unknown_selection_and_confirmed_manual_takeover_remain_distinct(rig):
    rig.automated()
    cfg = rig.opt.cfg
    rig.ha.observe(cfg.sigenergy_mode_select, "unavailable")
    unknown = rig.read()
    assert not unknown.sigenergy_mode_observed
    assert unknown.sigenergy_mode not in {
        cfg.manual_option, cfg.full_export_option, cfg.full_import_option,
        cfg.full_import_pv_option, cfg.block_flow_option,
    }, "initial Unknown must not be relabelled as confirmed operator ownership"
    rig.apply(unknown, rig.discharge())
    assert rig.writes() == []
    rig.ha.observe(cfg.sigenergy_mode_select, "Manual")
    takeover = rig.read()
    assert takeover.sigenergy_mode == "Manual" and takeover.sigenergy_mode_observed
    rig.opt._last_state = takeover
    rig.ha.observe(cfg.sigenergy_mode_select, "unavailable")
    uncertain = rig.read()
    assert uncertain.sigenergy_mode == "Manual" and not uncertain.sigenergy_mode_observed
    rig.apply(uncertain, rig.discharge())
    assert rig.writes() == []
    # Genuine new observations restore authority on this same optimizer instance.
    original_optimizer = rig.opt
    rig.clock.advance()
    rig.automated()
    verified = rig.read()
    assert rig.opt is original_optimizer
    assert verified.sigenergy_mode == cfg.automated_option
    assert verified.sigenergy_mode_observed and verified.ha_control_enabled
    recovered = rig.apply(verified, rig.decision(import_limit=5.0))
    assert recovered.succeeded
    assert ("set_number", cfg.grid_import_limit, 5.0) in rig.ha.calls
    assert not any(call[0] == "turn_on" for call in rig.ha.calls)


def test_confirmed_force_takeover_then_uncertainty_does_not_reclaim_automated_control(rig):
    rig.automated(switch="off")
    cfg = rig.opt.cfg
    rig.ha.observe(cfg.sigenergy_mode_select, cfg.full_export_option)
    confirmed = rig.read()
    assert confirmed.sigenergy_mode_observed
    rig.opt._last_state = confirmed
    rig.ha.observe(cfg.sigenergy_mode_select, "unavailable")
    uncertain = rig.read()
    assert uncertain.sigenergy_mode == cfg.full_export_option
    assert not uncertain.sigenergy_mode_observed
    # No drift is needed to test absence of automatic reclamation.
    targets = rig.opt._manual_mode_targets(cfg.full_export_option, uncertain)
    for field, key in (("current_ems_mode", "ems_mode"),
                       ("current_export_limit", "grid_export_limit"),
                       ("current_import_limit", "grid_import_limit"),
                       ("current_pv_max_power_limit", "pv_max_power_limit"),
                       ("current_ess_charge_limit", "ess_charge_limit"),
                       ("current_ess_discharge_limit", "ess_discharge_limit")):
        setattr(uncertain, field, targets[key])
    rig.apply(uncertain, rig.discharge())
    assert rig.ha.calls == []


@pytest.mark.parametrize("restart", [False, True], ids=["startup", "restart"])
def test_legitimate_startup_auto_enable_waits_for_observed_on_and_recovers(rig, restart):
    if restart:
        rig.automated()
        previous_optimizer = rig.opt
        prior = rig.apply(rig.state(), rig.decision(import_limit=5.0))
        assert prior.succeeded
        assert ("set_number", rig.opt.cfg.grid_import_limit, 5.0) in rig.ha.calls
        rig.clock.advance()
        rig.opt = rig.case.optimizer(rig.ha)
        assert rig.opt is not previous_optimizer
        assert rig.opt._last_state is None
        rig.ha.calls.clear()
    # HA independently reports the available OFF switch after startup/restart.
    rig.automated(switch="off")
    state = rig.state(ha_control_enabled=False, ha_control_switch_state="off",
                      feedin_is_negative=True, feedin_price=-0.10, feedin_price_cents=-10.0)
    decision = rig.clock.run(_decide(rig.opt, state))
    assert decision.needs_ha_control_switch
    rig.apply(state, decision)
    assert ("turn_on", rig.opt.cfg.ha_control_switch, True) in rig.ha.calls
    assert rig.writes() == []
    # The operator/HA supplies a new ON observation, independent of turn_on success.
    rig.clock.advance()
    rig.ha.observe(rig.opt.cfg.ha_control_switch, "on")
    rig.ha.calls.clear()
    observed_on = rig.read()
    assert observed_on.ha_control_enabled and observed_on.sigenergy_mode_observed
    result = rig.apply(observed_on, rig.decision(import_limit=5.0))
    assert result.succeeded
    assert ("set_number", rig.opt.cfg.grid_import_limit, 5.0) in rig.ha.calls
    assert not any(call[0] == "turn_on" for call in rig.ha.calls)


def _target_observation(rig, value, *, timing="later", change=None):
    cfg = rig.opt.cfg
    before = rig.clock.now - timedelta(seconds=1)

    async def on_read(ha, entities):
        if cfg.grid_export_limit in entities:
            rig.clock.advance()
            observed = before if timing == "before" else rig.clock.now
            ha.observe(cfg.grid_export_limit, value, at=observed)
            if change:
                entity, new_value = change
                ha.observe(entity, new_value)

    rig.ha.on_read = on_read


def test_authority_refresh_precedes_export_request_dispatch(rig):
    rig.automated()
    _target_observation(rig, 5.0)
    state = rig.state(current_export_limit=25.0)
    rig.apply(state, rig.discharge())
    cfg = rig.opt.cfg
    request = next(i for i, event in enumerate(rig.ha.timeline)
                   if event[:3] == ("set_number", (cfg.grid_export_limit,), 5.0))
    authority_reads = [event for event in rig.ha.timeline[:request]
                       if event[0] == "bulk"]
    assert any(cfg.sigenergy_mode_select in event[1] for event in authority_reads), \
        "refresh current ownership before recording/dispatching request"
    assert any(cfg.ha_control_switch in event[1] for event in authority_reads), \
        "refresh Remote EMS before recording/dispatching request"


@pytest.mark.parametrize("value,timing", [(5.0, "before"), (0.01, "later"), (3.0, "later"), (5.0, "later")],
                         ids=["pre-request-exact", "closed-upper-bound", "lower-upper-bound", "later-exact"])
def test_discharge_requires_later_intended_export_target_observation(rig, value, timing):
    rig.automated()
    _target_observation(rig, value, timing=timing)
    waiter = AsyncMock(wraps=rig.opt._wait_for_number_at_most)
    rig.opt._wait_for_number_at_most = waiter
    result = rig.apply(rig.state(current_export_limit=25.0), rig.discharge())
    target = ("set_number", rig.opt.cfg.grid_export_limit, 5.0)
    assert target in rig.ha.calls, "negative case must dispatch the intended target"
    assert any(call.args[:2] == (rig.opt.cfg.grid_export_limit, 5.0)
               for call in waiter.await_args_list), "target settlement must actually be awaited"
    discharge = ("select_option", rig.opt.cfg.ems_mode_select, MODE_CMD_DISCHARGE_PV)
    if value == 5.0 and timing == "later":
        assert result.succeeded
        assert rig.ha.calls.index(target) < rig.ha.calls.index(discharge)
    else:
        assert discharge not in rig.ha.calls, "a pre-request or merely upper-bound reading cannot settle the target"


def test_report_during_delayed_authority_refresh_cannot_settle_later_dispatch(rig):
    rig.automated()
    cfg = rig.opt.cfg
    state = rig.read()  # Finish setup before arming the application-time report.
    setup_finished_at = rig.clock.now.timestamp()
    rig.clock.advance()
    application_started_at = rig.clock.now.timestamp()
    target = ("set_number", cfg.grid_export_limit, 5.0)
    refresh_reports = []
    refresh_windows = []

    async def delayed_refresh(ha, entities):
        if cfg.sigenergy_mode_select in entities and not refresh_windows:
            assert target not in ha.calls, "authority refresh must precede target dispatch"
            window = {"started": rig.clock.now.timestamp()}
            refresh_windows.append(window)
            await asyncio.sleep(1.0)
            ha.observe(cfg.sigenergy_mode_select, cfg.automated_option)
            ha.observe(cfg.ha_control_switch, "on")
            ha.observe(cfg.grid_export_limit, 5.0)
            refresh_reports.append(rig.clock.now.timestamp())
            await asyncio.sleep(1.0)  # Validation completes after the actuator report.
            window["completed"] = rig.clock.now.timestamp()

    rig.ha.on_read = delayed_refresh
    waiter = AsyncMock(wraps=rig.opt._wait_for_number_at_most)
    rig.opt._wait_for_number_at_most = waiter
    rig.apply(state, rig.discharge())
    request = next(event for event in rig.ha.timeline
                   if event[:3] == ("set_number", (cfg.grid_export_limit,), 5.0))
    assert target in rig.ha.calls, "the intended export request must be dispatched"
    assert any(call.args[:2] == (cfg.grid_export_limit, 5.0) for call in waiter.await_args_list)
    assert len(refresh_reports) == 1, "only the intended pre-dispatch read seeds a report"
    assert len(refresh_windows) == 1
    window = refresh_windows[0]
    assert setup_finished_at < application_started_at <= window["started"]
    assert window["started"] < refresh_reports[0] < window["completed"] <= request[3]
    assert refresh_reports[0] < request[3]
    assert datetime.fromisoformat(
        rig.ha.reports[cfg.grid_export_limit]["last_reported"],
    ).timestamp() == refresh_reports[0], "no genuine post-dispatch report was supplied"
    assert ("select_option", cfg.ems_mode_select, MODE_CMD_DISCHARGE_PV) not in rig.ha.calls


@pytest.mark.parametrize("reported", [9.0, "unavailable"])
def test_unsettled_target_reaches_real_waiter_and_blocks_discharge(rig, reported):
    rig.automated()
    _target_observation(rig, reported)
    waiter = AsyncMock(wraps=rig.opt._wait_for_number_at_most)
    rig.opt._wait_for_number_at_most = waiter
    result = rig.apply(rig.state(current_export_limit=25.0), rig.discharge())
    cfg = rig.opt.cfg
    assert ("set_number", cfg.grid_export_limit, 5.0) in rig.ha.calls
    assert any(call.args[:2] == (cfg.grid_export_limit, 5.0) for call in waiter.await_args_list)
    assert result.fallback_attempted and not result.succeeded
    assert "export limit did not settle at or below 5.00kW" in result.error
    assert ("select_option", cfg.ems_mode_select, MODE_CMD_DISCHARGE_PV) not in rig.ha.calls


@pytest.mark.parametrize("change", ["manual", "force", "unknown", "remote_off", "refresh_failure"])
def test_authority_loss_during_awaited_target_read_stops_subsequent_permissive_commands(rig, change):
    rig.automated()
    cfg = rig.opt.cfg
    selection = {"manual": "Manual", "force": cfg.full_export_option,
                 "unknown": "unavailable"}
    target = ("set_number", cfg.grid_export_limit, 5.0)
    loss_boundary = []

    async def delayed(ha, entities):
        if (cfg.grid_export_limit not in entities or target not in ha.calls
                or loss_boundary):
            return
        rig.clock.advance()
        ha.observe(cfg.grid_export_limit, 5.0)
        if change == "refresh_failure":
            # The target report remains independently valid, but a current
            # ownership read cannot return the old Automated/ON snapshot.
            ha.reports.pop(cfg.sigenergy_mode_select)
            ha.metadata.pop(cfg.sigenergy_mode_select)
        elif change == "remote_off":
            ha.observe(cfg.ha_control_switch, "off")
        else:
            ha.observe(cfg.sigenergy_mode_select, selection[change])
        loss_boundary.append(len(ha.calls))
        await asyncio.sleep(0)  # An actual suspension boundary, using the local clock.

    rig.ha.on_read = delayed
    result = rig.apply(rig.state(current_export_limit=25.0), rig.discharge())
    assert ("set_number", cfg.grid_export_limit, 5.0) in rig.ha.calls
    assert rig.ha.bulk_state_calls, "the delayed read must be reached"
    assert loss_boundary, "authority must be lost after dispatch during target readback"
    _assert_no_permissive_continuation(rig, loss_boundary[0])
    assert ("select_option", cfg.ems_mode_select, MODE_CMD_DISCHARGE_PV) not in rig.ha.calls
    if change in {"manual", "force"}:
        assert not result.fallback_attempted, "confirmed takeover stops automatic recovery"


@pytest.mark.parametrize("lost", ["device_select_expiry", "remote_ems_currentness_loss"])
def test_authority_expiry_or_lost_currentness_during_target_wait_blocks_continuation(rig, lost):
    cfg = rig.opt.cfg
    if lost == "device_select_expiry":
        cfg.sigenergy_mode_select = "select.stage_a_mode"
    rig.automated()
    authority_reported_at = rig.clock.now
    max_age = cfg.hvac_solar_data_max_age_seconds
    if lost == "device_select_expiry":
        # Start within the existing device observation age limit, then cross it
        # inside a two-second awaited read (not an initially stale snapshot).
        rig.clock.advance(max_age - 1.0)
        rig.ha.observe(cfg.ha_control_switch, "on")
        rig.ha.observe(cfg.ems_mode_select, MODE_MAX_SELF)
    initial = rig.read()
    assert initial.sigenergy_mode_observed and initial.ha_control_enabled
    assert initial.hvac_solar_inputs.control_mode.fresh
    target = ("set_number", cfg.grid_export_limit, 5.0)
    loss_boundary = []

    async def expire_during_read(ha, entities):
        if (cfg.grid_export_limit not in entities or target not in ha.calls
                or loss_boundary):
            return
        await asyncio.sleep(2.0 if lost == "device_select_expiry" else 1.0)
        if lost == "device_select_expiry":
            assert (rig.clock.now - authority_reported_at).total_seconds() > max_age
            ha.observe(cfg.ha_control_switch, "on")  # Isolate selector expiry.
        else:
            # No approved Remote EMS age cutoff is established here. A failed
            # current switch read cannot reuse the earlier ON observation.
            ha.reports.pop(cfg.ha_control_switch)
            ha.metadata.pop(cfg.ha_control_switch)
            ha.observe(cfg.sigenergy_mode_select, cfg.automated_option)
        ha.observe(cfg.ems_mode_select, MODE_MAX_SELF)
        ha.observe(cfg.grid_export_limit, 5.0)  # Independently fresh settlement.
        loss_boundary.append(len(ha.calls))

    rig.ha.on_read = expire_during_read
    waiter = AsyncMock(wraps=rig.opt._wait_for_number_at_most)
    rig.opt._wait_for_number_at_most = waiter
    rig.apply(rig.state(current_export_limit=25.0), rig.discharge())
    assert target in rig.ha.calls
    assert any(call.args[:2] == (cfg.grid_export_limit, 5.0)
               for call in waiter.await_args_list)
    assert loss_boundary, "valid authority must expire/lose currentness inside the awaited read"
    report = rig.ha.reports[cfg.grid_export_limit]
    request = next(event for event in rig.ha.timeline
                   if event[:3] == ("set_number", (cfg.grid_export_limit,), 5.0))
    assert datetime.fromisoformat(report["last_reported"]).timestamp() > request[3]
    _assert_no_permissive_continuation(rig, loss_boundary[0])


def test_failed_authority_refresh_cannot_use_stale_in_flight_snapshot(rig):
    rig.automated()
    rig.ha.bulk_states = AsyncMock(return_value={})
    rig.apply(rig.state(), rig.decision(import_limit=5.0))
    assert rig.permissive() == [], "a failed current refresh cannot retain old Automated/ON authority"


def test_current_remote_off_overrides_an_older_on_snapshot(rig):
    rig.automated()
    stale = rig.state()
    rig.clock.advance()
    rig.ha.observe(rig.opt.cfg.ha_control_switch, "off")
    rig.apply(stale, rig.decision(import_limit=5.0))
    assert rig.writes() == [], "automatic writes need currently observed Remote EMS ON"


@pytest.mark.parametrize("takeover", ["Manual", "Force Full Export"])
def test_confirmed_takeover_then_uncertainty_supersedes_pending_automated_request(rig, takeover):
    rig.automated()
    pending = rig.state(current_export_limit=25.0)
    rig.clock.advance()
    rig.opt._last_state = rig.state(sigenergy_mode=takeover, sigenergy_mode_observed=True)
    rig.ha.observe(rig.opt.cfg.sigenergy_mode_select, takeover)
    rig.clock.advance()
    rig.ha.observe(rig.opt.cfg.sigenergy_mode_select, "unavailable")
    _target_observation(rig, 5.0)
    rig.apply(pending, rig.discharge())
    assert rig.writes() == [], "uncertainty cannot undo a confirmed takeover or reclaim automatic ownership"


def test_pv_only_reassertion_requires_its_own_later_exact_msc_report(rig):
    rig.automated()
    rig.opt._msc_baseline_established = True
    rig.clock.advance()  # Current MSC report is fresh but predates the reassertion.
    waiter = AsyncMock(wraps=rig.opt._wait_for_exact_entity_state)
    rig.opt._wait_for_exact_entity_state = waiter
    rig.apply(rig.state(), rig.decision(export_limit=25.0,
              export_intent=MSC_SURPLUS_CEILING, requires_verified_msc_before_export=True))
    cfg = rig.opt.cfg
    assert ("select_option", cfg.ems_mode_select, MODE_MAX_SELF) in rig.ha.calls
    assert waiter.await_count > 0, "MSC settlement must be awaited"
    assert ("set_number", cfg.grid_export_limit, 25.0) not in rig.ha.calls


def test_unsettled_pv_only_msc_reassertion_reaches_waiter_and_never_opens_export(rig):
    rig.automated()
    rig.opt._msc_baseline_established = True
    cfg = rig.opt.cfg

    async def uncertain_readback(ha, method, entity, value):
        if entity == cfg.ems_mode_select:
            rig.clock.advance()
            ha.observe(cfg.ems_mode_select, "unavailable")

    rig.ha.on_write = uncertain_readback
    waiter = AsyncMock(wraps=rig.opt._wait_for_exact_entity_state)
    rig.opt._wait_for_exact_entity_state = waiter
    result = rig.apply(rig.state(), rig.decision(export_limit=25.0,
              export_intent=MSC_SURPLUS_CEILING, requires_verified_msc_before_export=True))
    assert ("select_option", cfg.ems_mode_select, MODE_MAX_SELF) in rig.ha.calls
    assert waiter.await_count > 0, "the named exact-MSC safeguard must be reached"
    assert not result.succeeded and result.fallback_attempted
    assert "Maximum Self Consumption did not settle before high PV-only export" in result.error
    assert ("set_number", cfg.grid_export_limit, 25.0) not in rig.ha.calls


def test_ordinary_export_close_requires_its_own_post_request_observation(rig):
    rig.automated()
    rig.clock.advance()
    result = rig.apply(rig.state(current_export_limit=25.0), rig.decision())
    assert ("set_number", rig.opt.cfg.grid_export_limit, 0.01) in rig.ha.calls
    assert any(rig.opt.cfg.grid_export_limit in ids for ids in rig.ha.bulk_state_calls)
    assert not result.succeeded
    assert rig.permissive() == [], "pre-close evidence cannot release normal ESS capability"


@pytest.mark.parametrize("owner,required", [
    ("demand", "import"), ("untrusted_demand", "import"),
    ("standby", "pv"), ("negative_price", "pv"), ("negative_price", "ess_discharge"),
])
def test_unproven_export_close_keeps_independent_import_ess_and_pv_restrictions(rig, owner, required):
    rig.automated()
    cfg = rig.opt.cfg
    rig.ha.observe(cfg.grid_export_limit, 25.0)
    state = rig.state(current_export_limit=25.0, current_import_limit=25.0,
                      current_ess_charge_limit=0.01,
                      demand_window_active=owner == "demand",
                      demand_window_observed=owner != "untrusted_demand",
                      price_is_negative=owner == "negative_price",
                      current_price=-0.35 if owner == "negative_price" else 0.30)
    decision = rig.decision(ess_discharge_limit=0.01, pv_max_power_limit=0.0,
                            standby_holdoff_active=owner == "standby")
    failure_boundary = []

    async def observe_failed_close(ha, entities):
        if (cfg.grid_export_limit in entities and not failure_boundary
                and ("set_number", cfg.grid_export_limit, 0.01) in ha.calls):
            rig.clock.advance()
            ha.observe(cfg.grid_export_limit, 25.0)
            failure_boundary.append(len(ha.calls))
            await asyncio.sleep(0)

    rig.ha.on_read = observe_failed_close
    result = rig.apply(state, decision)
    assert not result.succeeded
    assert "observed readback remains open" in result.error
    assert ("set_number", cfg.grid_export_limit, 0.01) in rig.ha.calls
    assert ("set_number", cfg.grid_import_limit, 0.01) in rig.ha.calls
    if required == "ess_discharge":
        assert ("set_number", cfg.ess_max_discharging_limit, 0.01) in rig.ha.calls
    elif required == "pv":
        assert ("set_number", cfg.pv_max_power_limit, 0.0) in rig.ha.calls
    if owner == "negative_price":
        assert ("set_number", cfg.ess_max_discharging_limit, 0.01) in rig.ha.calls
        assert ("set_number", cfg.pv_max_power_limit, 0.0) in rig.ha.calls
    assert failure_boundary, "the still-open readback must follow the close request"
    _assert_no_permissive_continuation(
        rig, failure_boundary[0],
        pv_restriction=decision.pv_max_power_limit
        if owner in {"standby", "negative_price"} else None,
    )


def _fallback_observations(rig, *, stale_msc=False, stale_closure=False):
    cfg = rig.opt.cfg
    before = rig.clock.now - timedelta(seconds=1)
    rig.ha.outcomes[("set_number", cfg.grid_export_limit)] = [False, True]

    async def observe(ha, entities):
        rig.clock.advance()
        if cfg.grid_export_limit in entities:
            ha.observe(cfg.grid_export_limit, 0.01,
                       at=before if stale_closure else rig.clock.now)
        if cfg.ems_mode_select in entities:
            at = rig.clock.now - timedelta(seconds=20) if stale_msc else rig.clock.now
            ha.observe(cfg.ems_mode_select, MODE_MAX_SELF, at=at)

    rig.ha.on_read = observe


def test_fallback_export_closure_needs_its_own_post_request_evidence(rig):
    rig.automated()
    _fallback_observations(rig, stale_closure=True)
    export_wait = AsyncMock(wraps=rig.opt._wait_for_number_at_most)
    rig.opt._wait_for_number_at_most = export_wait
    result = rig.apply(rig.state(current_export_limit=25.0), rig.discharge())
    assert result.fallback_attempted
    assert export_wait.await_count > 0, "fallback closure settlement must actually be awaited"
    assert ("set_number", rig.opt.cfg.grid_export_limit, 0.01) in rig.ha.calls
    assert not result.fallback_succeeded, "fresh pre-close evidence cannot settle a later fallback close"
    assert not any(call[0] == "set_number" and call[1] == rig.opt.cfg.grid_import_limit
                   and float(call[2]) > 0.011 for call in rig.ha.calls)


def test_fallback_requires_separate_later_exact_msc_evidence(rig):
    rig.automated()
    _fallback_observations(rig, stale_msc=True)
    export_wait = AsyncMock(wraps=rig.opt._wait_for_number_at_most)
    msc_wait = AsyncMock(wraps=rig.opt._wait_for_exact_entity_state)
    rig.opt._wait_for_number_at_most = export_wait
    rig.opt._wait_for_exact_entity_state = msc_wait
    result = rig.apply(rig.state(current_export_limit=25.0), rig.discharge())
    assert result.fallback_attempted and not result.fallback_succeeded
    assert export_wait.await_count > 0 and msc_wait.await_count > 0
    assert msc_wait.await_args.kwargs["observed_after"] is not None
    assert ("set_number", rig.opt.cfg.ess_max_discharging_limit, 0.01) in rig.ha.calls
    assert not any(float(call[2]) > 0.011 for call in rig.writes()
                   if call[0] == "set_number" and call[1] == rig.opt.cfg.ess_max_discharging_limit)


@pytest.mark.parametrize("lost", ["closure", "msc", "manual", "force", "unknown", "remote_on"])
def test_fallback_recovery_rechecks_current_evidence_and_yields_to_takeover(rig, lost):
    rig.automated()
    _fallback_observations(rig)
    cfg = rig.opt.cfg
    real_wait = rig.opt._wait_for_exact_entity_state
    recovery_start = []

    async def wait_then_change(*args, **kwargs):
        settled = await real_wait(*args, **kwargs)
        assert settled, "the fallback MSC waiter must reach genuinely later evidence"
        rig.clock.advance()
        entity, value = {
            "closure": (cfg.grid_export_limit, 25.0),
            "msc": (cfg.ems_mode_select, MODE_CMD_DISCHARGE_PV),
            "manual": (cfg.sigenergy_mode_select, cfg.manual_option),
            "force": (cfg.sigenergy_mode_select, cfg.full_export_option),
            "unknown": (cfg.sigenergy_mode_select, "unavailable"),
            "remote_on": (cfg.ha_control_switch, "off"),
        }[lost]
        rig.ha.observe(entity, value)
        rig.ha.on_read = None
        recovery_start.append(len(rig.ha.calls))
        return settled

    rig.opt._wait_for_exact_entity_state = AsyncMock(side_effect=wait_then_change)
    result = rig.apply(rig.state(current_export_limit=25.0), rig.discharge())
    assert result.fallback_attempted
    assert recovery_start, "negative case must reach the recovery boundary"
    following = rig.ha.calls[recovery_start[0]:]
    assert not any(call[0] == "set_number" and float(call[2]) > 0.011
                   for call in following), "recovery cannot reuse superseded closure/MSC/ownership/ON evidence"


def test_confirmed_takeover_during_failed_command_stops_automatic_fallback(rig):
    rig.automated()
    cfg = rig.opt.cfg
    rig.ha.outcomes[("set_number", cfg.grid_export_limit)] = [False]
    boundary = []

    async def takeover(ha, method, entity, value):
        if entity == cfg.grid_export_limit and value == 5.0:
            rig.clock.advance()
            ha.observe(cfg.sigenergy_mode_select, cfg.manual_option)
            boundary.append(len(ha.calls))

    rig.ha.on_write = takeover
    result = rig.apply(rig.state(current_export_limit=25.0), rig.discharge())
    assert boundary, "primary command and takeover must occur"
    assert rig.ha.calls[boundary[0]:] == [], "confirmed Manual takeover stops automatic recovery writes"
    assert not result.fallback_attempted


def test_newer_manual_selection_supersedes_old_force_pin(rig):
    rig.automated()
    cfg = rig.opt.cfg
    rig.opt._manual_mode_override = cfg.full_export_option
    rig.clock.advance()
    rig.ha.observe(cfg.sigenergy_mode_select, cfg.manual_option)
    state = rig.state(sigenergy_mode=cfg.manual_option)
    rig.opt._wait_for_exact_entity_state = AsyncMock(return_value=True)
    rig.apply(state, rig.discharge())
    assert ("select_option", cfg.sigenergy_mode_select, cfg.full_export_option) not in rig.ha.calls
    assert rig.writes() == [], "a stale Force pin must not overwrite newer credible Manual ownership"


def test_force_retry_stops_when_newer_operator_selection_arrives_during_wait(rig):
    rig.automated()
    cfg = rig.opt.cfg
    rig.ha.observe(cfg.sigenergy_mode_select, cfg.full_export_option)
    targets = rig.opt._manual_mode_targets(cfg.full_export_option, rig.state())
    boundary = []

    async def unsettled(*args, **kwargs):
        rig.clock.advance()
        rig.ha.observe(cfg.sigenergy_mode_select, cfg.manual_option)
        boundary.append(len(rig.ha.calls))
        return False

    rig.opt._wait_for_exact_entity_state = AsyncMock(side_effect=unsettled)
    rig.clock.run(rig.opt._apply_manual_mode_targets(targets, mode_label=cfg.full_export_option))
    assert boundary and rig.opt._wait_for_exact_entity_state.await_count > 0
    assert ("select_option", cfg.ems_mode_select, targets["ems_mode"]) in rig.ha.calls
    assert rig.ha.calls[boundary[0]:] == [], "a stale Force retry must yield to the newer Manual selection"


def test_force_ems_retries_use_attempt_specific_request_boundaries(rig):
    rig.automated()
    cfg = rig.opt.cfg
    rig.ha.observe(cfg.sigenergy_mode_select, cfg.full_export_option)
    targets = rig.opt._manual_mode_targets(cfg.full_export_option, rig.state())
    waiter = AsyncMock(side_effect=[False, False, True])
    rig.opt._wait_for_exact_entity_state = waiter
    rig.clock.run(rig.opt._apply_manual_mode_targets(targets, mode_label=cfg.full_export_option))
    requests = [event for event in rig.ha.timeline
                if event[:3] == ("select_option", (cfg.ems_mode_select,), targets["ems_mode"])]
    assert len(requests) == waiter.await_count == 3, "all three attempt boundaries must be exercised"
    for request, awaited in zip(requests, waiter.await_args_list):
        assert awaited.kwargs.get("observed_after") == request[3], "each retry needs its own later-report boundary"


def test_report_after_first_force_request_cannot_settle_a_later_retry(rig):
    rig.automated()
    cfg = rig.opt.cfg
    rig.ha.observe(cfg.sigenergy_mode_select, cfg.full_export_option)
    targets = rig.opt._manual_mode_targets(cfg.full_export_option, rig.state())
    # The report can prove attempt 1's response, but arrives after attempt 2
    # dispatch with chronology that still precedes attempt 2.
    delayed_report_at = rig.clock.now + timedelta(seconds=2)
    attempts = []

    async def delayed_report(ha, method, entity, value):
        if entity == cfg.ems_mode_select:
            attempts.append(rig.clock.now.timestamp())
            if len(attempts) == 2:
                ha.observe(cfg.ems_mode_select, MODE_CMD_DISCHARGE_PV, at=delayed_report_at)

    rig.ha.on_write = delayed_report
    waiter = AsyncMock(wraps=rig.opt._wait_for_exact_entity_state)
    rig.opt._wait_for_exact_entity_state = waiter
    result = rig.clock.run(rig.opt._apply_manual_mode_targets(targets, mode_label=cfg.full_export_option))
    assert len(attempts) >= 2 and waiter.await_count >= 2, "the negative case must reach a real retry"
    assert attempts[0] < delayed_report_at.timestamp() < attempts[1]
    assert not result["ems_mode"], "a report preceding retry dispatch cannot settle that retry"


def test_force_retry_counts_remain_bounded_when_all_attempts_fail(rig):
    rig.automated()
    cfg = rig.opt.cfg
    rig.ha.observe(cfg.sigenergy_mode_select, cfg.full_export_option)
    ownership = rig.read()
    assert ownership.sigenergy_mode == cfg.full_export_option
    assert ownership.sigenergy_mode_observed
    targets = rig.opt._manual_mode_targets(cfg.full_export_option, rig.state())
    rig.opt._wait_for_exact_entity_state = AsyncMock(return_value=False)
    for entity in (cfg.ess_max_charging_limit, cfg.ess_max_discharging_limit):
        rig.ha.outcomes[("set_number", entity)] = [False, False]
    result = rig.clock.run(rig.opt._apply_manual_mode_targets(targets, mode_label=cfg.full_export_option))
    assert rig.opt._wait_for_exact_entity_state.await_count == 4
    assert len([call for call in rig.ha.calls if call[0] == "select_option"]) == 4
    for entity in (cfg.ess_max_charging_limit, cfg.ess_max_discharging_limit):
        assert len([call for call in rig.ha.calls if call[:2] == ("set_number", entity)]) == 2
    assert not result["ems_mode"] and not result["ess_charge_limit"] and not result["ess_discharge_limit"]


def test_auto_enable_retry_delay_preserves_existing_bound(rig):
    rig.automated(switch="off")
    state = rig.state(ha_control_enabled=False, ha_control_switch_state="off",
                      feedin_is_negative=True, feedin_price=-0.10, feedin_price_cents=-10.0)
    decision = rig.clock.run(_decide(rig.opt, state))
    rig.apply(state, decision)
    rig.apply(state, decision)
    assert len([call for call in rig.ha.calls if call[0] == "turn_on"]) == 1
    rig.clock.advance(61)
    rig.apply(state, decision)
    assert len([call for call in rig.ha.calls if call[0] == "turn_on"]) == 2
    assert rig.writes() == []


def test_cancellation_during_dispatch_propagates_without_recovery_or_later_writes(rig):
    rig.automated()
    cfg = rig.opt.cfg
    rig.ha.outcomes[("set_number", cfg.grid_export_limit)] = [asyncio.CancelledError()]
    with pytest.raises(asyncio.CancelledError):
        rig.apply(rig.state(current_export_limit=25.0), rig.discharge())
    assert rig.ha.calls == [("set_number", cfg.grid_export_limit, 5.0)]


@pytest.mark.parametrize("invalid", ["before_update", "malformed", "missing"])
def test_ha_metadata_interface_rejects_invalid_report_chronology(invalid):
    entity = "select.stage_a_mode"
    row = dict(entity_id=entity, state="Automated",
               last_updated="2026-01-15T14:00:00+00:00", last_reported="2026-01-15T14:00:01+00:00")
    if invalid == "before_update":
        row["last_reported"] = "2026-01-15T13:59:59+00:00"
    elif invalid == "malformed":
        row["last_reported"] = "invalid"
    else:
        row.pop("last_reported")

    async def run():
        client = HAClient("http://stage-a.invalid", "synthetic-test-token")
        await client.close()
        client._client = httpx.AsyncClient(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=[row])), base_url="http://stage-a.invalid")
        try:
            return await client.get_state_report_metadata([entity])
        finally:
            await client.close()

    assert asyncio.run(run()) == {}


def test_authenticated_direct_set_ess_preserves_separate_service_order(rig):
    # Direct operator writes retain their own route semantics in Stage A.
    from test_set_ess_service_failure import _DummyOptimizer, _RecordingHA

    opt = _DummyOptimizer()
    ha = _RecordingHA(mode_value="Manual")
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(optimizer=opt, ha=ha)),
                              client=SimpleNamespace(host="192.0.2.1"),
                              headers={"x-api-key": "synthetic-stage-a-api-key"})
    body = ESSRequest(ems_mode=MODE_CMD_DISCHARGE_PV, grid_export_limit=5.0,
                      grid_import_limit=0.0, pv_max_power_limit=10.0,
                      ess_charge_limit=5.0, ess_discharge_limit=5.0, ha_control=True)
    with patch("app.routers.api.settings.ui_api_key", "synthetic-stage-a-api-key"):
        response = asyncio.run(set_ess(request, body))
    assert response == {"ok": True}
    assert ha.calls == [
        ("select_option", "select.ems_mode", MODE_CMD_DISCHARGE_PV),
        ("set_number", "number.grid_export", 5.0),
        ("set_number", "number.grid_import", 0.0),
        ("set_number", "number.pv_max", 10.0),
        ("set_number", "number.ess_charge", 5.0),
        ("set_number", "number.ess_discharge", 5.0),
        ("turn_on", "switch.ha_control"),
    ]
    assert ha.state_reads == ["select.sigenergy_mode"]
