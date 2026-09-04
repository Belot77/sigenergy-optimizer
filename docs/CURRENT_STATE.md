# Current State

Last consolidated: 2026-09-05

**CURRENT TRUTH ONLY:** this file records the current operational and development checkpoint, not historical record. Durable control semantics live in `CONTROL_CONTRACT.md`; sequencing lives in `ROADMAP.md`.

Update this file whenever the live release or rollback baseline, active worktree/branch/HEAD/cleanliness, phase or gate, material test state or expected failures, exact next action, protected worktrees/items, or relevant operator tuning materially changes. Verify it against authoritative sources before a handover and before relying on it after substantive work.

Authority depends on the subject:

- committed repository state: GitHub;
- local uncommitted state: the relevant worktree, inspected through the current Codex session or PowerShell;
- live behavior: Home Assistant/Sigenergy observations and logs;
- operator configuration: actual Home Assistant/add-on settings.

If this file conflicts with an authoritative source, the authoritative source wins. Report the stale documentation and correct this file at the next permitted documentation write boundary.

Exact local branch, HEAD, and cleanliness must always be verified directly with Git in the relevant worktree. Any SHA or working-set list recorded here describes a checkpoint for comparison; this file is not authoritative for its own current committed state.

## Live release and rollback

- Known-good live release: `2.3.42-haos53`
- Tag: `v2.3.42-haos53`
- Release commit: `19f3c70d24dc086737d5956a1c66cad230287edd`
- Treat this release as the rollback baseline until a later release is explicitly proven live.

## Development worktrees

Active writable worktree:

- Path: `C:\Projects\sigenergy_optimizer-haos53-refactor`
- Branch: `refactor/msc-baseline-overlays-haos53`
- Committed Phase 1 checkpoint SHA: `e82ca50abc4b758038228f065ec7ba94c3bc4c1b`
- Checkpoint commit: `Complete Phase 1 MSC ownership checkpoint`
- Checkpoint condition: worktree was clean immediately after the commit; verify exact current Git state directly.

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

The Phase 1 implementation and automated validation are complete and committed at `e82ca50abc4b758038228f065ec7ba94c3bc4c1b`. Independent read-only safety review passed, and production is frozen. The two conflicting Value Gate Morning Slow expectations and all 24 obsolete haos49 characterization failures are reconciled tests-only; unobserved Automated ownership rejects the ceiling, leaves export closed, and preserves the existing live EMS without an MSC write.

No live proof is claimed. Phase 2 remains blocked until Phase 1 build/install/live acceptance passes.

## Exact next action

Phase 1 release candidate `2.3.43-haos54` is committed at `174136280ed1c516b7666b4600622ce9544bb8e0`, tagged `v2.3.43-haos54`, successfully built and published by GitHub Actions run `33922100095`, and GitHub `main` now points to that commit. The known-good live rollback remains `2.3.42-haos53` / `19f3c70d24dc086737d5956a1c66cad230287edd`. The next gate is Home Assistant repository refresh, then separately approved installation/start and Phase 1 live acceptance. No live proof is yet claimed. Keep Phase 2 blocked until live acceptance passes.

## Morning Slow Charge correction

The 2026-09-04 live evidence was:

- about 3.2 kW PV and 1.1 kW load left the export ceiling at 0.01 kW;
- later, about 4.4 kW PV and 1.1 kW load opened the ceiling to 25 kW;
- the battery continued charging at about 2 kW and MSC exported genuine surplus correctly once the ceiling opened.

Implemented result:

- Morning Slow owns the ESS charging rate;
- EMS remains Maximum Self Consumption;
- PV MAX remains the configured normal maximum, normally 25 kW;
- the export ceiling remains the configured high ceiling, normally 25 kW;
- actual export remains genuine inverter-controlled MSC surplus;
- Morning Slow never creates `BATTERY_EXPORT` intent.

The legacy measured-PV start/stop/export-margin gate no longer owns the Morning Slow export ceiling. When that ceiling is rejected because Automated ownership is unobserved, the existing live EMS is preserved and no MSC write is issued solely for Morning Slow.

## Current test checkpoint

- Two directly reconciled Value Gate Morning Slow tests: 2 passed.
- Full Value Gate advisory suite: 89 passed, 62 subtests passed.
- Architecture contract: 31 passed, 21 subtests passed, 2 intentionally deferred Phase 2 failures.
- Required protection suites combined: 108 passed, 68 subtests passed.
- haos49 characterization suites: 46 passed, 49 subtests passed.
- Full suite: 280 passed, 169 subtests passed, exactly 2 failures.
  - `test_return_from_discharge_waits_for_observed_close_before_requesting_msc`
  - `test_exact_msc_does_not_reopen_before_export_is_observed_closed`
- `python -m compileall -q app tests`: passed.
- `git diff --check`: passed.
- Independent read-only safety review: passed.

Those two failures are the untouched Phase 2 close-observe-MSC-observe-reopen settlement contract. Do not weaken them during Phase 1 review.

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
