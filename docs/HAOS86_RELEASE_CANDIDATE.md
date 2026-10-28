# HAOS .86 local release candidate

**2.3.75-haos86 is not published.** Local preparation branch:
`release/2.3.75-haos86`, `C:/Projects/sigenergy_optimizer-release-haos86`.
No metadata commit, tag, image build/digest, release or installation is claimed.
Do not use release.sh. Publication requires separate authorization of the final tree.

## Verified source

[PR #63](https://github.com/Belot77/sigenergy-optimizer/pull/63), reviewed head
`bdf4108e11f7c04b3811f12bcb54e6fff9504403`, merged normally at
`b294f463e9fd4a2cbb6e1266e7d922422067e318` on 29 October at 08:55:56 AEDT
(28 October 21:55:56 UTC). Parents are
`4ba817315f45fdbf47077d1095f1f0a2033a7316` and the reviewed head. Merge tree
`35c9b314047dc77da08af366e469a1be723b840a` equals the reviewed source tree.
The eventual container source must be the future verified metadata/tag commit,
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

## Publication and live acceptance gates

Latest published release is .85, tag `v2.3.74-haos85`, source
`72bd1fdfdc824b019a5eba43f991e3ef0ee5bbe1`, index
`sha256:68a15730cd18592d153a27f29e4e801c5581c28680e86c299cdd9f478c120329`.
Supplied startup logs confirm that installed identity at 07:25:16 AEDT on
29 October. No .86 installation or physical recovery evidence exists.

After separate publication approval, bind the exact metadata/tag source, existing
image workflow, both amd64/arm64 images, version/latest digest, layer integrity,
source bytes/modes and generated source pin. Revalidate retained immutable .85
integrity; merge metadata normally and publish the release only after proof.
Auto update was last reported off on 28 October and must be reconfirmed before
publication. Installation and live settings require separate authority.

Monitor-only review must compare report timestamps, accepted close/MSC requests,
application outcomes and coherent flows. Offline dry-run uses fake HA and isolated
storage. Supervised installation needs actual runtime/source identity, effective
limits, stop conditions and a usable operator backup/reinstall path. No such live
rollback path is demonstrated by retaining an immutable image alone.

Risk is an extra restrictive close and renewed evidence wait after a failed close.
Repeated command/report failure must still prevent automatic permission recovery.
Rollback now is withholding publication; later source rollback is a reviewed scoped
revert preserving unrelated work. Preserve all unfinished worktrees and runtime
data. Protected database contents were never read; no HA query or setting change
was performed during preparation.
