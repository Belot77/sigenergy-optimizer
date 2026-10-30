# 2.3.77-haos88 local release candidate

## Status and verified baseline

This local release-preparation candidate is on `release/2.3.77-haos88` at
`C:/Projects/sigenergy_optimizer-release-haos88`. It is not committed, tagged,
built, published or installed. This stage changes five established version
markers and release/status documentation, with no additional control changes.

Source [PR #70](https://github.com/Belot77/sigenergy-optimizer/pull/70) merged
normally at `2f0725602e339288efd1dbf5be07c229fa575c47` on 31 October 2026 at
10:17:29 AEDT (2026-10-30T23:17:29Z). Its parents are
`8f413773e53dca3864b70544546cb9934fd1af44` and
`ba812ed71e5ff9a233e87b2a621b5cf35a69d6c8`. Merge tree
`0c590ec2fa24089af9fda5524fcce34d53746e54` exactly matches the reviewed
12-file candidate. Independent normal-merge receipt review is GO.

The latest published and supplied installed release remains `2.3.76-haos87`,
tag `v2.3.76-haos87`, source `6a43077be1a59512bf44b1bb1c41aed410992c37`.
Supplied startup identifies it at 30 October 12:54:06 AEDT, and the trace identifies
it through 31 October 08:39:26 AEDT. Auto-update was last confirmed off on 29 October.
The .88 metadata commit, immutable source tag, build identity and OCI digests do
not exist yet; verify them during any separately authorized publication.

## Included behavior and limits

- Morning Dump previously re-entered as fill need crossed the same timed refill
  budget. After a successfully applied automatic Dump loses trusted refill
  feasibility, retire Dump for that identified morning window. This deliberately
  sacrifices later same-window export. The latch is process-local: restart loses
  it, and a fresh decision must pass all current eligibility, authority and
  settlement gates before qualifying. A later morning can qualify in the same
  process. The independent 15% SoC floor alone does not trigger retirement.
- A verified Solar generation could remain untrusted after temporary sun/sunset
  metadata uncertainty. Recovery permits only unchanged, fully revalidated evidence
  from the same source/session before its retained deadline. Changed or rejected
  generations, expiry, restart, continuity loss and source changes retain existing
  protections. Earlier schedules remain binding. No update is forced or trust persisted.
- An accepted primary MSC opening request missing the existing three-second proof
  wait can enter bounded restrictive recovery when the subsequent accepted fallback
  also lacks proof. The nonextendable 15-second budget starts before its first
  restrictive close. Fresh request-correlated close/new-MSC proof remains mandatory;
  contradictions retire the attempt. Rejected calls remain failures. If fallback
  fully settles in its original short wait, the initiating application still fails.
  This repairs one reproduced origin; other historical MSC errors remain unexplained.

Manual/Force authority, independent limits and owner priorities remain. Dump 15%,
Boost 80% and Boost's 120-second qualification are unchanged. Command acceptance,
reported settings and test success do not establish physical settlement.

## Validation

The reviewed integrated source passed the guarded full suite: **1,716 tests /
1,725 subtests**, zero failures (206 warnings, 283.08 seconds). Focused integration
passed **195 tests / 272 subtests**. Independent safety, interaction, tests,
documentation/scope, commit and normal-merge receipt reviews are GO.

Full-suite guards allowed 75 memory and 2,190 isolated temporary stores, with zero
rejected paths. Protected database size/mtime metadata stayed unchanged; contents
were not read. Dotenv was disabled and settings could not read env files. All
original production-stage and characterization worktrees remain preserved.

Local .88 version/source-pinning and focused safety checks passed **211 tests /
272 subtests**, zero failures across 16 modules (202 warnings, 25.62 seconds).
Guards allowed 393 isolated temporary stores, zero memory stores and zero
rejected paths. Protected database metadata remained unchanged; dotenv and
settings env-file reads were disabled. Independent final release-preparation
source/scope and documentation reviews are GO.
The full suite is retained from the exact reviewed merged control source; this
stage changes only version literals and documentation.

## Remaining work and later acceptance

Installation readiness requires separate publication approval, the reviewed metadata
commit, exact source tag, successful build, source/digest verification on both
platforms, normal metadata PR merge, GitHub release and final receipt. Installation
and live settings remain separate actions.

Use existing non-live Preview/Simulate tools to inspect intended decisions before
separately approved supervised live acceptance. No separate monitor-only mode is
claimed. Later live evidence must correlate request times, reports and actual flows
for Dump retirement/restart, provider metadata-loss recovery before its original
deadline, Morning-to-Solar charge/export handoff, fill-deadline behavior and accepted
MSC recovery/contradiction rejection. Boost needs an eligible forecast day under its
unchanged qualification. The supplied raw provider payload is absent, so the sole
cause of the prior live provider incident remains unproven.

Follow-up remains O4 Boost qualification retention/stability, O5 reserve/load/price
assumptions, O6 broader floor/depletion behavior, and O9 ownership/status semantics.
Unexplained legacy O11 outcomes and O20 non-positive-price Morning Dump redesign
remain parked. The O8 historical observation gap is irrecoverable; short Demand
Window import spikes are deferred and unconfirmed.

Safest local rollback is withholding this candidate. A later rollback requires a
separately reviewed scoped revert or verified immutable reinstall procedure.
Preserve .87 as the current immutable release; an operator restore procedure has
not been demonstrated here. No HA query/write, installation, restart, inverter/
battery/grid setting change, commit or publication occurred in this preparation.
