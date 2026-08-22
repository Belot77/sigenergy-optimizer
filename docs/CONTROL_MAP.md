# SigEnergy Optimizer Control Map

Audit date: 2026-06-17  
Project version/reference: 2.3.14-haos25  
Reference commit: ac57825 Add estimated PV surplus initiation
HVAC permission supplement: 2026-08-06, branch `fix/hvac-measured-solar-permission`, based on live commit `3e33088767977da6ba6543074e4129ecf9705e87`.

This document records the sensor, helper, config, derived-signal, algorithm, actuator, and UI/API control map from the read-only catalogue audit. It is intended to prevent duplicated, stale, or contradictory control logic from growing around the Value Gate, PV surplus, Solcast, anti-curtailment, manual override, and advisory HVAC solar-permission paths.

## Scope And Principles

- Control logic is safety-sensitive. Preserve conservative behavior when signals are unknown or contradictory.
- Proven measured PV surplus and estimated/probe PV surplus are different signals and must stay separate.
- Hidden PV is diagnostic unless explicitly promoted by guarded logic.
- For HVAC solar permission, Solcast and estimated opportunity are always diagnostic-only and must never be promoted to permission authority.
- HVAC solar permission is advisory only and cannot directly operate HVAC, zones, targets, AC0, AirTouch, or inverter actuators.
- Highest trusted actual optimizer import price is the source of truth for the actual import-cost export floor.
- Manual and force modes must override automatic optimizer decisions.
- Final actuator writes in a cycle are the source of truth for what the inverter is asked to do.

## Sensor And Entity Catalogue

| Item | Config key / default | Type | Expected unit | Conversion | Read location | Main use | Control impact | Status / rule |
|---|---|---|---|---|---|---|---|---|
| HA URL | `HA_URL=http://homeassistant.local:8123` | config | URL | none | `app/config.py` | HA API client | Indirect | Active; do not hardcode elsewhere. |
| HA token | `HA_TOKEN` | secret config | token | none | `app/config.py` | HA API client | Indirect | Secret; never log or document values. |
| UI API key | `UI_API_KEY` | secret config | token | none | `app/routers/api.py` | remote mutation auth | Live API guard | Secret; required for remote mutations. |
| HA control switch | `HA_CONTROL_SWITCH=switch.sigen_plant_remote_ems_controled_by_home_assistant` | switch | boolean | none | `_read_state`, `_apply`, `/set_ess` | enables remote EMS control | Live | Active actuator surface. |
| EMS mode select | `EMS_MODE_SELECT=select.sigen_plant_remote_ems_control_mode` | select | string | none | `_read_state`, `_apply`, manual/API | inverter EMS mode | Live | Final EMS source is automatic/manual/API write order. |
| Grid export limit | `GRID_EXPORT_LIMIT=number.sigen_plant_grid_export_limitation` | number | kW | none | `_read_state`, `_apply`, manual/API | export setpoint | Live | Central live output; hard guards clamp this. |
| Grid import limit | `GRID_IMPORT_LIMIT=number.sigen_plant_grid_import_limitation` | number | kW | none | `_read_state`, `_apply`, manual/API | import setpoint | Live | Central live output. |
| PV max power limit | `PV_MAX_POWER_LIMIT=number.sigen_plant_pv_max_power_limit` | number | kW | none | `_read_state`, `_apply`, manual/API | PV cap/curtailment | Live | Can change generation behavior. |
| ESS charge limit | `ESS_MAX_CHARGING_LIMIT` | number | kW | none | `_read_state`, `_apply`, manual/API | charge cap | Live | Optional but live if configured. |
| ESS discharge limit | `ESS_MAX_DISCHARGING_LIMIT` | number | kW | none | `_read_state`, `_apply`, manual/API | discharge cap | Live | Safety fallback sets near zero on failures. |
| PV power | `PV_POWER_SENSOR=sensor.sigen_plant_pv_power` | sensor | kW | raw `>100` treated as W and divided by 1000 | `_read_state` | measured PV, measured surplus | Live input | Authoritative measured PV; do not use alone for hidden PV. |
| House load | `CONSUMED_POWER_SENSOR=sensor.sigen_plant_consumed_power` | sensor | kW | raw `>100` treated as W and divided by 1000 | `_read_state` | surplus, reserve, load | Live input | Authoritative measured load. |
| Grid import power | `GRID_IMPORT_POWER_SENSOR` | sensor | kW | raw `>100` treated as W and divided by 1000 | `_read_state` | battery-flow fallback, price tracking | Live/diagnostic | Separate import sensor avoids signed-grid ambiguity. |
| Grid export power | `GRID_EXPORT_POWER_SENSOR` | sensor | kW | raw `>100` treated as W and divided by 1000 | `_read_state` | battery-flow fallback, price tracking | Live/diagnostic | Separate export sensor avoids signed-grid ambiguity. |
| Battery power | `BATTERY_POWER_SENSOR` | sensor | kW | raw `>100` treated as W and divided by 1000; optional invert | `_read_state` | PV-only proof | Live input | Required to rule out battery discharge. Unknown means not proven. |
| Battery SoC | `BATTERY_SOC_SENSOR` | sensor | percent | clamped 0-100 | `_read_state` | reserve, top-off, import/export | Live input | Authoritative SoC. |
| Rated capacity | `RATED_CAPACITY_SENSOR` | sensor | kWh | Wh unit divided by 1000; tiny raw values scaled | `_read_state` | reserve, forecasts | Live input | Capacity affects reserve math. |
| Available discharge | `AVAILABLE_DISCHARGE_SENSOR` | sensor | kWh | Wh unit divided by 1000 | `_read_state` | reserve/status | Live/status | Useful capacity signal; not primary export permission. |
| ESS rated discharge | `ESS_RATED_DISCHARGE_POWER_SENSOR` | sensor | kW | raw `>=1000` treated as W | `_read_state` | cap export/discharge | Live input | Hardware cap. |
| ESS rated charge | `ESS_RATED_CHARGE_POWER_SENSOR` | sensor | kW | raw `>=1000` treated as W | `_read_state` | cap import/charge | Live input | Hardware cap. |
| Sun entity | `SUN_ENTITY=sun.sun` | entity | state/attrs | timestamps parsed | `_read_state` | day/night, sunrise/sunset | Live input | Authoritative solar day boundaries. |
| Daily export energy | `DAILY_EXPORT_ENERGY` | sensor | kWh | numeric | `_read_state` | sessions, earnings | Diagnostic | Not export permission. |
| Daily import energy | `DAILY_IMPORT_ENERGY` | sensor | kWh | numeric | `_read_state`, top-up tracking | Guard input | May include house load during top-up window. |
| Daily load/PV/battery energy | daily energy sensors | sensors | kWh | numeric | `_read_state` | summaries/status | Diagnostic | Do not use as immediate control proof. |
| Import price | `PRICE_SENSOR=sensor.amber_general_price` | sensor | dollars/kWh | cents = value * `PRICE_MULTIPLIER` | `_read_state` | import decisions, actual import-cost floor | Live input | Trusted for hard floor only when price is actual. |
| Feed-in price | `FEEDIN_SENSOR=sensor.amber_feed_in_price` | sensor | dollars/kWh | cents = value * `PRICE_MULTIPLIER` | `_read_state` | export tiers, Value Gate, hard guard | Live input | Must be positive for PV-surplus initiation. |
| Price estimate flag | price sensor attribute | boolean | true/false | boolean parse | `_read_state` | actual import-cost trust | Live guard | Estimated prices must not set trusted import-cost floor. |
| Demand window | `DEMAND_WINDOW_SENSOR` | binary sensor | boolean | boolean parse | `_read_state` | decision/status | Live input | Active tariff context. |
| Price spike | `PRICE_SPIKE_SENSOR` | binary sensor | boolean | boolean parse | `_read_state` | spike export | Live input | Can influence export behavior. |
| Price forecasts | price/feed-in forecast sensors | sensor attrs | dollars/kWh, timestamps | attr parse | `_read_state` | curves, planning | Advisory/live | Forecasts are not actual-price proof. |
| Solcast remaining/today/tomorrow | forecast sensors | sensors | kWh | numeric | `_read_state` | holdoff, reserve, poor-tomorrow safeguard | Live input | Forecast, not measured production. |
| Solcast power now | `SOLAR_POWER_NOW_SENSOR` | sensor | kW | raw `>100` treated as W | `_read_state` | `solar_potential_kw` | Estimated live input | Use only for estimated/probe export logic and HVAC diagnostics; never HVAC permission authority. |
| HVAC solar permission | `HVAC_SOLAR_PERMISSION_ENTITY=sensor.sigenergy_hvac_solar_permission` | sensor publication | `start` / `continue` / `blocked` / `unavailable` | `HVACSolarPermissionResult.attributes()` | evaluator publication path | Climate Manager solar-target opportunity | Advisory only | Does not control HVAC or inverter actuators directly. |

## Helper Catalogue

| Helper | Default entity | Unit | Read/write locations | Purpose | Control impact | Status / warning |
|---|---|---|---|---|---|---|
| Mode select | `input_select.sigenergy_mode` | string | `_read_state`, `/set_mode`, manual apply | operator mode | Live | Manual/force override source. |
| Export session start | `input_number.sigenergy_export_session_start_kwh` | kWh | notifications | export session baseline | No | Active helper only. |
| Import session start | `input_number.sigenergy_import_session_start_kwh` | kWh | notifications | import session baseline | No | Active helper only. |
| Last export notification | `input_text.sigenergy_last_export_notification` | text | notifications | notification dedupe | No | Active helper only. |
| Last import notification | `input_text.sigenergy_last_import_notification` | text | notifications | notification dedupe | No | Active helper only. |
| Reason text | `input_text.sigenergy_reason` | text | `_apply` | operator-facing reason | No | Status only. |
| Min SoC to sunrise | `input_number.battery_min_soc_to_last_till_sunrise` | percent | `_apply`, history | reserve/status | No | Clamped to 100 for HA helper bounds. |
| Automated export flag | `input_boolean.sigenergy_automated_export` | boolean | configured/inventory | legacy/unclear | None found | Stale candidate; do not reuse without confirming purpose. |

## Config Groups

| Group | Important keys | Units | Used by | Control impact | Notes |
|---|---|---|---|---|---|
| API/security | `UI_API_KEY`, `ALLOW_LOOPBACK_WITHOUT_API_KEY`, mutation/read auth flags | booleans/tokens | `app/routers/api.py` | Live API protection | Direct `/set_ess` writes depend on this boundary. |
| Export thresholds | `EXPORT_THRESHOLD_*`, `EXPORT_LIMIT_*`, `ALLOW_*` | dollars/kWh, kW | `_desired_export_limit` | Live | Price-tier export behavior. |
| Value Gate | `EXPORT_VALUE_GATE_ENABLED`, `DRY_RUN`, `ENFORCE`, floor/premiums/margins | booleans, dollars/kWh, percent-ish floor | `_export_value_gate_advisory` | Live when enforced; hard guard independent | Keep advisory, enforce, and hard guard distinct. |
| Estimated PV initiation | `PV_SURPLUS_ESTIMATED_INIT_ENABLED=true` | boolean | decision PV-surplus path | Live small probe | Disables only estimated initiation, not hard import-cost guard. |
| HVAC solar permission | `HVAC_SOLAR_START_KW=1.0`, `HVAC_SOLAR_CONTINUE_KW=0.5`, discharge tolerance, live max-age, forecast max-age | kW/seconds | HVAC permission evaluator | Advisory HA entity only | Live measured inputs determine authority; forecast settings remain compatibility/diagnostic context. |
| Import thresholds | `IMPORT_THRESHOLD_*`, `IMPORT_LIMIT_*`, `CAP_TOTAL_IMPORT` | dollars/kWh, kW | `_desired_import_limit` | Live | Cheap import/top-up. |
| Reserve/top-off | `MIN_SOC_FLOOR`, `NIGHT_RESERVE_SOC`, `SUNRISE_RESERVE_SOC`, `DAYTIME_TOPUP_MAX_SOC` | percent | reserve and PV-only paths | Live | `DAYTIME_TOPUP_MAX_SOC` governs ordinary daytime import/top-up; PV-surplus-only export requires a fixed 100% top-off target. |
| Negative price/holdoff | standby, slow charge, forecast holdoff, negative lookahead | booleans, hours, kWh, kW | import/export/PV limit paths | Live | Overlaps with anti-curtailment. |
| Morning slow export | probe/ramp/margin keys | kW | morning slow-charge/export paths | Live | Existing anti-self-lock path. |
| Safeguards | full battery safeguard, hysteresis, min transfer, forecast safety | percent, kW, kWh | export/import/PV logic | Live | Safety margins. |
| Solar surplus bypass | `SOLAR_SURPLUS_BYPASS_*` | boolean/multipliers/kW | `_solar_surplus_bypass` | Live | Overlaps with newer PV-surplus logic. |
| Manual mode labels/values | `FULL_EXPORT_OPTION`, `FULL_IMPORT_OPTION`, `BLOCK_FLOW_OPTION`, etc. | strings/kW | manual apply and exemptions | Live | New labels must be added to exemption logic. |

## Derived Signal Catalogue

| Signal | Formula / source | Units | Calculated in | Used by | Type | Risk / source-of-truth recommendation |
|---|---|---|---|---|---|---|
| `solar_potential_kw` | `max(pv_kw, solar_power_now_kw)` | kW | optimizer decision | estimated surplus | Estimated | Source of truth for potential, not proof. |
| `pv_surplus` | `max(solar_potential_kw - load_kw, 0)` | kW | optimizer decision | forecast/estimated export logic | Estimated | Alias overlaps with estimated surplus; avoid using as measured proof. |
| `estimated_pv_surplus_kw` | same as `pv_surplus` | kW | trace values | UI/status, estimated probe | Estimated | Source of truth for estimated/probe surplus. |
| `pv_surplus_actual` | `max(pv_kw - load_kw, 0)` | kW | optimizer decision | measured export logic | Proven measured | Prefer explicit `measured_pv_surplus_kw` naming. |
| `measured_pv_surplus_kw` | `max(pv_kw - load_kw, 0)` | kW | Value Gate/PV-only path | PV-only proof, UI | Proven measured | Source of truth for proven PV surplus. |
| `hidden_pv_surplus_kw` | `max(estimated - measured, 0)` | kW | trace values | UI diagnostics | Diagnostic | Hidden PV is diagnostic unless explicitly promoted by guarded logic. |
| `pv_surplus_trusted_for_export` | measured surplus >= minimum transfer | boolean | trace gates | UI/status | Diagnostic/proof helper | Do not substitute for all PV-only conditions. |
| `battery_discharge_kw_for_pv_only` | battery sensor discharge, else power-balance fallback | kW | PV-only proof | carve-out/initiation | Proven if known | Unknown or above tolerance prevents PV-only classification. |
| `pv_only_discharge_ok` | discharge known and <= tolerance | boolean | PV-only proof | carve-out/initiation | Safety gate | Must stay conservative. |
| `pv_only_ems_safe` | current/proposed EMS not discharge mode | boolean | PV-only proof | carve-out/initiation | Safety gate | Prevents battery-backed export being called PV-only. |
| `topoff_target_soc` | `100` | percent | decision trace | PV-only export | Live guard | Fixed source of truth for the PV-surplus export top-off target. |
| `topoff_target_met` | `battery_soc >= topoff_target_soc` | boolean | PV-only proof | carve-out/initiation | Live guard | If target is 100, 99 is not enough. |
| `pv_surplus_only_proven` | common conditions + measured surplus + top-off + no discharge + EMS safe | boolean | decision | import-floor carve-out | Proven | Source of truth for measured PV-only export. |
| `pv_surplus_estimated_init_active` | estimated path conditions and capped probe | boolean | decision | export initiation | Estimated live probe | Never equate with measured proof. |
| `pv_surplus_probe_export_cap_kw` | min estimated surplus, ESS cap, low export limit, probe step/min transfer | kW | decision | export setpoint/status | Live cap | Source of truth for estimated probe size. |
| `pv_surplus_initiation_source` | `none`, `measured`, `estimated`, `full_battery_breathe_probe` | text | decision | UI/status | Diagnostic/control trace | Useful to explain export opening. |
| `pv_surplus_breathe_probe_active` | full-battery, export-clamped, positive-FiT, no-discharge tiny probe/continuation when measured/estimated surplus are both below threshold | boolean | decision | PV-only probe classification | Live guarded probe | Initial probe remains conservatively capped; proven continuation may ramp one configured step per cycle above `EXPORT_LIMIT_LOW` up to `EXPORT_LIMIT_HIGH`/ESS limit while all PV-only safety gates remain true. Must back off if battery discharge appears. |
| `stored_energy_value_floor` | Value Gate floor calculation | dollars/kWh | advisory | Value Gate | Advisory/enforced | Keep separate from actual import-cost floor. |
| `today_import_topup_kwh` | sum optimizer import records for date | kWh | `StateStore` | UI/status, guard context | Guard context | May include house load during optimizer import window. |
| `today_highest_actual_import_price` | max trusted actual import price in top-up records | dollars/kWh | `StateStore` | hard guard | Authoritative | Source of truth for actual import-cost floor. |
| `import_cost_export_floor` | highest actual import price | dollars/kWh | advisory | hard guard/UI | Authoritative | Do not use weighted averages. |
| `effective_battery_export_floor` | max stored-energy floor, import-cost floor | dollars/kWh | advisory | Value Gate/hard guard UI | Authoritative mixed floor | Best UI floor for battery-backed export. |
| `actual_import_cost_guard_active` | automatic mode with import-cost evidence/unknown floor | boolean | decision | hard guard | Live guard | Active independent of Value Gate enforcement flags. |
| `actual_import_cost_guard_blocking` | active and below/unknown floor for battery-backed/mixed export | boolean | decision | export veto | Live guard | Source of truth for hard block status. |
| `protected_reserve_soc` | reserve floor plus time/season adjustments | percent | advisory | export permission | Live/advisory | Battery protection source. |
| `sunrise_soc_target` / `min_soc_to_sunrise` | forecast/load reserve calculation | percent | decision | import/export reserve | Live | Source of truth for overnight reserve. |
| `desired_*_pre_value_gate` | desired outputs before guard changes | kW/string | trace values | diagnostics/tests | Diagnostic | Do not apply directly. |
| reason strings | branch and guard explanations | text | decision | UI/helper/status | Diagnostic | Mirror logic; useful to test key safety reasons. |

## Algorithm And Decision-Path Catalogue

| Algorithm | Trigger conditions | Inputs | Actuator outputs | Safety guards / priority | Tests / gaps |
|---|---|---|---|---|---|
| Automated cycle | mode is `Automated` or blank and HA control available/needed | all state/config | EMS, export/import, ESS, PV max, helpers | Manual mode exits before auto apply | Broad optimizer tests. |
| HVAC solar permission | supported safe control mode and fresh required measured inputs | actual PV, ordinary house load, battery flow, current-process prior published result | publishes advisory HA sensor only | discharge blocks; start at measured 1.0 kW; continue at measured 0.5 kW only with trustworthy unexpired prior; Solcast diagnostic-only; restart cannot inherit HA entity state | `tests/test_hvac_solar_permission.py`. |
| Manual mode | mode select not automated, or manual override set | configured mode labels | freezes decision; may reapply manual targets on drift | Highest priority before automatic writes | Manual tests present; add unknown-mode test. |
| Force Full Export | manual mode | hardware caps/manual values | discharge EMS, export cap, import block | Exempt from hard guard | Covered for hard-guard exemption. |
| Force Full Import | manual mode | hardware caps/manual values | grid charge EMS, import cap, export block | Manual override | Manual path covered indirectly. |
| Force Full Import + PV | manual mode | hardware caps/manual values | PV charge EMS, import cap, export block | Manual override | Add explicit test if changing. |
| Prevent Import & Export | manual mode | block limit, optional ESS overrides | max self, grid limits near zero, optional ESS caps | Manual drift correction retries | Manual path tested. |
| Cheap import/top-up | import price thresholds, reserve need, SoC | price, SoC, forecasts | import limit, charge modes | price/reserve/holdoff logic | Add more import-specific tests before cleanup. |
| Negative FiT curtailment | negative feed-in or related forecast context | FiT, PV/load, config | export/EMS controls | suppresses uneconomic export without imposing a house-load PV max cap solely because the battery is full | Direct regression coverage exists in `tests/test_negative_fit_pv_curtailment.py`. |
| PV max limiting | standby, battery-only, normal, and other configured PV-cap contexts | PV max config, current limit | PV max power limit | min-change threshold | UI diagnostics present. |
| Full battery export | full SoC and export opportunity | SoC, FiT, forecasts | export limit/EMS | poor-tomorrow measured surplus clamp | `test_export_poor_tomorrow.py`. |
| PV-surplus-only export | positive FiT, day, top-off met, measured surplus, no discharge, EMS safe | measured PV/load, battery flow, SoC, EMS | export capped to measured surplus; EMS safe | Can bypass import floor only when proven | Value Gate tests present. |
| Estimated PV-surplus initiation | measured surplus low, estimated surplus positive, top-off met, positive FiT, no battery discharge, automated mode | Solcast power now, PV/load, SoC, EMS | small capped export probe; no discharge EMS | Toggle only disables estimated initiation | 2.3.14 tests present. |
| Full-battery hidden-PV breathe probe | full/top-off battery, export clamped/open from previous breathe source, measured and estimated surplus below threshold, plausible live PV, positive FiT, no battery discharge, automated mode | PV/load, SoC, current/grid export, battery flow, EMS, previous decision source | tiny capped export probe with one-step continuation; no discharge EMS | Stops being PV-only if battery discharge appears | Tests cover active, continuation, and blocked paths. |
| Anti-curtailment/self-lock avoidance | slow-charge or export probe conditions | Solcast potential, measured PV/load | export limit tweaks | Conservative caps | Overlaps newer estimated initiation; document before changing. |
| Spike export | spike thresholds/SoC | FiT, spike sensor, SoC | export limit/EMS | Value Gate spike override rules | Advisory tests present. |
| Value Gate advisory/enforce | enabled/dry-run/enforce flags | stored energy value, reserve, FiT | status, optional export veto | Enforcement only when enabled and enforce true | Broad tests present. |
| Hard actual import-cost guard | optimizer import/top-up today has trusted or untrusted cost and automatic battery-backed/mixed export requested | top-up store, FiT, export type | export limit block; safe EMS | Active even when Value Gate flags off; manual exempt | Tests present. |
| Forecast/sunrise reserve | sunrise, load, forecast, reserve configs | forecast/state | import/export decisions and helper | conservative reserve protection | Needs coverage before refactor. |
| Notifications/session tracking | export/import transitions | daily kWh, helper state | helper input_numbers/texts and notifications | No inverter control | Not central to safety tests. |
| UI/API status generation | `/status` and websocket | last state/decision trace | JSON/UI only | Manual display targets override shown values | Add snapshot tests if restructuring. |

## Actuator And Write Map

| Actuator | Writers | Order / final source | Safety guards | Conflict risk |
|---|---|---|---|---|
| HA control switch | `_apply` auto-enable, `/set_ess` | API write or automatic need | API auth; `AUTO_ENABLE_HA_CONTROL` | Direct API can bypass optimizer stack by design. |
| EMS mode | `_apply`, `_safe_fallback`, `_apply_manual_mode_targets`, `/set_ess` | manual drift correction first; automatic decision later only in automated mode | hard guard/Value Gate can force max self; estimated probe avoids discharge mode | High-impact control surface. |
| Grid export limit | `_apply`, `_safe_fallback`, manual targets, `/set_ess` | final automatic `Decision.export_limit` unless manual/API | hard guard and Value Gate veto clamp; zero becomes 0.01 setpoint | Central export safety output. |
| Grid import limit | `_apply`, `_safe_fallback`, manual targets, `/set_ess` | final automatic `Decision.import_limit` unless manual/API | standby holdoff can force near zero | Can conflict with manual/API writes. |
| PV max power limit | `_apply`, manual targets, `/set_ess` | final `Decision.pv_max_power_limit` unless manual/API | min-change threshold; configured normal cap | Negative-FiT export suppression is handled by export/EMS control rather than a full-battery house-load PV cap. |
| HVAC solar permission sensor | HVAC permission publication path | published after successful evaluator cycle; prior in-memory result updates only after successful publication | advisory-only contract; failure publishes best-effort `unavailable` | No inverter or HVAC actuator write. |
| ESS charge limit | `_apply`, manual targets, `/set_ess` | decision/manual/API | retry logic in manual apply | Optional entity but live if configured. |
| ESS discharge limit | `_apply`, `_safe_fallback`, manual targets, `/set_ess` | decision/manual/API | fallback near zero on failures | Key to battery-backed export prevention. |
| Mode helper | `apply_manual_mode`, manual drift restore | manual selection | allowed mode validation in API | Source of manual override. |
| Reason helper | `_apply` | decision outcome | text truncation | Status only. |
| Min SoC helper | `_apply` | decision reserve | clamp to 100 | Status only. |
| Session helpers | notification handler | transition state | no live control | Notification-only. |
| Audit/price/top-up DB | optimizer and API audit helpers | persistent store | local SQLite | Guard/status inputs, not direct actuators. |

## UI/API/Status Field Catalogue

| Field group | Source | Meaning | Unit | Diagnostic/control | Wording and caution |
|---|---|---|---|---|---|
| `runtime_signature` | optimizer runtime | running app signature | version text | Diagnostic | Should match add-on version. |
| live power/price fields | `SolarState` | current plant/tariff state | kW/kWh/dollars | Input/status | Direct readings, not decisions. |
| displayed mode/limits | manual display targets or state/decision | current effective UI display | kW/string | Status/control reflection | Manual mode display can differ from last automatic decision. |
| `export_value_gate_*` | decision trace/advisory | Value Gate and floor analysis | booleans/cents/text | Advisory/live when enforced | Distinguish classic Value Gate from hard guard. |
| `actual_import_cost_guard_*` | decision trace | hard import-cost guard | booleans/text | Live guard status | Active even when Value Gate enforcement flags are off. |
| `today_import_topup_kwh` | top-up store summary | optimizer import-window kWh | kWh | Guard context/status | May include load during import window. |
| `today_highest_actual_import_price` | top-up store summary | highest trusted actual price today | dollars/kWh | Live guard input | Source of import-cost floor. |
| `topoff_target_soc`, `topoff_target_met` | decision trace | full-enough check for PV-only export | percent/boolean | Live guard status | 99 is not enough when target is 100. |
| `measured_pv_surplus_kw` | decision trace | measured PV above load | kW | Proven input/status | Source of proven PV surplus. |
| `estimated_pv_surplus_kw` | decision trace | potential PV above load | kW | Estimated input/status | Probe only; not proof. |
| `hidden_pv_surplus_kw`, `hidden_pv_possible` | decision trace | possible curtailment | kW/boolean | Diagnostic | Do not use directly for export permission. |
| `pv_surplus_estimated_init_*` | decision trace | estimated probe state/reason | boolean/text/kW | Live probe/status | Wording should keep "estimated/probe/capped". |
| `curtailment_diagnostic_reason` | decision trace | PV cap/hidden PV explanation | text | Diagnostic | Visibility only unless future guarded logic changes. |
| `/run_cycle` | API endpoint | trigger optimizer cycle | n/a | Live action | Not simulation. Requires mutation auth for remote clients. |
| `/set_mode` | API endpoint | set manual/automated mode | string | Live action | Validates allowed modes. |
| `/set_ess` | API endpoint | direct EMS/limit write | kW/string | Live action | Broad bypass surface; keep guarded and audited. |
| `/config` mutations | API endpoints | runtime config updates | mixed | Live or diagnostic depending key | Persisted to env; validate carefully. |

## Findings By Severity

### Critical

- None found in the read-only audit.

### High

- Direct `/set_ess` API writes can change EMS, grid limits, PV max, ESS limits, and HA control outside the normal optimizer guard stack. This is intentional manual/API control, but it is the broadest live-control bypass surface.
- Manual and force mode safety depends on configured label exemptions staying complete. New non-automated mode labels must not be treated as automatic by default.

### Medium

- PV surplus logic has overlapping names and purposes: `pv_surplus`, `pv_surplus_actual`, `measured_pv_surplus_kw`, `estimated_pv_surplus_kw`, `hidden_pv_surplus_kw`, `solar_surplus_bypass`, initiation flags, and carve-out flags.
- `today_import_topup_kwh` is conservative but may include house load during an optimizer import window. Keep wording clear.
- Value Gate status names now sit beside hard actual import-cost guard names. Future edits should avoid making hard guard behavior look dependent on dry-run/enforce flags.
- `EXPORT_VALUE_GATE_MIN_FLOOR` naming can be confused with a price floor even though it participates in stored-energy reserve/value logic.

### Low

- FastAPI metadata in `app/main.py` had drifted from the current release version before this docs/metadata patch.
- The UI exposes many dense diagnostics; grouping by control guard vs diagnostic would reduce operator confusion.

### Cleanup Only

- `AUTOMATED_EXPORT_FLAG` appears configured but not materially used in inspected optimizer/API paths.
- `AUTOMATED_MODES` appears stale or low-use compared with configurable mode labels.
- `_manual_import_recent_for_value_gate()` appears superseded by persisted actual import-cost tracking.

## Top Risks

1. Direct API live writes bypassing normal optimizer guard logic by design.
2. Future manual mode labels not added to all exemption paths.
3. Estimated PV surplus accidentally used as proven measured surplus.
4. Battery discharge sensor missing, inverted, or unavailable.
5. Import top-up kWh label misread as pure battery top-up.
6. Dry-run/advisory Value Gate paths leaking into actuator outputs.
7. Duplicate PV surplus calculations drifting apart.
8. Negative FiT, PV cap, full-battery export, and anti-curtailment paths fighting for priority.
9. Version metadata drift misleading operators or reviewers.
10. Dense diagnostics causing wrong operator interpretation.

## Duplicate Or Overlapping Logic Areas

- Measured PV surplus: `pv_surplus_actual`, `measured_pv_surplus_kw`, and `export_value_gate_pv_surplus_kw`.
- Estimated PV surplus: `pv_surplus`, `estimated_pv_surplus_kw`, `solar_potential_kw - load_kw`.
- Hidden PV/curtailment: `hidden_pv_surplus_kw`, `hidden_pv_possible`, PV cap diagnostics, estimated initiation.
- Export permission: export tier logic, solar surplus bypass, PV-only carve-out, estimated initiation, Value Gate, hard guard, forecast safeguards.
- Reserve protection: sunrise reserve, protected reserve, night reserve, battery full safeguard, poor-tomorrow clamp.
- Manual override: UI helper mode, optimizer manual override cache, manual display targets, direct `/set_ess`.

## Stale Or Dead Candidates

Do not delete these without a dedicated cleanup branch and tests:

- `AUTOMATED_EXPORT_FLAG`
- `AUTOMATED_MODES`
- `_manual_import_recent_for_value_gate()`
- Any old wording that implies Value Gate enforcement flags control the hard actual import-cost guard
- Any duplicated PV surplus alias that can be replaced by explicit measured/estimated names

## Source-Of-Truth Table

| Concern | Source of truth | Must not be replaced by |
|---|---|---|
| Proven PV surplus | `measured_pv_surplus_kw = max(pv_kw - load_kw, 0)` | Solcast-only potential, hidden PV diagnostic, estimated surplus |
| HVAC solar permission authority | fresh `measured_opportunity_kw = max(actual_pv_kw - ordinary_house_load_kw, 0)`, battery-flow safety, supported control mode, and current-process prior result for continuation | Solcast, estimated opportunity, retained HA permission state, SoC thresholds, PV MAX, feed-in price, zero export, export constraint alone |
| Estimated/probe surplus | `estimated_pv_surplus_kw = max(max(pv_kw, solar_power_now_kw) - load_kw, 0)` | measured proof flags |
| Hidden PV | `hidden_pv_surplus_kw = max(estimated - measured, 0)` | export permission by itself |
| PV-only export permission | `pv_surplus_only_proven` or explicitly capped estimated initiation | generic `pv_surplus` |
| Actual import-cost floor | highest trusted actual optimizer import price today | weighted average import cost, estimated price |
| Battery-backed export floor | `effective_battery_export_floor` | UI-only cents strings |
| Battery reserve/protection | protected reserve and sunrise reserve decision values | single SoC threshold without forecast context |
| Manual override | mode helper plus optimizer manual override state | automatic branch conditions |
| Final actuator writes | `_apply`, manual target apply, or direct API write for that cycle | pre-gate desired trace values |

## Recommended Future Cleanup Branches

1. `docs/control-map-maintenance`: keep this document aligned with future control changes.
2. `test/api-direct-write-guardrails`: add coverage for `/set_ess`, `/set_mode`, auth, and audit behavior.
3. `refactor/pv-surplus-source-names`: centralize measured vs estimated surplus helpers.
4. `refactor/value-gate-status-boundaries`: separate classic Value Gate labels from hard import-cost guard labels.
5. `test/negative-fit-pv-cap-priority`: focused negative-FiT/full-battery PV-max priority coverage now exists in `tests/test_negative_fit_pv_curtailment.py`.
6. `cleanup/stale-mode-and-helper-candidates`: remove or document `AUTOMATED_EXPORT_FLAG`, `AUTOMATED_MODES`, and legacy manual import premium hook.

## Tests To Add Before Cleanup

- API direct-write tests for `/set_ess`: auth, audit log, and explicit live-control status.
- Unknown non-automated mode label test: must not silently enable automatic estimated initiation.
- Centralized PV surplus helper tests: measured and estimated formulas stay distinct.
- Negative FiT plus full battery plus PV max priority is covered by `tests/test_negative_fit_pv_curtailment.py`.
- UI/status snapshot tests for hard import-cost guard vs classic Value Gate flags.
- Import top-up tracking test documenting conservative inclusion of load during optimizer import windows.
- Manual/force mode regression tests for every configured mode label.

## Commands Used For Audit Baseline

The audit used targeted reads and searches over source, docs, tests, templates, config, and add-on metadata. Generated files, caches, virtual environments, and live Home Assistant state were not inspected.
