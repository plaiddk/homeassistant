"""Sensors for the Škoda Public API integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfLength,
    UnitOfPower,
    UnitOfSpeed,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import SkodaConfigEntry, SkodaCoordinator, charging_state, get_path
from .entity import SkodaEntity


def _ts(path: str) -> Callable[[SkodaCoordinator], Any]:
    def _get(c: SkodaCoordinator) -> datetime | None:
        raw = get_path(c.data, path)
        return dt_util.parse_datetime(raw) if isinstance(raw, str) else None

    return _get


def _val(path: str) -> Callable[[SkodaCoordinator], Any]:
    return lambda c: get_path(c.data, path)


def _enum(path: str, options: list[str]) -> Callable[[SkodaCoordinator], Any]:
    # Unrecognised API values become unknown instead of breaking the enum sensor.
    def _get(c: SkodaCoordinator) -> str | None:
        raw = get_path(c.data, path)
        value = raw.lower() if isinstance(raw, str) else None
        return value if value in options else None

    return _get


def _charging_state(c: SkodaCoordinator) -> str | None:
    state = charging_state(c.data)
    value = state.lower() if isinstance(state, str) else None
    return value if value in CHARGING_STATES else None


def _fully_charged_at(c: SkodaCoordinator) -> datetime | None:
    # The API repeats the capture time here when not charging.
    if charging_state(c.data) != "CHARGING":
        return None
    return _ts("charging.status.fullyChargedAt")(c)


CHARGING_STATES = [
    "connect_cable",
    "charging",
    "conserving",
    "ready_for_charging",
    "discharging",
    "charging_interrupted",
]
CHARGE_TYPES = ["ac", "dc", "off"]
AIR_CONDITIONING_STATES = ["off", "cooling", "heating", "heating_auxiliary", "ventilation", "completed"]


@dataclass(frozen=True, kw_only=True)
class SkodaSensorDescription(SensorEntityDescription):
    value_fn: Callable[[SkodaCoordinator], Any]
    # Top-level part of the vehicle data that must be present for the entity to be created.
    requires: str | None = None


SENSORS: tuple[SkodaSensorDescription, ...] = (
    SkodaSensorDescription(
        key="battery_level",
        requires="charging",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_val("charging.status.battery.stateOfChargeInPercent"),
    ),
    SkodaSensorDescription(
        key="electric_range",
        requires="charging",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        suggested_unit_of_measurement=UnitOfLength.KILOMETERS,
        suggested_display_precision=0,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_val("charging.status.battery.remainingCruisingRangeInMeters"),
    ),
    SkodaSensorDescription(
        key="charging_state",
        requires="charging",
        icon="mdi:ev-station",
        device_class=SensorDeviceClass.ENUM,
        options=CHARGING_STATES,
        value_fn=_charging_state,
    ),
    SkodaSensorDescription(
        key="charge_type",
        requires="charging",
        icon="mdi:current-ac",
        device_class=SensorDeviceClass.ENUM,
        options=CHARGE_TYPES,
        value_fn=_enum("charging.status.chargeType", CHARGE_TYPES),
    ),
    SkodaSensorDescription(
        key="charging_power",
        requires="charging",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_val("charging.status.chargePowerInKw"),
    ),
    SkodaSensorDescription(
        key="charging_rate",
        requires="charging",
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        suggested_display_precision=0,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_val("charging.status.chargingRateInKilometersPerHour"),
    ),
    SkodaSensorDescription(
        key="remaining_charging_time",
        requires="charging",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=_val("charging.status.remainingTimeToFullyChargedInMinutes"),
    ),
    SkodaSensorDescription(
        key="fully_charged_at",
        requires="charging",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_fully_charged_at,
    ),
    SkodaSensorDescription(
        key="target_battery_level",
        requires="charging",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:battery-arrow-up",
        value_fn=_val("charging.settings.targetStateOfChargeInPercent"),
    ),
    SkodaSensorDescription(
        key="mileage",
        requires="odometer",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_val("odometer.mileageInKm"),
    ),
    SkodaSensorDescription(
        key="total_range",
        requires="fuelStatus",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_val("fuelStatus.totalRangeInKm"),
    ),
    SkodaSensorDescription(
        key="fuel_level",
        requires="fuelStatus",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:gas-station",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_val("fuelStatus.primaryEngineRange.currentFuelLevelInPercent"),
    ),
    SkodaSensorDescription(
        key="air_conditioning_state",
        requires="airConditioning",
        icon="mdi:air-conditioner",
        device_class=SensorDeviceClass.ENUM,
        options=AIR_CONDITIONING_STATES,
        value_fn=_enum("airConditioning.state", AIR_CONDITIONING_STATES),
    ),
    SkodaSensorDescription(
        key="target_temperature_reached_at",
        requires="airConditioning",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_ts("airConditioning.estimatedReachOfTargetTemperatureAt"),
    ),
    SkodaSensorDescription(
        key="parking_address",
        requires="parkingPosition",
        icon="mdi:map-marker",
        value_fn=_val("parkingPosition.formattedAddress"),
    ),
    SkodaSensorDescription(
        key="last_updated",
        requires="status",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_ts("status.carCapturedTimestamp"),
    ),
    SkodaSensorDescription(
        key="api_key_expires",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: c.client.meta.key_expires_at,
    ),
    SkodaSensorDescription(
        key="rate_limit_remaining",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:speedometer-slow",
        value_fn=lambda c: c.client.meta.rate_remaining,
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
        SkodaSensor(coordinator, desc)
        for desc in SENSORS
        if desc.requires is None or desc.requires in data
    )


class SkodaSensor(SkodaEntity, SensorEntity):
    entity_description: SkodaSensorDescription

    def __init__(self, coordinator: SkodaCoordinator, description: SkodaSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator)
