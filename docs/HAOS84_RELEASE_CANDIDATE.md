# HAOS .84 published release and verification receipt

**2.3.73-haos84 is published.** [GitHub release](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.73-haos84)
published 28 October 2026 at 03:51:01 UTC. A fresh postpublication check confirmed
it as the latest stable release. Source/image identity is verified. Installation,
live settings and physical acceptance remain separate and were not performed.

## Exact Git and build identity

- Repository: https://github.com/Belot77/sigenergy-optimizer.
- Annotated tag `v2.3.73-haos84`, tag object
  `08d99772d95cd4101c83cb7f2a9ab9d26eae174e`.
- Peeled tag/container source: `bc1439120ab6c68d5983768ffd678bb62fedefb8`.
- Reviewed/tagged tree: `8ae40a1ef597ce3e07578e1fddb2483910337d35`.
- Charge-readback [PR #55](https://github.com/Belot77/sigenergy-optimizer/pull/55)
  merged at `223ac22356fcb0fc3e8f21aaa639b2fc013165c1`.
- Boost-helper [PR #56](https://github.com/Belot77/sigenergy-optimizer/pull/56)
  merged at `de29a8754c6707cc8ead0497d12290ddaf31aa57`.
- Combined MSC source [PR #57](https://github.com/Belot77/sigenergy-optimizer/pull/57),
  reviewed head `4b71f54a66fd4556675b9289f6f003463de4d971`, normally merged at
  `61f17278499467ee79c7c4a4e1c7733517154400`.
- Metadata [PR #58](https://github.com/Belot77/sigenergy-optimizer/pull/58)
  normally merged at `f7025eac808534428035d8dd7d842661da1ae18e`, 03:50:43 UTC, parents
  `61f17278499467ee79c7c4a4e1c7733517154400` and `bc1439120ab6c68d5983768ffd678bb62fedefb8`.
  Its merge tree exactly equals the reviewed/tagged tree.
- [Build 40628165315](https://github.com/Belot77/sigenergy-optimizer/actions/runs/40628165315)
  succeeded at the exact source. Job 122617996556 ran 03:42:00-03:43:59 UTC.

Release preparation on `release/2.3.73-haos84` in
`C:/Projects/sigenergy_optimizer-release-haos84` changed exactly five established
version markers (FastAPI, optimizer signature, add-on config, build label and
buildstamp) plus five release/status documents. Canonical review confirmed one
version substitution per marker and no additional control behavior changes.
No tests, dependencies, workflows, permanent instructions or runtime data changed
in release preparation. Do not use `release.sh`.

Final receipt branch `docs/haos84-publication-proof` in
`C:/Projects/sigenergy_optimizer-haos84-publication-proof` starts at the normal
metadata merge and changes only README, CHANGELOG, AI_HANDOVER, CURRENT_STATE and
this receipt. All unfinished worktrees remain preserved; no reset, clean,
deletion, overwrite or history rewrite was used.

## Behavior and retained limits

Charge-setting report metadata now includes the ESS charge entity, retaining
exact-state/update correlation and existing freshness/post-command checks.
A currently read trusted persistent Boost mode helper can retain an old report
stamp without resetting qualification solely for that age. Device freshness,
nonfuture chronology, 120-second advancing load qualification, reserves,
Manual/Force ownership and independent limits remain enforced.

Pending MSC reuse retains an already-proven original request instead of resetting
its proof interval with another identical request. Fresh exact MSC, strictly
post-request evidence and request-correlated export closure remain mandatory.
Object/phase/boundary identity and authority are rechecked; proof is consumed only
after successful automatic completion.

Unchanged-ceiling maintenance is separate. Completed commands create only a
candidate. Later fresh actual-reader and joint current authority/mode/export
proof must match the original MSC and export-opening/anchor request boundaries,
identity and unchanged bounded target. Startup can establish one same-value
numeric anchor only after the final live check proves the ceiling already equals
the target; a later matching post-write report is still required. This cannot
reopen a reduced/closed ceiling or increase its target. Continuity/config changes,
failure and cancellation retire evidence; charging owners are rechecked after
added proof awaits. See [the control contract](CONTROL_CONTRACT.md#reuse-of-proven-msc-settlement-for-unchanged-surplus-permission).

Passive `application.msc_settlement` diagnostics use existing reads and scalar
allowlists: bounded request/report chronology, normalized values, metadata status,
rejection reasons and outcome. Each application retains first six/latest six
entries, at most 12 requests and 12 observations, plus counters. No raw HA payload,
config identity or credentials are emitted. Recorder failures cannot change
control decisions. Private reader identity was checked absent from API encoding.

Pending retry/latest-request rules, three-second waits, fallback ordering and
independent restrictions remain unchanged. This corrects reproduced software
cases; it does not prove every historical error shares a cause. Missing,
conflicting, slow or incorrect telemetry can still block safely. Pending retry
churn remains a separate semantic question. Solar feedback allocation, provider
recovery and Solar dip-helper follow-up are not fixed by this release.

## Offline validation and review

Final guarded source suite: **1,574 tests / 1,520 subtests passed**, zero failures,
206 warnings, 268.32 seconds. Focused source checks passed 56 / 41. Dotenv was
disabled before app imports; StateStore constructors were restricted to memory or
isolated temporary paths (75 memory / 1,914 temporary in the full run).
Initial broader failures led to stronger actual-reader provenance and initialization
of two fields in lightweight event-loop fixtures. Existing Solar/event-loop
assertions were preserved. Independent source/safety and docs reviews: GO.
Reviewers did not independently rerun the application suite.

Release/version/source-pinning and focused MSC/Boost checks: **93 tests / 104
subtests passed**, zero failures, 202 warnings, 18.81 seconds. Isolation guards
allowed 0 memory / 116 temporary StateStore constructions. No full suite was
repeated for five single-marker substitutions or this documentation-only receipt.
Independent metadata/scope review: GO.

Author and independent OCI-verifier synthetic runs each passed **73 offline
checks**, including the new diagnostic target, overlays/whiteouts, link/traversal,
digest and exact file-mode checks. Verifier changes retain prior security checks.

## Image and source proof

Version/latest computed index, checked against registry digest headers:
`sha256:ce9f9c1abf04effd9ef33a0bfccc29282f9f81356f617cebd8a6b61e3c36f112` (1,609 bytes). Two runtime descriptors are
linux/amd64 and linux/arm64; two recognized attestations reference those runtimes.
No unexplained platform remains.

| Platform | Manifest SHA-256 | Config SHA-256 | Layers |
| --- | --- | --- | --- |
| linux/amd64 | sha256:bf6f64b45a662932c3d162c1533f8a38043e57b127ea39679fdb610100906b89 | sha256:c04d81f22560b4fad0f663af8ac8ccc851560850d1c248930f6f5a18abcbe54d | 11 |
| linux/arm64 | sha256:d490659650e9d4889aede8ecebab93b11aa163bc60e026df6e9db1d871c3cda7 | sha256:d2e50d98a72d8fb2b785d44f0dad0096d7ad0f9a1d114e492d5d8864241d57e9 | 11 |

Runtime manifests are 2,378 bytes. Config sizes are 10,985 bytes (amd64) and
10,987 bytes (arm64). All 22 compressed-layer hashes/sizes and uncompressed diff
IDs passed. Source/version labels and generated source pin match the tagged source.
All **15 final targets per platform** match canonical tagged Git/generated bytes:

- `/app/.source_commit`: full source SHA plus LF, mode 0644.
- `/run.sh`: exact 0755, including `--no-proxy-headers`.
- `/app/templates/index.html` and `/app/app/main.py`, `optimizer.py`, `models.py`,
  `routers/api.py`, `state_store.py`, `import_topup_ledger.py`, `storage_worker.py`,
  `earnings.py`, `decision_trace_store.py`, `trace_clock.py`, `solar_reentry.py`
  and `msc_settlement_evidence.py`: exact 0644.

Common final-file fingerprint:
`sha256:407064edd5eb3fb4e60de311025d9efa326e1428e4fadf8f79946d629882dfec`.
Algorithm: SHA-256 of sorted absolute image path + NUL + file bytes + NUL.
This proves scoped final files and launch settings, not whole-filesystem
equivalence or physical behavior. Canonical Git bytes avoid Windows CRLF drift.

Full layer proof completed `2026-10-28T03:48:23.022364+00:00`. Default verified TLS and
an anonymous pull token held only in memory were used. Layers stayed in memory;
no container/application was executed. Independent registry/source proof completed
`2026-10-28T03:49:34.512205+00:00`: independently fetched index/manifests/configs,
checked all canonical target hashes/sizes/modes and every author layer-proof entry
against registry descriptors/diff IDs. The independent pass did **not** redownload
full layer bodies; the author verified those. Independent proof review: **GO**.

Previous immutable .83 remains
`sha256:55b20ab7f7e5f6c0c80f9ef0c55fee69537769fe686b8560b2997ea8a9d513b3`.
Fresh postpublication checks passed `2026-10-28T03:51:05.699019+00:00`: latest stable
GitHub release, exact remote tag, normal merge parents/tree, version/latest image
bodies and digest headers all agree. No existing ref was overwritten.

Token-free artifacts remain outside Git at
`C:/Users/belot/AppData/Local/Temp/sigenergy-haos84-proof-0v3fqdn1.wih`.
No logs, runtime data, tokens or binary layers are committed.

| Evidence | SHA-256 |
| --- | --- |
| verify_oci.py | c3cd0bec5dec92a7d82fdc0dde24c2bc4b3e3ce4360fe2167f267567e66b9af9 |
| synthetic_checks.py | d3c4f5fb152e25c5dc441d0cc0d98da46b6ff197df7f5aa45272a25edd2036af |
| synthetic-report-final-v2.json | 9c21248dacd89c7f5105f132d99a29d6114a9022fead8066ec1f5192b8cf00f3 |
| independent-offline-qyk79bpf/synthetic-report-final-v2.json | 9c21248dacd89c7f5105f132d99a29d6114a9022fead8066ec1f5192b8cf00f3 |
| oci-proof.json | 970854c3cba60ec0fbed82eb63b748053179fb9277ed682a7739f58f9d5c1b1e |
| independent_check.py | 65d5251a1e69493489281f0dce3328ba2b73b7752f395e7b1e4bac2a200f541e |
| independent-proof.json | ab078056e0d9c2415432eed3e14d68662c5f62b2c5294aa6b2cb305f86347c1c |
| postpublication_check.py | 73d8632a7a6a268b8d0122759e71c160d5346f1b1ec05867c180283a9a3af0fc |
| postpublication-proof.json | f6e86bb00d8a3d758e1eec7fc2da5f32ab598e5feaa39b2abb51d961bb5dcbcf |

## Installation, live acceptance and rollback

No HA query, installation, restart or live settings change was performed. Latest
supplied startup evidence identified .83 on 28 October; installed .84 identity is
not claimed. Auto update was last confirmed off on 26 October.

Separately approved installation must confirm:

```text
Runtime signature=2.3.73-haos84
Container source commit=bc1439120ab6c68d5983768ffd678bb62fedefb8
```

First inspect monitor/dry-run decisions and diagnostics, then use separately
approved live observation to compare command/request times, distinct fresh
readbacks and later coherent flows. Check Morning-to-Solar ownership, unchanged
ceiling maintenance, genuine failure closures/recovery and Boost qualification.
A successful service call or passed test does not establish physical settlement.
Morning numeric precision, inverter report cadence, periodic reassertion needs
and physical stability remain unverified.

Source rollback is a reviewed scoped revert. Live rollback requires a verified
backup/reinstall path and separate approval; no runtime archive/database should
be overwritten. Protected database contents were never opened: metadata remains
147,456 bytes, mtime_ns 1793003351955462200. Four preserved unfinished worktree
file-set hashes were rechecked unchanged after publication preparation.
