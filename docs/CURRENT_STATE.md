# Current State

Last consolidated: 2026-10-03

**CURRENT TRUTH ONLY:** durable control semantics live in `CONTROL_CONTRACT.md`; sequencing lives in `ROADMAP.md`.

## Release and live state

- Current live release: `2.3.52-haos63`, installed and running. Lightweight tag `v2.3.52-haos63` points to approved source commit `41df404570db6d4a026cdb6162dcab233876b6b6`.
- `origin/main` was fast-forwarded to that commit after publication because Home Assistant discovers the add-on manifest from main. `origin/fix/phase1-audit-remediation` points to the same commit; main's manifest exposes `version: "2.3.52-haos63"`. No new build or release was needed for main promotion.
- The published multi-architecture image is `ghcr.io/belot77/sigenergy-optimizer:2.3.52-haos63` (`linux/amd64`, `linux/arm64`), OCI index digest `sha256:7a7d5ed07d71b899ad0d11bfc292be6840144ae0276d047be7aa8dae905f99a0`. Its version and source-revision metadata match the release. GitHub Actions build/publish run `37086123886` succeeded before main promotion.
- Documented known-good rollback: `2.3.46-haos57`, commit `7144fd3d52069e3e8ef1e4df9bc8943bdd65dbe7`.
- **Solar live acceptance has not passed.** The latest confirmed `.63` trace was taken in the evening/night with PV effectively zero. It cannot demonstrate dynamic Solar ESS charge-ceiling ownership. Its representative late state showed ordinary MSC operation: PV MAX 25 kW, export permission 25 kW, normal ESS charge limit 21 kW, no Solar ownership, and no battery-export owner.
- Phase 1 remains open. Phase 2 remains frozen until controlled `.63` Solar acceptance and separate Evening Boost remediation and live acceptance are complete.

## Dynamic Solar checkpoint and validation

- Worktree: `C:\Projects\sigenergy_optimizer-phase1-remediation`; branch: `fix/phase1-audit-remediation`; approved `.63` source HEAD: `41df404570db6d4a026cdb6162dcab233876b6b6`.
- The `.63` change allows Solar to own a bounded lower ESS charge ceiling only after final arbitration selects `solar_surplus_policy_active` and stricter detailed charge evidence is trusted. It allocates protected fill need to the current interval only when future detailed charge opportunity cannot cover it, rounds positive requests upward within the normal safe/trusted request, and immediately relinquishes the restriction when evidence fails. Grid-import charging precedence and other higher-priority owners remain intact. Solar stays MSC/PV-only with normal PV MAX and high export permission.
- Pre-release code validation collected 755 tests: 753 passed, 2 known frozen Phase 2 failures, and 717 subtests passed. Dynamic Solar characterization, including grid-import charging precedence, passed 14 tests and 14 subtests. Compileall and `git diff --check` passed; independent review found no remaining production/safety blocker. This is code validation, not Solar live acceptance.
- The two frozen Phase 2 tests are `test_exact_msc_does_not_reopen_before_export_is_observed_closed` and `test_return_from_discharge_waits_for_observed_close_before_requesting_msc` in `tests/test_msc_baseline_overlay_contract.py`.

## Controlled Solar live acceptance still required

Capture daylight evidence when Solar Surplus genuinely owns policy, preferably before near-full battery taper:

- `solar_surplus_policy_active = true`, `solar_charge_ceiling_owned = true`, `ess_charge_limit_owner = solar_surplus`, and `solar_charge_ceiling_evidence_trusted = true`.
- The requested Solar ESS charge ceiling reflects the dynamic calculation and may be below the normal approximately 21 kW limit. A later 95-99% SoC capture is useful but cannot substitute for proof that the optimizer, rather than natural inverter taper, owned the lower ceiling.
- EMS remains Maximum Self Consumption; PV MAX and normal high export permission remain 25 kW; `battery_export_owner` remains `none`.
- When usable surplus exists, actual PV splits appropriately between battery charging and grid export, without rapid ownership or limit chatter. Observe the 27 September Solar aggregate-budget threshold-switching follow-up; `.63` is not claimed to fix it.

## Evening Boost findings parked until after Solar acceptance

- **Confirmed transition-stability defect:** `_battery_soc_required_to_sunrise()` projects instantaneous household load across the remaining overnight horizon. The latest `.63` trace again showed implausibly high required SoC/protected reserve above 100% under transiently high household load, preventing Evening Boost. Earlier `.62` evidence showed repeated transitions between `evening_export_boost` / Command Discharging and MSC while SoC and FiT were effectively stable and load changed sharply. No remediation or live acceptance is claimed.
- **Newly confirmed import-cost trust interaction:** `.63` records optimizer import/top-up chunks with price trust. A significant daily import chunk of at least `0.01 kWh` with untrusted, missing, or non-finite price leaves `import_cost_floor_trusted = false` and `import_cost_floor_unknown = true` for the day; later trusted import-price observations do not repair that state. Live `.63` evidence showed `today_import_topup_kwh` about `18.412 kWh`, `today_highest_actual_import_price` about `$0.2037716/kWh`, and that untrusted/unknown floor state. This indicates at least one significant earlier optimizer-controlled import/top-up event lacked trusted price provenance, even though other trusted-price imports existed. When Evening Boost qualifies as explicit `BATTERY_EXPORT` owner, the independent Actual Import Cost Guard can hard-veto it because of this state.
- Export Value Gate remains advisory-only; the independent Actual Import Cost Guard remains enforcing in current `.63` behavior. No Evening Boost import-cost solution or redesign has been selected. Investigate the persisted import/top-up event and provenance, and decide the intended guard interaction during the separate bounded Evening Boost review. Preserve reserve, forecast, ownership, import-cost, and settlement protections.

## Protected behavior and operator configuration

- Manual/Force ownership, Demand Window import ownership, observed Automated ownership, fail-closed telemetry and settlement, battery floor, and safe fallback remain protected. The Solar change does not introduce a Solar timer or battery-export authority.
- Earlier `.61` live evidence established the near-full Solar exception for genuinely untrusted available-discharge-energy telemetry at about 93.9-96.7% SoC, a clean Morning Slow to Solar transition, and the 25 kW ceiling acting as PV export permission rather than commanded battery discharge.
- Earlier `.62` Morning Slow evidence showed MSC, safe load-serving battery behavior, and clean closure at its end. Poor-solar evidence showed Morning Slow remained inactive when timed refill was infeasible even at normal capability. The operator accepted Morning Dump without another dedicated trace as a release blocker; its floor remains 15%.
- Recorded operator Morning Slow tuning: enabled, 2 kW, until 11:00, minimum FiT `$0.01/kWh`, base-load allowance 2 kW, sunset cutoff 1 hour.
- Discussed physical-relief values `15.0 / 0.5 kW` remain unconfigured and are not defaults. Before configuring them, decide whether 15 kW is merely the site-export threshold releasing Morning Slow's artificial charge cap or a hard network/export limit. Current code implements only the former.

## Sequence and next action

1. Obtain controlled daylight `.63` Solar live acceptance with dynamic ceiling ownership and actual PV/battery/grid behavior; observe threshold switching without assuming a fix.
2. Characterize and narrowly remediate Evening Boost transition stability. In the same bounded review, investigate the import/top-up event and price provenance behind the daily import-cost trust poisoning and decide the intended guard interaction.
3. Obtain Evening Boost live acceptance. Only then begin Phase 2 transition safety; the ownership audit, architecture/refactor cleanup, GUI/UX work, Climate Manager, and later diagnostics/replay/load modelling follow in roadmap order.

Keep `15.0 / 0.5 kW` unconfigured and all protected ownership/fail-closed behavior intact. This documentation checkpoint does not authorize a live action or implementation change.
