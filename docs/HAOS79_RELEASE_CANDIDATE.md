# HAOS .79 local release candidate

Prepared 26 October 2026. Version **2.3.68-haos79**, proposed tag
`v2.3.68-haos79`. Workspace `C:\Projects\sigenergy_optimizer-release-haos79`,
branch `release/2.3.68-haos79`, based on freshly verified main
`fbe3bfcc14312952748f1991eec7836977adfcb5`.

Status: **local preparation only**. No commit, push, tag, image, GitHub release,
HA installation or live setting change is part of this step. Proposed tag,
GitHub release, metadata PR and versioned GHCR manifest are absent at preflight.
Repeat conflict checks immediately before any separately approved publication.
The future release/container source is the metadata commit still to be approved
and created; do not use the source merge SHA as installed-build identity.

## Verified source and bounded metadata scope

Reviewed O2/O6 source `ad0e89fdc72d9bb6d52b03aada0456e629bd2963`:
[PR #40](https://github.com/Belot77/sigenergy-optimizer/pull/40), normal merge
`fbe3bfcc14312952748f1991eec7836977adfcb5` at 07:31:05 Sydney on 26 October
(25 October 20:31:05 UTC). Two merge parents and exact tree
`6a70c7c55321372969d87e522e57e27a2271b0ce` were verified. No branch was deleted;
all unfinished workspaces and protected data remain preserved.

Five established markers change from .78 to .79: FastAPI version in `app/main.py`,
`_RUNTIME_SIGNATURE` in `app/optimizer.py`, add-on `config.yaml`, `build.yaml`
and `buildstamp.txt`. The remaining seven changes are README, CHANGELOG,
AI_HANDOVER, CURRENT_STATE, ROADMAP, SOLAR_REENTRY_STABILITY and this document.
No production difference beyond those single-marker substitutions is permitted.
Tests, control contract, Dockerfiles and build workflow remain unchanged.

O2 closes immediately after a failed strict aggregate budget, then requires fresh
qualification before Solar reacquisition; first admission and independent export
priorities remain intact. O6 qualifies only restrictive Solar charging after
completed genuinely owned relieved Morning charging at the normal safe bound.
Solar export and raw Morning priority remain intact. Both use advancing PV/load
report spans of 30 seconds plus 30 seconds monotonic time, with 60-second per-source
age/gap limits. Existing hard closures, hardware limits, provider authority,
Manual/Force, import restrictions and observed MSC settlement remain effective.

This packages the merged behavior; it does not add a minimum-charge policy,
forecast-fill guarantee, reserve/price adjustment or further stabilization rule.
Waiting may increase normal charging and reduce useful export. Longer cycles,
physical sensor causes and inverter behavior remain unproven.

## Validation and publication preflight

Retained merged-source validation: **1,415 tests / 1,380 subtests passed**, zero
failures, 206 existing warnings, 241.93 seconds. Focused controls passed 165 / 184
in 14.97 seconds. Independent source/helper/test reviews are GO. The later single
test EOF newline cleanup is AST-identical; no logic changed. The merged tree is
that exact reviewed checkpoint. All **16 release/version/source-pinning checks
passed in 9.83 seconds**. Canonical comparison proves exactly one marker
substitution per established file and no other production/test/workflow drift;
Windows CRLF checkout conversion is normalized only for that comparison, with
no line-ending rewrite. The exact scope is five markers plus seven documents.
Independent metadata/documentation review is GO after reconciling the pending
validation wording. No full-suite repeat was needed for marker/docs preparation.

Latest published release remains [2.3.67-haos78](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.67-haos78),
source `3ccf99cc69a4586715aadcbdd2f1282aeea77bf0`, published 24 October at
07:57:03 UTC (18:57:03 Sydney). Its immutable version index remains
`sha256:35292feb279a4b33e4c86f5482d690a9704c91d7178038b115c3bc434ead991a`.
Read-only GHCR preflight returned 404 for .79 and 200 with that .78 digest;
normal TLS validation was retained and only an anonymous token lived in memory.

After separate publication approval: commit exact reviewed metadata, push the
release branch and create its PR; tag the exact release commit and let the
tag-triggered workflow publish. Verify both amd64/arm64 source labels, source
pin and compressed/uncompressed layer identities before advertising the version.
Then normally merge the metadata PR with exactly the tag tree, publish the GitHub
release and record the final receipt. Branch pushes alone do not build images.

Image/source verification must include **fourteen** target files per platform:
`/app/.source_commit`, `/run.sh`, `/app/templates/index.html` and eleven under
`/app/app/`: `main.py`, `optimizer.py`, `models.py`, `routers/api.py`,
`state_store.py`, `import_topup_ledger.py`, `storage_worker.py`, `earnings.py`,
`decision_trace_store.py`, `trace_clock.py` and the new `solar_reentry.py`.
Do not reuse .78's thirteen-file proof without adding the new imported module.
The source pin is the exact tag commit plus LF. Registry/image identities do not
exist for this local candidate yet. Preserve the immutable .78 image identity.

Publication changes `latest` and the version offered by HA; it can affect
automatic updates. Before advertising .79 while installation remains separate,
confirm Auto update is still off. The older operator report is not current proof.

## Acceptance, limits and rollback

The operator reported mostly .77 then .78 on the morning of 25 October. Supplied
traces lack exact runtime/source identity; last full supplied startup/source proof
remains historical .75. No installed .79 build or physical acceptance is claimed.

Before separately approved installation, retain a usable binary- and data-aware
backup/restore plan. Preserve the full database, ledger intervals/coverage and
trace history/protected clock epochs. Do not truncate, reprice or fabricate
history, or assume an older binary can safely consume newer ledger data.
Local rollback is to withhold this uncommitted metadata candidate; a later source
rollback needs a scoped reviewed revert. No live downgrade is performed here.

After an approved installation, compare Runtime signature `2.3.68-haos79` and
Container source commit against the actual tag commit assigned during publication.
Monitor-only/dry-run proof should compare raw candidates, pending/qualified states,
per-source timestamps, final owners and requested limits without actuator writes.
Separately approved supervised live proof must compare actual flows/readbacks
across O2 budget failure/recovery and O6 relieved-Morning handoffs, retain immediate
hard closures and verify provider loss, independent limits and MSC transitions.
Stop on unsafe discharge/export/import, lost authority, repeated failure or renewed
harmful switching and return to the operator's chosen safe mode.

O18 fill/minimum-charge strategy, O5/O9 reserve/configuration review, broader O6
depletion/floor questions, parked O11 and existing live/Boost acceptance remain
open. This candidate grants no new live-control or Boost-enable permission.
