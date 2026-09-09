# Current State

Last consolidated: 2026-09-09

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
- Package 4C production/test checkpoint: `85cfb1d`; verify the exact active HEAD directly with Git because a future docs-only commit may be a child of this checkpoint.
- Package 4D production/test checkpoint: `44c63e80fa72655087504f5c612df10e6b77109f` (`Harden forecast and solar-clock telemetry trust`).
- Package 5 actuator/fallback production/test checkpoint: `4c9c0e2663357a65e8cdf80d7c6d1cf7ea8d0473` (`Harden actuator fallback and settlement handling`).
- Package 5 chatter/reopen production/test checkpoint: `e119f6f` (`Repair Morning Slow MSC ceiling chatter`).
- Package 6A capability-trust production/test checkpoint: `f95f9ce01a53e66a533edbfe3bd423e4ee3dafd3` (`Repair Package 6A capability trust`).
- Package 6A documentation checkpoint: `f1ade7b0db500cadcdfccce7e2fd5e7d3a5cf573`.
- Verify the exact branch tip, worktree status, and remote synchronization directly with Git; documentation commits may be children of the production/test checkpoints.

Package 1 is committed at `9538cc84c1235f33d52ebc2ecdf1b6b9c64896b0` and pushed to `origin/fix/phase1-audit-remediation`. The worktree was clean after the verified push. Package 1 has not been merged, released, deployed, or live-tested.

Package 2 is committed at `d3294cb`, automated-validated, and present on the remote remediation branch. It has not been merged, tagged, released, deployed, installed, or live-tested.

Package 3 is committed at `91b0075`, automated-validated, and present on the remote remediation branch. It has not been merged, tagged, released, deployed, installed, or live-tested.

Package 4A is committed at `d3e1d56`, automated-validated, and pushed. It has not been merged, tagged, released, deployed, installed, or live-tested.

Package 4B is committed at `19a6279`, automated-validated, and pushed. It has not been merged, tagged, released, deployed, installed, or live-tested.

Package 4C is committed at `85cfb1d`, automated-validated, and pushed. It has not been merged, tagged, released, deployed, installed, restarted, or live-tested.

Package 4D is committed at `44c63e80fa72655087504f5c612df10e6b77109f`, automated-validated, and present on the remote remediation branch. It has not been merged, tagged, released, deployed, installed, restarted, or live-tested.

Package 5 actuator/fallback reliability is committed at `4c9c0e2663357a65e8cdf80d7c6d1cf7ea8d0473`, automated-validated, and pushed. The chatter/reopen repair is committed at `e119f6f` and automated-validated. Package 5 has not been merged, tagged, released, deployed, installed, restarted, live-tested, or live-accepted.

Package 6A is committed at `f95f9ce01a53e66a533edbfe3bd423e4ee3dafd3`, complete, automated-validated, and pushed to `origin/fix/phase1-audit-remediation`. Its documentation checkpoint `f1ade7b0db500cadcdfccce7e2fd5e7d3a5cf573` is also pushed. It has not been merged, tagged, released, deployed, installed, restarted, live-tested, or live-accepted.

Protected/reference worktrees:

- `C:\Projects\sigenergy_optimizer`: branch `refactor/msc-baseline-overlays`, HEAD `bce8411d5274fe17fb8d883e8e7faf43e9ce8d43`, intentionally dirty. Never modify, reset, or stash it.
- `C:\Projects\sigenergy_optimizer-pv-hotfix`: clean haos53 reference at `19f3c70d24dc086737d5956a1c66cad230287edd`. Never modify it.
- `C:\Projects\sigenergy_optimizer-phase2-transition`: branch `phase2/msc-transition-settlement`, HEAD `c624f0b4392634cf19276186ba46f4b80268627b`, clean when last verified. Phase 2 is paused/frozen.

Always verify branch, HEAD, and cleanliness directly before editing.

## Current phase and gate

Phase 1 was previously declared complete and live-accepted. That is no longer true. Phase 1 is **reopened for audit remediation** because a live Morning Slow low-SoC defect was proven and the broader audit found additional fail-closed and control-authority defects.

Production Remediation Packages 1, 2, 3, telemetry-trust Packages 4A through 4D, both Package 5 subparts, and Package 6A are complete and automated-validated. Package 6B architecture/design for authoritative grid-import and PV hardware capability is next. The Morning Slow forecast-feasibility discrepancy remains parked until after Package 6. All remaining audit remediation, full validation, and renewed Phase 1 live acceptance must finish before Phase 2. Phase 2 is frozen before production implementation and is not active.

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

Characterization results were **4 passed, 33 deselected**: safe 2.9 kW and 3.1 kW surplus cases both received the same 25 kW MSC ceiling, while unobserved Automated ownership and unsafe or unknown flow remained blocked. Focused Morning Slow/MSC protection results were **24 passed, 120 deselected**. Package 1 authority/fail-closed characterization was **11 passed**; focused Remote EMS, Manual, Force, and unavailable-mode protection was **8 passed, 4 deselected**; and Value Gate, positive-FiT, negative-price, MSC-intent, and battery-export protection was **95 passed, 31 deselected**.

The final complete suite result was **295 passed, 2 failed, 191 warnings** from 297 collected tests. The only failures were the frozen Phase 2 tests `test_exact_msc_does_not_reopen_before_export_is_observed_closed` and `test_return_from_discharge_waits_for_observed_close_before_requesting_msc`. `python -m compileall -q app tests` and `git diff --check` passed. No additional regression was found.

## Production Remediation Package 3

The Battery-export safety repair is implemented in `app/optimizer.py`, characterized in `tests/test_msc_baseline_overlay_contract.py`, automated-validated, and committed locally at `91b0075` (`Fix battery export discharge ownership`). It has not been pushed, merged, tagged, released, deployed, installed, or live-tested.

The confirmed defect allowed raw positive-FiT eligibility to leak into the independent ESS-discharge actuator. That could force the discharge limit to `0.01 kW` when positive-FiT export was enabled but positive-FiT battery sale was disabled, including while the battery served house load, export was an ownerless MSC-surplus ceiling or had failed closed, telemetry was untrusted, or another deliberate battery-export owner had priority.

Package 3 applies the positive-FiT-specific ESS-discharge restriction only when the final live `export_intent` is `BATTERY_EXPORT` and the final `battery_export_owner` is `positive_fit_override`. Ordinary house-load discharge and other deliberate owners retain discharge capability. Simultaneous material battery discharge plus meaningful export and unknown-flow cases still close export; explicit positive-FiT safeguards and the negative-price `0.01 kW` clamp remain intact. Morning Dump, high-price, spike, Evening Boost, Package 2 Morning Slow behavior, Package 1 authority/fail-closed protections, and the frozen Phase 2 logic are unchanged.

Targeted validation passed: Package 3 characterization **8 passed, 7 subtests passed**; existing flow/owner protection **12 passed, 7 subtests passed**; deliberate-owner protection **18 passed, 6 subtests passed**; all four selected actual-import-cost cases; both selected negative-price cases; Package 1 authority/fail-closed **11 passed, 39 subtests passed**; focused Remote EMS/Manual/Force/unavailable-mode **8 passed, 4 deselected, 14 subtests passed**; Package 2 Morning Slow **17 passed, 126 deselected, 8 subtests passed**; and broader MSC/export/Value Gate/positive-FiT/battery-export regression **101 passed, 31 deselected, 71 subtests passed**.

The final complete suite collected 303 tests and finished **301 passed, 2 failed, 191 warnings**. The only failures were the frozen Phase 2 tests `test_exact_msc_does_not_reopen_before_export_is_observed_closed` and `test_return_from_discharge_waits_for_observed_close_before_requesting_msc`. `python -m compileall -q app tests` and `git diff --check` passed. No unexpected regression was found.

## Production Remediation Package 4A

Tariff telemetry trust is implemented in `app/optimizer.py` and `app/state_store.py`, characterized in `tests/test_phase1_tariff_telemetry_trust_characterization.py`, automated-validated, committed at `d3e1d56` (`Harden tariff telemetry trust`), and pushed. It has not been merged, tagged, released, deployed, installed, or live-tested.

NaN and infinite import prices cannot establish tariff-dependent import or charging authority, and non-finite or unavailable FiT cannot establish permissive FiT-dependent export authority. Missing or untrusted import price cannot establish Standby Holdoff; missing or untrusted FiT cannot establish cheap-positive import; and non-finite optimizer import-cost evidence is excluded from trusted persistence and summary use. Finite estimated positive-price policy, actual negative-price Grid Charge, positive-FiT ownership, Package 2 Morning Slow behavior, Package 3 battery-export ownership, and the trusted negative-price `0.01 kW` discharge clamp remain preserved. Trust gates are branch-specific: invalid tariff telemetry does not globally seize or block unrelated controls.

Validation passed for the Package 4A characterization (**23 passed**), existing tariff/import-cost reference set (**14 passed, 4 subtests passed**), Package 1 protections (**23 passed, 61 subtests passed**), Package 2 focused protections (**15 passed, 6 subtests passed, 124 deselected**), Package 3 protections (**13 passed, 10 subtests passed**), and broader tariff regression (**131 passed, 89 subtests passed**). The final complete suite collected 326 tests and finished **324 passed, 2 failed, 191 warnings**. The only failures were the frozen Phase 2 tests `test_exact_msc_does_not_reopen_before_export_is_observed_closed` and `test_return_from_discharge_waits_for_observed_close_before_requesting_msc`. `python -m compileall -q app tests` and `git diff --check` passed. No unexpected regression remained.

Package 4 telemetry trust is automated-complete and present on the remote remediation branch: 4A Tariff trust, 4B SoC/battery-energy trust, 4C Live PV/load trust, and 4D Forecast/solar-clock trust. None is deployed or live-accepted.

## Production Remediation Package 4B

SoC and battery-energy telemetry trust is implemented in `app/models.py` and `app/optimizer.py`, characterized in `tests/test_phase1_battery_telemetry_trust_characterization.py`, automated-validated, committed at `19a6279` (`Harden battery telemetry trust`), and pushed. It has not been merged, tagged, released, deployed, installed, or live-tested.

`SolarState` now records `battery_soc_trusted`, `battery_capacity_trusted`, and `available_discharge_energy_trusted`, allowing the read path to retain conservative numeric fallbacks without treating them as trusted evidence. SoC is trusted only when freshly observed, finite, and within 0% through 100%; genuine fresh 0% and 100% remain trusted values, while missing, unavailable, unknown, non-finite, out-of-range, and stale observations cannot authorize behavior. Missing or unusable capacity may retain the synthetic 10 kWh arithmetic fallback but cannot make it permissive. Missing available energy remains a conservative numeric 0 kWh, while unavailable, non-finite, or stale available energy cannot become permissive proof.

Trust remains branch-specific rather than a global battery-telemetry veto. Positive-price top-up requires trusted SoC and capacity. Deliberate battery-export owners require the trusted battery facts they depend on; Morning Dump and Evening Boost require trusted SoC, capacity, and available energy. Exact-full PV-only MSC eligibility requires trusted SoC, and refill/energy-dependent branches cannot use synthetic capacity or stale available energy permissively. Ordinary trusted MSC surplus remains independent of unavailable SoC where that branch does not require SoC proof.

Preserved behavior includes genuine fresh 0% semantics, genuine exact-full 100% PV-only MSC behavior, conservative missing-available-energy behavior, ordinary MSC independence from unavailable SoC, Package 1 authority/fail-closed protections, Package 2 Morning Slow, Package 3 battery-export ownership, Package 4A tariff trust, Manual/Force, Demand Window, advisory-only Value Gate, normal PV MAX, Morning Dump's 15% floor, Evening Boost, negative-price behavior, and the rule that ordinary positive FiT does not implicitly create battery export.

Validation passed for the Package 4B characterization (**22 passed, 191 warnings**) and narrow regression set (**90 collected, 88 passed, 2 deselected, 191 warnings**), with the two frozen Phase 2 tests deselected. The complete suite collected 348 tests and finished **346 passed, 2 failed, 191 warnings**. The only failures were the frozen Phase 2 tests `test_exact_msc_does_not_reopen_before_export_is_observed_closed` and `test_return_from_discharge_waits_for_observed_close_before_requesting_msc`. `python -m compileall -q app tests` and `git diff --check` passed. No unexpected functional regression remained.

## Production Remediation Package 4C

Live PV/load telemetry trust is implemented in `app/models.py` and `app/optimizer.py`, characterized in `tests/test_phase1_pv_load_telemetry_trust_characterization.py`, automated-validated, committed at `85cfb1d` (`Harden PV and load telemetry trust`), and pushed. It has not been merged, tagged, released, deployed, installed, restarted, or live-tested.

`SolarState` now records `pv_power_trusted`, `load_power_trusted`, `derived_power_flow_coherent`, and `derived_power_flow_span_seconds`. The live read path captures PV, load, battery, and grid observations once per cycle, preserves PV/load trust separately from conservative scalar fallbacks, and retains timestamp-span provenance for derived power-flow coherence. It uses the existing `hvac_solar_data_max_age_seconds` freshness basis, 120 seconds by default, and adds no configuration setting.

Missing, unavailable, unknown, non-finite, stale, or otherwise invalid PV/load readings cannot become permissive evidence. Genuine fresh finite 0 kW PV and 0 kW load remain trusted zeros, and valid fresh positive readings remain trusted. Exact-full PV-only MSC permission requires trusted PV/load where that branch uses those observations, and Solar Surplus Bypass requires trusted PV/load for its surplus calculation. Ordinary MSC and economic branches that do not depend on PV/load proof remain independent; HVAC solar permission continues to fail unavailable or stale inputs appropriately.

Battery-flow evidence retains this hierarchy: fresh/trusted direct battery-power evidence first, coherent derived PV/load/grid evidence second, and otherwise battery-flow safety is not proven. Incoherent or unknown derived flow is not positive proof of battery safety, and the simultaneous battery-discharge plus grid-export fail-closed rule is unchanged.

Package 4C preserves genuine exact-full behavior with trusted evidence, fresh direct battery authority, HVAC solar permission behavior, ordinary MSC independence where PV/load proof is unnecessary, Packages 1 through 4B, Manual/Force, Demand Window, advisory-only Value Gate, normal PV MAX, Morning Dump's 15% floor, Evening Boost, negative-price behavior, and the rule that ordinary positive FiT does not implicitly create battery export.

Validation: Package 4C characterization **15 passed, 191 warnings**; focused regression **151 collected, 149 passed, 2 frozen Phase 2 tests deselected, 191 warnings**; complete suite **363 collected, 361 passed, 2 failed, 191 warnings**. The only failures were the frozen Phase 2 tests `test_exact_msc_does_not_reopen_before_export_is_observed_closed` and `test_return_from_discharge_waits_for_observed_close_before_requesting_msc`. `python -m compileall -q app tests` and `git diff --check` passed. No unexpected functional regression remained.

## Production Remediation Package 4D

Forecast and solar-clock telemetry trust is implemented in `app/models.py` and `app/optimizer.py`, characterized in `tests/test_phase1_forecast_solar_clock_telemetry_trust_characterization.py`, automated-validated, and committed at `44c63e80fa72655087504f5c612df10e6b77109f` (`Harden forecast and solar-clock telemetry trust`). It is present on the remote remediation branch through current checkpoint `68bfa92393c7ff3bd69871acf3ec0bc269eb868d`. It has not been merged, tagged, released, deployed, installed, restarted, or live-tested.

Aggregate provenance is retained separately in `forecast_remaining_observation_trusted`, `forecast_today_observation_trusted`, and `forecast_tomorrow_observation_trusted`; detailed-source provenance is retained in `solcast_detailed_source_trusted`; and solar-clock provenance is retained separately in `sun_state_observation_trusted`, `sunrise_observation_trusted`, and `sunset_observation_trusted`. Forecasts use the existing 600-second `hvac_solar_forecast_max_age_seconds` basis, while sun telemetry uses the existing 120-second `hvac_solar_data_max_age_seconds` basis and HA `last_reported`/`last_updated` metadata. `next_rising` and `next_setting` retain their existing future-timestamp meaning. No configuration or timing threshold was added.

Fresh finite aggregate forecasts, including genuine `0.0`, can be trusted. Missing, unavailable, malformed, or non-finite values may remain numeric `0.0` for conservative arithmetic but are untrusted; stale finite values may remain visible diagnostically but cannot become trusted permissive proof. Solar Surplus Bypass and solar export override require trusted remaining forecast, Standby Holdoff requires trusted today and remaining forecast, and Evening Boost requires trusted tomorrow and detailed forecast evidence. Stale-high remaining forecast no longer suppresses Forecast Safety Charging as trusted evidence, while missing or invalid forecast retains the conservative charging direction. Forecast uncertainty does not globally veto unrelated owners.

Detailed point dictionaries remain structurally compatible, but required timestamps and `pv_estimate` values must be finite before becoming permissive evidence; NaN and infinities are ignored. An untrusted detailed source cannot authorize Morning Dump, and evidence at or before the dump-window boundary cannot permissively reduce future load need in the proven prior-day case. No minimum horizon, point count, completeness requirement, intended-day alignment policy, or forecast issue-age policy beyond existing source freshness was created.

Parsed sun values may remain diagnostically available while untrusted. Morning Dump now requires trusted detailed source, sun state, and sunrise evidence, while preserving deliberate battery-export ownership, its 15% floor, tariff and battery-state trust, and existing priority. Missing, unavailable, unknown, or malformed sunrise cannot construct a permissive dump window. `close_to_sunset` requires trusted sunset evidence, so missing, stale, malformed, or prior sunset evidence cannot relax export forecast guards. Local wall-clock time remains distinct from HA sun telemetry trust, and no sunrise/sunset tolerance was invented. The separate Morning Dump post-window grace policy remains unresolved.

Package 4D preserved genuine fresh zero forecasts, conservative safety charging, negative-price Grid Charge independence, Manual/Force, Demand Window, advisory-only Value Gate, normal PV MAX, Morning Dump's floor, Evening Boost policy apart from telemetry trust, Packages 1 through 4C, the direct-before-derived battery-flow hierarchy, and the rule that ordinary positive FiT does not implicitly create battery export.

Validation: Package 4D characterization **26 passed, 191 warnings**; focused regression **88 passed, 191 warnings**; complete suite **389 collected, 387 passed, 2 failed, 191 warnings**. The only failures were the frozen Phase 2 tests `test_exact_msc_does_not_reopen_before_export_is_observed_closed` and `test_return_from_discharge_waits_for_observed_close_before_requesting_msc`. `python -m compileall -q app tests` and `git diff --check` passed. No unexpected functional regression remained.

## Production Remediation Package 5

Package 5 actuator/fallback reliability and chatter/reopen repair are complete and automated-validated. The actuator/fallback production/test checkpoint is `4c9c0e2663357a65e8cdf80d7c6d1cf7ea8d0473` (`Harden actuator fallback and settlement handling`); the chatter/reopen production/test checkpoint is `e119f6f` (`Repair Morning Slow MSC ceiling chatter`). Package 5 has not been merged, tagged, released, deployed, installed, restarted, live-tested, or live-accepted.

### Actuator/fallback reliability

`_apply` now returns an explicit application result. Required actuator write failures propagate as failed application; fallback return values are inspected; ordinary fallback exceptions remain visible while later independent safety actions are still attempted; and partial/asymmetric failures make the whole application fail. Successful fallback requests do not turn a failed primary application into observed success. This is failure accounting and fail-closed fallback, not transactional rollback.

`_tick` advances remembered applied decision/state only after successful application, restores the previous remembered state after failed pre-commit application, and retains application failure in cycle diagnostics. An ordinary export safety-close request now requires one immediate observed readback before it is considered settled. Open, unavailable, non-finite, or otherwise untrusted readback leaves application failed and allows later close reissue. Service-call success is not observed inverter state.

Validation: Package 5 characterization **19 passed, 191 warnings**; focused regression **84 collected, 82 passed, 2 deselected, 191 warnings**; complete suite **408 collected, 406 passed, 2 failed, 191 warnings**. The only failures were the frozen Phase 2 tests `test_exact_msc_does_not_reopen_before_export_is_observed_closed` and `test_return_from_discharge_waits_for_observed_close_before_requesting_msc`. `python -m compileall -q app tests` and `git diff --check` passed. No unexpected functional regression remained.

### Chatter/reopen repair

Morning Slow's high MSC ceiling no longer closes merely because trusted battery discharge crosses `0.10 kW`. For this safety decision Morning Slow now reuses the existing trusted ordinary-MSC flow classification: trusted load-serving battery discharge with grid export below the existing meaningful threshold is compatible with the MSC surplus ceiling; meaningful simultaneous battery discharge and grid export remains fail-closed; and unknown or untrusted battery or grid-export evidence remains fail-closed. Solar Surplus retains its separate raw battery-discharge protection. Ordinary positive-FiT behavior, battery-export ownership, Manual/Force, Demand Window, PV MAX, and unrelated safety behavior are unchanged.

The existing `0.10 kW` battery tolerance and `0.5 kW` meaningful grid-export threshold were not changed. No timer, deadband, hysteresis, cycle count, settlement duration, or reopen delay was added.

Characterization confirms that `0.094 kW` and `0.101 kW` discharge with negligible export both retain the `25 kW` MSC ceiling, with `0.101 kW` classified as load-serving. Alternating `0.094 / 0.101 / 0.094 / 0.101` remains `25 / 25 / 25 / 25 kW`. A `1.0 kW` discharge with `0.499999 kW` export can remain load-serving/open; exactly `0.5 kW` export with discharge above `0.10 kW` becomes simultaneous/closed. The approximately `0.273 kW` discharge plus `1.837 kW` export case remains simultaneous/fail-closed. The approximately `3.2 kW` load-serving case remains independently closed through `closed_no_daytime_pv`. Unknown battery flow and unknown, stale, or non-finite grid-export flow close.

Validation: chatter characterization **11 passed, 191 warnings**; affected actuator and Value Gate tests **108 passed, 191 warnings**; focused protection **200 collected, 198 passed, 2 deselected, 191 warnings**; complete suite **419 collected, 417 passed, 2 failed, 191 warnings**. The only failures were the frozen Phase 2 tests `test_exact_msc_does_not_reopen_before_export_is_observed_closed` and `test_return_from_discharge_waits_for_observed_close_before_requesting_msc`. Compileall and `git diff --check` passed.

## Production Remediation Package 6A

Package 6A repairs trust handling for the existing grid-export, ESS-charge, and ESS-discharge capability sources. It is complete, automated-validated, and pushed to `origin/fix/phase1-audit-remediation` at `f95f9ce01a53e66a533edbfe3bd423e4ee3dafd3` (`Repair Package 6A capability trust`). Its documentation checkpoint `f1ade7b0db500cadcdfccce7e2fd5e7d3a5cf573` is also pushed. It has not been merged, tagged, released, deployed, installed, restarted, live-tested, or live-accepted.

For Automated control, a trusted hardware capability is an upper bound, while a configured ESS baseline is a request and not capability evidence. Charge and discharge remain separate domains; the effective bound is the minimum of current trusted sources in the same domain. If no current trusted source exists, Automated control uses the cached trusted rating for that domain and then `ESS_LIMIT_FALLBACK_KW`. Invalid, unavailable, non-finite, or out-of-range evidence cannot enlarge a capability. Trusted grid-export number-entity maximum metadata bounds the Automated export target.

Manual/Force behavior is temporarily frozen to exact pre-Package-6A capability inputs and fallback behavior through an isolated legacy compatibility path. This covers Manual, Full Import, Full Import + PV, Full Export, Block Flow, and manual ESS charge and discharge overrides. The compatibility path is not long-term capability policy and must not be revisited until all currently planned work is complete.

Validation: Package 6A characterization **21 passed**; Manual/Force protection **13 passed, 5 deselected**; Automated export/ESS actuator protection **115 passed**; and the additional Manual/Force freeze regressions passed. The complete suite collected **440 tests: 438 passed, 2 failed, 191 warnings**. The only failures were the frozen Phase 2 tests `test_exact_msc_does_not_reopen_before_export_is_observed_closed` and `test_return_from_discharge_waits_for_observed_close_before_requesting_msc`. `python -m compileall -q app tests` and `git diff --check` passed.

## Parked investigation: Morning Slow forecast feasibility

Live observation found Morning Slow active with actual operator settings: enabled `True`, until `11:00`, charge rate `2 kW`, minimum feed-in price `0.01 $/kWh`, base-load allowance `2 kW`, and sunset cutoff `1 hour`. These are live operator settings, not software defaults.

At the time, observed values were approximately 15.9% SoC, 6.4 kWh available battery energy, 40 kWh battery capacity, 57.8 kWh remaining solar forecast, 3.5 kW PV, 0.9 kW load, and 2.57 kW battery charging. The implementation requires remaining forecast to cover battery refill need plus assumed load until the slow-charge solar cutoff, multiplied by the configured forecast-safety factor. The displayed values appear difficult to reconcile with Morning Slow eligibility, but this is not yet a confirmed production bug and does not justify changing operator settings or software defaults.

The later bounded investigation must capture and compare the exact trusted remaining forecast, battery capacity, available discharge energy, calculated refill need, calculated slow-charge end timestamp, hours left, configured base load, calculated load need, forecast-safety charging multiplier, final `required_kwh`, and final Morning Slow eligibility result. It must determine whether the observation reflects expected operator tuning, stale or different live inputs, a calculation/provenance mismatch, or a real implementation defect. No diagnostics or production change is approved yet.

## Remaining audit findings requiring remediation

High/proven static findings unless noted otherwise:

- export-spike minimum SoC does not enforce a real spike floor;
- grid-import and PV still require authoritative hardware capability sources and domain-specific architecture in Package 6B;
- `/set_ess` can report success despite failed service calls;

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
- Morning Slow: enabled `True`, 2 kW charge rate, until 11:00, minimum FiT `0.01`, base-load allowance 2 kW, sunset cutoff 1 hour;
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

Package 6B architecture/design for authoritative grid-import and PV hardware capability is the exact next engineering action. Do not map ESS charge capability to grid import or another capability domain to PV. Keep the Morning Slow forecast-feasibility discrepancy parked until after Package 6. Then continue in the existing order with Package 7 `/set_ess`, Package 8 configuration validation and persistence, Package 9 settings/UI, remaining cleanup, full Phase 1 validation and live acceptance, Phase 2, the short ownership audit, and Climate Manager. Do not deploy, live-test, or begin Phase 2 without separate authorization.
