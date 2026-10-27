# Morning Slow partial physical relief - merged source, unreleased

## Scope and baseline

The source change was reviewed and normally merged through PR #52 on 27 October
2026. Reviewed source commit `57949e728a635fd1488f567d04ce8bd916b39fc8` is the
second parent of merge commit `140ecf474253d520a503e4dbe1259b4c9c2e4bf4`; the
merge tree is `25c8cd1f98a780be17a392b0a53a4a587a1ba086`. The original
`fix/morning-slow-partial-relief` branch and worktree remain preserved as provenance.
This release-preparation copy is on `release/2.3.72-haos83`, based on the merged
main commit. Its marker/documentation work is local and unreleased: it has not been
committed, pushed, tagged, built, published, installed or physically accepted.
The published .82 remains latest. No HA query, settings change or live action is
included or authorized here. The completed tests-only
`test/morning-slow-physical-allocation` worktree remains preserved.

## Observed problem and change

Selected observations in the separately preserved characterization reproduce
13 requests switching between 2 and 21 kW. Coherent measured charging above the
slow rate made the counterfactual stay above the configured export threshold,
even while actual export was near zero. That counterfactual previously released
the entire artificial Morning cap. The supplied .81 startup and trace do not
prove that every requested setting or physical flow settled at the same time.

The physical path now has a separate Morning feedback controller. It starts at
the bounded slow rate and permits only small partial increases supported by
measured export above the configured reference. Counterfactual export remains
diagnostic evidence, not authority to select the full normal charge rate.
Independent trusted forecast refill relief still selects bounded normal charging.
Grid-import charging retains precedence. Morning never gains battery-export
ownership, changes the independently selected export ceiling, or caps PV output.

## Evidence and response policy

Implementation and numerical policy passed local tests and independent review;
physical validation remains outstanding. Let S be
bounded slow charging, N bounded normal trusted capability, H configured Morning
headroom, E measured export and T the configured connection reference minus H.
Operator values 15.0 and 0.5 kW give T=14.5 kW; neither is a new default.

The local trial policy is:

- Reserve min(0.05 kW, H/2) of measured excess. Each proposed rise is rounded down
  to 0.01 kW and bounded by E-T-reserve, H, an independent 0.4 kW maximum, and N
  minus the current cap. At E=T there is no rise. At E=14.8/T=14.5/H=0.5, the
  first supported rise is 0.25 kW, giving a 2.25 kW cap from a 2 kW baseline.
- Require two advancing four-flow cohorts after the first matching post-command
  readback. Morning matching uses 0.001 kW, distinguishing adjacent 0.01 kW
  requests; generic ESS/MSC/export settlement tolerances stay unchanged. Later fresh
  matching readbacks do not move the first-readback barrier.
- Require measured derived charging within min(0.05 kW, last positive step/4)
  of the confirmed cap before another rise. Initial baseline tolerance is
  0.05 kW. A tiny response to a larger request cannot qualify another increase.
- Below T-min(H/2,0.25 kW), reduce relief by the deficit T-E, capped at existing
  relief. Below T-min(H,0.5 kW), clear it. Require three cohorts after reduction.
  For the operator 15/0.5 values, these boundaries are 14.25 and 14.0 kW.

These trial response bounds passed isolated tests and independent review.
Measured inverter performance and a guaranteed export floor remain unproven.
Physical acceptance requires separately approved supervised validation.

A completed automatic changed charge request starts an epoch. Reasserting the
same value does not restart it. Later increases require a fresh matching ESS
charge-limit report, strictly later coherent PV/load/import/export reports, and
charging consistent with the confirmed request. A setting report alone cannot
prove physical response. Repeated or regressing reports cannot earn progress.
Any measured grid import pauses increases; this adds no import tolerance.

Before the first new-target match only, a fresh report of the previous confirmed
command can remain pending within the existing data-max-age window measured from
the new command. It earns no flow confirmations. Later matching reports establish
the first barrier; unexpected values, stale/regressing reports, an expired window,
or a contradiction after confirmation reset relief. A 2.00 kW report cannot
confirm a 2.01 kW request. HA must report the setting precisely enough to distinguish
hundredths of a kW. Device precision is an unverified integration assumption; a
coarse or delayed report may prevent relief rather than justify a tolerance change.

Lost physical proof clears only physical relief. Independent forecast relief,
import priority, Manual/Force ownership, MSC settlement, capability bounds,
reserve policy and higher-priority owners retain their contracts. No reset write
may bypass current control authority. Failure, fallback, pending MSC transitions
and ownership changes invalidate the physical epoch. Solar's controller state
and the full-normal-only completed Morning-to-Solar handoff remain separate.

## Local validation

Tests-first run reproduced three failures before source changes: two threshold
cases selected normal charging without command/readback feedback, and a
counterfactual-only case retained normal charging. The initial collection also
included imported legacy tests; its total is not the final new-test count.
Final new-module validation passed 21 tests / 11 subtests, zero failures,
202 warnings, in 1.25 seconds. Guards recorded 0 in-memory and 28 temporary-path
StateStore constructions. The final full suite passed 1,525 tests / 1,450 subtests,
zero failures, 206 warnings, in 254.31 seconds; guards recorded 75 in-memory and
1,839 temporary-path constructions. Dotenv was disabled before application-test
imports. Final source/test and documentation reviews are GO for local readiness.

Reviewed pre-release-marker source SHA-256:
`74af93a57303a855f2feccbc080a0102d91d1f4e305ac032b71a2b4190cd5e53`.
It identifies the reviewed implementation before the five proposed .83 marker
substitutions; it is not the source identity of a release tag or image.
Thirteen unaffected Solar, MSC observation, Morning eligibility, import/export,
EMS, PV, discharge and completed-handoff functions remain byte-identical to the
verified baseline. Existing eight-file unfinished work and the separate three-file
characterization retain their original file-set hashes. Release-preparation
validation and review are recorded below. Publication requires separate approval and
image/source proof; installation and supervised live validation require separate
approval after publication. Physical readback precision and stability remain
unverified.
Dotenv must be disabled and StateStore construction limited to memory/system
temporary paths before importing application tests. No runtime database contents,
raw trace files, credentials or logs are added to the candidate.

The separate .83 release-preparation checks passed 37 tests / 11 subtests,
zero failures, 202 warnings, in 11.53 seconds. They cover release-version
consistency, source pinning and this Morning controller, with dotenv disabled
and StateStore guards recording 0 memory / 28 temporary-path constructions.
The five marker files differ from merged main only by their version strings;
independent metadata/docs review is GO for local preparation. No .83 image or
physical acceptance is established.

## Verification modes and rollback

- Offline/dry-run: use isolated fake HA fixtures with independent command,
  setting-report and power-flow clocks. Cover static and changing PV, delayed
  readback/response, failures, stale/skewed reports, ownership and policy handoffs.
  No global nonapplying production mode is assumed. The existing financial
  export-value dry-run setting is not a dry-run switch for inverter control.
- Passive monitoring: analyze operator-supplied traces for requested cap,
  setting timestamps and coherent later power reports. Compare policy ownership
  and forecast relief separately. This requires no live control changes.
- Supervised live checks require separate approval and installed build identity.
  Review the configured physical enforcement independently, then observe charge
  requests, reported settings and settled flows through sun/load changes and the
  Morning-to-Solar transition. Stop on lost authority or repeated unsafe behavior.
  Passing software tests does not prove physical acceptance or a hard grid cap.

Current rollback is to withhold this local branch; main and published .82 stay
unchanged. Any later source rollback should use a separately reviewed scoped
revert. No reset, cleanup, deletion, deployment or live rollback occurs here.

## Remaining limits

Physical connection enforcement, inverter dynamics, sensor accuracy and exact
settling time remain unproven. A maximum charging setting is not a guaranteed
minimum charging rate. Static energy-balance arithmetic cannot guarantee export.
Solar feedback allocation and recurring MSC settlement errors remain separate
open investigations. The local candidate is not an installation recommendation.
