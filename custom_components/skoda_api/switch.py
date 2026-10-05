"""Switches for the Škoda Public API integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SkodaConfigEntry, SkodaCoordinator, charging_state, ensure_path
from .entity import SkodaEntity

VENTILATION_ACTIVE = ("PREHEATING", "VENTILATION")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SkodaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    data = coordinator.data or {}
    entities: list[SwitchEntity] = []
    if "charging" in data and coordinator.supports("startCharging"):
        entities.append(SkodaChargingSwitch(coordinator))
    if "activeVentilation" in data and coordinator.supports("startActiveVentilation"):
        entities.append(SkodaVentilationSwitch(coordinator))
    async_add_entities(entities)


class SkodaChargingSwitch(SkodaEntity, SwitchEntity):
    _attr_icon = "mdi:ev-station"

    def __init__(self, coordinator: SkodaCoordinator) -> None:
        super().__init__(coordinator, "charging_switch")

    @property
    def is_on(self) -> bool | None:
        state = charging_state(self.coordinator.data)
        return None if state is None else state == "CHARGING"

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_command(
            self.coordinator.client.start_charging(),
            lambda d: ensure_path(d, "charging.status").__setitem__("state", "CHARGING"),
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_command(
            self.coordinator.client.stop_charging(),
            lambda d: ensure_path(d, "charging.status").__setitem__("state", "READY_FOR_CHARGING"),
        )


class SkodaVentilationSwitch(SkodaEntity, SwitchEntity):
    _attr_icon = "mdi:fan"

    def __init__(self, coordinator: SkodaCoordinator) -> None:
        super().__init__(coordinator, "active_ventilation")

    @property
    def is_on(self) -> bool | None:
        state = self.data_at("activeVentilation.state")
        if state in (None, "UNKNOWN", "UNSUPPORTED"):
            return None
        return state in VENTILATION_ACTIVE

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_command(
            self.coordinator.client.start_active_ventilation(),
            lambda d: ensure_path(d, "activeVentilation").__setitem__("state", "VENTILATION"),
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_command(
            self.coordinator.client.stop_active_ventilation(),
            lambda d: ensure_path(d, "activeVentilation").__setitem__("state", "OFF"),
        )
