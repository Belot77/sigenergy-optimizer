# HAOS .78 local release candidate

Prepared 24 October 2026. Candidate: **2.3.67-haos78**. Published release remains
**2.3.66-haos77**. This document records a local preparation checkpoint; no .78
commit, push, tag, image build, metadata merge, release or installation is claimed.

## Baseline and scope

- Workspace: `C:\Projects\sigenergy_optimizer-release-haos78`.
- Branch: `release/2.3.67-haos78`.
- Verified base/main: `e12da76d9c11e6d92286ecaf9c98a7c3497e0872`.
- Reviewed O15/O17 source: `6deb930da9cfc8e03724405a1bb42f95937f3f25`,
  normally merged by [PR #37](https://github.com/Belot77/sigenergy-optimizer/pull/37)
  on 24 October at 07:40:46 UTC (18:40:46 Sydney).
- Exact tested source/merge tree: `5a63925bc07dc6ccf93a3b9d5f4f5b2e57d0b2b7`.
- Preparation changes only `sigenergy_optimizer_addon/config.yaml`,
  `build.yaml`, `buildstamp.txt`, the runtime signature in
  `app/optimizer.py`, the API version in `app/main.py`, and release/status docs.
  Control logic, authentication predicates, worker implementation, tests,
  dependencies, permanent instructions and build workflow remain unchanged.
- All original unfinished worktrees remain preserved.

## Resulting behavior and limits

O15 moves production SQLite work to one bounded worker while the event loop owns
ledger observations and exact acknowledgements. Busy, failed or unconfirmed
storage retains unknown-cost protections. API responses distinguish rejected
admission from accepted mutations with an unconfirmed outcome; an accepted write
can finish after timeout, so refresh state before retrying. Threads cannot kill
wedged OS I/O, and the API's wait limit applies per database wait, not per endpoint.

O17 requires actual Supervisor transport peer `172.30.32.2` and nonempty
`X-Ingress-Path` for the existing ingress API-key exemption. Both supported
launchers disable Uvicorn proxy-header rewriting. Normal HA login and existing
strict/key/read/status policies keep their boundaries. Custom proxies use the
existing API-key path. This does not secure an independently exposed listener,
establish installed exposure/flags, or authorize broader proxy trust.

The .77 configuration transaction, immutable ledger and trace clock-recovery
protections are retained. Unknown history can pause applicable automatic battery
sales beyond the current day; separately qualified PV-only and Manual/Force
semantics remain distinct. No threshold, export limit, MSC settlement, control
authority, inverter setting or Boost policy is changed. Ordinary runtime Logs
availability and historical HDD/trace/MSC causation are not established as fixed.

## Verification checkpoint

Retained merged-source results: **1,355 tests / 1,305 subtests passed**, zero
failures, 206 existing warnings, 232.02 seconds. Five focused modules passed
126 / 8 (202 warnings, 13.54 seconds). Independent combined source/test/docs review
was GO with no High/Medium blocker; the reviewer did not rerun tests or access HA.

All **16 release-marker/source-pinning checks passed in 9.58 seconds**.
Normalized comparison confirmed exactly one version replacement per marker file:
five substitutions plus seven targeted release/status documents, twelve files
total, with no other source/test/workflow drift. Independent release-metadata
review is **GO**, with no High/Medium blocker. The reviewer checked source/doc scope
without rerunning tests or accessing HA. The full source suite was not rerun for this marker/documentation-only
preparation; its existing result above remains separately attributed.

## Publication sequence requiring separate approval

1. Freeze the reviewed metadata tree, commit and push only this release branch,
   then create a release-metadata PR. Do not use `release.sh`.
2. Tag `v2.3.67-haos78` at that approved exact source commit and push that
   exact tag only. The tag-triggered workflow publishes version and `latest` images.
3. Verify Actions source/status, version and latest OCI indexes, both amd64/arm64
   manifests and labels, compressed layers/diff IDs, `/app/.source_commit`
   and the changed application/launcher bytes against the exact tagged source.
4. Only after image verification, normally merge the release-metadata PR and
   verify its tree equals the tag. This advertises the available HA update.
   Publish the GitHub Release and record the full receipt.
5. Installation and live settings changes remain separate operator actions.

No tag/image/release is claimed before these actions complete. Do not replace an
existing tag or image identity. Preserve immutable .77 version index
`sha256:0a743b4f32c0df7cd87d387f8870435d71ee5330f11c77999305cd665dd9e883`;
its source is `7aa712f72ca2c0467e6740e3cb0f2191ba8d077e`.

## Operator acceptance and rollback

The operator reported .76 installed after replacement-SSD restoration on 24 October.
Last full supplied startup/source proof remains .75. The fresh 24 October archive
shows partial persistence only, without runtime identity or another-restart proof.

After separately authorized publication, install through normal HA procedures
with a usable backup/restore method. Verify runtime `2.3.67-haos78` and
the full container source commit against the final tag before acceptance.
Keep Boost off during initial identity, configuration and cadence checks.
Monitor-only/dry-run checks should verify ordinary HA ingress access, denied
spoofed-header requests using synthetic authorized clients, bounded storage
failure behavior, fresh traces and honest unknown-cost state without changing
inverter controls. UI authentication checks need no live dispatch.

Any supervised control acceptance must retain current authority, independent
limits, Manual/Force priority, observed MSC settlement and explicit stop conditions.
O5 reserve policy, O11 parked follow-up and applicable live gates remain open.

Before commit, withhold this candidate to retain the published baseline. After
commit, use only a separately reviewed scoped revert. Preserve the complete
database, O16 interval/coverage data, trace segments and protected clock epochs.
Do not delete, truncate, reprice or fabricate coverage. An older binary is not
automatically ledger-safe; any installed downgrade needs a binary- and data-aware
restore/reinstall plan. No live installation or downgrade is performed here.

See [storage boundaries](STORAGE_EXECUTION_ISOLATION.md),
[ingress boundaries](INGRESS_TRUST_BOUNDARY.md),
[ledger rollback limits](IMPORT_LEDGER_INTEGRITY.md) and
[trace recovery](TRACE_CLOCK_RECOVERY.md). Passing tests does not prove physical
settlement, installed topology, disk health or recovery across another restart.
