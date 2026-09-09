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

## 2026-09-07 - Complete all audit remediation before Phase 2

Decision: Reopen Phase 1 and complete every audit-remediation package, full validation, and renewed live acceptance before beginning Phase 2. Phase 2 remains frozen until that gate passes.

Rationale: The live Morning Slow defect and broader authority/fail-closed findings invalidate the earlier Phase 1-complete gate.

## 2026-09-07 - Unknown operator ownership is not Automated authority

Decision: Permissive automatic actions require observed Automated ownership. Missing, unknown, unavailable, stale, or cached-only ownership does not grant Automated authority. Manual and Force remain user-owned.

Rationale: Automatic writes must not proceed when the operator's ownership state cannot be proven.

## 2026-09-07 - Demand Window fails closed for import

Decision: Observed Demand Window ON blocks import and observed OFF permits ordinary policy, subject to other safeguards. Unknown, unavailable, missing, stale, or otherwise untrustworthy state also blocks import until trustworthy observation resumes.

Rationale: Loss of the higher-priority import-block signal must not silently enable economic import.

## 2026-09-07 - HA-control service success is not authority

Decision: A successful HA-control `turn_on` service call does not grant same-cycle control authority. Observed HA-control ON is required.

Rationale: Service acceptance proves only that a request was accepted, not that control state changed.

## 2026-09-07 - Split Morning Slow policy from grid-transfer deadband

Decision: Do not tune `MIN_GRID_TRANSFER_KW` to repair Morning Slow. Separate the grid-transfer deadband from Morning Slow charging eligibility and ownership.

Rationale: Combining the configured 2 kW slow-charge rate with the 1 kW transfer threshold creates an unintended 3 kW PV-surplus gate and overloads an unrelated setting.

## 2026-09-07 - Preserve Evening Boost

Decision: Evening Boost behavior is intentional and must remain unchanged during audit remediation unless separately reviewed and approved.

Rationale: The audit did not establish Evening Boost as a defect, so remediation must not broaden into an unrelated policy redesign.

## 2026-09-07 - Trusted non-positive import is a charging owner

Decision: Once implemented, trusted actual import price `<= 0 $/kWh` is an explicit high-priority charging owner. It selects Grid First and the maximum safe/permitted grid-import and ESS-charge capabilities in separate domains; overrides Morning Slow charging/EMS ownership and Morning Dump; remains subordinate to Demand Window, Manual/Force, and hardware/safety limits; returns to MSC plus slow charge when price becomes positive and Morning Slow is eligible; and does not itself imply PV curtailment. Positive price must not steal Morning Slow ownership.

Rationale: Non-positive import has distinct economic intent, but still requires explicit ownership, separated capabilities, and preserved safety priority.

Unresolved: exact-zero import when FiT/export is extremely valuable, and PV MAX behavior during non-positive import. These are not settled by this decision.

## 2026-09-08 - Unknown current grid limits provide asymmetric evidence

Decision: Missing, unavailable, unknown, stale, or non-finite current grid-import/export limit telemetry cannot suppress a required safety-close command and cannot itself authorize permissive opening. Opening requires a trusted finite current-limit observation; trusted finite values retain normal deadband behavior.

Rationale: Untrusted actuator telemetry cannot prove that an actuator is safely closed. Safety therefore permits an idempotent closure request but withholds broader permission until trustworthy finite state is observed.

Implementation status: Production Remediation Package 1 satisfies this decision in automated validation only. It remains uncommitted, undeployed, and not live-accepted; Phase 1 is not complete.

## 2026-09-09 - Align the Cheap-FiT exact-full exception with MSC flow safety

Decision: Supersede the 2026-09-04 rule that any material trusted battery discharge closes the Cheap-FiT exact-full exception. The exception now uses the existing trusted ordinary-MSC flow distinction: load-serving battery discharge with grid export below the meaningful threshold is compatible with `MSC_SURPLUS_CEILING`, while meaningful simultaneous battery discharge plus grid export and unknown or untrusted battery/grid-export evidence remain fail-closed. The ceiling creates no `BATTERY_EXPORT` owner and cannot select a discharge EMS mode. The raw `pv_only_discharge_ok` predicate remains unchanged for policies that still intentionally require it.

Rationale: The central MSC flow model already distinguishes benign site-load service from evidence of stored-battery export. Reusing that contract prevents the exact-full branch from contradicting ordinary MSC safety without weakening simultaneous-export or telemetry-trust protections.
