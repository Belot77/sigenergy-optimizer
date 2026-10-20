from __future__ import annotations

from datetime import datetime, timedelta
from typing import NamedTuple

from app.models import EXPORT_BLOCKED, MSC_SURPLUS_CEILING
from app.optimizer import DISCHARGE_MODES, MODE_MAX_SELF
from test_phase1_solar_dynamic_charge_ceiling_characterization import (
    SolarDynamicChargeFixture,
)


class ExportSample(NamedTuple):
    offset_seconds: int
    soc: float
    pv_kw: float
    load_kw: float
    grid_export_kw: float
    battery_kw: float
    export_readback_kw: float
    requested_export_kw: float


# Sanitized numerical observations from 20 October 2026, 13:56:11-13:57:29
# Sydney. Readbacks precede application of the decision in the same record.
# The final Force Full Export record at 13:57:41 is operator-owned and excluded.
AUTOMATED_SAMPLES = (
    ExportSample(0, 99.8, 6.324, 0.839, 4.712, -0.007, 0.01, 25.0),
    ExportSample(6, 99.8, 1.033, 1.010, 0.000, -0.009, 25.0, 0.0),
    ExportSample(13, 99.8, 5.041, 1.661, 1.891, -0.008, 0.01, 25.0),
    ExportSample(19, 99.9, 1.030, 1.012, 0.000, -0.009, 25.0, 0.0),
    ExportSample(24, 99.9, 4.908, 1.530, 3.387, -0.009, 0.01, 25.0),
    ExportSample(30, 99.9, 1.048, 1.052, 0.032, -0.009, 25.0, 0.0),
    ExportSample(36, 99.9, 3.403, 0.598, 2.814, -0.009, 0.01, 25.0),
    ExportSample(42, 99.9, 1.070, 1.100, 0.005, -0.009, 25.0, 0.0),
    ExportSample(48, 99.9, 5.550, 1.278, 2.798, -0.009, 0.01, 25.0),
    ExportSample(54, 99.9, 1.069, 1.090, 0.050, -0.009, 25.0, 0.0),
    ExportSample(61, 99.9, 3.393, 1.196, 1.491, -0.009, 0.01, 25.0),
    ExportSample(66, 99.9, 1.069, 1.140, 0.012, -0.008, 25.0, 0.0),
    ExportSample(72, 99.9, 4.261, 1.030, 3.239, -0.008, 0.01, 25.0),
    ExportSample(78, 99.9, 1.040, 1.046, 0.029, -0.008, 25.0, 0.0),
)


class SolarExportFlappingCharacterizationTests(SolarDynamicChargeFixture):
    """Record current decision behavior, not a desired continuation policy.

    Power/SoC/readback samples retain the incident sequence. The clock, 10 kWh
    rated capacity, detailed forecast and other evidence use deterministic
    synthetic fixture inputs. This is not a complete on-site replay or a model
    of inverter response, application success, telemetry timing or PV collapse.
    """

    WHEN = datetime(2026, 1, 15, 14, 0, 0)
    NORMAL_CHARGE_KW = 21.0

    def _incident_optimizer(self):
        return self._optimizer(
            _env_file=None,
            import_threshold_low=0.0,
            ess_discharge_limit_value=24.0,
            grid_connection_export_limit_kw=15.0,
        )

    def _sample_state(self, sample: ExportSample):
        at = self.WHEN + timedelta(seconds=sample.offset_seconds)
        sunset = self.WHEN + timedelta(hours=4)
        # Keep the forecast, its generation and sunset fixed across cycles.
        return self._state(
            when=self.WHEN,
            forecast_pv_kw=[10.0] * 8,
            timestamp=at,
            hours_to_sunset=(sunset - at).total_seconds() / 3600.0,
            battery_soc=sample.soc,
            available_discharge_energy_kwh=10.0 * sample.soc / 100.0,
            pv_kw=sample.pv_kw,
            solar_power_now_kw=sample.pv_kw,
            load_kw=sample.load_kw,
            grid_export_power_kw=sample.grid_export_kw,
            battery_power_sensor_kw=sample.battery_kw,
            current_export_limit=sample.export_readback_kw,
            current_price=0.1514741,
            current_price_cents=15.14741,
            feedin_price=0.0445587,
            feedin_price_cents=4.45587,
            forecast_remaining_kwh=42.3523,
            ess_max_discharge_kw=24.0,
            current_ess_discharge_limit=24.0,
        )

    def _sample_decision(self, optimizer, sample: ExportSample):
        state = self._sample_state(sample)
        # Use the real _decide path without the charge fixture's provider
        # bootstrap. Unverified provider authority preserves normal charging;
        # this does not reproduce the incident's earlier provider invalidation.
        decision = self.decide(optimizer, state, state.timestamp)
        optimizer._last_decision = decision
        return decision

    def _assert_msc_without_solar_charge_ownership(self, decision):
        self.assertEqual(MODE_MAX_SELF, decision.ems_mode)
        self.assertNotIn(decision.ems_mode, DISCHARGE_MODES)
        self.assertEqual("none", decision.trace_values["battery_export_owner"])
        self.assertEqual(0.0, decision.import_limit)
        self.assertEqual(self.NORMAL_CHARGE_KW, decision.ess_charge_limit)
        self.assertEqual("normal", decision.trace_values["ess_charge_limit_owner"])
        self.assertFalse(decision.trace_gates["solar_charge_ceiling_owned"])
        self.assertFalse(decision.trace_gates["solar_provider_authority_trusted"])
        self.assertEqual("UNVERIFIED", decision.trace_values["solar_provider_state"])

    def test_recorded_near_full_sequence_repeatedly_opens_and_closes_export(self):
        optimizer = self._incident_optimizer()
        actual_limits = []

        for sample in AUTOMATED_SAMPLES:
            with self.subTest(offset_seconds=sample.offset_seconds):
                decision = self._sample_decision(optimizer, sample)
                actual_limits.append(decision.export_limit)
                active = sample.requested_export_kw > 0.0
                self.assertEqual(sample.requested_export_kw, decision.export_limit)
                self.assertEqual(active, decision.solar_surplus_policy_active)
                self.assertEqual(active, decision.solar_surplus_bypass)
                self.assertEqual(
                    MSC_SURPLUS_CEILING if active else EXPORT_BLOCKED,
                    decision.export_intent,
                )
                # This fixture equates solar potential with observed PV, so
                # five non-positive PV-load samples use the no-PV closure.
                # The captured trace instead labelled all seven closed_tier;
                # the reproduced behavior is Solar rejection and 25/0 targets.
                self.assertEqual(
                    "solar_surplus_pv_high" if active else (
                        "closed_no_daytime_pv" if sample.pv_kw <= sample.load_kw
                        else "closed_tier"
                    ),
                    decision.trace_values["desired_export_source"],
                )
                self.assertEqual(
                    "active_final_solar_surplus_owner" if active else
                    "measured_pv_surplus_below_hysteresis_threshold",
                    decision.trace_values["solar_surplus_fail_reason"],
                )
                self._assert_msc_without_solar_charge_ownership(decision)

        self.assertEqual([25.0, 0.0] * 7, actual_limits)
        self.assertEqual(7, actual_limits.count(0.0))
        self.assertEqual([], optimizer.ha.calls)

    def test_same_near_full_power_evidence_stays_open_as_clock_advances(self):
        optimizer = self._incident_optimizer()
        stable = AUTOMATED_SAMPLES[0]
        actual_limits = []

        for index, timing in enumerate(AUTOMATED_SAMPLES):
            with self.subTest(offset_seconds=timing.offset_seconds):
                sample = stable._replace(
                    offset_seconds=timing.offset_seconds,
                    soc=99.8 if index == 0 else 99.9,
                    export_readback_kw=0.01 if index == 0 else 25.0,
                )
                decision = self._sample_decision(optimizer, sample)
                actual_limits.append(decision.export_limit)
                self.assertTrue(decision.solar_surplus_policy_active)
                self.assertEqual(MSC_SURPLUS_CEILING, decision.export_intent)
                self._assert_msc_without_solar_charge_ownership(decision)

        self.assertEqual([25.0] * len(AUTOMATED_SAMPLES), actual_limits)
        self.assertEqual([], optimizer.ha.calls)
