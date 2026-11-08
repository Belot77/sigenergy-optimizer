# 2.3.80-haos91 publication receipt

**Status.** Published and install-ready. The latest confirmed installation is `2.3.79-haos90` from source `00b837b34e5c26639dd8d2f0d4d448dbf4e452b7` on 5 November. Auto update was confirmed off on 9 November. [GitHub release](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.80-haos91)

## Publication proof

- Published 9 November 2026 at 07:29:56 AEDT (2026-11-08T20:29:56Z). Annotated tag `v2.3.80-haos91` has object `485b15098730137eaa2fb2c8923fb4bfd5f80e62` and resolves to `6144d027496b2a1822219324eb37512d44b002c1`.
- Metadata PR #80 merged normally at 07:29:52 AEDT (2026-11-08T20:29:52Z) as `25c9c585f6a34614983584f4e937f0710f221ee5`. Its tree `5c75deb7276c0e3f69bea778a649f493e5317405` matches the approved and tagged tree. The source feature is PR #79, merged at `bfbcbdc1a128ed26bfa55742d1c3d292ed2fccf9`. [Metadata PR](https://github.com/Belot77/sigenergy-optimizer/pull/80) [O4 diagnostics PR](https://github.com/Belot77/sigenergy-optimizer/pull/79)
- Tag-triggered build 42520031965 completed at 07:26:58 AEDT (2026-11-08T20:26:58Z) with exact source `6144d027496b2a1822219324eb37512d44b002c1`. [Build](https://github.com/Belot77/sigenergy-optimizer/actions/runs/42520031965)
- `ghcr.io/belot77/sigenergy-optimizer:2.3.80-haos91` and `:latest` resolve to OCI index `sha256:cefd47aa755d9365d3dce3c8054e8acdeb6c9cbf43fb4ba0fc4c2a4bf0d7130e`. The immutable `2.3.79-haos90` reference retained `sha256:f15fe33002420affaece797353fa53a191b1fa5a9ab2a7d7f7de48db78b2823e`.

| Platform | Image manifest digest | Config digest |
| --- | --- | --- |
| linux/amd64 | `sha256:b07f1159b83123c96b42439f79266bd2e51f23526380b0255dcb7c665401ddfe` | `sha256:62528ef8b996188960155f0f4cf08f4df102260bc7d42d0f0dcbfca5df09392a` |
| linux/arm64 | `sha256:1e1f6d29ab31bcd5bed1afcef3012fe30787e3fbb632f9d7ff2a1092a3d2e181` | `sha256:820537f15ee12bc6cc45d90ee46648a86a43a27000f5b6f9378adbcb217d8cd8` |

Registry verification used default TLS and checked raw descriptor sizes and digests, runtime architecture, version, revision and source labels. Independent metadata and config verification passed. Each platform also passed 11 compressed layer hashes and uncompressed diff IDs, with 15 final source files and modes matching the tagged tree and the Dockerfile transformations. Verification streamed the layers without extracting or running the images. The shared source fingerprint is `sha256:c590e8611d7bd3081feafdf090e7255ec60476f6cdb7ba46bcab263ef7008242`, calculated over sorted absolute image paths, NUL, file bytes and NUL. The selected paths cover the source marker, entry script, requirements, dashboard template and application modules including the HA reader, optimizer, archive and API.

## Included change and validation

PR #79 adds optional `o4_sunset_provenance` near sunset. It records HA sun horizons, report timestamps, control ownership and inverter readbacks from the existing pre-application batch. The trace distinguishes corroborated chronology from fallback and conflicts. O4 continuation is separate. [Control contract](CONTROL_CONTRACT.md#passive-o4-sunset-report-provenance)

- The source candidate passed 1,747 tests and 1,779 subtests before the synthetic test fixture adjustment. The exact published source before the version bump passed 293 tests and 299 subtests across 16 guarded modules.
- The release candidate passed 309 tests and 299 subtests across 18 modules, including version consistency and source pinning. Guards recorded 328 isolated SQLite stores and three in-memory stores, with protected database metadata unchanged and dotenv disabled. Independent safety and release-scope reviews passed.

## Installation and remaining work

- Following separately authorized installation, verify startup signature `2.3.80-haos91` and container source `6144d027496b2a1822219324eb37512d44b002c1`.
- Check that a sunset trace contains the new field with coherent timestamps or explicit missing/conflict evidence. Correlate the application outcome and observed EMS and export-limit readbacks with measured export.
- The O4 continuation fix and live acceptance remain open. A natural sunset with Boost already exporting is the evidence target. The latest confirmed live version remains .90. [Roadmap](ROADMAP.md)
