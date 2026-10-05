"""The Škoda Public API integration."""

from __future__ import annotations

from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SkodaApiClient
from .const import CONF_SCAN_INTERVAL_MIN, CONF_VIN, DEFAULT_SCAN_INTERVAL_MIN, PLATFORMS
from .coordinator import SkodaConfigEntry, SkodaCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: SkodaConfigEntry) -> bool:
    client = SkodaApiClient(async_get_clientsession(hass), entry.data[CONF_API_KEY], entry.data[CONF_VIN])
    interval = entry.options.get(CONF_SCAN_INTERVAL_MIN, DEFAULT_SCAN_INTERVAL_MIN)
    coordinator = SkodaCoordinator(hass, entry, client, interval)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SkodaConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload(hass: HomeAssistant, entry: SkodaConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
