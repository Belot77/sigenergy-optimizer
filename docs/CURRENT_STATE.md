# Current State

## Current published release: 2.3.74-haos85 - 28 October 2026

[GitHub release](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.74-haos85) was published at 2026-10-28T06:39:02Z (17:39:02 AEDT). Metadata PR #61 merged normally at `ca569f1b8b44e892f2eec471cae573c175f36ad5`, with parents `aefba54dddcaace1e3b318bbf6cca2a282d6c3a3` and `72bd1fdfdc824b019a5eba43f991e3ef0ee5bbe1`; merge tree `3ed6e5a677f1af72cfac503be91fe725375ea15b` matches the published metadata tree. Annotated tag object `8fc43ef082498766561acb15157175e48906adb3` resolves to source/tag commit `72bd1fdfdc824b019a5eba43f991e3ef0ee5bbe1` and that tree.

Build 40644593573 succeeded. Version and `latest` resolve to the same OCI index, `sha256:68a15730cd18592d153a27f29e4e801c5581c28680e86c299cdd9f478c120329`. The linux/amd64 manifest is `sha256:033e75f038393164f0d856925dd2da8c2ded84d8dc324e388b49b391eb79a37f`; linux/arm64 is `sha256:4345a9faed15a000144b529e83713adbe951de820dc72520376a195e5412d494`. The author-run verifier checked 11 layers and 15 pinned source files per platform, including the expected source fingerprint `sha256:ad811c36d2a1f6708cbc9e5a6badfd53f4bdea73221e7df205f438db8e44d4be`. Independent registry metadata and expected source byte/mode checks are GO; the independent reviewer did not redownload full layer bodies. The offline synthetic verifier passed 73 cases. Previous immutable .84 index `sha256:ce9f9c1abf04effd9ef33a0bfccc29282f9f81356f617cebd8a6b61e3c36f112` remains unchanged.

The merged source full suite passed **1,632 tests / 1,606 subtests**, zero failures. Disjoint guarded release runs passed **16 version/source-pinning tests** and **72 runtime-focused tests / 175 subtests**, zero failures; the full suite was not repeated for version literals and documentation. No control behavior changed in the release metadata.

Automatic updates were explicitly confirmed off on 28 October. Earlier operator evidence identifies installed .84 at 15:00:56 AEDT that day. The supplied 29 October 07:25:16 app log confirms runtime signature `2.3.74-haos85` and container source commit `72bd1fdfdc824b019a5eba43f991e3ef0ee5bbe1`; this confirms process identity at that time, not ongoing physical acceptance. Supervised charging/export/MSC/Boost/provider evidence remains outstanding. Do not claim universal resolution of historical MSC errors or guarantee battery absorption, deadline fill or physical stability. Keep .84 immutable; backup/reinstall rollback readiness has not been demonstrated. See [the publication receipt](HAOS85_RELEASE_CANDIDATE.md) and [fill policy and limits](SOLAR_FILL_PROGRESS_TRAJECTORY.md).

## Local unreleased fix checkpoint: failed export-close recovery - 29 October 2026

The supplied 500-row excerpt covers 07:46:40-08:25:03 AEDT: 113 succeeded, one failed and 386 pending. At 07:55-07:56, HA commands failed and restrictive fallback reported export-close acceptance False, with request boundary 1793220936.620536. Later observations reported exact MSC and current export limit 0.01 with fresh/accepted evidence, but the application remained stuck: the current .85 close epoch retained close_accepted=False, and the pending handler retried MSC only (up to 15 times). This documents the supplied trace summary; it does not establish a broader network cause.

The 29 October 07:25:16 app startup log confirms runtime signature 2.3.74-haos85 and source commit 72bd1fdfdc824b019a5eba43f991e3ef0ee5bbe1. This confirms process identity at that timestamp; it does not establish ongoing physical charge/export acceptance.

The local recovery implementation is narrow: in the restrictive hold branch, when an actual identity-bound pending epoch has a close boundary and close_accepted=False, retry the restrictive export close even if the current read already reports the close value. Retire the retained MSC phase, establish a new close-request boundary, require a later matching close report, then issue a new MSC request and require a later exact-MSC report. A readback alone must never set acceptance. A successful fallback close may be accepted for this sequence; it still does not mean the application completed successfully.

Keep legacy identity-None/non-live paths and trusted-closed startup with no close boundary unchanged. Preserve omission of a close already known accepted, Manual/Force, Remote EMS and current authority checks, exact request identity, live-state confirmation and independent restrictions. The separate UI stale-status banner can age while pending ticks restore the prior last_state; it is outside this close-recovery change and is not evidence by itself that no fresh read was attempted.

Tests-first validation reproduced both primary failures before the repair. After the repair, the new module passed 11 tests / 24 subtests and nine existing applicable modules passed 166 tests / 171 subtests. The final guarded full suite passed 1,643 tests / 1,630 subtests, zero failures (206 warnings, 278.26 seconds). Dotenv stayed disabled; StateStore guards allowed only 75 memory / 2,047 isolated temporary constructions. Independent source/test review is GO; independent documentation/scope review is GO. Protected database metadata matched, contents were never read, and all nine original unfinished worktrees matched their recorded hashes. These simulations establish software permission ordering, not physical acceptance. Risk is an extra restrictive close request and a renewed wait for later proof. Safest rollback is withholding this local candidate or a reviewed scoped revert. No commit, push, version bump, release, HA query, installation or live setting change was performed.

## Historical pre-merge source integration checkpoint - 28 October 2026

At this historical pre-merge checkpoint, the operator approved local integration, tests, independent review and docs on
`fix/solar-msc-planning-integration` at
`C:/Projects/sigenergy_optimizer-solar-msc-planning`. Verified base and remote main:
`556cca8c040e3eea52029a8ac055a5c81f411018`. The destination was absent before creation;
its initial branch/HEAD and clean status were verified. No original branch or unfinished worktree was modified at that checkpoint. No
commit, push, GitHub merge, version bump, publication, installation, HA query or
live setting change had been authorized at that stage; later source integration and
publication are recorded above. Installation and live acceptance remain unverified.

Included changes:

- Solar fill progress takes priority over immediate export, subject to existing
  ownership/provider/coverage/deadline/capability gates. Retain any higher urgent
  current-interval request. A charging-cap allowance is not a physical minimum.
- Same-context completed-total-only rebasing prevents tiny time/SoC baseline
  movements from discarding earned relief. It cannot donate upward confirmations,
  preserve a proposed/failed target or resurrect an older total after downward
  feedback. ESS setting readback remains passive evidence.
- Solar Dip accepts a current-read unchanged persistent mode helper without an
  upper report-age veto. Finite nonfuture metadata, availability/freshness/value,
  actual device/Remote EMS and flow limits remain mandatory.
- MSC accepted pending epochs omit duplicate requests only while their original
  reader/control/request identity and finite freshness lease remain valid.
  Actual new dispatches retain latest-boundary semantics. Typed intentional
  pending remains uncommitted and logs waiting; genuine errors remain errors.
- Passive reserve diagnostics explain nominal-capacity shortfalls. Raw reserve
  floors, existing current-load model and bounded HA helper are unchanged.

Original isolated stages remain preserved, unstaged and uncommitted:

| Worktree under C:/Projects | Branch | Standalone validation |
| --- | --- | --- |
| sigenergy_optimizer-solar-allocation-planning | test/solar-allocation-planning-haos84 | 196 tests / 221 subtests; tests/docs-only GO |
| sigenergy_optimizer-solar-dip-helper-currentness | fix/solar-dip-helper-currentness | 64 / 129; independent safety GO |
| sigenergy_optimizer-msc-pending-request-epoch | fix/msc-pending-request-epoch | final full 1,588 / 1,533; independent safety/fixture/docs GO |
| sigenergy_optimizer-battery-planning-diagnostics | fix/battery-planning-diagnostics | 132 / 140; passive source/tests/docs GO |
| sigenergy_optimizer-solar-fill-progress-trajectory | fix/solar-fill-progress-trajectory | final full 1,593 / 1,544; source/adversarial/expectation/docs GO |

Integrated production source matches the exact union of the four approved code
patches; independent source review is provisionally GO at optimizer SHA-256
`44e70ab7c83c2b4f26e80f1c92f5cbc8c5344e1cbba5cd7ce330d659fc7553f6`.
The first affected-module run exposed old lifecycle zero-cap/cohort/expiry-trigger
assumptions. Scoped expectation updates retained the strict rejection, provenance,
owner, fallback and Manual checks. Root validation of all 19 affected modules
passed **365 tests / 495 subtests**, zero failures (202 warnings, 80.60 seconds;
three memory / 615 isolated temporary stores). Eight new actual-reader interaction
methods passed **8 tests / 16 subtests** (202 warnings, 1.20 seconds; 22 isolated
temporary stores, zero memory/rejected paths). They cover original pending MSC
boundaries through Solar receipt/relief, typed-pending tick cleanup, replaced/
stale/regressed/cancelled final proof, earned-receipt/maintenance retirement,
diagnostic sink isolation, an old persistent helper with the original 15-second
dip expiry, provider-deadline expiry during the final read, and passive 113%
reserve projection with an actual helper write bounded at 100%.
Initial new-fixture corrections concerned helper timestamp coherence, the retired
identity sentinel and competing synthetic reserve estimates; production stayed
unchanged. Final independent source/test review is GO with no High/Medium
findings; reviewers did not execute tests. The final guarded full suite passed
**1,632 tests / 1,606 subtests**, zero failures (206 warnings, 274.24 seconds).
Dotenv stayed disabled; StateStore guards allowed only 75 memory / 2,018 isolated
temporary constructions. Source/tests stayed frozen. Scope is 32 files: one
production module, 23 test/runner files and eight documents. Independent documentation/scope review is GO. This is local software readiness, not installation,
physical charging, stable export or deadline-fill acceptance. Combined module SHA-256:
`0e778560214b30c9acce85bcb0818932e8cbd93d385e5a25999e2bce06c8ebdd`.
Dotenv must remain disabled and every StateStore construction restricted to
memory or isolated temporary storage; protected database contents are never read.

Operator startup evidence confirms installed `.84`, source
`bc1439120ab6c68d5983768ffd678bb62fedefb8`, at 15:00:56 AEDT on 28 October.
The supplied 16-row startup sample has four pending then twelve successes.
It does not prove ongoing physical acceptance. Provider authority was still
unverified pending a new credible provider generation; startup baseline/advance
and expiry rules remain unchanged. No supplied post-update recovery is invented.

Risks: less immediate export and dependence on existing sensor/forecast/load
assumptions; missing or contradictory proof still blocks permission. Monitor-only
acceptance must compare requested caps, setting reports, advancing coherent flows,
provider/command boundaries and outcomes. Offline dry-run uses simulated HA and
isolated storage; it does not calibrate sensors or model physical acceptance.
Installation/settings and supervised live acceptance require separate approval.
Rollback: withhold this uncommitted candidate or later review a scoped revert;
never reset/clean originals or remove runtime archives/databases. See
[Solar policy and validation limits](SOLAR_FILL_PROGRESS_TRAJECTORY.md),
[lifecycle characterization](SOLAR_ALLOCATION_LIFECYCLE_PLANNING.md) and
[CONTROL_CONTRACT.md](CONTROL_CONTRACT.md).

## Published: 2.3.73-haos84 - 28 October 2026

[Release](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.73-haos84)
published at 2026-10-28T03:51:01Z. Tag/container source `bc1439120ab6c68d5983768ffd678bb62fedefb8`;
reviewed tree `8ae40a1ef597ce3e07578e1fddb2483910337d35`. Metadata PR #58 merged normally at
`f7025eac808534428035d8dd7d842661da1ae18e`, with exactly the tagged tree. Source PRs #55, #56
and #57 are included: charge-readback metadata, Boost persistent-helper currentness,
proven pending-MSC epoch reuse, qualified unchanged-ceiling maintenance and bounded
passive settlement diagnostics.

Full source suite: **1,574 tests / 1,520 subtests**; release checks: **93 / 104**,
zero failures. Source, safety, metadata and image-proof reviews are GO. Build
[40628165315](https://github.com/Belot77/sigenergy-optimizer/actions/runs/40628165315)
succeeded. All 22 layer/diff-ID checks and 15 final source-file byte/mode checks
per platform passed. Version/latest index:
`sha256:ce9f9c1abf04effd9ef33a0bfccc29282f9f81356f617cebd8a6b61e3c36f112`. Previous immutable .83 is unchanged.

See [the complete publication receipt](HAOS84_RELEASE_CANDIDATE.md). Final receipt
worktree `C:/Projects/sigenergy_optimizer-haos84-publication-proof`, branch
`docs/haos84-publication-proof`, changes only five documents. Unfinished work and
protected database metadata remain unchanged. No HA access, installation or live
settings changes were performed. Later operator startup evidence confirms installed
.84 source `bc1439120ab6c68d5983768ffd678bb62fedefb8` at 15:00:56 AEDT on
28 October; ongoing physical acceptance remains unverified. Genuine
unavailable/conflicting reports can still block;
pending retry/latest-request and timeout rules, Solar allocation and provider
recovery remain separate. Do not claim every historical MSC error is fixed.

## Historical source candidate for .84 - 28 October 2026

Branch `fix/msc-maintenance-proof` at
`C:\Projects\sigenergy_optimizer-msc-maintenance-proof` starts at
`de29a8754c6707cc8ead0497d12290ddaf31aa57`, the normal merge of
[Boost PR #56](https://github.com/Belot77/sigenergy-optimizer/pull/56)
at 02:57:31 UTC. Charge-readback [PR #55](https://github.com/Belot77/sigenergy-optimizer/pull/55)
is already included through merge `223ac22356fcb0fc3e8f21aaa639b2fc013165c1`.
This source candidate carries the separately reviewed pending-MSC epoch fix and
adds qualified maintenance plus passive settlement evidence. Publication is
explicitly authorized; installation and live settings remain separate.

The pending-transition correction retains an already-proven original MSC
request instead of resetting its proof interval with an identical command.
Fresh exact MSC must remain strictly post-request; fresh closed-export proof
must remain strictly post-close where a close boundary exists. Already-trusted
closed startup retains its absent close boundary. Object identity, phase, both
boundaries and current authority remain checked before reopening and completion.

Maintenance is a separate path for an unchanged, already-open bounded
`MSC_SURPLUS_CEILING`. Completed application creates only a command candidate.
A later real-reader snapshot and joint live read must prove fresh exact MSC
strictly after its original MSC request and matching export-setting readback
strictly after its original opening/anchor request. Current authority, exact
bounded target, numeric-request identity and opaque control/source generation
must remain valid after relevant awaits. A baseline boolean or hand-built live
flag cannot grant reuse. Maintenance may repeat while all proof stays valid;
it cannot reopen a reduced/closed ceiling or increase the target.

When startup has no process-local numeric request anchor, one same-setting
request may establish it only after the final joint read confirms that the
live positive ceiling already equals the bounded target. This is not observed
settlement: a later matching report is still required. Failure, cancellation,
pending/fallback state, authority/config/source changes and lost continuity
retire maintenance evidence. Reader identity is captured before HA awaits;
reconnect during a read or application cannot label old data as a new epoch.
Solar/Morning charging ownership is rechecked after any added charge-proof
await. Independent restrictions and Manual/Force behavior remain binding.

Pending retry boundaries, latest-request semantics, existing three-second waits
and fallback ordering are unchanged. Slow, missing, conflicting or genuinely
wrong device reports can still block operation safely. This fixes the reproduced
software cases; it does not establish every historical error's cause or physical
acceptance.

Passive `application.msc_settlement` evidence uses existing reads only. It stores
allowlisted request boundaries/outcomes, normalized mode/limit values, correlated
report/update times, metadata status and rejection codes. Lists retain at most
12 requests and 12 observations per application; counters preserve totals.
No raw HA payloads, URLs, configuration identities or credentials are emitted.
Recorder failures do not change control decisions. Existing application status
and fallback outcomes remain; a bounded error code improves classification.

Validation: final focused run passed 56 tests / 41 subtests. The final guarded
full suite passed 1,574 tests / 1,520 subtests, zero failures (206 warnings,
268.32 seconds). Dotenv was disabled; StateStore guards permitted only 75 memory
and 1,914 isolated temporary constructions. Initial broader validation exposed
lightweight fixture initialization and synthetic-live provenance issues. The
candidate now requires actual-reader identity; existing Solar and event-loop
assertions were retained. Independent source/safety and documentation reviews
are GO, with no remaining High/Medium findings; reviewers did not rerun the
application suite. Author and independent OCI-verifier synthetic runs each
passed 73 offline checks. Exact publication identity/receipt follows separately.

Rollback is to withhold or scoped-revert this candidate; preserved original
worktrees remain untouched. Before separately approved live acceptance:

- Monitor-only: compare command boundaries, later state/report metadata,
  application/fallback outcomes and requested versus measured flows.
- Offline dry-run: use simulated HA and isolated storage to exercise epoch reuse,
  unchanged maintenance, anchor initialization, drift, failure, continuity and
  takeover. No global runtime no-write switch is claimed.
- Supervised live control: separately approve installation/settings, verify the
  exact runtime/source build, and retain existing stop conditions. Successful
  calls and passing tests do not establish physical settlement or stability.

## Historical local candidate: Evening Boost helper currentness — 28 October 2026

The approved local branch `fix/evening-boost-helper-currentness` at
`C:\Projects\sigenergy_optimizer-boost-helper-currentness` is based on
`223ac22356fcb0fc3e8f21aaa639b2fc013165c1`. It skips only the duplicate
upper-age check for a current-read trusted mode `input_select` in Evening Boost
re-entry. Availability, freshness, expected value, finite non-boolean timestamp and
non-future chronology remain required (`0 <= age`; a report one second in the
future is rejected). Remote EMS/device age limits and existing qualification,
Manual/Force, dispatch authority, limits, reserve/price, MSC and immediate
failure-closure protections remain unchanged.

The supplied 3,955 closed live decision records are consistent with the
helper-age gate, but raw rejected timestamps are absent from the supplied evidence and live
causation is not established. SolarDip helper-age follow-up and recurring MSC
failures remain separate open issues.

Validation: the tests-first run reproduced four reported failures, including
two dispatch subcases that could not reach admission. After the correction,
all seven new test methods passed with 25 subtests. The seven-module applicable
run passed 247 tests / 190 subtests (202 warnings, 45.08 seconds). The full suite
passed 1,535 tests / 1,481 subtests (206 warnings, 260.16 seconds), zero failures.
Dotenv was disabled; full-suite StateStore guards allowed only memory (75) or
isolated temporary paths (1,854 constructions). Independent safety and
documentation reviews are GO. These checks do not prove physical acceptance.

This is a local uncommitted change only: no release, installation, or live action. Rollback is
a scoped revert of the helper-age exception. See [AI_HANDOVER](AI_HANDOVER.md)
for verification steps.

## Merged checkpoint: charge readback report metadata — PR #55 — 28 October 2026

The charge-readback candidate below later merged normally in
[PR #55](https://github.com/Belot77/sigenergy-optimizer/pull/55), source head
`f6eb5ef1080b10e07aa40d2e5f07850f1ecd54a2`, merge
`223ac22356fcb0fc3e8f21aaa639b2fc013165c1`. It remains unverified in an
installation and has no physical acceptance claim.

## Historical pre-merge charge-candidate context — 28 October 2026

The approved local branch `fix/charge-readback-report-metadata` at
`C:\Projects\sigenergy_optimizer-charge-readback-metadata` is based on
`3b10c7007f4a592a48ba92ec4fa0da291e3f385e`. Its narrow candidate adds
`cfg.ess_max_charging_limit` to `_read_state` report entity IDs so unchanged
charge-limit observations can use HA's `last_reported` time when
`last_updated` stops advancing. Exact-state / `last_updated` correlation
remains. Missing or malformed metadata may use the existing `last_updated`
fallback; stale metadata remains subject to existing freshness checks.
Conflicting state / `last_updated` metadata sets `_actuator_metadata_conflict`
and rejects the observation timestamp. Existing age, post-command, matching,
and coherent-flow rules remain unchanged, and no timestamps are synthesized.
A failed metadata batch can reduce availability; the addition cannot help an
integration that omits the entity.

The supplied 448-row `.83` trace has every readback `fresh=false`, with report
time fixed at `06:04:53.712060` AEDT. The supplied Morning partial-qualification
export was not seen (maximum `3.557 kW` versus `14.5 kW`). This is the
pre-fix supplied evidence, not live validation of the candidate. Supplied
startup evidence identifies `.83` at 07:42:15 AEDT on 28 October, runtime
`2.3.72-haos83`, source
`51d370a559397e52e2b5f5012733b87fab7a8096`; physical acceptance remains
unestablished. Boost’s 3,955 selected decision records on 27 October and recurring
MSC failures remain separate open issues and are not fixed here.

Validation: both initial regressions failed before the query addition. The final
six-module guarded run passed 221 tests / 172 subtests (202 warnings, 43.24 s);
StateStore guards allowed only isolated temporary storage (314 constructions),
with dotenv disabled. One existing Solcast event-loop deadline test initially
woke 9.441 ms early; isolated unchanged-.83 and candidate checks passed, then
the complete applicable set passed on repeat. No timing assertions were changed.
Independent source/test review: GO. No full-suite run or live access was performed.
See [AI_HANDOVER](AI_HANDOVER.md) for monitor-only, offline dry-run and separately
approved supervised acceptance steps. This input correction can enable existing
Morning relief qualification, but its physical behavior remains unproven.
Rollback, if later committed, is a scoped revert of the report-entity query addition. No HA query, installation, or live
setting change was performed by this agent.

## Historical .83 publication checkpoint - 27 October 2026

Published at 04:13:16 UTC: [GitHub release](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.72-haos83).
Tag/container source: `51d370a559397e52e2b5f5012733b87fab7a8096`; reviewed tree:
`d0c370d71c1ac965c59de02901b6541b3e15fc96`.
Metadata [PR #53](https://github.com/Belot77/sigenergy-optimizer/pull/53) normally
merged at `ba3642cf66019614da0265e0b62426c124d910a7` with exactly that tree.
Source [PR #52](https://github.com/Belot77/sigenergy-optimizer/pull/52) supplies
bounded Morning Slow partial charging with completed-command, distinct setting
readback and later coherent-flow evidence. Forecast refill, import priority,
Manual/Force authority and independent MSC/import/export protections remain.

[Build 40448173242](https://github.com/Belot77/sigenergy-optimizer/actions/runs/40448173242)
succeeded at the exact tagged source. Version/latest OCI index:
`sha256:55b20ab7f7e5f6c0c80f9ef0c55fee69537769fe686b8560b2997ea8a9d513b3`.
Across amd64/arm64, all 22 compressed-layer hash/size and uncompressed diff-ID
checks passed, plus fourteen final source-file byte/mode checks per platform. Author and independent
runs each passed 71 offline verifier cases. Separate independent index/manifest/config
and Git-source comparison passed; it did not redownload the layer bodies.
Previous immutable .82 remains unchanged. See [the full publication receipt](HAOS83_RELEASE_CANDIDATE.md).

Retained guarded source suite: 1,525 tests / 1,450 subtests passed, zero failures,
206 warnings, 254.31 seconds. Release/source-pinning/Morning checks passed 37 / 11,
zero failures, 202 warnings, 11.53 seconds. Dotenv was disabled; StateStore guards
allowed only memory/isolated temporary paths (0 memory / 28 temporary constructions
in release checks). No full suite was repeated for five single version substitutions
or this documentation-only receipt. Independent source and metadata reviews were GO.

Receipt branch `docs/haos83-publication-proof` in
`C:/Projects/sigenergy_optimizer-haos83-publication-proof` starts at the exact normal
metadata merge and changes documentation only. Original unfinished work and the
separate tests-only Morning characterization remain preserved.

Installation, HA hundredth-kW setting precision and physical stability remain
unverified. Latest supplied 27 October startup identifies .81 source
`247095a4f9905932c3f5716f3d1be6cee7b3c7f8`; no later installed identity is claimed.
Auto update was last confirmed off on 26 October. No HA query, installation or live
setting change was performed. Solar feedback allocation and recurring MSC error
causes remain open. Next: separately approved installation and exact startup identity,
then passive observations and supervised physical validation. A requested limit or
successful API call is not proof of actual inverter response or a hard export bound.

## Historical .82 publication and verification - 27 October 2026

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

Installed .82 identity and physical acceptance remain unverified. Latest supplied
27 October startup identifies .81 source 247095a4f9905932c3f5716f3d1be6cee7b3c7f8;
auto update was last confirmed off on 26 October. No HA query,
installation or live setting change was performed. Solar allocation and recurring
MSC errors remain unresolved; limits and tariff/policy values remain decision-time
snapshots. Accepted cost risk remains: unpriced energy can export at a loss.

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


**CURRENT TRUTH ONLY:** durable semantics live in `CONTROL_CONTRACT.md`; sequencing lives in `ROADMAP.md`; historical decisions remain in `DECISIONS.md`.

## Retained cost policy and historical integration - 27 October 2026

Incomplete history or unpriced import alone is a warning, not an automatic
export veto. Finite actual import prices available in the existing shared
summary remain the floor even when coverage is incomplete; zero and negative
finite floors are valid, with no weighted average. That maximum is only a lower
bound while history is incomplete, and a cache/query miss or storage failure
may leave no known price available; this policy adds no last-known-price cache.
Accounting remains unknown/sticky when history is missing, and payload
retention, retries, checkpoint truth, and measured import accounting are
unchanged. `actual_import_cost_guard_active` may remain true as
context for PV-only clamping; `actual_import_cost_guard_blocking` means a known
priced-floor veto. Existing UI reason text may surface the warning/context; no
new setting or UI behavior is claimed.

The supplied two-day trace reports unknown cost at 06:09 on 26 October with a
Boost veto under the then-current cost policy; at midnight on 27 October
coverage recovered, followed by a 07:00 pending MSC application that invalidated
permission/history again. This is reported lifecycle evidence, not physical
settlement proof. Under the integrated policy, unknown-only cost warns and must
not itself veto Boost when independent authority, permission, settlement,
reserve and flow gates pass. A pending application may independently leave
permission unproven; the integrated lifecycle regression addresses this boundary.
The known finite floor remains binding when available, with incomplete-history
prices only a lower bound. Financial risk is accepted: unpriced energy may
export at a loss. The policy does not repair recurring MSC/application errors
or Solar allocation. .81 only added passive diagnostics; supplied 27 October
startup identifies .80 source `acb576747e808e927bdd7d12346c507da9b188b6`, not an
installed .81. Live behavior and physical acceptance remain unverified.

Historical O21 integration baseline (superseded by the local correction): Three separate scripted cases exercise current Demand ON, unknown, and trusted OFF. In each, the positive BATTERY_EXPORT proposal fails; the post-request EXPORT close is 0.01 kW and exact MSC proof is present. ON and unknown keep import closed; trusted OFF permits the fixture's 13.25 kW import recovery. Independently, normal Automated ESS discharge-capability restoration is rejected because the original GRID-EXPORT target (25 kW in this fixture) does not match current EXPORT 0.01 kW. `result.succeeded` and `fallback_succeeded` are false, with error `normal Automated ESS discharge capability returned failure`; ESS discharge capability remains 0.01 kW. These fixture values are not site configuration or physical-operation evidence. That integration-only baseline contained no source correction. Track as O21 (Medium: incomplete ESS discharge recovery after failed battery export), which blocked release readiness at the integration checkpoint. This issue is not assigned to O5 overnight reserve or O9 obsolete/overlapping policies.

Historical integration checkpoint: branch `fix/cost-fallback-integration` is in
`C:\Projects\sigenergy_optimizer-cost-fallback`, based on verified remote main
`623bd5d95f757de1074cabc4ee25570f2ef80cfd`. Union scope: 25 files (one
production source, 15 tests, nine documents). Original cost and O19 candidate
worktrees remain preserved. No files are staged or committed; no push, release,
installation or live action is included. The combined offline suite passed 1,499 tests / 1,429 subtests, zero failures, 206 warnings, in 244.32 seconds; strict guards recorded 75 in-memory and 1,799 temporary-path StateStore constructions, with dotenv disabled. Final focused three-module validation passed 23 tests / 20 subtests, 202 warnings, in 4.87 seconds; guards recorded 4 and 32 constructions. Independent source/test review is GO for this local integration and characterization only. O21 was unfixed at that historical integration checkpoint; see the local correction for current status. Standalone cost validation passed 1,476 tests / 1,404
subtests, zero failures, 206 warnings, 241.61 seconds; strict guards recorded
72 in-memory and 1,762 temporary-path StateStore constructions, with dotenv
disabled. Standalone O19 validation passed 1,477 tests / 1,426 subtests, zero
failures, 206 warnings, 244.15 seconds; its per-run guards recorded 74 in-memory
and 1,775 temporary-path constructions. These are separate historical results.
The cost branch's final focused four-file run passed 69 tests / 35 subtests,
202 warnings, 4.64 seconds; earlier related focused tests passed 219 / 254, 203
warnings, 17.97 seconds, after a tests-first red of 14 failures / 1 pass, 202
warnings, 1.80 seconds. Independent integrated source/test review was GO for this local change and characterization only; O21 was unfixed at that historical integration checkpoint; see the local correction for current status. Preserve the existing 120-second Boost minimum; a standalone fixture
admitted at 121 seconds after both minimums were met. No timing rule is weakened.
Offline scripted HA results do not establish physical operation or settlement.

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

## Historical local passive evidence checkpoint - before PR #46 merge

Approved branch `fix/solar-allocation-evidence` in
`C:\Projects\sigenergy_optimizer-solar-evidence` adds reported ESS charge-limit
provenance, five flow report timestamps, signed balance and Solar feedback
boundaries to new trace rows. Requested limits, reported settings and measured
battery power remain distinct. Existing controls, negative-flow rejection,
settlement and safe recovery are unchanged. No allocation fix, commit, push,
publication or live action is included. The original characterization workspace
and all unfinished work remain preserved. Applicable checks passed 204 tests /
196 subtests, zero failures, 202 existing warnings, in 42.15 seconds; focused
checks passed 19 / 22. Independent production review is GO; baseline control AST
comparison passes after removing only passive additions. No full-suite or physical
acceptance claim. [Contract and limits](CONTROL_CONTRACT.md#passive-charge-allocation-evidence).

## Current Solar allocation characterization - 26 October 2026

The operator reports installed .79. Supplied evidence shows both zero charge
requests near 15 kW export and a later screenshot with 18.87 kW charging/zero
export. The approved isolated `test/solar-export-charge-allocation` branch adds
tests and investigation documentation only. Strict flow rejection can reset
relief; pending restrictive-charge handoff permits normal charging. Fallback
recovery and cached status require careful separation from physical readback.
The screenshot's exact cause and physical command acceptance remain unproven.
Combined focused checks passed 105 tests / 136 subtests, zero failures;
independent test-source review is GO. No full-suite repeat was needed.
.80 does not change this controller. O18 remains open; see the
[characterization and next engineering boundary](SOLAR_EXPORT_CHARGE_ALLOCATION_CHARACTERIZATION.md).

## Historical .80 publication and verification - superseded by .81 - 26 October 2026

**Published at this historical checkpoint: 2.3.69-haos80.** [GitHub release](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.69-haos80)
published at 10:20:09 Sydney (25 October 23:20:09 UTC). Tag/container source
`acb576747e808e927bdd7d12346c507da9b188b6`, approved/tag tree
`14103ec71d3b41ad6a85e2d8a149e3db705606bf`. Metadata
[PR #44](https://github.com/Belot77/sigenergy-optimizer/pull/44) normally merged
at `77bde899da35b2f933304192a9c7226d9e5e9ef3`, retaining exactly that tag tree.

[Build 40243683190](https://github.com/Belot77/sigenergy-optimizer/actions/runs/40243683190)
succeeded. Version/latest index:
`sha256:91120b1039eec3915a37c6ff1a1210cf1cf5e79d97e3e1d9de31207206301a5a`.
Both platforms passed all 22 layer hashes/sizes and diff IDs; fourteen target files
per platform match exact tag source. Independent helper/proof review is GO,
including 68 synthetic cases independently rerun. Immutable .79 is unchanged.
See [the complete publication receipt](HAOS80_RELEASE_CANDIDATE.md).

Published .80 filters recognized successful HTTP INFO only from the UI buffer.
HTTP failures/unknown formats and other diagnostics keep their existing behavior;
console logs, ring bound/process lifetime and inverter controls remain unchanged.
Retained source checks passed 122 tests / 10 subtests; independent logging checks
passed 30 cases. All 46 release/source-pinning/logging checks passed with zero
failures, 202 existing warnings, in 10.69 seconds. No full-suite repeat or physical
acceptance is claimed. Receipt scope is six documents only.

Supplied trace failures remain unexplained; this is not an actuator or settlement
correction. O18, O5/O9, broader O6, parked O11 and physical/Boost acceptance remain
open. No HA installation or live setting changes were performed. Exact installed
.80 identity is unverified. Auto update was last operator-confirmed off on
26 October before .79 publication; no later change was reported or directly queried.
Original unfinished work is preserved. Following preparation and older-release
sections are historical; this summary establishes current publication status.

## Historical local .80 release preparation - 26 October 2026

The UI log-retention correction is merged through
[PR #43](https://github.com/Belot77/sigenergy-optimizer/pull/43): source
`512601da8083f88a260e343dd980c2c14183c814`, normal merge
`bcd9fe51f7303467ed8e463805c30284110e6a95`, exact reviewed/tested tree
`70805bd6f1f49eb47654b7c686c6a8d904371d13`. It is not yet published.

Local `2.3.69-haos80` preparation uses `release/2.3.69-haos80` in
`C:\Projects\sigenergy_optimizer-release-haos80`, from that verified main.
Only five synchronized version markers and six documents change. No further
logging, control, test, configuration-value or workflow change is included.
There is no .80 commit, tag, image, release or installation in this checkpoint;
the eventual metadata commit will supply exact container/source identity.
See [the candidate and acceptance limits](HAOS80_RELEASE_CANDIDATE.md).

Retained source checks passed 122 tests / 10 subtests, zero failures,
202 existing warnings, 68.94 seconds; independent focused logging verification
passed 30 cases. Independent source/test/documentation review is GO. No new full
suite or physical proof is claimed. All 46 release/source-pinning/logging checks
passed, zero failures, 202 existing warnings, in 10.69 seconds. Canonical comparison
confirms exactly five marker substitutions plus six documents. Independent metadata/documentation review is GO. Published .79 remains unchanged. Original unfinished work,
O18/O5/O9, broader O6, parked O11 and existing physical/Boost gates are preserved.
The supplied trace's actuator failures remain unexplained; this release changes
UI diagnostic retention only and does not repair physical settlement.

## Historical local UI log-retention correction - pre-commit checkpoint, 26 October 2026

Approved local worktree `C:\Projects\sigenergy_optimizer-log-retention`, branch
`fix/diagnostic-log-retention`, starts from verified main
`0a1955874e8599ac273b8c8c06b5e8cde5595600`. Only recognized successful 2xx
`httpx` INFO request messages are filtered from the UI handler's 500-record
memory ring. HTTP failures, unknown formats, other loggers and warnings/errors
retain their existing behavior. Console logs and logger levels are unchanged.
The original failure reproduction was 16 failed / 10 passed; the refined focused
module independently passed 30 cases. Combined logging, HA-client, ingress,
application-outcome and fallback checks passed 122 tests / 10 subtests, zero
failures, 202 existing warnings, in 68.94 seconds. Independent code/test review
is GO. No full suite or physical acceptance is claimed.

This records pre-commit validation of an unpublished local diagnostic correction.
Any subsequent approved commit or PR identity is established by Git; publication
and live actions remain separate. No HA access, control logic, retries, settlement,
release markers or runtime settings change.
The supplied trace's 65 application failures / 59 unsuccessful fallbacks remain
unexplained; later helper success does not prove physical settlement. The supplied
HTTP-only log covers a later, non-overlapping interval. Evicted/restarted UI history
cannot be recovered by this filter; older host/container logs may still exist.
Published .79 and existing installation/physical acceptance gates remain unchanged.

## Historical .79 publication and verification - superseded by .80 - 26 October 2026

**Latest published: 2.3.68-haos79.** [GitHub release](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.68-haos79)
published at 08:08:21 Sydney (25 October 21:08:21 UTC). Exact tag/container source:
`ea516ef6cabd9918dbea675694a9de3aa207c8af`; tree
`8e7e6cf6cdcbb6196383352c2a351f055aed5912`. Metadata
[PR #41](https://github.com/Belot77/sigenergy-optimizer/pull/41) normally merged
at `44419af295a47be24d5f06af3ed7cba83b2f27bb`, with exactly the tag tree.

[Build 40233491965](https://github.com/Belot77/sigenergy-optimizer/actions/runs/40233491965)
succeeded. Version/`latest` index:
`sha256:cbaa5f68e4830737abba90666e486b9db848b3a853d1c9138c33a93f3b02bdad`.
All 22 layer hashes/sizes and diff IDs passed; fourteen target files per platform
match exact tag source on amd64/arm64. Independent helper/proof review is GO,
including 68 synthetic verifier cases. Immutable .78 remains unchanged.
See [the complete publication receipt](HAOS79_RELEASE_CANDIDATE.md).

O2 aggregate-budget reacquisition and O6 relieved-Morning restrictive-charge
handoff corrections are published. Retained source validation is 1,415 tests /
1,380 subtests passed, zero failures, 206 existing warnings, 241.93 seconds;
focused 165 / 184. The 16 release/source-pinning checks passed in 9.83 seconds.
The receipt changes only seven documents; no full-suite repeat is required.
O18, O5/O9, broader O6 depletion/floor questions, parked O11 and existing physical
acceptance gates remain open. No new minimum-charge or forecast-fill guarantee exists.

The operator confirmed Auto update off on 26 October. No HA installation or live
setting change was performed. Exact installed .79 identity, physical behavior and
Boost acceptance remain unverified. Expected startup source is `ea516ef...`, not
the PR #40 source merge or PR #41 metadata merge. Supplied traces lack build identity;
last full supplied startup/source proof remains historical .75. All original
unfinished/backlog/characterization workspaces are preserved. The following dated
preparation sections are historical; current status and issue register supersede them.

## Historical 26 October merged O2/O6 and local .79 candidate

[PR #40](https://github.com/Belot77/sigenergy-optimizer/pull/40) normally merged
source `ad0e89fdc72d9bb6d52b03aada0456e629bd2963` into main at
`fbe3bfcc14312952748f1991eec7836977adfcb5` at 07:31:05 Sydney on 26 October.
Its tree exactly matches the reviewed and tested
`6a70c7c55321372969d87e522e57e27a2271b0ce`. O2 budget re-entry and O6 restrictive
charge handoff corrections are merged source, not yet published behavior.

`2.3.68-haos79` is locally prepared on `release/2.3.68-haos79` in
`C:\Projects\sigenergy_optimizer-release-haos79`, based on freshly verified main.
Only five synchronized version markers and seven release/status documents change.
No new control, test, workflow or configuration-value change is included.
It is not committed, pushed, tagged, published, installed or physically accepted.
The future tag/container source will be its separately approved metadata commit,
not the source merge above. See [the candidate](HAOS79_RELEASE_CANDIDATE.md).

Retained source checks passed 1,415 tests / 1,380 subtests, zero failures,
206 existing warnings, 241.93 seconds; focused 165 / 184. Independent source
review is GO. All 16 release/version/source-pinning checks passed in 9.83 seconds;
the 12-file marker/docs scope has no other canonical source/test/workflow drift.
Independent release metadata/documentation review is GO. Published .78 remains
current with verified version index
`sha256:35292feb279a4b33e4c86f5482d690a9704c91d7178038b115c3bc434ead991a`.
The operator reports .78 installed; supplied traces do not establish its exact
source identity. Original unfinished/backlog/characterization work is preserved.
O18, O5/O9, broader O6 depletion, parked O11 and existing physical gates remain open.

## Historical 25 October local O2/O6 stabilization candidate

Explicitly approved local branch `fix/solar-charge-reentry-stability` in
`C:\Projects\sigenergy_optimizer-solar-reentry`, based on freshly fetched
`origin/main` `c84a61b6a6ca1fb6d5f23c421f1f11ebf4a1ce49`.
The candidate implements separate 30-second PV/load and monotonic reacquisition
guards, with 60-second report age/gap bounds. O2 applies after Solar's strict
budget failure; O6 applies only to restrictive Solar charging after completed
relieved Morning charging. Existing priorities, normal safe charge bounds,
initial Solar admission, exact-full, immediate safety closure, provider authority
and observed MSC settlement remain effective. There is no minimum-charge policy
change or version bump. The local-fix approval excludes commit, push, release and
live actions; any subsequent commit identity is established by Git.

Original characterization and backlog workspaces are unchanged. Supplied traces
still lack exact installed-source identity. O2/O6 have validated, peer-reviewed
local corrections; physical acceptance and broader O6
floor/depletion questions remain open. O18 remains separate. Current validation
and acceptance limits are in [the candidate record](SOLAR_REENTRY_STABILITY.md).

Final full suite passed **1,415 tests / 1,380 subtests**, zero failures,
206 existing warnings, 241.93 seconds. Focused checks passed **165 / 184**,
202 warnings, 14.97 seconds. Independent peer review is **GO**. Syntax/whitespace,
15-file scope and all nine protected-original SHA-256 checks pass. This records
pre-commit validation; publication remains separate. No physical acceptance or
live action is claimed.

## Historical 25 October offline characterization checkpoint

Approved tests-only workspace: `C:\Projects\sigenergy_optimizer-charge-cycling`,
branch `test/solar-charge-cycling`, based on freshly fetched `origin/main`
`c84a61b6a6ca1fb6d5f23c421f1f11ebf4a1ce49`. The prior three backlog documents
were copied here while preserving their uncommitted originals.

Two new test modules reproduce the O2 Solar/normal and O6 Morning Slow/Solar
switches on consecutive six-second decisions. They retain real provider
qualification, eligibility, ownership arbitration and charge calculations;
detailed forecast curves and some configuration are explicit fixture assumptions.
This establishes current-source mechanisms, not an exact historical replay,
installed-source identity, physical application or lost-energy estimate.

Focused combined checks passed **118 tests / 127 subtests**, zero failures,
202 existing warnings, in 3.82 seconds. Independent read-only cross-reviews were
**GO**. No production or existing test file changed, and no full suite, commit,
push, release or live action was performed. O2/O6 remain unfixed; O18 remains a
strategy/policy investigation. See [the cases and next scope](SOLAR_CHARGE_CYCLING_CHARACTERIZATION.md).

## 25 October trace evidence and follow-up

Historical documentation-only intake requested by the operator. That branch is
`docs/trace-findings-20261025` in `C:\Projects\sigenergy_optimizer-release-haos78`,
based on verified main `c84a61b6a6ca1fb6d5f23c421f1f11ebf4a1ce49`.
This update records findings; it does not approve a production fix or policy change.

Evidence comes from the supplied `20261025T010208Z`, `20261025T020814Z`
and `20261025T074811Z` decision-trace downloads. All times below are Sydney
time on 25 October. The latest file has 17,224 valid records; 12,978 records overlap
the previous download with no changed content. Raw traces remain outside Git.
The operator reports mostly .77 followed by a .78 update that morning. A new
recorder session begins at 08:36:52, but no runtime/source identity is serialized;
the report and session boundary are not exact installed-source proof.

- **O6: Morning Slow/Solar charge ownership switching.** From 11:35:42 to
  11:37:24, nine Solar decisions requesting 0–2.82 kW alternate about every six
  seconds with Morning Slow requests of 21 kW. Forecast and tariff remain fixed
  while available-discharge energy fluctuates. The reference code's aggregate
  Morning Slow eligibility comparison explains the selection changes; underlying
  sensor behavior and exact applied configuration remain unproven.
- **O2: Solar/normal energy-budget cycling.** After the last observed Morning
  Slow row at 11:58:58, there are 53 Solar-to-normal exits and 52 returns through
  13:06:54. Of the 53 exits, 47 fail the aggregate energy budget, two fail measured
  surplus and four close during a pending MSC transition. Current load is
  extrapolated through the remaining daylight horizon, so load changes can flip
  the strict budget comparison while Remaining Today is unchanged. The Solar
  dip-hold does not override a failed aggregate budget.
- **O18: Fill-strategy robustness under forecast downgrades.** The added
  11:51:57–13:06:54 segment contains 301 zero-charge requests in 50 runs; the
  longest recorded span is 3m12s. Those requests are intentional under the
  existing future-opportunity/protected-fill policy. In the morning-started
  session, SoC peaks at 73.3% at 13:43:43, reaches only 69.6% at the configured
  16:29:52 fill deadline and ends at 65.8% at 18:36:56. After 13:09:53, normal
  charging consistently requests 21 kW. At 14:08:27, Forecast Today falls from
  79.325 to 66.6231 kWh and Remaining Today from 17.7734 to 4.8182 kWh.
  The fill objective was missed; the marginal contribution of earlier bypass
  cannot be established without a defensible counterfactual. This is an
  investigation and operator-policy review, not a confirmed defect in every zero request.
- **Linked O5/O9 diagnostic review.** The final 113% export-floor message is an
  uncapped calculated overnight reserve requirement, not a request to charge
  above 100%. Review planning assumptions and operator wording separately from
  actuator safety and the existing unapproved reserve/price policy.
- **Existing acceptance limits remain.** Six afternoon application failures
  each reach recorded helper success 9–10 seconds later, without proving
  physical settlement or cause. O11 stays parked. Provider expiry recovers after
  one three-second cycle in both observed afternoon cases. Boost is never
  admitted. These observations do not close the existing operational gates.

The subsequently approved tests-only characterization is complete as recorded
above. Next, design stabilization for both boundaries, then review charging
deferral under forecast revisions. Preserve immediate
trust/authority failures, independent limits, MSC settlement and unknown-cost
protections. Any implementation or change to zero-charge/minimum-charge policy
needs a separately approved staged scope. No thresholds, runtime settings,
production code, tests, release markers or live systems change in this intake.

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

At the .76 checkpoint, latest GitHub Release was `.76` / `2.3.65-haos76`, published 22 October 2026 at 22:12:46 UTC (23 October 09:12:46 Sydney): [GitHub Release](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.65-haos76). Tag/source `e70d9ff016a546615367b6d69f4ac4602da7b23c`, tree `42439dff8ee6e02bc503b5e36e05fc965996fc31`. PR #32 normally merged at `c226c98703263e3a0c5cd5ca811a2d39554ea315`; its tree exactly matches the tag. Actions run `39862508030` succeeded at the exact source; the multi-architecture build job completed in 2m25s.

At .76 publication, GHCR version and `latest` OCI index is `sha256:b7df9f21fce7ef14e7b4f602235486e17b35b710907656dd0b43e796889a6e9a`; amd64 manifest/config `sha256:153257933183c42fa99afdd21a8ab0d48837eb64623e136d7d0a07b3db17269e` / `sha256:2d344f0b9b0f7c67ef60e34fa95cf201ec271016521e0c645906349c5676f916`, arm64 manifest/config `sha256:8288d84e1bd41858d022caff8b91d11adab998b21f99ee7d1a92985c9be4b161` / `sha256:962363630260823239533ba7bcae81625f11d5b303e01d872bebbc8a043e8945`. Labels identify the expected version/revision. In each image `/app/.source_commit` equals the full source SHA plus LF; `/app/app/main.py`, `/app/app/optimizer.py`, `/app/app/models.py` and `/app/templates/index.html` match exact tag Git blobs. All 11 compressed layer hashes and diff IDs were checked against content-addressed manifests/configs with whiteout/override replay. Five-file verification digest (source pin plus four application files): `sha256:9e17b439b6a2dfc56fb238c9118d844d35fcb102e79e841678fdc2b07fd762a1`; `.75` immutable version index remains `sha256:ed2a984b457bfddb2b74050d437f98337944076e9144a8d1a19f577d8e82d898`.

The operator reports .76 installed after replacement-SSD restoration on 24 October. The latest full startup/source proof remains `.75` / source `413e1691bb58e0b942098ab43f44e873df157a2b` on 21 October; the .76 installation report is not yet backed by a new runtime/source excerpt. No physical acceptance, settings confirmation, Boost enablement or verified rollback is claimed. O13 code is published but physically unverified. O4, O5, O11 and applicable Phase 1/2 live gates remain open. O10 clock-recovery work is reopened in the combined .77 candidate; archive/MSC incident investigation remains parked and HDD causation is unproven.

## Historical .77 release preparation - superseded by publication - 24 October 2026

Workspace `C:\Projects\sigenergy_optimizer-release-haos77`, branch `fix/combined-safety-trace-recovery`, based on main `e387010b83f7b017460870b1b456025f49f7e0a5`. The user approved completing the three fixes through source commit/PR, normal merges, tag/build verification and GitHub Release `2.3.66-haos77`. Reviewed source `f4cc6ae80df2d279cfef067f1ddd957916f8b3fc` was normally merged by [PR #34](https://github.com/Belot77/sigenergy-optimizer/pull/34) at `b4377de9f38d1c305c23a0b1dca9cb509afc1a9f` on 24 October 2026 at 01:46:14 UTC (12:46:14 Sydney). Both trees are `a8fc3a00fc7b0a9c0108b5123b5e7850bf1be9dd`. The release branch `release/2.3.66-haos77` starts from that merge. This step changes exactly the five synchronized version markers and release/status documentation; no control or trace logic is added. Release-specific checks passed all 16 tests in 9.35 seconds. Normalized comparison confirms exactly five version substitutions and no other production drift. Tag, Actions run, image digests and release identity remain pending. Installation is left to the operator; no live settings/control action is included.

The combined source integrates the separately validated O14 configuration-activation transaction and O16 import-ledger integrity candidate. O14 serializes validated configuration persistence/activation under the existing control lock, rechecks queued mutation authority, and retires affected identity evidence before refreshing its watchset. O16 preserves interval tariff/trust evidence through exact retries, stores interval/checkpoint/coverage atomically, and keeps incomplete history unknown. Existing Manual/Force and separately qualified PV-only behavior remain distinct; unknown accounting history can pause applicable automatic battery-backed/mixed sales beyond the current day.

O10 clock recovery is implemented and independently reviewed. A different/unknown boot or unresolved clock discontinuity requires two fixed certificate-verified HTTPS origins to corroborate current UTC through a worker-only subprocess bounded to twelve seconds, including DNS. Before a new anchor can permit persistence and active 24-hour pruning, full historical segment bytes and the completed-attempt status snapshot are durably preserved under `decision_trace/clock-history/<epoch>/`. Failed proof/preservation remains guarded, gap flags stay sticky, and the attestation requirement survives restart. No control decision, authority, settlement or system clock is changed. Preserved epochs remain outside normal downloads/retention; missing decisions cannot be reconstructed. See [clock recovery and operational limits](TRACE_CLOCK_RECOVERY.md).

Final combined offline validation passed **1,275 tests / 1,305 subtests**, zero failures, 206 existing warnings, in 226.40 seconds. Independent source/test/documentation review was GO with no High/Medium blocker; reviewers did not execute tests or access HA. Tests-first characterization reproduced both clock recovery defects and the integration accounting gaps before correction. The 15 combined-boundary tests pass, and the five focused trace suites passed 84 tests / 36 subtests (202 warnings, 11.22 seconds). A smoke check of the exact bounded subprocess/parent proof path succeeded against both fixed public HTTPS sources; this is development-host network evidence, not HA-network or physical acceptance. Original O14/O16 worktrees and the frozen trace candidate remain preserved.

The individual O14/O16 checkpoint sections below describe their original separate workspaces and approvals; their former local-only limits are superseded by this combined-release authorization. The explicit installation boundary, O5 policy, physical acceptance gates, and O11 parked status remain in force. See [the .77 candidate plan](HAOS77_RELEASE_CANDIDATE.md).

## Historical separate O14 local-fix checkpoint - 24 October 2026 (integrated above)

At this separate-candidate checkpoint, the user approved only the local branch `fix/config-activation-transactions` in `C:\Projects\sigenergy_optimizer-config-activation-transactions`, based on main `e387010b83f7b017460870b1b456025f49f7e0a5`. The later combined-release approval above supersedes that earlier action limit. The separate tests-only O14 reproduction and original audit-intake worktrees remain preserved.

The candidate performs validated single/batch configuration persistence and activation inside the existing control lock, rechecks mutation authentication for queued configuration and direct ESS requests, and routes direct ESS writes through the same lock. Actual identity changes retire affected number-settlement, MSC-baseline, Solar-relief/dip, Boost and cache evidence before refreshing the entity watchset. It preserves the pending-MSC close barrier, authenticated Manual/Force and ESS overrides, and Standby-floor continuity across repeated activation. Pending Manual mode rejects queued selector/label interpretation changes, including swap. HA clients remain startup-bound; no restart policy or client rebuild requirement is added.

Before commit, withhold this isolated candidate to retain the existing baseline. Any later rollback must be a separately reviewed scoped revert, preserving other work; no reset or discard is authorized.

Final full offline validation passed 1,178 tests / 1,287 subtests, zero failures, 206 warnings, in 212.53 seconds. Focused control validation passed 208 tests / 99 subtests (203 warnings, 97.52 seconds); after queued-key revocation and literal consecutive-activation additions, 17 transaction/Standby tests passed (202 warnings, 1.82 seconds). The initial full run exposed 16 subtest failures in an existing Solar API test double missing the new transaction method; its assertions were preserved, its targeted module then passed 10 tests / 41 subtests (204 warnings, 0.80 seconds), and the full rerun above passed. Production code did not change for that fixture repair. Independent source/test safety review was GO with no High/Medium blocker; the reviewer did not rerun tests and separately confirmed the fixture repair preserves its assertions. This establishes local candidate validation, not publication or physical acceptance. No physical behavior or historical incident cause is established. The separate O14 worktree remains a fully verified, uncommitted 13-file candidate with its recorded hashes and is not included in this O16 branch. O15/O17 remained unfixed at this checkpoint; O10/O11 follow-up was parked then. O10 clock recovery is now reopened above; archive/MSC investigation and O11 remain parked. O5 policy and applicable Phase 1/2 live gates are unchanged. At this checkpoint latest supplied installed proof remained .75; the later .76 operator report is stated above.

## Historical separate O16 local-candidate checkpoint - 24 October 2026 (integrated above)

At this separate-candidate checkpoint, the user approved only the local branch `fix/import-topup-ledger-integrity` in `C:\Projects\sigenergy_optimizer-import-topup-ledger-integrity`, based on main `e387010b83f7b017460870b1b456025f49f7e0a5`. The later combined-release approval above supersedes that earlier action limit. That O16 branch did not include the separate O14 candidate; the combined integration is described at the top of this document.

Synthetic ledger/store characterization demonstrates a missing-cost-evidence failure. An intact ledger with 1 kWh at 40¢ plus 1 kWh at 5¢ blocks a 30¢ export under a 40¢ floor. If the 40¢ insert fails after its checkpoint advances, only the trusted 5¢ interval remains and `_decide` permits 3.5 kW battery export; failure of an untrusted interval can likewise lose coverage. A successful commit followed by lost acknowledgement and blind retry duplicates 1 kWh to 2 kWh. Reordering only the in-memory checkpoint restores 2 kWh but prices both at 5¢. This is synthetic accounting/decision evidence only; no physical dispatch, actual financial loss or HDD causation is established.

The candidate adds an immutable-payload coordinator with IDs and a bounded 256-item queue; interval, checkpoint and coverage state are stored atomically with exact replay and rollback, preserving original tariff/trust evidence. Coverage stays unknown pending reconciliation and remains sticky unknown across startup, legacy data, restart, source/day/counter changes, gaps and overflow. Only known-inactive continuous midnight conservatively establishes a newly covered day; query failures remain unknown. Unknown history can pause applicable automatic battery-backed/mixed sales beyond the current day; independently qualified PV-only MSC and Manual/Force retain separate semantics. It measures import cost before `_decide` using prior/observed permission and retains post-close import tails. Only completed automatic applications or confirmed Manual observations establish permission; no-op/pending outcomes do not. Manual import costs remain retained, its export exemption remains unchanged, and a missing daily counter stays `None` in policy state (UI may display zero). Existing 1¢ cost and 0.01 kWh significance policies are unchanged. Coverage is accounting continuity, not physical proof. O15 synchronous-storage offload is separate. See [O16 design, validation scope and downgrade boundary](IMPORT_LEDGER_INTEGRITY.md).

If this candidate later writes the additive ledger tables to an installed database, downgrade to an older binary is not automatically ledger-safe because that binary reads only the legacy table. Preserve the new rows; any future deployment needs a separately reviewed data/coverage rollback plan. No installation or live migration is authorized here.

Final offline validation passed 1,210 tests / 1,287 subtests, zero failures, 206 existing warnings, in 222.95 seconds. Focused ledger/decision/tariff/tier/Boost validation passed 244 tests / 268 subtests (203 warnings, 17.10 seconds). The first full run exposed 25 test/subtest failures with 1,192 tests and 1,280 subtests passing: existing positive-control fixtures changed scenario time/timezone after seeding accounting history at 14:00. Their synthetic accounting prerequisites were made explicit without changing assertions or production guards; the affected nine-module checks passed, followed by the successful full rerun above. Two dynamic Morning/Evening gate cases and the existing Boost-specific suites use an explicit known-empty cost context; dedicated O16 real-tick/decision tests retain the actual ledger and unknown-history veto. Production bytes remained unchanged through those fixture repairs. Independent source/test/documentation safety review was GO with no High/Medium blocker; the reviewer did not execute tests and separately reviewed the fixture changes. The four reviewed production SHA-256 values are recorded in IMPORT_LEDGER_INTEGRITY.md. All 13 protected O14 file hashes still match the pre-O16 checkpoint. This establishes a locally verified, uncommitted O16 candidate, not publication, installation or physical acceptance. No files are staged. The candidate can be withheld before commit; after any later commit, rollback requires a separately reviewed scoped revert. Any installed ledger also requires a reviewed data/coverage rollback plan. It remains local, unreleased and not live-verified.

## Historical .76 local release candidate and merged fix - 23 October 2026 (superseded by publication)

At this prepublication checkpoint, PR #31 had normally merged reviewed fix `bcfdb75b33c8ae1db3c7f534cb8952f144d9c3cd` into main at `632a42081d9ff93b270ffcca048604031ec4fed1` on 23 October at 08:54:29 Sydney. Both trees were `b051e77dda3b3cfb38dfa1df1f0696c6bce027b3`; exact reviewed-tree preservation was independently verified. O13 and the two settings-surface corrections were integrated; publication status is now recorded above.

The release-preparation workspace branched from that merge and introduced only the five established version markers and release/status docs. At that time `.75` remained latest and no `.76` publication was claimed; publication is now verified above. The installed proof remains `.75`, and physical acceptance remains unverified.

Retained merged-source validation: 1,149 tests / 1,287 subtests passed, zero failures, 206 existing warnings, 211.18 seconds; seven focused owner regressions passed and six settings-UI checks passed separately. Independent code safety review found no High/Medium blocker. The full suite is not rerun for marker/documentation-only preparation. All 16 release consistency/source-pinning checks passed in 9.43 seconds. Independent normalized comparison confirms exactly five single-marker substitutions and no other source drift. Independent release-metadata review is GO for the local candidate; these results do not authorize publication or installation.

[The .76 receipt and remaining gates](HAOS76_RELEASE_CANDIDATE.md) record publication evidence and installation/physical-verification requirements. No changed thresholds, capabilities, control ownership or workflow were bundled into release preparation. Current installed identity, archive freshness, physical acceptance and Boost acceptance remain unverified; O5 policy is unchanged.

## Historical local fix validation - 23 October 2026 (before merge)

Approved local branch `fix/fallback-standby-import-ownership` in `C:\Projects\sigenergy_optimizer-fallback-standby-import`, based on verified main `3811d6a02069e850086fab2c1e042f7b9da40bff`. Published .75 and its exact operator-supplied installed source remain unchanged. The completed local-validation checkpoint was unreleased and uncommitted; the operator subsequently authorized one commit, this branch push and a review PR. Git and the PR establish source-control identity; merge, publication and live changes remain separate.

O13 (Medium): when Standby Holdoff or active Morning Dump owned zero import and Demand Window was trusted OFF, fallback either left an existing import ceiling open during unproven settlement or restored normal import capability after successful settlement. Existing fake-HA fixtures and real post-dispatch settlement waiters reproduced a 13.25 kW permission. No physical import is established. The correction requests the 0.01 kW import close before settlement waits and retains it while either explicit owner remains active. Morning Dump is reproduced in its supported blocked-export MSC branch. Genuine High/Spike preemption clears Morning Dump ownership and keeps its existing behavior. Demand ON/unknown behavior and non-Standby economic-zero recovery are preserved; PV/ESS restrictions, authority and request-specific settlement remain independent. Two UI descriptions/labels clarify positive-FiT Low permission and summary-notification timing and status/health stale-data thresholds without changing settings or loop cadence.

Validation: tests-first runs reproduced two Standby failures and two Morning Dump failures before their respective corrections. All seven focused import-owner regressions passed (202 existing warnings, 6.97 seconds). Final combined validation passed 1,149 tests / 1,287 subtests with zero failures and 206 existing warnings in 211.18 seconds. The six settings-UI checks also passed independently. Independent combined source/test review found no High/Medium blocker. These local results do not establish physical, release or live acceptance; historical .75 results below remain separate.

Monitor-only/dry-run verification uses isolated fake-HA decision inspection to confirm active Standby or Morning Dump ownership and zero requested import, and checks the settings labels without dispatching live controls. The Value Gate dry-run flag is advisory and does not disable actuator application. Offline regression checks inject service failure and delayed/unproven observations only in fake HA. Simulation output is not actuator settlement. Any later separately supervised live verification must confirm exact installed source, effective settings, current Automated/Remote EMS authority, trusted Demand state and active Standby/Morning Dump ownership, then compare requested/observed import, export, PV MAX and ESS limits. Stop on lost authority or unexpected permission/settlement and retain operator ownership. Passing this candidate does not enable or accept unattended Boost operation.

The latest supplied archive (23 October 08:16:10 Sydney filename time) is stale: 9,325 valid records from 18 October 19:59:12 to 19 October 07:58:42 Sydney, all bytes matching the ending portion of the earlier 21 October archive; final-record age 96h17m28s. SHA-256 `72f77e9b3b7d4fa8a3559237f735f1399f7dd7f4a78f8aa51a50bacc463cc8de`. The operator reports a failing HDD, but this does not prove archive causation or current optimizer behavior.

The separate 21 October live-memory sample (267 rows, 13:28:26–13:53:10 Sydney) contains 254 helper-success, eight pending and five failed applications with unsuccessful fallback. Four failures later recovered; the last has no subsequent evidence. Zero export in a successful 13:53:00 MSC cycle balances against battery charging consuming the PV surplus, with Solcast provider UNVERIFIED. This is not a diagnosis of the failure cause or proof of current behavior. O10/O11 remain parked; Phase 1/2, Boost acceptance and O5 policy gates remain open.

## Published .75, publication proof and HA status - 21 October 2026

GitHub Release v2.3.64-haos75 was published 21 October at 02:24:59 UTC (13:24:59 Sydney): https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.64-haos75. Tag/source `413e1691bb58e0b942098ab43f44e873df157a2b`; PR #29 merged at `b88ac1f36811a253fc8602a781103a255ec932fd`, tree `07b2ab78766358c6838377796cce352a2f3ca69e`, exactly matching the tag. Actions run `39532351637` succeeded. OCI index/latest `sha256:ed2a984b457bfddb2b74050d437f98337944076e9144a8d1a19f577d8e82d898`; amd64 manifest `sha256:a242af5c9a0b40bdbdf62bc9b44e3d13c44e080d85ed11ad9661cf404835ef07`, arm64 `sha256:38e22d54b4356f613c4ab75f80b5f7fa44e8f17c5b6de7b75c515870ed271a72`. Both architecture labels and embedded source/application bytes match the version and tag source. The `.74` OCI index remains unchanged at `sha256:3f3d46ce2cef41a8246cc63db2ef794c0e1907cf2a2518acf751cdc2646399ee`.

The 16 release checks passed in 9.89 seconds. Previously completed full validation remains 1,142 tests / 1,287 subtests, zero failures, 206 warnings, 209.04 seconds; focused validation remains 90 / 103, 202 warnings, 4.73 seconds. Those suites were not rerun for the version-only release. O12 reserve-trust correction and O4 re-entry qualification are now published; O4 live stability is unverified and O5 policy remains open.

The operator reported `.74` installed, Boost off and auto-update off; supplied startup evidence at 13:28:25 Sydney identifies runtime signature `2.3.64-haos75` and source commit `413e1691bb58e0b942098ab43f44e873df157a2b`, exactly matching the published tag. Authenticated WebSocket/event-loop startup was reported. Pending-close then pending-MSC states appeared from 13:28:26 to 13:28:29, with HTTP 200 service/reads continuing through 13:28:50. This proves runtime identity and those pending states in the excerpt, not physical settlement or later recovery. It is now the latest supplied full startup/source proof; `.73` evidence is historical. Rollback method remains unprovided. Separate Browser/Node launcher attempts fail while enumerating `Z:\` (Windows error 1326), blocking direct tool access; no agent live changes or security changes were made.

The later supplied log tail `sigenergy_logs_20261021T023228Z.log` contains exactly 500 INFO HTTP 200 lines from 13:31:03 to 13:32:28 Sydney (85 seconds), with no warning/error records. It contains no observed EMS/limit or physical-flow values, so it does not prove settlement, reserve adequacy or Boost readiness. No raw log was copied into the repository.

Keep Boost off during installation checks and initial verification of exact runtime identity, effective settings, report cadence and reserve/limit assumptions. Once those facts are verified, enable it only within the already-authorized supervised acceptance trial. Switch it off and retain manual ownership immediately on a safety failure, unexpected ownership, failed settlement or renewed flapping. Unattended use follows only after successful supervised acceptance. O4 remains live-unverified; O5 policy is unchanged and open.

### Historical .74 publication and pre-.75 preparation snapshot

Latest GitHub Release: **2.3.63-haos74**, tag `v2.3.63-haos74`, source commit `31ff4872877722d6c0adcae70b445c56cc209d48`, published 20 October at 10:36:23 UTC (21:36:23 Sydney). PR #27 merged to main at `4b7c8b2b6e8a22ee01db9c44942b7c8e8ed40b28`. Actions run `39408675841` succeeded for amd64/arm64; verified OCI index `sha256:3f3d46ce2cef41a8246cc63db2ef794c0e1907cf2a2518acf751cdc2646399ee`. Independent public registry checks confirmed both architecture configs report the expected version and source revision; the .73 index remains unchanged. .74 contains the PR #26 Solar stability change.

On 21 October the operator reported `.74` installed, Evening Boost off and add-on auto-update off. A rollback method was not supplied; rollback readiness remains unverified. The last supplied HA startup/source evidence is still runtime .73 at `46d36358d38137231dff081176a372c3aa1f4cee`, with Supervisor reporting local build .71 to .73 and `BUILD_VERSION=2.3.62-haos73` on 20 October. The `.74` installation report has not been verified against exact runtime source; live acceptance is unverified.

### Historical .75 release preparation checkpoint - 21 October 2026

Current workspace: `C:\Projects\sigenergy_optimizer-release-haos75`, branch `release/2.3.64-haos75`, based on merged PR #28 at `2ea64b4aaa4da1cb61627e74e53761662df41e5e`. The approved code fix was merged as PR #28 from `3494cb2d15585107721a63871a2d3f78ebeaa81d`. The `.75` release documentation and five version markers are being prepared here; `.74` remains latest published. Full local source validation passed 1,142 tests / 1,287 subtests (zero failures, 206 warnings, 209.04 seconds); focused validation passed 90 / 103 (202 warnings, 4.73 seconds). Release-specific checks passed 16 tests in 9.89 seconds, with normalized verification confirming exactly five marker replacements. No `.75` tag, image build, publication or installation is claimed. See [HAOS75 release candidate and supervised acceptance plan](HAOS75_RELEASE_CANDIDATE.md).

The operator reported `.74` installed, Evening Boost off and auto-update off; exact installed source remains unverified because the last supplied startup proof is `.73` at `46d36358d38137231dff081176a372c3aa1f4cee`. No rollback method was supplied, and live acceptance is unverified. Keep Boost disabled until `.75` is published, installed and supervised acceptance is complete. O4 live stability and O5 reserve policy remain open.

### Historical local Evening Boost reserve-trust and re-entry checkpoint - 21 October 2026

Historical prepublication checkpoint: the worktree carried the reviewed O12 reserve-trust correction and staged O4 re-entry qualification. Both changes are now included in published .75; residual live verification remains open. The O12 correction requires existing `load_power_trusted` and `sunrise_observation_trusted` for Boost eligibility and uses both observations in reserve calculation. The standalone O12 checkpoint passed focused 41 tests / 55 subtests (202 warnings, 2.12 seconds) and a full suite of 1,112 tests / 1,247 subtests (zero failures, 206 warnings, 208.46 seconds); those counts are for that standalone checkpoint, not the combined source.

The published .75 O4 re-entry qualification requires fresh qualifying load-report timestamps spanning at least 120 seconds and at least 120 seconds of local monotonic elapsed time before initial or resumed Boost admission. These are minimums, not a guaranteed admission time. Load-report timestamps must advance monotonically, with no gap over 60 seconds. A gap over 60 seconds or local elapsed time since the last advancing report resets qualification; heartbeat cadence and report latency may defer admission indefinitely until new reports are sufficiently frequent. Cached load reports cannot mature qualification. Sunrise remains subject to its existing trusted-future-horizon check and need not advance. Wall-clock or monotonic-clock rollback, or any failed gate, resets qualification and Boost context. Closed, Qualifying and Admitted distinguish permission from physical operation; qualification is retained only after successful automatic application completion or verified MSC-pending state, not generic no-op success. Existing failure closures remain immediate; higher-priority owners and permissions are unaffected. The 27 September proposal is superseded. No separate safety hold or 5.5 kW / 50% SoC / 20% reserve redesign is approved, and O5 policy remains open.

The combined implementation is local and complete for review. Final focused combined validation passed 90 tests / 103 subtests (202 warnings, 4.73 seconds); the full suite passed 1,142 tests / 1,287 subtests, zero failures, 206 warnings, in 209.04 seconds. Coverage includes fake-HA decisions, awaited-settlement races and simulated verified-MSC-pending outcomes; these do not prove physical operation or settlement. Independent review was GO for this local candidate with no High/Medium blocker; this is not live GO. Reviewed production SHA `bd4a7a8debae41e134cb9082e3240a3dedbd742ea119a64626bc9f45e4303ce0` remained unchanged since review. On 21 October 2026, the user authorized completing this update through commit/push, normal PR/merge and release publication, followed by installation and supervised checks, subject to verified HA access, rollback readiness and other operational gates. As of this pre-commit checkpoint, the candidate remains uncommitted and .74 remains latest published; no future action is claimed complete. Publication may proceed independently of HA access, but installation readiness is unverified. Keep Boost disabled until release, installation and supervised acceptance are complete. First collect monitor-only/dry-run evidence for load-report spacing, monotonic progression, resets and immediate failure closures; local fake-HA tests are not physical proof. Supervised live acceptance requires direct comparison of requested, observed and settled limits, and explicit stop conditions. On uncertainty, failed evidence or renewed flapping, stop Boost and retain manual ownership. Before commit the safe rollback was to withhold the branch; after commit, use only a separately reviewed scoped revert, preserving other work.

### Published Solar stability change - 21 October 2026

PR #26 merged checkpoint `fa9d926a734ceefd2426000d9edb92c037ac93a6` into main as `550c8eeee8239dfb3515d3a6c4b174f35e58f139`; its merged tree exactly matches the tested candidate. Solar bridges brief dips strictly before 15 seconds after the older fresh, coherent PV/load report proving measured surplus above 0.5 kW, following successful final Solar application. Both source reports must advance to renew proof; held/cached evidence, 0.2–0.5 kW continuation and forecasts cannot renew it. Hard-gate or application failure invalidates proof immediately. Expiry requests closure under current authority; failed application retains deadline re-evaluation with bounded three-second retries. Independent limits and physical settlement requirements remain in force.

The sanitized deterministic characterization produced seven 25-to-zero kW closures at baseline; candidate ticks retain permission through those short dips with new strong measured reports. Mocked application and real ticks do not constitute a full trace replay or physical inverter proof; separate fake-actuator tests cover expiry fallback. The initial PV collapse remains unexplained. The Solar stability change is included in published .74; no .74 live behavior is verified here.

### Historical standalone O12 checkpoint - 21 October 2026

Branch `fix/evening-boost-reserve-trust` starts from published .74 merge `4b7c8b2b6e8a22ee01db9c44942b7c8e8ed40b28`. The narrow local change requires both existing `load_power_trusted` and `sunrise_observation_trusted` evidence for Evening Boost eligibility, and its reserve calculation uses both observations. No threshold, duration or operator setting changes are included.

Baseline offline read-and-decide reproduction with fake HA identified four unsafe outputs under synthetic conditions (80% SoC, 30 kWh capacity and 15¢ FiT): missing, stale or unavailable load yielded 6.6 kW; missing sunrise observation yielded 4.4 kW. A valid tests-only red run reproduced the defect with expected failures in 12 assertions (10 subcases and two top-level checks); four tests and two subtests also passed. After the correction, the initial focused run passed 41 tests / 55 subtests in 2.07 seconds, with 202 warnings. The full suite passed 1,112 tests / 1,247 subtests, zero failures, 206 warnings, in 208.46 seconds; independent safety review found no blockers. After a test-only recovery-assertion refinement, the final focused run passed 41 tests / 55 subtests, with 202 warnings, in 2.12 seconds; production code was unchanged during that refinement. No second full-suite result is claimed. The new reserve-input scenarios exercise state reading and decisions only; no live actuation or physical proof is claimed. O4 switching oscillation and O5 reserve policy remain separate and unresolved. No .74 installation or live settings change is included. The candidate can be withheld; any committed rollback requires separate approval and must revert only this guard, preserving published .74 behavior and other work.

### Historical .74 pre-publication preparation snapshot - 20 October

Candidate-specific release checks passed 16 marker/source-pinning tests in 9.05 seconds. Exact marker-only and ten-file scope checks passed, with no independent release-review blockers. Docker was unavailable locally at that checkpoint. The full control-suite result below belongs to the Solar stability checkpoint; it was not rerun for version markers.

The Solar stability checkpoint passed 1,106 tests / 1,235 subtests with zero failures and 206 warnings in 206.22 seconds; focused checks passed 115 tests / 191 subtests. Independent targeted safety review found no remaining blockers after correction of awaited-expiry and refreshed-export-readback races. Tests used fake HA, synthetic report provenance and simulated/fake actuator outcomes; they do not prove live settlement. These are retained pre-publication results, not validation of the new Boost candidate.

### Retained publication and live-proof evidence

The supplied live trace has 371 rows from 08:25:04 to 09:01:26 Sydney: 356 helper-success, 8 failed and 7 pending. Seven failed attempts show fallback -> pending -> success after 9–10 seconds. The last row reports Automated/MSC, PV export, battery charging and trusted status; eight early success rows lacked trust. These are limited application/telemetry observations, not proof of every physical limit or settlement requirement.

The 20 October archive review found an export at 08:54:07 whose tail was 19 October 07:58:42 (age 24h55m25); all 16,245 returned rows were outside the nominal 24-hour window. Fresh successful trace rows at 08:54:03 and 08:54:08 bracketed that download. The earlier 07:39 export ended at 19 October 04:20; 2,654 older rows returned byte-identically at 08:54. The observed ~44-minute cutoff offset alone is insufficient to establish clock-guard cause. Archive writer status, cause and recovery remain unproven; no archive deletion or restore is assumed.

The operator parked archive and intermittent MSC follow-up, paused the reminder, and suspects HA/hardware without proof. O10 records the confirmed stale-archive symptom; O11 records parked intermittent MSC observations. The .65 source/image exists, but its actual restore/reinstall path is unproven. A separate Supervisor backup report recorded 49 errors across 7 files and missing backup.json; this does not mean all backups are invalid. Short physical Demand Window import spikes remain deferred and are distinct from O7 exact-full PV-only proof.

Retained historical validation is not a new run: .72 full suite 1,073 tests / 1,134 subtests, zero failures, 206 warnings in 170.97 seconds; .73 focused source-pinning/release checks 16 passed; local trace characterization recorded as 56/12. These results predate .74 publication and the current local Boost candidate; no full suite, container or HA test was run for that earlier documentation update. The latest supplied runtime report does not close O1–O12 or the formal Phase 1/2 gates. For the dated fixes and scoped live-proof checklist, see [HAOS73_STATUS_AND_LIVE_PROOF.md](HAOS73_STATUS_AND_LIVE_PROOF.md).

## Live identity and rollback

Operator-supplied startup at 13:28:25 Sydney on 21 October identifies .75 / 2.3.64-haos75 at source 413e1691bb58e0b942098ab43f44e873df157a2b, exactly matching the published tag. This supports installed runtime identity, not physical settlement or supervised acceptance; direct HA tool access remains unavailable.

- Protected rollback source .65 / 2.3.54-haos65: 9965e79133f38d5b9943dcf5a9b04ed6fdab1239; public amd64/arm64 image index sha256:dd7efe0fd9b192ae1fd996137c312e5f2aab12e01a285f6e75fb5a58dc8fe88c. Public image/source availability does not prove restore/reinstall selection or rollback readiness.
- One separate Supervisor backup report recorded 49 errors across 7 files and missing backup.json; this does not establish that every backup is invalid. Saved configuration and actual .65 restore path remain unverified.
- Installation and supervised acceptance were already authorized on 21 October. Before a supervised Boost trial or any rollback, establish effective settings/current authority, report cadence, reserve/limit assumptions, supervision and explicit stop conditions. Saved configuration and an executable rollback method remain unverified; public source/images alone do not establish restore capability.

The following section and all dated sections below preserve historical checkpoints and evidence. Their dated release and identity snapshots are not current; current publication and operator-supplied status is given above.

## Published Stage B baseline and validation

- Stage B checkpoint **`ae4a974692aae1300c97845fcc32d4cfa6c2bdea`** (`ae4a974692aa`) is historical; PR #20 was merged. The published tag `v2.3.60-haos71` remains at `9f3f02a5c1c82786c85026a3848574cca3cf891f`; `main` now includes PR #21 merge `5275e9cd3803ba991351c790be6b7187c3941981`.
- Stage B implementation is **completed**, including the narrow Medium-over-Evening Boost priority correction and authority/actuator safety repair. Defects A, B and C are corrected; the supplied independent focused review passed all three corrections.
- Retained final full-suite result supplied for this checkpoint: **1,036 tests / 1,084 subtests, zero failures**. Compileall and `git diff --check` passed. The full suite is not rerun for version-only preparation; release consistency, compileall with an external cache, diff and exact-scope checks are the preparation gate.
- **No supervised live acceptance yet. Stage B remains NO-GO for deployment.** Automated validation and independent code review do not prove inverter settlement or physical flow.

### Completed safety corrections

- **A - Contradictory actuator evidence:** conflicting actuator observations cannot prove settlement. Deliberate discharge requires the intended export target, with fresh provenance-bearing evidence strictly after its own dispatch boundary; a smaller value sufficient for a safety close is not proof of a deliberate discharge target.
- **B - Independent ESS restrictions:** successful fallback cannot restore ESS charge/discharge capability above independently owned restrictions. Solar relinquishment restores only the otherwise safe normal charge request; Demand Window import blocking and independent PV restrictions remain effective.
- **C - Pending Force ownership:** unchanged Automated selector reports prove freshness, not a new operator selection. A pending authenticated Force request yields to a verified selector state transition strictly after its request, with coherent change/update/report timestamps; supersession stops subsequent writes/retries.

Current Automated ownership and observed Remote EMS ON remain required at application/dispatch boundaries. Unknown evidence fails closed; independent restrictive writes remain available while unrelated permissive recovery waits for observed settlement. Preserve ordinary unattended restart/auto-enable after current Automated verification and observed Remote EMS ON, authenticated Manual/Force and `/set_ess`; no persistent OFF registry or mandatory restart handback redesign.

### Protected reference and historical Stage A evidence

- Stage A tests-only characterization was independently accepted on 15 October: 25 passed, 47 deliberately red baseline regressions; corrected D7 passed; independent protections 77 tests/89 subtests passed, zero unexpected failures. These are historical baseline results, not current Stage B failures. Preserve the regression assertions.
- Protected reference: `C:\Projects\sigenergy_optimizer-evening-priority`, branch `test/evening-medium-priority-characterization`, base `08f4daf...`, ten intentionally dirty files. Never reset, stash, discard, overwrite, commit, delete or wholesale-copy its optimizer. This checkpoint does not touch it or the Stage A worktree.

## Outstanding operational bug register

The register distinguishes published code corrections from remaining engineering, operator-policy and physical-evidence gates. O14, O16 and O10 clock recovery shipped in .77; their original worktrees remain preserved. O15 and O17 shipped in .78 after combined validation and independent source/test/documentation review GO. The narrow O2/O6 stabilization corrections shipped in .79; their physical acceptance and adjacent policy questions remain open. Their standalone results and evidence limits remain recorded separately below. Publication and image/source identity are verified; installation, exposure and physical acceptance remain unverified. O1, O3 and O6 retain the listed live acceptance or adjacent-behavior questions despite their earlier narrow corrections. O11 remains parked; historical HDD, archive and MSC causation is not established.

| ID | Issue | Classification and outstanding disposition |
| --- | --- | --- |
| O1 | Medium versus Evening Boost | Narrow priority defect corrected in published .71. Supervised live acceptance remains outstanding; broader Boost stability is O4. |
| O2 | Unexpected export interruptions/cycling | PR #60 normally merged the approved fill-progress floor/completed-total rebase into main; source validation passed 1,632 tests / 1,606 subtests. It is included in the unpublished .85 candidate; physical acceptance remains open. The 25 October trace confirms 53 Solar-to-normal exits and 52 returns after Morning Slow is last observed; 47 exits fail the load-sensitive aggregate budget. Source PR #40, published in .79, qualifies Solar reacquisition after a strict budget exit, with immediate failure closure. Unsafe battery flow, independent winners and closed capability cannot donate qualification time. First admission and existing priorities remain unchanged. Full validation and independent peer review pass; physical acceptance remains open. Exact installed source, sensor causes and lost energy remain unproven. See the publication receipt and `SOLAR_REENTRY_STABILITY.md`. |
| O3 | Solar Override | Selected/protected-floor bypass corrected in merged PR #21 and published .72, preserving separately qualified PV-only MSC. Historical physical reports and supervised live acceptance remain unresolved; related 27 September threshold-switching evidence is retained in ROADMAP.md section 3. |
| O4 | Evening Boost oscillation and re-entry | Observed unstable switching and SoC requirements remain open. Published .75 requires fresh qualifying load-report timestamps spanning at least 120 seconds and at least 120 seconds of local monotonic elapsed time, monotonic report timestamps and no load-report gap over 60 seconds. Sunrise uses its existing trusted-future-horizon check and need not advance. Cached load reports cannot mature qualification; a gap over 60 seconds, wall-clock or monotonic-clock rollback, or failed gate resets qualification and Boost context. Closed / Qualifying / Admitted distinguishes permission from physical operation; successful automatic application completion or verified MSC-pending state is required to retain qualification, and generic no-op success is insufficient. Existing failure closures remain immediate; higher-priority owners and permissions are unaffected. This is not live acceptance or proof of settlement. Supervised live stability and settlement remain unverified; the qualification gate does not redesign overnight reserve policy (O5). The 27 September proposal is superseded. Retained Phase 1 follow-up: ROADMAP.md sections 3-4. |
| O5 | Overnight battery reserve | PR #60 merged passive required-energy/full-capacity-shortfall explanations, included in the unpublished .85 candidate; the existing load model and reserve/price policy remain unchanged. Operator-policy decision pending: Medium/High thresholds, tomorrow-PV awareness and enough battery until solar takes over. Proposed 30-cent tuning is not approved; no threshold changes authorised. The 25 October trace also exposes a calculated 113% overnight export floor. This is a planning-derived requirement, not a command to charge above 100%; review its load extrapolation and diagnostic wording with O9. O18 separately tracks daytime fill-strategy robustness. |
| O6 | Morning Dump / Morning Slow | Published .83 bounded Morning partial relief and .84 charge-readback metadata remain included. PR #60 preserves Morning priority/handoff qualification while updating Solar cap expectations to the approved fill-progress policy; unpublished .85 and physical stability remain separate. The merged Dump discharge guard and explicit MSC fallback shipped in .72. Floor cycling and other depletion reports remain open. The 25 October six-second Morning Slow/Solar charge alternation is reproduced. Source PR #40, published in .79, qualifies only restrictive Solar charging after completed genuinely owned relieved Morning operation at its normal bound. The historical .79 eight-row fixture retains 25 kW export permission and commands 0 followed by seven 21 kW requests, preserving raw Morning priority and genuine slow charging. Full validation and independent peer review pass; physical acceptance remains open. Exact settings and sensor cause remain unproven. See `SOLAR_REENTRY_STABILITY.md`. |
| O7 | Demand Window at exact-full SoC | Live-acceptance requirement: prove PV-only surplus export without deliberate battery export or grid import. Retain hotfix evidence below and ROADMAP.md section 4B; automated tests do not prove physical outcome. |
| O8 | Historical 13-second transition observation gap | Remains unresolved and cannot be reconstructed from later records. The trace component records pending/error application outcomes but cannot recover missing historical records or prove physical settlement. Scoped .68 acceptance cannot fill the gap or establish unexercised cases; see ROADMAP.md section 4. |
| O9 | Obsolete, overlapping or misleading policies/settings | PR #60 merged the approved passive reserve wording correction; the broader ownership/settings audit remains queued. Queued short control-ownership/configuration audit, including Solar Override and configuration ownership. Include the 25 October overnight reserve message above 100%: distinguish raw planning need, export permission and actual charging targets. No removal, redesign, reserve-policy change or broad audit is authorized by this documentation intake. See ROADMAP.md section 5. |
| O10 | Stale trace archive and clock recovery | The 20 October downloads were demonstrably stale/inconsistent, but snapshot identity, cause and HDD involvement remain unverified. The operator parked the original archive/MSC incident investigation. O10 clock recovery is corrected in published .77 (source `7aa712f72ca2c0467e6740e3cb0f2191ba8d077e`): dual fixed-HTTPS time corroboration and immutable atomic snapshot of old segments/status before normal active-window pruning. Implemented and independently reviewed; combined offline validation passed 1,275 tests / 1,305 subtests. Failure retains evidence and keeps the guard closed. No historical cause is established. |
| O11 | Intermittent MSC observations | PR #60 merged the reproduced MSC request-epoch/waiting-log correction; it is included in the unpublished .85 candidate with source validation passing. It does not establish every historical observation failure or reopen unrelated parked causation. Operator parked follow-up and paused the reminder. Supplied observations do not establish whether HA, hardware, application or evidence timing caused the behavior. The 25 October afternoon adds six isolated normal-charge application failures, each followed by helper success in 9–10 seconds; that does not identify the cause or prove physical settlement. This evidence does not reopen the parked investigation or establish a fix. |
| O12 | Evening Boost reserve-trust provenance | Code defect corrected in published .75: Boost now requires existing trusted load and sunrise observations before using them in the overnight reserve calculation. The standalone regression checkpoint passed 41 tests / 55 subtests and 1,112 full-suite tests / 1,247 subtests. The combined .75 control checkpoint passed 1,142 tests / 1,287 subtests; 16 release/source-pinning checks also passed. Operator-supplied startup at 13:28:25 Sydney identifies .75 at exact tag source 413e1691bb58e0b942098ab43f44e873df157a2b. Publication and installed identity are established; physical acceptance remains unverified. O12 itself changes no prices, SoC/power thresholds or durations; O4 adds the separate qualification timing, and O5 reserve policy remains open. |
| O13 | Standby/Morning Dump fallback grid-import ownership | Reproduced in .75 with trusted Demand OFF: fallback omitted either active owner's import close before settlement and could restore normal import capability afterward. Corrected in fix commit `bcfdb75b33c8ae1db3c7f534cb8952f144d9c3cd`, normally merged by PR #31 at `632a42081d9ff93b270ffcca048604031ec4fed1` and published in .76 source `e70d9ff016a546615367b6d69f4ac4602da7b23c`. Seven focused regressions and the full 1,149-test / 1,287-subtest suite pass, with no High/Medium blocker in independent review. Code is published; physical behavior remains unverified. Ordinary economic-zero recovery and genuine Morning preemption are preserved. |
| O14 | Configuration activation across awaited control operations | Medium; reproduced offline on unchanged .76 source. The correction is published in .77 from reviewed PR #34 and uses the existing lock, rechecks queued authority, and retires identity-bound evidence. O14/O16 integration hardening also covers configuration A→B→A activation and direct-control boundaries that can otherwise lose accounting ownership; all 15 boundary tests and the 1,275-test / 1,305-subtest combined suite pass, with independent review GO. No physical behavior or historical-incident cause is established. |
| O15 | Synchronous storage on async control/API paths | Medium; reproduced offline with synthetic lock contention. The O15 correction is published in .78 from source PR #37 and isolates runtime database execution on one bounded worker while retaining event-loop-owned accounting, exact retries and unknown-cost safeguards. On-disk combined validation passed 1,355 tests / 1,305 subtests; focused checks passed 126 / 8. Independent source/test/documentation review is GO, with no High/Medium blocker. Publication and exact image/source identity are verified; installation, physical acceptance and historical HDD/trace/MSC causation remain unverified. See STORAGE_EXECUTION_ISOLATION.md. |
| O16 | Import-top-up ledger completeness and retry integrity | Medium; reproduced with synthetic store failures, without proof of physical dispatch or financial loss. The O16 correction is published in .77 from reviewed PR #34, preserving original interval evidence and exact retry while retaining unknown-coverage safeguards. Integration review added targeted accounting-only invalidation at relevant identity activation and validated direct Manual/ESS boundaries, including permission invalidation across midnight. Fifteen new boundary tests passed; a bounded 114-test / 101-subtest run passed before the last two midnight tests were added. Final .77 validation passed 1,275 tests / 1,305 subtests, zero failures, 206 existing warnings, 226.40 seconds; independent review was GO. O15 storage execution isolation is now integrated and published in .78; it retains the O16 accounting safeguards. HDD causation and physical acceptance remain unproven. |
| O17 | Ingress trust and optional API-key bypass | Conditional authentication defect reproduced offline. The O17 correction is published in .78 from source PR #37 and requires actual Supervisor peer 172.30.32.2 plus X-Ingress-Path and disables proxy rewriting in both supported launchers. Combined validation passed 1,355 tests / 1,305 subtests; independent source/test/documentation review is GO, with no High/Medium blocker. Normal HA login, existing flags and public read-only/status policies remain separate. Actual installed exposure is unverified; no exploit or physical acceptance is claimed. See INGRESS_TRUST_BOUNDARY.md. |
| O18 | Solar charging deferral and fill-strategy robustness | Operator chose fill progress on 28 October; PR #60 normally merged the reviewed policy into main for the unpublished .85 candidate. Dynamic protected-fill-energy/time-to-existing-deadline allowance, higher urgent need and trusted normal capability replace forecast-only zero deferral under valid authority; no guaranteed actual charging/full SoC. Local combined full validation passed; live acceptance remains open. Historical evidence: On 25 October, the morning-started session peaks at 73.3% SoC, is 69.6% at the 16:29:52 configured fill deadline, and ends at 65.8%. Normal charging consistently requests 21 kW after 13:09:53; Forecast Today is revised 79.325 to 66.6231 kWh at 14:08:27. Earlier zero requests followed the then-current future-opportunity calculation, but the fill objective was missed. Characterize forecast downgrades and assess the reliability/export/minimum-charge tradeoff; do not claim bypass caused the entire shortfall or infer exact forgone energy from sampled flows. The approved local policy retains existing safety and authority gates; its implementation does not establish the historical shortfall cause. See the 25 October evidence above. |

| O19 | Fallback Demand Window import race | Published in .82 via PR #49. Recheck current Demand in the final authority/settlement read: trusted OFF is required to reopen fallback import; ON or untrusted evidence requests the existing 0.01 kW close. Physical acceptance and transient-import evidence remain open. See CONTROL_LIFECYCLE_REVIEW.md and HAOS82_RELEASE_CANDIDATE.md. |
| O20 | Negative-price Morning Dump output conflict | Existing characterization records conflicting export intent/EMS and restricted ESS/PV outputs. The future non-positive-price Morning priority redesign remains parked; no production change is authorized. See `CONTROL_LIFECYCLE_REVIEW.md`. |
| O21 | Incomplete ESS discharge recovery after failed battery export | **Published in .82; physical acceptance open.** Restore bounded MSC house-serving discharge after current authority and fresh closure/MSC proof; ordinary export-target checks remain. Primary failure stays failed even when fallback succeeds. Full suite: 1,504 tests / 1,439 subtests, zero failures. Independent local review GO; physical acceptance remains open. See CONTROL_LIFECYCLE_REVIEW.md. |

### Historical O14 tests-only baseline characterization - 24 October 2026

At that baseline checkpoint, workspace `C:\Projects\sigenergy_optimizer-config-authority-race`, branch `test/config-activation-authority-race`, was based on main `e387010b83f7b017460870b1b456025f49f7e0a5`. Its production content was byte-identical to published .76 source `e70d9ff016a546615367b6d69f4ac4602da7b23c`; only the two carried-forward backlog/handover docs and new `tests/test_config_activation_authority_race.py` differed from main. The original uncommitted audit docs in `C:\Projects\sigenergy_optimizer-release-haos76` / `docs/audit-findings-20261024` remain byte-identical and protected. That tests-only checkpoint had no production fix, commit, push, publication or live action.

The fixture uses real FastAPI routes, real API-key checks with synthetic credentials and an in-process ASGI transport, real shared settings and `_apply`, the real control lock, independently supplied fake-HA reports and recorded command calls. Events suspend the second authority read inside the pre-EMS dispatch guard after initial authority succeeds. Complete single/batch settings activation occurs before valid old Automated/ON evidence resumes. Five cases reproduce the forbidden Grid First call: single selector to Manual, batch selector to Force, single switch to OFF, batch switch to OFF, and a batch replacing selector/switch/EMS together. Every case records activation during the await; the combined batch sends to the new EMS entity. This establishes an offline dispatch/authority-contract violation, not partial per-key batch interleaving or physical charging. The application subsequently reports failure/authority loss; that does not retract the command already issued to the double.

Focused module result: **5 deliberate baseline failures, 7 passed, 202 warnings, 2.17 seconds**. Controls cover unchanged identity through both routes, wrong API keys through both routes, preactivated Manual/Force, and fresh replacement Automated/ON recovery. The bounded combined run of the new module plus API validation, control-authority safety and Phase 1 fail-closed characterization returned **5 deliberate baseline failures, 154 passed, 92 subtests passed, 203 warnings, 31.06 seconds**. All five failures are the same new regression assertion; no unexpected existing regression failed. No full suite was run. Independent read-only test review was GO for the characterization and did not rerun the tests.

The safety assertions accept either future deferred activation after a control transaction or current-identity revalidation that closes permission. They inspect raw old/new EMS command records after the successful response. That activation marker is conservative: it could miss an earlier command, but cannot manufacture the reported failures because baseline activation completed while the authority await was held.

At this baseline checkpoint, the proposed local branch `fix/config-activation-transactions` was pending specific approval. The later combined-release approval and integration are recorded at the top of this document; this baseline is not validation of the integrated correction. The baseline reproduction does not validate the correction. The proposal was to serialize validated configuration activation/persistence under the existing control transaction lock, revalidate final settings, and examine evidence invalidation for replaced identities. Preserve Manual/Force priority, current Automated/Remote ON requirements, restart auto-enable, independent restrictions and request-specific settlement; avoid nested lock acquisition. No new restart requirement, client rebuild, threshold or live behavior change is adopted. O16 now has its own separate local candidate; O15/O17 remain queued, and Phase 1/2 live gates, O5 and parked O10/O11 remain unchanged.

### Independent audit intake - 24 October 2026

The operator requested discussion and backlog recording of a supplied read-only audit. Its recommendations were review input, not implementation or live-action instructions. Audited tag/source: `v2.3.65-haos76` / `e70d9ff016a546615367b6d69f4ac4602da7b23c`; main when audited and rechecked for the intake: `e387010b83f7b017460870b1b456025f49f7e0a5`. Main differs from the tag only in the completed publication receipt. At that original intake checkpoint, targeted exact-commit source checks supported the mechanisms below; no dynamic tests, builds or live probes were run. Subsequent O14 and O16 synthetic reproductions and their local candidates are recorded above. O15/O17 retain their static/conditional limits. No introduction date, .76 regression or physical effect is established.

Exact-source evidence and future validation scope:

- **O14:** `app/routers/api.py:1462,1494-1504,1610,1676-1677`; `app/optimizer.py:2331-2354,6745-6756,6881-6900`; current-authority contract `docs/CONTROL_CONTRACT.md:382-388`. At intake, the future test proposal was to suspend an authority read, change configured identities through authenticated routes, then resume with old valid evidence. The later O14 tests-only characterization and current local candidate above supersede that proposal. The handlers have no await within their mutation batch; the reproduced concern crosses another operation's await, not partial per-key batch interleaving.
- **O15:** `app/state_store.py:14-20,40-47,119-128,181-247`; async query `app/routers/api.py:1129-1134`. Slow/locked-storage effects remain unmeasured; preserve error visibility and protections in any separate bounded storage-execution proposal. O15 synchronous storage handling has not been implemented by the O16 branch.
- **O16:** `app/state_store.py:119-128,181-247`; `app/optimizer.py:1434-1480,1816-1839,1870-1895,4230-4237,8555-8558`. These references identify the source paths examined at intake; synthetic insert, commit/acknowledgement, replay and unknown-coverage failures are now characterized in the local O16 checkpoint above. See [O16 design and validation scope](IMPORT_LEDGER_INTEGRITY.md). Current candidate validation is recorded above; the baseline reproduction remains historical evidence and does not establish live behavior.
- **O10 diagnostics, parked:** `app/decision_trace_store.py:359-378,388-392,436-469,693-759`; `app/routers/api.py:1108-1126`. Expose persistence degradation before considering recovery. Preserve retained evidence and clock guard; no archive/status deletion or automatic time re-anchoring is proposed. No clock, hardware or optimizer causation for the observed stale archives is established; O11 remains separately parked.
- **O17:** `app/routers/api.py:332-363`; permissive defaults `app/config.py:18-19`. Later characterization should use synthetic remote clients and strict/permissive settings; actual exposure requires sanitized deployment evidence. No additional login, API-key mandate or enterprise infrastructure is adopted for this personal HA/Nabu Casa installation.

At the original intake checkpoint, proposed triage order was O14 configuration activation, O16 ledger integrity, then O15 storage execution; archive diagnostics/investigation remained parked. Later, O10 clock-recovery engineering was reopened in the approved combined candidate. The operator reported .76 installed after replacement-SSD restoration on 24 October; the latest supplied full startup/source proof remains .75. This report does not prove current runtime identity or physical acceptance. O15 remains queued; escalate O17 if direct exposure is established. Applicable Phase 1/2 live-proof gates, O9/ROADMAP ordering and O5 policy remain unchanged. The original archive/MSC investigation stays parked; no HDD causation is inferred. See the current combined checkpoint above. The original intake statements about approval and installation describe that earlier point in time.

### Supplied 20 October startup and trace/archive evidence

- Startup report: runtime .73, source 46d36358d38137231dff081176a372c3aa1f4cee; Supervisor local build .71 to .73, BUILD_VERSION=2.3.62-haos73, final start 06:53:23 Sydney. This is operator-supplied evidence, not direct reviewer HA access.
- The 371-row live sample spans 08:25:04–09:01:26 Sydney: 356 helper-success, 8 failed, 7 pending. Seven failed attempts show fallback -> pending -> success after 9–10 seconds. Eight early succeeded rows lacked trust. The last row reports Automated/MSC, PV export, battery charging and trusted status; these observations do not establish all physical limits or settlement.
- The 08:54:07 archive export ended at 19 October 07:58:42 Sydney (age 24h55m25); all 16,245 rows were outside the nominal 24-hour interval. Fresh successful rows at 08:54:03 and 08:54:08 bracketed the download. The earlier 07:39 export ended 19 October 04:20; 2,654 older records were returned byte-identically at 08:54. Across the same UTC hour, the exports contained 275 versus 817 rows, so 542 later same-hour rows were absent from the earlier export. The archive/index identity at the two requests is unverified; cause remains unresolved.
- The operator parked archive and MSC follow-up, paused the reminder, and suspects HA/hardware without proof. No archive deletion or restore is assumed. One separate Supervisor backup report recorded 49 errors across 7 files and missing backup.json; this does not establish all backups invalid. The .65 public source/image is available, but actual restore/reinstall selection remains unproven.
- Short physical Demand Window import spikes remain operator-deferred, not a confirmed bug, and separate from O7 exact-full PV-only export proof.

### Historical 17–18 October trace audit and operator disposition

- Source: `sigenergy_decision_trace_24h_20261017T215448Z.jsonl`, 17,340 valid records from 17 October 08:54:51 to 18 October 08:50:57 Australia/Sydney; SHA-256 `ccaa643684d4e2c2620aba22faba99bb22f81dc3df99015bd44b5ac7fc7b196f`. No raw trace is copied here.
- The operator deferred short physical import spikes associated with sudden changes/physics: not a confirmed Demand Window bug, no setting change. This is distinct from O7 exact-full PV-only export proof, which remains open. Four short floor-chatter pulses at 15/15.1% matched the configured 15% floor without breach. The stable-FiT 12:22 example follows the load-sensitive energy-budget gate; the 92 charge-owner transitions have not all been individually classified or resolved. See `CYCLING_AUDIT_2026-10-18.md`.
- 38 Morning Dump blocked-export/discharge-EMS records occurred between 07:10:51 and 07:13:34. The supplied file's 526s and 33s gaps do not resolve the historical 13-second O8 gap. EMS/import/export readbacks were present; build identity and observed ESS limits were absent. The P3 positive-FiT reason mismatch is diagnostic, not established as a control-path defect.
- The trace did not exercise Solar Override, Evening Boost, Medium-or-higher tiers, negative prices or actual-import-cost vetoes. All four changes are merged in PR #21; original Solar Override, Morning Dump and trace worktrees remain intact.

## Historical .70 release-preparation validation (2026-10-13)
The following is retained test evidence from before the operator-reported .70 installation, not a current release-preparation status.

- Exact-marker extraction asserted all five values equal `2.3.59-haos70`; existing release consistency checks passed: `python -m pytest -q -p no:cacheprovider tests/test_release_version_consistency.py` (**2 passed**).
- Demand Window regression and independent protections passed: **356 tests / 468 subtests**, zero failures, **203 Pydantic deprecation warnings**. Command: `python -m pytest -q -p no:cacheprovider tests/test_msc_baseline_overlay_contract.py tests/test_demand_window_pv_max.py tests/test_phase1_actuator_settlement_fallback_characterization.py tests/test_phase1_authority_fail_closed_characterization.py tests/test_four_tier_battery_export.py tests/test_export_value_gate_advisory.py tests/test_phase1_capability_model_characterization.py tests/test_phase1_battery_telemetry_trust_characterization.py tests/test_solar_surplus_redesign.py tests/test_phase1_morning_slow_relief_characterization.py`. This includes exact-full ON/OFF/untrusted, Manual/Force, observed settlement, actual import-cost, four-tier ownership, telemetry/capability, Morning and Solar protections.
- Final pre-checkpoint full suite run once: `python -m pytest -q -p no:cacheprovider --disable-warnings` -> **946 tests / 1,079 subtests passed**, zero failures, **206 Pydantic deprecation warnings**, in 128.42 seconds. Warning display was shortened; warning counts and test selection were unchanged.
- `python -m compileall -q app tests` passed with `PYTHONPYCACHEPREFIX` pointing to a unique external temporary cache. `git diff --check` passed. Complete diff review and exact ten-file scope checks passed; all changes remain local and unstaged, with no untracked files. No test, control logic, source-clone or workflow changes were needed.
- Test runs use `PYTHONDONTWRITEBYTECODE=1` and disable pytest's cache provider to keep generated files out of the worktree.
- Production-content comparison against published hotfix `67fae5db2451fbf3e706b10cf4e2dbad07b38bd9` passed after normalizing Git LF/checkout CRLF: exactly the FastAPI version and `_RUNTIME_SIGNATURE` substitutions. The initial raw-byte comparison encountered checkout line endings; this was a verification-method correction, with no source change or test failure. Tests, control contract, Dockerfile and workflow match the published hotfix.

## Demand Window / exact-full PV-only hotfix

The confirmed defect affected an otherwise qualifying exact-100%-SoC, cheap-positive-FiT MSC PV-only opportunity: Demand Window OFF and untrusted received the configured high MSC surplus ceiling, but trusted ON returned `0 kW` and `EXPORT_BLOCKED`. ON and untrusted correctly blocked import.

The narrow correction removes only `and not trusted_demand_window_active` from `pv_only_msc_transition_ready`. Qualified ON now receives the same configured, capability-bounded `MSC_SURPLUS_CEILING`; import remains blocked. OFF and untrusted behaviour is preserved. The transferred 49-line characterization test is the only test addition; existing expectations are unchanged.

Exact-full qualification, observed Automated/exact MSC authority, trusted safe flow evidence, actuator settlement and physical bounds remain mandatory. Below-100% cheap-FiT protection remains intact. The change creates no `BATTERY_EXPORT` owner or discharge EMS and leaves Morning, Solar Surplus, ordinary export, Manual/Force and actual import-cost protections unchanged. Settlement/application helpers and capability helpers are unchanged. Automated decision/test evidence is not proof of physical export or live settlement.

## Original .69 audit remediation (historical context)

The historical independent ChatGPT GitHub code audit reported GO for corrected checkpoint `bec1095539b96dbb90b62bd6eb047471e41801f6`, resolving both original blockers. That review does not cover the new Demand Window delta:

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
- **Four-tier live acceptance is outstanding.** The completed code-audit GO does not establish safe physical behavior or complete physical/live acceptance.
- Further Evening Boost redesign, trusted non-positive-import redesign, Package 6B, experimental scheduling and later architecture/cleanup/GUI/Climate work remain parked under the roadmap; this package does not authorize them.

## Site tuning is not a software default
- Reported physical grid-connection export cap: **15 kW**; previously reported normal permission/PV MAX **25 kW**, Morning Slow near **2 kW**, Morning Dump SoC minimum **15%**, timing setting **1.0 hour** and Evening Boost **disabled**.
- Previously reported `solar_surplus_fill_deadline_margin_minutes=120` and Morning Slow physical export headroom 0.0 remain historical reports, not rechecked effective settings. Do not infer other effective settings from source defaults or change defaults to match site tuning.
- The physical inverter grid-export maximum is reportedly configured to **15 kW**, not freshly verified here. Legacy Force targets remain unchanged, including **25 kW**. Physical grid-export enforcement and ESS limits are separate controls; do not infer live enforcement from software targets or tests.
- No HA settings or inverter controls are written by this checkpoint.
## Historical .72 release-preparation snapshot (18 October; superseded by current status above)

This section records the 18 October pre-publication preparation state and is retained for history. Its candidate-unpublished and no-tag/no-build statements describe that checkpoint only; current publication and source-pinning status is stated at the top of this document.

Current release-preparation worktree: `C:\Projects\sigenergy_optimizer-release-haos72`, branch `release/2.3.61-haos72`, based on merge `5275e9cd3803ba991351c790be6b7187c3941981`. The four merged changes are: Solar Override deliberate battery-backed export requires SoC strictly above selected and protected floors while preserving separate qualified PV-only MSC; early Morning Dump discharge EMS requires qualified `BATTERY_EXPORT` intent and positive bounded target, with explicit MSC fallback for blocked active Dump while preserving priority; application outcomes/exceptions are recorded without changing outcomes or actuator ordering; and positive FiT below 1¢ is described as below-minimum with precision near 1¢. Existing settings, thresholds and unrelated policies remain unchanged; this local preparation updates only the five established version markers and authorized documentation. Original component worktrees are preserved. [PR #21](https://github.com/Belot77/sigenergy-optimizer/pull/21) merged reviewed PR head `38f59fb9ad9b88652996be27a72dabbd1f8cc424` into `main` at merge `5275e9cd3803ba991351c790be6b7187c3941981`; code commit `4e4b17c2d3bb362716d6b4e5ddb60659faf7beec` is unchanged.

The earlier 1,070-test / 1,124-subtest combined pass predates the reproduced defect and is historical. After the approved correction, focused decision/floor checks passed 11 tests / 26 subtests (202 warnings, 1.16 seconds); independent Demand Window, Manual/Force, settlement and fallback checks passed 13 tests / 15 subtests (202 warnings, 4.79 seconds). Final combined offline validation passed **1,073 tests / 1,134 subtests, zero failures**, with 206 warnings in 170.97 seconds. Current `compileall app tests` passed using an isolated temporary cache. Pytest used `-q -p no:cacheprovider --disable-warnings --tb=short` with `PYTHONDONTWRITEBYTECODE=1` and `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`. These are offline results, not installation or physical-settlement proof. The code commit, branch push and PR merge are complete. Candidate `.72` local release validation passed; its documentation/marker commit remains pending; tagging, building, publication, installation and live acceptance are separate gates.

The new fallback deliberately suppresses lower-priority EMS selection only while active Dump already blocks import. Qualified Dump keeps discharge priority; inactive-Dump behavior and authority/settlement remain unchanged. If this additional change regresses, revert only its early-Dump fallback delta, preserving the other reviewed fixes and all original worktrees. Original integration risks remain Solar floor closure, discharge intent gating, diagnostic retention/interpretation and reason wording. Beyond the four approved corrections, the merged code changes no settings, entities or API behavior. Local release preparation changes only the five established version markers and documentation; no HA state or inverter controls changed.

The code commit, branch push and PR merge were separately approved and completed. This local `.72` preparation does not authorize tagging, building, release, deployment, installation or live actions. Any separately approved live acceptance must verify exact source/build, effective settings, observed authority, both Solar Override floors, Morning Dump floor, requested and observed EMS/import/export/ESS limits, physical flows, supervision, `.65` rollback readiness and stop/rollback conditions. Stage B remains **NO-GO for deployment**.

The approved roadmap order remains authoritative, including architecture, project cleanup and full GUI/UX work before Climate Manager integration. Climate Manager broadly works and is not the current priority. Before later authorised live work, verify effective settings/current authority and capture timestamped EMS, PV MAX, import/export ceilings, ESS limits, SoC, battery/PV/grid flows and reason/owner with explicit stop/rollback conditions.
