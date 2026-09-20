# SigEnergy Optimizer AI Handover

Last consolidated: 2026-09-21

Read root and project `AGENTS.md`, then `CURRENT_STATE.md`, `CONTROL_CONTRACT.md`, `DECISIONS.md`, and `ROADMAP.md`. Verify the exact worktree, branch, HEAD, and status before editing.

## Live baseline and rollback

- Live: `2.3.46-haos57`, candidate commit `7144fd3d52069e3e8ef1e4df9bc8943bdd65dbe7`.
- No rollback from `.57` has occurred.
- Known-good deeper rollback: `2.3.42-haos53`, tag `v2.3.42-haos53`, commit `19f3c70d24dc086737d5956a1c66cad230287edd`.
- D1-D7 and the post-review repair are branch-only; do not describe them as live.

## Active checkpoint

- Worktree: `C:\Projects\sigenergy_optimizer-phase1-remediation`
- Branch: `fix/phase1-audit-remediation`
- Last production/test checkpoint: `f2f0720` (`Harden restrictive close handling`)
- This documentation sync is a child of that production/test checkpoint.
- Verify the current branch tip, worktree status, and remote synchronization directly with Git before editing.

Packages 1-5, Package 6A, Package 7 `/set_ess` hardening, Package 8 configuration validation/persistence, Package 9 settings/UI cleanup, Evening Boost safety repair, D1-D7 trust/freshness remediation, export-notification correction, and the F1/R9 follow-up are complete, committed, and pushed on this branch. Package 6B design/investigation is complete and implementation remains deferred.

Protected worktrees must not be modified: `C:\Projects\sigenergy_optimizer` is the intentionally dirty reference worktree; `C:\Projects\sigenergy_optimizer-pv-hotfix` is the rollback reference; and `C:\Projects\sigenergy_optimizer-phase2-transition` is frozen until Phase 1 live acceptance. Their precise states in `CURRENT_STATE.md` are last-known references, not verification from this docs task.

## D1-D7 and independent review

D1-D7 establish trusted aggregate forecasts; trusted live PV/load/Solcast evidence; coherent finite, non-negative derived directional flow with direct battery telemetry taking precedence; explicit units and capability consistency for available discharge energy; source-specific negative-price forecast provenance; a 360-second Demand Window boundary distinct from 120-second dynamic inverter telemetry; and provenance-bearing, non-negative grid-limit readbacks for current-position proof.

Observed live cadence supports those boundaries: unchanged Demand Window ON reports arrived about 295-299 seconds apart, while unchanged dynamic grid-limit reports arrived about 58-61 seconds apart.

Independent Claude review found F1 and R9. Commit `f2f0720` ensures that an unproven export close does not prevent an independent restrictive import-close attempt, and that negative grid-limit readbacks cannot prove closure or authorize opening. Its earlier ordinary-MSC concern was resolved as not a defect. The frozen Phase 2 pair remains unchanged.

## Validation

Targeted F1/R9, D1-D7, authority, actuator, grid-readback, Demand Window/PV MAX, Manual/Force, MSC/exact-full/chatter, and export-notification tests passed. The full result is **565 passed, 2 failed, 510 subtests passed**. The only failures are the intentionally frozen Phase 2 tests:

- `test_exact_msc_does_not_reopen_before_export_is_observed_closed`
- `test_return_from_discharge_waits_for_observed_close_before_requesting_msc`

`compileall` and `git diff --check` passed. There are 192 existing Pydantic deprecation warnings. These automated results do not prove live behavior.

## Protected control behavior

Manual and Force remain user-owned. Demand Window primarily owns import blocking. Ordinary positive-FiT and PV-only MSC ceilings do not create battery-export authority. Untrusted Demand Window state fails closed for import without reducing normal PV MAX or acquiring export ownership. Service-call success is not settlement proof. Deliberate export must settle its target before discharge EMS, and an uncertain export close must not suppress an independent restrictive import close. Export notifications follow trusted measured flow, not ceiling changes.

## Phase 1 gate and Solar Surplus

Phase 1 is not complete or live-proven. Solar Surplus redesign/implementation, the consolidated final-candidate gate, release-candidate preparation, and final live acceptance remain.

Approved Solar Surplus behavior is PV -> house load -> enough battery charging to remain safely on the fill trajectory -> export only genuinely remaining PV while FiT is positive. Use remaining-today forecast minus expected remaining load, battery fill need, and a conservative buffer as the main energy budget, refined by detailed Solcast timing and current measured PV-load surplus. Re-evaluate every cycle.

The policy remains MSC/PV-only and must never discharge the battery merely to create export. A safe charging cap may expose genuine surplus. Start requires trusted inputs, positive FiT, strong net-energy proof, and measured surplus above `0.5 kW`; continuation uses the same budget with hysteresis and surplus above `0.2 kW`; loss of trust, non-positive FiT, or an unsupported budget stops export. Do not retain the old capacity-times-2/1.25 heuristics as the primary trigger. Charging-cap, timing, and priority architecture remain to be designed before coding.

Relevant operator context, not software defaults: observed normal PV MAX/high export ceiling is `25 kW`; Morning Slow is enabled at `2 kW` until `11:00` with minimum FiT `0.01 $/kWh`, `2 kW` base-load allowance, and one-hour sunset cutoff; Forecast Safety Charging/Export are `1.35`/`1.1`; Demand Window remains the higher-priority import block; Value Gate remains advisory-only. The existing Solar Surplus `2.0`/`1.25` multipliers are legacy live/operator context that the approved net-energy redesign is intended to replace as the primary decision basis.

## Parked and out of scope

- Package 6B implementation remains deferred.
- Manual/Force stale-readback rewrite churn is parked; do not redesign it during Solar Surplus work.
- Phase 2 remains frozen, and Climate Manager remains after Phase 2 and the short ownership audit.
- Diagnostics, replay tooling, load modelling, and the dynamic scheduler are later work.
- Exact-full/sub-1 kW observation and import-`0.00` A/B work remain parked.
- Do not opportunistically implement unrelated telemetry, tariff, or spike findings during Solar Surplus work.

## Exact next action

Use a **new Codex session**, **Ultra reasoning**, and **Standard speed** for a bounded Solar Surplus architecture/design pass before production changes. After Solar Surplus implementation and validation, run the final candidate gate, prepare the release candidate, and obtain live acceptance. Only then proceed to Phase 2 transition safety, the short control-ownership audit, and Climate Manager integration.
