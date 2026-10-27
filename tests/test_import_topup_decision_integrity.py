"""Real tick/decision O16 checks with synthetic reads and mocked application outcomes."""
from __future__ import annotations

import asyncio
from contextlib import ExitStack
from datetime import datetime, timedelta
import sqlite3
from unittest.mock import AsyncMock, patch

import pytest

from app.import_topup_ledger import ImportTopupLedger
from app.models import BATTERY_EXPORT, Decision
from app.optimizer import MODE_MAX_SELF, _ActuatorApplicationResult
from import_topup_coverage_helpers import seed_complete_import_history
import test_four_tier_battery_export as tier_fixtures
from test_import_topup_interval_store import FaultConnection


@pytest.fixture
def context():
    case = tier_fixtures.FourTierDecisionTests()
    case.setUp()
    try:
        optimizer = case.optimizer(max_battery_soc=100)
        when = case.FIXED_AFTERNOON
        seed_complete_import_history(optimizer, when - timedelta(minutes=2))
        yield case, optimizer, when
    finally:
        case.tearDown()


def measured(case, when, *, total, price, **changes):
    state = case.tier_state(
        fit=0.30, current_price=price, current_price_cents=price * 100,
        daily_import_kwh=total, daily_import_meter_value=total,
        battery_capacity_trusted=True, **changes,
    )
    state.timestamp = when
    return state


def tick(case, optimizer, state, when, result):
    seen = []

    async def apply(_state, decision):
        seen.append(decision)
        return result

    with ExitStack() as stack:
        stack.enter_context(case.optimizer_time(when))
        stack.enter_context(patch.object(optimizer, "_read_state", AsyncMock(return_value=state)))
        stack.enter_context(patch.object(optimizer, "_apply", apply))
        stack.enter_context(patch.object(optimizer, "_evaluate_hvac_solar_permission", return_value=None))
        for name in ("_publish_hvac_solar_permission", "_handle_notifications", "_handle_daily_summaries"):
            stack.enter_context(patch.object(optimizer, name, AsyncMock(return_value=True)))
        for name in ("_record_application_trace", "_record_automation_audit", "_accumulate_history", "_record_price_tracking"):
            stack.enter_context(patch.object(optimizer, name))
        asyncio.run(optimizer._tick())
    return seen[0]


def prime_import(case, optimizer, when):
    ledger = optimizer._import_topup_ledger
    start = when - timedelta(minutes=2)
    optimizer._record_optimizer_import_topup(measured(case, start, total=10, price=0.05), Decision(import_limit=0), start)
    ledger.set_permission(now=datetime.fromtimestamp(start.timestamp(), tz=optimizer._tz),
                          source=optimizer._import_topup_source(), import_active=True)
    middle = when - timedelta(minutes=1)
    optimizer._record_optimizer_import_topup(measured(case, middle, total=11, price=0.05), None, middle)
    assert ledger.import_active


@pytest.mark.parametrize("fault", [None, "insert", "commit-before", "commit-after"])
def test_final_expensive_import_is_accounted_before_real_export_arbitration(context, fault):
    case, optimizer, when = context
    prime_import(case, optimizer, when)
    if fault:
        optimizer._state_store._conn = FaultConnection(optimizer._state_store._conn, fault)
    decision = tick(case, optimizer, measured(case, when, total=12, price=0.40), when,
                    _ActuatorApplicationResult(succeeded=True, automatic_application_completed=True))
    if fault in {"insert", "commit-before"}:
        # The failed 40c write is retained for exact retry, but this decision
        # can only enforce the already acknowledged 5c price. Coverage warns.
        assert decision.trace_gates["import_cost_floor_unknown"]
        assert not decision.trace_gates["actual_import_cost_guard_blocking"]
        assert decision.export_intent == BATTERY_EXPORT
        later = when + timedelta(seconds=10)
        decision = tick(case, optimizer, measured(case, later, total=12, price=0.40), later,
                        _ActuatorApplicationResult(succeeded=True, automatic_application_completed=True))
        assert decision.trace_gates["actual_import_cost_guard_blocking"]
    assert decision.export_intent != BATTERY_EXPORT
    assert decision.export_limit == 0.0
    assert not decision.trace_values["battery_export_actual_import_cost_permitted"]
    summary = optimizer._state_store.optimizer_import_topup_summary(when.date().isoformat())
    assert summary["today_import_topup_kwh"] == 2.0
    assert summary["today_highest_actual_import_price"] == 0.40


def test_import_tail_seen_after_close_affects_next_real_decision_once(context):
    case, optimizer, when = context
    prime_import(case, optimizer, when)
    completed = _ActuatorApplicationResult(succeeded=True, automatic_application_completed=True)
    tick(case, optimizer, measured(case, when, total=11, price=0.40), when, completed)
    # The first close command follows its measurement. Import until that close
    # appears only in the subsequent read and must retain its own price.
    later = when + timedelta(seconds=10)
    decision = tick(case, optimizer, measured(case, later, total=11.1, price=0.40), later, completed)
    assert decision.export_intent != BATTERY_EXPORT
    summary = optimizer._state_store.optimizer_import_topup_summary(when.date().isoformat())
    assert summary["today_import_topup_kwh"] == 1.1
    assert summary["today_highest_actual_import_price"] == 0.40
    assert not optimizer._import_topup_ledger.import_active


@pytest.mark.parametrize("outcome", ["failure", "pending", "noop-success"])
def test_unconfirmed_or_noop_application_cannot_prove_next_inactive_day(context, outcome):
    case, optimizer, _ = context
    when = datetime(2026, 1, 15, 23, 59, 59, tzinfo=optimizer._tz)
    seed_complete_import_history(optimizer, when)
    state = measured(case, when, total=0, price=0.4)
    result = _ActuatorApplicationResult(
        succeeded=outcome == "noop-success", transition_pending=outcome == "pending",
        automatic_transition_pending=outcome == "pending", error="synthetic unconfirmed application",
    )
    if outcome == "noop-success":
        tick(case, optimizer, state, when, result)
    else:
        with pytest.raises(RuntimeError):
            tick(case, optimizer, state, when, result)
    ledger = optimizer._import_topup_ledger
    assert not ledger.permission_known
    following = when + timedelta(seconds=1)
    optimizer._record_optimizer_import_topup(measured(case, following, total=0, price=0.4), None, following)
    assert optimizer._state_store.optimizer_import_topup_summary(following.date().isoformat())["import_cost_floor_unknown"]


def test_observed_manual_import_remains_in_later_automatic_cost_floor(context):
    case, optimizer, when = context
    start = when - timedelta(minutes=2)
    optimizer._record_optimizer_import_topup(measured(case, start, total=10, price=0.05), Decision(import_limit=0), start)
    manual_when = when - timedelta(minutes=1)
    manual = measured(case, manual_when, total=11, price=0.40,
                      sigenergy_mode=optimizer.cfg.manual_option, current_import_limit=4.0)
    manual_decision = tick(case, optimizer, manual, manual_when, _ActuatorApplicationResult(succeeded=True))
    assert not manual_decision.trace_gates["actual_import_cost_guard_active"]
    decision = tick(case, optimizer, measured(case, when, total=12, price=0.05), when,
                    _ActuatorApplicationResult(succeeded=True, automatic_application_completed=True))
    assert decision.export_intent != BATTERY_EXPORT
    assert not decision.trace_values["battery_export_actual_import_cost_permitted"]
    assert optimizer._state_store.optimizer_import_topup_summary(when.date().isoformat())["today_highest_actual_import_price"] == 0.40


def test_unretained_snapshot_failure_before_decision_cannot_leave_trusted_floor(context):
    case, optimizer, when = context
    prime_import(case, optimizer, when)
    with patch.object(optimizer._import_topup_ledger, "_persist_interval", side_effect=ValueError("synthetic capture failure")):
        decision = tick(case, optimizer, measured(case, when, total=12, price=0.40), when,
                        _ActuatorApplicationResult(succeeded=True, automatic_application_completed=True))
    assert decision.trace_gates["import_cost_floor_unknown"]
    assert not decision.trace_gates["actual_import_cost_guard_blocking"]
    assert decision.export_intent == BATTERY_EXPORT
    with case.optimizer_time(when):
        assert optimizer._optimizer_import_topup_summary_today()["import_cost_floor_unknown"]
    # The next retained measurement identifies the 40c interval; its finite
    # price must bind even though this day's coverage stays unknown.
    later = when + timedelta(seconds=10)
    after = tick(case, optimizer, measured(case, later, total=13, price=0.40), later,
                 _ActuatorApplicationResult(succeeded=True, automatic_application_completed=True))
    assert after.trace_gates["import_cost_floor_unknown"]
    assert after.trace_gates["actual_import_cost_guard_blocking"]
    assert after.export_intent != BATTERY_EXPORT
    assert optimizer._state_store.optimizer_import_topup_summary(
        later.date().isoformat())["today_highest_actual_import_price"] == 0.40
