from __future__ import annotations

import asyncio
import copy
from datetime import datetime, timedelta, timezone

from test_msc_baseline_overlay_contract import (
    ClockedRecordingHA,
    establish_observed_msc_baseline,
    later_msc_report_clock,
)
from test_phase1_solar_dynamic_charge_ceiling_characterization import SolarDynamicChargeFixture


class SolarProviderTrustRecoveryTests(SolarDynamicChargeFixture):
    """Restore only the unchanged, previously verified provider evidence."""

    @staticmethod
    def iso(at: datetime) -> str:
        return datetime.fromtimestamp(at.timestamp(), timezone.utc).isoformat()

    def observe(self, opt, *, at=None, polled=None, deadline=None, **changes):
        at = at or self.WHEN
        # All observations retain one forecast and sunset. Advancing the clock
        # must not silently manufacture a changed provider payload.
        opt._tz = at.astimezone().tzinfo
        state = self._state()
        state.timestamp = at
        state.solcast_provider_source = opt._solar_provider_source
        state.solcast_provider_epoch = opt._solar_provider_epoch
        state.solcast_provider_polled = self.iso(polled or self.WHEN)
        state.solcast_provider_next_update = self.iso(
            deadline or self.WHEN + timedelta(minutes=10)
        )
        for key, value in changes.items():
            setattr(state, key, value)
        return state, self.decide(opt, state, at)

    def valid(self, opt, *, deadline=None):
        self.observe(opt, polled=self.WHEN - timedelta(minutes=1), deadline=deadline)
        state, decision = self.observe(opt, deadline=deadline)
        self.assertTrue(decision.trace_gates["solar_provider_authority_trusted"])
        self.assertTrue(decision.trace_gates["solar_charge_ceiling_owned"])
        return state, decision

    def assert_released(self, decision):
        self.assertFalse(decision.trace_gates["solar_provider_authority_trusted"])
        self.assertFalse(decision.trace_gates["solar_charge_ceiling_owned"])
        self.assertEqual(self.NORMAL_CHARGE_KW, decision.ess_charge_limit)

    def test_unchanged_verified_generation_recovers_when_sun_metadata_returns(self):
        for changes in (
            {"sun_state_observation_trusted": False},
            {"sunset_observation_trusted": False},
            {"sunset_observation_trusted": False, "next_sunset_ts": None},
            {"sun_state_observation_trusted": False, "sunset_observation_trusted": False},
        ):
            with self.subTest(changes=changes):
                opt = self._optimizer()
                state, _ = self.valid(opt)
                epoch, source = opt._solar_provider_epoch, opt._solar_provider_source
                due = opt._solar_provider_deadline
                _, lost = self.observe(opt, at=self.WHEN + timedelta(seconds=1), **changes)
                self.assert_released(lost)
                restored, recovered = self.observe(opt, at=self.WHEN + timedelta(seconds=2))
                self.assertEqual(state.solcast_detailed, restored.solcast_detailed)
                self.assertEqual(state.next_sunset_ts, restored.next_sunset_ts)
                self.assertEqual("VALID", recovered.trace_values["solar_provider_state"])
                self.assertTrue(recovered.trace_gates["solar_provider_authority_trusted"])
                self.assertTrue(recovered.trace_gates["solar_charge_ceiling_owned"])
                self.assertLess(recovered.ess_charge_limit, self.NORMAL_CHARGE_KW)
                self.assertEqual(self.iso(self.WHEN), recovered.trace_values["solar_provider_verified_polled"])
                self.assertEqual(self.iso(self.WHEN), recovered.trace_values["solar_provider_high_water"])
                self.assertEqual((epoch, source, due), (
                    opt._solar_provider_epoch, opt._solar_provider_source, opt._solar_provider_deadline,
                ))

    def test_repeated_metadata_flaps_never_slide_retained_deadline(self):
        opt = self._optimizer()
        self.valid(opt)
        due = self.WHEN + timedelta(minutes=10)
        for offset in (1, 3, 5):
            self.observe(opt, at=self.WHEN + timedelta(seconds=offset), sun_state_observation_trusted=False)
            _, recovered = self.observe(
                opt, at=self.WHEN + timedelta(seconds=offset + 1),
                deadline=due + timedelta(hours=2),
            )
            self.assertTrue(recovered.trace_gates["solar_provider_authority_trusted"])
            self.assertEqual(self.iso(due), recovered.trace_values["solar_provider_deadline"])
        _, expired = self.observe(opt, at=due, deadline=due + timedelta(hours=2))
        self.assert_released(expired)
        self.assertEqual("EXPIRED", expired.trace_values["solar_provider_state"])

    def test_metadata_return_at_deadline_cannot_restore_old_generation(self):
        opt = self._optimizer()
        self.valid(opt)
        self.observe(opt, sun_state_observation_trusted=False)
        due = self.WHEN + timedelta(minutes=10)
        _, expired = self.observe(opt, at=due, deadline=due + timedelta(hours=1))
        self.assert_released(expired)
        later = due + timedelta(seconds=1)
        _, renewed = self.observe(opt, at=later, polled=later, deadline=due + timedelta(hours=1))
        self.assertTrue(renewed.trace_gates["solar_charge_ceiling_owned"])

    def test_earlier_schedule_during_metadata_loss_is_retained(self):
        opt = self._optimizer()
        self.valid(opt)
        due = self.WHEN + timedelta(seconds=3)
        self.observe(opt, at=self.WHEN + timedelta(seconds=1), deadline=due,
                     sunset_observation_trusted=False)
        _, recovered = self.observe(opt, at=self.WHEN + timedelta(seconds=2))
        self.assertTrue(recovered.trace_gates["solar_provider_authority_trusted"])
        self.assertEqual(self.iso(due), recovered.trace_values["solar_provider_deadline"])
        _, expired = self.observe(opt, at=due)
        self.assert_released(expired)

    def test_startup_metadata_return_still_requires_baseline_and_advance(self):
        opt = self._optimizer()
        self.observe(opt, sun_state_observation_trusted=False)
        _, baseline = self.observe(opt)
        self.assert_released(baseline)
        _, unchanged = self.observe(opt, at=self.WHEN + timedelta(seconds=1))
        self.assert_released(unchanged)
        later = self.WHEN + timedelta(seconds=2)
        _, advanced = self.observe(opt, at=later, polled=later)
        self.assertTrue(advanced.trace_gates["solar_provider_authority_trusted"])

    def test_new_poll_rejected_during_sun_loss_cannot_be_rehabilitated(self):
        for bad_data in (False, True):
            with self.subTest(bad_data=bad_data):
                opt = self._optimizer()
                self.valid(opt)
                later = self.WHEN + timedelta(seconds=1)
                changes = {"sun_state_observation_trusted": False}
                if bad_data:
                    changes["solcast_detailed"] = []
                _, rejected = self.observe(opt, at=later, polled=later, **changes)
                self.assert_released(rejected)
                _, repaired = self.observe(opt, at=later + timedelta(seconds=1), polled=later)
                self.assert_released(repaired)
                self.assertEqual(self.iso(later), repaired.trace_values["solar_provider_high_water"])
                self.assertEqual(self.iso(self.WHEN), repaired.trace_values["solar_provider_verified_polled"])
                next_poll = later + timedelta(seconds=2)
                _, recovered = self.observe(opt, at=next_poll, polled=next_poll)
                self.assertTrue(recovered.trace_gates["solar_provider_authority_trusted"])

    def test_changed_valid_payload_under_old_poll_retires_evidence(self):
        for during_loss in (False, True):
            with self.subTest(during_loss=during_loss):
                opt = self._optimizer()
                self.valid(opt)
                changed = self._detailed_forecast([7.0] + [3.0] * 7)
                _, decision = self.observe(
                    opt, solcast_detailed=changed,
                    sun_state_observation_trusted=not during_loss,
                )
                self.assert_released(decision)
                _, original_returned = self.observe(opt, at=self.WHEN + timedelta(seconds=1))
                self.assert_released(original_returned)

    def test_bad_unchanged_generation_cannot_recover_after_payload_repair(self):
        detail = self._detailed_forecast([6.0] + [3.0] * 7)
        cases = [[], detail[:-1], list(reversed(detail)), [detail[0]] + detail]
        for delta in (-0.5, 0.5):
            bad = copy.deepcopy(detail)
            bad[2]["period_start"] = self.iso(self.WHEN + timedelta(hours=1, seconds=delta))
            cases.append(bad)
        for value in (-1.0, float("nan"), float("inf"), True):
            bad = copy.deepcopy(detail)
            bad[0]["pv_estimate"] = value
            cases.append(bad)
        for index, detail in enumerate(cases):
            with self.subTest(case=index):
                opt = self._optimizer()
                self.valid(opt)
                _, rejected = self.observe(opt, solcast_detailed=detail)
                self.assert_released(rejected)
                _, repaired = self.observe(opt, at=self.WHEN + timedelta(seconds=1))
                self.assert_released(repaired)

    def test_changed_trusted_sunset_does_not_reuse_old_verification(self):
        for hours in (3.5, 28.0):
            with self.subTest(hours=hours):
                opt = self._optimizer()
                self.valid(opt)
                self.observe(opt, sunset_observation_trusted=False)
                _, changed = self.observe(opt, next_sunset_ts=(self.WHEN + timedelta(hours=hours)).timestamp())
                self.assert_released(changed)
                _, original = self.observe(opt, at=self.WHEN + timedelta(seconds=1))
                self.assert_released(original)

    def test_bad_schedule_during_metadata_loss_retires_recovery_evidence(self):
        for raw in (None, "bad", "2026-01-15T15:00:00", self.iso(self.WHEN)):
            with self.subTest(raw=raw):
                opt = self._optimizer()
                self.valid(opt)
                self.observe(opt, sunset_observation_trusted=False, solcast_provider_next_update=raw)
                _, repaired = self.observe(opt, at=self.WHEN + timedelta(seconds=1))
                self.assert_released(repaired)

    def test_restart_reconnect_and_source_change_require_new_baseline_and_advance(self):
        for boundary in ("restart", "reconnect", "source"):
            with self.subTest(boundary=boundary):
                opt = self._optimizer()
                self.valid(opt)
                self.observe(opt, sun_state_observation_trusted=False)
                if boundary == "restart":
                    opt = self._optimizer()
                elif boundary == "reconnect":
                    opt.on_ws_disconnect()
                    opt.on_ws_connect()
                else:
                    opt.cfg.forecast_today_sensor = "sensor.reassigned_forecast"
                    opt._refresh_solar_provider_source()
                _, baseline = self.observe(opt)
                self.assert_released(baseline)
                _, unchanged = self.observe(opt, at=self.WHEN + timedelta(seconds=1))
                self.assert_released(unchanged)
                later = self.WHEN + timedelta(seconds=2)
                _, advanced = self.observe(opt, at=later, polled=later)
                self.assertTrue(advanced.trace_gates["solar_provider_authority_trusted"])

    def test_invalid_or_regressing_poll_cannot_restore_retained_evidence(self):
        for raw in (None, "bad", "2026-01-15T14:00:00", self.iso(self.WHEN - timedelta(seconds=1)),
                    self.iso(self.WHEN + timedelta(seconds=6))):
            with self.subTest(raw=raw):
                opt = self._optimizer()
                self.valid(opt)
                self.observe(opt, sun_state_observation_trusted=False)
                _, invalid = self.observe(opt, solcast_provider_polled=raw)
                self.assert_released(invalid)
                _, baseline = self.observe(opt, at=self.WHEN + timedelta(seconds=1))
                self.assert_released(baseline)

    def test_day_roll_retires_old_evidence_even_before_provider_deadline(self):
        opt = self._optimizer()
        tomorrow = self.WHEN + timedelta(days=1)
        due = tomorrow + timedelta(hours=1)
        self.valid(opt, deadline=due)
        self.observe(opt, deadline=due, sun_state_observation_trusted=False)
        new = self._state(when=tomorrow)
        changes = {"solcast_detailed": new.solcast_detailed, "next_sunset_ts": new.next_sunset_ts}
        _, boundary = self.observe(opt, at=tomorrow, polled=tomorrow, deadline=due, **changes)
        self.assert_released(boundary)
        _, baseline = self.observe(opt, at=tomorrow, polled=tomorrow, deadline=due, **changes)
        self.assert_released(baseline)
        later = tomorrow + timedelta(seconds=1)
        _, advanced = self.observe(opt, at=later, polled=later, deadline=due, **changes)
        self.assertTrue(advanced.trace_gates["solar_provider_authority_trusted"])

    def test_recovery_below_horizon_does_not_grant_solar_ownership(self):
        opt = self._optimizer()
        self.valid(opt)
        self.observe(opt, sun_state_observation_trusted=False)
        _, recovered = self.observe(opt, sun_above_horizon=False)
        self.assertTrue(recovered.trace_gates["solar_provider_authority_trusted"])
        self.assertFalse(recovered.solar_surplus_policy_active)
        self.assertFalse(recovered.trace_gates["solar_charge_ceiling_owned"])
        self.assertEqual(self.NORMAL_CHARGE_KW, recovered.ess_charge_limit)

    def test_preapply_metadata_loss_releases_charge_then_same_evidence_can_recover(self):
        for field in ("sun_state_observation_trusted", "sunset_observation_trusted"):
            with self.subTest(field=field):
                opt = self._optimizer()
                state, decision = self.valid(opt)
                setattr(state, field, False)
                opt._recheck_solar_charge_authority(state, decision, self.WHEN.timestamp())
                self.assert_released(decision)
                _, recovered = self.observe(opt, at=self.WHEN + timedelta(seconds=1))
                self.assertTrue(recovered.trace_gates["solar_charge_ceiling_owned"])

    def test_preapply_uncertain_continuity_or_source_requires_baseline_and_advance(self):
        for changes in (
            {"solcast_provider_continuity": False},
            {"solcast_provider_source": ("sensor.other_forecast", "sensor.other_poll")},
        ):
            with self.subTest(changes=changes):
                opt = self._optimizer()
                state, decision = self.valid(opt)
                epoch = opt._solar_provider_epoch
                for key, value in changes.items():
                    setattr(state, key, value)
                opt._recheck_solar_charge_authority(state, decision, self.WHEN.timestamp())
                self.assert_released(decision)
                self.assertGreater(opt._solar_provider_epoch, epoch)
                _, baseline = self.observe(opt)
                self.assert_released(baseline)
                _, unchanged = self.observe(opt, at=self.WHEN + timedelta(seconds=1))
                self.assert_released(unchanged)
                later = self.WHEN + timedelta(seconds=2)
                _, advanced = self.observe(opt, at=later, polled=later)
                self.assertTrue(advanced.trace_gates["solar_provider_authority_trusted"])

    def test_old_epoch_preapply_snapshot_cannot_retire_new_epoch_evidence(self):
        opt = self._optimizer()
        stale, old_decision = self.valid(opt)
        opt.on_ws_disconnect()
        opt.on_ws_connect()
        self.observe(opt)
        later = self.WHEN + timedelta(seconds=1)
        current, verified = self.observe(opt, at=later, polled=later)
        self.assertTrue(verified.trace_gates["solar_provider_authority_trusted"])
        epoch = opt._solar_provider_epoch
        opt._recheck_solar_charge_authority(stale, old_decision, later.timestamp())
        self.assert_released(old_decision)
        self.assertEqual(epoch, opt._solar_provider_epoch)
        self.assertTrue(opt._solar_provider_authority_current(current, later.timestamp()))

    def test_old_poll_preapply_snapshot_cannot_retire_newer_verified_generation(self):
        opt = self._optimizer()
        stale, old_decision = self.valid(opt)
        later = self.WHEN + timedelta(seconds=1)
        current, verified = self.observe(opt, at=later, polled=later)
        self.assertTrue(verified.trace_gates["solar_provider_authority_trusted"])
        epoch = opt._solar_provider_epoch
        evidence = opt._solar_provider_verified_evidence
        opt._recheck_solar_charge_authority(stale, old_decision, later.timestamp())
        self.assert_released(old_decision)
        self.assertEqual(epoch, opt._solar_provider_epoch)
        self.assertEqual(evidence, opt._solar_provider_verified_evidence)
        self.assertEqual("VALID", opt._solar_provider_state)
        self.assertTrue(opt._solar_provider_authority_current(current, later.timestamp()))

    def test_preapply_earlier_schedule_remains_binding_after_later_schedule(self):
        opt = self._optimizer()
        state, decision = self.valid(opt)
        earlier = self.WHEN + timedelta(seconds=2)
        state.solcast_provider_next_update = self.iso(earlier)
        opt._recheck_solar_charge_authority(state, decision, self.WHEN.timestamp())
        self.assertTrue(decision.trace_gates["solar_charge_ceiling_owned"])
        self.assertEqual(earlier.timestamp(), opt._solar_provider_deadline)
        state.solcast_provider_next_update = self.iso(self.WHEN + timedelta(seconds=600))
        opt._recheck_solar_charge_authority(
            state, decision, (self.WHEN + timedelta(seconds=3)).timestamp(),
        )
        self.assert_released(decision)
        self.assertEqual("EXPIRED", opt._solar_provider_state)
        self.assertEqual(earlier.timestamp(), opt._solar_provider_deadline)

    def test_metadata_loss_during_reduced_write_restores_normal_in_same_application(self):
        async def check():
            opt = self._optimizer(ess_max_charging_limit="number.test_charge")
            ha = ClockedRecordingHA()
            await establish_observed_msc_baseline(self, opt, ha, self.WHEN - timedelta(seconds=1))
            state, decision = self.valid(opt)
            state.current_export_limit = decision.export_limit
            state.current_import_limit = decision.import_limit
            reduced = decision.ess_charge_limit
            original = ha.set_number

            async def lose_metadata(entity, value):
                result = await original(entity, value)
                if entity == "number.test_charge" and value == reduced:
                    state.sun_state_observation_trusted = False
                return result

            ha.set_number = lose_metadata
            with later_msc_report_clock(ha, self.WHEN):
                result = await opt._apply(state, decision)
            self.assertTrue(result.succeeded, result.error)
            writes = [value for action, entity, value in ha.calls
                      if action == "set_number" and entity == "number.test_charge"]
            self.assertEqual([reduced, self.NORMAL_CHARGE_KW], writes)
            self.assert_released(decision)
        asyncio.run(check())
