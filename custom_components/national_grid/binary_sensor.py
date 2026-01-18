from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import NationalGridCoordinator
from .const import DATA_CLIENT, DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class NationalGridBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Provide a description of binary sensor"""

    unique_id: str | None = None
    update_category: str | None = None


BINARY_SENSORS = (
    NationalGridBinarySensorEntityDescription(
        key="margin_warning_active",
        name="Margin Warning Active",
        unique_id="margin_warning_active",
        device_class=BinarySensorDeviceClass.PROBLEM,
        update_category="system_warnings",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Setup the National Grid binary sensors"""
    coordinator: NationalGridCoordinator = hass.data[DOMAIN][DATA_CLIENT]

    async_add_entities(
        NationalGridBinarySensor(coordinator, description)
        for description in BINARY_SENSORS
    )

    return True


class NationalGridBinarySensor(
    CoordinatorEntity[NationalGridCoordinator], BinarySensorEntity
):
    entity_description: NationalGridBinarySensorEntityDescription
    _attr_has_entity_name = True

    def __init__(self, coordinator, description) -> None:
        super().__init__(coordinator)
        self.entity_description = description

        self._attr_device_class = description.device_class

        self._attr_device_info = DeviceInfo(
            configuration_url=None,
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, coordinator.entry_id)},
            manufacturer="JRascagneres",
            name="National Grid",
        )

        self._attr_unique_id = f"{coordinator.entry_id}_{description.unique_id}"

    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self) -> bool | None:
        """Return true if margin warning is active."""
        if self.coordinator.data is None:
            return False
        if self.entity_description.key == "margin_warning_active":
            system_warnings = self.coordinator.data.get("system_warnings")
            if system_warnings is None:
                return False
            current_warning = system_warnings.get("current_warning")
            return current_warning is not None
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = {}

        # Add timing attributes based on update_category
        category = self.entity_description.update_category
        if category:
            last_update = self.coordinator.last_updates.get(category)
            if last_update:
                attrs["last_update"] = last_update.isoformat()

        if self.coordinator.data is None:
            return attrs if attrs else None

        # Add current warning details
        if self.entity_description.key == "margin_warning_active":
            system_warnings = self.coordinator.data.get("system_warnings")
            if system_warnings:
                attrs["current_warning"] = system_warnings.get("current_warning")
                attrs["warnings"] = system_warnings.get("warnings", [])

        return attrs if attrs else None
