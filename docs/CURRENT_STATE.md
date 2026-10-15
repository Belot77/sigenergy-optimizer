# Current State

Last consolidated: 2026-10-15

**CURRENT TRUTH ONLY:** durable semantics live in `CONTROL_CONTRACT.md`; sequencing lives in `ROADMAP.md`; historical decisions remain in `DECISIONS.md`.

## Live identity and rollback
- Last **operator-reported** live release: **2.3.59-haos70**, source `08f4daf53941bd850a4fe392b458c42b1df68b47`. This is not a new Home Assistant/runtime verification. Stage A introduced no installed-system changes.
- Protected known-good rollback: **2.3.54-haos65**, source `9965e79133f38d5b9943dcf5a9b04ed6fdab1239`. Do not promote .70 to known-good without supervised live acceptance.
- Morning Dump physically activated on 15 October; minimum SoC deliberately set to 15%, and timing option set to 1.0 hour before sunrise (existing implementation runs from sunrise through one hour afterward). Morning Slow was observed near 2 kW and physical export near 15 kW. Evening Boost disabled. Approximate 15 October PV forecast: 130 kWh. These are reported observations/settings, not renewed authority verification.
- Phase 1 remains open, including exact-full Demand Window PV-only physical proof, Evening Boost reserve/transition stability and Solar threshold-switching disposition. Phase 2 retains only scoped .68 acceptance; a 13-second observation gap and broader cases remain unproven. Four-tier and .70 physical acceptance remain outstanding.
- Preserve .65 rollback readiness before any later supervised live testing. Passing tests and successful service calls do not prove inverter settlement.
## Active worktree and validation
- Current Stage A worktree: `C:\Projects\sigenergy_optimizer-authority-stage-a`; branch `test/control-authority-safety-characterization`; pre-checkpoint base HEAD `08f4daf53941bd850a4fe392b458c42b1df68b47`. After the approved local checkpoint, read Git HEAD for the new commit SHA. No push, merge, release, deploy or HA/inverter action is authorised.
- Stage A scope: modified `tests/test_phase1_d7_liveness_characterization.py` (22 additions/1 deletion), new `tests/test_control_authority_safety_characterization.py` (47,885 bytes), and this document plus `docs/AI_HANDOVER.md`.
- Stage A tests-only characterization **GO**, independently accepted on 15 October: corrected characterization **25 passed, 47 deliberately red**, corrected D7 test passed, recent independent protections **77 tests/89 subtests passed**, zero unexpected failures, AST/whitespace checks passed. The earlier baseline yielded 311 existing tests/409 subtests passed. No Stage A full-suite rerun was required.
- The 47 red cases are deliberately executable regressions exposing known baseline authority/actuator safety defects. Do not skip, xfail, delete or weaken them. A non-green isolated Stage A branch is expected; do not merge into a branch requiring green CI until Stage B resolves the defects.
- The seven initial review weaknesses (authority continuation, ESS restriction independence, unknown-vs-Manual, expiry during awaits, dispatch/refresh timing, Force ownership, restart/metadata evidence) were corrected and independently accepted. Fixture E reproduced unsafe boundary T+1/report T+2/dispatch T+3 versus valid report T+2/boundary-and-dispatch T+3 through the real waiter.
- Protected reference worktree: `C:\Projects\sigenergy_optimizer-evening-priority`, branch `test/evening-medium-priority-characterization`, base HEAD `08f4daf...`, containing exactly ten intentionally dirty files. This is **NO-GO for production, commit or deployment**. Never reset, stash, discard, overwrite, commit, delete or copy its optimizer file wholesale. Stage A checkpoint does not touch it.
- Stage B production authority/actuator repair **not yet approved**. Preserve verified Automated / Unknown / confirmed Manual-or-Force distinctions, request-time and application-time authority, dispatch boundaries, independent Demand/ESS/PV restrictions, observed settlement, fallback and safe operator ownership. Preserve unattended restart auto-enable with current Automated verification; no new persistent OFF database or mandatory handback redesign.
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
- No HA settings or inverter controls were written in Stage A.
## Next approval and live-proof boundary
1. Stage A is a local, isolated **tests + docs checkpoint only**; current branch HEAD after commit identifies that checkpoint. No push, merge, installation, restart or HA/inverter write is included.
2. Scope Stage B **separately**; no Stage B production write is authorised by this checkpoint. Candidate core scope: `app/optimizer.py`, `app/ha_client.py`, necessary targeted tests. Additional files/API wiring require demonstrated need and separate approval.
3. Stage B must satisfy the 47 red authority/settlement regressions while preserving the reviewed narrow Medium-over-Evening Boost priority hunk and established startup/manual behaviour; no wholesale transfer from the protected worktree.
4. Stage B validation: Stage A regressions, independent Manual/Force, Demand, MSC, Solar, Morning, fallback, reconnect and responsiveness protections; one final full suite, compileall, diff check and independent safety review. Stop on unexpected failures; never weaken protection tests.
5. Before any later live acceptance: obtain separate installation approval; preserve .65 rollback, current authority, effective site settings and timestamped inverter evidence (EMS, PV MAX, import/export ceilings, ESS limits, SoC, battery/PV/grid flows, reason/owner). Service-call success does not establish physical settlement.
6. Roadmap order remains outstanding Phase 1 physical proof, Phase 2 transition safety, short control-ownership audit, Climate Manager integration, then diagnostics/replay/experimental solar scheduling.
