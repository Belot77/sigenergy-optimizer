# Current State

Last consolidated: 2026-10-18

**CURRENT TRUTH ONLY:** durable semantics live in `CONTROL_CONTRACT.md`; sequencing lives in `ROADMAP.md`; historical decisions remain in `DECISIONS.md`.

## Approved local correction and remaining review gates

**Code checkpoint committed and pushed; draft PR #21 is open.** Active Dump now selects discharge only for qualified `BATTERY_EXPORT` intent and a requested target above 0.01 kW; otherwise it explicitly selects MSC. Qualified negative-price Dump retains priority, and inactive-Dump negative-price charging remains permitted. The exact red regression is green. Focused checks passed 11 tests / 26 subtests; independent Demand Window/authority/settlement checks passed 13 tests / 15 subtests. Independent safety/test review reported GO for the narrow correction; a subsequent full combined code/test review also reported GO with no actionable findings. Independent documentation review reported GO for the current documents and proposed 19-file scope after the local-export clarification. Final combined offline validation passed **1,073 tests / 1,134 subtests, zero failures**, with 206 warnings in 170.97 seconds. See `MORNING_DUMP_CORRECTION_REVIEW_2026-10-18.md`. The operator approved code checkpoint `4e4b17c2d3bb362716d6b4e5ddb60659faf7beec`, its development-branch push and draft PR #21. The PR remains draft and unmerged; no submitted reviews or GitHub CI checks were reported in the 18 October check. Local test evidence is separate. Further commits/pushes, merge, release and live actions require their own authorization.

## Live identity and rollback
- Latest published release: **2.3.60-haos71**, published 16 October 2026 at 16:45:11 Australia/Sydney. `main` and tag were verified at `9f3f02a5c1c82786c85026a3848574cca3cf891f` on 17 October; no new remote or live query was made for this fix. Publication does not establish installation or live acceptance.
- Last **operator-reported** live release: **2.3.59-haos70**, source `08f4daf53941bd850a4fe392b458c42b1df68b47`. This is not a new Home Assistant/runtime verification. This documentation checkpoint makes no installed-system changes.
- The supplied external review says later discussion identified .71 as installed. No HA About/startup/source-build evidence was supplied or accessed here, so current installation remains unverified; .70 is retained only as the last directly recorded operator report, not a claim that it is still installed.
- Protected known-good rollback: **2.3.54-haos65**, source `9965e79133f38d5b9943dcf5a9b04ed6fdab1239`. Do not promote .70 to known-good without supervised live acceptance.
- Morning Dump physically activated on 15 October; minimum SoC deliberately set to 15%, and timing option set to 1.0 hour before sunrise (existing implementation runs from sunrise through one hour afterward). Morning Slow was observed near 2 kW and physical export near 15 kW. Evening Boost disabled. Approximate 15 October PV forecast: 130 kWh. These are reported observations/settings, not renewed authority verification.
- Phase 1 remains open, including exact-full Demand Window PV-only physical proof, Evening Boost reserve/transition stability and Solar threshold-switching disposition. Phase 2 retains only scoped .68 acceptance; a 13-second observation gap and broader cases remain unproven. Four-tier and .70 physical acceptance remain outstanding.
- Preserve .65 rollback readiness before any later supervised live testing. Passing tests and successful service calls do not prove inverter settlement.
## Published Stage B baseline and validation

- Stage B checkpoint **`ae4a974692aae1300c97845fcc32d4cfa6c2bdea`** (`ae4a974692aa`) is historical; PR #20 was merged. The published tag/release and `main` point to `9f3f02a5c1c82786c85026a3848574cca3cf891f`; no open PRs were found in the 17 October check.
- Stage B implementation is **completed**, including the narrow Medium-over-Evening Boost priority correction and authority/actuator safety repair. Defects A, B and C are corrected; the supplied independent focused review passed all three corrections.
- Retained final full-suite result supplied for this checkpoint: **1,036 tests / 1,084 subtests, zero failures**. Compileall and `git diff --check` passed. The full suite is not rerun for version-only preparation; release consistency, compileall with an external cache, diff and exact-scope checks are the preparation gate.
- **No supervised live acceptance yet. Stage B remains NO-GO for deployment.** Automated validation and independent code review do not prove inverter settlement or physical flow.

### Completed safety corrections

- **A - Contradictory actuator evidence:** conflicting actuator observations cannot prove settlement. Deliberate discharge requires the intended export target, with fresh provenance-bearing evidence strictly after its own dispatch boundary; a smaller value sufficient for a safety close is not proof of a deliberate discharge target.
- **B - Independent ESS restrictions:** successful fallback cannot restore ESS charge/discharge capability above independently owned restrictions. Solar relinquishment restores only the otherwise safe normal charge request; Demand Window import blocking and independent PV restrictions remain effective.
- **C - Pending Force ownership:** unchanged Automated selector reports prove freshness, not a new operator selection. A pending authenticated Force request yields to a verified selector state transition strictly after its request, with coherent change/update/report timestamps; supersession stops subsequent writes/retries.

Current Automated ownership and observed Remote EMS ON remain required at application/dispatch boundaries. Unknown evidence fails closed; independent restrictive writes remain available while unrelated permissive recovery waits for observed settlement. Preserve ordinary unattended restart/auto-enable after current Automated verification and observed Remote EMS ON, authenticated Manual/Force and `/set_ess`; no persistent OFF registry or mandatory restart handback redesign.

### Protected reference and historical Stage A evidence

- Stage A tests-only characterization was independently accepted on 15 October: 25 passed, 47 deliberately red baseline regressions; corrected D7 passed; independent protections 77 tests/89 subtests passed, zero unexpected failures. These are historical baseline results, not current Stage B failures. Preserve the regression assertions.
- Protected reference: `C:\Projects\sigenergy_optimizer-evening-priority`, branch `test/evening-medium-priority-characterization`, base `08f4daf...`, ten intentionally dirty files. Never reset, stash, discard, overwrite, commit, delete or wholesale-copy its optimizer. This checkpoint does not touch it or the Stage A worktree.

## Outstanding operational bug register

All entries remain open for the stated evidence or decision. Candidate fixes and passing automated tests do not close live acceptance. Earlier evidence references below and in `ROADMAP.md` remain applicable. The supplied trace adds one confirmed Morning Dump command inconsistency and a trace-recording blind spot; other physical-flow/cycling causes and live acceptance remain open.

| ID | Issue | Classification and outstanding disposition |
| --- | --- | --- |
| O1 | Medium versus Evening Boost | Confirmed software defect; narrow priority correction included in published `.71` source. Supervised live acceptance outstanding; broader Boost stability is O4. |
| O2 | Unexpected export interruptions/cycling | The 12:22 Solar ownership flip is explained by a load-sensitive aggregate budget crossing zero, reproduced offline. Other reported interruptions and physical-flow causes remain unresolved; reconcile requests, actuator readbacks and physical flows. |
| O3 | Solar Override | A selected/protected-floor bypass was confirmed and corrected in this combined local candidate, preserving separately qualified PV-only MSC. Component tests passed 304 tests / 412 subtests plus two release checks. Historical physical reports and supervised live acceptance remain unresolved; related 27 September threshold-switching evidence is retained in `ROADMAP.md` section 3. |
| O4 | Evening Boost oscillation | Observed unstable switching and SoC requirements; operator-policy review and live acceptance outstanding. Not proven resolved by O1. Retained Phase 1 follow-up and 10 October deferral: `ROADMAP.md` sections 3-4. |
| O5 | Overnight battery reserve | Operator-policy decision pending: Medium/High thresholds, tomorrow-PV awareness and enough battery until solar takes over. Proposed 30-cent tuning is not approved; no threshold changes authorised. |
| O6 | Morning Dump / Morning Slow | The initial discharge guard and approved explicit MSC fallback now prevent blocked active Dump from selecting discharge or falling through to negative-price grid-charge EMS. Focused checks pass 11 tests / 26 subtests; independent safety/test review reports GO for this narrow delta. Floor cycling, other depletion/ownership reports and live verification remain open. Reported 15 October settings/flows above remain historical context. |
| O7 | Demand Window at exact-full SoC | Live-acceptance requirement: prove PV-only surplus export without deliberate battery export or grid import. Retain the hotfix evidence below and `ROADMAP.md` section 4B; automated tests do not prove physical outcome. |
| O8 | 13-second transition observation gap | Historical evidence/live-acceptance requirement remains unresolved. The trace component records pending/error application outcomes (298 tests / 248 subtests), but cannot recover missing historical records or prove physical settlement. Scoped `.68` acceptance cannot fill the gap or establish unexercised cases; see `ROADMAP.md` section 4. |
| O9 | Obsolete, overlapping or misleading policies/settings | Scheduled short control-ownership/configuration audit, including Solar Override and configuration ownership. No removal, redesign or policy decision in this checkpoint. See `ROADMAP.md` section 5. |

### Supplied 17–18 October trace audit and operator disposition

- Source: `sigenergy_decision_trace_24h_20261017T215448Z.jsonl`, 17,340 valid records from 17 October 08:54:51 to 18 October 08:50:57 Australia/Sydney; SHA-256 `ccaa643684d4e2c2620aba22faba99bb22f81dc3df99015bd44b5ac7fc7b196f`. No raw trace is copied here.
- The operator deferred short physical import spikes associated with sudden changes/physics: not a confirmed Demand Window bug, no setting change. This is distinct from O7 exact-full PV-only export proof, which remains open. Four short floor-chatter pulses at 15/15.1% matched the configured 15% floor without breach. The stable-FiT 12:22 example follows the load-sensitive energy-budget gate; the 92 charge-owner transitions have not all been individually classified or resolved. See `CYCLING_AUDIT_2026-10-18.md`.
- 38 Morning Dump blocked-export/discharge-EMS records occurred between 07:10:51 and 07:13:34. The supplied file's 526s and 33s gaps do not resolve the historical 13-second O8 gap. EMS/import/export readbacks were present; build identity and observed ESS limits were absent. The P3 positive-FiT reason mismatch is diagnostic, not established as a control-path defect.
- The trace did not exercise Solar Override, Evening Boost, Medium-or-higher tiers, negative prices or actual-import-cost vetoes. All four local changes are now combined in the review branch; original Solar Override, Morning Dump and trace worktrees remain intact.

## Historical .70 release-preparation validation (2026-10-13)
The following is retained test evidence from before the operator-reported .70 installation, not a current release-preparation status.

- Exact-marker extraction asserted all five values equal `2.3.59-haos70`; existing release consistency checks passed: `python -m pytest -q -p no:cacheprovider tests/test_release_version_consistency.py` (**2 passed**).
- Demand Window regression and independent protections passed: **356 tests / 468 subtests**, zero failures, **203 Pydantic deprecation warnings**. Command: `python -m pytest -q -p no:cacheprovider tests/test_msc_baseline_overlay_contract.py tests/test_demand_window_pv_max.py tests/test_phase1_actuator_settlement_fallback_characterization.py tests/test_phase1_authority_fail_closed_characterization.py tests/test_four_tier_battery_export.py tests/test_export_value_gate_advisory.py tests/test_phase1_capability_model_characterization.py tests/test_phase1_battery_telemetry_trust_characterization.py tests/test_solar_surplus_redesign.py tests/test_phase1_morning_slow_relief_characterization.py`. This includes exact-full ON/OFF/untrusted, Manual/Force, observed settlement, actual import-cost, four-tier ownership, telemetry/capability, Morning and Solar protections.
- Final pre-checkpoint full suite run once: `python -m pytest -q -p no:cacheprovider --disable-warnings` -> **946 tests / 1,079 subtests passed**, zero failures, **206 Pydantic deprecation warnings**, in 128.42 seconds. Warning display was shortened; warning counts and test selection were unchanged.
- `python -m compileall -q app tests` passed with `PYTHONPYCACHEPREFIX` pointing to a unique external temporary cache. `git diff --check` passed. Complete diff review and exact ten-file scope checks passed; all changes remain local and unstaged, with no untracked files. No test, control logic, source-clone or workflow changes were needed.
- Test runs use `PYTHONDONTWRITEBYTECODE=1` and disable pytest's cache provider to keep generated files out of the worktree.
- Production-content comparison against published hotfix `67fae5db2451fbf3e706b10cf4e2dbad07b38bd9` passed after normalizing Git LF/checkout CRLF: exactly the FastAPI version and `_RUNTIME_SIGNATURE` substitutions. The initial raw-byte comparison encountered checkout line endings; this was a verification-method correction, with no source change or test failure. Tests, control contract, Dockerfile and workflow match the published hotfix.

## Demand Window / exact-full PV-only hotfix

The confirmed defect affected an otherwise qualifying exact-100%-SoC, cheap-positive-FiT MSC PV-only opportunity: Demand Window OFF and untrusted received the configured high MSC surplus ceiling, but trusted ON returned `0 kW` and `EXPORT_BLOCKED`. ON and untrusted correctly blocked import.

The narrow correction removes only `and not trusted_demand_window_active` from `pv_only_msc_transition_ready`. Qualified ON now receives the same configured, capability-bounded `MSC_SURPLUS_CEILING`; import remains blocked. OFF and untrusted behaviour is preserved. The transferred 49-line characterization test is the only test addition; existing expectations are unchanged.

Exact-full qualification, observed Automated/exact MSC authority, trusted safe flow evidence, actuator settlement and physical bounds remain mandatory. Below-100% cheap-FiT protection remains intact. The change creates no `BATTERY_EXPORT` owner or discharge EMS and leaves Morning, Solar Surplus, ordinary export, Manual/Force and actual import-cost protections unchanged. Settlement/application helpers and capability helpers are unchanged. Automated decision/test evidence is not proof of physical export or live settlement.

## Original .69 audit remediation (historical context)

The historical independent ChatGPT GitHub code audit reported GO for corrected checkpoint `bec1095539b96dbb90b62bd6eb047471e41801f6`, resolving both original blockers. That review does not cover the new Demand Window delta:

1. Rejected High/Spike battery proposals no longer suppress independently qualified Solar Bypass or Evening Boost. Qualified High/Spike proposals retain priority and all execution vetoes; a cost-vetoed candidate cannot obtain alternate permission through an overlapping policy.
2. When arbitration selects an independent Solar/Evening policy, legacy High/Spike and Positive-FiT branches cannot intercept it. This preserves qualified Solar ownership when Medium defers, including with legacy opt-ins; it does not create lower-tier battery fallback.

Untrusted available energy still rejects High battery export with zero calculated power and no battery owner/discharge EMS. Independently qualified Solar may retain `MSC_SURPLUS_CEILING` under its own trusted evidence, flow, authority and settlement safeguards. The protected characterization now distinguishes those outcomes and retains unsafe-evidence coverage.

The existing three-cycle Phase 2 test now uses a local shared deterministic clock, explicitly advancing between requests and observations. All original actuator-order assertions remain; nine subcases cover trusted later reports and equal, older, stale or missing export/MSC reports through real application checks. The mechanical indentation correction changes no expectation. A fixed-clock diagnostic reproduced the prior restrictive sequence, but the original failure's timestamps were not captured, so that historical occurrence's exact cause remains unproven. No production settlement defect or live acceptance is claimed.

## Four-tier behavior

Ordinary automated deliberate battery export starts at **Medium**. Low remains a price classification and PV-only permission context; it cannot create a battery-export proposal/owner, discharge EMS or Morning preemption, even at 100% SoC or with persisted Low floors of 90%, 0% or any other accepted value. `battery_export_min_soc_low` remains compatible and validated, defaults to **100%**, and cannot re-enable Low sale. Medium / High / Spike retain independently configured floors of **40 / 20 / 10 percent**, with no ordering constraint or selected-tier fallback.

All four keys remain numeric, finite 0-100 inputs with booleans rejected and API/UI round-trip/persistence preserved. Eligible battery tiers require SoC strictly above selected and protected floors, trusted energy/telemetry, context-dependent forecast and reserve evidence, actual import-cost permission, observed operator authority and physical limits. Existing ramp and Spike arithmetic remain unchanged.

Legacy Positive-FiT opt-ins cannot restore Low battery sale. Ordinary positive-FiT MSC and legitimate Solar Bypass retain PV-only behavior. Separately named policies, including Morning Dump and Evening Boost, retain independently guarded deliberate-export authority below Medium; they do not inherit authority from Low. Manual/Force retain operator ownership.

High/Spike may preempt an eligible Morning owner only with a positive bounded candidate after the shared actual import-cost check and all other guards pass. Failed candidates do not displace eligible Morning ownership; untrusted remaining forecast cannot manufacture an eligible Morning Slow owner. High/Spike retain context-dependent untrusted-tomorrow behavior and the daytime near-full measured-PV cap.

`battery_export_owner` records proposal provenance; `battery_export_final_owner` records the final decision owner and is `none` when export is blocked. A qualified proposal may remain visible under a cost veto or missing operator authority without granting discharge, export permission or Morning preemption. Value Gate remains advisory-only; `effective_battery_export_floor` remains a monetary floor, not SoC. Decision diagnostics are not proof of physical settlement.

## Preserved protections and open acceptance

The `.68` sequence remains mandatory: close export -> fresh trusted observed closure -> request MSC -> fresh exact MSC strictly after the request -> permitted reopening. Independent restrictive controls remain effective through uncertainty, fallback and restart. Preserve ordinary MSC, Solar eligibility/provider freshness/fill trajectory/physical relief, Morning, Demand Window import blocking, Manual/Force, forecast/reserve and physical-cap protections.

- **Phase 1 remains open.** Scoped `.67` Solar evidence for handover, physical relief/backoff and fill-deadline relinquishment remains recorded evidence; it does not close Evening Boost reserve/transition stability or Solar threshold-switching disposition. Those follow-ups remain explicitly deferred.
- **Phase 2 has scoped `.68` acceptance only.** The 13-second observation gap and any broader or unexercised live scenarios remain outstanding. Automated tests and accepted service calls cannot fill observation gaps.
- **Four-tier live acceptance is outstanding.** The completed code-audit GO does not establish safe physical behavior or complete physical/live acceptance.
- Further Evening Boost redesign, trusted non-positive-import redesign, Package 6B, experimental scheduling and later architecture/cleanup/GUI/Climate work remain parked under the roadmap; this package does not authorize them.

## Site tuning is not a software default
- Reported physical grid-connection export cap: **15 kW**; previously reported normal permission/PV MAX **25 kW**, Morning Slow near **2 kW**, Morning Dump SoC minimum **15%**, timing setting **1.0 hour** and Evening Boost **disabled**.
- Previously reported `solar_surplus_fill_deadline_margin_minutes=120` and Morning Slow physical export headroom 0.0 remain historical reports, not rechecked effective settings. Do not infer other effective settings from source defaults or change defaults to match site tuning.
- The physical inverter grid-export maximum is reportedly configured to **15 kW**, not freshly verified here. Legacy Force targets remain unchanged, including **25 kW**. Physical grid-export enforcement and ESS limits are separate controls; do not infer live enforcement from software targets or tests.
- No HA settings or inverter controls are written by this checkpoint.
## Current integrated local review candidate and remaining gates

Current worktree: `C:\Projects\sigenergy_optimizer-review`, branch `test/local-fix-integration`, base `9f3f02a5c1c82786c85026a3848574cca3cf891f`. Four reviewed changes are combined locally: Solar Override deliberate battery-backed export requires SoC strictly above selected and protected floors while preserving separate qualified PV-only MSC; early Morning Dump discharge EMS requires qualified `BATTERY_EXPORT` intent and positive bounded target, with explicit MSC fallback for blocked active Dump while preserving priority; application outcomes/exceptions are recorded without changing outcomes or actuator ordering; and positive FiT below 1¢ is described as below-minimum with precision near 1¢. Existing settings, thresholds, version markers and unrelated policies remain unchanged. Original component worktrees are preserved. Approved code-bearing commit `4e4b17c2d3bb362716d6b4e5ddb60659faf7beec` is pushed to `test/local-fix-integration` and covered by [draft PR #21](https://github.com/Belot77/sigenergy-optimizer/pull/21); no merge has occurred.

The earlier 1,070-test / 1,124-subtest combined pass predates the reproduced defect and is historical. After the approved correction, focused decision/floor checks passed 11 tests / 26 subtests (202 warnings, 1.16 seconds); independent Demand Window, Manual/Force, settlement and fallback checks passed 13 tests / 15 subtests (202 warnings, 4.79 seconds). Final combined offline validation passed **1,073 tests / 1,134 subtests, zero failures**, with 206 warnings in 170.97 seconds. Current `compileall app tests` passed using an isolated temporary cache. Pytest used `-q -p no:cacheprovider --disable-warnings --tb=short` with `PYTHONDONTWRITEBYTECODE=1` and `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`. These are offline results, not installation or physical-settlement proof. The approved code commit, branch push and draft PR creation are complete; further commits/pushes, merge, release and live acceptance remain separate approval gates.

The new fallback deliberately suppresses lower-priority EMS selection only while active Dump already blocks import. Qualified Dump keeps discharge priority; inactive-Dump behavior and authority/settlement remain unchanged. If this additional change regresses, revert only its early-Dump fallback delta, preserving the other reviewed fixes and all original worktrees. Original integration risks remain Solar floor closure, discharge intent gating, diagnostic retention/interpretation and reason wording. No settings, entities, API, versions, HA state or inverter controls changed.

The code commit, branch push and draft PR creation were separately approved and completed. Merge, release, deployment, installation and live actions are not authorized by this checkpoint. Any separately approved live acceptance must verify exact source/build, effective settings, observed authority, both Solar Override floors, Morning Dump floor, requested and observed EMS/import/export/ESS limits, physical flows, supervision, `.65` rollback readiness and stop/rollback conditions. Stage B remains **NO-GO for deployment**.

The approved roadmap order remains authoritative, including architecture, project cleanup and full GUI/UX work before Climate Manager integration. Climate Manager broadly works and is not the current priority. Before later authorised live work, verify effective settings/current authority and capture timestamped EMS, PV MAX, import/export ceilings, ESS limits, SoC, battery/PV/grid flows and reason/owner with explicit stop/rollback conditions.
