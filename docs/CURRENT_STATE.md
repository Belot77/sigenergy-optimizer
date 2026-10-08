# Current State

Last consolidated: 2026-10-08

**CURRENT TRUTH ONLY:** durable control semantics live in `CONTROL_CONTRACT.md`; sequencing lives in `ROADMAP.md`.

## Release and worktree

- Current live release: **2.3.56-haos67**.
- Release/source commit: `1973ac643c29044e8bfb894873adfdd53c7eb4c8`.
- Tag: `v2.3.56-haos67`.
- Image: `ghcr.io/belot77/sigenergy-optimizer:2.3.56-haos67`.
- The GitHub Actions release build completed successfully. Live startup reported `Runtime signature=2.3.56-haos67`, container source commit `1973ac6`, and `morning_slow_charge_runtime_disabled=False`.
- Known-good rollback remains **2.3.54-haos65** at `9965e79133f38d5b9943dcf5a9b04ed6fdab1239`. Do not promote `.66` to the documented rollback.
- Writable worktree: `C:\Projects\sigenergy_optimizer-phase1-remediation`; branch: `fix/phase1-audit-remediation`; HEAD: `1973ac643c29044e8bfb894873adfdd53c7eb4c8`. The worktree was clean at the start of this documentation checkpoint, and both `origin/main` and `origin/fix/phase1-audit-remediation` resolved to the same commit.
- Continue work only in the remediation worktree. Do not edit the separate root worktree `C:\Projects\sigenergy_optimizer`.

## Phase 1 status

**Phase 1 is COMPLETE and LIVE-PROVEN.** Phase 2 transition safety is the exact next roadmap item and remains unimplemented.

Final pre-release validation for `.67`:

- physical saturation relief: **35 passed / 20 subtests**;
- affected Solar/controller tests: **140 passed / 221 subtests**;
- independent protections: **250 passed / 266 subtests**;
- full suite: **907 passed / 872 subtests**, with exactly the two expected frozen Phase 2 failures and no unexpected failures;
- compileall: **PASS**;
- `git diff --check`: **PASS**.

The frozen Phase 2 tests remain:

- `test_exact_msc_does_not_reopen_before_export_is_observed_closed`;
- `test_return_from_discharge_waits_for_observed_close_before_requesting_msc`.

## Live operator configuration

- `grid_connection_export_limit_kw = 15.0`: this site's confirmed physical/grid export boundary. The software default remains `0.0` and must not be changed to 15.
- `solar_surplus_fill_deadline_margin_minutes = 120`: this site's currently preferred operator tuning after live testing. The released software default remains 60 minutes and must not be changed by documentation work.
- Normal optimizer export permission remains 25 kW, PV MAX remains 25 kW, and Morning Slow physical export headroom remains 0.0.

These are site operator settings, not universal production defaults.

## `.67` live acceptance

### Morning Slow to Solar handover

At about 11:59:02 AEDT on 8 October 2026, Morning Slow became inactive and Solar Surplus became active at about 37.7% SoC. Maximum Self Consumption remained active, PV MAX and export permission remained 25 kW, Solar owned the 0 kW ESS charge ceiling, Solcast provider authority was VALID, and `battery_export_owner=none`.

### Physical export saturation relief: LIVE PASS

With the physical boundary configured to 15 kW and a Solar baseline charge ceiling of 0 kW, actual export remained near 15 kW while the controller increased only Solar ESS charge permission in bounded 0.4 kW steps: 0.4, 0.8, 1.2, then 1.6 kW. PV output rose and the battery absorbed otherwise-stranded PV while MSC, 25 kW PV MAX, 25 kW export permission, and `battery_export_owner=none` remained unchanged.

Backoff was also proven: as export fell, relief reduced from 1.6 to 0.4 kW and then to zero; below the hard-reset threshold the controller reset and later re-qualified. `hidden_pv_surplus` remained diagnostic-only and did not authorize relief.

### 120-minute fill-deadline tuning: LIVE PASS

The 120-minute site margin produced an effective target near 17:14:59 AEDT. At about 15:40, future opportunity was insufficient, so Solar requested about 9.17 kW with reason `present_charging_required_for_fill_trajectory`. Around 16:37 it still requested about 6.82 kW for the same trajectory need.

Immediately before the deadline, SoC was about 99.8%; Solar requested the normal 21 kW maximum while the inverter tapered actual charging to about 3.55 kW. At 17:15:00 the reason changed to `fill_deadline_reached`, Solar relinquished charge-ceiling ownership, and normal 21 kW charge permission returned. MSC, 25 kW export permission, 25 kW PV MAX, zero commanded import, and no battery-export owner were preserved.

The battery reported 100% at about 17:18:47, roughly 3 minutes 48 seconds after the target, consistent with near-full inverter taper. Tiny measured imports around 0.01-0.05 kW during final top-off occurred while commanded import remained zero and are not an optimizer import-policy violation.

Previously proven `.66` behavior remained preserved: provider-aware Solcast freshness and deadline recovery, Solar ownership at partial SoC, dynamic charge ceilings, trajectory-required charging, safe relinquishment to normal MSC when the energy budget was insufficient, no observed battery-export leakage, and Manual/Force ownership.

## Protected behavior and Phase 2 evidence

Preserve observed Automated ownership, exact MSC settlement, Manual/Force ownership, Demand Window import blocking, battery floor and reserve/forecast safeguards, fail-closed telemetry, normal PV MAX/high export permission, and explicit `BATTERY_EXPORT` ownership. Do not alter the durable contract in `CONTROL_CONTRACT.md` as part of status maintenance.

Useful parked Phase 2 evidence from about 07:20-07:25 AEDT on 8 October: Morning Dump hovered near its approximately 15% floor and toggled off/on. On two exits, physical discharge/export briefly persisted after the owner disappeared, with battery discharge about 12.6-14.0 kW and grid export about 12.8-14.6 kW. The optimizer detected the continuing flow, commanded export closed to zero, and recovered to Morning Slow within seconds. This is not a Phase 1 defect; it is live evidence for the already-planned Phase 2 transition-safety work.

## Exact next action

Begin a new, separately approved Phase 2 transition-safety session. Implement only the observed settlement sequence already defined in `CONTROL_CONTRACT.md`; do not partially improvise it in Phase 1 logic. Recommended reasoning is **Ultra** because the work is safety-critical; speed is **Standard**.
