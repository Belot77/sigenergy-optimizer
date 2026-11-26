from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

from app.optimizer import MODE_MAX_SELF, _ActuatorApplicationResult
from app.solar_provider_handoff import SolarProviderHandoff
from app.state_store import StateStore
from app.storage_worker import StorageUnavailable, StorageWorker
from haos49_characterization_helpers import RecordingHA
from test_phase1_solar_dynamic_charge_ceiling_characterization import SolarDynamicChargeFixture


class ProviderHA(RecordingHA):
    def __init__(self, version="4.6.1"):
        super().__init__()
        self.version = version
        self.witness = {}
        self.report_advances = 2
        self.republish_at = None
        self.witness_available = True
        self.service_accepted = True
        self.services = []
        self.after_republish = None

    async def get_solar_provider_handoff_witness(self, entities):
        if not self.witness_available:
            return {}
        return {entity: deepcopy(self.witness[entity]) for entity in entities}

    async def call_service(self, domain, service, data):
        self.services.append((domain, service, data))
        if not self.service_accepted:
            return False
        for entity in data["entity_id"][:self.report_advances]:
            self.witness[entity]["last_reported"] = self.republish_at
        if self.after_republish:
            self.after_republish()
        return True


class SolarProviderRestartHandoffTests(SolarDynamicChargeFixture):
    BOOT_ID = "02ab6635-1813-4bb9-94e7-4c0c60f840e3"
    DUE_IN = 600
    WHEN = datetime(2026, 1, 15, 14, tzinfo=timezone.utc)

    def _at(self, seconds):
        return self.WHEN + timedelta(seconds=seconds)

    def _iso(self, seconds):
        return self._at(seconds).isoformat()

    @contextmanager
    def _clock(self, seconds, *, elapsed=None):
        with self.optimizer_time(self._at(seconds)), patch(
            "app.optimizer.monotonic", return_value=1000 + (seconds if elapsed is None else elapsed)
        ):
            yield

    @asynccontextmanager
    async def _storage(self):
        path = str(Path(self._tmp.name) / "handoff.db")
        with patch.object(StateStore, "solar_provider_host_boot_id", return_value=self.BOOT_ID):
            worker = await StorageWorker.open(lambda: StateStore(path))
            try:
                yield worker
            finally:
                await worker.close()

    def _with_ha(self, ha, worker):
        opt = self._optimizer(ha=ha)
        opt._tz = timezone.utc
        opt._storage_worker = worker
        # Leave actual data ingestion, provider evaluation and decision logic in
        # the tick. Simulate actuation and unrelated bookkeeping.
        opt._apply = AsyncMock(return_value=_ActuatorApplicationResult(
            succeeded=True, automatic_application_completed=True,
        ))
        opt._reconcile_import_storage = AsyncMock()
        opt._publish_hvac_solar_permission = AsyncMock()
        opt._handle_notifications = AsyncMock()
        opt._handle_daily_summaries = AsyncMock()
        return opt

    def _live_states(self, opt, *, seconds=0, poll=0, due=DUE_IN, pv_kw=6.0, load_kw=1.0):
        ha = opt.ha
        cfg = opt.cfg
        # Keep a provider State revision stable while fresh electrical meter
        # reports and forecasts' scheduling metadata can be read independently.
        def row(value, *, at=seconds, **attrs):
            stamp = self._iso(at)
            return {"state": str(value), "attributes": attrs, "last_changed": stamp,
                    "last_updated": stamp, "last_reported": stamp}

        ha.states = {
            cfg.pv_power_sensor: row(pv_kw),
            cfg.consumed_power_sensor: row(load_kw),
            cfg.battery_soc_sensor: row(60),
            cfg.rated_capacity_sensor: row(10, unit_of_measurement="kWh"),
            cfg.available_discharge_sensor: row(6),
            cfg.battery_power_sensor: row(0),
            cfg.grid_import_power_sensor: row(0),
            cfg.grid_export_power_sensor: row(0),
            cfg.sun_entity: row("above_horizon", next_setting=self._iso(4 * 3600),
                                next_rising=self._iso(17 * 3600)),
            cfg.price_sensor: row(0.30),
            cfg.feedin_sensor: row(0.05),
            cfg.demand_window_sensor: row("off"),
            cfg.forecast_remaining_sensor: row(40),
            cfg.forecast_today_sensor: row(
                40, at=poll, detailedForecast=self._detailed_forecast([6, 6] + [3] * 7, when=self._at(-1800)),
            ),
            cfg.forecast_tomorrow_sensor: row(30),
            cfg.solar_power_now_sensor: row(pv_kw),
            cfg.solcast_api_last_polled_sensor: row(self._iso(poll), at=poll, next_auto_update=self._iso(due)),
            cfg.daily_import_energy: row(0),
            cfg.grid_import_limit: row(0.01, max=30, min=0.01, step=0.01, unit_of_measurement="kW"),
            cfg.grid_export_limit: row(25, max=25, min=0.01, step=0.01, unit_of_measurement="kW"),
            cfg.pv_max_power_limit: row(25),
            cfg.ems_mode_select: row(MODE_MAX_SELF),
            cfg.ha_control_switch: row("on"),
            cfg.sigenergy_mode_select: row("Automated"),
            cfg.ess_max_charging_limit: row(5, max=5, min=0, step=0.01, unit_of_measurement="kW"),
            cfg.ess_max_discharging_limit: row(25, max=25, min=0, step=0.01, unit_of_measurement="kW"),
        }
        for index, entity in enumerate(opt._solar_provider_source):
            context_id = f"revision-{index}-{poll}"
            ha.states[entity]["context"] = {"id": context_id}
            ha.witness[entity] = {
                **{key: ha.states[entity][key] for key in ("state", "last_changed", "last_updated")},
                "last_reported": self._iso(max(poll, seconds - 1)),
                "context_id": context_id,
                "entry_id": "native-solcast-test",
                "domain": "solcast_solar",
                "entry_state": "loaded",
                "version": ha.version,
            }
        ha.republish_at = self._iso(seconds)

    async def _save_previously_verified(self, worker, *, version="4.6.1"):
        opt = self._with_ha(ProviderHA(version), worker)
        with self._clock(-1):
            await opt.load_solar_provider_handoff()
            opt.on_ws_connect()
            self._live_states(opt, seconds=-1, poll=-60)
            self._assert_ordinary(await opt.run_once())
        with self._clock(0):
            self._live_states(opt)
            decision = await opt.run_once()
            self.assertEqual(decision.trace_values["solar_provider_reason"], "provider_success_verified")
            self.assertTrue(
                decision.trace_gates["solar_charge_ceiling_owned"],
                decision.trace_values["solar_charge_ceiling_reason"],
            )
            await opt.save_solar_provider_handoff()
        self.assertEqual(opt.ha.services, [])
        return decision

    def _assert_ordinary(self, decision, *, reason="baseline_requires_provider_advance"):
        self.assertFalse(decision.trace_gates["solar_provider_authority_trusted"])
        self.assertFalse(decision.trace_gates["solar_charge_ceiling_owned"])
        self.assertEqual(decision.ess_charge_limit, self.NORMAL_CHARGE_KW)
        if reason is not None:
            self.assertEqual(decision.trace_values["solar_provider_reason"], reason)

    def test_clean_restart_restores_only_after_connected_read_and_uses_fresh_inputs(self):
        async def run(version):
            async with self._storage() as worker:
                with self.assertLogs("app.optimizer", level="INFO") as handoff_log:
                    original = await self._save_previously_verified(worker, version=version)
                    opt = self._with_ha(ProviderHA(version), worker)
                    with self._clock(8):
                        self._live_states(opt, seconds=8, pv_kw=4.0, load_kw=2.0, due=1200)
                        await opt.load_solar_provider_handoff()
                        self.assertIsNotNone(opt._solar_provider_handoff)
                        self.assertIsNone(await worker.call("take_solar_provider_handoff"))
                        self._assert_ordinary(await opt.run_once(), reason=None)
                        self.assertEqual(opt.ha.services, [])
                        opt.on_ws_connect()
                        restored = await opt.run_once()
                messages = [record.getMessage() for record in handoff_log.records]
                for outcome in (
                    "load: checkpoint_missing", "save: saved", "load: loaded", "restore: revalidated",
                ):
                    self.assertEqual(messages.count(f"Solar restart handoff {outcome}"), 1, messages)
                self.assertIsNone(opt._solar_provider_handoff)
                self.assertEqual(opt.ha.services, [(
                    "homeassistant", "update_entity", {"entity_id": list(opt._solar_provider_source)},
                )])
                self.assertTrue(restored.trace_gates["solar_provider_authority_trusted"])
                self.assertTrue(restored.trace_gates["solar_charge_ceiling_owned"])
                self.assertEqual(restored.trace_values["solar_provider_reason"], "provider_clean_restart_revalidated")
                self.assertEqual(restored.trace_values["solar_provider_verified_polled"], self._iso(0))
                self.assertEqual(restored.trace_values["solar_provider_deadline"], self._iso(self.DUE_IN))
                self.assertEqual(restored.trace_values["solar_provider_advertised_next_update"], self._iso(1200))
                self.assertGreater(restored.ess_charge_limit, original.ess_charge_limit)
                self.assertLess(restored.ess_charge_limit, self.NORMAL_CHARGE_KW)
                self.assertEqual(opt._apply.await_args.args[0].pv_kw, 4.0)
                self.assertEqual(opt._apply.await_args.args[0].load_kw, 2.0)

        for version in ("4.6.1", "4.6.3"):
            with self.subTest(version=version):
                asyncio.run(run(version))

    def test_ineligible_witnesses_never_resume_or_retry_the_same_receipt(self):
        async def run(case, expected_calls, expected_rejection):
            async with self._storage() as worker:
                await self._save_previously_verified(worker)
                version = "4.6.3" if case == "integration_version_changed" else "4.6.1"
                opt = self._with_ha(ProviderHA(version), worker)
                seconds = self.DUE_IN if case == "expired" else 8
                with self._clock(seconds), self.assertLogs("app.optimizer", level="INFO") as handoff_log:
                    await opt.load_solar_provider_handoff()
                    opt.on_ws_connect()
                    self._live_states(opt, seconds=seconds, due=1200)
                    first, second = opt._solar_provider_source
                    if case == "witness_missing_or_unsupported":
                        opt.ha.witness_available = False
                    elif case == "revision_changed":
                        opt.ha.witness[first]["context_id"] = "replacement-provider-state"
                    elif case == "no_report_advanced":
                        opt.ha.report_advances = 0
                    elif case == "only_one_report_advanced":
                        opt.ha.report_advances = 1
                    elif case == "service_failed":
                        opt.ha.service_accepted = False
                    elif case == "rest_context_changed":
                        opt.ha.states[second]["context"]["id"] = "changed-after-witness"
                    elif case == "rest_forecast_changed":
                        opt.ha.states[first]["attributes"]["detailedForecast"][1]["pv_estimate"] = 2.5
                    self._assert_ordinary(await opt.run_once())
                    self.assertIsNone(opt._solar_provider_handoff)
                    self._assert_ordinary(await opt.run_once())
                    self.assertEqual(len(opt.ha.services), expected_calls)
                if expected_rejection is not None:
                    messages = [record.getMessage() for record in handoff_log.records]
                    self.assertEqual(
                        messages.count(f"Solar restart handoff restore: {expected_rejection}"), 1, messages,
                    )

        for case, expected_calls, expected_rejection in (
            ("expired", 0, None),
            ("witness_missing_or_unsupported", 0, None),
            ("revision_changed", 0, "native_revision_changed_before_refresh"),
            ("integration_version_changed", 0, "native_revision_changed_before_refresh"),
            ("no_report_advanced", 1, "reports_unverified_after_refresh"),
            ("only_one_report_advanced", 1, "reports_unverified_after_refresh"),
            ("service_failed", 1, "refresh_rejected"),
            ("rest_context_changed", 1, None),
            ("rest_forecast_changed", 1, None),
        ):
            with self.subTest(case=case):
                asyncio.run(run(case, expected_calls, expected_rejection))

    def test_malformed_checkpoint_is_logged_without_its_contents(self):
        async def run():
            async with self._storage() as worker:
                malformed = "diagnostic-fixture-malformed-receipt"
                await worker.call("save_solar_provider_handoff", malformed)
                opt = self._with_ha(ProviderHA(), worker)
                with self._clock(0), self.assertLogs("app.optimizer", level="INFO") as handoff_log:
                    await opt.load_solar_provider_handoff()

                self.assertIsNone(opt._solar_provider_handoff)
                self.assertIsNone(await worker.call("take_solar_provider_handoff"))
                messages = [record.getMessage() for record in handoff_log.records]
                self.assertIn("Solar restart handoff load: checkpoint_invalid", messages)
                self.assertNotIn("Solar restart handoff load: checkpoint_missing", messages)
                self.assertTrue(all(malformed not in message for message in messages))

        asyncio.run(run())

    def test_in_flight_provider_revision_change_and_reconnect_reject_receipt(self):
        async def run(disconnect):
            async with self._storage() as worker:
                await self._save_previously_verified(worker)
                opt = self._with_ha(ProviderHA(), worker)

                def provider_changed():
                    if disconnect:
                        opt.on_ws_disconnect()
                        opt.on_ws_connect()
                    else:
                        entity = opt._solar_provider_source[0]
                        obj = opt.ha.states[entity]
                        opt.on_provider_state_observation(entity, obj, obj)

                with self._clock(8):
                    await opt.load_solar_provider_handoff()
                    opt.on_ws_connect()
                    self._live_states(opt, seconds=8)
                    opt.ha.after_republish = provider_changed
                    self._assert_ordinary(await opt.run_once(), reason=None)
                    self.assertEqual(len(opt.ha.services), 1)
                with self._clock(9):
                    self._live_states(opt, seconds=9)
                    self._assert_ordinary(await opt.run_once(), reason=None)

        for disconnect in (False, True):
            with self.subTest(disconnect=disconnect):
                asyncio.run(run(disconnect))

    def test_chained_restart_does_not_extend_original_monotonic_deadline(self):
        async def run():
            async with self._storage() as worker:
                await self._save_previously_verified(worker)
                opt = self._with_ha(ProviderHA(), worker)
                with self._clock(8):
                    await opt.load_solar_provider_handoff()
                    opt.on_ws_connect()
                    self._live_states(opt, seconds=8)
                    self.assertTrue((await opt.run_once()).trace_gates["solar_provider_authority_trusted"])
                with self._clock(16, elapsed=20):  # Allowable skew behind the inherited wall projection.
                    self._live_states(opt, seconds=16)
                    await opt.save_solar_provider_handoff()
                    raw = await worker.call("take_solar_provider_handoff")
                    receipt = SolarProviderHandoff.from_json(raw)
                    self.assertIsNotNone(receipt)
                    self.assertEqual(receipt.saved_monotonic, 1020)
                    self.assertEqual(receipt.saved_wall, self._at(20).timestamp())
                    self.assertEqual(receipt.deadline, self._at(self.DUE_IN).timestamp())
                    self.assertEqual(
                        receipt.saved_monotonic + receipt.deadline - receipt.saved_wall, 1000 + self.DUE_IN
                    )
                    await worker.call("save_solar_provider_handoff", raw)
                again = self._with_ha(ProviderHA(), worker)
                with self._clock(21, elapsed=25):
                    await again.load_solar_provider_handoff()
                    again.on_ws_connect()
                    self._live_states(again, seconds=21)
                    self.assertTrue((await again.run_once()).trace_gates["solar_provider_authority_trusted"])
                with self._clock(596, elapsed=600):
                    self._live_states(again, seconds=596, due=1200)
                    expired = await again.run_once()
                    self._assert_ordinary(expired, reason="provider_restart_clock_or_deadline_lost")
                    self.assertEqual(expired.trace_values["solar_provider_state"], "EXPIRED")

        asyncio.run(run())

    def test_storage_failure_leaves_the_existing_cold_boot_path(self):
        async def run():
            async with self._storage() as worker:
                await self._save_previously_verified(worker)
                opt = self._with_ha(ProviderHA(), worker)
                with self._clock(8), patch.object(worker, "call", side_effect=StorageUnavailable("fixture")):
                    await opt.load_solar_provider_handoff()
                    opt.on_ws_connect()
                    self._live_states(opt, seconds=8)
                    self._assert_ordinary(await opt.run_once())
                    self.assertEqual(opt.ha.services, [])
                with self._clock(9):
                    self._live_states(opt, seconds=9, poll=9)
                    qualified = await opt.run_once()
                    self.assertTrue(qualified.trace_gates["solar_provider_authority_trusted"])
                    self.assertEqual(qualified.trace_values["solar_provider_reason"], "provider_success_verified")

        asyncio.run(run())
