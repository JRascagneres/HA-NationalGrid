from __future__ import annotations
from collections import OrderedDict
import csv, urllib.request
import io

import json
import logging
from datetime import datetime, timedelta, timezone
from time import strftime
from typing import Any, TypedDict

import requests
import xmltodict
from _collections_abc import Mapping
from dateutil import tz

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import DOMAIN

PLATFORMS = [Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Setup National Grid from config entry"""
    coodinator = NationalGridCoordinator(hass, entry)
    await coodinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coodinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


class NationalGridError(HomeAssistantError):
    """Base error"""


class InvalidAuthError(NationalGridError):
    """Invalid auth"""


class NationalGridGeneration(TypedDict):
    gas_mwh: int  # ccgt + ocgt
    oil_mwh: int  # oil
    coal_mwh: int  # coal
    biomass_mwh: int  # biomass
    nuclear_mwh: int  # nuclear
    wind_mwh: int  # wind
    solar_mwh: int  # solar
    pumped_storage_mwh: int  # ps - pumped storage
    hydro_mwh: int  # npshyd - non pumped storage hydro plant
    other_mwh: int  # other - undefined
    france_mwh: int  # intfr ( IFA ) + intelec ( ElecLink ) + intifa2 ( IFA2 )
    ireland_mwh: int  # intirl ( Moyle ) + intew ( East-West )
    netherlands_mwh: int  # intned ( Brit Ned )
    belgium_mwh: int  # intnem ( Nemo )
    norway_mwh: int  # intnsl ( North Sea Link )
    grid_collection_time: datetime


class NationalGridWindData(TypedDict):
    today_peak: float
    tomorrow_peak: float
    today_peak_time: datetime
    tomorrow_peak_time: datetime


class NationalGridData(TypedDict):
    sell_price: float
    carbon_intensity: int
    wind_data: NationalGridWindData
    wind_forecast: NationalGridWindForecast
    grid_generation: NationalGridGeneration


class NationalGridWindForecast(TypedDict):
    forecast: list[NationalGridWindForecastItem]


class NationalGridWindForecastItem(TypedDict):
    start_time: datetime
    generation: int


class NationalGridCoordinator(DataUpdateCoordinator[NationalGridData]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize"""
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=timedelta(minutes=5)
        )
        self._entry = entry

    @property
    def entry_id(self) -> str:
        return self._entry.entry_id

    async def _async_update_data(self) -> NationalGridData:
        try:
            data = await self.hass.async_add_executor_job(
                get_data, self.hass, self._entry.data, self.data
            )
        except:
            raise Exception()  # pylint: disable=broad-exception-raised

        return data


def get_data(
    hass: HomeAssistant, config: Mapping[str, Any], current_data: NationalGridData
) -> NationalGridData:
    api_key = config[CONF_API_KEY]

    today_utc = dt_util.utcnow().strftime("%Y-%m-%d")

    today = dt_util.now().strftime("%Y-%m-%d")
    tomorrow = (dt_util.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    today_full = dt_util.now()

    now_utc_full = dt_util.utcnow()

    wind_forecast = get_hourly_wind_forecast(today_full)

    try:
        carbon_intensity = get_carbon_intensity(now_utc_full)
    except Exception as e:  # pylint: disable=broad-except
        _LOGGER.exception("Failed to obtain carbon itensity data")
        carbon_intensity = get_data_if_exists(current_data, "carbon_intensity")

    try:
        grid_generation = get_generation(
            now_utc_full,
        )

        national_grid_data = get_national_grid_data(today_utc, now_utc_full)
        if national_grid_data is not None:
            grid_generation["wind_mwh"] += int(
                national_grid_data["EMBEDDED_WIND_GENERATION"]
            )
            grid_generation["solar_mwh"] = int(
                national_grid_data["EMBEDDED_SOLAR_GENERATION"]
            )
    except Exception as e:  # pylint: disable=broad-except
        _LOGGER.exception("Failed to obtain grid generation data")
        grid_generation = get_data_if_exists(current_data, "grid_generation")

    try:
        current_price = get_current_price(api_key, today_utc)
    except Exception as e:  # pylint: disable=broad-except
        _LOGGER.exception("Failed to obtain current price")
        current_price = get_data_if_exists(current_data, "sell_price")

    try:
        wind_data = get_wind_data(today, tomorrow)
    except Exception as e:  # pylint: disable=broad-except
        _LOGGER.exception("Failed to obtain wind data")
        wind_data = get_data_if_exists(current_data, "wind_data")

    return NationalGridData(
        sell_price=current_price,
        carbon_intensity=carbon_intensity,
        wind_data=wind_data,
        wind_forecast=wind_forecast,
        grid_generation=grid_generation,
    )


def get_data_if_exists(data, key: str):
    if data is None:
        _LOGGER.error("Previous data is None, returning None")
        return None
    if key in data:
        _LOGGER.error("Returning previous data")
        return data[key]

    return None


def get_hourly_wind_forecast(now: datetime) -> NationalGridWindForecast:
    start_time = now.replace(hour=20, minute=00, second=00, microsecond=00)

    if start_time > now:
        start_time = start_time - timedelta(days=1)

    start_time_formatted = start_time.strftime("%Y-%m-%dT%H:%M:%S")
    end_time_formatted = (start_time + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%S")

    url = (
        "https://data.elexon.co.uk/bmrs/api/v1/forecast/generation/wind/latest?from="
        + start_time_formatted
        + "&to="
        + end_time_formatted
        + "&format=json"
    )
    response = requests.get(url, timeout=10)
    item_list = json.loads(response.content)["data"]

    wind_forecast = []

    for item in item_list:
        wind_forecast.append(
            NationalGridWindForecastItem(
                start_time=datetime.strptime(item["startTime"], "%Y-%m-%dT%H:%M:%S%z"),
                generation=int(item["generation"]),
            )
        )

    return NationalGridWindForecast(forecast=wind_forecast)


def get_current_price(api_key: str, today_utc: str) -> float:
    url = (
        "https://api.bmreports.com/BMRS/DERSYSDATA/v1?APIKey="
        + api_key
        + "&FromSettlementDate="
        + today_utc
        + "&ToSettlementDate="
        + today_utc
        + "&SettlementPeriod=*"
    )
    latestResponse = get_bmrs_data_latest(url)
    currentPrice = round(float(latestResponse["systemSellPrice"]), 2)
    return currentPrice


def get_wind_data(today: str, tomorrow: str) -> NationalGridWindData:
    url = "https://data.elexon.co.uk/bmrs/api/v1/forecast/generation/wind/peak?format=json"
    response = requests.get(url, timeout=10)
    items = json.loads(response.content)["data"]

    todayIdx = None
    tomorrowIdx = None
    for idx, item in enumerate(items):
        if item["settlementDate"] == today:
            todayIdx = idx
        if item["settlementDate"] == tomorrow:
            tomorrowIdx = idx

    today_peak = items[0]["generation"]
    tomorrow_peak = items[1]["generation"]

    today_peak_time = datetime.strptime(items[0]["startTime"], "%Y-%m-%dT%H:%M:%S%z")
    tomorrow_peak_time = datetime.strptime(items[1]["startTime"], "%Y-%m-%dT%H:%M:%S%z")

    return NationalGridWindData(
        today_peak=today_peak,
        tomorrow_peak=tomorrow_peak,
        today_peak_time=today_peak_time,
        tomorrow_peak_time=tomorrow_peak_time,
    )


def get_national_grid_data(today_utc: str, now_utc: datetime) -> dict[str, Any]:
    today_minutes = now_utc.hour * 60 + now_utc.minute
    settlement_period = today_minutes // 30

    url = "https://data.nationalgrideso.com/backend/dataset/7a12172a-939c-404c-b581-a6128b74f588/resource/177f6fa4-ae49-4182-81ea-0c6b35f26ca6/download/demanddataupdate.csv"
    response = requests.get(url, timeout=20)
    response_data = response.content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(response_data))
    for row in reader:
        if (
            row["SETTLEMENT_DATE"] == today_utc
            and int(row["SETTLEMENT_PERIOD"]) == settlement_period
        ):
            return row

    return None


def get_carbon_intensity(now_utc_full: datetime) -> int:
    formatted_datetime = now_utc_full.strftime("%Y-%m-%dT%H:%MZ")
    url = (
        "https://api.carbonintensity.org.uk/intensity/" + formatted_datetime + "/pt24h"
    )
    response = requests.get(url, timeout=10)
    data = json.loads(response.content)
    for item in reversed(data["data"]):
        if item["intensity"]["actual"] is not None:
            return int(item["intensity"]["actual"])
    return None


def get_generation(utc_now: datetime) -> NationalGridGeneration:
    utc_now_formatted = utc_now.strftime("%Y-%m-%dT%H:%M:%SZ")
    ten_minutes_ago = (utc_now - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")

    url = (
        "https://data.elexon.co.uk/bmrs/api/v1/datasets/FUELINST?publishDateTimeFrom="
        + ten_minutes_ago
        + "&publishDateTimeTo="
        + utc_now_formatted
        + "&format=json"
    )
    response = requests.get(url, timeout=10)
    items = json.loads(response.content)["data"]

    latest_generation_time = items[0]["startTime"]
    latest_publish_time = items[0]["publishTime"]

    for item in items:
        if item["startTime"] > latest_generation_time:
            latest_generation_time = item["startTime"]
            latest_publish_time = item["publishTime"]

    # Initiate class where we need to
    national_grid_generation = NationalGridGeneration(
        gas_mwh=0,
        oil_mwh=0,
        coal_mwh=0,
        biomass_mwh=0,
        nuclear_mwh=0,
        wind_mwh=0,
        solar_mwh=0,
        pumped_storage_mwh=0,
        hydro_mwh=0,
        other_mwh=0,
        france_mwh=0,
        ireland_mwh=0,
        netherlands_mwh=0,
        belgium_mwh=0,
        norway_mwh=0,
        grid_collection_time=latest_publish_time,
    )

    check_count = 0

    for item in items:
        if item["startTime"] == latest_generation_time:
            generation = item["generation"]

            fuelType = item["fuelType"]
            if fuelType == "CCGT" or fuelType == "OCGT":
                national_grid_generation["gas_mwh"] += generation
            elif fuelType == "OIL":
                national_grid_generation["oil_mwh"] = generation
            elif fuelType == "COAL":
                national_grid_generation["coal_mwh"] = generation
            elif fuelType == "BIOMASS":
                national_grid_generation["biomass_mwh"] = generation
            elif fuelType == "NUCLEAR":
                national_grid_generation["nuclear_mwh"] = generation
            elif fuelType == "WIND":
                national_grid_generation["wind_mwh"] = generation
            elif fuelType == "PS":
                national_grid_generation["pumped_storage_mwh"] = generation
            elif fuelType == "NPSHYD":
                national_grid_generation["hydro_mwh"] = generation
            elif fuelType == "OTHER":
                national_grid_generation["other_mwh"] = generation
            elif fuelType == "INTFR" or fuelType == "INTELEC" or fuelType == "INTIFA2":
                national_grid_generation["france_mwh"] += generation
            elif fuelType == "INTIRL" or fuelType == "INTEW":
                national_grid_generation["ireland_mwh"] += generation
            elif fuelType == "INTNED":
                national_grid_generation["netherlands_mwh"] = generation
            elif fuelType == "INTNEM":
                national_grid_generation["belgium_mwh"] = generation
            elif fuelType == "INTNSL":
                national_grid_generation["norway_mwh"] = generation

    return national_grid_generation


def get_bmrs_data(url: str) -> OrderedDict[str, Any]:
    response = requests.get(url, timeout=10)
    data = xmltodict.parse(response.content)

    if int(data["response"]["responseMetadata"]["httpCode"]) == 403:
        raise InvalidAuthError

    return data


def get_bmrs_data_items(url: str) -> OrderedDict[str, Any]:
    data = get_bmrs_data(url)
    responseList = data["response"]["responseBody"]["responseList"]
    items = responseList["item"]
    if type(items) is not list:
        items = [items]

    return items


def get_bmrs_data_latest(url: str) -> OrderedDict[str, Any]:
    items = get_bmrs_data_items(url)
    latestResponse = items[len(items) - 1]

    return latestResponse
