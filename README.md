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

Note that the associated time sensors are important. Updates can lag by a few minutes and are in UTC so its possible that 'today' and 'tomorrow' aren't entirely accurate for a period of time.

### Grid Production Entity

Name - Grid Production\
ID - national_grid.grid_producton\
State - Temporary "Grid Generation"\
Attributes:
```
gas_mwh
oil_mwh
coal_mwh
nuclear_mwh
wind_mwh
pumped_storage_mwh
hydro_mwh
other_mwh
france_mwh
ireland_mwh
netherlands_mwh
biomass_mwh
belgium_mwh
norway_mwh
gridCollectionTime
```