# State-store execution isolation (O15)

## Scope and current status

This is the O15 component record for the reviewed integration source on
`fix/storage-ingress-integration`, based on
`df5c64c04dac67885270bfa15be89db6a6dc2d0d`. O15 was originally implemented on
`fix/storage-execution-isolation`; its 1,307 / 1,305 full result, focused 221 / 191
result, and independent source/test/documentation review GO apply to that component
branch. The on-disk combined suite passed 1,355 tests / 1,305 subtests (206 warnings,
232.02 seconds); five focused modules passed 126 / 8 (202 warnings, 13.54 seconds).
Independent combined source/test/documentation review is GO, with no High/Medium blocker.
This records pre-commit verification; Git/PR establish the resulting commit identity. No publication, installation, live Home Assistant or
inverter action, or physical acceptance is established.

O17 ingress trust is included as the second component in this worktree; its
standalone evidence is recorded in [the ingress trust component record](INGRESS_TRUST_BOUNDARY.md).
The .77 release contains O14 configuration transactions, O16 accounting integrity,
and O10 trace clock recovery; O15 preserves those published protections.

## Confirmed mechanism

`StateStore` uses synchronous SQLite operations and a `threading.Lock`. At the
baseline, async optimizer and API paths call those methods directly. A contended
lock, slow query or slow commit therefore occupies the shared event-loop thread.
The async label on a caller does not make its synchronous database calls async.

An isolated in-memory characterization held the real store lock for 200 ms. A
callback due after 20 ms ran after 219 ms through the exact price-tracking endpoint
function, and after 203 ms through the real import-ledger summary path. Authentication
and request plumbing were stubbed for the endpoint characterization; no database
file, real Home Assistant request or control service was used. This reproduces
event-loop blocking, not the cause of any historical HDD, trace or MSC incident.

Relevant paths include initialization, pre-decision import accounting, import-cost
summaries, post-application permission accounting, audit records, price tracking,
presets, history queries and estimated-earnings fallbacks. Passive decision-trace
files already use a separate worker and are not the StateStore database.

## Required safety properties

- Move runtime database open, lock acquisition, queries, commits and close off the
  shared event loop. Keep worker count, admitted work and per-cycle waits bounded.
- Keep mutable import-ledger observation, permission, pending-event and coverage
  state on the event loop. Workers receive immutable event payloads or detached
  query arguments, never a mutable optimizer or ledger operation.
- Acknowledge only the exact pending events actually committed. Preserve original
  event IDs, energy, tariff, trust, source and date through retries, including a
  commit whose acknowledgement is lost.
- Reject stale summary results after a new observation, pending interval,
  permission change, day/source change or accounting invalidation. Returning from
  identity A to A through B cannot revive A's old accounting evidence.
- Slow, busy, failed or unconfirmed storage retains unknown-cost safeguards.
  Existing independently qualified PV-only and Manual/Force semantics stay separate.
- Cancellation or timeout does not establish that a running write was rolled back.
  Retain its execution slot until completion and reconcile its result once.
- Keep API storage failures visible. An accepted mutation with an uncertain outcome
  must not be reported as a confirmed rollback. Audit admission/failure remains
  visible even where the existing audit path is best effort.
- Preserve SQLite schema, transaction/replay semantics, control authority, MSC
  settlement, independent limits, tariff thresholds and export policy.
- Stop admission and producers before shutdown. Close a connection only after its
  active operation finishes, on its owning worker. Do not race close with I/O.

The current implementation uses one daemon worker, capacity eight including
running work, with at most seven ordinary jobs so accounting retains an admission
slot. A ledger service turn contains at most sixteen immutable events; the ledger
still retains at most 256 pending events. The startup-ready wait is at most two
seconds (failed startup adds a 50 ms cleanup wait), each API database wait at
most 250 ms, the pre-decision storage wait at most 50 ms per cycle, and normal
asynchronous shutdown drain at most 250 ms. An earnings-history request may
perform several sequential database waits; 250 ms is not an endpoint-wide bound. These bounds limit
waiting, not the duration of an already running operating-system call. Final
source review confirmed these implementation details; the full suite passed.

Production lifespan injects this worker into the optimizer. Standalone offline
construction retains the synchronous StateStore API for existing unit tests and
offline consumers. The offline path is not evidence of runtime worker coverage;
new tests must exercise the injected production path and its actual tick/decision
boundaries.

A Python thread can bound the event loop's wait and work admission. It cannot
forcibly interrupt wedged operating-system I/O or guarantee a hard process-exit
deadline. Do not spawn replacement workers or reuse a timed-out live connection.

## Changed files

- `app/storage_worker.py`: one lifecycle-owned worker, bounded admission,
  immutable payload/result handoff, detached waiters and worker-owned close.
- `app/import_topup_ledger.py`: deferred runtime capture and exact acknowledgement,
  generation-bound cached summaries, and pending/unknown coverage safeguards.
- `app/optimizer.py`: injected runtime worker, one bounded pre-decision wait,
  nonblocking audit/price jobs and acknowledgement-only price markers.
- `app/main.py`: worker initialization and exception-safe lifecycle ownership.
- `app/state_store.py`: close a partially initialized connection on schema failure;
  no schema or successful transaction/replay semantics change.
- `app/routers/api.py`: await storage results and expose rejected/unconfirmed
  outcomes without changing authentication or control authorization.
- `app/earnings.py`: both estimated-history fallbacks use the injected worker.
- `tests/test_storage_execution_isolation.py`: runtime/fault/cancellation tests.
  The existing lifecycle fixture additionally selects synthetic `:memory:`
  storage; its original assertions remain intact.
- README, changelog, current state, handover, roadmap and control contract explain
  local status, storage behavior, evidence and rollback limits.

## Validation and review

The initial tests-first module produced two expected baseline failures: a real
price-tracking API call delayed its heartbeat under synthetic slow storage, and
no bounded worker existed. Later fault/runtime cases were added with the fix;
this is not a claim that all final cases were run red against the baseline.

The final focused 12-module run passed **221 tests / 191 subtests**, zero
failures, 204 warnings, in 12.11 seconds. The final new module contains 32 cases.
The full suite passed **1,307 tests / 1,305 subtests**, zero failures, 206 existing
warnings, in 229.54 seconds. Independent source/test/documentation review is **GO**, with no High/Medium
blocker. The reviewer inspected source, test assertions and docs without
rerunning tests or accessing HA.

A separate cross-candidate check passed **102 tests / 6 subtests** in 8.58 seconds.
It used the actual O15 API module with the exact reviewed O17 ingress predicate
loaded only in memory; launcher tests read the O17 candidate launch files. It
covered both new regression modules plus existing trace-download checks. No
combined source branch, artifact, release or installed identity is claimed.


Coverage includes slow/locked storage, bounded admission and accounting capacity,
cancellation, partial commits, lost acknowledgements, exact retry, late completion,
stale summaries, actual configuration A-to-B-to-A / Manual / ESS boundaries,
midnight and pending overflow, API outcomes, both earnings fallbacks, price-marker
acknowledgement, startup failures and lifecycle cleanup. A real runtime tick first
allows a qualified sale with known history, then vetoes it after the final
expensive import; blocked storage stays unknown while the event loop and
Manual/ESS paths remain responsive. Existing O16 assertions remain intact.

The sole existing-fixture change supplies synthetic `:memory:` StateStore storage
for decision-trace lifecycle tests; no assertion was removed or relaxed. Full
checks include existing ledger, control, API, trace, earnings and release-marker
coverage. Passing these synthetic tests does not prove physical settlement.

For monitor-only, dry-run and live modes, any later separately approved operational
verification should observe storage health, fresh trace timestamps, accounting
coverage and requested/observed control state without changing safety settings.

## Rollback

Before commit, the isolated candidate can be withheld. Any committed rollback
requires a scoped reviewed revert. Preserve the complete existing database and all
O16 additive interval/coverage data; do not delete, reprice or replace runtime data.
No installation or database rollback is performed by this local development task.
