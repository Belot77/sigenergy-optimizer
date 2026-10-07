# SigEnergy Optimizer AI Handover

Last consolidated: 2026-10-07

Read root/project `AGENTS.md`, then `CURRENT_STATE.md`, `CONTROL_CONTRACT.md`, `DECISIONS.md` and `ROADMAP.md`. Verify worktree, branch, HEAD and status before editing; the accepted .67 source checkpoint is committed; only the local release preparation is intentionally uncommitted.

## Authoritative release and task state

- Worktree: `C:\Projects\sigenergy_optimizer-phase1-remediation`; branch: `fix/phase1-audit-remediation`; HEAD/source checkpoint: `e2eba5431ee1fcfd36f9632c21f10e53f81c592d`.
- Live: **.66 / 2.3.55-haos66**, source/main/tag `d01db472019ad19d721e400e61ae8d5238fe6856`, tag `v2.3.55-haos66`, digest `sha256:42709e868e778111d03629378064857fbeae450a8bcc09c93d91b2aa1a4685ab`.
- Rollback: **.65 / 2.3.54-haos65**, source `9965e79133f38d5b9943dcf5a9b04ed6fdab1239`.
- The complete .67 Phase 1 candidate is independently accepted (`ACCEPT FOR CHECKPOINT COMMIT`), committed and pushed at the source checkpoint above. Release identity `2.3.56-haos67` is locally prepared, with future tag `v2.3.56-haos67` and future image `ghcr.io/belot77/sigenergy-optimizer:2.3.56-haos67`. Only release metadata/documentation remains uncommitted and unpushed. This preparation performs no staging, commit, push, merge, tag, build, publication, deployment, restart or live HA/inverter/operator configuration write. .67 is not tagged, built, deployed or live-proven.
- Operator-confirmed site physical limit: **15 kW**. Software/default `grid_connection_export_limit_kw=0.0` remains disabled; the live 15 kW setting has **not** been written by this task.
- Phase 2 remains blocked until .67 live acceptance and the separately required Evening Boost remediation/live acceptance. The two frozen settlement failures remain outside scope.

## .66 live evidence already accepted

Provider-aware freshness at partial SoC, deadline expiry/recovery, Solar ownership at partial SoC, the dynamic `0 -> small positive -> increasing` charge trajectory and `present_charging_required_for_fill_trajectory` are live-proven. Solar safely relinquished to normal MSC when its energy plan became insufficient. No battery-export leakage was observed; MSC/PV MAX/high export permission remained correct.

On 7 October the battery reached only about **97.8%**, missing full as late load and weak PV consumed margin. A separate Force Full Export diagnostic held actual export near 15 kW while PV and battery charging increased. These observations motivate the approved .67 changes; do not repeat the already accepted .66 investigation.

## Combined .67 behavior

**Fill deadline:** new `solar_surplus_fill_deadline_margin_minutes`, default **60**, finite/nonnegative with zero allowed and booleans rejected. Dynamic Solar charge opportunity is clipped at trusted same-day sunset minus this margin. Solar forecast safety remains **1.20**, independent of Morning Slow. Aggregate/export-eligibility sunset timing is unchanged. At the effective deadline restrictive Solar charging is relinquished to normal safe MSC; early full does not remove later surplus-export eligibility. All trusted-input, provider and priority gates remain.

**Physical relief:** Solar-only process-local feedback adds bounded relief to the baseline charge trajectory, never beyond the normal safe/trusted ESS request. A positive generic physical limit enables evidence assessment; it does not set inverter export permission. At a 15 kW site, entry is >=14.8, exit reduction is <14.5, hard reset is <14.0. Each increase is 0.4 kW after two fresh coherent post-command observations; export-driven reductions subtract 1.2 kW immediately and impose three-observation retry. Fixed policy values introduce no tuning settings.

All relevant PV/load/import/export timestamps must be fresh and coherent within five seconds; measured flow must support battery charging without grid import. A successfully applied changed charge target starts the feedback epoch, repeated telemetry cannot stack increases, and active relief requires actual charge response before increasing again. Fresh falling-export observations reduce promptly without requiring every still-trusted companion sensor to report again. Ownership/trust loss, exact-full, configuration disablement and actuator failure clear relief. Baseline/normal-cap changes restart feedback while retaining existing retry for the same site limit. Await-boundary checks restore baseline/normal charging if physical/Solar authority expires.

Keep MSC, normal PV MAX/high export permission, no `BATTERY_EXPORT`, Manual/Force, Morning Slow and Demand Window priorities. Morning Slow's binary release/retention and tuning are unchanged. Solcast potential, estimated PV and `hidden_pv_surplus_kw` are not authorization. See `CONTROL_CONTRACT.md` for exact boundaries and trace fields.

## Independent-review correction: accepted source checkpoint

The independent review reproduced active relief surviving timestamps regressing to before the command epoch. The prior authorized production correction now checks regression before waiting, clears relief and dependent state, and returns to the current Solar baseline. The integration characterization verifies that earned 0.4 kW relief above a 0.81 kW baseline is removed, ownership/MSC/PV MAX/export permission are preserved, and recovery requires baseline reapplication plus fresh confirmations.

The initial correction validation stopped at **1 failed, 33 passed / 20 subtests passed**: the old pre-command test expected probing after timestamp 0 -> -1 without reapplying the baseline. The user explicitly approved classifying that as regression and correcting the test. This continuation separates monotonic pre-command waiting (accepted observation 0, command epoch 2, observations 1 and 2; no reset or confirmation) from genuine regression (0 -> -1; reset to baseline and reapplication required). Existing active-relief regression and waiting protections remain intact. **No production code changed during this continuation.**

The user-approved **0.4 kW** increment remains unchanged; its explicit 2026-10-07 approval superseding the earlier 0.5 kW discussion remains recorded in `DECISIONS.md`.

Current validation: physical-relief suite **35 passed / 20 subtests**, affected Solar/controller suites **140 passed / 221 subtests**, independent protections **250 passed / 266 subtests**, with exactly the two frozen Phase 2 tests deselected from the protection gate. Those gates reported 198, 200 and 198 warnings respectively. The full suite ran **once**: **907 passed / 872 subtests**, exactly **2 frozen Phase 2 failures**, 201 warnings, 67.42 seconds. Failure character is unchanged: export 25 versus closed 0, and MSC requested before observed export closure. **No unexpected failures.** Compileall for `app` and all five candidate Python test files passed.

Correction validation included successful `git diff --check` and SHA-256 comparison confirming unchanged production files during the characterization continuation. Final independent review returned **ACCEPT FOR CHECKPOINT COMMIT**. The candidate and two documentation corrections are committed and pushed at `e2eba5431ee1fcfd36f9632c21f10e53f81c592d`. This release preparation changes only the five version identities and release-facing documentation; production behavior, tests and configuration semantics remain unchanged. The full suite is not rerun for metadata preparation. The two frozen Phase 2 tests remain unchanged; .66 remains live and .65 remains known-good rollback.

## Initial candidate tests (before independent review)

- Tests-first characterization captured only the approved missing features; no separate out-of-scope production defect was established.
- Final new/changed characterization gate: **144 passed / 186 subtests passed**.
- Existing affected suites: **345 passed / 332 subtests passed**, with exactly the two frozen Phase 2 tests deselected.
- Independent protections: **383 passed / 411 subtests passed**.
- Existing Solar test bodies and Morning Slow control methods retain their prior assertions/behavior; legacy sunset-focused fixtures explicitly select margin zero.
- The affected and independent groups were repeated after the startup-retry correction: zero-relief entry uses two observations; an actual downward hard reset requires three. Both final groups passed without unexpected failures.
- Full suite ran **once** with `python -B -m pytest -q -p no:cacheprovider --disable-warnings --tb=short tests`: **904 passed / 872 subtests passed**, exactly **2 frozen Phase 2 failures**, 201 warnings, 67.75 seconds. Both failures retain their prior character: export 25 versus closed 0, and MSC before observed closure.
- Initial compileall for `app` and all five changed/new Python test files and `git diff --check` passed. Current continuation results supersede this historical gate. The 13 modified and 3 new candidate files are now committed in the accepted source checkpoint; .67 live acceptance remains pending.

The only frozen expected failures in `tests/test_msc_baseline_overlay_contract.py` remain:

- `test_exact_msc_does_not_reopen_before_export_is_observed_closed`
- `test_return_from_discharge_waits_for_observed_close_before_requesting_msc`

The new setting is exposed in config/API/UI/.env.example, with atomic invalid-update rejection and nullable trace-copy status diagnostics. `app/models.py` now includes observation timestamp data used by the Solar physical-relief feedback controller. The five release-version identities are now locally prepared as `2.3.56-haos67`; control semantics remain unchanged.

## Preserved diagnostics and historical evidence

.66 retains the .65 diagnostics hotfix: 512 MiB maximum download, at most 4 active downloads, 2-minute lifetime, 25 segments; approximately 1000-cycle memory trace and 15-minute flushes to the rolling 24-hour archive. Diagnostics remain isolated from control with conservative gap/clock handling and no final shutdown flush.

Historical provider/regression and metadata-preparation gates each recorded 842 passed / 778 subtests with only the two frozen failures. The metadata API/version subset passed 48 / 53 subtests. Those results do not substitute for the .67 gate above.

Morning Dump remains operator-accepted for its observed export/floor/relinquishment case. Recorded Morning Slow tuning remains 2 kW until 11:00, minimum FiT $0.01/kWh, base-load allowance 2 kW and sunset cutoff 1 hour. Live tuning does not change software defaults.

## Parked work

Evening Boost reserve-estimator instability remains unresolved: instantaneous load projected across the overnight horizon can yield reserve above 100% and unstable Boost/MSC transitions. Its import-cost trust interaction is also parked: a >=0.01 kWh import/top-up chunk with untrusted price can poison that day's floor despite later valid observations. Prior .63 evidence included about 18.412 kWh imported and $0.2037716/kWh highest actual import price with an unknown floor. Separate bounded review/remediation and live acceptance are still required.

Export Value Gate remains advisory-only and Actual Import Cost Guard enforcing. Do not begin Phase 2, Climate Manager, Morning Dump redesign or broad refactoring, and do not weaken settlement protections.

The 27 September Solar aggregate-budget threshold-switching observation remains parked for evidence-led monitoring; .67 does not claim to fix that independent gate.

## Exact next action

Review the local `2.3.56-haos67` release-preparation diff and obtain separate authorization for its checkpoint commit. Leave preparation unstaged, uncommitted and unpushed. Tagging, build/publication, release/deployment, restart, the live 15 kW setting and .67 live acceptance require separate authorization. No .67 tag, build, deployment or live acceptance has occurred; Phase 2 remains frozen.

Earlier necessary charging is an intentional effect of the margin. Physical export preservation depends on real plant feedback and is not live-proven for .67. The source checkpoint is committed; the release-preparation patch remains local and uncommitted. Known-good rollback remains .65.

Monitor-only/dry-run review must confirm requests, priority/normal-cap bounds and absence of writes; simulated decisions alone cannot establish post-command relief authority. After separately approved deployment/configuration, verify earlier fill, deadline relinquishment/full-battery export, actual export-preserving probe response, reduction/reset/retry and trust/ownership transitions. Acceptance must retain MSC, normal PV MAX/high permission, no battery export and Demand Window import blocking. Full steps are in `CURRENT_STATE.md`; .65 remains rollback.
