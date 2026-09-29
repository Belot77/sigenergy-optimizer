# Current State

Last consolidated: 2026-09-30

**CURRENT TRUTH ONLY:** durable control semantics live in `CONTROL_CONTRACT.md`; sequencing lives in `ROADMAP.md`.

## Live release and rollback

- Current known live release: `2.3.50-haos61`, tag `v2.3.50-haos61`, commit `76db9e43588f0e9862d73e4e8402c0b5ce9773a7`.
- Documented known-good rollback: `2.3.46-haos57`, commit `7144fd3d52069e3e8ef1e4df9bc8943bdd65dbe7`.
- Live `.61` evidence established the near-full Solar exception with genuinely untrusted available-discharge-energy telemetry at about 93.9-96.7% SoC. It prevented the raw Battery Full Safeguard from blocking the 25 kW MSC/PV-only ceiling. A clean Morning Slow -> Solar transition was observed: Morning Slow held about 2 kW ESS charging, Solar later allowed normal higher charging capability, and one desired-export transition occurred without rapid `0 <-> 25 kW` chatter.
- The 25 kW ceiling was observed as permission, not commanded battery discharge.

None of the seven local Phase 1 commits below has been pushed, released, deployed, installed, or restarted. Their new behavior is not live-proven.

## Active Phase 1 checkpoint

- Worktree: `C:\Projects\sigenergy_optimizer-phase1-remediation`
- Branch: `fix/phase1-audit-remediation`
- Phase 1 code-validation HEAD before the docs-only checkpoint: `7649d185b71fe08fab2636801396e2ae7c793a13`
- Status at checkpoint start: clean; tracking `0 behind / 7 ahead` of `origin/fix/phase1-audit-remediation`.

Local checkpoint chain:

1. `61f79bc5c285cc31c6b6aee7a2eba6573fb12cec` - `fix: clamp trusted available battery energy`
2. `99ef0f0c9c086ed1ba06ff736a34d04b1dcf6cf2` - `fix: preserve house supply during safe fallback`
3. `aca34975bd0d8dc9adf4565d76ce8f29ba35aa97` - `fix: protect morning refill and export relief`
4. `11ae4801a934481b25b71fb5e8ad2956255458d8` - `fix: make optimizer events immediately responsive`
5. `7cfcd7778c0a87609fd2d1261f59f0dd06e3bcd5` - `fix: restore bounded optimizer event coalescing`; this corrects the over-aggressive zero-delay approach in `11ae480`.
6. `bb6af74b386b410bc9288cd32540bc4f3ba32dce` - `fix: decouple evening boost from ordinary export tier`
7. `7649d185b71fe08fab2636801396e2ae7c793a13` - `test: update safe fallback settlement expectations`

## Phase 1 code-validation gate

Final validation at HEAD `7649d185b71fe08fab2636801396e2ae7c793a13`:

- `python -B -m pytest -p no:cacheprovider`: 735 collected, 733 passed, 2 failed, 197 warnings.
- The only failures are the intentionally frozen Phase 2 transition-safety tests:
  - `tests/test_msc_baseline_overlay_contract.py::MscBaselineOverlayContractTests::test_exact_msc_does_not_reopen_before_export_is_observed_closed`
  - `tests/test_msc_baseline_overlay_contract.py::MscBaselineOverlayContractTests::test_return_from_discharge_waits_for_observed_close_before_requesting_msc`
- `python -m compileall -q app`: passed.
- `git diff --check`: passed.
- The worktree and index were clean after code/test validation.
- The earlier unexpected safe-fallback failure was a stale protection-test expectation. Correcting that test resolved it; production code did not change in the final checkpoint.

**PHASE 1 CODE VALIDATION GATE PASSED locally.** Phase 1 is not fully complete: push, release, deployment, restart, and live acceptance of these seven commits remain outstanding.

## Local Phase 1 behavior awaiting release/live proof

- Available-discharge energy: fresh, finite, nonnegative, supported-unit telemetry remains trusted when above rated capacity. When rated capacity is trusted, the control value is clamped to capacity while the raw diagnostic remains visible. No clamp is invented from untrusted capacity; invalid telemetry still fails closed, with the established near-full Solar exception retained for genuinely untrusted telemetry.
- Safe fallback: closes export first, requests MSC, clamps ESS discharge while unresolved, and requires observed export closure plus observed MSC before permissive recovery. Service-call success is not settlement. Failed proof withholds normal import, ESS charge/discharge capability, and PV MAX recovery; Demand Window may retain import blocking; fallback creates no `BATTERY_EXPORT` owner.
- Morning Dump: remains deliberate `BATTERY_EXPORT`, preserves the 15% operator floor, and now requires trusted timed refill feasibility without assuming future Morning Slow relief.
- Morning Slow: remains an MSC charging-only policy with normal PV MAX and high export permission. Its end time ends ownership, not the refill deadline. Timed opportunity is evaluated through same-day sunset minus cutoff. If normal bounded charging provides strictly more safe refill opportunity than the slow cap, only the artificial slow charge cap is released.
- Physical export relief: `grid_connection_export_limit_kw` and `morning_slow_physical_export_headroom_kw` default to `0.0` and are disabled/unconfigured by default. Coherent measured site export at the configured threshold may release Morning Slow's artificial charging cap; it does not set or enforce a 15 kW Sigenergy export ceiling.
- Responsiveness: relevant HA state/attribute changes use a fixed, non-sliding 3-second pre-decision coalescing window. There is no immediate first-event tick or immediate catch-up tick. Startup remains immediate, the 60-second heartbeat remains, metadata-only changes do not trigger, and events during/after a cycle remain eligible for the next bounded cycle.
- Evening Boost: `evening_boost_min_feedin_price` defaults to and has a hard minimum of `$0.01/kWh`, with no arbitrary upper bound. A qualifying boost may operate below the ordinary export-tier threshold and owns `BATTERY_EXPORT` as `evening_export_boost`; sub-1-cent export remains blocked and ordinary positive-FiT export gains no such ownership.

These local changes do not alter Manual/Force ownership, Demand Window separation, actual import-cost protection, forecast/reserve protections, battery floor, observed Automated ownership, actuator/readback settlement protection, or normal Solar stabilization behavior.

## Current operator configuration and unresolved risk

Known live Morning Slow tuning, recorded as operator configuration rather than software defaults:

- enabled: `true`
- slow rate: `2 kW`
- until: `11:00`
- minimum FiT: `$0.01/kWh`
- base-load allowance: `2 kW`
- sunset cutoff: `1 hour`

Morning Dump operator floor is `15%`.

Discussed future physical-relief values are `15.0 kW` with `0.5 kW` headroom. They are not live and are not software defaults. Before configuring them, decide whether 15 kW is only the site-export level that releases Morning Slow's 2 kW charge cap or a hard network/export limit that must never be exceeded. The current implementation provides the former behavior only; a hard cap requires further design.

## Frozen and parked work

- The two Phase 2 transition tests above remain protected and intentionally unresolved.
- The 27 September morning trace showing Solar aggregate-budget threshold switching remains a separate evidence-led Phase 1 follow-up; none of the seven local checkpoints establishes that it is fixed.
- Phase 2, the control-ownership audit, architecture/refactor cleanup, GUI/UX redesign, Climate Manager integration, diagnostics/replay/load modelling, and experimental dynamic scheduling remain parked in roadmap order.

## Exact next action

Review the complete Phase 1 checkpoint and decide the push/release/deployment/live-acceptance sequence. Before enabling future `15.0 / 0.5` physical-relief operator values, resolve whether 15 kW is a relief threshold or an inviolable network export cap. Do not begin Phase 2 until the Phase 1 release is live-accepted.
