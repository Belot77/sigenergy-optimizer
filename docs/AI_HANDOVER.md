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
- worktree clean after Package 1 checkpoint commit and verified push.

Package 1 is committed at `9538cc84c1235f33d52ebc2ecdf1b6b9c64896b0` and pushed to `origin/fix/phase1-audit-remediation`. Preserve that checkpoint; it has not been merged, released, deployed, or live-tested.

Protected: never modify/reset/stash `C:\Projects\sigenergy_optimizer` (intentionally dirty `refactor/msc-baseline-overlays` at `bce8411d5274fe17fb8d883e8e7faf43e9ce8d43`) or `C:\Projects\sigenergy_optimizer-pv-hotfix` (clean haos53 reference at `19f3c70d24dc086737d5956a1c66cad230287edd`). Phase 2 worktree `C:\Projects\sigenergy_optimizer-phase2-transition`, branch `phase2/msc-transition-settlement`, is frozen at `c624f0b4392634cf19276186ba46f4b80268627b` and was clean when last verified.

## Phase and gate

Phase 1 is reopened for audit remediation after a proven live Morning Slow low-SoC defect and broader fail-closed/control-authority findings. All remediation, validation, and renewed Phase 1 live acceptance must finish before Phase 2. Phase 2 is paused/frozen, not active.

The Morning Slow defect comes from the production gate `morning_slow_charge_rate_kw + min_grid_transfer_kw`: live tuning creates a hidden `2 + 1 = 3 kW` PV-surplus threshold. Split these concepts; do not tune `MIN_GRID_TRANSFER_KW` as a workaround.

## Production Remediation Package 1 checkpoint

Package 1 is implemented in `app/models.py` and `app/optimizer.py`, automated-validated, committed at `9538cc84c1235f33d52ebc2ecdf1b6b9c64896b0`, pushed to `origin/fix/phase1-audit-remediation`, and not deployed or live-tested. Its test artifacts are `tests/test_haos49_failure_characterization.py` and `tests/test_phase1_authority_fail_closed_characterization.py`.

The completed contracts require observed Automated ownership, fail Demand Window closed for import when untrustworthy, treat HA-control service success as a request rather than observation, and prevent unknown current grid limits from suppressing required closure or authorizing permissive opening. Manual and Force remain protected.

Validation: characterization **11 passed, 191 warnings**; authority/Demand Window/HA/manual-force **37 passed**; MSC/export/Value Gate/positive-FiT **120 passed, 2 Phase 2 deselected**; Evening Boost **5 passed**; corrected legacy HA-control test **1 passed**. The broader suite was **291 passed, 2 failed, 191 warnings**, with exactly `test_return_from_discharge_waits_for_observed_close_before_requesting_msc` and `test_exact_msc_does_not_reopen_before_export_is_observed_closed` deferred to Phase 2. `python -m compileall -q app` and `git diff --check` passed.

The next engineering package is Morning control repair. Separate Morning Slow policy from the overloaded grid-transfer threshold while preserving MSC, the configured slow charge rate, normal PV MAX, independently owned ordinary MSC surplus export, and no battery-export authority. Do not change `MIN_GRID_TRANSFER_KW` as the repair.

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

Exact next action: begin the separate Morning control repair package from the clean pushed Package 1 checkpoint. Do not change `MIN_GRID_TRANSFER_KW` as a workaround and do not begin Phase 2.
