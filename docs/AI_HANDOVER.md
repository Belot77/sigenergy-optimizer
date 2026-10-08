# SigEnergy Optimizer AI Handover

Last consolidated: 2026-10-08

Read root/project `AGENTS.md`, then `CURRENT_STATE.md`, `CONTROL_CONTRACT.md`, `DECISIONS.md`, and `ROADMAP.md`. Verify worktree, branch, HEAD, and status before editing.

## Continuation checkpoint

- Live release: **2.3.56-haos67**.
- Release/source commit: `1973ac643c29044e8bfb894873adfdd53c7eb4c8`.
- Tag: `v2.3.56-haos67`.
- Image: `ghcr.io/belot77/sigenergy-optimizer:2.3.56-haos67`.
- Release build: GitHub Actions completed successfully.
- Live startup: runtime signature `2.3.56-haos67`, container source `1973ac6`, `morning_slow_charge_runtime_disabled=False`.
- Known-good rollback: **2.3.54-haos65** at `9965e79133f38d5b9943dcf5a9b04ed6fdab1239`. Do not promote `.66`.
- Writable worktree: `C:\Projects\sigenergy_optimizer-phase1-remediation`.
- Branch: `fix/phase1-audit-remediation`.
- HEAD: `1973ac643c29044e8bfb894873adfdd53c7eb4c8`.
- Start-of-checkpoint status: clean; `origin/main` and `origin/fix/phase1-audit-remediation` matched HEAD.
- Do not edit the separate root worktree `C:\Projects\sigenergy_optimizer`.

## Phase status and validation

**Phase 1 is COMPLETE and LIVE-PROVEN.** Phase 2 transition safety is next and remains unimplemented.

Final `.67` validation passed: physical relief **35 / 20 subtests**, affected Solar/controller **140 / 221**, independent protections **250 / 266**, and full suite **907 / 872**. The full suite had exactly the two expected frozen Phase 2 failures and no unexpected failures. Compileall and `git diff --check` passed.

Frozen Phase 2 tests:

- `test_exact_msc_does_not_reopen_before_export_is_observed_closed`;
- `test_return_from_discharge_waits_for_observed_close_before_requesting_msc`.

## Protection invariants

- Automated permissive control requires observed Automated ownership; service-call success is not observation.
- Returning from deliberate battery export must close export, later observe it closed, request MSC, later observe exact MSC, and only then reopen the normal high export ceiling.
- Deliberate battery export must settle its export target before selecting discharge EMS.
- Solar remains MSC/PV-only, never owns `BATTERY_EXPORT`, and changes only its bounded ESS charge ceiling.
- Preserve Manual/Force ownership, Demand Window import blocking, battery floor, reserve/forecast and import-cost safeguards, fail-closed telemetry, actuator settlement, normal PV MAX, normal high export permission, and explicit owner separation.
- Do not weaken or bypass the two frozen transition tests.

## Live operator tuning

- `grid_connection_export_limit_kw = 15.0` is this site's physical/grid boundary. The software default remains `0.0`.
- `solar_surplus_fill_deadline_margin_minutes = 120` is this site's currently preferred tuning. The released software default remains 60 minutes.
- Normal export permission remains 25 kW; PV MAX remains 25 kW; Morning Slow physical export headroom remains 0.0.

Do not convert site tuning into production defaults.

## `.67` live proof

Morning Slow handed ownership to Solar at about 11:59:02 AEDT on 8 October 2026, near 37.7% SoC. MSC remained active, PV MAX/export permission remained 25 kW, Solar owned a 0 kW ESS charge ceiling, provider authority was VALID, and `battery_export_owner=none`.

**Saturation relief: LIVE PASS.** With export near the physical 15 kW boundary and a 0 kW Solar baseline, relief increased the Solar ESS charge ceiling in bounded 0.4 kW steps to 1.6 kW while PV rose and export stayed near the boundary. MSC, PV MAX, normal export permission, and no-battery-export ownership were preserved. When export fell, relief rapidly backed off to zero, hard-reset below the lower boundary, and later re-qualified. `hidden_pv_surplus` remained diagnostic-only.

**120-minute fill margin: LIVE PASS.** The earlier deadline caused `present_charging_required_for_fill_trajectory` once future opportunity became insufficient: about 9.17 kW requested near 15:40 and about 6.82 kW near 16:37. Just before the 17:14:59 target the battery was about 99.8%; at 17:15 Solar relinquished its ceiling with `fill_deadline_reached`, returning normal 21 kW charge permission while preserving zero commanded import, MSC, 25 kW PV MAX/export permission, and no battery-export owner. The inverter's near-full taper completed physical 100% at about 17:18:47. Tiny 0.01-0.05 kW measured imports during final taper were not commanded optimizer import.

## Parked Phase 2 live evidence

Around 07:20-07:25 AEDT on 8 October, Morning Dump hovered near its approximately 15% floor and toggled off/on. On two exits the owner disappeared while physical battery discharge persisted around 12.6-14.0 kW and grid export around 12.8-14.6 kW. The optimizer detected the continuing discharge/export, commanded the export limit closed to zero, and recovered to Morning Slow within seconds.

This is not a Phase 1 defect. Preserve it as evidence for the planned Phase 2 observed-transition implementation.

## Exact next action

Start a **NEW** Codex session for **Phase 2 transition safety**. Use **Ultra** reasoning because transition safety is safety-critical. Speed: **Standard**.

Work only on the settlement sequence in `CONTROL_CONTRACT.md`, with a separately approved staged fix branch. Do not alter Phase 1 semantics, operator defaults, roadmap order, or unrelated parked work.
