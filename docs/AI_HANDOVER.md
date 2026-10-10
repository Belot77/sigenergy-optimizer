# SigEnergy Optimizer AI Handover

Last consolidated: 2026-10-10

Read root/project `AGENTS.md`, then `CURRENT_STATE.md`, `CONTROL_CONTRACT.md`, `DECISIONS.md` and `ROADMAP.md`. Verify identity/status before editing.

## Continuation checkpoint

- Work only in `C:/Projects/sigenergy_optimizer-phase1-remediation`; never edit the protected root worktree.
- Branch: `fix/phase2-observed-msc-transition`.
- HEAD: `02c26af2ae47cdb5596a007b5055ba6fbd378bfa`.
- Implementation checkpoint `22602e1ad225e39b7679a1af9d9bf3e04348e887` and .68 metadata at HEAD are committed locally. Four scoped-deferral documents are now modified, unstaged and uncommitted; no production/test changes.
- Phase 2 observed transition settlement is locally complete, code-validated and independently reviewed. Production review and final test-delta review passed.
- Final suite: **920 passed, 913 subtests, zero failures, 201 Pydantic deprecation warnings**. Compileall (`app`, `tests`) and `git diff --check` passed. Both formerly frozen transition tests passed unchanged; exact names are in `CURRENT_STATE.md`.
- Last recorded live identity: `.67 / 2.3.56-haos67`, source `1973ac643c29044e8bfb894873adfdd53c7eb4c8`, based on the 8 October startup/runtime record, not repository defaults. No new live query was made here.
- Known-good rollback: `.65 / 2.3.54-haos65`, source `9965e79133f38d5b9943dcf5a9b04ed6fdab1239`. Do not promote `.66`.

## Prepared .68 release identity

- Version: **2.3.57-haos68**; proposed tag: `v2.3.57-haos68`.
- Proposed image: `ghcr.io/belot77/sigenergy-optimizer:2.3.57-haos68`.
- Metadata committed locally; no tag, build, image publication, deployment or live acceptance. Existing local/remote tag checks found no conflicting .68/2.3.57 identity during release investigation.
- All five established surfaces are synchronized: add-on config version, build version label, plain build stamp, API version and optimizer runtime signature. No controller, test or configuration-default changes.
- Prior Phase 2 validation and both passed reviews remain the behavioural evidence; metadata preparation does not repeat the full suite or compileall.

## Boundaries and outstanding gates

Return from deliberate discharge requires close export -> trusted observed closure -> request MSC -> trusted exact MSC strictly after request -> permitted reopening. Preserve fresh provenance, fail-closed restart/telemetry handling, restrictive PV MAX through fallback, Manual/Force ownership and Demand Window import blocking. Solar fill-deadline, physical-relief and provider-freshness protections remain intact.

Phase 1 remains open. The operator explicitly deferred Evening Boost reserve-instability and Solar threshold-switching fixes and permits consideration of a limited .68 trial before full Phase 1 closure. This scoped exception isolates validation of the observed-settlement repair; it neither accepts the deferred issues nor waives inverter safety. The later combined High/Spike + Medium + independent tier SoC package is unchanged and separate.

## Trial gates and next approval

**Publication: GO for approval** based on prior code/review and metadata validation; no publication action is authorized here. **Deployment: CONDITIONAL GO** for a supervised limited trial, only after actual HA/effective-setting and live checks show Evening Boost cannot interfere and Solar is not causing unsafe behaviour or excessive actuator cycling. Unknown/failed checks mean NO-GO.

Use the publication/trial checklist in `CURRENT_STATE.md`. Check actual enabled/window settings and observed owners, agree the trial duration/cycling limit and stop authority, verify source/image identity and .65 rollback readiness, then capture timestamped requests, trusted readbacks and physical flows. Source defaults and service-call success are insufficient. Stop for lost safety ownership, unproven settlement, unintended export, Boost interference or unsafe/excessive cycling; rollback requires the agreed operator procedure. Restart/telemetry scenarios and any setting/mode changes need separate live authorization.

Next: separately approve a local commit of these four gate documents, then exact publication scope. Controlled installation/restart/trial requires separate approval after operator checks pass, including stop/rollback arrangements. No live queries or writes occurred in this documentation checkpoint; Phase 2 remains code-validated, not live-accepted.
