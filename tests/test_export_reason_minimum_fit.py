from __future__ import annotations

import os
import math
import tempfile
import unittest
from unittest.mock import patch

from app.config import Settings
from app.models import SolarState
from app.optimizer import SigEnergyOptimizer


class _DummyHA:
    pass


class ExportReasonMinimumFitTests(unittest.TestCase):
    def setUp(self) -> None:
        environment = patch.dict(os.environ, {}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        self._tmp = tempfile.TemporaryDirectory()
        self._old_state_db_path = os.environ.get("STATE_DB_PATH")
        os.environ["STATE_DB_PATH"] = os.path.join(self._tmp.name, "state.db")
        self.optimizer = SigEnergyOptimizer(
            _DummyHA(),
            Settings(
                _env_file=None,
                battery_full_safeguard_enabled=False,
                evening_boost_enabled=False,
                morning_dump_enabled=False,
                morning_slow_charge_enabled=False,
                solar_surplus_bypass_enabled=False,
                standby_holdoff_enabled=False,
            ),
        )

    def tearDown(self) -> None:
        self.optimizer._state_store.close()
        if self._old_state_db_path is None:
            os.environ.pop("STATE_DB_PATH", None)
        else:
            os.environ["STATE_DB_PATH"] = self._old_state_db_path
        self._tmp.cleanup()

    def _reason(self, fit_cents: float, *, import_price_is_negative: bool = False,
                morning_dump: bool = False) -> str:
        state = SolarState(
            battery_soc=90.0,
            current_price=0.03,
            current_price_cents=3.0,
            price_is_negative=import_price_is_negative,
            feedin_price=fit_cents / 100.0,
            feedin_price_cents=fit_cents,
        )
        return self.optimizer._export_reason(
            state,
            spike=False,
            solar_override=False,
            morning_dump=morning_dump,
            export_blocked=False,
            forecast_guard=False,
            is_evening_or_night=False,
            export_min_soc=20.0,
            pv_safeguard=False,
            tier_limit=5.0,
            morning_slow_charge=False,
            surplus_bypass=False,
            evening_boost=False,
            safeguard=False,
            desired_export=0.0,
            positive_fit_override=False,
        )

    def test_nonpositive_fit_keeps_existing_zero_negative_reason(self) -> None:
        with self.subTest(fit_cents=-0.5):
            self.assertEqual(
                "Export blocked, FIT zero/negative (-0.5¢)",
                self._reason(-0.5),
            )
        with self.subTest(fit_cents=0.0):
            self.assertEqual(
                "Export blocked, FIT zero/negative (0.0¢)",
                self._reason(0.0),
            )

    def test_positive_sub_cent_fit_reports_below_minimum_with_precision(self) -> None:
        self.assertEqual(
            "Export blocked, FIT below 1¢ minimum (0.24502¢)",
            self._reason(0.24502),
        )
        self.assertEqual(
            "Export blocked, FIT below 1¢ minimum (0.9999¢)",
            self._reason(0.9999),
        )
        just_below_one = math.nextafter(1.0, 0.0)
        self.assertEqual(
            f"Export blocked, FIT below 1¢ minimum ({just_below_one!r}¢)",
            self._reason(just_below_one),
        )

    def test_exact_one_cent_passes_minimum_reason_gate(self) -> None:
        self.assertEqual(
            "Exporting 0.0kW, Morning dump @ 1¢, 90%",
            self._reason(1.0, morning_dump=True),
        )

    def test_negative_import_price_reason_keeps_precedence(self) -> None:
        self.assertEqual(
            "Export blocked, price is negative (3¢)",
            self._reason(0.24502, import_price_is_negative=True),
        )
