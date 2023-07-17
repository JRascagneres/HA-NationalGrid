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
    now_utc_formatted_datetime = now_utc_full.strftime("%Y-%m-%d %H:%M:%S")
    two_hours_ago_utc_formatted_datetime = (now_utc_full - timedelta(hours=2)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    wind_forecast = get_hourly_wind_forecast(today_full)

    try:
        carbon_intensity = get_carbon_intensity(now_utc_full)
    except Exception as e:  # pylint: disable=broad-except
        _LOGGER.exception("Failed to obtain carbon itensity data")
        carbon_intensity = get_data_if_exists(current_data, "carbon_intensity")

    try:
        grid_generation = get_generation(
            api_key, two_hours_ago_utc_formatted_datetime, now_utc_formatted_datetime
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
        wind_data = get_wind_data(api_key, today, tomorrow)
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
                start_time=datetime.strptime(item["startTime"], "%Y-%m-%dT%H:%M:%SZ"),
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


def get_wind_data(api_key: str, today: str, tomorrow: str) -> NationalGridWindData:
    url = "https://api.bmreports.com/BMRS/WINDFORPK/v1?APIKey=" + api_key
    items = get_bmrs_data_items(url)

    todayIdx = None
    tomorrowIdx = None
    for idx, item in enumerate(items):
        if item["dayAndDate"] == today:
            todayIdx = idx
        if item["dayAndDate"] == tomorrow:
            tomorrowIdx = idx

    today_peak = items[0]["peakMaxGeneration"]
    tomorrow_peak = items[1]["peakMaxGeneration"]

    today_peak_time = datetime.strptime(
        items[0]["dayAndDate"] + items[0]["startTimeOfHalfHrPeriod"], "%Y-%m-%d%H:%M"
    )
    tomorrow_peak_time = datetime.strptime(
        items[1]["dayAndDate"] + items[1]["startTimeOfHalfHrPeriod"], "%Y-%m-%d%H:%M"
    )

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
    response = requests.get(url, timeout=10)
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


def get_generation(
    api_key: str, from_datetime: str, to_datetime: str
) -> NationalGridGeneration:
    url = (
        "https://api.bmreports.com/BMRS/FUELINST/v1?APIKey="
        + api_key
        + "&FromDateTime="
        + from_datetime
        + "&ToDateTime="
        + to_datetime
    )
    latestItem = get_bmrs_data_latest(url)
    grid_collection_time = datetime.strptime(
        latestItem["publishingPeriodCommencingTime"], "%Y-%m-%d %H:%M:%S"
    )
    grid_collection_time = grid_collection_time.replace(tzinfo=tz.tzutc())
    grid_collection_time = grid_collection_time.astimezone(tz=dt_util.now().tzinfo)

    url = "https://api.bmreports.com/BMRS/INTERFUELHH/v1?APIKey=" + api_key
    latest_interconnectors_item = get_bmrs_data_latest(url)

    return NationalGridGeneration(
        gas_mwh=int(latestItem["ccgt"]) + int(latestItem["ocgt"]),
        oil_mwh=int(latestItem["oil"]),
        coal_mwh=int(latestItem["coal"]),
        biomass_mwh=int(latestItem["biomass"]),
        nuclear_mwh=int(latestItem["nuclear"]),
        wind_mwh=int(latestItem["wind"]),
        solar_mwh=0,
        pumped_storage_mwh=int(latestItem["ps"]),
        hydro_mwh=int(latestItem["npshyd"]),
        other_mwh=int(latestItem["other"]),
        france_mwh=int(latest_interconnectors_item["intfrGeneration"])
        + int(latest_interconnectors_item["intelecGeneration"])
        + int(latest_interconnectors_item["intifa2Generation"]),
        ireland_mwh=int(latest_interconnectors_item["intirlGeneration"])
        + int(latest_interconnectors_item["intewGeneration"]),
        netherlands_mwh=int(latest_interconnectors_item["intnedGeneration"]),
        belgium_mwh=int(latest_interconnectors_item["intnemGeneration"]),
        norway_mwh=int(latest_interconnectors_item["intnslGeneration"]),
        grid_collection_time=grid_collection_time,
    )


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
