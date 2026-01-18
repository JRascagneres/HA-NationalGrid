# National Grid Home Assistant Integration
![installation_badge](https://img.shields.io/badge/dynamic/json?color=41BDF5&logo=home-assistant&label=integration%20usage&suffix=%20installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.national_grid.total)


Custom component providing information about the UK National Grid. Provides generation data, forecast data and more from the official endorsed APIs of the UK power network.

This integration is in no way affiliated with or approved by the National Grid.

## Installation
There are two methods of setting up the integration: Either using HACS or manually.

### HACS
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

This integration can be added through HACS, this is the easiest and recommended method.

1. [Add the repository to HACS](https://my.home-assistant.io/redirect/hacs_repository/?owner=JRascagneres&repository=HA-NationalGrid&category=integration)
2. Click 'Add' in the prompt
3. Once redirected click 'Download' in the bottom right

### Manual
1. Download the current repo
2. Place the contents of custom_components into the /config/custom_components folder of your Home Assistant installation

Note: A restart will be required for the integration to be registered.

## Setup
Follow the same steps that are using to setup most integrations:
1. Head to settings then Devices & Services
2. Click 'Add Integration' in the bottom right
3. Search for 'National Grid'
4. Click 'National Grid'
5. Optionally select a region for regional carbon intensity data (England, Scotland, Wales, or specific DNO regions)
6. Your device and entities will be created

**Note:** If you configure a region, you will get additional regional carbon intensity sensors. You can reconfigure the integration later to change or add a region.

## Sensors
| Name | ID | Description |
| ---- | -- | ----------- |
| National Grid Current Sell Price (optional) | sensor.national_grid_current_sell_price | Current balancing price of Grid |
| National Grid Current Grid Frequency | sensor.national_grid_current_grid_frequency | Current Grid Frequency (every 5 minutes) |
| National Grid Today Wind Peak | sensor.national_grid_today_wind_peak | Estimated peak wind production of Grid today |
| National Grid Today Wind Peak Time | sensor.national_grid_today_wind_peak_time | Estimated time of peak wind production of Grid today |
| National Grid Tomorrow Wind Peak | sensor.national_grid_tomorrow_wind_peak | Estimated peak wind production of Grid tomorrow |
| National Grid Tomorrow Wind Peak Time | sensor.national_grid_tomorrow_wind_peak_time | Estimated time of peak wind production of Grid tomorrow |
| National Grid Grid Generation Gas MWh | sensor.national_grid_grid_generation_gas_mwh | Current electricity generation from gas in MWh |
| National Grid Grid Generation Oil MWh | sensor.national_grid_grid_generation_oil_mwh | Current electricity generation from oil in MWh |
| National Grid Grid Generation Coal MWh | sensor.national_grid_grid_generation_coal_mwh | Current electricity generation from coal in MWh |
| National Grid Grid Generation Biomass MWh | sensor.national_grid_grid_generation_biomass_mwh | Current electricity generation from biomass in MWh |
| National Grid Grid Generation Nuclear MWh | sensor.national_grid_grid_generation_nuclear_mwh | Current electricity generation from nuclear in MWh |
| National Grid Grid Generation Wind MWh | sensor.national_grid_grid_generation_wind_mwh | Current electricity generation from wind in MWh |
| National Grid Grid Generation Solar MWh | sensor.national_grid_grid_generation_solar_mwh | Current electricity generation from solar in MWh |
| National Grid Grid Generation Pumped Storage MWh | sensor.national_grid_grid_generation_pumped_storage_mwh | Current electricity generation from pumped storage in MWh |
| National Grid Grid Generation Hydro MWh | sensor.national_grid_grid_generation_hydro_mwh | Current electricity generation from hydro in MWh |
| National Grid Grid Generation Other MWh | sensor.national_grid_grid_generation_other_mwh | Current electricity generation from other / unknown sources in MWh |
| National Grid Grid Generation France MWh | sensor.national_grid_grid_generation_france_mwh | Current electricity generation from France interconnectors in MWh |
| National Grid Grid Generation Ireland MWh | sensor.national_grid_grid_generation_ireland_mwh | Current electricity generation from Ireland interconnectors in MWh |
| National Grid Grid Generation Netherlands MWh | sensor.national_grid_grid_generation_netherlands_mwh | Current electricity generation from Netherlands interconnectors in MWh |
| National Grid Grid Generation Belgium MWh | sensor.national_grid_grid_generation_belgium_mwh | Current electricity generation from Belgium interconnectors in MWh |
| National Grid Grid Generation Norway MWh | sensor.national_grid_grid_generation_norway_mwh | Current electricity generation from Norway interconnectors in MWh |
| National Grid Grid Generation Denmark MW | sensor.national_grid_grid_generation_denmark_mw | Current electricity generation from Denmark interconnectors in MW |
| National Grid Total Generation | sensor.total_generation_mwh | Total generation in MWh |
| National Grid Total Demand MWh | sensor.national_grid_total_demand_mwh | Total electricity demand in MWh. This is all generation with the inclusion of interconnectors and storage. |
| National Grid Total Transfers MWh | sensor.national_grid_total_transfers_mwh | Total electricity transfers in MWh. This is all the transfers which are interconnectors and storage. |
| National Grid Grid Generation Fossil Fuel Percentage | sensor.national_grid_fossil_fuel_percentage_generation | Percentage of total grid generation that is generated from fossil fuel sources: Gas, Oil & Coal |
| National Grid Grid Generation Renewable Percentage | sensor.national_grid_renewable_percentage_generation | Percentage of total grid generation that is generated from renewable sources: Solar, Wind & Hydro |
| National Grid Grid Generation Low Carbon Percentage | sensor.national_grid_low_carbon_percentage_generation | Percentage of total grid generation that is generated from renewable & low carbon sources: Solar, Wind, Hydro & Nuclear |
| National Grid Grid Generation Low Carbon With Biomass Percentage | sensor.low_carbon_with_biomass_percentage_generation | Percentage of total grid generation that is generated from renewable & low carbon sources including Biomass (which is contentious): Solar, Wind, Hydro, Nuclear & Biomass |
| National Grid Grid Generation Other Percentage | sensor.national_grid_other_percentage_generation | Percentage of total grid generation that is generated from 'other' sources: Nuclear, Biomass & Unknown / Other |
| National Grid Forecast Margin | sensor.national_grid_forecast_margin | Daily operating margin forecast in MW showing headroom between supply and demand |
| National Grid System Warning | sensor.national_grid_system_warning | Current system warning type (e.g., "Electricity Margin Notice") or "None" |
| National Grid Margin Warning Active | binary_sensor.national_grid_margin_warning_active | Binary sensor indicating whether a margin warning is currently active |
| National Grid Carbon Intensity Forecast | sensor.national_grid_carbon_intensity_forecast | 48-hour carbon intensity forecast with half-hourly resolution |
| National Grid Carbon Intensity Index | sensor.national_grid_carbon_intensity_index | Current carbon intensity level: very low, low, moderate, high, or very high |
| National Grid Regional Carbon Intensity | sensor.national_grid_regional_carbon_intensity | Regional carbon intensity in gCO2/kWh (only if region configured) |
| National Grid Regional Carbon Index | sensor.national_grid_regional_carbon_index | Regional carbon intensity level (only if region configured) |


Note that the associated time sensors are important. Updates can lag by a few minutes and are in UTC so its possible that 'today' and 'tomorrow' aren't entirely accurate for a period of time.

## Update Frequencies

The integration uses differentiated update intervals to balance data freshness with API load:

| Data Category | Update Interval | Sensors |
|---------------|-----------------|---------|
| Grid Frequency | 2 minutes | Current Grid Frequency |
| Sell Price | 5 minutes | Current Sell Price |
| Grid Generation | 5 minutes | All generation, demand, transfers, percentage sensors |
| System Warnings | 5 minutes | System Warning, Margin Warning Active |
| Carbon Intensity | 15 minutes | Current Carbon Intensity, Carbon Intensity Index, Regional Carbon Intensity, Regional Carbon Index |
| Margin Indicators | 15 minutes | Forecast Margin, Carbon Intensity Forecast |
| Wind Forecasts | 30 minutes | Wind Forecast, Wind Forecast Earliest, Wind Forecast Now To Three Day, Wind Forecast Fourteen Day, Embedded Wind/Solar Forecasts |
| Solar Forecasts | 30 minutes | Solar Forecast |
| Demand Forecasts | 30 minutes | Grid Demand Day Ahead, Three Day, and Fourteen Day Forecasts |
| DFS Requirements | 30 minutes | DFS Requirements |

All sensors include a `last_update` attribute showing when the data was last refreshed (in ISO 8601 format).

### Grid Generation Sensor Entity

Name - Grid Generation\
ID - sensor.national_grid_grid_generation\
State - Temporary "Grid Generation"\
Attributes:
```
gas_mwh
oil_mwh
coal_mwh
nuclear_mwh
wind_mwh
national_wind_mwh
embedded_wind_mwh
solar_mwh
pumped_storage_mwh
hydro_mwh
other_mwh
france_mwh
ireland_mwh
netherlands_mwh
biomass_mwh
belgium_mwh
norway_mwh
denmark_mw
total_generation_mwh
fossil_fuel_percentage_generation
renewable_percentage_generation
low_carbon_percentage_generation
low_carbon_with_biomass_percentage_generation
other_percentage_generation
grid_collection_time
last_update
```

### Day Ahead Solar Forecast
Thirty minute day ahead solar forecast

Name - Solar Forecast\
ID - sensor.national_grid_solar_forecast\
State - Current forecast value\
Attributes:
```
forecast:
    - start_time: ...
      generation: ...
...
last_update
```

### Wind Forecast Entity
Hourly forecast from 20:00 (UTC) on the current day to 20:00 (GMT) on day + 2

Name - Wind Forecast\
ID - sensor.national_grid_wind_forecast\
State - Current hour forecast\
Attributes:
```
forecast:
    - start_time: ...
      generation: ...
...
last_update
```

### Wind Forecast Earliest Entity
Hourly forecast from 20:00 (UTC) on the current day to 20:00 (GMT) on day + 2
This is however, the first forecast obtained for this period, not the latest update

Name - Wind Forecast Earlist\
ID - sensor.national_grid_wind_forecast_earliest\
State - Current hour earliest forecast\
Attributes:
```
forecast:
    - start_time: ...
      generation: ...
...
```

### Wind Forecast Now To Three Day Entity
Thirty minute long term wind forecast - From now to three days ahead

Name - Wind Forecast Now To Three Day\
ID - sensor.national_grid_now_to_three_day_wind_forecast\
State - None\
Attributes:
```
forecast:
    - start_time: ...
      generation: ...
...
```

### Wind Forecast Fourteen Day Entity
Two-hourly long term wind forecast - From now to fourteen days ahead

Name - Wind Forecast Fourteen Day\
ID - sensor.national_grid_fourteen_day_wind_forecast\
State - None\
Attributes:
```
forecast:
    - start_time: ...
      generation: ...
...
```

### Embedded Wind Forecast Three Day
Thirty minute long term wind forecast - From now to three days ahead

Name - Embedded Wind Forecast Three Day\
ID - sensor.national_grid_embedded_wind_forecast_three_day\
State - Closest forecasted value to 'now'
Attributes:
```
current_value:
forecast:
    - start_time: ...
      generation: ...
...
```

### Embedded Wind Forecast Fourteen Day
Two-hourly long term wind forecast - From now to fourteen days ahead

Name - Embedded Wind Forecast Fourteen Day\
ID - sensor.national_grid_embedded_wind_forecast_fourteen_day\
State - Closest forecasted value to 'now'
Attributes:
```
current_value:
forecast:
    - start_time: ...
      generation: ...
...
```

### Embedded Solar Forecast Three Day
Thirty minute long term wind forecast - From now to three days ahead

Name - Embedded Solar Forecast Three Day\
ID - sensor.national_grid_embedded_solar_forecast_three_day\
State - Closest forecasted value to 'now'
Attributes:
```
current_value:
forecast:
    - start_time: ...
      generation: ...
...
```

### Embedded Solar Forecast Fourteen Day Entity
Two-hourly long term solar forecast - From now to fourteen days ahead

Name - Embedded Solar Forecast Fourteen Day\
ID - sensor.national_grid_embedded_solar_forecast_fourteen_day\
State - Closest forecasted value to 'now'
Attributes:
```
current_value:
forecast:
    - start_time: ...
      generation: ...
...
```

### National Grid Grid Demand Day Ahead Forecast Entity
Thirty minute day ahead demand forecast

Name - Grid Demand Day Ahead Forecast
ID - sensor.national_grid_grid_demand_day_ahead_forecast
State - Closest forecasted value to 'now'
Attributes:
```
current_value:
forecast:
    - start_time: ...
      transmission_demand: ...
      national_demand: ...
...
```

### National Grid Grid Demand Three Day Forecast Entity
Thirty minute three day demand forecast

Name - Grid Demand Three Day Forecast
ID - sensor.national_grid_grid_demand_three_day_forecast
State - Closest forecasted value to 'now'
Attributes:
```
current_value:
forecast:
    - start_time: ...
      national_demand: ...
...
```

### National Grid Grid Demand Fourteen Day Forecast Entity
Two hourly fourteen day demand forecast

Name - Grid Demand Fourteen Day Forecast
ID - sensor.national_grid_grid_demand_fourteen_day_forecast
State - Closest forecasted value to 'now'
Attributes:
```
current_value:
forecast:
    - start_time: ...
      national_demand: ...
...
```

### National Grid DFS Requirements Entity
National Grid DFS Requirements - Shows last 10 only

Name - National Grid DFS Requirements\
ID - sensor.national_grid_dfs_requirements\
State - National Grid DFS Requirements\
Attributes:
```
requirements:
    - start_time: ...
      end_time: ...
      required_mw: ...
      requirement_type: ...
      despatch_type: ...
      participants_eligible:
        - ...
...
last_update
```

### Forecast Margin Entity
Daily operating margin forecast showing the headroom between available supply and predicted demand.

Name - Forecast Margin\
ID - sensor.national_grid_forecast_margin\
State - Current margin value in MW\
Attributes:
```
forecast:
    - date: "2024-01-15"
      margin: 5200
    - date: "2024-01-16"
      margin: 4800
...
last_update
```

### System Warning Entity
Current grid system warning status. Shows the type of any active warning or "None" when grid is operating normally.

Name - System Warning\
ID - sensor.national_grid_system_warning\
State - Warning type (e.g., "Electricity Margin Notice") or "None"\
Attributes:
```
warnings:
    - type: "Electricity Margin Notice"
      message: "..."
      published: "2024-01-15T18:00:00Z"
...
last_update
```

### Margin Warning Active Entity
Binary sensor that indicates when a margin warning is currently active on the grid.

Name - Margin Warning Active\
ID - binary_sensor.national_grid_margin_warning_active\
State - on/off\
Attributes:
```
last_update
```

### Carbon Intensity Forecast Entity
48-hour carbon intensity forecast with half-hourly resolution.

Name - Carbon Intensity Forecast\
ID - sensor.national_grid_carbon_intensity_forecast\
State - Current carbon intensity value in gCO2/kWh\
Attributes:
```
forecast:
    - from: "2024-01-15T12:00Z"
      to: "2024-01-15T12:30Z"
      intensity: 185
      index: "moderate"
    - from: "2024-01-15T12:30Z"
      to: "2024-01-15T13:00Z"
      intensity: 178
      index: "moderate"
...
last_update
```

### Carbon Intensity Index Entity
Current carbon intensity level categorisation.

Name - Carbon Intensity Index\
ID - sensor.national_grid_carbon_intensity_index\
State - Intensity level (very low, low, moderate, high, very high)\
Attributes:
```
last_update
```

### Regional Carbon Intensity Entity
Regional carbon intensity data. Only available when a region is configured during setup.

Name - Regional Carbon Intensity\
ID - sensor.national_grid_regional_carbon_intensity\
State - Current regional carbon intensity in gCO2/kWh\
Attributes:
```
region: "South England"
last_update
```

### Regional Carbon Index Entity
Regional carbon intensity level. Only available when a region is configured during setup.

Name - Regional Carbon Index\
ID - sensor.national_grid_regional_carbon_index\
State - Intensity level (very low, low, moderate, high, very high)\
Attributes:
```
region: "South England"
last_update
```

## Uses / Examples
This section outlines some graphs / views I have personally created with the data provided by the integration.

![Example 1 screenshot](docs/assets/example1.png)
![Example 2 screenshot](docs/assets/example2.png)
![Example 3 screenshot](docs/assets/example3.png)
![Example 4 screenshot](docs/assets/example4.png)
![Example 5 screenshot](docs/assets/example5.png)
![Example 6 screenshot](docs/assets/example6.png)

## Data Sources

### BMRS - Balancing Mechanism Reporting Service
An Elexon developed API responsible for reporting power generation, interconnectors, pricing and wind forecasting.\
Data is provided from their newer API which provides data in a JSON format (but optionally others too).

### Carbon Itensity API
A National Grid ESO API developed in partner ship with the University of Oxford is responsible for reporting the carbon intensity of power generation in the UK in grams of carbon dioxide per kilowatt hour.\
Data is provided in JSON format.

### National Grid ESO API
A National Grid ESO API responsible for estimating power generation from embedded solar and wind. This is required as BMRS only reports main grid generation, embedded generation is not counted. Embedded generation being the generation connected to local distribution networks rather than the national transmission network.
