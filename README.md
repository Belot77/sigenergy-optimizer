# SigEnergy Optimizer — Complete Setup Guide

## What This Does

This service automatically controls your SigEnergy battery system based on electricity prices and solar forecasts. It replaces the Home Assistant blueprint automations.

**How it works:**
- Monitors your battery charge level, solar power, and current electricity price
- Automatically switches between charging from the grid, discharging to the grid, or using solar power
- Maximizes profit by charging when prices are cheap and exporting when prices are high
- Includes a dashboard at `http://your-machine:7123` where you can see what it's doing and override it manually

---

## Prerequisites — What You Need

- **Home Assistant** up and running on your network (with admin access)
- **SigEnergy integration** added to Home Assistant (your battery and inverter already connected)
- **Amber integration** (for electricity prices)
- **Solcast integration** (for solar forecasts)
- **Docker and Docker Compose** installed on the same or similar machine
  - If you're on Raspberry Pi, Windows, Mac, or Linux: [Get Docker here](https://docs.docker.com/get-docker/)
- A **Home Assistant Long-Lived Access Token** (instructions below)

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

The optimizer needs several helper entities. Add them to Home Assistant:

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

### Step 3: Get Your Home Assistant Access Token

1. Log in as an admin user
2. Click your **profile picture** (bottom-left corner)
3. Scroll to **Long-Lived Access Tokens**
4. Click **Create Token**
5. Give it a name: `sigenergy-optimizer`
6. Copy the long text string
7. **Save it somewhere safe** — you'll need it in the next step

---

### Step 4: Download and Configure the Optimizer

**On Windows (PowerShell):**
```powershell
# Create a folder for the optimizer
mkdir C:\sigenergy-optimizer
cd C:\sigenergy-optimizer

# Copy the files from this directory into C:\sigenergy-optimizer
# (Download the repository or copy the folder here)
```

**On Mac/Linux:**
```bash
mkdir ~/sigenergy-optimizer
cd ~/sigenergy-optimizer
# Copy the files here
```

**Create the `.env` file:**

1. In the `sigenergy-optimizer` folder, look for a file named `.env.example`
2. Make a copy and rename it to `.env`
3. Open `.env` in any text editor
4. **Change these values:**

```
# Your Home Assistant IP address or hostname
HA_URL=http://192.168.1.100:8123

# Your Long-Lived Access Token from Step 3
HA_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ...

# Your SigEnergy battery system's entity IDs
# (Find these in Home Assistant Settings → Devices & Services)
PV_POWER_SENSOR=sensor.sigen_plant_pv_power
CONSUMED_POWER_SENSOR=sensor.sigen_plant_consumed_power
BATTERY_SOC_SENSOR=sensor.sigen_plant_battery_state_of_charge

# Amber/price entity IDs
PRICE_SENSOR=sensor.amber_general_price
FEEDIN_SENSOR=sensor.amber_feed_in_price

# Everything else can stay default
```

**How to find entity IDs:**

In Home Assistant, go to **Developer Tools → States** and search for your sensors. Copy the entity ID exactly.

---

### Step 5: Start the Docker Container

**On Windows (PowerShell):**
```powershell
cd C:\sigenergy-optimizer
docker-compose up -d
```

**On Mac/Linux:**
```bash
cd ~/sigenergy-optimizer
docker-compose up -d
```

Wait 10 seconds, then check that it started:
```bash
docker-compose logs -f
```

You should see output like:
```
Starting SigEnergy Optimizer
Optimizer event loop started (debounce=3s, heartbeat=60s)
```

---

### Step 6: Access the Dashboard

Open your web browser and go to:
```
http://192.168.1.100:7123
```

(Replace `192.168.1.100` with the IP address of the machine running Docker)

You should see:
- **Current Status:** Battery %, power in/out, prices
- **Decision:** What it's doing (charging, exporting, idle)
- **Reason:** Why it made that decision
- **Manual Overrides:** Buttons to force different modes

---

## Testing & Verification

### Check the logs:
```bash
docker-compose logs -f optimizer
```

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
- Verify `HA_URL` in `.env` is correct
- Check firewall isn't blocking port 8123

### "Entity not found" errors in logs
- Go to Home Assistant **Developer Tools → States**
- Search for your sensor (e.g., `sigen_plant_pv_power`)
- Copy the exact entity ID to `.env`
- Restart: `docker-compose restart`

### Dashboard shows nothing / blank page
- Wait 30 seconds (first startup takes time)
- Check logs: `docker-compose logs -f`
- Clear browser cache (Ctrl+Shift+Del)
- Verify URL is correct: `http://your-ip:7123`

### Optimizer stops working
- Check logs: `docker-compose logs -f`
- Verify `.env` hasn't been corrupted
- Restart: `docker-compose restart`
- If still stuck, restart everything: `docker-compose down && docker-compose up -d`

---

## Configuration Tuning

Once it's running, you can adjust behavior either from the web GUI (Apply & Save Thresholds writes to `.env`) or by editing environment variables in `.env` directly:

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

After changing `.env`, restart: `docker-compose restart`

---

## Stopping & Uninstalling

### Stop temporarily:
```bash
docker-compose stop
```

### Stop and remove everything:
```bash
docker-compose down
# Type 'y' to confirm
```

### Re-enable old blueprint automations:
Go back to Home Assistant and re-enable the automations you disabled in Step 1.

---

## Support & Troubleshooting

### View detailed logs:
```bash
docker-compose logs -f optimizer
```

### Monitor in real-time:
Dashboard is always at: `http://your-machine:7123`

### Check Home Assistant integration:
All automations are logged in Home Assistant **Settings → System → Logs**

---

## How It Works — The Short Version

Each cycle (every 30 seconds by default):

1. **Read state:** Battery %, solar power, current prices
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
3. If you want to tweak, adjust the price thresholds in `.env` and restart
4. Check logs monthly to ensure it's still running smoothly

---

**Questions?** Check the logs first — most issues are explained there.

**Version:** 2.1.1 (March 2026)
