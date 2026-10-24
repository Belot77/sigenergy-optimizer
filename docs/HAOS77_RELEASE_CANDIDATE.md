# .77 combined safety and clock-recovery release candidate

Status: reviewed source merged; release metadata in preparation, 24 October 2026. Candidate version `2.3.66-haos77`, tag `v2.3.66-haos77`. The user approved completing the O14, O16 and O10 clock-recovery changes through source PR, normal merge, tag/build verification and GitHub Release. Installation and live acceptance remain separate operator actions.

## Candidate identity and scope

Workspace: `C:\Projects\sigenergy_optimizer-release-haos77`, branch `fix/combined-safety-trace-recovery`, based on main `e387010b83f7b017460870b1b456025f49f7e0a5`. Reviewed source `f4cc6ae80df2d279cfef067f1ddd957916f8b3fc` was normally merged by [PR #34](https://github.com/Belot77/sigenergy-optimizer/pull/34) at `b4377de9f38d1c305c23a0b1dca9cb509afc1a9f` on 24 October 2026 at 01:46:14 UTC (12:46:14 Sydney). Both trees are `a8fc3a00fc7b0a9c0108b5123b5e7850bf1be9dd`. The release branch `release/2.3.66-haos77` starts from that merge. This step changes exactly the five synchronized version markers and release/status documentation; no control or trace logic is added. No version tag, build, OCI digest or GitHub Release identity is recorded yet. Combined source review and offline verification are complete; publication identities remain pending.

The combined candidate contains:

- **O14 configuration activation:** validate, persist and activate single/batch configuration under the existing control lock; recheck queued mutation authority and route direct ESS writes through the lock; retire identity-bound evidence before refreshing the entity watchset. Existing Manual/Force, ESS override, pending-MSC close barrier and Standby-floor behavior are retained.
- **O16 import ledger:** preserve each interval's original energy, tariff, trust and source; atomically persist intervals, checkpoints and coverage; retry identical immutable payloads; keep unresolved history unknown. Applicable automatic battery-backed/mixed sales can remain paused beyond the current day. Manual/Force and independently qualified PV-only permissions retain their separate behavior. See [ledger behavior and rollback limits](IMPORT_LEDGER_INTEGRITY.md).
- **O10 clock recovery:** implemented and reviewed. Two fixed certificate-verified HTTPS origins corroborate current UTC through a worker-only subprocess with a twelve-second parent deadline, including DNS. Full old segment bytes and the completed-attempt status snapshot are durably preserved in an immutable history epoch before a new anchor permits normal active 24-hour pruning. The requirement for independent proof survives application restart. Failure leaves writes/pruning guarded, gap evidence remains sticky, and historical snapshots remain outside normal downloads. No optimizer control rule or system clock changes. See [recovery details and limits](TRACE_CLOCK_RECOVERY.md).

O15 synchronous storage execution and O17 conditional ingress exposure are outside this candidate. O11 remains parked. O5 reserve policy and applicable Phase 1/2 physical evidence gates are unchanged. Reopening O10 clock-recovery work does not reopen the parked archive/MSC incident investigation or establish HDD causation.

## Validation status

Final combined offline validation passed **1,275 tests / 1,305 subtests**, zero failures, 206 existing warnings, in 226.40 seconds. Independent source/test/documentation review was GO with no High/Medium blocker; reviewers did not execute tests or access HA. Tests-first characterization reproduced both clock recovery defects and the integration accounting gaps before correction. The 15 combined-boundary tests pass, and the five focused trace suites passed 84 tests / 36 subtests (202 warnings, 11.22 seconds). A smoke check of the exact bounded subprocess/parent proof path succeeded against both fixed public HTTPS sources; this is development-host network evidence, not HA-network or physical acceptance. Original O14/O16 worktrees and the frozen trace candidate remain preserved. Separate component full-suite results below remain historical evidence. No HA or physical acceptance result is claimed.

Release-specific checks passed all 16 tests in 9.35 seconds. Normalized comparison confirms exactly five version substitutions and no other production drift.

## Version and publication sequence

The five synchronized version markers are owned by the release-preparation step: `app/main.py`, `app/optimizer.py`, `sigenergy_optimizer_addon/config.yaml`, `sigenergy_optimizer_addon/build.yaml` and `sigenergy_optimizer_addon/buildstamp.txt`. Set all five to `2.3.66-haos77` only after the reviewed combined source is merged to `main`.

1. Finish trace implementation and independent review; run the final combined test suite and exact source-scope checks. Record the exact source candidate tree and changed-file hashes.
2. Commit and push the combined source branch, open a review PR, and normally merge it. Verify the merge tree contains the exact reviewed candidate and recheck `main`.
3. Create a release-metadata branch from that merged source. Change only the five version markers and approved release documentation. Run release-version consistency and add-on source-pinning checks; verify normalized production diff has exactly the five marker substitutions.
4. Review and push the metadata branch and open its PR. Push `v2.3.66-haos77` only at the exact metadata candidate commit. Tag push triggers the repository's multi-architecture build and updates version, major/minor and `latest` image aliases.
5. Require successful amd64 and arm64 builds. Verify the OCI index and both platform manifests, version/revision labels, `/app/.source_commit`, and embedded application bytes against the exact tag. Reconfirm the immutable `.76` version-specific index is unchanged. Do not infer source identity from a successful workflow alone.
6. After image verification, normally merge the release-metadata PR and prove the merged tree matches the tagged candidate. Publish the GitHub Release for that verified tag, then independently verify release and registry identities. Record all actual commit, PR, run, digest and release values below.

## Publication receipt (pending)

| Item | Verified value |
| --- | --- |
| Combined source commit and merge PR | `f4cc6ae80df2d279cfef067f1ddd957916f8b3fc`; [PR #34](https://github.com/Belot77/sigenergy-optimizer/pull/34); normal merge `b4377de9f38d1c305c23a0b1dca9cb509afc1a9f`, tree `a8fc3a00fc7b0a9c0108b5123b5e7850bf1be9dd` |
| Release-metadata commit and PR | Pending |
| Tag/source SHA and tree | Pending |
| Actions run and amd64/arm64 result | Pending |
| OCI index, platform manifests and configs | Pending |
| `/app/.source_commit` and embedded-file comparison | Pending |
| Prior `.76` immutable version index reconfirmed | Pending |
| GitHub Release URL and publication time | Pending |

## Operator installation and rollback guidance

The operator reported .76 installed after replacement-SSD restoration on 24 October. The latest full startup/source proof remains .75; the report does not verify current runtime identity, effective settings, control state or physical behavior. No .77 installation is part of this release work.

Before any later installation, a verified Home Assistant backup is recommended. Confirm the installed version/source and effective settings, supervision and a usable restore path. On startup, O16 coverage may be unknown until reconciled or a naturally observed, continuous known-inactive midnight boundary establishes a covered day. Do not fabricate coverage or infer physical export from a request, trace or database status.

After .77 writes new ledger tables, an older binary is not automatically safe to run against that database. Never delete, truncate, copy or reprice the new rows to force downgrade. If automatic behavior is unexpected, stop automatic control and retain Manual/Force ownership; preserve the full database and use a separately reviewed binary- and data-aware restore/reinstall plan. Any source rollback after commit is a scoped reviewed revert. Trace-history snapshots are also retained evidence: if their disk budget cannot be met, recovery fails closed rather than deleting old segments automatically.

Publication, test results and artifact verification do not establish physical acceptance, Boost readiness, a cause for the earlier archive/HDD symptoms, or rollback readiness at the operator's installation. O4, O5, O11 and the applicable Phase 1/2 live gates remain separate.
