# Current State

Last consolidated: 2026-10-10

**CURRENT TRUTH ONLY:** durable control semantics live in `CONTROL_CONTRACT.md`; sequencing lives in `ROADMAP.md`.

## Release and worktree

- Last recorded live release (8 October checkpoint): **2.3.56-haos67**. No live query was performed for this checkpoint.
- Release/source commit: `1973ac643c29044e8bfb894873adfdd53c7eb4c8`.
- Tag: `v2.3.56-haos67`.
- Image: `ghcr.io/belot77/sigenergy-optimizer:2.3.56-haos67`.
- The GitHub Actions release build completed successfully. Live startup reported `Runtime signature=2.3.56-haos67`, container source commit `1973ac6`, and `morning_slow_charge_runtime_disabled=False`.
- Known-good rollback remains **2.3.54-haos65** at `9965e79133f38d5b9943dcf5a9b04ed6fdab1239`. Do not promote `.66` to the documented rollback.
- Verified worktree: `C:\Projects\sigenergy_optimizer-phase1-remediation`; branch: `fix/phase2-observed-msc-transition`; HEAD: `22602e1ad225e39b7679a1af9d9bf3e04348e887`.
- Phase 2 implementation/tests and checkpoint documentation are committed locally at HEAD. This release preparation starts clean and changes only five release identity values and three release documents; these eight files remain unstaged and uncommitted. No tag, build, publication or deployment has occurred.
- The recorded `.67` runtime signature/container source supersedes the older `.66` and unreleased `.67` status by date. Repository defaults are not live evidence; reconfirm installed identity at the deployment gate.
- Continue work only in the remediation worktree. Do not edit the separate root worktree `C:\Projects\sigenergy_optimizer`.

## Prepared .68 release identity

- Version: **2.3.57-haos68**; proposed tag: `v2.3.57-haos68`.
- Proposed image: `ghcr.io/belot77/sigenergy-optimizer:2.3.57-haos68`.
- Local metadata preparation only: no tag, build, image publication, deployment or live acceptance. Existing local/remote tag checks found no conflicting .68/2.3.57 identity during release investigation.
- All five established surfaces are synchronized: add-on config version, build version label, plain build stamp, API version and optimizer runtime signature. No controller, test or configuration-default changes.
- Prior Phase 2 validation and both passed reviews remain the behavioural evidence; metadata preparation does not repeat the full suite or compileall.

## Phase 2 local checkpoint and Phase 1 gate

Phase 2 observed transition-settlement implementation is **code-validated, independently reviewed and locally complete**, and committed locally, but not released, deployed or live-accepted. Independent production review and final test-delta review both **PASSED**.

Final validation: **920 passed, 913 subtests passed, zero failures**, with **201 Pydantic deprecation warnings** (197 extra Field keyword warnings, three deprecated `.dict()` calls, one class-based Config warning). Compileall for `app` and `tests` and `git diff --check` **PASSED**. Both formerly frozen tests listed below now pass with their test bodies unchanged.

The return path now requires export close, trusted observed closure, MSC request, trusted exact MSC strictly after that request, then permitted reopening. Fresh provenance, fail-closed fallback recovery and independent restrictive PV ownership remain required through uncertainty, restart and actuator failure. Manual/Force, Demand Window and Solar protections remain intact; see `CONTROL_CONTRACT.md`.

Phase 2 development proceeded with explicit approval **ahead of the roadmap's Phase 1 live gate**. The earlier blanket Phase 1 complete/live-proven statement is corrected: scoped `.67` Solar evidence does not close the retained acceptance dependency, including the separate Evening Boost follow-up and disposition of Solar threshold switching. Phase 1 is not marked accepted. High/Spike, Medium and tier-specific SoC work remain a separate later package; unrelated Phase 1 issues remain parked.

Recorded .67 evidence proves scoped Solar handover, physical-relief increase/backoff and fill-deadline relinquishment. The separate Evening Boost stability acceptance and Solar threshold-switching disposition remain unproven in the available record. No new implementation defect was established by release preparation, but these unresolved acceptance decisions prevent declaring the controlled-deployment gate cleared. They require explicit evidence/disposition; .67 installation alone is insufficient.

Earlier `.67` pre-release validation is retained in `CHANGELOG.md`; the Phase 2 result above is the current local validation gate.

The formerly frozen Phase 2 tests, now passing unchanged, are:

- `test_exact_msc_does_not_reopen_before_export_is_observed_closed`;
- `test_return_from_discharge_waits_for_observed_close_before_requesting_msc`.

## Last recorded live operator configuration (8 October)

- `grid_connection_export_limit_kw = 15.0`: this site's confirmed physical/grid export boundary. The software default remains `0.0` and must not be changed to 15.
- `solar_surplus_fill_deadline_margin_minutes = 120`: this site's currently preferred operator tuning after live testing. The released software default remains 60 minutes and must not be changed by documentation work.
- Normal optimizer export permission remains 25 kW, PV MAX remains 25 kW, and Morning Slow physical export headroom remains 0.0.

These are site operator settings, not universal production defaults.

## Recorded `.67` Solar live evidence (8 October)

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

Preserve observed Automated ownership, exact MSC settlement, Manual/Force ownership, Demand Window import blocking, battery floor and reserve/forecast safeguards, fail-closed telemetry, normal PV MAX/high export permission, and explicit `BATTERY_EXPORT` ownership. Durable settlement requirements are recorded in `CONTROL_CONTRACT.md`.

Recorded Phase 2 motivation from about 07:20-07:25 AEDT on 8 October: Morning Dump hovered near its approximately 15% floor and toggled off/on. On two exits, physical discharge/export briefly persisted after the owner disappeared, with battery discharge about 12.6-14.0 kW and grid export about 12.8-14.6 kW. The optimizer detected the continuing flow, commanded export closed to zero, and recovered to Morning Slow within seconds. This is not a Phase 1 defect; it is live evidence for the Phase 2 transition-safety implementation now awaiting live acceptance.

## Exact next action

Obtain separate approval to **commit the prepared .68 release metadata**. Subsequent publication/tag/build actions require separate approval. Explicitly resolve the retained Phase 1 gate before controlled deployment and Phase 2 live acceptance; local completion does not waive that dependency. Deployment and live actions require their own authorization. Retain `.65` as the known-good rollback.

Live acceptance must correlate requests with fresh observed EMS, export/import limits, PV MAX, ESS charge/discharge limits, SoC, battery power, PV/load/grid flows and actuator ownership. Capture deliberate-discharge exit, observed closure before MSC request, exact MSC strictly after the request, then permitted reopening. Include unfinished-transition restart, telemetry loss/recovery, actuator failure/fallback, restrictive Standby/negative-price PV MAX, Demand Window and Manual/Force.

Review monitor-only/dry-run decisions without treating them as physical proof; only with authorization capture controlled live requests and actual flows. Tests and accepted HA service calls do not prove physical inverter settlement. Live acceptance remains outstanding.
