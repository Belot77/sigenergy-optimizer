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

## Solcast provider-aware Solar charge freshness

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
Trace. The latest published add-on release is `2.3.64-haos75`, tag/source
`413e1691bb58e0b942098ab43f44e873df157a2b`; the source and both architecture
images were verified. The operator reported `.74` installed, Evening Boost off
and add-on auto-update off. Startup evidence at 13:28:25 Sydney identifies
runtime `2.3.64-haos75` and source
`413e1691bb58e0b942098ab43f44e873df157a2b`, matching the release. Pending-close
then pending-MSC states appeared through 13:28:29; HTTP 200 service/reads
continued through 13:28:50. This does not prove physical settlement or later
recovery. It is the latest full startup/source proof; the prior `.73` proof is
historical. Rollback method remains unprovided.

### Solar low-surplus continuation (published .74; historical characterization, 20 October 2026)

After successful final Solar application, existing MSC export permission may
bridge a brief dip strictly before 15 seconds after the older fresh, coherent
PV/load report proving measured surplus above 0.5 kW.
Only a newly advancing PV and load report pair can renew the hold. Held or
cached reports, surplus from 0.2 to 0.5 kW, and forecast evidence cannot renew
it. Trust, coherent-flow, authority or application failure invalidates proof
immediately. Expiry requests conservative closure under current control
authority; failed applications retain deadline re-evaluation with bounded
three-second retries. Physical closure still requires actuator settlement.

A sanitized deterministic candidate characterization reproduced seven
25-to-zero kW closures at baseline; the candidate retained permission through
those short dips with renewed strong measured reports. Its mocked application
and real-tick timing do not constitute a full trace replay or physical inverter
proof; the physical cause remains unproven. This change is included in published
.74; this characterization does not establish installation or live behavior.

The release includes the reviewed control behavior from PR #26. See [the .74
release and supervised proof plan](docs/HAOS74_RELEASE_CANDIDATE.md).

## Evening Boost changes in published .75

The published .75 code requires trusted load and sunrise inputs for the overnight reserve calculation. Before initial Boost admission or after startup, restart, or return from manual ownership, fresh load reports must span at least 120 seconds and local monotonic time must also advance at least 120 seconds. These are minimums, not a promised start time. Cached reports do not qualify. A load-report gap or more than 60 seconds without an advancing report resets qualification; report cadence and latency may delay admission indefinitely. Existing failure closures remain immediate. Offline tests do not prove physical operation or settlement. Keep Boost off during initial verification of runtime identity, effective settings, report cadence, and reserve/limit assumptions; then enable it only as part of the already-authorized supervised acceptance trial. Switch off and retain manual ownership immediately on a safety failure, unexpected ownership, failed settlement, or renewed flapping. Unattended use follows only after acceptance succeeds. See the [published release and acceptance receipt](docs/HAOS75_RELEASE_CANDIDATE.md), [control contract](docs/CONTROL_CONTRACT.md), and [current status](docs/CURRENT_STATE.md).

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
- The retained `poll_interval_seconds` setting controls daily/morning summary timing tolerance and status/health stale-data thresholds, not decision-loop frequency.

Local unreleased correction: Standby Holdoff and active Morning Dump keep their grid-import close through actuator fallback and settlement recovery. Ordinary economic-zero recovery retains its existing behavior. See [current candidate validation and supervised verification requirements](docs/CURRENT_STATE.md); published .75 does not yet include this correction.

## Version

Latest published release: [**2.3.64-haos75**](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.64-haos75), published 21 October 2026. Tag/source `413e1691bb58e0b942098ab43f44e873df157a2b`; PR #29 merged at `b88ac1f36811a253fc8602a781103a255ec932fd`. Verified OCI index `sha256:ed2a984b457bfddb2b74050d437f98337944076e9144a8d1a19f577d8e82d898`, with amd64 and arm64 images matching the tagged source. The prior .74 OCI index remains `sha256:3f3d46ce2cef41a8246cc63db2ef794c0e1907cf2a2518acf751cdc2646399ee`.

The operator initially reported `.74` installed, Evening Boost off and add-on auto-update off. Later startup evidence at 13:28:25 Sydney identifies runtime signature `.75` and exact source `413e1691bb58e0b942098ab43f44e873df157a2b`. The excerpt shows pending-close then pending-MSC states through 13:28:29 and HTTP 200 service/reads through 13:28:50; it does not prove physical settlement or later recovery. This is the latest full startup/source proof; the earlier `.73` evidence is historical. No rollback method was supplied; supervised acceptance remains unverified.

`.73` includes version/source-pinned builds and resolved full-SHA recording, while carrying `.72` optimizer control behavior unchanged. The `.72` corrections cover Solar Override selected/protected floors, Morning Dump discharge intent and blocked-Dump MSC fallback, application-outcome trace recording, and precise positive sub-1-cent FiT explanations. The frozen `.72` tag/image exclude the Dockerfile source-pinning fix.

Current live-memory recording is demonstrated, including pending/error outcomes and later successful Automated/MSC applications. Persistent 24-hour download freshness and intermittent MSC settlement remain **parked, unresolved** by operator choice; HA/hardware cause is unproven. Short physical Demand Window import spikes remain separately deferred. See [current issues, past-week fixes and the .73 live-proof checklist](docs/HAOS73_STATUS_AND_LIVE_PROOF.md).

Protected rollback reference: **2.3.54-haos65**, source `9965e79133f38d5b9943dcf5a9b04ed6fdab1239`, public OCI index `sha256:dd7efe0fd9b192ae1fd996137c312e5f2aab12e01a285f6e75fb5a58dc8fe88c`. There is no GitHub Release for `.65`; an actual usable Supervisor restore/reinstall method and saved effective settings remain unverified. Artifact availability alone is not rollback proof.

Existing unfinished worktrees and the separate local archive-characterization tests remain preserved. The physical-export software default remains `0.0` (disabled); the reported site limit is not a universal default. The earlier README publication-status update changed no application behavior, thresholds, settings or permanent instructions; the Evening Boost behavior described above is included in published .75, with exact installed startup identity supplied and physical acceptance still unverified. The historical `release.sh` remains unsuitable: it preserves the haos suffix, updates only three of five markers, stages all changes and can commit/tag/push. Do not use it without a separate repair/review.

## Historical Maintainer Release Flow (not current instructions)

The helper examples below are historical. `release.sh` preserves an existing `haos` suffix and updates only three of the five established version markers. Do not use it for a future release until this behavior has a separate fix and review. For future catalog or publication work, create and verify the matching source tag before advertising the version or relying on a version-tag build; publication requires separate authorization.

Historical helper usage (do not use for current releases without separate review):

```bash
./release.sh patch
./release.sh minor "Release vX.Y.Z"
./release.sh major "Release vX.0.0"
./release.sh --dry-run patch
```

Notes:
- Historical behavior: the script updates only three of the five version markers and preserves an existing `haos` suffix.
- Historically it created and pushed `vX.Y.Z` to trigger `.github/workflows/build.yml`; do not treat these examples as current release instructions.
- If `GITHUB_TOKEN` is set, the helper polls GitHub Actions and reports success/failure.
