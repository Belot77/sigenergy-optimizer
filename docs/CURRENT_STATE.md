# Current State

Last consolidated: 2026-10-06

**CURRENT TRUTH ONLY:** durable control semantics live in `CONTROL_CONTRACT.md`; sequencing lives in `ROADMAP.md`.

## Release and live state

- Current live release: `.65` / `2.3.54-haos65`, source commit `9965e79133f38d5b9943dcf5a9b04ed6fdab1239` (operator-supplied live state).
- Provider-aware Solar freshness and regression hardening are committed through pre-release source checkpoint `f203387a445fcf9e4ea569861ca3d35703b1b7b9` on `fix/phase1-audit-remediation`, based on live `.65`. Release metadata for `2.3.55-haos66` is now prepared locally but uncommitted, unpushed and unbuilt. The worktree started clean and is dirty only with release identities/documentation; production behavior is unchanged from that checkpoint. The candidate remains unreleased and undeployed.
- Rollback remains live `.65` / `2.3.54-haos65`, source `9965e79`; the candidate has not altered live control.
- **Solar dynamic ESS charge-ceiling live acceptance is still pending.** Available evidence does not yet prove dynamic Solar ownership and safe relinquishment.
- Phase 1 remains open. Phase 2 remains frozen until controlled Solar acceptance and separate Evening Boost remediation and live acceptance are complete.

## Diagnostics checkpoint

- Worktree: `C:\Projects\sigenergy_optimizer-phase1-remediation`; branch: `fix/phase1-audit-remediation`; local HEAD/pre-release source checkpoint is `f203387a445fcf9e4ea569861ca3d35703b1b7b9`. Live `.65` remains at `9965e79133f38d5b9943dcf5a9b04ed6fdab1239`.
- Historical `.64` live evidence confirmed 24 Hour Trace producing approximately 3.5 MB in its first approximately 15-minute flush. The released `.65` diagnostics hotfix increased only the download ceiling from 256 MiB to 512 MiB; that release did not change control behavior.
- The existing approximately 1000-cycle in-memory trace remains unchanged. A rolling 24-hour JSONL archive flushes every 15 minutes, with diagnostics I/O isolated from control and the default executor. Persistent possible-gap reporting is conservative; clock uncertainty safely pauses persistent writes and pruning.
- `.65` downloads allow at most 4 active requests, a 2-minute lifetime, 25 segments and 512 MiB per download. All other diagnostics resource bounds, chunk size, archive retention, persistence cadence, clock handling, authentication, streaming and pin cleanup remain unchanged. An abrupt crash can still lose the unflushed interval; there is no final shutdown flush. Diagnostics failure cannot block optimizer/control startup.
- Historical `.65` diagnostics validation before its mechanical version bump: focused download/UI **27 passed**, **18 subtests passed**; diagnostics/store/lifecycle/API/UI **100 passed**, **61 subtests passed**; selected control protections **543 passed**, **540 subtests passed**, with the two frozen tests deselected. Its full-suite gate recorded **806 passed**, **725 subtests passed**, and only the **2 frozen Phase 2 failures** below.
- The only expected failures remain the frozen Phase 2 tests `test_exact_msc_does_not_reopen_before_export_is_observed_closed` and `test_return_from_discharge_waits_for_observed_close_before_requesting_msc` in `tests/test_msc_baseline_overlay_contract.py`.

## Live Dynamic Solar behavior

- The `.63` change allows Solar to own a bounded lower ESS charge ceiling only after final arbitration selects `solar_surplus_policy_active` and stricter detailed charge evidence is trusted. It allocates protected fill need to the current interval only when future detailed charge opportunity cannot cover it, rounds positive requests upward within the normal safe/trusted request, and immediately relinquishes the restriction when evidence fails. Grid-import charging precedence and other higher-priority owners remain intact. Solar stays MSC/PV-only with normal PV MAX and high export permission.

- Live `.65` still uses Forecast Today's shared 600-second observation-age gate for dynamic charge ownership. Operator evidence showed this gate expiring about ten minutes after a successful poll while the legitimate next update was the following morning. The candidate below addresses that dependency only; it is not live-accepted.

## Unreleased provider-aware freshness candidate

- Implemented process-local UNVERIFIED/VALID/EXPIRED authority using configured Forecast Today and API Last Polled sources. Startup establishes a baseline only; later successful P advancement and strict detailed evidence are required. The accepted Solcast v4.6.1 external success contract is recorded in `DECISIONS.md`.
- Retained deadline D never slides with later schedules or successes before D. Earlier N shortens D; qualifying success at/after D may establish a future deadline. Expiry and local-day rollover revoke authority through the existing event loop without waiting for an HA event or heartbeat. Charge writes recheck authority and restore the selected normal request when an in-flight reduced write crosses invalidation.
- Sticky WebSocket/source epochs survive overflow/coalescing. Disconnect/reconnect, unavailable/reload, reassignment, regression and uncertain continuity require a fresh baseline and later advance; older in-flight REST reads cannot establish authority.
- Global Forecast Today trust, Standby Holdoff, Remaining Today/Power Now, Forecast Tomorrow and import-price consumers retain their existing semantics. Settings expose the existing observation-age key/default of 600 and reject nonpositive/nonfinite runtime updates; it cannot extend provider authority. Control priorities, calculation/rounding/capability bounds, Manual/Force, MSC/PV MAX/export/battery-export and settlement protections remain unchanged.
- Source-checkpoint validation on 2026-10-05: Solar redesign **68 passed / 78 subtests**; affected suites **282 passed / 305 subtests**; independent protections **371 passed / 412 subtests**, with the two frozen tests deselected (the group passed both its recovery run and ladder rerun). Full suite ran once: **840 passed / 778 subtests**, exactly the **2 frozen Phase 2 failures**, no unexpected failures. Compileall passed for `app` and changed Python tests; `git diff --check` passed. All 68 Solar redesign test method bodies remain identical; only their shared provider setup was added.
- Existing lifecycle doubles were extended with the provider callback; no protection assertions were weakened or skipped. Decision Trace now includes provider state, observed/high-water/verified P, retained/advertised deadlines, source/epoch, trust gates and reasons. Tests establish local behavior only; no deployment or live control validation occurred.

## Tests/docs regression-hardening follow-up

- Added isolated local-day rollover coverage with retained D still future and structurally valid new-day evidence: revoke the old epoch, establish a fresh UNVERIFIED baseline, then recover only after another qualifying P advance.
- Added actual optimizer-loop coverage for continuity loss during the discharge await after the reduced ESS charge write. The immediate next cycle rejects stale authority and restores the normal request without waiting for the 60-second heartbeat. HA reads/writes and unrelated publication/history effects are mocked; neither new test exposed a production defect.
- Corrected stale current live/rollback wording in README and ROADMAP; historical release evidence and phase order/dependencies remain unchanged. This follow-up changes tests/docs only, with no control-contract or production change.
- Follow-up validation on 2026-10-05: each new case passed individually (**1 passed** each); complete provider suite **32 passed / 34 subtests**; directly affected dynamic-charge/lifecycle suites **23 passed / 16 subtests**. Independent Solar redesign/status, forecast/clock/telemetry, event-responsiveness and MSC-baseline protections: **173 passed / 188 subtests**, with exactly the two frozen tests deselected. The full suite ran once: **842 passed / 778 subtests**, exactly the **2 frozen Phase 2 failures** named above, no unexpected failures. Compileall passed for the changed Python test file; `git diff --check` passed. AST comparison confirmed all 30 existing provider test bodies are unchanged, with only the two regression cases added. The tests/docs follow-up was committed at `f203387a445fcf9e4ea569861ca3d35703b1b7b9`; no release/deployment has occurred.

## Local release preparation - 2026-10-06

- Prepared candidate `2.3.55-haos66` using the verified `.64 -> .65` convention: future tag `v2.3.55-haos66`, versioned image `ghcr.io/belot77/sigenergy-optimizer:2.3.55-haos66`, and plain-version buildstamp. No tag, image or release has been created by this preparation.
- Only the FastAPI version and optimizer runtime-signature literals changed in production Python. Add-on version/label/buildstamp and release-facing README/both changelogs are aligned; configuration defaults and control semantics remain unchanged.
- Release-preparation validation completed successfully on 2026-10-06 within the approved gate. Explicit UTF-8 comparison proves each production file differs from HEAD only by `2.3.54-haos65` -> `2.3.55-haos66`; add-on YAML parsing and metadata comparison confirm unchanged defaults/build inputs. Release-version/API-validation suites: **48 passed / 53 subtests**. Full suite ran once: **842 passed / 778 subtests**, exactly the two frozen Phase 2 failures named above, unchanged in character (premature export reopening and MSC request before observed closure); no unexpected failures. Compileall for `app` and `git diff --check` passed. The prior comparison-helper CP1252/UTF-8 mismatch was resolved in the validation command without further production edits.
- Prepared version remains `2.3.55-haos66`, future tag `v2.3.55-haos66`; HEAD remains `f203387a445fcf9e4ea569861ca3d35703b1b7b9`. Release preparation remains uncommitted, unpushed and unbuilt. Live/rollback remain `2.3.54-haos65` / `9965e79`; no build, release or deployment has occurred, and Phase 1 live acceptance remains pending. Next decision: review and approve the release-preparation checkpoint commit.

## Controlled Solar live acceptance still required

Required next live evidence:

After a separately approved candidate release/deployment, first capture UNVERIFIED baseline followed by VALID provider advancement, including an old Forecast Today observation with unchanged global trust. Capture missed-deadline or discontinuity relinquishment and restoration of the otherwise applicable normal ESS request, then recovery requiring a new baseline/advance. Confirm retained D does not slide when N advances or a manual success arrives before D, and that the existing safeguards and control permissions below remain intact. Do not force a provider update solely to bootstrap this candidate.

1. **Solar ownership after Morning Slow ends:** `solar_surplus_policy_active=true`, `solar_charge_ceiling_owned=true`, `solar_charge_ceiling_evidence_trusted=true`, and `ess_charge_limit_owner=solar_surplus`; a dynamic requested ceiling below the normal approximately 21 kW when appropriate. Confirm MSC, PV MAX 25 kW, export permission 25 kW, `battery_export_owner=none`, and actual PV/load/grid/battery flows showing PV surplus export.
2. **Near-full / Solar exit:** capture around 95-99% SoC or when Solar relinquishes. Prove no stale low ESS charge ceiling or Solar owner remains, and distinguish inverter taper from an optimizer-owned ceiling. This supplements the ownership capture.
3. **Conditional blocker trace:** capture only if Solar unexpectedly does not activate under strong suitable conditions.

Observe the 27 September Solar aggregate-budget threshold-switching follow-up without assuming `.63` fixes it. Solar acceptance does not automatically start Phase 2.

## Evening Boost findings parked until after Solar acceptance

- **Confirmed transition-stability defect:** `_battery_soc_required_to_sunrise()` projects instantaneous household load across the remaining overnight horizon. The latest `.63` trace again showed implausibly high required SoC/protected reserve above 100% under transiently high household load, preventing Evening Boost. Earlier `.62` evidence showed repeated transitions between `evening_export_boost` / Command Discharging and MSC while SoC and FiT were effectively stable and load changed sharply. No remediation or live acceptance is claimed.
- **Newly confirmed import-cost trust interaction:** `.63` records optimizer import/top-up chunks with price trust. A significant daily import chunk of at least `0.01 kWh` with untrusted, missing, or non-finite price leaves `import_cost_floor_trusted = false` and `import_cost_floor_unknown = true` for the day; later trusted import-price observations do not repair that state. Live `.63` evidence showed `today_import_topup_kwh` about `18.412 kWh`, `today_highest_actual_import_price` about `$0.2037716/kWh`, and that untrusted/unknown floor state. This indicates at least one significant earlier optimizer-controlled import/top-up event lacked trusted price provenance, even though other trusted-price imports existed. When Evening Boost qualifies as explicit `BATTERY_EXPORT` owner, the independent Actual Import Cost Guard can hard-veto it because of this state.
- Export Value Gate remains advisory-only; the independent Actual Import Cost Guard remains enforcing in current `.63` behavior. No Evening Boost import-cost solution or redesign has been selected. Investigate the persisted import/top-up event and provenance, and decide the intended guard interaction during the separate bounded Evening Boost review. Preserve reserve, forecast, ownership, import-cost, and settlement protections.

## Protected behavior and operator configuration

- Manual/Force ownership, Demand Window import ownership, observed Automated ownership, fail-closed telemetry and settlement, battery floor, and safe fallback remain protected. Provider deadline reevaluation uses the existing event loop; the candidate introduces no independent control loop or battery-export authority.
- Earlier `.61` live evidence established the near-full Solar exception for genuinely untrusted available-discharge-energy telemetry at about 93.9-96.7% SoC, a clean Morning Slow to Solar transition, and the 25 kW ceiling acting as PV export permission rather than commanded battery discharge.
- Earlier `.62` Morning Slow evidence showed MSC, safe load-serving battery behavior, and clean closure at its end. Poor-solar evidence showed Morning Slow remained inactive when timed refill was infeasible even at normal capability.
- **Morning Dump live evidence is accepted for the observed case:** deliberate battery export worked, approximately 15 kW actual export was observed with no grid import, PV MAX remained 25 kW, and the dump reached the approximately 15% floor before relinquishing. Transition safety closed/reopened export appropriately. No further Morning Dump evidence is required now.
- Recorded operator Morning Slow tuning: enabled, 2 kW, until 11:00, minimum FiT `$0.01/kWh`, base-load allowance 2 kW, sunset cutoff 1 hour.
- `grid_connection_export_limit_kw=15` and `morning_slow_physical_export_headroom_kw=0.5` remain parked/unconfigured and are not defaults. Before configuring them, decide whether 15 kW is merely the site-export threshold releasing Morning Slow's artificial charge cap or a hard network/export limit. Current code implements only the former.

## Sequence and next action

Exact next action: review the release-preparation diff and validation results, then approve a release-preparation checkpoint commit. Pre-release source remains `f203387a445fcf9e4ea569861ca3d35703b1b7b9`. Commit approval alone will not authorize push/tag, release, image build/publication, installation, restart or deployment. Live `.65` remains the baseline and rollback; Phase 1 still requires separate release/deployment approval and live acceptance.

Obtain the provider/Solar evidence above only after separately approved candidate deployment. Evening Boost reserve-estimator instability and import-cost trust poisoning remain parked; no Evening Boost remediation has begun. Morning Dump remains accepted for the observed case. The two Phase 2 transition-settlement failures remain frozen and expected. Phase 1 is not live-accepted; Solar acceptance does not automatically start Phase 2. ROADMAP corrections update current release identities only; phase order/dependencies are unchanged.

Keep the parked settings unconfigured and all protected ownership/fail-closed behavior intact. Leave release preparation uncommitted for review. The earlier authorized source and tests/docs commits are complete; this release preparation performed no commit, push, main promotion, tag, build, release, install, restart, deployment or live control change.
