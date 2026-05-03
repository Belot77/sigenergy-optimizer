"""
Additional coverage tests for telemetry_service, reason_formatter, and
runtime_utils to push toward 55%+ total coverage.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from app.config import Settings
from app.models import Decision, SolarState
from app.optimizer import SigEnergyOptimizer
from app.telemetry_service import (
    record_price_tracking,
    record_decision_trace,
    record_automation_audit,
)
from app.reason_formatter import export_reason, import_reason
from app.runtime_utils import (
    warn_parse_issue,
    is_valid_time,
    valid_hw_cap_kw,
    parse_ts,
)


class _DummyHA:
    pass


class _OptimizerFixture(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._optimizers: list[SigEnergyOptimizer] = []
        self._old_db = os.environ.get("STATE_DB_PATH")
        os.environ["STATE_DB_PATH"] = os.path.join(self._tmp.name, "state.db")

    def tearDown(self) -> None:
        for opt in self._optimizers:
            opt._state_store.close()
        if self._old_db is None:
            os.environ.pop("STATE_DB_PATH", None)
        else:
            os.environ["STATE_DB_PATH"] = self._old_db
        self._tmp.cleanup()

    def _make_optimizer(self, **cfg_overrides) -> SigEnergyOptimizer:
        cfg = Settings(**cfg_overrides)
        opt = SigEnergyOptimizer(_DummyHA(), cfg)
        self._optimizers.append(opt)
        return opt


# ---------------------------------------------------------------------------
# telemetry_service — record_price_tracking, record_decision_trace, record_automation_audit
# ---------------------------------------------------------------------------

class TestRecordPriceTracking(_OptimizerFixture):
    def test_records_when_first_call(self):
        opt = self._make_optimizer()
        s = SolarState(
            grid_import_power_kw=2.0,
            grid_export_power_kw=1.0,
            current_price=0.25,
            feedin_price=0.15,
        )
        # First call: no prior tracked state
        record_price_tracking(opt, s)
        self.assertIsNotNone(opt._last_tracked_block)
        self.assertEqual(opt._last_tracked_import_kw, 2.0)
        self.assertEqual(opt._last_tracked_export_kw, 1.0)

    def test_skips_when_no_change(self):
        opt = self._make_optimizer()
        s = SolarState(
            grid_import_power_kw=2.0,
            grid_export_power_kw=1.0,
            current_price=0.25,
            feedin_price=0.15,
        )
        # First call
        record_price_tracking(opt, s)
        tracked_block = opt._last_tracked_block
        # Second call with same state in same time block → should not record
        record_price_tracking(opt, s)
        # We can't directly verify the DB write, but we can verify the cache didn't change state
        self.assertEqual(opt._last_tracked_import_kw, 2.0)

    def test_records_on_import_change(self):
        opt = self._make_optimizer()
        s1 = SolarState(
            grid_import_power_kw=2.0,
            grid_export_power_kw=1.0,
            current_price=0.25,
            feedin_price=0.15,
        )
        record_price_tracking(opt, s1)
        old_block = opt._last_tracked_block
        # Change import by > 0.25 kW
        s2 = SolarState(
            grid_import_power_kw=3.0,
            grid_export_power_kw=1.0,
            current_price=0.25,
            feedin_price=0.15,
        )
        record_price_tracking(opt, s2)
        self.assertEqual(opt._last_tracked_import_kw, 3.0)

    def test_purge_old_at_midnight(self):
        opt = self._make_optimizer()
        s = SolarState(grid_import_power_kw=1.0, feedin_price=0.15)
        with patch("app.telemetry_service.datetime") as mock_dt:
            fixed = datetime(2026, 5, 5, 0, 5, 0, tzinfo=timezone.utc)
            mock_dt.now.return_value = fixed
            mock_dt.fromtimestamp.side_effect = lambda ts, tz=None: datetime.fromtimestamp(ts, tz=tz)
            # Mock state_store.purge_old_price_tracking
            opt._state_store.purge_old_price_tracking = MagicMock()
            record_price_tracking(opt, s)
            # Verify purge_old_price_tracking was called
            opt._state_store.purge_old_price_tracking.assert_called_once_with(retain_days=14)


class TestRecordDecisionTrace(_OptimizerFixture):
    def test_records_decision_and_state(self):
        opt = self._make_optimizer()
        s = SolarState(battery_soc=60.0, pv_kw=5.0, load_kw=1.5)
        d = Decision(ems_mode="Test Mode", export_limit=10.0, outcome_reason="test")
        record_decision_trace(opt, s, d)
        # Check the deque was populated
        self.assertEqual(len(opt._decision_trace), 1)
        trace = opt._decision_trace[0]
        self.assertEqual(trace["summary"]["ems_mode"], "Test Mode")
        self.assertEqual(trace["summary"]["export_limit_kw"], 10.0)
        self.assertEqual(trace["state"]["battery_soc"], 60.0)

    def test_handles_missing_trace_gates_and_values(self):
        opt = self._make_optimizer()
        s = SolarState()
        d = Decision()
        # Don't set trace_gates or trace_values → should default to empty dict
        record_decision_trace(opt, s, d)
        trace = opt._decision_trace[0]
        self.assertEqual(trace["gates"], {})
        self.assertEqual(trace["values"], {})


class TestRecordAutomationAudit(_OptimizerFixture):
    def test_skips_when_not_automated_mode(self):
        opt = self._make_optimizer(automated_option="Automated", manual_option="Manual")
        opt._manual_mode_override = "Manual"
        s = SolarState(sigenergy_mode="Manual")
        d = Decision(ems_mode="Mode A")
        prev = Decision(ems_mode="Mode B")
        # Should skip because effective_mode is "Manual" not "Automated"
        opt.record_audit_event = MagicMock()
        record_automation_audit(opt, s, d, prev)
        opt.record_audit_event.assert_not_called()

    def test_skips_when_no_previous_decision(self):
        opt = self._make_optimizer(automated_option="Automated")
        s = SolarState(sigenergy_mode="Automated")
        d = Decision(ems_mode="Mode A")
        opt.record_audit_event = MagicMock()
        record_automation_audit(opt, s, d, None)
        opt.record_audit_event.assert_not_called()

    def test_skips_when_no_changes(self):
        opt = self._make_optimizer(automated_option="Automated")
        s = SolarState(sigenergy_mode="Automated")
        d = Decision(ems_mode="Same Mode", export_limit=10.0)
        prev = Decision(ems_mode="Same Mode", export_limit=10.0)
        opt.record_audit_event = MagicMock()
        record_automation_audit(opt, s, d, prev)
        opt.record_audit_event.assert_not_called()

    def test_records_when_ems_mode_changes(self):
        opt = self._make_optimizer(automated_option="Automated")
        s = SolarState(sigenergy_mode="Automated")
        d = Decision(ems_mode="New Mode", export_limit=10.0)
        prev = Decision(ems_mode="Old Mode", export_limit=10.0)
        opt.record_audit_event = MagicMock()
        record_automation_audit(opt, s, d, prev)
        opt.record_audit_event.assert_called_once()

    def test_records_when_export_limit_changes(self):
        opt = self._make_optimizer(automated_option="Automated")
        s = SolarState(sigenergy_mode="Automated")
        d = Decision(ems_mode="Mode", export_limit=15.0)
        prev = Decision(ems_mode="Mode", export_limit=10.0)
        opt.record_audit_event = MagicMock()
        record_automation_audit(opt, s, d, prev)
        opt.record_audit_event.assert_called_once()


# ---------------------------------------------------------------------------
# reason_formatter — export_reason and import_reason branches
# ---------------------------------------------------------------------------

def _state(**kwargs) -> SolarState:
    defaults = dict(
        feedin_price_cents=20.0,
        feedin_price=0.20,
        current_price_cents=25.0,
        current_price=0.25,
        price_is_estimated=False,
        price_is_negative=False,
        feedin_is_negative=False,
        price_is_actual=True,
        battery_soc=60.0,
        pv_kw=5.0,
        load_kw=1.5,
        grid_export_power_kw=3.0,
    )
    defaults.update(kwargs)
    return SolarState(**defaults)


class TestExportReason(_OptimizerFixture):
    def test_negative_price_return_value(self):
        opt = self._make_optimizer()
        s = _state(price_is_negative=True, current_price_cents=-10.0)
        result = export_reason(
            opt, s, spike=False, solar_override=False, morning_dump=False,
            export_blocked=False, forecast_guard=False, export_min_soc=20.0,
            pv_safeguard=False, tier_limit=10.0, morning_slow_charge=False,
            surplus_bypass=False, evening_boost=False, safeguard=False,
            desired_export=0.0, positive_fit_override=False,
        )
        self.assertIn("negative", result)

    def test_zero_fit_return_value(self):
        opt = self._make_optimizer()
        s = _state(feedin_price_cents=0.5)
        result = export_reason(
            opt, s, spike=False, solar_override=False, morning_dump=False,
            export_blocked=False, forecast_guard=False, export_min_soc=20.0,
            pv_safeguard=False, tier_limit=10.0, morning_slow_charge=False,
            surplus_bypass=False, evening_boost=False, safeguard=False,
            desired_export=0.0, positive_fit_override=False,
        )
        self.assertIn("zero/negative", result)

    def test_safeguard_blocks_return_value(self):
        opt = self._make_optimizer(export_threshold_high=1.0)
        s = _state(feedin_price=0.25)  # Below threshold_high
        result = export_reason(
            opt, s, spike=False, solar_override=False, morning_dump=False,
            export_blocked=False, forecast_guard=False, export_min_soc=20.0,
            pv_safeguard=False, tier_limit=10.0, morning_slow_charge=False,
            surplus_bypass=False, evening_boost=False, safeguard=True,
            desired_export=10.0, positive_fit_override=False,
        )
        self.assertIn("saving for sunset", result)

    def test_high_tier_return_value(self):
        opt = self._make_optimizer(export_threshold_high=0.15)
        s = _state(feedin_price=0.20, feedin_price_cents=20.0)
        result = export_reason(
            opt, s, spike=False, solar_override=False, morning_dump=False,
            export_blocked=False, forecast_guard=False, export_min_soc=20.0,
            pv_safeguard=False, tier_limit=10.0, morning_slow_charge=False,
            surplus_bypass=False, evening_boost=False, safeguard=False,
            desired_export=10.0, positive_fit_override=False,
        )
        self.assertIn("High tier", result)

    def test_spike_return_value(self):
        opt = self._make_optimizer()
        s = _state()
        result = export_reason(
            opt, s, spike=True, solar_override=False, morning_dump=False,
            export_blocked=False, forecast_guard=False, export_min_soc=20.0,
            pv_safeguard=False, tier_limit=10.0, morning_slow_charge=False,
            surplus_bypass=False, evening_boost=False, safeguard=False,
            desired_export=10.0, positive_fit_override=False,
        )
        self.assertIn("Spike", result)

    def test_solar_override_return_value(self):
        opt = self._make_optimizer()
        s = _state(feedin_price_cents=5.0)  # Low price
        result = export_reason(
            opt, s, spike=False, solar_override=True, morning_dump=False,
            export_blocked=False, forecast_guard=False, export_min_soc=20.0,
            pv_safeguard=False, tier_limit=0.0, morning_slow_charge=False,
            surplus_bypass=False, evening_boost=False, safeguard=False,
            desired_export=10.0, positive_fit_override=False,
        )
        self.assertIn("Solar override", result)

    def test_morning_slow_charge_return_value(self):
        opt = self._make_optimizer()
        s = _state(feedin_price_cents=5.0)
        result = export_reason(
            opt, s, spike=False, solar_override=False, morning_dump=False,
            export_blocked=False, forecast_guard=False, export_min_soc=20.0,
            pv_safeguard=False, tier_limit=0.0, morning_slow_charge=True,
            surplus_bypass=False, evening_boost=False, safeguard=False,
            desired_export=10.0, positive_fit_override=False,
        )
        self.assertIn("Slow charge", result)

    def test_surplus_bypass_with_target_export(self):
        opt = self._make_optimizer(solar_surplus_start_multiplier=2.0)
        s = _state(feedin_price_cents=5.0, forecast_remaining_kwh=10.0)
        result = export_reason(
            opt, s, spike=False, solar_override=False, morning_dump=False,
            export_blocked=False, forecast_guard=False, export_min_soc=20.0,
            pv_safeguard=False, tier_limit=0.0, morning_slow_charge=False,
            surplus_bypass=True, evening_boost=False, safeguard=False,
            desired_export=5.0, positive_fit_override=False,
        )
        self.assertIn("Solar bypass", result)

    def test_surplus_bypass_waiting_measured_export_settling(self):
        opt = self._make_optimizer()
        s = _state(
            feedin_price_cents=5.0,
            forecast_remaining_kwh=10.0,
            grid_export_power_kw=5.0,  # High measured export
        )
        result = export_reason(
            opt, s, spike=False, solar_override=False, morning_dump=False,
            export_blocked=False, forecast_guard=False, export_min_soc=20.0,
            pv_safeguard=False, tier_limit=0.0, morning_slow_charge=False,
            surplus_bypass=True, evening_boost=False, safeguard=False,
            desired_export=0.0, positive_fit_override=False,
        )
        self.assertIn("settling", result)

    def test_low_forecast_block(self):
        opt = self._make_optimizer()
        s = _state()
        result = export_reason(
            opt, s, spike=False, solar_override=False, morning_dump=False,
            export_blocked=True, forecast_guard=False, export_min_soc=20.0,
            pv_safeguard=False, tier_limit=10.0, morning_slow_charge=False,
            surplus_bypass=False, evening_boost=False, safeguard=False,
            desired_export=0.0, positive_fit_override=False,
        )
        self.assertIn("low forecast", result)

    def test_battery_at_floor(self):
        opt = self._make_optimizer()
        s = _state(battery_soc=20.0)
        result = export_reason(
            opt, s, spike=False, solar_override=False, morning_dump=False,
            export_blocked=False, forecast_guard=False, export_min_soc=20.0,
            pv_safeguard=False, tier_limit=10.0, morning_slow_charge=False,
            surplus_bypass=False, evening_boost=False, safeguard=False,
            desired_export=0.0, positive_fit_override=False,
        )
        self.assertIn("20% floor", result)

    def test_below_evening_floor(self):
        opt = self._make_optimizer(evening_aggressive_floor=40.0)
        s = _state(battery_soc=35.0)
        result = export_reason(
            opt, s, spike=False, solar_override=False, morning_dump=False,
            export_blocked=False, forecast_guard=False, export_min_soc=20.0,
            pv_safeguard=False, tier_limit=10.0, morning_slow_charge=False,
            surplus_bypass=False, evening_boost=True, safeguard=False,
            desired_export=0.0, positive_fit_override=False,
        )
        self.assertIn("40% target", result)

    def test_full_battery_export(self):
        opt = self._make_optimizer()
        s = _state(battery_soc=99.0, feedin_price=0.01)
        result = export_reason(
            opt, s, spike=False, solar_override=False, morning_dump=False,
            export_blocked=False, forecast_guard=False, export_min_soc=20.0,
            pv_safeguard=False, tier_limit=10.0, morning_slow_charge=False,
            surplus_bypass=False, evening_boost=False, safeguard=False,
            desired_export=10.0, positive_fit_override=False,
        )
        self.assertIn("Full battery", result)

    def test_pv_safeguard_forecast_protection(self):
        opt = self._make_optimizer(min_export_target_soc=40.0)  # Lower floor
        s = _state(feedin_price_cents=5.0, battery_soc=50.0)  # Above 40% floor
        result = export_reason(
            opt, s, spike=False, solar_override=False, morning_dump=False,
            export_blocked=False, forecast_guard=False, export_min_soc=20.0,
            pv_safeguard=True, tier_limit=0.0, morning_slow_charge=False,
            surplus_bypass=False, evening_boost=False, safeguard=False,
            desired_export=0.0, positive_fit_override=False,
        )
        self.assertIn("forecast protection", result)

    def test_medium_tier_export(self):
        opt = self._make_optimizer(
            export_threshold_medium=0.15,
            export_threshold_high=1.0,
            min_export_target_soc=40.0,  # Lower floor
        )
        s = _state(feedin_price=0.17, feedin_price_cents=17.0, battery_soc=50.0)  # Above floor
        result = export_reason(
            opt, s, spike=False, solar_override=False, morning_dump=False,
            export_blocked=False, forecast_guard=False, export_min_soc=20.0,
            pv_safeguard=False, tier_limit=10.0, morning_slow_charge=False,
            surplus_bypass=False, evening_boost=False, safeguard=False,
            desired_export=10.0, positive_fit_override=False,
        )
        self.assertIn("Med tier", result)


class TestImportReason(_OptimizerFixture):
    def test_morning_dump_blocks_import(self):
        opt = self._make_optimizer()
        s = _state()
        result = import_reason(
            opt, s, morning_dump=True, standby_holdoff=False,
            sunrise_soc_target=30.0, desired_import=0.0, pv_surplus=0.0,
        )
        self.assertIn("morning dump", result)

    def test_demand_window_blocks_import(self):
        opt = self._make_optimizer()
        s = _state(demand_window_active=True)
        result = import_reason(
            opt, s, morning_dump=False, standby_holdoff=False,
            sunrise_soc_target=30.0, desired_import=0.0, pv_surplus=0.0,
        )
        self.assertIn("demand window", result)

    def test_standby_holdoff_blocks_import(self):
        opt = self._make_optimizer()
        s = _state()
        result = import_reason(
            opt, s, morning_dump=False, standby_holdoff=True,
            sunrise_soc_target=30.0, desired_import=0.0, pv_surplus=0.0,
        )
        self.assertIn("holdoff", result)

    def test_paid_price_import(self):
        opt = self._make_optimizer()
        s = _state(current_price=-0.10, current_price_cents=-10.0, price_is_actual=True)
        result = import_reason(
            opt, s, morning_dump=False, standby_holdoff=False,
            sunrise_soc_target=30.0, desired_import=10.0, pv_surplus=0.0,
        )
        self.assertIn("paid price", result)

    def test_free_import(self):
        opt = self._make_optimizer()
        s = _state(current_price=0.0, current_price_cents=0.0, price_is_actual=True)
        result = import_reason(
            opt, s, morning_dump=False, standby_holdoff=False,
            sunrise_soc_target=30.0, desired_import=10.0, pv_surplus=0.0,
        )
        self.assertIn("FREE", result)

    def test_high_price_blocks_import(self):
        # feedin_price < threshold_low, battery above sunrise target, price too high
        opt = self._make_optimizer(max_price_threshold=0.20, export_threshold_low=0.10)
        s = _state(
            current_price=0.30,
            feedin_price=0.05,  # Low FIT, won't trigger FIT block
            battery_soc=35.0,
            price_is_actual=True,
        )
        result = import_reason(
            opt, s, morning_dump=False, standby_holdoff=False,
            sunrise_soc_target=30.0, desired_import=0.0, pv_surplus=0.0,
        )
        self.assertIn("price too high", result)

    def test_battery_full_blocks_import(self):
        opt = self._make_optimizer(
            daytime_topup_max_soc=95.0,
            export_threshold_low=0.10,
            max_price_threshold=0.20,
        )
        s = _state(
            battery_soc=95.0,
            feedin_price=0.05,  # Below threshold_low
            current_price=0.10,  # Below max_price_threshold
            price_is_actual=True,
        )
        result = import_reason(
            opt, s, morning_dump=False, standby_holdoff=False,
            sunrise_soc_target=30.0, desired_import=0.0, pv_surplus=0.0,
        )
        self.assertIn("battery full", result)

    def test_pv_sufficient_blocks_import(self):
        opt = self._make_optimizer(
            target_battery_charge=2.0,
            export_threshold_low=0.10,
            max_price_threshold=0.20,
            daytime_topup_max_soc=60.0,
        )
        s = _state(
            feedin_price=0.05,  # Below threshold_low
            current_price=0.10,  # Below max_price_threshold
            price_is_actual=True,
            battery_soc=45.0,  # Below daytime_topup_max_soc
        )
        result = import_reason(
            opt, s, morning_dump=False, standby_holdoff=False,
            sunrise_soc_target=30.0, desired_import=0.0, pv_surplus=3.0,
        )
        self.assertIn("PV sufficient", result)

    def test_forecast_sufficient_blocks_import(self):
        opt = self._make_optimizer(
            export_threshold_low=0.10,
            max_price_threshold=0.20,
            daytime_topup_max_soc=60.0,
        )
        s = _state(
            feedin_price=0.05,  # Below threshold_low
            current_price=0.10,  # Below max_price_threshold
            price_is_actual=True,
            battery_soc=45.0,  # Below daytime_topup_max_soc
        )
        result = import_reason(
            opt, s, morning_dump=False, standby_holdoff=False,
            sunrise_soc_target=30.0, desired_import=0.0, pv_surplus=0.5,
        )
        self.assertIn("forecast sufficient", result)

    def test_cheap_import(self):
        opt = self._make_optimizer(
            export_threshold_low=0.10,
            max_price_threshold=0.20,
        )
        s = _state(
            current_price=0.05,
            current_price_cents=5.0,
            feedin_price=0.05,  # Below threshold_low
            price_is_actual=True,
            price_is_negative=False,
            battery_soc=50.0,
        )
        result = import_reason(
            opt, s, morning_dump=False, standby_holdoff=False,
            sunrise_soc_target=30.0, desired_import=10.0, pv_surplus=0.0,
        )
        self.assertIn("cheap", result)


# ---------------------------------------------------------------------------
# runtime_utils — warn_parse_issue, is_valid_time, valid_hw_cap_kw, parse_ts
# ---------------------------------------------------------------------------

class TestWarnParseIssue(_OptimizerFixture):
    def test_logs_warning_on_first_call(self):
        opt = self._make_optimizer()
        with patch("app.runtime_utils.logger") as mock_logger:
            warn_parse_issue(opt, "sensor.foo", "bad_value", "Test")
            mock_logger.warning.assert_called_once()

    def test_cache_entry_created(self):
        opt = self._make_optimizer()
        warn_parse_issue(opt, "sensor.foo", "bad_value", "Test")
        # Verify cache was populated
        self.assertIn(("sensor.foo", "bad_value"), opt._sensor_parse_warning_cache)


class TestIsValidTime(unittest.TestCase):
    def test_valid_hm_format(self):
        self.assertTrue(is_valid_time("08:30"))
        self.assertTrue(is_valid_time("23:59"))
        self.assertTrue(is_valid_time("00:00"))

    def test_valid_hms_format(self):
        self.assertTrue(is_valid_time("08:30:45"))
        self.assertTrue(is_valid_time("23:59:59"))

    def test_invalid_hour(self):
        self.assertFalse(is_valid_time("24:00"))
        self.assertFalse(is_valid_time("25:30"))

    def test_invalid_minute(self):
        self.assertFalse(is_valid_time("12:60"))
        self.assertFalse(is_valid_time("12:70"))

    def test_invalid_second(self):
        self.assertFalse(is_valid_time("12:30:60"))
        self.assertFalse(is_valid_time("12:30:99"))

    def test_invalid_format(self):
        self.assertFalse(is_valid_time("not_a_time"))
        self.assertFalse(is_valid_time("12"))
        self.assertFalse(is_valid_time(""))


class TestValidHwCapKw(unittest.TestCase):
    def test_valid_float_in_range(self):
        self.assertTrue(valid_hw_cap_kw(10.5))
        self.assertTrue(valid_hw_cap_kw(1.0))
        self.assertTrue(valid_hw_cap_kw(500.0))

    def test_valid_int_in_range(self):
        self.assertTrue(valid_hw_cap_kw(10))
        self.assertTrue(valid_hw_cap_kw(500))

    def test_zero_invalid(self):
        self.assertFalse(valid_hw_cap_kw(0.0))
        self.assertFalse(valid_hw_cap_kw(0))

    def test_negative_invalid(self):
        self.assertFalse(valid_hw_cap_kw(-5.0))

    def test_too_large_invalid(self):
        self.assertFalse(valid_hw_cap_kw(999.0))
        self.assertFalse(valid_hw_cap_kw(1000.0))

    def test_non_numeric_invalid(self):
        self.assertFalse(valid_hw_cap_kw("10"))
        self.assertFalse(valid_hw_cap_kw(None))


class TestParseTs(unittest.TestCase):
    def test_parse_float_timestamp(self):
        result = parse_ts(1234567890.0)
        self.assertEqual(result, 1234567890.0)

    def test_parse_iso_format(self):
        result = parse_ts("2026-05-04T12:30:45+00:00")
        self.assertIsNotNone(result)
        self.assertIsInstance(result, float)

    def test_parse_iso_format_with_z(self):
        result = parse_ts("2026-05-04T12:30:45Z")
        self.assertIsNotNone(result)

    def test_parse_none_returns_none(self):
        self.assertIsNone(parse_ts(None))

    def test_parse_empty_string_returns_none(self):
        self.assertIsNone(parse_ts(""))

    def test_parse_invalid_string_returns_none(self):
        result = parse_ts("not a timestamp")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
