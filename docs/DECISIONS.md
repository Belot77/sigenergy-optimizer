# Decision Log

This log records durable decisions and their rationale. Volatile checkpoint data belongs in `CURRENT_STATE.md`.

Append concise entries for material architectural or control-policy decisions and their reasons. Do not rewrite prior decisions to hide superseded history; record a changed or superseded decision in a new dated entry. Include operational tuning only when materially relevant, and always label it as operator configuration rather than a software default.

## 2026-09-04 - Normal Automated baseline is MSC

Decision: Normal Automated operation uses Maximum Self Consumption, normal configured PV MAX, the configured high export ceiling, and no deliberate stored-battery export intent.

Rationale: The inverter should dispatch genuine surplus under MSC; ordinary operation should not manufacture a battery-sale command.

## 2026-09-04 - A high export ceiling is permission

Decision: A high grid-export ceiling is permission for available surplus, not an instruction to export at that power and not authority to discharge stored energy.

Rationale: Numeric export capacity and energy provenance are different control concepts.

## 2026-09-04 - Deliberate battery export requires an explicit owner

Decision: `BATTERY_EXPORT` is valid only when a qualifying named policy owns deliberate stored-energy sale. Generic ordinary tier eligibility cannot own it.

Rationale: EMS selection must follow explicit intent rather than infer intent from a positive target.

## 2026-09-04 - Demand Window owns import blocking

Decision: Demand Window primarily controls import permission. It does not implicitly curtail normal PV MAX or create battery-export intent.

Rationale: Import and export ownership must compose independently.

## 2026-09-04 - Morning Dump remains deliberate battery export

Decision: Morning Dump may own `BATTERY_EXPORT` and use `Command Discharging (PV First)` while its existing window, floor, feasibility, and safety conditions remain valid.

Rationale: Unlike an MSC ceiling, Morning Dump intentionally exports stored energy.

## 2026-09-04 - Morning Slow owns charging, not the export ceiling

Decision: Morning Slow controls the ESS charging rate. It retains MSC, normal PV MAX, and the normal high export ceiling and does not create `BATTERY_EXPORT` intent.

Rationale: MSC can charge at the configured slow rate while independently exporting genuine excess PV. Legacy measured-PV export start/ramp gates unnecessarily suppress surplus.

## 2026-09-04 - Preserve the cheap-FiT exact-full distinction

Decision: Below the ordinary threshold, the implicit cheap-FiT path remains closed below 100% SoC. Exact 100% may open only through the verified MSC/PV-only path, and material or unknown battery flow prevents it.

Rationale: The narrow exception prevents PV curtailment without authorizing sale of stored battery energy.

## 2026-09-04 - No hard Morning Dump or Morning Slow forecast floor

Decision: Do not add a fixed 80 kWh or similar PV forecast floor for Morning Dump or Morning Slow at this time. Retain dynamic feasibility logic.

Rationale: No live evidence currently justifies replacing adaptive policy with a hard site-specific threshold.

## 2026-09-04 - Live tuning is not a software default

Decision: Record Forecast Safety Charging 1.30 and Morning Slow Charge Base Load 2.0 kW as current operator tuning only. Do not change defaults from 1.25 and 1.0 kW merely to match the live settings.

Rationale: Operator calibration and distributable defaults have different scopes and evidence requirements.

## 2026-09-04 - Phase 2 requires observed settlement

Decision: The deliberate-export-to-MSC transition must close export, observe closure later, request MSC, observe exact MSC later, and only then reopen the high ceiling. Service-call success is not observation.

Rationale: Inverter state must be proven before a ceiling is reopened.

## 2026-09-04 - Climate Manager follows Phase 2 and stabilisation

Decision: Climate Manager integration begins after Phase 2 is live-proven and a short ownership audit is complete, not after the experimental scheduler.

Rationale: The permission interface needs a stable upstream control foundation; experimental scheduling is not an integration dependency.

## 2026-09-04 - Dynamic solar scheduling is experimental future work

Decision: Develop any dynamic solar charge scheduler on a separate branch and require historical replay, shadow mode, and a bounded controlled live trial before considering merge.

Rationale: Economic optimization must be demonstrated against the live-proven safety baseline before gaining production authority.
