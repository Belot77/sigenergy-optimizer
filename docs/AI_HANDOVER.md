# SigEnergy Optimizer AI Handover

Last consolidated: 2026-09-09

This is concise continuation context for a new ChatGPT/Codex thread. Read root and project `AGENTS.md`, then `CURRENT_STATE.md`, `CONTROL_CONTRACT.md`, `ROADMAP.md`, and `DECISIONS.md`. Verify Git state directly before editing.

## Live baseline and rollback

Live is `2.3.43-haos54`. Home Assistant observed runtime source `083b1fcc241b0d86271f5da80538d4e224fc6433`; its production code is identical to tagged candidate `174136280ed1c516b7666b4600622ce9544bb8e0`.

Known-good emergency rollback is `2.3.42-haos53`, tag `v2.3.42-haos53`, commit `19f3c70d24dc086737d5956a1c66cad230287edd`. If separately authorized, rollback means stop the add-on, restore Sig Opt only, then verify EMS, PV MAX, export, and HA control. No rollback is underway.

GitHub `main` remains `c624f0b4392634cf19276186ba46f4b80268627b` (`Record Phase 1 live acceptance`), whose phase-status documentation is now stale.

## Active checkpoint

- Worktree: `C:\Projects\sigenergy_optimizer-phase1-remediation`
- Branch: `fix/phase1-audit-remediation`
- Package 5 actuator/fallback production/test checkpoint: `4c9c0e2663357a65e8cdf80d7c6d1cf7ea8d0473` (`Harden actuator fallback and settlement handling`).
- Package 5 actuator/fallback reliability is locally committed and automated-validated, but not pushed, merged, tagged, released, deployed, installed, restarted, live-tested, or live-accepted.
- Remote branch was last verified at `6b1c6f2b84e955c597d4f57953e6c4ef24203725` (`Record Package 4D checkpoint state`). Do not claim the remote contains `4c9c0e2`.
- Package 4A Tariff trust, 4B SoC/battery-energy trust, and 4C Live PV/load trust are complete, automated-validated, and pushed. Package 4D Forecast/solar-clock trust is also on the remote remediation branch. None of Packages 4A through 5 is deployed or live-accepted.

Protected worktrees remain unchanged. Never modify/reset/stash `C:\Projects\sigenergy_optimizer` or `C:\Projects\sigenergy_optimizer-pv-hotfix`. The Phase 2 worktree remains frozen.

## Package 5 actuator/fallback result

`_apply` now returns an explicit application result. Required write failures propagate; fallback returns are checked; ordinary fallback exceptions remain visible while later independent safety actions continue; and partial/asymmetric failure makes the overall application fail. Successful fallback requests do not turn a failed primary application into observed success. `_tick` advances remembered applied state only after success, restores prior remembered state after failed pre-commit application, and retains the failure diagnostic. This is not transactional rollback.

Ordinary export safety-close now requires one immediate observed readback. Open, unavailable, non-finite, or otherwise untrusted readback leaves application failed and preserves later close reissue. Service-call success is not observed inverter state.

Validation: characterization **19 passed, 191 warnings**; focused regression **84 collected, 82 passed, 2 deselected, 191 warnings**; full suite **408 collected, 406 passed, 2 failed, 191 warnings**. The only failures were `test_exact_msc_does_not_reopen_before_export_is_observed_closed` and `test_return_from_discharge_waits_for_observed_close_before_requesting_msc`, both frozen for Phase 2. Compileall and `git diff --check` passed; no unexpected functional regression remained.

## Package 5 chatter/reopen is next

Fresh direct battery discharge at about `0.094 kW` can permit the high MSC/PV-only ceiling, while about `0.101 kW` can close it, allowing fresh snapshots to produce `25 -> 0 -> 25 -> 0 kW`. This records current policy behavior without declaring the `0.10 kW` threshold wrong or selecting a larger threshold, deadband, timer, N-cycle hysteresis, settlement duration, or reopen delay.

Investigation hypothesis only: under MSC, the high export ceiling is permission for genuine surplus, not a command to export or discharge the battery. Determine whether the existing contract can suppress unnecessary chatter while preserving fail-closed treatment of meaningful simultaneous battery discharge plus grid export. The characterized case near `0.273 kW` battery discharge and `1.837 kW` grid export remains `simultaneous_battery_discharge_and_grid_export` and fail-closed. The separate load-serving case near `1.6 kW` PV, `4.7 kW` load, and `3.2 kW` battery discharge was correctly kept export closed; it does not establish that all load-serving discharge should open export.

## Parked Morning Slow investigation

Actual live operator settings were: enabled `True`, until `11:00`, charge rate `2 kW`, minimum FiT `0.01 $/kWh`, base-load allowance `2 kW`, and sunset cutoff `1 hour`. These are not software defaults. Morning Slow was observed active near 15.9% SoC, 6.4 kWh available energy, 40 kWh capacity, 57.8 kWh remaining forecast, 3.5 kW PV, 0.9 kW load, and 2.57 kW battery charging. Those displayed values are difficult to reconcile with the existing refill-plus-load forecast-feasibility calculation, but this is parked investigation evidence, not a confirmed bug or an approved settings/default change.

Later capture the exact trusted remaining forecast, battery capacity, available discharge energy, calculated refill need, slow-charge end timestamp, hours left, configured base load, calculated load need, forecast-safety charging multiplier, final `required_kwh`, and eligibility result. Compare them to distinguish operator tuning, stale/different inputs, a calculation/provenance mismatch, or a real defect.

## Frozen Phase 2 and next action

Phase 2 remains frozen. Preserve its close -> observe closed -> request MSC -> observe exact MSC -> reopen contract and the two expected failing tests. Live remains `2.3.43-haos54`; rollback remains `2.3.42-haos53`, tag `v2.3.42-haos53`, commit `19f3c70d24dc086737d5956a1c66cad230287edd`.

Exact next action: commit this documentation checkpoint, then separately decide whether to push the local checkpoints before beginning Package 5 chatter/reopen characterization. Deployment, live testing, and Phase 2 require separate authorization.
