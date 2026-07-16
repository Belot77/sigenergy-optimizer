# SigEnergy Optimizer - AI Handover

## 1. Project purpose
Home Assistant add-on and web UI for SigEnergy battery/energy optimization using Home Assistant state, Amber pricing, and solar forecast inputs. The project is safety-first and intended to replace older SigEnergy blueprint automations.

## 2. Current source-of-truth files
- Root guidance: AGENTS.md and README.md
- Add-on version/package metadata: sigenergy_optimizer_addon/config.yaml
- Main runtime configuration and entity assumptions: app/config.py
- Core optimizer logic: app/optimizer.py
- Control-map/audit reference: docs/CONTROL_MAP.md
- API/UI entry points: app/main.py and app/routers/
- Forecast, earnings, and persistence helpers: app/forecast_utils.py, app/earnings.py, app/state_store.py
- Tests: tests/
- Source of truth is this project folder, not ZIPs, generated outputs, local env files, caches, or test artifacts.

## 3. Current version
- **Authoritative source**: sigenergy_optimizer_addon/config.yaml (version field)
- **Live-known-good version**: 2.3.30-haos41 at commit `b088bb6`, tagged `live-good-2.3.30-haos41`.
- **Feature branch**: `feature/safety-actuator-refactor` at commit `89ccc21` contains completed EMS trust and recovery safety work.
- **Deployment status**: the feature branch is not merged into `main`, is not versioned as a new add-on release, has not been installed into Home Assistant, and has not been live-tested.
- **Note**: release.sh updates config.yaml but not README.md. README.md has been updated to match current config version.

## 4. Main features
- Event-driven optimizer with 60-second heartbeat fallback.
- Home Assistant add-on with ingress web UI and REST/WebSocket integration.
- Amber price and feed-in driven import/export decisions.
- Value Gate / actual import-cost protection on main: 2.3.15-haos26 is cache-bust/metadata only; live control behaviour remains the 2.3.14-haos25 behaviour. That includes the hard automatic guard from 2.3.13 that blocks automatic battery-backed or mixed export below today's highest trusted actual optimiser import/top-up price. True PV-surplus-only export may still be allowed after the configured top-off target is met when measured surplus is proven; a conservative estimated-surplus initiation probe can open a small capped export when measured PV is self-curtailed to house load. Manual/force modes remain exempt.
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

### Confirmed control and actuator policy
- Automated mode may use the specifically approved inverter Command Charging and Command Discharging modes selected by the existing native strategy. These modes are part of known-good energy strategy and must not be removed by a structural safety refactor.
- Automated strategy must not generate or interpret the manual Force-mode labels as automatic decisions.
- PV-only discovery and confirmed `pv_surplus_only` export must remain in Maximum Self Consumption. They must not use a discharge EMS mode.
- Battery-backed export may use the existing approved Command Discharging mode when all existing safety, reserve, price, Value Gate, and actual import-cost conditions permit it.
- Normal automatic writes require a correctly configured, real, available Remote EMS `switch.*` entity that has been observed as on.
- Successfully requesting Remote EMS activation is not equivalent to observing the switch on. Normal automatic strategy writes must wait for a later confirmed on state.
- Observed EMS-mode state must be represented separately from a fallback or recovery target. Maximum Self Consumption must not be used as a fabricated observed value.
- If EMS state is missing, unavailable, unknown, empty, malformed, or otherwise untrusted, normal strategy limit writes must remain blocked. Maximum Self Consumption is the safe recovery target, but a recovery write is allowed only when the EMS entity configuration is valid and Remote EMS has already been observed on. Normal strategy processing may resume only after Maximum Self Consumption has actually been observed; it must not be fabricated as an observed state. A subsequent normal automatic decision may then select another specifically approved EMS mode.
- Supported Command Charging and Command Discharging observations remain trusted during normal operation. Once an untrusted observation starts a recovery episode, however, an approved command-mode observation does not complete recovery; only a later observed Maximum Self Consumption state does.
- Manual modes may continue using their current mapped inverter command modes.
- Returning from Manual to Automated must clear manual overrides. The final safe transition sequence still requires design and tests because Automated may legitimately select a command mode.
- Every Sigenergy write should eventually pass through one controlled actuator boundary.
- The direct `/api/set_ess` operator-control route requires separate future safety hardening, allowed-value validation, ordered execution, and truthful failure reporting.
- HAFO, HAEO, and EMHASS may provide advisory information only. SigEnergy Optimizer remains the sole Sigenergy actuator.

## 7. Control mode behaviour
- Documented HA helper mode options are:
  - Automated
  - Force Full Export
  - Force Full Import
  - Force Full Import + PV
  - Prevent Import & Export
  - Manual
- Automated inverter EMS behaviour intentionally includes:
  - Command Charging (PV First) for positive desired import, cheap charging, and top-up behaviour.
  - Command Charging (Grid First) for sufficiently negative import prices.
  - Command Discharging (PV First) for morning dumping, demand-window export, permitted battery-backed export, export hysteresis, and related existing strategy.
  - Maximum Self Consumption for PV-only discovery and confirmed PV-surplus-only export.
- Automated planning does not use the manual Force-mode labels themselves.
- Current manual mappings are:
  - Force Full Export -> Command Discharging (PV First)
  - Force Full Import -> Command Charging (Grid First)
  - Force Full Import + PV -> Command Charging (PV First)
  - Prevent Import & Export -> Maximum Self Consumption
- Command Discharging (ESS First) is not selected by the native planner or manual target map. It is currently exposed by the direct ESS-control UI/API.
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
- The general Value Gate flags still control stored-energy advisory/enforcement behaviour, but the actual import-cost guard is a hard automatic protection for optimiser-controlled battery-backed/mixed export. Manual force modes remain exempt, and PV-surplus-only export below the import-cost floor is allowed only after the top-off target is met and export is safely capped to measured surplus or the conservative estimated-surplus initiation probe.

### Safety/actuator feature-branch status
Completed on `feature/safety-actuator-refactor` and not live:
- `fafc42a` corrected the safety policy while preserving approved automatic Command Charging (PV First), Command Charging (Grid First), and Command Discharging (PV First) strategy modes. PV-only discovery and confirmed `pv_surplus_only` export remain Maximum Self Consumption only.
- `30e1ace` characterized the approved automatic and manual EMS strategy modes so the safety work does not remove intentional charging, morning-dump, demand-window, or battery-backed-export behaviour.
- `41cfdfc` made EMS observation trust explicit: `SolarState` retains the raw Home Assistant value and separately trusts only Maximum Self Consumption, both Command Charging modes, and both Command Discharging modes. Missing, unavailable, unknown, empty, and malformed values are not fabricated as Maximum Self Consumption.
- Untrusted EMS state blocks ordinary grid, PV, and ESS limit writes. With Remote EMS already observed on, the only permitted recovery request is Maximum Self Consumption; service-call success is not state confirmation.
- Remote EMS observed off may receive the existing activation request, after which the optimiser returns without EMS recovery or limit writes and waits for a later observed-on cycle.
- Recovery requests are limited to once per 60 seconds, detailed warnings to once per five minutes, and failed attempts consume the same retry interval. Remote EMS activation retry state remains separate.
- `89ccc21` requires observed Maximum Self Consumption to complete a recovery episode. Supported command modes remain trusted normally but cannot complete a recovery episode started by an untrusted observation. After Max Self is observed, ordinary Automated processing may resume and may select an approved command mode.
- Validation at `89ccc21`: Remote EMS tests 23 passed plus 2 subtests; strategy tests 83 passed plus 3 subtests; full suite 141 passed plus 5 subtests; compileall and `git diff --check` passed. No Home Assistant installation or live testing occurred.

Still unresolved:
- Manual-to-Automated currently clears the helper and internal overrides but does not perform a distinct, confirmed neutral transition.
- `/api/set_ess` is a supported direct operator-control feature that bypasses the normal automatic gate, accepts backend EMS strings without an allow-list, and ignores service-call failure results.
- Safe fallback writes may partially fail and currently lack strong per-write result handling and confirmed final-state verification.
- A common controlled actuator boundary has not yet been created and should be reconsidered only after the targeted safety behaviours are characterized and hardened.

## 11. Next likely work
### Recommended safety work order
1. Completed: correct the safety policy.
2. Completed: characterize approved automatic and manual EMS strategy modes.
3. Completed: separate observed EMS trust from the recovery target.
4. Completed: make Remote EMS activation wait for a later observed-on state.
5. Completed: require observed Maximum Self Consumption to complete an untrusted-state recovery episode.
6. Completed: add EMS recovery retry and warning throttling.
7. Next: inspect, characterize, and design Manual-to-Automated transition behaviour.
8. Later: harden `/api/set_ess`, including allowed values, prerequisites, write ordering, and failure reporting.
9. Later: harden fallback partial-failure handling and confirmed final-state verification.
10. Later: reassess the common safety/actuator boundary.

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
