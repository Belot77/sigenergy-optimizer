# SigEnergy Optimizer Add-on (HAOS)

This folder contains a Home Assistant OS Add-on package for SigEnergy Optimizer.

## Install (Home Assistant OS)

1. In Home Assistant: **Settings -> Add-ons -> Add-on Store -> Repositories**.
2. Add this repository URL:
   - `https://github.com/Belot77/sigenergy-optimizer`
3. Find **SigEnergy Optimizer** in the Add-on Store and install it.
4. In the add-on **Configuration** tab, set at least:
   - `ha_url`
   - `ha_token`
5. Start the add-on and open via Ingress.

## Options

- `ha_url`: Home Assistant URL, e.g. `http://homeassistant.local:8123`
- `ha_token`: Long-lived access token
- `ui_api_key`: Optional dashboard/API key
- `extra_env`: Optional extra env lines (`KEY=value`), one per line

The add-on keeps runtime config in `/data/.env` inside Home Assistant add-on storage.

## Unreleased Solar provider-freshness candidate

In app Settings, map Forecast Today and Solcast API Last Polled from the same
Solcast instance. The compatible keys are `FORECAST_TODAY_SENSOR` and
`SOLCAST_API_LAST_POLLED_SENSOR` (the latter defaults to
`sensor.solcast_pv_forecast_api_last_polled`). Startup and discontinuity recovery
require a baseline followed by a successful provider timestamp advance. Reduced
Solar charging is bounded by the retained scheduled deadline and today's horizon.

Forecast Safety exposes **Forecast observation maximum age (seconds)** using
the unchanged `HVAC_SOLAR_FORECAST_MAX_AGE_SECONDS` key/default of 600. It continues
to bound Remaining Today, Power Now, Forecast Today/Standby Holdoff, age-based
Forecast Tomorrow and selected import-price observations. It cannot extend
schedule/provider-aware dynamic Solar charge authority.

This candidate is not installed or live-accepted. Live release and rollback
remain `2.3.54-haos65` / `9965e79`; release/deployment requires separate approval.
