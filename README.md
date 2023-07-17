# National Grid Home Assistant Integration
Custom component providing information about the UK National Grid

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
An API key first must be obtained for the BMRS API:
1. Register [here](https://www.elexonportal.co.uk/)
2. 'Register now' in the top right and follow the standard process
3. Once the account is created login and you'll see 'My Portal' banner open.
4. Inside the 'My Portal' banner click 'My Profile' - your API key is the 'Scripting Key'

Then follow the same steps that are using to setup most integrations:
1. Head to settings then Devices & Services
2. Click 'Add Integration' in the bottom right
3. Search for 'National Grid'
4. Enter API Key and hit Submit
5. Your device and entities will be created

## Sensors
| Name | ID | Description |
| ---- | -- | ----------- |
| National Grid Current Sell Price | sensor.national_grid_current_sell_price | Current balancing price of Grid |
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
| National Grid Grid Generation Belgium MWh | sensor.national_grid_grid_generation_belgium_mwh | Current electricity generation from France interconnectors in MWh |
| National Grid Grid Generation France MWh | sensor.national_grid_grid_generation_france_mwh | Current electricity generation from Belgium interconnectors in MWh |
| National Grid Grid Generation Norway MWh | sensor.national_grid_grid_generation_norway_mwh | Current electricity generation from Norway interconnectors in MWh |

Note that the associated time sensors are important. Updates can lag by a few minutes and are in UTC so its possible that 'today' and 'tomorrow' aren't entirely accurate for a period of time.

### Grid Generation Entity

Name - Grid Generation\
ID - national_grid.grid_generation\
State - Temporary "Grid Generation"\
Attributes:
```
gas_mwh
oil_mwh
coal_mwh
nuclear_mwh
wind_mwh
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
grid_collection_time
```

### Wind Forecast Entity

Name - Wind Forecast\
ID - national_grid.wind_forecast\
State - Temporary "Wind Forecast"\
Attributes:
```
forecast:
    - start_time: ...
      generation: ...

...
```
