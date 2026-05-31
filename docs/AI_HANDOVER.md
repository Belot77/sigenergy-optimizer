# SigEnergy Optimizer - AI Handover

## 1. Project purpose
Home Assistant add-on and web UI for SigEnergy battery/energy optimization using Home Assistant state, Amber pricing, and solar forecast inputs. The project is safety-first and intended to replace older SigEnergy blueprint automations.

## 2. Current source-of-truth files
- Root guidance: AGENTS.md and README.md
- Add-on version/package metadata: sigenergy_optimizer_addon/config.yaml
- Main runtime configuration and entity assumptions: app/config.py
- Core optimizer logic: app/optimizer.py
- API/UI entry points: app/main.py and app/routers/
- Forecast, earnings, and persistence helpers: app/forecast_utils.py, app/earnings.py, app/state_store.py
- Tests: tests/
- Source of truth is this project folder, not ZIPs, generated outputs, local env files, caches, or test artifacts.

## 3. Current version
- **Authoritative source**: sigenergy_optimizer_addon/config.yaml (version field)
- **Current version**: 2.3.8-haos22
- **Note**: release.sh updates config.yaml but not README.md. README.md has been updated to match current config version.

## 4. Main features
- Event-driven optimizer with 60-second heartbeat fallback.
- Home Assistant add-on with ingress web UI and REST/WebSocket integration.
- Amber price and feed-in driven import/export decisions.
- Advisory-only export value gate on `main` that dry-runs a protected-reserve/value-floor check without changing live export limits by default.
- Solar forecast-aware battery/export planning.
- Earnings/session tracking and reporting.
- Manual override controls via HA helper mode select and UI.
- Non-live simulation/preview/overlay tools documented in README.
- Runtime tuning through dashboard controls plus advanced extra_env overrides.

## 5. Important design decisions
- Safety is more important than aggressiveness.
- Keep control logic centralized in app/optimizer.py.
- Keep entity IDs and thresholds configurable through app/config.py and add-on options.
- Separate non-live simulation/inspection tools from live control actions.
- Changes to control logic should be small, explicit, and accompanied by before/after reasoning and test notes.
- Do not scan .git, .venv, ZIP/release artifacts, backups, caches, generated files, local DBs, or unrelated files unless explicitly required.

## 6. Safety rules / do-not-break rules
- Be conservative with battery, grid, solar, import/export, and live-control assumptions.
- Preserve manual override and safety behaviour.
- Do not assume grid sign conventions from a single signed sensor if separate import/export sensors are configured.
- Do not assume export/import semantics, battery SoC meaning, inverter state behaviour, or tariff interpretation without checking current config/docs.
- Document entity and integration assumptions for any logic change.
- Do not run old SigEnergy blueprint automations alongside this add-on.

## 7. Control mode behaviour
- Documented HA helper mode options are:
  - Automated
  - Force Full Export
  - Force Full Import
  - Force Full Import + PV
  - Prevent Import & Export
  - Manual
- README distinguishes non-live tools from live actions:
  - Verified non-live paths are Simulate Automated, Preview, Overlay This, and Clear Simulation.
  - Verified live-control paths are Run Cycle Now and manual override actions.
  - Manual override controls exist in the UI and should be returned to Automated after testing when appropriate.
- Needs confirmation: whether current UI/runtime explicitly exposes a separately named "monitor-only" mode beyond the documented non-live simulation tools.

## 8. Battery/grid/solar/import/export assumptions
- Default config uses separate import and export power sensors, separate energy sensors, and separate Amber import/export value entities.
- Battery SoC, reserve floors, sunrise reserve, export thresholds, import thresholds, and cap values are configurable in app/config.py.
- Grid import/export limit entities, ESS charge/discharge limits, and PV max power limits are live-controlled surfaces.
- reason_text_helper and sigenergy_mode helper entities are part of the operator-facing control/reporting path.
- Avoid changing logic that depends on SoC floors, reserve buffers, forecast safety, or export/import thresholds without test notes.

## 9. Key files and folders
- AGENTS.md
- README.md
- docker-compose.yml
- Dockerfile
- requirements.txt
- release.sh
- sigenergy_optimizer_addon/config.yaml
- app/config.py
- app/main.py
- app/optimizer.py
- app/forecast_utils.py
- app/earnings.py
- app/ha_client.py
- app/ha_ws_client.py
- app/state_store.py
- app/routers/
- tests/

## 10. Known issues or watch items
- Old blueprint automation coexistence is explicitly unsafe.
- Control-path regressions can come from wrong entity assumptions, wrong tariff interpretation, or mistaken import/export sign handling.
- Note: release.sh updates config.yaml version but not README.md, so ensure README.md is manually updated when releasing new versions.
- Local env/test artifact files exist in the repo root but are not source of truth.
- Daytime full-battery export now clamps to measured PV surplus (not optimistic solar-power-now headroom) when tomorrow forecast is below forecast_safety_charging × battery_capacity_kwh.
- Advisory export value gate is calculation/status only on `main` for now: `export_value_gate_enabled=false`, `export_value_gate_dry_run=true`, and `export_value_gate_enforce=false` keep live export behavior unchanged unless a future task explicitly wires enforcement.

## 11. Next likely work
- Continue targeted control-path hardening with explicit test coverage.
- If approved, carry the advisory export value gate from `main` into `feature/modular-refactor` as a separate follow-up task.
- Keep entity assumptions and operator docs aligned with current UI and add-on behaviour.
- Maintain clear separation between simulation/inspection tools and live control actions.

## 12. Testing/audit checklist
- Run targeted tests for changed control, forecast, earnings, and state-store paths.
- For any control logic change, document before/after reasoning and include test notes.
- Manually verify behaviour for non-live simulation tools versus live actions.
- Verify helper entities and configured entity IDs exist before diagnosing logic faults.
- Verify old blueprint automations are disabled when testing live add-on control.
- Check add-on logs after install/update and after live override testing.

## 13. Packaging/release notes
- Add-on metadata/version lives in sigenergy_optimizer_addon/config.yaml.
- README documents release.sh for version bump/tag/release flow.
- Keep add-on config, app config defaults, and README setup instructions aligned.
- Exclude local env files, caches, coverage, test outputs, ZIPs, and other generated artifacts from releases.

## 14. How a future AI should start work on this project
1. Read AGENTS.md first.
2. Read this handover, then README.md and sigenergy_optimizer_addon/config.yaml.
3. Check app/config.py before assuming entity IDs, thresholds, or mode labels.
4. Touch only the minimum files needed; keep control changes small and explicit.
5. Treat battery/grid/solar/import/export logic as safety-sensitive.
6. If a requested change affects live control, record before/after reasoning and validate with targeted tests.
7. If version or behaviour documentation conflicts, write Needs confirmation rather than guessing.
