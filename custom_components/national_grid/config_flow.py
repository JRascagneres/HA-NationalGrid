import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries

from .const import (
    API_KEY,
    API_REQUIRED,
    API_NOT_REQUIRED,
    DOMAIN,
    INCLUDE_API_OPTION,
    INCLUDE_API_OPTION_LIST,
)
from .coordinators.national_grid import get_data
from .errors import InvalidAuthError

_LOGGER = logging.getLogger(__name__)


class NationalGridConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._api_option = None

    # Initial step provides the API options
    async def async_step_user(self, user_input=None):
        data_schema = vol.Schema(
            {vol.Required(INCLUDE_API_OPTION): vol.In(INCLUDE_API_OPTION_LIST)}
        )

        return self.async_show_form(step_id="include_api", data_schema=data_schema)

    # Following selection on whether to include API key this is hit
    async def async_step_include_api(self, user_input=None):
        if INCLUDE_API_OPTION in user_input:
            self._api_option = user_input[INCLUDE_API_OPTION]

        # If API Key required option was not selected hit this. Skip through to the end.
        # If this step fails it'll return to this.
        if self._api_option == API_NOT_REQUIRED:
            data = {API_KEY: "", INCLUDE_API_OPTION: self._api_option}
            data_schema = vol.Schema(
                {vol.Required(INCLUDE_API_OPTION): vol.In(INCLUDE_API_OPTION_LIST)}
            )
            return await self.validate_and_create("include_api", data, data_schema)

        # Otherwise, API Key is required. Pass onto next step requiring API key
        data_schema = vol.Schema({vol.Required(API_KEY): str})
        return self.async_show_form(step_id="add_api_key", data_schema=data_schema)

    async def async_step_add_api_key(self, user_input=None):
        data = {API_KEY: user_input[API_KEY], INCLUDE_API_OPTION: self._api_option}
        data_schema = vol.Schema({vol.Required(API_KEY): str})
        return await self.validate_and_create("add_api_key", data, data_schema)

    async def validate_and_create(
        self, step_id: str, data: dict[str, Any], data_schema: vol.Schema
    ):
        errors: dict[str, str] = {}

        try:
            await self.hass.async_add_executor_job(get_data, self.hass, data, None)
        except InvalidAuthError as e:
            _LOGGER.error("Auth error ocurred")
            errors["base"] = "Invalid API Key"
        except Exception as e:  # pylint: disable=broad-except
            _LOGGER.error(e)
            errors["base"] = "error"

        else:
            return self.async_create_entry(title="National Grid", data=data)

        return self.async_show_form(
            step_id=step_id, data_schema=data_schema, errors=errors
        )
