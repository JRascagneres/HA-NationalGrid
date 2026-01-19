import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .const import DOMAIN
from .coordinators.national_grid import CARBON_REGIONS, get_data

_LOGGER = logging.getLogger(__name__)

# Region options for selection (None + all regions)
REGION_OPTIONS = {
    0: "None (National data only)",
    **CARBON_REGIONS,
}


class NationalGridConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 4

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "NationalGridOptionsFlow":
        return NationalGridOptionsFlow()

    # Initial step provides the API options
    async def async_step_user(self, user_input=None):
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate by trying to fetch data
            try:
                await self.hass.async_add_executor_job(
                    get_data, self.hass, user_input, None, {}
                )
            except Exception as e:  # pylint: disable=broad-except
                _LOGGER.error(e)
                errors["base"] = "connection_error"
            else:
                # Store region_id as None if 0 (national only) was selected
                region_id = user_input.get("region_id")
                data = {}
                if region_id and region_id > 0:
                    data["region_id"] = region_id

                return self.async_create_entry(title="National Grid", data=data)

        # Show form with region selection
        data_schema = vol.Schema(
            {
                vol.Optional("region_id", default=0): vol.In(REGION_OPTIONS),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )


class NationalGridOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            # Update entry.data with new region_id
            new_data = {**self.config_entry.data}
            if user_input["region_id"] == 0:
                new_data.pop("region_id", None)
            else:
                new_data["region_id"] = user_input["region_id"]

            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )
            return self.async_create_entry(title="", data={})

        # Get current region (default to 0 if not set)
        current_region = self.config_entry.data.get("region_id", 0)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required("region_id", default=current_region): vol.In(REGION_OPTIONS),
            }),
        )
