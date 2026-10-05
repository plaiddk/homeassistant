"""Minimal async client for the MyŠkoda Public API."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any

import aiohttp

from .const import BASE_URL

_LOGGER = logging.getLogger(__name__)

PROBLEM_KEY_EXPIRED = "api-key-expired"
PROBLEM_KEY_NOT_AUTHORIZED = "api-key-not-authorized"
PROBLEM_VEHICLE_BUSY = "vehicle-not-accepting-requests"


class SkodaApiError(Exception):
    """Generic API error."""

    def __init__(self, status: int, problem: str | None = None, detail: str | None = None) -> None:
        self.status = status
        self.problem = problem
        self.detail = detail
        super().__init__(f"{status} {problem or ''} {detail or ''}".strip())


class SkodaAuthError(SkodaApiError):
    """API key expired or not authorized (401/403 on key)."""


class SkodaRateLimitError(SkodaApiError):
    """Rate limit exceeded or vehicle declined (429)."""

    def __init__(self, status: int, problem: str | None, detail: str | None, retry_after: int | None) -> None:
        super().__init__(status, problem, detail)
        self.retry_after = retry_after


@dataclass
class ApiMeta:
    """Metadata from response headers."""

    key_expires_at: datetime | None = None
    rate_limit: int | None = None
    rate_remaining: int | None = None
    rate_reset: int | None = None


def _int_header(headers: Any, name: str) -> int | None:
    try:
        return int(headers[name])
    except (KeyError, ValueError, TypeError):
        return None


class SkodaApiClient:
    """Client for a single vehicle."""

    def __init__(self, session: aiohttp.ClientSession, api_key: str, vin: str) -> None:
        self._session = session
        self._api_key = api_key
        self.vin = vin
        self.meta = ApiMeta()

    async def _request(self, method: str, path: str, json: dict | None = None, params: dict | None = None) -> Any:
        url = f"{BASE_URL}/api/v1/vehicles/{self.vin}{path}"
        headers = {"X-API-Key": self._api_key, "Accept": "application/json"}
        async with self._session.request(
            method, url, headers=headers, json=json, params=params, timeout=aiohttp.ClientTimeout(total=60)
        ) as resp:
            self._update_meta(resp.headers)
            if resp.status < 400:
                if resp.status == 200 and resp.content_type == "application/json":
                    return await resp.json()
                return None

            problem = detail = None
            try:
                body = await resp.json(content_type=None)
                problem = str(body.get("type", "")).rsplit("/", 1)[-1] or None
                detail = body.get("detail")
            except (aiohttp.ContentTypeError, ValueError, AttributeError):
                pass

            if resp.status == 401 or (resp.status == 403 and problem == PROBLEM_KEY_NOT_AUTHORIZED):
                raise SkodaAuthError(resp.status, problem, detail)
            if resp.status == 429:
                raise SkodaRateLimitError(resp.status, problem, detail, _int_header(resp.headers, "Retry-After"))
            raise SkodaApiError(resp.status, problem, detail)

    def _update_meta(self, headers: Any) -> None:
        if (expires := headers.get("X-API-Key-Expires-At")) is not None:
            try:
                self.meta.key_expires_at = datetime.fromisoformat(expires.replace("Z", "+00:00"))
            except ValueError:
                _LOGGER.debug("Unparseable X-API-Key-Expires-At: %s", expires)
        if (limit := _int_header(headers, "RateLimit-Limit")) is not None:
            self.meta.rate_limit = limit
        if (remaining := _int_header(headers, "RateLimit-Remaining")) is not None:
            self.meta.rate_remaining = remaining
        if (reset := _int_header(headers, "RateLimit-Reset")) is not None:
            self.meta.rate_reset = reset

    async def get_vehicle(self) -> dict[str, Any]:
        """Return the full vehicle response ({'vehicle': ..., 'errors': [...]})."""
        return await self._request("GET", "")

    async def start_charging(self) -> None:
        await self._request("POST", "/charging/start")

    async def stop_charging(self) -> None:
        await self._request("POST", "/charging/stop")

    async def set_charging_limit(self, percent: int) -> None:
        await self._request("PUT", "/charging/limit", json={"targetStateOfChargeInPercent": percent})

    async def set_charge_mode(self, mode: str) -> None:
        await self._request("PUT", "/charging/mode", json={"chargeMode": mode})

    async def start_air_conditioning(self, temperature: float | None, without_external_power: bool | None = None) -> None:
        body: dict[str, Any] = {}
        if temperature is not None:
            body["targetTemperature"] = {"value": temperature, "unit": "CELSIUS"}
        if without_external_power is not None:
            body["airConditioningWithoutExternalPower"] = without_external_power
        await self._request("POST", "/air-conditioning/start", json=body)

    async def stop_air_conditioning(self) -> None:
        await self._request("POST", "/air-conditioning/stop")

    async def start_active_ventilation(self) -> None:
        await self._request("POST", "/active-ventilation/start")

    async def stop_active_ventilation(self) -> None:
        await self._request("POST", "/active-ventilation/stop")
