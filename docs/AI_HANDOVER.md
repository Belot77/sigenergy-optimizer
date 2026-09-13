# SigEnergy Optimizer AI Handover

Last consolidated: 2026-09-13

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
- Package 6A capability-trust production/test checkpoint: `f95f9ce01a53e66a533edbfe3bd423e4ee3dafd3` (`Repair Package 6A capability trust`).
- Package 6A documentation checkpoint: `f1ade7b0db500cadcdfccce7e2fd5e7d3a5cf573`.
- Package 6A documentation-sync checkpoint: `a60f71063ef4c3c3043e18f5f1ef4eb85787bc69`.
- Current committed local HEAD before the uncommitted candidate-metadata edits, and local documentation checkpoint commit: `87b9a4390c558f895bcb1e7de69cab535c522f77` (`Record pushed remediation checkpoint`).
- The Solar Surplus implementation commit is `7ded75f9155d7002150a7308f03eb9510f5beb39` (`Stabilize Solar Surplus bypass hysteresis`). The pushed remediation checkpoint and current upstream tip remain `c12da071a6bd18849eff125771ac525b85fd3470`; the local documentation checkpoint is `87b9a4390c558f895bcb1e7de69cab535c522f77`, so the branch was ahead 1 / behind 0 before these edits.
- Candidate metadata for `2.3.44-haos55` is now prepared locally but remains uncommitted and unpushed. No `.55` tag exists, and no `.55` build, publish, release, deployment, installation, restart, live test, or live acceptance has occurred. Live remains `2.3.43-haos54`, rollback remains `2.3.42-haos53`, and no Home Assistant or Sigenergy write has occurred.

Nothing from the current remediation branch has been deployed, live-tested, or live-accepted.

Protected worktrees remain unchanged. Never modify, reset, or stash `C:\Projects\sigenergy_optimizer` or `C:\Projects\sigenergy_optimizer-pv-hotfix`. The Phase 2 worktree remains frozen.

## Package 5 result

Actuator/fallback reliability preserves explicit application outcomes, failed primary and fallback accounting, independent later safety attempts after exceptions, partial/asymmetric failure handling, remembered-state rollback before commit, cycle diagnostics, and immediate observed readback for an ordinary export safety close. Service-call success is not observed inverter state.

Morning Slow's high MSC ceiling now uses the existing trusted ordinary-MSC flow classification rather than closing solely when trusted battery discharge crosses `0.10 kW`. Trusted load-serving discharge with grid export below the existing meaningful threshold is compatible with the ceiling. Meaningful simultaneous battery discharge plus grid export and unknown or untrusted battery/grid-export evidence remain fail-closed. Solar Surplus retains its raw battery-discharge protection. Ordinary positive-FiT behavior, battery-export ownership, Manual/Force, Demand Window, PV MAX, and unrelated safety behavior are unchanged. The `0.10 kW` battery tolerance and `0.5 kW` meaningful grid-export threshold are unchanged, and no timer, deadband, hysteresis, cycle count, settlement duration, or reopen delay was added.

Characterization confirms `0.094 kW` and `0.101 kW` discharge with negligible export both retain the `25 kW` ceiling; alternating those values remains `25 / 25 / 25 / 25 kW`. A `1.0 kW` discharge with `0.499999 kW` export may remain load-serving/open, while exactly `0.5 kW` export with discharge above `0.10 kW` is simultaneous/closed. The `0.273 kW` discharge plus `1.837 kW` export case remains fail-closed, and the approximately `3.2 kW` load-serving case remains independently closed through `closed_no_daytime_pv`. Unknown battery flow and unknown, stale, or non-finite grid-export flow close.

Validation: chatter characterization **11 passed, 191 warnings**; affected actuator and Value Gate tests **108 passed, 191 warnings**; focused protection **200 collected, 198 passed, 2 deselected, 191 warnings**; complete suite **419 collected, 417 passed, 2 failed, 191 warnings**. The only failures were `test_exact_msc_does_not_reopen_before_export_is_observed_closed` and `test_return_from_discharge_waits_for_observed_close_before_requesting_msc`, both frozen for Phase 2. Compileall and `git diff --check` passed.

## Package 6A result

Package 6A repairs the existing grid-export, ESS-charge, and ESS-discharge capability sources. Automated control treats trusted hardware capability as an upper bound and configured ESS baselines as requests, not evidence. It keeps charge and discharge separate, takes the minimum of current trusted sources within a domain, and falls back to that domain's cached trusted rating and then `ESS_LIMIT_FALLBACK_KW`. Invalid, unavailable, non-finite, or out-of-range evidence cannot enlarge a capability. Trusted grid-export number-entity maximum metadata bounds Automated export.

Manual/Force modes retain exact pre-Package-6A capability inputs and fallback behavior through an isolated legacy compatibility path. This temporary freeze covers Manual, Full Import, Full Import + PV, Full Export, Block Flow, and manual ESS charge/discharge overrides; it is not long-term capability policy and must be revisited only after all currently planned work.

Validation: Package 6A characterization **21 passed**; Manual/Force protection **13 passed, 5 deselected**; Automated export/ESS actuator protection **115 passed**; and additional Manual/Force freeze regressions passed. The full suite collected **440 tests: 438 passed, 2 failed, 191 warnings**. Only the two frozen Phase 2 tests failed: `test_exact_msc_does_not_reopen_before_export_is_observed_closed` and `test_return_from_discharge_waits_for_observed_close_before_requesting_msc`. Compileall passed, and `git diff --check` passed apart from the prior line-ending notices.

## Package 6B status

The read-only investigation is complete; implementation is deferred and no production change was made. Do not invent speculative grid-import or PV-capability architecture. The known ESS-to-grid-import coupling remains parked. Do not call 25 kW universal operator truth from defaults; the current live flap specifically captured PV MAX and the high export ceiling at 25 kW.

## Exact-full MSC repair and parked fallback discrepancy

The proven live exact-full defect had two mechanisms:

- Stale-direct/fallback: fresh direct discharge around `0.007 kW` permits exact-full 25 kW; stale direct evidence selects a measured-grid-flow residual around `0.75 kW` and closes it. Alternating freshness reproduces `25 -> 0 -> 25 -> 0`. Live normal samples later showed residual and direct values materially disagreeing despite effectively simultaneous Home Assistant `last_reported` timestamps. This stale-direct/measured-grid-flow fallback discrepancy remains parked; no fallback redesign is part of the current work.
- Fresh-direct load-serving: a clean live capture moved from exact-full 25 kW with direct discharge around `0.005 kW` to fresh direct discharge around `1.629 kW`, PV below load, and grid export zero. The committed repair at `067d52c` now reuses trusted ordinary-MSC flow safety: load-serving battery discharge with grid export below the meaningful threshold is compatible with `MSC_SURPLUS_CEILING`; meaningful simultaneous discharge and export and unknown or untrusted relevant flow remain fail-closed. It creates no `BATTERY_EXPORT` owner and remains in Maximum Self Consumption.

Regression coverage for the committed exact-full repair proves the trusted load-serving case remains open, simultaneous battery discharge plus meaningful grid export closes, and unknown relevant flow closes. The raw `pv_only_discharge_ok` predicate remains available for its other consumers and diagnostics but is no longer the decisive exact-full MSC transition gate.

The exact-full repair is committed and pushed at `067d52cc5e231d4c3ffd4be2d8c0d058bfbf19b2`, but is not merged, released, deployed, installed, restarted, live-tested, or live-accepted.

## Committed local Solar Surplus PV-margin repair

The locally committed repair retains entry strictly above 0.5 kW and permits continuation strictly above 0.2 kW only when the immediately previous decision genuinely held a Solar-Surplus-owned high `MSC_SURPLUS_CEILING` under observed Automated ownership. At or below 0.2 kW it stops; re-entry again requires more than 0.5 kW. Forecast hysteresis remains 2.0 start / 1.25 continue. No timer or smoothing is added.

The new `solar_surplus_stop_pv_margin` / `SOLAR_SURPLUS_STOP_PV_MARGIN` setting defaults to 0.2 kW. Initialization and runtime API updates preserve `0.0 <= solar_surplus_stop_pv_margin <= solar_surplus_min_pv_margin`; a valid batch is checked as its final requested pair before mutation. Solar Surplus remains an MSC surplus-ceiling policy, creates no battery-export authority, and does not redesign EMS or PV MAX.

Validation evidence: focused API/config **11 passed**; affected Solar Surplus **104 passed**; independent protections **45 passed, 2 frozen Phase 2 tests deselected**; full suite **459 collected, 457 passed, 2 failed**, with only `test_exact_msc_does_not_reopen_before_export_is_observed_closed` and `test_return_from_discharge_waits_for_observed_close_before_requesting_msc` failing as expected. Compileall passed. `git diff --check` passed apart from the existing line-ending conversion notices.

## Protected and parked work

- The stale-direct/measured-grid-flow fallback discrepancy remains parked.
- Morning Slow behavior is unchanged; its forecast-feasibility discrepancy remains parked and is not a confirmed defect.
- Evening Boost is unchanged.
- Manual/Force behavior remains frozen.
- Phase 2 remains frozen, including its two expected failing transition-settlement tests.
- Package 7 remains after renewed Phase 1 live acceptance.
- Climate Manager remains later work and is not part of this repair.

## Next action

Review the locally prepared, uncommitted and unpushed `2.3.44-haos55` candidate metadata, then decide separately whether to commit it. No final candidate commit SHA exists yet. Tagging, building, publishing, releasing, deploying, installing, restarting, live testing, and live acceptance remain separate later boundaries requiring explicit approval.

Do not release, deploy, install, restart, or claim live acceptance as part of either decision. Preserve the Phase 2 close -> observe closed -> request MSC -> observe exact MSC -> reopen contract and its two expected failing tests.
