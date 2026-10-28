# Solar allocation lifecycle and planning - integrated offline characterization

28 October 2026. Branch `fix/solar-msc-planning-integration`, worktree
`C:/Projects/sigenergy_optimizer-solar-msc-planning`, baseline
`556cca8c040e3eea52029a8ac055a5c81f411018`. The original nine-test characterization
stage remains preserved in `test/solar-allocation-planning-haos84`. This integrated
copy follows the separately approved fill-progress policy and MSC request epochs.
No original stage is modified. No commit, push, release, installation or live action.

## Evidence and scope

The tests compose fake HA fixtures and use real decision, actuator application and
completion paths. Independent setting reports and four-flow observations are
explicit fixture events. Cancellation exercises real tick cleanup. They are
software characterizations, not a sensor calibration, inverter model, historical
trace replay or physical acceptance.

- A completed command plus advancing coherent post-command flows can earn 0.4 kW
  physical relief. The ESS setting report is separate passive evidence; accepted
  writes and setting readbacks do not prove physical device adoption.
- Signed aggregate `16.026 - 1.049 - 15.051 = -0.074 kW` still rejects relief despite
  a separate `+0.002 kW` direct battery report. Return to the current trusted
  fill-progress baseline; do not widen the balance tolerance. Each reused flow
  timestamp blocks upward qualification. Same-value commands retain their epoch.
- Provider expiry during a charge write restores bounded normal charging under
  retained authority. The expiry trigger follows the current nonzero approved
  floor. An unchanged provider poll cannot renew authority; a new credible
  generation can. Rejected generations cannot be repaired at the same timestamp.
- Manual takeover blocks further automatic recovery writes and feedback receipt
  commitment. Pending, cancellation and failed/fallback paths remain uncommitted;
  fallback requires independent later closure/exact-MSC proof before normal
  charging recovery. Demand Window import restrictions remain binding.
- Completed Morning partial relief below normal does not arm the full-normal
  handoff latch. Full-normal forecast relief does; restrictive Solar charging
  then requires both advancing reports and 30 seconds monotonic qualification.
  Export permission and independent owners retain their existing priorities.

## Approved fill policy and limits

Original .84 characterization showed that abundant future forecasts could defer
all present charging. The operator subsequently selected fill progress. The
integrated policy requests at least protected remaining fill energy divided by
hours to the existing deadline, retaining a higher urgent-current-interval
requirement, safe normal capability and upward 0.01 kW precision. Physical relief
may earn more allowance only under its existing strict evidence contract.

A 4 kWh physical fill need with only half an hour left and a 5 kW maximum has at
most 2.5 kWh remaining theoretical charging opportunity. Normal restoration cannot
recover missing sunlight or capacity. The floor permits progress and may reduce
immediate export; it does not guarantee actual charging, a full battery or a new
load/forecast model. See SOLAR_FILL_PROGRESS_TRAJECTORY.md for formulas and the
completed-total rebase contract.

## Validation and acceptance

The original tests-only stage passed 196 tests / 221 subtests, zero failures
(202 warnings, 19.28 seconds; 292 isolated temporary stores). Those results belong
to its original .84 policy; they do not validate this integrated copy. Combined
expectation updates preserve strict safety assertions. Root's 19 affected-module
run passed 365 tests / 495 subtests, zero failures (202 warnings, 80.60 seconds;
three memory / 615 isolated temporary stores). Eight new actual-reader interaction
methods passed 8 tests / 16 subtests (202 warnings, 1.20 seconds; 22 temporary
stores, zero memory/rejected paths). Independent integrated source/test review is
GO. The final guarded full suite passed 1,632 tests / 1,606 subtests, zero failures
(206 warnings, 274.24 seconds; 75 memory / 2,018 isolated temporary stores).
Independent documentation/scope review is GO. Physical acceptance is unproven.
See CURRENT_STATE.md for current source/review status.

Use the guarded runner with the bundled project interpreter and `-B`. It disables
dotenv, forces `_env_file=None` before application imports, restricts StateStore
paths to memory or isolated descendants of the system temporary directory, and
passes `-p no:cacheprovider`. Additional explicit test paths select combined tests.
Never use an unguarded application import or runtime database for validation.

Monitor-only acceptance should compare requested caps and owners, independent
setting reports, advancing coherent flows, source/provider/command chronology,
and application/settlement outcomes. Offline dry-run uses simulated HA and
isolated data. Supervised live installation/settings require separate approval;
passing tests and accepted service calls do not establish physical settlement.
Rollback is to withhold this candidate or later review a scoped revert. Never
reset or clean preserved original branches or remove runtime data.
