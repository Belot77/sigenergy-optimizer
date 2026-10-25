# HAOS .80 published release and verification receipt

**2.3.69-haos80 is published.** [GitHub release](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.69-haos80)
published on 26 October 2026 at 10:20:09 Sydney (25 October 23:20:09 UTC).
It is the latest stable release. Publication and scoped image/source identity are
verified; HA installation, live settings and physical acceptance remain separate.

## Exact Git and build identity

- Tag: `v2.3.69-haos80`.
- Tag/container source: `acb576747e808e927bdd7d12346c507da9b188b6`.
- Approved/tag tree: `14103ec71d3b41ad6a85e2d8a149e3db705606bf`.
- Metadata [PR #44](https://github.com/Belot77/sigenergy-optimizer/pull/44), normal
  merge `77bde899da35b2f933304192a9c7226d9e5e9ef3` at 10:19:24 Sydney
  (25 October 23:19:24 UTC). Both parents, source merge `bcd9fe51...` and metadata
  source `acb57674...`, were verified; the merge tree exactly equals the tag tree.
- [Build 40243683190](https://github.com/Belot77/sigenergy-optimizer/actions/runs/40243683190)
  completed successfully at the exact tag/source. Build job ran 10:12:20–10:14:27
  Sydney (25 October 23:12:20–23:14:27 UTC); image push finished at 10:14:21 Sydney.

Reviewed logging source `512601da8083f88a260e343dd980c2c14183c814` normally merged
through [PR #43](https://github.com/Belot77/sigenergy-optimizer/pull/43) at
`bcd9fe51f7303467ed8e463805c30284110e6a95`, 10:00:11 Sydney on 26 October,
retaining exact reviewed/tested tree `70805bd6f1f49eb47654b7c686c6a8d904371d13`.

Release preparation changed only five established version markers plus six
documents. Markers: FastAPI version in `app/main.py`, runtime signature in
`app/optimizer.py`, add-on `config.yaml`, `build.yaml`, `buildstamp.txt`.
No further production/test/control-contract/configuration-value/workflow change
was bundled. Final receipt branch `docs/haos80-publication-proof` in
`C:\Projects\sigenergy_optimizer-receipt-haos80` starts at metadata merge
`77bde899...` and changes those six documents only. No branch was deleted;
all original unfinished workspaces and protected data remain preserved.

## Published behavior and limits

Previously, successful HTTP INFO could occupy all 500 UI records; the supplied
log contained only successful requests spanning 84 seconds. The merged filter
excludes recognized successful 2xx `httpx` INFO requests from the UI handler only.
Non-2xx, unknown formats, other loggers and warning/error messages retain their
existing behavior. Filtering fails open on unknown formats/errors and does not
mutate shared records. Console/other handlers, global levels and inverter control
are unchanged. Custom/lowercase method tokens outside the recognized pattern
remain visible.

The newest-first ring still holds at most 500 retained records in process memory.
Later retained messages may evict errors; restart clears the buffer. This is not
persistent logging or recovery of lost history, and console logging volume remains
unchanged. It does not explain the trace's 65 application failures / 59 unsuccessful
fallbacks, change retries/MSC settlement or prove that a particular command failed.
Raw logs, traces, proof artifacts and image layers remain outside Git.

## Offline validation

Tests-first reproduction: 16 failed / 10 passed. Independent refined logging
module: all 30 cases passed. Retained combined logging, HA-client, ingress,
application-outcome and fallback checks: **122 tests / 10 subtests passed**, zero
failures, 202 existing warnings, **68.94 seconds**. Independent source/test/docs
review is GO. Source-fix syntax, exact six-file scope, whitespace/EOF and API AST
comparison passed. Removing only the filter class/attachment restores baseline
API AST; all 500 supplied successful messages were recognized offline.

All **46 release/source-pinning/logging checks passed**, zero failures,
202 existing warnings, **10.69 seconds**: sixteen release/source-pinning checks
and thirty logging cases. Canonical comparison proved five one-marker
substitutions plus six docs, with no other source/test/workflow drift. Existing
formatting was preserved. Independent release metadata/documentation review is GO.
No full suite was repeated for this narrow logging fix, markers or receipt docs;
the .79 full-suite result remains historical.

The successful build reported non-blocking action/runner deprecation annotations
(Node.js 20 actions forced onto Node.js 24 and the ubuntu-latest migration).
No workflow update was included; these are separate maintenance follow-ups.

## Registry and image/source proof

Registry: `ghcr.io/belot77/sigenergy-optimizer`. Version `2.3.69-haos80` and `latest`
resolve to index:

`sha256:91120b1039eec3915a37c6ff1a1210cf1cf5e79d97e3e1d9de31207206301a5a`

| Platform | Manifest | Config |
| --- | --- | --- |
| linux/amd64 | `sha256:e6e6fe4c7db4cf5e93c6f5da524a616edaccdde38fe5ff043efaa040e386f8d6` | `sha256:fceff0356270a3ae8815f0e0cea0d7ca0a3f508ddcc1ec2807b47ca3e61b4672` |
| linux/arm64 | `sha256:e962b43eaa789bc6f8cd01bcef99a4ac34316a3023be9a42f9ec396c06076ae5` | `sha256:e13d1a8c724689ae4836645b8956e906afa611393e0835f77404504fa734b6e2` |

Both configs identify version `2.3.69-haos80` and full revision
`acb576747e808e927bdd7d12346c507da9b188b6`.
Each contains eleven layers: all **22 compressed hashes/sizes and uncompressed
diff IDs** were verified. Safe in-memory overlay reconstruction checked fourteen
exact tag targets per platform:

`/app/.source_commit`, `/run.sh`, `/app/templates/index.html` and eleven under
`/app/app/`: `main.py`, `optimizer.py`, `models.py`, `routers/api.py`,
`state_store.py`, `import_topup_ledger.py`, `storage_worker.py`, `earnings.py`,
`decision_trace_store.py`, `trace_clock.py`, `solar_reentry.py`.

Source pin is full tag SHA plus LF. Launcher matches tag bytes at mode 0755 and
includes `--no-proxy-headers`. Both configs have `Cmd=["/run.sh"]`, no entrypoint,
working directory `/app`. Shared fourteen-file fingerprint:

`sha256:386444cfc2defee474052cc86cb473059d8f1551d67ad49832e4e352fd382cf4`

Fingerprint algorithm: SHA-256 of sorted absolute image path, NUL, bytes, NUL for
each target. Exactly two explicitly annotated unknown/unknown attestation
descriptors were excluded; no unexplained runtime platform was ignored.

Complete proof finished at 10:16:40 Sydney (25 October 23:16:40 UTC).
Helper SHA-256: `cb00b3c3d488d885a59d5824a8fda7d323570bcb7bfc79450ec7398720e59e57`.
Proof JSON SHA-256: `2dec3ad41cbe0a7fd349bec52bfd6f09e5eed9b59f23ccd43bf43ae615766ed4`.
Independent review GO at 10:17:09 Sydney verified the exact three-constant helper
adaptation, independently reran all **68 synthetic cases**, and reconciled both
platform manifests/configs, all 22 descriptors/diff IDs and fourteen Git target
hashes/sizes/modes. Complete blob/overlay proof relies on the reviewed helper
execution; the reviewer did not duplicate full layer downloads. Normal verified
TLS and public anonymous registry access were used; token stayed in RAM only.
No filesystem extraction or container execution occurred. This establishes scoped
source/image identities, not full-filesystem equivalence, runtime operation,
in-situ HA compatibility or physical inverter settlement.

Previous [2.3.68-haos79](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.68-haos79),
source `ea516ef6cabd9918dbea675694a9de3aa207c8af`, retains immutable index
`sha256:cbaa5f68e4830737abba90666e486b9db848b3a853d1c9138c33a93f3b02bdad`.
A fresh public pre-merge check at 10:17:55 Sydney verified .80/latest and .79
header digests against computed response-byte SHA-256.
A separate public post-publication check at 10:23:31 Sydney on 26 October
(25 October 23:23:31 UTC) reconfirmed release status/source, tag tree, both
.80/latest indexes and unchanged immutable .79, including response-byte hashes.

## Historical preparation and approved publication

Local preparation on `release/2.3.69-haos80` in
`C:\Projects\sigenergy_optimizer-release-haos80` began at verified main
`bcd9fe51...`. The .80 tag/release/remote branch and registry version were absent
at preflight; .79/latest matched the preserved index above. These absence checks
are historical and superseded by completed publication.

The operator approved exact metadata tree, commit/push/PR, tag/build, source/digest
verification, normal metadata merge, GitHub release and final receipt/normal PR
merge. Source was tagged, both platforms verified, PR #44 normally merged with
exact tag tree, then GitHub release published. Branch pushes alone do not build
images under the unchanged tag-only workflow. Auto update was last confirmed off
on 26 October before .79 publication; no later change was reported, and no direct
HA query was performed.

## Installation, acceptance and rollback

No .80 installation, live setting change or physical acceptance was performed.
The operator previously reported .78; last supplied full startup/source proof
remains historical .75. After separately approved installation, expect:

```text
Runtime signature=2.3.69-haos80
Container source commit=acb576747e808e927bdd7d12346c507da9b188b6
```

Read-only UI/download checks should show app diagnostics without routine successful
polls; console output remains unchanged. Confirm errors/warnings remain visible.
Controlled failure cases belong in offline/fake-HA tests; do not provoke live
actuator or HTTP failures just to test logging. Read-only/monitor/dry-run comparisons
should retain existing control outcomes, request frequency, authority and settlement
behavior. This diagnostic update grants no new control or Boost permission.

Before installation retain a binary- and data-aware rollback plan, preserving
ledger/database coverage and trace history/protected clock epochs. An immutable
older image alone does not establish a data-compatible downgrade. A source rollback
requires a scoped reviewed revert; no live downgrade or restoration is performed.

O18 fill strategy, O5/O9 reserve/settings review, broader O6 depletion/floor
questions, parked O11 and existing physical/Boost acceptance remain open. Battery
floors, export/import policy, relief tolerances and retries are unchanged.
