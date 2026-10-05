"""Binary sensors for the Škoda Public API integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SkodaConfigEntry, SkodaCoordinator, charging_state, get_path
from .entity import SkodaEntity


def _is(path: str, on: str, off: str | tuple[str, ...]) -> Callable[[dict | None], bool | None]:
    """Map an API string to on/off; anything else (UNKNOWN, missing) is unknown."""
    offs = (off,) if isinstance(off, str) else off

    def _get(data: dict | None) -> bool | None:
        raw = get_path(data, path)
        if raw == on:
            return True
        if raw in offs:
            return False
        return None

    return _get


def _window_heating(data: dict | None) -> bool | None:
    states = (get_path(data, "airConditioning.windowHeating.front"), get_path(data, "airConditioning.windowHeating.rear"))
    if "ON" in states:
        return True
    if "OFF" in states:
        return False
    return None


@dataclass(frozen=True, kw_only=True)
class SkodaBinarySensorDescription(BinarySensorEntityDescription):
    is_on_fn: Callable[[dict | None], bool | None]
    requires: str
    # Skip the entity when the vehicle reports this value at setup (e.g. UNSUPPORTED).
    unsupported_path: str | None = None
    # Skip the entity when this value is absent at setup.
    present_path: str | None = None


BINARY_SENSORS: tuple[SkodaBinarySensorDescription, ...] = (
    # Lock device class: on means unlocked.
    SkodaBinarySensorDescription(
        key="locked",
        requires="status",
        device_class=BinarySensorDeviceClass.LOCK,
        is_on_fn=_is("status.overall.locked", "NO", "YES"),
    ),
    SkodaBinarySensorDescription(
        key="doors",
        requires="status",
        device_class=BinarySensorDeviceClass.DOOR,
        is_on_fn=_is("status.overall.doors", "OPEN", "CLOSED"),
    ),
    SkodaBinarySensorDescription(
        key="windows",
        requires="status",
        device_class=BinarySensorDeviceClass.WINDOW,
        is_on_fn=_is("status.overall.windows", "OPEN", "CLOSED"),
        unsupported_path="status.overall.windows",
    ),
    SkodaBinarySensorDescription(
        key="lights",
        requires="status",
        device_class=BinarySensorDeviceClass.LIGHT,
        is_on_fn=_is("status.overall.lights", "ON", "OFF"),
    ),
    SkodaBinarySensorDescription(
        key="trunk",
        requires="status",
        device_class=BinarySensorDeviceClass.OPENING,
        is_on_fn=_is("status.detail.trunk", "OPEN", "CLOSED"),
    ),
    SkodaBinarySensorDescription(
        key="bonnet",
        requires="status",
        device_class=BinarySensorDeviceClass.OPENING,
        is_on_fn=_is("status.detail.bonnet", "OPEN", "CLOSED"),
    ),
    SkodaBinarySensorDescription(
        key="sunroof",
        requires="status",
        device_class=BinarySensorDeviceClass.WINDOW,
        is_on_fn=_is("status.detail.sunroof", "OPEN", "CLOSED"),
        unsupported_path="status.detail.sunroof",
    ),
    SkodaBinarySensorDescription(
        key="charger_connected",
        requires="charging",
        device_class=BinarySensorDeviceClass.PLUG,
        is_on_fn=_is("charging.status.plugConnectionState", "CONNECTED", "DISCONNECTED"),
    ),
    SkodaBinarySensorDescription(
        key="charger_locked",
        requires="charging",
        device_class=BinarySensorDeviceClass.LOCK,
        is_on_fn=_is("charging.status.plugLockState", "UNLOCKED", "LOCKED"),
    ),
    SkodaBinarySensorDescription(
        key="charging",
        requires="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        is_on_fn=lambda d: None if (s := charging_state(d)) is None else s == "CHARGING",
    ),
    SkodaBinarySensorDescription(
        key="in_saved_location",
        requires="charging",
        device_class=BinarySensorDeviceClass.PRESENCE,
        is_on_fn=lambda d: get_path(d, "charging.isVehicleInSavedLocation"),
    ),
    SkodaBinarySensorDescription(
        key="moving",
        requires="parkingPosition",
        device_class=BinarySensorDeviceClass.MOVING,
        is_on_fn=_is("parkingPosition.state", "IN_MOTION", "PARKED"),
    ),
    SkodaBinarySensorDescription(
        key="window_heating",
        requires="airConditioning",
        icon="mdi:car-defrost-front",
        is_on_fn=_window_heating,
        present_path="airConditioning.windowHeating",
    ),
    # Settings below can only be changed in the MyŠkoda app.
    SkodaBinarySensorDescription(
        key="window_heating_with_ac",
        requires="airConditioning",
        icon="mdi:car-defrost-rear",
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda d: get_path(d, "airConditioning.windowHeating.enabled"),
        present_path="airConditioning.windowHeating.enabled",
    ),
    SkodaBinarySensorDescription(
        key="ac_at_unlock",
        requires="airConditioning",
        icon="mdi:car-key",
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda d: get_path(d, "airConditioning.airConditioningAtUnlock"),
        present_path="airConditioning.airConditioningAtUnlock",
    ),
    SkodaBinarySensorDescription(
        key="battery_care_mode",
        requires="charging",
        icon="mdi:battery-heart-variant",
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=_is("charging.settings.chargingCareMode", "ACTIVATED", "DEACTIVATED"),
        present_path="charging.settings.chargingCareMode",
    ),
    SkodaBinarySensorDescription(
        key="reduced_charge_current",
        requires="charging",
        icon="mdi:current-ac",
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=_is("charging.settings.maxChargeCurrentAc", "REDUCED", "MAXIMUM"),
        present_path="charging.settings.maxChargeCurrentAc",
    ),
    SkodaBinarySensorDescription(
        key="auto_unlock_plug",
        requires="charging",
        icon="mdi:ev-plug-type2",
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=_is("charging.settings.autoUnlockPlugWhenCharged", "PERMANENT", "OFF"),
        present_path="charging.settings.autoUnlockPlugWhenCharged",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SkodaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    data = coordinator.data or {}
    async_add_entities(
        SkodaBinarySensor(coordinator, desc)
        for desc in BINARY_SENSORS
        if desc.requires in data
        and not (desc.unsupported_path and get_path(data, desc.unsupported_path) == "UNSUPPORTED")
        and not (desc.present_path and get_path(data, desc.present_path) is None)
    )


class SkodaBinarySensor(SkodaEntity, BinarySensorEntity):
    entity_description: SkodaBinarySensorDescription

    def __init__(self, coordinator: SkodaCoordinator, description: SkodaBinarySensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.is_on_fn(self.coordinator.data)
