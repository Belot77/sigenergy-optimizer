# SigEnergy Optimizer AI Handover

## Current published release: 2.3.77-haos88 - 31 October 2026

Version 2.3.77-haos88 was published at 2026-10-30T23:42:25Z (31 October 10:42:25 AEDT): [GitHub release](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.77-haos88). The source is `41a2a93d27e3bd88146b68c77639f28193b3a565` (tree `e3c7f5b1f31c30ef54902937baf0f9cf59969c60`); annotated tag object `f7b5fd4f204a26c3b6c915c9417ddf54f5085a11`. Metadata PR #71 merged normally at `9579a3dbd7d7efd36367922809d118395f0eafee` at 23:41:50Z, with parents `2f0725602e339288efd1dbf5be07c229fa575c47` and the release source; merge tree `e3c7f5b1f31c30ef54902937baf0f9cf59969c60` matches the tagged tree.

Build [41145559636](https://github.com/Belot77/sigenergy-optimizer/actions/runs/41145559636) succeeded at 23:39:25Z. Version/latest OCI index: `sha256:cc6759bf5deb23e659083699840237288f744248ec053226acabe46722b7bb39`; amd64 manifest `sha256:116bd5668a8232f734096acde551c2774a662233afc94c839ae18358f7a73447`; arm64 manifest `sha256:0f91b913adde97bd49ab9c78ba05ccc4e4b70b03ebc13a6cc4f6eddf2ebaa4d7`. Source fingerprint: `sha256:7bd45c684e98c79b60b20bb6b671b01d8a7191f3deb91304b5606119a2d066fd`. Both platforms passed 11 compressed-layer/diff-ID checks and 15 source byte/mode checks. Independent metadata/source-expectation review is GO; it did not redownload all compressed layer bodies. The offline verifier passed 73 synthetic cases. Post-publication tag/source/merge/version/latest and prior-image checks passed; the immutable .87 index `sha256:b0e703483652a3b5ead7a1eb968f10dee2571c9d613f6d72e29a210c01d790f6` is unchanged. See [the detailed .88 publication receipt](HAOS88_RELEASE_CANDIDATE.md).

The release includes the three narrowly scoped PR #70 changes: same-morning process-local Morning Dump retirement after a completed automatic export loses trusted timed refill feasibility (the independent 15% floor is unchanged); provider recovery only from unchanged, fully revalidated evidence for the same source/session before its retained deadline; and one additional MSC origin only when an accepted primary request misses exact proof after the existing 3-second wait and an accepted restrictive fallback also lacks proof. The MSC recovery uses the existing nonextendable 15-second budget; ordinary-close retry remains a subtype. These changes do not claim general resolution of historical MSC errors.

Retained source validation passed 1,716 tests / 1,725 subtests. Release checks passed 211 tests / 272 subtests, zero failures (202 warnings, 25.62 seconds); guards recorded 393 isolated temporary stores, no memory stores and no rejected paths. Protected database metadata was unchanged; dotenv/settings environment-file access was disabled. Independent source/safety, tests, release metadata and documentation/scope reviews are GO. These checks establish software/publication evidence, not live physical acceptance.

The latest supplied startup and trace still identify installed .87 source `6a43077be1a59512bf44b1bb1c41aed410992c37` at 30 October 12:54:06 through 31 October 08:39:26 AEDT; auto-update was last confirmed off on 31 October. No .88 installation or physical acceptance is established. Next evidence is an approved .88 startup/source identity check, then separately supervised live validation of Dump retirement/restart, provider recovery, Morning-to-Solar handoff/deadline, request-correlated MSC/close behavior and eligible-day Boost qualification under its unchanged 120-second rule. O4/O5/O6/O9 policy and behavior questions, O11 legacy investigation, O20 parked work, O8 observation gap and deferred Demand Window question remain as tracked below. No HA action is included in this documentation stage.


## Historical published release: 2.3.76-haos87 - 30 October 2026 (superseded by .88)

Published at 2026-10-29T22:49:07Z (30 October 09:49:07 AEDT): [GitHub release](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.76-haos87). Metadata [PR #68](https://github.com/Belot77/sigenergy-optimizer/pull/68) merged normally at `77be45d70b665283a49ce249111f1fa6c6732c69` at 22:48:37Z, with parents `4ebdb82daf8a3c41efbab1f12366f413e382fbb2` and `6a43077be1a59512bf44b1bb1c41aed410992c37`; merge tree `de893cf6a0bae925025d22eb0099b5b6beb00b8f`. Annotated tag object `9a3ff193b8a79791a3eb333f75463365e939a9ba` resolves `v2.3.76-haos87` to source `6a43077be1a59512bf44b1bb1c41aed410992c37` and that tree.

Build [40968005213](https://github.com/Belot77/sigenergy-optimizer/actions/runs/40968005213) succeeded for the exact source. Version/latest OCI index: `sha256:b0e703483652a3b5ead7a1eb968f10dee2571c9d613f6d72e29a210c01d790f6`. The amd64 manifest is `sha256:9fb2e71617d7e943fd64aff45dbe011fb18c1642022dd8e25dbb539aa6e11051`; arm64 is `sha256:2e36eabf2820d78eabeff254fcdcd61ae8e680375c8b55a3adb041aa4e7d95fa`. Each platform passed 11 layer/diff-ID checks and 15 expected source byte/mode checks. Source fingerprint: `sha256:a80c8d7e425ec222b03ff731f0e9c50f810440f43776b96aa22131b163b999f2`. The author verified layer bodies; the independent verifier confirmed registry metadata and expected source, but did not redownload all compressed layer bodies. Offline OCI verification passed 73 synthetic cases. Post-publication tag, source, normal-merge, version/latest and previous-index checks are GO. Previous immutable .86 index `sha256:68ae9242488169b25525c53ef106eae92197a3f398aa3210344a43c6601b9359` remains unchanged.

The source includes PR #66 provider-payload/daylight separation and PR #67 bounded recovery for the two accepted restrictive-settlement origins. Retained source validation: guarded full suite 1,676 tests / 1,672 subtests, zero failures; focused five-module run 86 / 136; independent safety run 11 / 28. Release version/source-pinning checks passed 16 tests, six runtime modules passed 96 / 141, and the offline verifier passed 73 cases.

Subsequent supplied evidence for .87: the 30 October 12:54:06 AEDT startup identified runtime `2.3.76-haos87` and source `6a43077be1a59512bf44b1bb1c41aed410992c37`; the 31 October trace continued to identify it through 08:39:26 AEDT. Auto-update was last confirmed off on 29 October. PR #70 was not in published .87 and was later released in .88. This historical identity does not establish a .88 installation or physical acceptance.

The supplied startup/trace establishes only the `.87` installed identity. No `.88` startup/source proof or physical acceptance is supplied. Outstanding live evidence remains provider recovery after the next scheduled update, the Morning-to-Solar charge/export handoff and deadline behavior, request-correlated MSC/close recovery, and Boost qualification on an eligible forecast day under its unchanged 120-second rule. At each publication, report shipped changes, remaining engineering/policy work, missing live proof and the next authorized action.

## Historical .88 release-preparation checkpoint - before 31 October publication

Branch `release/2.3.77-haos88` is local release preparation based on `main` `2f0725602e339288efd1dbf5be07c229fa575c47`. PR #70 has already merged the combined 12-file change; the merged corrections are not in the published or installed `.87` image. The installed runtime/source remains `2.3.76-haos87` / `6a43077be1a59512bf44b1bb1c41aed410992c37`. Morning Dump keeps the independent 15% floor and adds process-local same-morning retirement after a completed automatic export loses trusted timed refill feasibility; restart loses the latch and all current gates must pass again. Provider recovery can reuse only unchanged, fully revalidated prior evidence from the same source/session before its retained deadline. MSC adds only `accepted_primary_msc_opening_unobserved` when the accepted primary request misses exact proof during the unchanged 3-second opening wait and the subsequent accepted restrictive fallback also lacks proof; any recovery uses the existing nonextendable 15-second budget. Ordinary-close retry remains a subtype, not a generic origin.

The merged full suite passed 1,716 tests / 1,725 subtests (206 warnings, 283.08 seconds); guards allowed 75 memory / 2,190 temporary stores and rejected zero paths. Independent receipt review is GO for the exact 12-file PR #70 scope. Release checks passed 16 modules with 211 tests / 272 subtests, zero failures (202 warnings, 25.62 seconds); guards recorded 393 isolated temporary stores, zero memory stores and zero rejected paths. Protected DB metadata stayed unchanged, and dotenv/settings environment-file access was disabled. Independent release-preparation source/scope and documentation reviews are GO. At that preparation checkpoint, no additional control changes, release commit, tag, publication, HA action or live setting change was included. Physical acceptance remains partial; see `docs/HAOS88_RELEASE_CANDIDATE.md` for release gates and evidence limits.

## Current remaining work and reporting

- Engineering/policy decisions remain open for O4 Boost qualification retention and stability, O5 reserve/load/price assumptions, O6 broader floor/depletion behavior, and O9 overlapping ownership/status semantics.
- Published O2/O6/O18 corrections still need live acceptance. Published .87 recovery remains limited to its two reproduced accepted restrictive-settlement origins. PR #70 adds one narrowly qualified accepted-primary MSC opening origin, now published in .88; it does not establish that every historical O11 MSC/application error is fixed. Legacy O11 investigation remains parked.
- O20 non-positive-price Morning Dump redesign is parked; the old O8 observation gap is irrecoverable; short Demand Window import spikes are deferred and not confirmed as a defect.
- The supplied installed identity remains .87; no .88 startup/source proof or physical acceptance is supplied. Remaining live evidence is Dump retirement/restart, provider recovery after the next scheduled update, Morning-to-Solar charge/export and deadline behavior, request-correlated MSC/close recovery, and Boost qualification on an eligible forecast day under its unchanged 120-second rule. .88 release checks and independent source/scope reviews passed.
- Each publication report should say what shipped, what engineering/policy work remains, which live proof is missing, and the next authorized action. Supplied installed identity remains .87; no .88 installation or physical acceptance is established.

## Historical pre-merge integration checkpoint - combined dawn recovery - 31 October 2026

Branch `fix/dawn-recovery-integration` at `C:\Projects\sigenergy_optimizer-dawn-recovery-integration` is based on verified `origin/main` `8f413773e53dca3864b70544546cb9934fd1af44`. The user approved local integration of the three preserved stages. The combined candidate contains 12 files: one optimizer file with 20 source hunks verified nonoverlapping, six test files, and these five shared documents. The source-only composition check recorded normalized SHA-256 `682fe643fdd94975a2731d3828a5506512b03a98f7433baf44afe30901b46ded`; it is a composition check, not integrated runtime validation.

The combined behavior is:

- Morning Dump: after a successfully completed automatic Dump loses trusted timed refill feasibility, retire Dump admission for that same identified morning window. Only a completed, selected positive battery-export Dump arms the process-local history, and only actual application may arm or retire it. Keep the stop through failed closure, cancellation and operator-mode changes. Trusted capacity and available-energy evidence are required; the independent 15% SoC floor alone does not trigger retirement. A later morning can qualify again in the same process. A restart loses the latch; even in the same morning, a fresh decision must pass all current eligibility, authority and settlement gates before Dump can qualify again. Fewer same-window exports, including after a better forecast, are deliberate.
- Provider trust: distinguish temporary sun/sunset metadata uncertainty from rejection of a provider generation. Retain immutable evidence for the last verified normalized detailed payload, trusted sunset, poll, source, session epoch and period configuration. Release provider authority and restrictive Solar charging while metadata is untrusted. Restore only unchanged, fully revalidated evidence before the retained deadline in the same source/session; a changed, bad or rejected generation cannot recover under an unchanged poll. Revalidate before and during restrictive application, preserve a newer verified generation against older in-flight state, and retain an earlier observed schedule with `min(D, N)`. Trust is not persisted and no update is forced; daylight ownership and independent protections remain separate.
- MSC opening recovery: add only `accepted_primary_msc_opening_unobserved` when the primary MSC request was accepted but exact proof misses the existing three-second opening wait, and the subsequent accepted restrictive fallback also lacks proof. Use the existing nonextendable 15-second budget captured before the first fallback close and require request-correlated close and new-MSC proof. Fresh contradictory open reports retire the attempt. Rejected or exceptional calls remain failures; if fallback fully settles within the original short wait, the initiating application still remains failed.

Standalone stage validation is retained as component evidence, not as validation of this composed worktree. Morning Dump passed 13 new tests / 9 subtests and its guarded suite passed 1,689 / 1,681; provider trust passed 20 new tests and its guarded suite passed 1,696 / 1,708; MSC recovery passed 7 new tests / 8 subtests, focused safety checks 88 / 137, and guarded suite 1,683 / 1,680. Each component full-suite result had zero failures.

Historical tests-only characterization: branch `test/dawn-recovery-characterization` added 11 tests / 17 subtests without production changes; the focused run passed 158 tests / 220 subtests, and independent review was GO. The protected characterization branch remains separate from this integrated candidate.

The focused run on this combined worktree passed 195 tests / 272 subtests (202 warnings, 14.05 seconds). Guards allowed 393 isolated temporary stores and rejected zero paths; protected database metadata stayed unchanged. Integrated source/safety and test-coverage reviews are GO. The combined guarded full suite passed 1,716 tests / 1,725 subtests, zero failures (206 warnings, 283.08 seconds). Full-suite guards allowed 75 memory / 2,190 isolated temporary stores and zero rejected paths. Protected database size/mtime metadata stayed unchanged; contents were not read. Dotenv stayed disabled and settings could not read env files. Independent final documentation/scope review is GO; exact 12-file scope and preservation checks passed. All three production-stage patches and the tests-only characterization patch remain unchanged in their original worktrees. At this pre-merge checkpoint, no commit, push, merge, version bump, publication, HA query, installation or live settings change had occurred. PR #70 subsequently merged; see the receipt below. Safest rollback is withholding this candidate or using a separately reviewed scoped revert. Software checks do not establish physical acceptance.

### Subsequent PR #70 merge receipt

[PR #70](https://github.com/Belot77/sigenergy-optimizer/pull/70) merged the combined dawn-recovery changes normally on 31 October 2026 at 10:17:29 AEDT (2026-10-30T23:17:29Z), merge commit `2f0725602e339288efd1dbf5be07c229fa575c47`, with parents `8f413773e53dca3864b70544546cb9934fd1af44` and `ba812ed71e5ff9a233e87b2a621b5cf35a69d6c8`, and merge/review tree `0c590ec2fa24089af9fda5524fcce34d53746e54`. Independent receipt review is GO; the exact 12-file scope and merged source are confirmed. This merge is not release/publication or live acceptance. The pre-merge validation above remains the record for that integration stage; current .88 release preparation is stated at the top of this document.

## Supplied .87 trace evidence retained - 31 October 2026

The supplied file `sigenergy_decision_trace_24h_20261030T214815Z.jsonl` contains 18,912 valid rows overall. The `.87` runtime session spans 30 October 12:54:06 through 31 October 08:39:26 AEDT and contains 15,807 rows: 15,781 succeeded, 23 pending and three failed, with continuous session sequence 1–15,807. Recorded flow and charge-readback freshness flags are true. The earlier 13-minute-17-second gap crosses the restart boundary; no new internal .87 recording gap is established, and retained possible-gap flags remain.

- Morning Dump re-entered eight times from 06:30–06:34 as fill need crossed unchanged safe refill opportunity 26.8465178595 kWh. Nine close requests and eight MSC requests accompanied 17 pending records. This establishes controller admission chatter; the cause of the energy telemetry rebound is unproven. Correct independent safety closes must remain immediate.
- Provider authority became VALID at 05:59:34 after the 05:59:33 poll. At 06:45:31 untrusted sun metadata accompanied `provider_detailed_payload_invalid`. Sun/coverage flags recovered at 06:45:34, but the unchanged provider generation remained `UNVERIFIED` through 08:39:26. Raw detailed payload is absent, so the sole live cause is unproven. Recovery after the advertised 08:42:43 update is outside the supplied evidence.
- At 20:50:33 on 30 October the MSC-opening application failed, returned to success at 20:50:39 and had matching MSC/export maintenance reports by 20:50:54. This primary opening-timeout origin was outside the published two-origin recovery. Accepted commands, application success and reported settings do not prove physical settlement; fresh contradictory open reports remain unsafe.
- Evening Boost was enabled with a 100 kWh minimum tomorrow forecast; the recorded 82.7882 kWh forecast explains nonselection. Its 80% target and 120-second qualification remain unchanged.
- At 08:39:26 Morning Slow requested and read back 2 kW; measured battery charge was 2.001 kW, PV 10.425 kW, load 1.244 kW, export 7.214 kW, import zero and SoC 38.6%. This is a sampled operating point, not complete live acceptance.

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

## Historical published release: 2.3.75-haos86 - 29 October 2026

[GitHub release](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.75-haos86)
was published at 2026-10-28T22:53:02Z (29 October 09:53:02 AEDT).
Metadata [PR #64](https://github.com/Belot77/sigenergy-optimizer/pull/64) merged
normally at `3f94c6a86b0f7163d6f7762cddf123a509644be2` with parents
`b294f463e9fd4a2cbb6e1266e7d922422067e318` and metadata/tag source
`74f21875e9a30e561d78644c4a5b0791becccc83`. Merge tree
`711fe705180524edf12bbc45d790541ae120a724` equals the reviewed preparation tree;
annotated tag object `901b75918082666f2ade9027c222d14ffc709819` resolves to that source.

Build [40782770509](https://github.com/Belot77/sigenergy-optimizer/actions/runs/40782770509)
succeeded. Version and latest resolve to index
`sha256:68ae9242488169b25525c53ef106eae92197a3f398aa3210344a43c6601b9359`. Both runtime platforms passed
11 layer/diff-ID checks and 15 source byte/mode checks each, including the exact
source pin. Source fingerprint: `sha256:d362aad0e623fdd6a63134cdee0803bdcd8d23a6d9228690149ec40ffec05bba`.
Independent registry metadata/source expectations are GO; full layer bodies were
verified by the author, not independently redownloaded. The offline verifier passed
73 cases. Previous immutable .85 index remains
`sha256:68a15730cd18592d153a27f29e4e801c5581c28680e86c299cdd9f478c120329`.
Post-publication checks confirmed release, tag/source, exact merge parents/tree and
version/latest/previous indexes.

Normally merged source PR #63 repairs the .85 failed-close recovery deadlock:
renew an identity-bound unaccepted restrictive close, require later closure proof,
then a new MSC request and later exact-MSC proof. Authority, Manual/Force, request
identity and independent restrictions remain. The separate retained dashboard
snapshot policy is unchanged; this does not resolve every historical MSC failure.

Retained source validation: **1,643 tests / 1,630 subtests**, zero failures.
Disjoint guarded release checks: **16 static tests** and **42 runtime tests /
61 subtests**, zero failures. Independent source, tests, release docs/scope and
image-proof reviews are GO. No full suite was repeated for version literals/docs.

Auto update was confirmed off on 29 October. The supplied 29 October 09:55:23
AEDT startup confirms runtime `2.3.75-haos86` and source
`74f21875e9a30e561d78644c4a5b0791becccc83`. This confirms process identity at
that timestamp, not ongoing physical acceptance. The 30 October 06:00:37 provider
poll was rejected at 06:00:39; baseline was observed from 06:02:37 through
07:10:44, but the raw provider payload is absent, so the mechanism is reproduced
without establishing the sole live cause. Dump15% and Boost80% were confirmed on
30 October and are unchanged by this candidate. Broader review and supervised
acceptance remain pending.
The .86 release remains published and immutable. Physical acceptance, current reports,
effective limits and supervised behavior are not established by startup identity.
Keep a usable operator backup/reinstall path; none is demonstrated here. Preserve
unfinished work and runtime data. Do not use release.sh. See [publication receipt
and acceptance limits](HAOS86_RELEASE_CANDIDATE.md).

## Historical published release: 2.3.74-haos85 - 28 October 2026

[GitHub release](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.74-haos85) was published at 2026-10-28T06:39:02Z (17:39:02 AEDT). Metadata PR #61 merged normally at `ca569f1b8b44e892f2eec471cae573c175f36ad5`, with parents `aefba54dddcaace1e3b318bbf6cca2a282d6c3a3` and `72bd1fdfdc824b019a5eba43f991e3ef0ee5bbe1`; merge tree `3ed6e5a677f1af72cfac503be91fe725375ea15b` matches the published metadata tree. Annotated tag object `8fc43ef082498766561acb15157175e48906adb3` resolves to source/tag commit `72bd1fdfdc824b019a5eba43f991e3ef0ee5bbe1` and that tree.

Build 40644593573 succeeded. Version and `latest` resolve to the same OCI index, `sha256:68a15730cd18592d153a27f29e4e801c5581c28680e86c299cdd9f478c120329`. The linux/amd64 manifest is `sha256:033e75f038393164f0d856925dd2da8c2ded84d8dc324e388b49b391eb79a37f`; linux/arm64 is `sha256:4345a9faed15a000144b529e83713adbe951de820dc72520376a195e5412d494`. The author-run verifier checked 11 layers and 15 pinned source files per platform, including the expected source fingerprint `sha256:ad811c36d2a1f6708cbc9e5a6badfd53f4bdea73221e7df205f438db8e44d4be`. Independent registry metadata and expected source byte/mode checks are GO; the independent reviewer did not redownload full layer bodies. The offline synthetic verifier passed 73 cases. Previous immutable .84 index `sha256:ce9f9c1abf04effd9ef33a0bfccc29282f9f81356f617cebd8a6b61e3c36f112` remains unchanged.

The merged source full suite passed **1,632 tests / 1,606 subtests**, zero failures. Disjoint guarded release runs passed **16 version/source-pinning tests** and **72 runtime-focused tests / 175 subtests**, zero failures; the full suite was not repeated for version literals and documentation. No control behavior changed in the release metadata.

Automatic updates were explicitly confirmed off on 28 October. Earlier operator evidence identifies installed .84 at 15:00:56 AEDT that day. The supplied 29 October 07:25:16 app log confirms runtime signature `2.3.74-haos85` and container source commit `72bd1fdfdc824b019a5eba43f991e3ef0ee5bbe1`; this confirms process identity at that time, not ongoing physical acceptance. Supervised charging/export/MSC/Boost/provider evidence remains outstanding. Do not claim universal resolution of historical MSC errors or guarantee battery absorption, deadline fill or physical stability. Keep .84 immutable; backup/reinstall rollback readiness has not been demonstrated. See [the publication receipt](HAOS85_RELEASE_CANDIDATE.md) and [fill policy and limits](SOLAR_FILL_PROGRESS_TRAJECTORY.md).

## Historical pre-merge recovery checkpoint - merged by PR #63 - 29 October 2026

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

Approved local branch `fix/evening-boost-helper-currentness` at
`C:\Projects\sigenergy_optimizer-boost-helper-currentness`, based on
`223ac22356fcb0fc3e8f21aaa639b2fc013165c1`, contains a narrow eligibility
correction. A current read of the trusted persistent mode `input_select` can
remain current even when its `last_reported` or fallback `last_updated` is old.
Before this candidate, the separate upper-age check in Evening Boost re-entry could still
reject that observation and reset qualification. The candidate skips only that
upper-age cap for a current-read, available, fresh, trusted `input_select` mode
observation with the expected value and a finite, non-boolean, non-future timestamp. The
existing `0 <= age` condition remains strict: even a timestamp one second in
the future is rejected. Remote EMS and device age limits remain unchanged.

All other re-entry and dispatch gates remain: trusted load and sunrise evidence,
120 seconds of advancing load-report span and local monotonic qualification,
report monotonicity and the 60-second gap reset, Manual/Force ownership,
current dispatch authority and limits, forecast/reserve/price checks, MSC
protections, and immediate failure closures. This changes only the helper age
check; it adds no independent safety hold or Boost redesign.

The supplied 3,955 closed live decision records are consistent with this
helper-age gate, but raw rejected timestamps are absent from the supplied evidence, so no live cause
is established. SolarDip helper-age follow-up is separate; recurring MSC
failures remain open.

Validation: the tests-first run reproduced four reported failures, including
two dispatch subcases that could not reach admission. After the correction,
all seven new test methods passed with 25 subtests. The seven-module applicable
run passed 247 tests / 190 subtests (202 warnings, 45.08 seconds). The full suite
passed 1,535 tests / 1,481 subtests (206 warnings, 260.16 seconds), zero failures.
Dotenv was disabled; full-suite StateStore guards allowed only memory (75) or
isolated temporary paths (1,854 constructions). Independent safety and
documentation reviews are GO. These checks do not prove physical acceptance.

This is a local uncommitted candidate with no release, installation, or live change. Rollback is a scoped
revert of the helper-age exception.

Verification sequence for separately approved installation:

- Monitor-only: observe current mode chronology, old report/update timestamps, and the
  associated Remote EMS, load and sunrise report times without changing
  settings; confirm qualification resets and failures remain immediate.
- Offline dry-run: use fake HA and isolated storage to cover a current mode read
  with old report/update timestamps, future mode timestamps, independent Remote EMS/device
  age, report-span and gap resets, and unchanged authority/limit/price/reserve/
  MSC gates. This does not claim a global dry-run switch or suppression of all
  writes.
- Supervised live control: only after separate approval, compare requested,
  observed and settled behavior under existing limits and stop conditions.
  Local tests do not establish physical operation.

## Merged checkpoint: charge readback report metadata — PR #55 — 28 October 2026

The charge-readback candidate below later merged normally in
[PR #55](https://github.com/Belot77/sigenergy-optimizer/pull/55), source head
`f6eb5ef1080b10e07aa40d2e5f07850f1ecd54a2`, merge
`223ac22356fcb0fc3e8f21aaa639b2fc013165c1`. It remains unverified in an
installation and has no physical acceptance claim.

## Historical pre-merge charge-candidate context — 28 October 2026

Approved local branch `fix/charge-readback-report-metadata` at
`C:\Projects\sigenergy_optimizer-charge-readback-metadata`, based on
`3b10c7007f4a592a48ba92ec4fa0da291e3f385e`, contains a narrow candidate adding
`cfg.ess_max_charging_limit` to `_read_state` report entity IDs. This lets
charge-limit observations use HA's `last_reported` time when the setting is unchanged
and its `last_updated` time no longer advances. Exact-state / `last_updated`
correlation remains. Missing or malformed metadata may use the existing
`last_updated` fallback; stale metadata remains subject to existing freshness
checks. Conflicting state / `last_updated` metadata sets
`_actuator_metadata_conflict` and rejects the observation timestamp. Existing
age, post-command, matching, and coherent-flow rules are unchanged. No
timestamps are synthesized. A metadata batch failure can reduce readback
availability, and this cannot help an integration that does not report the
entity.

The supplied 448-row `.83` trace shows every readback `fresh=false` with the
recorded report time frozen at `06:04:53.712060` AEDT. The supplied Morning
partial-qualification export was not seen (maximum `3.557 kW` versus `14.5 kW`). These are supplied
trace findings, not proof that this candidate fixes live behavior. Supplied
startup evidence identifies `.83` at 07:42:15 AEDT on 28 October, runtime
`2.3.72-haos83`, source
`51d370a559397e52e2b5f5012733b87fab7a8096`; physical acceptance is not
established. Boost’s 3,955 selected decision records on 27 October and recurring
MSC failures remain separate open issues.

Validation: both initial regressions failed before the query addition. The final
six-module guarded run passed 221 tests / 172 subtests (202 warnings, 43.24 s);
StateStore guards allowed only isolated temporary storage (314 constructions),
with dotenv disabled. One existing Solcast event-loop deadline test initially
woke 9.441 ms early; isolated unchanged-.83 and candidate checks passed, then
the complete applicable set passed on repeat. No timing assertions were changed.
Independent source/test review: GO. No full-suite run or live access was performed.

The only production change is the report-entity query addition. It can let the
existing Morning relief controller qualify a genuinely fresh charge readback;
it does not guarantee relief or fix provider, Boost or MSC recovery.

Verification sequence for a separately authorized installation:

- Monitor-only: inspect correlated charge state, `last_updated` and `last_reported`
  without changing settings; confirm genuine integration reports advance.
- Offline dry-run: use fake HA/isolated storage to check fresh matching reports
  and rejection of missing, conflicting, stale and future reports. No global
  runtime dry-run switch or suppression of all writes is claimed.
- Supervised live control: retain existing authority/physical limits and compare
  command completion, later matching readback and later coherent flows when
  Morning relief actually qualifies. Stop on unsafe flow, lost authority or
  repeated settlement failures; passing local tests is not physical acceptance.

If later committed, rollback is a scoped revert of the query addition. This local documentation
update makes no claim of live validation, installation, or physical acceptance.

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
