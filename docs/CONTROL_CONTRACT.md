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
- the export ceiling remains the configured high ceiling;
- actual export is genuine MSC surplus;
- it never owns `BATTERY_EXPORT` merely because Morning Slow is active.

Morning Slow must not retain legacy measured-PV start/ramp/probe gates for its export ceiling. Do not add a hard PV forecast floor without separate evidence and approval.

## Demand Window

Demand Window primarily owns import blocking. It does not implicitly own battery export, lower ordinary PV MAX, or convert ordinary economic export permission into deliberate discharge.

Unless another explicit overlay or safety rule owns a different value, normal PV MAX and the MSC surplus ceiling remain available.

## Cheap-FiT exact-full exception

Cheap positive FiT below the ordinary export threshold remains a separate protected policy:

- below 100% SoC, the implicit path is closed;
- at exact 100%, a high ceiling may open only through the verified Automated plus exact Maximum Self Consumption PV-only path;
- material trusted battery discharge above the existing tolerance closes the exception;
- unknown or untrusted flow cannot broaden it;
- it never uses `Command Discharging (PV First)`;
- it must not be generalized into ordinary positive-FiT rules.

An independently configured positive-FiT policy remains separate and follows its own two-control contract.

## Telemetry and ownership safety

Where safety depends on observed state, service-call success is not observation. Required observations must be available, fresh, finite, and from trusted sources. Unknown evidence fails closed when the safe export type or actuator ownership cannot be proven.

Manual and Force modes remain user-owned. Automated logic must not silently reinterpret them as ordinary MSC or deliberate battery export.

Negative-price, standby, freshness, remote-control availability, reserve, forecast, and other established safety policies keep their existing ownership and priority unless a separately approved change says otherwise.

## Phase 2 transition contract

Returning from deliberate battery export to an MSC surplus ceiling requires a multi-cycle observed transition:

1. Close the export ceiling.
2. On a later trusted observation, confirm export is actually closed.
3. Request Maximum Self Consumption.
4. On a later trusted observation, confirm exact Maximum Self Consumption.
5. Only then reopen the normal high export ceiling.

No service-call result, cached request, or assumed inverter response may replace an observed state. This settlement sequence is Phase 2 work and must not be partially improvised inside Phase 1 policy logic.
