"""Base entity for the Škoda Public API integration."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SkodaCoordinator, get_path


class SkodaEntity(CoordinatorEntity[SkodaCoordinator]):
    """Entity bound to a single vehicle."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SkodaCoordinator, key: str) -> None:
        super().__init__(coordinator)
        vin = coordinator.client.vin
        self._attr_unique_id = f"{vin}_{key}"
        self._attr_translation_key = key
        data = coordinator.data or {}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, vin)},
            manufacturer="Škoda",
            name=data.get("name") or f"Škoda {vin[-6:]}",
            serial_number=vin,
        )

    def data_at(self, path: str) -> Any:
        return get_path(self.coordinator.data, path)
