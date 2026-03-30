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
