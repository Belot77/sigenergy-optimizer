# Changelog

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
