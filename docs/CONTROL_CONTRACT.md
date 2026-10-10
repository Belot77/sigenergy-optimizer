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

## Solar Surplus

Solar Surplus is a Phase 1 MSC/PV-only export-permission policy with bounded dynamic ESS charge-ceiling ownership. It:

- remains in Maximum Self Consumption;
- retains normal PV MAX;
- never owns `BATTERY_EXPORT` or deliberately selects a discharge EMS;
- may reduce the existing normal safe/trusted ESS charge request only after final arbitration selects `solar_surplus_policy_active`, with the stricter charge-ownership evidence below; it must never increase that normal request;
- does not own grid import;
- treats a high export ceiling as permission for genuine PV surplus, never as an instruction to discharge or proof that physical export settled.

Its energy order is PV to current house load, preserve enough opportunity to fill the battery safely, then permit export of genuinely remaining PV. Eligibility is recalculated every cycle and requires all of the following:

- FiT at least `1 cent/kWh`;
- trusted finite PV and load values with coherent observations;
- measured PV-load surplus strictly above `0.5 kW` for entry;
- for genuinely owned continuation only, measured surplus strictly above `0.2 kW`;
- trusted Remaining Today aggregate forecast;
- trusted battery SoC and rated battery capacity;
- trusted same-day future sunset while the sun is above the horizon;
- a finite Solar-specific forecast safety factor `K >= 1`;
- a passing aggregate energy budget;
- when battery fill remains, passing trusted detailed timing evidence using trusted effective charge capability.

At or below the continuation threshold Solar stops. After stopping, full entry strictly above `0.5 kW` is required again. Missing, stale, malformed, incoherent, or otherwise unsafe evidence fails Solar closed.

### Aggregate energy budget

The Phase 1 energy model is:

```text
remaining_load_kwh = current trusted site load x hours to same-day sunset
fill_need_kwh = trusted rated capacity x remaining SoC headroom to 100%
required_energy_kwh = remaining_load_kwh + fill_need_kwh
protected_requirement_kwh = K x required_energy_kwh
```

Solar requires trusted PV Forecast Remaining Today to be **strictly greater than** the protected requirement. Equality does not pass.

The dedicated setting is `solar_surplus_forecast_safety_factor`, default `1.20`: `1.00` adds no margin, `1.20` requires 20% more aggregate Remaining Today than calculated load plus fill need, and higher values are more conservative. Legacy `solar_surplus_start_multiplier` and `solar_surplus_stop_multiplier` remain stored/configurable for compatibility but do not drive redesigned eligibility.

### Detailed timing

Detailed timing is required only when `fill_need_kwh > 0`. Trusted detailed Solcast intervals must cover the decision horizon through same-day sunset. Each interval deducts current trusted site load before estimating chargeable PV, bounds charge opportunity by trusted effective charge capability, and applies the same Solar safety factor conservatively. The resulting timed opportunity must prove the battery can fill to 100% by sunset.

Aggregate Remaining Today energy and detailed interval energy are independent gates; they are not added together. If fill need is exactly zero, detailed timing is not required. Missing, gapped, truncated, untrusted, or insufficient detailed evidence fails Solar closed.

### Dynamic ESS charge ceiling

Charge ownership is evaluated only after final arbitration selects Solar Surplus. It requires provider-aware freshness for detailed Solcast data, continuous interval coverage from now through the effective Solar fill deadline, trusted current load, battery SoC and rated capacity, the valid Solar safety factor, and trusted effective normal ESS charge capability. Detailed evidence is required for this authority even when the battery is full.

The dedicated setting `solar_surplus_fill_deadline_margin_minutes` defaults to **60** and accepts finite nonnegative minutes, including zero; booleans are invalid. The effective trajectory deadline is trusted same-day sunset minus this margin. Zero retains the sunset trajectory. This timing margin is independent of Morning Slow's cutoff and the unchanged Solar safety factor `1.20`. It changes only the dynamic charge trajectory: aggregate remaining-load and independent eligibility timing above still use sunset.

At or after the effective fill deadline, Solar relinquishes restrictive charge ownership so normal safe MSC charging can use available PV. Earlier/full-battery surplus export remains subject to the existing independent PV-only eligibility and safety rules; the earlier deadline is not an export cutoff. A sufficiently large margin can place the deadline before now, safely releasing the restriction. Missing/untrusted sunset, invalid margin or unusable deadline cannot authorize a restrictive ceiling. Provider/same-local-day semantics remain unchanged.

Provider freshness uses explicitly configured Forecast Today and API Last Polled entities from the same Solcast instance (`forecast_today_sensor` and `solcast_api_last_polled_sensor`). Under the accepted BJReplay/ha-solcast-solar v4.6.1 contract, an advancing API Last Polled state represents a successful ordinary provider refresh. Sig Opt independently validates finite/nonnegative detailed estimates, aware timestamps, ordering, exact continuous coverage, the current interval and same-local-day sunset horizon. `dataCorrect` is not mandatory; its row-count semantics can reject a legitimate 23-hour DST day. Forecast Today HA `last_reported`, `last_attempt`, and schedule advancement alone do not establish provider success.

The process-local states are UNVERIFIED, VALID and EXPIRED. Startup begins UNVERIFIED: the first coherent observation establishes only a provider timestamp baseline and expected deadline. A later credible successful timestamp advance is required for VALID. Credible advances are retained as a high-water mark even when their payload is rejected; unchanged rejected generations cannot become trusted after repair or elapsed time. Malformed, naive, materially future-dated or regressing provider timestamps fail closed. Provider freshness is never persisted and no Solcast update is forced.

The retained scheduled obligation D cannot slide:

- With unchanged P, later advertised N leaves D unchanged; earlier valid N shortens D and expires authority immediately if already due.
- A qualifying new P before D remains bounded by `min(D, N)`, including manual/forced success immediately before a scheduled refresh.
- Only a qualifying success at/after the retained deadline, validated at/after D with a usable future N and complete payload, may discharge that obligation and establish a new deadline.
- At `now >= D` without qualifying replacement, authority is EXPIRED with no grace. Solar releases only its charge restriction and restores the otherwise applicable normal safe/trusted ESS request.

HA disconnect/reconnect, source reassignment, unavailability/reload, timestamp regression or uncertain continuity invalidate the source epoch. Relevant WebSocket observations signal invalidation synchronously before lossy queue handling; the epoch and urgent flag survive coalescing and overflow. REST reads retain the source/epoch captured before their first await and cannot establish authority after an epoch change. Recovery requires a new baseline followed by another provider advance.

The existing optimizer event loop bounds its wait and debounce by D and local midnight, so reevaluation does not depend on an HA event or the 60-second heartbeat. Authority is rechecked immediately before a reduced charge write; a pending reduced write that crosses expiry/invalidation is followed by restoration in the same serialized application. This introduces no independent control loop or change to actuator settlement semantics. A final daytime poll may use tomorrow's next update for today's remaining horizon, but its Forecast Today generation cannot carry into another local day.

This authority is isolated from global `forecast_today_observation_trusted`. `hvac_solar_forecast_max_age_seconds` retains its backend/environment key and 600-second default for existing consumers: Remaining Today, Power Now, Forecast Today/Standby Holdoff, age-based Forecast Tomorrow and selected import-price forecast freshness. It cannot extend dynamic Solar provider authority. All existing final-owner, load, SoC, capacity, sun, capability and higher-priority-owner safeguards remain required.

For each detailed interval, subtract trusted current load from forecast PV, floor the available power at zero, and bound charge opportunity by the existing normal safe/trusted charge capability/request. Multiply by actual interval overlap hours before the effective fill deadline, clipping a partial final interval. Identify the interval containing now; future opportunity includes only intervals strictly after that current interval.

```text
protected_fill_need_kwh = K x energy_needed_to_reach_100_percent
future_opportunity_kwh = sum of bounded charge opportunity after the current interval
required_now_kwh = max(0, protected_fill_need_kwh - future_opportunity_kwh)
requested_charge_kw = required_now_kwh / remaining current-interval overlap hours
```

Clamp the request between zero and the existing normal safe/trusted capability/request. Round a positive request UP to 0.01 kW without exceeding that normal bound, retaining its existing safe command precision. Abundant future opportunity may request `0.00 kW`. Recalculate each decision without a timer; this changes only ESS charging authority and cannot authorize stored-battery export.

Missing, expired, gapped, invalid, or untrusted charge evidence immediately relinquishes only the Solar charge restriction and restores the normal charge request. This stricter authority does not redefine Solar eligibility: complete current-day detailed intervals may still support the existing Solar policy despite old parent Forecast Today metadata. Provider-verified evidence may also authorize the dynamic charge restriction in that case; absent provider authority reports `solcast_provider_authority_untrusted`. Solar's independent eligibility and safety gates still apply.

### Physical-export saturation relief

Solar may relax only its own restrictive ESS charge ceiling using a separate process-local feedback controller:

```text
final Solar charge ceiling = min(normal safe/trusted ESS charge request,
                                baseline trajectory ceiling + physical relief)
```

Relief starts at zero. `grid_connection_export_limit_kw` is generic physical-site saturation evidence, with software default **0.0 = disabled**. The confirmed 15 kW site limit is operator configuration, not a universal default or an inverter export command. Solar keeps MSC, normal PV MAX, normal high export permission (currently 25 kW at the site), and `battery_export_owner=none`. Relief must not deliberately divert export into charging or authorize `BATTERY_EXPORT`.

Required authority is final Solar charge ownership, observed Automated ownership and exact MSC, no Manual/Force/Morning Slow or deliberate battery-export owner, partial SoC, and trusted coherent measured physical flows. PV, load, grid-import and grid-export observations must be finite, fresh and temporally coherent within five seconds; measured flow must support nonnegative battery charging with no grid import. Existing direct-battery discharge safety checks remain required; relief derives charging evidence from the coherent measured components. A static saturated sample cannot prove hidden PV. Solcast potential, estimated PV and `hidden_pv_surplus_kw` cannot authorize relief.

The approved fixed Solar policy has no additional operator tuning settings:

- Entry/upward confirmation requires actual export **>= physical limit - 0.2 kW**. Each increase is at most **0.4 kW**, after **two** fresh coherent post-command observations. Every relevant timestamp must advance; telemetry reuse cannot stack increases. A successfully applied changed charge target starts its feedback epoch, while reasserting the same target does not erase a valid first observation. Further increases require measured battery charging above the baseline ceiling.
- One new coherent export observation **< physical limit - 0.5 kW** reduces active relief immediately by **1.2 kW**, floored at zero. The other flow observations must remain trusted/coherent but need not all advance to permit this restrictive response. The interval between exit and entry holds relief and resets upward confirmations; exact exit does not reduce.
- Actual trusted export **< physical limit - 1.0 kW** hard-resets relief to baseline. Any export-driven downward adjustment imposes **three** fresh coherent observations at/above entry before another increase; afterward the ordinary two-observation rule resumes.
- Relevant flow trust/freshness/coherence loss, regressing feedback, loss of Solar/Automated/MSC ownership, Manual/Force/Morning Slow, exact-full, disabled/invalid limit or actuator application failure resets relief. Baseline or normal-cap changes clear relief and start a fresh command/feedback epoch, retaining an existing retry requirement for the same physical limit.

At a 15 kW configured site the entry, exit and hard-reset boundaries are 14.8, 14.5 and 14.0 kW respectively. This asymmetry permits cautious discovery and faster export restoration. Application rechecks restore the baseline if physical evidence expires, and restore the normal safe request if provider/fill-deadline authority expires, including during an in-flight charge write. Service-call success arms later feedback only; it is not observed export preservation or actuator settlement.

Morning Slow's existing binary cap release/retention and its tuning remain unchanged and do not control Solar. Demand Window continues to own import blocking. This relief does not redesign export ownership or Phase 2 settlement.

### Near-full safeguard arbitration

A synthetic refill requirement caused solely by untrusted available-discharge-energy telemetry cannot, by itself, veto an independently qualified and safely verified Solar Surplus MSC/PV-only ceiling. The raw Battery Full Safeguard calculation and diagnostics remain visible; the distinction applies only to final export arbitration.

The distinction requires all normal Solar aggregate, detailed-timing, measured-surplus, forecast, tariff, and trust gates, plus genuinely observed Automated ownership, genuinely observed exact Maximum Self Consumption, and trusted PV/battery/grid-flow evidence proving the request remains PV-only-safe. Re-arbitration must select the specific `solar_surplus_pv_high` source. A failed Solar gate, unknown or unsafe flow, competing deliberate battery-export owner, manual owner, or independent higher-priority safety owner retains the fail-closed result and cannot fall through to a general permissive ceiling.

This distinction creates only `MSC_SURPLUS_CEILING`. It never creates `BATTERY_EXPORT`, never selects a deliberate discharge EMS, and does not itself grant ESS charging, grid-import, or PV-curtailment ownership. A final Solar owner may separately qualify for the bounded charge ceiling above. All downstream actuator, settlement, and ownership protections remain mandatory.

### Ownership interactions

- Morning Slow owns its charging behavior. Solar is off while Morning Slow is active and cannot alter its charge rate.
- Morning Dump and other explicit deliberate `BATTERY_EXPORT` owners win over Solar. After Morning Dump ends, Solar must satisfy full entry again.
- Demand Window continues to own import blocking; Solar does not take import ownership.
- Exact-full remains a separate PV-only branch and its semantics must not be merged into Solar.
- Manual and Force remain operator-owned; Solar continuation cannot survive as active control ownership through them.
- Positive-FiT deliberate battery export remains separate. Solar itself never authorizes battery discharge.

### Diagnostics

`solar_surplus_policy_active` identifies final Solar policy ownership after arbitration. Operator diagnostics also expose the fail reason, aggregate budget evidence, detailed timing evidence, measured surplus and active threshold, and Solar safety factor. Policy-active status and an open ceiling do not prove physical inverter or grid export settlement.

Charge diagnostics expose gates `solar_charge_ceiling_evidence_trusted` and `solar_charge_ceiling_owned`, plus values `ess_charge_limit_owner`, `solar_charge_ceiling_requested_kw`, `solar_charge_ceiling_protected_fill_need_kwh`, `solar_charge_ceiling_future_opportunity_kwh`, `solar_charge_ceiling_required_now_kwh`, `solar_charge_ceiling_current_window_hours`, and `solar_charge_ceiling_reason`. When owned, the charge owner is `solar_surplus`; current charging needed for the fill trajectory reports `present_charging_required_for_fill_trajectory`. Charge ownership is distinct from policy eligibility and observed actuator settlement.

Fill/relief diagnostics add `solar_charge_ceiling_fill_deadline_ts` (Unix timestamp), `solar_charge_ceiling_fill_deadline_margin_minutes`, `solar_charge_ceiling_baseline_kw`, gates `solar_physical_relief_active` / `solar_physical_relief_flow_trusted`, and values `solar_physical_relief_kw`, `solar_physical_relief_reason`, `solar_physical_relief_export_kw`, `solar_physical_relief_limit_kw` and `solar_physical_relief_confirmations`. `solar_charge_ceiling_requested_kw` remains the final requested ceiling after relief. The API copies these trace values without recalculating control and suppresses stale relief-active status when final Solar ownership is absent.

Provider trace evidence includes `solar_provider_state`, observed/high-water/verified poll timestamps, retained deadline, advertised next update, configured source, epoch, source-continuity trust, provider-authority trust and rejection/expiry reason. These fields prove decision provenance, not live actuator settlement.

## Explicit deliberate battery-export policies

Existing policies that genuinely own deliberate battery sale remain distinguishable. These include qualifying Morning Dump, high-price export, export spike, Evening Export Boost, explicitly enabled positive-FiT battery discharge, and established solar/export or external overrides where their current policy owns discharge.

Each owner remains subject to its own eligibility and all independent safety guards. Generic ordinary tier eligibility is never an owner.

## Evening Boost

Evening Boost is a deliberate `BATTERY_EXPORT` policy with owner `evening_export_boost`. Its dedicated setting is `evening_boost_min_feedin_price`: the software default and hard permitted minimum are both `$0.01/kWh`. Values below one cent and non-finite values are invalid; no arbitrary upper bound applies.

When every Evening Boost eligibility and safety gate passes, it may operate below the ordinary export-tier threshold. The existing `export_limit_low` remains the ordinary tier output, not an Evening Boost-specific export ceiling. Ordinary positive-FiT export does not acquire Evening Boost ownership, and absolute sub-one-cent export remains blocked.

Available-energy trust, refill feasibility, actual import-cost protection, forecast and reserve protections, battery floor, observed Automated ownership, Demand Window separation, Manual/Force ownership, and fail-closed actuator settlement remain mandatory. This decision does not introduce a 5.5 kW Evening Boost redesign.

## Morning Dump

Morning Dump is deliberate stored-battery export. While its existing time window, configurable floor, forecast feasibility, and safety rules remain valid, it may own `BATTERY_EXPORT` and use `Command Discharging (PV First)`.

Eligibility requires trusted timed refill feasibility. The model must not assume that a future Morning Slow relief condition will rescue refill feasibility; missing, untrusted, gapped, or insufficient evidence fails closed. The current operator floor remains 15%, recorded as operator configuration rather than a software default.

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

Refill feasibility uses trusted timed detailed-forecast opportunity through same-day sunset minus the configured sunset cutoff. The configured Morning Slow end time ends this policy's ownership; it is not the refill deadline. If slow charging is infeasible but normal bounded charging offers strictly greater safe refill opportunity, release only Morning Slow's artificial charge cap. Missing or untrusted evidence cannot authorize relief, and no arbitrary 60-second stabilization applies.

Morning Slow's optional physical-relief settings remain `grid_connection_export_limit_kw` and `morning_slow_physical_export_headroom_kw`; both default to `0.0`, and Morning Slow requires both to be positive with headroom below the physical limit. Coherent trusted measured site export reaching its configured threshold may release only Morning Slow's artificial charge cap. Its existing binary release and counterfactual retention behavior are unchanged; Solar does not reuse them. The generic physical limit may independently enable Solar's controller above even with Morning Slow headroom zero. Neither policy sets Sigenergy export permission to that threshold or enforces a hard network export cap. The confirmed `15.0 kW` site capability and discussed `0.5 kW` Morning Slow headroom remain operator values, not software defaults; Solar's approved meaning is physical saturation evidence only.

## Event responsiveness

Relevant Home Assistant state and watched-attribute changes trigger event-driven optimizer cycles through a fixed 3-second pre-decision coalescing window. The deadline does not slide when more events arrive, allowing related telemetry bursts to produce one coherent decision without restoring the earlier zero-delay behavior.

There is no immediate first-event tick and no immediate catch-up tick. Events arriving during or after a cycle remain eligible for the next bounded cycle. Startup remains immediate, the 60-second heartbeat remains, metadata-only changes do not trigger, and actuator/readback settlement protections remain unchanged. No arbitrary 60-second Solar stabilization is part of this contract.

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

Available discharge energy requires an explicit supported unit and a fresh, finite, non-negative value. Missing units must not silently default to kWh. A value slightly or materially above separately reported rated capacity remains trusted; when rated capacity is itself trusted, the bounded control value is clamped to rated capacity while the raw normalized diagnostic remains visible. When rated capacity is untrusted, no capacity clamp is invented. Invalid, unavailable, stale, non-finite, negative, or unsupported-unit telemetry remains fail-closed, subject only to the established near-full Solar exception for genuinely untrusted available-energy telemetry.

Unavailable, missing, unknown, stale, or non-finite actuator-state telemetry is not proof that import or export is safely closed. Deadband or a numeric default must not suppress a required safety-close request when the present actuator state is untrusted. Untrusted current grid-limit telemetry also cannot authorize a permissive opening; opening requires a trusted finite observation. Trusted finite current limits retain ordinary deadband behavior.

Dynamic grid import/export current-position readbacks use the live inverter telemetry boundary of 120 seconds and require provenance-bearing fresh observations. Missing provenance, stale values, and negative values are not current-position proof, cannot prove closure, and cannot authorize permissive opening; raw values may remain diagnostic. Restrictive closes remain allowed. Static `grid_export_limit_entity_max_kw` capability is separate from dynamic current-position liveness.

Safety-critical settlement requires provenance-bearing readback. Deliberate battery export must establish or set the intended export target before entering or changing discharge EMS. If an export-close request succeeds but settlement remains unproven, that uncertainty must not suppress an independent restrictive grid-import close; the overall application remains failed and unrelated permissive writes remain deferred.

Safe fallback closes export first, requests Maximum Self Consumption, and clamps ESS discharge while settlement is unresolved. Permissive recovery requires observed export closure and observed exact Maximum Self Consumption; successful service calls are not proof. If settlement cannot be proven, normal import, ESS charge/discharge capability, and normal PV MAX recovery remain withheld, although Demand Window may continue to own import blocking. Fallback never creates `BATTERY_EXPORT`; Manual and Force behavior is unchanged. Observing settlement of the fallback `0.01 kW` export-close request is an intentional safety requirement.

Fallback exact-MSC recovery proof must be fresh, provenance-backed and strictly later than the MSC request boundary, correlated to the observed EMS state. Stale, missing, unavailable, untrusted, pre-request or equal-timestamp reports cannot restore normal import or ESS capabilities. A genuinely later report of unchanged exact MSC may qualify; a cached string or accepted command cannot. Successful fallback recovery does not itself grant automatic export-reopening authority.

An independently owned restrictive Standby or negative-price PV MAX request remains effective during pending transition, transition completion, actuator failure and every fallback path, including successful settlement. A lower valid restriction must not be raised by normal PV recovery. Required independent restrictive PV, import and ESS safety writes must not wait for transition settlement; unrelated permissive writes remain deferred. Demand Window retains import blocking during fallback recovery, and Manual/Force retain their own authority and settlement requirements.

Export start/stop notifications are classified from trusted measured grid export. A changed export ceiling alone is not proof that physical export started or stopped.

Manual and Force modes remain user-owned. Automated logic must not silently reinterpret them as ordinary MSC or deliberate battery export.

Negative-price, standby, freshness, remote-control availability, reserve, forecast, and other established safety policies keep their existing ownership and priority unless a separately approved change says otherwise.

## Phase 2 transition contract

Returning from deliberate battery export to an MSC surplus ceiling requires a multi-cycle observed transition:

1. Close the export ceiling.
2. On a fresh, provenance-backed observation strictly after the close request, confirm export is actually closed.
3. Request Maximum Self Consumption.
4. On a fresh, provenance-backed observation strictly after the MSC request, confirm exact Maximum Self Consumption.
5. Only then reopen the permitted MSC/PV-only export ceiling, subject to all independent safety and ownership gates.

Entering deliberate battery export must settle the export target before selecting a discharge EMS mode.

No service-call result, cached request, reused snapshot, equal-timestamp report or assumed inverter response may replace later observed settlement. EMS state and report provenance must agree; freshness and request/observation timing must use a coherent clock.

Unfinished transitions remain restrictive across cycles, telemetry uncertainty and restart. Lost process-local evidence cannot authorize reopening; recovery requires the trusted observed sequence. Genuinely safe, freshly observed MSC at startup is distinct from an unresolved discharge-to-MSC transition and must not unnecessarily block otherwise safe Solar charging, fill-deadline recovery or provider-freshness protections. All independent charging and flow safeguards still apply.

The multi-cycle return sequence above is distinct from the emergency fallback command ordering defined under telemetry and ownership safety. Fallback keeps export closed and requires observed settlement before permissive capability recovery; it is not a shortcut to reopen export.
