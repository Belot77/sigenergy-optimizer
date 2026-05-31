# SigEnergy Optimizer for Home Assistant OS

This guide is for Home Assistant OS users running the SigEnergy Optimizer as a Home Assistant Add-on.

## Scope and Safety

This optimizer replaces the old blueprint automations for SigEnergy control.
Do not run both at the same time.

Safe order:
1. Disable old blueprint automations.
2. Verify or create required helpers.
3. Install and configure the add-on.
4. Start the add-on.
5. Verify behavior and logs.

## Prerequisites

- Home Assistant OS
- SigEnergy entities available in Home Assistant
- Amber price entities available in Home Assistant
- Solcast entities available in Home Assistant
- Home Assistant Long-Lived Access Token

## Install the Add-on Repository

1. Open Home Assistant: Settings -> Add-ons -> Add-on Store -> Repositories
2. Add repository URL:
   - https://github.com/Belot77/sigenergy-optimizer
3. Find SigEnergy Optimizer in the Add-on Store

## Step 1 - Disable Old Blueprint Automations

Go to Settings -> Automations and Scenes and disable or remove:
- sigenergy_optimiser
- sigenergy_manual_control

## Step 2 - Verify or Create Required Helpers

If you previously used the YAML automations, these may already exist.
Check Developer Tools -> States for these exact entity IDs:

- input_boolean.sigenergy_automated_export
- input_number.sigenergy_export_session_start_kwh
- input_number.sigenergy_import_session_start_kwh
- input_number.battery_min_soc_to_last_till_sunrise
- input_text.sigenergy_last_export_notification
- input_text.sigenergy_last_import_notification
- input_text.sigenergy_reason
- input_select.sigenergy_mode

If all exist, continue to Step 3.
If any are missing, create only the missing helpers.

### Helper YAML (optional)

If you prefer YAML helper creation, add this and restart Home Assistant:

```yaml
input_boolean:
  sigenergy_automated_export:
    name: "SigEnergy Automated Export"

input_number:
  sigenergy_export_session_start_kwh:
    name: "Export Session Start (kWh)"
    min: 0
    max: 9999
    step: 0.001
    unit_of_measurement: "kWh"

  sigenergy_import_session_start_kwh:
    name: "Import Session Start (kWh)"
    min: 0
    max: 9999
    step: 0.001
    unit_of_measurement: "kWh"

  battery_min_soc_to_last_till_sunrise:
    name: "Min SoC to Last Till Sunrise"
    min: 0
    max: 100
    step: 0.1
    unit_of_measurement: "%"

input_text:
  sigenergy_last_export_notification:
    name: "Last Export Notification"
    max: 255

  sigenergy_last_import_notification:
    name: "Last Import Notification"
    max: 255

  sigenergy_reason:
    name: "Current Reason"
    max: 255

input_select:
  sigenergy_mode:
    name: "SigEnergy Mode"
    options:
      - Automated
      - Force Full Export
      - Force Full Import
      - Force Full Import + PV
      - Prevent Import & Export
      - Manual
    initial: Automated
```

## Step 3 - Configure the Add-on

Open the add-on Configuration tab and set at least:

- ha_url
- ha_token

Notes:
- The token is required. The optimizer authenticates to Home Assistant REST and WebSocket APIs using ha_token.
- Advanced overrides can be added in extra_env as KEY=value lines.

## Step 4 - Start and Open

1. Start the add-on.
2. Open Web UI from the add-on page.

You should see current state, active decision, and manual override controls.

## What The Main Buttons Mean (Plain English)

These buttons are easy to confuse at first. Here is what each one does in everyday terms.

### Simulate Automated

Runs a what-if comparison using the live Home Assistant state and current prices.
It ranks the built-in profiles, opens the simulation panel, and overlays the best simulated result on the charts without writing anything back to your inverter.


### Run Cycle Now

Forces the optimizer to perform one real decision cycle immediately instead of waiting for the next background tick.
Use this after changing settings or helpers when you want the add-on to recalculate and write a fresh decision straight away.


### Preview (inside Simulation cards)

Highlights a profile so you can inspect its computed import and export limits and estimated net result.
This changes the preview focus inside the simulation panel, but it does not change the live optimizer output.


### Overlay This (inside Simulation cards)

Draws that simulated profile onto the charts and summary widgets so you can compare it against the current live state.
This is still simulation only. It does not save thresholds and it does not send commands to Home Assistant.


Quick rule of thumb:

- Preview lets you inspect a scenario.
- Overlay This paints that scenario onto the dashboard.
- Simulate Automated picks the current best scenario and turns the overlay on.
- Run Cycle Now executes the real optimizer.

### Clear Simulation

Turns the simulation overlay off, hides the simulation panel, and returns the dashboard to the live optimizer view.


## Step 5 - Verify Correct Operation

Watch one full cycle after startup before you trust the current state.
The UI should populate, the reason bar should update, and the logs should show normal status reads instead of repeated connection or entity errors.


Quick check:
1. Use a manual override in the UI.
2. Confirm expected EMS mode and limits are written.
3. Return to Automated mode.
4. Press Run Cycle Now and confirm the reason text and limits refresh cleanly.
5. If you use simulation, confirm Clear Simulation returns the charts to the live view.

## Module Map

The codebase is now split into modules that match their responsibility:

- [app/optimizer.py](app/optimizer.py): coordinator and thin wrappers
- [app/decision_engine.py](app/decision_engine.py): decision assembly
- [app/decision_reporting.py](app/decision_reporting.py): trace and outcome formatting
- [app/decision_limits.py](app/decision_limits.py): compatibility wrapper for limit-policy modules
- [app/decision_guards.py](app/decision_guards.py): compatibility wrapper for guard-policy modules
- [app/battery_power_service.py](app/battery_power_service.py): battery power source selection
- [app/battery_eta_service.py](app/battery_eta_service.py): battery ETA formatting
- [app/telemetry_api.py](app/telemetry_api.py): telemetry wrapper surface
- [app/telemetry_recording.py](app/telemetry_recording.py): telemetry persistence and recording
- [app/state_api.py](app/state_api.py): state, history, and preset accessors
- [app/state_reader.py](app/state_reader.py): Home Assistant state snapshot reads
- [app/state_store.py](app/state_store.py): local persistence store
- [app/optimizer_runtime.py](app/optimizer_runtime.py): runtime validation and parsing helpers
- [app/optimizer_bootstrap.py](app/optimizer_bootstrap.py): constructor and runtime state initialization
- [app/lifecycle_service.py](app/lifecycle_service.py): WebSocket lifecycle helpers
- [app/manual_mode_service.py](app/manual_mode_service.py): manual mode target logic
- [app/action_applier.py](app/action_applier.py): write decisions back to Home Assistant
- [app/notification_service.py](app/notification_service.py): notifications and summaries
- [app/time_forecast_service.py](app/time_forecast_service.py): compatibility wrapper for time and forecast helpers
- [app/sunrise_window_service.py](app/sunrise_window_service.py): day-window and sunrise SoC target logic
- [app/forecast_policy_service.py](app/forecast_policy_service.py): forecast-driven decision checks
- [app/forecast_guard_service.py](app/forecast_guard_service.py): forecast-driven guard policy
- [app/import_policy_service.py](app/import_policy_service.py): import/grid charging policy
- [app/power_limit_policy.py](app/power_limit_policy.py): PV/ESS output limit policy
- [app/ems_mode_service.py](app/ems_mode_service.py): EMS mode selection policy
- [app/event_loop_service.py](app/event_loop_service.py): optimizer loop and queue draining
- [app/tick_service.py](app/tick_service.py): single optimizer cycle execution

## Plug-In Surface

If you want to test this in another checkout, the smallest useful runtime surface is:

- `Settings` from [app/config.py](app/config.py)
- `HAClient` from [app/ha_client.py](app/ha_client.py)
- `SigEnergyOptimizer` from [app/optimizer.py](app/optimizer.py)
- `create_app()` from [app/main.py](app/main.py) if you want the FastAPI app

Minimal wiring looks like this:

```python
from app.config import Settings
from app.ha_client import HAClient
from app.optimizer import SigEnergyOptimizer

cfg = Settings(
  ha_url="http://homeassistant.local:8123",
  ha_token="YOUR_TOKEN",
)
ha = HAClient(cfg.ha_url, cfg.ha_token)
optimizer = SigEnergyOptimizer(ha, cfg)
```

For a separate repo, copy the package, keep the config contract the same, and point your test harness at the same `SigEnergyOptimizer` constructor.

## Configuration Tuning

Use the dashboard for day-to-day threshold tuning (Apply and Save).

For advanced keys, use extra_env in add-on config, for example:

```text
MAX_PRICE_THRESHOLD=0.015
TARGET_BATTERY_CHARGE=2.0
EXPORT_THRESHOLD_LOW=0.10
EXPORT_THRESHOLD_MEDIUM=0.20
EXPORT_THRESHOLD_HIGH=1.00
EXPORT_LIMIT_LOW=5.0
EXPORT_LIMIT_MEDIUM=12.0
EXPORT_LIMIT_HIGH=25.0
SUNRISE_RESERVE_SOC=10.0
```

After changing add-on config, restart the add-on.

## Common Issues

Connection refused:
- Check ha_url in add-on config
- Ensure Home Assistant is reachable from add-on runtime

Entity not found:
- Verify entity IDs in Developer Tools -> States
- Add missing helper entities from Step 2
- Use extra_env for non-default sensor/entity IDs if needed

Blank UI or stale state:
- Wait up to 60 seconds for initial cycle/heartbeat
- Check add-on logs
- Reopen via Open Web UI

## Stop or Uninstall

Stop:
- Add-on page -> Stop

Uninstall:
1. Stop add-on
2. Uninstall add-on
3. Re-enable old blueprint automations only if you are rolling back

## Operational Notes

- Decision loop is event-driven with a 60-second heartbeat fallback.
- State inputs include battery, PV, load, and price signals.
- Hardware limit clamping uses live ESS caps, then cached last-known-good caps, then fallback.

## Version

2.3.8-haos22

## Maintainer Release Flow

Use the helper script at repository root to bump version, tag, push, and wait for the publish workflow:

```bash
./release.sh patch
./release.sh minor "Release vX.Y.Z"
./release.sh major "Release vX.0.0"
./release.sh --dry-run patch
```

Notes:
- The script updates `sigenergy_optimizer_addon/config.yaml` `version`.
- It creates and pushes `vX.Y.Z` tag to trigger `.github/workflows/build.yml`.
- If `GITHUB_TOKEN` is set, it polls GitHub Actions and reports success/failure.
