# Current State

Last consolidated: 2026-09-08

**CURRENT TRUTH ONLY:** this file records the current operational and development checkpoint, not historical record. Durable control semantics live in `CONTROL_CONTRACT.md`; sequencing lives in `ROADMAP.md`.

Authority depends on the subject: GitHub for committed repository state; the relevant verified worktree for local uncommitted state; Home Assistant/Sigenergy observations and logs for live behavior; and actual Home Assistant/add-on settings for operator configuration. If this file conflicts with an authoritative source, report and correct the stale documentation at the next permitted documentation boundary.

## Live release and rollback

- Current live release: `2.3.43-haos54`.
- Runtime source observed from Home Assistant: `083b1fcc241b0d86271f5da80538d4e224fc6433`.
- Tagged haos54 candidate: `174136280ed1c516b7666b4600622ce9544bb8e0`.
- Production code in `083b1fc` is identical to the tagged candidate.
- Known-good emergency rollback: `2.3.42-haos53`, tag `v2.3.42-haos53`, commit `19f3c70d24dc086737d5956a1c66cad230287edd`.

Rollback, if separately authorized, means stop the add-on, restore Sig Opt only, then verify EMS, PV MAX, export, and Home Assistant control. No rollback is currently being performed.

GitHub `main` remains at `c624f0b4392634cf19276186ba46f4b80268627b` (`Record Phase 1 live acceptance`). That committed documentation is stale because Phase 1 was subsequently reopened after a proven live defect and broader control-authority audit.

## Worktrees

Active remediation worktree:

- Path: `C:\Projects\sigenergy_optimizer-phase1-remediation`
- Branch: `fix/phase1-audit-remediation`
- Package 1 production checkpoint: `9538cc84c1235f33d52ebc2ecdf1b6b9c64896b0`; verify the exact active HEAD directly with Git because later docs-only commits may be children of this checkpoint.
- Package 2 production/test checkpoint: `d3294cb`; verify the exact active HEAD directly with Git because a later docs-only commit may be a child of this checkpoint.
- Package 3 production/test checkpoint: `91b0075`; verify the exact active HEAD directly with Git because a future docs-only commit may be a child of this checkpoint.
- Package 4A production/test checkpoint: `d3e1d56`; verify the exact active HEAD directly with Git because a future docs-only commit may be a child of this checkpoint.
- Package 4B production/test checkpoint: `19a6279`; verify the exact active HEAD directly with Git because a future docs-only commit may be a child of this checkpoint.
- Worktree state: clean after the local Package 4B checkpoint commit, before this documentation update.

Package 1 is committed at `9538cc84c1235f33d52ebc2ecdf1b6b9c64896b0` and pushed to `origin/fix/phase1-audit-remediation`. The worktree was clean after the verified push. Package 1 has not been merged, released, deployed, or live-tested.

Package 2 is committed locally at `d3294cb` and automated-validated. It has not been pushed, merged, tagged, released, deployed, installed, or live-tested.

Package 3 is committed locally at `91b0075` and automated-validated. It has not been pushed, merged, tagged, released, deployed, installed, or live-tested.

Package 4A is committed locally at `d3e1d56` and automated-validated. It has not been pushed, merged, tagged, released, deployed, installed, or live-tested.

Package 4B is committed locally at `19a6279` and automated-validated. It has not been pushed, merged, tagged, released, deployed, installed, or live-tested.

Protected/reference worktrees:

- `C:\Projects\sigenergy_optimizer`: branch `refactor/msc-baseline-overlays`, HEAD `bce8411d5274fe17fb8d883e8e7faf43e9ce8d43`, intentionally dirty. Never modify, reset, or stash it.
- `C:\Projects\sigenergy_optimizer-pv-hotfix`: clean haos53 reference at `19f3c70d24dc086737d5956a1c66cad230287edd`. Never modify it.
- `C:\Projects\sigenergy_optimizer-phase2-transition`: branch `phase2/msc-transition-settlement`, HEAD `c624f0b4392634cf19276186ba46f4b80268627b`, clean when last verified. Phase 2 is paused/frozen.

Always verify branch, HEAD, and cleanliness directly before editing.

## Current phase and gate

Phase 1 was previously declared complete and live-accepted. That is no longer true. Phase 1 is **reopened for audit remediation** because a live Morning Slow low-SoC defect was proven and the broader audit found additional fail-closed and control-authority defects.

Production Remediation Packages 1, 2, 3, 4A, and 4B are complete and automated-validated. Package 4 telemetry trust is intentionally split into 4A Tariff trust, 4B SoC/battery-energy trust, 4C Live PV/load trust, and 4D Forecast/solar-clock trust. Package 4C is next. All remaining audit remediation, full validation, and Phase 1 live acceptance must finish before Phase 2. Phase 2 is frozen before production implementation and is not the active phase.

## Production Remediation Package 1

The authority/fail-closed package is implemented in `app/models.py` and `app/optimizer.py`, automated-validated, committed at `9538cc84c1235f33d52ebc2ecdf1b6b9c64896b0`, and pushed to `origin/fix/phase1-audit-remediation`. Its test artifacts are `tests/test_haos49_failure_characterization.py` and `tests/test_phase1_authority_fail_closed_characterization.py`. Nothing from this package has been merged, released, deployed, or live-tested.

The package implements four bounded contracts:

- permissive automatic action requires genuinely observed Automated ownership; missing, unavailable, unknown, stale, or cached-only ownership is not authority, while Manual and Force remain protected;
- Demand Window observed ON or untrustworthy blocks import, while observed OFF retains ordinary import policy;
- successful HA-control `turn_on` is only a request; inverter actuator writes wait for a later trustworthy observation of HA control ON;
- unknown, unavailable, missing, or non-finite current grid-import/export limits cannot suppress a required safety close or authorize a permissive open; opening requires trusted finite observation, while ordinary deadband behavior remains for trusted finite values.

Final automated results:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -m pytest -p no:cacheprovider tests/test_phase1_authority_fail_closed_characterization.py
# 11 passed, 191 warnings
```

Targeted protection results were 37 passed for authority, Demand Window, HA control, and Manual/Force; 120 passed with the two Phase 2 tests deselected for MSC/export safety, Value Gate, and positive-FiT behavior; 5 passed for Evening Boost; and 1 passed for the corrected legacy HA-control test.

The broader suite result was **291 passed, 2 failed, 191 warnings**. The only failures were the two deliberately deferred Phase 2 transition-settlement tests named below. `python -m compileall -q app` and `git diff --check` passed.

## Production Remediation Package 2

The Morning control repair is implemented in `app/optimizer.py`, characterized in `tests/test_msc_baseline_overlay_contract.py`, automated-validated, and committed locally at `d3294cb`. It has not been pushed, merged, tagged, released, deployed, installed, or live-tested.

The proven live defect occurred at approximately 14.2-14.5% SoC with Morning Slow active, MSC observed, PV MAX 25 kW, ESS charging about 2 kW, export closed, and no deliberate battery-export owner. The old low-SoC path required the configured 2 kW slow charge plus the 1 kW `MIN_GRID_TRANSFER_KW`, creating an unintended 3 kW PV-surplus threshold.

Package 2 makes below-minimum-SoC export closure apply only when Morning Slow is inactive. Active Morning Slow no longer depends on `morning_slow_charge_rate_kw + min_grid_transfer_kw`; unrelated uses of `MIN_GRID_TRANSFER_KW` are unchanged. Morning Slow continues to own only the ESS charge rate, remains in Maximum Self Consumption with normal PV MAX, does not own export permission, retains `MSC_SURPLUS_CEILING` intent through independently owned ordinary MSC-surplus permission, and creates no battery-export owner. Package 1 authority and fail-closed protections remain intact.

Characterization results were **4 passed, 33 deselected**: safe 2.9 kW and 3.1 kW surplus cases both received the same 25 kW MSC ceiling, while unobserved Automated ownership and material or unknown battery flow remained blocked. Focused Morning Slow/MSC protection results were **24 passed, 120 deselected**. Package 1 authority/fail-closed characterization was **11 passed**; focused Remote EMS, Manual, Force, and unavailable-mode protection was **8 passed, 4 deselected**; and Value Gate, positive-FiT, negative-price, MSC-intent, and battery-export protection was **95 passed, 31 deselected**.

The final complete suite result was **295 passed, 2 failed, 191 warnings** from 297 collected tests. The only failures were the frozen Phase 2 tests `test_exact_msc_does_not_reopen_before_export_is_observed_closed` and `test_return_from_discharge_waits_for_observed_close_before_requesting_msc`. `python -m compileall -q app tests` and `git diff --check` passed. No additional regression was found.

## Production Remediation Package 3

The Battery-export safety repair is implemented in `app/optimizer.py`, characterized in `tests/test_msc_baseline_overlay_contract.py`, automated-validated, and committed locally at `91b0075` (`Fix battery export discharge ownership`). It has not been pushed, merged, tagged, released, deployed, installed, or live-tested.

The confirmed defect allowed raw positive-FiT eligibility to leak into the independent ESS-discharge actuator. That could force the discharge limit to `0.01 kW` when positive-FiT export was enabled but positive-FiT battery sale was disabled, including while the battery served house load, export was an ownerless MSC-surplus ceiling or had failed closed, telemetry was untrusted, or another deliberate battery-export owner had priority.

Package 3 applies the positive-FiT-specific ESS-discharge restriction only when the final live `export_intent` is `BATTERY_EXPORT` and the final `battery_export_owner` is `positive_fit_override`. Ordinary house-load discharge and other deliberate owners retain discharge capability. Simultaneous material battery discharge plus meaningful export and unknown-flow cases still close export; explicit positive-FiT safeguards and the negative-price `0.01 kW` clamp remain intact. Morning Dump, high-price, spike, Evening Boost, Package 2 Morning Slow behavior, Package 1 authority/fail-closed protections, and the frozen Phase 2 logic are unchanged.

Targeted validation passed: Package 3 characterization **8 passed, 7 subtests passed**; existing flow/owner protection **12 passed, 7 subtests passed**; deliberate-owner protection **18 passed, 6 subtests passed**; all four selected actual-import-cost cases; both selected negative-price cases; Package 1 authority/fail-closed **11 passed, 39 subtests passed**; focused Remote EMS/Manual/Force/unavailable-mode **8 passed, 4 deselected, 14 subtests passed**; Package 2 Morning Slow **17 passed, 126 deselected, 8 subtests passed**; and broader MSC/export/Value Gate/positive-FiT/battery-export regression **101 passed, 31 deselected, 71 subtests passed**.

The final complete suite collected 303 tests and finished **301 passed, 2 failed, 191 warnings**. The only failures were the frozen Phase 2 tests `test_exact_msc_does_not_reopen_before_export_is_observed_closed` and `test_return_from_discharge_waits_for_observed_close_before_requesting_msc`. `python -m compileall -q app tests` and `git diff --check` passed. No unexpected regression was found.

## Production Remediation Package 4A

Tariff telemetry trust is implemented in `app/optimizer.py` and `app/state_store.py`, characterized in `tests/test_phase1_tariff_telemetry_trust_characterization.py`, automated-validated, and committed locally at `d3e1d56` (`Harden tariff telemetry trust`). It has not been pushed, merged, tagged, released, deployed, installed, or live-tested.

NaN and infinite import prices cannot establish tariff-dependent import or charging authority, and non-finite or unavailable FiT cannot establish permissive FiT-dependent export authority. Missing or untrusted import price cannot establish Standby Holdoff; missing or untrusted FiT cannot establish cheap-positive import; and non-finite optimizer import-cost evidence is excluded from trusted persistence and summary use. Finite estimated positive-price policy, actual negative-price Grid Charge, positive-FiT ownership, Package 2 Morning Slow behavior, Package 3 battery-export ownership, and the trusted negative-price `0.01 kW` discharge clamp remain preserved. Trust gates are branch-specific: invalid tariff telemetry does not globally seize or block unrelated controls.

Validation passed for the Package 4A characterization (**23 passed**), existing tariff/import-cost reference set (**14 passed, 4 subtests passed**), Package 1 protections (**23 passed, 61 subtests passed**), Package 2 focused protections (**15 passed, 6 subtests passed, 124 deselected**), Package 3 protections (**13 passed, 10 subtests passed**), and broader tariff regression (**131 passed, 89 subtests passed**). The final complete suite collected 326 tests and finished **324 passed, 2 failed, 191 warnings**. The only failures were the frozen Phase 2 tests `test_exact_msc_does_not_reopen_before_export_is_observed_closed` and `test_return_from_discharge_waits_for_observed_close_before_requesting_msc`. `python -m compileall -q app tests` and `git diff --check` passed. No unexpected regression remained.

Package 4 is split into 4A Tariff trust (complete and automated-validated), 4B SoC/battery-energy trust (complete and automated-validated), 4C Live PV/load trust (next), and 4D Forecast/solar-clock trust (pending).

## Production Remediation Package 4B

SoC and battery-energy telemetry trust is implemented in `app/models.py` and `app/optimizer.py`, characterized in `tests/test_phase1_battery_telemetry_trust_characterization.py`, automated-validated, and committed locally at `19a6279` (`Harden battery telemetry trust`). It has not been pushed, merged, tagged, released, deployed, installed, or live-tested.

`SolarState` now records `battery_soc_trusted`, `battery_capacity_trusted`, and `available_discharge_energy_trusted`, allowing the read path to retain conservative numeric fallbacks without treating them as trusted evidence. SoC is trusted only when freshly observed, finite, and within 0% through 100%; genuine fresh 0% and 100% remain trusted values, while missing, unavailable, unknown, non-finite, out-of-range, and stale observations cannot authorize behavior. Missing or unusable capacity may retain the synthetic 10 kWh arithmetic fallback but cannot make it permissive. Missing available energy remains a conservative numeric 0 kWh, while unavailable, non-finite, or stale available energy cannot become permissive proof.

Trust remains branch-specific rather than a global battery-telemetry veto. Positive-price top-up requires trusted SoC and capacity. Deliberate battery-export owners require the trusted battery facts they depend on; Morning Dump and Evening Boost require trusted SoC, capacity, and available energy. Exact-full PV-only MSC eligibility requires trusted SoC, and refill/energy-dependent branches cannot use synthetic capacity or stale available energy permissively. Ordinary trusted MSC surplus remains independent of unavailable SoC where that branch does not require SoC proof.

Preserved behavior includes genuine fresh 0% semantics, genuine exact-full 100% PV-only MSC behavior, conservative missing-available-energy behavior, ordinary MSC independence from unavailable SoC, Package 1 authority/fail-closed protections, Package 2 Morning Slow, Package 3 battery-export ownership, Package 4A tariff trust, Manual/Force, Demand Window, advisory-only Value Gate, normal PV MAX, Morning Dump's 15% floor, Evening Boost, negative-price behavior, and the rule that ordinary positive FiT does not implicitly create battery export.

Validation passed for the Package 4B characterization (**22 passed, 191 warnings**) and narrow regression set (**90 collected, 88 passed, 2 deselected, 191 warnings**), with the two frozen Phase 2 tests deselected. The complete suite collected 348 tests and finished **346 passed, 2 failed, 191 warnings**. The only failures were the frozen Phase 2 tests `test_exact_msc_does_not_reopen_before_export_is_observed_closed` and `test_return_from_discharge_waits_for_observed_close_before_requesting_msc`. `python -m compileall -q app tests` and `git diff --check` passed. No unexpected functional regression remained.

## Parked live defect: PV-only export-ceiling flapping

A live `2.3.43-haos54` observation on 2026-09-08 showed repeated PV-only MSC export-ceiling oscillation between 25 kW and closed (`0.01 kW`). Automated ownership, Maximum Self Consumption, 100% battery SoC, and 25 kW PV MAX remained observed; no deliberate battery-export owner was active, and import price and FiT were essentially stable. The direct battery sensor remained near zero discharge at approximately `-0.006 kW`, while the derived battery-discharge value used by the PV-only safety classification intermittently indicated approximately `0.7-1.43 kW`. Those cycles were classified as simultaneous battery discharge plus grid export and failed export closed; subsequent settled-looking cycles returned within flow tolerance and reopened the 25 kW MSC ceiling.

The root cause is not proven. Cross-sensor timing or snapshot incoherence and/or post-actuation settlement lag may temporarily make PV/load/grid-flow arithmetic disagree with the direct battery-power sensor. The observed response appears fail-safe because export closes when battery-backed export cannot be disproven, but it is unstable: it creates repeated `0.01 <-> 25 kW` actuator chatter, interrupts legitimate PV-surplus export, and destabilizes control reasons. There is no evidence from this observation of an actual deliberate battery dump.

Do not weaken the simultaneous battery-discharge plus grid-export fail-closed rule to suppress the flapping. This issue is parked for the 4C/Package 5 boundary: 4C must first characterize and, if appropriate, repair telemetry-coherence/trust causes; any remaining reopen-before-settlement, actuator-readback timing, or transition-settling defect belongs in Package 5. Package 4C Live PV/load trust is the immediate next engineering task.

## Remaining audit findings requiring remediation

High/proven static findings unless noted otherwise:

- export-spike minimum SoC does not enforce a real spike floor;
- configured baselines can enlarge an observed capability cap, and capability domains are conflated;
- failed cycles lack a reliable settled safe fallback, fallback results are unchecked, and partial actuator failures are asymmetric;
- `/set_ess` can report success despite failed service calls;
- some paths accept core PV/load telemetry without equivalent freshness proof.

Medium findings:

- cheap-positive import can steal Morning Slow EMS ownership;
- Morning Dump and negative-price paths can issue internally conflicting intent.

Policy/test items still requiring decisions:

- Morning Dump post-window grace is based on time/enablement rather than proof that a dump occurred;
- Battery Full Safeguard suppresses the ordinary MSC surplus ceiling; final policy remains unresolved.

Preserve intentional behavior: Morning Dump's 15% floor, Evening Boost, advisory-only Value Gate, no implicit battery export from ordinary positive-FiT export, and user ownership of Manual/Force modes.

## Approved non-positive import policy

Approved but **not yet implemented**: trusted actual import price `<= 0 $/kWh` becomes an explicit high-priority charging owner. It requests Grid First, the maximum safe/permitted grid-import capability, and the maximum safe/permitted ESS-charge capability using separate capability domains.

It overrides Morning Slow charging/EMS ownership and Morning Dump. Demand Window remains higher priority and blocks import; Manual/Force and hardware/safety limits remain protected. A positive price must not steal Morning Slow ownership, and transition back to positive while Morning Slow is eligible returns to MSC plus slow charge. Non-positive import does not itself imply PV curtailment.

Still unresolved: exact-zero import when FiT/export is extremely valuable, and PV MAX policy during non-positive import.

## Relevant operator tuning

These are operator settings, not software-default policy:

- normal PV MAX and high export ceiling: 25 kW;
- `MIN_SOC_FLOOR`: 20%; `MIN_EXPORT_TARGET_SOC`: 90%;
- Morning Slow: enabled, 2 kW, until 11:00, minimum FiT `0.01`, base load 2 kW;
- Morning Dump: enabled, 15% floor;
- Evening Boost: enabled, 35% floor, safety multiplier 1.1, minimum tomorrow forecast 100 kWh;
- `MIN_GRID_TRANSFER_KW`: 1 kW;
- Forecast Safety Charging: 1.35; Forecast Safety Export: 1.1;
- Solar Surplus Bypass: enabled at 2.0 / 1.25 / 0.5;
- spike minimum SoC: 60%, although current implementation does not enforce it;
- cheap-positive threshold: `0.015 $/kWh`; daytime top-up maximum SoC: 50%; target battery charge: 2 kW;
- Demand Window remains the higher-priority import block; Value Gate remains advisory-only.

## Frozen Phase 2 contract

Future Phase 2 returns from deliberate battery export by closing export, later observing it closed, requesting MSC, later observing exact MSC, and only then reopening the normal 25 kW export ceiling. Entry into deliberate battery export must settle the export target before selecting discharge EMS. Service-call success is not observed inverter state.

Protect the two existing expected Phase 2 failures:

- `test_return_from_discharge_waits_for_observed_close_before_requesting_msc`
- `test_exact_msc_does_not_reopen_before_export_is_observed_closed`

## Exact next action

Production Remediation Packages 1, 2, 3, 4A, and 4B are complete and automated-validated. Package 4B is committed locally at `19a6279` but is not pushed, deployed, or live-tested. The exact next engineering subpackage is 4C Live PV/load trust, beginning with characterization of the parked telemetry-coherence hypothesis. Preserve all completed checkpoints and do not begin Phase 2. Verify the exact active HEAD directly with Git after any documentation commit rather than hard-coding that future child commit here.
