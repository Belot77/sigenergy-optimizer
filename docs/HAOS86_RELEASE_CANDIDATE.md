# HAOS .86 publication receipt

**2.3.75-haos86 is published**, 2026-10-28T22:53:02Z / 29 October 09:53:02 AEDT.
[GitHub release](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.75-haos86).
The operator approved publication and this documentation receipt, and confirmed
Auto update off on 29 October. No HA installation, query or live settings change
was made. Do not use release.sh.

Metadata source/tag commit: `74f21875e9a30e561d78644c4a5b0791becccc83`.
Reviewed metadata tree: `711fe705180524edf12bbc45d790541ae120a724`.
Annotated tag object: `901b75918082666f2ade9027c222d14ffc709819`.
Metadata [PR #64](https://github.com/Belot77/sigenergy-optimizer/pull/64) merged
normally at `3f94c6a86b0f7163d6f7762cddf123a509644be2` on 28 October 22:52:30 UTC /
29 October 09:52:30 AEDT. Exact parents are
`b294f463e9fd4a2cbb6e1266e7d922422067e318` and the metadata source; merge tree
matches the reviewed tree. Receipt documentation does not change the tagged image.

## Image publication proof

Build [40782770509](https://github.com/Belot77/sigenergy-optimizer/actions/runs/40782770509)
succeeded at the exact source. Version and latest share index:
`sha256:68ae9242488169b25525c53ef106eae92197a3f398aa3210344a43c6601b9359`.

| Platform | Runtime manifest | Checked layers | Checked source files |
| --- | --- | --- | --- |
| linux/amd64 | `sha256:0aacd1a0ac078735a4ead9d6ad87362e3f4dbd3b2af74b8db3a60fcf938a2d1e` | 11 | 15 |
| linux/arm64 | `sha256:3d2cf0a0f482e70718cb7cd63831dc8d6acf62ffeebc7ead4aa21b5db694d3c0` | 11 | 15 |

The author verifier checked index/manifest/config integrity, labels and launch
command, every compressed-layer digest and uncompressed diff ID, overlay paths,
source bytes/modes and exact generated source pin. Fingerprint:
`sha256:d362aad0e623fdd6a63134cdee0803bdcd8d23a6d9228690149ec40ffec05bba`.
Independent registry metadata and source byte/mode expectations are GO; the reviewer
did not redownload full layer bodies. Offline verifier: 73 cases passed, zero failures.
Immutable .85 index remains
`sha256:68a15730cd18592d153a27f29e4e801c5581c28680e86c299cdd9f478c120329`.
Post-publication verification confirmed release identity, remote annotated tag,
source/tree, exact normal merge parents and version/latest/previous indexes.

## Verified source

[PR #63](https://github.com/Belot77/sigenergy-optimizer/pull/63), reviewed head
`bdf4108e11f7c04b3811f12bcb54e6fff9504403`, merged normally at
`b294f463e9fd4a2cbb6e1266e7d922422067e318` on 29 October at 08:55:56 AEDT
(28 October 21:55:56 UTC). Parents are
`4ba817315f45fdbf47077d1095f1f0a2033a7316` and the reviewed head. Merge tree
`35c9b314047dc77da08af366e469a1be723b840a` equals the reviewed source tree.
The published container source is metadata/tag commit `74f21875e9a30e561d78644c4a5b0791becccc83`,
not this source-merge SHA.

## Problem and repair

The supplied .85 trace covers 07:46:40-08:25:03 AEDT on 29 October: 500 records,
113 succeeded, one failed and 386 pending. HA service failures at 07:55-07:56
triggered fallback; its close response was false. Later fresh matching close/MSC
reports could not clear the unaccepted close-command flag. MSC-only retries
therefore could not complete recovery. This establishes a source-level .85
regression triggered by the service fault; it does not establish that fault's cause.

The repair retries a restrictive close for an identity-bound pending epoch with
an existing unaccepted close request, even if its current report is closed.
Retire prior MSC proof and establish a new close boundary; require a later matching
closure report, then a new MSC request and later exact-MSC report. Readback alone
never establishes command acceptance. A successful fallback close may retain its
accepted request provenance without completing the whole application.

Existing accepted-close omission, legacy non-live paths and trusted-closed startup
without a close boundary remain. Manual/Force, Remote EMS, current reader/identity,
latest boundaries, exact settlement and independent restrictions remain binding.
Dashboard telemetry/last-applied snapshot separation is not changed. No universal
MSC-error resolution or physical acceptance is claimed.

## Preparation scope and checks

Only the five established version markers change: app/main.py, app/optimizer.py,
sigenergy_optimizer_addon/config.yaml, build.yaml and buildstamp.txt. Six release,
status and contract documents reconcile the source merge and pending release.
No additional control code, tests, settings, dependencies, workflow or AGENTS change.

Before the repair, both primary false/timeout regressions failed. After repair,
the new module passed 11 tests / 24 subtests, existing applicable modules passed
166 tests / 171 subtests, and the full guarded source suite passed
**1,643 tests / 1,630 subtests**, zero failures (206 warnings, 278.26 seconds).
Independent source/test/docs/scope reviews GO. These are retained source-stage
results; a full suite is not repeated for version literals and release documents.
Dotenv stayed disabled, with 75 memory / 2,047 isolated temporary stores only.

Disjoint guarded release runs passed **16 version/source-pinning tests** and
**42 MSC runtime tests / 61 subtests**, zero failures. The runtime selection covers
failed-close recovery, settled-epoch reuse and settlement evidence (202 warnings,
3.12 seconds; zero memory / 77 isolated temporary stores). Static checks created
no stores. Dotenv remained disabled in both runs. Independent metadata/docs/scope
review is GO; final candidate binding is recorded outside the candidate tree.
No future commit or image digest is claimed.

## Installation and live acceptance

Latest published release is .86. Latest supplied installed identity remains .85,
source `72bd1fdfdc824b019a5eba43f991e3ef0ee5bbe1`, at 07:25:16 AEDT on
29 October. No .86 startup or physical recovery evidence has been supplied.
Expected startup lines after a separately authorized installation are:

```text
Runtime signature=2.3.75-haos86
Container source commit=74f21875e9a30e561d78644c4a5b0791becccc83
```

Monitor-only review must compare report timestamps, accepted close/MSC requests,
application outcomes and coherent flows. Offline dry-run uses fake HA and isolated
storage. Supervised live verification must show later accepted close/MSC proof,
recovery from pending to successful application, fresh status and effective
independent limits. Service success alone does not prove physical settlement.
Do not deliberately induce a communication fault on the live system for this check.

Keep Manual/Force and existing physical protections available. Stop the supervised
trial on unexpected ownership, failed restrictions, untrusted settlement, repeated
command failure or renewed oscillation. Retain operator control and capture logs/
trace without changing physical limits. A usable operator backup/reinstall path
is required for live rollback; retaining an immutable image does not prove one.
Installation and settings remain separate authority. Auto update was confirmed off
on 29 October and was not changed by this work.

Risk is an extra restrictive close and renewed evidence wait after a failed close.
Repeated command/report failure must still prevent automatic permission recovery.
Source rollback is a reviewed scoped revert preserving unrelated work. Preserve all
unfinished worktrees and runtime data. Protected database contents were never read;
no HA query or setting change was performed during publication or receipt work.
