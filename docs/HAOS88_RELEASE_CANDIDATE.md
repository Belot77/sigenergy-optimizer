# 2.3.77-haos88 publication receipt

## Publication and immutable source

Release [v2.3.77-haos88](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.77-haos88)
was published at 2026-10-30T23:42:25Z (31 October 2026, 10:42:25 AEDT).
Source commit: `41a2a93d27e3bd88146b68c77639f28193b3a565`.
Tagged tree: `e3c7f5b1f31c30ef54902937baf0f9cf59969c60`.
Annotated tag object: `f7b5fd4f204a26c3b6c915c9417ddf54f5085a11`.

Metadata [PR #71](https://github.com/Belot77/sigenergy-optimizer/pull/71)
merged normally at `9579a3dbd7d7efd36367922809d118395f0eafee` at
2026-10-30T23:41:50Z (31 October 10:41:50 AEDT). Its parents are
`2f0725602e339288efd1dbf5be07c229fa575c47` and the source commit above.
Its tree exactly equals the immutable tagged tree.

Source [PR #70](https://github.com/Belot77/sigenergy-optimizer/pull/70) merged
normally at `2f0725602e339288efd1dbf5be07c229fa575c47` on 31 October
10:17:29 AEDT. Its reviewed source tree is
`0c590ec2fa24089af9fda5524fcce34d53746e54`. Release preparation changed only
five established version literals and seven release/status documents.
No further control behavior changed during publication.

## Build and OCI proof

[Build 41145559636](https://github.com/Belot77/sigenergy-optimizer/actions/runs/41145559636)
succeeded at the exact source and completed at 2026-10-30T23:39:25Z
(31 October 10:39:25 AEDT).

Version and `latest` OCI index:
`sha256:cc6759bf5deb23e659083699840237288f744248ec053226acabe46722b7bb39`.

- amd64 manifest: `sha256:116bd5668a8232f734096acde551c2774a662233afc94c839ae18358f7a73447`.
- arm64 manifest: `sha256:0f91b913adde97bd49ab9c78ba05ccc4e4b70b03ebc13a6cc4f6eddf2ebaa4d7`.
- Both platforms passed 11 compressed-layer size/hash and uncompressed diff-ID
  checks, then 15 final source byte/mode checks. The expected launcher and
  source pin matched. Two attestation descriptors correlated to runtime manifests.
- Source fingerprint: `sha256:7bd45c684e98c79b60b20bb6b671b01d8a7191f3deb91304b5606119a2d066fd`.
  Algorithm: SHA-256 of sorted absolute image path, NUL, file bytes, NUL.
- Immutable .87 index remains
  `sha256:b0e703483652a3b5ead7a1eb968f10dee2571c9d613f6d72e29a210c01d790f6`.

The author downloaded and verified all layer bodies without extraction or
container execution. Independent verification fetched registry indexes,
manifests and configs, recomputed source expectations, and compared them against
the author proof. It did not independently redownload full layer bodies.
Both verifications are GO; default verified TLS remained enabled.

The reused OCI helper changed only version and previous-index constants.
Independent helper review is GO. All 73 offline synthetic integrity checks
passed. Post-publication release, remote tag/source, normal-merge parents/tree,
version/latest index and prior immutable index checks are GO.

## Shipped changes and limits

- Morning Dump: after a successfully completed automatic Dump loses trusted
  timed refill feasibility, retire Dump admission for that identified morning
  window. This deliberately reduces later same-window export opportunities.
  A later morning may qualify in-process. The latch is process-local: restart
  loses it, and a fresh decision must pass every current eligibility, authority
  and settlement gate before qualifying even in the same morning. The
  independent 15% floor alone does not trigger retirement.
- Provider recovery: temporary sun/sunset metadata uncertainty can release
  authority and restrictive Solar charging, then restore only unchanged,
  fully revalidated prior evidence from the same source/session before its
  retained deadline. Changed or rejected generations, source/session changes,
  restart, expiry, timestamp regression and local-day rollover retain their
  protections. Earlier observed schedules remain binding. No update is forced
  and provider trust is not persisted.
- MSC opening: an accepted primary MSC request missing the unchanged
  three-second observation wait may enter existing bounded restrictive recovery
  when its subsequent accepted fallback also lacks proof. The nonextendable
  15-second budget begins before the first restrictive close and requires fresh,
  request-correlated close/new-MSC proof. Contradictions retire the attempt.
  Rejected or exceptional calls remain failures. A fallback that fully settles
  during its original short wait still leaves the initiating application failed.
  This adds one narrow recovery origin; other historical MSC failures remain
  unexplained.

Manual/Force ownership, independent physical/capability limits and policy
priorities remain. The operator's Dump 15%, Boost 80%, minimum tomorrow forecast
100 kWh and existing 120-second Boost qualification were not changed.
Command acceptance and reported settings do not establish physical settlement.

## Validation and preservation

The reviewed integrated source passed **1,716 tests / 1,725 subtests**, zero
failures (206 warnings, 283.08 seconds). Focused integration passed 195 / 272.
Release version/source-pinning and focused safety checks passed **211 tests /
272 subtests** across 16 modules, zero failures (202 warnings, 25.62 seconds).
Independent source, interaction, tests, documentation/scope, commit/tag and
publication image/source reviews are GO.

The full suite allowed 75 memory / 2,190 isolated temporary stores; release
checks allowed zero memory / 393 temporary stores. Both rejected zero paths.
Protected database size/mtime metadata remained unchanged; contents were not
read. Dotenv and settings env-file access were disabled. All original production
and characterization worktrees remain preserved. The full suite was not
repeated for literal-only metadata or this documentation-only receipt.

## Installation and remaining work

The release is published and source/image verified for installation readiness.
No .88 installation is verified. Last supplied installed runtime remains
`2.3.76-haos87`, source `6a43077be1a59512bf44b1bb1c41aed410992c37`,
confirmed at 30 October 12:54:06 AEDT and in trace through 31 October 08:39:26.
Auto-update was reconfirmed off on 31 October. No HA query, installation, restart
or inverter/battery/grid/settings action was performed during publication.

After a separately approved installation, supplied startup must identify:

```text
Runtime signature=2.3.77-haos88
Container source commit=41a2a93d27e3bd88146b68c77639f28193b3a565
```

Then correlate requests, later reports and actual flows for Dump retirement and
restart, provider metadata-loss recovery before the original deadline,
Morning-to-Solar charge/export and fill-deadline behavior, accepted MSC recovery
and contradiction rejection, and Boost on an eligible forecast day.
The supplied raw provider payload is absent, so its prior incident's sole
cause remains unproven. These software/image checks do not prove physical
acceptance or guarantee a full battery.

Engineering/policy work remains for O4 Boost qualification retention/stability,
O5 reserve/load/price assumptions, O6 broader floor/depletion behavior and O9
ownership/status semantics. Unexplained legacy O11 and O20 non-positive-price
Morning Dump redesign remain parked. O8's historical observation gap is
irrecoverable; short Demand Window import spikes are deferred and unconfirmed.

Preserve immutable .87. Any rollback needs a separately reviewed scoped revert
or verified immutable reinstall/restore procedure; operator restore readiness
has not been demonstrated here. Each publication report must state shipped
changes, remaining work, missing live proof and the next authorized action.
