# Changelog

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
