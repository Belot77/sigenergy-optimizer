# SigEnergy Optimizer AI Handover

Last consolidated: 2026-09-30

Read root and project `AGENTS.md`, then `CURRENT_STATE.md`, `CONTROL_CONTRACT.md`, `DECISIONS.md`, and `ROADMAP.md`. Verify worktree, branch, HEAD, tracking, and status before editing.

## Current identities

- Worktree: `C:\Projects\sigenergy_optimizer-phase1-remediation`
- Branch: `fix/phase1-audit-remediation`
- Prepared Phase 1 release-candidate identity: `2.3.51-haos62`; expected later tag: `v2.3.51-haos62`.
- Release-identity preparation is uncommitted atop starting HEAD `1d3617714e42f7bc5a19aec489cfbc0622a81520`.
- Phase 1 code-validation HEAD before the docs-only checkpoint: `7649d185b71fe08fab2636801396e2ae7c793a13`
- Validated Phase 1 checkpoint through `1d3617714e42f7bc5a19aec489cfbc0622a81520` is safely present on `origin/fix/phase1-audit-remediation`.
- Remote `main` is unchanged at `de5b5af082533a48ffb6d0d300f636cbcb4463ad`; before this release-identity working-tree update, the feature branch was 9 commits ahead and 0 behind `main`.
- Current known live release: `2.3.50-haos61`, tag `v2.3.50-haos61`, commit `76db9e43588f0e9862d73e4e8402c0b5ce9773a7`.
- Known-good rollback: `2.3.46-haos57`, commit `7144fd3d52069e3e8ef1e4df9bc8943bdd65dbe7`.
- The `.62` candidate is not yet committed, tagged, built, published, promoted to `main`, deployed, installed, restarted, or live-accepted.

## Local Phase 1 checkpoints

1. `61f79bc` clamps trusted available battery energy to trusted rated capacity while retaining raw diagnostics.
2. `99ef0f0` preserves house supply during observed-settlement safe fallback.
3. `aca3497` adds trusted timed Morning refill protection and physical export relief.
4. `11ae480` introduced zero-delay event response.
5. `7cfcd77` corrected `11ae480` by restoring the deliberate fixed 3-second pre-decision coalescing safeguard.
6. `bb6af74` decouples Evening Boost's dedicated minimum FiT from the ordinary export tier.
7. `7649d18` updates stale safe-fallback settlement test expectations only.

Do not hide or reverse the relationship between `11ae480` and `7cfcd77`.

## Validation gate

Phase 1 validation collected 735 tests: 733 passed, 2 failed, with 197 warnings. The only failures are the frozen Phase 2 tests:

- `tests/test_msc_baseline_overlay_contract.py::MscBaselineOverlayContractTests::test_exact_msc_does_not_reopen_before_export_is_observed_closed`
- `tests/test_msc_baseline_overlay_contract.py::MscBaselineOverlayContractTests::test_return_from_discharge_waits_for_observed_close_before_requesting_msc`

`python -m compileall -q app` and `git diff --check` passed. The earlier unexpected safe-fallback failure was a stale protection-test expectation, not a production defect. **Phase 1 code validation passed locally and the checkpoint is published to the remote feature branch**, but the `.62` release-candidate identity remains uncommitted and `main` promotion, tagging/build/publication, deployment, restart, and live acceptance remain outstanding.

## Protected behavior

- Manual and Force remain user-owned. Observed Automated ownership is required for permissive automatic control.
- Available-energy data fails closed unless fresh, finite, nonnegative, and in a supported unit. Trusted over-cap data is clamped only when rated capacity is trusted, and raw diagnostics remain visible. The live-proven near-full Solar exception for genuinely untrusted telemetry remains.
- Safe fallback closes export, requests MSC, clamps ESS discharge while unresolved, and waits for observed export closure plus observed MSC before restoring normal import/ESS/PV capability. Demand Window can retain import blocking. Fallback never creates `BATTERY_EXPORT`.
- Morning Dump remains deliberate `BATTERY_EXPORT`, requires trusted timed refill feasibility, assumes no future relief, and preserves the 15% operator floor.
- Morning Slow owns only its charging restriction: MSC, normal PV MAX, and normal high export permission remain. Refill opportunity runs to same-day sunset minus cutoff; the Morning Slow end time is not the refill deadline. Forecast or physical relief releases only the artificial slow cap.
- Physical relief defaults disabled at `0.0 / 0.0`; it responds to coherent measured site export and does not enforce a 15 kW export cap.
- Relevant events use a fixed non-sliding 3-second pre-decision window, with no immediate first-event or catch-up tick. Startup is immediate and the heartbeat remains 60 seconds.
- Evening Boost has dedicated `evening_boost_min_feedin_price`, default and hard minimum `$0.01/kWh`, no arbitrary upper bound, and explicit owner `evening_export_boost`. It may qualify below the ordinary tier, but never below one cent. Existing safety, reserve, forecast, actual import-cost, ownership, and settlement guards remain.

## Live evidence and operator tuning

Live `.61` proved the near-full Solar exception around 93.9-96.7% SoC, a clean Morning Slow -> Solar transition, roughly 2 kW charging while Morning Slow owned the cap, normal higher charging afterward, and one clean desired-export transition. The 25 kW ceiling behaved as permission. None of the seven new local behaviors is live-proven.

Live Morning Slow operator tuning is enabled, 2 kW, until 11:00, minimum FiT `$0.01/kWh`, base-load allowance 2 kW, sunset cutoff 1 hour. Morning Dump's operator floor is 15%. Discussed future physical-relief values `15.0 / 0.5 kW` are neither live nor defaults.

## Unresolved and parked

- Before configuring `15.0 / 0.5`, determine whether 15 kW is a Morning Slow relief threshold or a hard network cap. Current code implements only the relief-threshold meaning.
- The 27 September Solar aggregate-budget switching observation remains a separate evidence-led Phase 1 follow-up; the seven local checkpoints do not establish a fix.
- Keep the two Phase 2 tests frozen until Phase 1 release/live acceptance.
- Then proceed in order: Phase 2 transition safety -> short ownership audit -> architecture/refactor and project cleanup -> full GUI/UX redesign/fix -> Climate Manager -> later diagnostics/replay/load modelling/dynamic scheduling.

## Exact next action

Review the prepared `2.3.51-haos62` identity and explicitly authorize the release-candidate commit. Promotion to `main`, tagging, build/publication, deployment, restart, and live acceptance require later decisions. Do not start Phase 2 or configure `15.0 / 0.5` until its semantic question is resolved.
