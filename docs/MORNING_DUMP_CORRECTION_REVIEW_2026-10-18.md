# Approved Morning Dump correction review - 18 October 2026

## Scope and current verdict

The operator approved the proposed local correction after the tests-only reproduction. The correction is applied in `C:\Projects\sigenergy_optimizer-review`, branch `test/local-fix-integration`. The approved code-bearing checkpoint is `4e4b17c2d3bb362716d6b4e5ddb60659faf7beec`, based on `9f3f02a5c1c82786c85026a3848574cca3cf891f`. Origin remains `https://github.com/Belot77/sigenergy-optimizer`.

Independent source and test review reported **GO for this narrow local delta**, with no actionable findings. This is not blanket approval of the combined documentation, a commit, installation or physical acceptance. Final combined offline validation passed **1,073 tests / 1,134 subtests, zero failures**, with 206 warnings in 170.97 seconds.

The earlier `INDEPENDENT_REVIEW_HANDOFF_2026-10-18.md` and `INDEPENDENT_REVIEW_FOLLOWUP_2026-10-18.md`, plus their original exported patches, are preserved historical snapshots. Their NO-GO/test-only/production-unchanged statements describe the earlier checkpoints and are superseded for this correction by this report.

## Before and after

With active Morning Dump, positive FiT 0.24502 or 0.99 cents/kWh, import price -5 cents/kWh and trusted Demand Window OFF, the prior combined candidate requested import/export limits both zero but returned `Command Charging (Grid First)`. The tests-only reproduction recorded two failing subcases; physical charging was not established.

The approved early branch now returns `Command Discharging (PV First)` only for `BATTERY_EXPORT` and a bounded requested export target above 0.01 kW. Otherwise active Dump returns `Maximum Self Consumption`. Qualified Dump keeps its priority, including negative-price cases. Inactive Dump follows the unchanged independent import/standby/Demand Window paths.

An independent artifact check reconstructed the entire pre-correction production file in memory by replacing only this fallback block. Its SHA-256 matched `52b74a4b85ec029ade36054f63d1ab0463f3e6e410b6b4fec6c8faf2a66d3b05`, proving no other production bytes changed during this correction. Current production SHA-256 is `026c7970556b78fd2979dc7eb9a6149258f6a9db054ef32d1a5bdc99574467b2`.

## Verification

All commands ran offline from the review worktree with fake HA/temp databases, `PYTHONDONTWRITEBYTECODE=1` and `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`. Interpreter: `C:\Projects\sigenergy_optimizer-dev\.venv\Scripts\python.exe`. Pytest arguments: `-q -p no:cacheprovider --disable-warnings --tb=short`.

- Exact unchanged regression and original controls immediately after the production edit: 8 tests / 15 subtests passed, 202 warnings, 0.85 seconds.
- Final focused decision and floor-cycling tests: 11 tests / 26 subtests passed, 202 warnings, 1.16 seconds. Preservation cases include inactive-Dump negative-price grid charging with positive import permission; qualified Dump at exact 1-cent and 5-cent FiT; observed-ON and unobserved Demand Window states; actual import-cost vetoes; trusted battery evidence and the existing floor/cycling behavior.
- Independent Demand Window, Manual/Force takeover, remote-EMS authority, requested-target settlement and fallback protections: 13 tests / 15 subtests passed, 202 warnings, 4.79 seconds.
- Final combined offline validation passed **1,073 tests / 1,134 subtests, zero failures**, with 206 warnings in 170.97 seconds.
- Current `compileall app/tests` passed; bytecode was confined to an isolated temporary cache.
- Independent source/test safety review found no actionable defect in the new delta. Independent artifact review confirmed the exact bounded production change, all ten code/test paths and an empty Git index.
- All 37 protected/source fingerprints matched; baseline HEAD is unchanged, `git diff --check` passed and the index remains empty. Original component and unfinished worktrees are preserved.

The earlier 1,070-test / 1,124-subtest pass is historical and predates the new regression. It is not substituted for current validation.

## Risk, rollback and manual verification

The intentional change suppresses lower-priority EMS fall-through only while active Dump already blocks import. It changes no thresholds, floors, timing, damping, export authority, Manual/Force behavior, independently owned restrictions or observed-settlement logic. Roll back only this additional early-Dump fallback delta if a regression is found; preserve the other reviewed changes and all original unfinished work.

Monitor-only verification: compare requested EMS/import/export/owner decisions for blocked and qualified Dump; the offline fixed-clock fake-HA tests implement this comparison. No live monitor session was started.

Dry-run verification: use fake/recording HA to check no calls from decision-only tests, Demand Window limits, Manual/Force ownership and settlement/fallback protections. The preservation tests passed; no live application was exercised.

Live verification remains separately authorized work. Before any such trial, verify actual installed source/build, effective settings, authority, observed EMS/import/export/ESS limits, physical flows and .65 rollback readiness. Observe naturally occurring scenarios under supervision with explicit stop/rollback conditions; do not alter prices or live controls under this approval. Helper success and offline tests are not proof of physical settlement.

## Documentation, installation evidence and review artifacts

The Morning Dump control contract now states the explicit active-Dump MSC fallback. Current handover, state, README, changelogs, roadmap and cycling-validation records describe the correction and distinguish historical red/green checkpoints.

Published .71 at baseline was verified on 17 October. The external review reports .71 installed, whereas earlier direct operator records said .70. No actual HA About/startup/source-build evidence was supplied or accessed here; installed identity remains unresolved. .65 remains the protected known-good rollback. Short physical Demand Window import spikes remain deferred, separate from O7 exact-full PV-only acceptance.

Optional local code/test snapshot (excluded from the commit and not required in another checkout): `INDEPENDENT_REVIEW_CODE_V2_2026-10-18.patch`, SHA-256 `1b11c4534935ddd05dd615d93d976cfa08dc4c4c89322cad9f14393f00d62025`, 62,233 bytes, ten paths. It includes all six new tests, the three modified trace compatibility tests and `app/optimizer.py`. The original patch SHA `ad9c8decc0597901ca6d7d9f6659e1040c3f2bb4f2a885f9550451df6389c025` is preserved locally as historical review evidence.

The local `INDEPENDENT_REVIEW_DOCS_V2_2026-10-18.patch` is a historical documentation snapshot from before the final portability clarification. All exported patches and earlier review handoffs remain local evidence outside the proposed commit; they may be absent from another checkout. Repository reviewers can inspect [the optimizer](../app/optimizer.py), [the Morning Dump regression and preservation tests](../tests/test_morning_dump_export_intent.py), the other changed tests and the project documents directly against baseline `9f3f02a5c1c82786c85026a3848574cca3cf891f`. No excluded export is required to review the committed source or understand this report. Patch verification is read-only; no patch was applied during export.

A subsequent independent review reported GO for the full combined local code/test candidate, with no actionable findings. Independent documentation review also reported GO for the current documents and proposed 19-file scope after verifying the local-export portability clarification above. The exact 19-file local code commit, branch push and [draft PR #21](https://github.com/Belot77/sigenergy-optimizer/pull/21) were subsequently approved and completed. The PR is draft and unmerged; no submitted reviews or GitHub CI checks were reported in the 18 October check. The index and tracked worktree were verified clean after publication. Further commits/pushes, merge, release, installation, HA writes and inverter-setting changes require separate authorization. Installation and live acceptance remain unverified.
