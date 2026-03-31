# SigEnergy Optimizer — Complete Setup Guide

## What This Does

This service automatically controls your SigEnergy battery system based on electricity prices and solar forecasts. It replaces the Home Assistant blueprint automations.

**How it works:**
- Monitors your battery charge level, solar power, and current electricity price
- Automatically switches between charging from the grid, discharging to the grid, or using solar power
- Maximizes profit by charging when prices are cheap and exporting when prices are high
- Includes a dashboard (Open Web UI from the add-on page) where you can see what it's doing and override it manually

---

## Prerequisites — What You Need

- **Home Assistant** up and running on your network (with admin access)
- **SigEnergy integration** added to Home Assistant (your battery and inverter already connected)
- **Amber integration** (for electricity prices)
- **Solcast integration** (for solar forecasts)
- **Home Assistant OS** install type
- A **Home Assistant Long-Lived Access Token** (required)

---

## Home Assistant OS (Recommended Path)

If your install type is **Home Assistant OS**, run this as a Home Assistant Add-on instead of external Docker.

You still need a Long-Lived Access Token because the optimizer authenticates to Home Assistant REST/WebSocket APIs using `ha_token`.
Create it under your Home Assistant user profile, then paste it into the add-on configuration.

**Important safety order:** Complete **Installation Step 1 (disable old blueprint automations)** before installing or starting the add-on.

1. Open **Settings -> Add-ons -> Add-on Store -> Repositories**.
2. Add this repository URL:
  - `https://github.com/Belot77/sigenergy-optimizer`
3. Install **SigEnergy Optimizer** from the Add-on Store.
4. In the add-on config, set at least:
  - `ha_url`
  - `ha_token`
5. Start the add-on and open via Ingress.

Add-on files are in `sigenergy_optimizer_addon/` and repository metadata is in `repository.yaml`.

If you are **not** on Home Assistant OS, use the Docker deployment method from an earlier release of this guide.

---

## Installation — Step by Step

### Step 1: Disable the Old Blueprint Automations

Log into Home Assistant and go to **Settings → Automations & Scenes**.

Find and disable (or delete) these two automations:
- `sigenergy_optimiser`
- `sigenergy_manual_control`

This prevents conflicts when your new optimizer starts.

---

### Step 2: Create Home Assistant Helpers

The optimizer needs several helper entities. If you already used the original YAML automation, these may already exist.

Before creating anything new, check **Developer Tools -> States** for these exact entity IDs:

- `input_boolean.sigenergy_automated_export`
- `input_number.sigenergy_export_session_start_kwh`
- `input_number.sigenergy_import_session_start_kwh`
- `input_number.battery_min_soc_to_last_till_sunrise`
- `input_text.sigenergy_last_export_notification`
- `input_text.sigenergy_last_import_notification`
- `input_text.sigenergy_reason`
- `input_select.sigenergy_mode`

If they already exist, skip creation and continue to Step 3. Only create missing helpers.

To create missing helpers:

1. Open Home Assistant → **Settings → Devices & Services → Helpers**
2. Click **Create Helper → Automation**
3. Add these helpers:

**Easiest way: Copy/paste YAML**

Go to **Settings → System → YAML Configuration** (or edit `configuration.yaml`):

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

Save and **restart Home Assistant** (Settings → System → Restart).

---

### Step 3: Access the Dashboard

Open your web browser and go to:
```
Home Assistant -> Settings -> Add-ons -> SigEnergy Optimizer -> Open Web UI
```

You should see:
- **Current Status:** Battery %, power in/out, prices
- **Decision:** What it's doing (charging, exporting, idle)
- **Reason:** Why it made that decision
- **Manual Overrides:** Buttons to force different modes

---

## Testing & Verification

### Check the logs:
- Go to **Settings -> Add-ons -> SigEnergy Optimizer -> Logs**
- Or from HA CLI: `ha addons logs local_sigenergy_optimizer`

### Test a mode override from the dashboard:
1. Click **Force Full Export** button
2. Check Home Assistant — the EMS mode should change to "Command Discharging (PV First)"
3. Click **Automated** to resume auto control

### Check Home Assistant automations:
The optimizer creates a notification whenever it changes modes. Go to **Settings → System → Logs** and search for "SigEnergy" to see recent actions.

---

## Common Issues & Fixes

### "Connection refused" error
- Check Home Assistant is running: `http://192.168.1.100:8123`
- Verify `ha_url` in add-on configuration is correct
- Check firewall isn't blocking port 8123

### "Entity not found" errors in logs
- Go to Home Assistant **Developer Tools → States**
- Search for your sensor (e.g., `sigen_plant_pv_power`)
- Copy the exact entity ID into add-on config (`extra_env` as `KEY=value`)
- Restart the add-on

### Dashboard shows nothing / blank page
- Wait up to 60 seconds (first startup and first heartbeat can take a moment)
- Check add-on logs in Home Assistant
- Clear browser cache (Ctrl+Shift+Del)
- Open via **Open Web UI** from the add-on page

### Optimizer stops working
- Check add-on logs in Home Assistant
- Verify add-on config values are valid
- Restart the add-on
- If still stuck, stop/start the add-on, then reboot Home Assistant host if needed

---

## Configuration Tuning

Once it's running, you can adjust behavior from the web GUI using **Apply & Save Thresholds**.

For advanced config keys, use the add-on configuration field `extra_env` with one `KEY=value` per line, for example:

```
# When to charge from grid (price threshold, in $ per kWh)
MAX_PRICE_THRESHOLD=0.015

# How much to charge when price is cheap
TARGET_BATTERY_CHARGE=2.0

# Morning export minimum price (in $/kWh)
EXPORT_THRESHOLD_LOW=0.10
EXPORT_THRESHOLD_MEDIUM=0.20
EXPORT_THRESHOLD_HIGH=1.00

# How much to export at each price tier
EXPORT_LIMIT_LOW=5.0
EXPORT_LIMIT_MEDIUM=12.0
EXPORT_LIMIT_HIGH=25.0

# Battery preservation (don't go below this before sunrise)
SUNRISE_RESERVE_SOC=10.0
```

After changing add-on config, restart the add-on.

---

## Stopping & Uninstalling

### Stop temporarily:
- Go to **Settings -> Add-ons -> SigEnergy Optimizer** and click **Stop**.

### Stop and remove everything:
1. Stop the add-on.
2. Click **Uninstall**.

### Re-enable old blueprint automations:
Go back to Home Assistant and re-enable the automations you disabled in Step 1.

---

## Support & Troubleshooting

### View detailed logs:
- **Settings -> Add-ons -> SigEnergy Optimizer -> Logs**

### Monitor in real-time:
Open the add-on page and click **Open Web UI**

### Check Home Assistant integration:
All automations are logged in Home Assistant **Settings → System → Logs**

---

## How It Works — The Short Version

Each cycle (event-driven on watched state changes, with a 60-second heartbeat fallback):

1. **Read state:** Battery %, solar power, load power, current prices
2. **Decide:** Should we charge, export, or idle?
3. **Apply:** Change EMS mode, set export/import limits
4. **Notify:** Send update to Home Assistant and dashboard

The decision rules are:
- **Charge from grid:** If price is low (< $0.015) and battery not full
- **Export:** If FIT price is high (> $0.10) and battery high enough
- **Use solar:** Maximize self-consumption during day
- **Prepare for sunrise:** Charge if forecast shows low solar tomorrow

---

## Next Steps

1. Let it run for 24 hours and watch the dashboard
2. If behavior looks good, it's done — you can forget about it
3. If you want to tweak, adjust thresholds in the dashboard and save
4. Check logs monthly to ensure it's still running smoothly

---

**Questions?** Check the logs first — most issues are explained there.

**Version:** 2.1.2 (March 2026)
