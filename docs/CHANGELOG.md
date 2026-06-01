# Changelog

## 2026-05-31
- Added an advisory-only battery export value gate on `main` that calculates a protected reserve, stored-energy value floor, and would-allow/would-block result without changing live export behavior by default.
- Exposed advisory export value gate fields in the status payload so operators can compare the current live export decision with the dry-run reserve/value gate result.
- Added targeted tests covering winter evening cheap-export blocking, spike override above protected reserve, below-reserve blocking, summer-like advisory allowance, dry-run no-op behavior, and non-enforcing config defaults.
- Bumped add-on and app version surfaces to 2.3.7-haos22 for advisory export value gate rollout consistency.
- Bumped add-on and app version surfaces to 2.3.9-haos22 for advisory export value gate UI card rollout consistency.

## 2026-05-25
- Added a daytime poor-tomorrow safeguard in export limiting: when battery SoC is full and tomorrow forecast is below forecast_safety_charging x battery capacity, export is clamped to measured PV surplus only.
- Added tests covering full-battery export behavior for low and healthy tomorrow forecast scenarios.
- Bumped add-on version to 2.3.5-haos22.
