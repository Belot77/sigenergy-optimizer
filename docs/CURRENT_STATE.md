# Current State

Last consolidated: 2026-10-03

**CURRENT TRUTH ONLY:** durable control semantics live in `CONTROL_CONTRACT.md`; sequencing lives in `ROADMAP.md`.

## Live release and rollback

- Current live release: `2.3.51-haos62`, tag `v2.3.51-haos62`, source commit `70f1766354c163b9259a3e5e128f8e083528fc64`; the operator confirms it has been installed/restarted and is live.
- Documented known-good rollback: `2.3.46-haos57`, commit `7144fd3d52069e3e8ef1e4df9bc8943bdd65dbe7`.
- Live `.61` evidence established the near-full Solar exception with genuinely untrusted available-discharge-energy telemetry at about 93.9-96.7% SoC. It prevented the raw Battery Full Safeguard from blocking the 25 kW MSC/PV-only ceiling. A clean Morning Slow -> Solar transition was observed: Morning Slow held about 2 kW ESS charging, Solar later allowed normal higher charging capability, and one desired-export transition occurred without rapid `0 <-> 25 kW` chatter.
- The 25 kW ceiling was observed as permission, not commanded battery discharge.
- Live `.62` Morning Slow evidence from 3 October showed MSC operation, safe load-serving battery behaviour, the 25 kW ceiling acting as PV-surplus permission rather than stored-battery export, and clean closure when Morning Slow ended.
- On 2 October, poor-solar evidence showed Morning Slow inactive despite trusted refill timing evidence: `morning_slow_refill_timing_reason` was `refill_infeasible_even_at_normal_capability`. This is positive fail-safe evidence that Morning Slow did not impose its 2 kW restriction when refill could not be proved. The operator later used Force Full Import + PV manually; that action is not Morning Slow behaviour. Morning Dump was operator-disabled during this run, so the run adds no Morning Dump acceptance evidence.
- The operator explicitly accepted Morning Dump without another dedicated Morning Dump trace as a release blocker.
- Live `.62` Evening Boost qualified deliberate battery export, but repeatedly transitioned between `evening_export_boost` / Command Discharging and MSC while SoC and FiT were effectively stable and short-term household load changed sharply. Source inspection found `_battery_soc_required_to_sunrise()` projects instantaneous `load_kw` across the remaining overnight horizon; transient load therefore moves `soc_required` / sunrise reserve sharply and can repeatedly acquire or release Evening Boost ownership. This is a separate narrow Phase 1 transition-stability defect, with no fix or live acceptance yet.

## Published Phase 1 release

- Release `2.3.51-haos62` was built from source commit `70f1766354c163b9259a3e5e128f8e083528fc64`; lightweight tag `v2.3.51-haos62` points to that exact source commit.
- GitHub Actions workflow `Build and publish add-on`, run `36643883464`, completed successfully, including the build/publish job.
- Multi-architecture image `ghcr.io/belot77/sigenergy-optimizer:2.3.51-haos62` was published with OCI index digest `sha256:dcc4f941df120dbd6e704f87218b72331363c3d1a58014bb10adbf6fdc38b888` for `linux/amd64` and `linux/arm64`.
- Published OCI metadata reports version `2.3.51-haos62` and revision `70f1766354c163b9259a3e5e128f8e083528fc64`, matching the release identity and tagged source.
- Remote `main` is promoted to the later documentation-only publication-record commit containing this state. That publication-record commit is distinct from the tagged release-source commit above.
- `.62` is published, promoted, installed/restarted, and operator-confirmed live. Known rollback remains `2.3.46-haos57`. The new dynamic Solar charge ceiling is not part of `.62`.
- The historical `.62` code gate collected 735 tests, with 733 passed and only the two frozen Phase 2 failures; compileall and `git diff --check` passed.
- Phase 2 remains frozen through `.63` Solar live acceptance and the subsequent separate Evening Boost transition-stability characterization, remediation, and live acceptance. The discussed `15.0 / 0.5 kW` physical-relief values remain unconfigured, semantically unresolved, and outside this release.

## Active Phase 1 checkpoint

- Worktree: `C:\Projects\sigenergy_optimizer-phase1-remediation`
- Branch: `fix/phase1-audit-remediation`
- Current HEAD before the local Solar implementation and release preparation: `8f77a602b93aaa6a7464c46dddf7bff7e20a56d5`.
- Local candidate: `2.3.52-haos63`, uncommitted and unreleased; not tagged, built, published, installed, or live-accepted.
- Phase 1 code-validation HEAD before the docs-only checkpoint: `7649d185b71fe08fab2636801396e2ae7c793a13`
- Phase 1 release-source commit: `70f1766354c163b9259a3e5e128f8e083528fc64`
- Publication record: the later documentation-only commit containing this state is present on both `origin/fix/phase1-audit-remediation` and remote `main`; it is not the tagged release source.

Earlier `.62` checkpoint chain:

1. `61f79bc5c285cc31c6b6aee7a2eba6573fb12cec` - `fix: clamp trusted available battery energy`
2. `99ef0f0c9c086ed1ba06ff736a34d04b1dcf6cf2` - `fix: preserve house supply during safe fallback`
3. `aca34975bd0d8dc9adf4565d76ce8f29ba35aa97` - `fix: protect morning refill and export relief`
4. `11ae4801a934481b25b71fb5e8ad2956255458d8` - `fix: make optimizer events immediately responsive`
5. `7cfcd7778c0a87609fd2d1261f59f0dd06e3bcd5` - `fix: restore bounded optimizer event coalescing`; this corrects the over-aggressive zero-delay approach in `11ae480`.
6. `bb6af74b386b410bc9288cd32540bc4f3ba32dce` - `fix: decouple evening boost from ordinary export tier`
7. `7649d185b71fe08fab2636801396e2ae7c793a13` - `test: update safe fallback settlement expectations`

The new local `.63` checkpoint adds dynamic Solar ESS charge-ceiling ownership only after final Solar arbitration. It allocates protected fill need to the current interval only when future detailed charge opportunity cannot cover it, rounds positive requests upward within the existing normal safe/trusted request, and immediately relinquishes the restriction when stricter charge evidence fails. Solar remains MSC/PV-only with normal PV MAX; all higher-priority owners remain intact and existing eligibility is unchanged.

Implementation files are `app/optimizer.py`, `tests/test_solar_surplus_redesign.py`, and intentionally untracked `tests/test_phase1_solar_dynamic_charge_ceiling_characterization.py`. Retain the characterization for eventual commit. Release preparation changes documentation and existing version markers only.

## Phase 1 code-validation gate

Final local validation of the dynamic Solar implementation on HEAD `8f77a602b93aaa6a7464c46dddf7bff7e20a56d5` plus the uncommitted changes:

- `python -B -m pytest -q -p no:cacheprovider --disable-warnings`: 755 collected, 753 passed, 2 failed, 197 warnings, 717 subtests passed.
- Dynamic Solar characterization, including grid-import charging precedence: 14 passed, 14 subtests passed.
- The only failures are the intentionally frozen Phase 2 transition-safety tests:
  - `tests/test_msc_baseline_overlay_contract.py::MscBaselineOverlayContractTests::test_exact_msc_does_not_reopen_before_export_is_observed_closed`
  - `tests/test_msc_baseline_overlay_contract.py::MscBaselineOverlayContractTests::test_return_from_discharge_waits_for_observed_close_before_requesting_msc`
- `python -m compileall -q app`: passed.
- `git diff --check`: passed.
- The candidate remains unstaged and uncommitted; the new characterization is intentionally untracked.

**THE `.63` SOLAR CODE VALIDATION GATE PASSED locally.** Independent pre-commit review found no remaining production/safety blocker after correction of grid-import charging precedence. Release `.62` is live; `.63` is LOCAL/UNRELEASED. The project lead's commit decision, commit/push, build/publication, manual installation, and one controlled live Solar validation remain outstanding. Solar live acceptance will not close Phase 1: the separate Evening Boost transition-stability defect then requires characterization, narrow remediation, and live acceptance before Phase 2 may begin.

## Protected Phase 1 behavior in live `.62`

- Available-discharge energy: fresh, finite, nonnegative, supported-unit telemetry remains trusted when above rated capacity. When rated capacity is trusted, the control value is clamped to capacity while the raw diagnostic remains visible. No clamp is invented from untrusted capacity; invalid telemetry still fails closed, with the established near-full Solar exception retained for genuinely untrusted telemetry.
- Safe fallback: closes export first, requests MSC, clamps ESS discharge while unresolved, and requires observed export closure plus observed MSC before permissive recovery. Service-call success is not settlement. Failed proof withholds normal import, ESS charge/discharge capability, and PV MAX recovery; Demand Window may retain import blocking; fallback creates no `BATTERY_EXPORT` owner.
- Morning Dump: remains deliberate `BATTERY_EXPORT`, preserves the 15% operator floor, and now requires trusted timed refill feasibility without assuming future Morning Slow relief.
- Morning Slow: remains an MSC charging-only policy with normal PV MAX and high export permission. Its end time ends ownership, not the refill deadline. Timed opportunity is evaluated through same-day sunset minus cutoff. If normal bounded charging provides strictly more safe refill opportunity than the slow cap, only the artificial slow charge cap is released.
- Physical export relief: `grid_connection_export_limit_kw` and `morning_slow_physical_export_headroom_kw` default to `0.0` and are disabled/unconfigured by default. Coherent measured site export at the configured threshold may release Morning Slow's artificial charging cap; it does not set or enforce a 15 kW Sigenergy export ceiling.
- Responsiveness: relevant HA state/attribute changes use a fixed, non-sliding 3-second pre-decision coalescing window. There is no immediate first-event tick or immediate catch-up tick. Startup remains immediate, the 60-second heartbeat remains, metadata-only changes do not trigger, and events during/after a cycle remain eligible for the next bounded cycle.
- Evening Boost: `evening_boost_min_feedin_price` defaults to and has a hard minimum of `$0.01/kWh`, with no arbitrary upper bound. A qualifying boost may operate below the ordinary export-tier threshold and owns `BATTERY_EXPORT` as `evening_export_boost`; sub-1-cent export remains blocked and ordinary positive-FiT export gains no such ownership.

The local `.63` Solar change preserves these `.62` behaviors, Manual/Force ownership, Demand Window separation, actual import-cost protection, forecast/reserve protections, battery floor, observed Automated ownership, and actuator/readback settlement protection. It does not introduce a Solar timer or claim live proof for the new ceiling.

## Current operator configuration and unresolved risk

Known live Morning Slow tuning, recorded as operator configuration rather than software defaults:

- enabled: `true`
- slow rate: `2 kW`
- until: `11:00`
- minimum FiT: `$0.01/kWh`
- base-load allowance: `2 kW`
- sunset cutoff: `1 hour`

Morning Dump operator floor is `15%`.

Discussed future physical-relief values are `15.0 kW` with `0.5 kW` headroom. They remain unconfigured, are not software defaults, and are NOT part of this release. Before configuring them, decide whether 15 kW is only the site-export level that releases Morning Slow's 2 kW charge cap or a hard network/export limit that must never be exceeded. The current implementation provides the former behavior only; a hard cap requires further design.

## Frozen and parked work

- The two Phase 2 transition tests above remain protected and intentionally unresolved. Phase 2 may begin only after both `.63` Solar live acceptance and the separate Evening Boost transition-stability remediation/live acceptance.
- Evening Boost transition stability is the next narrow Phase 1 remediation after `.63` Solar live acceptance. Do not redesign it in this checkpoint or weaken reserve, forecast, `BATTERY_EXPORT` ownership, import-cost, or settlement protections.
- The 27 September Solar aggregate-budget threshold switching observation remains an evidence-led follow-up and is not claimed fixed by this change. Observe it during `.63` Solar live acceptance; do not invent a separate fix without evidence.
- Phase 2, the control-ownership audit, architecture/refactor cleanup, GUI/UX redesign, Climate Manager integration, diagnostics/replay/load modelling, and experimental dynamic scheduling remain parked in roadmap order.

## Exact next action

Obtain the project lead's commit decision for the independently reviewed `.63` candidate, then commit/push if authorized, build/publish, manually install, and perform one controlled live Solar validation. Observe the 27 September Solar aggregate-budget threshold switching without assuming `.63` fixes it. Keep `15.0 / 0.5` unconfigured. After Solar acceptance, characterize and remediate the separate Evening Boost transition-stability defect and obtain its live acceptance; only then may Phase 2 begin. This documentation step stops before staging or committing and does not authorize publishing or Home Assistant changes.
