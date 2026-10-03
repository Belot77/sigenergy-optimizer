# SigEnergy Optimizer AI Handover

Last consolidated: 2026-10-03

Read root and project `AGENTS.md`, then `CURRENT_STATE.md`, `CONTROL_CONTRACT.md`, `DECISIONS.md`, and `ROADMAP.md`. Verify worktree, branch, HEAD, tracking, and status before editing.

## Current release and identities

- Worktree: `C:\Projects\sigenergy_optimizer-phase1-remediation`; branch: `fix/phase1-audit-remediation`.
- Approved `.63` source commit and expected branch HEAD: `41df404570db6d4a026cdb6162dcab233876b6b6`. Tag `v2.3.52-haos63`, `origin/main`, and `origin/fix/phase1-audit-remediation` point to it. Main's add-on manifest exposes `version: "2.3.52-haos63"` for Home Assistant discovery.
- `.63` was built/published successfully before main was fast-forwarded; no new build/release was required for that promotion. Image: `ghcr.io/belot77/sigenergy-optimizer:2.3.52-haos63`, platforms `linux/amd64` and `linux/arm64`, OCI index digest `sha256:7a7d5ed07d71b899ad0d11bfc292be6840144ae0276d047be7aa8dae905f99a0`; OCI version/revision match the tag and approved commit. Build/publish run: `37086123886`.
- `.63` is installed and running live, but **dynamic Solar live acceptance is pending**. Known-good rollback: `2.3.46-haos57`, commit `7144fd3d52069e3e8ef1e4df9bc8943bdd65dbe7`. `.62` is historical, not the current live release.

## Code gate and control boundaries

- Pre-release full suite: 755 collected, 753 passed, 2 known frozen Phase 2 failures, 717 subtests passed. Dynamic Solar characterization including grid-import charging precedence: 14 tests and 14 subtests passed. Compileall and diff check passed; independent review found no remaining production/safety blocker. None of this establishes live Solar acceptance.
- Solar can own a bounded lower ESS charge ceiling only after final Solar arbitration and stricter trusted detailed evidence. Failed evidence immediately releases that restriction; grid-import charging precedence and higher-priority owners remain. Solar remains MSC/PV-only, with normal PV MAX and high export permission, and no `BATTERY_EXPORT` authority.
- Protect Manual/Force ownership, Demand Window import ownership, observed Automated ownership, fail-closed telemetry and actuator settlement, battery floor, reserve/forecast checks, and the independent Actual Import Cost Guard. Export Value Gate is advisory-only; Actual Import Cost Guard is enforcing in `.63`. Do not change this contract in the checkpoint.
- The frozen Phase 2 tests in `tests/test_msc_baseline_overlay_contract.py` are `test_exact_msc_does_not_reopen_before_export_is_observed_closed` and `test_return_from_discharge_waits_for_observed_close_before_requesting_msc`.

## Live evidence and pending Solar acceptance

- The latest confirmed `.63` trace was evening/night with PV effectively zero. Its representative late state was ordinary MSC with PV MAX 25 kW, export permission 25 kW, normal ESS charge limit 21 kW, no Solar ownership, and no battery-export owner. It cannot prove the dynamic Solar ceiling.
- Capture daylight while `solar_surplus_policy_active = true`, `solar_charge_ceiling_owned = true`, `ess_charge_limit_owner = solar_surplus`, and `solar_charge_ceiling_evidence_trusted = true`. Confirm the optimizer's calculated charge request, possibly below normal ~21 kW, while EMS remains MSC, PV MAX and export permission remain 25 kW, and `battery_export_owner = none`. With usable surplus, check actual battery charging and grid export split and absence of rapid ownership/limit chatter. Prefer evidence before near-full taper; a 95-99% SoC trace alone cannot establish optimizer ownership of a lower ceiling. Observe the 27 September aggregate-budget threshold-switching follow-up without claiming `.63` fixes it.
- Historical `.61` evidence proved the near-full Solar exception for genuinely untrusted discharge-energy telemetry and a clean Morning Slow to Solar transition. Historical `.62` evidence supported Morning Slow behavior; the operator accepted Morning Dump without another dedicated trace as a release blocker.

## Evening Boost: confirmed findings, no approved fix

- Transition stability remains the next narrow Phase 1 remediation after Solar acceptance. `_battery_soc_required_to_sunrise()` projects instantaneous household load across the overnight horizon. The latest `.63` trace again showed required SoC/protected reserve above 100% under transiently high load, blocking Boost; earlier `.62` evidence showed repeated `evening_export_boost` / Command Discharging to MSC transitions with stable SoC/FiT and changing short-term load.
- `.63` records optimizer import/top-up chunks with price trust. Any significant daily chunk `>= 0.01 kWh` with missing, non-finite, or untrusted price leaves `import_cost_floor_trusted = false` / `import_cost_floor_unknown = true` for the day; later trusted import prices do not restore trust. Live `.63` evidence showed `today_import_topup_kwh` about `18.412 kWh`, `today_highest_actual_import_price` about `$0.2037716/kWh`, and that untrusted floor state. At least one earlier significant optimizer-controlled import/top-up event lacked trusted price provenance. When Boost qualifies as explicit `BATTERY_EXPORT` owner, the independent Actual Import Cost Guard can hard-veto it.
- During the bounded Evening Boost review, inspect the persisted import/top-up event/provenance and decide the intended guard interaction. No import-cost solution has been selected; preserve the enforcing guard and other protections until reviewed.

## Parked and exact next action

- Keep discussed physical-relief values `15.0 / 0.5 kW` unconfigured; the current mechanism is a Morning Slow relief threshold, not a hard export cap. Phase 2 remains frozen. Climate Manager stays later in roadmap order.
- Next: controlled daylight `.63` Solar acceptance; then narrow Evening Boost transition-stability characterization/remediation plus import-cost trust investigation; then Evening Boost live acceptance; only then Phase 2. Do not claim Phase 1 complete. This documentation checkpoint authorizes no live control, add-on change, commit, publication, or Evening Boost implementation.
