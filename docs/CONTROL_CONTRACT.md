# Control Contract

This document defines durable approved control semantics, not current implementation status. Current commits, test counts, and immediate work belong in `CURRENT_STATE.md`.

Update this contract whenever an approved control-ownership rule, invariant, or transition contract changes. Do not change it merely to match accidental current code behavior; report the mismatch and obtain an approved semantic decision first.

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

Ordinary economic eligibility produces an MSC surplus ceiling, not a battery-discharge target. Time of day alone does not create stored-battery export authority.

The configured positive-FiT policy has two independent controls:

- `ALLOW_LOW_MEDIUM_EXPORT_POSITIVE_FIT` enables the separate export policy;
- `ALLOW_POSITIVE_FIT_BATTERY_DISCHARGING` determines whether that policy may deliberately export stored battery energy.

With battery discharging enabled, the qualifying policy is an explicit `BATTERY_EXPORT` owner. With it disabled, a verified Automated, exact-MSC, trusted-flow case may use a bounded `MSC_SURPLUS_CEILING`; otherwise it fails closed. The raw numeric policy target cannot manufacture battery-export authority.

For ordinary MSC flow interpretation:

- battery discharge serving site load while grid export is below the meaningful threshold is compatible with the MSC ceiling;
- meaningful simultaneous battery discharge and grid export is not presumed benign and closes conservatively;
- unknown, stale, unavailable, or non-finite safety evidence cannot broaden permission.

## Solar Surplus Bypass

The approved Solar Surplus direction is an MSC/PV-only surplus policy and never owns deliberate battery export. Its energy order is PV serving house load first, then enough battery charging to remain safely on the fill trajectory, then export of genuinely remaining PV while FiT is positive.

The primary energy budget is remaining-today forecast minus expected remaining load, battery fill need, and a conservative buffer. Detailed Solcast timing may refine that budget. Current measured PV-load surplus must independently support export, and the budget must be recalculated every cycle so export is reduced or stopped as conditions deteriorate. The old battery-capacity-times-2 and 1.25-times forecast heuristics are not the primary trigger.

Entry requires positive FiT, trusted qualifying inputs, strong net-energy proof, and current measured PV-load surplus strictly above `0.5 kW`. Continuation uses the same budget model with a smaller hysteresis margin and current measured surplus strictly above `0.2 kW`. Loss of trust, non-positive FiT, or a budget that no longer supports export ends the policy; re-entry must satisfy the full entry contract.

Solar Surplus may cap charging to expose genuine surplus only when the fill trajectory remains safely supported. It must never discharge the battery merely to create Solar Surplus export, must remain in Maximum Self Consumption, and must not create a `BATTERY_EXPORT` owner. The charging-cap, timing, and priority architecture requires a bounded design before implementation.

## Explicit deliberate battery-export policies

Existing policies that genuinely own deliberate battery sale remain distinguishable. These include qualifying Morning Dump, high-price export, export spike, Evening Export Boost, explicitly enabled positive-FiT battery discharge, and established solar/export or external overrides where their current policy owns discharge.

Each owner remains subject to its own eligibility and all independent safety guards. Generic ordinary tier eligibility is never an owner.

## Morning Dump

Morning Dump is deliberate stored-battery export. While its existing time window, configurable floor, forecast feasibility, and safety rules remain valid, it may own `BATTERY_EXPORT` and use `Command Discharging (PV First)`.

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

## Demand Window

Demand Window primarily owns import blocking. It does not implicitly own battery export, lower ordinary PV MAX, or convert ordinary economic export permission into deliberate discharge.

Observed ON blocks import. Observed OFF permits ordinary policy, subject to all other owners and safeguards. Missing, unknown, unavailable, stale, or otherwise untrustworthy Demand Window state also blocks import until trustworthy observation resumes.

Demand Window observations use a dedicated 360-second freshness maximum, reflecting the source's slower reporting cadence. A trusted current ON state has its normal import-block effect. Uncertainty does not gain trusted-ON export effects, create battery-export ownership, or by itself reduce normal PV MAX. Notification remembered state advances only from trusted observations.

Unless another explicit overlay or safety rule owns a different value, normal PV MAX and the MSC surplus ceiling remain available; failing Demand Window closed for import does not itself curtail PV or authorize battery export.

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

Available discharge energy requires an explicit supported unit, a finite non-negative value, and consistency with trusted capability. Missing units must not silently default to kWh.

Unavailable, missing, unknown, stale, or non-finite actuator-state telemetry is not proof that import or export is safely closed. Deadband or a numeric default must not suppress a required safety-close request when the present actuator state is untrusted. Untrusted current grid-limit telemetry also cannot authorize a permissive opening; opening requires a trusted finite observation. Trusted finite current limits retain ordinary deadband behavior.

Dynamic grid import/export current-position readbacks use the live inverter telemetry boundary of 120 seconds and require provenance-bearing fresh observations. Missing provenance, stale values, and negative values are not current-position proof, cannot prove closure, and cannot authorize permissive opening; raw values may remain diagnostic. Restrictive closes remain allowed. Static `grid_export_limit_entity_max_kw` capability is separate from dynamic current-position liveness.

Safety-critical settlement requires provenance-bearing readback. Deliberate battery export must establish or set the intended export target before entering or changing discharge EMS. If an export-close request succeeds but settlement remains unproven, that uncertainty must not suppress an independent restrictive grid-import close; the overall application remains failed and unrelated permissive writes remain deferred.

Export start/stop notifications are classified from trusted measured grid export. A changed export ceiling alone is not proof that physical export started or stopped.

Manual and Force modes remain user-owned. Automated logic must not silently reinterpret them as ordinary MSC or deliberate battery export.

Negative-price, standby, freshness, remote-control availability, reserve, forecast, and other established safety policies keep their existing ownership and priority unless a separately approved change says otherwise.

## Phase 2 transition contract

Returning from deliberate battery export to an MSC surplus ceiling requires a multi-cycle observed transition:

1. Close the export ceiling.
2. On a later trusted observation, confirm export is actually closed.
3. Request Maximum Self Consumption.
4. On a later trusted observation, confirm exact Maximum Self Consumption.
5. Only then reopen the normal high export ceiling.

Entering deliberate battery export must settle the export target before selecting a discharge EMS mode.

No service-call result, cached request, or assumed inverter response may replace an observed state. This settlement sequence is Phase 2 work and must not be partially improvised inside Phase 1 policy logic.
