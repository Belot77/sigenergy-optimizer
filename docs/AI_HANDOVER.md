# SigEnergy Optimizer AI Handover

Last consolidated: 2026-09-14

Read root and project `AGENTS.md`, then `CURRENT_STATE.md`, `CONTROL_CONTRACT.md`, `ROADMAP.md`, and `DECISIONS.md`. Verify the exact branch tip, worktree status, and remote synchronization directly with Git before editing.

## Live baseline and rollback

Live remains `2.3.44-haos55`. Morning Dump failed closed under apparently valid live telemetry; this was conservative behavior, but `.55` is not live-accepted.

Before any `.56` live test, separately confirm and prepare a rollback path for the current `.55` installation. Do not claim that a current `.55` backup or rollback artifact exists without authoritative verification. Historical known-good reference `2.3.42-haos53`, tag `v2.3.42-haos53`, commit `19f3c70d24dc086737d5956a1c66cad230287edd`, remains useful evidence. No rollback is underway.

GitHub `main` remains `c624f0b4392634cf19276186ba46f4b80268627b` (`Record Phase 1 live acceptance`), whose phase-status documentation is stale because Phase 1 was reopened.

## Active checkpoint

- Worktree: `C:\Projects\sigenergy_optimizer-phase1-remediation`
- Branch: `fix/phase1-audit-remediation`
- Package 5 actuator/fallback production/test checkpoint: `4c9c0e2663357a65e8cdf80d7c6d1cf7ea8d0473` (`Harden actuator fallback and settlement handling`).
- Package 5 chatter/reopen production/test checkpoint: `e119f6f` (`Repair Morning Slow MSC ceiling chatter`).
- Package 6A capability-trust production/test checkpoint: `f95f9ce01a53e66a533edbfe3bd423e4ee3dafd3` (`Repair Package 6A capability trust`).
- Package 6A documentation checkpoint: `f1ade7b0db500cadcdfccce7e2fd5e7d3a5cf573`.
- Package 6A documentation-sync checkpoint: `a60f71063ef4c3c3043e18f5f1ef4eb85787bc69`.
- Current committed HEAD: `df90c365fc0413ad0ce048a2796ab8df30ec0c0a` (`Repair telemetry and forecast trust`).
- Before candidate preparation, the branch was pushed and synchronized with `origin/fix/phase1-audit-remediation` at that commit, with divergence 0/0 and a clean worktree.
- Candidate `2.3.45-haos56` is now prepared locally only as uncommitted metadata and documentation changes. It is not pushed, tagged, built, published, released, deployed, installed, restarted, live-tested, or live-accepted. Live remains `2.3.44-haos55`; no Home Assistant or Sigenergy write has occurred.

The pre-repair remediation content is present in live `.55`, but renewed Phase 1 live acceptance is withheld. The repair commit and local `.56` candidate identity have not been deployed or live-tested.

Protected worktrees remain unchanged. Never modify, reset, or stash `C:\Projects\sigenergy_optimizer` or `C:\Projects\sigenergy_optimizer-pv-hotfix`. The Phase 2 worktree remains frozen.

## Live `.55` regression repair and `.56` candidate

Commit `df90c365fc0413ad0ce048a2796ab8df30ec0c0a` (`Repair telemetry and forecast trust`) is pushed and synchronized. It repairs two independent trust defects behind the live Morning Dump fail-closed result:

- one batched, read-only `/api/template` request enriches freshness-sensitive REST snapshots with timezone-aware State-object `last_reported` only when entity ID, exact state string, and timezone-aware `last_updated` match; mismatches or failure remain conservative, and request receipt time is never freshness evidence;
- rated battery capacity is treated as static capability only when its current value is available, finite, positive, and has an explicit supported unit;
- detailed Solcast periods must be ordered, timezone-aware, finite, non-negative, cadence-continuous, and cover the same-local-day interval required by Morning Dump, Evening Boost, or Battery Full Safeguard. Sparse or gapped data fails closed.

Dynamic live telemetry retains the 120-second limit, and unrelated aggregate forecast observations retain the 600-second limit. Manual/Force ownership, Maximum Self Consumption, PV MAX, Demand Window, deliberate Morning Dump battery-export ownership, and unrelated controls are unchanged.

Validation passed: affected tests **121 passed, 127 subtests passed**; independent protections **253 passed, 2 frozen Phase 2 tests deselected, 245 subtests passed**; full suite **478 passed, 421 subtests passed**, with only the two expected frozen Phase 2 failures. Compileall and `git diff --check` passed.

The compatibility probe used the actual add-on Home Assistant credentials and received HTTP 200 from `/api/template`. REST `last_reported` remained frozen while template `last_reported` advanced, including unchanged rated capacity. Entity ID, exact state string, and the same `last_updated` instant all correlated, so the repair does not substitute receipt time for observation freshness.

Package 7 remains blocked pending renewed Phase 1 live acceptance. Phase 2 remains frozen. Before any `.56` live test, confirm and prepare rollback for the current `.55` installation; no backup is asserted without authoritative evidence.

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

The exact-full repair is committed and pushed at `067d52cc5e231d4c3ffd4be2d8c0d058bfbf19b2` and included in live `.55`; renewed live acceptance is withheld.

## Solar Surplus PV-margin repair

The repair included in live `.55` retains entry strictly above 0.5 kW and permits continuation strictly above 0.2 kW only when the immediately previous decision genuinely held a Solar-Surplus-owned high `MSC_SURPLUS_CEILING` under observed Automated ownership. At or below 0.2 kW it stops; re-entry again requires more than 0.5 kW. Forecast hysteresis remains 2.0 start / 1.25 continue. No timer or smoothing is added.

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

Review the uncommitted `2.3.45-haos56` identity/documentation candidate and decide whether to commit it. Push, tag, build, publish, release, deployment, installation, restart, and live testing remain separate approval boundaries.

Do not release, deploy, install, restart, or claim live acceptance as part of either decision. Preserve the Phase 2 close -> observe closed -> request MSC -> observe exact MSC -> reopen contract and its two expected failing tests.
