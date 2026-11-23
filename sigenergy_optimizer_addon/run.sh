#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/app"
DATA_DIR="/data"
OPTIONS_FILE="/data/options.json"
ENV_FILE="/data/.env"

mkdir -p "${DATA_DIR}"
haos_managed_settings=$(python3 <<'PY'
from __future__ import annotations

import json
import re
from io import StringIO
from pathlib import Path

from dotenv.parser import parse_stream

from app.settings_persistence import write_settings_atomically

options_path = Path("/data/options.json")
env_path = Path("/data/.env")

options = {}
if options_path.exists():
    options = json.loads(options_path.read_text(encoding="utf-8"))

existing_or_template = env_path if env_path.exists() else Path("/app/.env.example")
contents = existing_or_template.read_text(encoding="utf-8")

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

managed_keys: set[str] = set()
extra_env = str(options.get("extra_env", ""))
for raw_line in extra_env.splitlines():
    line = raw_line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    key = key.strip().upper()
    if re.fullmatch(r"[A-Z0-9_]+", key):
        updates[key] = value.strip()
        managed_keys.add(key)

remaining = set(updates)
out: list[str] = []
managed_by_lowercase = {key.lower(): key for key in managed_keys}
for binding in parse_stream(StringIO(contents)):
    # Match dotenv assignments, including quoted keys and export directives.
    # A matching line inside another setting's multiline value is not an assignment.
    env_key = managed_by_lowercase.get(binding.key.lower()) if binding.key else None
    lines = binding.original.string.splitlines()
    if env_key is not None:
        for line in lines:
            if line.strip():
                break
            out.append(line)
        out.append(f"{env_key}={updates[env_key]}")
        remaining.discard(env_key)
        continue

    # Keep direct add-on option matching as before.
    for line in lines:
        lhs, separator, _ = line.partition("=")
        env_key = lhs.strip()
        if separator and env_key in updates and env_key not in managed_keys:
            out.append(f"{env_key}={updates[env_key]}")
            remaining.discard(env_key)
        else:
            out.append(line)

for env_key in sorted(remaining):
    out.append(f"{env_key}={updates[env_key]}")

write_settings_atomically(env_path, "\n".join(out).rstrip() + "\n")
print(",".join(sorted(managed_keys)))
PY
)
export SIGENERGY_HAOS_MANAGED_SETTINGS="${haos_managed_settings}"

ln -sf "${ENV_FILE}" "${APP_DIR}/.env"

exec uvicorn app.main:app --host 0.0.0.0 --port 7123 --workers 1 --no-proxy-headers
