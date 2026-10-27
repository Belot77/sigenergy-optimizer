"""Morning Slow physical relief is gradual and grounded in measured export."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timedelta

from app.models import HVACObservedValue, HVACSolarInputContext
from haos49_characterization_helpers import Haos49CharacterizationCase
import test_phase1_morning_slow_relief_characterization as morning_fixture_module
from test_msc_baseline_overlay_contract import (
    ClockedRecordingHA,
    establish_observed_msc_baseline,
    later_msc_report_clock,
)


class MorningSlowPartialReliefTests(Haos49CharacterizationCase):
    """Exercise the real Morning Slow decision with the established state fixture."""

    MORNING = morning_fixture_module.Phase1MorningSlowReliefCharacterizationTests.MORNING
    SLOW_END = morning_fixture_module.Phase1MorningSlowReliefCharacterizationTests.SLOW_END
    SUNSET = morning_fixture_module.Phase1MorningSlowReliefCharacterizationTests.SUNSET
    _observed = staticmethod(
        morning_fixture_module.Phase1MorningSlowReliefCharacterizationTests._observed
    )
    _flow_inputs = morning_fixture_module.Phase1MorningSlowReliefCharacterizationTests._flow_inputs
    _optimizer = morning_fixture_module.Phase1MorningSlowReliefCharacterizationTests._optimizer
    _detailed_forecast = morning_fixture_module.Phase1MorningSlowReliefCharacterizationTests._detailed_forecast
    _morning_state = morning_fixture_module.Phase1MorningSlowReliefCharacterizationTests._morning_state

    def _flow_state(
        self,
        optimizer,
        *,
        seconds: int,
        export_kw: float,
        charge_kw: float,
        report_seconds: float | None = None,
        charge_readback: HVACObservedValue | None = None,
        import_kw: float = 0.0,
        **overrides,
    ):
        when = self.MORNING + timedelta(seconds=seconds)
        report_ts = (self.MORNING + timedelta(
            seconds=seconds if report_seconds is None else report_seconds
        )).timestamp()
        state = self._morning_state(
            optimizer,
            grid_export_kw=export_kw,
            battery_charge_kw=charge_kw,
            timestamp=when,
            current_ess_charge_limit=2.0 if charge_readback is None else charge_readback.value,
            grid_import_power_kw=import_kw,
            **overrides,
        )
        pv_kw = state.load_kw + export_kw + charge_kw - import_kw
        state.pv_kw = pv_kw
        state.solar_power_now_kw = pv_kw
        observed = lambda value: HVACObservedValue(
            value=value, available=True, fresh=True, observed_at_ts=report_ts
        )
        state.hvac_solar_inputs = HVACSolarInputContext(
            pv_power=observed(pv_kw),
            load_power=observed(state.load_kw),
            battery_power=observed(charge_kw),
            grid_import_power=observed(import_kw),
            grid_export_power=observed(export_kw),
            solar_power_now=observed(pv_kw),
            sun_above_horizon=observed(True),
            control_mode=observed("Automated"),
            observed_ems_mode=observed("Maximum Self Consumption"),
            remote_ems_control=observed("on"),
            observed_export_limit=observed(25.0),
            live_snapshot=True,
        )
        state._msc_ems_reported_at = report_ts
        if charge_readback is not None:
            state.current_ess_charge_limit_observation = charge_readback
        return state, when

    def _apply(self, optimizer, ha, state, decision, when, *, report_applied=True):
        with later_msc_report_clock(ha, when) as moment:
            cfg = optimizer.cfg
            for entity, value in (
                (cfg.sigenergy_mode_select, cfg.automated_option),
                (cfg.ha_control_switch, "on"),
                (cfg.ems_mode_select, "Maximum Self Consumption"),
                (cfg.grid_export_limit, cfg.export_limit_high),
                (cfg.ess_max_charging_limit, state.current_ess_charge_limit),
            ):
                ha._record_state_value(entity, value)
            result = asyncio.run(optimizer._apply(state, decision))
            if result.succeeded and report_applied:
                # Actuator report arrives independently after service success.
                moment[0] += timedelta(milliseconds=100)
                ha._record_state_value(
                    cfg.ess_max_charging_limit, decision.ess_charge_limit,
                )
        self.assertTrue(result.succeeded, result.error)
        self.assertTrue(result.automatic_application_completed)
        optimizer._last_state = state
        optimizer._last_decision = decision

    def _started_morning(self, export_kw: float, **config_overrides):
        ha = ClockedRecordingHA()
        optimizer = self._optimizer(**config_overrides)
        optimizer.ha = ha
        asyncio.run(establish_observed_msc_baseline(
            self, optimizer, ha, self.MORNING - timedelta(seconds=2),
        ))
        ha.settle_numbers = False
        initial, when = self._flow_state(
            optimizer, seconds=0, export_kw=export_kw, charge_kw=2.0,
        )
        initial.current_ess_charge_limit = 10.0
        initial.current_ess_charge_limit_observation = self._charge_readback(optimizer, ha)
        decision = self.decide(optimizer, initial, when)
        self.assertEqual(2.0, decision.ess_charge_limit)
        self._apply(optimizer, ha, initial, decision, when)
        self.assertIn(("set_number", optimizer.cfg.ess_max_charging_limit, 2.0), ha.calls)
        return optimizer, ha

    @staticmethod
    def _charge_readback(optimizer, ha):
        entity = optimizer.cfg.ess_max_charging_limit
        return HVACObservedValue(
            value=ha.state_values[entity],
            available=True,
            fresh=True,
            observed_at_ts=datetime.fromisoformat(
                ha._state_value_metadata[entity]["last_reported"]
            ).timestamp(),
        )

    def test_measured_threshold_waits_for_applied_slow_cap_before_relief(self) -> None:
        for export_kw in (14.5, 14.8):
            with self.subTest(export_kw=export_kw):
                optimizer = self._optimizer()
                state = self._morning_state(
                    optimizer,
                    grid_export_kw=export_kw,
                    battery_charge_kw=2.0,
                )

                decision = self.decide(optimizer, state, self.MORNING)

                self.assertTrue(decision.morning_slow_charge_active)
                self.assertFalse(
                    decision.trace_gates["morning_slow_physical_export_relief"]
                )
                self.assertEqual(14.5, decision.trace_values[
                    "morning_slow_physical_relief_threshold_kw"
                ])
                self.assertEqual(2.0, decision.ess_charge_limit)

    def test_full_normal_counterfactual_cannot_authorize_physical_jump(self) -> None:
        optimizer = self._optimizer()
        state = self._morning_state(
            optimizer,
            grid_export_kw=8.0,
            battery_charge_kw=10.0,
        )

        decision = self.decide(optimizer, state, self.MORNING)

        self.assertEqual(16.0, decision.trace_values[
            "morning_slow_estimated_export_if_slow_cap_restored_kw"
        ])
        self.assertFalse(decision.trace_gates["morning_slow_forecast_refill_relief"])
        self.assertLess(decision.ess_charge_limit, 10.0)
        self.assertLessEqual(decision.ess_charge_limit, 2.4)

    def test_below_threshold_starts_at_slow_cap(self) -> None:
        optimizer = self._optimizer()
        state = self._morning_state(
            optimizer,
            grid_export_kw=14.49,
            battery_charge_kw=2.0,
        )

        decision = self.decide(optimizer, state, self.MORNING)

        self.assertEqual(2.0, decision.ess_charge_limit)
        self.assertFalse(
            decision.trace_gates["morning_slow_physical_export_relief"]
        )

    def test_equal_threshold_cannot_raise_even_after_two_new_flow_reports(self) -> None:
        optimizer, ha = self._started_morning(14.5)
        readback = self._charge_readback(optimizer, ha)
        for seconds in (1, 2, 3):
            state, when = self._flow_state(
                optimizer, seconds=seconds, export_kw=14.5, charge_kw=2.0,
                charge_readback=readback,
            )
            decision = self.decide(optimizer, state, when)
            self.assertEqual(2.0, decision.ess_charge_limit)

    def test_two_post_readback_flow_cohorts_allow_only_measured_excess(self) -> None:
        optimizer, ha = self._started_morning(14.8)
        readback = self._charge_readback(optimizer, ha)

        first, when = self._flow_state(
            optimizer, seconds=1, export_kw=14.8, charge_kw=2.0,
            charge_readback=readback,
        )
        first_decision = self.decide(optimizer, first, when)
        self.assertEqual(2.0, first_decision.ess_charge_limit)

        repeated, when = self._flow_state(
            optimizer, seconds=2, export_kw=14.8, charge_kw=2.0,
            report_seconds=1, charge_readback=readback,
        )
        repeated_decision = self.decide(optimizer, repeated, when)
        self.assertEqual(2.0, repeated_decision.ess_charge_limit)

        second, when = self._flow_state(
            optimizer, seconds=3, export_kw=14.8, charge_kw=2.0,
            charge_readback=readback,
        )
        second_decision = self.decide(optimizer, second, when)
        self.assertGreater(
            second_decision.ess_charge_limit, 2.0,
            second_decision.trace_values.get("morning_slow_physical_export_reason"),
        )
        self.assertLessEqual(second_decision.ess_charge_limit, 2.25)
        self.assertTrue(second_decision.trace_gates[
            "morning_slow_physical_export_relief"
        ])

    def test_advancing_setting_reports_do_not_move_first_readback_barrier(self) -> None:
        optimizer, ha = self._started_morning(14.8)
        for seconds, readback_seconds in ((1, 0.5), (2, 1.5)):
            readback = HVACObservedValue(
                value=2.0, available=True, fresh=True,
                observed_at_ts=(self.MORNING + timedelta(
                    seconds=readback_seconds
                )).timestamp(),
            )
            state, when = self._flow_state(
                optimizer, seconds=seconds, export_kw=14.8, charge_kw=2.0,
                charge_readback=readback,
            )
            decision = self.decide(optimizer, state, when)
            if seconds == 1:
                self.assertEqual(2.0, decision.ess_charge_limit)
            else:
                self.assertGreater(
                    decision.ess_charge_limit, 2.0,
                    decision.trace_values.get("morning_slow_physical_export_reason"),
                )
                self.assertLessEqual(decision.ess_charge_limit, 2.25)

    def test_repeated_decisions_cannot_stack_an_unapplied_rise(self) -> None:
        optimizer, ha = self._started_morning(14.8)
        readback = self._charge_readback(optimizer, ha)
        requests = []
        for seconds in (1, 2, 3, 4):
            state, when = self._flow_state(
                optimizer, seconds=seconds, export_kw=14.8, charge_kw=2.0,
                charge_readback=readback,
            )
            requests.append(self.decide(optimizer, state, when).ess_charge_limit)
        self.assertEqual(2.0, requests[0])
        self.assertGreater(requests[1], 2.0)
        self.assertEqual([requests[1]] * 3, requests[1:])

    def test_static_plant_settles_partial_without_stacking_or_chatter(self) -> None:
        optimizer, ha = self._started_morning(14.8)
        readback = self._charge_readback(optimizer, ha)
        decisions = []
        for seconds in (1, 2):
            state, when = self._flow_state(
                optimizer, seconds=seconds, export_kw=14.8, charge_kw=2.0,
                charge_readback=readback,
            )
            decisions.append(self.decide(optimizer, state, when))
        self.assertEqual(2.0, decisions[0].ess_charge_limit)
        partial = decisions[1]
        self.assertGreater(
            partial.ess_charge_limit, 2.0,
            partial.trace_values.get("morning_slow_physical_export_reason"),
        )
        self.assertLessEqual(partial.ess_charge_limit, 2.25)
        self._apply(optimizer, ha, state, partial, when)
        partial_readback = self._charge_readback(optimizer, ha)

        # A lossless plant with 16.8 kW net PV surplus initially exports 14.8
        # at a 2 kW cap. One small rise consumes that much surplus on settlement.
        net_surplus_kw = 16.8
        for seconds, measured_charge in ((3, 2.0), (4, partial.ess_charge_limit),
                                         (5, partial.ess_charge_limit),
                                         (6, partial.ess_charge_limit)):
            export_kw = net_surplus_kw - measured_charge
            observed, when = self._flow_state(
                optimizer, seconds=seconds, export_kw=export_kw,
                charge_kw=measured_charge, charge_readback=partial_readback,
            )
            decision = self.decide(optimizer, observed, when)
            self.assertEqual(partial.ess_charge_limit, decision.ess_charge_limit)
            self.assertLess(decision.ess_charge_limit, 10.0)

    def test_lost_setting_readback_revokes_partial_even_in_hysteresis_band(self) -> None:
        optimizer, ha = self._started_morning(14.8)
        readback = self._charge_readback(optimizer, ha)
        for seconds in (1, 2):
            state, when = self._flow_state(
                optimizer, seconds=seconds, export_kw=14.8, charge_kw=2.0,
                charge_readback=readback,
            )
            decision = self.decide(optimizer, state, when)
        self.assertGreater(decision.ess_charge_limit, 2.0)
        self._apply(optimizer, ha, state, decision, when)

        lost = HVACObservedValue(value=decision.ess_charge_limit,
                                 available=False, fresh=False)
        next_state, when = self._flow_state(
            optimizer, seconds=3, export_kw=14.5,
            charge_kw=decision.ess_charge_limit, charge_readback=lost,
        )
        next_decision = self.decide(optimizer, next_state, when)
        self.assertEqual(2.0, next_decision.ess_charge_limit)
        self.assertFalse(next_decision.trace_gates[
            "morning_slow_physical_export_relief"
        ])

    def test_configuration_identity_change_retires_earned_relief(self) -> None:
        optimizer, ha = self._started_morning(14.8)
        readback = self._charge_readback(optimizer, ha)
        for seconds in (1, 2):
            state, when = self._flow_state(
                optimizer, seconds=seconds, export_kw=14.8, charge_kw=2.0,
                charge_readback=readback,
            )
            decision = self.decide(optimizer, state, when)
        self.assertGreater(decision.ess_charge_limit, 2.0)
        self._apply(optimizer, ha, state, decision, when)

        optimizer._invalidate_configuration_evidence({"ess_max_charging_limit"})
        new_state, when = self._flow_state(
            optimizer, seconds=3, export_kw=14.8,
            charge_kw=decision.ess_charge_limit,
            charge_readback=self._charge_readback(optimizer, ha),
        )
        new_decision = self.decide(optimizer, new_state, when)
        self.assertFalse(new_decision.trace_gates[
            "morning_slow_physical_export_relief"
        ])
        self.assertLessEqual(new_decision.ess_charge_limit, 2.0)

    def test_remote_off_during_application_retires_pending_rise(self) -> None:
        optimizer, ha = self._started_morning(14.8)
        readback = self._charge_readback(optimizer, ha)
        for seconds in (1, 2):
            state, when = self._flow_state(
                optimizer, seconds=seconds, export_kw=14.8, charge_kw=2.0,
                charge_readback=readback,
            )
            decision = self.decide(optimizer, state, when)
        self.assertGreater(decision.ess_charge_limit, 2.0)

        with later_msc_report_clock(ha, when):
            ha._record_state_value(optimizer.cfg.ha_control_switch, "off")
            result = asyncio.run(optimizer._apply(state, decision))
        self.assertFalse(result.automatic_application_completed)

        resumed, when = self._flow_state(
            optimizer, seconds=3, export_kw=14.8, charge_kw=2.0,
            charge_readback=readback,
        )
        resumed_decision = self.decide(optimizer, resumed, when)
        self.assertEqual(2.0, resumed_decision.ess_charge_limit)
        self.assertFalse(resumed_decision.trace_gates[
            "morning_slow_physical_export_relief"
        ])

    def test_bad_or_nonadvancing_four_flow_reports_cannot_raise_cap(self) -> None:
        for case in ("stale", "future", "skew", "regressed", "one_flow_lag"):
            with self.subTest(case=case):
                optimizer, ha = self._started_morning(14.8)
                readback = self._charge_readback(optimizer, ha)
                first, when = self._flow_state(
                    optimizer, seconds=1, export_kw=14.8, charge_kw=2.0,
                    charge_readback=readback,
                )
                self.assertEqual(2.0, self.decide(optimizer, first, when).ess_charge_limit)
                report_seconds = {"stale": -1000, "future": 11,
                                  "skew": 10, "regressed": 0.5,
                                  "one_flow_lag": 2}[case]
                second, when = self._flow_state(
                    optimizer, seconds=10 if case == "skew" else 2,
                    report_seconds=report_seconds,
                    export_kw=14.8, charge_kw=2.0,
                    charge_readback=readback,
                )
                if case in ("skew", "one_flow_lag"):
                    old = second.hvac_solar_inputs.load_power
                    second.hvac_solar_inputs = replace(
                        second.hvac_solar_inputs,
                        load_power=replace(
                            old, observed_at_ts=(self.MORNING + timedelta(
                                seconds=4 if case == "skew" else 1
                            )).timestamp(),
                        ),
                    )
                decision = self.decide(optimizer, second, when)
                self.assertEqual(2.0, decision.ess_charge_limit)

    def test_positive_measured_import_pauses_upward_relief(self) -> None:
        optimizer, ha = self._started_morning(14.8)
        readback = self._charge_readback(optimizer, ha)
        for seconds in (1, 2, 3):
            state, when = self._flow_state(
                optimizer, seconds=seconds, export_kw=14.8, charge_kw=2.0,
                charge_readback=readback, import_kw=0.1,
            )
            decision = self.decide(optimizer, state, when)
            self.assertEqual(2.0, decision.ess_charge_limit)

    def test_same_value_reassert_keeps_epoch_and_partial_does_not_arm_handoff(self) -> None:
        optimizer, ha = self._started_morning(14.8)
        readback = self._charge_readback(optimizer, ha)
        first, when = self._flow_state(
            optimizer, seconds=1, export_kw=14.8, charge_kw=2.0,
            charge_readback=readback,
        )
        same = self.decide(optimizer, first, when)
        self.assertEqual(2.0, same.ess_charge_limit)
        original_command_ts = same.trace_values[
            "morning_slow_physical_relief_feedback_command_ts"
        ]
        self._apply(optimizer, ha, first, same, when)

        second, when = self._flow_state(
            optimizer, seconds=2, export_kw=14.8, charge_kw=2.0,
            charge_readback=self._charge_readback(optimizer, ha),
        )
        partial = self.decide(optimizer, second, when)
        self.assertGreater(partial.ess_charge_limit, 2.0)
        self.assertEqual(original_command_ts, partial.trace_values[
            "morning_slow_physical_relief_feedback_command_ts"
        ])
        self.assertFalse(partial.trace_gates["morning_slow_reentry_arm_candidate"])
        self._apply(optimizer, ha, second, partial, when)
        self.assertFalse(optimizer._solar_charge_reentry.required)

    def test_dip_reduces_partial_then_hard_reset_requires_retry_proof(self) -> None:
        optimizer, ha = self._started_morning(14.95)
        readback = self._charge_readback(optimizer, ha)
        for seconds in (1, 2):
            state, when = self._flow_state(
                optimizer, seconds=seconds, export_kw=14.95, charge_kw=2.0,
                charge_readback=readback,
            )
            partial = self.decide(optimizer, state, when)
        self.assertGreater(partial.ess_charge_limit, 2.0)
        self.assertLessEqual(partial.ess_charge_limit, 2.4)
        self._apply(optimizer, ha, state, partial, when)

        dip, when = self._flow_state(
            optimizer, seconds=3, export_kw=14.2,
            charge_kw=partial.ess_charge_limit,
            charge_readback=self._charge_readback(optimizer, ha),
        )
        reduced = self.decide(optimizer, dip, when)
        self.assertGreater(reduced.ess_charge_limit, 2.0)
        self.assertLess(reduced.ess_charge_limit, partial.ess_charge_limit)
        self._apply(optimizer, ha, dip, reduced, when)

        hard, when = self._flow_state(
            optimizer, seconds=4, export_kw=13.9,
            charge_kw=reduced.ess_charge_limit,
            charge_readback=self._charge_readback(optimizer, ha),
        )
        closed = self.decide(optimizer, hard, when)
        self.assertEqual(2.0, closed.ess_charge_limit)
        self._apply(optimizer, ha, hard, closed, when)
        readback = self._charge_readback(optimizer, ha)
        for seconds in (5, 6, 7):
            recovered, when = self._flow_state(
                optimizer, seconds=seconds, export_kw=14.95, charge_kw=2.0,
                charge_readback=readback,
            )
            decision = self.decide(optimizer, recovered, when)
            if seconds < 7:
                self.assertEqual(2.0, decision.ess_charge_limit)
            else:
                self.assertGreater(decision.ess_charge_limit, 2.0)
                self.assertLessEqual(decision.ess_charge_limit, 2.4)

    def test_large_headroom_still_bounds_step_and_exit_width(self) -> None:
        optimizer, ha = self._started_morning(
            14.95, morning_slow_physical_export_headroom_kw=3.0,
        )
        readback = self._charge_readback(optimizer, ha)
        for seconds in (1, 2):
            state, when = self._flow_state(
                optimizer, seconds=seconds, export_kw=14.95, charge_kw=2.0,
                charge_readback=readback,
            )
            partial = self.decide(optimizer, state, when)
        self.assertGreater(partial.ess_charge_limit, 2.0)
        self.assertLessEqual(partial.ess_charge_limit, 2.4)
        self._apply(optimizer, ha, state, partial, when)
        # T=12: export at 11.7 is past the capped 0.25 kW exit band.
        dipped, when = self._flow_state(
            optimizer, seconds=3, export_kw=11.7,
            charge_kw=partial.ess_charge_limit,
            charge_readback=self._charge_readback(optimizer, ha),
        )
        reduced = self.decide(optimizer, dipped, when)
        self.assertLess(reduced.ess_charge_limit, partial.ess_charge_limit)

    def test_failed_charge_write_discards_unapplied_partial_proposal(self) -> None:
        optimizer, ha = self._started_morning(14.8)
        readback = self._charge_readback(optimizer, ha)
        for seconds in (1, 2):
            state, when = self._flow_state(
                optimizer, seconds=seconds, export_kw=14.8, charge_kw=2.0,
                charge_readback=readback,
            )
            partial = self.decide(optimizer, state, when)
        self.assertGreater(partial.ess_charge_limit, 2.0)

        original_set_number = ha.set_number

        async def reject_charge(entity_id, value):
            if entity_id == optimizer.cfg.ess_max_charging_limit:
                ha.calls.append(("set_number", entity_id, value))
                return False
            return await original_set_number(entity_id, value)

        with later_msc_report_clock(ha, when):
            cfg = optimizer.cfg
            for entity, value in (
                (cfg.sigenergy_mode_select, cfg.automated_option),
                (cfg.ha_control_switch, "on"),
                (cfg.ems_mode_select, "Maximum Self Consumption"),
                (cfg.grid_export_limit, cfg.export_limit_high),
                (cfg.ess_max_charging_limit, 2.0),
            ):
                ha._record_state_value(entity, value)
            ha.set_number = reject_charge
            try:
                result = asyncio.run(optimizer._apply(state, partial))
            finally:
                ha.set_number = original_set_number
        self.assertFalse(result.succeeded)
        self.assertFalse(result.automatic_application_completed)

        next_state, when = self._flow_state(
            optimizer, seconds=3, export_kw=14.8, charge_kw=2.0,
            charge_readback=readback,
        )
        next_decision = self.decide(optimizer, next_state, when)
        self.assertEqual(2.0, next_decision.ess_charge_limit)

    def test_manual_takeover_and_trusted_cap_change_retire_partial(self) -> None:
        for case in ("manual", "cap"):
            with self.subTest(case=case):
                optimizer, ha = self._started_morning(14.8)
                readback = self._charge_readback(optimizer, ha)
                for seconds in (1, 2):
                    state, when = self._flow_state(
                        optimizer, seconds=seconds, export_kw=14.8,
                        charge_kw=2.0, charge_readback=readback,
                    )
                    partial = self.decide(optimizer, state, when)
                self._apply(optimizer, ha, state, partial, when)
                overrides = (
                    {"sigenergy_mode": "Manual"} if case == "manual" else
                    {"ess_max_charge_kw": 3.0,
                     "ess_charge_limit_entity_max_kw": 3.0}
                )
                changed, when = self._flow_state(
                    optimizer, seconds=3, export_kw=14.8,
                    charge_kw=partial.ess_charge_limit,
                    charge_readback=self._charge_readback(optimizer, ha),
                    **overrides,
                )
                if case == "manual":
                    changed.hvac_solar_inputs = replace(
                        changed.hvac_solar_inputs,
                        control_mode=replace(
                            changed.hvac_solar_inputs.control_mode,
                            value="Manual",
                        ),
                    )
                decision = self.decide(optimizer, changed, when)
                self.assertFalse(decision.trace_gates[
                    "morning_slow_physical_export_relief"
                ])
                if case == "cap":
                    self.assertEqual(2.0, decision.ess_charge_limit)
                else:
                    self.assertFalse(decision.trace_gates[
                        "morning_slow_genuinely_owns_charging"
                    ])

    def test_old_readback_during_new_command_lag_holds_then_later_contradiction_resets(self) -> None:
        optimizer, ha = self._started_morning(14.8)
        readback = self._charge_readback(optimizer, ha)
        for seconds in (1, 2):
            state, when = self._flow_state(
                optimizer, seconds=seconds, export_kw=14.8, charge_kw=2.0,
                charge_readback=readback,
            )
            partial = self.decide(optimizer, state, when)
        self.assertGreater(partial.ess_charge_limit, 2.0)
        self._apply(optimizer, ha, state, partial, when, report_applied=False)

        # Service accepted 2.25, but the next fresh setting report still says 2.
        old = HVACObservedValue(
            value=2.0, available=True, fresh=True,
            observed_at_ts=(self.MORNING + timedelta(seconds=2.1)).timestamp(),
        )
        waiting, when = self._flow_state(
            optimizer, seconds=3, export_kw=14.8, charge_kw=2.0,
            charge_readback=old,
        )
        held = self.decide(optimizer, waiting, when)
        self.assertEqual(partial.ess_charge_limit, held.ess_charge_limit)
        self.assertEqual(
            "awaiting_post_command_readback",
            held.trace_values["morning_slow_physical_export_reason"],
        )
        self.assertIsNone(optimizer._morning_slow_relief.first_readback_ts)
        self.assertEqual(0, optimizer._morning_slow_relief.confirmations)

        matching = HVACObservedValue(
            value=partial.ess_charge_limit, available=True, fresh=True,
            observed_at_ts=(self.MORNING + timedelta(seconds=3.5)).timestamp(),
        )
        after_report, when = self._flow_state(
            optimizer, seconds=4, export_kw=14.8, charge_kw=2.0,
            charge_readback=matching,
        )
        self.assertEqual(
            partial.ess_charge_limit,
            self.decide(optimizer, after_report, when).ess_charge_limit,
        )
        settled, when = self._flow_state(
            optimizer, seconds=5,
            export_kw=16.8 - partial.ess_charge_limit,
            charge_kw=partial.ess_charge_limit,
            charge_readback=matching,
        )
        self.assertEqual(
            partial.ess_charge_limit,
            self.decide(optimizer, settled, when).ess_charge_limit,
        )

        contradicted = HVACObservedValue(
            value=2.0, available=True, fresh=True,
            observed_at_ts=(self.MORNING + timedelta(seconds=5.5)).timestamp(),
        )
        bad, when = self._flow_state(
            optimizer, seconds=6, export_kw=14.55,
            charge_kw=partial.ess_charge_limit, charge_readback=contradicted,
        )
        rejected = self.decide(optimizer, bad, when)
        self.assertEqual(2.0, rejected.ess_charge_limit)

    def test_pending_old_readback_expires_and_unexpected_value_rejects(self) -> None:
        for case in ("expired_old", "unexpected_new"):
            with self.subTest(case=case):
                optimizer, ha = self._started_morning(14.8)
                readback = self._charge_readback(optimizer, ha)
                for seconds in (1, 2):
                    state, when = self._flow_state(
                        optimizer, seconds=seconds, export_kw=14.8,
                        charge_kw=2.0, charge_readback=readback,
                    )
                    partial = self.decide(optimizer, state, when)
                self._apply(optimizer, ha, state, partial, when, report_applied=False)

                seen = HVACObservedValue(
                    value=2.0 if case == "expired_old" else 3.0,
                    available=True, fresh=True,
                    observed_at_ts=(self.MORNING + timedelta(
                        seconds=129 if case == "expired_old" else 2.1
                    )).timestamp(),
                )
                checked, when = self._flow_state(
                    optimizer, seconds=130 if case == "expired_old" else 3,
                    export_kw=14.8, charge_kw=2.0, charge_readback=seen,
                )
                decision = self.decide(optimizer, checked, when)
                self.assertEqual(2.0, decision.ess_charge_limit)
                self.assertFalse(decision.trace_gates[
                    "morning_slow_physical_export_relief"
                ])
                if case == "expired_old":
                    self.assertEqual(
                        "ess_charge_readback_timeout",
                        decision.trace_values["morning_slow_physical_export_reason"],
                    )

    def test_one_hundredth_kw_old_readback_is_not_exact_new_command_proof(self) -> None:
        optimizer, ha = self._started_morning(14.565)
        readback = self._charge_readback(optimizer, ha)
        for seconds in (1, 2):
            state, when = self._flow_state(
                optimizer, seconds=seconds, export_kw=14.565, charge_kw=2.0,
                charge_readback=readback,
            )
            partial = self.decide(optimizer, state, when)
        self.assertAlmostEqual(2.01, partial.ess_charge_limit, places=2)
        self._apply(optimizer, ha, state, partial, when, report_applied=False)

        old = HVACObservedValue(
            value=2.0, available=True, fresh=True,
            observed_at_ts=(self.MORNING + timedelta(seconds=2.1)).timestamp(),
        )
        lagged, when = self._flow_state(
            optimizer, seconds=3, export_kw=14.565, charge_kw=2.0,
            charge_readback=old,
        )
        waiting = self.decide(optimizer, lagged, when)
        self.assertAlmostEqual(2.01, waiting.ess_charge_limit, places=2)
        self.assertEqual(
            "awaiting_post_command_readback",
            waiting.trace_values["morning_slow_physical_export_reason"],
        )
        self.assertIsNone(optimizer._morning_slow_relief.first_readback_ts)
        self.assertEqual(0, optimizer._morning_slow_relief.confirmations)

        exact = HVACObservedValue(
            value=2.01, available=True, fresh=True,
            observed_at_ts=(self.MORNING + timedelta(seconds=3.5)).timestamp(),
        )
        matched, when = self._flow_state(
            optimizer, seconds=4, export_kw=14.565, charge_kw=2.0,
            charge_readback=exact,
        )
        self.assertAlmostEqual(
            2.01, self.decide(optimizer, matched, when).ess_charge_limit, places=2,
        )
        self.assertEqual(exact.observed_at_ts,
                         optimizer._morning_slow_relief.first_readback_ts)
