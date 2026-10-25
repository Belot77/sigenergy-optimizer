# Solar charge-owner switching characterization - 25 October 2026

Status: **historical offline characterization complete**. The separately approved
local correction is recorded in [Solar re-entry stabilization](SOLAR_REENTRY_STABILITY.md).
The original tests-only workspace below remains unchanged; updated expectations
and live-provenance regressions live in the isolated correction workspace.
Workspace `C:\Projects\sigenergy_optimizer-charge-cycling`, branch
`test/solar-charge-cycling`, baseline freshly fetched `origin/main`
`c84a61b6a6ca1fb6d5f23c421f1f11ebf4a1ce49`.

The operator approved the proposed tests-only continuation. Two new test modules
and matching documentation are the entire new scope. Three uncommitted backlog
documents were copied from `sigenergy_optimizer-release-haos78`; those originals
remain preserved. No production/existing-test/configuration/version/workflow
file is changed. No commit, push, release or live action is included.

## O2: aggregate Solar budget switches with short load changes

`tests/test_solar_normal_charge_cycling_characterization.py` holds sunset,
Remaining Today, SoC/capacity, provider evidence and the detailed forecast fixed
while load changes at six-second intervals. It uses the supplied trace's Sydney
12:00:10/16/22 instants, 40.3 kWh capacity, 62.6% SoC, 35.9018 kWh remaining
forecast and 1.969 -> 2.399 -> 1.536 kW loads.

The real calculation projects current load across almost 7.5 remaining daylight
hours. A transient 0.430 kW rise adds over 3.2 kWh to that estimate, crossing the
strict protected-energy comparison despite 13.73 kW measured PV surplus. Real
ownership changes Solar -> normal -> Solar, with normal 21 kW charge permission
between a positive restrictive Solar request and zero Solar request. Repeated
crossings repeat the switching; a persistent deficit stays on normal charging.

The detailed curve (15.7 kW followed by fourteen 4.4 kW half-hours) is synthetic.
The tests do not reconstruct the historical 1.52 kW request. A fixed, independently
qualified provider generation and prior numeric request readback are fixture
evidence, not proof of physical application. The future-opportunity calculation
can still request zero while all its current gates pass; no minimum-charge rule
is introduced. A single aggregate forecast downgrade closes that permission and
restores normal charging, but does not simulate the full O18 forecast history.

Controls cover steady eligible loads, persistent failed budget, tariff below
1 cent, lost PV/load/remaining-forecast trust, incoherent PV/load observations
and unavailable Automated authority, with recovery. Those failures release on
the next decision; no hold through a failed hard gate is asserted.

## O6: Morning Slow eligibility and Solar select different charge owners

`tests/test_morning_solar_charge_handoff_characterization.py` uses eight
six-second decisions with capacity 40.3 kWh, SoC 50.8%, Remaining Today
41.2198 kWh and available-energy values
21.57/21.58/21.34/21.60/21.29/21.63/21.36/21.68 kWh.

The real Morning Slow comparison uses capacity minus available-discharge energy
and a configured base-load horizon. Solar's separate comparison uses SoC/capacity
and current load. Under the explicit fixture, the available-energy sequence
alternates Morning Slow eligibility. Its real timed-refill relief restores normal
21 kW permission; alternate Solar-owned requests are at most 2.82 kW. No owner,
eligibility, provider or charge-calculation helper is mocked.

The 2 kW base load, 1.35 Morning forecast factor, 12:00 Morning eligibility cutoff,
two-hour sunset margin, economic/accounting inputs, normal capability and detailed
forecast are explicit synthetic assumptions. The provider curve is 12 kW followed
by fifteen 4.85 kW half-hours. The short sequence uses the shared harness's naive
host-local wall-clock convention. It is not exact Sydney-time historical replay
or evidence of the installed settings. Available energy and SoC are independent
fixture observations, as they are separate inputs to the production comparisons.

Controls cover steady inputs on both sides, genuine forecast deficit, untrusted
remaining forecast, lost available-energy trust and lost detailed-source trust.
Loss of available-energy trust removes Morning Slow while independently trusted
SoC/capacity can still qualify Solar. Lost detailed-source trust removes Solar
and Morning detailed-forecast refill relief without manufacturing loss of the
remaining-forecast authority used by Morning eligibility.

## Validation and limits

The two new modules contain 13 tests and 18 subtests. Combined with the existing
aggregate-budget, Morning relief, Solar redesign and dynamic-ceiling modules:
**118 tests / 127 subtests passed**, zero failures, 202 existing warnings,
3.82 seconds. Each module received independent read-only cross-review: **GO**,
no concrete blocker. Environment-file loading was disabled before importing
application settings; temporary accounting data and in-memory HA doubles were
used. No raw trace or runtime data was added to Git.

The tests retain the real decision path and carry decision memory between ticks.
They never call control application or simulate observed MSC settlement. Assertions
exclude deliberate battery-export/discharge commands and import permission in
these fixtures; they do not prove inverter behavior, physical safety, exact live
configuration, sensor causes, lost energy or fill-objective reliability. No full
suite was run because production and existing tests are unchanged. Passing
characterization is a reproducible starting point, not a stabilization fix.

## Next staged scope and rollback

Next design should separate restrictive safety exits from admission/re-entry
stability at both eligibility boundaries. A conservative candidate is sustained
fresh eligible observations before re-entry, while failed budget, trust,
authority, tariff and other independent restrictions still close immediately.
Its durations, cross-policy priority and reserve effects need evidence and a
separately approved fix branch; these tests prescribe none. Keeping export
permission open through a failed aggregate budget is not justified by this work.

Risk: longer qualification can reduce useful export and still cannot guarantee
battery fill after a forecast downgrade. O18's deferral/minimum-charge tradeoff
therefore remains a separate policy review. O5/O9 diagnostic/reserve review,
parked O11 and existing live-acceptance gates remain unchanged.

No runtime rollback is required for this local tests-only checkpoint. Preserve
this branch and all unfinished originals; an implementation can start in another
approved branch from the verified baseline without discarding this evidence.
Any future behavior correction must update the characterization expectations
alongside tests for the explicitly approved replacement behavior.
