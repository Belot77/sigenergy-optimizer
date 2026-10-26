# Solar export and charging allocation - offline characterization

Date: 26 October 2026. The operator approved tests-first investigation on
`test/solar-export-charge-allocation`. Isolated workspace:
`C:\Projects\sigenergy_optimizer-solar-allocation`, based on freshly fetched
`origin/main` `45afeb660f01cca3854d9599b6935d2bab69d026`.
Remote: `https://github.com/Belot77/sigenergy-optimizer`.

Only tests and this investigation's documentation change. No production control,
configuration, tolerance, priority, minimum charging rule or release marker changes.
No commit, push, publication, HA access or live settings changes are included.
Existing worktrees and their unfinished work are preserved.

## Supplied evidence and its limits

The operator reports installed `.79`. Exact installed source is not established
by that report or by the trace, which contains no build identity. Published .79
is `2.3.68-haos79`, source `ea516ef6cabd9918dbea675694a9de3aa207c8af`.
Its optimizer differs from this baseline only in the runtime version marker;
.80's UI log filtering does not change the Solar controller.

The supplied 24-hour trace has 17,298 records, from 25 October 12:57:19 to
26 October 12:47:03 Sydney. Three sessions and gaps of 716 and 791 seconds are
present. After 10:00 on 26 October, 468 decisions have active Solar policy.
Of 320 Solar decisions observing export at least 14.8 kW, 219 request zero
ESS charging. The longest sampled continuous zero-request period at that export
level is 211 seconds, from 12:12:27 to 12:15:58. Relief sometimes operates:
its maximum in these Solar rows is 3.6 kW; the last row requests 0.8 kW.
These are sampled decisions, not a measure of forgone energy or physical limit
settlement. Requested ceilings and pre-application measured power are distinct.

Selected 26 October Sydney observations:

| Time | Recorded evidence | Supported interpretation |
| --- | --- | --- |
| 12:00:16 | Solar policy active, normal charge owner, 21 kW request, `morning_handoff_qualifying`, application succeeded; PV 19.887 kW, load 1.1 kW, export zero | Normal charging permission remains during restrictive-charge qualification. Helper success does not establish ESS readback. |
| 12:00:22 | Solar charge owner, zero request, qualified handoff, application succeeded | Qualification permits the existing restrictive Solar calculation. This row's measured flows precede its application. |
| 12:00:34 | PV 16.026 minus load 1.049 minus export 15.051 equals -0.074 kW; direct battery reports +0.002 kW; `physical_flow_untrusted` | Strict aggregate balance rejects this sample and resets relief. The residual's physical/sensor cause is unproven. |
| 12:45:35 | Failed application; fallback attempted and unsuccessful | Safe recovery is not established. Do not infer a successfully restored normal ceiling. |
| 12:45:57 / 12:46:03 | Successful zero request, then a later sample with PV 19.194 kW, load 0.975 kW, export zero and direct charging 18.163 kW | Timing alone does not explain high charging after the preceding zero request. Delay, readback and settlement remain unresolved. |
| 12:47:03 | Export 14.999 kW, charge request/relief 0.8 kW, application succeeded | Relief can reacquire; this does not prove stable allocation or hidden available PV. |

The later screenshot reports PV 19.9 kW, house load 1.1 kW, battery charging
18.87 kW and zero export at 73.8% SoC. It shows Automated/MSC and 25 kW export
permission, but no ESS charge-limit readback. It postdates the trace endpoint,
so the trace cannot identify that screenshot's exact application or gate.

## Confirmed mechanisms

The existing trajectory calculation permits a zero baseline when forecast future
charge opportunity covers protected fill need. The last record has approximately
47.66 kWh future opportunity versus 14.80 kWh protected need. This is the existing
O18 policy concern; no new minimum charging behavior is introduced here.

Physical relief cautiously raises that baseline using post-command measured
feedback. The current nonnegative aggregate-balance gate has no negative
tolerance. A rejected sample clears earned relief. All four PV/load/import/export
source streams must supply sufficiently new coherent evidence for upward steps.
Repeated rejected samples and waits interrupt the ramp. The trace lacks those
four source timestamps and the command boundary, so it cannot explain every wait
or assign all zero-charge periods to one source. Reasserting an unchanged command
does not reset its established feedback epoch; existing tests retain that control.

Relinquishing Solar's charge restriction restores the otherwise safe normal
request, including during Morning handoff qualification or loss of provider
authority. MSC can then use PV for house and battery before exporting. A 25 kW
export ceiling is permission, not an instruction to reserve 15 kW for export.
Mandatory fallback closes export, requests MSC and requires later trusted
observations before permitted recovery. Preserve that behavior.

An unsuccessful application restores the previous cached state and decision.
The status API uses those cached objects, so an old Solar label/limit may survive
a failed attempt even after fallback has changed requested controls. That is a
diagnostic limitation, not proof that it caused the screenshot or a new regression.

## Automated characterization

Four new tests across three modules describe current behavior:

- `test_solar_export_charge_allocation_physical.py`: helper-level feedback earns
  relief, loses it on the explicit -74 W residual despite +2 W direct battery
  power, then requires advancing four source streams and two qualifying
  observations to reacquire it. A separate stale/incoherent control cannot earn
  relief. Source timestamps are explicit synthetic assumptions.
- `test_solar_export_charge_allocation_handoff.py`: real decisions and the real
  completion hook, with an assumed completed application result, keep the normal
  21 kW request while PV/load reports are held. Advancing both endpoints admits
  the zero Solar request. MSC, export permission and battery-export ownership
  remain checked. This fixture never calls `_apply`.
- `test_solar_export_charge_allocation_fallback.py`: real `_tick` and `_apply`
  with fake HA inject a discharge-write failure after a zero charge request.
  Explicit later closure plus fresh MSC permits normal 21 kW recovery; cached
  MSC does not. The matrix also retains Demand Window import blocking, closed
  export, failed application recording and the previous cached status. Export
  closure always has a scripted later report; existing provenance tests supply
  the separate missing/stale closure protections.

No test simulates the inverter's allocation physics, proves that a requested
ceiling was physically obeyed, or reproduces the entire supplied trace.

Combined focused validation passed **105 tests / 136 subtests**, zero failures,
202 existing Pydantic deprecation warnings, in 29.71 seconds. This includes all
four new tests (12 subtests), the existing physical-relief, dynamic-charge,
Morning handoff, re-entry application/qualification modules and two applicable
MSC fallback/provenance cases. No full suite was necessary for this tests-only
change. Bytecode and pytest cache were disabled; settings did not load dotenv.
Temporary storage and fake HA isolated the tests from live systems.

Independent final source review of the three new modules is **GO**, with the
scope/physical-evidence limits above. Early fallback-fixture runs failed before
the intended path: its local decision clock and failure trigger were corrected.
Those setup failures are not claimed as reproduced production regressions. A
charge-write failure alone does not necessarily invoke fallback; the final test
explicitly injects a discharge-write failure to exercise that path.

## Next engineering boundary

The operator's desired allocation is export near the commissioned 15 kW site
limit while charging from additional PV. At the screenshot's rounded readings,
that arithmetic would leave about 3.8 kW for charging. The screenshot does not
establish hidden generation or whether that allocation was physically available
under all controls at that moment.

Next, review a narrow design for relief reset/reacquisition and useful allocation
diagnostics, separately identifying any O18 fill-strategy policy change. Do not
silently widen the balance tolerance, use forecast PV as physical proof, remove
source-provenance checks, force 15 kW export, or suppress safe fallback recovery.
The proposed correction requires its own specific branch approval.

For further supplied evidence, retain adjacent decision/application records with
timestamped ESS charge/export readback, four measured flow source timestamps,
direct battery power/provenance and the successful command boundary. These are
read-only evidence needs, not authorization for live experiments or settings.

Risk and rollback: this uncommitted tests/documentation branch can be withheld.
No runtime behavior has changed, and no release or installation is ready from
this investigation. O18 and physical allocation acceptance remain open.
