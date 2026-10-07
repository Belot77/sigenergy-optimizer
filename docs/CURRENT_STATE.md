# Current State

Last consolidated: 2026-10-07

**CURRENT TRUTH ONLY:** durable control semantics live in `CONTROL_CONTRACT.md`; sequencing lives in `ROADMAP.md`.

## Release and live state

- Current live release: **.66 / 2.3.55-haos66**, source/main/tag commit `d01db472019ad19d721e400e61ae8d5238fe6856`, tag `v2.3.55-haos66`, image digest `sha256:42709e868e778111d03629378064857fbeae450a8bcc09c93d91b2aa1a4685ab`. These are the operator-supplied authoritative identities.
- Rollback remains **.65 / 2.3.54-haos65**, source `9965e79133f38d5b9943dcf5a9b04ed6fdab1239`.
- Worktree: `C:\Projects\sigenergy_optimizer-phase1-remediation`; branch: `fix/phase1-audit-remediation`; HEAD/source checkpoint: `e2eba5431ee1fcfd36f9632c21f10e53f81c592d`. The complete .67 Phase 1 candidate was independently accepted (`ACCEPT FOR CHECKPOINT COMMIT`), committed and pushed. Release identity `2.3.56-haos67` is now locally prepared; only release metadata/documentation is uncommitted and unpushed. Future tag: `v2.3.56-haos67`; future image: `ghcr.io/belot77/sigenergy-optimizer:2.3.56-haos67`. No .67 tag, build, publication, deployment or live acceptance has occurred.
- This release-preparation task performs no staging, commit, push, merge, tag, build, release, deployment, restart, HA/inverter write or live operator-configuration write. Production behavior, tests and configuration semantics remain unchanged from the accepted source checkpoint.
- Phase 1 remains open. Phase 2 remains blocked until .67 controlled live acceptance and the separately required Evening Boost remediation/live acceptance. Its two frozen settlement failures remain unchanged.

## Operator-proven .66 live results and remaining problem

- Provider-aware Solcast freshness at partial SoC: PASS. Provider deadline expiry/recovery: PASS.
- Solar ownership at partial SoC: PASS. Dynamic charge trajectory `0 -> small positive -> increasing`: PASS, including `present_charging_required_for_fill_trajectory`.
- Safe relinquishment to normal MSC when the energy plan becomes insufficient: PASS. No battery-export leakage was observed; MSC, PV MAX and high export permission remained correct.
- On 7 October the battery finished at about **97.8%**, missing 100%; late load and the weak PV tail consumed the remaining margin. This motivated the approved independent 60-minute fill margin.
- The operator confirmed the site's physical export limit as **15 kW**. A Force Full Export diagnostic retained about 15 kW actual export while PV increased and additional energy charged the battery, demonstrating otherwise-curtailed PV opportunity.
- The software/default `grid_connection_export_limit_kw` remains **0.0 = disabled**. The 15 kW operator value has **not** been written to live configuration by this task.

## Combined .67 candidate

**A - Earlier Solar fill trajectory.** `solar_surplus_fill_deadline_margin_minutes` defaults to 60, accepts finite nonnegative minutes (including zero), and is independent of Morning Slow's cutoff. Dynamic charge opportunity ends at trusted same-day sunset minus this margin. Solar forecast safety remains 1.20. The aggregate budget and independent export-eligibility timing retain their sunset horizon. Reaching the effective deadline releases restrictive Solar charge ownership to normal safe MSC charging; a full battery can still export later surplus under the existing PV-only rules. Missing/invalid timing and provider evidence fail closed. Requests remain bounded by the normal safe/trusted charge request.

**B - Solar physical-export saturation feedback.** Only final Solar charge ownership in observed Automated/exact MSC can relax its restrictive trajectory ceiling. The request is `min(normal safe request, baseline trajectory + physical relief)`; relief starts at zero. A positive generic physical limit supplies evidence, never an export command. Normal high export permission, normal PV MAX, MSC, Demand Window import ownership and `battery_export_owner=none` remain intact.

- Entry is actual export at or above `limit - 0.2 kW`; each increase is at most 0.4 kW after two fresh coherent observations following the successfully applied charge target. New targets require new feedback; unchanged observations cannot stack increases. Further increases also require measured charging above baseline.
- One new coherent export observation below `limit - 0.5 kW` reduces active relief by 1.2 kW, floored at zero. Export below `limit - 1.0 kW` hard-resets relief. After export-driven reduction/reset, three fresh observations at/above entry are required for another increase.
- Relevant PV/load/import/export observations must remain trusted, fresh and coherent within five seconds; measured battery-flow evidence and no grid import must support the probe. Estimated PV, Solcast potential and `hidden_pv_surplus_kw` cannot authorize relief.
- Trust/ownership loss, Manual/Force, Morning Slow, exact-full, disabled/invalid configuration and actuator failures clear relief. Baseline/cap changes clear relief and restart feedback, retaining an existing retry requirement for the same physical limit. Application rechecks release stale relief to baseline, or expired Solar charge authority to the normal request.
- Morning Slow keeps its existing binary charge-cap release/retention behavior and tuning. Its settings do not govern Solar. No new relief tuning settings are introduced.

Decision Trace and API diagnostics distinguish effective fill deadline/margin, baseline ceiling, final requested ceiling, actual export, configured physical limit, relief amount, active/trust state, confirmation count and reason. These describe decision evidence, not observed actuator settlement.

## Independent-review correction and current gate

- Independent review reproduced active Solar relief surviving a feedback timestamp regression to before the command epoch. The authorized production correction moved the existing regression reset before the pre-command waiting return. Regression clears relief and dependent confirmation/retry/command/feedback state, returning to the current Solar baseline while otherwise valid Solar ownership continues.
- The tests-first integration case reproduced **1.21 kW actual versus 0.81 kW baseline** before the correction. It now verifies removal of the earned 0.4 kW relief, unchanged Solar/MSC/PV MAX/export ownership and recovery only after baseline reapplication and fresh confirmations.
- On 2026-10-07 the user explicitly approved **0.4 kW**, superseding the earlier 0.5 kW discussion; provenance remains in `DECISIONS.md`. The increment is unchanged.
- The first correction validation stopped at **1 failed, 33 passed / 20 subtests passed** because the old pre-command test supplied timestamp -1 after accepting 0 yet expected probing without baseline reapplication. The user has now explicitly classified that sequence as regression and approved correcting the characterization. That conflict is resolved.
- The corrected waiting test accepts observation 0, establishes command epoch 2, then receives observations 1 and 2: no regression, no post-command confirmation, no reset. Two later fresh observations are still required for a 0.4 kW probe. A separate startup-regression test retains the 0 -> -1 sequence, requires reset to a nonzero 1.0 kW baseline, prevents probes without baseline reapplication and then requires two fresh confirmations. Existing active-relief regression and waiting coverage remains intact.
- **Continuation validation:** complete physical-relief suite **35 passed / 20 subtests passed**, 198 warnings; affected Solar/controller suites **140 passed / 221 subtests passed**, 200 warnings; independent protection suites **250 passed / 266 subtests passed**, exactly two frozen Phase 2 tests deselected, 198 warnings. Protection coverage includes Morning Slow, Manual/Force, Demand Window, battery-export safety, provider freshness, actuator fallback/capabilities, MSC/PV MAX/export permission and fill-deadline behavior.
- Full suite ran **once** for this continuation: `python -B -m pytest -q -p no:cacheprovider --disable-warnings --tb=short tests` returned **907 passed / 872 subtests passed**, exactly the **two frozen Phase 2 failures**, 201 warnings, in 67.42 seconds. Their character remains export 25 versus closed 0 and MSC requested before observed export closure. **No unexpected failures occurred.**
- Compileall for `app` and all five candidate Python test files and `git diff --check` passed. SHA-256 comparison with the starting candidate confirms no production file changed during this continuation; only the physical-relief characterization and these current-state/handover records changed. The two frozen tests remain untouched.
- Final independent review returned **ACCEPT FOR CHECKPOINT COMMIT**. The candidate and two documentation corrections were committed and pushed at `e2eba5431ee1fcfd36f9632c21f10e53f81c592d`. Current work is release metadata/documentation preparation only, not release/live approval. Live remains .66, known-good rollback .65, and .67 is not live-proven.

## Initial candidate validation (before independent review)

- Tests-first characterization captured only the approved missing features; no separate out-of-scope production defect was established.
- Final new/changed characterization gate: **144 passed / 186 subtests passed**.
- Existing affected suites: **345 passed / 332 subtests passed**, with exactly the two frozen Phase 2 tests deselected.
- Independent protections: **383 passed / 411 subtests passed**.
- Existing Solar test bodies and Morning Slow control methods retain their prior assertions/behavior; legacy sunset-focused fixtures explicitly select margin zero.
- The affected and independent groups were repeated after a narrow startup-retry correction: entering from below saturation with zero relief retains the ordinary two-observation entry, while an actual downward hard reset requires three. Final results above passed without unexpected failures.
- Full suite ran **once**: `python -B -m pytest -q -p no:cacheprovider --disable-warnings --tb=short tests` recorded **904 passed / 872 subtests passed**, exactly **2 frozen Phase 2 failures**, 201 warnings, in 67.75 seconds. The failure character remains export 25 versus closed 0, and MSC requested before observed export closure. No additional failures occurred.
- Initial compileall for `app` and all five changed/new Python test files and `git diff --check` passed. These pre-review results are superseded by the completed continuation gate above. That historical candidate comprised 13 modified and 3 new files; it is now committed in the accepted source checkpoint, with no .67 live acceptance.

The only frozen failures are `test_exact_msc_does_not_reopen_before_export_is_observed_closed` and `test_return_from_discharge_waits_for_observed_close_before_requesting_msc` in `tests/test_msc_baseline_overlay_contract.py`. Do not weaken, skip or repair them inside this candidate.

## Diagnostics and historical validation

- Released .65 raised only the 24 Hour Trace download ceiling from 256 MiB to 512 MiB after .64 live output reached approximately 3.5 MB per 15-minute flush. Current .66 retains the approximately 1000-cycle in-memory trace and rolling 24-hour JSONL archive with 15-minute persistence.
- Downloads retain at most 4 active requests, a 2-minute lifetime, 25 segments and 512 MiB. Diagnostics I/O remains isolated from control; uncertain clocks pause persistent writes/pruning, possible-gap reporting is conservative, and abrupt shutdown can lose an unflushed interval.
- Historical provider/regression checkpoint `f203387a445fcf9e4ea569861ca3d35703b1b7b9` passed 842 tests / 778 subtests with exactly the two frozen Phase 2 failures. The .66 metadata-only release-preparation gate repeated those counts; its API/version subset passed 48 tests / 53 subtests. Compileall and diff checks passed. Those were historical local gates; the authoritative .66 live results are above.
- .66 provider authority remains process-local UNVERIFIED/VALID/EXPIRED with baseline plus qualifying poll advancement, retained deadlines, source-epoch invalidation and immediate safe restoration. Global forecast-age consumers and provider freshness semantics are unchanged by .67.

## Protected behavior and parked work

- Manual/Force, Demand Window import ownership, observed Automated authority, fail-closed telemetry and settlement, battery floor, reserve/forecast safeguards, ordinary MSC/PV-only flow and explicit battery-export ownership remain protected.
- Morning Dump is operator-accepted for its observed case: deliberate export, approximately 15 kW actual export without import, PV MAX 25 kW, about 15% floor and safe relinquishment. Another Morning Dump trace is not a new .67 blocker.
- Recorded Morning Slow operator tuning remains enabled, 2 kW, until 11:00, minimum FiT $0.01/kWh, base-load allowance 2 kW, sunset cutoff 1 hour. Neither those values nor the discussed 0.5 kW Morning Slow physical headroom become software defaults.
- **Evening Boost reserve-estimator instability remains parked.** `_battery_soc_required_to_sunrise()` projects instantaneous load across the overnight horizon; earlier .62/.63 evidence showed implausible reserve above 100% and unstable Boost/MSC transitions. No fix is part of .67.
- **Evening Boost import-cost trust interaction remains parked.** A significant optimizer import/top-up chunk >= 0.01 kWh with missing/nonfinite/untrusted price can leave the daily cost floor unknown; later valid prices do not repair it. Earlier .63 evidence included approximately 18.412 kWh imported and $0.2037716/kWh highest actual import price while the floor remained untrusted. A separate review must decide provenance and guard behavior.
- Export Value Gate remains advisory-only; Actual Import Cost Guard remains enforcing. Climate Manager, Morning Dump redesign, Phase 2 settlement and broader controller cleanup are outside this task.
- The 27 September Solar aggregate-budget threshold-switching observation remains parked for evidence-led monitoring; .67 does not claim to fix or redesign that gate.

## Next action and controlled acceptance

Next decision: review the local `2.3.56-haos67` release-preparation diff and authorize its checkpoint commit separately. The Phase 1 source checkpoint is already accepted, committed and pushed. This task leaves release metadata unstaged and uncommitted. Tagging, image build/publication, release/deployment, restart, the live 15 kW operator setting and .67 live acceptance require separate authorization; none has occurred.

The timing margin intentionally raises necessary ESS requests earlier within the existing safe bound. Closed-loop relief still needs live evidence that additional charging preserves actual export; local tests do not prove that plant response. Review the bounded release-preparation diff before any later release, and retain the established .65 operational rollback.

For monitor-only/dry-run review, compare margin 0 and 60 requests, confirm deadline/normal-cap bounds and unchanged ownership permissions, and verify no live writes. Stateful relief cannot acquire post-command authority from a simulated decision alone.

After separately approved release/deployment and operator configuration, capture the earlier fill trajectory and deadline relinquishment, full-battery late surplus export, two-observation 0.4 kW increases, export-preserving PV/charge response, immediate reduction/hard reset and three-observation retry. Also capture loss/recovery of provider or flow trust, Manual/Force/Morning Slow exclusion and Demand Window import blocking. Verify MSC, normal PV MAX/high export permission and no battery export throughout. .65 remains the recorded rollback; this local task requires no live rollback action.
