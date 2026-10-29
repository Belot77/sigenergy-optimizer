from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from app.optimizer import DISCHARGE_MODES
from test_msc_baseline_overlay_contract import (
    ClockedRecordingHA,
    establish_observed_msc_baseline,
    later_msc_report_clock,
)
from test_phase1_solar_dynamic_charge_ceiling_characterization import SolarDynamicChargeFixture


class SolarProviderDaylightValidationTests(SolarDynamicChargeFixture):
    """Provider generations and Solar daylight ownership have separate gates."""

    WHEN = datetime(2026, 10, 30, 6, 0, 0)

    @staticmethod
    def iso(at):
        return datetime.fromtimestamp(at.timestamp(), timezone.utc).isoformat()

    def observe(self, opt, *, at=None, polled=None, deadline=None, **changes):
        at = at or self.WHEN
        # Use the host-local fixture clock consistently, including day rollover.
        opt._tz = at.astimezone().tzinfo
        state = self._state(
            when=at,
            forecast_pv_kw=[6.0] * 24,
            sun_above_horizon=False,
        )
        state.solcast_provider_source = opt._solar_provider_source
        state.solcast_provider_epoch = opt._solar_provider_epoch
        state.solcast_provider_polled = self.iso(polled or at)
        state.solcast_provider_next_update = self.iso(deadline or (at + timedelta(hours=2)))
        for key, value in changes.items():
            setattr(state, key, value)
        return state, self.decide(opt, state, at)

    def valid_before_sunrise(self, opt, *, deadline=None):
        self.observe(opt, polled=self.WHEN - timedelta(minutes=1), deadline=deadline)
        return self.observe(opt, deadline=deadline)

    def assert_no_solar_ownership(self, decision):
        self.assertFalse(decision.solar_surplus_policy_active)
        self.assertFalse(decision.trace_gates["solar_charge_ceiling_owned"])
        self.assertEqual(self.NORMAL_CHARGE_KW, decision.ess_charge_limit)
        self.assertEqual("none", decision.trace_values["battery_export_owner"])
        self.assertNotIn(decision.ems_mode, DISCHARGE_MODES)

    def test_predawn_baseline_and_advance_survive_sunrise_without_another_poll(self):
        opt = self._optimizer()
        first_poll = self.WHEN - timedelta(minutes=1)
        cached, baseline = self.observe(opt, polled=first_poll)
        self.assertEqual("baseline_requires_provider_advance", baseline.trace_values["solar_provider_reason"])
        self.assertFalse(baseline.trace_gates["solar_provider_authority_trusted"])
        # Keep one complete payload and fixed sunset, rather than synthesizing
        # another forecast generation as the observation clock advances.
        cached_payload = {"solcast_detailed": cached.solcast_detailed,
                          "next_sunset_ts": cached.next_sunset_ts}
        _, unchanged = self.observe(opt, at=self.WHEN + timedelta(seconds=1),
                                    polled=first_poll, **cached_payload)
        self.assertEqual("UNVERIFIED", unchanged.trace_values["solar_provider_state"])
        _, advanced = self.observe(opt, at=self.WHEN + timedelta(seconds=2),
                                   polled=self.WHEN, **cached_payload)
        self.assertEqual("VALID", advanced.trace_values["solar_provider_state"])
        self.assert_no_solar_ownership(advanced)
        _, sunrise = self.observe(
            opt, at=self.WHEN + timedelta(minutes=2), polled=self.WHEN,
            sun_above_horizon=True, **cached_payload,
        )
        self.assertEqual("VALID", sunrise.trace_values["solar_provider_state"])
        self.assertTrue(sunrise.trace_gates["solar_charge_ceiling_owned"])
        self.assertLess(sunrise.ess_charge_limit, self.NORMAL_CHARGE_KW)

    def test_cached_startup_poll_does_not_qualify_merely_because_sun_rises(self):
        opt = self._optimizer()
        _, baseline = self.observe(opt)
        self.assertEqual("UNVERIFIED", baseline.trace_values["solar_provider_state"])
        for daylight in (False, True):
            with self.subTest(daylight=daylight):
                _, decision = self.observe(
                    opt, at=self.WHEN + timedelta(minutes=2), polled=self.WHEN,
                    sun_above_horizon=daylight,
                )
                self.assertFalse(decision.trace_gates["solar_provider_authority_trusted"])
                self.assertEqual(self.NORMAL_CHARGE_KW, decision.ess_charge_limit)

    def test_valid_predawn_provider_cannot_dispatch_a_solar_charge_restriction(self):
        async def check():
            opt = self._optimizer(ess_max_charging_limit="number.test_charge")
            ha = ClockedRecordingHA()
            await establish_observed_msc_baseline(self, opt, ha, self.WHEN - timedelta(seconds=1))
            state, decision = self.valid_before_sunrise(opt)
            self.assertTrue(decision.trace_gates["solar_provider_authority_trusted"])
            self.assert_no_solar_ownership(decision)
            state.current_export_limit = decision.export_limit
            state.current_import_limit = decision.import_limit
            with later_msc_report_clock(ha, self.WHEN):
                result = await opt._apply(state, decision)
            self.assertTrue(result.succeeded, result.error)
            charge_writes = [value for action, entity, value in ha.calls
                             if action == "set_number" and entity == "number.test_charge"]
            self.assertEqual([self.NORMAL_CHARGE_KW], charge_writes)
            self.assert_no_solar_ownership(decision)
        asyncio.run(check())

    def test_predawn_generations_still_require_trusted_sun_and_sunset_metadata(self):
        for changes in ({"sun_state_observation_trusted": False},
                        {"sunset_observation_trusted": False},
                        {"solcast_detailed_source_trusted": False}):
            with self.subTest(changes=changes):
                opt = self._optimizer()
                self.observe(opt, polled=self.WHEN - timedelta(minutes=1))
                _, decision = self.observe(opt, **changes)
                self.assertFalse(decision.trace_gates["solar_provider_authority_trusted"])
                self.assert_no_solar_ownership(decision)

    def test_bad_predawn_generation_cannot_be_repaired_with_unchanged_poll(self):
        opt = self._optimizer()
        self.observe(opt, polled=self.WHEN - timedelta(minutes=1))
        incomplete = self._detailed_forecast([6.0] * 23, when=self.WHEN)
        _, rejected = self.observe(opt, solcast_detailed=incomplete)
        self.assertEqual("provider_detailed_payload_invalid", rejected.trace_values["solar_provider_reason"])
        _, repaired = self.observe(opt, at=self.WHEN + timedelta(seconds=1), polled=self.WHEN)
        self.assertFalse(repaired.trace_gates["solar_provider_authority_trusted"])
        _, recovered = self.observe(opt, at=self.WHEN + timedelta(seconds=2), polled=self.WHEN + timedelta(seconds=2))
        self.assertTrue(recovered.trace_gates["solar_provider_authority_trusted"])

    def test_predawn_deadline_cannot_slide_and_late_new_poll_can_recover(self):
        opt = self._optimizer()
        due = self.WHEN + timedelta(minutes=10)
        _, valid = self.valid_before_sunrise(opt, deadline=due)
        self.assertTrue(valid.trace_gates["solar_provider_authority_trusted"])
        _, expired = self.observe(opt, at=due, polled=self.WHEN, deadline=due + timedelta(hours=2))
        self.assertEqual("EXPIRED", expired.trace_values["solar_provider_state"])
        self.assertEqual(due.timestamp(), opt._solar_provider_deadline)
        _, recovered = self.observe(opt, at=due + timedelta(seconds=1), polled=due + timedelta(seconds=1))
        self.assertTrue(recovered.trace_gates["solar_provider_authority_trusted"])
        self.assert_no_solar_ownership(recovered)

    def test_predawn_reconnect_requires_new_baseline_and_generation(self):
        opt = self._optimizer()
        _, valid = self.valid_before_sunrise(opt)
        self.assertTrue(valid.trace_gates["solar_provider_authority_trusted"])
        opt.on_ws_disconnect()
        opt.on_ws_connect()
        _, baseline = self.observe(opt)
        self.assertFalse(baseline.trace_gates["solar_provider_authority_trusted"])
        _, unchanged = self.observe(opt, at=self.WHEN + timedelta(seconds=1), polled=self.WHEN)
        self.assertFalse(unchanged.trace_gates["solar_provider_authority_trusted"])
        _, recovered = self.observe(opt, at=self.WHEN + timedelta(seconds=2))
        self.assertTrue(recovered.trace_gates["solar_provider_authority_trusted"])
        self.assert_no_solar_ownership(recovered)

    def test_local_midnight_revokes_provider_even_with_complete_new_day_payload(self):
        opt = self._optimizer()
        next_day = self.WHEN + timedelta(days=1)
        _, valid = self.valid_before_sunrise(opt, deadline=next_day + timedelta(hours=2))
        self.assertTrue(valid.trace_gates["solar_provider_authority_trusted"])
        midnight = next_day.replace(hour=0)
        _, revoked = self.observe(opt, at=midnight)
        self.assertFalse(revoked.trace_gates["solar_provider_authority_trusted"])
        _, baseline = self.observe(opt, at=midnight)
        self.assertFalse(baseline.trace_gates["solar_provider_authority_trusted"])
        _, recovered = self.observe(opt, at=midnight + timedelta(seconds=1))
        self.assertTrue(recovered.trace_gates["solar_provider_authority_trusted"])
        self.assert_no_solar_ownership(recovered)

    def test_tomorrows_sunset_is_not_a_usable_today_payload(self):
        opt = self._optimizer()
        self.valid_before_sunrise(opt)
        _, decision = self.observe(
            opt, at=self.WHEN + timedelta(seconds=1),
            next_sunset_ts=(self.WHEN + timedelta(days=1, hours=12)).timestamp(),
        )
        self.assertFalse(decision.trace_gates["solar_provider_authority_trusted"])
        self.assert_no_solar_ownership(decision)

    def test_valid_predawn_provider_cannot_survive_an_inflight_continuity_loss(self):
        async def check():
            opt = self._optimizer(ess_max_charging_limit="number.test_charge")
            ha = ClockedRecordingHA()
            await establish_observed_msc_baseline(self, opt, ha, self.WHEN - timedelta(seconds=1))
            state, decision = self.valid_before_sunrise(opt)
            state.current_export_limit = decision.export_limit
            state.current_import_limit = 1.0
            self.assertTrue(decision.trace_gates["solar_provider_authority_trusted"])
            original = ha.set_number
            async def disconnect_before_charge(entity, value):
                if entity == opt.cfg.grid_import_limit:
                    opt.on_ws_disconnect()
                return await original(entity, value)
            ha.set_number = disconnect_before_charge
            with later_msc_report_clock(ha, self.WHEN):
                result = await opt._apply(state, decision)
            self.assertTrue(result.succeeded, result.error)
            self.assertFalse(opt._solar_provider_authority_current(state, self.WHEN.timestamp()))
            self.assert_no_solar_ownership(decision)
            self.assertFalse(any(action == "set_number" and entity == "number.test_charge"
                                 and value < self.NORMAL_CHARGE_KW for action, entity, value in ha.calls))
        asyncio.run(check())
