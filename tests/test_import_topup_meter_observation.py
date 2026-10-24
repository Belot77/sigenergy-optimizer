from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

import pytest

from app.import_topup_ledger import ImportTopupLedger
from app.optimizer import MODE_MAX_SELF
from test_control_authority_safety_characterization import _Rig


@pytest.fixture
def rig():
    value = _Rig()
    value.clock.now = datetime.fromtimestamp(
        value.case.FIXED_AFTERNOON.timestamp(), timezone.utc,
    )
    value.automated()
    try:
        yield value
    finally:
        value.case.tearDown()


def _capture_and_summarize(rig, state):
    async def capture():
        now = rig.clock.now.astimezone(rig.opt._tz)
        rig.opt._record_optimizer_import_topup(state, None, now)
        return rig.opt._optimizer_import_topup_summary_today()

    return rig.clock.run(capture())


@pytest.mark.parametrize(
    "reading",
    [
        pytest.param(None, id="missing-entity"),
        pytest.param("unavailable", id="unavailable"),
        pytest.param("unknown", id="unknown"),
        pytest.param("nan", id="nan"),
        pytest.param("inf", id="infinity"),
    ],
)
def test_invalid_daily_import_meter_read_is_unknown_not_zero(rig, reading):
    entity = rig.opt.cfg.daily_import_energy
    if reading is not None:
        rig.ha.observe(entity, reading)

    state = rig.read()

    assert state.daily_import_kwh == 0.0
    assert state.daily_import_meter_value is None
    summary = _capture_and_summarize(rig, state)
    assert summary["import_cost_export_floor"] is None
    assert summary["import_cost_floor_unknown"] is True
    assert summary["import_cost_floor_trusted"] is False
    assert summary["import_history_complete"] is False
    assert summary["import_history_reason"] == "import_counter_unavailable"


def test_valid_zero_daily_import_meter_preserves_complete_history(rig):
    rig.ha.observe(rig.opt.cfg.daily_import_energy, "0")

    state = rig.read()

    assert state.daily_import_kwh == 0.0
    assert state.daily_import_meter_value == 0.0
    summary = _capture_and_summarize(rig, state)
    assert summary["import_history_complete"] is True
    assert summary["import_cost_floor_unknown"] is False
    assert summary["import_cost_floor_trusted"] is True


def test_missing_meter_at_midnight_cannot_complete_new_day_coverage(rig):
    optimizer = rig.opt
    source = optimizer._import_topup_source()
    accounting_now = rig.clock.now.astimezone(optimizer._tz)
    midnight = datetime.combine(
        accounting_now.date() + timedelta(days=1),
        time.min,
        tzinfo=optimizer._tz,
    )
    before_midnight = midnight - timedelta(seconds=1)
    ledger = ImportTopupLedger(
        optimizer._state_store,
        started_at=before_midnight,
        source=source,
    )
    optimizer._import_topup_ledger = ledger

    before_state = rig.case.state(
        before_midnight.replace(tzinfo=None),
        daily_import_kwh=0.0,
        daily_import_meter_value=0.0,
        grid_import_power_kw=0.0,
    )
    optimizer._record_optimizer_import_topup(
        before_state,
        rig.decision(ems_mode=MODE_MAX_SELF, import_limit=0.0),
        before_midnight,
    )

    rig.clock.now = midnight.astimezone(timezone.utc)
    entity = optimizer.cfg.daily_import_energy
    rig.ha.reports.pop(entity, None)
    rig.ha.metadata.pop(entity, None)
    after_state = rig.read()

    assert after_state.daily_import_kwh == 0.0
    assert after_state.daily_import_meter_value is None
    summary = _capture_and_summarize(rig, after_state)
    assert summary["import_history_complete"] is False
    assert summary["import_cost_floor_unknown"] is True
    assert summary["import_cost_floor_trusted"] is False
    assert summary["import_history_reason"] == "import_counter_unavailable"
