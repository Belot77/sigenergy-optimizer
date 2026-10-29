# Control Contract

This document defines durable approved control semantics, not current implementation status. Current commits, test counts, and immediate work belong in `CURRENT_STATE.md`.

## Import-cost policy with incomplete history

Incomplete accounting coverage or unpriced import by itself is advisory: it
must not veto an otherwise-qualified automatic battery-backed export. When the
existing shared summary contains finite recorded actual import prices, their
highest value remains the cost floor even while coverage is incomplete; zero
and negative finite prices are valid, and no weighted average is used. With
incomplete history, that known maximum is only a lower bound on the true daily
maximum. A deferred summary/cache miss or storage/query failure may leave no
known price available, in which case unknown cost warns and does not veto. This
policy adds no last-known-price cache. Unknown coverage remains unknown in the
ledger and UI context, including its sticky day marker and reconciliation
state. A successful later write does not reconstruct missing intervals or
establish that no import occurred.

The actual import-cost guard can report `active` while cost is unknown because
it also supplies the existing PV-only clamp context. `blocking` describes an
actual veto from a known priced floor. The classic Value Gate remains
advisory-only: stored-energy and reserve analysis and known-price comparisons
continue, while unknown cost alone warns. Manual/Force exemptions remain as
defined elsewhere. Physical protection is
unchanged: authority, permissions, MSC settlement, reserves, flow validation,
Demand Window behavior, PV-only limits and the 120-second Evening Boost
qualification continue to apply. The accepted financial risk is that imported
energy without a known cost can be exported at a loss. Existing UI reason text
may expose the warning; no new UI setting is part of this policy.

## Application outcome trace metadata

Application-outcome metadata is diagnostic only. `application.status` is `succeeded`, `pending`, `failed`, `exception`, or `unreported`; `application.succeeded` is true/false/null. `transition_phase` is `close`, `msc`, or `unknown` only while pending, and null otherwise. `fallback_attempted` and `fallback_succeeded` describe fallback activity. These fields record the application helper's returned result or an ordinary raised application exception; they do not establish whole-cycle success, actuator readback, or physical settlement. A `succeeded` outcome means only that the helper returned success, including a no-op or manual pause. The internal `_ActuatorApplicationResult.transition_pending` flag marks only an intentional wait returned without restriction-write errors; it is not a separate JSON field and it does not redefine existing `succeeded=False` or control-exception behavior. Pending/failed application attempts do not replace the committed decision.

Accepted restrictive-settlement attempts add an optional `application.restrictive_settlement` object with `pending`, `purpose`, `cause`, and `deadline_monotonic`. `purpose` is `ordinary_close`, `fallback`, or `ordinary_close_retry`; `ordinary_close_retry` is a protocol subtype for a renewed ordinary-close-origin attempt, not a third eligibility origin. `cause` is retained from the bounded identifiers `ordinary_close_unobserved` or `accepted_discharge_target_unobserved`. The object is distinct from `transition_phase` and `transition_pending`; existing `application.status` remains `pending` during an intentional wait and reports failure/exception under its existing rules. The monotonic deadline is diagnostic, process-local evidence only: it cannot extend authority, survive restart as control state, or prove physical response. Raw `result.error` and exception text remain omitted. Missing metadata on historical rows means unknown. Trace recording failure must not stop control.

### Passive charge-allocation evidence

New trace rows include an additive `charge_allocation` object. Existing request,
state, gate, value and application fields retain their meanings. Historical rows
without this object contain unknown evidence; no archive migration or backfill is
performed. The status UI still uses its existing committed-state semantics.

`snapshot_phase=pre_application` and `snapshot_timestamp` identify the decision's
input state. `ess_charge_limit_readback` retains the configured HA charge-limit
entity's reported number and provenance independently of the requested ceiling
in `summary.ess_charge_limit_kw`. It does not infer an unknown setting from the
legacy numeric zero default, and does not establish that the inverter obeyed it.
The existing legacy `current_ess_charge_limit` control value is unchanged.

`flows` contains `pv`, `load`, `grid_import`, `grid_export` and `battery`.
Each observation and the charge-limit readback contain `value_kw`, `available`,
`fresh` and `reported_at_ts`. Missing or nonfinite values become null with false
availability/freshness. A finite stale reading remains visible with `fresh=false`.
Freshness is the flag at state-read time, not a new check at trace-recording time.
ESS provenance uses the existing bulk response; no independent metadata request
is added. An unchanged entity can therefore conservatively appear stale.
Report timestamps are HA metadata, not proof of simultaneous physical samples.
Battery sign and unit conversion retain the existing configured reader semantics:
positive battery power means charging after that conversion. No entity IDs or
configuration secrets are added by this object.

`derived_balance_kw` is signed PV plus import minus export minus load, only when
all four directional observations are available, finite and nonnegative. It may
be negative and may use stale readings; their individual flags remain visible.
It is diagnostic arithmetic, not a new balance tolerance, trust gate, hidden-PV
estimate or permission to charge/discharge. Missing/invalid components or an
overflowed result produce null.

`solar_feedback_before_evaluation` copies the prior Solar feedback command before
this evaluation can reset it. `solar_feedback_at_recording` describes the armed
feedback state when this row is built, which may precede later failure cleanup.
Both contain `command_kw` and `acknowledged_at_ts`, with null for unknown fields.
The timestamp is Solar's feedback boundary after a successful charge-write
response; it is not ESS readback, physical settlement or a full actuator-write
history. Reasserting an unchanged command retains the existing boundary.

These fields are passive. They add no HA request or actuator write, change no
control authority or safety condition, and remain inside diagnostic failure
isolation. In particular, negative balance still rejects physical relief, and
normal charging recovery still requires the existing ownership/settlement gates.

Update this contract whenever an approved control-ownership rule, invariant, or transition contract changes. Do not change it merely to match accidental current code behavior; report the mismatch and obtain an approved semantic decision first.

## Runtime configuration activation

Runtime single and batch configuration updates validate, optionally persist and activate under the same control lock as a complete automatic or Manual/Force application and direct ESS writes. Activation cannot split an awaited control operation between old authority evidence and new actuator bindings. Validation uses the configuration active after waiting. Failed persistence or cancellation while waiting does not activate changes. Queued configuration and direct ESS requests must still pass mutation authorization after acquiring the lock.

A changed evidence identity retires old number-settlement requests, MSC baseline proof, cached telemetry/decisions and permissive Solar/Boost qualification. It refreshes the existing shared entity watch set. Current identity evidence must satisfy the existing authority and settlement gates before permissive recovery. A pending MSC transition retains its close barrier with retired old request proof; clearing configuration evidence must not turn an unfinished transition into completion.

Preserve authenticated Manual/Force requests and explicit ESS overrides, independent restrictive owners and the snapshotted entry floor of an active Standby Holdoff, including consecutive activations before another decision. A newly bound selector's historical differing value cannot supersede a pending authenticated request: coherent transition evidence must be strictly later than both the request and ownership-identity activation. A verified later operator choice can still supersede it. A queued manual selection is rejected before dispatch if its selector or ownership-label interpretation changed while waiting; renamed or swapped labels cannot silently reinterpret operator intent.

Changing an unrelated policy value or saving an unchanged identity does not retire identity-bound proof. HA HTTP/WebSocket connections keep their existing startup-bound settings; this contract introduces no client reconstruction, automatic restart, new policy priority or permission to alter live settings.

## State-store execution and accounting evidence

Production database initialization, lock acquisition, queries, commits and close
execute on one lifecycle-owned storage worker, with bounded admission and async
waiting. StateStore schema and atomic interval/checkpoint/coverage transactions
retain their existing semantics. Standalone offline construction keeps its
synchronous API; production lifespan explicitly injects the worker.

Mutable import-ledger observation, permission, invalidation and pending-event
state stays on the event loop. Worker jobs contain immutable captured intervals
and detached query arguments. Only matching committed event identities can
retire a pending prefix. A summary is usable only for the current observation
generation, unknown revision, day, source and sequence, with existing pending
interval, measurement-tail and coverage guards applied. A late result cannot
restore trust after configuration A-to-B-to-A or direct-control invalidation.

One finite pre-decision wait cannot become an unbounded wait under the control
lock. Busy, failed or unconfirmed accounting retains unknown coverage and any
known finite-price comparisons available from the existing shared summary; it
does not fabricate known-empty history. Unknown-only cost warns without a
global export veto. Existing independently qualified PV-only and Manual/Force
policies remain separate. Authority, settlement, independent restrictions and
economic thresholds retain their existing rules.

A timeout or cancelled waiter does not prove that a running mutation was rolled
back. Keep its execution slot and reconcile its eventual result; do not create a
replacement worker. Storage APIs distinguish rejected admission from an accepted
operation with an unconfirmed outcome. Audit failure stays visible where audit
recording remains best effort, and price-tracking markers advance only after
successful persistence acknowledgement.

Shutdown stops admission and producers, cancels undispatched jobs and bounds
asynchronous drain. A connection closes only on its worker after the active
operation finishes. A Python thread cannot forcibly interrupt wedged operating-
system I/O or establish a hard process-exit deadline. See
[storage execution details](STORAGE_EXECUTION_ISOLATION.md).

## Passive trace archive clock recovery

Trace persistence is diagnostic only and must never delay control on the event loop or modify system/control clocks. A different or unknown OS boot cannot prove UTC by pairing an old UTC anchor with a new monotonic sample, even within the normal continuity tolerance. Healthy same-boot monotonic continuity remains sufficient without network access.

A new epoch after unresolved clock discontinuity requires bounded corroboration from two independent certificate-verified HTTPS origins with coherent Date, wall and monotonic timing. Before adopting that epoch, preserve full prior decision-segment bytes and the status captured by the completed preservation attempt in a verified durable history snapshot outside active retention. Missing evidence or failed preservation/status publication leaves writes and age-based deletion suspended. Historical gap flags remain sticky; recovery cannot reconstruct missing decisions. See [the recovery and preservation details](TRACE_CLOCK_RECOVERY.md).

## Reuse of proven MSC settlement for unchanged surplus permission

An already-proven pending MSC epoch may retain its original request when reopening
PV-only permission. Fresh exact MSC strictly after that MSC request and fresh
export closure strictly after an existing close request remain mandatory; preserve
an absent close boundary for already-trusted closed startup. Recheck epoch object,
phase, both boundaries and current authority after awaits. Consume only after
successful automatic completion. Failure under retained authority requests the
existing restrictive fallback; takeover/cancellation cannot consume proof and
introduce no new immediate-close guarantee after automatic authority is lost.

An accepted unchanged command may also remain pending without redundant
re-dispatch, retaining its original boundary only within the current actual-reader
and opaque source/control epoch, strictly before the existing actuator-report
freshness horizon expires (`0 <= request age < hvac_solar_data_max_age_seconds`).
Expiry re-dispatches and renews the latest-request boundary; service acceptance
cannot suppress retries indefinitely. Export-close retention additionally requires the
same bounded numeric request. All independent restrictive writes still run. A
fresh later contradictory report, replaced numeric request or genuinely changed
command requires a new dispatch and latest request boundary; delayed feedback
from before that dispatch cannot satisfy it. Missing or untrusted evidence grants
no completion. Retired config/source/authority epochs and failure/cancellation
retain the unfinished barrier and require new correlated closure. An already
trusted closed initial startup retains its absent close boundary. Relevant awaits
must preserve object/phase/boundaries, acceptance, identity and authority before
permissive dispatch or completion.

Pending continues through the existing unsuccessful-application cleanup and never
commits the decision or calls normal completion hooks. Only verified automatic
intentional pending without fallback raises the internal typed RuntimeError that
the scheduler and startup classify as waiting. Direct tick callers still receive
a RuntimeError; actuator errors, fallback and unverified authority remain failures.
The pending trace records bounded allowlisted observations from its existing
snapshot without extra reads. Diagnostic failure cannot change control behavior.

Maintenance applies only to an unchanged, already-open bounded `MSC_SURPLUS_CEILING`.
A completed application creates only a command candidate. Later actual-reader
provenance and current joint authority/mode/export reads must prove exact fresh
MSC strictly after its original request, matching fresh export readback strictly
after its original opening/anchor request, stable identity/generation and unchanged
numeric-request identity. Maintain non-regressing proof through relevant awaits.
Repeated maintenance may omit the redundant MSC command only while all checks
hold. This path never reopens a reduced/closed ceiling or increases the target.

When a local opening anchor is absent, a one-time same-setting request is allowed
only after the final joint live read confirms the positive ceiling still exactly
matches the bounded target. Later matching post-request readback remains required;
the request itself grants no maintenance proof. Restart, continuity/config/source
changes, pending/fallback state, failed/cancelled applications, authority loss or
contradictory evidence retire maintenance permission. Capture reader identity
before awaits and verify it after them. Recheck charging owners after any added
proof await and before a charge write. A baseline boolean or synthetic live flag
cannot replace this provenance. Deliberate `BATTERY_EXPORT`, independent owners,
latest-request semantics for actual dispatches, timeouts and fallback ordering
remain unchanged. Bounded allowlisted diagnostics use existing reads, grant no authority,
and cannot change control behavior or prove physical settlement.

### Recovery after an unaccepted export-close request - merged by PR #63

Observed .85 trace summary records failed HA commands at 07:55-07:56 and a fallback close whose service result was False, despite a recorded request boundary. Later fresh/accepted exact-MSC and current export-limit 0.01 reports did not release the stuck pending epoch: its actual identity-bound close boundary remained unaccepted, while pending recovery retried MSC only. This is a local issue report, not evidence of a general HA/network cause.

Reviewed behavior merged by PR #63 and published in 2.3.75-haos86: within the restrictive hold branch, if the actual identity-bound pending epoch has a close boundary and close_accepted=False, renew the restrictive close even when the current state already reads closed. Retire the retained MSC phase and establish a new close boundary. Require a later matching close report before dispatching a new MSC request, then require a later exact-MSC report. Never infer request acceptance from readback alone. A successful fallback close may establish accepted close evidence for this sequence, but it is not successful overall application completion.

Scope is limited to that live identity-bound unaccepted-close case. Keep identity-None/non-live handling and trusted-closed startup without a close boundary unchanged. Continue omitting an already accepted close. Preserve current identity, request tuple, live authority, Manual/Force, Remote EMS and independent restrictions. UI stale-snapshot behavior during pending ticks is separate and out of scope; its banner reports retained last_state age and does not prove that no read was attempted.

Two primary tests reproduced the missing restrictive retry before the repair. The repaired new module passed 11 tests / 24 subtests; existing applicable checks passed 166 tests / 171 subtests. Final guarded full suite passed 1,643 tests / 1,630 subtests, zero failures (206 warnings, 278.26 seconds). Independent source/test review is GO; independent documentation/scope review is GO. Source PR #63 merged normally at `b294f463e9fd4a2cbb6e1266e7d922422067e318`; .86 was published from metadata/tag source `74f21875e9a30e561d78644c4a5b0791becccc83` after normal metadata PR #64 merge and image proof. Installation and live acceptance remain unverified. The conservative risk is another restrictive close call and a renewed wait for later evidence; the recovery must not complete the pending transition or reopen export without newly accepted close provenance and subsequent valid report proof. Source rollback is a reviewed scoped revert preserving other work; live rollback requires an operator-verified backup/reinstall path. No HA rollback procedure is claimed.

## Automated baseline

Normal Automated operation is deliberately uneventful:

- EMS: Maximum Self Consumption;
- PV MAX: configured normal maximum;
- export ceiling: configured high ceiling;
- no deliberate stored-battery export intent.

Typical configured values are 25 kW for both PV MAX and the high export ceiling. Configuration and trusted live hardware authority remain definitive.

Permissive automatic actions require observed Automated operator ownership. Missing, unknown, unavailable, stale, or merely cached ownership is not Automated authority. Manual and Force remain user-owned and must not be displaced by automatic control.

An export ceiling is permission for the inverter to export genuine surplus. It is not a request to export at that power and must never, by itself, select a battery-discharge EMS mode.

## First-class export intents

| Intent | Meaning | Permitted EMS consequence |
| --- | --- | --- |
| `EXPORT_BLOCKED` | No live export permission | Export remains closed |
| `MSC_SURPLUS_CEILING` | MSC may export genuine inverter-controlled PV surplus up to a ceiling | Remain in Maximum Self Consumption |
| `BATTERY_EXPORT` | An explicit policy deliberately authorizes stored-battery export | A discharge EMS may be selected when all independent safeguards pass |

A positive numeric export target is not proof of `BATTERY_EXPORT`. Deliberate stored-energy sale requires an explicit owner.

## Actuator ownership

Import permission, export permission, battery-export intent, ESS charging rate, PV curtailment, and manual/safety control are independent decisions. An overlay changes only the actuators it genuinely owns.

Grid-import, grid-export, ESS-charge, ESS-discharge, and PV capability are separate domains. A configured baseline must not enlarge a smaller trusted observed hardware cap.

- The baseline owns ordinary MSC operation, normal PV MAX, and the high surplus ceiling.
- Import overlays may change import or charging without manufacturing battery-sale intent.
- Battery-export overlays must identify their explicit owner and remain subject to reserve, floor, forecast, import-cost, discharge-cap, and other existing safeguards.
- Safety and manual ownership override economic convenience.

Value Gate is advisory-only, including when its enforce setting is true. The independent actual import-cost guard remains an actuator protection for deliberate battery-backed or mixed automatic export. Manual/force ownership remains separate.

## Ordinary positive-FiT export

Ordinary MSC economic eligibility produces a surplus ceiling, not a battery-discharge target. The explicit four-tier battery-export policies below have separate qualification and execution permission. Time of day alone does not create stored-battery export authority.

The configured positive-FiT policy has two independent controls:

- `ALLOW_LOW_MEDIUM_EXPORT_POSITIVE_FIT` enables the separate export policy;
- `ALLOW_POSITIVE_FIT_BATTERY_DISCHARGING` determines whether that policy may deliberately export stored battery energy.

Neither legacy control authorizes ordinary Low battery sale. In Low, a verified Automated, exact-MSC, trusted-flow case may use a bounded `MSC_SURPLUS_CEILING`; otherwise it fails closed. Medium/High/Spike and separately named deliberate-export policies require their own independent qualification. The raw numeric policy target cannot manufacture battery-export authority.

For ordinary MSC flow interpretation:

- battery discharge serving site load while grid export is below the meaningful threshold is compatible with the MSC ceiling;
- meaningful simultaneous battery discharge and grid export is not presumed benign and closes conservatively;
- unknown, stale, unavailable, or non-finite safety evidence cannot broaden permission.

## Solar Surplus

Solar Surplus is a Phase 1 MSC/PV-only export-permission policy with bounded dynamic ESS charge-ceiling ownership. It:

- remains in Maximum Self Consumption;
- retains normal PV MAX;
- never owns `BATTERY_EXPORT` or deliberately selects a discharge EMS;
- may reduce the existing normal safe/trusted ESS charge request only after final arbitration selects `solar_surplus_policy_active`, with the stricter charge-ownership evidence below; it must never increase that normal request;
- does not own grid import;
- treats a high export ceiling as permission for genuine PV surplus, never as an instruction to discharge or proof that physical export settled.

Its energy order is PV to current house load, preserve enough opportunity to fill the battery safely, then permit export of genuinely remaining PV. Eligibility is recalculated every cycle and requires all of the following:

- FiT at least `1 cent/kWh`;
- trusted finite PV and load values with coherent observations;
- measured PV-load surplus strictly above `0.5 kW` for entry;
- for genuinely owned continuation only, measured surplus strictly above `0.2 kW`, or the bounded measured-proof dip hold below;
- trusted Remaining Today aggregate forecast;
- trusted battery SoC and rated battery capacity;
- trusted same-day future sunset while the sun is above the horizon;
- a finite Solar-specific forecast safety factor `K >= 1`;
- a passing aggregate energy budget;
- when battery fill remains, passing trusted detailed timing evidence using trusted effective charge capability.

At or below the continuation threshold Solar stops unless the bounded dip hold qualifies. After stopping, full entry strictly above `0.5 kW` is required again. Missing, stale, malformed, incoherent, or otherwise unsafe evidence fails Solar closed.

### Brief measured-surplus dip hold (published .74)

An already active Solar MSC permission may bridge a short measured-surplus dip until **strictly before 15 seconds after the older PV/load source report** that proved measured surplus strictly above `0.5 kW` and produced a successfully applied final Solar decision. This is five existing three-second coalescing windows; it bounds continuation without delaying startup or ordinary measured-surplus decisions. It applies at any otherwise eligible SoC and does not change the separate exact-100% branch.

Both PV and load report timestamps must advance before new strong measured evidence renews that permission. A held decision, cached report, ordinary `0.2-0.5 kW` continuation, forecast potential or elapsed time cannot renew it. Proof is process-local, begins absent after restart, and cannot be granted by decision calculation alone or a successful application completed after the source evidence expires.

Every normal non-surplus Solar eligibility gate remains mandatory. In addition, the hold requires current provenance-bearing Automated, exact MSC and Remote EMS ON observations, no pending MSC transition, directly observed battery discharge at most `0.1 kW`, grid import at most `0.1 kW`, and finite fresh measured PV/load/battery/import/export reports within five seconds of each other and younger than 15 seconds. Missing or future timestamps, regressions, ownership loss, unsafe flow, failed/pending/cancelled application and Manual/Force invalidate proof. Advancing physical evidence and successful final Solar application are required to rearm it. For Automated control mode configured as a persistent `input_select.*` helper, the current read may remain usable when its report timestamp is older than the HVAC age limit; availability, freshness, expected value, finite timestamp and non-future chronology remain mandatory (`0 <= age`). Device-backed control selectors, observed EMS mode, Remote EMS control and all flow reports retain their existing age limits.

The observed export ceiling must already be positive and at least the prior successful Solar request within `0.01 kW`. Held permission is bounded by that previous request, the current observed ceiling and current authoritative capability. Immediately before any positive held export write, the existing joint authority read must also prove a fresh finite positive actual export limit at least that requested write, within `0.001 kW` command tolerance. It cannot reopen a closed or independently reduced actuator, raise its previous ceiling, select discharge EMS or manufacture battery-export ownership. The daytime zero-surplus exception is scoped only to this qualified hold. Existing import, PV, ESS, competing-owner, dispatch and settlement restrictions retain authority.

The serialized event loop bounds quiet waits and event coalescing by the proof deadline; it does not rely on the 60-second heartbeat to notice expiry. Failed held applications retain a separate re-evaluation obligation even when proof is cleared and the previous decision is restored. An unsuccessful expiry-triggered attempt retries through the same serialized loop after three seconds, without busy-spinning, until a successful non-held cycle or operator takeover clears the obligation. Permissive application checks expiry after authority awaits and before completion; expiry during application requests the existing conservative fallback. These bounds govern decision/dispatch authority, not a guarantee that physical equipment settles by the deadline. Dynamic ESS charge ownership still requires its independent provider/fill evidence; an unverified provider retains the normal safe charge request.

Offline checks use synthetic live-report provenance and simulated application outcomes, plus fake-actuator expiry tests. They do not establish why PV collapsed in the supplied incident or prove inverter behavior. For later verification: monitor-only and dry-run observations must show the proof deadline and immediate hard-gate rejection without control writes; separately approved supervised live proof must compare source timestamps, held permission, actual flows and requested/observed ceilings, and confirm persistent low surplus expires. Stop and return to the operator's chosen safe mode on unsafe discharge/export, lost trust/authority, repeated failures or renewed flapping. Local rollback is to withhold this uncommitted candidate; no live rollback or settings change is performed here.

### Scoped reacquisition qualification (local O2/O6 candidate)

Initial Solar admission retains its existing rules. When a previously final
Solar owner loses a valid strict aggregate energy-budget comparison, that loss
closes Solar immediately and arms a process-local re-entry obligation. Subsequent
Solar eligibility is withheld before export arbitration until the qualification
below passes. Independent policies still arbitrate through their existing gates;
pending Solar is not an active export or restrictive charge owner. The timer
cannot extend permission through a failed budget, trust, tariff or safety gate.

O6 is separate: only completed automatic genuinely owned Morning Slow operation
with qualified forecast/physical relief restoring the normal safe charge bound
arms its handoff obligation. Raw Morning eligibility, priority, artificial-cap
relief and Solar's independent export permission remain unchanged. During a
partial-battery Solar handoff, full Solar charge evidence and trajectory are
still calculated, but its restrictive request waits for qualification. The
already selected bounded normal charge request applies meanwhile; independent
import and other charging owners are not overridden. Genuine slow charging
without relief does not arm this guard. Exact-full retains its separate behavior.

Each guard requires advancing provenance-bearing PV and load source reports
spanning at least **30 seconds each**, plus at least **30 seconds of local
monotonic time**. Each source report and each stream's local advancement gap
must be at most **60 seconds** old; PV/load coherence retains its existing
five-second bound. Cached reports cannot mature the interval. Observed Automated,
exact MSC and Remote EMS ON authority and all existing applicable gates remain
mandatory. These are minimum qualification bounds, not a promise of admission
at 30 seconds or proof of physical continuity between observations.

Failed gates, unavailable reports, regression of reports/wall/monotonic clocks,
configuration/source/context changes, competing ownership and failed/cancelled
application retire qualifying proof while preserving an unfulfilled obligation.
Only a qualified final selection and completed automatic application without
fallback retires its obligation. Generic success, Manual pauses and pending
transitions are insufficient. Generations are rechecked after authority awaits,
before relevant writes and before completion; expiry of O2 uses existing fallback,
while expiry of O6 restores the selected bounded normal charge request without
closing independently valid export. Provider expiry remains charge-only authority
and is not a new O2 export prerequisite. Restart starts with the existing initial
admission rules; neither qualification nor its cause is persisted.

These scoped admission rules do not change the brief measured-surplus dip hold,
Morning relief, control cadence, MSC settlement, export/import limits, reserve
policy or the zero-charge/fill-deadline strategy. Waiting can reduce export and
increase normal charging; it cannot guarantee filling after forecast downgrade.
See [candidate validation and supervised acceptance](SOLAR_REENTRY_STABILITY.md).

### Aggregate energy budget

The Phase 1 energy model is:

```text
remaining_load_kwh = current trusted site load x hours to same-day sunset
fill_need_kwh = trusted rated capacity x remaining SoC headroom to 100%
required_energy_kwh = remaining_load_kwh + fill_need_kwh
protected_requirement_kwh = K x required_energy_kwh
```

Solar requires trusted PV Forecast Remaining Today to be **strictly greater than** the protected requirement. Equality does not pass.

The dedicated setting is `solar_surplus_forecast_safety_factor`, default `1.20`: `1.00` adds no margin, `1.20` requires 20% more aggregate Remaining Today than calculated load plus fill need, and higher values are more conservative. Legacy `solar_surplus_start_multiplier` and `solar_surplus_stop_multiplier` remain stored/configurable for compatibility but do not drive redesigned eligibility.

### Detailed timing

Detailed timing is required only when `fill_need_kwh > 0`. Trusted detailed Solcast intervals must cover the decision horizon through same-day sunset. Each interval deducts current trusted site load before estimating chargeable PV, bounds charge opportunity by trusted effective charge capability, and applies the same Solar safety factor conservatively. The resulting timed opportunity must prove the battery can fill to 100% by sunset.

Aggregate Remaining Today energy and detailed interval energy are independent gates; they are not added together. If fill need is exactly zero, detailed timing is not required. Missing, gapped, truncated, untrusted, or insufficient detailed evidence fails Solar closed.

### Dynamic ESS charge ceiling

Charge ownership is evaluated only after final arbitration selects Solar Surplus. It requires provider-aware freshness for detailed Solcast data, continuous interval coverage from now through the effective Solar fill deadline, trusted current load, battery SoC and rated capacity, the valid Solar safety factor, and trusted effective normal ESS charge capability. Detailed evidence is required for this authority even when the battery is full.

The dedicated setting `solar_surplus_fill_deadline_margin_minutes` defaults to **60** and accepts finite nonnegative minutes, including zero; booleans are invalid. The effective trajectory deadline is trusted same-day sunset minus this margin. Zero retains the sunset trajectory. This timing margin is independent of Morning Slow's cutoff and the unchanged Solar safety factor `1.20`. It changes only the dynamic charge trajectory: aggregate remaining-load and independent eligibility timing above still use sunset.

At or after the effective fill deadline, Solar relinquishes restrictive charge ownership so normal safe MSC charging can use available PV. Earlier/full-battery surplus export remains subject to the existing independent PV-only eligibility and safety rules; the earlier deadline is not an export cutoff. A sufficiently large margin can place the deadline before now, safely releasing the restriction. Missing/untrusted sunset, invalid margin or unusable deadline cannot authorize a restrictive ceiling. Provider/same-local-day semantics remain unchanged.

Provider freshness uses explicitly configured Forecast Today and API Last Polled entities from the same Solcast instance (`forecast_today_sensor` and `solcast_api_last_polled_sensor`). Under the accepted BJReplay/ha-solcast-solar v4.6.1 contract, an advancing API Last Polled state represents a successful ordinary provider refresh. Sig Opt independently validates finite/nonnegative detailed estimates, aware timestamps, ordering, exact continuous coverage, the current interval and same-local-day sunset horizon. `dataCorrect` is not mandatory; its row-count semantics can reject a legitimate 23-hour DST day. Forecast Today HA `last_reported`, `last_attempt`, and schedule advancement alone do not establish provider success. Provider-payload validity is independent of daylight ownership: a valid forecast can refresh provider authority below the horizon, but it cannot establish Solar ownership or dispatch. Trusted daylight and sunset metadata remain required by the separate ownership gate; this distinction does not add a monitor-only mode or relax any other provider/source/generation/coverage/deadline check.

The process-local states are UNVERIFIED, VALID and EXPIRED. Startup begins UNVERIFIED: the first coherent observation establishes only a provider timestamp baseline and expected deadline. A later credible successful timestamp advance is required for VALID. Credible advances are retained as a high-water mark even when their payload is rejected; unchanged rejected generations cannot become trusted after repair or elapsed time. Malformed, naive, materially future-dated or regressing provider timestamps fail closed. Provider freshness is never persisted and no Solcast update is forced.

The retained scheduled obligation D cannot slide:

- With unchanged P, later advertised N leaves D unchanged; earlier valid N shortens D and expires authority immediately if already due.
- A qualifying new P before D remains bounded by `min(D, N)`, including manual/forced success immediately before a scheduled refresh.
- Only a qualifying success at/after the retained deadline, validated at/after D with a usable future N and complete payload, may discharge that obligation and establish a new deadline.
- At `now >= D` without qualifying replacement, authority is EXPIRED with no grace. Solar releases only its charge restriction and restores the otherwise applicable normal safe/trusted ESS request.

HA disconnect/reconnect, source reassignment, unavailability/reload, timestamp regression or uncertain continuity invalidate the source epoch. Relevant WebSocket observations signal invalidation synchronously before lossy queue handling; the epoch and urgent flag survive coalescing and overflow. REST reads retain the source/epoch captured before their first await and cannot establish authority after an epoch change. Recovery requires a new baseline followed by another provider advance.

The existing optimizer event loop bounds its wait and debounce by D and local midnight, so reevaluation does not depend on an HA event or the 60-second heartbeat. Authority is rechecked immediately before a reduced charge write; a pending reduced write that crosses expiry/invalidation is followed by restoration in the same serialized application. This introduces no independent control loop or change to actuator settlement semantics. A final daytime poll may use tomorrow's next update for today's remaining horizon, but its Forecast Today generation cannot carry into another local day.

This authority is isolated from global `forecast_today_observation_trusted`. `hvac_solar_forecast_max_age_seconds` retains its backend/environment key and 600-second default for existing consumers: Remaining Today, Power Now, Forecast Today/Standby Holdoff, age-based Forecast Tomorrow and selected import-price forecast freshness. It cannot extend dynamic Solar provider authority. All existing final-owner, load, SoC, capacity, sun, capability and higher-priority-owner safeguards remain required.

For each detailed interval, subtract trusted current load from forecast PV, floor the available power at zero, and bound charge opportunity by the existing normal safe/trusted charge capability/request. Multiply by actual interval overlap hours before the effective fill deadline, clipping a partial final interval. Identify the interval containing now; future opportunity includes only intervals strictly after that current interval.

```text
protected_fill_need_kwh = K x energy_needed_to_reach_100_percent
future_opportunity_kwh = sum of bounded charge opportunity after the current interval
required_now_kwh = max(0, protected_fill_need_kwh - future_opportunity_kwh)
urgent_current_kw = required_now_kwh / remaining current-interval overlap hours
fill_progress_floor_kw = protected_fill_need_kwh / hours to effective fill deadline
requested_charge_kw = max(urgent_current_kw, fill_progress_floor_kw)
```

For the approved local `fix/solar-fill-progress-trajectory` candidate, this formula supersedes the published .84 zero-baseline allocation: fill progress takes priority when available PV cannot provide both the desired export and charging progress. Clamp the request between zero and the existing normal safe/trusted capability/request. Round a positive request UP to 0.01 kW without exceeding that normal bound, retaining its existing safe command precision. While partial and all existing ownership/trust/coverage gates pass, ample future forecast opportunity alone cannot make the request zero. Exact-full retains zero protected fill need. Recalculate from current SoC and time without a new timer or fixed-rate setting; this changes only ESS charging authority and cannot authorize stored-battery export or guarantee actual charging/full SoC. Higher urgent present need remains binding.

Missing, expired, gapped, invalid, or untrusted charge evidence immediately relinquishes only the Solar charge restriction and restores the normal charge request. This stricter authority does not redefine Solar eligibility: complete current-day detailed intervals may still support the existing Solar policy despite old parent Forecast Today metadata. Provider-verified evidence may also authorize the dynamic charge restriction in that case; absent provider authority reports `solcast_provider_authority_untrusted`. Solar's independent eligibility and safety gates still apply.

### Physical-export saturation relief

Solar may relax only its own restrictive ESS charge ceiling using a separate process-local feedback controller:

```text
final Solar charge ceiling = min(normal safe/trusted ESS charge request,
                                baseline trajectory ceiling + physical relief)
```

Relief starts at zero. `grid_connection_export_limit_kw` is generic physical-site saturation evidence, with software default **0.0 = disabled**. The confirmed 15 kW site limit is operator configuration, not a universal default or an inverter export command. Solar keeps MSC, normal PV MAX, normal high export permission (currently 25 kW at the site), and `battery_export_owner=none`. Relief must not deliberately divert export into charging or authorize `BATTERY_EXPORT`.

Required authority is final Solar charge ownership, observed Automated ownership and exact MSC, no Manual/Force/Morning Slow or deliberate battery-export owner, partial SoC, and trusted coherent measured physical flows. PV, load, grid-import and grid-export observations must be finite, fresh and temporally coherent within five seconds; measured flow must support nonnegative battery charging with no grid import. Existing direct-battery discharge safety checks remain required; relief derives charging evidence from the coherent measured components. A static saturated sample cannot prove hidden PV. Solcast potential, estimated PV and `hidden_pv_surplus_kw` cannot authorize relief.

The approved fixed Solar policy has no additional operator tuning settings:

- Entry/upward confirmation requires actual export **>= physical limit - 0.2 kW**. Each increase is at most **0.4 kW**, after **two** fresh coherent post-command observations. Every relevant timestamp must advance; telemetry reuse cannot stack increases. A successfully applied changed charge target starts its feedback epoch, while reasserting the same target does not erase a valid first observation. Further increases require measured battery charging above the baseline ceiling.
- One new coherent export observation **< physical limit - 0.5 kW** reduces active relief immediately by **1.2 kW**, floored at zero. The other flow observations must remain trusted/coherent but need not all advance to permit this restrictive response. The interval between exit and entry holds relief and resets upward confirmations; exact exit does not reduce.
- Actual trusted export **< physical limit - 1.0 kW** hard-resets relief to baseline. Any export-driven downward adjustment imposes **three** fresh coherent observations at/above entry before another increase; afterward the ordinary two-observation rule resumes.
- Relevant flow trust/freshness/coherence loss, regressing feedback, loss of Solar/Automated/MSC ownership, Manual/Force/Morning Slow, exact-full, disabled/invalid limit or actuator application failure resets relief. Normal-cap/context changes and legacy/static baseline changes clear relief and start a fresh command/feedback epoch, retaining an existing retry requirement for the same physical limit. The approved local fill-progress candidate adds only the bounded completed-total exception below for a pure time/SoC baseline rebase.

At a 15 kW configured site the entry, exit and hard-reset boundaries are 14.8, 14.5 and 14.0 kW respectively. This asymmetry permits cautious discovery and faster export restoration. Application rechecks restore the baseline if physical evidence expires, and restore the normal safe request if provider/fill-deadline authority expires, including during an in-flight charge write. Service-call success arms later feedback only; it is not observed export preservation or actuator settlement.

Morning Slow uses the separate partial physical-relief contract below in this local candidate; its state and tuning do not control Solar. Demand Window continues to own import blocking. This relief does not redesign export ownership or Phase 2 settlement.

#### Local fill-progress completed-total rebase

This candidate requires a separate process-local receipt from real successful
automatic application completion, not a decision, accepted individual service
call, mocked completion flag, no-op, pending or fallback outcome. It binds the
actual bounded completed total and command epoch to opaque control/source
continuity, provider generation/deadline, effective fill deadline, day, capacity,
normal charge capability and physical-reference context. Time/SoC/baseline alone
may vary; source/ownership changes cannot carry a receipt.

A pure baseline rebase may retain at most the earlier completed total:
`new_total = min(current_normal, max(current_baseline, prior_completed_total))`.
The rebase grants no increment; its relief is only the difference above current
baseline. It consumes the present cohort and clears upward confirmations while
preserving same-command timing, report high-water and retry penalty. A changed
total requires an actual successful changed command and later fresh feedback.
Downward feedback retires or clips the candidate immediately, before a lower
command completes, so an older higher total cannot resurrect. Every hard reset,
trust/authority/provider/context loss and failed/pending/cancelled or uncommitted
application retires it. Final checks after awaits retain request-correlated MSC,
export, dip/reentry and owner protections. Rejecting proof cannot leave an old
receipt available. This proves software completion only, not inverter settlement. ESS charge-setting
readback remains passive evidence; the receipt does not assert that the device
physically adopted or obeyed the requested cap.


### Near-full safeguard arbitration

A synthetic refill requirement caused solely by untrusted available-discharge-energy telemetry cannot, by itself, veto an independently qualified and safely verified Solar Surplus MSC/PV-only ceiling. The raw Battery Full Safeguard calculation and diagnostics remain visible; the distinction applies only to final export arbitration.

The distinction requires all normal Solar aggregate, detailed-timing, measured-surplus, forecast, tariff, and trust gates, plus genuinely observed Automated ownership, genuinely observed exact Maximum Self Consumption, and trusted PV/battery/grid-flow evidence proving the request remains PV-only-safe. Re-arbitration must select the specific `solar_surplus_pv_high` source. A failed Solar gate, unknown or unsafe flow, competing deliberate battery-export owner, manual owner, or independent higher-priority safety owner retains the fail-closed result and cannot fall through to a general permissive ceiling.

This distinction creates only `MSC_SURPLUS_CEILING`. It never creates `BATTERY_EXPORT`, never selects a deliberate discharge EMS, and does not itself grant ESS charging, grid-import, or PV-curtailment ownership. A final Solar owner may separately qualify for the bounded charge ceiling above. All downstream actuator, settlement, and ownership protections remain mandatory.

### Ownership interactions

- Morning Slow owns its charging behavior. Solar is off while Morning Slow is active and cannot alter its charge rate.
- Morning Dump and other explicit deliberate `BATTERY_EXPORT` owners win over Solar. After Morning Dump ends, Solar must satisfy full entry again.
- Demand Window continues to own import blocking; Solar does not take import ownership.
- Exact-full remains a separate PV-only branch and its semantics must not be merged into Solar.
- Manual and Force remain operator-owned; Solar continuation cannot survive as active control ownership through them.
- Positive-FiT deliberate battery export remains separate. Solar itself never authorizes battery discharge.

### Diagnostics

`solar_surplus_policy_active` identifies final Solar policy ownership after arbitration. Operator diagnostics also expose the fail reason, aggregate budget evidence, detailed timing evidence, measured surplus and active threshold, and Solar safety factor. Policy-active status and an open ceiling do not prove physical inverter or grid export settlement.

Dip diagnostics add `solar_surplus_dip_hold_active`, `solar_surplus_strong_measured_proof`, `solar_surplus_dip_clock_regressed` and `solar_surplus_dip_hold_deadline_ts`. Held final ownership reports `active_final_solar_surplus_owner_dip_hold`; application expiry rejection adds `solar_surplus_dip_dispatch_rejected`. A deadline in a decision trace describes the existing proof at decision time, not physical settlement or successful renewal.

Charge diagnostics expose gates `solar_charge_ceiling_evidence_trusted` and `solar_charge_ceiling_owned`, plus values `ess_charge_limit_owner`, `solar_charge_ceiling_requested_kw`, `solar_charge_ceiling_protected_fill_need_kwh`, `solar_charge_ceiling_future_opportunity_kwh`, `solar_charge_ceiling_required_now_kwh`, `solar_charge_ceiling_current_window_hours`, and `solar_charge_ceiling_reason`. When owned, the charge owner is `solar_surplus`; current charging needed for the fill trajectory reports `present_charging_required_for_fill_trajectory`. Charge ownership is distinct from policy eligibility and observed actuator settlement.

Fill/relief diagnostics add `solar_charge_ceiling_fill_deadline_ts` (Unix timestamp), `solar_charge_ceiling_fill_deadline_margin_minutes`, `solar_charge_ceiling_baseline_kw`, gates `solar_physical_relief_active` / `solar_physical_relief_flow_trusted`, and values `solar_physical_relief_kw`, `solar_physical_relief_reason`, `solar_physical_relief_export_kw`, `solar_physical_relief_limit_kw` and `solar_physical_relief_confirmations`. `solar_charge_ceiling_requested_kw` remains the final requested ceiling after relief. The API copies these trace values without recalculating control and suppresses stale relief-active status when final Solar ownership is absent.

Provider trace evidence includes `solar_provider_state`, observed/high-water/verified poll timestamps, retained deadline, advertised next update, configured source, epoch, source-continuity trust, provider-authority trust and rejection/expiry reason. These fields prove decision provenance, not live actuator settlement.

## Explicit deliberate battery-export policies

Policies that genuinely own deliberate battery sale remain distinguishable. These include qualifying Morning Dump, Medium-tier export, high-price export, export spike, Evening Export Boost, and established solar/export or external overrides where their policy owns discharge.

Each owner remains subject to its own eligibility and all independent safety guards. Generic ordinary MSC economic eligibility is never a deliberate battery-export owner.

Solar Override may retain a deliberate battery-backed export only when trusted SoC is strictly above both the selected battery-export tier floor and the independent protected floor, and every existing qualification, authority, forecast, actual-import-cost, capability and settlement guard passes. At or below either floor, that override must not create a battery-export owner or discharge EMS. This floor check does not suppress a separately qualified genuine PV-only MSC surplus ceiling: it may remain only when the existing observed Automated/exact-MSC and trusted-flow evidence proves no meaningful battery-backed export. Never infer PV-only permission from the rejected override or its numeric target. This rule applies to Solar Override only; Morning Dump, Evening Boost and operator-owned Manual/Force keep their own policies and floors.

### Four independent battery-export tiers

| Selected tier | SoC configuration key | Software default |
| --- | --- | --- |
| Low (compatibility only; battery sale disabled) | `battery_export_min_soc_low` | 100% |
| Medium | `battery_export_min_soc_medium` | 40% |
| High | `battery_export_min_soc_high` | 20% |
| Spike | `battery_export_min_soc_spike` | 10% |

Select the tier using the existing price thresholds and Spike activation rules. Ordinary automated deliberate battery export starts at Medium. Low remains a price classification and PV-only permission context. No persisted Low floor or legacy Positive-FiT opt-in may enable Low battery sale, even at 100% SoC. The selected eligible battery tier owns its economic eligibility and SoC floor; failure does not fall back to another tier, including Low. All four floors are independent: there is no required ordering. Configuration and API inputs must be numeric, finite and within 0-100 inclusive, with booleans rejected; UI/API round-trip and persistence retain those values.

Battery export requires trusted SoC, rated capacity, available discharge energy and the evidence required by the relevant forecast/reserve protection. SoC must be strictly above the selected floor and the independent protected floor. Lowering a tier's economic floor cannot lower a physical, safety or protected reserve limit. Spike's economic-reserve exception never bypasses those protections, telemetry trust or operator authority.

Preserve the existing price interpolation, SoC scaling, headroom, discharge-window divisor/boost, caps, rounding and Spike full-power arithmetic. Tier selection changes neither hardware capability domains nor the actuator/settlement contract.

Forecast evidence remains context-dependent. Required Remaining Today or reserve evidence fails closed; there is no blanket tomorrow-trust veto for High/Spike. During daytime at SoC >=99%, poor or untrusted tomorrow evidence retains the existing measured-PV-surplus cap. Untrusted Solcast Power Now cannot inflate the control surplus; independently trusted measured PV may still support a separately eligible policy.

The Low setting is retained for config/API/UI compatibility and defaults to 100%; it is not an execution gate that operators can lower to restore battery sale. Low cannot create `BATTERY_EXPORT`, a battery-export proposal/final owner, commanded discharge EMS or Morning preemption. Ordinary positive-FiT MSC, exact-full cheap-FiT and legitimate Solar Bypass retain their independently qualified PV-only behavior. Below-Medium deliberate discharge remains possible only through a separately named, explicitly qualified policy such as Morning Dump or Evening Boost, or operator-owned Manual/Force. These policies keep their own guards and priority; Low cannot supply accidental fallback authority.

High/Spike may preempt Morning Dump or Morning Slow only after a valid positive bounded proposal, known-priced-floor permission when a finite price is available, observed Automated authority and all other guards pass. Unknown cost alone is advisory and does not veto or prevent preemption; use the same known-price evidence and permission result for Morning preemption and final battery-export execution. A failed candidate leaves an otherwise eligible Morning owner intact. Morning Slow itself requires trusted remaining-forecast evidence; an ineligible Morning owner must not be artificially retained. Medium/Low do not gain High/Spike Morning-preemption authority. Preserve other owner priorities, Demand Window import blocking and Manual/Force ownership.

### Proposal, permission and final ownership

Keep the qualified proposal (tier/source, selected and protected SoC floors, bounded calculated power and reason) separate from execution permission and the final decision owner. `battery_export_owner` records proposal provenance; it may remain `high_price` or `export_spike` when an actual import-cost veto or unavailable observed operator authority blocks execution. That diagnostic is not battery-sale permission. A genuinely unqualified tier cannot fabricate a proposal owner.

`battery_export_final_owner` is `none` when final export is blocked. A vetoed candidate must have zero export limit, `EXPORT_BLOCKED` intent, no commanded discharge through that candidate and no Morning preemption. Normal ESS discharge capability for MSC load service is a separate protection; a cost veto must not be repurposed into an unrelated discharge-cap clamp.

The authoritative actual import-cost snapshot is shared by arbitration and advisory calculation. A finite highest price present in that snapshot can veto applicable automatic battery-backed/mixed export only when FiT is below its floor; equality or a higher FiT does not fail this cost comparison. Unknown actual-cost evidence alone warns and does not veto. When history is incomplete, the known maximum is only a lower bound, and a summary/cache miss or storage/query failure may leave no known price; no last-known-price cache is added. Independently proven PV-only MSC and Manual/Force retain their established separate semantics. Value Gate remains advisory-only, including with enforcement configured; stored-energy/reserve analysis and known-price comparisons continue. Preserve qualified proposals for advisory calculation when operator authority prevents execution, without granting actuator permission. `effective_battery_export_floor` remains a monetary value, never a SoC field.

### Passive reserve-planning diagnostics (approved local candidate)

`reserve_planning_*` fields describe the existing advisory reserve estimate:
required nominal kWh, kWh beyond a full nominal battery, whether the requirement
exceeds nominal capacity, calculation basis and reason. A raw requirement above
100% is possible when projected demand exceeds full capacity; it is not a command
to charge above 100%. Preserve the original reserve/export-surplus calculations
and existing bounded HA helper write. These fields never grant charging or export
permission and do not change actuator targets.

The estimate uses existing current-load extrapolation, safety factors and floors;
it is not proof of future demand, usable energy, grid import or a refill guarantee.
Disabled advisory returns null estimates with `not_evaluated`. Invalid/nonfinite/
boolean inputs, unavailable capacity and arithmetic overflow return explicit
unavailable diagnostics rather than false zero shortfalls or nonfinite JSON.
These reserve diagnostics introduce no charging rule, forecast model or
reserve/price policy; the separately approved Solar fill-progress allowance is
defined above and does not use these passive reserve estimates.

### Import-cost ledger completeness (approved local O16 candidate)

Measured import evidence must be captured before automatic battery-export arbitration. Import ownership for that interval comes from prior application and observed permission, not a future decision that closes import. A confirmed close retains the next measured import tail; a command is not a new meter observation. Completed automatic application or confirmed Manual observations can establish permission. Pending, failed and generic no-op outcomes cannot establish a safe inactive boundary. Manual imports remain accounted for without removing the Manual/Force export exemption.

Actual activation of accounting source, tariff, authority or import-actuator identities invalidates accounting and permission evidence under the control lock, even if changed back before the next sample. Validated direct Manual/ESS requests invalidate that evidence before their first write; unchanged identities, unrelated tuning and rejected validation do not. An unobserved open/close interval cannot certify trusted cost history or the following inactive midnight. Operator targets and the Manual/Force exemption remain unchanged. Accounting unknown by itself is a warning; any independent loss of authority or permission still follows its existing safety behavior.

Captured intervals retain immutable energy, original tariff/trust, date, source and stable identity through retry. Persist interval, checkpoint and coverage atomically; exact replay must not duplicate energy or rewind the durable checkpoint. An ID with changed payload is an error. Unknown or pending coverage cannot be treated as trusted zero cost. Query failure, missing/non-finite counters, unretained snapshots and queue overflow must remain conservative. The existing 0.01 kWh significance and 1¢ cost-floor policies remain unchanged.

Startup/legacy history, restart, source/counter changes and observation gaps leave affected-day coverage unknown. Recoverable queued intervals may restore a previously covered day only after exact reconciliation. Irrecoverable unknown coverage remains sticky for that day; only a continuous known-inactive midnight boundary with valid observations establishes a newly covered day. Accounting coverage can remain unknown beyond the current day, but unknown cost alone is advisory and does not veto otherwise-qualified automatic battery-backed export. Coverage records accounting continuity under existing measurement assumptions, not physical verification or new telemetry freshness guarantees. Independently proven PV-only MSC permission, operator ownership, price/reserve rules and actuator safeguards retain their existing semantics. See [the local design and acceptance boundaries](IMPORT_LEDGER_INTEGRITY.md).

Diagnostics distinguish tier, selected/protected floor, proposal qualification/selection, execution eligibility or rejection, binding protection, calculated power, proposal owner, final decision owner and Morning preemption. Neither a proposal nor a final requested decision proves observed physical settlement.

## Evening Boost

Evening Boost is a deliberate `BATTERY_EXPORT` policy with owner `evening_export_boost`. Its dedicated setting is `evening_boost_min_feedin_price`: the software default and hard permitted minimum are both `$0.01/kWh`. Values below one cent and non-finite values are invalid; no arbitrary upper bound applies.

When every Evening Boost eligibility and safety gate passes, it may operate below the ordinary export-tier threshold. The existing `export_limit_low` remains the ordinary tier output, not an Evening Boost-specific export ceiling. Ordinary positive-FiT export does not acquire Evening Boost ownership, and absolute sub-one-cent export remains blocked.

Available-energy trust, refill feasibility, actual import-cost protection, forecast and reserve protections, battery floor, observed Automated ownership, Demand Window separation, Manual/Force ownership, and fail-closed actuator settlement remain mandatory. This decision does not introduce a 5.5 kW Evening Boost redesign.

Evening Boost eligibility requires both existing `load_power_trusted` and `sunrise_observation_trusted` evidence. Its overnight reserve calculation uses both observations; if either observation is untrusted or unavailable, the Boost gate fails closed.

### Persistent operator mode helpers

A current HA read of the configured persistent `input_select.*` mode helper establishes operator ownership when its observation is available, fresh, chronology-valid and has the expected value. Its unchanged report timestamp (or `last_updated` fallback) does not require periodic advancement for Evening Boost re-entry. The timestamp must still be finite, non-boolean and non-future (`0 <= age`); even one second in the future fails. Missing usable timestamps, conflicting metadata, unavailable or nonfresh observations, and wrong mode values fail closed. Device-backed mode selectors and Remote EMS retain their independent report-age limits.

This helper distinction does not replace trusted load or sunrise evidence, advancing load-report timestamps spanning at least 120 seconds, at least 120 seconds monotonic elapsed time, monotonic report chronology or the 60-second report-gap reset. Manual/Force ownership, current dispatch authority, physical limits, reserve and price checks, MSC protections and immediate failure closures remain mandatory. Observed operator ownership alone grants no export permission or physical-settlement proof.

### Published re-entry qualification - 21 October 2026

The published .75 re-entry implementation requires fresh qualifying load-report timestamps spanning at least 120 seconds and at least 120 seconds of local monotonic elapsed time before initial Evening Boost admission or readmission after restart or return from manual ownership. These are minimums, not a promise of admission at 120 seconds. Load-report timestamps must advance monotonically; no gap between load reports may exceed 60 seconds. A gap over 60 seconds or local elapsed time since the last advancing load report resets qualification. Heartbeat cadence and report latency may delay qualification indefinitely until sufficiently frequent new reports arrive. Cached load reports cannot mature qualification. Sunrise remains subject to its existing trusted-future-horizon check; sunrise observations do not need to advance during the load qualification interval. Wall-clock or monotonic-clock rollback, or any failed existing gate, resets the Boost context. Existing failure closures remain immediate.

The implementation uses Closed, Qualifying and Admitted states. Admitted means permission to proceed, not physical operation or settlement. Qualification is retained only after successful automatic application completion or verified MSC-pending state; generic no-op success is insufficient. Startup and return from manual ownership therefore delay new Boost admission. Existing higher-priority owners and their permissions are unaffected.

This qualification delays only new Boost admission. It does not delay or weaken an existing failure closure, alter higher-priority owners or their permissions, or establish physical settlement. Existing requested/observed/settled limits remain subject to supervised live acceptance, which has not been completed. Keep Boost off through installation checks and initial verification of exact runtime identity, effective settings, report cadence and reserve/limit assumptions. Once those facts are verified, enable Boost only within the already-authorized supervised acceptance trial. Switch it off and retain manual ownership immediately on safety failure, unexpected ownership, failed settlement or renewed flapping. Unattended use follows only after successful acceptance. Begin with monitor-only and dry-run checks of report spacing, timestamp progression, resets and failure closures; local fake-HA tests do not prove physical operation. Supervised acceptance requires direct requested/observed/settled comparisons and explicit stop conditions. On uncertainty or failed evidence, stop Boost and retain manual ownership. The approved change adds no independent safety hold, reserve-price rule, 5.5 kW cap, 50% SoC target or 20% reserve redesign. O5 reserve policy remains unresolved. The 27 September re-entry proposal is superseded by this approval, which covers the 120-second load coverage and monotonic elapsed-time requirements plus the 60-second load-report-gap limit.

## Morning Dump

Morning Dump is deliberate stored-battery export. While its existing time window, configurable floor, forecast feasibility, and safety rules remain valid, it may own `BATTERY_EXPORT` and use `Command Discharging (PV First)`.

Selecting discharge EMS requires a qualified `BATTERY_EXPORT` intent and a positive bounded requested export target. Early Morning Dump eligibility alone, a missing intent, or a zero/non-positive target must not select discharge EMS. This is an eligibility gate only: downstream authority, safety, and observed-settlement requirements remain mandatory. This rule does not change Morning Dump's configured floor, hysteresis, timing, or priority position.

While Morning Dump remains active and therefore keeps import permission closed, its early EMS branch must return explicitly: qualified deliberate battery export with a bounded target above 0.01 kW uses discharge EMS; otherwise it uses Maximum Self Consumption. Blocked active Dump must not fall through to negative-price grid charging or another lower-priority EMS branch. Qualified negative-import-price Dump retains discharge priority. Inactive Dump leaves independent charging policies unchanged. This fallback adds no export permission and does not bypass operator authority, independent restrictions or observed settlement.

Eligibility requires trusted timed refill feasibility. The model must not assume that a future Morning Slow relief condition will rescue refill feasibility; missing, untrusted, gapped, or insufficient evidence fails closed. The current operator floor remains 15%, recorded as operator configuration rather than a software default.

Do not convert Morning Dump into MSC surplus permission. Do not add a hard PV forecast floor unless later evidence and a separate approved change justify one.

## Morning Slow Charge

Morning Slow is a charging policy:

- it owns the configured ESS charging rate;
- EMS remains Maximum Self Consumption;
- PV MAX remains the normal configured maximum;
- it does not own export permission; under observed Automated baseline authority, the independently owned export ceiling remains the configured high ceiling;
- actual export is genuine MSC surplus;
- it never owns `BATTERY_EXPORT` merely because Morning Slow is active.

Morning Slow must not retain legacy measured-PV start/ramp/probe gates for its export ceiling. Do not add a hard PV forecast floor without separate evidence and approval.

Refill feasibility uses trusted timed detailed-forecast opportunity through same-day sunset minus the configured sunset cutoff. The configured Morning Slow end time ends this policy's ownership; it is not the refill deadline. If slow charging is infeasible but normal bounded charging offers strictly greater safe refill opportunity, release only Morning Slow's artificial charge cap. Missing or untrusted evidence cannot authorize relief, and no arbitrary 60-second stabilization applies.

Morning Slow's optional physical-relief settings remain `grid_connection_export_limit_kw` and `morning_slow_physical_export_headroom_kw`; both default to `0.0`. Both must be finite and positive, with headroom below the connection reference. The local partial-relief candidate uses `T = connection reference - headroom`, with requests bounded between the slow rate and normal trusted hardware capability. The operator values `15.0 kW` and `0.5 kW` give `T = 14.5 kW`; these are not new defaults. The old counterfactual export estimate remains diagnostic only and cannot authorize full normal charging. Trusted forecast refill relief retains its independent full-normal path and import charging retains precedence.

Physical relief requires genuine Morning ownership, observed Automated and exact MSC, no competing battery-export owner, trusted partial SoC/capability, and fresh coherent live PV/load/import/export reports. It does not own export permission, change the independent export ceiling or cap PV output. Positive measured import pauses increases without adding an import tolerance. Missing or regressing physical proof clears only physical relief; it does not cancel independent forecast relief.

Each changed successful completed automatic ESS charge write establishes a separate Morning command epoch. A desired proposal is distinct from committed relief and cannot stack before application. Same-value reassertions retain the epoch. A fresh matching setting report must be strictly later than the command. Before that first match only, a fresh nonregressing report of the single previous command may remain pending within the existing data-max-age window measured from the command, without feedback credit. An unexpected value, expired window, stale or regressed report resets relief. After the first match, contradictory reports reset relief; later matching reports do not move that first-readback barrier. Two advancing coherent four-flow cohorts strictly later than that barrier are required before another increase. Morning setting matching uses `0.001 kW`, distinguishing adjacent `0.01 kW` requests; all generic ESS, MSC and export settlement tolerances remain unchanged. Measured derived charging must be within `min(0.05 kW, last positive command step / 4)` of the confirmed cap; the initial baseline uses `0.05 kW`. These are local trial response bounds, not a physical settlement claim.

The local fixed policy reserves `min(0.05 kW, headroom / 2)` of measured export excess. Each rise is rounded down to `0.01 kW` and bounded by the remaining measured excess above `T`, headroom, an independent `0.4 kW` maximum step, and the remaining normal capability. Thus export exactly at `T` cannot trigger a fixed upward step. Export below `T - min(headroom / 2, 0.25 kW)` reduces relief by the measured deficit, bounded by existing relief. Export below `T - min(headroom, 0.5 kW)` clears relief. Three advancing cohorts are required after a reduction. These response and hysteresis choices passed local independent review; later supervised physical validation remains required before physical acceptance.

Configuration identity/day/capability/context changes, ownership loss, Manual/Force, untrusted or regressing flow/readback evidence, failed/fallback/pending/noncompleted application and cycle failure retire the Morning epoch. Dispatch rechecks physical context and authority around the ESS write and before recording completion; no reset write may bypass current authority. Partial relief below the full normal safe bound does not arm the existing Solar handoff obligation. Solar's controller and legacy Morning ramp/probe settings are not reused.

The generic connection reference may independently enable Solar's controller even with Morning headroom zero. Neither controller sets Sigenergy export permission to this reference or enforces a hard network export cap. Charging is a maximum setting, not a guaranteed absorption rate. Hidden PV estimates cannot authorize Morning feedback; physical enforcement, sensor accuracy and inverter dynamics remain independent.

## Event responsiveness

Relevant Home Assistant state and watched-attribute changes trigger event-driven optimizer cycles through a fixed 3-second pre-decision coalescing window. The deadline does not slide when more events arrive, allowing related telemetry bursts to produce one coherent decision without restoring the earlier zero-delay behavior.

There is no immediate first-event tick and no immediate catch-up tick. Events arriving during or after a cycle remain eligible for the next bounded cycle. Startup remains immediate, the 60-second heartbeat remains, metadata-only changes do not trigger, and actuator/readback settlement protections remain unchanged. The measured-proof dip deadline above may shorten an existing wait; no arbitrary 60-second Solar stabilization is part of this contract.

## Demand Window

Demand Window primarily owns import blocking. It does not implicitly own battery export, lower ordinary PV MAX, or convert ordinary economic export permission into deliberate discharge.

Observed ON blocks import. Observed OFF permits ordinary policy, subject to all other owners and safeguards. Missing, unknown, unavailable, stale, or otherwise untrustworthy Demand Window state also blocks import until trustworthy observation resumes.

Demand Window observations use a dedicated 360-second freshness maximum, reflecting the source's slower reporting cadence. A trusted current ON state has its normal import-block effect. Uncertainty does not gain trusted-ON export effects, create battery-export ownership, or by itself reduce normal PV MAX. Notification remembered state advances only from trusted observations.

Unless another explicit overlay or safety rule owns a different value, normal PV MAX and the MSC surplus ceiling remain available; failing Demand Window closed for import does not itself curtail PV or authorize battery export.

### Fallback recovery revalidates Demand Window (local O19)

Before permissive fallback import recovery, include Demand Window in the same
final read as operator/Remote EMS authority and MSC/export settlement evidence.
Only trusted current OFF within the existing 360-second freshness boundary
permits the opening. ON, unknown, unavailable, stale, malformed or conflicting
evidence requests the existing restrictive 0.01 kW import close through the
same dispatcher, with a fresh restrictive-authority check. Manual/Force takeover
or lost Remote EMS prevents automatic writes. This 0.01 kW value is the
existing restrictive sentinel; it does not represent permission to recover
import.

Initial Demand, Standby and Morning Dump import blocks remain binding despite a
later OFF report. The correction adds no timer, threshold, tolerance, setting or
ordinary-import rule, does not cover every import opening, and cannot guarantee
zero physical transient import. Other independently permitted ESS/PV recovery
and request-specific settlement remain unchanged. Pending/failed applications
still cannot certify permission or accounting coverage. Unknown cost alone is
advisory under the import-cost policy above; any independent authority,
permission, flow or settlement failure retains its existing protective effect.

## Trusted non-positive import price

The following policy is approved but not yet implemented. Trusted actual import price `<= 0 $/kWh` is an explicit high-priority charging owner:

- request Grid First;
- request the maximum safe/permitted grid-import capability;
- request the maximum safe/permitted ESS-charge capability in its separate domain;
- override Morning Slow charging and EMS ownership and override Morning Dump;
- remain subordinate to Demand Window import blocking, Manual/Force ownership, and hardware/safety limits;
- return to MSC plus slow charge when price becomes positive and Morning Slow is eligible;
- do not infer PV curtailment from non-positive import price alone.

A positive price must not take Morning Slow EMS or charging ownership through this policy. Exact-zero behavior when export value is extremely high and PV MAX behavior during non-positive import remain unresolved and are not defined here.

## Cheap-FiT exact-full exception

Cheap positive FiT below the ordinary export threshold remains a separate protected policy:

- below 100% SoC, the implicit path is closed;
- at exact 100%, a high ceiling may open only through the verified Automated plus exact Maximum Self Consumption PV-only path;
- trusted finite PV and load telemetry remain required, together with positive live PV presence strictly above `0.05 kW`;
- positive PV presence is not an adequacy test against the productive-solar threshold or the instantaneous site load;
- trusted battery discharge serving site load while grid export remains below the meaningful threshold is compatible with the MSC surplus ceiling;
- meaningful simultaneous battery discharge plus grid export remains fail-closed;
- unknown or untrusted battery-flow or grid-export evidence remains fail-closed;
- the high value is only an MSC surplus ceiling and never a request to discharge or export the battery;
- it creates no `BATTERY_EXPORT` owner;
- it never uses `Command Discharging (PV First)`;
- it must not be generalized into ordinary positive-FiT rules.

An independently configured positive-FiT policy remains separate and follows its own two-control contract.

## Telemetry and ownership safety

Where safety depends on observed state, service-call success is not observation. A successful HA-control `turn_on` call does not grant control authority; observed HA-control ON is required. Required observations must be available, fresh, finite, and from trusted sources. Unknown evidence fails closed when the safe export type or actuator ownership cannot be proven.

Control decisions requiring future-energy evidence must not use stale or untrusted aggregate forecasts. A selected forecast source carries its own trust and freshness provenance; malformed, boolean, non-finite, or out-of-window entries cannot prove a future negative-price condition. Permissive PV-surplus decisions require trusted live PV, load, and relevant Solcast evidence.

Derived battery flow from PV, load, and directional grid components requires finite, non-negative values, fresh timestamps, and temporal coherence within the established skew window. Trusted direct battery telemetry takes precedence. Negative directional grid-power readings are untrusted and must not be silently clamped into trusted zero.

Available discharge energy requires an explicit supported unit and a fresh, finite, non-negative value. Missing units must not silently default to kWh. A value slightly or materially above separately reported rated capacity remains trusted; when rated capacity is itself trusted, the bounded control value is clamped to rated capacity while the raw normalized diagnostic remains visible. When rated capacity is untrusted, no capacity clamp is invented. Invalid, unavailable, stale, non-finite, negative, or unsupported-unit telemetry remains fail-closed, subject only to the established near-full Solar exception for genuinely untrusted available-energy telemetry.

Unavailable, missing, unknown, stale, or non-finite actuator-state telemetry is not proof that import or export is safely closed. Deadband or a numeric default must not suppress a required safety-close request when the present actuator state is untrusted. Untrusted current grid-limit telemetry also cannot authorize a permissive opening; opening requires a trusted finite observation. Trusted finite current limits retain ordinary deadband behavior.

Dynamic grid import/export current-position readbacks use the live inverter telemetry boundary of 120 seconds and require provenance-bearing fresh observations. Missing provenance, stale values, and negative values are not current-position proof, cannot prove closure, and cannot authorize permissive opening; raw values may remain diagnostic. Restrictive closes remain allowed. Static `grid_export_limit_entity_max_kw` capability is separate from dynamic current-position liveness.

Safety-critical settlement requires provenance-bearing readback. Deliberate battery export must establish or set the intended export target before entering or changing discharge EMS. If an export-close request succeeds but settlement remains unproven, that uncertainty must not suppress an independent restrictive grid-import close; the overall application remains failed and unrelated permissive writes remain deferred.

Safe fallback closes export first, requests Maximum Self Consumption, and clamps ESS discharge while settlement is unresolved. Permissive recovery requires observed export closure and observed exact Maximum Self Consumption; successful service calls are not proof. If settlement cannot be proven, normal import, ESS charge/discharge capability, and normal PV MAX recovery remain withheld, although Demand Window may continue to own import blocking. Fallback never creates `BATTERY_EXPORT`; Manual and Force behavior is unchanged. Observing settlement of the fallback `0.01 kW` export-close request is an intentional safety requirement.

Fallback exact-MSC recovery proof must be fresh, provenance-backed and strictly later than the MSC request boundary, correlated to the observed EMS state. Stale, missing, unavailable, untrusted, pre-request or equal-timestamp reports cannot restore normal import or ESS capabilities. A genuinely later report of unchanged exact MSC may qualify; a cached string or accepted command cannot. Successful fallback recovery does not itself grant automatic export-reopening authority.

An independently owned restrictive Standby or negative-price PV MAX request remains effective during pending transition, transition completion, actuator failure and every fallback path, including successful settlement. A lower valid restriction must not be raised by normal PV recovery. Required independent restrictive PV, import and ESS safety writes must not wait for transition settlement; unrelated permissive writes remain deferred. Demand Window retains import blocking during fallback recovery. Independently active Standby Holdoff and Morning Dump also retain their grid-import close: fallback requests the 0.01 kW closed sentinel before waiting for settlement and cannot restore normal import permission while either owner remains active, whether settlement is proven or not. This includes active Morning Dump using MSC because its export is blocked; genuine preemption that clears Morning Dump ownership retains its existing behavior. A zero import target caused only by ordinary economic policy does not acquire Standby ownership; its established settled-fallback recovery remains unchanged. Manual/Force retain their own authority and settlement requirements.

Export start/stop notifications are classified from trusted measured grid export. A changed export ceiling alone is not proof that physical export started or stopped.

Manual and Force modes remain user-owned. Automated logic must not silently reinterpret them as ordinary MSC or deliberate battery export.

Negative-price, standby, freshness, remote-control availability, reserve, forecast, and other established safety policies keep their existing ownership and priority unless a separately approved change says otherwise.

## Authority, request settlement and fallback ownership

Automated control requires current verified Automated ownership and observed Remote EMS ON, rechecked after awaits and immediately before dispatch. Unknown authority fails closed. Preserve ordinary unattended restart/auto-enable after current Automated verification; a successful enable call alone grants no authority. No persistent OFF registry or mandatory restart handback is introduced.

Settlement is specific to the dispatched request. Conflicting actuator state/metadata observations cannot establish settlement; report timestamps must be coherent with state and update provenance. Deliberate discharge requires the intended bounded export target, not merely a lower safe value, proven by a fresh trusted report strictly after that target's dispatch boundary. Safety closes and bounded restrictive corrections retain their upper-bound semantics. Recheck settlement and authority before permissive recovery; a later contradiction or takeover invalidates prior proof.

Successful fallback releases only its temporary restrictions. ESS charge and discharge recovery remain bounded by independently owned decision limits and normal safe/trusted capabilities. Relinquished Solar charge ownership restores the otherwise applicable safe normal charge request; it cannot remove another owner's restriction. Demand Window import blocking and independent restrictive PV MAX remain effective through failed or successful fallback.

Approved O21 recovery semantics: classify positive ESS discharge as deliberate
battery-export capability only during ordinary dispatch (recovery is None).
Fallback retains its non-None recovery context and must still prove current
authority, request-correlated export closure and exact MSC before every
permissive recovery write. It must not require the failed proposal's old
positive export target to restore bounded house-serving capability under MSC.
Normal capability and independent decision limits remain binding. The primary
application stays failed even when its separate fallback succeeds.
Capability and policy values retain decision-time snapshot semantics; no
after-await tariff or hardware-cap refresh is added. Historical reproduction
and local implementation status are recorded in CONTROL_LIFECYCLE_REVIEW.md
and CURRENT_STATE.md.

An authenticated pending Manual/Force request is not cancelled by repeated unchanged Automated selector reports. Supersession requires a verified differing selector state transition strictly after the request, with coherent `request < last_changed <= last_updated <= observed report` evidence. Freshness alone does not prove an operator transition. Once superseded, subsequent writes and retries for the old request stop. Manual/Force targets, including the legacy 25 kW target, remain unchanged. Physical grid-export enforcement and ESS limits remain separate controls.

### Bounded retry for accepted restrictive settlement observations (approved local Stage A)

Eligibility has exactly two originating cases: (1) an accepted ordinary export-close request whose later report misses its short observation wait; and (2) an accepted restrictive fallback after proof of the accepted discharge target was delayed. A genuinely renewed retry is an origin-bound subtype that retains its originating cause and current identity and receives a new request boundary and budget; it is not another generic eligibility case. Generic startup MSC-pending behavior is unchanged. The 15-second recovery budget begins before the first restrictive dispatch and includes internal awaits. It does not cancel an in-flight HTTP call or establish that equipment responded. While pending, the event loop caps idle waits at one second, including debounce; actual cycle time may be longer when HA/service/read awaits run longer. The ordinary three-second primary target wait remains in place. An already accepted close or MSC request is not duplicated during the wait. Pending is not application completion. Existing fallback and the fresh, request-correlated close/MSC proof barrier remain mandatory before permissive recovery.

Each recheck must retain current authority, purpose, request identity/timestamp, exactness and transition phase. A phase conflict or any loss of those facts invalidates eligibility. Authority is checked after awaited work and before a charge-permission write; active Automated context is retired before Manual/Force or Remote EMS OFF handling. A recheck may reapply independently required import/discharge clamps and issue additional HA requests; it is not read-only. Existing fallback may re-close a late permissive request if an awaited opening crosses the deadline, then return a failed outcome. Failed restriction writes, rejected results and exceptions never qualify. At expiry, the attempt fails visibly; a later attempt requires a new real close-request boundary and a fresh 15-second budget, not an extension of the old one. Preserve the initiating cause and fallback history. This policy does not keep an Evening Boost admission through fallback or remove its existing 120-second requalification; Morning Dump minimum SoC remains 15% and Evening Boost target SoC remains 80%.

## Phase 2 transition contract

Returning from deliberate battery export to an MSC surplus ceiling requires a multi-cycle observed transition:

1. Close the export ceiling.
2. On a fresh, provenance-backed observation strictly after the close request, confirm export is actually closed.
3. Request Maximum Self Consumption.
4. On a fresh, provenance-backed observation strictly after the MSC request, confirm exact Maximum Self Consumption.
5. Only then reopen the permitted MSC/PV-only export ceiling, subject to all independent safety and ownership gates.

Entering deliberate battery export must settle the export target before selecting a discharge EMS mode.

No service-call result, cached request, reused snapshot, equal-timestamp report or assumed inverter response may replace later observed settlement. EMS state and report provenance must agree; freshness and request/observation timing must use a coherent clock.

Unfinished transitions remain restrictive across cycles, telemetry uncertainty and restart. Lost process-local evidence cannot authorize reopening; recovery requires the trusted observed sequence. Genuinely safe, freshly observed MSC at startup is distinct from an unresolved discharge-to-MSC transition and must not unnecessarily block otherwise safe Solar charging, fill-deadline recovery or provider-freshness protections. All independent charging and flow safeguards still apply.

The multi-cycle return sequence above is distinct from the emergency fallback command ordering defined under telemetry and ownership safety. Fallback keeps export closed and requires observed settlement before permissive capability recovery; it is not a shortcut to reopen export.
