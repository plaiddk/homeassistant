"""Device tracker for the Škoda Public API integration."""

from __future__ import annotations

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SkodaConfigEntry, SkodaCoordinator
from .entity import SkodaEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SkodaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    if "parkingPosition" in (coordinator.data or {}):
        async_add_entities([SkodaTracker(coordinator)])


class SkodaTracker(SkodaEntity, TrackerEntity):
    _attr_icon = "mdi:car"

    def __init__(self, coordinator: SkodaCoordinator) -> None:
        super().__init__(coordinator, "location")

    @property
    def source_type(self) -> SourceType:
        return SourceType.GPS

    @property
    def latitude(self) -> float | None:
        return self.data_at("parkingPosition.gpsCoordinates.latitude")

    @property
    def longitude(self) -> float | None:
        return self.data_at("parkingPosition.gpsCoordinates.longitude")

    @property
    def location_accuracy(self) -> float:
        return 0
