# SigEnergy Optimizer AI Handover

Last consolidated: 2026-10-06

Read root and project `AGENTS.md`, then `CURRENT_STATE.md`, `CONTROL_CONTRACT.md`, `DECISIONS.md`, and `ROADMAP.md`. Verify worktree, branch, HEAD, tracking, and status before editing.

## Current release and identities

- Worktree: `C:\Projects\sigenergy_optimizer-phase1-remediation`; branch: `fix/phase1-audit-remediation`.
- Local branch HEAD/pre-release source checkpoint is `f203387a445fcf9e4ea569861ca3d35703b1b7b9`, including provider-aware Solar freshness and tests/docs regression hardening. Version `2.3.55-haos66` release identities are prepared locally but uncommitted, unpushed and unbuilt. The worktree started clean and is dirty only with release identities/documentation; production behavior remains unchanged. The candidate is unreleased and undeployed.
- Operator-supplied live release and rollback: `.65` / `2.3.54-haos65`, source `9965e79`. **Phase 1 and dynamic Solar live acceptance remain pending.**
- The earlier authorized source and tests/docs checkpoint commits are complete. This release preparation performed no commit, push, main promotion, tag, build, publication, deployment, installation, restart or live control write.

## Provider-aware candidate continuation

- Dynamic Solar charge ownership now uses configured Forecast Today/API Last Polled from one Solcast instance. The accepted v4.6.1 successful-provider contract is in `DECISIONS.md`; durable semantics are in `CONTROL_CONTRACT.md`. First observation is baseline only, later qualifying P advancement validates, and no state is persisted or forced refresh requested.
- Retained D cannot slide with later N or early manual success. Earlier N shortens D; qualifying success at/after D may replace it. Epoch invalidation precedes lossy WS queue handling and rejects older in-flight reads. Existing-loop deadline/midnight wakes and pre/post-write authority checks release the restriction safely. Global observation trust and all other control consumers/priorities remain unchanged.
- Settings expose the compatible observation-age key/default of 600 and the API Last Polled mapping; invalid runtime ages are rejected. Decision Trace includes state, observed/high-water/verified P, retained/advertised deadlines, source/epoch, trust and rejection reasons.
- Source-checkpoint validation: Solar redesign **68 passed / 78 subtests**; affected suites **282 passed / 305 subtests**; independent protections **371 passed / 412 subtests**, two frozen tests deselected, on both recovery and ladder runs. Full suite once: **840 passed / 778 subtests**, only the two frozen Phase 2 failures. Compileall passed for app and changed Python tests; `git diff --check` passed. No unexpected failures remain.
- The approved additional edit in `tests/test_solar_surplus_redesign.py` adds only shared fixture setup: configured source/epoch, baseline P, later P and valid deadline. All 68 existing test bodies are identical. Missing-provenance scenarios retain missing provider evidence. Other lifecycle fixture doubles gained the callback; assertions were not weakened.
- No live candidate behavior is established. Next decision: review and approve the release-preparation checkpoint commit; release/version/publication/build/deployment/restart require separate authorization. After candidate deployment, obtain provider bootstrap, stale-parent valid ownership, retained-deadline/discontinuity release/recovery and the Solar ownership/near-full captures below. Rollback remains live `.65`.

## Tests/docs regression-hardening follow-up

- Two added regressions isolate day rollover with D still future and valid new-day evidence (epoch revocation, fresh baseline, later P recovery), and continuity loss after the charge write during a later discharge await (actual optimizer loop immediately restores normal charging on its next cycle). Neither exposed a production defect; existing assertions and production/control-contract semantics are unchanged.
- README/ROADMAP current live/rollback identities now distinguish live `.65` / `9965e79` from committed, undeployed checkpoint `aec127d7efd9fe7787c8253b882207b50a44eeed`. Historical context and phase dependencies are preserved.
- Follow-up validation: each new test passed individually; provider suite **32 passed / 34 subtests**; dynamic-charge/lifecycle suites **23 passed / 16 subtests**; independent Solar/provider/event/MSC protections **173 passed / 188 subtests**, with the two frozen tests deselected. Full suite ran once: **842 passed / 778 subtests**, only the **2 frozen Phase 2 failures**, no unexpected failures. Compileall and `git diff --check` passed; all 30 existing provider test bodies are unchanged by AST comparison. This regression hardening is committed at `f203387a445fcf9e4ea569861ca3d35703b1b7b9`; Phase 1 still requires separate live acceptance.

## Local release preparation - 2026-10-06

- Prepared candidate `2.3.55-haos66` using the verified `.64 -> .65` convention: future tag `v2.3.55-haos66`, versioned image `ghcr.io/belot77/sigenergy-optimizer:2.3.55-haos66`, and plain-version buildstamp. No tag, image or release has been created by this preparation.
- Only the FastAPI version and optimizer runtime-signature literals changed in production Python. Add-on version/label/buildstamp and release-facing README/both changelogs are aligned; configuration defaults and control semantics remain unchanged.
- Release-preparation validation completed successfully on 2026-10-06 within the approved gate: explicit UTF-8 comparison proves version-only production changes; YAML parsing/metadata comparison confirms unchanged defaults/build inputs. Release-version/API suites: **48 passed / 53 subtests**. Full suite once: **842 passed / 778 subtests**, only the two frozen Phase 2 failures, unchanged in character; no unexpected failures. Compileall for `app` and `git diff --check` passed. The earlier CP1252/UTF-8 helper mismatch was corrected only in the validation command.
- Version `2.3.55-haos66` and future tag `v2.3.55-haos66` remain locally prepared; HEAD remains `f203387a445fcf9e4ea569861ca3d35703b1b7b9`. Changes remain uncommitted, unpushed and unbuilt. Live/rollback remain `2.3.54-haos65` / `9965e79`; no build/release/deployment occurred and Phase 1 live acceptance remains pending. Exact next action: review and approve the release-preparation checkpoint commit.

## Completed diagnostics checkpoint and control boundaries

- The existing approximately 1000-cycle in-memory Decision Trace remains unchanged. Persistent rolling 24-hour JSONL diagnostics flush every 15 minutes; diagnostics I/O is isolated from control and the default executor. Persistent possible-gap reporting remains conservative. Clock uncertainty safely pauses persistent writes/pruning; diagnostics failure cannot block optimizer/control startup.
- Historical `.64` live evidence confirmed 24 Hour Trace producing approximately 3.5 MB in its first approximately 15-minute flush. The released `.65` diagnostics hotfix increased only the download ceiling from 256 MiB to 512 MiB and did not change control behavior.
- Live `.65` downloads remain bounded to 4 active requests, a 2-minute lifetime, 25 segments and 512 MiB (previous `.64` limit: 256 MiB). All other diagnostics resource bounds, chunk size, retention, persistence cadence, clock handling, authentication, streaming and pin cleanup remain unchanged. Abrupt crashes can lose the unflushed interval; there is no final shutdown flush.
- Historical `.65` diagnostics validation is retained in `CURRENT_STATE.md`; the provider-aware candidate's current gate results are above. Neither gate establishes Solar live acceptance.
- Solar can own a bounded lower ESS charge ceiling only after final Solar arbitration and stricter trusted detailed evidence. Failed evidence immediately releases that restriction; grid-import charging precedence and higher-priority owners remain. Solar remains MSC/PV-only, with normal PV MAX and high export permission, and no `BATTERY_EXPORT` authority.
- Protect Manual/Force ownership, Demand Window import ownership, observed Automated ownership, fail-closed telemetry and actuator settlement, battery floor, reserve/forecast checks, and the independent Actual Import Cost Guard. Export Value Gate remains advisory-only; Actual Import Cost Guard remains enforcing in live `.65` and the provider-aware candidate.
- The only expected failures remain the frozen Phase 2 transition-settlement tests in `tests/test_msc_baseline_overlay_contract.py`: `test_exact_msc_does_not_reopen_before_export_is_observed_closed` and `test_return_from_discharge_waits_for_observed_close_before_requesting_msc`.

## Live evidence and pending Solar acceptance

- **Morning Dump is accepted for the observed case:** deliberate battery export worked; approximately 15 kW actual export with no grid import; PV MAX stayed 25 kW; dump reached the approximately 15% floor, then relinquished and transition safety closed/reopened export appropriately. Do not require further Morning Dump evidence now.
- **Solar dynamic ESS charge-ceiling live acceptance is still pending.** Live `.65` remains unchanged; obtain provider acceptance and these captures after separately approved candidate deployment:

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
- Exact next action: review the release-preparation diff/results and approve a release-preparation checkpoint commit. Leave this preparation uncommitted, unpushed and unbuilt. Live `.65` remains authoritative and the rollback. Release/deployment and live acceptance require separate approval; phase order/dependencies remain unchanged.
- Next live evidence is the Solar ownership and near-full/exit captures above, plus a blocker trace only if needed. Morning Dump remains accepted for the observed case. Evening Boost reserve-estimator instability and import-cost trust poisoning remain parked pending a separate decision. The two Phase 2 failures remain frozen. This checkpoint authorizes no commit, push, main promotion, tag, build, publication, release, installation, restart, deployment or control change.
