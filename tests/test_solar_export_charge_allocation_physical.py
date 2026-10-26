from __future__ import annotations

import unittest
from dataclasses import replace

class SolarExportChargeAllocationPhysicalTests(unittest.TestCase):
    """Bounded synthetic feedback characterization, not a trace replay.

    Export, PV, load, battery and report timestamps below are explicit fixture
    assumptions. These checks describe the current offline physical-relief
    contract; they do not establish installed settings or inverter settlement.
    """

    def setUp(self) -> None:
        # Import at setup time so pytest does not collect the helper TestCase's
        # existing characterization methods as part of this module.
        from test_phase1_solar_physical_relief_characterization import (
            SolarPhysicalReliefCharacterizationTests as _PhysicalReliefFixture,
        )

        self.physical = _PhysicalReliefFixture("runTest")
        self.physical.setUp()

    def tearDown(self) -> None:
        self.physical.tearDown()

    def _set_measured_flow(
        self, state, *, reported_at: float, pv_kw: float, load_kw: float,
        export_kw: float, battery_kw: float,
    ):
        state.pv_kw = pv_kw
        state.solar_power_now_kw = pv_kw
        state.load_kw = load_kw
        state.grid_import_power_kw = 0.0
        state.grid_export_power_kw = export_kw
        state.battery_power_sensor_kw = battery_kw

        inputs = state.hvac_solar_inputs
        state.hvac_solar_inputs = replace(
            inputs,
            pv_power=replace(inputs.pv_power, value=pv_kw, observed_at_ts=reported_at),
            load_power=replace(inputs.load_power, value=load_kw, observed_at_ts=reported_at),
            grid_import_power=replace(
                inputs.grid_import_power, value=0.0, observed_at_ts=reported_at,
            ),
            grid_export_power=replace(
                inputs.grid_export_power, value=export_kw, observed_at_ts=reported_at,
            ),
            battery_power=replace(
                inputs.battery_power, value=battery_kw, observed_at_ts=reported_at,
            ),
        )
        return state

    def test_negative_residual_resets_relief_then_four_streams_allow_requalification(self):
        opt = self.physical._optimizer()
        self.physical._ramp(opt, 2)
        self.assertAlmostEqual(0.8, opt._solar_relief.relief_kw)

        # Synthetic measured residual: 16.026 - 1.049 - 15.051 = -0.074 kW.
        # The +0.002 kW direct battery reading does not make the grid-flow
        # aggregate trustworthy under the current strict nonnegative check.
        bad = self.physical._flow_state(5, export=15.051, charge=0.002)
        bad = self._set_measured_flow(
            bad, reported_at=self.physical.WHEN.timestamp() + 5,
            pv_kw=16.026, load_kw=1.049, export_kw=15.051, battery_kw=0.002,
        )
        ceiling, gates, values = self.physical._sample(opt, 5, state=bad)
        self.assertEqual(0.0, ceiling)
        self.assertFalse(gates["solar_physical_relief_flow_trusted"])
        self.assertEqual("physical_flow_untrusted", values["solar_physical_relief_reason"])
        self.assertEqual(0.0, opt._solar_relief.relief_kw)
        self.assertIsNone(opt._solar_relief.command_ts)

        # Reapply the safe baseline before qualifying relief again.
        self.assertEqual(0.0, self.physical._sample(opt, 6)[0])
        self.physical._command(opt, 0.0, 6)
        feedback_names = (
            "pv_power", "load_power", "grid_import_power", "grid_export_power",
        )
        command_ts = self.physical.WHEN.timestamp() + 6
        for lagging in feedback_names:
            state = self.physical._flow_state(7)
            inputs = state.hvac_solar_inputs
            changed = {}
            for name in feedback_names:
                observation = getattr(inputs, name)
                stamp = command_ts if name == lagging else command_ts + 1
                changed[name] = replace(observation, observed_at_ts=stamp)
            state.hvac_solar_inputs = replace(inputs, **changed)
            _, _, values = self.physical._sample(opt, 7, state=state)
            self.assertEqual(0, values["solar_physical_relief_confirmations"], lagging)
            self.assertEqual("awaiting_post_command_feedback",
                             values["solar_physical_relief_reason"])

        self.assertEqual(0.0, self.physical._sample(opt, 8)[0])
        ceiling, _, values = self.physical._sample(opt, 9)
        self.assertAlmostEqual(0.4, ceiling)
        self.assertEqual(0.4, values["solar_physical_relief_kw"])

    def test_stale_or_incoherent_flow_cannot_create_relief(self):
        for case in ("stale_export", "incoherent"):
            with self.subTest(case=case):
                opt = self.physical._optimizer()
                self.physical._prime(opt)
                state = self.physical._flow_state(1)
                if case == "stale_export":
                    state.hvac_solar_inputs = replace(
                        state.hvac_solar_inputs,
                        grid_export_power=replace(
                            state.hvac_solar_inputs.grid_export_power, fresh=False,
                        ),
                    )
                else:
                    state.derived_power_flow_coherent = False

                ceiling, gates, values = self.physical._sample(opt, 1, state=state)
                self.assertEqual(0.0, ceiling)
                self.assertFalse(gates["solar_physical_relief_flow_trusted"])
                self.assertFalse(gates["solar_physical_relief_active"])
                self.assertEqual("physical_flow_untrusted", values["solar_physical_relief_reason"])
                self.assertEqual(0.0, opt._solar_relief.relief_kw)


if __name__ == "__main__":
    unittest.main()
