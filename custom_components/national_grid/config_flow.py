import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY

from . import InvalidAuthError, get_data
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class NationalGridConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input):
        """Handle initial step"""
        data_schema = vol.Schema({vol.Required(CONF_API_KEY): str})

        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=data_schema,
            )

        data = {CONF_API_KEY: user_input[CONF_API_KEY]}

        return await self.validate_and_create("user", data, data_schema)

    async def validate_and_create(
        self, step_id: str, data: dict[str, Any], data_schema: vol.Schema
    ):
        errors: dict[str, str] = {}

        try:
            await self.hass.async_add_executor_job(get_data, self.hass, data)
        except InvalidAuthError as e:
            _LOGGER.error("Auth error ocurred")
            errors["base"] = "Invalid API Key"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.error(e)
            errors["base"] = "error"

        else:
            return self.async_create_entry(title="National Grid", data=data)

        return self.async_show_form(
            step_id=step_id, data_schema=data_schema, errors=errors
        )
