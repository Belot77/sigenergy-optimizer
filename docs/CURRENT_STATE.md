# Current State

Last consolidated: 2026-09-06

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

- Current live release: `2.3.43-haos54`
- Runtime signature observed live: `2.3.43-haos54`
- Live container source commit: `083b1fcc241b0d86271f5da80538d4e224fc6433`
- Tagged/tested production candidate: `174136280ed1c516b7666b4600622ce9544bb8e0`; `083b1fc` is its docs-only child, so production behavior is unchanged.
- Emergency rollback release: `2.3.42-haos53`
- Rollback tag: `v2.3.42-haos53`
- Rollback commit: `19f3c70d24dc086737d5956a1c66cad230287edd`

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

Phase 1, MSC baseline and overlay architecture, is complete and live-proven. Phase 2 transition safety is now the next active phase; no Phase 2 production change has yet been started. The committed checkpoint already provides:

- first-class `EXPORT_BLOCKED`, `MSC_SURPLUS_CEILING`, and `BATTERY_EXPORT` intents;
- ordinary positive-FiT export without implicit stored-battery discharge;
- explicit deliberate battery-export ownership;
- independent Demand Window import ownership;
- independent positive-FiT export-policy and battery-discharge controls;
- distinction between battery serving house load and simultaneous battery discharge plus grid export;
- preserved haos53 exact-full cheap-FiT protection.

The Phase 1 implementation and automated validation are complete and committed at `e82ca50abc4b758038228f065ec7ba94c3bc4c1b`. Independent read-only safety review passed, and production is frozen. The two conflicting Value Gate Morning Slow expectations and all 24 obsolete haos49 characterization failures are reconciled tests-only; unobserved Automated ownership rejects the ceiling, leaves export closed, and preserves the existing live EMS without an MSC write.

Phase 1 live acceptance passed on 2026-09-06.

Captured haos54 evidence proved:

- Automated ownership with exact Maximum Self Consumption;
- normal PV MAX remained 25 kW;
- negative-FiT export remained blocked;
- Demand Window blocked import without reducing normal PV MAX;
- ordinary positive-FiT operation opened the 25 kW `MSC_SURPLUS_CEILING` with `battery_export_owner=none`;
- with zero PV and the battery discharging to serve house load, the open 25 kW ceiling did not cause meaningful battery-to-grid export;
- trusted flow remained classified as load-serving battery discharge rather than simultaneous battery discharge plus grid export;
- Value Gate remained advisory-only.

The operator also observed a natural haos54 Morning Slow period with sufficient PV: the battery charged at about the configured 2 kW rate while remaining in Maximum Self Consumption with normal PV MAX and the high export ceiling, and PV beyond house load plus charging exported to grid as genuine surplus. That Morning Slow/genuine-surplus case is operator-observed rather than preserved in the diagnostic capture.

Phase 1 is therefore accepted live. `2.3.43-haos54` remains live and `2.3.42-haos53` remains the emergency rollback.

## Exact next action

Commit and publish this docs-only Phase 1 live-acceptance checkpoint. After that checkpoint is clean and authoritative, begin Phase 2 transition-safety work. Phase 2 must implement the already-approved close export -> later observe closed -> request MSC -> later observe exact MSC -> reopen high ceiling sequence and make the two intentionally failing transition tests pass without weakening them.

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
