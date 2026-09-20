from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models import SolarState
from haos49_characterization_helpers import Haos49CharacterizationCase


class Phase1D6NegativePriceForecastTrustTests(Haos49CharacterizationCase):
    NOW = datetime(2026, 1, 15, 8, 0, 0, tzinfo=timezone(timedelta(hours=11)))

    @staticmethod
    def _entry(when: object, price: object) -> dict[str, object]:
        return {"start_time": when, "per_kwh": price}

    def _state(self, entries: list[object], *, trusted: bool | None = None) -> SolarState:
        return SolarState(
            price_forecast_entries=entries,
            price_forecast_source_trusted=trusted,
        )

    def test_negative_price_ahead_requires_future_entry_inside_lookahead(self) -> None:
        optimizer = self.optimizer(negative_price_forecast_lookahead_hours=2)
        now_ts = self.NOW.timestamp()

        cases = (
            (
                "past negative only",
                [self._entry((self.NOW - timedelta(minutes=30)).isoformat(), -0.20)],
                False,
            ),
            (
                "future negative inside window",
                [self._entry((self.NOW + timedelta(hours=1)).isoformat(), -0.20)],
                True,
            ),
            (
                "future negative after cutoff",
                [self._entry((self.NOW + timedelta(hours=2, minutes=1)).isoformat(), -0.20)],
                False,
            ),
            (
                "entry exactly now",
                [self._entry(self.NOW.isoformat(), -0.20)],
                True,
            ),
            (
                "entry exactly cutoff",
                [self._entry((self.NOW + timedelta(hours=2)).isoformat(), -0.20)],
                True,
            ),
            (
                "past negative and future positive",
                [
                    self._entry((self.NOW - timedelta(minutes=30)).isoformat(), -0.20),
                    self._entry((self.NOW + timedelta(hours=1)).isoformat(), 0.20),
                ],
                False,
            ),
            (
                "past and future negative",
                [
                    self._entry((self.NOW - timedelta(minutes=30)).isoformat(), -0.20),
                    self._entry((self.NOW + timedelta(hours=1)).isoformat(), -0.10),
                ],
                True,
            ),
        )

        for name, entries, expected in cases:
            with self.subTest(name=name):
                self.assertEqual(
                    expected,
                    optimizer._negative_price_forecast_ahead(
                        self._state(entries),
                        now_ts,
                    ),
                )

    def test_negative_price_before_cutoff_uses_inclusive_future_window(self) -> None:
        optimizer = self.optimizer(standby_holdoff_end_time="11:00")
        optimizer._tz = self.NOW.tzinfo
        now_ts = self.NOW.timestamp()

        for name, when, expected in (
            ("past", self.NOW - timedelta(minutes=30), False),
            ("now", self.NOW, True),
            ("cutoff", self.NOW.replace(hour=11), True),
            ("after cutoff", self.NOW.replace(hour=11, minute=1), False),
        ):
            with self.subTest(name=name):
                state = self._state([self._entry(when.isoformat(), -0.20)])
                self.assertEqual(
                    expected,
                    optimizer._negative_price_before_cutoff(state, now_ts),
                )

    def test_malformed_entries_cannot_create_negative_price_evidence(self) -> None:
        optimizer = self.optimizer(negative_price_forecast_lookahead_hours=2)
        now_ts = self.NOW.timestamp()
        future = (self.NOW + timedelta(hours=1)).isoformat()
        malformed_entries = (
            self._entry("not-a-time", -0.20),
            self._entry(True, -0.20),
            self._entry(future, float("nan")),
            self._entry(future, float("inf")),
            self._entry(future, float("-inf")),
            self._entry(future, "not-a-price"),
            self._entry(future, False),
            [future, -0.20],
        )

        for entry in malformed_entries:
            with self.subTest(entry=entry):
                self.assertFalse(
                    optimizer._negative_price_forecast_ahead(
                        self._state([entry]),
                        now_ts,
                    )
                )

    def test_explicitly_untrusted_source_blocks_both_helpers(self) -> None:
        optimizer = self.optimizer(
            negative_price_forecast_lookahead_hours=2,
            standby_holdoff_end_time="11:00",
        )
        now_ts = self.NOW.timestamp()
        state = self._state(
            [self._entry((self.NOW + timedelta(hours=1)).isoformat(), -0.20)],
            trusted=False,
        )

        self.assertFalse(optimizer._negative_price_forecast_ahead(state, now_ts))
        self.assertFalse(optimizer._negative_price_before_cutoff(state, now_ts))
