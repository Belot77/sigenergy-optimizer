"""
Unit tests for the modules extracted during the modular refactor:
  - runtime_utils (pure functions)
  - reason_formatter (export_reason / import_reason)
  - limit_calculator (export_tier_limit / desired_export_limit)
  - time_forecast_service (today_at, day_window, battery_soc_required_to_sunrise, parse_ts)
"""
from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from app.config import Settings
from app.models import SolarState
from app.optimizer import SigEnergyOptimizer
from app.runtime_utils import is_valid_time, parse_ts, valid_hw_cap_kw
from app.reason_formatter import export_reason, import_reason
from app.limit_calculator import export_tier_limit
from app.time_forecast_service import today_at, day_window, battery_soc_required_to_sunrise


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

class _DummyHA:
    pass


class _OptimizerFixture(unittest.TestCase):
    """Base class that creates a real SigEnergyOptimizer against a temp DB."""

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
# runtime_utils — pure functions, no optimizer needed
# ---------------------------------------------------------------------------

class TestIsValidTime(unittest.TestCase):
    def test_valid_hhmm(self):
        self.assertTrue(is_valid_time("07:30"))
        self.assertTrue(is_valid_time("00:00"))
        self.assertTrue(is_valid_time("23:59"))

    def test_valid_hhmmss(self):
        self.assertTrue(is_valid_time("07:30:00"))
        self.assertTrue(is_valid_time("23:59:59"))

    def test_invalid_out_of_range(self):
        self.assertFalse(is_valid_time("24:00"))
        self.assertFalse(is_valid_time("07:60"))
        self.assertFalse(is_valid_time("07:30:60"))

    def test_invalid_format(self):
        self.assertFalse(is_valid_time(""))
        self.assertFalse(is_valid_time("730"))
        self.assertFalse(is_valid_time("07-30"))
        self.assertFalse(is_valid_time("not_a_time"))
        self.assertFalse(is_valid_time(None))


class TestValidHwCapKw(unittest.TestCase):
    def test_valid_positive_floats(self):
        self.assertTrue(valid_hw_cap_kw(10.0))
        self.assertTrue(valid_hw_cap_kw(1))
        self.assertTrue(valid_hw_cap_kw(0.5))

    def test_invalid_zero_negative_and_nonnumeric(self):
        self.assertFalse(valid_hw_cap_kw(0))
        self.assertFalse(valid_hw_cap_kw(-1.0))
        self.assertFalse(valid_hw_cap_kw(None))
        self.assertFalse(valid_hw_cap_kw("10"))
        self.assertFalse(valid_hw_cap_kw(float("nan")))
        self.assertFalse(valid_hw_cap_kw(999))   # >= 999 is invalid sentinel


class TestParseTs(unittest.TestCase):
    def test_numeric_string(self):
        self.assertAlmostEqual(parse_ts("1714800000"), 1714800000.0)

    def test_numeric_float(self):
        self.assertAlmostEqual(parse_ts(1714800000.0), 1714800000.0)

    def test_iso_string(self):
        result = parse_ts("2026-05-04T12:00:00+00:00")
        expected = datetime(2026, 5, 4, 12, 0, 0, tzinfo=timezone.utc).timestamp()
        self.assertAlmostEqual(result, expected, places=0)

    def test_iso_z_suffix(self):
        result = parse_ts("2026-05-04T12:00:00Z")
        expected = datetime(2026, 5, 4, 12, 0, 0, tzinfo=timezone.utc).timestamp()
        self.assertAlmostEqual(result, expected, places=0)

    def test_none_and_empty(self):
        self.assertIsNone(parse_ts(None))
        self.assertIsNone(parse_ts(""))
        self.assertIsNone(parse_ts(0))

    def test_garbage_returns_none(self):
        self.assertIsNone(parse_ts("not-a-timestamp"))


# ---------------------------------------------------------------------------
# reason_formatter — export_reason / import_reason
# ---------------------------------------------------------------------------

def _make_reason_state(**kwargs) -> SolarState:
    defaults = dict(
        battery_soc=50.0,
        feedin_price=0.15,
        feedin_price_cents=15.0,
        current_price_cents=25.0,
        current_price=0.25,
        pv_kw=5.0,
        load_kw=1.5,
        grid_export_power_kw=3.5,
        forecast_remaining_kwh=10.0,
        price_is_negative=False,
        feedin_is_negative=False,
        price_is_estimated=False,
    )
    defaults.update(kwargs)
    return SolarState(**defaults)


class TestExportReason(_OptimizerFixture):
    def _reason(self, s: SolarState, **flags) -> str:
        opt = self._make_optimizer()
        defaults = dict(
            spike=False,
            solar_override=False,
            morning_dump=False,
            export_blocked=False,
            forecast_guard=False,
            export_min_soc=20.0,
            pv_safeguard=False,
            tier_limit=12.0,
            morning_slow_charge=False,
            surplus_bypass=False,
            evening_boost=False,
            safeguard=False,
            desired_export=10.0,
            positive_fit_override=False,
        )
        defaults.update(flags)
        return export_reason(opt, s, **defaults)

    def test_negative_price_takes_priority(self):
        s = _make_reason_state(price_is_negative=True)
        result = self._reason(s)
        self.assertIn("negative", result)

    def test_zero_fit_blocks_export(self):
        s = _make_reason_state(feedin_price_cents=0.5)
        result = self._reason(s)
        self.assertIn("zero/negative", result)

    def test_spike_reason(self):
        s = _make_reason_state()
        result = self._reason(s, spike=True)
        self.assertIn("Spike", result)

    def test_high_tier_reason(self):
        s = _make_reason_state(feedin_price=1.5, feedin_price_cents=150.0)
        result = self._reason(s)
        self.assertIn("High tier", result)

    def test_medium_tier_reason(self):
        # Must have soc >= min_export_target_soc (90) to reach the tier check
        s = _make_reason_state(feedin_price=0.25, feedin_price_cents=25.0, battery_soc=95.0)
        result = self._reason(s)
        self.assertIn("Med tier", result)

    def test_morning_dump_reason(self):
        s = _make_reason_state()
        result = self._reason(s, morning_dump=True)
        self.assertIn("Morning dump", result)

    def test_low_forecast_block(self):
        s = _make_reason_state()
        result = self._reason(s, export_blocked=True, tier_limit=5.0)
        self.assertIn("low forecast", result)

    def test_soc_floor_block(self):
        s = _make_reason_state(battery_soc=15.0)
        result = self._reason(s, export_min_soc=20.0)
        self.assertIn("floor", result)

    def test_solar_override_reason(self):
        s = _make_reason_state()
        result = self._reason(s, solar_override=True)
        self.assertIn("Solar override", result)


class TestImportReason(_OptimizerFixture):
    def _reason(self, s: SolarState, **flags) -> str:
        opt = self._make_optimizer()
        defaults = dict(
            morning_dump=False,
            standby_holdoff=False,
            sunrise_soc_target=30.0,
            desired_import=15.0,
            pv_surplus=0.0,
        )
        defaults.update(flags)
        return import_reason(opt, s, **defaults)

    def test_morning_dump_blocks_import(self):
        s = _make_reason_state()
        result = self._reason(s, morning_dump=True)
        self.assertIn("dump", result.lower())

    def test_standby_holdoff_blocks_import(self):
        s = _make_reason_state()
        result = self._reason(s, standby_holdoff=True)
        self.assertIn("holdoff", result.lower())

    def test_high_price_blocks_import(self):
        s = _make_reason_state(current_price=0.50, current_price_cents=50.0)
        result = self._reason(s, desired_import=0.0)
        self.assertIn("price", result.lower())

    def test_pv_surplus_suppresses_import(self):
        # price_is_actual=True; feedin < export_threshold_low; current_price <= max_price_threshold
        # so we reach the pv_surplus branch
        s = _make_reason_state(
            battery_soc=40.0,
            price_is_actual=True,
            feedin_price=0.0,
            feedin_price_cents=0.0,
            current_price=0.01,
            current_price_cents=1.0,
        )
        result = self._reason(s, pv_surplus=3.0, desired_import=0.0)
        self.assertIn("PV", result)


# ---------------------------------------------------------------------------
# limit_calculator — export_tier_limit
# ---------------------------------------------------------------------------

class TestExportTierLimit(_OptimizerFixture):
    def _tier(self, feedin_price: float, battery_soc: float = 60.0, **flags) -> float:
        opt = self._make_optimizer(
            export_threshold_low=0.10,
            export_threshold_medium=0.20,
            export_threshold_high=1.00,
            export_limit_low=5.0,
            export_limit_medium=12.0,
            export_limit_high=25.0,
            evening_aggressive_floor=35.0,
            min_export_target_soc=90.0,
        )
        s = SolarState(feedin_price=feedin_price, battery_soc=battery_soc)
        defaults = dict(spike=False, solar_override=False, pv_safeguard=False, boost=False, surplus_bypass=False)
        defaults.update(flags)
        return export_tier_limit(opt, s, **defaults)

    def test_below_low_threshold_returns_zero(self):
        self.assertEqual(self._tier(0.05), 0.0)

    def test_spike_returns_high_limit(self):
        self.assertEqual(self._tier(0.05, spike=True), 25.0)

    def test_solar_override_returns_high_limit(self):
        self.assertEqual(self._tier(0.05, solar_override=True), 25.0)

    def test_high_threshold_returns_high_limit(self):
        self.assertEqual(self._tier(1.50), 25.0)

    def test_medium_tier_interpolates(self):
        # feedin = 0.20 (exactly at medium threshold) → result at or above export_limit_medium
        result = self._tier(0.20)
        self.assertGreaterEqual(result, 12.0)
        self.assertLessEqual(result, 25.0)

    def test_below_target_soc_without_surplus_bypass_returns_zero(self):
        # battery_soc=80 < min_export_target_soc=90, no bypass
        result = self._tier(0.15, battery_soc=80.0)
        self.assertEqual(result, 0.0)

    def test_full_battery_returns_high_limit(self):
        # bsoc >= 99 and feedin > 0.01 → high limit
        result = self._tier(0.15, battery_soc=99.5)
        self.assertEqual(result, 25.0)

    def test_pv_safeguard_blocks_medium_tier(self):
        result = self._tier(0.50, pv_safeguard=True)
        self.assertEqual(result, 0.0)


# ---------------------------------------------------------------------------
# time_forecast_service — today_at, day_window, battery_soc_required_to_sunrise
# ---------------------------------------------------------------------------

class TestTodayAt(_OptimizerFixture):
    def test_returns_today_with_given_hhmm(self):
        fixed = datetime(2026, 5, 4, 10, 0, 0)
        opt = self._make_optimizer()
        with patch("app.optimizer.datetime") as mock_dt:
            mock_dt.now.return_value = fixed
            result = today_at(opt, "07:30")
        self.assertEqual(result.hour, 7)
        self.assertEqual(result.minute, 30)
        self.assertEqual(result.second, 0)
        self.assertEqual(result.date(), fixed.date())

    def test_invalid_time_string_returns_end_of_day(self):
        fixed = datetime(2026, 5, 4, 10, 0, 0)
        opt = self._make_optimizer()
        with patch("app.optimizer.datetime") as mock_dt:
            mock_dt.now.return_value = fixed
            result = today_at(opt, "invalid")
        self.assertEqual(result.hour, 23)
        self.assertEqual(result.minute, 59)


class TestDayWindow(_OptimizerFixture):
    def test_sun_above_horizon_uses_yesterday_sunrise(self):
        opt = self._make_optimizer(evening_mode_hours_before_sunset=1.0)
        now_ts = datetime(2026, 5, 4, 12, 0, 0).timestamp()
        with patch("app.optimizer.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 5, 4, 12, 0, 0)
            sunrise_ts = now_ts + 60000  # some future value
            sunset_ts = now_ts + 20000
            s = SolarState(
                next_sunrise_ts=sunrise_ts,
                next_sunset_ts=sunset_ts,
                sun_above_horizon=True,
            )
            start, end = day_window(opt, s)
        # day_start = (sunrise_ts - 86400) + 3600
        expected_start = sunrise_ts - 86400 + 3600
        self.assertAlmostEqual(start, expected_start, places=0)
        # day_end = sunset_ts - 1hr
        expected_end = sunset_ts - 3600
        self.assertAlmostEqual(end, expected_end, places=0)

    def test_sun_below_horizon_uses_next_sunrise(self):
        opt = self._make_optimizer(evening_mode_hours_before_sunset=1.0)
        now_ts = datetime(2026, 5, 4, 5, 0, 0).timestamp()
        with patch("app.optimizer.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 5, 4, 5, 0, 0)
            sunrise_ts = now_ts + 3600
            sunset_ts = now_ts + 50000
            s = SolarState(
                next_sunrise_ts=sunrise_ts,
                next_sunset_ts=sunset_ts,
                sun_above_horizon=False,
            )
            start, end = day_window(opt, s)
        expected_start = sunrise_ts + 3600
        self.assertAlmostEqual(start, expected_start, places=0)


class TestBatterySocRequiredToSunrise(_OptimizerFixture):
    def test_no_sunrise_returns_reserve_plus_buffer(self):
        opt = self._make_optimizer(night_reserve_soc=30.0, night_reserve_buffer=10.0)
        s = SolarState(next_sunrise_ts=None, battery_capacity_kwh=10.0, load_kw=0.5)
        result = battery_soc_required_to_sunrise(opt, s)
        self.assertEqual(result, 40.0)

    def test_typical_overnight_calculation(self):
        """With 10 kWh battery, 0.5 kW load for ~8 hours → ~40% needed (capped)."""
        opt = self._make_optimizer(
            night_reserve_soc=20.0,
            night_reserve_buffer=5.0,
            sunrise_safety_factor=1.0,
            sunrise_buffer_percent=0.0,
        )
        now_ts = datetime(2026, 5, 4, 22, 0, 0).timestamp()
        sunrise_ts = datetime(2026, 5, 5, 7, 0, 0).timestamp()  # 9 hours later
        sunset_ts = now_ts - 3600  # already past sunset
        with patch("app.optimizer.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 5, 4, 22, 0, 0)
            s = SolarState(
                next_sunrise_ts=sunrise_ts,
                next_sunset_ts=sunset_ts,
                sun_above_horizon=False,
                battery_capacity_kwh=10.0,
                load_kw=0.5,
            )
            result = battery_soc_required_to_sunrise(opt, s)
        # energy_need = 0.5 kW * (9+1)h = 5 kWh, 5/10 * 100 = 50% → clamped to 20–100
        self.assertGreater(result, 20.0)
        self.assertLessEqual(result, 100.0)


if __name__ == "__main__":
    unittest.main()
