from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
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
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import NationalGridCoordinator
from .const import DATA_CLIENT, DOMAIN

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
        native_unit_of_measurement="MW",
        icon="mdi:solar-power-variant",
        state_class=SensorStateClass.MEASUREMENT,
        extra_attributes_key="solar_forecast",
    ),
)

SENSORS = (
    NationalGridSensorEntityDescription(
        key="grid_frequency",
        name="Current Grid Frequency",
        unique_id="grid_frequency",
        native_unit_of_measurement="Hz",
        icon="mdi:sine-wave",
        state_class=SensorStateClass.MEASUREMENT,
    ),
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
        native_unit_of_measurement="MW",
        icon="mdi:wind-turbine",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NationalGridSensorEntityDescription(
        key="wind_data.tomorrow_peak",
        name="Tomorrow Wind Peak",
        unique_id="tomorrow_peak",
        native_unit_of_measurement="MW",
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
        name="Total Demand MW",
        unique_id="total_demand_mwh",
        native_unit_of_measurement="MW",
        icon="mdi:transmission-tower",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NationalGridSensorEntityDescription(
        key="total_transfers_mwh",
        name="Total Transfers MW",
        unique_id="total_transfers_mwh",
        native_unit_of_measurement="MW",
        icon="mdi:transmission-tower-export",
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

SENSORS_GENERATION = (
    NationalGridSensorEntityDescription(
        key="grid_generation.gas_mwh",
        name="Grid Generation Gas MW",
        unique_id="grid_generation_gas_mwh",
        native_unit_of_measurement="MW",
        icon="mdi:fire",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NationalGridSensorEntityDescription(
        key="grid_generation.oil_mwh",
        name="Grid Generation Oil MW",
        unique_id="grid_generation_oil_mwh",
        native_unit_of_measurement="MW",
        icon="mdi:oil",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NationalGridSensorEntityDescription(
        key="grid_generation.coal_mwh",
        name="Grid Generation Coal MW",
        unique_id="grid_generation_coal_mwh",
        native_unit_of_measurement="MW",
        icon="mdi:fire",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NationalGridSensorEntityDescription(
        key="grid_generation.biomass_mwh",
        name="Grid Generation Biomass MW",
        unique_id="grid_generation_biomass_mwh",
        native_unit_of_measurement="MW",
        icon="mdi:leaf",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NationalGridSensorEntityDescription(
        key="grid_generation.nuclear_mwh",
        name="Grid Generation Nuclear MW",
        unique_id="grid_generation_nuclear_mwh",
        native_unit_of_measurement="MW",
        icon="mdi:turbine",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NationalGridSensorEntityDescription(
        key="grid_generation.wind_mwh",
        name="Grid Generation Wind MW",
        unique_id="grid_generation_wind_mwh",
        native_unit_of_measurement="MW",
        icon="mdi:wind-turbine",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NationalGridSensorEntityDescription(
        key="grid_generation.national_wind_mwh",
        name="Grid Generation National Wind MW",
        unique_id="grid_generation_national_wind_mwh",
        native_unit_of_measurement="MW",
        icon="mdi:wind-turbine",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NationalGridSensorEntityDescription(
        key="grid_generation.embedded_wind_mwh",
        name="Grid Generation Embedded Wind MW",
        unique_id="grid_generation_embedded_wind_mwh",
        native_unit_of_measurement="MW",
        icon="mdi:wind-turbine",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NationalGridSensorEntityDescription(
        key="grid_generation.solar_mwh",
        name="Grid Generation Solar MW",
        unique_id="grid_generation_solar_mwh",
        native_unit_of_measurement="MW",
        icon="mdi:solar-power-variant",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NationalGridSensorEntityDescription(
        key="grid_generation.pumped_storage_mwh",
        name="Grid Generation Pumped Storage MW",
        unique_id="grid_generation_pumped_storage_mwh",
        native_unit_of_measurement="MW",
        icon="mdi:pump",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NationalGridSensorEntityDescription(
        key="grid_generation.hydro_mwh",
        name="Grid Generation Hydro MW",
        unique_id="grid_generation_hydro_mwh",
        native_unit_of_measurement="MW",
        icon="mdi:hydro-power",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NationalGridSensorEntityDescription(
        key="grid_generation.other_mwh",
        name="Grid Generation Other MW",
        unique_id="grid_generation_other_mwh",
        native_unit_of_measurement="MW",
        icon="mdi:help",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NationalGridSensorEntityDescription(
        key="grid_generation.france_mwh",
        name="Grid Generation France MW",
        unique_id="grid_generation_france_mwh",
        native_unit_of_measurement="MW",
        icon="mdi:transmission-tower",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NationalGridSensorEntityDescription(
        key="grid_generation.ireland_mwh",
        name="Grid Generation Ireland MW",
        unique_id="grid_generation_ireland_mwh",
        native_unit_of_measurement="MW",
        icon="mdi:transmission-tower",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NationalGridSensorEntityDescription(
        key="grid_generation.netherlands_mwh",
        name="Grid Generation Netherlands MW",
        unique_id="grid_generation_netherlands_mwh",
        native_unit_of_measurement="MW",
        icon="mdi:transmission-tower",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NationalGridSensorEntityDescription(
        key="grid_generation.belgium_mwh",
        name="Grid Generation Belgium MW",
        unique_id="grid_generation_belgium_mwh",
        native_unit_of_measurement="MW",
        icon="mdi:transmission-tower",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NationalGridSensorEntityDescription(
        key="grid_generation.norway_mwh",
        name="Grid Generation Norway MW",
        unique_id="grid_generation_norway_mwh",
        native_unit_of_measurement="MW",
        icon="mdi:transmission-tower",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NationalGridSensorEntityDescription(
        key="grid_generation.denmark_mw",
        name="Grid Generation Denmark MW",
        unique_id="grid_generation_denmark_mw",
        native_unit_of_measurement="MW",
        icon="mdi:transmission-tower",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NationalGridSensorEntityDescription(
        key="grid_generation.total_generation_mwh",
        name="Grid Generation Total MW",
        unique_id="grid_generation_total_generation_mwh",
        native_unit_of_measurement="MW",
        icon="mdi:transmission-tower",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NationalGridSensorEntityDescription(
        key="wind_forecast.current_value",
        name="Wind Forecast",
        unique_id="wind_forecast",
        native_unit_of_measurement="MW",
        icon="mdi:wind-turbine",
        state_class=SensorStateClass.MEASUREMENT,
        extra_attributes_key="wind_forecast",
    ),
    NationalGridSensorEntityDescription(
        key="wind_forecast_earliest.current_value",
        name="Wind Forecast Earliest",
        unique_id="wind_forecast_earliest",
        native_unit_of_measurement="MW",
        icon="mdi:wind-turbine",
        state_class=SensorStateClass.MEASUREMENT,
        extra_attributes_key="wind_forecast_earliest",
    ),
    NationalGridSensorEntityDescription(
        key=None,
        name="Wind Forecast Now To Three Day",
        unique_id="now_to_three_wind_forecast",
        icon="mdi:wind-turbine",
        extra_attributes_key="now_to_three_wind_forecast",
    ),
    NationalGridSensorEntityDescription(
        key=None,
        name="Wind Forecast Fourteen Day",
        unique_id="fourteen_day_wind_forecast",
        icon="mdi:wind-turbine",
        extra_attributes_key="fourteen_wind_forecast",
    ),
    NationalGridSensorEntityDescription(
        key="fourteen_embedded_solar.current_value",
        name="Embedded Solar Forecast Fourteen Day",
        unique_id="fourteen_day_embedded_solar",
        native_unit_of_measurement="MW",
        icon="mdi:solar-power-variant",
        state_class=SensorStateClass.MEASUREMENT,
        extra_attributes_key="fourteen_embedded_solar",
    ),
    NationalGridSensorEntityDescription(
        key="three_embedded_solar.current_value",
        name="Embedded Solar Forecast Three Day",
        unique_id="three_day_embedded_solar",
        native_unit_of_measurement="MW",
        icon="mdi:solar-power-variant",
        state_class=SensorStateClass.MEASUREMENT,
        extra_attributes_key="three_embedded_solar",
    ),
    NationalGridSensorEntityDescription(
        key="fourteen_embedded_wind.current_value",
        name="Embedded Wind Forecast Fourteen Day",
        unique_id="fourteen_day_embedded_wind",
        native_unit_of_measurement="MW",
        icon="mdi:wind-turbine",
        state_class=SensorStateClass.MEASUREMENT,
        extra_attributes_key="fourteen_embedded_wind",
    ),
    NationalGridSensorEntityDescription(
        key="three_embedded_wind.current_value",
        name="Embedded Wind Forecast Three Day",
        unique_id="three_day_embedded_wind",
        native_unit_of_measurement="MW",
        icon="mdi:wind-turbine",
        state_class=SensorStateClass.MEASUREMENT,
        extra_attributes_key="three_embedded_wind",
    ),
    NationalGridSensorEntityDescription(
        key="grid_demand_day_ahead_forecast.current_value",
        name="Grid Demand Day Ahead Forecast",
        unique_id="grid_demand_day_ahead_forecast",
        native_unit_of_measurement="MW",
        icon="mdi:transmission-tower",
        state_class=SensorStateClass.MEASUREMENT,
        extra_attributes_key="grid_demand_day_ahead_forecast",
    ),
    NationalGridSensorEntityDescription(
        key="grid_demand_three_day_forecast.current_value",
        name="Grid Demand Three Day Forecast",
        unique_id="grid_demand_three_day_forecast",
        native_unit_of_measurement="MW",
        icon="mdi:transmission-tower",
        state_class=SensorStateClass.MEASUREMENT,
        extra_attributes_key="grid_demand_three_day_forecast",
    ),
    NationalGridSensorEntityDescription(
        key="grid_demand_fourteen_day_forecast.current_value",
        name="Grid Demand Fourteen Day Forecast",
        unique_id="grid_demand_fourteen_day_forecast",
        native_unit_of_measurement="MW",
        icon="mdi:transmission-tower",
        state_class=SensorStateClass.MEASUREMENT,
        extra_attributes_key="grid_demand_fourteen_day_forecast",
    ),
    NationalGridSensorEntityDescription(
        key=None,
        name="DFS Requirements",
        unique_id="dfs_requirements",
        icon="mdi:leaf",
        extra_attributes_key="dfs_requirements",
    ),
    NationalGridSensorEntityDescription(
        key=None,
        name="Grid Generation",
        unique_id="grid_generation",
        icon="mdi:transmission-tower",
        extra_attributes_key="grid_generation",
    ),
    NationalGridSensorEntityDescription(
        key="grid_generation.fossil_fuel_percentage_generation",
        name="Grid Generation Fossil Fuel Percentage",
        unique_id="fossil_fuel_percentage_generation",
        native_unit_of_measurement="%",
        icon="mdi:molecule-co2",
    ),
    NationalGridSensorEntityDescription(
        key="grid_generation.renewable_percentage_generation",
        name="Grid Generation Renewable Percentage",
        unique_id="renewable_percentage_generation",
        native_unit_of_measurement="%",
        icon="mdi:leaf",
    ),
    NationalGridSensorEntityDescription(
        key="grid_generation.low_carbon_percentage_generation",
        name="Grid Generation Low Carbon Percentage",
        unique_id="low_carbon_percentage_generation",
        native_unit_of_measurement="%",
        icon="mdi:leaf",
    ),
    NationalGridSensorEntityDescription(
        key="grid_generation.low_carbon_with_biomass_percentage_generation",
        name="Grid Generation Low Carbon With Biomass Percentage",
        unique_id="low_carbon_with_biomass_percentage_generation",
        native_unit_of_measurement="%",
        icon="mdi:leaf",
    ),
    NationalGridSensorEntityDescription(
        key="grid_generation.other_percentage_generation",
        name="Grid Generation Other Percentage",
        unique_id="other_percentage_generation",
        native_unit_of_measurement="%",
        icon="mdi:help",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Setup the National Grid sensor"""
    coordinator: NationalGridCoordinator = hass.data[DOMAIN][DATA_CLIENT]

    sensors = SENSORS + API_SENSORS

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
