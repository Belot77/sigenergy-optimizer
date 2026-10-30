# SigEnergy Optimizer for Home Assistant OS

## Unreleased local integration candidate - combined dawn recovery

`fix/dawn-recovery-integration` is an approved local candidate based on `main` `8f41377`; it combines three isolated fixes for separate symptoms in the supplied .87 trace. It is unpublished and is not installed. Morning Dump now retains a process-local stop for the same morning window after a completed automatic export loses trusted timed refill feasibility; a later morning can qualify again in the same process, while a restart loses the latch and requires a fresh decision to pass all current gates even within the same morning. Fewer same-window export opportunities are deliberate. Provider recovery separates temporary sun/sunset metadata uncertainty from rejection of a provider generation; restoration requires unchanged, fully revalidated prior evidence from the same source/session before its retained deadline. MSC recovery adds only the `accepted_primary_msc_opening_unobserved` origin when the accepted restrictive fallback also lacks proof, using the existing bounded 15-second recovery and correlated close/MSC proof.

The existing 15% Dump floor, 80% Boost target, independent owners, provider source/session/deadline checks, and Manual/Force and authority protections remain. Component results are recorded in docs/AI_HANDOVER.md. The guarded combined full suite passed 1,716 tests / 1,725 subtests with zero failures. Independent source/safety, test-coverage and final documentation/scope reviews are GO. The installed .87 identity is unchanged. No version or live settings change is included.

## Current published release: 2.3.76-haos87 - 30 October 2026

Published at 2026-10-29T22:49:07Z (30 October 09:49:07 AEDT): [GitHub release](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.76-haos87). Metadata [PR #68](https://github.com/Belot77/sigenergy-optimizer/pull/68) merged normally at `77be45d70b665283a49ce249111f1fa6c6732c69` at 22:48:37Z, with parents `4ebdb82daf8a3c41efbab1f12366f413e382fbb2` and `6a43077be1a59512bf44b1bb1c41aed410992c37`; merge tree `de893cf6a0bae925025d22eb0099b5b6beb00b8f`. Annotated tag object `9a3ff193b8a79791a3eb333f75463365e939a9ba` resolves `v2.3.76-haos87` to source `6a43077be1a59512bf44b1bb1c41aed410992c37` and that tree.

Build [40968005213](https://github.com/Belot77/sigenergy-optimizer/actions/runs/40968005213) succeeded for the exact source. Version/latest OCI index: `sha256:b0e703483652a3b5ead7a1eb968f10dee2571c9d613f6d72e29a210c01d790f6`. The amd64 manifest is `sha256:9fb2e71617d7e943fd64aff45dbe011fb18c1642022dd8e25dbb539aa6e11051`; arm64 is `sha256:2e36eabf2820d78eabeff254fcdcd61ae8e680375c8b55a3adb041aa4e7d95fa`. Each platform passed 11 layer/diff-ID checks and 15 expected source byte/mode checks. Source fingerprint: `sha256:a80c8d7e425ec222b03ff731f0e9c50f810440f43776b96aa22131b163b999f2`. The author verified layer bodies; the independent verifier confirmed registry metadata and expected source, but did not redownload all compressed layer bodies. Offline OCI verification passed 73 synthetic cases. Post-publication tag, source, normal-merge, version/latest and previous-index checks are GO. Previous immutable .86 index `sha256:68ae9242488169b25525c53ef106eae92197a3f398aa3210344a43c6601b9359` remains unchanged.

The source includes PR #66 provider-payload/daylight separation and PR #67 bounded recovery for the two accepted restrictive-settlement origins. Retained source validation: guarded full suite 1,676 tests / 1,672 subtests, zero failures; focused five-module run 86 / 136; independent safety run 11 / 28. Release version/source-pinning checks passed 16 tests, six runtime modules passed 96 / 141, and the offline verifier passed 73 cases.

The supplied 30 October 12:54:06 AEDT startup confirms installed runtime `2.3.76-haos87` and source `6a43077be1a59512bf44b1bb1c41aed410992c37`. The 31 October trace identifies the same runtime through 08:39:26 AEDT. Auto-update was last confirmed off on 29 October. Physical acceptance remains partial. The combined candidate is local and unpublished; it has not been installed and no live settings were changed.

Installed .87 runtime/source identity is confirmed above. Outstanding supplied evidence is provider recovery after the next scheduled update, the Morning-to-Solar charge/export handoff and deadline behavior, request-correlated MSC/close recovery, and Boost qualification on an eligible forecast day under its unchanged 120-second rule. The new provider and MSC recovery paths are not established by the supplied trace. Report shipped changes, remaining engineering/policy work, missing live proof and the next authorized action at each publication.

## Historical pre-merge checkpoint - Solar provider daylight validation - merged by PR #66 - 30 October 2026

Branch `fix/solar-provider-daylight-validation` at
`C:/Projects/sigenergy_optimizer-provider-daylight` is based on verified main
`5f32ec510c6314aed91587c5efb957442fdd0046`. The narrow correction separates
provider-payload validation from Solar daylight ownership. A coherent pre-sunrise
provider generation may establish a baseline and a later genuine advance may
qualify freshness. Below the horizon, independent daylight eligibility still
prevents Solar ownership and restrictive charging. Source continuity, trusted
sun/sunset metadata, current-interval/same-day coverage, rejected-generation
high-water and strict retained deadlines remain unchanged. Dump 15% and Boost
80% settings remain unchanged.

Tests-first reproduced six failures and four passes. The ten-test module then
passed with five subtests. Six modules total (one new, five existing) passed
117 tests / 145 subtests. The guarded full suite passed 1,653 tests / 1,635
subtests, zero failures (206 warnings, 280.36 seconds; 75 memory / 2,059 isolated
temporary stores). After independent review, the sunrise fixture was strengthened
to retain identical forecast data and sunset; its 10 tests / 5 subtests passed
again. Production was unchanged during that refinement. Independent source,
test and documentation/scope reviews are GO. Protected database metadata stayed
unchanged; contents were not read.

This candidate is local, uncommitted, unpublished and not installed. Software
checks do not prove physical acceptance or that daylight was the sole reason for
the supplied 06:00 provider rejection: raw provider payload was absent. Safest
rollback is withholding the candidate or a reviewed scoped revert. Non-live
preview should first confirm that valid provider data below the horizon does not
grant Solar charging ownership. Any live startup, provider-poll or sunrise
verification requires separate approval. No separate monitor-only mode is claimed.

PR #66 later merged normally at `0e0fa8a5e2779d318390124a34ff9e1b8cabd4ed`,
with parents `5f32ec510c6314aed91587c5efb957442fdd0046` and
`beff7112b7f18e0bfe016458e3f095eabdf25651`, tree
`cb513e17aa9756d9e1a133b514d4d962f9f478bd`. The source fix is merged but not
included in published .86 or installed runtime identity; .86 remains published
and unchanged. Merge does not establish physical acceptance, and the supplied
provider-poll trace still lacks the raw payload needed to establish the sole live
cause. Stage A is a separate local candidate based on this merge.

## Historical published release: 2.3.75-haos86

[Published 29 October 2026 at 09:53:02 AEDT](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.75-haos86).
Repairs the .85 failed-close recovery deadlock by renewing an unaccepted restrictive
close before requiring later close/MSC proof. Manual/Force, authority and independent
restrictions remain. The separate dashboard snapshot policy is unchanged.

Build 40782770509 verified both platforms: 22 layers total and 15 source byte/mode
checks each. Version/latest index: `sha256:68ae9242488169b25525c53ef106eae92197a3f398aa3210344a43c6601b9359`.
Metadata PR #64 merged normally at `3f94c6a86b0f7163d6f7762cddf123a509644be2`;
tag/container source: `74f21875e9a30e561d78644c4a5b0791becccc83`.
Independent image-proof review is GO, with full layer bodies checked by the author.
Source suite: **1,643 tests / 1,630 subtests**; disjoint release checks:
**58 tests / 61 subtests**, zero failures. Offline verifier: 73 cases passed.

Auto update was confirmed off on 29 October. The supplied 29 October 09:55:23 AEDT
startup confirms runtime `2.3.75-haos86` and source
`74f21875e9a30e561d78644c4a5b0791becccc83`. This confirms process identity at that
time, not ongoing physical acceptance. The 30 October 06:00:37 provider poll was
rejected at 06:00:39; baseline was observed from 06:02:37 through 07:10:44, but
without the raw provider payload the sole live cause is unproven. Dump15% and
Boost80% were confirmed on 30 October and are unchanged. Broader review and
supervised acceptance remain pending. See [publication receipt and live checks](docs/HAOS86_RELEASE_CANDIDATE.md).

## Historical published release: 2.3.74-haos85

[Published 28 October 2026 at 06:39:02 UTC](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.74-haos85). Metadata PR #61 merged normally at `ca569f1b8b44e892f2eec471cae573c175f36ad5`; its parents are the source PR #60 merge `aefba54dddcaace1e3b318bbf6cca2a282d6c3a3` and release metadata commit `72bd1fdfdc824b019a5eba43f991e3ef0ee5bbe1`. The release tag points to that metadata commit and tree `3ed6e5a677f1af72cfac503be91fe725375ea15b`; annotated tag object `8fc43ef082498766561acb15157175e48906adb3`.

Build 40644593573 succeeded. The amd64 and arm64 images each passed 11 layer/diff-ID checks and 15 source byte/mode checks. Version and `latest` share index `sha256:68a15730cd18592d153a27f29e4e801c5581c28680e86c299cdd9f478c120329`; platform manifests are amd64 `sha256:033e75f038393164f0d856925dd2da8c2ded84d8dc324e388b49b391eb79a37f` and arm64 `sha256:4345a9faed15a000144b529e83713adbe951de820dc72520376a195e5412d494`. The expected source fingerprint is `sha256:ad811c36d2a1f6708cbc9e5a6badfd53f4bdea73221e7df205f438db8e44d4be`. Independent registry metadata and source byte/mode expectations are GO; the independent reviewer did not redownload full layer bodies. The author-run OCI verifier checked all 22 layers, and 73 synthetic verifier cases passed. The previous .84 index remains `sha256:ce9f9c1abf04effd9ef33a0bfccc29282f9f81356f617cebd8a6b61e3c36f112`.

The merged source suite passed **1,632 tests / 1,606 subtests**. The disjoint release checks passed **16 tests** and **72 tests / 175 subtests**; no full-suite rerun was done for version markers and documentation. Automatic updates were confirmed off on 28 October. The supplied 29 October 07:25:16 app log confirms runtime signature 2.3.74-haos85 and source commit 72bd1fdfdc824b019a5eba43f991e3ef0ee5bbe1; ongoing physical acceptance remains unverified. A charge allowance may reduce immediate export; it does not guarantee battery absorption, full SoC or physical stability. See [the publication receipt and remaining live checks](docs/HAOS85_RELEASE_CANDIDATE.md) and [current state](docs/CURRENT_STATE.md).

## Historical pre-merge recovery checkpoint - merged by PR #63 - 29 October 2026

The supplied 500-row excerpt covers 07:46:40-08:25:03 AEDT: 113 succeeded, one failed and 386 pending. At 07:55-07:56, HA commands failed and restrictive fallback reported export-close acceptance False, with request boundary 1793220936.620536. Later observations reported exact MSC and current export limit 0.01 with fresh/accepted evidence, but the application remained stuck: the current .85 close epoch retained close_accepted=False, and the pending handler retried MSC only (up to 15 times). This documents the supplied trace summary; it does not establish a broader network cause.

The 29 October 07:25:16 app startup log confirms runtime signature 2.3.74-haos85 and source commit 72bd1fdfdc824b019a5eba43f991e3ef0ee5bbe1. This confirms process identity at that timestamp; it does not establish ongoing physical charge/export acceptance.

The local recovery implementation is narrow: in the restrictive hold branch, when an actual identity-bound pending epoch has a close boundary and close_accepted=False, retry the restrictive export close even if the current read already reports the close value. Retire the retained MSC phase, establish a new close-request boundary, require a later matching close report, then issue a new MSC request and require a later exact-MSC report. A readback alone must never set acceptance. A successful fallback close may be accepted for this sequence; it still does not mean the application completed successfully.

Keep legacy identity-None/non-live paths and trusted-closed startup with no close boundary unchanged. Preserve omission of a close already known accepted, Manual/Force, Remote EMS and current authority checks, exact request identity, live-state confirmation and independent restrictions. The separate UI stale-status banner can age while pending ticks restore the prior last_state; it is outside this close-recovery change and is not evidence by itself that no fresh read was attempted.

Tests-first validation reproduced both primary failures before the repair. After the repair, the new module passed 11 tests / 24 subtests and nine existing applicable modules passed 166 tests / 171 subtests. The final guarded full suite passed 1,643 tests / 1,630 subtests, zero failures (206 warnings, 278.26 seconds). Dotenv stayed disabled; StateStore guards allowed only 75 memory / 2,047 isolated temporary constructions. Independent source/test review is GO; independent documentation/scope review is GO. Protected database metadata matched, contents were never read, and all nine original unfinished worktrees matched their recorded hashes. These simulations establish software permission ordering, not physical acceptance. Risk is an extra restrictive close request and a renewed wait for later proof. Safest rollback is withholding this local candidate or a reviewed scoped revert. No commit, push, version bump, release, HA query, installation or live setting change was performed.

## Historical pre-publication source integration checkpoint - merged by PR #60

Approved branch `fix/solar-msc-planning-integration` in
`C:/Projects/sigenergy_optimizer-solar-msc-planning` combines five reviewed local
stages at main `556cca8c040e3eea52029a8ac055a5c81f411018`. Solar prioritizes present
fill progress using the existing deadline and bounded normal charge capability;
less immediate export is possible. Retain-only completed-total rebasing prevents
tiny floor changes from discarding earned relief. Persistent mode-helper currentness,
MSC pending request timing/waiting logs and passive reserve explanations are included.

Integrated source/test independent review is GO. Affected modules passed 365
tests / 495 subtests; eight new interaction methods passed 8 / 16. The final
guarded full suite passed **1,632 tests / 1,606 subtests**, zero failures.
Independent documentation/scope review is GO. See
[CURRENT_STATE.md](docs/CURRENT_STATE.md) for combined and standalone evidence. See [policy, risk and rollback](docs/SOLAR_FILL_PROGRESS_TRAJECTORY.md)
and the [control contract](docs/CONTROL_CONTRACT.md). At this pre-merge checkpoint no commit,
push, publication, installation or live setting change had occurred. A charge cap permits charging;
it does not guarantee battery absorption, full SoC or physical stability.

## Previous published release: 2.3.73-haos84

[Published 28 October 2026 at 03:51:01 UTC](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.73-haos84). This prior release included charge-readback metadata, Evening Boost persistent-helper currentness, proven pending-MSC epoch reuse, qualified unchanged-open-ceiling maintenance and bounded passive settlement evidence. Build 40628165315 passed. Immutable .84 version index `sha256:ce9f9c1abf04effd9ef33a0bfccc29282f9f81356f617cebd8a6b61e3c36f112` remains unchanged. See [the .84 publication proof and live checks](docs/HAOS84_RELEASE_CANDIDATE.md).

Operator startup evidence identifies installed .84 source `bc1439120ab6c68d5983768ffd678bb62fedefb8` at 15:00:56 AEDT on 28 October. No .85 installation or ongoing physical acceptance is established.

## Previous published release: 2.3.72-haos83

[Published 27 October 2026, 04:13:16 UTC](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.72-haos83).
Morning Slow now uses bounded partial charging instead of binary normal-cap release,
with command/readback/later-flow feedback. Forecast refill and other priorities remain
independent. Source PR #52 and metadata PR #53 are normally merged.

Tag/container source: `51d370a559397e52e2b5f5012733b87fab7a8096`.
Build 40448173242 passed. Across amd64/arm64, all 22 layer/diff-ID checks passed.
Each platform passed fourteen final source byte/mode checks; independent comparison passed.
Version/latest index: `sha256:55b20ab7f7e5f6c0c80f9ef0c55fee69537769fe686b8560b2997ea8a9d513b3`.
Retained source validation: 1,525 tests / 1,450 subtests; release checks: 37 / 11.
Previous immutable .82 remains unchanged.

See [publication proof and installation gates](docs/HAOS83_RELEASE_CANDIDATE.md)
and [Morning policy assumptions](docs/MORNING_SLOW_PARTIAL_RELIEF.md).
Installed .83 identity, hundredth-kW device precision and physical stability remain
unverified. Solar feedback allocation and recurring MSC diagnosis remain open.
No HA installation or live settings changes were performed.

## Previous published release: 2.3.71-haos82

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
See [the full publication receipt and installation gates](docs/HAOS82_RELEASE_CANDIDATE.md).

Installed .82 identity and physical acceptance remain unverified. Latest supplied
27 October startup identifies .81 source 247095a4f9905932c3f5716f3d1be6cee7b3c7f8;
auto update was last confirmed off on 26 October. No HA query,
installation or live setting change was performed. Solar allocation and recurring
MSC errors remain unresolved; limits and tariff/policy values remain decision-time
snapshots. Accepted cost risk remains: unpriced energy can export at a loss.

## Previous published release: 2.3.70-haos81

Published 26 October 2026 at 07:24:39 UTC (18:24:39 Sydney):
[GitHub Release](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.70-haos81).
Tag/container source `247095a4f9905932c3f5716f3d1be6cee7b3c7f8`, tree
`8a49610bcaee9fc41390c96580710136831a3ffe`. Metadata
[PR #47](https://github.com/Belot77/sigenergy-optimizer/pull/47) normally merged at
`f2a2d9a4b77ba6ce8e8ef40d419a6abe56f7d55f` with the exact tag tree.
[Build 40284898464](https://github.com/Belot77/sigenergy-optimizer/actions/runs/40284898464)
and independent image/source verification passed for amd64 and arm64:
22 layer hashes/sizes/diff IDs and fourteen target files per platform.
Version/latest OCI index:
`sha256:e3f58087681c0c08ab53b0b8263387e8388d0916796aea326fdf9344ba821526`.
Immutable .80 remains unchanged.

New traces separate requested ESS charging, the reported charge-limit setting and
measured battery power, with five flow report times and Solar feedback boundaries.
This is diagnostic evidence, not a Solar allocation correction or physical
settlement proof. The .80 UI log-retention improvement is included unchanged.
Retained source checks passed 204 tests / 196 subtests; release/evidence/logging
checks passed 54 tests / 12 subtests. No full suite was repeated.
See [the publication receipt and installation gates](docs/HAOS81_RELEASE_CANDIDATE.md)
and [evidence contract](docs/CONTROL_CONTRACT.md#passive-charge-allocation-evidence).
No installed .81 identity or live acceptance is claimed.


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
is added. See docs/CURRENT_STATE.md for exact scope, results and approval boundaries.

## Historical premerge import-cost checkpoint - 27 October 2026

Incomplete or unpriced import history alone is a warning and does not veto an
otherwise-qualified automatic battery-backed export. A finite recorded highest
actual import price still applies as the cost floor during incomplete history;
zero and negative floors are valid, and the floor is not averaged. Accounting
coverage remains unknown when evidence is incomplete, with existing sticky-day,
retry and retained-record behavior unchanged. The local combined candidate also
includes O19's final Demand Window check before permissive fallback import
recovery; ON or untrusted/conflicting evidence requests the existing restrictive
0.01 kW close after a current authority check. Both original candidate worktrees
remain preserved. The combined offline suite passed 1,499 tests / 1,429 subtests with zero failures. Independent source/test review was GO for this local integration and characterization only; O21 was unfixed at that historical integration checkpoint; see the local correction for current status. No release, installation or physical acceptance is claimed. Existing authority, flow, reserve,
Demand Window, PV-only protection, settlement and Evening Boost qualification
rules remain in force. Financial risk accepted by this policy: energy with no
known import price may be exported at a loss.

## Previous published release: 2.3.69-haos80

Published 25 October 2026 at 23:20:09 UTC (26 October 10:20:09 Sydney):
[GitHub Release](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.69-haos80).
Tag/source `acb576747e808e927bdd7d12346c507da9b188b6`, tree
`14103ec71d3b41ad6a85e2d8a149e3db705606bf`; metadata [PR #44](https://github.com/Belot77/sigenergy-optimizer/pull/44)
normally merged at `77bde899da35b2f933304192a9c7226d9e5e9ef3` with the exact tag
tree. Build [40243683190](https://github.com/Belot77/sigenergy-optimizer/actions/runs/40243683190)
succeeded at the exact source.

The UI logging fix filters recognized successful 2xx `httpx` INFO request messages
from the built-in UI ring. The newest-first 500-record in-memory buffer resets on
restart and can evict older errors; console logging and global levels are unchanged.
No control, retry or settlement behavior changed. See [the .80 publication receipt
and verification limits](docs/HAOS80_RELEASE_CANDIDATE.md).

Version/latest OCI index: `sha256:91120b1039eec3915a37c6ff1a1210cf1cf5e79d97e3e1d9de31207206301a5a`.
For amd64 and arm64, all 22 layer hashes, sizes and diff IDs were verified, and
fourteen target files per architecture match the tag. Fingerprint:
`sha256:386444cfc2defee474052cc86cb473059d8f1551d67ad49832e4e352fd382cf4`.
Immutable .79 index remains unchanged at
`sha256:cbaa5f68e4830737abba90666e486b9db848b3a853d1c9138c33a93f3b02bdad`.

Retained source validation passed 122 tests / 10 subtests, zero failures, 202
warnings, in 68.94 seconds; independent logging verification passed 30 cases.
All 46 release/source-pinning/logging checks passed in 10.69 seconds. Independent
helper and complete publication-proof reviews were GO; 68 synthetic verifier cases
passed. Auto-update was last confirmed off on 26 October before .79 publication;
there was no new HA query. No installed .79/.80 identity, full filesystem
equivalence or physical acceptance is claimed. The 65 failed applications and
59 unsuccessful fallbacks remain unexplained. O18, O5/O9, broader O6 depletion/floor
questions and parked O11 remain open.

## Previous published release: 2.3.68-haos79

Published 25 October 2026 at 21:08:21 UTC (26 October 08:08:21 Sydney):
[GitHub Release](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.68-haos79).
Tag/source `ea516ef6cabd9918dbea675694a9de3aa207c8af`; metadata [PR #41](https://github.com/Belot77/sigenergy-optimizer/pull/41)
normally merged at `44419af295a47be24d5f06af3ed7cba83b2f27bb` with exact tagged
tree `8e7e6cf6cdcbb6196383352c2a351f055aed5912`. Actions run `40233491965`
succeeded at the exact tag source.

Includes bounded O2 Solar re-entry and O6 relieved-Morning charge-handoff
qualification. Version/latest OCI index:
`sha256:cbaa5f68e4830737abba90666e486b9db848b3a853d1c9138c33a93f3b02bdad`.
Both amd64/arm64 images were checked; all 22 layer hashes, sizes and diff IDs
were verified, and fourteen target files per platform match the tag. Verification fingerprint:
`sha256:a5a6945fc54c5a872a97b717d377cb88b57c6c0e7d8a9704174bc33324f2e3f8`.
Immutable .78 index remains unchanged at
`sha256:35292feb279a4b33e4c86f5482d690a9704c91d7178038b115c3bc434ead991a`.

Full offline validation passed 1,415 tests / 1,380 subtests, zero failures,
206 existing warnings, in 241.93 seconds; focused checks passed 165 / 184.
All 16 release checks passed in 9.83 seconds. Independent source and publication
proof reviews were GO. See [the .79 publication receipt and acceptance limits](docs/HAOS79_RELEASE_CANDIDATE.md).
Auto-update was confirmed off by the operator on 26 October. No HA installation
or physical acceptance is claimed; O18 fill strategy, O5/O9 review, broader O6
depletion/floor questions and parked O11 remain open.

## Previous published release: 2.3.67-haos78

Published 24 October 2026 at 07:57:03 UTC (18:57:03 Sydney):
[GitHub Release](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.67-haos78).
Tag/container source: `3ccf99cc69a4586715aadcbdd2f1282aeea77bf0`.
[PR #38](https://github.com/Belot77/sigenergy-optimizer/pull/38) normally merged
with the exact tag tree after both architecture images were verified.

Includes O15 bounded runtime database execution and O17 transport-peer-bound HA
ingress authentication, atop .77 transaction, ledger and trace-recovery fixes.
Slow or unconfirmed storage retains unknown-cost protections. Normal HA ingress
keeps its HA login; custom proxies use the existing API-key path. Public
read/status policies remain unchanged. Accepted writes can complete after
timeout: refresh state before retrying. Threads cannot interrupt wedged OS I/O.

Merged-source validation passed **1,355 tests / 1,305 subtests**; focused 126 / 8.
All 16 release/source-pinning checks passed in 9.58 seconds. Independent source
and metadata reviews were GO. Both platform images, all 22 layers and thirteen
source/launcher files per platform match exact tag bytes.

[Publication receipt, upgrade and rollback notes](docs/HAOS78_RELEASE_CANDIDATE.md).
Installation and physical acceptance remain operator actions; existing reserve,
MSC settlement, independent limits and Manual/Force safeguards remain in place.
Ordinary runtime Logs availability and historical HDD/MSC causation remain unproven.

## Previous published release: 2.3.66-haos77

Published **2.3.66-haos77** on 24 October 2026 at 01:54:00 UTC (12:54:00 Sydney): [GitHub Release](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.66-haos77). Tag/source `7aa712f72ca2c0467e6740e3cb0f2191ba8d077e`, tree `33d9b94399f87d27baf787a59403861988182ce9`. Source PR #34 merged at `b4377de9f38d1c305c23a0b1dca9cb509afc1a9f`; metadata PR #35 merged at `81c2752c4e031bb9786ec0d00f1dca4e22c59de9` with exactly the tagged tree.

Includes configuration transaction safety, import-cost ledger integrity and trace clock recovery. Both architecture images and exact source bytes are verified; 1,275 tests / 1,305 subtests and all 16 release checks passed. [Publication receipt, upgrade and rollback notes](docs/HAOS77_RELEASE_CANDIDATE.md).

Install through the normal Home Assistant update flow using your backup/restore precautions. Trace recovery can take a normal 15-minute persistence interval when its HTTPS time checks pass. Unknown import-cost history may pause applicable automatic battery sales; independently qualified PV-only and Manual/Force behavior remain separate. Installation and physical acceptance remain operator actions.

This guide is for Home Assistant OS users running the SigEnergy Optimizer as a Home Assistant Add-on.

## Scope and Safety

This optimizer replaces the old blueprint automations for SigEnergy control.
Do not run both at the same time.

Safe order:
1. Disable old blueprint automations.
2. Verify or create required helpers.
3. Install and configure the add-on.
4. Start the add-on.
5. Verify behavior and logs.

## Prerequisites

- Home Assistant OS
- SigEnergy entities available in Home Assistant
- Amber price entities available in Home Assistant
- Solcast entities available in Home Assistant
- Home Assistant Long-Lived Access Token

## Install the Add-on Repository

1. Open Home Assistant: Settings -> Add-ons -> Add-on Store -> Repositories
2. Add repository URL:
   - https://github.com/Belot77/sigenergy-optimizer
3. Find SigEnergy Optimizer in the Add-on Store

## Step 1 - Disable Old Blueprint Automations

Go to Settings -> Automations and Scenes and disable or remove:
- sigenergy_optimiser
- sigenergy_manual_control

## Step 2 - Verify or Create Required Helpers

If you previously used the YAML automations, these may already exist.
Check Developer Tools -> States for these exact entity IDs:

- input_boolean.sigenergy_automated_export
- input_number.sigenergy_export_session_start_kwh
- input_number.sigenergy_import_session_start_kwh
- input_number.battery_min_soc_to_last_till_sunrise
- input_text.sigenergy_last_export_notification
- input_text.sigenergy_last_import_notification
- input_text.sigenergy_reason
- input_select.sigenergy_mode

If all exist, continue to Step 3.
If any are missing, create only the missing helpers.

### Helper YAML (optional)

If you prefer YAML helper creation, add this and restart Home Assistant:

```yaml
input_boolean:
  sigenergy_automated_export:
    name: "SigEnergy Automated Export"

input_number:
  sigenergy_export_session_start_kwh:
    name: "Export Session Start (kWh)"
    min: 0
    max: 9999
    step: 0.001
    unit_of_measurement: "kWh"

  sigenergy_import_session_start_kwh:
    name: "Import Session Start (kWh)"
    min: 0
    max: 9999
    step: 0.001
    unit_of_measurement: "kWh"

  battery_min_soc_to_last_till_sunrise:
    name: "Min SoC to Last Till Sunrise"
    min: 0
    max: 100
    step: 0.1
    unit_of_measurement: "%"

input_text:
  sigenergy_last_export_notification:
    name: "Last Export Notification"
    max: 255

  sigenergy_last_import_notification:
    name: "Last Import Notification"
    max: 255

  sigenergy_reason:
    name: "Current Reason"
    max: 255

input_select:
  sigenergy_mode:
    name: "SigEnergy Mode"
    options:
      - Automated
      - Force Full Export
      - Force Full Import
      - Force Full Import + PV
      - Prevent Import & Export
      - Manual
    initial: Automated
```

## Step 3 - Configure the Add-on

Open the add-on Configuration tab and set at least:

- ha_url
- ha_token

Notes:
- The token is required. The optimizer authenticates to Home Assistant REST and WebSocket APIs using ha_token.
- Advanced overrides can be added in extra_env as KEY=value lines.

## Step 4 - Start and Open

1. Start the add-on.
2. Open Web UI from the add-on page.

You should see current state, active decision, and manual override controls.

## What The Main Buttons Mean (Plain English)

These buttons are easy to confuse at first. Here is what each one does in everyday terms.

### Simulate Automated

- Think of this as a practice run.
- It tries different strategy styles and shows which one looks best right now.
- The simulation comparison panel is hidden by default and appears after you press this button.
- It only changes what you see on the screen.
- It does not change your real inverter settings.

### Run Cycle Now

- Think of this as "do the real check now".
- It makes the optimizer run immediately instead of waiting for the next normal cycle.
- This can apply real control changes (mode/limits) if the optimizer decides they are needed.
- Use this when you want an immediate live refresh/action.

### Preview (inside Simulation cards)

- Preview means "select this option and inspect it".
- It updates the comparison view and details so you can review that strategy.
- It does not draw the full simulation overlay on the chart.
- It does not change live settings.

### Overlay This (inside Simulation cards)

- Overlay means "draw this scenario over the live chart".
- It visually places the simulated path on top of your normal chart so you can compare easier.
- It is still a visual what-if tool only.
- It does not change live settings.

Quick rule of thumb:
- Preview = pick and inspect.
- Overlay = show it on the chart.
- Simulate Automated = run a what-if comparison.
- Run Cycle Now = run the real optimizer immediately.

### Clear Simulation

- After running simulation, the Simulate Automated button changes to Clear Simulation.
- Clear Simulation removes the visual simulation overlay and hides the simulation comparison panel again.
- It does not change live inverter settings.

## Step 5 - Verify Correct Operation

- Add-on logs: Settings -> Add-ons -> SigEnergy Optimizer -> Logs
- Optional CLI: ha addons logs local_sigenergy_optimizer

Published .80 release: the optimizer's built-in
log viewer/download omits recognized successful 2xx `httpx` INFO requests while
keeping HTTP failures and other diagnostics. Add-on console logs remain unchanged.
The UI holds at most 500 retained records in memory, newest first; requesting more
lines cannot recover evicted entries, and restarting clears this buffer. This
change improves diagnostic retention without changing optimizer control behavior.

Quick check:
1. Use a manual override in the UI.
2. Confirm expected EMS mode and limits are written.
3. Return to Automated mode.

## Configuration Tuning

Use the dashboard for day-to-day threshold tuning (Apply and Save).

For advanced keys, use extra_env in add-on config, for example:

```text
MAX_PRICE_THRESHOLD=0.015
TARGET_BATTERY_CHARGE=2.0
EXPORT_THRESHOLD_LOW=0.10
EXPORT_THRESHOLD_MEDIUM=0.20
EXPORT_THRESHOLD_HIGH=1.00
EXPORT_LIMIT_LOW=5.0
EXPORT_LIMIT_MEDIUM=12.0
EXPORT_LIMIT_HIGH=25.0
PV_SURPLUS_ESTIMATED_INIT_ENABLED=true
SUNRISE_RESERVE_SOC=10.0
MORNING_DUMP_MIN_SOC=30.0
```

Morning Dump uses `MORNING_DUMP_HOURS_BEFORE_SUNRISE` as a compatibility key for
the total window duration ending one hour after sunrise. For example, `0.5`
starts 30 minutes after sunrise and can run for up to 30 minutes. Morning Dump
cannot start or continue at or below `MORNING_DUMP_MIN_SOC`, which defaults to
30%, regardless of forecast refill confidence.

After changing add-on config, restart the add-on.

## Solcast provider-aware Solar charge freshness

Dynamic Solar charge-ceiling ownership uses provider refresh evidence separately
from Forecast Today's HA observation age. Map `forecast_today_sensor` and
`solcast_api_last_polled_sensor` to entities from the same Solcast instance. Their
default entity IDs are `sensor.solcast_pv_forecast_forecast_today` and
`sensor.solcast_pv_forecast_api_last_polled`; compatible environment keys are
`FORECAST_TODAY_SENSOR` and `SOLCAST_API_LAST_POLLED_SENSOR`.

Startup/reconnect/reload requires a baseline followed by a successful API Last
Polled advance. Normal charging remains available while unverified. Later
schedules and successful manual polls before a retained deadline cannot extend
that deadline. Expiry releases only the dynamic Solar charge restriction;
Solar remains subject to all existing MSC/PV-only and ownership protections.

Settings -> Forecast Safety exposes **Forecast observation maximum age (seconds)**,
using the existing `hvac_solar_forecast_max_age_seconds` /
`HVAC_SOLAR_FORECAST_MAX_AGE_SECONDS` key and 600-second default. It applies to
Remaining Today, Power Now, Forecast Today trust for Standby Holdoff, age-based
Forecast Tomorrow trust and selected import-price forecast freshness. Dynamic
Solar provider freshness is schedule/provider-aware and is not extended by it.

Before live acceptance, inspect provider state, poll/high-water/verified times,
retained/advertised deadlines, source/epoch and rejection reasons in Decision
Trace. The latest supplied installed startup/source proof remains
`2.3.64-haos75` / `413e1691bb58e0b942098ab43f44e873df157a2b` from 21 October;
it is not evidence that published `.76` is installed. The excerpt's
pending-close then pending-MSC states and subsequent HTTP 200 reads do not
prove physical settlement or later recovery. The prior `.73` proof is
historical. Rollback method remains unprovided.

### Solar low-surplus continuation (published .74; historical characterization, 20 October 2026)

After successful final Solar application, existing MSC export permission may
bridge a brief dip strictly before 15 seconds after the older fresh, coherent
PV/load report proving measured surplus above 0.5 kW.
Only a newly advancing PV and load report pair can renew the hold. Held or
cached reports, surplus from 0.2 to 0.5 kW, and forecast evidence cannot renew
it. Trust, coherent-flow, authority or application failure invalidates proof
immediately. Expiry requests conservative closure under current control
authority; failed applications retain deadline re-evaluation with bounded
three-second retries. Physical closure still requires actuator settlement.

A sanitized deterministic candidate characterization reproduced seven
25-to-zero kW closures at baseline; the candidate retained permission through
those short dips with renewed strong measured reports. Its mocked application
and real-tick timing do not constitute a full trace replay or physical inverter
proof; the physical cause remains unproven. This change is included in published
.74; this characterization does not establish installation or live behavior.

The release includes the reviewed control behavior from PR #26. See [the .74
release and supervised proof plan](docs/HAOS74_RELEASE_CANDIDATE.md).

## Evening Boost changes in published .75

The published .75 code requires trusted load and sunrise inputs for the overnight reserve calculation. Before initial Boost admission or after startup, restart, or return from manual ownership, fresh load reports must span at least 120 seconds and local monotonic time must also advance at least 120 seconds. These are minimums, not a promised start time. Cached reports do not qualify. A load-report gap or more than 60 seconds without an advancing report resets qualification; report cadence and latency may delay admission indefinitely. Existing failure closures remain immediate. Offline tests do not prove physical operation or settlement. Keep Boost off during initial verification of runtime identity, effective settings, report cadence, and reserve/limit assumptions; then enable it only as part of the already-authorized supervised acceptance trial. Switch off and retain manual ownership immediately on a safety failure, unexpected ownership, failed settlement, or renewed flapping. Unattended use follows only after acceptance succeeds. See the [published release and acceptance receipt](docs/HAOS75_RELEASE_CANDIDATE.md), [control contract](docs/CONTROL_CONTRACT.md), and [current status](docs/CURRENT_STATE.md).

## Common Issues

Connection refused:
- Check ha_url in add-on config
- Ensure Home Assistant is reachable from add-on runtime

Entity not found:
- Verify entity IDs in Developer Tools -> States
- Add missing helper entities from Step 2
- Use extra_env for non-default sensor/entity IDs if needed

Blank UI or stale state:
- Wait up to 60 seconds for initial cycle/heartbeat
- Check add-on logs
- Reopen via Open Web UI

## Stop or Uninstall

Stop:
- Add-on page -> Stop

Uninstall:
1. Stop add-on
2. Uninstall add-on
3. Re-enable old blueprint automations only if you are rolling back

## Operational Notes

- Decision loop is event-driven with a 60-second heartbeat fallback.
- State inputs include battery, PV, load, and price signals.
- Hardware limit clamping uses live ESS caps, then cached last-known-good caps, then fallback.
- The retained `poll_interval_seconds` setting controls daily/morning summary timing tolerance and status/health stale-data thresholds, not decision-loop frequency.

Published .76 includes the PR #31 Standby Holdoff and active Morning Dump fallback import-blocking correction. Ordinary economic-zero recovery retains its existing behavior. O13 code is published, but physical behavior remains unverified. See [current status and remaining gates](docs/CURRENT_STATE.md).

## Historical .77 version checkpoint (superseded)

At that checkpoint, the current published release was [**2.3.66-haos77**](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.66-haos77), published 24 October 2026. Tag/source `7aa712f72ca2c0467e6740e3cb0f2191ba8d077e`; metadata PR #35 merged at `81c2752c4e031bb9786ec0d00f1dca4e22c59de9` with the tagged tree. O15/O17 are source changes in this integration candidate, not part of .77. The current published release is .81; the supplied 27 October startup identifies .80 source `acb5767`, not an installed .81. See [the verified .77 receipt](docs/HAOS77_RELEASE_CANDIDATE.md), [current release and evidence status](docs/CURRENT_STATE.md), and [current README release status](#current-published-release-2370-haos81).

Historical .76 image verification, superseded as the current release by .77: OCI index: `sha256:b7df9f21fce7ef14e7b4f602235486e17b35b710907656dd0b43e796889a6e9a`; amd64 manifest `sha256:153257933183c42fa99afdd21a8ab0d48837eb64623e136d7d0a07b3db17269e`, arm64 manifest `sha256:8288d84e1bd41858d022caff8b91d11adab998b21f99ee7d1a92985c9be4b161`. The `.75` version-specific index remains unchanged at `sha256:ed2a984b457bfddb2b74050d437f98337944076e9144a8d1a19f577d8e82d898`.

Historical startup evidence available at that checkpoint identified `.75` / `413e1691bb58e0b942098ab43f44e873df157a2b` on 21 October as the latest full installed startup/source proof. The operator reported .76 installed after replacement-SSD restoration on 24 October; neither the .77 release receipt nor the fresh trace established a newer exact runtime identity. No live settings change, Boost enablement or physical acceptance was claimed there; actual rollback remained unverified. O4/O5, the parked O11 investigation and applicable Phase 1/2 live gates remained open.

Historical startup evidence records the operator initially reporting `.74` installed, Evening Boost off and add-on auto-update off. Later evidence at 13:28:25 Sydney identified runtime signature `.75` and exact source `413e1691bb58e0b942098ab43f44e873df157a2b`. The excerpt shows pending-close then pending-MSC states through 13:28:29 and HTTP 200 service/reads through 13:28:50; it does not prove physical settlement or later recovery. This was the latest full startup/source proof at that checkpoint; the earlier `.73` evidence is historical. No rollback method was supplied; supervised acceptance remained unverified.

`.73` includes version/source-pinned builds and resolved full-SHA recording, while carrying `.72` optimizer control behavior unchanged. The `.72` corrections cover Solar Override selected/protected floors, Morning Dump discharge intent and blocked-Dump MSC fallback, application-outcome trace recording, and precise positive sub-1-cent FiT explanations. The frozen `.72` tag/image exclude the Dockerfile source-pinning fix.

Clock recovery code is published in .77. The supplied 24 October archive contains 152 current persisted records from 17:07:41 to 17:22:40 Sydney with intact sequence continuity and a maximum ten-second interval. This is partial freshness evidence, not proof of runtime source, the preservation manifest, missing historical cycles or behavior across another restart. The original archive/MSC incident investigation remains parked and HA/hardware causation unproven. Short physical Demand Window import spikes remain separately deferred. See [current state and evidence limits](docs/CURRENT_STATE.md).

Protected rollback reference: **2.3.54-haos65**, source `9965e79133f38d5b9943dcf5a9b04ed6fdab1239`, public OCI index `sha256:dd7efe0fd9b192ae1fd996137c312e5f2aab12e01a285f6e75fb5a58dc8fe88c`. There is no GitHub Release for `.65`; an actual usable Supervisor restore/reinstall method and saved effective settings remain unverified. Artifact availability alone is not rollback proof.

Existing unfinished worktrees and the separate local archive-characterization tests remain preserved. The physical-export software default remains `0.0` (disabled); the reported site limit is not a universal default. The earlier README publication-status update changed no application behavior, thresholds, settings or permanent instructions; the Evening Boost behavior described above is included in published .75, with exact installed startup identity supplied and physical acceptance still unverified. The historical `release.sh` remains unsuitable: it preserves the haos suffix, updates only three of five markers, stages all changes and can commit/tag/push. Do not use it without a separate repair/review.

## Historical Maintainer Release Flow (not current instructions)

The helper examples below are historical. `release.sh` preserves an existing `haos` suffix and updates only three of the five established version markers. Do not use it for a future release until this behavior has a separate fix and review. For future catalog or publication work, create and verify the matching source tag before advertising the version or relying on a version-tag build; publication requires separate authorization.

Historical helper usage (do not use for current releases without separate review):

```bash
./release.sh patch
./release.sh minor "Release vX.Y.Z"
./release.sh major "Release vX.0.0"
./release.sh --dry-run patch
```

Notes:
- Historical behavior: the script updates only three of the five version markers and preserves an existing `haos` suffix.
- Historically it created and pushed `vX.Y.Z` to trigger `.github/workflows/build.yml`; do not treat these examples as current release instructions.
- If `GITHUB_TOKEN` is set, the helper polls GitHub Actions and reports success/failure.
