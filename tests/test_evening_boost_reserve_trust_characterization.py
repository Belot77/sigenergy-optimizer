from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from app.models import BATTERY_EXPORT, EXPORT_BLOCKED
from app.optimizer import MODE_CMD_DISCHARGE_PV, MODE_MAX_SELF
from haos49_characterization_helpers import Haos49CharacterizationCase, RecordingHA
import test_phase1_forecast_solar_clock_telemetry_trust_characterization as _fixtures

_UNSET = object()


class EveningBoostReserveTrustCharacterizationTests(Haos49CharacterizationCase):
    EVENING = datetime(2026, 1, 15, 19, 18)

    def _fixture_states(
        self,
        optimizer,
        when: datetime,
        *,
        load_kw: float = 0.0,
        feedin_price: float = 0.15,
    ):
        # Reuse the proven Phase 1 fake-HA entity/timestamp fixture without
        # inheriting its test methods.
        fixture = _fixtures.Phase1ForecastSolarClockTelemetryTrustCharacterizationTests()
        states = fixture._states(
            optimizer,
            when=when,
            forecast_today_state="100.0",
            forecast_tomorrow_state="120.0",
            detailed_forecast=(
                fixture._morning_detail(when)
            ),
            tomorrow_detailed_forecast=(
                fixture._tomorrow_detail_for_total(when, 120.0)
            ),
            battery_soc=80.0,
            available_discharge_kwh=24.0,
            load_kw=load_kw,
            current_price=0.30,
            feedin_price=feedin_price,
        )
        cfg = optimizer.cfg
        overnight = [
            {
                cfg.price_forecast_time_key: (when + timedelta(hours=hour)).isoformat(),
                cfg.price_forecast_value_key: 0.30,
            }
            for hour in range(1, 12)
        ]
        feedin = [
            {
                cfg.price_forecast_time_key: (when + timedelta(hours=hour)).isoformat(),
                cfg.feedin_forecast_value_key: 0.05,
            }
            for hour in range(1, 12)
        ]
        states[cfg.price_forecast_sensor] = (
            fixture._entity(
                "available",
                when,
                {cfg.price_forecast_attribute: overnight},
            )
        )
        states[cfg.feedin_forecast_sensor] = (
            fixture._entity(
                "available",
                when,
                {cfg.feedin_forecast_attribute: feedin},
            )
        )
        return states

    def _read_and_decide(
        self,
        optimizer,
        when: datetime,
        *,
        load_kw: float = 0.0,
        load_case: str = "fresh",
        next_rising: object = _UNSET,
        feedin_price: float = 0.15,
    ):
        ha = optimizer.ha
        fixture = _fixtures.Phase1ForecastSolarClockTelemetryTrustCharacterizationTests()
        states = self._fixture_states(
            optimizer,
            when,
            load_kw=load_kw,
            feedin_price=feedin_price,
        )
        load_entity = optimizer.cfg.consumed_power_sensor
        if load_case == "missing":
            states.pop(load_entity)
        elif load_case == "stale":
            states[load_entity] = fixture._entity(
                load_kw,
                when,
                observed_at=when - timedelta(hours=2),
            )
        elif load_case == "unavailable":
            states[load_entity]["state"] = "unavailable"
        elif load_case == "unknown":
            states[load_entity]["state"] = "unknown"
        elif load_case == "nan":
            states[load_entity]["state"] = "nan"
        elif load_case == "negative":
            states[load_entity]["state"] = -0.1
        elif load_case != "fresh":
            raise AssertionError(f"unknown load case: {load_case}")

        if next_rising is not _UNSET:
            states[optimizer.cfg.sun_entity]["attributes"]["next_rising"] = next_rising
        ha.states = states
        optimizer._tz = timezone(when.astimezone().utcoffset() or timedelta())
        with self.optimizer_time(when):
            state = asyncio.run(optimizer._read_state())
            decision = optimizer._decide(state)
        return state, decision

    def _optimizer(self, ha: RecordingHA | None = None):
        optimizer = self.optimizer(
            ha=ha or RecordingHA(),
            evening_boost_enabled=True,
            evening_boost_min_tomorrow_forecast_kwh=100.0,
            evening_boost_min_feedin_price=0.01,
        )
        # These cases characterize raw eligibility and reserve handling; the
        # dedicated reentry suite exercises the real delayed-admission state.
        optimizer._evening_boost_reentry_allowed = (
            lambda state, *, candidate, now_ts: candidate
        )
        return optimizer

    def test_fresh_zero_and_positive_load_readings_keep_boost_eligible(self) -> None:
        for load_kw in (0.0, 1.0):
            with self.subTest(load_kw=load_kw):
                optimizer = self._optimizer()
                state, decision = self._read_and_decide(
                    optimizer, self.EVENING, load_kw=load_kw
                )
                self.assertTrue(state.load_power_trusted)
                self.assertTrue(decision.evening_export_boost_active)
                self.assertEqual(BATTERY_EXPORT, decision.export_intent)

    def test_stale_missing_unavailable_and_invalid_load_fail_closed_for_boost(self) -> None:
        cases = (
            ("stale", 0.0),
            ("missing", 0.0),
            ("unavailable", 0.0),
            ("unknown", 0.0),
            ("nan", 0.0),
            ("negative", -0.1),
        )
        for load_case, load_kw in cases:
            with self.subTest(load_case=load_case):
                optimizer = self._optimizer()
                state, decision = self._read_and_decide(
                    optimizer,
                    self.EVENING,
                    load_kw=load_kw,
                    load_case=load_case,
                )
                self.assertFalse(state.load_power_trusted)
                self.assertFalse(decision.evening_export_boost_active)
                self.assertEqual(EXPORT_BLOCKED, decision.export_intent)
                self.assertEqual(0.0, decision.export_limit)
                self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
                self.assertEqual(
                    "none",
                    decision.trace_values.get("battery_export_final_owner"),
                )

    def test_untrusted_load_preserves_independent_qualified_high_export(self) -> None:
        """Characterize owner independence; this is not global reserve approval."""
        optimizer = self._optimizer()
        state, decision = self._read_and_decide(
            optimizer,
            self.EVENING,
            load_case="missing",
            feedin_price=1.20,
        )
        self.assertFalse(state.load_power_trusted)
        self.assertFalse(decision.evening_export_boost_active)
        self.assertEqual(BATTERY_EXPORT, decision.export_intent)
        self.assertEqual("high_price", decision.trace_values.get("battery_export_owner"))
        self.assertEqual(
            "high_price",
            decision.trace_values.get("battery_export_final_owner"),
        )
        self.assertGreater(decision.export_limit, 0.01)
        self.assertEqual(MODE_CMD_DISCHARGE_PV, decision.ems_mode)

    def test_missing_invalid_or_past_sunrise_fails_closed_then_fresh_report_recovers(self) -> None:
        invalid_sunrises = (
            None,
            "unavailable",
            "not-a-timestamp",
            "2026-01-15T07:00:00",
        )
        for raw_sunrise in invalid_sunrises:
            with self.subTest(next_rising=raw_sunrise):
                optimizer = self._optimizer()
                _initial_state, prior = self._read_and_decide(optimizer, self.EVENING)
                self.assertTrue(prior.evening_export_boost_active)
                optimizer._last_decision = prior

                state, blocked = self._read_and_decide(
                    optimizer,
                    self.EVENING + timedelta(seconds=5),
                    next_rising=raw_sunrise,
                )
                self.assertFalse(state.sunrise_observation_trusted)
                self.assertFalse(blocked.evening_export_boost_active)
                self.assertNotEqual(BATTERY_EXPORT, blocked.export_intent)
                if raw_sunrise in (None, "unavailable", "not-a-timestamp"):
                    self.assertEqual(EXPORT_BLOCKED, blocked.export_intent)
                    self.assertEqual(0.0, blocked.export_limit)
                # A finite past timestamp may retain an independent MSC ceiling;
                # this guard removes Boost authority, not every other policy.
                self.assertEqual(MODE_MAX_SELF, blocked.ems_mode)
                self.assertEqual("none", blocked.trace_values.get("battery_export_final_owner"))
                optimizer._last_decision = blocked

                recovered_state, recovered = self._read_and_decide(
                    optimizer, self.EVENING + timedelta(seconds=10)
                )
                self.assertTrue(recovered_state.sunrise_observation_trusted)
                self.assertTrue(recovered.evening_export_boost_active)

    def test_untrusted_load_after_active_boost_fails_closed_and_fresh_reading_recovers(self) -> None:
        optimizer = self._optimizer()
        _initial_state, prior = self._read_and_decide(optimizer, self.EVENING)
        self.assertTrue(prior.evening_export_boost_active)
        optimizer._last_decision = prior

        stale_state, blocked = self._read_and_decide(
            optimizer,
            self.EVENING + timedelta(seconds=5),
            load_case="stale",
        )
        self.assertFalse(stale_state.load_power_trusted)
        self.assertFalse(blocked.evening_export_boost_active)
        self.assertEqual(EXPORT_BLOCKED, blocked.export_intent)
        self.assertEqual(0.0, blocked.export_limit)
        self.assertEqual(MODE_MAX_SELF, blocked.ems_mode)
        self.assertEqual("none", blocked.trace_values.get("battery_export_final_owner"))
        optimizer._last_decision = blocked

        fresh_state, recovered = self._read_and_decide(
            optimizer,
            self.EVENING + timedelta(seconds=10),
            load_kw=0.0,
        )
        self.assertTrue(fresh_state.load_power_trusted)
        self.assertTrue(recovered.evening_export_boost_active)

    def test_alternating_load_near_export_threshold_cycles_under_raw_eligibility(self) -> None:
        """Underlying eligibility cycles when reentry admission is bypassed."""
        optimizer = self._optimizer()
        limits: list[float] = []
        for index, load_kw in enumerate((1.6, 1.7, 1.6, 1.7, 1.6, 1.7)):
            when = self.EVENING + timedelta(seconds=5 * index)
            state, decision = self._read_and_decide(
                optimizer, when, load_kw=load_kw
            )
            self.assertTrue(state.load_power_trusted)
            limits.append(decision.export_limit)
            optimizer._last_decision = decision
        self.assertEqual([1.4, 0.0, 1.4, 0.0, 1.4, 0.0], limits)


if __name__ == "__main__":
    import unittest

    unittest.main()
