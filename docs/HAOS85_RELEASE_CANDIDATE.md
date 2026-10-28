# HAOS .85 local release candidate

**2.3.74-haos85 is not published.** This is local preparation on
`release/2.3.74-haos85` in `C:/Projects/sigenergy_optimizer-release-haos85`.
No metadata commit, tag, build, image digest, GitHub release or installation is
claimed. Publication requires separate approval of the final reviewed tree.

## Verified source and merge

Repository: https://github.com/Belot77/sigenergy-optimizer.
Source [PR #60](https://github.com/Belot77/sigenergy-optimizer/pull/60), reviewed
head `a5286581f402038be06375e45b62b525e65eb3e1`, merged normally on 28 October
2026 at 06:10:42 UTC / 17:10:42 AEDT. Merge commit:
`aefba54dddcaace1e3b318bbf6cca2a282d6c3a3`. Its parents are
`556cca8c040e3eea52029a8ac055a5c81f411018` and the reviewed head.
Merge tree `7bbc4d998081bf8fa606c71a9392930bba09a0b4` exactly equals the reviewed
source tree. Remote main and GitHub merge/parent/tree proof were verified.
The source branch remains clean and preserved; all nine original/unfinished
worktrees were preserved. Protected database metadata remained unchanged;
contents were never read.

The future tag/container source must be the separately approved metadata commit,
not this source baseline. The final candidate tree belongs in the publication
approval/proof. Do not invent a future commit, digest, build result or install.

## Behavior included

- Solar requests a protected-fill-energy/time-to-existing-deadline allowance,
  retaining a higher urgent-current-interval need, trusted normal capability
  and upward 0.01 kW precision. Fill progress has the approved priority when
  available PV cannot support both that allowance and desired export. This is
  a maximum-charging permission, not a forced minimum or a full-battery guarantee.
- A separate completed-total receipt permits only a retain-only same-context
  baseline rebase. Proposed/accepted individual writes, failed/pending/no-op/
  fallback/cancelled outcomes cannot mint it. Downward feedback retires/clips
  old permission before it can resurrect; changed commands require later
  feedback. Extra proof awaits retain final authority/provider/dip checks.
- Solar Dip permits a current-read unchanged persistent mode input_select with
  an old nonfuture report, while device/Remote EMS/flow limits stay binding.
- Accepted unchanged pending MSC/close epochs omit redundant writes only in
  the same actual-reader/control/source context and existing freshness lease.
  Expiry, contradiction, request replacement or lost continuity requires a new
  latest-boundary dispatch. Pending is uncommitted; intentional waiting logs
  separately from genuine errors. Passive diagnostics never grant authority.
- Reserve diagnostics explain required nominal energy and full-capacity
  shortfall. A 113% estimate is not a charge-above-100 command; raw reserve
  floors, the existing bounded HA helper and load/price policy remain unchanged.

Provider startup baseline/credible advance and expiry remain unchanged. Missing,
conflicting or genuinely stale proof may still block safely. This does not claim
all historical MSC failures share one cause. Morning priorities/handoffs,
Manual/Force, Demand Window, independent restrictions and existing physical
limits remain binding. Detailed source contracts and evidence are in
[CONTROL_CONTRACT.md](CONTROL_CONTRACT.md),
[SOLAR_FILL_PROGRESS_TRAJECTORY.md](SOLAR_FILL_PROGRESS_TRAJECTORY.md) and
[SOLAR_ALLOCATION_LIFECYCLE_PLANNING.md](SOLAR_ALLOCATION_LIFECYCLE_PLANNING.md).

## Local metadata scope

Exactly one version substitution per established marker, .84 to .85:

| File | Marker |
| --- | --- |
| app/main.py | FastAPI version |
| app/optimizer.py | runtime signature |
| sigenergy_optimizer_addon/config.yaml | add-on version |
| sigenergy_optimizer_addon/build.yaml | io.hass.version label |
| sigenergy_optimizer_addon/buildstamp.txt | clone-layer build stamp |

Seven release/status/design documents reconcile the normal merge and pending
publication. No tests, dependencies, workflows, packaging recipes, permanent
instructions, actual configuration settings or control behavior change in this
preparation. Independent root canonical review proved reversing those five
single substitutions recreates the exact baseline bytes after Git line-ending
normalization. All 12 changed files retain CRLF; the working index is unstaged.
Do not use release.sh. No staging or commit is needed to claim preparation ready.

## Validation and independent review

The exact merged source passed **1,632 tests / 1,606 subtests**, zero failures
(206 warnings, 274.24 seconds), with source/test/docs/scope independent GO.
Those are source-stage results; no new .85 full-suite run is claimed.

Two disjoint guarded release runs passed:

- Version consistency and Docker source-pinning fixtures: **16 tests**, zero
  failures, 9.21 seconds. Local Git fixtures reject missing/invalid/mismatched
  source and stop on clone/fetch/checkout failure. No settings or StateStore
  constructions occurred in these static tests.
- Solar/MSC integration, fill trajectory, pending epochs, Dip and reserve runtime
  modules: **72 tests / 175 subtests**, zero failures (202 existing warnings,
  37.73 seconds). Dotenv was disabled; settings forced `_env_file=None` before
  application imports. StateStore guards allowed 195 isolated temporary
  constructions and zero memory/runtime-database paths.

Total: 88 tests across the two disjoint runs, plus 175 subtests. A full suite was
not repeated for version literals/docs. Independent metadata/docs/scope review
is GO, with no remaining findings; reviewers did not rerun tests. This establishes
local release-preparation readiness only. Passing offline tests
cannot prove physical charging, export stability, sensor calibration or fill.

## Publication gates - not authorized by local preparation

If separately approved, use the reviewed candidate tree for one metadata commit,
branch push/PR and exact annotated `v2.3.74-haos85` tag. The tag triggers the
existing workflow; do not alter that workflow. Verify both linux/amd64 and
linux/arm64 images against the actual metadata source commit, all compressed/
uncompressed layers, normalized source bytes/modes, runtime/API versions and
generated source pin. Check version/latest registry digests and retain previous
.84 integrity. Then normally merge the metadata PR with identical tree, publish
the GitHub release, and prepare a separately authorized final receipt branch.
Do not claim any of these future steps complete in this candidate record.

Auto update was last reported off on 26 October; it is not reverified here.
Confirm current status before publication, because publication changes the
available version/latest image. Installation and live settings need their own
approval, actual startup identity, rollback readiness and supervised evidence.

## Prior release, acceptance and rollback

Latest verified GitHub release remains `v2.3.73-haos84`, published at
2026-10-28T03:51:01Z. Tag/container source:
`bc1439120ab6c68d5983768ffd678bb62fedefb8`. Last verified version/latest index:
`sha256:ce9f9c1abf04effd9ef33a0bfccc29282f9f81356f617cebd8a6b61e3c36f112`.
Revalidate immutable .84 image integrity during any approved publication.
Operator startup identifies installed .84 at 15:00:56 AEDT on 28 October.
No .85 installation or physical acceptance is established.

Risks: less immediate export and dependence on existing load/forecast/sensor
assumptions. The ten-minute trajectory assumes measured absorption and sufficient
PV; it is not a hardware model or proof under PV deficit. Monitor-only review
must correlate requested allowances/owners, independent setting reports,
advancing coherent flows, source/provider/command boundaries and outcomes.
Offline dry-run uses fake HA and isolated storage. Supervised live acceptance
requires separately approved installation/settings, exact runtime signature and
actual container source, effective limits, stop conditions and a usable operator
backup/reinstall method. A service-call success is not physical settlement.

Rollback now: withhold publication and preserve the candidate. After publication,
retain the prior immutable .84 identity, but do not claim a live rollback method
or backup has been demonstrated. Any source rollback requires a reviewed scoped
revert preserving unrelated work. Never reset/clean originals or remove runtime
archives/databases. No HA query, production write or Windows security change was
performed during preparation.
