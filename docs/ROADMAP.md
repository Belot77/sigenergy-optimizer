# Roadmap

This roadmap is ordered by dependency. Later work must not bypass the stated safety, validation, and live-proof gates.

## 1. Checkpoint the validated near-full Phase 1 candidate

Status: **repository checkpoint committed; release decision pending**.

Live Home Assistant is `2.3.49-haos60` from commit `a625ca16e59a3a0ff89fd724510355ef53b79315`; documented known-good rollback is `2.3.46-haos57` at `7144fd3d52069e3e8ef1e4df9bc8943bdd65dbe7`.

The near-full MSC/PV-only safeguard correction, its characterization, and the deterministic advisory clock fixture are committed as `47c591be6bf920a82995b9f402c3efb202ffa5fe`; reconciled documentation follows as a separate checkpoint commit on the same branch. The final repository gate collected 663 tests: 661 passed and only the two frozen Phase 2 tests failed; compileall and `git diff --check` passed.

Next boundary: obtain a separate decision for the exact version/release identity. Version changes, tagging, build/publication, installation/restart, and live acceptance remain separately approved work. Do not invent a `.61` version at this checkpoint.

## 2. Complete Phase 1 live acceptance and reconcile follow-ups

After an approved commit/release sequence, obtain controlled live proof of the repaired candidate. Repository validation and service-call success are not live settlement proof.

The following retained Phase 1 items require explicit state reconciliation before Phase 1 is declared complete; this documentation checkpoint does not prove whether they are already included in live `.60` or remain pending:

- hard-fallback house-supply repair;
- Morning Dump / Morning Slow refill-feasibility protection;
- Morning Slow 15 kW physical-export relief.

Morning Slow remains one bounded policy improvement with two independently diagnosable relief reasons: forecast/refill feasibility and physical export limit.

Separate observed follow-up: the 27 September morning trace showed Solar's aggregate energy budget crossing near its threshold with repeated export-ceiling switching. Investigate it independently; the near-full repair does not prove it fixed. The operator must decide from focused evidence whether it blocks final Phase 1 acceptance. Do not implement a switching correction as part of the near-full checkpoint.

Gate: Phase 1 live acceptance, including disposition of the retained follow-ups, must pass before Phase 2 begins.

## 3. Phase 2 transition-settlement safety

Status: **paused/frozen until the Phase 1 live gate passes**.

Implement the observed close -> later observe closed -> request MSC -> later observe exact MSC -> reopen sequence in `CONTROL_CONTRACT.md`. Entering deliberate battery export must settle its export target before discharge EMS. Service-call success never counts as observation.

Protect the two existing expected Phase 2 failures:

- `test_exact_msc_does_not_reopen_before_export_is_observed_closed`
- `test_return_from_discharge_waits_for_observed_close_before_requesting_msc`

Then run targeted transition tests, complete regression testing, a test release, and controlled live proof.

Gate: Phase 2 must be stable and live-accepted before downstream integration or restructuring.

## 4. Short control-ownership audit

After Phase 2, confirm that every owner changes only its own actuator domains and that Manual, Force, freshness, price, reserve, import-cost, and settlement protections compose correctly. Resolve material findings before restructuring or integration.

## 5. Architecture refactor / consolidation

Treat architecture consolidation as an explicit phase, not incidental cleanup.

- Preserve known-good behaviour unless a separately approved safety change requires otherwise.
- Separate “is it safe to act?”, “what should we do?”, and “apply/write it to Sigenergy” more clearly.
- Isolate Home Assistant/Sigenergy actuator application behind a clearer boundary.
- Consolidate duplicated or dead control paths only where proven safe.
- Preserve protection and characterization tests.
- Do not perform a wholesale rewrite merely for neatness.
- Do not wholesale-merge old experimental or refactor branches. Salvage useful ideas individually after fresh review.

The old `refactor/msc-baseline-overlays` worktree is a reference, not a branch to merge wholesale.

## 6. Repository / project cleanup

Perform this as its own phase after the architecture refactor:

- reconcile stale documentation;
- audit obsolete or dead tests without weakening protections;
- clean obsolete branches and worktrees only with explicit approval;
- identify stale local and recovery artifacts;
- confirm that `main`, tags, and live release history are coherent;
- remove obsolete configuration and UI remnants where safe;
- leave `CURRENT_STATE.md`, `AI_HANDOVER.md`, `ROADMAP.md`, `CONTROL_CONTRACT.md`, and `DECISIONS.md` coherent;
- converge toward one obvious active development path rather than accumulating permanent worktrees.

## 7. Full GUI / UX redesign and functional corrections

Perform a substantial operator-facing information-architecture, presentation, and functional UI redesign after the architecture refactor and project cleanup. This is not equivalent to the completed Package 9 settings/UI cleanup. Preserve backend and control semantics unless separately approved. Do not rewrite the frontend framework merely for appearance or design the GUI around structures that are about to change.

Target information areas:

- **Status/Home:** current mode, EMS, owner, import/export state, battery action, PV MAX, SoC, PV/load/grid.
- **Why:** the current decision and activation or blocking reason in plain English.
- **Policies:** Morning Dump, Morning Slow, Solar Surplus, Demand Window, Evening Boost, Exact-full, and similar policies with enabled, eligible, active, blocked, and reason states.
- **Forecast/Energy:** Solcast remaining energy, expected load, battery refill need, refill feasibility, and margins.
- **Actuators:** requested versus observed EMS, PV MAX, import/export limits, and ESS charge/discharge limits, including settlement state.
- **Safety/Trust:** stale or untrusted telemetry, fail-closed reasons, ownership conflicts, and capability limits.
- **Settings:** grouped by policy rather than one unrelated list.
- **Diagnostics:** advanced technical detail available without dominating the normal operator view.

The GUI must clearly distinguish:

- permission from actual physical flow;
- policy eligibility from active policy ownership;
- requested actuator state from observed settled state;
- deliberate battery-export intent from ordinary MSC battery discharge serving house load.

## 8. Climate Manager integration

Climate Manager integration comes only after Phase 1 live acceptance -> Phase 2 -> the ownership audit -> architecture refactor -> project cleanup -> GUI/UX overhaul. Do not jump directly from the ownership audit to Climate Manager.

Integrate the stable `sensor.sigenergy_hvac_solar_permission` interface (`start`, `continue`, `blocked`, `unavailable`). SigEnergy Optimizer owns energy opportunity and safety; Climate Manager owns HVAC profiles, zones, targets, comfort/manual behavior, AC0, and AirTouch commands.

## 9. Integration-specific UI polish

After Climate Manager integration, complete cross-component integration validation and final operator-facing UI polish without weakening the preceding gates or ownership boundaries.

Sequencing decision reserved for operator review: any proposal to move Climate Manager ahead of the architecture/project-cleanup/full-GUI sequence, or to begin Climate-specific UI work before the full GUI/UX phase, changes the approved order and requires an explicit decision. Until then, the order above remains authoritative.

## 10. Later work

Only after the preceding phases and gates:

- additional diagnostics and ownership visibility;
- deterministic replay tooling;
- evidence-driven load and forecast modelling;
- the separate Evening Boost redesign recorded in `CONTROL_CONTRACT.md`: explicit deliberate battery-export ownership, reserve-based overnight energy protection, stable-condition resumption, and its required import-cost/value/capability engineering review; it is not implemented or live, and its exact scheduling relative to Phase 2 and the architecture initiatives remains an operator decision;
- Package 6B, only if deliberately resumed;
- experimental dynamic solar scheduling on a separate branch, proved through replay, shadow comparison, and a bounded live trial before any merge.

These later items must not bypass or displace earlier safety, validation, and live-proof work.
