# SigEnergy Optimizer for Home Assistant OS

Local, unpublished diagnostics candidate: decision traces distinguish requested
ESS charging from the reported charge-limit setting and measured battery power,
with flow report timestamps and Solar feedback boundaries. This does not correct
Solar allocation or prove inverter settlement. See the
[passive evidence contract](docs/CONTROL_CONTRACT.md#passive-charge-allocation-evidence).

## Current published release: 2.3.69-haos80

Published 25 October 2026 at 23:20:09 UTC (26 October 10:20:09 Sydney):
[GitHub Release](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.69-haos80).
Tag/source `acb576747e808e927bdd7d12346c507da9b188b6`, tree
`14103ec71d3b41ad6a85e2d8a149e3db705606bf`; metadata [PR #44](https://github.com/Belot77/sigenergy-optimizer/pull/44)
normally merged at `77bde899da35b2f933304192a9c7226d9e5e9ef3` with the exact tag
tree. Build [40243683190](https://github.com/Belot77/sigenergy-optimizer/actions/runs/40243683190)
succeeded at the exact source.

The UI logging fix filters recognized successful 2xx `httpx` INFO request messages
from the built-in UI ring. The newest-first 500-record in-memory buffer resets on
restart and can evict older errors; console logging and global levels are unchanged.
No control, retry or settlement behavior changed. See [the .80 publication receipt
and verification limits](docs/HAOS80_RELEASE_CANDIDATE.md).

Version/latest OCI index: `sha256:91120b1039eec3915a37c6ff1a1210cf1cf5e79d97e3e1d9de31207206301a5a`.
For amd64 and arm64, all 22 layer hashes, sizes and diff IDs were verified, and
fourteen target files per architecture match the tag. Fingerprint:
`sha256:386444cfc2defee474052cc86cb473059d8f1551d67ad49832e4e352fd382cf4`.
Immutable .79 index remains unchanged at
`sha256:cbaa5f68e4830737abba90666e486b9db848b3a853d1c9138c33a93f3b02bdad`.

Retained source validation passed 122 tests / 10 subtests, zero failures, 202
warnings, in 68.94 seconds; independent logging verification passed 30 cases.
All 46 release/source-pinning/logging checks passed in 10.69 seconds. Independent
helper and complete publication-proof reviews were GO; 68 synthetic verifier cases
passed. Auto-update was last confirmed off on 26 October before .79 publication;
there was no new HA query. No installed .79/.80 identity, full filesystem
equivalence or physical acceptance is claimed. The 65 failed applications and
59 unsuccessful fallbacks remain unexplained. O18, O5/O9, broader O6 depletion/floor
questions and parked O11 remain open.

## Previous published release: 2.3.68-haos79

Published 25 October 2026 at 21:08:21 UTC (26 October 08:08:21 Sydney):
[GitHub Release](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.68-haos79).
Tag/source `ea516ef6cabd9918dbea675694a9de3aa207c8af`; metadata [PR #41](https://github.com/Belot77/sigenergy-optimizer/pull/41)
normally merged at `44419af295a47be24d5f06af3ed7cba83b2f27bb` with exact tagged
tree `8e7e6cf6cdcbb6196383352c2a351f055aed5912`. Actions run `40233491965`
succeeded at the exact tag source.

Includes bounded O2 Solar re-entry and O6 relieved-Morning charge-handoff
qualification. Version/latest OCI index:
`sha256:cbaa5f68e4830737abba90666e486b9db848b3a853d1c9138c33a93f3b02bdad`.
Both amd64/arm64 images were checked; all 22 layer hashes, sizes and diff IDs
were verified, and fourteen target files per platform match the tag. Verification fingerprint:
`sha256:a5a6945fc54c5a872a97b717d377cb88b57c6c0e7d8a9704174bc33324f2e3f8`.
Immutable .78 index remains unchanged at
`sha256:35292feb279a4b33e4c86f5482d690a9704c91d7178038b115c3bc434ead991a`.

Full offline validation passed 1,415 tests / 1,380 subtests, zero failures,
206 existing warnings, in 241.93 seconds; focused checks passed 165 / 184.
All 16 release checks passed in 9.83 seconds. Independent source and publication
proof reviews were GO. See [the .79 publication receipt and acceptance limits](docs/HAOS79_RELEASE_CANDIDATE.md).
Auto-update was confirmed off by the operator on 26 October. No HA installation
or physical acceptance is claimed; O18 fill strategy, O5/O9 review, broader O6
depletion/floor questions and parked O11 remain open.

## Previous published release: 2.3.67-haos78

Published 24 October 2026 at 07:57:03 UTC (18:57:03 Sydney):
[GitHub Release](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.67-haos78).
Tag/container source: `3ccf99cc69a4586715aadcbdd2f1282aeea77bf0`.
[PR #38](https://github.com/Belot77/sigenergy-optimizer/pull/38) normally merged
with the exact tag tree after both architecture images were verified.

Includes O15 bounded runtime database execution and O17 transport-peer-bound HA
ingress authentication, atop .77 transaction, ledger and trace-recovery fixes.
Slow or unconfirmed storage retains unknown-cost protections. Normal HA ingress
keeps its HA login; custom proxies use the existing API-key path. Public
read/status policies remain unchanged. Accepted writes can complete after
timeout: refresh state before retrying. Threads cannot interrupt wedged OS I/O.

Merged-source validation passed **1,355 tests / 1,305 subtests**; focused 126 / 8.
All 16 release/source-pinning checks passed in 9.58 seconds. Independent source
and metadata reviews were GO. Both platform images, all 22 layers and thirteen
source/launcher files per platform match exact tag bytes.

[Publication receipt, upgrade and rollback notes](docs/HAOS78_RELEASE_CANDIDATE.md).
Installation and physical acceptance remain operator actions; existing reserve,
MSC settlement, independent limits and Manual/Force safeguards remain in place.
Ordinary runtime Logs availability and historical HDD/MSC causation remain unproven.

## Previous published release: 2.3.66-haos77

Published **2.3.66-haos77** on 24 October 2026 at 01:54:00 UTC (12:54:00 Sydney): [GitHub Release](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.66-haos77). Tag/source `7aa712f72ca2c0467e6740e3cb0f2191ba8d077e`, tree `33d9b94399f87d27baf787a59403861988182ce9`. Source PR #34 merged at `b4377de9f38d1c305c23a0b1dca9cb509afc1a9f`; metadata PR #35 merged at `81c2752c4e031bb9786ec0d00f1dca4e22c59de9` with exactly the tagged tree.

Includes configuration transaction safety, import-cost ledger integrity and trace clock recovery. Both architecture images and exact source bytes are verified; 1,275 tests / 1,305 subtests and all 16 release checks passed. [Publication receipt, upgrade and rollback notes](docs/HAOS77_RELEASE_CANDIDATE.md).

Install through the normal Home Assistant update flow using your backup/restore precautions. Trace recovery can take a normal 15-minute persistence interval when its HTTPS time checks pass. Unknown import-cost history may pause applicable automatic battery sales; independently qualified PV-only and Manual/Force behavior remain separate. Installation and physical acceptance remain operator actions.

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

Published .80 release: the optimizer's built-in
log viewer/download omits recognized successful 2xx `httpx` INFO requests while
keeping HTTP failures and other diagnostics. Add-on console logs remain unchanged.
The UI holds at most 500 retained records in memory, newest first; requesting more
lines cannot recover evicted entries, and restarting clears this buffer. This
change improves diagnostic retention without changing optimizer control behavior.

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
Trace. The latest supplied installed startup/source proof remains
`2.3.64-haos75` / `413e1691bb58e0b942098ab43f44e873df157a2b` from 21 October;
it is not evidence that published `.76` is installed. The excerpt's
pending-close then pending-MSC states and subsequent HTTP 200 reads do not
prove physical settlement or later recovery. The prior `.73` proof is
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

Published .76 includes the PR #31 Standby Holdoff and active Morning Dump fallback import-blocking correction. Ordinary economic-zero recovery retains its existing behavior. O13 code is published, but physical behavior remains unverified. See [current status and remaining gates](docs/CURRENT_STATE.md).

## Version

Current published release: [**2.3.66-haos77**](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.66-haos77), published 24 October 2026. Tag/source `7aa712f72ca2c0467e6740e3cb0f2191ba8d077e`; metadata PR #35 merged at `81c2752c4e031bb9786ec0d00f1dca4e22c59de9` with the tagged tree. O15/O17 are source changes in this integration candidate, not part of .77. See [the verified .77 receipt](docs/HAOS77_RELEASE_CANDIDATE.md) and [current development state](docs/CURRENT_STATE.md).

Historical .76 image verification, superseded as the current release by .77: OCI index: `sha256:b7df9f21fce7ef14e7b4f602235486e17b35b710907656dd0b43e796889a6e9a`; amd64 manifest `sha256:153257933183c42fa99afdd21a8ab0d48837eb64623e136d7d0a07b3db17269e`, arm64 manifest `sha256:8288d84e1bd41858d022caff8b91d11adab998b21f99ee7d1a92985c9be4b161`. The `.75` version-specific index remains unchanged at `sha256:ed2a984b457bfddb2b74050d437f98337944076e9144a8d1a19f577d8e82d898`.

The latest supplied full installed startup/source proof remains `.75` / `413e1691bb58e0b942098ab43f44e873df157a2b` on 21 October. The operator reported .76 installed after replacement-SSD restoration on 24 October; neither the .77 release receipt nor the fresh trace establishes a newer exact runtime identity. No live settings change, Boost enablement or physical acceptance is claimed here; actual rollback remains unverified. O4/O5, the parked O11 investigation and applicable Phase 1/2 live gates remain open.

The operator initially reported `.74` installed, Evening Boost off and add-on auto-update off. Later startup evidence at 13:28:25 Sydney identifies runtime signature `.75` and exact source `413e1691bb58e0b942098ab43f44e873df157a2b`. The excerpt shows pending-close then pending-MSC states through 13:28:29 and HTTP 200 service/reads through 13:28:50; it does not prove physical settlement or later recovery. This is the latest full startup/source proof; the earlier `.73` evidence is historical. No rollback method was supplied; supervised acceptance remains unverified.

`.73` includes version/source-pinned builds and resolved full-SHA recording, while carrying `.72` optimizer control behavior unchanged. The `.72` corrections cover Solar Override selected/protected floors, Morning Dump discharge intent and blocked-Dump MSC fallback, application-outcome trace recording, and precise positive sub-1-cent FiT explanations. The frozen `.72` tag/image exclude the Dockerfile source-pinning fix.

Clock recovery code is published in .77. The supplied 24 October archive contains 152 current persisted records from 17:07:41 to 17:22:40 Sydney with intact sequence continuity and a maximum ten-second interval. This is partial freshness evidence, not proof of runtime source, the preservation manifest, missing historical cycles or behavior across another restart. The original archive/MSC incident investigation remains parked and HA/hardware causation unproven. Short physical Demand Window import spikes remain separately deferred. See [current state and evidence limits](docs/CURRENT_STATE.md).

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
