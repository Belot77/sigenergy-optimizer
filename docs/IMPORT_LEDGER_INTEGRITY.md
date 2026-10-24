# O16 import-cost ledger integrity

Status: O16 candidate integrated into the approved combined .77 workspace, `C:\Projects\sigenergy_optimizer-release-haos77`, branch `fix/combined-safety-trace-recovery`, based on `e387010b83f7b017460870b1b456025f49f7e0a5`. This document retains the separately reviewed O16 behavior and production hashes. The combined candidate is not yet committed, published or installed; installation remains the operator's later action. No live settings action is included.

## Problem and resulting behavior

The combined O14/O16 review found that configuration identity changes can hide ForceImport→BlockFlow→Automated or ESS 4→0 boundaries, and an A→B→A cycle between accounting captures could otherwise preserve stale permission. The combined candidate adds accounting-only invalidation at actual relevant identity activation and accepted validated direct Manual/ESS boundaries under the existing lock; permission can remain known-invalid across midnight. The resulting safety tradeoff is that source, owner or direct-control changes can pause applicable automatic battery sales for the affected day until a new known-inactive covered day. Operator targets and Manual export exemption remain unchanged. Boundary tests and final review are still in progress.

A failed legacy insert advanced the in-memory measurement checkpoint. Later capture could omit the failed interval or assign its energy a later tariff. A commit whose acknowledgement was lost could be duplicated by a blind retry. Synthetic 1 kWh at 40¢ plus 1 kWh at 5¢ should retain a 40¢ floor; the failed-insert baseline instead retained only 5¢ and allowed a 3.5 kW battery-export decision at 30¢. This demonstrates an offline evidence/control defect, not physical export, actual financial loss or HDD causation.

The candidate retains each interval's original evidence before storage retries. Automatic battery-export arbitration sees the latest captured interval and any incomplete coverage. A measured import tail after a confirmed close is retained once. Failure to retain an interval marks history unknown even if an older retry is already queued. Queue drainage alone cannot repair evidence that was never captured.

## Persistence and reconciliation

`ImportTopupLedger` separates measurement progress from acknowledged storage progress. Each immutable JSON payload includes a session/sequence ID, energy source, original tariff/trust, meter checkpoint, permission state and affected-day coverage. The bounded in-memory queue retains up to 256 events. A raised or lost acknowledgement leaves the identical payload queued.

Three additive SQLite tables hold new evidence:

- `optimizer_import_interval`: stable ID, canonical payload and interval values.
- `optimizer_import_checkpoint`: last acknowledged checkpoint and its event ID.
- `optimizer_import_coverage`: complete/unknown status and reason for each day.

Each new event, checkpoint and coverage update commits in one transaction. Failures explicitly roll back. Replaying an already committed identical payload is a no-op and cannot rewind the checkpoint; reusing its ID with changed evidence fails. Coverage marked unknown cannot be cleared by a later complete-day event. Legacy `optimizer_import_topup` rows remain intact and summaries include both old and new interval rows. Legacy rows alone do not prove complete coverage.

Database access remains synchronous. O15 event-loop/storage execution is separate and unresolved. This candidate does not diagnose or repair a failing disk.

## Measurement, permission and unknown coverage

The configured daily import-energy entity, grid-import power entity and local timezone identify the accounting source. Missing, negative or non-finite daily-counter data remains unavailable in ledger input; the existing UI zero default does not establish meter evidence. Existing finite sampling, same-day counter-delta/power fallback, 300-second ceiling, 0.01 kWh significance and tariff-trust policies remain in force. Accounting coverage does not prove actual inverter settlement, meter freshness or a physical energy allocation.

Capture runs before `_decide`, using prior applied import permission and observed positive permission. A completed automatic application or confirmed Manual observation can update permission after application. Failed, pending, OFF/enable/authority-paused no-ops do not certify a change. Confirmed closure retains the next measured tail without advancing the meter timestamp to the command time. Manual import costs are retained; Manual/Force execution keeps its existing exemption.

Pending writes or unavailable queries make the current summary unknown. Reconciliation can restore a previously covered day's trust only if every original captured event is acknowledged and no irreversible coverage gap exists. Untrusted tariff evidence remains untrusted after retry.

Startup/migration, restart, source/counter changes, observation gaps or clock rollback, unavailable counter data, unretained snapshots and queue overflow leave affected-day coverage unknown. This state is sticky for that day. Restored database access or an empty retry queue cannot clear it. A new day becomes covered only through a continuous, known-inactive midnight boundary with available counter evidence. Active or unproven import at midnight leaves the new day unknown too.

Expected tradeoff: applicable automatic battery-backed/mixed sales may remain paused beyond the current day. Independently proven PV-only MSC permissions and Manual/Force ownership retain their separate semantics. Existing reserve, tariff, capability, authority and settlement protections remain mandatory. No live setting change is needed or authorized by this local work.

## Verification and operational acceptance

Final full offline validation: **1,210 tests / 1,287 subtests passed**, zero failures, 206 existing warnings, 222.95 seconds. Focused validation: 244 tests / 268 subtests, 203 warnings, 17.10 seconds. Independent review was GO with no High/Medium blocker; the reviewer did not run tests. The first full run exposed fixture accounting-time prerequisites; the assertions and production code remained unchanged during those repairs.

Local tests use synthetic HA, in-memory SQLite and injected insert/commit/acknowledgement/query faults. They cover original tariff/trust retention, exact retry, payload mismatch, rollback, restart, legacy rows, source/day/counter changes, gaps, bounded-queue loss, missing meter values, final measured import before decisions, close tails, Manual accounting and unconfirmed application. Shared policy fixtures explicitly establish known synthetic accounting history; they do not relax the production unknown-history veto. Final counts and independent-review limits are recorded in `CURRENT_STATE.md` and `AI_HANDOVER.md`.

Before any separately authorized installation, verify source identity and an appropriate backup/reinstall and ledger rollback plan. After installation:

1. Monitor-only: inspect runtime/source, meter availability, accounting source and coverage reason. Confirm that startup history is unknown. Do not infer physical export from a requested limit or database status.
2. Offline dry-run: retain deterministic fault/retry and decision regressions. Do not inject faults, delete rows or fabricate complete coverage on a live system.
3. Separately authorized supervised live acceptance: compare fresh meter/tariff evidence, coverage, policy ownership and observed application/settlement. Check that an unknown history prevents applicable automatic battery sales and that independently qualified PV-only/manual behavior remains separate. Check a natural inactive midnight boundary when available; do not alter settings to manufacture one.

The original stale-archive/MSC investigation remains parked and its cause, including HDD causation, is unproven; O10 clock-recovery engineering is reopened in the approved .77 candidate. O11, O5 reserve-policy decisions and existing Phase 1/2 physical-evidence gates remain unchanged. Latest published release remains `.76`. The operator reports .76 installed on 24 October, while the latest supplied full installed proof remains `.75`. Local tests do not establish installation identity, physical operation or unattended Boost readiness.

## Reviewed production identity

Independent source/test/documentation review found no High/Medium blocker. The reviewer inspected source and tests but did not execute them. These SHA-256 values identify the reviewed local production bytes; they are not commit IDs or release/image identities.

| File | SHA-256 |
| --- | --- |
| `app/import_topup_ledger.py` | `b0b70fa33fd8b7f4b28030004f877965d367bcc3c07136d269d65afbc9a73cdc` |
| `app/state_store.py` | `610c667eee93a065e93d81b22bdaba88bd15f7e1f05460bb7a2016de001d27aa` |
| `app/optimizer.py` | `77a93460f286859b52e0966bf78a3ca08efc6e8b3905bb1659ffc44f912bd4e5` |
| `app/models.py` | `1d74d998492247b1b3fa4695c66abecfe45f73ea0f6e850a54e46290ed705dc1` |

## Rollback boundary

Before installation, a verified Home Assistant backup is recommended. Once .77 writes additive ledger rows, an older binary is not automatically ledger-safe: it reads the legacy table and does not understand the new interval/coverage tables. Never truncate, delete, copy or reprice those rows to force compatibility, and never fabricate complete coverage. If rollback becomes necessary after installation, stop automatic control and retain Manual/Force ownership, preserve the full database, and use a separately reviewed binary- and data-aware restore/reinstall plan. A source rollback after commit also requires a separately reviewed scoped revert. No database downgrade, live migration or backup manipulation is performed by this document.
