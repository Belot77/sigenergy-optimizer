# Solar fill-progress trajectory - approved local integration

Source [PR #60](https://github.com/Belot77/sigenergy-optimizer/pull/60), head
`a5286581f402038be06375e45b62b525e65eb3e1`, merged normally at
`aefba54dddcaace1e3b318bbf6cca2a282d6c3a3` on 28 October 2026.
The exact reviewed tree passed 1,632 tests / 1,606 subtests and independent
source/test/docs/scope review. This document defines the reviewed policy and
retains its original standalone validation history; those historical source hashes
are not the future .85 container source identifier.

Local `2.3.74-haos85` preparation changes only five version markers and status
records. It is not published or installed. See HAOS85_RELEASE_CANDIDATE.md and
CURRENT_STATE.md for current release checks and remaining approval gates.
Existing work remains preserved; physical acceptance is unproven.

## Operator choice and formula

Fill progress takes priority when available PV cannot support both the desired
export and charging progress. The existing provider, ownership, detailed coverage,
load, SoC, capacity, sun/deadline and safe charge-capability gates remain mandatory.
Inside the admitted dynamic-charge calculation:

```text
protected_fill_kwh = existing K x rated capacity x (100 - observed SoC) / 100
urgent_current_kw = max(0, protected_fill_kwh - future_opportunity_kwh) / current_interval_hours
fill_progress_floor_kw = protected_fill_kwh / hours_to_existing_fill_deadline
request_kw = min(normal_safe_cap, max(urgent_current_kw, fill_progress_floor_kw))
```

Use Decimal arithmetic and existing upward 0.01 kW rounding without exceeding the
normal safe/trusted request. Partial current/final intervals retain actual overlap.
For example, 6 kWh protected need and five remaining hours gives a 1.20 kW floor,
even if the future forecast appears ample. A higher urgent need still wins.
The floor/horizon/source are trace evidence; they do not create authority.

The floor is a lower bound on the requested maximum charging allowance, not a
physical minimum charging rate. MSC still determines actual energy allocation.
Insufficient PV, changing load, taper, hardware capability and expiry can prevent
fill. ESS charge-setting readback remains passive evidence; a completed-total receipt
does not prove that the inverter physically adopted or obeyed that cap.
No fixed kW setting, price change, import permission, battery-export intent
or new load/forecast model is introduced. Exact-full, higher-priority owners,
Morning handoffs, provider expiry and safe normal-charge restoration remain.
Startup still requires a provider baseline followed by a credible advance.

## Stability and completion contract

A floor-only ten-minute synthetic trajectory exposed seven cap collapses solely
from 0.01 kW baseline changes. Recomputing the floor must not discard an otherwise
valid completed total each time SoC/time changes. The local candidate therefore
requires a separate completed-total receipt and a retain-only same-context rebase.

The receipt must originate in real successful automatic application completion
with the actual bounded command, same relief-state object and current source/
control/provider/deadline context. Accepted individual writes, decision targets,
completion-hook booleans, no-op, fallback, pending and failed/cancelled application
cannot mint it. All added awaits must precede applicable final permission checks;
rejecting later evidence must retire any prior receipt.

A pure baseline rebase may retain the earlier completed total, bounded by current
normal capability and current baseline. It grants no upward step, consumes the
present cohort, clears upward confirmations and preserves retry/report high-water
and unchanged-command timing. A changed total requires a new successful command
and later feedback. Newer downward feedback retires or clips the old candidate
immediately, including before the reduced command completes. Hard reset, negative
signed balance, stale/regressed evidence, context/authority/provider loss and
uncommitted application clear it. Legacy static helper calls retain their reset
rules. See CONTROL_CONTRACT.md for the complete current local invariants.

## Combined integration requirements

The five original stages remain preserved and uncommitted. The approved integration
must preserve both MSC pending-request and Solar completion invalidation and exact
request/report boundaries. The shared startup fixture must retain actual-reader
provenance. Earlier lifecycle characterizations need current floor expectations
and a nonzero charge-write expiry trigger, without relaxing any safety assertion.

Combined regressions must cover pending-to-settled Solar completion, expiry and
reconnect/cancellation, replaced or regressed final proof, passive diagnostic
failure isolation, provider/flow/dip expiry during final reads, Manual/Force and
independent restrictions, and reserve projections above full capacity remaining
passive. Original standalone passes cannot establish combined correctness. Root's 19
affected modules passed 365 tests / 495 subtests, zero failures (202 warnings,
80.60 seconds; three memory / 615 temporary stores). Eight new actual-reader
interaction methods passed 8 tests / 16 subtests (202 warnings, 1.20 seconds;
22 temporary stores, zero memory/rejected paths). Independent source/test review
is GO at integrated optimizer SHA-256
`44e70ab7c83c2b4f26e80f1c92f5cbc8c5344e1cbba5cd7ce330d659fc7553f6`.
The final guarded full suite passed **1,632 tests / 1,606 subtests**, zero failures
(206 warnings, 274.24 seconds; 75 memory / 2,018 isolated temporary stores).
Source/tests remained frozen and dotenv disabled. Scope is 32 files: one production
module, 23 test/runner files and eight documents. Independent documentation/scope review is GO. Physical acceptance is unproven. Current combined results belong
here; the section below records only the preserved standalone policy stage.

## Standalone validation history and remaining limits

Tests-first regressions reproduced missing positive floors and missing diagnostics
on the unchanged baseline. Source and adversarial-test independent review are GO,
with no remaining High/Medium findings. The 19 new policy/receipt methods cover
rounding, urgent needs, command/receipt provenance, context loss, downward feedback,
late authority loss, cancellation and final MSC report chronology. Focused validation
passed 206 tests / 237 subtests, zero failures (202 warnings, 32.62 seconds; 312
isolated temporary stores, zero memory or rejected paths).

The first guarded full suite passed 1,581 tests / 1,544 subtests and found 12
old-policy numeric expectations in three additional test modules (206 warnings,
270.35 seconds; 75 memory / 1,945 isolated temporary stores). Exact method-scoped
corrections were derived from fixture energy/deadline arithmetic. Three complete
affected modules plus the new policy tests passed 101 tests / 108 subtests, zero
failures (202 warnings, 16.46 seconds; three memory / 101 isolated temporary stores).
Independent expectation review is GO; all ownership, rejection, restoration and
post-freeze Manual assertions remain. Production source stayed frozen. The final
guarded full-suite rerun passed **1,593 tests / 1,544 subtests**, zero failures
(206 warnings, 270.82 seconds). Dotenv remained disabled; the guard allowed
75 memory / 1,945 isolated temporary StateStore constructions. Independent source,
adversarial and documentation reviews are GO; reviewers did not rerun the suite.
Original standalone scope: 21 files, comprising one production module, 13
test/runner files and seven documents. Original standalone source SHA-256:
`9a985a69713910decdd1afef102a8950a392e3c19cc7fec4545d5cd35d941488`.
That standalone pass establishes only the original component readiness; current
combined validation belongs to the integration section above.

The ten-minute simulation assumes measured charging equals the prior cap and
supplies enough PV for export, load and charging. It demonstrates no software cap
collapse under that synthetic plant; it does not establish deficit-PV allocation,
inverter acceptance, physical stability or deadline fill. Existing assertions change
only where the approved policy changes allocation; safety/authority/rejection
assertions remain. Synthetic tests do not calibrate sensors or model inverter physics.

Future monitor-only review should compare requested floor/total, actual charge
setting reports, advancing coherent flows, receipt/command chronology, owner and
provider/fill deadlines. Offline dry-run uses fake HA and guarded memory/temporary
storage with dotenv disabled. Separately approved installation and supervised
live evidence are still needed; actual charging, fill completion, device precision
and stable export are unproven. Historical replay/shadow acceptance is separate.

Risk: less immediate export, sensitivity to the existing current-load/forecast
model, and new feedback interactions. All current independent protections remain
binding. Rollback is withholding this local branch or a reviewed scoped revert
if later committed. Never remove runtime archives/databases or overwrite existing
unfinished branches. All five original stages remain preserved; AI_HANDOVER.md lists their paths,
standalone validation and the approved combined integration status.
