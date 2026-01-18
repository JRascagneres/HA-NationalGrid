from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DATA_CLIENT, DOMAIN
from .coordinators.national_grid import NationalGridCoordinator

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})

    coodinator = NationalGridCoordinator(hass, entry)
    hass.data[DOMAIN][DATA_CLIENT] = coodinator

    await coodinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version < 4:
        # Migration to version 4: region_id is now optional
        # Existing installs will not have a region_id, which is fine
        # They will continue to use national data only
        new_data = {**config_entry.data}
        hass.config_entries.async_update_entry(
            config_entry, data=new_data, version=4
        )

    _LOGGER.info("Migration to version %s successful", config_entry.version)

    return True
