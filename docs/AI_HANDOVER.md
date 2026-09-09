# SigEnergy Optimizer AI Handover

Last consolidated: 2026-09-09

Read root and project `AGENTS.md`, then `CURRENT_STATE.md`, `CONTROL_CONTRACT.md`, `ROADMAP.md`, and `DECISIONS.md`. Verify the exact branch tip, worktree status, and remote synchronization directly with Git before editing.

## Live baseline and rollback

Live remains `2.3.43-haos54`. Home Assistant observed runtime source `083b1fcc241b0d86271f5da80538d4e224fc6433`; its production code is identical to tagged candidate `174136280ed1c516b7666b4600622ce9544bb8e0`.

Known-good emergency rollback remains `2.3.42-haos53`, tag `v2.3.42-haos53`, commit `19f3c70d24dc086737d5956a1c66cad230287edd`. If separately authorized, rollback means stop the add-on, restore Sig Opt only, then verify EMS, PV MAX, export, and HA control. No rollback is underway.

GitHub `main` remains `c624f0b4392634cf19276186ba46f4b80268627b` (`Record Phase 1 live acceptance`), whose phase-status documentation is stale because Phase 1 was reopened.

## Active checkpoint

- Worktree: `C:\Projects\sigenergy_optimizer-phase1-remediation`
- Branch: `fix/phase1-audit-remediation`
- Package 5 actuator/fallback production/test checkpoint: `4c9c0e2663357a65e8cdf80d7c6d1cf7ea8d0473` (`Harden actuator fallback and settlement handling`).
- Package 5 chatter/reopen production/test checkpoint: `e119f6f` (`Repair Morning Slow MSC ceiling chatter`).
- Both Package 5 subparts are complete and automated-validated. They have not been merged, tagged, released, deployed, installed, restarted, live-tested, or live-accepted.

Protected worktrees remain unchanged. Never modify, reset, or stash `C:\Projects\sigenergy_optimizer` or `C:\Projects\sigenergy_optimizer-pv-hotfix`. The Phase 2 worktree remains frozen.

## Package 5 result

Actuator/fallback reliability preserves explicit application outcomes, failed primary and fallback accounting, independent later safety attempts after exceptions, partial/asymmetric failure handling, remembered-state rollback before commit, cycle diagnostics, and immediate observed readback for an ordinary export safety close. Service-call success is not observed inverter state.

Morning Slow's high MSC ceiling now uses the existing trusted ordinary-MSC flow classification rather than closing solely when trusted battery discharge crosses `0.10 kW`. Trusted load-serving discharge with grid export below the existing meaningful threshold is compatible with the ceiling. Meaningful simultaneous battery discharge plus grid export and unknown or untrusted battery/grid-export evidence remain fail-closed. Solar Surplus retains its raw battery-discharge protection. Ordinary positive-FiT behavior, battery-export ownership, Manual/Force, Demand Window, PV MAX, and unrelated safety behavior are unchanged. The `0.10 kW` battery tolerance and `0.5 kW` meaningful grid-export threshold are unchanged, and no timer, deadband, hysteresis, cycle count, settlement duration, or reopen delay was added.

Characterization confirms `0.094 kW` and `0.101 kW` discharge with negligible export both retain the `25 kW` ceiling; alternating those values remains `25 / 25 / 25 / 25 kW`. A `1.0 kW` discharge with `0.499999 kW` export may remain load-serving/open, while exactly `0.5 kW` export with discharge above `0.10 kW` is simultaneous/closed. The `0.273 kW` discharge plus `1.837 kW` export case remains fail-closed, and the approximately `3.2 kW` load-serving case remains independently closed through `closed_no_daytime_pv`. Unknown battery flow and unknown, stale, or non-finite grid-export flow close.

Validation: chatter characterization **11 passed, 191 warnings**; affected actuator and Value Gate tests **108 passed, 191 warnings**; focused protection **200 collected, 198 passed, 2 deselected, 191 warnings**; complete suite **419 collected, 417 passed, 2 failed, 191 warnings**. The only failures were `test_exact_msc_does_not_reopen_before_export_is_observed_closed` and `test_return_from_discharge_waits_for_observed_close_before_requesting_msc`, both frozen for Phase 2. Compileall and `git diff --check` passed.

## Parked Morning Slow investigation

The Morning Slow forecast-feasibility discrepancy remains parked and is not a confirmed defect. A later bounded investigation must compare the exact trusted remaining forecast, battery capacity, available discharge energy, refill need, slow-charge end, hours left, configured base load, load need, forecast-safety multiplier, final `required_kwh`, and eligibility result. Do not change operator settings or defaults from the current evidence.

## Next action and frozen work

Package 6 capability modelling is next: separate grid-import, grid-export, ESS-charge, ESS-discharge, and PV capability domains, and prevent configured baselines from enlarging smaller trusted observed hardware caps.

Phase 2 remains frozen. Preserve its close -> observe closed -> request MSC -> observe exact MSC -> reopen contract and the two expected failing tests. Deployment and live testing require separate authorization.
