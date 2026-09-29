# Roadmap

This roadmap is ordered by dependency. Later work must not bypass the stated safety, validation, release, and live-proof gates.

## 1. Phase 1 code validation

Status: **PASSED locally** at `7649d185b71fe08fab2636801396e2ae7c793a13`.

The seven local remediation checkpoints are `0 behind / 7 ahead` of `origin/fix/phase1-audit-remediation`. The final gate collected 735 tests: 733 passed and only the two frozen Phase 2 transition-safety tests failed; compileall and `git diff --check` passed. The final checkpoint corrected a stale safe-fallback protection-test expectation without changing production code.

These commits have not been pushed, released, deployed, installed, restarted, or live-proven. Current known live remains `2.3.50-haos61` at `76db9e43588f0e9862d73e4e8402c0b5ce9773a7`; documented known-good rollback remains `2.3.46-haos57` at `7144fd3d52069e3e8ef1e4df9bc8943bdd65dbe7`.

## 2. Phase 1 checkpoint documentation

Status: **checkpoint documentation reconciled**.

The checkpoint records the local code-validation result, durable semantics, live `.61` baseline, protected Phase 2 failures, and unresolved meaning of the proposed 15 kW physical-relief configuration. Documentation does not constitute release or live acceptance.

## 3. Phase 1 push, release, deployment, and live acceptance

Requires separate explicit approval. Push the seven local code/test checkpoints together with an approved documentation checkpoint, prepare a release, deploy/restart, and obtain controlled live proof. Repository validation and service-call success are not live settlement proof.

Before configuring the discussed `15.0 kW` physical threshold and `0.5 kW` headroom, decide whether 15 kW is merely the site-export level that releases Morning Slow's 2 kW charge cap or a hard network/export limit. Current physical-relief behavior does not enforce a hard cap.

Separate observed follow-up: the 27 September morning trace showed Solar's aggregate energy budget crossing near its threshold with repeated export-ceiling switching. Investigate it independently; the near-full repair and these seven checkpoints do not establish a fix. The operator must decide from focused evidence whether it blocks final Phase 1 acceptance.

Gate: Phase 1 release and live acceptance, including disposition of retained follow-ups, must pass before Phase 2 begins.

## 4. Phase 2 transition-settlement safety

Status: **paused/frozen until the Phase 1 live gate passes**.

Implement the observed close -> later observe closed -> request MSC -> later observe exact MSC -> reopen sequence in `CONTROL_CONTRACT.md`. Entering deliberate battery export must settle its export target before discharge EMS. Service-call success never counts as observation.

Protect the two existing expected Phase 2 failures:

- `test_exact_msc_does_not_reopen_before_export_is_observed_closed`
- `test_return_from_discharge_waits_for_observed_close_before_requesting_msc`

Then run targeted transition tests, complete regression testing, a test release, and controlled live proof.

Gate: Phase 2 must be stable and live-accepted before downstream integration or restructuring.

## 5. Short control-ownership audit

After Phase 2, confirm that every owner changes only its own actuator domains and that Manual, Force, freshness, price, reserve, import-cost, and settlement protections compose correctly. Resolve material findings before restructuring or integration.

## 6. Architecture refactor / consolidation

Treat architecture consolidation as an explicit phase, not incidental cleanup.

- Preserve known-good behaviour unless a separately approved safety change requires otherwise.
- Separate “is it safe to act?”, “what should we do?”, and “apply/write it to Sigenergy” more clearly.
- Isolate Home Assistant/Sigenergy actuator application behind a clearer boundary.
- Consolidate duplicated or dead control paths only where proven safe.
- Preserve protection and characterization tests.
- Do not perform a wholesale rewrite merely for neatness.
- Do not wholesale-merge old experimental or refactor branches. Salvage useful ideas individually after fresh review.

The old `refactor/msc-baseline-overlays` worktree is a reference, not a branch to merge wholesale.

## 7. Repository / project cleanup

Perform this as its own phase after the architecture refactor:

- reconcile stale documentation;
- audit obsolete or dead tests without weakening protections;
- clean obsolete branches and worktrees only with explicit approval;
- identify stale local and recovery artifacts;
- confirm that `main`, tags, and live release history are coherent;
- remove obsolete configuration and UI remnants where safe;
- leave `CURRENT_STATE.md`, `AI_HANDOVER.md`, `ROADMAP.md`, `CONTROL_CONTRACT.md`, and `DECISIONS.md` coherent;
- converge toward one obvious active development path rather than accumulating permanent worktrees.

## 8. Full GUI / UX redesign and functional corrections

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

## 9. Climate Manager integration

Climate Manager integration comes only after Phase 1 live acceptance -> Phase 2 -> the ownership audit -> architecture refactor -> project cleanup -> GUI/UX overhaul. Do not jump directly from the ownership audit to Climate Manager.

Integrate the stable `sensor.sigenergy_hvac_solar_permission` interface (`start`, `continue`, `blocked`, `unavailable`). SigEnergy Optimizer owns energy opportunity and safety; Climate Manager owns HVAC profiles, zones, targets, comfort/manual behavior, AC0, and AirTouch commands.

## 10. Integration-specific UI polish

After Climate Manager integration, complete cross-component integration validation and final operator-facing UI polish without weakening the preceding gates or ownership boundaries.

Sequencing decision reserved for operator review: any proposal to move Climate Manager ahead of the architecture/project-cleanup/full-GUI sequence, or to begin Climate-specific UI work before the full GUI/UX phase, changes the approved order and requires an explicit decision. Until then, the order above remains authoritative.

## 11. Later work

Only after the preceding phases and gates:

- additional diagnostics and ownership visibility;
- deterministic replay tooling;
- evidence-driven load and forecast modelling;
- further Evening Boost redesign beyond the validated dedicated minimum-FiT decoupling, only if separately approved and engineered;
- Package 6B, only if deliberately resumed;
- experimental dynamic solar scheduling on a separate branch, proved through replay, shadow comparison, and a bounded live trial before any merge.

These later items must not bypass or displace earlier safety, validation, and live-proof work.
