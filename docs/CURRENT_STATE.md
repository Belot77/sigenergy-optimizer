# Current State

Last consolidated: 2026-10-11

**CURRENT TRUTH ONLY:** durable semantics live in `CONTROL_CONTRACT.md`; sequencing lives in `ROADMAP.md`; historical decisions remain in `DECISIONS.md`.

## Live identity and rollback

- Last reported live: **2.3.57-haos68**, source baseline `0aa616c55a87f204d30193d8006f2e57ba265941`. This is operator-reported live identity, not a new HA/runtime query or an inference from repository metadata.
- Known-good rollback: **2.3.54-haos65**, commit `9965e79133f38d5b9943dcf5a9b04ed6fdab1239`. Do not promote another build to rollback without evidence and approval.
- `.68` has passed reported **scoped Phase 2 live acceptance**. Its **13-second observation gap remains documented and unproven**; neither that interval nor unexercised scenarios are assumed safe by observation.
- Four-tier changes are local work on the `.68` source baseline. They are not part of the reported live installation. Prepared candidate identity: **2.3.58-haos69**, proposed tag `v2.3.58-haos69`. Fresh upstream tag/release checks found no conflict. The add-on config/build label/buildstamp, API version and runtime signature are synchronized; no tag, release or image was created.

## Active worktree and validation

- Worktree: `C:\Projects\sigenergy_optimizer-four-tier`.
- Branch: `feature/four-tier-battery-export`.
- HEAD: `0aa616c55a87f204d30193d8006f2e57ba265941`.
- Intentionally dirty pre-commit checkpoint: fifteen tracked implementation/test/metadata files plus these six checkpoint documents are modified and uncommitted (21 tracked files); `tests/test_four_tier_battery_export.py` remains untracked. The complete proposed commit contains 22 files. Preserve all changes and all other worktrees.
- The final Low-policy candidate is **code-validated**, but **not committed, pushed, released, installed or live-accepted**. The independent ChatGPT GitHub safety audit is **pending**. Prior `.68` reviews do not constitute review of this delta.
- Final full-suite validation: **941 tests passed, 1045 subtests passed, zero failures, 206 warnings**. Compileall for `app`/`tests`, with cache outside the worktree, and `git diff --check` passed. Targeted tariff trust: 24 tests / 2 subtests; four-tier: 18 / 124; independent Positive-FiT/MSC/Solar: 217 / 208. The preceding broader Morning/actuator/transition/ownership protection run passed 420 tests / 399 subtests. These runs overlap and must not be summed.
- Warning accounting: 201 Pydantic deprecated extra `Field` keyword warnings, four deprecated `.dict()` calls and one class-based Config warning. These identify dependency-migration work, not live-safety proof. The local environment also logged unavailable `Australia/Adelaide` timezone data and UTC fallback; deterministic fixture times do not validate installation timezone behavior.
- Production delta remains limited to `app/optimizer.py`, `app/config.py`, `app/routers/api.py`, `templates/index.html` and `.env.example`, with focused tests. The five established version/signature surfaces additionally prepare `.69` metadata only. Startup, hardware-cap helpers, `.68` transition/settlement infrastructure and `_apply` remain unchanged.

## Four-tier behavior

Ordinary automated deliberate battery export starts at **Medium**. Low remains a price classification and PV-only permission context; it cannot create a battery-export proposal/owner, discharge EMS or Morning preemption, even at 100% SoC or with persisted Low floors of 90%, 0% or any other accepted value. `battery_export_min_soc_low` remains compatible and validated, defaults to **100%**, and cannot re-enable Low sale. Medium / High / Spike retain independently configured floors of **40 / 20 / 10 percent**, with no ordering constraint or selected-tier fallback.

All four keys remain numeric, finite 0-100 inputs with booleans rejected and API/UI round-trip/persistence preserved. Eligible battery tiers require SoC strictly above selected and protected floors, trusted energy/telemetry, context-dependent forecast and reserve evidence, actual import-cost permission, observed operator authority and physical limits. Existing ramp and Spike arithmetic remain unchanged.

Legacy Positive-FiT opt-ins cannot restore Low battery sale. Ordinary positive-FiT MSC and legitimate Solar Bypass retain PV-only behavior. Separately named policies, including Morning Dump and Evening Boost, retain independently guarded deliberate-export authority below Medium; they do not inherit authority from Low. Manual/Force retain operator ownership.

High/Spike may preempt an eligible Morning owner only with a positive bounded candidate after the shared actual import-cost check and all other guards pass. Failed candidates do not displace eligible Morning ownership; untrusted remaining forecast cannot manufacture an eligible Morning Slow owner. High/Spike retain context-dependent untrusted-tomorrow behavior and the daytime near-full measured-PV cap.

`battery_export_owner` records proposal provenance; `battery_export_final_owner` records the final decision owner and is `none` when export is blocked. A qualified proposal may remain visible under a cost veto or missing operator authority without granting discharge, export permission or Morning preemption. Value Gate remains advisory-only; `effective_battery_export_floor` remains a monetary floor, not SoC. Decision diagnostics are not proof of physical settlement.

## Preserved protections and open acceptance

The `.68` sequence remains mandatory: close export -> fresh trusted observed closure -> request MSC -> fresh exact MSC strictly after the request -> permitted reopening. Independent restrictive controls remain effective through uncertainty, fallback and restart. Preserve ordinary MSC, Solar eligibility/provider freshness/fill trajectory/physical relief, Morning, Demand Window import blocking, Manual/Force, forecast/reserve and physical-cap protections.

- **Phase 1 remains open.** Scoped `.67` Solar evidence for handover, physical relief/backoff and fill-deadline relinquishment remains recorded evidence; it does not close Evening Boost reserve/transition stability or Solar threshold-switching disposition. Those follow-ups remain explicitly deferred.
- **Phase 2 has scoped `.68` acceptance only.** The 13-second observation gap and any broader or unexercised live scenarios remain outstanding. Automated tests and accepted service calls cannot fill observation gaps.
- **Four-tier live acceptance is outstanding.** Code validation does not establish safe physical behavior or independent safety acceptance.
- Further Evening Boost redesign, trusted non-positive-import redesign, Package 6B, experimental scheduling and later architecture/cleanup/GUI/Climate work remain parked under the roadmap; this package does not authorize them.

## Site tuning is not a software default

Last reported operator tuning remains `grid_connection_export_limit_kw=15.0` and `solar_surplus_fill_deadline_margin_minutes=120`; software defaults remain **0.0** and **60** respectively. Morning Slow physical export headroom remains reported at **0.0**. Normal site export permission and PV MAX remain reported at 25 kW. Morning Dump's reported 15% operator floor is not a new software default. None of these settings was queried or written for this checkpoint.

## Next approval and installation gate

Approved sequence: **validate -> obtain permission to commit/push the exact checkpoint -> independent ChatGPT GitHub safety audit -> explicit GO/NO-GO -> separately authorized HA installation**. A push is for review, not release or deployment permission. No commit, push, tag, release, installation, restart or HA/inverter write is authorized by this documentation task.

Next approval: one checkpoint commit with message `Implement guarded battery export tiers and prepare haos69 candidate`, then push only to `origin/feature/four-tier-battery-export`. Reverify the exact reviewed 22-file candidate before staging; stop on any difference. No tag/build/release is included in that proposed approval.

Before any separately authorized live trial, verify the exact reviewed source/build identity, effective operator settings, observed authority and `.65` rollback readiness. Use monitor-only/dry-run observation to compare tier proposals, rejection reasons, final owners and requested limits without actuating. Under separate live authorization, capture timestamped requests, fresh readbacks and physical flows through deliberate export and MSC return; include reserve/cost boundaries and failed-candidate Morning preservation. Contain deferred Evening Boost/Solar switching risks, agree supervision and stop/rollback conditions, and label unexercised or missing observations as gaps. Stop for unsafe flows, lost authority, premature reopening, unproven settlement or limit violations. Do not infer permission to inject failures, change settings or restart from this checklist.
