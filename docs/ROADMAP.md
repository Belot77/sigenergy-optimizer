# Roadmap

This roadmap is ordered by dependency. Later work must not bypass the stated live-proof gates.

Update it whenever approved phase order, scope, dependencies, or gates change. Parked ideas do not become approved roadmap work merely because they are documented.

## 1. Finish and live-prove Phase 1

Status: current.

Committed Phase 1 work already separates MSC surplus permission, deliberate battery export, and blocked export; establishes explicit owners; separates Demand Window import ownership; separates positive-FiT export and battery-discharge controls; distinguishes load-serving battery flow; and preserves the exact-full cheap-FiT path.

Mandatory remaining work:

1. Correct Morning Slow Charge so it owns charging rate but retains MSC, normal PV MAX, and the normal high export ceiling without `BATTERY_EXPORT` intent.
2. Run the architecture, Value Gate, haos50-53 protection, compile, and diff validations.
3. Freeze production code.
4. Reconcile the 24 obsolete haos49 characterization failures as tests-only work. Stop if a failure reveals a production defect.
5. Reach the pre-live target: all automated tests green except exactly the two deferred Phase 2 transition tests.
6. Build and install a Phase 1 test release, then prove its control behavior live.

Gate: do not start Phase 2 until Phase 1 is test-complete and live-proven.

## 2. Implement and live-prove Phase 2

Implement the observed close -> observe closed -> request MSC -> observe exact MSC -> reopen sequence defined in `CONTROL_CONTRACT.md`.

Use targeted transition tests, complete regression testing, a test release, and controlled live proof. Service-call success must never count as inverter observation.

Gate: Phase 2 must be stable and live-proven before downstream integration.

## 3. Stabilisation and control-ownership audit

Perform a short, bounded audit after Phase 2. Confirm that each overlay changes only the actuators it owns and that manual, force, freshness, negative-price, reserve, and import-cost protections still compose correctly.

Gate: resolve material ownership defects before Climate Manager integration.

## 4. Climate Manager integration

Integrate the stable SigEnergy Optimizer permission entity only after Phase 2 and stabilisation:

- entity: `sensor.sigenergy_hvac_solar_permission`;
- states: `start`, `continue`, `blocked`, `unavailable`;
- SigEnergy Optimizer owns energy-opportunity and energy-safety determination;
- Climate Manager owns HVAC profiles, zones, targets, manual behavior, comfort policy, AC0, and AirTouch commands.

Climate Manager is not currently consuming this entity. Do not redesign Climate Manager before the upstream contract is stable.

## 5. Operator diagnostics and bounded cleanup

Improve operator-facing diagnostics, control ownership visibility, and UI clarity without broad control-policy redesign.

## 6. Required-SoC presentation cleanup

Preserve internal energy-shortfall information when required or sunrise SoC exceeds 100%. Prefer presenting 100% plus the remaining energy shortfall rather than hiding information through a simple clamp.

## 7. Historical replay framework

Build deterministic replay tooling before experimental scheduling or model changes. Replay must preserve production safety assumptions and support comparison against the live-proven baseline.

## 8. Evidence-driven load and forecast modelling

Investigate load assumptions or forecast modelling only if live evidence shows current configured behavior is inadequate. Do not add speculative complexity or a hard 80 kWh Morning Dump/Morning Slow forecast floor.

## 9. Experimental dynamic solar charge scheduler

Use a separate experimental branch. Objective: maximize economically useful positive-FiT solar export while retaining a forecast-safe trajectory to 100% battery by the end of productive solar.

This work must not block Climate Manager integration and must never be wholesale-merged from the old `feature/safety-actuator-refactor` reference branch.

## 10. Prove the scheduler before any merge

Require, in order:

1. historical replay;
2. shadow-mode comparison;
3. bounded controlled live trial;
4. explicit review of safety and economic results;
5. only then, consideration for merge.
