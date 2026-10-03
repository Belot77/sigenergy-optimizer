# SigEnergy Optimizer AI Handover

Last consolidated: 2026-10-03

Read root and project `AGENTS.md`, then `CURRENT_STATE.md`, `CONTROL_CONTRACT.md`, `DECISIONS.md`, and `ROADMAP.md`. Verify worktree, branch, HEAD, tracking, and status before editing.

## Current identities

- Worktree: `C:\Projects\sigenergy_optimizer-phase1-remediation`
- Branch: `fix/phase1-audit-remediation`
- Current HEAD before the local Solar implementation and release preparation: `8f77a602b93aaa6a7464c46dddf7bff7e20a56d5`.
- Local release candidate: `2.3.52-haos63`, uncommitted and unreleased; not tagged, built, published, installed, or live-accepted.
- Published Phase 1 release: `2.3.51-haos62`; tag `v2.3.51-haos62` points to release-source commit `70f1766354c163b9259a3e5e128f8e083528fc64`.
- GitHub Actions run `36643883464` and its build/publish job succeeded.
- Published multi-architecture image: `ghcr.io/belot77/sigenergy-optimizer:2.3.51-haos62`, OCI index digest `sha256:dcc4f941df120dbd6e704f87218b72331363c3d1a58014bb10adbf6fdc38b888`, platforms `linux/amd64` and `linux/arm64`.
- OCI version `2.3.51-haos62` and revision `70f1766354c163b9259a3e5e128f8e083528fc64` match the expected release and source.
- Phase 1 code-validation HEAD before the docs-only checkpoint: `7649d185b71fe08fab2636801396e2ae7c793a13`
- The later documentation-only publication-record commit is present on both `origin/fix/phase1-audit-remediation` and promoted remote `main`; it is distinct from the tagged release-source commit.
- Current live release: `2.3.51-haos62`, confirmed by the operator as installed/restarted and live.
- Known-good rollback: `2.3.46-haos57`, commit `7144fd3d52069e3e8ef1e4df9bc8943bdd65dbe7`.
- The new dynamic Solar ESS charge ceiling is LOCAL/UNRELEASED and is not part of live `.62`.

## Local Phase 1 checkpoints

1. `61f79bc` clamps trusted available battery energy to trusted rated capacity while retaining raw diagnostics.
2. `99ef0f0` preserves house supply during observed-settlement safe fallback.
3. `aca3497` adds trusted timed Morning refill protection and physical export relief.
4. `11ae480` introduced zero-delay event response.
5. `7cfcd77` corrected `11ae480` by restoring the deliberate fixed 3-second pre-decision coalescing safeguard.
6. `bb6af74` decouples Evening Boost's dedicated minimum FiT from the ordinary export tier.
7. `7649d18` updates stale safe-fallback settlement test expectations only.
8. Uncommitted `.63` adds bounded dynamic Solar ESS charge-ceiling ownership after final arbitration, with stricter evidence and immediate relinquishment to the normal charge request.

Do not hide or reverse the relationship between `11ae480` and `7cfcd77`.

The current Solar implementation changes are in `app/optimizer.py`, `tests/test_solar_surplus_redesign.py`, and the intentionally untracked `tests/test_phase1_solar_dynamic_charge_ceiling_characterization.py`, which must be retained for eventual commit. Release preparation reconciles documentation and established version surfaces only; the validated algorithm and tests remain unchanged.

## Validation gate

The final local gate for dynamic Solar charge ownership collected 755 tests: 753 passed, 2 failed, 197 warnings, and 717 subtests passed. The dynamic Solar characterization, including grid-import charging precedence, passed all 14 tests and 14 subtests. The only failures are the frozen Phase 2 tests:

- `tests/test_msc_baseline_overlay_contract.py::MscBaselineOverlayContractTests::test_exact_msc_does_not_reopen_before_export_is_observed_closed`
- `tests/test_msc_baseline_overlay_contract.py::MscBaselineOverlayContractTests::test_return_from_discharge_waits_for_observed_close_before_requesting_msc`

`python -m compileall -q app` and `git diff --check` passed. **The local `.63` Solar code gate passed; `.62` is live.** Independent pre-commit review found no remaining production/safety blocker after correction of grid-import charging precedence. The `.63` candidate still requires the project lead's commit decision, commit/push, build/publication, manual installation, and one controlled live Solar validation. No `.63` release or live acceptance is claimed. Solar acceptance alone will not close Phase 1; the separate Evening Boost transition-stability defect must then be characterized, remediated, and live-accepted before Phase 2.

## Protected behavior

- Manual and Force remain user-owned. Observed Automated ownership is required for permissive automatic control.
- Available-energy data fails closed unless fresh, finite, nonnegative, and in a supported unit. Trusted over-cap data is clamped only when rated capacity is trusted, and raw diagnostics remain visible. The live-proven near-full Solar exception for genuinely untrusted telemetry remains.
- Safe fallback closes export, requests MSC, clamps ESS discharge while unresolved, and waits for observed export closure plus observed MSC before restoring normal import/ESS/PV capability. Demand Window can retain import blocking. Fallback never creates `BATTERY_EXPORT`.
- Morning Dump remains deliberate `BATTERY_EXPORT`, requires trusted timed refill feasibility, assumes no future relief, and preserves the 15% operator floor.
- Morning Slow owns only its charging restriction: MSC, normal PV MAX, and normal high export permission remain. Refill opportunity runs to same-day sunset minus cutoff; the Morning Slow end time is not the refill deadline. Forecast or physical relief releases only the artificial slow cap.
- Solar may own a lower ESS charge ceiling only after final arbitration selects `solar_surplus_policy_active` and stricter fresh, trusted, continuous detailed evidence passes. It subtracts future bounded PV-minus-load opportunity after the current interval from K times fill need to 100%, allocates the remainder to the current interval, and rounds positive requests up to 0.01 kW within the existing normal safe/trusted request. Abundant future opportunity permits zero charging. Lost evidence immediately releases only this restriction; existing Solar eligibility remains independent. Morning Slow excludes Solar, Demand Window retains import ownership, Manual/Force remain user-owned, and Solar stays MSC/PV-only with normal PV MAX and no `BATTERY_EXPORT` authority.
- Physical relief defaults disabled at `0.0 / 0.0`; it responds to coherent measured site export and does not enforce a 15 kW export cap.
- Relevant events use a fixed non-sliding 3-second pre-decision window, with no immediate first-event or catch-up tick. Startup is immediate and the heartbeat remains 60 seconds.
- Evening Boost has dedicated `evening_boost_min_feedin_price`, default and hard minimum `$0.01/kWh`, no arbitrary upper bound, and explicit owner `evening_export_boost`. It may qualify below the ordinary tier, but never below one cent. Existing safety, reserve, forecast, actual import-cost, ownership, and settlement guards remain.

## Live evidence and operator tuning

Earlier live `.61` evidence proved the near-full Solar exception around 93.9-96.7% SoC, a clean Morning Slow -> Solar transition, roughly 2 kW charging while Morning Slow owned the cap, normal higher charging afterward, and one clean desired-export transition. The 25 kW ceiling behaved as permission.

Operator-provided live `.62` Morning Slow evidence from 3 October showed MSC operation, safe load-serving battery behaviour, the 25 kW ceiling acting as PV-surplus permission rather than stored-battery export, and clean closure when Morning Slow ended. The operator explicitly accepted Morning Dump; another dedicated Morning Dump trace is not a release blocker. The new `.63` Solar charge ceiling has no live evidence yet.

On 2 October, poor-solar evidence showed Morning Slow inactive with trusted refill timing evidence and `morning_slow_refill_timing_reason="refill_infeasible_even_at_normal_capability"`. This positively shows the 2 kW slow restriction was not imposed when refill could not be proved. The operator's later Force Full Import + PV was a manual action, separate from Morning Slow. Morning Dump was operator-disabled during this run, which adds no Morning Dump acceptance evidence; the prior operator acceptance remains recorded above.

Live `.62` Evening Boost deliberate `BATTERY_EXPORT` works when qualified, but repeated transitions were observed between `evening_export_boost` / Command Discharging and MSC while SoC and FiT were effectively stable and short-term household load changed sharply. Source inspection found `_battery_soc_required_to_sunrise()` projects instantaneous `load_kw` across the remaining overnight horizon, moving `soc_required` / sunrise reserve sharply with transient load and allowing repeated ownership acquisition/release. Treat this as a separate narrow Phase 1 transition-stability defect. No fix is designed or implemented in this documentation step; preserve reserve, forecast, `BATTERY_EXPORT` ownership, import-cost, and settlement protections.

Live Morning Slow operator tuning is enabled, 2 kW, until 11:00, minimum FiT `$0.01/kWh`, base-load allowance 2 kW, sunset cutoff 1 hour. Morning Dump's operator floor is 15%. Discussed physical-relief values `15.0 / 0.5 kW` remain unconfigured, are not defaults, and are NOT part of this release.

## Unresolved and parked

- Before configuring `15.0 / 0.5`, determine whether 15 kW is a Morning Slow relief threshold or a hard network cap. Current code implements only the relief-threshold meaning.
- The 27 September Solar aggregate-budget threshold switching observation remains an evidence-led follow-up and is not claimed fixed by the dynamic charge ceiling. Observe it during `.63` Solar live acceptance; do not invent a separate fix without evidence.
- Keep the two Phase 2 tests frozen through `.63` Solar live acceptance and the subsequent separate Evening Boost transition-stability characterization, remediation, and live acceptance. Keep `15.0 / 0.5` unconfigured and outside this release.
- After both Phase 1 items are live-accepted, proceed in order: Phase 2 transition safety -> short ownership audit -> architecture/refactor and project cleanup -> full GUI/UX redesign/fix -> Climate Manager -> later diagnostics/replay/load modelling/dynamic scheduling.

## Exact next action

Obtain the project lead's commit decision for the independently reviewed `.63` candidate, then commit/push if authorized, build/publish, manually install, and perform one controlled live Solar validation. Check dynamic charge requests and relinquishment while MSC/PV-only operation, normal PV MAX, higher-priority owners, and Demand Window import blocking remain intact. Observe the 27 September threshold-switching follow-up in that trace without assuming `.63` fixes it. After Solar acceptance, characterize and remediate the separate Evening Boost transition-stability defect and obtain its live acceptance. Only after both Phase 1 items are accepted may Phase 2 begin. These release and live actions are not authorized by this documentation step; stop before staging or committing.
