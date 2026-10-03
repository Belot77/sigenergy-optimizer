# SigEnergy Optimizer AI Handover

Last consolidated: 2026-10-04

Read root and project `AGENTS.md`, then `CURRENT_STATE.md`, `CONTROL_CONTRACT.md`, `DECISIONS.md`, and `ROADMAP.md`. Verify worktree, branch, HEAD, tracking, and status before editing.

## Current release and identities

- Worktree: `C:\Projects\sigenergy_optimizer-phase1-remediation`; branch: `fix/phase1-audit-remediation`.
- Local branch HEAD remains `99d8ed640d16a699674e061355dbcd9e773e1356`, `release: 2.3.53-haos64`. The `.65` / `2.3.54-haos65` diagnostics-only hotfix candidate is an uncommitted delta from this live source.
- Operator-confirmed live release: `.64` / `2.3.53-haos64`, installed and running, source commit `99d8ed640d16a699674e061355dbcd9e773e1356`. **Dynamic Solar live acceptance remains pending.**
- Known rollback: `.63` / `2.3.52-haos63`, source commit `41df404570db6d4a026cdb6162dcab233876b6b6`.
- Candidate preparation performed no commit, push, main promotion, tag, build, publication, installation or restart. `.64` remains live; `.65` is unreleased.

## Completed diagnostics checkpoint and control boundaries

- The existing approximately 1000-cycle in-memory Decision Trace remains unchanged. Persistent rolling 24-hour JSONL diagnostics flush every 15 minutes; diagnostics I/O is isolated from control and the default executor. Persistent possible-gap reporting remains conservative. Clock uncertainty safely pauses persistent writes/pruning; diagnostics failure cannot block optimizer/control startup.
- **24 Hour Trace is confirmed live and producing data on `.64`.** Its first flush produced approximately 3.5 MB after approximately 15 minutes. The 256 MiB download ceiling is insufficient for an expected full 24-hour archive. The `.65` candidate changes only the download ceiling from 256 MiB to 512 MiB, with no control-behaviour change.
- Downloads remain bounded to 4 active requests, a 2-minute lifetime, and 25 segments. Live `.64` allows 256 MiB; `.65` allows 512 MiB. All other diagnostics resource bounds, chunk size, retention, persistence cadence, clock handling, authentication, streaming and pin cleanup remain unchanged. Abrupt crashes can lose the unflushed interval; there is no final shutdown flush.
- `.65` validation before the mechanical version bump: focused download/UI **27 passed**, **18 subtests passed**; diagnostics/store/lifecycle/API/UI **100 passed**, **61 subtests passed**; selected control protections **543 passed**, **540 subtests passed**, with the two frozen tests deselected. Full suite run once: **806 passed**, **725 subtests passed**, only the **2 frozen Phase 2 failures** below. No unexpected failures. This does not establish Solar live acceptance.
- Solar can own a bounded lower ESS charge ceiling only after final Solar arbitration and stricter trusted detailed evidence. Failed evidence immediately releases that restriction; grid-import charging precedence and higher-priority owners remain. Solar remains MSC/PV-only, with normal PV MAX and high export permission, and no `BATTERY_EXPORT` authority.
- Protect Manual/Force ownership, Demand Window import ownership, observed Automated ownership, fail-closed telemetry and actuator settlement, battery floor, reserve/forecast checks, and the independent Actual Import Cost Guard. Export Value Gate remains advisory-only; Actual Import Cost Guard remains enforcing in live `.64` and the `.65` candidate. Do not change this contract in the checkpoint.
- The only expected failures remain the frozen Phase 2 transition-settlement tests in `tests/test_msc_baseline_overlay_contract.py`: `test_exact_msc_does_not_reopen_before_export_is_observed_closed` and `test_return_from_discharge_waits_for_observed_close_before_requesting_msc`.

## Live evidence and pending Solar acceptance

- **Morning Dump is accepted for the observed case:** deliberate battery export worked; approximately 15 kW actual export with no grid import; PV MAX stayed 25 kW; dump reached the approximately 15% floor, then relinquished and transition safety closed/reopened export appropriately. Do not require further Morning Dump evidence now.
- **Solar dynamic ESS charge-ceiling live acceptance is still pending on live `.64`.** Continue the required captures after `.65` installation:

1. Solar ownership after Morning Slow ends: `solar_surplus_policy_active=true`, `solar_charge_ceiling_owned=true`, `solar_charge_ceiling_evidence_trusted=true`, `ess_charge_limit_owner=solar_surplus`, and a dynamic ceiling below normal (~21 kW) when appropriate. Confirm MSC, PV MAX 25 kW, export permission 25 kW, `battery_export_owner=none`, and actual PV/load/grid/battery flows showing PV surplus export.
2. Near-full / Solar-exit trace around 95-99% SoC or at relinquishment: prove no stale low ESS charge ceiling/owner remains and distinguish inverter taper from the optimizer ceiling.
3. A blocker trace only if Solar unexpectedly does not activate under strong suitable conditions.

Observe the 27 September aggregate-budget threshold-switching follow-up without claiming `.63` fixes it. Historical `.61` evidence supports the near-full untrusted-discharge-energy exception and Morning Slow to Solar transition; `.62` supports Morning Slow behavior.

## Evening Boost: confirmed findings, no approved fix

- Evening Boost reserve-estimator instability remains parked; no remediation has begun. `_battery_soc_required_to_sunrise()` projects instantaneous household load across the overnight horizon. `.63` evidence showed required SoC/protected reserve above 100% under transiently high load, blocking Boost; `.62` evidence showed repeated `evening_export_boost` / Command Discharging to MSC transitions with stable SoC/FiT and changing short-term load.
- `.63` records optimizer import/top-up chunks with price trust. Any significant daily chunk `>= 0.01 kWh` with missing, non-finite, or untrusted price leaves `import_cost_floor_trusted = false` / `import_cost_floor_unknown = true` for the day; later trusted import prices do not restore trust. Live `.63` evidence showed `today_import_topup_kwh` about `18.412 kWh`, `today_highest_actual_import_price` about `$0.2037716/kWh`, and that untrusted floor state. At least one earlier significant optimizer-controlled import/top-up event lacked trusted price provenance. When Boost qualifies as explicit `BATTERY_EXPORT` owner, the independent Actual Import Cost Guard can hard-veto it.
- Evening Boost import-cost trust poisoning also remains parked. A separately approved bounded review should inspect persisted import/top-up event provenance and decide the intended guard interaction. No remediation or import-cost solution has been selected; preserve the enforcing guard and other protections.

## Parked and exact next action

- Keep `grid_connection_export_limit_kw=15` and `morning_slow_physical_export_headroom_kw=0.5` parked/unconfigured; the current mechanism is a Morning Slow relief threshold, not a hard export cap. Phase 2 and its two expected failures remain frozen. Solar acceptance does not automatically start Phase 2. Climate Manager stays later in roadmap order; Phase 1 is not complete.
- Exact next action: release/install `.65` / `2.3.54-haos65`, then continue Solar live evidence. This preparation leaves the complete `.65` candidate uncommitted and unreleased; `.64` remains live until the next action is separately authorized.
- Next live evidence is the Solar ownership and near-full/exit captures above, plus a blocker trace only if needed. Morning Dump remains accepted for the observed case. Evening Boost reserve-estimator instability and import-cost trust poisoning remain parked pending a separate decision. The two Phase 2 failures remain frozen. This checkpoint authorizes no commit, push, main promotion, tag, build, publication, release, installation, restart, deployment or control change.
