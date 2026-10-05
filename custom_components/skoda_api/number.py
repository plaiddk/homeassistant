"""Number entities for the Škoda Public API integration."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SkodaConfigEntry, SkodaCoordinator, ensure_path, get_path
from .entity import SkodaEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SkodaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    # Not gated on 'operations': that list is transient and dropped the entity at startup.
    if get_path(coordinator.data, "charging.settings.targetStateOfChargeInPercent") is not None:
        async_add_entities([SkodaChargeLimit(coordinator)])


class SkodaChargeLimit(SkodaEntity, NumberEntity):
    _attr_icon = "mdi:battery-charging-80"
    _attr_native_unit_of_measurement = PERCENTAGE
    # Vehicles accept 50-100 in steps of 10.
    _attr_native_min_value = 50
    _attr_native_max_value = 100
    _attr_native_step = 10
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator: SkodaCoordinator) -> None:
        super().__init__(coordinator, "charge_limit")

    @property
    def native_value(self) -> float | None:
        return self.data_at("charging.settings.targetStateOfChargeInPercent")

    async def async_set_native_value(self, value: float) -> None:
        percent = int(value)
        await self.coordinator.async_command(
            self.coordinator.client.set_charging_limit(percent),
            lambda d: ensure_path(d, "charging.settings").__setitem__("targetStateOfChargeInPercent", percent),
        )
