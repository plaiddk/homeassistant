"""Climate entity for the Škoda Public API integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components.climate import (
    ATTR_TEMPERATURE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .coordinator import SkodaConfigEntry, SkodaCoordinator
from .entity import SkodaEntity

DEFAULT_TARGET = 22.0
# How long to show the commanded mode while waiting for the car to confirm it.
PENDING_TIMEOUT = timedelta(minutes=5)
RUNNING_STATES = ("COOLING", "HEATING", "HEATING_AUXILIARY", "VENTILATION")
ACTIONS = {
    "COOLING": HVACAction.COOLING,
    "HEATING": HVACAction.HEATING,
    "HEATING_AUXILIARY": HVACAction.HEATING,
    "VENTILATION": HVACAction.FAN,
    "COMPLETED": HVACAction.IDLE,
    "OFF": HVACAction.OFF,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SkodaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    if "airConditioning" in (coordinator.data or {}) and coordinator.supports("startAirConditioning"):
        async_add_entities([SkodaClimate(coordinator)])


class SkodaClimate(SkodaEntity, ClimateEntity, RestoreEntity):
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT_COOL]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = 15.5
    _attr_max_temp = 30
    _attr_target_temperature_step = 0.5

    def __init__(self, coordinator: SkodaCoordinator) -> None:
        super().__init__(coordinator, "air_conditioning")
        self._target: float | None = None
        # Last target reported by the API; a change there overrides the local target.
        self._last_api_target: float | None = self._api_target()
        self._pending_mode: HVACMode | None = None
        self._pending_until = dt_util.utcnow()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self._api_target() is None and (last := await self.async_get_last_state()) is not None:
            self._target = last.attributes.get(ATTR_TEMPERATURE)

    def _api_target(self) -> float | None:
        if self.data_at("airConditioning.targetTemperature.unit") != "CELSIUS":
            return None
        return self.data_at("airConditioning.targetTemperature.value")

    @callback
    def _handle_coordinator_update(self) -> None:
        if self._pending_mode is not None and (
            self._api_mode() == self._pending_mode or dt_util.utcnow() >= self._pending_until
        ):
            self._pending_mode = None
        api = self._api_target()
        if api is not None and api != self._last_api_target:
            self._target = api
            self._last_api_target = api
        super()._handle_coordinator_update()

    @property
    def target_temperature(self) -> float | None:
        return self._target if self._target is not None else self._api_target()

    def _api_mode(self) -> HVACMode | None:
        state = self.data_at("airConditioning.state")
        if state in (None, "UNKNOWN", "UNSUPPORTED"):
            return None
        return HVACMode.HEAT_COOL if state in RUNNING_STATES else HVACMode.OFF

    @property
    def hvac_mode(self) -> HVACMode | None:
        if self._pending_mode is not None and dt_util.utcnow() < self._pending_until:
            return self._pending_mode
        return self._api_mode()

    @property
    def hvac_action(self) -> HVACAction | None:
        return ACTIONS.get(self.data_at("airConditioning.state"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "state": self.data_at("airConditioning.state"),
            "window_heating_front": self.data_at("airConditioning.windowHeating.front"),
            "window_heating_rear": self.data_at("airConditioning.windowHeating.rear"),
            "without_external_power": self.data_at("airConditioning.airConditioningWithoutExternalPower"),
        }

    async def _start(self) -> None:
        await self.coordinator.async_command(
            self.coordinator.client.start_air_conditioning(self.target_temperature or DEFAULT_TARGET)
        )
        self._set_pending(HVACMode.HEAT_COOL)

    async def _stop(self) -> None:
        await self.coordinator.async_command(self.coordinator.client.stop_air_conditioning())
        self._set_pending(HVACMode.OFF)

    @callback
    def _set_pending(self, mode: HVACMode) -> None:
        self._pending_mode = mode
        self._pending_until = dt_util.utcnow() + PENDING_TIMEOUT
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            await self._stop()
        else:
            await self._start()

    async def async_turn_on(self) -> None:
        await self._start()

    async def async_turn_off(self) -> None:
        await self._stop()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        self._target = float(temp)
        # The API has no separate "set temperature" call; restart AC only if it is running.
        if self.hvac_mode == HVACMode.HEAT_COOL:
            await self._start()
        else:
            self.async_write_ha_state()
