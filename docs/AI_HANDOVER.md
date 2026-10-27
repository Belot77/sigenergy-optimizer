# SigEnergy Optimizer AI Handover

## Preparing 2.3.71-haos82 - 27 October 2026

The operator approved release preparation, publication and the final receipt.
Source PR [#49](https://github.com/Belot77/sigenergy-optimizer/pull/49) normally
merged at ce70f4ca41be0992ab899e56f2ba3d20ef0482f7, preserving reviewed tree
3dbca50c9b014e181db6c1505f1b352523d438f9.

This candidate combines the accepted unknown-cost advisory policy, O19's current
Demand check before fallback import, and O21's bounded MSC house-supply recovery.
Known finite import-price floors, current authority, fresh export-close/MSC proof
and independent decision/capability limits remain. The original application
stays failed even when separate fallback recovery succeeds.

The guarded source suite passed 1,504 tests / 1,439 subtests, zero failures,
206 warnings; independent source/test/docs reviews are GO. Release checks passed
55 tests / 30 subtests, zero failures, 202 warnings, in 23.12 seconds.
Image/source proof is pending. See [the .82 candidate and gates](HAOS82_RELEASE_CANDIDATE.md).
Solar allocation and recurring MSC errors remain unresolved. Values retain
decision-time snapshot semantics; unpriced energy can export at a loss.
HA installation, live settings and physical acceptance remain separate.
The supplied 27 October startup identifies .80, not an installed .81 or .82.

Last consolidated: 2026-10-27

## Historical premerge O21 correction - 27 October 2026

Approved local branch: fix/fallback-house-supply-recovery in
C:\Projects\sigenergy_optimizer-fallback-house-supply, based on verified
origin/main at 623bd5d95f757de1074cabc4ee25570f2ef80cfd.
It retains the cost-advisory and O19 corrections and adds the narrow O21 repair.
Total scope: 26 files (one production file, 16 tests, nine documents).
The integration and both original candidate worktrees remain unchanged.

Ordinary deliberate battery-export dispatch is classified only when
recovery is None. Fallback retains its non-None recovery context: every
permissive recovery write still requires current Automated/Remote authority and
fresh, request-correlated export-closure and exact MSC reports. It no longer
requires the old positive export target to restore MSC house-serving discharge.
The ESS request remains bounded by normal capability and the decision's ESS
limit. Ordinary export-target and Boost qualification checks are unchanged.

The original application stays failed (result.succeeded=False).
fallback_succeeded=True means only that the separate fallback requirements and
service requests succeeded. Missing proof, takeover or a failed write still
leaves fallback incomplete. Demand ON/unknown keeps import closed independently;
trusted OFF may permit bounded recovery. Scripted software dispatch results
are not proof of physical inverter settlement.

Capability, tariff and policy-owner values remain decision-time snapshots.
This correction adds no after-await tariff or hardware-cap refresh.
It does not establish the cause of recurring MSC errors or fix Solar allocation.
Unpriced imported energy may still export at a loss under the accepted cost
policy; available finite recorded import prices retain their floor.

Final guarded full suite: **1,504 tests / 1,439 subtests passed**, zero failures,
206 warnings, 256.19 seconds. Guards recorded 75 in-memory and 1,811
temporary-path StateStore constructions (counts, not memory sizes).
Dotenv loading was disabled. Final focused checks passed 24 tests / 30 subtests,
202 warnings, 10.86 seconds, with 0 in-memory / 44 temporary-path constructions.
The tests-first run reproduced seven failing recovery subcases before the fix.

Independent source and strengthened-test reviews are GO for this local
correction. Production SHA-256:
f58f5501c9356b5defc231698c16563d9502050c05e095867482fed4be85721b.
O21 is locally corrected and verified, not published or physically accepted.
Nothing is staged or committed; no push, release, installation or live action
has occurred. Supplied startup evidence identifies .80 source acb5767; .81 is
the recorded published release, with no supplied .81 installation proof.

Local rollback is to withhold this candidate; any later rollback needs a
separately reviewed scoped revert. Monitor-only and dry-run observations must
precede separately approved supervised live checks of requested limits, report
times, actual flows and recovery. Stop on lost authority, unproven settlement
or renewed unsafe behavior.


## Retained cost policy and historical integration - 27 October 2026

The approved policy is that incomplete history or unpriced import alone warns
but does not veto an otherwise-qualified automatic battery-backed export.
Finite actual import prices available in the existing shared summary remain a
hard floor even while history is incomplete; zero and negative finite floors
are valid, and no weighted-average cost is used. That maximum is only a lower
bound under incomplete coverage, and a cache/query miss or storage failure may
leave no known price available. No last-known-price cache is added. Ledger truth
remains unchanged: coverage and
day-level unknown flags stay unknown/sticky, exact captured payloads and retries
remain intact, and recovery does not invent missing history or prove zero import.
The guard may remain `active` because it also supplies PV-only clamp context;
`blocking` represents an actual known-priced-floor veto. UI wording continues
to expose the existing guard reason as warning/context; no UI setting is added.

The supplied two-day trace reports unknown cost at 06:09 on 26 October with a
Boost veto under the then-current cost policy; midnight recovery occurred on 27
October, followed by a 07:00 pending MSC application that invalidated
permission/history again. This is reported sequence evidence, not physical
export or settlement. Under the integrated policy, unknown-only cost warns and
must not itself veto Boost when independent authority, permission, settlement,
reserve and flow gates pass. A pending application may independently leave
permission unproven; the integrated lifecycle regression addresses this boundary.
The known finite floor remains binding when available, with incomplete-history
prices only a lower bound. Financial risk accepted: unpriced energy may export
at a loss. The policy does not repair recurring MSC/application errors or Solar
allocation. The published .81 contains passive diagnostics only; supplied 27
October startup identifies .80 source `acb576747e808e927bdd7d12346c507da9b188b6`,
not an installed .81. Physical behavior remains unverified.

Historical O21 integration baseline (superseded by the local correction): Three separate scripted cases exercise current Demand ON, unknown, and trusted OFF. In each, the positive BATTERY_EXPORT proposal fails; the post-request EXPORT close is 0.01 kW and exact MSC proof is present. ON and unknown keep import closed; trusted OFF permits the fixture's 13.25 kW import recovery. Independently, normal Automated ESS discharge-capability restoration is rejected because the original GRID-EXPORT target (25 kW in this fixture) does not match current EXPORT 0.01 kW. `result.succeeded` and `fallback_succeeded` are false, with error `normal Automated ESS discharge capability returned failure`; ESS discharge capability remains 0.01 kW. These fixture values are not site configuration or physical-operation evidence. That integration-only baseline contained no source correction. Track as O21 (Medium: incomplete ESS discharge recovery after failed battery export), which blocked release readiness at the integration checkpoint. This issue is not assigned to O5 overnight reserve or O9 obsolete/overlapping policies.

The previously reviewed integration branch was `fix/cost-fallback-integration` in
`C:\Projects\sigenergy_optimizer-cost-fallback`, based on verified remote main
`623bd5d95f757de1074cabc4ee25570f2ef80cfd`. Its union scope is 25 files: one
production file (`app/optimizer.py`), 15 tests and nine documents. The original
cost candidate `C:\Projects\sigenergy_optimizer-cost-advisory` and O19 candidate
`C:\Projects\sigenergy_optimizer-fallback-demand` remain preserved. The
integration combines their reviewed changes without additional control logic.
Standalone cost validation passed 1,476 tests / 1,404 subtests, zero failures,
206 warnings, 241.61 seconds; strict guards recorded 72 in-memory and 1,762
temporary-path StateStore constructions, with dotenv disabled. Standalone O19
validation passed 1,477 tests / 1,426 subtests, zero failures, 206 warnings,
244.15 seconds; its per-run guards recorded 74 in-memory and 1,775 temporary-path
constructions. These are separate historical runs. The combined offline suite passed 1,499 tests / 1,429 subtests, zero failures, 206 warnings, in 244.32 seconds; strict guards recorded 75 in-memory and 1,799 temporary-path StateStore constructions, with dotenv disabled. Final focused three-module validation passed 23 tests / 20 subtests, 202 warnings, in 4.87 seconds; guards recorded 4 and 32 constructions. Independent source/test review is GO for this local integration and characterization only. O21 was unfixed at that historical integration checkpoint; see the local correction for current status. No file is staged or committed; no push, release,
installation or live action is included. Preserve the existing 120-second Boost
qualification minimum; a standalone fixture admitted at 121 seconds after both
minimums were met. No timing rule is weakened. Scripted HA tests are not physical
acceptance. Full live/physical verification remains open.

Read `C:\Projects\AGENTS.md`, worktree `AGENTS.md`, this handover, `CURRENT_STATE.md` and relevant `CONTROL_CONTRACT.md` sections. Inspect only minimum relevant files. Git records repository identity; HA and operator evidence establish live state.

## Historical .81 publication and verification - 26 October 2026

**2.3.70-haos81 is published.** [GitHub release](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.70-haos81)
published 26 October at 18:24:39 Sydney (07:24:39 UTC). Tag/container source
`247095a4f9905932c3f5716f3d1be6cee7b3c7f8`, approved/tag tree
`8a49610bcaee9fc41390c96580710136831a3ffe`. Metadata
[PR #47](https://github.com/Belot77/sigenergy-optimizer/pull/47) normally merged at
`f2a2d9a4b77ba6ce8e8ef40d419a6abe56f7d55f`, 18:24:19 Sydney, with exactly that tree.
Source [PR #46](https://github.com/Belot77/sigenergy-optimizer/pull/46) remains the
reviewed passive implementation; all original unfinished work is preserved.

[Build 40284898464](https://github.com/Belot77/sigenergy-optimizer/actions/runs/40284898464)
succeeded at the exact source. Version/latest OCI index:
`sha256:e3f58087681c0c08ab53b0b8263387e8388d0916796aea326fdf9344ba821526`.
Both architectures passed all 22 compressed-layer hashes/sizes and uncompressed
diff IDs; fourteen final target files per platform match the tag. Independent
helper and final proof review are GO; 68 offline verifier cases independently
passed. The reviewer separately checked manifests/configs and Git target hashes,
without redownloading every layer. Immutable .80 is unchanged.
[Full publication receipt and verification limits](HAOS81_RELEASE_CANDIDATE.md).

Retained source validation passed 204 tests / 196 subtests, zero failures,
202 existing warnings, in 42.15 seconds; focused evidence/outcome checks passed
19 / 22. All 54 release/source-pinning/evidence/logging tests / 12 subtests passed,
zero failures, 202 warnings, in 13.86 seconds. No full suite was repeated for
metadata or this six-document receipt.

This release adds passive evidence and retains the .80 UI log filter.
It does not change allocation, targets, tolerances, authority, settlement or safe
fallback. HA report times and setting/helper acknowledgments are not physical
settlement proof. O18, O5/O9, broader O6, parked O11 and physical/Boost acceptance
remain open. The supplied 27 October startup identifies .80 source
`acb576747e808e927bdd7d12346c507da9b188b6`; exact installed .81 identity is
unverified. Auto update was last operator-confirmed off on 26 October;
no direct HA query, installation or live settings change was performed.

## Historical local Solar evidence validation - before PR #46 merge

The operator approved `fix/solar-allocation-evidence`, isolated in
`C:\Projects\sigenergy_optimizer-solar-evidence` from freshly fetched main
`45afeb660f01cca3854d9599b6935d2bab69d026`. The six approved characterization
files below were copied byte-for-byte; their original worktree remains untouched.
Production scope is passive readback provenance and additive trace evidence in
`app/models.py` and `app/optimizer.py`, with focused tests and matching docs.
Commit, push, publication, installation and live changes are not included.

The trace now separates pre-application reported ESS charge limit from requested
charging and measured battery power. It retains five flow report timestamps,
signed balance and before-evaluation/recording-time Solar feedback boundaries.
These are HA reports/helper boundaries, not physical sampling or settlement
proof. Existing trace/application keys retain their meanings; no UI redesign,
additional HA I/O, archive migration or historical backfill is added.

The -74 W aggregate/+2 W direct reading does not justify a meter-error tolerance.
All control gates, negative-balance rejection, normal recovery, Manual/Force and
the O18 policy remain unchanged. This is evidence collection, not an allocation
correction. Final validation and its limits are recorded below.
See the [field semantics and limits](CONTROL_CONTRACT.md#passive-charge-allocation-evidence).

Final applicable checks passed **204 tests / 196 subtests**, zero failures,
202 existing warnings, in 42.15 seconds; focused evidence/outcome checks passed
19 / 22 in 1.23 seconds. The eight new evidence tests include temporary-archive
round-trip, missing versus zero readback, malformed values and diagnostic-failure
isolation. The initial tests-first run failed two expected missing-field cases.
No full suite was needed. Mechanical AST comparison confirms baseline control
source after removing only the approved passive additions; independent production
review is GO. ESS report provenance uses existing bulk metadata and may appear
stale; no supplementary read or physical acceptance is claimed.

## Current Solar charge/export allocation investigation - 26 October 2026

Operator-approved tests-first branch `test/solar-export-charge-allocation` is in
`C:\Projects\sigenergy_optimizer-solar-allocation`, based on freshly fetched
main `45afeb660f01cca3854d9599b6935d2bab69d026`. Only tests and investigation
documentation change; no production correction, commit, push, release or live
action is included. The operator reports installed .79; exact runtime identity
and physical acceptance remain unverified. .80 changes logging, not Solar control.

The supplied 26 October trace confirms frequent zero charging requests near the
15 kW physical export limit and occasional relief. A later screenshot shows the
opposite: approximately 18.87 kW charging and zero export. Strict aggregate-flow
rejection resets relief; pending Morning handoff leaves normal 21 kW charging
permission. Mandatory fallback/authority recovery can also restore normal
charging. The screenshot's exact trigger and actual ESS readback are unavailable.
Failed applications may retain old cached Solar status; do not infer settlement
from that label or a successful helper result.

Four new offline characterizations cover feedback reset/reacquisition, held-report
handoff and real fallback with fake HA. Combined focused validation passed
105 tests / 136 subtests, zero failures, 202 existing warnings, in 29.71 seconds;
independent test-source review is GO. No full suite was repeated. Keep O18 and physical acceptance open;
do not weaken safety, add a tolerance or change charging policy on this evidence.
See [evidence, tests, limits and next scope](SOLAR_EXPORT_CHARGE_ALLOCATION_CHARACTERIZATION.md).

## Historical .80 publication and verification - superseded by .81 - 26 October 2026

**2.3.69-haos80 is published.** [GitHub release](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.69-haos80)
published at 10:20:09 Sydney (25 October 23:20:09 UTC). Exact tag/container source
is `acb576747e808e927bdd7d12346c507da9b188b6`, approved/tag tree
`14103ec71d3b41ad6a85e2d8a149e3db705606bf`. Metadata
[PR #44](https://github.com/Belot77/sigenergy-optimizer/pull/44) normally merged at
`77bde899da35b2f933304192a9c7226d9e5e9ef3` at 10:19:24 Sydney with exactly the
tag tree. Source PR #43, its branch and all unfinished workspaces remain preserved.

[Build 40243683190](https://github.com/Belot77/sigenergy-optimizer/actions/runs/40243683190)
succeeded at the exact source. Version and `latest` index:
`sha256:91120b1039eec3915a37c6ff1a1210cf1cf5e79d97e3e1d9de31207206301a5a`.
All 22 compressed-layer hashes/sizes and uncompressed diff IDs passed; fourteen
target files per amd64/arm64 platform match exact tag bytes. Shared fingerprint:
`sha256:386444cfc2defee474052cc86cb473059d8f1551d67ad49832e4e352fd382cf4`.
Independent helper/proof review is GO; 68 synthetic verifier cases independently
passed. Immutable .79 remains unchanged. Full identities, scope and verification
limits are in [the publication receipt](HAOS80_RELEASE_CANDIDATE.md).

Retained logging-source validation passed 122 tests / 10 subtests, zero failures,
202 existing warnings, 68.94 seconds. The independent logging module passed 30
cases; all 46 release/source-pinning/logging checks passed in 10.69 seconds.
No full suite was repeated for this narrow fix or release markers/receipt docs.
The filter improves UI diagnostic retention only: console logs, the 500-record
process-memory bound, controls, retries and settlement are unchanged. It does not
recover lost records or explain the 65 application / 59 unsuccessful fallback
outcomes in supplied evidence. O18, O5/O9, broader O6, parked O11 and physical/Boost
acceptance remain open.

Auto update was last confirmed off by the operator on 26 October before .79
publication; no later change was reported and no direct HA query is claimed.
No HA installation/live changes or exact installed .80 identity is established.
Expected startup is `Runtime signature=2.3.69-haos80` and
`Container source commit=acb576747e808e927bdd7d12346c507da9b188b6`.
The receipt workspace `C:\Projects\sigenergy_optimizer-receipt-haos80`, branch
`docs/haos80-publication-proof`, starts at metadata merge `77bde899...` and changes
six documents only. Following local-preparation/publication sections record their
dated checkpoints; this .80 summary supersedes their current-version statements.

## Historical local .80 release preparation - 26 October 2026

[PR #43](https://github.com/Belot77/sigenergy-optimizer/pull/43) normally merged
reviewed head `512601da8083f88a260e343dd980c2c14183c814` into main at
`bcd9fe51f7303467ed8e463805c30284110e6a95` at 10:00:11 Sydney
(25 October 23:00:11 UTC), retaining exact reviewed tree
`70805bd6f1f49eb47654b7c686c6a8d904371d13`. Source branch and all unfinished
workspaces are preserved. The prior local correction checkpoint below is historical.

The operator continued to local `2.3.69-haos80` preparation on branch
`release/2.3.69-haos80` in `C:\Projects\sigenergy_optimizer-release-haos80`,
based on that freshly verified main. Scope is five single-marker substitutions
and six documents. No new logging/control/test/configuration-value/workflow change
is bundled. Commit, tag/image/publication and HA installation remain separate.
The future tag/container source will be a separately approved metadata commit,
not the source merge above; it is not yet assigned.

Retained logging-source validation passed 122 tests / 10 subtests, zero failures,
202 existing warnings, 68.94 seconds; independent focused checks passed 30 cases.
Independent source/test/documentation review is GO. The previous .79 full suite
is historical and is not claimed as a full run of this new logging candidate.
All 46 release/source-pinning/logging checks passed in 10.69 seconds, with 202
existing warnings and zero failures. Exact five-marker/six-document scope is
verified; independent metadata/documentation review is GO. See [the .80 candidate](HAOS80_RELEASE_CANDIDATE.md).

Latest published remains .79 at `ea516ef6cabd9918dbea675694a9de3aa207c8af`.
The logging fix only filters recognized successful 2xx HTTP INFO from the UI ring;
console logs, its 500-record/process-lifetime limit and control behavior remain
unchanged. It cannot recover lost history or explain recorded actuator failures.
O18, O5/O9, broader O6 depletion/floor questions, parked O11 and existing live/Boost
acceptance remain open. No installed .79/.80 identity or physical acceptance is claimed.

## Historical local UI log-retention correction - pre-commit checkpoint, 26 October 2026

The operator approved local branch `fix/diagnostic-log-retention`, in
`C:\Projects\sigenergy_optimizer-log-retention`, from freshly fetched main
`0a1955874e8599ac273b8c8c06b5e8cde5595600`. No commit, push, release, installation
or live action is authorized by this local-fix approval. Original unfinished
workspaces remain preserved.

The supplied 500-entry log contains only successful HTTP INFO requests and spans
84 seconds. A UI-handler-only filter now suppresses recognized 2xx `httpx` INFO
request messages. Non-2xx responses, unknown formats, other loggers and all
warnings/errors retain their existing behavior. Filtering fails open on unknown
formats/errors and does not mutate shared records. Console logging and global
logger levels are unchanged. The newest-first ring still holds at most 500 retained
records and is cleared on process restart; later retained records can still evict
older errors. No persistent storage or history recovery is added.

Production scope is only the log-capture block in `app/routers/api.py`, with
focused regression coverage in `tests/test_ui_log_retention.py` and matching
README/changelog/current-state notes. Controls, service-call frequency, MSC
settlement, application outcome metadata, accounting, release markers and settings
are unchanged. This does not resolve the trace's 65 failed application outcomes
or 59 unsuccessful fallbacks, whose underlying causes remain unproven.

Before the change, the initial regression run reproduced the issue with
16 failures / 10 passes. Independent focused verification of the refined module
passed all 30 cases. Combined logging, HA-client, ingress, application-outcome and
fallback checks passed 122 tests / 10 subtests, zero failures, 202 existing warnings,
in 68.94 seconds. Independent code/test review is GO. No full-suite or physical
acceptance is claimed. To roll back this local candidate,
withhold the uncommitted branch; any later committed reversal must remain scoped
to the diagnostic filter and preserve unrelated work.

## Historical .79 publication and verification - superseded by .80 - 26 October 2026

**2.3.68-haos79 is published.** [GitHub release](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.68-haos79)
was published at 08:08:21 Sydney (25 October 21:08:21 UTC). Tag/container source
is `ea516ef6cabd9918dbea675694a9de3aa207c8af`, tree
`8e7e6cf6cdcbb6196383352c2a351f055aed5912`. Metadata
[PR #41](https://github.com/Belot77/sigenergy-optimizer/pull/41) normally merged
at `44419af295a47be24d5f06af3ed7cba83b2f27bb` at 08:07:43 Sydney, with exactly
the tag tree. Source PR #40 and all original worktrees remain preserved.

[Tag build 40233491965](https://github.com/Belot77/sigenergy-optimizer/actions/runs/40233491965)
succeeded at that exact source. Version and `latest` index are
`sha256:cbaa5f68e4830737abba90666e486b9db848b3a853d1c9138c33a93f3b02bdad`.
Both amd64/arm64 images passed all 22 compressed-layer and uncompressed diff-ID
checks, with fourteen exact target files each, including `solar_reentry.py`.
Their shared file fingerprint is
`sha256:a5a6945fc54c5a872a97b717d377cb88b57c6c0e7d8a9704174bc33324f2e3f8`.
Independent helper/proof review is GO; 68 synthetic verifier cases passed.
This is source/image evidence, not runtime or physical acceptance. Full identities,
verification limits and rollback are in [the publication receipt](HAOS79_RELEASE_CANDIDATE.md).

Retained control validation: 1,415 tests / 1,380 subtests passed, zero failures,
206 existing warnings, 241.93 seconds; focused 165 / 184. All 16 release checks
passed in 9.83 seconds. The final receipt changes documentation only. O2 budget
reacquisition and the narrow O6 relieved-Morning restrictive-charge handoff ship
in .79; O18 fill strategy, O5/O9 review, broader O6 depletion/floor questions,
parked O11 and existing physical/Boost acceptance remain open.

The operator confirmed Auto update off on 26 October. No HA installation,
live settings change or installed .79 identity is claimed. Expected startup is
`Runtime signature=2.3.68-haos79` and
`Container source commit=ea516ef6cabd9918dbea675694a9de3aa207c8af`.
The receipt workspace is `C:\Projects\sigenergy_optimizer-receipt-haos79`, branch
`docs/haos79-publication-proof`, based on metadata merge `44419af...`.
The following dated local-preparation checkpoints are historical, superseded by
this publication; their narrower approval statements describe those earlier steps.

## Historical 26 October local .79 release preparation

[PR #40](https://github.com/Belot77/sigenergy-optimizer/pull/40) normally merged
reviewed head `ad0e89fdc72d9bb6d52b03aada0456e629bd2963` into main at
`fbe3bfcc14312952748f1991eec7836977adfcb5` on 26 October at 07:31:05 Sydney
(25 October 20:31:05 UTC). The merge tree is the reviewed/tested
`6a70c7c55321372969d87e522e57e27a2271b0ce`. Source branch and original workspaces
remain preserved. No public PR comments/reviews/checks blocked that source merge.

The operator then continued the proposed local `2.3.68-haos79` preparation on
branch `release/2.3.68-haos79` in `C:\Projects\sigenergy_optimizer-release-haos79`,
based on that freshly verified main. Five version markers and seven documents
are the complete release-preparation scope. No new control/test/workflow change,
commit, push, tag, image, GitHub release or HA action is included here. The future
tag/container source will be a separately approved metadata commit; it is not
the source merge SHA above and is not yet assigned.

Published .78 remains `2.3.67-haos78`, source
`3ccf99cc69a4586715aadcbdd2f1282aeea77bf0`. Proposed .79 tag, GitHub release,
release PR and GHCR version tag are absent at preflight; .78's immutable version
index remains `sha256:35292feb279a4b33e4c86f5482d690a9704c91d7178038b115c3bc434ead991a`.
Retained source validation is 1,415 tests / 1,380 subtests, zero failures,
206 warnings, 241.93 seconds; focused 165 / 184. Independent source/helper/test
review is GO. All 16 release/version/source-pinning checks passed in 9.83 seconds;
normalized comparison confirms exactly five marker substitutions and seven docs.
Independent release metadata/documentation review is GO. These are recorded in
[the .79 candidate](HAOS79_RELEASE_CANDIDATE.md), with publication and live gates.
O18 strategy, O5/O9 review, broader O6 depletion, parked O11 and physical
acceptance remain open. No assumption of exact installed .78 identity is made.

## Historical 25 October approved local O2/O6 correction

Workspace `C:\Projects\sigenergy_optimizer-solar-reentry`, branch
`fix/solar-charge-reentry-stability`, starts from freshly fetched `origin/main`
`c84a61b6a6ca1fb6d5f23c421f1f11ebf4a1ce49`. The operator explicitly approved
the 30-second dual-source/monotonic qualification with 60-second age/gap bounds,
local correction, regression tests, safety review and matching documentation.
Commit, push, release and live actions are not authorized by this approval.

O2 withholds Solar reacquisition after its strict aggregate-budget failure;
initial activation and immediate failure closures remain unchanged. O6 delays
only Solar's restrictive charge reacquisition after a completed relieved Morning
owner restored the normal safe bound. Raw Morning priority and valid Solar export
stay intact. The two obligations and qualification generations are independent.
No available-energy trust prerequisite, new setting, minimum-charge rule or
release-version change is added. O18 and broader O6 depletion/floor questions
remain open. See [implementation, validation and acceptance](SOLAR_REENTRY_STABILITY.md).

Final offline suite: **1,415 tests / 1,380 subtests passed**, zero failures,
206 existing warnings, 241.93 seconds. Focused combined checks: **165 / 184**,
202 warnings, 14.97 seconds. Independent production/helper/test peer reviews
are **GO** after correcting unsafe-flow proof accrual and expiry after final
helper awaits. Documentation review's stale status wording is reconciled.
Syntax, whitespace, exact 15-file scope and original-file SHA-256 checks pass.
No HA access or physical acceptance is claimed. This records pre-commit
validation; Git supplies the identity of any separately approved commit.
On 26 October, commit preparation confirmed unchanged main and the tested
source/test fingerprint, then removed one extra EOF blank line exposed by the
staged check in the new Morning test. Its Python AST is unchanged; no logic
changed and no test repeat was needed. The exact 15-file patch is staged only
for review. Local commit requires separate approval; push/publication/live
actions remain outside the current authorization.

The characterization workspace and its six uncommitted files remain preserved;
they were copied into this isolated correction workspace. The earlier backlog
workspace is also preserved. The following checkpoints are historical evidence.

## Historical 25 October offline charge-switching characterization

The operator approved the proposed tests-only branch by asking to continue.
Workspace `C:\Projects\sigenergy_optimizer-charge-cycling`, branch
`test/solar-charge-cycling`, starts from freshly fetched `origin/main`
`c84a61b6a6ca1fb6d5f23c421f1f11ebf4a1ce49`. The three uncommitted backlog
documents below were copied into this isolated checkout; their originals in
`sigenergy_optimizer-release-haos78` remain unchanged.

Two new modules reproduce **O2** Solar/normal and **O6** Morning Slow/Solar
charge-owner switching using real decision, provider, eligibility and charge
calculations. Six-second sequences alternate restrictive Solar requests with
normal 21 kW permission. Explicit synthetic forecast/configuration assumptions
prevent an exact-replay or installed-configuration claim. Controls retain
immediate failed-gate release, steady-owner cases and the existing permitted
zero-charge calculation. No production behavior was changed or accepted as fixed.

Combined focused validation passed **118 tests / 127 subtests**, zero failures,
202 existing warnings, in 3.82 seconds. Each new module received independent
read-only cross-review: **GO**, no concrete blocker. No full suite was needed for
this tests/documentation-only change. Tests do not dispatch controls, access HA,
prove physical settlement or explain the sensor fluctuations.

See [the characterization and next scope](SOLAR_CHARGE_CYCLING_CHARACTERIZATION.md).
Next is a separately approved stabilization design/fix, retaining immediate hard
closures and independent policy priorities. O18 fill-strategy/minimum-charge
policy remains open; its single aggregate downgrade control is not a full
strategy simulation. No commit, push, release or live action is included here.

## Historical 25 October backlog intake from supplied traces

The operator requested adding the discussed findings to the list. The documentation
branch is `docs/trace-findings-20261025` in
`C:\Projects\sigenergy_optimizer-release-haos78`, based on main
`c84a61b6a6ca1fb6d5f23c421f1f11ebf4a1ce49`. Only CURRENT_STATE.md,
AI_HANDOVER.md and ROADMAP.md are changed; no commit or push is included.

Expanded **O2** for confirmed Solar/normal aggregate-budget cycling and **O6**
for confirmed Morning Slow/Solar charge-owner switching. Added **O18** as a
fill-strategy investigation/operator-policy review: the battery misses its
16:29:52 fill objective at 69.6% despite normal 21 kW charge permission after
13:09:53, and a large forecast downgrade occurs at 14:08:27. Earlier bypass
contribution remains unproven; zero charge is permitted by existing policy.

Linked the computed 113% overnight floor to **O5/O9** planning/diagnostic review.
It is not a command to charge beyond 100%. O11 remains parked despite six
additional afternoon helper failures/recoveries. No new tests, control changes,
policy decisions, releases or live actions are authorized by this intake.

The operator reports .78 installed on the morning of 25 October after mostly .77.
The traces contain two recorder sessions but no runtime/source version; do not
convert that report into verified installed identity or close physical acceptance.
See [the evidence and register](CURRENT_STATE.md#25-october-trace-evidence-and-follow-up)
and [the queued order](ROADMAP.md#25-october-trace-follow-up-priority).
Raw traces remain outside the repository. Next proposed engineering is tests-first
characterization of both switching boundaries and forecast-revision behavior,
followed by separately scoped implementation/policy approval.

## Historical .78 publication and verification - superseded by .79 - 24 October 2026

Published **2.3.67-haos78** on 24 October at 07:57:03 UTC (18:57:03 Sydney):
[GitHub Release](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.67-haos78).
Tag/container source `3ccf99cc69a4586715aadcbdd2f1282aeea77bf0`;
tree `2542e3600ef3280f1dd166953804f708f8b1137d`.
[Metadata PR #38](https://github.com/Belot77/sigenergy-optimizer/pull/38) normally
merged at `5b84d7f976e9d9db07fbeefd98aa90089a2f40be` with exactly the tag tree.
It packages O15/O17 source PR #37, merged at `e12da76d9c11e6d92286ecaf9c98a7c3497e0872`.

[Actions run 40075754355](https://github.com/Belot77/sigenergy-optimizer/actions/runs/40075754355)
succeeded for the exact tag. Version/latest OCI index:
`sha256:35292feb279a4b33e4c86f5482d690a9704c91d7178038b115c3bc434ead991a`.
Both amd64/arm64 labels, all 22 compressed layers and uncompressed diff IDs,
the source pin and twelve application/launcher files match exact tag bytes.
The thirteen-file fingerprint (sorted absolute image path + NUL + bytes + NUL) is
`sha256:b84b39d53f7a6e9581d49d4a77d3b2a9643b1bf704f1edb825ef1e734a5fc9a1`.
The immutable .77 version index remains
`sha256:0a743b4f32c0df7cd87d387f8870435d71ee5330f11c77999305cd665dd9e883`.
Corrected complete image proof passed; independent helper review was GO.

Retained merged-source suite: **1,355 tests / 1,305 subtests passed**, zero failures,
206 warnings, 232.02 seconds; focused 126 / 8. All 16 release/source-pinning
checks passed in 9.58 seconds. Independent source and metadata review were GO.
No full-suite repeat was run for marker/docs-only preparation.

O15 isolates production SQLite work while retaining bounded admission, immutable
accounting retries and unknown-cost protections. O17 binds the ingress exemption
to the actual Supervisor peer plus `X-Ingress-Path`, with proxy rewriting
disabled. Existing HA login, API-key/read/status policy, MSC settlement, limits
and Manual/Force boundaries remain intact. Accepted writes may finish after
timeout; worker threads cannot interrupt wedged OS I/O. Custom proxies use the
existing key path. No ordinary runtime Logs repair or HDD/MSC cause is established.

Publication and receipt documentation are authorized; installation and live
settings changes remain separate operator actions. The operator reports mostly
.77 followed by a .78 update on the morning of 25 October. Exact installed source
remains unverified; the latest full supplied startup/source proof is the historical
.75 excerpt. New trace evidence and its acceptance limits are recorded above.
O5 policy, O11 parked follow-up and applicable live/Boost acceptance gates remain
open. Original unfinished worktrees and protected data remain preserved.
See [the complete .78 receipt and acceptance notes](HAOS78_RELEASE_CANDIDATE.md).

## Historical .78 preparation checkpoint - superseded by publication

[PR #37](https://github.com/Belot77/sigenergy-optimizer/pull/37) normally merged
reviewed head `6deb930da9cfc8e03724405a1bb42f95937f3f25` into main at
`e12da76d9c11e6d92286ecaf9c98a7c3497e0872` on 24 October at 07:40:46 UTC
(18:40:46 Sydney). Both source trees are
`5a63925bc07dc6ccf93a3b9d5f4f5b2e57d0b2b7`, exactly the tested combined tree.

The isolated workspace `C:\Projects\sigenergy_optimizer-release-haos78`,
branch `release/2.3.67-haos78`, starts from that merge. The local
`2.3.67-haos78` candidate changes only the five established version markers
and release/status documentation. No new control, storage, authentication or
trace logic is introduced during release preparation. All 16 release-marker/source-pinning
checks passed in 9.58 seconds. Normalized comparison confirms exactly five single-marker
substitutions and seven targeted documents, with no other source/test/workflow drift.
Independent release-metadata review is **GO**, with no High/Medium blocker;
the reviewer did not rerun tests or access HA.

Retained source validation: **1,355 tests / 1,305 subtests passed**, zero failures,
206 existing warnings, 232.02 seconds; focused checks passed 126 / 8
(202 warnings, 13.54 seconds). Independent combined source/test/documentation
review was GO with no High/Medium blocker. These are the existing merged-source
results, not a new full-suite run or physical acceptance.

The source merge was separately approved and completed. Local release preparation
is now authorized; commit, push, tag, image publication, metadata merge and GitHub
Release remain pending separate publication approval. Published .77 remains
current. No installation, live HA access, settings change or Boost enablement is
part of this preparation. Original unfinished worktrees remain preserved.

O15 keeps slow/failed/unconfirmed accounting evidence unknown, with bounded worker
admission and immutable retries. Accepted mutations may finish after timeout;
threads cannot interrupt wedged OS I/O. O17 trusts the actual Supervisor peer
`172.30.32.2` plus `X-Ingress-Path` with proxy rewriting disabled.
Normal HA login and existing key/read/status policies retain their boundaries;
custom proxies use the existing API-key route. Ordinary runtime Logs availability
and HDD/MSC causation are not established as fixed by these changes.

The operator reported .76 installed after replacement-SSD restoration on 24 October;
last full supplied startup/source proof remains .75. The fresh trace sample is
partial persistence evidence without runtime identity or another-restart proof.
O5 policy, O11 parked follow-up and applicable physical acceptance gates remain open.
See [the .78 candidate, publication order and acceptance plan](HAOS78_RELEASE_CANDIDATE.md).

## Historical O15/O17 pre-commit verification checkpoint - 24 October 2026

Workspace `C:\Projects\sigenergy_optimizer-storage-ingress`, branch
`fix/storage-ingress-integration`, based on `df5c64c04dac67885270bfa15be89db6a6dc2d0d`.
The complete on-disk combined suite passed **1,355 tests / 1,305 subtests**, zero
failures, 206 existing warnings, in 232.02 seconds. Five focused modules passed
126 tests / 8 subtests (202 warnings, 13.54 seconds). Independent combined source/test/documentation review is **GO**, with no
High/Medium blocker. The reviewer inspected source and assertions without rerunning tests
or accessing HA.

This is the recorded pre-commit verification checkpoint. The user approved one
combined commit, branch push and draft PR after final independent GO. Git and the
draft PR establish the resulting source identity. This scope does not authorize
merge, release, installation or live settings changes. No physical acceptance is
claimed. The source and tests are the reviewed components combined without new
control logic; only the ingress predicate/import overlap in the API file.

Preserved standalone evidence: O15 passed 1,307 tests / 1,305 subtests and focused
221 / 191; O17 passed 295 / 89 broader and 70 / 6 focused. Each component had its
own independent source/test/documentation GO. The earlier 102 / 6 in-memory
cross-candidate check remains limited compatibility evidence; the new 1,355 /
1,305 result above is the full on-disk integration run. Both original worktrees
remain unchanged. See [O15](STORAGE_EXECUTION_ISOLATION.md) and
[O17](INGRESS_TRUST_BOUNDARY.md) for reproduction, design and limitations.

Slow or unconfirmed storage retains unknown-cost protections and mutable ledger
state remains on the event loop. Accepted writes can complete after timeout;
threads cannot kill wedged OS I/O. O17 binds trust to the actual Supervisor peer
plus `X-Ingress-Path`, with proxy rewriting disabled in supported launchers.
Normal HA login, optional public read/status policies and control safeguards
retain their boundaries. Custom proxies use the existing API-key route; actual
installed exposure/flags and physical behavior remain unverified.

Published .77 remains the current release. The supplied 24 October archive shows
partial fresh persistent records, not installed source, preservation-manifest
proof or behavior across another restart. Existing acceptance and O5 policy
gates remain open; historical HDD/trace/MSC causation is unproven.

## Historical .77 publication and verification - superseded by .78

Published **2.3.66-haos77** on 24 October 2026 at 01:54:00 UTC (12:54:00 Sydney): [GitHub Release](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.66-haos77). Tag/source `7aa712f72ca2c0467e6740e3cb0f2191ba8d077e`, tree `33d9b94399f87d27baf787a59403861988182ce9`. Source PR #34 merged at `b4377de9f38d1c305c23a0b1dca9cb509afc1a9f`; metadata PR #35 merged at `81c2752c4e031bb9786ec0d00f1dca4e22c59de9` with exactly the tagged tree.

Version and `latest` OCI index: `sha256:0a743b4f32c0df7cd87d387f8870435d71ee5330f11c77999305cd665dd9e883`. Both amd64 and arm64 images, version/revision labels, all 22 compressed layer digests and uncompressed diff IDs, `/app/.source_commit` and eight application files match the exact tag. Nine-file verification fingerprint (source pin plus eight files, sorted relative path + NUL + bytes + NUL): `sha256:19c830fb53506bca02a342882b6da90f5d14e9097f519c0a815dfc9892427774`. The immutable .76 version index remains `sha256:b7df9f21fce7ef14e7b4f602235486e17b35b710907656dd0b43e796889a6e9a`.

Combined offline validation: **1,275 tests / 1,305 subtests passed**, zero failures, 206 existing warnings, 226.40 seconds. All 16 release/source-pinning checks passed in 9.35 seconds. Independent source and release review was GO with no High/Medium blocker; reviewers did not execute tests or access HA. Development-host dual-HTTPS corroboration smoke passed. These results establish publication and source identity, not installation or physical acceptance.

This release includes O14 configuration-activation transactions, O16 immutable import-cost accounting with direct-control/identity-boundary invalidation, and O10 trace clock recovery. Trace recovery corroborates UTC through two fixed HTTPS origins, durably preserves historical record bytes before active retention resumes, and retains gap evidence. It can take a normal 15-minute persistence interval after successful checks. Missing decisions cannot be reconstructed. Unknown accounting can pause applicable automatic battery sales until a newly covered day; independently qualified PV-only and Manual/Force semantics remain separate.

The operator reported .76 installed after HAOS 18.3 restoration onto a replacement SSD on 24 October. Last full supplied startup/source proof remains .75; .77 installation is left to the operator. No live HA, inverter, battery, export settings or Boost enablement changed during this release. O15 storage execution and O17 ingress trust are outside .77; their combined local candidate is described above and remains unpublished. O5 policy, O11 parked follow-up and applicable physical acceptance gates remain open. Original O14/O16 worktrees and the frozen trace candidate remain preserved.

See [the complete .77 receipt and operator notes](HAOS77_RELEASE_CANDIDATE.md).

## Historical .76 publication verification - superseded by .77

`.76` / `2.3.65-haos76` was the latest GitHub Release at that checkpoint, published 22 October 2026 at 22:12:46 UTC (23 October 09:12:46 Sydney): [GitHub Release](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.65-haos76). Tag/source `e70d9ff016a546615367b6d69f4ac4602da7b23c`, tree `42439dff8ee6e02bc503b5e36e05fc965996fc31`; PR #32 normally merged at `c226c98703263e3a0c5cd5ca811a2d39554ea315` with the same tree. Actions run `39862508030` succeeded for the exact source; the multi-architecture build job took 2m25s.

At .76 publication, GHCR version and `latest` OCI index: `sha256:b7df9f21fce7ef14e7b4f602235486e17b35b710907656dd0b43e796889a6e9a`. amd64 manifest/config: `sha256:153257933183c42fa99afdd21a8ab0d48837eb64623e136d7d0a07b3db17269e` / `sha256:2d344f0b9b0f7c67ef60e34fa95cf201ec271016521e0c645906349c5676f916`; arm64 manifest/config: `sha256:8288d84e1bd41858d022caff8b91d11adab998b21f99ee7d1a92985c9be4b161` / `sha256:962363630260823239533ba7bcae81625f11d5b303e01d872bebbc8a043e8945`. Both labels identify the expected version/revision. In each image `/app/.source_commit` equals the full source SHA plus LF; `/app/app/main.py`, `/app/app/optimizer.py`, `/app/app/models.py` and `/app/templates/index.html` match exact tag Git blobs. All 11 compressed layer hashes and diff IDs were checked against content-addressed manifests/configs using whiteout/override replay. The five-file verification digest covers the source pin plus those four files, using sorted relative path + NUL + bytes + NUL: `sha256:9e17b439b6a2dfc56fb238c9118d844d35fcb102e79e841678fdc2b07fd762a1`. The immutable `.75` version index remains `sha256:ed2a984b457bfddb2b74050d437f98337944076e9144a8d1a19f577d8e82d898`.

This establishes publication and image/source identity only. The operator reports that .76 was installed after replacement-SSD restoration on 24 October; the latest full startup/source proof still identifies `.75` at source `413e1691bb58e0b942098ab43f44e873df157a2b` on 21 October. Do not treat the operator report as a verified runtime identity. No physical acceptance or verified rollback is claimed. O13 code is published but physically unverified; O4, O5, O11 and applicable Phase 1/2 live gates remain open. O10 clock-recovery engineering is reopened in the .77 candidate; the separate archive/MSC incident investigation remains parked and HDD causation is unproven.

## Historical .77 release preparation - superseded by publication - 24 October 2026

Workspace `C:\Projects\sigenergy_optimizer-release-haos77`, branch `fix/combined-safety-trace-recovery`, based on main `e387010b83f7b017460870b1b456025f49f7e0a5`. The user approved completing the three fixes through source commit/PR, normal merges, tag/build verification and GitHub Release `2.3.66-haos77`. Reviewed source `f4cc6ae80df2d279cfef067f1ddd957916f8b3fc` was normally merged by [PR #34](https://github.com/Belot77/sigenergy-optimizer/pull/34) at `b4377de9f38d1c305c23a0b1dca9cb509afc1a9f` on 24 October 2026 at 01:46:14 UTC (12:46:14 Sydney). Both trees are `a8fc3a00fc7b0a9c0108b5123b5e7850bf1be9dd`. The release branch `release/2.3.66-haos77` starts from that merge. This step changes exactly the five synchronized version markers and release/status documentation; no control or trace logic is added. Release-specific checks passed all 16 tests in 9.35 seconds. Normalized comparison confirms exactly five version substitutions and no other production drift. Tag, Actions run, image digests and release identity remain pending. Installation is left to the operator; no live settings/control action is included.

The combined source integrates the separately validated O14 configuration-activation transaction and O16 import-ledger integrity candidate. O14 serializes validated configuration persistence/activation under the existing control lock, rechecks queued mutation authority, and retires affected identity evidence before refreshing its watchset. O16 preserves interval tariff/trust evidence through exact retries, stores interval/checkpoint/coverage atomically, and keeps incomplete history unknown. Existing Manual/Force and separately qualified PV-only behavior remain distinct; unknown accounting history can pause applicable automatic battery-backed/mixed sales beyond the current day.

O10 clock recovery is implemented and independently reviewed. A different/unknown boot or unresolved clock discontinuity requires two fixed certificate-verified HTTPS origins to corroborate current UTC through a worker-only subprocess bounded to twelve seconds, including DNS. Before a new anchor can permit persistence and active 24-hour pruning, full historical segment bytes and the completed-attempt status snapshot are durably preserved under `decision_trace/clock-history/<epoch>/`. Failed proof/preservation remains guarded, gap flags stay sticky, and the attestation requirement survives restart. No control decision, authority, settlement or system clock is changed. Preserved epochs remain outside normal downloads/retention; missing decisions cannot be reconstructed. See [clock recovery and operational limits](TRACE_CLOCK_RECOVERY.md).

Final combined offline validation passed **1,275 tests / 1,305 subtests**, zero failures, 206 existing warnings, in 226.40 seconds. Independent source/test/documentation review was GO with no High/Medium blocker; reviewers did not execute tests or access HA. Tests-first characterization reproduced both clock recovery defects and the integration accounting gaps before correction. The 15 combined-boundary tests pass, and the five focused trace suites passed 84 tests / 36 subtests (202 warnings, 11.22 seconds). A smoke check of the exact bounded subprocess/parent proof path succeeded against both fixed public HTTPS sources; this is development-host network evidence, not HA-network or physical acceptance. Original O14/O16 worktrees and the frozen trace candidate remain preserved.

The individual O14/O16 checkpoint sections below describe their original separate workspaces and approvals; their former local-only limits are superseded by this combined-release authorization. The explicit installation boundary, O5 policy, physical acceptance gates, and O11 parked status remain in force. See [the .77 candidate plan](HAOS77_RELEASE_CANDIDATE.md).

## Historical separate O14 local-fix checkpoint - 24 October 2026 (integrated above)

Approved local workspace: `C:\Projects\sigenergy_optimizer-config-activation-transactions`, branch `fix/config-activation-transactions`, based on main `e387010b83f7b017460870b1b456025f49f7e0a5`. The user approved this local fix branch only; no commit, push, release or live action is authorized by that approval. The original tests-only O14 reproduction and audit-intake worktrees remain preserved.

The candidate serializes validated single/batch configuration persistence and activation under the existing control lock; rechecks mutation authentication for queued configuration and direct ESS requests; and routes direct ESS writes through the same lock. Actual identity changes retire affected number-settlement, MSC-baseline, Solar-relief/dip, Boost and cache evidence, then refresh the entity watchset. It preserves the pending-MSC close barrier, authenticated Manual/Force and ESS overrides, and Standby-floor continuity across repeated activation. Pending Manual mode rejects queued selector/label interpretation changes, including swap. HA clients remain startup-bound; no restart policy or client rebuild requirement is introduced.

Before commit, withhold this isolated candidate to retain the existing baseline. Any later rollback must be a separately reviewed scoped revert, preserving other work; no reset or discard is authorized.

Final full offline validation passed 1,178 tests / 1,287 subtests, zero failures, 206 warnings, in 212.53 seconds. Focused control validation passed 208 tests / 99 subtests (203 warnings, 97.52 seconds); after queued-key revocation and literal consecutive-activation additions, 17 transaction/Standby tests passed (202 warnings, 1.82 seconds). The initial full run exposed 16 subtest failures in an existing Solar API test double missing the new transaction method; its assertions were preserved, its targeted module then passed 10 tests / 41 subtests (204 warnings, 0.80 seconds), and the full rerun above passed. Production code did not change for that fixture repair. Independent source/test safety review was GO with no High/Medium blocker; the reviewer did not rerun tests and separately confirmed the fixture repair preserves its assertions. This establishes local candidate validation, not publication or physical acceptance. The O14 baseline result is retained below: five deliberate regression failures and seven controls passed; the bounded combined run reproduced those same five failures with 154 existing passes and 92 subtests passing. This candidate is locally verified and remains unpublished. Latest supplied installed proof remains .75; no .76 installation or new live evidence is claimed. The separate O14 worktree remains an uncommitted, fully verified 13-file candidate with its recorded hashes and is not included in this O16 branch. O15/O17, parked O10/O11, O5 policy and Phase 1/2 gates are unchanged.

## Historical separate O16 local-candidate checkpoint - 24 October 2026 (integrated above)

Approved local workspace: `C:\Projects\sigenergy_optimizer-import-topup-ledger-integrity`, branch `fix/import-topup-ledger-integrity`, based on freshly fetched main `e387010b83f7b017460870b1b456025f49f7e0a5`. The user approved this local fix branch only. No commit, push, release, installation or live action is authorized. The separate verified O14 worktree remains preserved and is not part of this candidate.

Synthetic ledger/store characterization reproduced an accounting-evidence failure. An intact ledger with 1 kWh at 40¢ and 1 kWh at 5¢ correctly blocks a 30¢ export under a 40¢ floor. If the 40¢ insert fails after its measurement checkpoint advances, only the trusted 5¢ interval remains and `_decide` permits a 3.5 kW battery export; an untrusted interval can be lost the same way. A successful commit followed by a lost acknowledgement and blind retry duplicates 1 kWh to 2 kWh. Reordering only the in-memory checkpoint restores 2 kWh but prices both at 5¢, losing the original tariff evidence. These synthetic outcomes do not prove physical dispatch, actual financial loss or HDD causation.

The candidate adds an immutable-payload coordinator with IDs and a bounded 256-item queue, and atomically stores interval data, checkpoint and coverage state. It supports exact replay and rollback while retaining original tariff/trust evidence. Coverage remains unknown until reconciled and is sticky unknown across startup, legacy data, restart, source/day/counter changes, gaps and overflow; only a known-inactive, continuous midnight transition conservatively starts a newly covered day. Query failure remains unknown. This can pause applicable automatic battery-backed/mixed sales beyond the current day; independently qualified PV-only MSC and Manual/Force retain separate semantics. Measured import cost is captured before `_decide` using prior/observed permission, and post-close import tails are retained. Only completed automatic applications or confirmed Manual observations establish permission; no-op and pending outcomes do not. Manual import costs remain recorded and the Manual export exemption is unchanged. A missing daily counter stays `None` in policy state (the UI may display zero). The existing 1¢ cost and 0.01 kWh significance policies are unchanged; coverage is accounting continuity, not physical proof. O15 synchronous-storage offload remains separate. See [O16 design, validation scope and downgrade boundary](IMPORT_LEDGER_INTEGRITY.md).

Final offline validation passed 1,210 tests / 1,287 subtests, zero failures, 206 existing warnings, in 222.95 seconds. Focused ledger/decision/tariff/tier/Boost validation passed 244 tests / 268 subtests (203 warnings, 17.10 seconds). The first full run exposed 25 test/subtest failures with 1,192 tests and 1,280 subtests passing: existing positive-control fixtures changed scenario time/timezone after seeding accounting history at 14:00. Their synthetic accounting prerequisites were made explicit without changing assertions or production guards; the affected nine-module checks passed, followed by the successful full rerun above. Two dynamic Morning/Evening gate cases and the existing Boost-specific suites use an explicit known-empty cost context; dedicated O16 real-tick/decision tests retain the actual ledger and unknown-history veto. Production bytes remained unchanged through those fixture repairs. Independent source/test/documentation safety review was GO with no High/Medium blocker; the reviewer did not execute tests and separately reviewed the fixture changes. The four reviewed production SHA-256 values are recorded in IMPORT_LEDGER_INTEGRITY.md. All 13 protected O14 file hashes still match the pre-O16 checkpoint. This establishes a locally verified, uncommitted O16 candidate, not publication, installation or physical acceptance. O15/O17 remain queued; O10/O11 remain parked; O5 policy and Phase 1/2 gates are unchanged. Latest supplied installed proof remains .75, with no .76 installation or new live evidence. No files are staged. Before commit this candidate can be withheld; after any future commit, rollback requires a separately reviewed scoped revert and any installed ledger needs a reviewed data/coverage rollback plan.

## O14 offline baseline reproduction - 24 October 2026 (before local correction)

At that baseline checkpoint, the tests-only workspace was `C:\Projects\sigenergy_optimizer-config-authority-race`, branch `test/config-activation-authority-race`, based on main `e387010b83f7b017460870b1b456025f49f7e0a5`; its production files were identical to published .76. The original dirty audit-intake docs/worktree below are preserved byte-for-byte. The new test file and two carried-forward docs were the only changes in that checkpoint. No production fix, commit, push, release or live action was included in that tests-only work.

O14 is now reproduced offline: during the authority read immediately before EMS dispatch, authenticated real single/batch configuration routes activate a replacement Manual/Force selector and/or OFF switch. Old Automated/ON evidence then authorizes Grid First, including a batch that sends to the new EMS entity. The later failed/paused outcome does not undo that recorded call. Real FastAPI/authentication, `_apply` and the control lock run against synthetic ASGI/HA only. Focused result: five deliberate failures and seven passes (202 warnings, 2.17 seconds); bounded API/authority regression check: five same deliberate failures, 154 passes, 92 subtests passed (203 warnings, 31.06 seconds). No unexpected existing failure or full-suite run is claimed. Independent tests-only review was GO without rerunning tests; no physical charging or historical-incident cause is established.

At that baseline checkpoint, `fix/config-activation-transactions` was a proposal pending approval. The user has since approved that separate local branch; its implementation and completed local verification are recorded above. The baseline tests remain historical reproduction evidence, not validation of the fix. At this checkpoint O15/O16/O17 were still queued; the separate O16 candidate is now recorded above. Phase 1/2 gates, O5 and parked O10/O11 remain unchanged; .76 installation is still unproven.

## Independent audit intake and queued findings - 24 October 2026

The operator requested discussion and backlog recording of a supplied read-only audit of exact .76 source `e70d9ff016a546615367b6d69f4ac4602da7b23c`. Main was rechecked at `e387010b83f7b017460870b1b456025f49f7e0a5`; .76 remains latest published. At the original intake checkpoint, targeted static checks supported O14 configuration activation across awaited authority reads, O15 synchronous storage on async paths, O16 incomplete import-cost ledger/retry integrity and conditional O17 ingress trust. No dynamic reproduction, exploit, physical effect, introduction date or correction was established then. Subsequent O14 offline reproduction and local candidate, and O16 synthetic reproduction and separately approved local candidate, are recorded above. O15/O17 retain their static/conditional evidence limits. No introduction date, .76 regression or physical effect is established. See CURRENT_STATE.md for current status and evidence limits.

At intake time O14 and O16 were the proposed first triage candidates; O15 was a separate storage-resilience proposal. Separate local approvals followed, then the broader approval for the combined .77 source/PR/release sequence recorded above superseded their local-only action limits. O14 is locally verified and O16 is locally verified as a component; the integrated candidate still needs final validation. Archive-pause visibility and the original archive/MSC incident investigation remain parked; O10 clock-recovery engineering is now reopened in the current candidate, without inferring clock/HDD causation. O11 remains parked. O17 still needs proportional exposure verification and trusted-ingress handling, preserving normal HA authentication without another login or mandatory UI API key. Existing Phase 1/2 gates, O9 roadmap order and O5 policy remain unchanged. The operator later reported .76 installation on 24 October; the latest supplied installed source proof remains .75. The original audit-intake branch and files remain historical and preserved. See the current checkpoints above for approvals and verification state.

## Historical local .76 release preparation - superseded by publication - 23 October 2026

Workspace: `C:\Projects\sigenergy_optimizer-release-haos76`, branch `release/2.3.65-haos76`, based on verified main/PR #31 normal merge `632a42081d9ff93b270ffcca048604031ec4fed1`. Its tree `b051e77dda3b3cfb38dfa1df1f0696c6bce027b3` exactly matches reviewed fix commit `bcfdb75b33c8ae1db3c7f534cb8952f144d9c3cd`. PR #31 merged on 23 October at 08:54:29 Sydney. Candidate version is `2.3.65-haos76`; planned tag `v2.3.65-haos76`. Preparation changes only the five synchronized version markers and release/status documentation. No control logic, tests, defaults, permanent instructions or workflow changes are included.

The merged code fixes O13 import ownership for Standby Holdoff and active Morning Dump before fallback settlement waits and through recovery, plus the two settings-surface corrections. Combined control validation passed 1,149 tests / 1,287 subtests, zero failures, 206 existing warnings, in 211.18 seconds; seven focused owner regressions passed, as did six settings-UI checks. Independent code review found no High/Medium blocker. These results apply to the merged source and are retained for version-only preparation; they are not physical acceptance. All 16 release-consistency/source-pinning checks passed in 9.43 seconds. Two independent normalized comparisons proved exactly one version substitution per marker file and no other production drift. Independent release-metadata review was GO for the local candidate with no blocker; this is not publication or live acceptance.

At that prepublication checkpoint, `.75` was the latest release and `.76` had not yet been committed, tagged or published; those statements are superseded by the current receipt above. Its 21 October startup remains the latest full installed proof. The subsequent release and image verification do not establish installation or physical acceptance. See [the publication receipt and remaining gates](HAOS76_RELEASE_CANDIDATE.md).

Live acceptance, actual rollback readiness, Boost stability and O5 reserve policy remain open. Archive/MSC follow-up stays parked; failing HDD causation is unproven. The 23 October stale archive and the separate 21 October live-memory observations below do not establish current .75 behavior or .76 readiness for installation. Existing worktrees and unfinished changes remain protected.

## Historical multi-fix validation checkpoint - 23 October 2026 (before PR #31 merge)

Workspace: `C:\Projects\sigenergy_optimizer-fallback-standby-import`, branch `fix/fallback-standby-import-ownership`, based on verified main `3811d6a02069e850086fab2c1e042f7b9da40bff`. Main and published .75 tag/source `413e1691bb58e0b942098ab43f44e873df157a2b` were rechecked on 23 October. The operator approved this local branch after the offline preparatory ownership audit; this does not accept Phase 1/2 or authorize a new publication/live change.

New Medium finding O13: Standby Holdoff and active Morning Dump require import blocked, but .75 fallback retains only Demand Window import ownership. With trusted Demand OFF, the Standby real decision/fake-HA characterization requested zero import and 1 kW PV MAX; settled fallback reopened a synthetic 13.25 kW import capability, while unproven settlement omitted the import close. The 1 kW PV restriction belongs to that Standby case, not Morning Dump. This establishes permission behavior, not physical import. The local correction retains both explicit owners before settlement waits and through recovery, preserving ordinary economic-zero recovery and independent PV/ESS, Demand and Manual/Force safeguards. The separately reproduced Morning Dump case uses its supported blocked-export MSC branch, not a failed discharge proposal being treated as ownership. High/Spike preemption already clears Morning Dump ownership; that boundary is unchanged. Two settings-label/help corrections are included without changing configuration behavior. Tests-first characterization reproduced two Standby failures and, before the additional owner correction, two Morning Dump failures; controls retained ordinary economic-zero recovery and Demand uncertainty blocking. All seven focused owner regressions then passed (202 existing warnings, 6.97 seconds). Final combined validation passed 1,149 tests / 1,287 subtests, zero failures, 206 existing warnings, in 211.18 seconds. The six settings-UI checks passed separately. Independent combined source/test review found no High/Medium blocker. These are local validation results, not physical acceptance; see CURRENT_STATE.md for remaining gates.

The 23 October download `sigenergy_decision_trace_24h_20261022T211610Z.jsonl` has 9,325 valid records covering 18 October 19:59:12 to 19 October 07:58:42 Sydney. It is a byte-identical suffix of the earlier 21 October archive (SHA-256 `72f77e9b3b7d4fa8a3559237f735f1399f7dd7f4a78f8aa51a50bacc463cc8de`), ending 96h17m28s before its filename timestamp. No current .75 proof can be obtained from it; HDD causation remains unproven, and the operator's archive/MSC investigation remains parked.

A separate supplied live-memory sample from 21 October 13:28:26 to 13:53:10 Sydney has 267 records: 254 helper-success, eight pending and five failed with unsuccessful fallback. The first four failures subsequently recovered; the final recovery is unknown. At 13:53:00 a successful MSC cycle observed a 25 kW export ceiling, PV 16.506 kW, load 1.227 kW, battery charging 15.309 kW and zero export. Provider state remained UNVERIFIED, retaining normal charging pending a newer successful provider poll. These facts do not identify the application errors or establish O13 as their cause. No raw trace/log was copied into the repository.

Published .75 and supplied installed identity remain as recorded below. Boost live stability, reserve policy O5, other outstanding live gates and actual rollback readiness remain open. Existing unfinished worktrees are preserved. On 23 October the operator authorized one commit of this reviewed nine-file batch, a push of this fix branch and a review PR. Git and the PR establish the resulting source-control identity; this approval does not authorize merge, publication or live changes. Before commit the candidate can be withheld; any later rollback must be a separately reviewed scoped revert.

## Historical .75 published release and supplied HA evidence - 21 October 2026 (superseded as latest by .76)

**Latest published release: .75 / 2.3.64-haos75.** [GitHub Release](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.64-haos75) published 21 October at 02:24:59 UTC (13:24:59 Sydney); tag/source `413e1691bb58e0b942098ab43f44e873df157a2b`. PR #29 merged at `b88ac1f36811a253fc8602a781103a255ec932fd`, tree `07b2ab78766358c6838377796cce352a2f3ca69e` exactly matching the tag. Actions run `39532351637` succeeded. OCI index/latest is `sha256:ed2a984b457bfddb2b74050d437f98337944076e9144a8d1a19f577d8e82d898`; amd64 manifest `sha256:a242af5c9a0b40bdbdf62bc9b44e3d13c44e080d85ed11ad9661cf404835ef07`, arm64 manifest `sha256:38e22d54b4356f613c4ab75f80b5f7fa44e8f17c5b6de7b75c515870ed271a72`. Labels and embedded source/application bytes match the tag. The `.74` index remains unchanged at `sha256:3f3d46ce2cef41a8246cc63db2ef794c0e1907cf2a2518acf751cdc2646399ee`.

The operator reported `.74` installed, Evening Boost off, and add-on auto-update off. Later startup evidence at 13:28:25 Sydney reports runtime signature `2.3.64-haos75` and container source commit `413e1691bb58e0b942098ab43f44e873df157a2b`, matching the release tag exactly, with authenticated WebSocket/event-loop startup. Pending-close then pending-MSC states were reported from 13:28:26 through 13:28:29; HTTP 200 service/reads continued through 13:28:50. This confirms installed identity and those pending states in the excerpt, not physical settlement or later recovery. This is the latest supplied full startup/source proof; `.73` source `46d36358d38137231dff081176a372c3aa1f4cee` at 06:53:23 Sydney on 20 October is historical. No rollback method was supplied. Separate Browser/Node launcher attempts fail while enumerating `Z:\` (Windows error 1326), blocking direct tool access; no agent live changes or security changes were made.

Keep Boost off during installation checks and initial verification of exact runtime identity, effective settings, report cadence, and reserve/limit assumptions. Once those facts are verified, enable Boost only within the already-authorized supervised acceptance trial. Switch it off and retain manual ownership immediately on safety failure, unexpected ownership, failed settlement, or renewed flapping. Unattended use follows only after successful supervised acceptance. O4 remains live-unverified; O5 policy remains open.

The later supplied log tail `sigenergy_logs_20261021T023228Z.log` contains exactly 500 INFO HTTP 200 lines from 13:31:03 to 13:32:28 Sydney (85 seconds), with no warning/error records. It contains no observed EMS/limit or physical-flow values, so it does not prove settlement, reserve adequacy or Boost readiness. No raw log was copied into the repository.

### Historical .75 release preparation checkpoint - 21 October 2026

Current workspace: `C:\Projects\sigenergy_optimizer-release-haos75`, branch `release/2.3.64-haos75`, based on merged PR #28 at `2ea64b4aaa4da1cb61627e74e53761662df41e5e`. PR #28 merged the approved code fix commit `3494cb2d15585107721a63871a2d3f78ebeaa81d`. Release metadata targets `2.3.64-haos75`; `.74` remains the latest published release. Combined local source validation passed 1,142 tests / 1,287 subtests (zero failures, 206 warnings, 209.04 seconds), focused validation passed 90 / 103 (202 warnings, 4.73 seconds), and release-specific checks passed 16 tests in 9.89 seconds. Normalized verification confirmed exactly five marker replacements. No `.75` tag, image, GitHub Release or installation is claimed. Follow [the .75 candidate plan](HAOS75_RELEASE_CANDIDATE.md) for tag/build/image verification before merging release metadata and publication.

Operator report on 21 October: `.74` installed, Evening Boost off, auto-update off. Exact installed source and live acceptance remain unverified; last supplied startup/source evidence is `.73` at `46d36358d38137231dff081176a372c3aa1f4cee`. No rollback method was supplied. Keep Boost disabled until publication, installation and separately supervised live acceptance; O4 live stability and O5 policy remain open.

### Historical local Evening Boost reserve-trust and re-entry checkpoint - 21 October 2026

Current workspace: `C:\Projects\sigenergy_optimizer-boost-reentry-stability`, branch `fix/evening-boost-reentry-stability`, based on `.74` merge `4b7c8b2b6e8a22ee01db9c44942b7c8e8ed40b28`. It carries reviewed O12 reserve-trust changes plus newly approved O4 re-entry qualification. Neither is in published .74; the last supplied live proof remains .73. O12 requires existing `load_power_trusted` and `sunrise_observation_trusted` evidence for Boost eligibility and uses both observations in reserve calculation. Its previous independent checkpoint passed focused tests (41 / 55 subtests, 202 warnings, 2.12 seconds) and the full suite (1,112 / 1,247 subtests, zero failures, 206 warnings, 208.46 seconds). Do not treat those as validation of the combined source in this worktree.

The local O4 implementation requires fresh qualifying load-report timestamps spanning at least 120 seconds and at least 120 seconds of local monotonic elapsed time before initial or resumed Evening Boost admission; these are minimums, not an exact admission promise. Load timestamps advance monotonically with no gap over 60 seconds. A gap over 60 seconds or local elapsed time since the last advancing report resets qualification; heartbeat cadence and report latency can postpone admission indefinitely. Cached load reports cannot mature qualification. Sunrise keeps its existing trusted-future-horizon check and need not advance. Wall-clock or monotonic-clock rollback, or a failed gate, resets qualification/context. Closed / Qualifying / Admitted distinguishes permission from physical operation. Successful automatic application completion or verified MSC-pending state is required to retain qualification; generic no-op success is insufficient. Existing failure closures remain immediate; higher-priority owners and their permissions are unaffected. Final focused combined validation passed 90 tests / 103 subtests (202 warnings, 4.73 seconds); the full suite passed 1,142 tests / 1,287 subtests, zero failures, 206 warnings, in 209.04 seconds. Coverage includes fake-HA decisions, awaited-settlement races and simulated verified-MSC-pending outcomes; these do not prove physical operation or settlement. Independent review was GO for this local candidate with no High/Medium blocker; this is not live GO. Reviewed production SHA `bd4a7a8debae41e134cb9082e3240a3dedbd742ea119a64626bc9f45e4303ce0` remained unchanged since review. On 21 October 2026, the user authorized completing this update through commit/push, normal PR/merge and release publication, followed by installation and supervised checks, subject to verified HA access, rollback readiness and other operational gates. As of this pre-commit checkpoint, the candidate remains uncommitted and .74 remains latest published; no future action is claimed complete. Publication may proceed independently of HA access; installation readiness is unverified. Keep Boost disabled until release, installation and supervised acceptance are complete. Start with monitor-only/dry-run checks; supervised acceptance requires direct requested/observed/settled comparisons and explicit stop conditions. Local fake-HA tests do not establish physical behavior. On uncertainty, failed evidence or renewed flapping, stop Boost and retain manual ownership. Before commit the safe rollback was to withhold the branch; after commit, use only a separately reviewed scoped revert, preserving other work. The 21 October approval covers the two 120-second minimums and 60-second maximum load-report gap only: no 5.5 kW, 50% SoC, 20% reserve redesign, new safety hold or reserve-price rule is included. The 27 September proposal is superseded. O4 and O5 remain open; As of this pre-commit checkpoint, commit, publication, installation and live acceptance have not occurred; the user authorization to complete the sequence is recorded above.

PR #23 source-pinning fix `1042ee95c94c56eb64ff0a5ae123ca863c49cd25` is included in .73 and carried into .74. It selects a full SOURCE_REF matching HEAD or resolves BUILD_VERSION to the corresponding version tag, fetches and detached-checks out the selected source, and records its full identity. The original .72 tag/image remains at `3afefcd113d2c6f3eadd5aadd52fbda1a8b35f28` and does not contain that Dockerfile fix. See [HAOS73_STATUS_AND_LIVE_PROOF.md](HAOS73_STATUS_AND_LIVE_PROOF.md) for the dated fixes and scoped live-proof checklist.

### Published Solar stability change - 21 October 2026

PR #26 merged the reviewed `fix/solar-export-stability` checkpoint `fa9d926a734ceefd2426000d9edb92c037ac93a6` into main as `550c8eeee8239dfb3515d3a6c4b174f35e58f139`; merged tree `999b2cb4b405a409bf1f17df80d9ba85de5f016a` exactly matches the tested candidate. The change bridges brief Solar dips strictly before 15 seconds after the older fresh, coherent PV/load report proving measured surplus above 0.5 kW, following successful final Solar application. Both reports must advance to renew proof; held/cached evidence, 0.2–0.5 kW continuation and forecasts cannot renew it. Hard-gate or application failure invalidates proof immediately. Expiry requests closure under current authority, retaining deadline re-evaluation and bounded three-second retries after failed application. Independent limits and physical settlement requirements remain mandatory. See CONTROL_CONTRACT.md for exact conditions.

A sanitized deterministic characterization produced seven 25-to-zero kW closures at baseline; candidate ticks retain permission through the short dips with advancing strong measured reports. Mocked application with real ticks is not a complete trace replay or physical inverter proof; separate fake-actuator tests cover expiry fallback. The initial PV collapse remains unexplained. The Solar stability change is included in published .74; no .74 live behavior is verified here.

### Historical .74 release-preparation snapshot - before publication on 20 October

Release-preparation workspace `C:\Projects\sigenergy_optimizer-release-haos74`, branch `release/2.3.63-haos74`, started at merged main `550c8ee`. Candidate `2.3.63-haos74` changed only the five synchronized version markers and release documentation. At that pre-publication checkpoint, .73 remained latest and no .74 tag, image publication or installation had occurred. See [HAOS74_RELEASE_CANDIDATE.md](HAOS74_RELEASE_CANDIDATE.md) for the retained preparation and supervised-proof record.

Candidate-specific verification passed 16 release-marker/source-pinning checks in 9.05 seconds. Exact five-marker replacement and ten-file scope checks passed; independent release review found no blockers. These checks describe the pre-publication candidate. The later approved publication and verified image identity are recorded above.

At this pre-publication checkpoint, the control suite had passed 1,106 tests / 1,235 subtests, with zero failures and 206 warnings in 206.22 seconds; focused checks passed 115 tests / 191 subtests. Independent targeted safety review found no remaining blockers after expiry/failure scheduling and refreshed-export-readback corrections. Tests used fake HA, synthetic report provenance and simulated/fake actuator outcomes; they do not prove live settlement. Release preparation and separately supervised live proof remained required at that checkpoint. Do not infer deployment from integration or local test results.

### Historical standalone O12 checkpoint - 21 October 2026

O12 is a newly reproduced reserve-trust defect. Branch `fix/evening-boost-reserve-trust` starts from published .74 merge `4b7c8b2b6e8a22ee01db9c44942b7c8e8ed40b28`. The local narrow gate requires both existing `load_power_trusted` and `sunrise_observation_trusted` evidence for Evening Boost eligibility; the reserve calculation uses both observations. This adds no thresholds, durations or operator settings.

Baseline offline read-and-decide reproduction with fake HA identified four unsafe outputs under synthetic conditions (80% SoC, 30 kWh capacity and 15¢ FiT): missing, stale or unavailable load yielded 6.6 kW; missing sunrise observation yielded 4.4 kW. A valid tests-only red run reproduced the defect with expected failures in 12 assertions (10 subcases and two top-level checks); four tests and two subtests also passed. After the correction, the initial focused run passed 41 tests / 55 subtests in 2.07 seconds, with 202 warnings. The full suite passed 1,112 tests / 1,247 subtests, zero failures, 206 warnings, in 208.46 seconds; independent safety review found no blockers. After a test-only recovery-assertion refinement, the final focused run passed 41 tests / 55 subtests, with 202 warnings, in 2.12 seconds; production code was unchanged during that refinement. No second full-suite result is claimed. The new reserve-input scenarios exercise state reading and decisions only; no live actuation or physical proof was performed. O4 oscillation and O5 reserve policy remain separate and unresolved. The candidate is local, unreleased and uninstalled. It can be withheld; any committed rollback requires separate approval and must revert only this guard, preserving other fixes.

### Retained publication and live-proof evidence

The supplied 20 October trace contains 371 rows from 08:25:04 to 09:01:26 Sydney: 356 helper-success, 8 failed and 7 pending. Seven failures show fallback, pending, then success after 9–10 seconds. The last row reports Automated/MSC, PV export, battery charging and trusted status. Eight early success rows lacked trusted status. These records do not establish all physical limits or settlement outcomes.

O1–O12 retain their listed live, evidence or policy gates. O12 reserve-trust and O4 re-entry corrections are published in .75, with operator-supplied exact startup identity at 13:28:25 Sydney; physical acceptance remains unverified. Combined validation passed 1,142 tests / 1,287 subtests, focused 90 / 103 and release/source-pinning 16 checks. O5 reserve policy is unchanged. O10 archive staleness and O11 intermittent MSC observations remain parked with unproven causes; short physical Demand Window import spikes remain deferred and separate from O7 exact-full PV-only proof.

Protected .65 / 2.3.54-haos65 source and public amd64/arm64 images remain available. A separate Supervisor backup report had 49 errors across 7 files and reported backup.json missing; this does not establish that all backups are invalid. The actual .65 restore/reinstall path remains unproven. Do not infer restore readiness from public source/image availability.

For the earlier publication/documentation checkpoint, retained validation was the .72 full-suite result of 1,073 tests / 1,134 subtests, zero failures, 206 warnings in 170.97 seconds; .73 source-pinning/release checks passed 16 tests and local trace characterization was recorded as 56/12. Those historical results were not rerun for that documentation-only update. The later Solar stability candidate has its separate new full-suite result above.

Do not use release.sh: it preserves the existing haos suffix, updates only three of five version markers, stages all changes and can commit/tag/push. Keep installation and live changes separate from this documentation update.

## Historical Stage B checkpoint (16 October, before merge/publication)

- Writable worktree `C:\Projects\sigenergy_optimizer-authority-stage-b`; branch `fix/control-authority-safety`, origin `https://github.com/Belot77/sigenergy-optimizer`. Completed Stage B checkpoint: `ae4a974692aae1300c97845fcc32d4cfa6c2bdea` (`ae4a974692aa`), committed and pushed. At that historical checkpoint PR #20 was open against `main`; it was subsequently merged and .71 was published, verified on 17 October.
- Release candidate **2.3.60-haos71** is prepared with all five release markers aligned. This release-preparation commit contains only those markers and four approved documents; Stage B safety code/tests remain identical to the completed checkpoint. At that historical checkpoint the candidate was not tagged or published; publication was subsequently verified. Installation and live acceptance are not established here.
- Stage B implementation completed, including narrow Medium-over-Evening Boost priority correction. Supplied independent focused review passed corrections A/B/C. Retained final validation: **1,036 tests / 1,084 subtests, zero failures**; compileall and diff check passed. No full-suite/compileall rerun for documentation.
- **No supervised live acceptance. Stage B remains NO-GO for deployment.** Review/test success does not prove live settlement.

## Completed corrections and durable boundaries

- **A - Contradictory actuator evidence:** conflicting actuator observations cannot prove settlement. Deliberate discharge requires the intended export target, with fresh provenance-bearing evidence strictly after its own dispatch boundary; a smaller value sufficient for a safety close is not proof of a deliberate discharge target.
- **B - Independent ESS restrictions:** successful fallback cannot restore ESS charge/discharge capability above independently owned restrictions. Solar relinquishment restores only the otherwise safe normal charge request; Demand Window import blocking and independent PV restrictions remain effective.
- **C - Pending Force ownership:** unchanged Automated selector reports prove freshness, not a new operator selection. A pending authenticated Force request yields to a verified selector state transition strictly after its request, with coherent change/update/report timestamps; supersession stops subsequent writes/retries.

Preserve current Automated/Unknown/confirmed Manual-Force distinctions, dispatch-time authority, observed Remote EMS ON, independent Demand/ESS/PV restrictions, request-specific settlement, fallback and bounded retries. Preserve unattended restart auto-enable after current Automated verification; no persistent OFF registry or mandatory restart handback redesign. Manual/Force targets, including 25 kW, and authenticated `/set_ess` remain unchanged.

## Live identity, rollback and outstanding risks

The latest operator-supplied startup at 13:28:25 Sydney on 21 October identifies .75 / 2.3.64-haos75 at source 413e1691bb58e0b942098ab43f44e873df157a2b, exactly matching the published tag. This supports installed runtime identity but is not direct HA access or physical acceptance. The earlier 20 October .73 startup at source 46d36358d38137231dff081176a372c3aa1f4cee and .70/.71 identity reports are historical.

- The 20 October live trace sample contains 371 records (08:25:04–09:01:26 Sydney): 356 helper-success, 8 failed and 7 pending. Seven failures progressed through fallback, pending, then success after 9–10 seconds; eight early succeeded rows lacked trust. The last row reports Automated/MSC with trusted PV export and battery charging. These are reported telemetry/application records, not proof of all physical limits or settlement.
- .65 / 2.3.54-haos65, source 9965e79133f38d5b9943dcf5a9b04ed6fdab1239, and its public amd64/arm64 image remain available. A separate Supervisor backup report recorded 49 errors across 7 files and a missing backup.json; this does not mean all backups are invalid. The actual .65 restore/reinstall selection remains unproven.
- Physical inverter export maximum reportedly 15 kW. Physical grid-export enforcement and ESS limits are separate controls. Reported 15 October Morning Dump floor 15%, timing option 1.0 hour (sunrise through one hour after), Morning Slow near 2 kW, export near 15 kW, Evening Boost disabled and PV forecast about 130 kWh are historical operator context, not renewed verification.
- O1–O12 remain open for residual live acceptance, physical evidence or operator-policy gates. O1, O3 and O6 have narrow code corrections in .71/.72; this does not close their surrounding live and adjacent-behavior questions. O12 has a correction published in .75, with exact installed startup identity supplied by the operator; physical acceptance remains unverified. O10 is the stale archive/tail symptom; O11 is the parked intermittent MSC observation. The operator parked archive and MSC follow-up and paused the reminder; a suspected HA/hardware cause is unproven.
- Phase 1 and applicable Phase 2 live-proof requirements remain incomplete. Retain the 13-second historical observation gap, unexercised scenarios, Evening Boost stability and physical acceptance as recorded in CURRENT_STATE.md and ROADMAP.md.
- Protected dirty reference C:\Projects\sigenergy_optimizer-evening-priority (ten existing modifications) and Stage A worktree remain untouched. Never reset, stash, discard, overwrite, commit, delete or wholesale-copy its optimizer.

## Historical continuation sequence (superseded by current trace work)

The operator authorised one normal `.71` release-preparation commit and push on `fix/control-authority-safety`. The earlier 25-file development checkpoint is completed at `ae4a974692aa`; its pre-commit approval and dirty-state descriptions are superseded. At that pre-publication checkpoint PR #20 remained open and unmerged; it was subsequently merged. The publication step below is historical and completed; installation/live acceptance remain unverified.

1. Historical publication step completed: PR #20 was merged and tag/release `v2.3.60-haos71` was published, verified on 17 October. The former publication-approval/tag-absence instructions are superseded.
2. Obtain separate approval for supervised installation and live acceptance with .65 rollback ready.
3. Capture actual inverter state and physical-flow evidence.
4. Close or explicitly retain unresolved operational bugs based on evidence.
5. Proceed to the short control-ownership audit and existing approved roadmap.

Before any separately approved live acceptance, verify actual source/build, effective settings, current authority and .65 rollback readiness; plan supervision and explicit stop/rollback conditions. Capture timestamped requested/observed EMS, PV MAX, import/export ceilings, ESS limits, SoC, battery/PV/grid flows and reason/owner. Service-call success is not settlement.

Preserve the full approved roadmap order: ownership audit -> architecture -> project cleanup -> full GUI/UX -> Climate Manager integration. Climate Manager broadly works and is not the current priority.

Historical release-preparation validation: run the existing release-version consistency tests, compileall with an external cache, complete diff review and exact nine-file scope/marker-only checks. Retain the final full-suite evidence above; do not rerun the full suite for version-only preparation. Git tag/release absence and public GHCR version-manifest absence were reconfirmed before preparation; GitHub package listing lacks `read:packages` permission. That pre-publication recheck instruction is superseded by the 17 October verification of the completed .71 publication; any future candidate requires its own separately authorized publication review.
