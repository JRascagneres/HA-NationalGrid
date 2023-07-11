import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from config.custom_components.national_grid import NationalGridCoordinator
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

SCAN_INTERVAL = timedelta(minutes=5)
_LOGGER = logging.getLogger(__name__)


@dataclass
class NationalGridSensorEntityDescription(SensorEntityDescription):
    """Provide a description of sensor"""

    # For backwards compat, allow description to override unique ID key to use
    unique_id: str | None = None


SENSORS = (
    NationalGridSensorEntityDescription(
        key="sellPrice",
        name="Current Sell Price",
        unique_id="sellPrice",
        native_unit_of_measurement="GBP/MWh",
        icon="mdi:currency-gbp",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NationalGridSensorEntityDescription(
        key="windData.todayPeak",
        name="Today Wind Peak",
        unique_id="todayPeak",
        native_unit_of_measurement="MWh",
        icon="mdi:wind-turbine",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NationalGridSensorEntityDescription(
        key="windData.tomorrowPeak",
        name="Tomorrow Wind Peak",
        unique_id="tomorrowPeak",
        native_unit_of_measurement="MWh",
        icon="mdi:wind-turbine",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NationalGridSensorEntityDescription(
        key="windData.todayPeakTime",
        name="Today Wind Peak Time",
        unique_id="todayPeakTime",
        native_unit_of_measurement=None,
        icon="mdi:clock",
        state_class=None,
        device_class=SensorDeviceClass.DATE,
    ),
    NationalGridSensorEntityDescription(
        key="windData.tomorrowPeakTime",
        name="Tomorrow Wind Peak Time",
        unique_id="tomorrowPeakTime",
        native_unit_of_measurement=None,
        icon="mdi:clock",
        state_class=None,
        device_class=SensorDeviceClass.DATE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Setup the National Grid sensor"""
    coordinator: NationalGridCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        NationalGridSensor(coordinator, description) for description in SENSORS
    )

    async_add_entities([Grid(coordinator)])

    return True


class NationalGridSensor(CoordinatorEntity[NationalGridCoordinator], SensorEntity):
    entity_description: NationalGridSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(self, coordinator, description) -> None:
        super().__init__(coordinator)
        self.entity_description = description

        self._attr_state_class = description.state_class
        self._attr_device_class = description.device_class

        self._attr_device_info = DeviceInfo(
            configuration_url=None,
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, coordinator.entry_id)},
            manufacturer="JRascagneres",
            name="National Grid",
        )

        self._attr_unique_id = f"{coordinator.entry_id}_{description.unique_id}"
        self._attr_icon = description.icon

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self) -> float | datetime | None:
        keys = self.entity_description.key.split(".")

        value = self.coordinator.data[keys[0]]
        if len(keys) > 1:
            for key in keys[1:]:
                if value is None:
                    return None
                value = value[key]

        return value

    @property
    def native_unit_of_measurement(self) -> str | None:
        return self.entity_description.native_unit_of_measurement


class Grid(CoordinatorEntity[NationalGridCoordinator], Entity):
    """Representation of the Grid"""

    _attr_name = "Grid Production"
    entity_id = DOMAIN + ".grid_producton"

    grid_gen: float

    def __init__(self, coordinator) -> None:
        """Initialize Grid"""
        super().__init__(coordinator)
        self.coordinator = coordinator

        self.grid_gen = 1

    @property
    def state(self) -> str:
        return "Grid Generation"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.coordinator.data["gridGeneration"]
