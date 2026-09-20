# Current State

Last consolidated: 2026-09-21

**CURRENT TRUTH ONLY:** this file records the current operational and development checkpoint. Durable control semantics live in `CONTROL_CONTRACT.md`; sequencing lives in `ROADMAP.md`.

## Live release and rollback

- Current live release: `2.3.46-haos57`.
- Live candidate commit: `7144fd3d52069e3e8ef1e4df9bc8943bdd65dbe7`.
- No rollback from `.57` has occurred.
- Known-good deeper rollback: `2.3.42-haos53`, tag `v2.3.42-haos53`, commit `19f3c70d24dc086737d5956a1c66cad230287edd`.

No D1-D7 trust remediation described below is live. It is committed and pushed only on the remediation branch. Automated validation does not prove live behavior.

## Active remediation worktree

- Path: `C:\Projects\sigenergy_optimizer-phase1-remediation`
- Branch: `fix/phase1-audit-remediation`
- Last production/test checkpoint: `f2f0720` (`Harden restrictive close handling`)
- This documentation sync is a child of that production/test checkpoint.
- Verify the current branch tip, worktree status, and remote synchronization directly with Git before editing.

Phase 1 work completed, committed, and pushed on this branch includes Packages 1-5, Package 6A, Package 7 `/set_ess` hardening, Package 8 configuration validation/persistence, Package 9 settings/UI cleanup, the Evening Boost safety-critical repair, D1-D7 trust/freshness remediation, the export-notification correction, and the post-D7 F1/R9 repair. Package 6B investigation/design is complete; implementation remains deferred.

The D1-D7 checkpoint commits are useful continuation references: D2 `4ab3f84`, export notifications `2270c2c`, D5 `1e3c78e`, D1 `f350df3`, D3/D4 `f5d1d80`, D6 `0f7fc74`, D7 `50d1169`, and F1/R9 `f2f0720`.

## Protected worktrees

- `C:\Projects\sigenergy_optimizer`: branch `refactor/msc-baseline-overlays`, last known HEAD `bce8411d5274fe17fb8d883e8e7faf43e9ce8d43`; intentionally dirty and protected. Never modify, reset, or stash it without explicit approval.
- `C:\Projects\sigenergy_optimizer-pv-hotfix`: `main` rollback-reference worktree, last known HEAD `19f3c70d24dc086737d5956a1c66cad230287edd`; protected.
- `C:\Projects\sigenergy_optimizer-phase2-transition`: branch `phase2/msc-transition-settlement`, last known HEAD `c624f0b4392634cf19276186ba46f4b80268627b`; frozen and protected until Phase 1 live acceptance.

These are last-known reference states, not fresh verification from this documentation task.

## Current Phase 1 gate

Phase 1 is not complete and the branch is not live-proven. Remaining Phase 1 work is:

1. Design and implement the agreed Solar Surplus behavior.
2. Run the consolidated final-candidate gate.
3. Prepare the release candidate.
4. Obtain final live acceptance of the complete Phase 1 candidate.

Only after that gate may work proceed to Phase 2 transition safety, the short control-ownership audit, and Climate Manager integration.

## D1-D7 trust checkpoint

The branch now enforces the following trust boundaries:

- Aggregate forecasts cannot support future-energy decisions when stale or untrusted.
- Permissive PV-surplus decisions require trusted live PV/load/Solcast evidence; missing, stale, malformed, boolean, non-finite, or out-of-window evidence cannot prove permission.
- Derived battery flow requires fresh, finite, non-negative directional PV/load/grid components coherent within the established skew window. Trusted direct battery telemetry retains precedence; negative directional grid power is untrusted rather than clamped into trusted zero.
- Available discharge energy requires an explicit supported unit, a finite non-negative value, and capability consistency. Missing units do not default to kWh.
- Negative-price forecast entries retain source-specific trust/freshness provenance and cannot prove a future condition when malformed, boolean, non-finite, or outside the permitted window.
- Demand Window uses a dedicated 360-second freshness maximum. Trusted ON blocks import; trusted OFF may permit ordinary import; missing, unavailable, malformed, stale, or otherwise untrusted state fails closed for import without acquiring battery-export or PV-curtailment ownership.
- Dynamic grid import/export current-position readbacks retain the 120-second live-telemetry boundary and require fresh provenance. Missing provenance, stale values, and negative values are not current-position proof and cannot authorize permissive opening; restrictive closes remain allowed.
- Service-call success is not observed settlement. Deliberate battery export must establish the intended export target before discharge EMS is selected. An unproven export close cannot suppress an independent restrictive import-close attempt.
- Export notifications use trusted measured grid export for start/stop classification; changing a ceiling is not proof of physical export.

Live liveness evidence supports the distinct freshness boundaries. The actual Demand Window entity, `binary_sensor.amber_express_home_demand_window`, was observed reporting unchanged ON state at approximately 295-299 second intervals, proving 120 seconds too short and supporting the 360-second policy. The actual dynamic grid-limit entities, `number.sigen_plant_grid_export_limitation` and `number.sigen_plant_grid_import_limitation`, showed unchanged-report heartbeat gaps of approximately 58-61 seconds, so the existing 120-second live-telemetry boundary remains appropriate.

## Independent review and repair

An independent Claude review found two actionable issues, both fixed in `f2f0720`:

- **F1:** after a successful export-close request with unproven settlement, `_apply` could return before attempting an independent restrictive import close. The import `0.01 kW` safety close is now still attempted; application remains failed, ordinary ESS/PV MAX/helper writes remain deferred, and import-close failure is reported.
- **R9:** finite negative dynamic grid-limit readbacks, such as `-1`, could be mistaken for trusted actuator position. Negative values are now untrusted, cannot prove closure, and cannot authorize permissive opening; the raw value may remain diagnostic.

The review's earlier concern about ordinary MSC PV-only ceilings was resolved as not a defect. Ordinary PV-only MSC permission remains separate from deliberate battery export and still requires trusted flow evidence. The frozen Phase 2 pair is unchanged from the review base to branch head.

## Validation state

Final post-F1/R9 validation passed for the F1/R9 cases, D7 liveness, authority fail-closed behavior, actuator settlement/fallback, grid capability/readback, Demand Window/PV MAX, Manual/Force protections, D1-D6 regressions, export notifications, and the MSC/exact-full/chatter suite apart from the intentionally frozen Phase 2 pair.

- Full suite: **565 passed, 2 failed, 510 subtests passed**.
- The only failures are `test_exact_msc_does_not_reopen_before_export_is_observed_closed` and `test_return_from_discharge_waits_for_observed_close_before_requesting_msc`.
- `compileall`: passed.
- `git diff --check`: passed.
- Existing Pydantic deprecation warnings: 192; not a current blocker.

## Protected behavior

- Manual and Force modes remain user-owned.
- Demand Window primarily owns import blocking.
- Ordinary positive-FiT and PV-only MSC ceilings do not create deliberate battery-export ownership or select discharge EMS.
- Normal PV MAX is not reduced merely because Demand Window is uncertain.
- Evening Boost and the established exact-full/MSC chatter protections remain preserved.
- Service-call success never substitutes for trusted observed settlement.

## Relevant operator tuning

These are observed live/operator settings, not software defaults:

- observed normal PV MAX and high export ceiling: `25 kW`;
- `MIN_SOC_FLOOR`: `20%`; `MIN_EXPORT_TARGET_SOC`: `90%`;
- Morning Slow: enabled, `2 kW`, until `11:00`, minimum FiT `0.01 $/kWh`, base-load allowance `2 kW`, sunset cutoff `1 hour`;
- Morning Dump: enabled, `15%` floor;
- Evening Boost: enabled, `35%` floor, safety multiplier `1.1`, minimum tomorrow forecast `100 kWh`;
- `MIN_GRID_TRANSFER_KW`: `1 kW`;
- Forecast Safety Charging: `1.35`; Forecast Safety Export: `1.1`;
- cheap-positive threshold: `0.015 $/kWh`; daytime top-up maximum SoC: `50%`; target battery charge: `2 kW`;
- Demand Window remains the higher-priority import block; Value Gate remains advisory-only.

Existing/live Solar Surplus legacy tuning includes the `2.0` start and `1.25` continuation forecast multipliers and the established measured-surplus margins. These describe the old implementation/operator context only; the approved redesign replaces those multipliers as the primary decision basis with the net-energy budget below.

## Solar Surplus approved direction

Solar Surplus redesign and implementation are not complete. The approved energy order is: serve house load from PV first, preserve enough battery charging to remain safely on the fill trajectory, and export only genuinely remaining PV while FiT is positive.

The main energy budget is remaining-today forecast minus expected remaining load, battery fill need, and a conservative buffer. Detailed Solcast timing may refine that budget. Current measured PV-load surplus must also support the action, and the decision must be recalculated every cycle so export reduces or stops if conditions deteriorate.

Solar Surplus remains MSC/PV-only. It may cap charging to expose genuine surplus when safely justified, but must never discharge the battery merely to create export. Start requires trusted inputs, positive FiT, strong net-energy proof, and measured surplus above `0.5 kW`; continuation uses the same budget model with hysteresis and measured surplus above `0.2 kW`; loss of trust, non-positive FiT, or an unsupported budget stops it. The old capacity-times-2 and 1.25-times heuristics are not the primary trigger. Charging-cap, timing, and priority architecture still require a fresh bounded design before coding.

## Frozen Phase 2 contract

The two expected transition-settlement failures remain intentionally frozen:

- `test_exact_msc_does_not_reopen_before_export_is_observed_closed`
- `test_return_from_discharge_waits_for_observed_close_before_requesting_msc`

They must not be documented as solved by Phase 1.

## Exact next action

Start a new Codex session for a bounded Solar Surplus architecture/design pass, using Ultra reasoning at Standard speed, before making production changes. Then implement and validate the agreed design on the existing remediation branch. Do not begin final candidate preparation, Phase 2, or live acceptance until Solar Surplus is complete.
