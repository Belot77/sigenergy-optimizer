# Current State

Last consolidated: 2026-09-04

**CURRENT TRUTH ONLY:** this file records the current operational and development checkpoint, not historical record. Durable control semantics live in `CONTROL_CONTRACT.md`; sequencing lives in `ROADMAP.md`.

Update this file whenever the live release or rollback baseline, active worktree/branch/HEAD/cleanliness, phase or gate, material test state or expected failures, exact next action, protected worktrees/items, or relevant operator tuning materially changes. Verify it against authoritative sources before a handover and before relying on it after substantive work.

Authority depends on the subject:

- committed repository state: GitHub;
- local uncommitted state: the relevant worktree, inspected through the current Codex session or PowerShell;
- live behavior: Home Assistant/Sigenergy observations and logs;
- operator configuration: actual Home Assistant/add-on settings.

If this file conflicts with an authoritative source, the authoritative source wins. Report the stale documentation and correct this file at the next permitted documentation write boundary.

## Live release and rollback

- Known-good live release: `2.3.42-haos53`
- Tag: `v2.3.42-haos53`
- Release commit: `19f3c70d24dc086737d5956a1c66cad230287edd`
- Treat this release as the rollback baseline until a later release is explicitly proven live.

## Development worktrees

Active writable worktree:

- Path: `C:\Projects\sigenergy_optimizer-haos53-refactor`
- Branch: `refactor/msc-baseline-overlays-haos53`
- HEAD: `8309c5e6644c74f7aeb5ba613f983e0b7d2fe4c2`
- Expected status: clean before the next production task

Protected worktrees:

- `C:\Projects\sigenergy_optimizer`: intentional dirty legacy refactor on `refactor/msc-baseline-overlays` at `bce8411d5274fe17fb8d883e8e7faf43e9ce8d43`. Do not modify, reset, or stash it.
- `C:\Projects\sigenergy_optimizer-pv-hotfix`: clean release reference on `main` at `19f3c70d24dc086737d5956a1c66cad230287edd`. Do not modify it.

## Current phase and gate

Phase 1, MSC baseline and overlay architecture, is the active phase. The committed checkpoint already provides:

- first-class `EXPORT_BLOCKED`, `MSC_SURPLUS_CEILING`, and `BATTERY_EXPORT` intents;
- ordinary positive-FiT export without implicit stored-battery discharge;
- explicit deliberate battery-export ownership;
- independent Demand Window import ownership;
- independent positive-FiT export-policy and battery-discharge controls;
- distinction between battery serving house load and simultaneous battery discharge plus grid export;
- preserved haos53 exact-full cheap-FiT protection.

Phase 1 is not ready for a test release. The Morning Slow Charge ceiling correction and haos49 characterization reconciliation remain mandatory, followed by a production freeze and live proof.

## Exact next production action

Correct the remaining Morning Slow Charge legacy export-ceiling gate.

Observed on 2026-09-04:

- about 3.2 kW PV and 1.1 kW load left the export ceiling at 0.01 kW;
- later, about 4.4 kW PV and 1.1 kW load opened the ceiling to 25 kW;
- the battery continued charging at about 2 kW and MSC exported genuine surplus correctly once the ceiling opened.

Approved result:

- Morning Slow owns the ESS charging rate;
- EMS remains Maximum Self Consumption;
- PV MAX remains the configured normal maximum, normally 25 kW;
- the export ceiling remains the configured high ceiling, normally 25 kW;
- actual export remains genuine inverter-controlled MSC surplus;
- Morning Slow never creates `BATTERY_EXPORT` intent.

Do not implement the Phase 2 transition state machine as part of this correction.

## Test checkpoint before the Morning Slow correction

- Architecture contract: 30 passed, 2 intentionally deferred Phase 2 failures.
- Value Gate: 89 passed.
- `test_pv_surplus_hotfix.py`: 7 passed.
- `test_haos52_control_cleanup.py`: 7 passed.
- `test_demand_window_pv_max.py`: 3 passed.
- `test_negative_fit_pv_curtailment.py`: 2 passed.
- Full suite: 269 passed, 26 failed.
  - 24 failures are obsolete haos49 characterization expectations awaiting tests-only reconciliation.
  - 2 failures are the deferred Phase 2 transition tests.
- `python -m compileall -q app tests`: passed.
- `git diff --check`: passed.

After the Morning Slow production fix, reconcile the 24 haos49 failures without changing production. If any supposedly obsolete characterization failure reveals a real production defect, stop instead of rewriting that test.

Target pre-live automated result: everything green except exactly the two deferred Phase 2 transition tests.

## Current operator tuning

These are live operator settings, not software defaults:

- Forecast Safety Charging: 1.30, changed from 1.25.
- Morning Slow Charge Base Load: 2.0 kW, changed from 1.0 kW.

Do not change software defaults merely to match these observations.

## Protected contracts and parked work

Preserve the exact-100% cheap-FiT contract, explicit battery-export ownership, Demand Window PV MAX behavior, Value Gate advisory-only behavior, actual import-cost guard, negative-price behavior, and manual/force ownership.

Parked until their roadmap phase:

- Phase 2 close-observe-MSC-observe-reopen transition safety;
- hard forecast floors for Morning Dump or Morning Slow, which are not approved;
- required/sunrise SoC presentation as 100% plus an energy shortfall;
- load/forecast-model changes without supporting live evidence;
- the old `feature/safety-actuator-refactor` branch, which is reference only;
- the experimental dynamic solar scheduler and its replay/shadow/live-trial tooling.
