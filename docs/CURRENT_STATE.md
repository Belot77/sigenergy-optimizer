# Current State

Last consolidated: 2026-10-11

**CURRENT TRUTH ONLY:** durable semantics live in `CONTROL_CONTRACT.md`; sequencing lives in `ROADMAP.md`; historical decisions remain in `DECISIONS.md`.

## Live identity and rollback

- Last reported live: **2.3.57-haos68**, source baseline `0aa616c55a87f204d30193d8006f2e57ba265941`. This is operator-reported live identity, not a new HA/runtime query or an inference from repository metadata.
- Known-good rollback: **2.3.54-haos65**, commit `9965e79133f38d5b9943dcf5a9b04ed6fdab1239`. Do not promote another build to rollback without evidence and approval.
- `.68` has passed reported **scoped Phase 2 live acceptance**. Its **13-second observation gap remains documented and unproven**; neither that interval nor unexercised scenarios are assumed safe by observation.
- The original four-tier candidate was committed and pushed for review as `5989b1c588b3c05e35ae1e13c3b333d2a2796f57`; it is not part of the reported live installation. Prepared candidate identity remains **2.3.58-haos69**, proposed tag `v2.3.58-haos69`. Remediation changes no release metadata and creates no tag, release or image.

## Active worktree and validation

- Worktree: `C:\Projects\sigenergy_optimizer-four-tier`.
- Branch: `feature/four-tier-battery-export`.
- HEAD and independently reviewed corrected checkpoint: `bec1095539b96dbb90b62bd6eb047471e41801f6`. Original candidate: `5989b1c588b3c05e35ae1e13c3b333d2a2796f57`.
- Corrected commit `Fix independent export arbitration and stabilize settlement characterization` contains exactly nine files and was pushed to `origin/feature/four-tier-battery-export`; local and remote SHA were verified equal. The post-audit handoff reports independent GitHub verification and an independent ChatGPT code-audit **GO**: both original arbitration blockers are resolved, with no new release-blocking defect identified in the reviewed code.
- The original candidate's NO-GO is superseded for the corrected code checkpoint. **Code audit is complete; release authorization and physical/live acceptance remain outstanding.** This is the recorded independent audit outcome, not a new audit or HA observation performed for this documentation task.
- Starting worktree was clean. This documentation-only checkpoint modifies exactly `docs/CURRENT_STATE.md`, `docs/AI_HANDOVER.md`, `docs/ROADMAP.md` and `docs/CHANGELOG.md`; nothing is staged and no files are untracked. Production, tests, configuration, metadata, contract and historical decisions remain unchanged.
- Retained reported final full suite, run once after remediation: **945 tests passed, 1079 subtests passed, zero failures, 206 warnings**. Compileall for `app`/`tests` with cache outside the worktree and `git diff --check` passed.
- Focused validation: corrected transition test 1 / 9 subtests; complete transition file 7 / 9; actuator settlement/fallback 22 tests; arbitration 4 / 25; complete four-tier 19 / 136; Solar/Evening/Positive-FiT protections 292 / 277; independent Morning/Demand Window/Manual/Force/telemetry/import-cost/MSC protections 323 / 431. These runs overlap and must not be summed.
- Warnings remain unchanged: 201 Pydantic extra `Field` argument deprecations, four `.dict()` deprecations and one class-based Config deprecation. The previously documented local timezone-data limitation remains an installation-validation gap, not proof of live behavior. Git also reports its existing LF-to-CRLF normalization advisory for the four-tier test; diff check finds no whitespace errors.
- The retained production patch changes only arbitration in `_decide` and `_desired_export_limit`. No new production edit was made during final validation. `_apply`, settlement helpers, startup, hardware-cap helpers and release metadata remain unchanged from the original candidate. All four files predating the clock correction retain their recorded hashes.

## Bounded audit remediation

The completed independent ChatGPT GitHub code audit confirms both original blockers are resolved in the corrected checkpoint:

1. Rejected High/Spike battery proposals no longer suppress independently qualified Solar Bypass or Evening Boost. Qualified High/Spike proposals retain priority and all execution vetoes; a cost-vetoed candidate cannot obtain alternate permission through an overlapping policy.
2. When arbitration selects an independent Solar/Evening policy, legacy High/Spike and Positive-FiT branches cannot intercept it. This preserves qualified Solar ownership when Medium defers, including with legacy opt-ins; it does not create lower-tier battery fallback.

Untrusted available energy still rejects High battery export with zero calculated power and no battery owner/discharge EMS. Independently qualified Solar may retain `MSC_SURPLUS_CEILING` under its own trusted evidence, flow, authority and settlement safeguards. The protected characterization now distinguishes those outcomes and retains unsafe-evidence coverage.

The existing three-cycle Phase 2 test now uses a local shared deterministic clock, explicitly advancing between requests and observations. All original actuator-order assertions remain; nine subcases cover trusted later reports and equal, older, stale or missing export/MSC reports through real application checks. The mechanical indentation correction changes no expectation. A fixed-clock diagnostic reproduced the prior restrictive sequence, but the original failure's timestamps were not captured, so that historical occurrence's exact cause remains unproven. No production settlement defect or live acceptance is claimed.

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
- **Four-tier live acceptance is outstanding.** The completed code-audit GO does not establish safe physical behavior or complete release/live acceptance.
- Further Evening Boost redesign, trusted non-positive-import redesign, Package 6B, experimental scheduling and later architecture/cleanup/GUI/Climate work remain parked under the roadmap; this package does not authorize them.

## Site tuning is not a software default

Last reported operator tuning remains `grid_connection_export_limit_kw=15.0` and `solar_surplus_fill_deadline_margin_minutes=120`; software defaults remain **0.0** and **60** respectively. Morning Slow physical export headroom remains reported at **0.0**. Normal site export permission and PV MAX remain reported at 25 kW. Morning Dump's reported 15% operator floor is not a new software default. None of these settings was queried or written for this checkpoint.

## Next approval and release-preparation gate

Next approval: commit/push this exact four-file documentation checkpoint, proposed message `Record haos69 code-audit GO and remaining release gates`. This task does not authorize that commit/push. No tag, build, release, deployment, installation, restart or HA/inverter write is authorized.

After that documentation checkpoint, the next phase is **bounded .69 release preparation**, requiring separate authorization. Retain prepared candidate **2.3.58-haos69** and proposed tag **v2.3.58-haos69**. Release preparation must verify:

- Exact reviewed source identity `bec1095539b96dbb90b62bd6eb047471e41801f6` and the relationship of any later documentation-only commit to that source.
- No conflicting tag or release, and package/version consistency; prior checks do not substitute for checks at the release boundary.
- Known-good `.65` rollback readiness.
- Effective HA operator settings and observed authority before any installation; these have not been freshly queried.
- A proposed monitor-only and controlled live-acceptance procedure, supervision, and explicit stopping/rollback conditions.

Preserve roadmap dependencies and the open Phase 1/2 gates. Release preparation and code-audit GO do not authorize installation or declare live safety. Before separately authorized live work, confirm source/build identity, effective settings, authority and rollback readiness. Propose monitor-only observation of tier proposals, rejection reasons, final owners and requested limits; controlled live acceptance must capture timestamped requests, fresh readbacks and physical flows through deliberate export and MSC return, reserve/cost boundaries and failed-candidate Morning preservation. Contain unresolved Evening Boost reserve/transition stability and Solar threshold-switching risks. Stop for unsafe flows, lost authority, premature reopening, unproven settlement or limit violations, using separately approved rollback arrangements. Label unexercised scenarios and the 13-second observation gap as unresolved. No release-preparation checks or live actions were executed in this documentation task.
