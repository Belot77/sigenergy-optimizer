# 2.3.80-haos91 release candidate

**Status.** Local metadata preparation. Latest published and confirmed installed is `2.3.79-haos90`. The 5 November startup reported source `00b837b34e5c26639dd8d2f0d4d448dbf4e452b7`. Auto update was last confirmed off on 5 November. [Published .90](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.79-haos90)

## Baseline and scope

- Workspace `C:\Projects\sigenergy_optimizer-release-haos91`, branch `release/2.3.80-haos91`.
- Verified main `bfbcbdc1a128ed26bfa55742d1c3d292ed2fccf9`. PR #79 merged normally on 9 November at 07:11:46 AEDT. Its merge tree `7193fdad479004d31b40a82ea14eecc0152d12e2` matches reviewed head `651c644c3ea63ec2d9ad6b96972fc30cb556613f`. [PR #79](https://github.com/Belot77/sigenergy-optimizer/pull/79)
- Preparation aligns the API version, optimizer runtime signature, add-on config version, build label and buildstamp to `2.3.80-haos91`. The release scope also includes the project status and release notes.

## Included change

PR #79 adds the optional `o4_sunset_provenance` decision-trace field. Near sunset it records HA sun horizons, report timestamps, control ownership and inverter readbacks from the pre-application snapshot. The trace distinguishes matching chronology from fallback and conflicts. It reuses the existing HA batch.

This is evidence for the O4 investigation. Boost qualification, export priority and actuator dispatch use the existing control path. O4 continuation remains a separate control change. Its live evidence target is a natural sunset with Boost already exporting. [Control contract](CONTROL_CONTRACT.md#passive-o4-sunset-report-provenance)

## Validation

- The source candidate passed 1,747 tests and 1,779 subtests before replacing the fixture timestamp with a synthetic value. The exact sanitized source passed 293 tests and 299 subtests in 16 guarded modules. Independent safety and scope reviews passed.
- The local .91 preparation passed 309 tests and 299 subtests across 18 modules. These include version consistency, add-on source pinning and the guarded O4, HA metadata, export and trace regressions. Guards recorded 328 isolated SQLite stores and three in-memory stores. Protected database metadata matched and dotenv access was disabled.

## Publication and live checks

- Publication requires separate approval of the reviewed release tree and an updated Auto update confirmation. Verify the exact release tag, multi-platform image digests and source before marking it install-ready.
- After separately authorized installation, confirm the runtime signature and container source from startup. Check that a sunset trace contains the new field with coherent timestamps or explicit missing/conflict evidence. Compare observed EMS and export-limit readbacks with the application outcome and measured export.
- The local candidate can be withheld. Any installed rollback uses a separately authorized known-good build.
