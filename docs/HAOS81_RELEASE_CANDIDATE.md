# HAOS .81 published release and verification receipt

**2.3.70-haos81 is published.** [GitHub release](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.70-haos81)
published 26 October 2026 at 18:24:39 Sydney (07:24:39 UTC). It is the latest
stable release at the postpublication check below. Source/image identity is
verified; installation, live settings and physical acceptance remain separate.

## Exact Git and build identity

- Repository: `https://github.com/Belot77/sigenergy-optimizer`.
- Tag: `v2.3.70-haos81`; annotated tag object
  `34230f7d1f33122615f369f7ed925e33f46e031a`.
- Peeled tag/container source: `247095a4f9905932c3f5716f3d1be6cee7b3c7f8`.
- Approved/tag tree: `8a49610bcaee9fc41390c96580710136831a3ffe`.
- Metadata [PR #47](https://github.com/Belot77/sigenergy-optimizer/pull/47) normally
  merged at `f2a2d9a4b77ba6ce8e8ef40d419a6abe56f7d55f`, 18:24:19 Sydney
  (07:24:19 UTC). Parents are source merge `ff5993a7fd56e228bd1e776df1447cc085d5a8a5`
  and metadata source `247095a4f9905932c3f5716f3d1be6cee7b3c7f8`; merge tree
  exactly equals the approved/tag tree.
- [Build 40284898464](https://github.com/Belot77/sigenergy-optimizer/actions/runs/40284898464)
  succeeded at the exact tag/source. Build job `121446137938` ran
  18:17:34-18:19:21 Sydney (07:17:34-07:19:21 UTC); image push finished
  at 18:19:12 Sydney (07:19:12 UTC).

Reviewed source `6ad0175dd824e930954294b4a8a71f4524588dd5` normally merged
through [PR #46](https://github.com/Belot77/sigenergy-optimizer/pull/46) at
`ff5993a7fd56e228bd1e776df1447cc085d5a8a5`, 17:35:44 Sydney (06:35:44 UTC),
preserving reviewed/tested tree `a8eead0542ea3cacac6d85532a73a6c16362f467`.

Release preparation on `release/2.3.70-haos81` in
`C:\Projects\sigenergy_optimizer-release-haos81` changed five established
version markers only: FastAPI version, optimizer runtime signature, add-on
`config.yaml`, `build.yaml`, `buildstamp.txt`; plus six release/status documents.
No additional production, test, configuration-value, workflow, dependency,
archive-store or control-contract change was bundled. Final receipt branch
`docs/haos81-publication-proof` in `C:\Projects\sigenergy_optimizer-receipt-haos81`
starts at metadata merge `f2a2d9a4...` and changes only README, CHANGELOG,
AI_HANDOVER, CURRENT_STATE, ROADMAP and this receipt. All original branches and
unfinished work remain preserved. Do not use `release.sh`.

## Behavior and evidence limits

New trace rows distinguish requested charge ceiling from the pre-application
reported ESS charge setting and direct measured battery power. Five measured
flow observations retain their individual report timestamps and freshness flags.
Signed aggregate balance and Solar feedback boundaries help explain relief
reset/requalification and command-response uncertainty. Existing application
outcomes remain separate from these observations.

This is passive diagnostic evidence. It adds no HA request or actuator write,
changes no control target, tolerance, ownership, settlement or fallback rule,
and does not correct Solar allocation. The current negative aggregate balance
still rejects relief; permitted normal charging recovery remains in place.
The existing .80 UI log-retention filter is included unchanged.

ESS provenance comes from existing bulk metadata, which may appear stale.
HA report timestamps do not prove simultaneous physical sampling. Feedback
timestamps identify the armed Solar command boundary, not all successful writes
or physical settlement; recording can precede later failed-tick cleanup. Reported
setpoints and successful helper outcomes do not establish actual inverter response.
Missing data remains unknown. Historical trace rows are not backfilled.
See [the durable evidence contract](CONTROL_CONTRACT.md#passive-charge-allocation-evidence).

The supplied -74 W aggregate/+2 W direct sample does not justify a new meter-error
tolerance. O18 fill strategy/allocation, O5/O9, broader O6, parked O11 and existing
physical/Boost acceptance remain open. No unsafe-flow cause or physical energy
loss is inferred from the sampled trace or screenshot.

## Offline validation

Retained source validation: **204 tests / 196 subtests passed**, zero failures,
202 existing warnings, 42.15 seconds. Focused evidence/outcome checks passed
19 / 22 in 1.23 seconds. Eight new evidence tests cover readback provenance,
zero versus unknown, malformed values, failure isolation and archive round-trip.
Independent source/test, documentation and staged-scope reviews are GO.
Mechanical AST comparison confirmed baseline control code after removing only
the approved passive additions. These are source results, not physical proof.

All **54 release-marker/source-pinning/evidence/logging tests / 12 subtests
passed**, zero failures, 202 existing warnings, in **13.86 seconds**. Settings did
not load dotenv; bytecode and pytest cache were disabled. Source-pinning cases
use local Git fixtures, and evidence/archive checks use fake HA and temporary
storage. No full suite was repeated for marker/documentation changes.
Normalized byte comparison confirmed exactly five single-marker substitutions
plus the six stated documents, with no other source drift. Independent metadata/
documentation review was GO. This final receipt does not change executable code.

## Image and source proof

Version and `latest` computed OCI index, matching registry digest headers:
`sha256:e3f58087681c0c08ab53b0b8263387e8388d0916796aea326fdf9344ba821526`
(1,609 bytes). Both linux/amd64 and linux/arm64 runtime descriptors are verified;
two recognized attestation descriptors are accounted for, not mistaken for
runtime platforms. No unexplained runtime platform descriptor remains.

| Platform | Manifest SHA-256 | Config SHA-256 | Layers |
| --- | --- | --- | --- |
| linux/amd64 | `a9538684aad7a848dfa3754d117c458b6cf78a8f04002f626349760d681c7148` | `e4a3a4f5f1efbfbaac1da08798a31edceea6e0ac54bfa13e9df4506841ac2781` | 11 |
| linux/arm64 | `79f6a872175f21e597b227cea350bd75e674e5dbcbe19966c51efc5bb77e0fbd` | `7f6a3e7f59f68a6bdbb9559b947200a2bc5ef846a3b66c4fb7b3dfa430b2eb44` | 11 |

Each runtime manifest is 2,378 bytes; configs are 10,984 bytes (amd64) and
10,985 bytes (arm64). All 22 compressed-layer hashes/sizes and uncompressed
diff IDs passed. Each platform's version/revision labels and exact source pin
match the tagged source. Fourteen final overlay target files per platform match
Git bytes:

- `/app/.source_commit`: exact full source SHA followed by LF.
- `/run.sh`: mode 0755, including `--no-proxy-headers`.
- `/app/templates/index.html`.
- `/app/app/main.py`, `optimizer.py`, `models.py`, `routers/api.py`,
  `state_store.py`, `import_topup_ledger.py`, `storage_worker.py`, `earnings.py`,
  `decision_trace_store.py`, `trace_clock.py`, `solar_reentry.py`.

The other thirteen targets are mode 0644. Both platforms share target fingerprint:
`sha256:f5e473e44e13e4092a4a81bf09416c416963c7d8af0c82cc442159cf8fe2affb`.
Algorithm: sorted absolute image path + NUL + file bytes + NUL, hashed with SHA-256.
This is scoped file/launcher verification, not whole-filesystem equivalence or
container execution.

The previous .80 verifier was adapted with exactly three release constants;
remaining code and 68-case offline synthetic checks were unchanged.
Author and independent runs each passed all 68 cases. Full verification used
default TLS and an anonymous pull token held only in memory, streamed layer
bodies, and performed no filesystem extraction or container execution.
Full proof completed at 07:20:27.735286 UTC (18:20:27.735286 Sydney).
Independent review recomputed all fourteen Git-source target hashes/sizes,
modes and fingerprint, then separately fetched the index, both manifests/configs
and checked layer descriptors/diff IDs. The reviewer did not redownload all
22 layer bodies. Final independent proof review: **GO**.

Local temporary evidence remains outside Git at
`C:\Users\belot\AppData\Local\Temp\sigenergy-haos81-proof-20261026-b7bf6539`.
Hashes provide local receipt integrity; no logs, tokens or binary layers are
committed:

- `verify_oci.py` SHA-256:
  `db91436c79d824c6b1fd6c8f27b22af4c64b045e7e36d9fef8d69eb55ba779e9`.
- `oci-proof.json` SHA-256:
  `60680058f9f8c23cf94ae765900fc86db03d6971aaa734c016eab82ffd7d75a4`.
- `synthetic_checks.py` SHA-256:
  `41bfb928f048f93f611e40989527b908008f28f254249d5d8ce2a6945636732d`.
- `synthetic-report-final-v2.json` SHA-256:
  `55d58d85c57d0b3405beb8c1d1789cf1e9ed1be422b5c761c3ed2450b1499a6a`.

Fresh postpublication checks passed at **07:25:04.461944 UTC**
(18:25:04.461944 Sydney): GitHub latest stable release is `.81`, remote tag
peels to `247095a4...`, and separate default-TLS GET bodies/headers confirm
the .81/latest index above. Immutable .80 remains unchanged:
`sha256:91120b1039eec3915a37c6ff1a1210cf1cf5e79d97e3e1d9de31207206301a5a`.
Postpublication proof JSON SHA-256:
`d5bbab5c198af66e18e768c24130527879ded796acd20973825cc62f37268ee0`.

## Historical preflight checkpoint

At 17:58 Sydney (06:58 UTC), the proposed remote branch, tag, GitHub release
and GHCR version tag were absent. .80/latest digest headers retained the .80
index. Those absence/header checks were prepublication checks, not layer proof;
the completed publication and full verification above supersede them.

## Installation and rollback gates

The operator explicitly approved publication and this receipt's commit, push,
PR and normal merge. That approval excludes HA installation and live settings.
The operator last reported installed .79, without renewed exact startup proof.
Auto update was last confirmed off on 26 October; no direct HA query is claimed.
After separately approved installation, verify both startup lines:

```text
Runtime signature=2.3.70-haos81
Container source commit=247095a4f9905932c3f5716f3d1be6cee7b3c7f8
```

Use new rows generated after this build's verified startup when investigating
allocation, while retaining original trace evidence. The rolling 24-hour download
can include older rows without `charge_allocation`; nothing backfills them.
A readback or helper success still does not establish physical compliance.
No live control mode, inverter, battery or export setting changes were performed.

Published .80 and .79 source/images remain available. Availability does not prove
the operator's usable backup or reinstall method; operational rollback remains
unverified. Any installed rollback requires separate authority and a verified
recovery method, preserving runtime data and historical evidence. Source rollback
must be a scoped new change, with no resets, force pushes or tag rewrites.
