from datetime import datetime
from typing import TypedDict


class NationalGridGeneration(TypedDict):
    gas_mwh: int  # ccgt + ocgt
    oil_mwh: int  # oil
    coal_mwh: int  # coal
    biomass_mwh: int  # biomass
    nuclear_mwh: int  # nuclear
    wind_mwh: int  # wind
    solar_mwh: int  # solar
    national_wind_mwh: int  # wind plugged into national transmission network
    embedded_wind_mwh: int  # wind plugged into local distribution networks
    pumped_storage_mwh: int  # ps - pumped storage
    hydro_mwh: int  # npshyd - non pumped storage hydro plant
    other_mwh: int  # other - undefined
    france_mwh: int  # intfr ( IFA ) + intelec ( ElecLink ) + intifa2 ( IFA2 )
    ireland_mwh: int  # intirl ( Moyle ) + intew ( East-West )
    netherlands_mwh: int  # intned ( Brit Ned )
    belgium_mwh: int  # intnem ( Nemo )
    norway_mwh: int  # intnsl ( North Sea Link )
    total_generation_mwh: int  # total generation
    fossil_fuel_percentage_generation: int  # Counts gas, oil, coal
    renewable_percentage_generation: int  # Counts solar, wind, hydro
    low_carbon_percentage_generation: int  # Counts renewable, nuclear
    low_carbon_with_biomass_percentage_generation: int  # Counts renewable, nuclear, biomass
    other_percentage_generation: int  # Counts nuclear, biomass
    grid_collection_time: datetime


class NationalGridWindData(TypedDict):
    today_peak: float
    tomorrow_peak: float
    today_peak_time: datetime
    tomorrow_peak_time: datetime


class NationalGridWindForecastItem(TypedDict):
    start_time: datetime
    generation: int


class NationalGridWindForecast(TypedDict):
    current_value: int
    forecast: list[NationalGridWindForecastItem]


class NationalGridWindForecastLongTerm(TypedDict):
    forecast: list[NationalGridWindForecastItem]


class NationalGridSolarForecastItem(TypedDict):
    start_time: datetime
    generation: int


class NationalGridSolarForecast(TypedDict):
    current_value: int
    forecast: list[NationalGridSolarForecastItem]


class NationalGridData(TypedDict):
    sell_price: float
    carbon_intensity: int
    wind_data: NationalGridWindData
    wind_forecast: NationalGridWindForecast
    wind_forecast_earliest: NationalGridWindForecast
    now_to_three_wind_forecast: NationalGridWindForecastLongTerm
    fourteen_wind_forecast: NationalGridWindForecastLongTerm
    solar_forecast: NationalGridSolarForecast
    three_embedded_solar: NationalGridSolarForecast
    fourteen_embedded_solar: NationalGridSolarForecast
    three_embedded_wind: NationalGridWindForecast
    fourteen_embedded_wind: NationalGridWindForecast
    grid_generation: NationalGridGeneration
    total_demand_mwh: int
    total_transfers_mwh: int
