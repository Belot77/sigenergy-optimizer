# Changelog

## 2026-08-06
- Release `2.3.33-haos44` fixes HVAC solar permission freshness when the observed Home Assistant EMS selector is present and valid but unchanged, preventing false `required_data_stale` results.
- Existing inverter commands, export-limit policy, PV MAX behaviour and actuator settlement logic are unchanged.
- Added regression coverage for an unchanged valid `Maximum Self Consumption` EMS selector.

## 2026-08-05
- Added the authoritative Home Assistant entity `sensor.sigenergy_hvac_solar_permission`, publishing `start`, `continue`, `blocked`, or `unavailable`.
- Added measured solar-opportunity evaluation with separate start/continue hysteresis; Solcast is used only as separate hidden-opportunity evidence.
- Live inverter evidence and permission expiry use a 120-second freshness window, while Solcast forecast evidence uses a separate 600-second window.
- Added permission-critical WebSocket triggers so relevant entity changes promptly refresh the published permission.
- Kept permission publication isolated from existing optimiser inverter decisions and actuator writes.
- Bumped add-on metadata, buildstamp, FastAPI metadata, and runtime signature to 2.3.32-haos43.

## 2026-08-04
- At negative feed-in prices, the automatic optimiser no longer reduces PV max power to approximately rounded house load when the battery is full. Existing grid-export controls remain responsible for preventing uneconomic export, while normal PV max allows solar to serve house load before the inverter internally curtails genuine excess.
- The separate PV-surplus-only export top-off threshold is now fixed at 100% SoC. `DAYTIME_TOPUP_MAX_SOC` remains unchanged and continues to govern ordinary daytime cheap-import/top-up behaviour.
- Added focused regression tests for the 100% PV-export top-off threshold and negative-FiT full-battery PV-max behaviour.
- Bumped add-on metadata, buildstamp, FastAPI metadata, and runtime signature to 2.3.31-haos42.

## 2026-07-14
- Fixed the default Remote EMS control switch entity spelling and added availability/domain guards before automatic `switch.turn_on` calls.
- Missing, unavailable, or helper-domain Remote EMS targets now pause automatic EMS writes, emit a rate-limited warning, and do not hammer Home Assistant services; valid switches already on are left alone, while valid switches off retain bounded auto-enable behaviour.
- Bumped add-on metadata, buildstamp, FastAPI metadata, and runtime signature to 2.3.30-haos41.

## 2026-06-27
- Added a narrow full-battery hidden-PV breathe probe that can open a tiny capped export when measured and estimated surplus are both below threshold, export is clamped near zero, top-off is met, FiT is positive, and battery discharge is safely ruled out.
- The probe stays out of discharge EMS modes and is reported as `pv_surplus_initiation_source=full_battery_breathe_probe`; manual/force modes remain exempt.
- Added safe continuation/ramping for the breathe probe when the previous cycle used that source, grid export confirms the probe is producing export, and battery discharge remains safely within tolerance.

## 2026-06-17
- Bumped add-on buildstamp, add-on metadata, runtime signature, FastAPI metadata, and docs to 2.3.15-haos26 as a cache-bust/metadata release only.
- This forces the Home Assistant add-on image to rebuild from current `main` so the container source commit matches the current code.
- No optimiser control logic changed from 2.3.14-haos25.

## 2026-06-17
- Added conservative estimated-PV-surplus initiation for the PV-surplus-only export path, gated by `PV_SURPLUS_ESTIMATED_INIT_ENABLED`, so a full battery can open a small probe export when measured PV is curtailed to house load but Solcast/current potential shows surplus.
- Bumped add-on and app version surfaces to 2.3.14-haos25 for the estimated PV-surplus initiation rollout.

## 2026-06-16
- Added optimiser import/top-up tracking for today's imported kWh and highest trusted actual import price, using the highest actual price as the import-cost export floor rather than a weighted average.
- Updated the Value Gate effective battery export floor to `max(stored-energy floor, today highest actual optimiser import price)` and to block battery-backed/mixed export when the actual import-cost floor is unknown or the FiT is below that floor.
- Tightened PV-surplus-only export initiation/carve-out so below-floor export is only allowed after the configured top-off target is met, measured surplus is proven, battery discharge is not measured, and EMS is not already in a discharge mode.
- Added status/UI fields explaining import-cost floor trust, top-off target state, PV-only allowance, and import-cost block reasons.
- Bumped add-on and app version surfaces to 2.3.13-haos24 for the Value Gate actual import-cost protection rollout.

## 2026-06-15
- Added visibility-only PV cap and hidden-surplus diagnostics to the Value Gate status payload and overview UI card (cap state/reason, measured vs estimated surplus, hidden-surplus estimate, trust flags, and curtailment diagnostic reason).
- Confirmed diagnostics are informational only: no changes to live inverter control outputs, no estimated-surplus bypass, and no change to Value Gate enforcement behavior.
- Bumped add-on and app version surfaces to 2.3.12-haos23 for diagnostics visibility rollout consistency.

## 2026-05-31
- Added an advisory-only battery export value gate on `main` that calculates a protected reserve, stored-energy value floor, and would-allow/would-block result without changing live export behavior by default.
- Exposed advisory export value gate fields in the status payload so operators can compare the current live export decision with the dry-run reserve/value gate result.
- Added targeted tests covering winter evening cheap-export blocking, spike override above protected reserve, below-reserve blocking, summer-like advisory allowance, dry-run no-op behavior, and non-enforcing config defaults.
- Bumped add-on and app version surfaces to 2.3.7-haos22 for advisory export value gate rollout consistency.
- Bumped add-on and app version surfaces to 2.3.11-haos22 for advisory export value gate UI card rollout consistency.

## 2026-05-25
- Added a daytime poor-tomorrow safeguard in export limiting: when battery SoC is full and tomorrow forecast is below forecast_safety_charging x battery capacity, export is clamped to measured PV surplus only.
- Added tests covering full-battery export behavior for low and healthy tomorrow forecast scenarios.
- Bumped add-on version to 2.3.6-haos22 so Home Assistant users on higher refactor versions can receive main-branch updates (no downgrade block).
