# Current State

Last consolidated: 2026-10-13

**CURRENT TRUTH ONLY:** durable semantics live in `CONTROL_CONTRACT.md`; sequencing lives in `ROADMAP.md`; historical decisions remain in `DECISIONS.md`.

## Live identity and rollback

- Last reported live: **2.3.58-haos69**, source `b90fdeafce5e40e206ffd17dce5e1a8c810519e6`. This is the operator-reported original .69 release, not a freshly verified HA/runtime observation. It supersedes the earlier current .68 and pre-release .69 descriptions.
- Known-good rollback remains **2.3.54-haos65**, source `9965e79133f38d5b9943dcf5a9b04ed6fdab1239`. Neither the original .69 release nor this local hotfix is promoted to known-good rollback.
- Scoped Phase 2 acceptance was reported for `.68`; its **13-second observation gap remains unproven**. The reported .69 identity supplies no additional physical/live acceptance evidence.
- The local code-bearing hotfix checkpoint is committed as `67fae5db2451fbf3e706b10cf4e2dbad07b38bd9` (`Fix Demand Window exact-full PV-only export under MSC`). No GitHub publication, independent committed-SHA GitHub audit, merge, release, deployment or hotfix live acceptance has occurred. No new hotfix version/tag is assigned and release metadata is unchanged.

## Active worktree and validation

- Worktree: `C:\Projects\sigenergy_optimizer-demand-window-hotfix`.
- Branch: `fix/demand-window-exact-full-pv-only`.
- Completed code-bearing checkpoint: `67fae5db2451fbf3e706b10cf4e2dbad07b38bd9`. This identifies the committed hotfix source, not necessarily the final branch HEAD after a subsequent documentation-only commit.
- The operator completed and verified the seven-file local commit: `CHANGELOG.md`, `app/optimizer.py`, `docs/AI_HANDOVER.md`, `docs/CHANGELOG.md`, `docs/CURRENT_STATE.md`, `docs/ROADMAP.md` and `tests/test_msc_baseline_overlay_contract.py`. Documentation follow-up preflight verified the expected branch, HEAD `67fae5db2451fbf3e706b10cf4e2dbad07b38bd9` and a clean worktree with no modified, staged or untracked files.
- This separate documentation-only follow-up changes only `docs/CURRENT_STATE.md`, `docs/AI_HANDOVER.md`, `docs/ROADMAP.md`, `docs/CHANGELOG.md` and root `CHANGELOG.md`. Production and tests are untouched; the completed code-bearing checkpoint remains identified independently of any later documentation-only HEAD.
- Targeted regression: `test_demand_window_exact_full_pv_only_export_contract` failed before the production correction and passed afterward, checking final decisions for Demand Window OFF, ON and untrusted states without weakening assertions.
- Independent protections: **466 tests / 611 subtests passed**, zero failures. Coverage includes Demand Window, exact-full/cheap-FiT, Manual/Force, MSC settlement, telemetry trust, actual import-cost guards, battery-export ownership, Morning and Solar policies.
- Final full suite after the hotfix, run once: **946 tests / 1,079 subtests passed**, zero failures, **206 warnings**. Compileall for `app`/`tests` with bytecode cache outside the worktree and `git diff --check` passed. These are retained results from the preceding hotfix validation; tests and compileall are not rerun for this documentation-only checkpoint.
- Missing local `Australia/Adelaide` timezone data caused UTC fallback in optimizer fixture logs. This is a test-environment limitation, not installed-timezone or live-behaviour proof. The full-suite warnings remain the recorded Pydantic deprecations.

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

Previously reported operator tuning was `grid_connection_export_limit_kw=15.0` and `solar_surplus_fill_deadline_margin_minutes=120`; software defaults remain **0.0** and **60** respectively. Morning Slow physical export headroom was reported at **0.0**, normal site export permission and PV MAX at 25 kW, and Morning Dump's operator floor at 15%. These are historical operator reports, not freshly verified current settings or authority to change defaults. No operator settings were queried or written for this checkpoint.

## Next approval and live-proof boundary

Next actions:

1. Review this five-file documentation correction.
2. Obtain separate approval for its local documentation-only commit.
3. Only afterward consider separately authorised GitHub push and independent committed-source review.
4. Retain explicit release/deployment and live-acceptance gates; commit or push approval does not authorise live work.

This task performs no staging, commit, push, tag, build, release, deployment, installation, restart or HA/inverter write.

The hotfix has no independent committed-SHA GitHub audit or live acceptance yet. Any later publication/release or controlled live work requires separate authorization, exact source/build identification, effective operator-setting/authority checks, .65 rollback readiness, supervision and explicit stop/rollback conditions. Monitor-only observation and controlled live acceptance must distinguish requested ceiling/intent from actual export, capture fresh timestamped actuator readbacks and physical flows, and retain all observed-settlement barriers. No live action is performed here.

Preserve roadmap dependencies and the open Phase 1/2 gates, including Evening Boost reserve/transition stability, Solar threshold-switching disposition, the unproven 13-second observation gap and unexercised four-tier scenarios. The original .69 release report and passing hotfix tests do not close those limitations.
