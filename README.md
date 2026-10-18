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

- Think of this as a practice run.
- It tries different strategy styles and shows which one looks best right now.
- The simulation comparison panel is hidden by default and appears after you press this button.
- It only changes what you see on the screen.
- It does not change your real inverter settings.

### Run Cycle Now

- Think of this as "do the real check now".
- It makes the optimizer run immediately instead of waiting for the next normal cycle.
- This can apply real control changes (mode/limits) if the optimizer decides they are needed.
- Use this when you want an immediate live refresh/action.

### Preview (inside Simulation cards)

- Preview means "select this option and inspect it".
- It updates the comparison view and details so you can review that strategy.
- It does not draw the full simulation overlay on the chart.
- It does not change live settings.

### Overlay This (inside Simulation cards)

- Overlay means "draw this scenario over the live chart".
- It visually places the simulated path on top of your normal chart so you can compare easier.
- It is still a visual what-if tool only.
- It does not change live settings.

Quick rule of thumb:
- Preview = pick and inspect.
- Overlay = show it on the chart.
- Simulate Automated = run a what-if comparison.
- Run Cycle Now = run the real optimizer immediately.

### Clear Simulation

- After running simulation, the Simulate Automated button changes to Clear Simulation.
- Clear Simulation removes the visual simulation overlay and hides the simulation comparison panel again.
- It does not change live inverter settings.

## Step 5 - Verify Correct Operation

- Add-on logs: Settings -> Add-ons -> SigEnergy Optimizer -> Logs
- Optional CLI: ha addons logs local_sigenergy_optimizer

Quick check:
1. Use a manual override in the UI.
2. Confirm expected EMS mode and limits are written.
3. Return to Automated mode.

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
PV_SURPLUS_ESTIMATED_INIT_ENABLED=true
SUNRISE_RESERVE_SOC=10.0
MORNING_DUMP_MIN_SOC=30.0
```

Morning Dump uses `MORNING_DUMP_HOURS_BEFORE_SUNRISE` as a compatibility key for
the total window duration ending one hour after sunrise. For example, `0.5`
starts 30 minutes after sunrise and can run for up to 30 minutes. Morning Dump
cannot start or continue at or below `MORNING_DUMP_MIN_SOC`, which defaults to
30%, regardless of forecast refill confidence.

After changing add-on config, restart the add-on.

## Solcast provider-aware Solar charge freshness (unreleased candidate)

Dynamic Solar charge-ceiling ownership uses provider refresh evidence separately
from Forecast Today's HA observation age. Map `forecast_today_sensor` and
`solcast_api_last_polled_sensor` to entities from the same Solcast instance. Their
default entity IDs are `sensor.solcast_pv_forecast_forecast_today` and
`sensor.solcast_pv_forecast_api_last_polled`; compatible environment keys are
`FORECAST_TODAY_SENSOR` and `SOLCAST_API_LAST_POLLED_SENSOR`.

Startup/reconnect/reload requires a baseline followed by a successful API Last
Polled advance. Normal charging remains available while unverified. Later
schedules and successful manual polls before a retained deadline cannot extend
that deadline. Expiry releases only the dynamic Solar charge restriction;
Solar remains subject to all existing MSC/PV-only and ownership protections.

Settings -> Forecast Safety exposes **Forecast observation maximum age (seconds)**,
using the existing `hvac_solar_forecast_max_age_seconds` /
`HVAC_SOLAR_FORECAST_MAX_AGE_SECONDS` key and 600-second default. It applies to
Remaining Today, Power Now, Forecast Today trust for Standby Holdoff, age-based
Forecast Tomorrow trust and selected import-price forecast freshness. Dynamic
Solar provider freshness is schedule/provider-aware and is not extended by it.

Before live acceptance, inspect provider state, poll/high-water/verified times,
retained/advertised deadlines, source/epoch and rejection reasons in Decision
Trace. Local tests do not prove inverter behavior. Live `.65` remains unchanged;
this candidate has not been released or deployed.

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

Latest published release: [**2.3.60-haos71**](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.60-haos71), with tag `v2.3.60-haos71` at published baseline `9f3f02a5c1c82786c85026a3848574cca3cf891f`. PR #21 merged the reviewed code checkpoint into `main` at `5275e9cd3803ba991351c790be6b7187c3941981`; this merge does not establish installation or live acceptance. Last operator-reported live remains `.70 / 2.3.59-haos70` at `08f4daf53941bd850a4fe392b458c42b1df68b47`, not freshly HA-verified. An external report says .71 was installed, but no HA About/startup/source-build evidence was supplied; installed identity remains unresolved. Protected rollback remains `.65 / 2.3.54-haos65` at `9965e79133f38d5b9943dcf5a9b04ed6fdab1239`.

Local release candidate: **2.3.61-haos72**, branch `release/2.3.61-haos72`, based on merge `5275e9cd3803ba991351c790be6b7187c3941981`. Version/documentation preparation remains uncommitted and unpushed; preflight found candidate tag `v2.3.61-haos72` absent; GHCR namespace conflict was not verified and remains a publication-gate check. No candidate build, publication, installation or live acceptance is claimed. The two release consistency tests passed and `compileall app tests` passed with an isolated temporary cache. Final checks passed: exactly 12 modified files (five release-marker files and seven documents), marker-only source deltas, unchanged protected code/tests/contract, and `git diff --check`. Retained combined offline validation is 1,073 tests / 1,134 subtests, zero failures, 206 warnings in 170.97 seconds; those results predate release preparation and are not physical-settlement evidence.

The merged code includes the Solar Override selected/protected floor guard with separately qualified PV-only MSC preservation; Morning Dump qualified-intent discharge and explicit blocked-Dump MSC fallback; application-outcome trace metadata with recorder isolation; and precise positive sub-1¢ FIT reasons. Thresholds and settings are unchanged. Short physical Demand Window import spikes remain deferred separately from O7 exact-full PV-only proof; O1-O9 live/evidence gates remain open.

Original Solar Override and Morning Dump worktrees remain preserved. The physical export-limit software default remains `0.0` (disabled), with no universal 15 kW default. Release, deployment and live-control actions require separate approval.

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
