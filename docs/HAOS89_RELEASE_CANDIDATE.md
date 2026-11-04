# 2.3.78-haos89 publication receipt

**Status:** published and install-ready for a separately authorized operator action. Publication is verified; installation and physical acceptance are not established. The latest supplied installed identity remains `2.3.77-haos88`. Auto-update was confirmed off by the operator on 4 November 2026.

## Publication receipt

The GitHub release [v2.3.78-haos89](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.78-haos89) was published at 2026-11-04T08:01:17Z (19:01:17 AEDT). Annotated tag object `e29d5beddadf3e76b287d647ef354e55612857b1` resolves to source `352b61303e7b18da4a46b40ba57546e0c8baa1e7`, tree `0d4ce6a64772dd58136ed45483559b1ecb413104`. Metadata PR #74 merged normally at `2ce58a8e89b849c8588b960869610f3df703879d` at 07:58:50Z with parents `eef008b6ba86e9efcdfd1f37795f374029215d88` and the release source; merge tree matches the tagged tree.

Build [41795353716](https://github.com/Belot77/sigenergy-optimizer/actions/runs/41795353716) succeeded at 07:55:15Z. The version/latest OCI index is `sha256:1d9e0ed00453cb57698d04d3ca0ef972cf1e672a4bd87a369029334b647961b5`; amd64 manifest `sha256:1834ef0c11a004b278cfcec9da8beca4a823989cba7ca9506477723c9349414c`; arm64 manifest `sha256:6f9350b4b99dec2dc70b0940fe5dc7886b7eb5e9449098fbf41750143a50a3a2`. Source fingerprint `sha256:7cfbfe4221fcb49b979fa14e26deb028a87bf6e792aecf018cf12dad8cae3abe` is SHA-256(sorted absolute image path + NUL + file bytes + NUL). All 11 compressed layers/diff IDs and 15 source files/modes per platform were downloaded and verified. Verification used default TLS and did not extract or execute a container. Independent helper/source-expectation/registry metadata-config and completed-proof consistency reviews are GO; the independent reviewer did not redownload compressed layer bodies. The offline verifier passed 73 safety cases. Previous immutable `.88` index `sha256:cc6759bf5deb23e659083699840237288f744248ec053226acabe46722b7bb39` is unchanged.

Post-publication checks are GO: GitHub latest is the non-draft, non-prerelease `.89` release at the stated time; remote annotated tag/source and normal metadata merge tree match; `.89` version/latest index and prior `.88` index match this receipt.

## Merged source and correction

PR #73 merged source `8c366db87ee955b06ba2d8d07f9808291c7e59da` at `eef008b6ba86e9efcdfd1f37795f374029215d88`. The merge tree was `dfced95cb2064fe67177de2e8b5ee34d5b934f11`, the exact tested tree used for release preparation. The published release source contains the separately approved five version literals and release/status documentation; no control behavior changed after that tested tree.

For a deliberate battery-export request, the shared `deliberate_export_target_correction_required` predicate requires dispatch of the bounded target through the existing `exact=True` path when `abs(bounded_target - current_observed_export_limit) > 0.011 kW`. It applies at both export-write and pre-discharge checks, regardless of the ordinary deadband. The existing setting-observation wait remains at most three seconds, followed by the unchanged final joint exact post-request guard before positive ESS discharge; the wait itself does not prove exact settlement. Proof tolerance (0.011 kW), request-identity tolerance (0.001 kW), valid same-target debounce, PV-only behavior, settlement-failure fallback, qualification, timing, and policy thresholds are unchanged.

The supplied `.88` trace records 16 failed application outcomes (13 on 2 November and three on 3 November), all correlated with an approximately 0.1 kW desired/current export-limit difference. The runtime deadband is not present in the trace. This correlation does not establish HA service-call rejection or prove live causality; legacy O11 causes remain unresolved. The 4 November trace has no failed applications through 17:10:58 AEDT but ends before the Evening Boost window.

## Validation

The tests-first baseline had 16 failed checks and five passed checks (including subtests), reproducing the 24.00 kW wrapper error. After correction, the new module passed six tests / 15 subtests. The focused run passed 107 tests / 128 subtests in 97.45 seconds. The guarded pre-bump source suite passed 1,722 tests / 1,740 subtests, zero failures (four warnings, 288.12 seconds). Independent source/safety and documentation/scope reviews are GO.

For the release version, static checks passed 16 tests in 9.73 seconds. The separate six-module runtime release check passed 107 tests / 128 subtests in 97.96 seconds. Its guards recorded 205 isolated temporary StateStore/SQLite accesses and 243 exact internal asyncio socket pairs; protected database metadata was unchanged, dotenv/settings environment-file access was disabled, and no external access was rejected. These disjoint release checks total 123 tests / 128 subtests. Independent version/source and release-documentation/scope reviews are GO. These checks establish software evidence, not physical behavior.

## Remaining work and physical evidence

O4 Boost qualification retention/stability, O5 reserve/load/price policy, O6 broader floor/depletion behavior, and O9 overlapping ownership/status semantics remain open. Legacy O11 investigation remains unresolved; O20 is parked, the historical O8 observation gap is irrecoverable, and short Demand Window import spikes remain deferred rather than confirmed defects. Provider recovery, Dump retirement/restart, Morning-to-Solar handoff/deadline, request-correlated MSC/close behavior, and eligible-day Boost qualification retain applicable live-proof requirements.

Physical evidence is partial. Both observed days reached 99.9% SoC at the deadline and 100% about two minutes later. Morning Dump ran and then closed at 15% on both mornings, with no re-entry in the sampled window; previously observed floor flapping remains open. Boost closed at 79.9% on 3 November at 20:01:46 AEDT. O5 reserve-estimate instability remains open. The older archive tail was filled; a new uncovered interval of 6 minutes 56 seconds is not established as permanent. None of this demonstrates the new correction operating in the installed runtime.

## Installation and live acceptance gates

Publication is complete. After separate installation authorization, capture startup evidence that identifies runtime signature `2.3.78-haos89` and container source commit `352b61303e7b18da4a46b40ba57546e0c8baa1e7`. The operator confirmed auto-update off on 4 November; the last supplied startup still identifies `.88`. Do not infer installation from publication or package availability.

After installation, supervised live acceptance requires separate authorization. Confirm current control authority, correlate target requests with observed controls and measured flows, and observe relevant owner transitions and stop behavior. Do not treat service-call success as settlement or imply a monitor-only mode. Stop and return to the existing safe ownership path on failed, contradictory, or stale evidence. Missing proof includes applicable provider recovery, Dump retirement/restart, Morning-to-Solar handoff/deadline, request-correlated MSC/close behavior, and eligible-day Boost qualification.

The historical preparation rollback was to withhold the candidate; after a future source change, use only a separately reviewed scoped revert that preserves unrelated work. Publication does not itself authorize installation or live action.
