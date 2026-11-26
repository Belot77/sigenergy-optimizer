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
    ENTRY_ID = "native-solcast-test"
    DEVICE_ID = "native-solcast-device"

    def __init__(self, version="4.6.1"):
        super().__init__()
        self.version = version
        self.witness = {}
        self.witness_available = True
        self.loaded_entry_id = self.ENTRY_ID
        self.cached_forecast = None
        self.handoff_reads = []
        self.services = []
        self.after_query = None

    async def bulk_states(self, entity_ids):
        return deepcopy(await super().bulk_states(entity_ids))

    async def get_solar_provider_handoff_witness(self, entities):
        self.handoff_reads.append(("witness", entities))
        if not self.witness_available:
            return {}
        return {entity: deepcopy(self.witness[entity]) for entity in entities}

    async def get_loaded_solcast_entry_id(self):
        self.handoff_reads.append(("entry", self.loaded_entry_id))
        return self.loaded_entry_id

    async def query_solcast_cached_forecast(self, start, end):
        self.handoff_reads.append(("cache", start, end))
        self.events.append(("cache", "", None))
        result = deepcopy(self.cached_forecast)
        if self.after_query:
            self.after_query()
        return result

    async def call_service(self, domain, service, data):
        self.services.append((domain, service, data))
        return True

    def cache_query_count(self):
        return sum(read[0] == "cache" for read in self.handoff_reads)


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
                "entry_id": ha.ENTRY_ID,
                "device_id": ha.DEVICE_ID,
                "domain": "solcast_solar",
                "entry_state": "loaded",
                "version": ha.version,
            }
        ha.cached_forecast = deepcopy(ha.states[cfg.forecast_today_sensor]["attributes"]["detailedForecast"])

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
        self.assertEqual(opt.ha.cache_query_count(), 0)
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
                        startup_witness = deepcopy(opt.ha.witness)
                        # The cache may encode equivalent instants with local offsets.
                        provider_zone = timezone(timedelta(hours=11))
                        for period in opt.ha.cached_forecast:
                            period["period_start"] = datetime.fromisoformat(
                                period["period_start"]
                            ).astimezone(provider_zone).isoformat()
                        await opt.load_solar_provider_handoff()
                        self.assertIsNotNone(opt._solar_provider_handoff)
                        self.assertIsNone(await worker.call("take_solar_provider_handoff"))
                        self._assert_ordinary(await opt.run_once(), reason=None)
                        self.assertEqual(opt.ha.handoff_reads, [])
                        opt.on_ws_connect()
                        restored = await opt.run_once()
                messages = [record.getMessage() for record in handoff_log.records]
                for outcome in (
                    "load: checkpoint_missing", "save: saved", "load: loaded", "restore: revalidated",
                ):
                    self.assertEqual(messages.count(f"Solar restart handoff {outcome}"), 1, messages)
                self.assertIsNone(opt._solar_provider_handoff)
                self.assertEqual(opt.ha.services, [])
                self.assertEqual(opt.ha.witness, startup_witness)
                self.assertEqual(opt.ha.handoff_reads, [
                    ("witness", opt._solar_provider_source),
                    ("entry", ProviderHA.ENTRY_ID),
                    ("cache", self._at(-1800), self._at(8 * 1800)),
                    ("entry", ProviderHA.ENTRY_ID),
                    ("witness", opt._solar_provider_source),
                ])
                cache_read = opt.ha.handoff_reads[2]
                self.assertIs(cache_read[1].tzinfo, timezone.utc)
                self.assertIs(cache_read[2].tzinfo, timezone.utc)
                fresh_meter_read = ("bulk_states", opt.cfg.pv_power_sensor, None)
                # The disconnected tick reads meters without attempting a handoff.
                meter_reads = [index for index, event in enumerate(opt.ha.events) if event == fresh_meter_read]
                self.assertLess(opt.ha.events.index(("cache", "", None)), meter_reads[-1])
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

        for version in ("4.6.1", "4.6.3", "4.6.4", "4.6.5"):
            with self.subTest(version=version):
                asyncio.run(run(version))

    def test_ineligible_cache_proofs_never_resume_or_retry_the_same_receipt(self):
        async def run(case, expected_queries, expected_rejection):
            async with self._storage() as worker:
                await self._save_previously_verified(worker)
                version = "4.6.5" if case == "integration_version_changed" else "4.6.1"
                opt = self._with_ha(ProviderHA(version), worker)
                seconds = self.DUE_IN if case == "expired" else 8
                with self._clock(seconds), self.assertLogs("app.optimizer", level="INFO") as handoff_log:
                    await opt.load_solar_provider_handoff()
                    opt.on_ws_connect()
                    self._live_states(opt, seconds=seconds, due=1200)
                    first, second = opt._solar_provider_source
                    ha = opt.ha
                    if case == "witness_missing":
                        ha.witness_available = False
                    elif case == "revision_changed":
                        ha.witness[first]["context_id"] = "replacement-provider-state"
                    elif case == "device_changed":
                        for witness in ha.witness.values():
                            witness["device_id"] = "replacement-solcast-device"
                    elif case == "entry_unavailable":
                        ha.loaded_entry_id = None
                    elif case == "entry_differs_from_witness":
                        ha.loaded_entry_id = "different-entry"
                    elif case == "entry_changed_during_query":
                        ha.after_query = lambda: setattr(ha, "loaded_entry_id", "different-entry")
                    elif case == "witness_missing_after_query":
                        ha.after_query = lambda: setattr(ha, "witness_available", False)
                    elif case == "witness_changed_after_query":
                        def replace_native_device():
                            for witness in ha.witness.values():
                                witness["device_id"] = "different-device"

                        ha.after_query = replace_native_device
                    elif case == "report_regressed_after_query":
                        ha.after_query = lambda: ha.witness[first].update(last_reported=self._iso(seconds - 2))
                    elif case == "report_in_future_after_query":
                        ha.after_query = lambda: ha.witness[first].update(last_reported=self._iso(seconds + 60))
                    elif case == "cache_missing":
                        ha.cached_forecast = None
                    elif case == "cache_incomplete":
                        ha.cached_forecast.pop(3)
                    elif case == "cache_estimate_changed":
                        ha.cached_forecast[1]["pv_estimate"] = 2.5
                    elif case == "rest_context_changed":
                        ha.states[second]["context"]["id"] = "changed-after-witness"
                    elif case == "rest_forecast_changed":
                        ha.states[first]["attributes"]["detailedForecast"][1]["pv_estimate"] = 2.5
                    elif case == "rest_forecast_changed_after_query":
                        def change_rest_forecast():
                            ha.states[first]["attributes"]["detailedForecast"][1]["pv_estimate"] = 2.5

                        ha.after_query = change_rest_forecast
                    elif case == "both_forecasts_changed":
                        ha.states[first]["attributes"]["detailedForecast"][1]["pv_estimate"] = 2.5
                        ha.cached_forecast[1]["pv_estimate"] = 2.5
                    self._assert_ordinary(await opt.run_once())
                    self.assertIsNone(opt._solar_provider_handoff)
                    queries = opt.ha.cache_query_count()
                    self._assert_ordinary(await opt.run_once())
                    self.assertEqual(opt.ha.services, [])
                    self.assertEqual(opt.ha.cache_query_count(), queries)
                    if expected_queries is not None:
                        self.assertEqual(queries, expected_queries)
                if expected_rejection is not None:
                    messages = [record.getMessage() for record in handoff_log.records]
                    self.assertEqual(
                        messages.count(f"Solar restart handoff restore: {expected_rejection}"), 1, messages,
                    )

        for case, expected_queries, expected_rejection in (
            ("expired", 0, None),
            ("witness_missing", 0, "witness_unavailable_before_query"),
            ("revision_changed", 0, "native_revision_changed_before_query"),
            ("device_changed", 0, "native_revision_changed_before_query"),
            ("integration_version_changed", 0, "native_revision_changed_before_query"),
            ("entry_unavailable", 0, "cache_entry_unverified_before_query"),
            ("entry_differs_from_witness", 0, "cache_entry_unverified_before_query"),
            ("entry_changed_during_query", 1, "cache_entry_unverified_after_query"),
            ("witness_missing_after_query", 1, "witness_unavailable_after_query"),
            ("witness_changed_after_query", 1, "native_revision_changed_after_query"),
            ("report_regressed_after_query", 1, "reports_unverified_after_query"),
            ("report_in_future_after_query", 1, "reports_unverified_after_query"),
            ("cache_missing", 1, "cache_forecast_unverified"),
            ("cache_incomplete", 1, "cache_forecast_unverified"),
            ("cache_estimate_changed", 1, "cache_snapshot_mismatch"),
            ("rest_context_changed", None, None),
            ("rest_forecast_changed", None, None),
            ("rest_forecast_changed_after_query", 1, "cache_snapshot_mismatch"),
            ("both_forecasts_changed", None, None),
        ):
            with self.subTest(case=case):
                asyncio.run(run(case, expected_queries, expected_rejection))

    def test_cache_handoff_respects_shortened_advertised_deadline(self):
        async def run():
            async with self._storage() as worker:
                await self._save_previously_verified(worker)
                opt = self._with_ha(ProviderHA(), worker)
                shortened = self.DUE_IN // 2
                with self._clock(8):
                    await opt.load_solar_provider_handoff()
                    opt.on_ws_connect()
                    self._live_states(opt, seconds=8, due=shortened)
                    restored = await opt.run_once()
                    self.assertTrue(restored.trace_gates["solar_provider_authority_trusted"])
                    self.assertEqual(restored.trace_values["solar_provider_deadline"], self._iso(shortened))
                with self._clock(shortened):
                    self._live_states(opt, seconds=shortened, due=self.DUE_IN)
                    self._assert_ordinary(await opt.run_once(), reason=None)
                    self.assertEqual(opt.ha.cache_query_count(), 1)
                    self.assertEqual(opt.ha.services, [])

        asyncio.run(run())

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
                    opt.ha.after_query = provider_changed
                    self._assert_ordinary(await opt.run_once(), reason=None)
                    self.assertEqual(opt.ha.cache_query_count(), 1)
                    self.assertEqual(opt.ha.services, [])
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
