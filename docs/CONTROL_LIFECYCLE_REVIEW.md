# Cross-policy control lifecycle review

Date: 26-27 October 2026. This document retains the standalone O19 review and
validation history and records its inclusion in the cost/fallback integration.

Historical integration baseline: branch `fix/cost-fallback-integration` in
`C:\Projects\sigenergy_optimizer-cost-fallback`, based on verified main
`623bd5d95f757de1074cabc4ee25570f2ef80cfd`. The union is 25 files: one production
source, 15 tests and nine documents. It combines the approved unknown-cost
policy with O19's fallback Demand Window recheck, without additional control
logic. The original cost and O19 candidate worktrees remain preserved.
The combined offline suite passed 1,499 tests / 1,429 subtests, zero failures; independent source/test review was GO for local integration and characterization only. The integration-only O21 finding is historical; see the local correction for current status. No commit, push, release, HA installation or live action is included.

The historical tests-only checkpoint continued the specifically proposed
`test/cross-policy-control-lifecycle` branch. Workspace:
`C:\Projects\sigenergy_optimizer-control-lifecycle`. Verified repository:
`https://github.com/Belot77/sigenergy-optimizer`. Freshly fetched baseline:
`623bd5d95f757de1074cabc4ee25570f2ef80cfd`, tree
`6b4abd537e9bb6b43f95e9f6e6e48fe15e6235a9`.
Production code matches published .81 source
`247095a4f9905932c3f5716f3d1be6cee7b3c7f8`; main adds the six-document receipt.
Original unfinished worktrees remain preserved.

That preserved tests-only checkpoint changed no production code. The later
operator continuation authorizes local `fix/fallback-demand-revalidation` in
`C:\Projects\sigenergy_optimizer-fallback-demand`, based on the same verified
main. All seven reviewed files were transferred byte-for-byte before correction;
the original worktree remains intact. That O19 candidate's production scope was solely
its current-Demand fallback guard and conflicting report rejection. Configuration,
version markers and permanent AGENTS instructions remain unchanged.

No commit, push, merge, publication, HA access, installation or live settings
change is included. The tests are synthetic; they do not prove physical inverter
acceptance or reconstruct an entire live day.

## O19 fallback Demand Window implementation in the integration candidate

Before the correction, fallback reused initial Demand OFF across awaited
settlement and could reopen import after live fake HA changed to ON. The new
guard is in the shared numeric dispatcher only for a positive fallback import
recovery request. Demand is included in the existing joint read alongside
operator authority, Remote EMS, MSC and export evidence.

After that read, a finite-age, provenance-backed exact OFF report under the
existing 360-second Demand boundary is required for permissive import recovery.
A late ON, missing/malformed state, stale or invalid timestamp, or conflicting
bulk/report evidence instead requests 0.01 kW import through the same
restrictive dispatcher. That request performs another current-authority read;
Manual/Force takeover or lost Remote EMS prevents an automatic close. The
recursive close is bounded because a restrictive 0.01 request has no fallback
recovery tuple and cannot enter this guard again.

This independent close may proceed without waiting for MSC/export recovery
proof, while any actual opening still requires that proof. Existing initial
Demand/Standby/Dump import ownership is never relaxed by a later OFF report.
Other ESS/PV recovery remains independently bounded. Primary application status
remains failed even when fallback safely succeeds with import held closed.
Success wording refers to independently permitted house-serving capabilities,
rather than implying all normal capabilities were restored.

## Local O21 fallback correction - 27 October 2026

A local, unreleased correction restores only bounded MSC house-serving ESS
discharge after a failed battery-export attempt and verified fallback closure.
Current authority and fresh export-close/MSC proof remain mandatory. Ordinary
export-target checks, independent decision limits and normal capability bounds
remain. The original application stays failed even when fallback succeeds.

The guarded full suite passed 1,504 tests / 1,439 subtests, zero failures.
Independent source/test review is GO for the local correction. O21 is locally
verified; publication and physical acceptance remain separate. Capability and
policy values retain decision-time snapshot semantics; no after-await refresh
is added. See CURRENT_STATE.md for exact scope, results and approval boundaries.


Historical O21 integration baseline (superseded by the local correction): Three separate scripted cases exercise current Demand ON, unknown, and trusted OFF. In each, the positive BATTERY_EXPORT proposal fails; the post-request EXPORT close is 0.01 kW and exact MSC proof is present. ON and unknown keep import closed; trusted OFF permits the fixture's 13.25 kW import recovery. Independently, normal Automated ESS discharge-capability restoration is rejected because the original GRID-EXPORT target (25 kW in this fixture) does not match current EXPORT 0.01 kW. `result.succeeded` and `fallback_succeeded` are false, with error `normal Automated ESS discharge capability returned failure`; ESS discharge capability remains 0.01 kW. These fixture values are not site configuration or physical-operation evidence. That integration-only baseline contained no source correction. Track as O21 (Medium: incomplete ESS discharge recovery after failed battery export), which blocked release readiness at the integration checkpoint. This issue is not assigned to O5 overnight reserve or O9 obsolete/overlapping policies.

This limitation is separate from the O19 Demand guard: ON or untrusted current Demand still requires the restrictive close; trusted OFF permits a recovery attempt only after existing authority and settlement checks. It does not change known-price cost-floor policy, accounting truth, or physical safeguards.

Demand is also included in existing correlated metadata-conflict rejection.
An old bulk OFF cannot gain authority from newer conflicting ON metadata.
Normal Demand reading becomes conservative on that same explicit conflict.
Metadata enrichment failure does not invent a new blanket veto: a genuinely
recent `last_updated` may still qualify under the existing fallback semantics;
an old change time cannot be refreshed using unverified REST `last_reported`.

No standalone Demand Window request, timer, threshold, tolerance, persistent
state or charging/export priority is added. Fallback import recovery adds Demand
to its existing dispatch-evidence read. A rejected opening uses the existing
restrictive dispatcher, including its separate current-authority check. The new
guard does not cover all ordinary import openings or guarantee zero physical
transient import.

Risk: excessive rejection could unnecessarily withhold legitimate recovery,
while a missed late veto could reopen import. The focused matrix covers both.
Rollback is to withhold this uncommitted branch or later revert only O19's
guard/conflict handling; do not discard the preserved lifecycle tests or other
unfinished work. O20 and the future non-positive-price redesign remain separate.

### Historical standalone O19 validation

The following results belong to the separate O19 candidate worktree, not the
combined cost/fallback integration. Its combined offline suite passed; see `CURRENT_STATE.md`. The integration-only O21 finding is historical; see the local correction for current status.

- Tests-first red: 10 expected failures, 2 passed, 202 warnings, 1.28 seconds;
  four failing test methods and six failing subcases exposed the missing guard.
- Final focused fallback checks: **45 tests / 17 subtests passed**, 202 warnings,
  67.25 seconds. This author-run result covers the new regression module and
  existing Phase 1 fallback module after final reviewer hardening.
- Final related 15-module checks: **308 tests / 268 subtests passed**, zero
  failures, 202 warnings, 90.53 seconds. The first related run had two legacy
  fixture failures: recovery was expected without a current fake Demand OFF
  observation. Three explicit setup lines supplied that evidence; assertions
  and settlement checks were unchanged.
- The first full-suite run returned two failed MSC-provenance subcases,
  1,477 tests and 1,424 subtests passed, 206 warnings, in 244.77 seconds.
  That separate legacy matrix also lacked a live Demand observation. One OFF
  seed inside its existing patched clock corrected the fixture without changing
  MSC/export reports, request boundaries, scenarios or assertions. Its focused
  rerun passed **1 test / 11 subtests**, 202 warnings, in 3.35 seconds.
- Final full offline suite: **1,477 tests / 1,426 subtests passed**, zero
  failures, 206 warnings, in **244.15 seconds**. This run includes the final
  one-line MSC fixture correction and all current production/test changes.
  No further production edits followed validation.
- Independent read-only design/source/safety review, final regression review,
  the one-line MSC fixture review and documentation wording review are **GO**.
  The reviewers inspected the delta; no independently rerun full suite is claimed.
- Validation disabled dotenv, bytecode and pytest cache. A validation-only
  StateStore constructor guard rejected every path outside memory/system
  temporary storage. The related run admitted 3 memory and 442 temporary store
  constructions; each full run admitted 74 and 1,775. This is not a
  production storage change. The earlier default-database incident below remains
  unresolved; no database contents were inspected or exported for this work.
- The standalone O19 source checkpoint had thirteen unstaged/uncommitted files:
  one production
  file, five test files and seven documentation files. Only _apply and
  _enrich_state_report_metadata differ in the optimizer AST; all other
  optimizer methods, permanent instructions and release/configuration files
  remained unchanged in that candidate. The original seven-file lifecycle
  checkpoint retains its exact fingerprint. The integration branch is the
  separate 25-file union noted above. No commit, push, version bump or live
  action occurred.

The retained tests-only results below describe their historical fixture and
source version. Offline dispatch permission and report trust do not establish
physical acceptance.

## Verification boundaries and later operator checks

No HA connection, installation or live setting change was performed here.

- Monitor-only: inspect the installed build identity, existing Demand report
  provenance, authority, application outcome and requested/observed limits without
  sending commands. Passive observations alone cannot exercise a fallback race.
- Offline dry-run: use the temporary-data fake-HA regression matrix to change
  Demand during settlement and the final joint read. Verify withheld openings,
  independently authorized closes and unchanged legitimate OFF recovery. This
  is test replay, not a new global production dry-run setting.
- Separately approved supervised live acceptance: first verify exact source,
  effective settings, authority, report cadence and a usable rollback method.
  Compare requested import limit, provenance-backed readback and measured grid
  flow during naturally occurring fallback/recovery. Do not force an unsafe
  Demand transition or infer zero physical import from an accepted close call.
  Stop the trial on an unexpected opening, lost ownership, failed settlement or
  repeated recovery failure; return to the operator's chosen safe mode through
  authorized controls. No live acceptance is claimed by passing offline tests.

## Scope and architecture assessment

Targeted review covered the central state/decision model, live observation
provenance, proposal/final-owner arbitration, charge allocation, application,
MSC settlement/fallback, and relevant characterization tests. It is not a full
repository or security audit.

The system already has a single central Decision and a serialized control lock.
Morning Dump, Morning Slow, Solar Surplus and Evening Boost are not four
independent writers. The weakness is the coupling within the shared pipeline:

1. The state reader obtains readings and report provenance.
2. Policy calculations qualify proposals and calculate reserves/forecast opportunity.
3. Arbitration selects export ownership; import and ESS ownership are calculated
   separately, with independent restrictions.
4. Application rechecks authority/settlement and may withhold, modify or recover
   requested outputs.
5. Application outcome determines which process-local qualifications survive.
6. Cached policy status, attempted commands, observed settings and measured flow
   represent different stages.

The `_decide` header describes pure logic, but the implementation updates
provider, relief and qualification state. That is an architectural boundary to
make explicit, not proof those state machines can be deleted. Some control
handoff data is carried in `trace_gates` and `trace_values`; necessary control
fields should eventually become explicit typed plan fields. The new .81 passive
`charge_allocation` object remains diagnostic only.

The prior roadmap already requires a control-ownership audit before architecture
consolidation. This continuation authorizes the scoped review and tests, not
wholesale restructuring or merging the old refactor branch.

## Owner and interaction map

This is a domain map, not a single unconditional priority list.

| Policy/owner | Owned control or restriction | Important interaction |
| --- | --- | --- |
| Manual/Force | Operator-owned requested controls | Automated control yields to verified takeover; no automatic reinterpretation of operator targets. |
| Demand Window | Independent import block; unknown observation also blocks | Must remain effective during normal application and fallback recovery. |
| Morning Dump | Qualified deliberate battery export, discharge EMS and import close | Subject to floor, refill feasibility, final export intent/target and independent restrictions. High/Spike may genuinely preempt it. |
| Morning Slow | Restricted ESS charge request, or qualified release to normal safe charging; MSC | Does not own battery export. Export permission is independently selected. Its completion can arm Solar restrictive-charge qualification. |
| Solar Surplus/bypass | PV-only MSC export permission; separately qualified dynamic ESS charge restriction | Export eligibility and charge authority are distinct. Flow failure can reset relief to baseline; provider/handoff authority loss can restore normal charging. |
| Evening Boost | Qualified deliberate battery export above protected reserves | Admission requires its existing load-report proof. Higher-priority owners and independent cost/authority protections remain effective. |
| Battery-export tiers | Qualified deliberate export proposal/final ownership | High/Spike can preempt Morning only after positive bounded proposal and the same actual-cost/Automated permission used for execution. Medium/Low do not gain that Morning preemption. |
| Fallback | Temporary export/ESS restrictions and later bounded recovery | It must not remove independent import/PV/ESS restrictions or create export ownership. |

The Solar opposite outcomes are existing local rules, not a newly proven cause
of every live incident: invalid physical feedback resets earned charging relief,
often toward a zero baseline; lost restrictive-charge authority restores the
otherwise safe normal charging request. A coherent allocation objective needs
to cover both outcomes, forecast downgrades and the transition between owners.

## Findings by severity

### O19 - Medium: historical baseline fallback import race; local correction above

Confirmed with the existing fake-HA application harness. The initial decision
contains trusted Demand OFF. While fallback awaits MSC settlement, the fake live
Demand Window changes to ON. Fallback then writes a normal 13.25 kW grid-import
limit and reports success without rereading that entity after the change.

At baseline, `app/optimizer.py:7390` captures `independent_import_blocked` from
the earlier state. Settlement awaits at lines 7423-7444 precede permissive import
recovery at lines 7453-7463. Dispatch refreshes operator/Remote EMS authority and
export/MSC settlement, but does not refresh Demand Window for this opening.
This conflicts with `CONTROL_CONTRACT.md`'s independent fallback restrictions.

This is a software import-permission race, separate from the operator-deferred
brief physical import spikes. It proves neither an on-site occurrence nor
actual grid flow. Durable test cases and their exact scope are recorded below.

The local correction above implements the narrow current Demand Window guard
before permissive fallback import recovery. It preserves unknown-state blocking,
independent owners, current operator authority and request-specific settlement.
Ordinary economic-zero import does not become a persistent safety owner. The
regression matrix covers report loss/staleness, initial/late ON, legitimate OFF
recovery and takeover during both awaited authority boundaries. HA can change
again after a read; no software read/command sequence guarantees zero physical
transient import.

Risk: an incorrect guard could permit import or unnecessarily block legitimate
recovery. Withhold the local patch or use a later scoped revert; do not reset
worktrees or alter live controls.

### O20 - Medium: negative-price Morning Dump has conflicting final outputs

Two independent in-memory decision reproductions used the existing Morning Dump
fixture. For trusted actual import price -$0.05/kWh and FiT $0.05/kWh, the result
is Morning Dump active, `BATTERY_EXPORT`, 25 kW export permission, zero import
permission and `Command Discharging (PV First)`, but ESS discharge is limited to
0.01 kW. PV MAX is 0.1 kW. Estimated-negative and actual-positive controls retain
normal discharge capability in that fixture.

The exact fixture capabilities are 25 kW; these are requested values, not a
new site configuration or proof of physical 25 kW export. The contradiction is
deliberate discharge intent/mode combined with effectively blocked discharge.
PV curtailment is an explicitly preserved independent negative-price restriction;
do not infer that it should be removed.

At baseline, `app/optimizer.py:10642` gives qualified Dump EMS priority, while
lines 10790-10791 apply the negative-price discharge clamp without the final
owner. Existing tests at `test_morning_dump_export_intent.py:98` check
owner/intent/EMS/import but omit the full discharge/PV output combination.

Do not automatically exempt Dump from the clamp. The recorded decision at
`DECISIONS.md:115` and `CONTROL_CONTRACT.md:474` specifies a future trusted actual
non-positive-price charging owner that overrides Dump/Slow, but explicitly says
it is not implemented; its redesign remains parked in CURRENT_STATE. Exact-zero
import with extreme export value and PV MAX policy are unresolved. Reconcile
that existing decision and sequencing before a production priority change.
These tests characterize current behavior; they do not activate the future policy.

Risk: an overly broad exemption could enable unintended battery discharge, while
unreviewed preemption could alter Morning behavior. Keep the O20 characterization
local; any O20 production change requires its own approved scope and rollback.

### O21 baseline - Medium: incomplete ESS recovery (locally corrected)

Three separate scripted cases use trusted Demand ON, unknown, and trusted OFF. In all three, a positive `BATTERY_EXPORT` proposal fails, post-request `EXPORT` close is 0.01 kW, and exact MSC proof is present. With ON or unknown, import remains closed; trusted OFF permits the fixture's 13.25 kW import recovery.

The independent normal Automated ESS discharge-capability restore is rejected because the original `GRID-EXPORT` target (25 kW in this fixture) does not match current `EXPORT` 0.01 kW. `result.succeeded` and `fallback_succeeded` are false; the exact error is `normal Automated ESS discharge capability returned failure`. ESS discharge capability remains 0.01 kW. These are scripted fixture values, not site configuration or physical-operation evidence.

This is a conservative incomplete house-serving recovery defect, not proof of physical harm. No source correction is included in this integration. O21 was open in that integration baseline; see the local correction and validation for current status. Do not place it under O5 (overnight reserve) or O9 (obsolete/overlapping policies).

### Design debt and test coverage

- Raw eligibility/activity, final owner, successful application, setting readback
  and physical flow must remain distinguishable. A failed tick may retain the
  prior cached policy after partial writes; a generic successful pause need not
  mean automatic actuation occurred.
- Existing topic-specific tests include handoffs, re-entry, authority and fallback.
  In the inspected set, no single chronological shared-state sequence covered
  all four feature phases through the reader/application boundary.
- Legacy hand-built SolarState fixtures intentionally permit optional trust
  markers to remain None. They are useful decision-policy tests, but do not
  stand in for positive live provenance. Live Solar feedback requires
  `live_snapshot`, coherent advancing report times and explicit trusted evidence.
- Complete-output assertions must cover EMS, export intent/owner, import/export,
  PV MAX and ESS charge/discharge together, not just one feature's activity flag.
- Provider/re-entry/settlement guards protect different claims. Consolidation
  should clarify their purpose and ownership rather than give every datum one
  generic freshness rule or remove all qualification.

### Observed coupling: pending MSC transitions and later battery-sale permission

The historical standalone O19 test-only checkpoint recorded the then-current
behavior: a pending Morning-to-MSC transition invalidated import-cost coverage
as `application_not_confirmed`, after which unknown cost could veto Evening
Boost. That characterization predates the approved cost-policy change and is
not the policy for this combined branch.

In the integration, unknown-only cost remains logged as warning/context and must
not itself veto a qualified Boost. Do not reseed accounting coverage or infer
zero import. A pending application may separately leave authority/permission or
settlement unproven; those independent safety gates still apply. The combined
two-day lifecycle test must retain unknown accounting state while confirming
Boost admission only when all independent qualification and permission gates
pass. Combined offline tests passed; O21 was unfixed at that historical integration checkpoint; see the local correction for current status. No physical Boost behavior is established.

## Test-isolation incident

One preliminary negative-price test run mistakenly cleared `STATE_DB_PATH`
after the fixture had installed its temporary path. It therefore used the default
`C:\data\optimizer_state.db`. Metadata shows that file predates this task
(creation 1 April 2026), with last write 26 October 2026 at 08:29:11.9554622 UTC
and size 147,456 bytes at inspection. The test run wrote to existing local
development storage; the exact prior rows and impact are unverified.

The fixture was corrected to isolate environment variables before installing its
temporary database, and to disable dotenv explicitly. No database contents were
inspected, exported or committed. The existing file is preserved; no deletion or
unverified restoration was attempted. No HA connection or live control occurred.
A later validation guard must reject database paths outside temporary storage or
`:memory:`. This limitation must remain visible in handover and the completion report.

## Historical tests-only validation checkpoint

Final focused validation: **7 tests / 7 subtests passed**, zero failures,
202 existing warnings, in **0.92 seconds**. Independent review of all three
modules after fixture corrections is **GO**; the reviewer inspected source and
fixtures but did not independently rerun these tests.

| New test module | Tests / subtests | Boundary exercised |
| --- | --- | --- |
| `test_cross_policy_control_lifecycle.py` | 3 / 0 | One optimizer through selected Dump/MSC/Slow/Solar/Boost checkpoints; real reader/tick/decision/application; separate covered-history Boost admission, Manual pause/return and interrupted load qualification. |
| `test_cross_policy_fallback_demand_characterization.py` | 3 / 2 | Real application/fallback, Demand changes to ON/unknown/unavailable during settlement, and steady-OFF recovery control. |
| `test_cross_policy_negative_price_characterization.py` | 1 / 5 | Complete Decision outputs for actual/estimated negative, positive, blocked-FiT and inactive-Dump cases, with Demand Window observed OFF. |

A broader combined run passed **295 tests / 253 subtests**, zero failures,
202 existing warnings, in **91.07 seconds**. It comprised these seven tests plus
288 related tests / 246 subtests covering Dump, Boost reserve/re-entry, Morning/
Solar handoff, Solar qualification/application, authority, live provenance,
dynamic charging, physical relief and fallback. That earlier run used the first
lifecycle fixture, before independent review corrected a future afternoon seed
and its initialization timezone. It is retained as the related-test checkpoint,
not claimed as a run of the final lifecycle fixture. All seven new tests were
rerun successfully after both corrections. No full suite was run.

Final fixture and validation limits:

- Exactly one initial synthetic midnight-to-06:00 accounting seed is installed.
  The fixed synthetic local offset is set before optimizer construction/seed,
  rather than changing accounting timezone afterward. This clock fixture does
  not test DST, the host timezone database or installed HA timezone settings.
- Explicit inactive ledger samples bridge skipped wall-clock checkpoints using
  the same real ledger. Measured flows, SoC, available energy and forecasts are
  prescribed assumptions, not results of a physical battery/PV simulation.
  Coverage is not reseeded after a pending application.
- The same-instance Morning-to-Solar-to-evening sequence retains the genuine
  pending-transition cost-history block. It does not demonstrate admitted Boost
  after that earlier pending transition. Separate covered-history evening
  scenarios exercise real admission and interrupted qualification.
- Real `_read_state`, `_decide`, `_apply`, `_tick` and control/accounting helpers
  remain in use. Only wall/monotonic clocks, initialization timezone lookup,
  unrelated publications/history and trace capture are scripted or suppressed.
- Accepted fake commands are queued separately from reports. Scripted readbacks
  are strictly later than requests; unchanged load retains old `last_updated`
  while correlated `last_reported` advances. No fake readback proves hardware
  settlement.
- All final checks disabled dotenv, bytecode and pytest cache. A validation-only
  StateStore constructor guard rejected every path outside `:memory:` or the
  system temporary directory. The broad run admitted 3 memory and 420 temporary
  store constructions; final focused run admitted 3 memory and 9 temporary ones.
  This guard was in the validation runner, not a production code change.
- Earlier fixture corrections and failed setup runs are not production fixes or
  physical reproductions. Passing current-behavior tests does not close O19/O20;
  their expectations must change alongside a later approved production correction.

Independent documentation review is GO. Final syntax, whitespace and exact
seven-file scope checks pass: three new test modules and four documentation
files. Production, configuration, version markers, AGENTS and the durable control
contract remain unchanged. The branch is uncommitted and unstaged; no commit,
push or publication is part of this checkpoint.

## Staged engineering sequence

1. Preserve the two reproductions and add a shared chronological lifecycle with
   real reader/application seams, explicit fake report provenance, complete
   outputs, Manual takeover and application-result retention checks.
2. Independently review fixtures and run focused related tests. State exactly
   which policy, timing and application paths are real or scripted.
3. The approved local O19 correction and its independent source/test review are
   complete, with legitimate recovery and independent restrictions retained.
   Commit, integration, publication and physical acceptance remain separate.
4. Reconcile negative-price Morning priority with the approved-but-parked design.
   Keep unresolved zero-price/PV questions separate; do not silently remove clamps.
5. Define O18 allocation/fill robustness against forecast downgrades and the
   export-versus-charging tradeoff. No new meter tolerance is justified yet.
6. Extract typed ownership/plan and application boundaries incrementally against
   characterization coverage. Preserve authority, reserve, hardware and settlement
   safeguards; do not merge an old refactor wholesale.

O5 reserve policy, broader O6 and O18 remain open. O11 and the brief physical
Demand Window investigation remain parked. Publication and physical acceptance
remain separate from every local engineering checkpoint.

Rollback for this branch: withhold the uncommitted O19 production patch or later
revert only its fallback guard and Demand metadata-conflict handling. Preserve
the characterization tests, documentation and original lifecycle worktree; no
reset, deletion or live control change is required.
