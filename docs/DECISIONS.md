# Decision Log

This log records durable decisions and their rationale. Volatile checkpoint data belongs in `CURRENT_STATE.md`.

Append concise entries for material architectural or control-policy decisions and their reasons. Do not rewrite prior decisions to hide superseded history; record a changed or superseded decision in a new dated entry. Include operational tuning only when materially relevant, and always label it as operator configuration rather than a software default.

## 2026-09-04 - Normal Automated baseline is MSC

Decision: Normal Automated operation uses Maximum Self Consumption, normal configured PV MAX, the configured high export ceiling, and no deliberate stored-battery export intent.

Rationale: The inverter should dispatch genuine surplus under MSC; ordinary operation should not manufacture a battery-sale command.

## 2026-09-04 - A high export ceiling is permission

Decision: A high grid-export ceiling is permission for available surplus, not an instruction to export at that power and not authority to discharge stored energy.

Rationale: Numeric export capacity and energy provenance are different control concepts.

## 2026-09-04 - Deliberate battery export requires an explicit owner

Decision: `BATTERY_EXPORT` is valid only when a qualifying named policy owns deliberate stored-energy sale. Generic ordinary tier eligibility cannot own it.

Rationale: EMS selection must follow explicit intent rather than infer intent from a positive target.

## 2026-09-04 - Demand Window owns import blocking

Decision: Demand Window primarily controls import permission. It does not implicitly curtail normal PV MAX or create battery-export intent.

Rationale: Import and export ownership must compose independently.

## 2026-09-04 - Morning Dump remains deliberate battery export

Decision: Morning Dump may own `BATTERY_EXPORT` and use `Command Discharging (PV First)` while its existing window, floor, feasibility, and safety conditions remain valid.

Rationale: Unlike an MSC ceiling, Morning Dump intentionally exports stored energy.

## 2026-09-04 - Morning Slow owns charging, not the export ceiling

Decision: Morning Slow controls the ESS charging rate. It retains MSC, normal PV MAX, and the normal high export ceiling and does not create `BATTERY_EXPORT` intent.

Rationale: MSC can charge at the configured slow rate while independently exporting genuine excess PV. Legacy measured-PV export start/ramp gates unnecessarily suppress surplus.

## 2026-09-04 - Preserve the cheap-FiT exact-full distinction

Decision: Below the ordinary threshold, the implicit cheap-FiT path remains closed below 100% SoC. Exact 100% may open only through the verified MSC/PV-only path, and material or unknown battery flow prevents it.

Rationale: The narrow exception prevents PV curtailment without authorizing sale of stored battery energy.

## 2026-09-04 - No hard Morning Dump or Morning Slow forecast floor

Decision: Do not add a fixed 80 kWh or similar PV forecast floor for Morning Dump or Morning Slow at this time. Retain dynamic feasibility logic.

Rationale: No live evidence currently justifies replacing adaptive policy with a hard site-specific threshold.

## 2026-09-04 - Live tuning is not a software default

Decision: Record Forecast Safety Charging 1.30 and Morning Slow Charge Base Load 2.0 kW as current operator tuning only. Do not change defaults from 1.25 and 1.0 kW merely to match the live settings.

Rationale: Operator calibration and distributable defaults have different scopes and evidence requirements.

## 2026-09-04 - Phase 2 requires observed settlement

Decision: The deliberate-export-to-MSC transition must close export, observe closure later, request MSC, observe exact MSC later, and only then reopen the high ceiling. Service-call success is not observation.

Rationale: Inverter state must be proven before a ceiling is reopened.

## 2026-09-04 - Climate Manager follows Phase 2 and stabilisation

Decision: Climate Manager integration begins after Phase 2 is live-proven and a short ownership audit is complete, not after the experimental scheduler.

Rationale: The permission interface needs a stable upstream control foundation; experimental scheduling is not an integration dependency.

## 2026-09-04 - Dynamic solar scheduling is experimental future work

Decision: Develop any dynamic solar charge scheduler on a separate branch and require historical replay, shadow mode, and a bounded controlled live trial before considering merge.

Rationale: Economic optimization must be demonstrated against the live-proven safety baseline before gaining production authority.

## 2026-09-07 - Complete all audit remediation before Phase 2

Decision: Reopen Phase 1 and complete every audit-remediation package, full validation, and renewed live acceptance before beginning Phase 2. Phase 2 remains frozen until that gate passes.

Rationale: The live Morning Slow defect and broader authority/fail-closed findings invalidate the earlier Phase 1-complete gate.

## 2026-09-07 - Unknown operator ownership is not Automated authority

Decision: Permissive automatic actions require observed Automated ownership. Missing, unknown, unavailable, stale, or cached-only ownership does not grant Automated authority. Manual and Force remain user-owned.

Rationale: Automatic writes must not proceed when the operator's ownership state cannot be proven.

## 2026-09-07 - Demand Window fails closed for import

Decision: Observed Demand Window ON blocks import and observed OFF permits ordinary policy, subject to other safeguards. Unknown, unavailable, missing, stale, or otherwise untrustworthy state also blocks import until trustworthy observation resumes.

Rationale: Loss of the higher-priority import-block signal must not silently enable economic import.

## 2026-09-07 - HA-control service success is not authority

Decision: A successful HA-control `turn_on` service call does not grant same-cycle control authority. Observed HA-control ON is required.

Rationale: Service acceptance proves only that a request was accepted, not that control state changed.

## 2026-09-07 - Split Morning Slow policy from grid-transfer deadband

Decision: Do not tune `MIN_GRID_TRANSFER_KW` to repair Morning Slow. Separate the grid-transfer deadband from Morning Slow charging eligibility and ownership.

Rationale: Combining the configured 2 kW slow-charge rate with the 1 kW transfer threshold creates an unintended 3 kW PV-surplus gate and overloads an unrelated setting.

## 2026-09-07 - Preserve Evening Boost

Decision: Evening Boost behavior is intentional and must remain unchanged during audit remediation unless separately reviewed and approved.

Rationale: The audit did not establish Evening Boost as a defect, so remediation must not broaden into an unrelated policy redesign.

## 2026-09-07 - Trusted non-positive import is a charging owner

Decision: Once implemented, trusted actual import price `<= 0 $/kWh` is an explicit high-priority charging owner. It selects Grid First and the maximum safe/permitted grid-import and ESS-charge capabilities in separate domains; overrides Morning Slow charging/EMS ownership and Morning Dump; remains subordinate to Demand Window, Manual/Force, and hardware/safety limits; returns to MSC plus slow charge when price becomes positive and Morning Slow is eligible; and does not itself imply PV curtailment. Positive price must not steal Morning Slow ownership.

Rationale: Non-positive import has distinct economic intent, but still requires explicit ownership, separated capabilities, and preserved safety priority.

Unresolved: exact-zero import when FiT/export is extremely valuable, and PV MAX behavior during non-positive import. These are not settled by this decision.

## 2026-09-08 - Unknown current grid limits provide asymmetric evidence

Decision: Missing, unavailable, unknown, stale, or non-finite current grid-import/export limit telemetry cannot suppress a required safety-close command and cannot itself authorize permissive opening. Opening requires a trusted finite current-limit observation; trusted finite values retain normal deadband behavior.

Rationale: Untrusted actuator telemetry cannot prove that an actuator is safely closed. Safety therefore permits an idempotent closure request but withholds broader permission until trustworthy finite state is observed.

Implementation status: Production Remediation Package 1 satisfies this decision in automated validation only. It remains uncommitted, undeployed, and not live-accepted; Phase 1 is not complete.

## 2026-09-09 - Align the Cheap-FiT exact-full exception with MSC flow safety

Decision: Supersede the 2026-09-04 rule that any material trusted battery discharge closes the Cheap-FiT exact-full exception. The exception now uses the existing trusted ordinary-MSC flow distinction: load-serving battery discharge with grid export below the meaningful threshold is compatible with `MSC_SURPLUS_CEILING`, while meaningful simultaneous battery discharge plus grid export and unknown or untrusted battery/grid-export evidence remain fail-closed. The ceiling creates no `BATTERY_EXPORT` owner and cannot select a discharge EMS mode. The raw `pv_only_discharge_ok` predicate remains unchanged for policies that still intentionally require it.

Rationale: The central MSC flow model already distinguishes benign site-load service from evidence of stored-battery export. Reusing that contract prevents the exact-full branch from contradicting ordinary MSC safety without weakening simultaneous-export or telemetry-trust protections.

## 2026-09-13 - Separate Solar Surplus entry and continuation PV margins

Decision: Solar Surplus Bypass starts only above its existing 0.5 kW real-time PV margin and, once the immediately previous cycle genuinely owned an active Solar Surplus high ceiling under observed Automated ownership, continues strictly above a separate configurable 0.2 kW stop margin. At or below 0.2 kW it stops, and re-entry again requires more than 0.5 kW. Forecast hysteresis remains separately controlled by the existing 2.0 start and 1.25 continuation multipliers. No timer or smoothing is added.

Rationale: Live gate chatter around 0.5 kW and synthetic decision tests proved that, above the ordinary FiT threshold, the former single PV-margin boundary propagated into `25 -> 0 -> 25 kW` export-ceiling chatter. Ownership-scoped continuation removes that control chatter without granting lower-threshold entry to unrelated policies or creating battery-export authority.

## 2026-09-15 - Exact-full Cheap-FiT requires PV presence, not instantaneous adequacy

Decision: The exact-full Cheap-FiT MSC exception requires trusted finite PV and load telemetry and positive live PV strictly above `0.05 kW`. It does not require PV to meet the productive-solar threshold or remain within `0.1 kW` of instantaneous load. Observed Automated and exact Maximum Self Consumption ownership, the exact-full target, ordinary-MSC flow safety, and all independent fail-closed protections remain mandatory; the ceiling creates no `BATTERY_EXPORT` owner.

Rationale: Live `.56` evidence showed genuine `25 -> 0 -> 25 -> 0 kW` desired-ceiling chatter as sub-1 kW PV/load readings crossed the former `load - 0.1 kW` adequacy boundary while every independent ownership and flow-safety condition remained valid. Positive PV presence retains the narrow PV-only character without feeding instantaneous load variation back into ceiling eligibility.

## 2026-09-21 - Separate Demand Window freshness from inverter telemetry

Decision: Demand Window uses a dedicated 360-second freshness maximum, while dynamic inverter and grid-limit telemetry retains the 120-second boundary. Trusted current ON blocks import, trusted current OFF may permit ordinary import, and missing, malformed, stale, or untrusted Demand Window state fails closed for import without acquiring export, battery-discharge, or PV-curtailment ownership.

Rationale: The actual Demand Window entity reported unchanged ON state at approximately 295-299 second intervals, proving 120 seconds too short. Dynamic grid-limit entities reported unchanged values at approximately 58-61 second intervals, so 120 seconds remains appropriate for those readbacks.

## 2026-09-21 - Current grid-limit position requires fresh non-negative provenance

Decision: A dynamic grid-limit value proves current actuator position only when it has provenance, is fresh within 120 seconds, finite, and non-negative. Missing provenance, stale data, and negative values may remain diagnostic but cannot prove closure or authorize permissive opening. Restrictive closes remain permitted. Static export-capability metadata is a separate trust domain.

Rationale: Numeric finiteness alone does not establish a valid actuator position; sentinel-like negative values such as `-1` must not become safety or permission evidence.

## 2026-09-21 - Independent safety closes must remain independent

Decision: An export-close request whose settlement is not proven must not prevent an independent restrictive grid-import close from being attempted. The combined application remains failed, unrelated permissive writes remain deferred, and any import-close failure is reported.

Rationale: Uncertainty in one actuator's settlement must not suppress a separate safety action on another actuator domain.

## 2026-09-21 - Solar Surplus uses a net-energy budget

Decision: Solar Surplus remains MSC/PV-only and follows the order PV to house load, sufficient battery charging to preserve a safe fill trajectory, then export of genuinely remaining PV while FiT is positive. Its primary budget is remaining-today forecast minus expected remaining load, battery fill need, and a conservative buffer, refined by detailed Solcast timing and current measured PV-load surplus. Start requires trusted inputs, positive FiT, strong net-energy proof, and measured surplus above `0.5 kW`; continuation uses the same model with hysteresis and surplus above `0.2 kW`; loss of trust, non-positive FiT, or an unsupported budget stops it. It may safely cap charging but must never discharge the battery to create Solar Surplus export.

Rationale: The capacity-times-2 and 1.25-times heuristics do not directly establish genuinely exportable energy or preserve the battery fill trajectory. The charging-cap, timing, and priority architecture remains pending a bounded design before implementation.

## 2026-09-21 - Finalize Solar Surplus as a Phase 1 energy gate

Decision: Supersede the pending charging-cap portion of the earlier net-energy decision. Phase 1 Solar Surplus is an energy-gate-only MSC/PV-only policy: it owns neither an ESS charge cap nor import, never owns `BATTERY_EXPORT`, and never deliberately selects discharge EMS. Its battery fill target is 100% SoC by the trusted same-day sunset deadline. FiT must be at least `1 cent/kWh`. Trusted Remaining Today must be strictly greater than Solar-specific `K x (remaining load to sunset + fill need to 100%)`, where `K >= 1` and defaults to `1.20`. When fill need remains, trusted detailed Solcast intervals and trusted effective charge capability must separately prove sufficient fill opportunity before sunset. Missing or unsafe evidence fails closed. Aggregate and detailed forecasts are independent gates and are not summed.

Ownership: Morning Slow excludes Solar and retains charging ownership; deliberate-export owners such as Morning Dump win; Demand Window retains import ownership; Exact-full remains a separate PV-only branch; Manual and Force remain operator-owned. Entry requires measured surplus strictly above `0.5 kW`; owned continuation requires strictly above `0.2 kW`, and stopping restores the full entry requirement.

Rationale: Separating permission from actuator ownership preserves the existing inverter charging policy while proving that aggregate energy and physical time/capability can still fill the battery. It prevents Solar from creating stored-battery export or taking unrelated actuator domains.

## 2026-09-22 - Preserve the post-safety roadmap before Climate Manager

Decision: Architecture refactor/consolidation, repository/project cleanup, and a GUI/UX overhaul are explicit sequential roadmap phases after Phase 2 and the short control-ownership audit and before Climate Manager integration. Later phases cannot bypass earlier safety, validation, or live-proof gates. The old `refactor/msc-baseline-overlays` worktree is a reference only; useful ideas may be salvaged individually after fresh review, but the branch must not be merged wholesale.

The architecture phase preserves known-good behaviour unless a separately approved safety change requires otherwise, clarifies the boundaries between safety assessment, policy decisions, and HA/Sigenergy actuator application, and consolidates duplicated or dead paths only where protections and characterization tests prove that safe. It is not a wholesale rewrite for neatness. Repository cleanup is a separate subsequent phase that reconciles documentation, tests, branches/worktrees, artifacts, release history, configuration, and UI remnants without weakening protections or deleting branches/worktrees without explicit approval.

The GUI overhaul is an information-architecture and operator-UX redesign, not a control-logic or frontend-framework rewrite by default. It must preserve backend semantics unless separately approved and clearly distinguish permission from physical flow, policy eligibility from active ownership, requested actuator state from observed settlement, and deliberate battery export from ordinary MSC discharge serving house load.

Morning Slow future work is one bounded policy improvement combining forecast/refill-feasibility relief and 15 kW physical-export-limit relief, while keeping the two relief reasons independently diagnosable. It follows live testing of the existing immutable `.58` checkpoint and does not alter that release.

Rationale: Durable sequencing prevents safety gates and necessary consolidation from being skipped, lets the GUI reflect a stable architecture, and keeps distinct Morning Slow safety/physical constraints explainable without broadening the current release.

## 2026-09-27 - Distinguish synthetic refill from effective Solar arbitration

Decision: Preserve the raw Battery Full Safeguard calculation and diagnostics, but do not let a refill requirement created solely by the untrusted available-energy zero substitute veto an independently qualified MSC/PV-only Solar Surplus ceiling. The exception is final-arbitration-only and requires the initial safeguard closure, untrusted available-energy telemetry, a passing safeguard result using trusted SoC headroom, full Solar qualification, observed Automated and exact Maximum Self Consumption ownership, trusted PV/battery/grid flow that is PV-only-safe, no competing deliberate-export or higher-priority owner, and a winning source of exactly `solar_surplus_pv_high`.

The result remains `MSC_SURPLUS_CEILING` with battery-export owner `none` and Maximum Self Consumption. It cannot grant `BATTERY_EXPORT`, deliberate discharge EMS, ESS charging, grid import, or PV curtailment. Failed qualification or safety evidence retains the raw fail-closed outcome.

Implementation status: committed as `47c591be6bf920a82995b9f402c3efb202ffa5fe`; not versioned, tagged, built, published as a release, installed, restarted, or live-accepted.

Rationale: Untrusted available-energy telemetry must not manufacture a full-capacity refill need that contradicts separately trusted SoC headroom, but uncertainty also must not become a general export bypass. Comparing the raw result with the trusted-SoC safeguard result isolates the established defect while preserving every independent gate.

## 2026-09-27 - Define the future Evening Boost policy without implementing it

Decision: A future Evening Boost redesign remains an explicit deliberate `BATTERY_EXPORT` owner with a configurable minimum FiT (default `1 cent/kWh`), grid-export ceiling (default `5.5 kW`), and morning SoC target (default `50%`). It protects current household load multiplied by remaining overnight hours through the existing sunrise-plus-one-hour endpoint, plus a configurable overnight-consumption safety margin defaulting to `20%`. It starts after productive solar ends, has a configurable cutoff defaulting to midnight, and may resume only after two minutes of stable safe conditions. It has no fixed `1 kWh` restart threshold: actual stored energy above the protected reserve determines exportability. Tomorrow's solar forecast supports replenishment planning but is not energy available tonight.

Status: **not implemented and not live**. Independent ownership, reserve, forecast, actuator, and safety protections remain required. The interaction with the actual import-cost guard, higher-value-FiT protection, and physical discharge/grid-export capabilities requires a separate engineering review. Live operator settings are not software defaults.

Rationale: A reserve-based model reflects energy physically available overnight and avoids treating tomorrow's forecast as present stored energy, while stable-condition resumption prevents an arbitrary fixed-energy threshold from becoming a second hidden policy.

## 2026-09-30 - Trust and clamp available discharge energy separately

Decision: Fresh, finite, nonnegative, supported-unit available-discharge-energy telemetry remains trusted even when it exceeds separately reported rated capacity. When rated capacity is trusted, clamp only the control value to that capacity and retain the raw normalized diagnostic. When capacity is untrusted, do not invent a clamp. Invalid or stale telemetry remains fail-closed, with the established near-full Solar exception preserved for genuinely untrusted telemetry.

Rationale: Telemetry plausibility and bounded actuator input are separate concerns. An over-cap reading can remain usable evidence while the control calculation stays physically bounded and auditable.

## 2026-09-30 - Safe fallback requires observed settlement before recovery

Decision: Safe fallback closes export first, requests Maximum Self Consumption, clamps ESS discharge while unresolved, and restores permissive import, ESS charge/discharge capability, and PV MAX only after export closure and exact MSC are observed. Demand Window may retain import blocking. Fallback creates no `BATTERY_EXPORT` owner, and successful service calls do not count as settlement.

Rationale: Preserving house supply after a failed primary application must not convert requested actuator state into assumed state or reopen other permissive capabilities before the inverter proves a safe baseline.

## 2026-09-30 - Morning refill uses trusted timed opportunity and bounded relief

Decision: Morning Dump remains deliberate `BATTERY_EXPORT` and requires trusted timed refill feasibility without assuming future Morning Slow relief. Morning Slow remains a charging-only MSC policy; its end time ends ownership rather than defining the refill deadline. Refill opportunity runs through same-day sunset minus cutoff. If normal bounded charging offers strictly greater safe refill opportunity than the slow cap, release only that artificial cap.

Rationale: A policy must prove its energy plan from evidence available now. Selective charge-cap relief protects refill feasibility without taking export, import, PV, or battery-export ownership.

## 2026-09-30 - Physical export relief is not a hard export cap

Decision: `grid_connection_export_limit_kw` and `morning_slow_physical_export_headroom_kw` default to `0.0` and are disabled until configured. Coherent measured site export at the configured threshold may release Morning Slow's artificial charge cap; it does not set Sigenergy export permission or enforce a network cap. Discussed `15.0 / 0.5 kW` values are future operator configuration, not defaults.

Unresolved: Before live configuration, decide whether 15 kW is only the relief threshold or a hard network/export limit that must never be exceeded. A hard-cap meaning requires further design.

Rationale: Charging-cap ownership and network export enforcement are different actuator responsibilities and must not be conflated.

## 2026-09-30 - Restore fixed bounded event coalescing

Decision: Supersede the zero-delay event-response approach introduced at `11ae480`. Relevant HA events use a fixed, non-sliding 3-second pre-decision coalescing window, with no immediate first-event or catch-up tick. Startup remains immediate, the 60-second heartbeat remains, and events arriving during or after a cycle remain eligible for the next bounded cycle.

Rationale: The original 3-second delay was a deliberate anti-thrash and telemetry-coherency safeguard. A bounded fixed deadline preserves prompt event-driven control without making sequential sensor updates separate inconsistent decisions.

## 2026-09-30 - Decouple Evening Boost from the ordinary export tier

Decision: Supersede the unimplemented 2026-09-27 Evening Boost redesign. Evening Boost now uses dedicated `evening_boost_min_feedin_price`, default and hard minimum `$0.01/kWh`, with no arbitrary upper bound. It may own `BATTERY_EXPORT` as `evening_export_boost` below the ordinary export-tier threshold when every existing eligibility and safety gate passes. Sub-one-cent export remains blocked, ordinary positive-FiT export gains no battery-export ownership, and `export_limit_low` remains the ordinary tier output rather than an Evening Boost ceiling. No 5.5 kW redesign is introduced.

Rationale: Evening Boost has distinct deliberate-export intent and should not be accidentally disabled by an unrelated tier boundary, while the absolute one-cent value floor and all reserve, refill, import-cost, forecast, ownership, and settlement protections remain intact.

## 2026-10-03 - Permit bounded dynamic Solar ESS charge-ceiling ownership

Decision: Supersede only the "Solar owns no ESS charge cap" portion of the 2026-09-21 Phase 1 energy-gate decision. Preserve both historical 2026-09-21 entries and all unrelated eligibility, export, safety, and ownership semantics. Only after final arbitration selects `solar_surplus_policy_active` may Solar reduce the existing normal safe/trusted ESS charge request; it must never increase it. Morning Slow remains the higher-priority charging owner and excludes Solar, Demand Window retains import ownership, and Manual/Force remain user-owned. Solar retains Maximum Self Consumption, normal PV MAX, and `MSC_SURPLUS_CEILING`; it never owns `BATTERY_EXPORT` or deliberately selects discharge EMS.

The ceiling requires stricter fresh, trusted, continuous detailed forecast evidence, trusted current load, battery SoC/capacity, same-day sunset, and effective normal charging capability. Protected fill need is Solar safety factor K times energy to 100% SoC. Deduct future detailed charge opportunity strictly after the current interval, using PV minus current load, bounded normal charging power, and actual overlap hours. Allocate only the remaining required energy to the current interval's remaining hours; round positive requests UP to 0.01 kW within the existing normal safe/trusted capability/request. Abundant future opportunity may permit zero charging. Missing, stale, gapped, invalid, or untrusted evidence releases only this charge restriction and immediately restores the normal request. Existing Solar eligibility, including complete current-day detail with old parent metadata, remains independent; old parent freshness cannot authorize the new restriction.

Rationale: Solar should export genuine surplus earlier when trusted detailed forecast opportunity proves the battery can still safely reach 100% by sunset, rather than letting the inverter consume all available PV at the normal charging limit. The bounded dynamic ceiling preserves the fill trajectory while retaining MSC/PV-only semantics and all higher-priority owners. It provides no stored-battery export authority.

Status: implemented and validated locally for candidate `2.3.52-haos63`; uncommitted and unreleased, not part of operator-confirmed live `2.3.51-haos62`. Build, publication, manual installation, and controlled live Solar acceptance remain outstanding. Phase 2 remains frozen until `.63` is built, installed, and live-accepted.

## 2026-10-03 - Keep Phase 1 open for Evening Boost transition stability

Decision: After controlled `.63` Solar live acceptance, Phase 1 remains open for the separately confirmed Evening Boost transition-stability defect. Characterize and remediate it narrowly, then obtain live acceptance before starting Phase 2. Keep the two frozen Phase 2 transition tests unresolved until both Phase 1 items are accepted. This sequencing does not specify an Evening Boost fix or claim that `.63` is committed, published, installed, or live-accepted.

## 2026-10-05 - Trust successful Solcast provider refreshes for Solar charge freshness

Decision: Accept the externally reviewed BJReplay/ha-solcast-solar v4.6.1 success contract at tag commit `34e1d007e9d4a9b7a783520d723fcd05adb2ff9a`: advancing API Last Polled represents a successful ordinary provider refresh. Replace only dynamic Solar ESS charge-ceiling dependence on Forecast Today's 600-second HA observation age with process-local provider authority. Bootstrap and discontinuity recovery require a baseline followed by a credible successful timestamp advance, independent strict detailed-payload validation, and retained scheduled-deadline enforcement. Early manual/forced refreshes cannot forgive outstanding scheduled obligations. All existing control safeguards and global forecast consumers remain unchanged.

Rationale: Forecast Today legitimately remains unchanged between provider refreshes while Remaining Today and Power Now recalculate every five minutes. A shared observation-age timeout therefore revokes charge authority prematurely. Conversely, schedule advancement or `last_attempt` cannot prove success or renew authority. Retained deadlines and sticky source epochs prevent missed scheduled refreshes and lost discontinuities from preserving a reduced ceiling. `dataCorrect` is row-count evidence only and is not mandatory because legitimate DST days can have fewer rows.

The provider owns conformance of a successful response to its documented contract. Sig Opt validates exposed structure and control safety; independently detecting hypothetical HTTP-200 responses that violate that external successful-response contract is outside this accepted trust boundary. No arbitrary provider-age timeout, grace setting, persistence, forced poll or unrelated forecast redesign is introduced.

Status: locally validated unreleased candidate based on live `.65` / `9965e79`; no deployment or live acceptance is claimed. Phase 1 remains open and the two Phase 2 settlement failures remain frozen.
