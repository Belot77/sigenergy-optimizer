# SigEnergy Optimizer AI Handover

Last consolidated: 2026-09-06

Keep this handover concise and current. Update it at meaningful checkpoints, phase transitions, and before handing work to a new ChatGPT/Codex session. Do not retain obsolete historical state merely because it once appeared here; `CURRENT_STATE.md` is the first place to look for present state.

This is the minimum engineering context needed to continue safely. Read in this order:

1. root and project `AGENTS.md`;
2. `docs/CURRENT_STATE.md` for the volatile checkpoint and exact next action;
3. `docs/CONTROL_CONTRACT.md` for durable semantics;
4. `docs/ROADMAP.md` for phase gates;
5. `docs/DECISIONS.md` for approved rationale.

Use `docs/CHANGELOG.md` only when release history is needed. Do not reconstruct current state from old changelog entries.

## Project and live baseline

SigEnergy Optimizer is a safety-first Home Assistant add-on that coordinates SigEnergy battery, grid import/export, PV, tariff, and forecast-aware decisions.

The current live and Phase 1 accepted release is `2.3.43-haos54`. Live runtime reported `2.3.43-haos54` with container source commit `083b1fcc241b0d86271f5da80538d4e224fc6433`, the docs-only child of tagged/tested production candidate `174136280ed1c516b7666b4600622ce9544bb8e0`. Emergency rollback remains `2.3.42-haos53`, tag `v2.3.42-haos53`, commit `19f3c70d24dc086737d5956a1c66cad230287edd`.

## Worktree boundaries

Only the explicitly assigned worktree is writable for a task. Current development uses:

- `C:\Projects\sigenergy_optimizer-haos53-refactor`
- branch `refactor/msc-baseline-overlays-haos53`

Protected references:

- `C:\Projects\sigenergy_optimizer` contains intentional dirty legacy work. Never modify, reset, or stash it.
- `C:\Projects\sigenergy_optimizer-pv-hotfix` is the clean haos53/main release reference. Never modify it.
- The old `feature/safety-actuator-refactor` branch is conceptual reference only. Never wholesale merge it.

Always verify the exact branch, HEAD, and cleanliness directly with Git in the assigned worktree before editing. Use `CURRENT_STATE.md` only for the relevant checkpoint/base SHA and expected logical working set; stop on a material mismatch.

## Current architecture

Phase 1 separates export capacity from stored-battery export authority:

- `EXPORT_BLOCKED`: no live export permission;
- `MSC_SURPLUS_CEILING`: a ceiling for genuine inverter-controlled surplus while remaining in Maximum Self Consumption;
- `BATTERY_EXPORT`: explicit deliberate stored-energy sale owned by an authorized policy.

A positive export ceiling is not a battery-discharge command. Ordinary Automated operation uses MSC, normal PV MAX, and the configured high export ceiling unless a specific overlay or safety condition owns a different actuator.

Import, export, charging, battery-export intent, PV curtailment, and safety/manual ownership are independent. Generic ordinary tariff eligibility cannot produce `BATTERY_EXPORT`.

Deliberate owners such as qualifying Morning Dump, high-price export, spike, Evening Export Boost, enabled positive-FiT battery discharge, and established solar/external overrides keep their existing safeguards.

## Current Phase 1 checkpoint

The Phase 1 checkpoint was committed successfully at `e82ca50abc4b758038228f065ec7ba94c3bc4c1b` (`Complete Phase 1 MSC ownership checkpoint`). Its Morning Slow Charge correction removes legacy measured-PV start/stop/export-margin ownership of export-ceiling opening.

When Morning Slow is legitimately active under safe Automated/MSC ownership:

- Morning Slow owns the ESS charge rate;
- remain in Maximum Self Consumption;
- retain normal configured PV MAX;
- retain the configured high export ceiling;
- allow only genuine MSC surplus to export;
- never create `BATTERY_EXPORT` intent.

Production is frozen after that Stage A change and its narrow ownership safeguard. The two affected Value Gate expectations now distinguish safe low-surplus MSC permission from unobserved Automated ownership. Rejected unobserved ownership leaves export closed, preserves the existing live EMS, and causes no MSC write solely for Morning Slow. All 24 obsolete haos49 characterization failures were reconciled tests-only to the approved Phase 1 architecture.

Phase 1 implementation and automated validation are complete for this committed checkpoint, and independent read-only safety review passed. The full suite has exactly the two untouched Phase 2 settlement failures recorded in `CURRENT_STATE.md`; all other tests pass.

`2.3.43-haos54` is installed and Phase 1 live acceptance passed on 2026-09-06. Captured evidence proved Automated/MSC ownership, PV MAX 25 kW, negative-FiT blocking, Demand Window import ownership, Value Gate advisory behavior, and the central Phase 1 safety case: an ordinary positive-FiT 25 kW `MSC_SURPLUS_CEILING` with no battery-export owner did not cause stored-battery grid export even while the battery was actively serving house load with zero PV.

The operator also observed a natural Morning Slow solar case in haos54: about the configured 2 kW battery charging rate, Maximum Self Consumption, normal PV MAX, high export ceiling, and genuine PV surplus exported after house load plus charging demand. That Morning Slow case is operator-observed rather than retained in the diagnostic capture.

Phase 1 is complete. The next engineering phase is the already-approved Phase 2 multi-cycle deliberate-export-to-MSC settlement sequence. The two existing Phase 2 transition tests remain intentional protection tests and must not be weakened.

## Safety contracts to preserve

- Cheap-FiT implicit export remains closed below 100% SoC.
- Exact 100% cheap-FiT export uses only the verified Automated plus exact-MSC PV-only path.
- Material or unknown battery flow cannot broaden that exception.
- The separate positive-FiT export policy and its battery-discharge enable are independent.
- Battery serving house load with negligible grid export is not automatically battery-to-grid sale.
- Meaningful simultaneous battery discharge and grid export closes conservatively when no deliberate owner exists.
- Unknown or stale evidence fails closed where safety or ownership cannot be proven.
- Demand Window primarily owns import blocking and does not reduce normal PV MAX by implication.
- Morning Dump remains deliberate battery export with its existing floor and window.
- Value Gate remains advisory-only; the actual import-cost guard remains independent.
- Negative-price, standby, reserve, forecast, freshness, remote-control, manual, and force behavior must not be casually redesigned.

## Phase boundaries

Phase 1 establishes decision and ownership semantics only.

Phase 2 implements the multi-cycle deliberate-export-to-MSC sequence:

1. close export;
2. observe it closed later;
3. request MSC;
4. observe exact MSC later;
5. reopen the normal high ceiling.

Service-call success is not observed inverter state. Phase 1 is now test-complete and live-proven; Phase 2 may begin only through its explicit multi-cycle observed-state contract.

Climate Manager integration follows Phase 2 plus a short stabilisation audit. The intended stable interface is `sensor.sigenergy_hvac_solar_permission` with states `start`, `continue`, `blocked`, and `unavailable`. SigEnergy Optimizer owns energy opportunity and safety; Climate Manager owns HVAC profiles, zones, targets, comfort/manual behavior, AC0, and AirTouch commands. Climate Manager is not yet consuming this entity.

## Working method

- Inspect only the minimum files relevant to the assigned change.
- Keep control changes narrow, reviewable, and accompanied by focused regressions.
- Never modify Home Assistant directly from repository work.
- Do not change software defaults to match live operator tuning.
- Run focused architecture and protection suites before the complete suite.
- Run `python -m compileall -q app tests` and `git diff --check`.
- Keep release, build, install, and live validation as separately approved actions.

Current test counts, operator tuning, checkpoint/base SHAs, and the next task live in `CURRENT_STATE.md`. Exact local branch, HEAD, and cleanliness must still be verified directly with Git.
