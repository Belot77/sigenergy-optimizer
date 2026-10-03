# Current State

Last consolidated: 2026-10-04

**CURRENT TRUTH ONLY:** durable control semantics live in `CONTROL_CONTRACT.md`; sequencing lives in `ROADMAP.md`.

## Release and live state

- Current live release: `2.3.52-haos63`, installed and running. Lightweight tag `v2.3.52-haos63` points to approved source commit `41df404570db6d4a026cdb6162dcab233876b6b6`.
- `origin/main` was fast-forwarded to that commit after publication because Home Assistant discovers the add-on manifest from main. `origin/fix/phase1-audit-remediation` points to the same commit; main's manifest exposes `version: "2.3.52-haos63"`. No new build or release was needed for main promotion.
- The published multi-architecture image is `ghcr.io/belot77/sigenergy-optimizer:2.3.52-haos63` (`linux/amd64`, `linux/arm64`), OCI index digest `sha256:7a7d5ed07d71b899ad0d11bfc292be6840144ae0276d047be7aa8dae905f99a0`. Its version and source-revision metadata match the release. GitHub Actions build/publish run `37086123886` succeeded before main promotion.
- Documented known-good rollback: `2.3.46-haos57`, commit `7144fd3d52069e3e8ef1e4df9bc8943bdd65dbe7`.
- **Solar dynamic ESS charge-ceiling live acceptance is still pending.** Available evidence does not yet prove dynamic Solar ownership and safe relinquishment.
- Phase 1 remains open. Phase 2 remains frozen until controlled `.63` Solar acceptance and separate Evening Boost remediation and live acceptance are complete.

## Diagnostics checkpoint

- Worktree: `C:\Projects\sigenergy_optimizer-phase1-remediation`; branch: `fix/phase1-audit-remediation`; local HEAD: `ff5c96d77d1082b8327faee5a3000f2685240d69`, committed as `diagnostics: add persistent 24-hour decision trace`.
- This is diagnostics-only. It has **not** been pushed, versioned, tagged, built, published, released, installed or deployed. The live system remains `.63` / `2.3.52-haos63`.
- The existing approximately 1000-cycle in-memory trace remains unchanged. A rolling 24-hour JSONL archive flushes every 15 minutes, with diagnostics I/O isolated from control and the default executor. Persistent possible-gap reporting is conservative; clock uncertainty safely pauses persistent writes and pruning.
- Downloads allow at most 4 active requests, with a 2-minute lifetime and at most 25 segments / 256 MiB per download. An abrupt crash can still lose the unflushed interval; there is no final shutdown flush. Diagnostics failure cannot block optimizer/control startup.
- Validation: diagnostics/UI suites **55 passed**; existing API/lifecycle **82 passed**; selected control protections **237 passed**; full suite **804 passed**, **723 subtests passed**. Compileall and `git diff --check` passed. Final independent Astra review: **SAFE TO COMMIT AS DIAGNOSTICS-ONLY**.
- The only expected failures remain the frozen Phase 2 tests `test_exact_msc_does_not_reopen_before_export_is_observed_closed` and `test_return_from_discharge_waits_for_observed_close_before_requesting_msc` in `tests/test_msc_baseline_overlay_contract.py`.

## Live Dynamic Solar behavior

- The `.63` change allows Solar to own a bounded lower ESS charge ceiling only after final arbitration selects `solar_surplus_policy_active` and stricter detailed charge evidence is trusted. It allocates protected fill need to the current interval only when future detailed charge opportunity cannot cover it, rounds positive requests upward within the normal safe/trusted request, and immediately relinquishes the restriction when evidence fails. Grid-import charging precedence and other higher-priority owners remain intact. Solar stays MSC/PV-only with normal PV MAX and high export permission.

## Controlled Solar live acceptance still required

Required next live evidence:

1. **Solar ownership after Morning Slow ends:** `solar_surplus_policy_active=true`, `solar_charge_ceiling_owned=true`, `solar_charge_ceiling_evidence_trusted=true`, and `ess_charge_limit_owner=solar_surplus`; a dynamic requested ceiling below the normal approximately 21 kW when appropriate. Confirm MSC, PV MAX 25 kW, export permission 25 kW, `battery_export_owner=none`, and actual PV/load/grid/battery flows showing PV surplus export.
2. **Near-full / Solar exit:** capture around 95-99% SoC or when Solar relinquishes. Prove no stale low ESS charge ceiling or Solar owner remains, and distinguish inverter taper from an optimizer-owned ceiling. This supplements the ownership capture.
3. **Conditional blocker trace:** capture only if Solar unexpectedly does not activate under strong suitable conditions.

Observe the 27 September Solar aggregate-budget threshold-switching follow-up without assuming `.63` fixes it. Solar acceptance does not automatically start Phase 2.

## Evening Boost findings parked until after Solar acceptance

- **Confirmed transition-stability defect:** `_battery_soc_required_to_sunrise()` projects instantaneous household load across the remaining overnight horizon. The latest `.63` trace again showed implausibly high required SoC/protected reserve above 100% under transiently high household load, preventing Evening Boost. Earlier `.62` evidence showed repeated transitions between `evening_export_boost` / Command Discharging and MSC while SoC and FiT were effectively stable and load changed sharply. No remediation or live acceptance is claimed.
- **Newly confirmed import-cost trust interaction:** `.63` records optimizer import/top-up chunks with price trust. A significant daily import chunk of at least `0.01 kWh` with untrusted, missing, or non-finite price leaves `import_cost_floor_trusted = false` and `import_cost_floor_unknown = true` for the day; later trusted import-price observations do not repair that state. Live `.63` evidence showed `today_import_topup_kwh` about `18.412 kWh`, `today_highest_actual_import_price` about `$0.2037716/kWh`, and that untrusted/unknown floor state. This indicates at least one significant earlier optimizer-controlled import/top-up event lacked trusted price provenance, even though other trusted-price imports existed. When Evening Boost qualifies as explicit `BATTERY_EXPORT` owner, the independent Actual Import Cost Guard can hard-veto it because of this state.
- Export Value Gate remains advisory-only; the independent Actual Import Cost Guard remains enforcing in current `.63` behavior. No Evening Boost import-cost solution or redesign has been selected. Investigate the persisted import/top-up event and provenance, and decide the intended guard interaction during the separate bounded Evening Boost review. Preserve reserve, forecast, ownership, import-cost, and settlement protections.

## Protected behavior and operator configuration

- Manual/Force ownership, Demand Window import ownership, observed Automated ownership, fail-closed telemetry and settlement, battery floor, and safe fallback remain protected. The Solar change does not introduce a Solar timer or battery-export authority.
- Earlier `.61` live evidence established the near-full Solar exception for genuinely untrusted available-discharge-energy telemetry at about 93.9-96.7% SoC, a clean Morning Slow to Solar transition, and the 25 kW ceiling acting as PV export permission rather than commanded battery discharge.
- Earlier `.62` Morning Slow evidence showed MSC, safe load-serving battery behavior, and clean closure at its end. Poor-solar evidence showed Morning Slow remained inactive when timed refill was infeasible even at normal capability.
- **Morning Dump live evidence is accepted for the observed case:** deliberate battery export worked, approximately 15 kW actual export was observed with no grid import, PV MAX remained 25 kW, and the dump reached the approximately 15% floor before relinquishing. Transition safety closed/reopened export appropriately. No further Morning Dump evidence is required now.
- Recorded operator Morning Slow tuning: enabled, 2 kW, until 11:00, minimum FiT `$0.01/kWh`, base-load allowance 2 kW, sunset cutoff 1 hour.
- `grid_connection_export_limit_kw=15` and `morning_slow_physical_export_headroom_kw=0.5` remain parked/unconfigured and are not defaults. Before configuring them, decide whether 15 kW is merely the site-export threshold releasing Morning Slow's artificial charge cap or a hard network/export limit. Current code implements only the former.

## Sequence and next action

After this documentation checkpoint, decide separately whether to commit the two docs files, push the diagnostics commit/branch, or prepare a new diagnostics release (`.64` candidate). Preserve `.63` as the current live release until explicit release/install approval.

Obtain the required `.63` Solar evidence above. Evening Boost reserve-estimator instability and import-cost trust poisoning remain parked; no Evening Boost remediation has begun. The two Phase 2 transition-settlement failures remain frozen and expected. Solar acceptance does not automatically start Phase 2; subsequent work requires a separate decision under the roadmap.

Keep the parked settings unconfigured and all protected ownership/fail-closed behavior intact. This checkpoint authorizes no commit, push, release, install, deployment or control change.
