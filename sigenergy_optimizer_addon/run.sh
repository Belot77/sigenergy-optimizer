#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/app"
DATA_DIR="/data"
OPTIONS_FILE="/data/options.json"
ENV_FILE="/data/.env"

mkdir -p "${DATA_DIR}"
if [ ! -f "${ENV_FILE}" ]; then
  cp "${APP_DIR}/.env.example" "${ENV_FILE}"
fi

python3 <<'PY'
from __future__ import annotations

import json
import re
from pathlib import Path

options_path = Path("/data/options.json")
env_path = Path("/data/.env")

options = {}
if options_path.exists():
    options = json.loads(options_path.read_text(encoding="utf-8"))

lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []

updates: dict[str, str] = {}


def put(key: str, value: object) -> None:
    if value is None:
        return
    raw = str(value).strip()
    if not raw:
        return
    updates[key] = raw


put("HA_URL", options.get("ha_url"))
put("HA_TOKEN", options.get("ha_token"))
put("UI_API_KEY", options.get("ui_api_key"))

extra_env = str(options.get("extra_env", ""))
for raw_line in extra_env.splitlines():
    line = raw_line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    key = key.strip().upper()
    if re.fullmatch(r"[A-Z0-9_]+", key):
        updates[key] = value.strip()

remaining = set(updates)
out: list[str] = []
for line in lines:
    replaced = False
    for env_key, env_val in updates.items():
        if re.match(rf"^\s*{re.escape(env_key)}\s*=", line):
            out.append(f"{env_key}={env_val}")
            remaining.discard(env_key)
            replaced = True
            break
    if not replaced:
        out.append(line)

for env_key in sorted(remaining):
    out.append(f"{env_key}={updates[env_key]}")

env_path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
PY

ln -sf "${ENV_FILE}" "${APP_DIR}/.env"

exec uvicorn app.main:app --host 0.0.0.0 --port 7123 --workers 1
