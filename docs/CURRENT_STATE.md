# Current State

Last consolidated: 2026-09-15

**CURRENT TRUTH ONLY:** this file records the current operational and development checkpoint, not historical record. Durable control semantics live in `CONTROL_CONTRACT.md`; sequencing lives in `ROADMAP.md`.

Authority depends on the subject: GitHub for committed repository state; the relevant verified worktree for local uncommitted state; Home Assistant/Sigenergy observations and logs for live behavior; and actual Home Assistant/add-on settings for operator configuration. If this file conflicts with an authoritative source, report and correct the stale documentation at the next permitted documentation boundary.

## Live release and rollback

- Current live release: `2.3.45-haos56`.
- Live `.56` proved the Morning Dump telemetry/forecast repair, Morning Slow activation with actual charging around `2 kW`, static battery-capacity trust, and detailed Solcast trust/coverage.
- Live acceptance remains withheld because `.56` exhibited genuine exact-full Cheap-FiT desired export-ceiling chatter `25 -> 0 -> 25 -> 0 kW` as sub-1 kW PV/load readings crossed the former instantaneous adequacy boundary.
- The bounded repair is committed and pushed at `9e5517ea85dea286608d564cbe2cdeaa18a2e03e` (`Stabilize exact-full cheap-FiT MSC ceiling`). Candidate identity and documentation for `2.3.46-haos57` are now being prepared locally; they are not committed, tagged, built, published, installed, restarted, or live-tested.
- The rollback ladder remains the immediate fresh `.55` backup, followed by deeper `.54`/`.53` fallbacks. `.54` has known exact-full and Solar Surplus defects and is not preferred.

Rollback, if separately authorized, means stop the add-on, restore Sig Opt only, then verify EMS, PV MAX, export, and Home Assistant control. No rollback is currently being performed.

GitHub `main` is at `1566beb3252119aabc060b39420581ca3a550631` (`Prepare 2.3.45-haos56 repair candidate`). The exact-full chatter repair remains on the synchronized remediation branch pending the `.57` candidate checkpoint.

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
- Package 6A documentation-sync checkpoint: `a60f71063ef4c3c3043e18f5f1ef4eb85787bc69`.
- Current committed HEAD: `9e5517ea85dea286608d564cbe2cdeaa18a2e03e` (`Stabilize exact-full cheap-FiT MSC ceiling`).
- Before `.57` candidate preparation, the branch was pushed and synchronized with `origin/fix/phase1-audit-remediation` at that commit, with divergence 0/0 and a clean worktree.
- Local status: candidate identity and documentation for `2.3.46-haos57` are being prepared as uncommitted changes. Live remains `2.3.45-haos56`; no tag, build, publish, release, deployment, installation, restart, Home Assistant write, or Sigenergy write is part of this preparation.
- Verify the exact branch tip, worktree status, and remote synchronization directly with Git; documentation commits may be children of the production/test checkpoints.

Package 1 is committed at `9538cc84c1235f33d52ebc2ecdf1b6b9c64896b0`, pushed, and included in live `.56`; renewed live acceptance is withheld.

Package 2 is committed at `d3294cb`, automated-validated, pushed, and included in live `.56`; renewed live acceptance is withheld.

Package 3 is committed at `91b0075`, automated-validated, pushed, and included in live `.56`; renewed live acceptance is withheld.

Package 4A is committed at `d3e1d56`, automated-validated, pushed, and included in live `.56`; renewed live acceptance is withheld.

Package 4B is committed at `19a6279`, automated-validated, pushed, and included in live `.56`; renewed live acceptance is withheld.

Package 4C is committed at `85cfb1d`, automated-validated, pushed, and included in live `.56`; renewed live acceptance is withheld.

Package 4D is committed at `44c63e80fa72655087504f5c612df10e6b77109f`, automated-validated, pushed, and included in live `.56`; its follow-up trust repair at `df90c365fc0413ad0ce048a2796ab8df30ec0c0a` is live-proven in `.56`.

Package 5 actuator/fallback reliability is committed at `4c9c0e2663357a65e8cdf80d7c6d1cf7ea8d0473`; the chatter/reopen repair is committed at `e119f6f`. Both are automated-validated, pushed, and included in live `.56`; renewed live acceptance is withheld.

Package 6A is committed at `f95f9ce01a53e66a533edbfe3bd423e4ee3dafd3`, complete, automated-validated, pushed, and included in live `.56`. Its documentation checkpoints `f1ade7b0db500cadcdfccce7e2fd5e7d3a5cf573` and `a60f71063ef4c3c3043e18f5f1ef4eb85787bc69` are also pushed; renewed live acceptance is withheld.

The telemetry/forecast repair and `.56` candidate identity are deployed and live-proven. Renewed Phase 1 acceptance remains withheld pending `.57` natural proof of the exact-full chatter repair and Solar Surplus hysteresis.

Protected/reference worktrees:

- `C:\Projects\sigenergy_optimizer`: branch `refactor/msc-baseline-overlays`, HEAD `bce8411d5274fe17fb8d883e8e7faf43e9ce8d43`, intentionally dirty. Never modify, reset, or stash it.
- `C:\Projects\sigenergy_optimizer-pv-hotfix`: clean haos53 reference at `19f3c70d24dc086737d5956a1c66cad230287edd`. Never modify it.
- `C:\Projects\sigenergy_optimizer-phase2-transition`: branch `phase2/msc-transition-settlement`, HEAD `c624f0b4392634cf19276186ba46f4b80268627b`, clean when last verified. Phase 2 is paused/frozen.

Always verify branch, HEAD, and cleanliness directly before editing.

## Current phase and gate

Phase 1 was previously declared complete and live-accepted. That is no longer true. Phase 1 is **reopened for audit remediation** because a live Morning Slow low-SoC defect was proven and the broader audit found additional fail-closed and control-authority defects.

Production Remediation Packages 1 through 6A, the telemetry/forecast repair, the exact-full MSC load-serving-discharge repair, Solar Surplus hysteresis, and the exact-full PV/load chatter repair are committed, pushed, and automated-validated. The `.56` live gate proved Morning Dump, Morning Slow activation and charging, static capacity trust, and detailed Solcast validity. Natural `.57` proof is still required for stable exact-full Cheap-FiT behavior through the prior PV/load boundary and for the full Solar Surplus enter/continue/stop/re-enter sequence without ceiling chatter. Phase 1 is not complete; Packages 7 through 9 remain future work after current live acceptance, and Phase 2 remains frozen.

## Live `.56` telemetry/forecast repair acceptance

Repair commit `df90c365fc0413ad0ce048a2796ab8df30ec0c0a` (`Repair telemetry and forecast trust`) is included and live-proven in `.56`. It addresses two independent trust defects exposed by the live Morning Dump failure:

- Dynamic freshness-sensitive snapshots receive one batched, read-only `/api/template` metadata enrichment. A timezone-aware `last_reported` is accepted only when entity ID, exact state string, and timezone-aware `last_updated` match the preceding REST snapshot. Home Assistant request receipt time is never treated as telemetry freshness, and failed or mismatched enrichment falls back conservatively to genuine `last_updated`.
- Rated battery capacity is static capability data: its current snapshot is trusted only when available, finite, positive, and expressed in supported `Wh`, `kWh`, or `MWh`; it no longer expires merely because its value is unchanged.
- Detailed Solcast validity is based on ordered, timezone-aware, finite, non-negative, cadence-continuous periods covering the policy's required same-local-day interval. Morning Dump, Evening Boost, and Battery Full Safeguard fail closed on sparse, gapped, malformed, wrong-day, or insufficient-horizon detail.

The 120-second freshness limit for dynamic live telemetry is unchanged. The unrelated 600-second freshness limit for aggregate forecast observations is unchanged. Manual/Force ownership, Maximum Self Consumption, PV MAX, Demand Window, deliberate Morning Dump battery-export ownership, and unrelated policy behavior are unchanged.

Validation passed: affected tests **121 passed, 127 subtests passed**; independent protections **253 passed, 2 frozen Phase 2 tests deselected, 245 subtests passed**; complete suite **478 passed, 421 subtests passed**, with only the two expected frozen Phase 2 failures; `python -m compileall app` and `git diff --check` passed.

The live compatibility probe used the actual add-on Home Assistant credentials and received HTTP 200 from `/api/template`. The REST `last_reported` remained frozen while the State-object template value advanced, including for unchanged rated capacity. Correlation requirements passed for entity ID, exact state string, and the same `last_updated` instant, confirming that the implementation can safely merge advancing report metadata without manufacturing receipt-time freshness.

The Morning Dump, Morning Slow activation/charging, static-capacity, and detailed-Solcast acceptance items passed live. Package 7 remains blocked pending the two outstanding natural `.57` acceptance items, and Phase 2 remains frozen, including its two expected transition-settlement failures.

## Production Remediation Package 1

The authority/fail-closed package is implemented in `app/models.py` and `app/optimizer.py`, automated-validated, committed at `9538cc84c1235f33d52ebc2ecdf1b6b9c64896b0`, pushed, and included in live `.56`. Its test artifacts are `tests/test_haos49_failure_characterization.py` and `tests/test_phase1_authority_fail_closed_characterization.py`.

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

The Morning control repair is implemented in `app/optimizer.py`, characterized in `tests/test_msc_baseline_overlay_contract.py`, automated-validated, committed at `d3294cb`, pushed, and included in live `.56`.

The proven live defect occurred at approximately 14.2-14.5% SoC with Morning Slow active, MSC observed, PV MAX 25 kW, ESS charging about 2 kW, export closed, and no deliberate battery-export owner. The old low-SoC path required the configured 2 kW slow charge plus the 1 kW `MIN_GRID_TRANSFER_KW`, creating an unintended 3 kW PV-surplus threshold.

Package 2 makes below-minimum-SoC export closure apply only when Morning Slow is inactive. Active Morning Slow no longer depends on `morning_slow_charge_rate_kw + min_grid_transfer_kw`; unrelated uses of `MIN_GRID_TRANSFER_KW` are unchanged. Morning Slow continues to own only the ESS charge rate, remains in Maximum Self Consumption with normal PV MAX, does not own export permission, retains `MSC_SURPLUS_CEILING` intent through independently owned ordinary MSC-surplus permission, and creates no battery-export owner. Package 1 authority and fail-closed protections remain intact.

Characterization results were **4 passed, 33 deselected**: safe 2.9 kW and 3.1 kW surplus cases both received the same 25 kW MSC ceiling, while unobserved Automated ownership and unsafe or unknown flow remained blocked. Focused Morning Slow/MSC protection results were **24 passed, 120 deselected**. Package 1 authority/fail-closed characterization was **11 passed**; focused Remote EMS, Manual, Force, and unavailable-mode protection was **8 passed, 4 deselected**; and Value Gate, positive-FiT, negative-price, MSC-intent, and battery-export protection was **95 passed, 31 deselected**.

The final complete suite result was **295 passed, 2 failed, 191 warnings** from 297 collected tests. The only failures were the frozen Phase 2 tests `test_exact_msc_does_not_reopen_before_export_is_observed_closed` and `test_return_from_discharge_waits_for_observed_close_before_requesting_msc`. `python -m compileall -q app tests` and `git diff --check` passed. No additional regression was found.

## Production Remediation Package 3

The Battery-export safety repair is implemented in `app/optimizer.py`, characterized in `tests/test_msc_baseline_overlay_contract.py`, automated-validated, committed at `91b0075` (`Fix battery export discharge ownership`), pushed, and included in live `.56`.

The confirmed defect allowed raw positive-FiT eligibility to leak into the independent ESS-discharge actuator. That could force the discharge limit to `0.01 kW` when positive-FiT export was enabled but positive-FiT battery sale was disabled, including while the battery served house load, export was an ownerless MSC-surplus ceiling or had failed closed, telemetry was untrusted, or another deliberate battery-export owner had priority.

Package 3 applies the positive-FiT-specific ESS-discharge restriction only when the final live `export_intent` is `BATTERY_EXPORT` and the final `battery_export_owner` is `positive_fit_override`. Ordinary house-load discharge and other deliberate owners retain discharge capability. Simultaneous material battery discharge plus meaningful export and unknown-flow cases still close export; explicit positive-FiT safeguards and the negative-price `0.01 kW` clamp remain intact. Morning Dump, high-price, spike, Evening Boost, Package 2 Morning Slow behavior, Package 1 authority/fail-closed protections, and the frozen Phase 2 logic are unchanged.

Targeted validation passed: Package 3 characterization **8 passed, 7 subtests passed**; existing flow/owner protection **12 passed, 7 subtests passed**; deliberate-owner protection **18 passed, 6 subtests passed**; all four selected actual-import-cost cases; both selected negative-price cases; Package 1 authority/fail-closed **11 passed, 39 subtests passed**; focused Remote EMS/Manual/Force/unavailable-mode **8 passed, 4 deselected, 14 subtests passed**; Package 2 Morning Slow **17 passed, 126 deselected, 8 subtests passed**; and broader MSC/export/Value Gate/positive-FiT/battery-export regression **101 passed, 31 deselected, 71 subtests passed**.

The final complete suite collected 303 tests and finished **301 passed, 2 failed, 191 warnings**. The only failures were the frozen Phase 2 tests `test_exact_msc_does_not_reopen_before_export_is_observed_closed` and `test_return_from_discharge_waits_for_observed_close_before_requesting_msc`. `python -m compileall -q app tests` and `git diff --check` passed. No unexpected regression was found.

## Production Remediation Package 4A

Tariff telemetry trust is implemented in `app/optimizer.py` and `app/state_store.py`, characterized in `tests/test_phase1_tariff_telemetry_trust_characterization.py`, automated-validated, committed at `d3e1d56` (`Harden tariff telemetry trust`), pushed, and included in live `.56`.

NaN and infinite import prices cannot establish tariff-dependent import or charging authority, and non-finite or unavailable FiT cannot establish permissive FiT-dependent export authority. Missing or untrusted import price cannot establish Standby Holdoff; missing or untrusted FiT cannot establish cheap-positive import; and non-finite optimizer import-cost evidence is excluded from trusted persistence and summary use. Finite estimated positive-price policy, actual negative-price Grid Charge, positive-FiT ownership, Package 2 Morning Slow behavior, Package 3 battery-export ownership, and the trusted negative-price `0.01 kW` discharge clamp remain preserved. Trust gates are branch-specific: invalid tariff telemetry does not globally seize or block unrelated controls.

Validation passed for the Package 4A characterization (**23 passed**), existing tariff/import-cost reference set (**14 passed, 4 subtests passed**), Package 1 protections (**23 passed, 61 subtests passed**), Package 2 focused protections (**15 passed, 6 subtests passed, 124 deselected**), Package 3 protections (**13 passed, 10 subtests passed**), and broader tariff regression (**131 passed, 89 subtests passed**). The final complete suite collected 326 tests and finished **324 passed, 2 failed, 191 warnings**. The only failures were the frozen Phase 2 tests `test_exact_msc_does_not_reopen_before_export_is_observed_closed` and `test_return_from_discharge_waits_for_observed_close_before_requesting_msc`. `python -m compileall -q app tests` and `git diff --check` passed. No unexpected regression remained.

Package 4 telemetry trust is automated-complete, pushed, and included in live `.56`: 4A Tariff trust, 4B SoC/battery-energy trust, 4C Live PV/load trust, and 4D Forecast/solar-clock trust. The follow-up telemetry/forecast repair is live-proven in `.56`; renewed Phase 1 acceptance remains withheld for the separate exact-full and Solar Surplus items.

## Production Remediation Package 4B

SoC and battery-energy telemetry trust is implemented in `app/models.py` and `app/optimizer.py`, characterized in `tests/test_phase1_battery_telemetry_trust_characterization.py`, automated-validated, committed at `19a6279` (`Harden battery telemetry trust`), pushed, and included in live `.56`; the follow-up static-capacity repair at `df90c365fc0413ad0ce048a2796ab8df30ec0c0a` is live-proven in `.56`.

`SolarState` now records `battery_soc_trusted`, `battery_capacity_trusted`, and `available_discharge_energy_trusted`, allowing the read path to retain conservative numeric fallbacks without treating them as trusted evidence. SoC is trusted only when freshly observed, finite, and within 0% through 100%; genuine fresh 0% and 100% remain trusted values, while missing, unavailable, unknown, non-finite, out-of-range, and stale observations cannot authorize behavior. Missing or unusable capacity may retain the synthetic 10 kWh arithmetic fallback but cannot make it permissive. Missing available energy remains a conservative numeric 0 kWh, while unavailable, non-finite, or stale available energy cannot become permissive proof.

Trust remains branch-specific rather than a global battery-telemetry veto. Positive-price top-up requires trusted SoC and capacity. Deliberate battery-export owners require the trusted battery facts they depend on; Morning Dump and Evening Boost require trusted SoC, capacity, and available energy. Exact-full PV-only MSC eligibility requires trusted SoC, and refill/energy-dependent branches cannot use synthetic capacity or stale available energy permissively. Ordinary trusted MSC surplus remains independent of unavailable SoC where that branch does not require SoC proof.

Preserved behavior includes genuine fresh 0% semantics, genuine exact-full 100% PV-only MSC behavior, conservative missing-available-energy behavior, ordinary MSC independence from unavailable SoC, Package 1 authority/fail-closed protections, Package 2 Morning Slow, Package 3 battery-export ownership, Package 4A tariff trust, Manual/Force, Demand Window, advisory-only Value Gate, normal PV MAX, Morning Dump's 15% floor, Evening Boost, negative-price behavior, and the rule that ordinary positive FiT does not implicitly create battery export.

Validation passed for the Package 4B characterization (**22 passed, 191 warnings**) and narrow regression set (**90 collected, 88 passed, 2 deselected, 191 warnings**), with the two frozen Phase 2 tests deselected. The complete suite collected 348 tests and finished **346 passed, 2 failed, 191 warnings**. The only failures were the frozen Phase 2 tests `test_exact_msc_does_not_reopen_before_export_is_observed_closed` and `test_return_from_discharge_waits_for_observed_close_before_requesting_msc`. `python -m compileall -q app tests` and `git diff --check` passed. No unexpected functional regression remained.

## Production Remediation Package 4C

Live PV/load telemetry trust is implemented in `app/models.py` and `app/optimizer.py`, characterized in `tests/test_phase1_pv_load_telemetry_trust_characterization.py`, automated-validated, committed at `85cfb1d` (`Harden PV and load telemetry trust`), pushed, and included in live `.56`.

`SolarState` now records `pv_power_trusted`, `load_power_trusted`, `derived_power_flow_coherent`, and `derived_power_flow_span_seconds`. The live read path captures PV, load, battery, and grid observations once per cycle, preserves PV/load trust separately from conservative scalar fallbacks, and retains timestamp-span provenance for derived power-flow coherence. It uses the existing `hvac_solar_data_max_age_seconds` freshness basis, 120 seconds by default, and adds no configuration setting.

Missing, unavailable, unknown, non-finite, stale, or otherwise invalid PV/load readings cannot become permissive evidence. Genuine fresh finite 0 kW PV and 0 kW load remain trusted zeros, and valid fresh positive readings remain trusted. Exact-full PV-only MSC permission requires trusted PV/load where that branch uses those observations, and Solar Surplus Bypass requires trusted PV/load for its surplus calculation. Ordinary MSC and economic branches that do not depend on PV/load proof remain independent; HVAC solar permission continues to fail unavailable or stale inputs appropriately.

Battery-flow evidence retains this hierarchy: fresh/trusted direct battery-power evidence first, coherent derived PV/load/grid evidence second, and otherwise battery-flow safety is not proven. Incoherent or unknown derived flow is not positive proof of battery safety, and the simultaneous battery-discharge plus grid-export fail-closed rule is unchanged.

Package 4C preserves genuine exact-full behavior with trusted evidence, fresh direct battery authority, HVAC solar permission behavior, ordinary MSC independence where PV/load proof is unnecessary, Packages 1 through 4B, Manual/Force, Demand Window, advisory-only Value Gate, normal PV MAX, Morning Dump's 15% floor, Evening Boost, negative-price behavior, and the rule that ordinary positive FiT does not implicitly create battery export.

Validation: Package 4C characterization **15 passed, 191 warnings**; focused regression **151 collected, 149 passed, 2 frozen Phase 2 tests deselected, 191 warnings**; complete suite **363 collected, 361 passed, 2 failed, 191 warnings**. The only failures were the frozen Phase 2 tests `test_exact_msc_does_not_reopen_before_export_is_observed_closed` and `test_return_from_discharge_waits_for_observed_close_before_requesting_msc`. `python -m compileall -q app tests` and `git diff --check` passed. No unexpected functional regression remained.

## Production Remediation Package 4D

Forecast and solar-clock telemetry trust is implemented in `app/models.py` and `app/optimizer.py`, characterized in `tests/test_phase1_forecast_solar_clock_telemetry_trust_characterization.py`, automated-validated, committed at `44c63e80fa72655087504f5c612df10e6b77109f` (`Harden forecast and solar-clock telemetry trust`), pushed, and included in live `.56`. The follow-up repair at `df90c365fc0413ad0ce048a2796ab8df30ec0c0a` is live-proven in `.56`.

Aggregate provenance is retained separately in `forecast_remaining_observation_trusted`, `forecast_today_observation_trusted`, and `forecast_tomorrow_observation_trusted`; detailed-source provenance is retained in `solcast_detailed_source_trusted`; and solar-clock provenance is retained separately in `sun_state_observation_trusted`, `sunrise_observation_trusted`, and `sunset_observation_trusted`. Aggregate forecasts retain the existing 600-second `hvac_solar_forecast_max_age_seconds` basis, while dynamic sun telemetry retains the existing 120-second `hvac_solar_data_max_age_seconds` basis. `next_rising` and `next_setting` retain their existing future-timestamp meaning. No configuration or timing threshold was added.

Fresh finite aggregate forecasts, including genuine `0.0`, can be trusted. Missing, unavailable, malformed, or non-finite values may remain numeric `0.0` for conservative arithmetic but are untrusted; stale finite values may remain visible diagnostically but cannot become trusted permissive proof. Solar Surplus Bypass and solar export override require trusted remaining forecast, Standby Holdoff requires trusted today and remaining forecast, and Evening Boost requires trusted tomorrow and detailed forecast evidence. Stale-high remaining forecast no longer suppresses Forecast Safety Charging as trusted evidence, while missing or invalid forecast retains the conservative charging direction. Forecast uncertainty does not globally veto unrelated owners.

Detailed point dictionaries remain structurally compatible, but current live trust requires ordered, timezone-aware timestamps, finite non-negative `pv_estimate` values, configured-cadence continuity, and coverage of the consuming policy's required same-local-day interval. Morning Dump, Evening Boost, and Battery Full Safeguard reject sparse, gapped, malformed, wrong-day, or insufficient-horizon detail. Detailed validity is not tied to the aggregate forecast's 600-second issue age.

Parsed sun values may remain diagnostically available while untrusted. Morning Dump now requires trusted detailed source, sun state, and sunrise evidence, while preserving deliberate battery-export ownership, its 15% floor, tariff and battery-state trust, and existing priority. Missing, unavailable, unknown, or malformed sunrise cannot construct a permissive dump window. `close_to_sunset` requires trusted sunset evidence, so missing, stale, malformed, or prior sunset evidence cannot relax export forecast guards. Local wall-clock time remains distinct from HA sun telemetry trust, and no sunrise/sunset tolerance was invented. The separate Morning Dump post-window grace policy remains unresolved.

Package 4D preserved genuine fresh zero forecasts, conservative safety charging, negative-price Grid Charge independence, Manual/Force, Demand Window, advisory-only Value Gate, normal PV MAX, Morning Dump's floor, Evening Boost policy apart from telemetry trust, Packages 1 through 4C, the direct-before-derived battery-flow hierarchy, and the rule that ordinary positive FiT does not implicitly create battery export.

Validation: Package 4D characterization **26 passed, 191 warnings**; focused regression **88 passed, 191 warnings**; complete suite **389 collected, 387 passed, 2 failed, 191 warnings**. The only failures were the frozen Phase 2 tests `test_exact_msc_does_not_reopen_before_export_is_observed_closed` and `test_return_from_discharge_waits_for_observed_close_before_requesting_msc`. `python -m compileall -q app tests` and `git diff --check` passed. No unexpected functional regression remained.

## Production Remediation Package 5

Package 5 actuator/fallback reliability and chatter/reopen repair are complete, automated-validated, pushed, and included in live `.56`. The actuator/fallback production/test checkpoint is `4c9c0e2663357a65e8cdf80d7c6d1cf7ea8d0473` (`Harden actuator fallback and settlement handling`); the chatter/reopen production/test checkpoint is `e119f6f` (`Repair Morning Slow MSC ceiling chatter`). Renewed live acceptance is withheld.

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

Package 6A repairs trust handling for the existing grid-export, ESS-charge, and ESS-discharge capability sources. It is complete, automated-validated, pushed at `f95f9ce01a53e66a533edbfe3bd423e4ee3dafd3` (`Repair Package 6A capability trust`), and included in live `.56`. Its documentation checkpoint `f1ade7b0db500cadcdfccce7e2fd5e7d3a5cf573` is also pushed; renewed live acceptance is withheld.

For Automated control, a trusted hardware capability is an upper bound, while a configured ESS baseline is a request and not capability evidence. Charge and discharge remain separate domains; the effective bound is the minimum of current trusted sources in the same domain. If no current trusted source exists, Automated control uses the cached trusted rating for that domain and then `ESS_LIMIT_FALLBACK_KW`. Invalid, unavailable, non-finite, or out-of-range evidence cannot enlarge a capability. Trusted grid-export number-entity maximum metadata bounds the Automated export target.

Manual/Force behavior is temporarily frozen to exact pre-Package-6A capability inputs and fallback behavior through an isolated legacy compatibility path. This covers Manual, Full Import, Full Import + PV, Full Export, Block Flow, and manual ESS charge and discharge overrides. The compatibility path is not long-term capability policy and must not be revisited until all currently planned work is complete.

Validation: Package 6A characterization **21 passed**; Manual/Force protection **13 passed, 5 deselected**; Automated export/ESS actuator protection **115 passed**; and the additional Manual/Force freeze regressions passed. The complete suite collected **440 tests: 438 passed, 2 failed, 191 warnings**. The only failures were the frozen Phase 2 tests `test_exact_msc_does_not_reopen_before_export_is_observed_closed` and `test_return_from_discharge_waits_for_observed_close_before_requesting_msc`. `python -m compileall -q app tests` passed, and `git diff --check` passed apart from the prior line-ending notices.

## Package 6B investigation

The read-only Package 6B investigation is complete; implementation is deferred and no production change was made. Do not invent a speculative grid-import or PV-capability architecture. The known ESS-to-grid-import capability coupling remains parked. Software defaults alone do not establish that normal PV MAX or the high export ceiling is universally 25 kW; the specific current live flap captures an observed 25 kW.

## Exact-full Cheap-FiT MSC status

The earlier exact-full repair at `067d52cc5e231d4c3ffd4be2d8c0d058bfbf19b2` aligned this path with `ordinary_msc_flow_ok`: trusted load-serving battery discharge with no meaningful grid export is compatible with the MSC ceiling, while meaningful simultaneous discharge/export and unknown or untrusted relevant flow remain fail-closed. The separate stale-direct/measured-grid-flow fallback discrepancy remains parked.

Live `.56` exposed an independent eligibility defect. At exact 100% SoC, Cheap-FiT, observed Automated plus exact Maximum Self Consumption, trusted safe flow, no battery-export owner, and zero measured PV surplus, the desired ceiling oscillated `25 -> 0 -> 25 -> 0 kW`. The first differing gate was `live_pv_plausible_for_msc_ceiling`: sub-1 kW PV moved above and below the former requirement that PV meet the productive-solar threshold or remain within `0.1 kW` of instantaneous load.

Commit `9e5517ea85dea286608d564cbe2cdeaa18a2e03e` removes only that unstable adequacy test. The exact-full path still requires trusted finite PV/load telemetry and positive live PV strictly above `0.05 kW`. Observed Automated and exact MSC ownership, exact-full target, `ordinary_msc_flow_ok`, forecast/standby/demand protections, no explicit battery-export owner, and all other independent safety conditions remain mandatory. The 25 kW value remains an MSC export ceiling, creates no `BATTERY_EXPORT` owner, and never selects a discharge EMS mode. Diagnostics now expose `live_pv_plausible_for_msc_ceiling` and `pv_surplus_common_conditions`.

Validation passed: exact-full characterization **6 passed**; MSC baseline/overlay plus chatter protection **52 passed, 2 frozen Phase 2 tests deselected**; final suite **482 collected, 480 passed**, with only the two frozen Phase 2 tests failing as expected. Compileall and `git diff --check` passed with no unexpected finding. Natural `.57` proof through the prior PV/load-deficit boundary remains required.

## Solar Surplus PV-margin hysteresis repair

Live haos54 observation showed the Solar Surplus eligibility gate toggle `true -> false -> true` as real-time PV surplus moved `0.536 -> 0.439 -> 0.575 kW` around the configured 0.5 kW margin. At the observed 6c FiT below the ordinary 10c threshold, export remained closed, intent remained `EXPORT_BLOCKED`, EMS remained Maximum Self Consumption, PV MAX remained normal, and no battery-export owner appeared. Synthetic 12c testing proved that the same gate sequence previously propagated into `25 -> 0 -> 25 kW` and `MSC_SURPLUS_CEILING -> EXPORT_BLOCKED -> MSC_SURPLUS_CEILING`.

The repair included in live `.56` keeps entry strictly above `SOLAR_SURPLUS_MIN_PV_MARGIN`, unchanged at 0.5 kW, and adds `SOLAR_SURPLUS_STOP_PV_MARGIN`, default 0.2 kW, for continuation. The new value is normalized to a finite, non-negative value no greater than the entry margin. Only an immediately previous, genuinely active Solar Surplus high ceiling under observed Automated ownership may use the lower margin. At or below 0.2 kW the policy stops, and re-entry again requires more than 0.5 kW. Existing 2.0/1.25 forecast hysteresis is unchanged; no timer, smoothing, battery-export ownership, discharge EMS mode, or PV MAX change is introduced.

Regression coverage proves strict 0.5 kW entry, strict 0.2 kW continuation, re-entry protection, forecast continuation at 60.0 kWh for a 40.3 kWh battery while inactive entry remains blocked, rejection of unrelated prior MSC ownership, stable `25 / 25 / 25 kW` and `MSC_SURPLUS_CEILING` at synthetic 12c FiT, and stable closed outputs at observed-style 6c FiT. Focused API/config validation passed **11 tests**; directly affected Solar Surplus modules passed **104 tests**; independent MSC and exact-full protection passed **45 tests with the two frozen Phase 2 tests deselected**; and the complete suite collected **459 tests: 457 passed, 2 failed**. The only failures were the frozen Phase 2 tests `test_exact_msc_does_not_reopen_before_export_is_observed_closed` and `test_return_from_discharge_waits_for_observed_close_before_requesting_msc`. `python -m compileall` passed, and `git diff --check` passed apart from the repository's existing line-ending conversion notices.

The Solar Surplus repair is committed and pushed at `7ded75f9155d7002150a7308f03eb9510f5beb39` and included in live `.56`. Natural proof of entry above `0.5 kW`, continuation above `0.2 kW`, stop at or below `0.2 kW`, re-entry above `0.5 kW`, and no ceiling chatter remains required after `.57` installation.

## Parked investigation: Morning Slow forecast feasibility

Live observation found Morning Slow active with actual operator settings: enabled `True`, until `11:00`, charge rate `2 kW`, minimum feed-in price `0.01 $/kWh`, base-load allowance `2 kW`, and sunset cutoff `1 hour`. These are live operator settings, not software defaults.

At the time, observed values were approximately 15.9% SoC, 6.4 kWh available battery energy, 40 kWh battery capacity, 57.8 kWh remaining solar forecast, 3.5 kW PV, 0.9 kW load, and 2.57 kW battery charging. The implementation requires remaining forecast to cover battery refill need plus assumed load until the slow-charge solar cutoff, multiplied by the configured forecast-safety factor. The displayed values appear difficult to reconcile with Morning Slow eligibility, but this is not yet a confirmed production bug and does not justify changing operator settings or software defaults.

The later bounded investigation must capture and compare the exact trusted remaining forecast, battery capacity, available discharge energy, calculated refill need, calculated slow-charge end timestamp, hours left, configured base load, calculated load need, forecast-safety charging multiplier, final `required_kwh`, and final Morning Slow eligibility result. It must determine whether the observation reflects expected operator tuning, stale or different live inputs, a calculation/provenance mismatch, or a real implementation defect. No diagnostics or production change is approved yet.

## Remaining audit findings requiring remediation

High/proven static findings unless noted otherwise:

- export-spike minimum SoC does not enforce a real spike floor;
- authoritative grid-import and PV hardware capability remain deferred after the read-only Package 6B investigation; the known ESS-to-grid-import coupling is parked and no speculative architecture is approved;
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

- the specific current live flap captures observed normal PV MAX and high export ceiling at 25 kW; do not infer a universal operator truth from software defaults;
- `MIN_SOC_FLOOR`: 20%; `MIN_EXPORT_TARGET_SOC`: 90%;
- Morning Slow: enabled `True`, 2 kW charge rate, until 11:00, minimum FiT `0.01`, base-load allowance 2 kW, sunset cutoff 1 hour;
- Morning Dump: enabled, 15% floor;
- Evening Boost: enabled, 35% floor, safety multiplier 1.1, minimum tomorrow forecast 100 kWh;
- `MIN_GRID_TRANSFER_KW`: 1 kW;
- Forecast Safety Charging: 1.35; Forecast Safety Export: 1.1;
- Solar Surplus Bypass live settings: enabled at 2.0 / 1.25 / 0.5; live `.56` includes the separate 0.2 kW continuation default without changing those operator values;
- spike minimum SoC: 60%, although current implementation does not enforce it;
- cheap-positive threshold: `0.015 $/kWh`; daytime top-up maximum SoC: 50%; target battery charge: 2 kW;
- Demand Window remains the higher-priority import block; Value Gate remains advisory-only.

## Frozen Phase 2 contract

Future Phase 2 returns from deliberate battery export by closing export, later observing it closed, requesting MSC, later observing exact MSC, and only then reopening the normal 25 kW export ceiling. Entry into deliberate battery export must settle the export target before selecting discharge EMS. Service-call success is not observed inverter state.

Protect the two existing expected Phase 2 failures:

- `test_return_from_discharge_waits_for_observed_close_before_requesting_msc`
- `test_exact_msc_does_not_reopen_before_export_is_observed_closed`

## Exact next action

Review the uncommitted `2.3.46-haos57` identity/documentation checkpoint and decide whether to commit it. Push, tag, build, publish, installation, restart, and natural live acceptance remain separate approval boundaries. After `.57` is published and installed under separate approvals, verify stable exact-full Cheap-FiT behavior through the prior PV/load-deficit boundary and the complete Solar Surplus hysteresis sequence before Phase 1 can advance.
