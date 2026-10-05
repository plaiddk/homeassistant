"""Data update coordinator for the Škoda Public API."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import timedelta
import logging
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SkodaApiClient, SkodaApiError, SkodaAuthError, SkodaRateLimitError
from .const import COMMAND_REFRESH_DELAY, DOMAIN

_LOGGER = logging.getLogger(__name__)

type SkodaConfigEntry = ConfigEntry[SkodaCoordinator]


class SkodaCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls the vehicle endpoint."""

    config_entry: SkodaConfigEntry

    def __init__(self, hass: HomeAssistant, entry: SkodaConfigEntry, client: SkodaApiClient, interval_min: int) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{client.vin}",
            update_interval=timedelta(minutes=interval_min),
        )
        self.client = client
        self.errors: list[dict[str, Any]] = []
        self._cancel_delayed_refresh: Callable[[], None] | None = None

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            resp = await self.client.get_vehicle()
        except SkodaAuthError as err:
            raise ConfigEntryAuthFailed(f"API key rejected: {err.problem or err.status}") from err
        except SkodaRateLimitError as err:
            if self.data is not None:
                _LOGGER.warning("Rate limited (retry after %ss); keeping last known state", err.retry_after)
                return self.data
            raise UpdateFailed(f"Rate limited, retry after {err.retry_after}s") from err
        except SkodaApiError as err:
            raise UpdateFailed(f"API error: {err}") from err
        except (aiohttp.ClientError, TimeoutError) as err:
            raise UpdateFailed(f"Connection error: {err}") from err

        self.errors = resp.get("errors") or []
        return resp["vehicle"]

    async def async_command(
        self,
        command: Awaitable[None],
        optimistic: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        """Run a remote command, apply an optimistic update and schedule a refresh."""
        try:
            await command
        except SkodaAuthError as err:
            self.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(f"API key rejected: {err.problem or err.status}") from err
        except SkodaRateLimitError as err:
            raise HomeAssistantError(
                f"Request declined ({err.problem or 'rate limit'}), retry after {err.retry_after}s"
            ) from err
        except SkodaApiError as err:
            raise HomeAssistantError(f"Command failed: {err.detail or err}") from err
        except (aiohttp.ClientError, TimeoutError) as err:
            raise HomeAssistantError(f"Connection error: {err}") from err

        if optimistic is not None and self.data is not None:
            optimistic(self.data)
            self.async_update_listeners()
        self._schedule_refresh_after_command()

    @callback
    def _schedule_refresh_after_command(self) -> None:
        if self._cancel_delayed_refresh is not None:
            self._cancel_delayed_refresh()

        @callback
        def _refresh(_now: Any) -> None:
            self._cancel_delayed_refresh = None
            self.hass.async_create_task(self.async_request_refresh())

        self._cancel_delayed_refresh = async_call_later(self.hass, COMMAND_REFRESH_DELAY, _refresh)

    async def async_shutdown(self) -> None:
        if self._cancel_delayed_refresh is not None:
            self._cancel_delayed_refresh()
            self._cancel_delayed_refresh = None
        await super().async_shutdown()

    def supports(self, operation: str) -> bool:
        """Return True if the vehicle lists the operation (or operations are unknown)."""
        ops = (self.data or {}).get("operations")
        if ops is None:
            return True
        return any(op.get("name") == operation for op in ops)


def get_path(data: dict[str, Any] | None, path: str) -> Any:
    """Read a dotted path like 'charging.status.battery.stateOfChargeInPercent'."""
    cur: Any = data
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def charging_state(data: dict[str, Any] | None) -> str | None:
    """Return charging.status.state, derived from plug and power when the API omits it."""
    state = get_path(data, "charging.status.state")
    if state is not None:
        return state
    plug = get_path(data, "charging.status.plugConnectionState")
    if plug == "DISCONNECTED":
        return "CONNECT_CABLE"
    power = get_path(data, "charging.status.chargePowerInKw")
    if plug != "CONNECTED" or not isinstance(power, (int, float)):
        return None
    return "CHARGING" if power > 0 else "READY_FOR_CHARGING"


def ensure_path(data: dict[str, Any], path: str) -> dict[str, Any]:
    """Return the dict at a dotted path, creating intermediate dicts."""
    cur = data
    for part in path.split("."):
        cur = cur.setdefault(part, {})
    return cur
