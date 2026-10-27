"""Policy boundary: incomplete cost history warns but known priced imports bind.

These are synthetic decisions, not inverter settlement or financial outcomes.
The ledger is deliberately unchanged; its unknown flag remains diagnostic truth.
"""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from app.config import Settings
from app.models import BATTERY_EXPORT, EXPORT_BLOCKED
from app.optimizer import MODE_CMD_DISCHARGE_PV, MODE_MAX_SELF
import test_four_tier_battery_export as tier_fixtures


@pytest.fixture
def case():
    environment = patch.dict(os.environ, {}, clear=True)
    environment.start()
    fixture = tier_fixtures.FourTierDecisionTests()
    fixture.setUp()  # installs a temporary STATE_DB_PATH after clearing env
    try:
        # The shared fixture seeds a complete synthetic cost history. Explicitly
        # disable any repository/user .env while constructing its Settings.
        with patch("haos49_characterization_helpers.Settings",
                   side_effect=lambda **kw: Settings(_env_file=None, **kw)):
            yield fixture
    finally:
        fixture.tearDown()
        environment.stop()


def decide(case, summary, *, fit=1.10, soc=70.0, **settings):
    optimizer = case.optimizer(max_battery_soc=100, **settings)
    state = case.tier_state(
        fit=fit, soc=soc, battery_capacity_trusted=True,
        forecast_remaining_observation_trusted=True,
    )
    with patch.object(optimizer, "_optimizer_import_topup_summary_today", return_value=summary):
        decision = case.decide(optimizer, state, case.FIXED_AFTERNOON)
    return decision


@pytest.mark.parametrize("known_floor,fit,permitted", [
    (None, 1.10, True),       # unknown coverage alone is advisory
    (0.0, 1.10, True),        # zero is a real priced floor
    (-0.10, 1.10, True),      # negative is a real priced floor
    (0.40, 1.10, True),       # partial history still compares known prices
    (1.10, 1.10, True),       # equality meets the existing floor
    (1.20, 1.10, False),      # known price binds despite unknown coverage
])
def test_unknown_history_keeps_known_price_floor_and_warning(case, known_floor, fit, permitted):
    summary = {
        "import_cost_floor_unknown": True,
        "import_cost_floor_trusted": False,
        "import_history_complete": False,
        "import_history_reason": "application_not_confirmed",
        "today_import_topup_kwh": 0.0,
        "today_highest_actual_import_price": known_floor,
    }
    d = decide(case, summary, fit=fit)
    assert d.trace_gates["import_cost_floor_unknown"]
    assert d.trace_gates["actual_import_cost_guard_active"]
    assert d.trace_values["today_highest_actual_import_price"] == known_floor
    assert d.trace_values["battery_export_actual_import_cost_permitted"] is permitted
    assert d.trace_gates["actual_import_cost_guard_blocking"] is (not permitted)
    assert "warning" in d.trace_values["actual_import_cost_guard_reason"].lower()
    if permitted:
        assert d.export_intent == BATTERY_EXPORT
        assert d.trace_values["battery_export_final_owner"] == "high_price"
        assert d.ems_mode == MODE_CMD_DISCHARGE_PV
        assert d.export_limit > 0.01
    else:
        assert d.export_intent == EXPORT_BLOCKED
        assert d.trace_values["battery_export_final_owner"] == "none"
        assert d.ems_mode == MODE_MAX_SELF
        assert d.export_limit == 0.0


@pytest.mark.parametrize("reason", ["observation_gap_or_clock_change", "untrusted_import_price"])
def test_unknown_reason_does_not_create_an_economic_veto(case, reason):
    d = decide(case, {
        "import_cost_floor_unknown": True,
        "import_history_complete": False,
        "import_history_reason": reason,
        "today_highest_actual_import_price": None,
    })
    assert d.trace_gates["import_cost_floor_unknown"]
    assert d.trace_gates["actual_import_cost_guard_active"]
    assert not d.trace_gates["actual_import_cost_guard_blocking"]
    assert d.export_intent == BATTERY_EXPORT


@pytest.mark.parametrize("malformed", [float("nan"), float("inf"), "invalid"])
def test_unknown_with_nonfinite_or_malformed_price_has_no_false_known_floor(case, malformed):
    # Store-produced prices are finite; this protects the decision boundary if
    # a partial/unavailable accounting summary ever supplies malformed data.
    d = decide(case, {
        "import_cost_floor_unknown": True,
        "import_history_complete": False,
        "import_history_reason": "history_unavailable",
        "today_highest_actual_import_price": malformed,
    })
    assert d.trace_gates["import_cost_floor_unknown"]
    assert d.trace_gates["actual_import_cost_guard_active"]
    assert not d.trace_gates["actual_import_cost_guard_blocking"]
    assert "warning" in d.trace_values["actual_import_cost_guard_reason"].lower()
    assert d.export_intent == BATTERY_EXPORT


def test_unknown_without_known_price_does_not_block_qualified_high_morning_preemption(case):
    d = decide(case, {
        "import_cost_floor_unknown": True,
        "today_highest_actual_import_price": None,
    }, morning_slow_charge_enabled=True, morning_slow_charge_until="16:00",
       morning_slow_charge_rate_kw=3.7)
    assert d.trace_values["morning_preemption_requested"]
    assert d.trace_values["morning_preempted"]
    assert d.export_intent == BATTERY_EXPORT
    assert d.trace_values["battery_export_final_owner"] == "high_price"


def test_unknown_does_not_override_independent_price_or_reserve_gate(case):
    summary = {"import_cost_floor_unknown": True, "today_highest_actual_import_price": None}
    below_one_cent = decide(case, summary, fit=0.0)
    assert below_one_cent.export_intent != BATTERY_EXPORT
    at_floor = decide(case, summary, soc=20.0)
    assert at_floor.export_intent != BATTERY_EXPORT
    assert not at_floor.trace_values["morning_preempted"]


def test_value_gate_advisory_does_not_report_unknown_as_cost_veto(case):
    d = decide(case, {
        "import_cost_floor_unknown": True,
        "today_highest_actual_import_price": None,
    }, export_value_gate_enabled=True, export_value_gate_dry_run=True,
       export_value_gate_enforce=True)
    assert d.trace_gates["import_cost_floor_unknown"]
    assert d.trace_values["export_value_gate_block_reason"] != "import_cost_floor_untrusted"
    assert not d.trace_gates["export_value_gate_enforcement_active"]
    assert d.export_intent == BATTERY_EXPORT
