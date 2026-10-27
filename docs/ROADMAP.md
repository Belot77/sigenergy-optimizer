# Roadmap

## Published checkpoint - 27 October 2026 (.82)

Published 27 October 2026 at 00:24:22 UTC:
[GitHub release](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.71-haos82).
Tag/container source: af174d2745f283e3f2e297d57e72d58fada62cb2.
Tag tree: f858b292fd4e6d8b9b67c044bb314cbb9f9455de.
Metadata [PR #50](https://github.com/Belot77/sigenergy-optimizer/pull/50) normally
merged at 4c3a2116d112f3eda97a950eb4893d32a0d77adf with exactly the tag tree.
Source [PR #49](https://github.com/Belot77/sigenergy-optimizer/pull/49) contains
the reviewed cost-advisory, O19 and O21 corrections.

[Build 40425641785](https://github.com/Belot77/sigenergy-optimizer/actions/runs/40425641785)
succeeded at the exact source. Version/latest OCI index:
sha256:b286d224ee01bb54b5144cb6b3c642374d4e1c557df9c7074501f05179e51cb3.
Both platforms passed all 22 compressed-layer hash/size and uncompressed diff-ID
checks, plus fourteen final target byte/mode checks each. Author and independent
verifier runs each passed 71 synthetic cases; independent image proof review is GO.
Immutable .81 remains unchanged.

Unknown/unpriced import history alone warns; available finite actual import
prices retain their floor. O19 requires current trusted Demand OFF before bounded
fallback import recovery. O21 restores bounded MSC house-serving discharge after
current authority and fresh export-close/MSC proof. Ordinary export-target checks,
independent limits and failed-primary/separate-fallback status remain.

Retained guarded source suite: 1,504 tests / 1,439 subtests passed, zero failures,
206 warnings. Release checks: 55 / 30, zero failures, 202 warnings. No full suite
was repeated for five marker substitutions or this documentation-only receipt.
See [the full publication receipt and installation gates](HAOS82_RELEASE_CANDIDATE.md).

Installation and physical acceptance are unverified. Supplied 27 October startup
identifies .80; auto update was last confirmed off on 26 October. No HA query,
installation or live setting change was performed. Solar allocation and recurring
MSC errors remain unresolved; limits and tariff/policy values remain decision-time
snapshots. Accepted cost risk remains: unpriced energy can export at a loss.

Next: separately approved installation and exact startup identity, then monitor-only,
dry-run and supervised-live acceptance. Evaluate known cost floors versus unknown
warnings, Demand ON/unknown fallback closure, bounded ESS recovery and current
authority. Keep Solar allocation/O18 and recurring MSC diagnosis open; do not
infer physical compliance from setpoints or successful service requests.

## Historical premerge O21 fallback checkpoint - 27 October 2026

A local, unreleased correction restores only bounded MSC house-serving ESS
discharge after a failed battery-export attempt and verified fallback closure.
Current authority and fresh export-close/MSC proof remain mandatory. Ordinary
export-target checks, independent decision limits and normal capability bounds
remain. The original application stays failed even when fallback succeeds.

The guarded full suite passed 1,504 tests / 1,439 subtests, zero failures.
Independent source/test review is GO for the local correction. O21 is locally
verified; publication and physical acceptance remain separate. Capability and
policy values retain decision-time snapshot semantics; no after-await refresh
is added. See CURRENT_STATE.md for exact scope, results and approval boundaries.


This roadmap is ordered by dependency. Later work must not bypass safety, validation, release and live-proof gates except for an explicitly recorded scoped sequencing exception. The scoped `.68` trial and authorized four-tier development below do not waive inverter safety or accept Phase 1.

## Historical cost-policy checkpoint - 2026-10-27

Unknown or unpriced cost alone warns and does not veto otherwise-qualified
automatic battery-backed export. Any finite recorded highest actual import
price remains the cost floor during incomplete coverage, including zero and
negative values. Ledger accounting truth and sticky unknown coverage remain
unchanged; see `CONTROL_CONTRACT.md` and `IMPORT_LEDGER_INTEGRITY.md`. The
integration candidate also carries the narrowly scoped O19 fallback Demand
Window recheck described below. The original O19 worktree at
`C:\Projects\sigenergy_optimizer-fallback-demand` is preserved. Combined offline validation passed 1,499 tests / 1,429 subtests, zero failures; source/test review was GO for local integration and characterization only. The integration-only O21 finding is historical; see the local correction for current status. Results and scope are in `CURRENT_STATE.md`. Before any live acceptance, verify
runtime identity, current coverage and price evidence, control ownership,
settlement, reserves and rollback readiness. The accepted financial risk is that
unpriced energy can be exported at a loss. A safe code rollback requires a
separately reviewed scoped revert; this checkpoint authorizes no install,
release or live action.

## Historical O19 fallback checkpoint - 2026-10-26

The combined integration candidate carries O19 from the preserved
`fix/fallback-demand-revalidation` worktree, based on the same verified main.
The correction revalidates current Demand Window evidence in the final
authority/settlement read before fallback can reopen import. ON or
untrusted/conflicting evidence requests the existing 0.01 kW close with a fresh
authority check. Initial Demand/Standby/Morning Dump restrictions, ordinary
import policy, freshness bounds and other recovery/settlement protections remain.

Historical O21 integration baseline (superseded by the local correction): Three separate scripted cases exercise current Demand ON, unknown, and trusted OFF. In each, the positive BATTERY_EXPORT proposal fails; the post-request EXPORT close is 0.01 kW and exact MSC proof is present. ON and unknown keep import closed; trusted OFF permits the fixture's 13.25 kW import recovery. Independently, normal Automated ESS discharge-capability restoration is rejected because the original GRID-EXPORT target (25 kW in this fixture) does not match current EXPORT 0.01 kW. `result.succeeded` and `fallback_succeeded` are false, with error `normal Automated ESS discharge capability returned failure`; ESS discharge capability remains 0.01 kW. These fixture values are not site configuration or physical-operation evidence. That integration-only baseline contained no source correction. Track as O21 (Medium: incomplete ESS discharge recovery after failed battery export), which blocked release readiness at the integration checkpoint. This issue is not assigned to O5 overnight reserve or O9 obsolete/overlapping policies.

Standalone O19 validation passed 1,477 tests / 1,426 subtests, zero failures;
standalone cost-policy validation passed 1,476 / 1,404. These are separate
historical results, not combined validation. The combined offline run passed; local review was GO for integration/characterization only. O21 was unfixed and blocked release readiness at the historical integration checkpoint; details are in `CURRENT_STATE.md`. This candidate does not fix recurring MSC/application errors or Solar
allocation. No commit, release, installation or live action is included.

## Historical published checkpoint - 2026-10-26 (.81)

Version **2.3.70-haos81** is [published](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.70-haos81)
at 07:24:39 UTC (18:24:39 Sydney). Tag/container source
`247095a4f9905932c3f5716f3d1be6cee7b3c7f8`, tree
`8a49610bcaee9fc41390c96580710136831a3ffe`; metadata PR #47 normally merged
at `f2a2d9a4b77ba6ce8e8ef40d419a6abe56f7d55f` with exactly that tree.
Build 40284898464 and independent image/source proof are GO. Version/latest index:
`sha256:e3f58087681c0c08ab53b0b8263387e8388d0916796aea326fdf9344ba821526`.
All 22 layers/diff IDs and fourteen target files per architecture passed.
Immutable .80 remains unchanged. [Full receipt and limits](HAOS81_RELEASE_CANDIDATE.md).

Retained source checks passed 204 tests / 196 subtests. All 54 release/evidence/
logging tests / 12 subtests passed in 13.86 seconds. No full suite was repeated for
markers or the final six-document receipt. This release adds passive evidence and
retains .80 logging changes; it does not fix allocation or change control rules.

Next: separately approved installation, exact startup identity, then supplied new
trace evidence covering both zero-charge-at-export-limit and normal-charge/no-export
states. Use reported ESS settings, individual HA report times and Solar command
boundaries to narrow command response and relief reset causes. Do not infer
physical settlement from settings/helper success, silently accept meter disagreement,
force export or remove safe charging recovery. Historical rows are not backfilled.

O18 allocation/fill strategy, O5/O9, broader O6, parked O11 and physical/Boost
acceptance retain their existing gates. Preserve ownership audit, architecture,
cleanup, GUI/UX and Climate Manager sequence below. No HA installation, live
experiment or inverter setting change is authorized by publication.

## Historical published checkpoint - 2026-10-26 (.80)

Version **2.3.69-haos80** was published 25 October 2026 at 23:20:09 UTC
(26 October 10:20:09 Sydney): [GitHub Release](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.69-haos80).
Tag/source `acb576747e808e927bdd7d12346c507da9b188b6`, tree
`14103ec71d3b41ad6a85e2d8a149e3db705606bf`; metadata PR #44 normally merged at
`77bde899da35b2f933304192a9c7226d9e5e9ef3`. Build 40243683190 succeeded at the
exact source. Version/latest OCI index is
`sha256:91120b1039eec3915a37c6ff1a1210cf1cf5e79d97e3e1d9de31207206301a5a`.
All 22 layer hashes, sizes and diff IDs were verified for both architectures;
fourteen target files per architecture match the tag. Fingerprint
`sha256:386444cfc2defee474052cc86cb473059d8f1551d67ad49832e4e352fd382cf4`.
Immutable .79 index remains unchanged. See [the .80 publication receipt](HAOS80_RELEASE_CANDIDATE.md)
for proof details and limits.

The UI-handler filter suppresses only recognized successful 2xx `httpx` INFO
requests. Non-2xx, unknown formats, other loggers and warnings/errors retain their
behavior; console logging and global levels are unchanged. The 500-record ring is
in memory, resets on process restart and can evict older errors. The fix does not
explain the 65 failed applications or 59 unsuccessful fallbacks. Retained source
validation passed 122 tests / 10 subtests, with 202 warnings, in 68.94 seconds;
independent logging checks passed 30 cases and all 46 release checks passed in
10.69 seconds. Independent helper/proof reviews were GO, including 68 synthetic
verifier cases. No full-suite repeat was run.

Auto-update was last confirmed off on 26 October before .79 publication; no new
HA query was made. No installed .79/.80 identity, physical acceptance or full
filesystem equivalence is claimed. O18, O5/O9, broader O6 depletion/floor questions,
parked O11 and existing live/Boost acceptance remain open.

## Historical .79 publication checkpoint - 2026-10-26

Version **2.3.68-haos79** is published at [GitHub Releases](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.68-haos79),
25 October 2026 21:08:21 UTC (26 October 08:08:21 Sydney). Tag/source
`ea516ef6cabd9918dbea675694a9de3aa207c8af`, tree
`8e7e6cf6cdcbb6196383352c2a351f055aed5912`; metadata PR #41 normally merged at
`44419af295a47be24d5f06af3ed7cba83b2f27bb`. Actions run `40233491965` succeeded
at the exact tag source. Version/latest OCI index
`sha256:cbaa5f68e4830737abba90666e486b9db848b3a853d1c9138c33a93f3b02bdad`;
both architecture images were checked: all 22 layer hashes, sizes and diff IDs
were verified, and fourteen target files per platform match the tag. Fingerprint `sha256:a5a6945fc54c5a872a97b717d377cb88b57c6c0e7d8a9704174bc33324f2e3f8`.
Immutable .78 index remains unchanged. Full validation, publication proof and
acceptance limits are in [the .79 receipt](HAOS79_RELEASE_CANDIDATE.md).

Retained source validation passed 1,415 tests / 1,380 subtests, zero failures,
206 warnings, in 241.93 seconds; focused checks passed 165 / 184. All 16 release
checks passed in 9.83 seconds. Independent source/proof reviews are GO. Auto-update
was confirmed off by the operator on 26 October. No HA installation or physical
acceptance is claimed. O18, O5/O9, broader O6 depletion/floor questions and parked
O11 remain open. This is a documentation receipt; no source or tests changed.

## Historical 25 October source-validation checkpoint

The operator approved local branch `fix/solar-charge-reentry-stability` in
`C:\Projects\sigenergy_optimizer-solar-reentry`. Separate O2 budget re-entry and
O6 restrictive-charge handoff guards use 30-second advancing PV/load and local
monotonic proof, with 60-second report age/gap bounds. This preserves immediate
closures, raw Morning priority, valid Solar export and existing charge bounds.
Full validation passed 1,415 tests / 1,380 subtests, zero failures, 206 existing
warnings, in 241.93 seconds; focused checks passed 165 / 184. Independent peer
review is GO. The correction is now published in .79; installation and physical
acceptance remain separate. See [the implementation and acceptance plan](SOLAR_REENTRY_STABILITY.md).

Previous published release is **.78 / `2.3.67-haos78`**, published 24 October
at 07:57:03 UTC (18:57:03 Sydney). Tag/container source:
`3ccf99cc69a4586715aadcbdd2f1282aeea77bf0`. Metadata PR #38 normally merged
at `5b84d7f976e9d9db07fbeefd98aa90089a2f40be` with the exact tag tree.
Both architecture images and version/latest OCI index were verified; immutable
.77 remains available. See [the .78 receipt](HAOS78_RELEASE_CANDIDATE.md).

O15 bounded database execution and O17 ingress trust are now published atop
.77's O14/O16/O10 fixes. The merged source passed 1,355 tests / 1,305 subtests,
zero failures, 206 warnings, 232.02 seconds; focused 126 / 8. All 16 release checks
passed in 9.58 seconds. Independent source and metadata review were GO.
No full-suite repeat was run for marker/docs-only release preparation.

Publication is not installation or physical acceptance. The operator reports
mostly .77 followed by a .78 update on the morning of 25 October; exact installed
source is unverified. The latest full supplied startup/source proof remains the
historical .75 excerpt. No agent HA installation, settings change or Boost
enablement was performed.
Unknown import-cost evidence retains its safeguards. Ordinary runtime Logs
availability and historical HDD/MSC causation are not established as fixed.

The supplied 24 October archive contains 152 records from 17:07:41 to 17:22:40
Sydney, with sequence continuity and a maximum ten-second interval. This is partial
fresh-disk evidence, not runtime-version identity, preservation-manifest proof, or
behavior across another restart. One failed application at 17:14:18 is followed by
pending recovery and helper success at 17:14:28; its cause and physical settlement
remain unproven. The old archive/MSC investigation and O11 remain parked. O5
reserve policy is unchanged. Short physical Demand Window import spikes remain
deferred and separate from O7 exact-full PV-only acceptance.

Sections 1–4 retain their dated phase records and historical live-version snapshots.
Preserve the dependency order: complete applicable Phase 1 and Phase 2 live proof,
then complete the ownership/configuration audit (O9), architecture, project cleanup,
full GUI/UX and Climate Manager integration. The integration candidate does not
bypass those gates. The protected .65 source/image remain available, but the actual
restore/reinstall path remains unproven.

## 25 October trace follow-up priority

1. **O6 and O2:** offline sequence characterization is now complete on local
   tests-only branch `test/solar-charge-cycling` in
   `C:\Projects\sigenergy_optimizer-charge-cycling`, based on main `c84a61b`.
   Two new modules reproduce Morning Slow/Solar charge handoffs and Solar/normal
   aggregate-budget crossings through real decision logic. Combined checks pass
   118 tests / 127 subtests; independent cross-review is GO. The subsequent
   correction merged normally through PR #40 and is now published in .79, with
   full validation and independent review GO. Neither
   the tests nor supplied traces establish physical sensor causes, exact installed
   configuration or lost energy. See [the characterization](SOLAR_CHARGE_CYCLING_CHARACTERIZATION.md).
2. **O18:** review fill-strategy robustness against forecast downgrades. The
   25 October battery was 69.6% at its 16:29:52 fill deadline. Normal charging
   already requested 21 kW after 13:09:53; the earlier bypass contribution cannot
   be determined from these samples alone. Zero-charge/minimum-charge behavior is
   an operator-policy tradeoff requiring separate approval.
3. **O5/O9:** retain reserve-policy and diagnostic review for a computed overnight
   floor above 100%; this planning estimate is not an above-100% charging command.

See [the dated evidence and updated register](CURRENT_STATE.md#25-october-trace-evidence-and-follow-up).
The historical intake was documentation-only; the subsequent continuation
approved local characterization tests and matching documentation. The later
explicit approval covers the bounded local correction recorded above, regression
tests, review and docs. Commit, publication and live actions remain separate.
O11 remains parked. Existing acceptance and
sequencing gates, the deferred short physical Demand Window import issue, and
the later O9/architecture/cleanup/GUI/Climate Manager order remain unchanged.

## 1. Phase 1 code validation

Status: **COMPLETE locally** at code-validation HEAD `7649d185b71fe08fab2636801396e2ae7c793a13`.

The final gate collected 735 tests: 733 passed and only the two frozen Phase 2 transition-safety tests failed; compileall and `git diff --check` passed. The final code/test checkpoint corrected a stale safe-fallback protection-test expectation without changing production code.

The earlier validated Phase 1 checkpoint through docs commit `06efdfd0512e2b88f3431d6206b42c0af7b1c5ce` is present on `origin/fix/phase1-audit-remediation`; that checkpoint recorded remote `main` as `de5b5af082533a48ffb6d0d300f636cbcb4463ad`. At that historical checkpoint, live and rollback were `2.3.54-haos65` at `9965e79133f38d5b9943dcf5a9b04ed6fdab1239`. The provider-aware Solar source checkpoint is `aec127d7efd9fe7787c8253b882207b50a44eeed` on `fix/phase1-audit-remediation`, committed but undeployed at that checkpoint. Current validation and the tests/docs follow-up are recorded in `CURRENT_STATE.md`; Phase 1 live acceptance remains pending.

## 2. Phase 1 checkpoint documentation

Status: **COMPLETE and included in the published feature-branch checkpoint through `06efdfd0512e2b88f3431d6206b42c0af7b1c5ce`**.

The checkpoint records the local code-validation result, durable semantics, live `.61` baseline, protected Phase 2 failures, and unresolved meaning of the proposed 15 kW physical-relief configuration. Documentation does not constitute release or live acceptance.

## 3. Phase 1 feature publication, main promotion, release, deployment, and live acceptance

Feature-branch push: **COMPLETE** through `06efdfd0512e2b88f3431d6206b42c0af7b1c5ce` on `origin/fix/phase1-audit-remediation`.

The publication status above is historical. The 8 October checkpoint records `.67` release/startup and scoped Solar live evidence. Last operator-reported live is now `.69 / 2.3.58-haos69`, source `b90fdeafce5e40e206ffd17dce5e1a8c810519e6`; `.65 / 9965e79133f38d5b9943dcf5a9b04ed6fdab1239` remains known-good rollback. This checkpoint makes no new live query; current identity and evidence limits are in `CURRENT_STATE.md`.

Formal Phase 1 acceptance and explicit disposition of retained follow-ups remain **PENDING**. Scoped Solar evidence does not establish completion of the separate Evening Boost transition-stability dependency. Repository validation and service-call success are not live settlement proof.

The 7 October decision resolves Solar's 15 kW value as physical saturation evidence, not hard-cap enforcement. The 8 October record reports site configuration of 15 kW with Morning Slow headroom 0.0; the older 0.5 kW discussion is not authority to change it.

Separate observed follow-up: the 27 September morning trace showed Solar's aggregate energy budget crossing near its threshold with repeated export-ceiling switching. Investigate it independently; the near-full repair and these seven checkpoints do not establish a fix. The operator must decide from focused evidence whether it blocks final Phase 1 acceptance.

Gate retained: Phase 1 release and live acceptance, including disposition of retained follow-ups, were prerequisites to beginning Phase 2. Explicit approval allowed Phase 2 local development ahead of this gate; the later scoped trial decision below permits consideration of a limited .68 trial before full Phase 1 closure, without accepting Phase 1 or waiving inverter safety.

## 4. Phase 2 transition-settlement safety

Status: **scoped Phase 2 live acceptance was reported for `.68`; current operator-reported release is `.69`**. The newer release identity adds no fresh acceptance evidence. The **13-second observation gap remains unproven**; broader/unexercised live acceptance remains outstanding. Development and the limited trial proceeded under the recorded Phase 1 sequencing exception, not Phase 1 completion.

The local implementation enforces the observed close -> later observe closed -> request MSC -> later observe exact MSC -> reopen sequence in `CONTROL_CONTRACT.md`. Entering deliberate battery export must settle its export target before discharge EMS. Service-call success never counts as observation.

Both formerly frozen tests now pass unchanged:

- `test_exact_msc_does_not_reopen_before_export_is_observed_closed`
- `test_return_from_discharge_waits_for_observed_close_before_requesting_msc`

The prior `.68` protection validation and independent production/final test-delta reviews remain historical evidence for the settlement implementation. They do not constitute independent review of the four-tier delta.

The 10 October operator decision deferred Evening Boost reserve-instability and Solar threshold-switching fixes and allowed the limited `.68` trial. Those deferred fixes/acceptance decisions remain open. Scoped acceptance does not establish uninterrupted observation across the retained gap or validate unexercised restart, telemetry-loss or other scenarios.

Any further live work requires separate authorization, effective-setting/authority checks, containment of deferred policy risks, supervision and stop/rollback arrangements. Unknown or failed prerequisites mean NO-GO. Preserve the full observed-settlement contract and all independent restrictive controls.

Gate retained: full Phase 1 disposition and applicable Phase 2 live-proof requirements remain prerequisites to downstream restructuring/integration. The four-tier development authorization below is bounded and does not close those gates.

## 4A. Authorized four-tier battery-export package

Historical code-review status: **corrected checkpoint committed/pushed; independent ChatGPT GitHub code audit GO**, as reported in the post-audit handoff. Historical worktree `C:/Projects/sigenergy_optimizer-four-tier`, branch `feature/four-tier-battery-export`, HEAD `bec1095539b96dbb90b62bd6eb047471e41801f6`. Original candidate `5989b1c588b3c05e35ae1e13c3b333d2a2796f57` received NO-GO; the corrected nine-file commit `Fix independent export arbitration and stabilize settlement characterization` was pushed to `origin/feature/four-tier-battery-export`. Both original blockers are resolved and no new release-blocking defect was identified in the reviewed code. This superseded the code NO-GO only. The original .69 release is now operator-reported live at `b90fdeafce5e40e206ffd17dce5e1a8c810519e6`; physical/live acceptance gaps remain outstanding, and that historical audit does not cover the new hotfix. The bounded development authorization does not waive Phase 1/2 dependencies.

Ordinary Low battery sale remains disabled regardless of persisted floors/legacy opt-ins; compatible Low default is 100%, independent Medium/High/Spike floors are 40/20/10%. Both audit blockers are resolved in the independently reviewed code: rejected High/Spike proposals no longer suppress independently qualified Solar/Evening, and selected independent policies cannot be intercepted by legacy tier/Positive-FiT branches when Medium defers. Qualified High/Spike priority and cost vetoes remain intact. No tier fallback, new ownership semantics or production settlement change is introduced.

Retained reported remediation validation: **945 tests / 1079 subtests passed, zero failures, 206 classified Pydantic deprecation warnings**; compileall with external cache and diff check passed. Nine deterministic timestamp subcases preserve the real strict-after application checks. The original intermittent failure's timestamps remain unavailable. The corrected commit contains nine files. Current documentation scope, retained validation and evidence limits are recorded in `CURRENT_STATE.md`; tests and compileall were not rerun for this docs-only checkpoint.

## 4B. Bounded Demand Window hotfix checkpoint (2026-10-13)

Current worktree `C:/Projects/sigenergy_optimizer-demand-window-hotfix`, branch `fix/demand-window-exact-full-pv-only`. Published hotfix source: `67fae5db2451fbf3e706b10cf4e2dbad07b38bd9`; published documentation and verified clean pre-preparation HEAD: `a562fd269d4dea651afc39b535745a866f656295`. Independent GitHub code audit reported **GO for the bounded hotfix**. Any future release-preparation commit will contain this local metadata/documentation patch and have its own SHA; it is not assigned or claimed here.

Candidate **2.3.59-haos70 is locally prepared only**, with all five established version markers aligned. It is not committed, pushed, tagged, built, released, installed or live-accepted. Production differences from the published hotfix are limited to the FastAPI version and `_RUNTIME_SIGNATURE`; tests, control behavior, contract, Dockerfile and build workflow are unchanged.

The local hotfix removes one unintended Demand Window exclusion from exact-full cheap-FiT MSC PV-only readiness. Qualified ON now retains the configured, capability-bounded MSC surplus ceiling; ON/untrusted continue blocking import, without battery-export ownership or discharge EMS. OFF/untrusted export outcomes, exact-full/trust/ownership/settlement protections and independent policies remain unchanged. The original regression failed before production editing and passed afterward; independent protections passed **466 tests / 611 subtests**; the final full suite ran once and passed **946 tests / 1,079 subtests**, zero failures, **206 warnings**. Compileall with external cache and diff check passed. Missing local Adelaide timezone data/UTC fallback remains a test-environment limitation. These results are retained, not rerun for documentation.

Verified preparation context reports proposed tag `v2.3.59-haos70` absent from remote Git tags and `gh release list` returning no GitHub releases. These are supplied checks, not refreshed here. GHCR image namespace conflict checking remains outstanding; recheck publication identities/conflicts before separately authorized publication. The tag-triggered workflow publishes version, major/minor and `latest` image tags and passes `SOURCE_REF=${{ github.sha }}`; no build or workflow change is performed.

Original `2.3.58-haos69` remains operator-reported live at `b90fdeafce5e40e206ffd17dce5e1a8c810519e6`, not freshly HA-verified; known-good rollback remains `2.3.54-haos65` at `9965e79133f38d5b9943dcf5a9b04ed6fdab1239`.

Release-preparation preflight matched the expected branch and clean pre-preparation HEAD. The patch is limited to five release-version surfaces and five approved documentation files; current validation is recorded in `CURRENT_STATE.md`.

Next gates:

1. Review the exact ten-file local, unstaged release-preparation checkpoint and validation results.
2. Obtain separate approval to stage and create a local metadata/documentation-only commit on `fix/demand-window-exact-full-pv-only`; record its SHA separately from the published hotfix source and pre-preparation HEAD.
3. Complete GHCR namespace/conflict and publication identity checks before separately authorized push, merge, tag, build or release.
4. Retain separate installation and supervised live-acceptance approval, effective-setting/authority checks, .65 rollback readiness and explicit stop/rollback conditions. Commit approval does not authorize publication or live work.

Before any separately authorised live work, verify exact source/build identity, effective HA settings and observed authority, .65 rollback readiness, supervision and monitor-only/controlled live-acceptance arrangements with explicit stopping/rollback conditions. No settings are inferred from defaults or freshly queried here.

Retain Phase 1 incompleteness, unresolved Evening Boost reserve/transition stability, outstanding Solar threshold-switching disposition, scoped Phase 2 acceptance with its unproven 13-second gap, and outstanding four-tier/hotfix physical/live proof. Neither the .69 release report nor passing tests closes these gates.

This bounded correction preserves the established phase ordering, dependencies and scoped sequencing exceptions. It does not authorize architecture, cleanup, GUI, Climate, broader control redesign or live work. The separately approved .70 metadata/documentation preparation remains local and unstaged.

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
