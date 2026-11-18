from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import ValidationError

from app.routers.api import ESSFieldsRequest, ESSRequest, router, set_ess, set_ess_fields


class _RecordingHA:
    def __init__(
        self,
        *,
        failed_operation: str | None = None,
        raised_operation: str | None = None,
        mode_value: str = "Automated",
    ) -> None:
        self.failed_operation = failed_operation
        self.raised_operation = raised_operation
        self.mode_value = mode_value
        self.calls: list[tuple[object, ...]] = []
        self.state_reads: list[str] = []

    def _result(self, operation: str) -> bool:
        if operation == self.raised_operation:
            raise RuntimeError(f"raised failure for {operation}")
        return operation != self.failed_operation

    async def select_option(self, entity_id: str, option: str) -> bool:
        operation = f"select_option:{entity_id}"
        self.calls.append(("select_option", entity_id, option))
        return self._result(operation)

    async def set_number(self, entity_id: str, value: float) -> bool:
        operation = f"set_number:{entity_id}"
        self.calls.append(("set_number", entity_id, value))
        return self._result(operation)

    async def turn_on(self, entity_id: str) -> bool:
        operation = f"turn_on:{entity_id}"
        self.calls.append(("turn_on", entity_id))
        return self._result(operation)

    async def turn_off(self, entity_id: str) -> bool:
        operation = f"turn_off:{entity_id}"
        self.calls.append(("turn_off", entity_id))
        return self._result(operation)

    async def get_state_value(self, entity_id: str, default: object = None) -> object:
        self.state_reads.append(entity_id)
        return self.mode_value


class _DummyOptimizer:
    def __init__(self) -> None:
        self.cfg = SimpleNamespace(
            ems_mode_select="select.ems_mode",
            grid_export_limit="number.grid_export",
            grid_import_limit="number.grid_import",
            pv_max_power_limit="number.pv_max",
            ess_max_charging_limit="number.ess_charge",
            ess_max_discharging_limit="number.ess_discharge",
            ha_control_switch="switch.ha_control",
            sigenergy_mode_select="select.sigenergy_mode",
            automated_option="Automated",
            block_flow_option="Prevent Import & Export",
        )
        self._control_lock = asyncio.Lock()
        self.last_decision = None
        self.last_state = SimpleNamespace(sigenergy_mode="Automated")
        self.audit_events: list[dict[str, object]] = []
        self.manual_overrides: list[tuple[float | None, float | None]] = []
        self.accounting_invalidations: list[str] = []

    def get_power_caps_kw(self) -> tuple[float, float]:
        return 30.0, 30.0

    def record_audit_event(self, **event: object) -> None:
        self.audit_events.append(event)

    def invalidate_import_accounting(self, reason: str) -> None:
        self.accounting_invalidations.append(reason)

    def set_manual_ess_overrides(
        self,
        *,
        charge_kw: float | None,
        discharge_kw: float | None,
    ) -> None:
        self.manual_overrides.append((charge_kw, discharge_kw))


class SetEssServiceFailureTests(unittest.TestCase):
    @staticmethod
    def _request(optimizer: _DummyOptimizer, ha: _RecordingHA) -> SimpleNamespace:
        return SimpleNamespace(
            app=SimpleNamespace(
                state=SimpleNamespace(optimizer=optimizer, ha=ha),
            ),
            client=SimpleNamespace(host="127.0.0.1"),
            headers={},
        )

    @staticmethod
    def _body(*, ha_control: bool | None = True) -> ESSRequest:
        return ESSRequest(
            ems_mode="Maximum Self Consumption",
            grid_export_limit=12.0,
            grid_import_limit=11.0,
            pv_max_power_limit=10.0,
            ess_charge_limit=9.0,
            ess_discharge_limit=8.0,
            ha_control=ha_control,
        )

    @staticmethod
    def _expected_calls(*, ha_control: bool | None = True) -> list[tuple[object, ...]]:
        calls: list[tuple[object, ...]] = [
            ("select_option", "select.ems_mode", "Maximum Self Consumption"),
            ("set_number", "number.grid_export", 12.0),
            ("set_number", "number.grid_import", 11.0),
            ("set_number", "number.pv_max", 10.0),
            ("set_number", "number.ess_charge", 9.0),
            ("set_number", "number.ess_discharge", 8.0),
        ]
        if ha_control is True:
            calls.append(("turn_on", "switch.ha_control"))
        elif ha_control is False:
            calls.append(("turn_off", "switch.ha_control"))
        return calls

    def test_all_required_calls_succeed_with_existing_response_and_order(self) -> None:
        optimizer = _DummyOptimizer()
        ha = _RecordingHA()

        response = asyncio.run(
            set_ess(self._request(optimizer, ha), self._body())
        )

        self.assertEqual({"ok": True}, response)
        self.assertEqual(self._expected_calls(), ha.calls)
        self.assertEqual(["select.sigenergy_mode"], ha.state_reads)
        self.assertEqual("ok", optimizer.audit_events[-1]["result"])
        self.assertEqual([], optimizer.manual_overrides)

    def test_false_result_from_any_required_call_reports_failure(self) -> None:
        operations = (
            "select_option:select.ems_mode",
            "set_number:number.grid_export",
            "set_number:number.grid_import",
            "set_number:number.pv_max",
            "set_number:number.ess_charge",
            "set_number:number.ess_discharge",
            "turn_on:switch.ha_control",
        )
        expected_calls = self._expected_calls()

        for failed_index, operation in enumerate(operations):
            with self.subTest(operation=operation):
                optimizer = _DummyOptimizer()
                ha = _RecordingHA(failed_operation=operation)

                with self.assertRaises(HTTPException) as raised:
                    asyncio.run(
                        set_ess(self._request(optimizer, ha), self._body())
                    )

                self.assertEqual(500, raised.exception.status_code)
                self.assertIn(
                    "Home Assistant service call failed",
                    str(raised.exception.detail),
                )
                self.assertEqual(expected_calls[: failed_index + 1], ha.calls)
                self.assertEqual([], ha.state_reads)
                self.assertEqual("error", optimizer.audit_events[-1]["result"])
                self.assertEqual([], optimizer.manual_overrides)

    def test_turn_off_false_result_reports_failure(self) -> None:
        optimizer = _DummyOptimizer()
        ha = _RecordingHA(failed_operation="turn_off:switch.ha_control")

        with self.assertRaises(HTTPException) as raised:
            asyncio.run(
                set_ess(
                    self._request(optimizer, ha),
                    self._body(ha_control=False),
                )
            )

        self.assertEqual(500, raised.exception.status_code)
        self.assertEqual(self._expected_calls(ha_control=False), ha.calls)
        self.assertEqual([], ha.state_reads)
        self.assertEqual("error", optimizer.audit_events[-1]["result"])

    def test_raised_service_exception_reports_failure_without_later_calls(self) -> None:
        optimizer = _DummyOptimizer()
        operation = "set_number:number.grid_import"
        ha = _RecordingHA(raised_operation=operation)

        with self.assertRaises(HTTPException) as raised:
            asyncio.run(set_ess(self._request(optimizer, ha), self._body()))

        self.assertEqual(500, raised.exception.status_code)
        self.assertIn("raised failure", str(raised.exception.detail))
        self.assertEqual(self._expected_calls()[:3], ha.calls)
        self.assertEqual([], ha.state_reads)
        self.assertEqual("error", optimizer.audit_events[-1]["result"])

    def test_optional_calls_remain_optional(self) -> None:
        optimizer = _DummyOptimizer()
        ha = _RecordingHA()
        body = ESSRequest(
            ems_mode="Maximum Self Consumption",
            grid_export_limit=12.0,
            grid_import_limit=11.0,
            pv_max_power_limit=10.0,
        )

        response = asyncio.run(set_ess(self._request(optimizer, ha), body))

        self.assertEqual({"ok": True}, response)
        self.assertEqual(self._expected_calls(ha_control=None)[:4], ha.calls)
        self.assertEqual(["select.sigenergy_mode"], ha.state_reads)

    def test_block_flow_manual_overrides_remain_after_successful_sequence(self) -> None:
        optimizer = _DummyOptimizer()
        ha = _RecordingHA(mode_value="Prevent Import & Export")

        response = asyncio.run(
            set_ess(self._request(optimizer, ha), self._body(ha_control=None))
        )

        self.assertEqual({"ok": True}, response)
        self.assertEqual([(9.0, 8.0)], optimizer.manual_overrides)

    def test_pv_only_edit_never_reapplies_mode_export_cap_or_switch(self) -> None:
        for mode in ("Automated", "Manual", "Force Full Export", "Prevent Import & Export"):
            with self.subTest(mode=mode):
                optimizer = _DummyOptimizer()
                ha = _RecordingHA(mode_value=mode)

                response = asyncio.run(
                    set_ess_fields(self._request(optimizer, ha), ESSFieldsRequest(pv_max_power_limit=12))
                )

                self.assertEqual({"ok": True, "accepted_fields": ["pv_max_power_limit"]}, response)
                self.assertEqual([("set_number", "number.pv_max", 12)], ha.calls)
                self.assertEqual([], ha.state_reads)
                self.assertEqual([], optimizer.manual_overrides)
                self.assertEqual(["direct_ess_import_boundary"], optimizer.accounting_invalidations)
                self.assertEqual({"pv_max_power_limit": 12}, optimizer.audit_events[-1]["new_value"])

    def test_explicit_zero_and_off_are_dispatched_in_existing_order(self) -> None:
        optimizer = _DummyOptimizer()
        ha = _RecordingHA()

        response = asyncio.run(
            set_ess_fields(self._request(optimizer, ha), ESSFieldsRequest(ha_control=False, grid_export_limit=0))
        )

        self.assertEqual({"ok": True, "accepted_fields": ["grid_export_limit", "ha_control"]}, response)
        self.assertEqual([("set_number", "number.grid_export", 0), ("turn_off", "switch.ha_control")], ha.calls)

    def test_partial_failure_reports_prior_acceptance_and_stops_later_writes(self) -> None:
        for failure_kind in ("failed_operation", "raised_operation"):
            with self.subTest(failure_kind=failure_kind):
                optimizer = _DummyOptimizer()
                ha = _RecordingHA(**{failure_kind: "set_number:number.grid_export"})
                body = ESSFieldsRequest(
                    ha_control=False,
                    grid_export_limit=12,
                    ems_mode="Maximum Self Consumption",
                )

                with self.assertRaises(HTTPException) as raised:
                    asyncio.run(set_ess_fields(self._request(optimizer, ha), body))

                self.assertEqual(500, raised.exception.status_code)
                self.assertEqual(["ems_mode"], raised.exception.detail["accepted_fields"])
                self.assertEqual("grid_export_limit", raised.exception.detail["failed_field"])
                self.assertEqual(self._expected_calls()[:2], ha.calls)
                self.assertEqual("error", optimizer.audit_events[-1]["result"])
                self.assertEqual(raised.exception.detail, optimizer.audit_events[-1]["details"])

    def test_block_flow_remembers_only_the_successful_battery_field(self) -> None:
        optimizer = _DummyOptimizer()
        ha = _RecordingHA(mode_value="Prevent Import & Export", failed_operation="set_number:number.ess_discharge")
        body = ESSFieldsRequest(ha_control=True, ess_charge_limit=0, ess_discharge_limit=8)

        with self.assertRaises(HTTPException) as raised:
            asyncio.run(set_ess_fields(self._request(optimizer, ha), body))

        self.assertEqual(["ess_charge_limit"], raised.exception.detail["accepted_fields"])
        self.assertEqual("ess_discharge_limit", raised.exception.detail["failed_field"])
        self.assertEqual([
            ("set_number", "number.ess_charge", 0),
            ("set_number", "number.ess_discharge", 8),
        ], ha.calls)
        self.assertEqual([(0, None)], optimizer.manual_overrides)

    def test_invalid_edited_fields_are_rejected_before_any_write(self) -> None:
        for values, key in (
            ({}, "fields"),
            ({"ha_control": None}, "ha_control"),
            ({"ems_mode": "unavailable", "pv_max_power_limit": 12}, "ems_mode"),
            ({"pv_max_power_limit": float("nan")}, "pv_max_power_limit"),
            ({"pv_max_power_limit": float("inf")}, "pv_max_power_limit"),
            ({"grid_import_limit": 31}, "grid_import_limit"),
        ):
            with self.subTest(key=key, values=values):
                optimizer = _DummyOptimizer()
                ha = _RecordingHA()

                with self.assertRaises(HTTPException) as raised:
                    asyncio.run(set_ess_fields(self._request(optimizer, ha), ESSFieldsRequest(**values)))

                self.assertEqual(422, raised.exception.status_code)
                self.assertEqual(key, raised.exception.detail["field_errors"][0]["key"])
                self.assertEqual([], ha.calls)
                self.assertEqual([], optimizer.accounting_invalidations)

        for values in ({"unknown_key": 1}, {"pv_max_power_limit": True}, {"pv_max_power_limit": "12"}):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                ESSFieldsRequest.model_validate(values)

    def test_new_route_checks_auth_again_inside_control_lock(self) -> None:
        optimizer = _DummyOptimizer()
        ha = _RecordingHA()
        lock_states = []

        def authorize(request):
            lock_states.append(optimizer._control_lock.locked())
            if lock_states[-1]:
                raise HTTPException(status_code=401, detail="Changed credentials")

        with patch("app.routers.api._require_mutation_auth", side_effect=authorize):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(set_ess_fields(self._request(optimizer, ha), ESSFieldsRequest(pv_max_power_limit=12)))

        self.assertEqual(401, raised.exception.status_code)
        self.assertEqual([False, True], lock_states)
        self.assertEqual([], ha.calls)
        self.assertEqual([], optimizer.accounting_invalidations)

    def test_http_route_returns_structured_partial_acceptance_and_rejects_extra_fields(self) -> None:
        optimizer = _DummyOptimizer()
        ha = _RecordingHA(failed_operation="set_number:number.pv_max")
        app = FastAPI()
        app.state.optimizer = optimizer
        app.state.ha = ha
        app.include_router(router, prefix="/api")

        async def submit_edits():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                invalid = await client.post("/api/set_ess_fields", json={"pv_max_power_limit": 10, "unknown": 1})
                incomplete = await client.post("/api/set_ess_fields", json={"grid_import_limit": 11, "pv_max_power_limit": 10})
                return invalid, incomplete

        invalid, incomplete = asyncio.run(submit_edits())

        self.assertEqual(422, invalid.status_code)
        self.assertEqual(500, incomplete.status_code)
        self.assertEqual({
            "message": "Home Assistant service call failed: set PV max power limit",
            "accepted_fields": ["grid_import_limit"],
            "failed_field": "pv_max_power_limit",
        }, incomplete.json()["detail"])
        self.assertEqual(self._expected_calls()[2:4], ha.calls)


if __name__ == "__main__":
    unittest.main()
