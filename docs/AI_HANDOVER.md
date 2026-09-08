# SigEnergy Optimizer AI Handover

Last consolidated: 2026-09-08

This is concise continuation context for a new ChatGPT/Codex thread. Read root and project `AGENTS.md`, then `CURRENT_STATE.md`, `CONTROL_CONTRACT.md`, `ROADMAP.md`, and `DECISIONS.md`. Verify Git state directly before editing.

## Live baseline and rollback

Live is `2.3.43-haos54`. Home Assistant observed runtime source `083b1fcc241b0d86271f5da80538d4e224fc6433`; its production code is identical to tagged candidate `174136280ed1c516b7666b4600622ce9544bb8e0`.

Known-good emergency rollback is `2.3.42-haos53`, tag `v2.3.42-haos53`, commit `19f3c70d24dc086737d5956a1c66cad230287edd`. If separately authorized, rollback means stop the add-on, restore Sig Opt only, then verify EMS, PV MAX, export, and HA control. No rollback is underway.

GitHub `main` remains `c624f0b4392634cf19276186ba46f4b80268627b` (`Record Phase 1 live acceptance`), whose phase-status documentation is now stale.

## Active and protected worktrees

Active remediation:

- `C:\Projects\sigenergy_optimizer-phase1-remediation`
- branch `fix/phase1-audit-remediation`
- Package 1 production checkpoint `9538cc84c1235f33d52ebc2ecdf1b6b9c64896b0`; verify exact current HEAD directly with Git because docs-only commits may be children of it.
- Package 2 production/test checkpoint `d3294cb`; verify exact current HEAD directly with Git because a docs-only commit may be a child of it.
- Package 3 production/test checkpoint `91b0075`; verify exact current HEAD directly with Git because a future docs-only commit may be a child of it.
- Package 4A production/test checkpoint `d3e1d56`; verify exact current HEAD directly with Git because a future docs-only commit may be a child of it.
- Package 4B production/test checkpoint `19a6279`; verify exact current HEAD directly with Git because a future docs-only commit may be a child of it.
- worktree clean after the local Package 4B checkpoint commit, before this documentation update.

Package 1 is committed at `9538cc84c1235f33d52ebc2ecdf1b6b9c64896b0` and pushed to `origin/fix/phase1-audit-remediation`. Preserve that checkpoint; it has not been merged, released, deployed, or live-tested.

Package 2 is committed locally at `d3294cb` and has not been pushed, merged, tagged, released, deployed, installed, or live-tested.

Package 3 is committed locally at `91b0075` and has not been pushed, merged, tagged, released, deployed, installed, or live-tested.

Package 4A is committed locally at `d3e1d56` and has not been pushed, merged, tagged, released, deployed, installed, or live-tested.

Package 4B is committed locally at `19a6279` and has not been pushed, merged, tagged, released, deployed, installed, or live-tested.

Protected: never modify/reset/stash `C:\Projects\sigenergy_optimizer` (intentionally dirty `refactor/msc-baseline-overlays` at `bce8411d5274fe17fb8d883e8e7faf43e9ce8d43`) or `C:\Projects\sigenergy_optimizer-pv-hotfix` (clean haos53 reference at `19f3c70d24dc086737d5956a1c66cad230287edd`). Phase 2 worktree `C:\Projects\sigenergy_optimizer-phase2-transition`, branch `phase2/msc-transition-settlement`, is frozen at `c624f0b4392634cf19276186ba46f4b80268627b` and was clean when last verified.

## Phase and gate

Phase 1 is reopened for audit remediation after a proven live Morning Slow low-SoC defect and broader fail-closed/control-authority findings. Packages 1, 2, 3, 4A, and 4B are complete and automated-validated, but all remaining remediation, validation, and renewed Phase 1 live acceptance must finish before Phase 2. Phase 2 is paused/frozen, not active.

## Production Remediation Package 1 checkpoint

Package 1 is implemented in `app/models.py` and `app/optimizer.py`, automated-validated, committed at `9538cc84c1235f33d52ebc2ecdf1b6b9c64896b0`, pushed to `origin/fix/phase1-audit-remediation`, and not deployed or live-tested. Its test artifacts are `tests/test_haos49_failure_characterization.py` and `tests/test_phase1_authority_fail_closed_characterization.py`.

The completed contracts require observed Automated ownership, fail Demand Window closed for import when untrustworthy, treat HA-control service success as a request rather than observation, and prevent unknown current grid limits from suppressing required closure or authorizing permissive opening. Manual and Force remain protected.

Validation: characterization **11 passed, 191 warnings**; authority/Demand Window/HA/manual-force **37 passed**; MSC/export/Value Gate/positive-FiT **120 passed, 2 Phase 2 deselected**; Evening Boost **5 passed**; corrected legacy HA-control test **1 passed**. The broader suite was **291 passed, 2 failed, 191 warnings**, with exactly `test_return_from_discharge_waits_for_observed_close_before_requesting_msc` and `test_exact_msc_does_not_reopen_before_export_is_observed_closed` deferred to Phase 2. `python -m compileall -q app` and `git diff --check` passed.

## Production Remediation Package 2 checkpoint

Package 2 repairs Morning Slow low-SoC export gating in `app/optimizer.py` and adds its characterization to `tests/test_msc_baseline_overlay_contract.py`. It is automated-validated and committed locally at `d3294cb`, but is not yet pushed, deployed, installed, or live-tested.

Below-minimum-SoC export closure now applies only when Morning Slow is inactive. Active Morning Slow no longer requires the legacy `morning_slow_charge_rate_kw + min_grid_transfer_kw` surplus threshold; unrelated uses of `MIN_GRID_TRANSFER_KW` are unchanged. Morning Slow still owns only the ESS charge rate, remains in Maximum Self Consumption with normal PV MAX, relies on independently owned ordinary MSC-surplus permission with `MSC_SURPLUS_CEILING` intent, and creates no battery-export owner. Unobserved Automated ownership and unsafe or unknown battery flow remain blocked, and Package 1 protections remain intact.

Validation: new characterization **4 passed, 33 deselected**; focused Morning Slow/MSC **24 passed, 120 deselected**; Package 1 authority/fail-closed **11 passed**; Remote EMS/Manual/Force/unavailable mode **8 passed, 4 deselected**; Value Gate/positive-FiT/negative-price/MSC-intent/battery-export **95 passed, 31 deselected**. The complete suite collected 297 tests and finished **295 passed, 2 failed, 191 warnings**, with only the two frozen Phase 2 transition tests failing. `python -m compileall -q app tests` and `git diff --check` passed.

## Production Remediation Package 3 checkpoint

Package 3 repairs Battery-export safety in `app/optimizer.py` and adds its characterization to `tests/test_msc_baseline_overlay_contract.py`. It is automated-validated and committed locally at `91b0075`, but is not yet pushed, deployed, installed, or live-tested.

The positive-FiT-specific ESS-discharge clamp now applies only when final live intent is `BATTERY_EXPORT` and final ownership is `positive_fit_override`. Raw positive-FiT eligibility no longer suppresses ordinary battery-to-house discharge or another deliberate owner's discharge authority. Existing fail-closed flow handling, explicit positive-FiT safeguards, the negative-price `0.01 kW` clamp, deliberate export owners, Packages 1 and 2, and frozen Phase 2 behavior remain protected.

Validation: Package 3 characterization **8 passed, 7 subtests passed**; existing flow/owner protection **12 passed, 7 subtests passed**; deliberate-owner protection **18 passed, 6 subtests passed**; broader MSC/export/Value Gate/positive-FiT/battery-export regression **101 passed, 31 deselected, 71 subtests passed**. The complete suite collected 303 tests and finished **301 passed, 2 failed, 191 warnings**, with only the two frozen Phase 2 transition tests failing. `python -m compileall -q app tests` and `git diff --check` passed.

## Production Remediation Package 4A checkpoint

Package 4A hardens tariff telemetry trust in `app/optimizer.py` and `app/state_store.py`, with characterization in `tests/test_phase1_tariff_telemetry_trust_characterization.py`. It is automated-validated and committed locally at `d3e1d56` (`Harden tariff telemetry trust`), but has not been pushed, merged, tagged, released, deployed, installed, or live-tested.

Non-finite import prices no longer establish tariff-dependent import or charging authority; non-finite or unavailable FiT no longer establishes permissive FiT-dependent export authority. Missing or untrusted import price cannot establish Standby Holdoff, missing or untrusted FiT cannot establish cheap-positive import, and non-finite optimizer import-cost evidence is rejected from trusted persistence and summaries. Existing finite estimated-positive, actual-negative, positive-FiT, Morning Slow, battery-export ownership, and trusted negative-price clamp behavior remains preserved. The trust gates are branch-specific and do not globally seize unrelated controls.

Validation: Package 4A characterization **23 passed**; tariff/import-cost reference **14 passed, 4 subtests passed**; Package 1 **23 passed, 61 subtests passed**; Package 2 focused **15 passed, 6 subtests passed, 124 deselected**; Package 3 **13 passed, 10 subtests passed**; broader tariff regression **131 passed, 89 subtests passed**. The complete suite collected 326 tests and finished **324 passed, 2 failed, 191 warnings**, with exactly the two frozen Phase 2 transition tests failing. `python -m compileall -q app tests` and `git diff --check` passed; no unexpected regression remained.

Package 4 is split into 4A Tariff trust (complete and automated-validated), 4B SoC/battery-energy trust (complete and automated-validated), 4C Live PV/load trust (next), and 4D Forecast/solar-clock trust (pending).

## Production Remediation Package 4B checkpoint

Package 4B hardens SoC and battery-energy telemetry trust in `app/models.py` and `app/optimizer.py`, with characterization in `tests/test_phase1_battery_telemetry_trust_characterization.py`. It is automated-validated and committed locally at `19a6279` (`Harden battery telemetry trust`), but has not been pushed, merged, tagged, released, deployed, installed, or live-tested.

`SolarState` now carries explicit trust for SoC, capacity, and available discharge energy. Fresh finite SoC from 0% through 100% remains trusted, including genuine 0% and 100%; missing, unavailable, unknown, non-finite, out-of-range, or stale values cannot become permissive proof. Synthetic capacity and stale available energy cannot authorize behavior, while missing available energy remains the conservative numeric 0 kWh. Battery-dependent top-up, deliberate-export, exact-full, and refill decisions require the trusted facts they use; ordinary trusted MSC surplus remains independent of unavailable SoC where it does not require that proof.

Package 4B preserves Package 1 authority/fail-closed protections, Package 2 Morning Slow, Package 3 battery-export ownership, Package 4A tariff trust, Manual/Force, Demand Window, advisory-only Value Gate, normal PV MAX, Morning Dump's 15% floor, Evening Boost, negative-price behavior, ordinary positive-FiT ownership boundaries, genuine fresh 0% and exact-full 100% behavior, conservative missing-energy behavior, and ordinary MSC independence from unavailable SoC.

Validation: characterization **22 passed, 191 warnings**; narrow regression **90 collected, 88 passed, 2 frozen Phase 2 tests deselected, 191 warnings**; complete suite **348 collected, 346 passed, 2 failed, 191 warnings**, with only the two frozen Phase 2 transition tests failing. `python -m compileall -q app tests` and `git diff --check` passed, with no unexpected functional regression.

Package 4 status: 4A Tariff trust and 4B SoC/battery-energy trust are complete and automated-validated; 4C Live PV/load trust is next; 4D Forecast/solar-clock trust remains pending.

## Parked live-control warning

A live `2.3.43-haos54` observation on 2026-09-08 showed repeated PV-only MSC export-ceiling flapping between 25 kW and closed (`0.01 kW`). The direct battery sensor remained near zero discharge while derived flow arithmetic intermittently indicated up to approximately 1.43 kW battery discharge, triggering the simultaneous battery-discharge plus grid-export fail-closed rule before later cycles reopened the MSC ceiling. Cross-sensor snapshot incoherence and/or post-actuation settlement lag is suspected, not proven; the observation does not prove an actual deliberate battery dump.

Do not weaken the existing battery-export fail-closed protection. Characterize telemetry coherence first in 4C and repair it there if that is the defect; move any settlement/readback-specific remainder to Package 5. Package 4C Live PV/load trust is the immediate next task.

## Protected behavior

- Manual and Force remain user-owned; unknown ownership is not Automated authority.
- Morning Slow owns ESS charge rate only, remains MSC, retains normal PV MAX, and never owns export permission or deliberate battery export.
- Morning Dump's 15% floor and Evening Boost behavior are intentional.
- Demand Window is the higher-priority import block.
- Value Gate remains advisory-only.
- Ordinary positive-FiT export must not implicitly create battery export.
- Unavailable actuator-state telemetry and service-call success are not proof of settled state.

## Material operator tuning

Operator tuning, not software defaults: PV MAX/high export ceiling 25 kW; minimum SoC floor 20%; minimum export target SoC 90%; Morning Slow enabled at 2 kW until 11:00, minimum FiT 0.01, base load 2 kW; Morning Dump enabled with 15% floor; Evening Boost enabled with 35% floor, 1.1 safety multiplier, and 100 kWh minimum tomorrow forecast; `MIN_GRID_TRANSFER_KW` 1 kW; Forecast Safety Charging 1.35; Forecast Safety Export 1.1; Solar Surplus Bypass enabled 2.0/1.25/0.5; spike minimum SoC configured 60% but not enforced; cheap-positive threshold 0.015 $/kWh; daytime top-up maximum SoC 50%; target battery charge 2 kW.

## Approved non-positive import policy

Approved but not implemented: trusted actual import price `<= 0 $/kWh` is an explicit high-priority charging owner. Use Grid First plus maximum safe/permitted grid-import and ESS-charge capabilities in separate domains. It overrides Morning Slow charging/EMS ownership and Morning Dump; Demand Window, Manual/Force, and hardware/safety limits remain higher protections. Positive price must not steal Morning Slow; transition back to positive while eligible returns to MSC plus slow charge. Non-positive import does not imply PV curtailment.

Do not invent the unresolved exact-zero/high-FiT choice or PV MAX behavior during non-positive import.

## Frozen Phase 2 contract

Future return from deliberate battery export: close export -> later observe closed -> request MSC -> later observe exact MSC -> reopen the normal 25 kW ceiling. Entering deliberate battery export must settle its export target before discharge EMS. Service-call success is not observation. Preserve the two existing expected tests named in `CURRENT_STATE.md`.

## Continuation method

Recommended next session: Codex in the active remediation worktree, high reasoning, normal/standard speed; use a fresh thread with this handover loaded. Inspect narrowly, stage one remediation package at a time, and keep release/live actions separately authorized.

Exact next action: begin Package 4C Live PV/load trust from the local Package 4B checkpoint, first characterizing the parked PV/load/grid telemetry-coherence hypothesis. Verify the exact active HEAD directly with Git rather than treating `19a6279` as volatile current-HEAD truth, and do not begin Phase 2.
