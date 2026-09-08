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
- Package 4D production/test checkpoint: `44c63e80fa72655087504f5c612df10e6b77109f` (`Harden forecast and solar-clock telemetry trust`)
- Package 4D is locally committed and automated-validated, but not pushed, merged, tagged, released, deployed, installed, restarted, or live-tested.
- Remote branch was last verified at `db8133567b3543b2d7aaff4e18e241ab9c409c44`, before Package 4D. Do not claim the remote contains `44c63e8`.
- Package 4A Tariff trust, 4B SoC/battery-energy trust, and 4C Live PV/load trust are complete, automated-validated, and pushed. Package 4D Forecast/solar-clock trust is complete and automated-validated locally only.
- None of Packages 4A through 4D is deployed or live-accepted.

Protected worktrees remain unchanged. Never modify/reset/stash `C:\Projects\sigenergy_optimizer` or `C:\Projects\sigenergy_optimizer-pv-hotfix`. The Phase 2 worktree remains frozen.

## Package 4D result

`SolarState` now retains separate trust for remaining, today, and tomorrow aggregate forecasts; the detailed forecast source; sun state; sunrise; and sunset. The fields are `forecast_remaining_observation_trusted`, `forecast_today_observation_trusted`, `forecast_tomorrow_observation_trusted`, `solcast_detailed_source_trusted`, `sun_state_observation_trusted`, `sunrise_observation_trusted`, and `sunset_observation_trusted`.

Forecast trust uses the existing 600-second forecast freshness setting. Sun trust uses the existing 120-second live-data setting, HA `last_reported`/`last_updated` metadata, and the existing future meaning of `next_rising`/`next_setting`. No configuration or new timing threshold was added.

Fresh finite forecasts, including genuine zero, remain valid. Missing, malformed, unavailable, non-finite, or stale evidence cannot become permissive proof, while conservative numeric-zero arithmetic and forecast-safety charging are preserved. Solar Surplus Bypass/solar override require trusted remaining forecast; Standby Holdoff requires trusted today and remaining forecasts; Evening Boost requires trusted tomorrow and detailed forecast evidence.

Detailed points remain structurally compatible but require finite timestamps and `pv_estimate` values before becoming permissive evidence. Untrusted source data, infinities, and the proven prior-day case cannot authorize Morning Dump. No horizon, point-count, completeness, intended-day, or new issue-age policy was invented.

Morning Dump requires trusted detailed source, sun state, and sunrise evidence while retaining deliberate battery-export ownership, its 15% floor, tariff/battery trust, and priority. `close_to_sunset` requires trusted sunset evidence, so missing, stale, malformed, or prior sunset data cannot relax export forecast guards. Wall-clock time remains separate from HA sun telemetry, and no sun tolerance was added. Morning Dump post-window grace remains unresolved.

Validation: Package 4D characterization **26 passed, 191 warnings**; focused regression **88 passed, 191 warnings**; complete suite **389 collected, 387 passed, 2 failed, 191 warnings**. The only failures were `test_exact_msc_does_not_reopen_before_export_is_observed_closed` and `test_return_from_discharge_waits_for_observed_close_before_requesting_msc`, both frozen for Phase 2. Compileall and `git diff --check` passed; no unexpected functional regression remained.

## Package 5 is next

Package 5 actuator and fallback hardening must characterize, without preselecting a fix:

- earlier `25 kW -> closed -> 25 kW` chatter with `battery_within_tolerance -> simultaneous_battery_discharge_and_grid_export -> battery_within_tolerance` after Package 4C repaired stale/untrusted PV/load evidence;
- fresh direct battery evidence around the hard `0.10 kW` boundary: about `0.094 kW` could allow the Morning Slow high ceiling, just over `0.10 kW` could block it, and observed load-serving discharge was commonly around `0.13-0.34 kW`; this is distinct from the earlier derived-flow/coherence issue;
- actuator/readback/flow settlement evidence: one captured cycle had desired export closed, the ceiling effectively closed or being closed, grid export about `1.837 kW`, and fresh direct discharge about `0.273 kW`; fail-closed classification was correct, and neither command failure nor settled inverter state is proven by service-call success.

Package 5 also retains failed-cycle fallback reliability, fallback command checking, and partial/asymmetric actuator failure scope. It must distinguish unsafe battery-backed export, harmless/load-serving flow, settlement/readback lag, and unknown evidence. The simultaneous battery-discharge plus grid-export rule remains fail-closed, and ordinary positive-FiT export must not become battery export. No larger tolerance, deadband, timer, cycle hysteresis, or settlement duration is approved.

## Frozen Phase 2 and next action

Phase 2 remains frozen. Preserve its close -> observe closed -> request MSC -> observe exact MSC -> reopen contract and the two expected failing tests. Live remains `2.3.43-haos54`; rollback remains `2.3.42-haos53`, tag `v2.3.42-haos53`, commit `19f3c70d24dc086737d5956a1c66cad230287edd`.

Exact next action: commit and push the Package 4D production/test checkpoint and this documentation checkpoint before beginning Package 5 characterization. Deployment, live testing, and Phase 2 require separate authorization.
