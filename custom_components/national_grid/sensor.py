import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo, Entity, EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import NationalGridCoordinator
from .const import DATA_CLIENT, DOMAIN, API_KEY_PROVIDED

SCAN_INTERVAL = timedelta(minutes=5)
_LOGGER = logging.getLogger(__name__)


@dataclass
class NationalGridSensorEntityDescription(SensorEntityDescription):
    """Provide a description of sensor"""

    # For backwards compat, allow description to override unique ID key to use
    unique_id: str | None = None
    extra_attributes_key: str | None = None


API_SENSORS = (
    NationalGridSensorEntityDescription(
        key="sell_price",
        name="Current Sell Price",
        unique_id="sell_price",
        native_unit_of_measurement="GBP/MWh",
        icon="mdi:currency-gbp",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NationalGridSensorEntityDescription(
        key="solar_forecast.current_value",
        name="Solar Forecast",
        unique_id="solar_forecast",
        native_unit_of_measurement="MWh",
        icon="mdi:solar-power-variant",
        state_class=SensorStateClass.MEASUREMENT,
        extra_attributes_key="solar_forecast",
    ),
)

SENSORS = (
    NationalGridSensorEntityDescription(
        key="carbon_intensity",
        name="Current Carbon Intensity",
        unique_id="carbon_intensity",
        native_unit_of_measurement="gCO2eq/kWh",
        icon="mdi:molecule-co2",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NationalGridSensorEntityDescription(
        key="wind_data.today_peak",
        name="Today Wind Peak",
        unique_id="today_peak",
        native_unit_of_measurement="MWh",
        icon="mdi:wind-turbine",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NationalGridSensorEntityDescription(
        key="wind_data.tomorrow_peak",
        name="Tomorrow Wind Peak",
        unique_id="tomorrow_peak",
        native_unit_of_measurement="MWh",
        icon="mdi:wind-turbine",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NationalGridSensorEntityDescription(
        key="wind_data.today_peak_time",
        name="Today Wind Peak Time",
        unique_id="today_peak_time",
        native_unit_of_measurement=None,
        icon="mdi:clock",
        state_class=None,
        device_class=SensorDeviceClass.DATE,
    ),
    NationalGridSensorEntityDescription(
        key="wind_data.tomorrow_peak_time",
        name="Tomorrow Wind Peak Time",
        unique_id="tomorrow_peak_time",
        native_unit_of_measurement=None,
        icon="mdi:clock",
        state_class=None,
        device_class=SensorDeviceClass.DATE,
    ),
    NationalGridSensorEntityDescription(
        key="total_demand_mwh",
        name="Total Demand MWh",
        unique_id="total_demand_mwh",
        native_unit_of_measurement="MWh",
        icon="mdi:transmission-tower",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NationalGridSensorEntityDescription(
        key="total_transfers_mwh",
        name="Total Transfers MWh",
        unique_id="total_transfers_mwh",
        native_unit_of_measurement="MWh",
        icon="mdi:transmission-tower-export",
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

SENSORS_GENERATION = (
    NationalGridSensorEntityDescription(
        key="grid_generation.gas_mwh",
        name="Grid Generation Gas MWh",
        unique_id="grid_generation_gas_mwh",
        native_unit_of_measurement="MWh",
        icon="mdi:fire",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NationalGridSensorEntityDescription(
        key="grid_generation.oil_mwh",
        name="Grid Generation Oil MWh",
        unique_id="grid_generation_oil_mwh",
        native_unit_of_measurement="MWh",
        icon="mdi:oil",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NationalGridSensorEntityDescription(
        key="grid_generation.coal_mwh",
        name="Grid Generation Coal MWh",
        unique_id="grid_generation_coal_mwh",
        native_unit_of_measurement="MWh",
        icon="mdi:fire",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NationalGridSensorEntityDescription(
        key="grid_generation.biomass_mwh",
        name="Grid Generation Biomass MWh",
        unique_id="grid_generation_biomass_mwh",
        native_unit_of_measurement="MWh",
        icon="mdi:leaf",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NationalGridSensorEntityDescription(
        key="grid_generation.nuclear_mwh",
        name="Grid Generation Nuclear MWh",
        unique_id="grid_generation_nuclear_mwh",
        native_unit_of_measurement="MWh",
        icon="mdi:turbine",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NationalGridSensorEntityDescription(
        key="grid_generation.wind_mwh",
        name="Grid Generation Wind MWh",
        unique_id="grid_generation_wind_mwh",
        native_unit_of_measurement="MWh",
        icon="mdi:wind-turbine",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NationalGridSensorEntityDescription(
        key="grid_generation.national_wind_mwh",
        name="Grid Generation National Wind MWh",
        unique_id="grid_generation_national_wind_mwh",
        native_unit_of_measurement="MWh",
        icon="mdi:wind-turbine",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NationalGridSensorEntityDescription(
        key="grid_generation.embedded_wind_mwh",
        name="Grid Generation Embedded Wind MWh",
        unique_id="grid_generation_embedded_wind_mwh",
        native_unit_of_measurement="MWh",
        icon="mdi:wind-turbine",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NationalGridSensorEntityDescription(
        key="grid_generation.solar_mwh",
        name="Grid Generation Solar MWh",
        unique_id="grid_generation_solar_mwh",
        native_unit_of_measurement="MWh",
        icon="mdi:solar-power-variant",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NationalGridSensorEntityDescription(
        key="grid_generation.pumped_storage_mwh",
        name="Grid Generation Pumped Storage MWh",
        unique_id="grid_generation_pumped_storage_mwh",
        native_unit_of_measurement="MWh",
        icon="mdi:pump",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NationalGridSensorEntityDescription(
        key="grid_generation.hydro_mwh",
        name="Grid Generation Hydro MWh",
        unique_id="grid_generation_hydro_mwh",
        native_unit_of_measurement="MWh",
        icon="mdi:hydro-power",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NationalGridSensorEntityDescription(
        key="grid_generation.other_mwh",
        name="Grid Generation Other MWh",
        unique_id="grid_generation_other_mwh",
        native_unit_of_measurement="MWh",
        icon="mdi:help",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NationalGridSensorEntityDescription(
        key="grid_generation.france_mwh",
        name="Grid Generation France MWh",
        unique_id="grid_generation_france_mwh",
        native_unit_of_measurement="MWh",
        icon="mdi:transmission-tower",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NationalGridSensorEntityDescription(
        key="grid_generation.ireland_mwh",
        name="Grid Generation Ireland MWh",
        unique_id="grid_generation_ireland_mwh",
        native_unit_of_measurement="MWh",
        icon="mdi:transmission-tower",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NationalGridSensorEntityDescription(
        key="grid_generation.netherlands_mwh",
        name="Grid Generation Netherlands MWh",
        unique_id="grid_generation_netherlands_mwh",
        native_unit_of_measurement="MWh",
        icon="mdi:transmission-tower",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NationalGridSensorEntityDescription(
        key="grid_generation.belgium_mwh",
        name="Grid Generation Belgium MWh",
        unique_id="grid_generation_belgium_mwh",
        native_unit_of_measurement="MWh",
        icon="mdi:transmission-tower",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NationalGridSensorEntityDescription(
        key="grid_generation.norway_mwh",
        name="Grid Generation Norway MWh",
        unique_id="grid_generation_norway_mwh",
        native_unit_of_measurement="MWh",
        icon="mdi:transmission-tower",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NationalGridSensorEntityDescription(
        key="grid_generation.total_generation_mwh",
        name="Grid Generation Total MWh",
        unique_id="grid_generation_total_generation_mwh",
        native_unit_of_measurement="MWh",
        icon="mdi:transmission-tower",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NationalGridSensorEntityDescription(
        key="wind_forecast.forecast.0.generation",
        name="Wind Forecast",
        unique_id="wind_forecast",
        native_unit_of_measurement="MWh",
        icon="mdi:wind-turbine",
        state_class=SensorStateClass.MEASUREMENT,
        extra_attributes_key="wind_forecast",
    ),
    NationalGridSensorEntityDescription(
        key="wind_forecast_earliest.forecast.0.generation",
        name="Wind Forecast Earliest",
        unique_id="wind_forecast_earliest",
        native_unit_of_measurement="MWh",
        icon="mdi:wind-turbine",
        state_class=SensorStateClass.MEASUREMENT,
        extra_attributes_key="wind_forecast_earliest",
    ),
    NationalGridSensorEntityDescription(
        key=None,
        name="Grid Generation",
        unique_id="grid_generation",
        icon="mdi:transmission-tower",
        extra_attributes_key="grid_generation",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Setup the National Grid sensor"""
    coordinator: NationalGridCoordinator = hass.data[DOMAIN][DATA_CLIENT]

    sensors = SENSORS

    if entry.data[API_KEY_PROVIDED]:
        sensors = sensors + API_SENSORS

    async_add_entities(
        NationalGridSensor(coordinator, description) for description in sensors
    )

    async_add_entities(
        NationalGridSensor(coordinator, description)
        for description in SENSORS_GENERATION
    )

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
        if not self.entity_description.key:
            return self.entity_description.name

        keys = self.entity_description.key.split(".")

        value = self.coordinator.data[keys[0]]
        if len(keys) > 1:
            for key in keys[1:]:
                if value is None:
                    return None
                if key.isnumeric():
                    value = value[int(key)]
                    continue
                value = value[key]

        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.entity_description.extra_attributes_key:
            return None

        keys = self.entity_description.extra_attributes_key.split(".")

        value = self.coordinator.data[keys[0]]
        if len(keys) > 1:
            for key in keys[1:]:
                if value is None:
                    return None
                if key.isnumeric():
                    value = value[int(key)]
                    continue
                value = value[key]

        return value

    @property
    def native_unit_of_measurement(self) -> str | None:
        return self.entity_description.native_unit_of_measurement
