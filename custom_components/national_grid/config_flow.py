import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries

from .const import DOMAIN
from .coordinators.national_grid import get_data
from .errors import InvalidAuthError

_LOGGER = logging.getLogger(__name__)


class NationalGridConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 3

    # Initial step provides the API options
    async def async_step_user(self, user_input=None):
        return await self.validate_and_create("user")

    async def validate_and_create(self, step_id: str):
        errors: dict[str, str] = {}

        try:
            await self.hass.async_add_executor_job(get_data, self.hass, None, None)
        except Exception as e:  # pylint: disable=broad-except
            _LOGGER.error(e)
            errors["base"] = "An error occurred"

        else:
            return self.async_create_entry(title="National Grid", data={})

        return self.async_show_form(step_id=step_id, data_schema={}, errors=errors)
