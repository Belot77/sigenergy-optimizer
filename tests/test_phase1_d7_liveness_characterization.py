from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

from app.models import BATTERY_EXPORT, EXPORT_BLOCKED, MSC_SURPLUS_CEILING, Decision
from app.optimizer import MODE_CMD_DISCHARGE_PV, MODE_MAX_SELF
from haos49_characterization_helpers import Haos49CharacterizationCase, RecordingHA


class _MetadataHA(RecordingHA):
    def __init__(
        self,
        states: dict[str, dict[str, object]],
        metadata: dict[str, dict[str, object]] | None = None,
        *,
        metadata_error: Exception | None = None,
    ) -> None:
        super().__init__(states)
        self.metadata = dict(metadata or {})
        self.metadata_error = metadata_error

    async def get_state_report_metadata(
        self,
        entity_ids: list[str],
    ) -> dict[str, dict[str, object]]:
        self.report_metadata_calls.append(list(entity_ids))
        if self.metadata_error is not None:
            raise self.metadata_error
        return {
            entity_id: self.metadata[entity_id]
            for entity_id in entity_ids
            if entity_id in self.metadata
        }


class _NotificationHA(RecordingHA):
    def __init__(self) -> None:
        super().__init__()
        self.notifications: list[tuple[str, str, str]] = []

    async def send_notification(self, service: str, title: str, message: str) -> bool:
        self.notifications.append((service, title, message))
        return True

    async def logbook_log(self, name: str, message: str) -> bool:
        self.calls.append(("logbook_log", name, message))
        return True


class Phase1D7LivenessCharacterizationTests(Haos49CharacterizationCase):
    FIXED_UTC = datetime(2026, 1, 15, 3, 30, tzinfo=timezone.utc)

    @staticmethod
    def _snapshot(
        value: object,
        updated_at: datetime,
        *,
        reported_at: datetime | None = None,
        attributes: dict[str, object] | None = None,
    ) -> dict[str, object]:
        snapshot: dict[str, object] = {
            "state": str(value),
            "attributes": dict(attributes or {}),
            "last_updated": updated_at.isoformat(),
        }
        if reported_at is not None:
            snapshot["last_reported"] = reported_at.isoformat()
        return snapshot

    @staticmethod
    def _metadata_row(
        entity_id: str,
        value: object,
        updated_at: datetime,
        reported_at: datetime,
    ) -> dict[str, object]:
        return {
            "entity_id": entity_id,
            "state": str(value),
            "last_updated": updated_at.isoformat(),
            "last_reported": reported_at.isoformat(),
        }

    def _read_d7_state(
        self,
        *,
        demand_state: object = "off",
        export_state: object = 0.01,
        import_state: object = 0.01,
        updated_at: datetime | None = None,
        reported_at: datetime | None = None,
        metadata_mutator=None,
        metadata_error: Exception | None = None,
        export_max: object = 25.0,
    ):
        updated_at = updated_at or (self.FIXED_UTC - timedelta(days=1))
        reported_at = reported_at or self.FIXED_UTC
        optimizer = self.optimizer()
        cfg = optimizer.cfg
        values = {
            cfg.demand_window_sensor: demand_state,
            cfg.grid_export_limit: export_state,
            cfg.grid_import_limit: import_state,
        }
        states = {
            cfg.demand_window_sensor: self._snapshot(
                demand_state,
                updated_at,
                # This looks fresh but must be discarded until correlated.
                reported_at=self.FIXED_UTC,
            ),
            cfg.grid_export_limit: self._snapshot(
                export_state,
                updated_at,
                reported_at=self.FIXED_UTC,
                attributes={"max": export_max},
            ),
            cfg.grid_import_limit: self._snapshot(
                import_state,
                updated_at,
                reported_at=self.FIXED_UTC,
            ),
        }
        metadata = {
            entity_id: self._metadata_row(
                entity_id,
                value,
                updated_at,
                reported_at,
            )
            for entity_id, value in values.items()
        }
        if metadata_mutator is not None:
            metadata_mutator(metadata, cfg)
        ha = _MetadataHA(states, metadata, metadata_error=metadata_error)
        optimizer.ha = ha
        with self.optimizer_time(self.FIXED_UTC):
            state = asyncio.run(optimizer._read_state())
        return optimizer, ha, state

    def _import_opportunity_state(self, parsed_state):
        return self.state(
            self.FIXED_AFTERNOON,
            demand_window_active=parsed_state.demand_window_active,
            demand_window_observed=parsed_state.demand_window_observed,
            battery_soc=30.0,
            available_discharge_energy_kwh=9.0,
            current_price=-0.35,
            current_price_cents=-35.0,
            price_is_actual=True,
            feedin_price=0.0,
            feedin_price_cents=0.0,
            pv_kw=0.0,
            solar_power_now_kw=0.0,
            load_kw=1.0,
        )

    @staticmethod
    def _closed_decision() -> Decision:
        return Decision(
            ems_mode=MODE_MAX_SELF,
            export_limit=0.0,
            import_limit=0.0,
            pv_max_power_limit=25.0,
            ess_charge_limit=25.0,
            ess_discharge_limit=25.0,
            export_intent=EXPORT_BLOCKED,
        )

    def test_correlated_live_metadata_trusts_demand_and_both_grid_limits(self) -> None:
        optimizer, ha, state = self._read_d7_state(
            demand_state="off",
            export_state=0.01,
            import_state=7.5,
        )

        self.assertFalse(state.demand_window_active)
        self.assertTrue(state.demand_window_observed)
        self.assertTrue(state.current_export_limit_observed)
        self.assertTrue(state.current_import_limit_observed)
        self.assertEqual(0.01, state.current_export_limit)
        self.assertEqual(7.5, state.current_import_limit)
        self.assertEqual(25.0, state.grid_export_limit_entity_max_kw)
        self.assertEqual(1, len(ha.report_metadata_calls))
        requested = ha.report_metadata_calls[0]
        self.assertIn(optimizer.cfg.demand_window_sensor, requested)
        self.assertIn(optimizer.cfg.grid_export_limit, requested)
        self.assertIn(optimizer.cfg.grid_import_limit, requested)

    def test_fresh_trusted_off_permits_import_and_fresh_trusted_on_blocks(self) -> None:
        for raw_state, expected_active, expected_import_open in (
            ("off", False, True),
            ("on", True, False),
        ):
            with self.subTest(raw_state=raw_state):
                optimizer, _ha, parsed = self._read_d7_state(demand_state=raw_state)
                decision = self.decide(
                    optimizer,
                    self._import_opportunity_state(parsed),
                    self.FIXED_AFTERNOON,
                )

                self.assertEqual(expected_active, parsed.demand_window_active)
                self.assertTrue(parsed.demand_window_observed)
                self.assertEqual(expected_import_open, decision.import_limit > 0.011)

    def test_demand_window_is_trusted_through_360_second_boundary(self) -> None:
        for age_seconds in (120, 300, 360):
            with self.subTest(age_seconds=age_seconds):
                optimizer, _ha, parsed = self._read_d7_state(
                    demand_state="off",
                    reported_at=self.FIXED_UTC - timedelta(seconds=age_seconds),
                )
                decision = self.decide(
                    optimizer,
                    self._import_opportunity_state(parsed),
                    self.FIXED_AFTERNOON,
                )

                self.assertFalse(parsed.demand_window_active)
                self.assertTrue(parsed.demand_window_observed)
                self.assertGreater(decision.import_limit, 0.011)

    def test_demand_window_just_over_360_seconds_blocks_import_but_preserves_raw_state(self) -> None:
        stale_report = self.FIXED_UTC - timedelta(
            seconds=360,
            microseconds=1,
        )
        for raw_state, expected_active in (("off", False), ("on", True)):
            with self.subTest(raw_state=raw_state):
                optimizer, _ha, parsed = self._read_d7_state(
                    demand_state=raw_state,
                    reported_at=stale_report,
                )
                decision = self.decide(
                    optimizer,
                    self._import_opportunity_state(parsed),
                    self.FIXED_AFTERNOON,
                )

                self.assertEqual(expected_active, parsed.demand_window_active)
                self.assertFalse(parsed.demand_window_observed)
                self.assertEqual(0.0, decision.import_limit)
                self.assertTrue(decision.trace_gates["demand_window_import_blocked"])
                self.assertFalse(decision.trace_gates["demand_window_observed"])

    def test_missing_unavailable_and_malformed_demand_window_fail_closed(self) -> None:
        for raw_state in (None, "unavailable", "unknown", "invalid"):
            with self.subTest(raw_state=raw_state):
                if raw_state is None:
                    optimizer = self.optimizer()
                    ha = _MetadataHA({}, {})
                    optimizer.ha = ha
                    with self.optimizer_time(self.FIXED_UTC):
                        parsed = asyncio.run(optimizer._read_state())
                else:
                    optimizer, _ha, parsed = self._read_d7_state(
                        demand_state=raw_state,
                    )
                decision = self.decide(
                    optimizer,
                    self._import_opportunity_state(parsed),
                    self.FIXED_AFTERNOON,
                )

                self.assertFalse(parsed.demand_window_active)
                self.assertFalse(parsed.demand_window_observed)
                self.assertEqual(0.0, decision.import_limit)
                self.assertEqual(
                    "demand_window_untrusted_block",
                    decision.trace_values["import_branch"],
                )

    def test_demand_uncertainty_does_not_create_battery_export_or_reduce_pv_max(self) -> None:
        for stale_raw_active in (False, True):
            with self.subTest(stale_raw_active=stale_raw_active):
                optimizer = self.optimizer()
                state = self.state(
                    self.FIXED_AFTERNOON,
                    demand_window_active=stale_raw_active,
                    demand_window_observed=False,
                    current_price=0.30,
                    current_price_cents=30.0,
                    price_is_actual=True,
                    feedin_price=0.15,
                    feedin_price_cents=15.0,
                    pv_kw=5.0,
                    solar_power_now_kw=5.0,
                    load_kw=1.0,
                    current_pv_max_power_limit=2.0,
                )

                decision = self.decide(optimizer, state, self.FIXED_AFTERNOON)

                self.assertEqual(0.0, decision.import_limit)
                self.assertEqual("none", decision.trace_values["battery_export_owner"])
                self.assertNotEqual(BATTERY_EXPORT, decision.export_intent)
                self.assertEqual(
                    optimizer.cfg.pv_max_power_normal,
                    decision.pv_max_power_limit,
                )

    def test_demand_notification_ignores_trust_loss_and_alerts_on_trusted_on_edge(self) -> None:
        ha = _NotificationHA()
        optimizer = self.optimizer(
            ha,
            notification_service="notify.test",
            notify_export_started_stopped=False,
            notify_import_started_stopped=False,
            notify_battery_alerts=False,
            notify_price_spike_alert=False,
            notify_demand_window_alert=True,
        )
        previous = self._closed_decision()
        current = self._closed_decision()
        uncertain = self.state(
            self.FIXED_AFTERNOON,
            demand_window_active=True,
            demand_window_observed=False,
        )
        trusted_on = self.state(
            self.FIXED_AFTERNOON,
            demand_window_active=True,
            demand_window_observed=True,
        )

        asyncio.run(optimizer._handle_notifications(uncertain, current, previous))
        self.assertEqual([], ha.notifications)
        asyncio.run(optimizer._handle_notifications(trusted_on, current, previous))
        self.assertEqual(1, len(ha.notifications))

    def test_grid_limit_readbacks_at_121_seconds_are_untrusted_but_remain_diagnostic(self) -> None:
        _optimizer, _ha, state = self._read_d7_state(
            export_state=25.0,
            import_state=15.0,
            reported_at=self.FIXED_UTC - timedelta(seconds=121),
            export_max=10.0,
        )

        self.assertEqual(25.0, state.current_export_limit)
        self.assertEqual(15.0, state.current_import_limit)
        self.assertFalse(state.current_export_limit_observed)
        self.assertFalse(state.current_import_limit_observed)
        self.assertEqual(10.0, state.grid_export_limit_entity_max_kw)

    def test_fresh_negative_grid_limit_readbacks_are_untrusted_but_remain_diagnostic(
        self,
    ) -> None:
        _optimizer, _ha, state = self._read_d7_state(
            export_state=-1.0,
            import_state=-1.0,
        )

        self.assertEqual(-1.0, state.current_export_limit)
        self.assertEqual(-1.0, state.current_import_limit)
        self.assertFalse(state.current_export_limit_observed)
        self.assertFalse(state.current_import_limit_observed)

    def test_negative_grid_limit_is_not_observed_even_with_explicit_provenance(
        self,
    ) -> None:
        optimizer = self.optimizer()

        self.assertFalse(optimizer._grid_limit_is_observed(-1.0, True))

    def test_live_negative_grid_limit_readback_retains_value_without_trust(self) -> None:
        ha = RecordingHA()
        optimizer = self.optimizer(ha)
        ha._record_state_value(optimizer.cfg.grid_export_limit, -1.0)

        value, trusted = asyncio.run(
            optimizer._read_trusted_live_number(optimizer.cfg.grid_export_limit)
        )

        self.assertEqual(-1.0, value)
        self.assertFalse(trusted)

    def test_failed_or_missing_enrichment_discards_fake_rest_last_reported(self) -> None:
        for label, error in (("missing", None), ("failed", RuntimeError("boom"))):
            with self.subTest(label=label):
                def remove_metadata(metadata, _cfg):
                    metadata.clear()

                _optimizer, _ha, state = self._read_d7_state(
                    metadata_mutator=remove_metadata,
                    metadata_error=error,
                )

                self.assertFalse(state.demand_window_observed)
                self.assertFalse(state.current_export_limit_observed)
                self.assertFalse(state.current_import_limit_observed)

    def test_state_or_last_updated_metadata_mismatch_is_not_trusted(self) -> None:
        def state_mismatch(metadata, cfg):
            metadata[cfg.grid_export_limit]["state"] = "999"
            metadata[cfg.grid_import_limit]["state"] = "999"
            metadata[cfg.demand_window_sensor]["state"] = "on"

        def updated_mismatch(metadata, cfg):
            mismatched = (self.FIXED_UTC - timedelta(hours=2)).isoformat()
            metadata[cfg.grid_export_limit]["last_updated"] = mismatched
            metadata[cfg.grid_import_limit]["last_updated"] = mismatched
            metadata[cfg.demand_window_sensor]["last_updated"] = mismatched

        for label, mutator in (
            ("state", state_mismatch),
            ("last_updated", updated_mismatch),
        ):
            with self.subTest(label=label):
                _optimizer, _ha, state = self._read_d7_state(
                    metadata_mutator=mutator,
                )
                self.assertFalse(state.demand_window_observed)
                self.assertFalse(state.current_export_limit_observed)
                self.assertFalse(state.current_import_limit_observed)

    def test_untrusted_ownerless_export_opening_closes_instead_of_opening(self) -> None:
        ha = RecordingHA()
        optimizer = self.optimizer(ha)
        state = self.state(
            self.FIXED_AFTERNOON,
            current_export_limit=0.01,
            current_export_limit_observed=False,
        )
        decision = Decision(
            ems_mode=MODE_MAX_SELF,
            export_limit=25.0,
            import_limit=0.0,
            pv_max_power_limit=25.0,
            ess_charge_limit=25.0,
            ess_discharge_limit=25.0,
            export_intent=MSC_SURPLUS_CEILING,
            requires_verified_msc_before_export=True,
        )

        result = asyncio.run(optimizer._apply(state, decision))
        export_calls = [
            call for call in ha.calls
            if call[0] == "set_number" and call[1] == optimizer.cfg.grid_export_limit
        ]

        self.assertEqual(
            [("set_number", optimizer.cfg.grid_export_limit, 0.01)],
            export_calls,
        )
        self.assertFalse(result.succeeded)

    def test_untrusted_high_export_and_import_readbacks_cannot_suppress_safety_closes(self) -> None:
        ha = RecordingHA()
        optimizer = self.optimizer(ha)
        state = self.state(
            self.FIXED_AFTERNOON,
            current_export_limit=25.0,
            current_export_limit_observed=False,
            current_import_limit=25.0,
            current_import_limit_observed=False,
        )

        result = asyncio.run(optimizer._apply(state, self._closed_decision()))

        self.assertIn(
            ("set_number", optimizer.cfg.grid_export_limit, 0.01),
            ha.calls,
        )
        self.assertIn(
            ("set_number", optimizer.cfg.grid_import_limit, 0.01),
            ha.calls,
        )
        self.assertTrue(result.succeeded)

    def test_untrusted_import_readback_withholds_permissive_opening(self) -> None:
        ha = RecordingHA()
        optimizer = self.optimizer(ha)
        state = self.state(
            self.FIXED_AFTERNOON,
            current_import_limit=0.01,
            current_import_limit_observed=False,
        )
        decision = self._closed_decision()
        decision.import_limit = 25.0

        result = asyncio.run(optimizer._apply(state, decision))
        import_calls = [
            call for call in ha.calls
            if call[0] == "set_number" and call[1] == optimizer.cfg.grid_import_limit
        ]

        self.assertEqual(
            [("set_number", optimizer.cfg.grid_import_limit, 0.01)],
            import_calls,
        )
        self.assertFalse(result.succeeded)

    def test_untrusted_export_readback_cannot_prove_safety_close_settled(self) -> None:
        ha = RecordingHA(settle_numbers=False)
        optimizer = self.optimizer(ha)
        state = self.state(
            self.FIXED_AFTERNOON,
            current_export_limit=0.01,
            current_export_limit_observed=False,
        )

        result = asyncio.run(optimizer._apply(state, self._closed_decision()))

        self.assertFalse(result.succeeded)
        self.assertIn("readback remains open or unavailable", result.error)

    def test_negative_export_readback_cannot_prove_safety_close_settled(self) -> None:
        ha = RecordingHA(settle_numbers=False)
        optimizer = self.optimizer(ha)
        cfg = optimizer.cfg
        ha._record_state_value(cfg.grid_export_limit, -1.0)
        state = self.state(
            self.FIXED_AFTERNOON,
            current_export_limit=-1.0,
            current_export_limit_observed=True,
            current_import_limit=25.0,
            current_import_limit_observed=True,
        )

        result = asyncio.run(optimizer._apply(state, self._closed_decision()))

        self.assertIn(("set_number", cfg.grid_export_limit, 0.01), ha.calls)
        self.assertIn(("set_number", cfg.grid_import_limit, 0.01), ha.calls)
        self.assertFalse(result.succeeded)
        self.assertIn("readback remains open or unavailable", result.error)

    def test_negative_import_readback_cannot_authorize_permissive_opening(self) -> None:
        ha = RecordingHA()
        optimizer = self.optimizer(ha)
        cfg = optimizer.cfg
        state = self.state(
            self.FIXED_AFTERNOON,
            current_import_limit=-1.0,
            current_import_limit_observed=True,
        )
        decision = self._closed_decision()
        decision.import_limit = 25.0

        result = asyncio.run(optimizer._apply(state, decision))

        self.assertIn(("set_number", cfg.grid_import_limit, 0.01), ha.calls)
        self.assertNotIn(("set_number", cfg.grid_import_limit, 25.0), ha.calls)
        self.assertFalse(result.succeeded)

    def test_deliberate_export_with_unknown_prior_position_settles_before_discharge(self) -> None:
        ha = RecordingHA()
        optimizer = self.optimizer(ha)
        state = self.state(
            self.FIXED_AFTERNOON,
            current_ems_mode=MODE_MAX_SELF,
            current_export_limit=25.0,
            current_export_limit_observed=False,
        )
        decision = Decision(
            ems_mode=MODE_CMD_DISCHARGE_PV,
            export_limit=5.0,
            import_limit=0.0,
            pv_max_power_limit=25.0,
            ess_charge_limit=25.0,
            ess_discharge_limit=25.0,
            export_intent=BATTERY_EXPORT,
        )

        result = asyncio.run(optimizer._apply(state, decision))
        export_index = ha.calls.index(
            ("set_number", optimizer.cfg.grid_export_limit, 5.0)
        )
        mode_index = ha.calls.index(
            ("select_option", optimizer.cfg.ems_mode_select, MODE_CMD_DISCHARGE_PV)
        )

        self.assertLess(export_index, mode_index)
        self.assertTrue(result.succeeded)

    def test_deliberate_export_does_not_change_ems_when_target_cannot_settle(self) -> None:
        ha = RecordingHA(settle_numbers=False)
        optimizer = self.optimizer(ha)
        optimizer._wait_for_number_at_most = AsyncMock(return_value=False)
        state = self.state(
            self.FIXED_AFTERNOON,
            current_ems_mode=MODE_MAX_SELF,
            current_export_limit=25.0,
            current_export_limit_observed=False,
        )
        decision = Decision(
            ems_mode=MODE_CMD_DISCHARGE_PV,
            export_limit=5.0,
            import_limit=0.0,
            pv_max_power_limit=25.0,
            ess_charge_limit=25.0,
            ess_discharge_limit=25.0,
            export_intent=BATTERY_EXPORT,
        )

        result = asyncio.run(optimizer._apply(state, decision))

        self.assertFalse(result.succeeded)
        self.assertNotIn(
            ("select_option", optimizer.cfg.ems_mode_select, MODE_CMD_DISCHARGE_PV),
            ha.calls,
        )

    def test_none_grid_provenance_is_not_legacy_permissive_proof(self) -> None:
        ha = RecordingHA()
        optimizer = self.optimizer(ha)
        state = self.state(
            self.FIXED_AFTERNOON,
            current_export_limit=0.01,
            current_import_limit=0.01,
            current_export_limit_observed=None,
            current_import_limit_observed=None,
        )
        decision = self._closed_decision()
        decision.export_limit = 25.0
        decision.import_limit = 25.0
        decision.export_intent = MSC_SURPLUS_CEILING
        decision.requires_verified_msc_before_export = True

        result = asyncio.run(optimizer._apply(state, decision))

        self.assertFalse(result.succeeded)
        self.assertNotIn(
            ("set_number", optimizer.cfg.grid_export_limit, 25.0),
            ha.calls,
        )
        self.assertNotIn(
            ("set_number", optimizer.cfg.grid_import_limit, 25.0),
            ha.calls,
        )
