from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace

from fastapi import HTTPException

from app.routers.api import ESSRequest, set_ess


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
        self.last_decision = None
        self.last_state = SimpleNamespace(sigenergy_mode="Automated")
        self.audit_events: list[dict[str, object]] = []
        self.manual_overrides: list[tuple[float | None, float | None]] = []

    def get_power_caps_kw(self) -> tuple[float, float]:
        return 30.0, 30.0

    def record_audit_event(self, **event: object) -> None:
        self.audit_events.append(event)

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


if __name__ == "__main__":
    unittest.main()
