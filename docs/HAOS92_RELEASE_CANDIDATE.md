# 2.3.81-haos92 publication receipt

**Status.** Published and install-ready. The latest confirmed installation is `2.3.79-haos90` at source `00b837b34e5c26639dd8d2f0d4d448dbf4e452b7`. The operator last confirmed Auto update off on 9 November. [GitHub release](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.81-haos92)

## Publication proof

- Published on 9 November 2026 at 15:02:13 AEDT (2026-11-09T04:02:13Z). Annotated tag `v2.3.81-haos92` has object `249ffc287360321b2dd8a710c7ada4416371ad01` and resolves to `04eeaf153a2eb2b5fb22751664e33f807e0130a1`.
- Metadata PR #86 merged normally at 15:02:08 AEDT (2026-11-09T04:02:08Z) as `f2f4c6082dbb065809b7feeab3656d6fc1483987`. Its tree `f4af62f494c5acebe31a76765a82865da4194a5e` matches the approved and tagged tree. [Metadata PR](https://github.com/Belot77/sigenergy-optimizer/pull/86)
- Build 42559204242 completed successfully at 14:59:57 AEDT (2026-11-09T03:59:57Z). The image publication step completed at 14:59:50 AEDT. [Build run](https://github.com/Belot77/sigenergy-optimizer/actions/runs/42559204242)
- The version and `latest` references resolve to OCI index `sha256:7bd4aa33b1fd0110e9bfd1dd8158da1b7c2f7011eddb87900a8d081c924b2fcd`. The immutable .91 and .90 indices still match `sha256:cefd47aa755d9365d3dce3c8054e8acdeb6c9cbf43fb4ba0fc4c2a4bf0d7130e` and `sha256:f15fe33002420affaece797353fa53a191b1fa5a9ab2a7d7f7de48db78b2823e`.

| Platform | Manifest digest | Config digest |
| --- | --- | --- |
| linux/amd64 | `sha256:320c50fbd9ea95d9b5b59a43a8993ac500de27dab6b932a857f5e17f1c54efbe` | `sha256:0522de69e53b0461bcaa777c956dc068558ce0dcd12d2764c95d2e04ed57a6c9` |
| linux/arm64 | `sha256:d04e1c188cb634ab254f20ec72e5d1022d1c318180486040808392982021468f` | `sha256:48c2993cdc7c723333e821a4e0fc83ae71f7cf221c78652c20d2e95f90fe5c95` |

Independent registry metadata verification checked raw sizes and digests, version, revision, source and architecture labels, and attestation manifest and config descriptors. The streaming verifier checked all 11 compressed layer digests and uncompressed diff IDs and 25 selected final source files and modes per platform. Verification used anonymous registry pulls and default TLS. The source comparison excluded the environment template. Its containing layer still passed the digest checks. No container extraction or execution was used.

The shared source fingerprint is `sha256:1a90e62432a3e3b717b1c4cc8258a3acae3d2c66710627c7963c2d0ac87d03d6`, calculated over sorted absolute image paths, a NUL, file bytes and a NUL.

## Included changes

- PR #82 merged as `403f31b`. Apply ESS Controls preserves an explicit 0 kW PV Max in its request and rejects blank, nonnumeric, nonfinite and negative entries before submission. [PR #82](https://github.com/Belot77/sigenergy-optimizer/pull/82)
- PR #83 merged as `b99fa4d`. Successful Mode and ESS API requests show “Request accepted” and refresh the dashboard. Confirm the hardware outcome from request-correlated readbacks. [PR #83](https://github.com/Belot77/sigenergy-optimizer/pull/83)
- PR #84 merged as `362fbbc`. The dashboard distinguishes last optimizer or preset targets, HA-reported limits and measured power for grid export, grid import and ESS charge. It shows snapshot age and replaces stale, unavailable or unverified readings with evidence labels. Positive measured battery power indicates charging and negative indicates discharging. [PR #84](https://github.com/Belot77/sigenergy-optimizer/pull/84)
- PR #85 merged as `4acb81c`. The WebSocket sends unavailable power evidence before the first optimizer snapshot and reads freshness settings when a valid report is present. [PR #85](https://github.com/Belot77/sigenergy-optimizer/pull/85)

## Offline validation

The first expanded release run caught an ingress WebSocket failure in the empty-snapshot fixture. PR #85 deferred the freshness-settings reads until a valid report is present and extended the ingress regression. Independent review passed.

The approved .92 tree passed 229 guarded Python tests and 106 subtests, plus 14 Node dashboard and form tests. The Python suite covered version consistency, local source pinning, ingress, dashboard status, manual ESS, telemetry and adjacent control safety. The guards allowed 154 temporary SQLite connections and 246 internal socket pairs and rejected zero database paths. Live HA and browser layout remain unverified.

The prepared worktree advanced to `4acb81cb6f941556b683da49a6ccdaf6154780f3` after PR #85. All 12 prepared files matched their original bytes immediately after fast-forward. Release documentation was reconciled before the exact candidate tree was approved.

## Installation, evidence and rollback

- For a source rollback, use a separately reviewed scoped revert. Before an authorized installation, verify the rollback path and exact image for the prior confirmed `.90` runtime. A live rollback requires separate authorization.
- After a separately authorized installation, verify the `.92` runtime and exact published container source from startup. Begin with read-only dashboard and HA checks for target, reported limit, measured power, snapshot age and unavailable evidence. Confirm the applicable authority and settings before any supervised actuation.
- During separately authorized live checks, correlate accepted Mode and ESS requests with the requested targets, fresh post-request HA and inverter observations, and measured grid and battery flows. Verify zero PV Max only under an approved scenario with a safe restoration plan. Stop on conflicting or missing evidence or unexpected actuation. Live acceptance remains open.
- O4 sunset continuation and stability, O5 reserve/load/price policy, O6 broader Morning Dump handoff and depletion, and O9 ownership and settings remain open. Capture the passive O4 sunset trace during a natural eligible sunset and correlate the outcome with observed controls and measured export. Relevant .90 floor-retirement and .89 deliberate-export target proof also remain open. [Roadmap](ROADMAP.md)
