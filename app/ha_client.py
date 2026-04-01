"""
Home Assistant client — wraps the REST API for state reads and service calls.
Uses httpx for async HTTP.
"""
from __future__ import annotations
import logging
from datetime import datetime
from typing import Any
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

UNAVAILABLE = {"unknown", "unavailable", "none", ""}


class HAClient:
    def __init__(self, base_url: str, token: str) -> None:
        self._base = base_url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        self._client = httpx.AsyncClient(
            base_url=self._base,
            headers=self._headers,
            timeout=15.0,
        )

    async def close(self) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------
    # State reads
    # ------------------------------------------------------------------

    async def get_state(self, entity_id: str) -> dict[str, Any] | None:
        """Return the full state object for entity_id, or None on error."""
        try:
            r = await self._client.get(f"/api/states/{entity_id}")
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            logger.debug("get_state(%s) failed: %s", entity_id, exc)
            return None

    async def get_state_value(self, entity_id: str, default: Any = None) -> Any:
        """Return just the state string, or default if unavailable."""
        obj = await self.get_state(entity_id)
        if obj is None:
            return default
        val = obj.get("state", "")
        if val in UNAVAILABLE:
            return default
        return val

    async def get_float(self, entity_id: str, default: float = 0.0) -> float:
        val = await self.get_state_value(entity_id)
        try:
            return float(val)
        except (TypeError, ValueError):
            return default

    async def get_bool(self, entity_id: str) -> bool:
        val = await self.get_state_value(entity_id, "off")
        return str(val).lower() in ("on", "true", "1")

    async def get_attr(self, entity_id: str, attribute: str, default: Any = None) -> Any:
        obj = await self.get_state(entity_id)
        if obj is None:
            return default
        return obj.get("attributes", {}).get(attribute, default)

    async def get_unit(self, entity_id: str) -> str:
        return (await self.get_attr(entity_id, "unit_of_measurement") or "").lower()

    async def bulk_states(self, entity_ids: list[str]) -> dict[str, dict]:
        """Fetch all states in one call and filter to the ones we need."""
        try:
            r = await self._client.get("/api/states")
            r.raise_for_status()
            all_states: list[dict] = r.json()
            return {s["entity_id"]: s for s in all_states if s["entity_id"] in entity_ids}
        except Exception as exc:
            logger.warning("bulk_states failed: %s", exc)
            return {}

    async def search_entities(
        self,
        query: str = "",
        limit: int = 200,
        domains: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Return HA entities for UI type-ahead selection."""
        try:
            q = str(query or "").strip().lower()
            limit = max(1, min(int(limit), 1000))
            domain_set = {str(d).strip().lower() for d in (domains or []) if str(d).strip()}
            r = await self._client.get("/api/states")
            r.raise_for_status()
            all_states: list[dict[str, Any]] = r.json()

            rows: list[dict[str, Any]] = []
            for item in all_states:
                entity_id = str(item.get("entity_id", ""))
                domain = entity_id.split(".", 1)[0].lower() if "." in entity_id else ""
                if domain_set and domain not in domain_set:
                    continue
                attrs = item.get("attributes", {}) or {}
                friendly_name = str(attrs.get("friendly_name", ""))
                if q and (q not in entity_id.lower() and q not in friendly_name.lower()):
                    continue
                rows.append(
                    {
                        "entity_id": entity_id,
                        "friendly_name": friendly_name,
                        "domain": domain,
                    }
                )
                if len(rows) >= limit:
                    break
            return rows
        except Exception as exc:
            logger.warning("search_entities failed: %s", exc)
            return []

    async def get_history_period(
        self,
        start_time: datetime,
        end_time: datetime | None = None,
        entity_ids: list[str] | None = None,
    ) -> list[Any]:
        """Return recorder history for the requested entity IDs over a period."""
        try:
            path = f"/api/history/period/{quote(start_time.isoformat())}"
            params: dict[str, str] = {}
            if end_time is not None:
                params["end_time"] = end_time.isoformat()
            if entity_ids:
                params["filter_entity_id"] = ",".join(entity_ids)
            r = await self._client.get(path, params=params)
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            logger.warning("get_history_period failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Service calls
    # ------------------------------------------------------------------

    async def call_service(self, domain: str, service: str, data: dict[str, Any]) -> bool:
        try:
            r = await self._client.post(f"/api/services/{domain}/{service}", json=data)
            r.raise_for_status()
            return True
        except Exception as exc:
            logger.error("call_service %s.%s failed: %s", domain, service, exc)
            return False

    async def set_number(self, entity_id: str, value: float) -> bool:
        return await self.call_service("number", "set_value", {"entity_id": entity_id, "value": round(value, 2)})

    async def select_option(self, entity_id: str, option: str) -> bool:
        return await self.call_service("select", "select_option", {"entity_id": entity_id, "option": option})

    async def turn_on(self, entity_id: str) -> bool:
        domain = entity_id.split(".")[0]
        return await self.call_service(domain, "turn_on", {"entity_id": entity_id})

    async def turn_off(self, entity_id: str) -> bool:
        domain = entity_id.split(".")[0]
        return await self.call_service(domain, "turn_off", {"entity_id": entity_id})

    async def set_input_text(self, entity_id: str, value: str) -> bool:
        return await self.call_service("input_text", "set_value", {"entity_id": entity_id, "value": value[:255]})

    async def set_input_number(self, entity_id: str, value: float) -> bool:
        return await self.call_service("input_number", "set_value", {"entity_id": entity_id, "value": round(value, 3)})

    async def send_notification(self, service: str, title: str, message: str) -> bool:
        if not service:
            return False
        # service looks like "notify.mobile_app_pixel" → domain=notify, svc=mobile_app_pixel
        parts = service.split(".", 1)
        if len(parts) != 2:
            return False
        domain, svc = parts
        return await self.call_service(domain, svc, {"title": title, "message": message})

    async def logbook_log(self, name: str, message: str, entity_id: str = "") -> bool:
        data: dict = {"name": name, "message": message}
        if entity_id:
            data["entity_id"] = entity_id
        return await self.call_service("logbook", "log", data)

    async def enable_automation(self, entity_id: str) -> bool:
        return await self.call_service("automation", "turn_on", {"entity_id": entity_id})

    async def disable_automation(self, entity_id: str) -> bool:
        return await self.call_service("automation", "turn_off", {"entity_id": entity_id})

    # ------------------------------------------------------------------
    # Connectivity check
    # ------------------------------------------------------------------

    async def ping(self) -> bool:
        try:
            r = await self._client.get("/api/")
            return r.status_code == 200
        except Exception:
            return False
