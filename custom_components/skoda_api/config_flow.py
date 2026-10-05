"""Config flow for the Škoda Public API integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_API_KEY
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .api import SkodaApiClient, SkodaApiError, SkodaAuthError, SkodaRateLimitError
from .const import (
    CONF_SCAN_INTERVAL_MIN,
    CONF_VIN,
    DEFAULT_SCAN_INTERVAL_MIN,
    DOMAIN,
    MIN_SCAN_INTERVAL_MIN,
)

_LOGGER = logging.getLogger(__name__)

API_KEY_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


class SkodaApiConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def _validate(self, api_key: str, vin: str) -> tuple[dict[str, Any] | None, dict[str, str]]:
        client = SkodaApiClient(async_get_clientsession(self.hass), api_key, vin)
        try:
            resp = await client.get_vehicle()
        except SkodaAuthError:
            return None, {"base": "invalid_auth"}
        except SkodaRateLimitError:
            return None, {"base": "rate_limited"}
        except SkodaApiError as err:
            if err.status == 404:
                return None, {CONF_VIN: "vehicle_not_found"}
            _LOGGER.warning("Validation failed: %s", err)
            return None, {"base": "cannot_connect"}
        except (aiohttp.ClientError, TimeoutError):
            return None, {"base": "cannot_connect"}
        return resp.get("vehicle") or {}, {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            vin = user_input[CONF_VIN].strip().upper()
            api_key = user_input[CONF_API_KEY].strip()
            await self.async_set_unique_id(vin)
            self._abort_if_unique_id_configured()
            vehicle, errors = await self._validate(api_key, vin)
            if vehicle is not None:
                return self.async_create_entry(
                    title=vehicle.get("name") or vin,
                    data={CONF_API_KEY: api_key, CONF_VIN: vin},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): API_KEY_SELECTOR,
                    vol.Required(CONF_VIN): vol.All(str, vol.Length(min=17, max=17)),
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            vehicle, errors = await self._validate(api_key, entry.data[CONF_VIN])
            if vehicle is not None:
                return self.async_update_reload_and_abort(entry, data_updates={CONF_API_KEY: api_key})

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): API_KEY_SELECTOR}),
            description_placeholders={"vin": entry.data[CONF_VIN]},
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return SkodaApiOptionsFlow()


class SkodaApiOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = self.config_entry.options.get(CONF_SCAN_INTERVAL_MIN, DEFAULT_SCAN_INTERVAL_MIN)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCAN_INTERVAL_MIN, default=current): vol.All(
                        vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL_MIN, max=120)
                    )
                }
            ),
        )
