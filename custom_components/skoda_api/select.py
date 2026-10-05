"""Select entities for the Škoda Public API integration."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SkodaConfigEntry, SkodaCoordinator, ensure_path
from .entity import SkodaEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SkodaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    if "charging" in (coordinator.data or {}) and coordinator.supports("setChargeMode"):
        async_add_entities([SkodaChargeModeSelect(coordinator)])


class SkodaChargeModeSelect(SkodaEntity, SelectEntity):
    _attr_icon = "mdi:ev-plug-type2"

    def __init__(self, coordinator: SkodaCoordinator) -> None:
        super().__init__(coordinator, "charge_mode")

    @property
    def options(self) -> list[str]:
        modes = list(self.data_at("charging.settings.availableChargeModes") or [])
        current = self.current_option
        if current and current not in modes:
            modes.append(current)
        return modes

    @property
    def current_option(self) -> str | None:
        return self.data_at("charging.settings.preferredChargeMode")

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_command(
            self.coordinator.client.set_charge_mode(option),
            lambda d: ensure_path(d, "charging.settings").__setitem__("preferredChargeMode", option),
        )
