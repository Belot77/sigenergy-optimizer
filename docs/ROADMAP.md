# Roadmap

This roadmap is ordered by dependency. Later work must not bypass safety, validation, release and live-proof gates except for an explicitly recorded scoped sequencing exception. The scoped `.68` trial and authorized four-tier development below do not waive inverter safety or accept Phase 1.

## 1. Phase 1 code validation

Status: **COMPLETE locally** at code-validation HEAD `7649d185b71fe08fab2636801396e2ae7c793a13`.

The final gate collected 735 tests: 733 passed and only the two frozen Phase 2 transition-safety tests failed; compileall and `git diff --check` passed. The final code/test checkpoint corrected a stale safe-fallback protection-test expectation without changing production code.

The earlier validated Phase 1 checkpoint through docs commit `06efdfd0512e2b88f3431d6206b42c0af7b1c5ce` is present on `origin/fix/phase1-audit-remediation`; that checkpoint recorded remote `main` as `de5b5af082533a48ffb6d0d300f636cbcb4463ad`. At that historical checkpoint, live and rollback were `2.3.54-haos65` at `9965e79133f38d5b9943dcf5a9b04ed6fdab1239`. The provider-aware Solar source checkpoint is `aec127d7efd9fe7787c8253b882207b50a44eeed` on `fix/phase1-audit-remediation`, committed but undeployed at that checkpoint. Current validation and the tests/docs follow-up are recorded in `CURRENT_STATE.md`; Phase 1 live acceptance remains pending.

## 2. Phase 1 checkpoint documentation

Status: **COMPLETE and included in the published feature-branch checkpoint through `06efdfd0512e2b88f3431d6206b42c0af7b1c5ce`**.

The checkpoint records the local code-validation result, durable semantics, live `.61` baseline, protected Phase 2 failures, and unresolved meaning of the proposed 15 kW physical-relief configuration. Documentation does not constitute release or live acceptance.

## 3. Phase 1 feature publication, main promotion, release, deployment, and live acceptance

Feature-branch push: **COMPLETE** through `06efdfd0512e2b88f3431d6206b42c0af7b1c5ce` on `origin/fix/phase1-audit-remediation`.

The publication status above is historical. The 8 October checkpoint records `.67` release/startup and scoped Solar live evidence. Last reported live is now `.68 / 2.3.57-haos68`, source baseline `0aa616c55a87f204d30193d8006f2e57ba265941`; `.65` remains rollback. This checkpoint makes no new live query; current identity and evidence limits are in `CURRENT_STATE.md`.

Formal Phase 1 acceptance and explicit disposition of retained follow-ups remain **PENDING**. Scoped Solar evidence does not establish completion of the separate Evening Boost transition-stability dependency. Repository validation and service-call success are not live settlement proof.

The 7 October decision resolves Solar's 15 kW value as physical saturation evidence, not hard-cap enforcement. The 8 October record reports site configuration of 15 kW with Morning Slow headroom 0.0; the older 0.5 kW discussion is not authority to change it.

Separate observed follow-up: the 27 September morning trace showed Solar's aggregate energy budget crossing near its threshold with repeated export-ceiling switching. Investigate it independently; the near-full repair and these seven checkpoints do not establish a fix. The operator must decide from focused evidence whether it blocks final Phase 1 acceptance.

Gate retained: Phase 1 release and live acceptance, including disposition of retained follow-ups, were prerequisites to beginning Phase 2. Explicit approval allowed Phase 2 local development ahead of this gate; the later scoped trial decision below permits consideration of a limited .68 trial before full Phase 1 closure, without accepting Phase 1 or waiving inverter safety.

## 4. Phase 2 transition-settlement safety

Status (11 October checkpoint): **reported live in `.68`, with scoped Phase 2 live acceptance passed**. The **13-second observation gap remains unproven**; broader/unexercised live acceptance remains outstanding. Development and the limited trial proceeded under the recorded Phase 1 sequencing exception, not Phase 1 completion.

The local implementation enforces the observed close -> later observe closed -> request MSC -> later observe exact MSC -> reopen sequence in `CONTROL_CONTRACT.md`. Entering deliberate battery export must settle its export target before discharge EMS. Service-call success never counts as observation.

Both formerly frozen tests now pass unchanged:

- `test_exact_msc_does_not_reopen_before_export_is_observed_closed`
- `test_return_from_discharge_waits_for_observed_close_before_requesting_msc`

The prior `.68` protection validation and independent production/final test-delta reviews remain historical evidence for the settlement implementation. They do not constitute independent review of the four-tier delta.

The 10 October operator decision deferred Evening Boost reserve-instability and Solar threshold-switching fixes and allowed the limited `.68` trial. Those deferred fixes/acceptance decisions remain open. Scoped acceptance does not establish uninterrupted observation across the retained gap or validate unexercised restart, telemetry-loss or other scenarios.

Any further live work requires separate authorization, effective-setting/authority checks, containment of deferred policy risks, supervision and stop/rollback arrangements. Unknown or failed prerequisites mean NO-GO. Preserve the full observed-settlement contract and all independent restrictive controls.

Gate retained: full Phase 1 disposition and applicable Phase 2 live-proof requirements remain prerequisites to downstream restructuring/integration. The four-tier development authorization below is bounded and does not close those gates.

## 4A. Authorized four-tier battery-export package

Status: **original candidate pushed and independently audited NO-GO; bounded remediation locally validated, uncommitted and unpushed** in `C:/Projects/sigenergy_optimizer-four-tier`, branch `feature/four-tier-battery-export`, HEAD `5989b1c588b3c05e35ae1e13c3b333d2a2796f57`. This authorization supersedes only the earlier parking of combined High/Spike, Medium and independent tier SoC work. It does not grant release or live acceptance.

Ordinary Low battery sale remains disabled regardless of persisted floors/legacy opt-ins; compatible Low default is 100%, independent Medium/High/Spike floors are 40/20/10%. Both audit blockers are addressed locally: rejected High/Spike proposals no longer suppress independently qualified Solar/Evening, and selected independent policies cannot be intercepted by legacy tier/Positive-FiT branches when Medium defers. Qualified High/Spike priority and cost vetoes remain intact. No tier fallback, new ownership semantics or production settlement change is introduced.

Final remediation validation: **945 tests / 1079 subtests passed, zero failures, 206 classified Pydantic deprecation warnings**; compileall with external cache and diff check passed. Nine deterministic timestamp subcases preserve the real strict-after application checks. The original intermittent failure's timestamps remain unavailable. Exact nine-file scope, focused results and evidence limits are recorded in `CURRENT_STATE.md`.

Next gates:

1. Obtain explicit permission for the exact validated nine-file correction, proposed message `Fix independent export arbitration and stabilize settlement characterization`.
2. Reverify scope/hashes/HEAD, commit and push only the feature branch, then verify the new remote SHA. Publication for review is not deployment permission.
3. Obtain independent ChatGPT GitHub re-audit of that SHA. The original NO-GO remains in force until a new explicit GO/NO-GO decision.
4. Retain all Phase 1/2 evidence gaps and deferred issues; seek separately authorized HA installation and bounded live acceptance only after review and applicable gates.

Candidate identity remains `2.3.58-haos69`; remediation changes no release metadata and authorizes no tag, build, release or live action. Last reported live `.68`, known-good `.65` rollback, the unproven 13-second gap and outstanding Phase 1/2/four-tier acceptance remain unchanged. Architecture, cleanup, GUI, Climate and other parked work remain outside this package.

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
