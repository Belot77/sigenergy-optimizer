# 2.3.78-haos89 release preparation

**Status:** local release preparation only. This workspace is uncommitted, unpublished, and uninstalled. `2.3.77-haos88` remains the latest published and operator-confirmed installed release. No tag, image, GitHub release, or physical acceptance is claimed.

## Merged source and correction

PR #73 merged source `8c366db87ee955b06ba2d8d07f9808291c7e59da` at `eef008b6ba86e9efcdfd1f37795f374029215d88`. The merge tree is `dfced95cb2064fe67177de2e8b5ee34d5b934f11`, the exact tested tree. The local release branch is `release/2.3.78-haos89`.

For a deliberate battery-export request, the shared `deliberate_export_target_correction_required` predicate requires dispatch of the bounded target through the existing `exact=True` path when `abs(bounded_target - current_observed_export_limit) > 0.011 kW`. It applies at both export-write and pre-discharge checks, regardless of the ordinary deadband. The existing setting-observation wait remains at most three seconds, followed by the unchanged final joint exact post-request guard before positive ESS discharge; the wait itself does not prove exact settlement. Proof tolerance (0.011 kW), request-identity tolerance (0.001 kW), valid same-target debounce, PV-only behavior, settlement-failure fallback, qualification, timing, and policy thresholds are unchanged.

The supplied `.88` trace records 16 failed application outcomes (13 on 2 November and three on 3 November), all correlated with an approximately 0.1 kW desired/current export-limit difference. The runtime deadband is not present in the trace. This correlation does not establish HA service-call rejection or prove live causality; legacy O11 causes remain unresolved. The 4 November trace has no failed applications through 17:10:58 AEDT but ends before the Evening Boost window.

## Validation

The tests-first baseline had 16 failed checks and five passed checks (including subtests), reproducing the 24.00 kW wrapper error. After correction, the new module passed six tests / 15 subtests. The focused run passed 107 tests / 128 subtests in 97.45 seconds. The guarded pre-bump source suite passed 1,722 tests / 1,740 subtests, zero failures (four warnings, 288.12 seconds). Independent source/safety and documentation/scope reviews are GO.

For the release version, static checks passed 16 tests in 9.73 seconds. The separate six-module runtime release check passed 107 tests / 128 subtests in 97.96 seconds. Its guards recorded 205 isolated temporary StateStore/SQLite accesses and 243 exact internal asyncio socket pairs; protected database metadata was unchanged, dotenv/settings environment-file access was disabled, and no external access was rejected. These disjoint release checks total 123 tests / 128 subtests. Independent version/source and release-documentation/scope reviews are GO. These checks establish software evidence, not physical behavior.

## Remaining work and physical evidence

O4 Boost qualification retention/stability, O5 reserve/load/price policy, O6 broader floor/depletion behavior, and O9 overlapping ownership/status semantics remain open. Legacy O11 investigation remains unresolved; O20 is parked, the historical O8 observation gap is irrecoverable, and short Demand Window import spikes remain deferred rather than confirmed defects. Provider recovery, Dump retirement/restart, Morning-to-Solar handoff/deadline, request-correlated MSC/close behavior, and eligible-day Boost qualification retain applicable live-proof requirements.

Physical evidence is partial. Both observed days reached 99.9% SoC at the deadline and 100% about two minutes later. Morning Dump ran and then closed at 15% on both mornings, with no re-entry in the sampled window; previously observed floor flapping remains open. Boost closed at 79.9% on 3 November at 20:01:46 AEDT. O5 reserve-estimate instability remains open. The older archive tail was filled; a new uncovered interval of 6 minutes 56 seconds is not established as permanent. None of this demonstrates the new correction operating in the installed runtime.

## Publication gates and rollback

After separate publication approval, complete and record this sequence:

1. Commit the reviewed release metadata, push the release branch, and open its PR. Create the intended annotated tag from that exact approved commit and verify its source and tree.
2. Build the release image, verify its immutable digests, and verify embedded source bytes against the tag for each platform.
3. Merge the reviewed metadata PR normally after the tag/image/source proof passes.
4. Publish the GitHub release and retain a receipt covering tag, source, merge, image digests, source verification, and limits.

Build and release-check results beyond the recorded tests above are not claimed. Installation and supervised live acceptance require separate authorization. Acceptance should first confirm installed runtime/source and current control authority, then correlate requests with observed controls and measured flows through relevant owner transitions and stop behavior. Do not treat service-call success as settlement or imply a monitor-only mode. Stop and return to the existing safe ownership path on failed, contradictory, or stale evidence.

The safest rollback is to withhold the candidate. After any future commit, rollback requires a separately reviewed scoped revert that preserves unrelated work. No publication, installation, or live action is authorized by this preparation record.
