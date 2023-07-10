from __future__ import annotations
from collections import OrderedDict

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
    nuclear_mwh: int  # nuclear
    wind_mwh: int  # wind
    pumped_storage_mwh: int  # ps - pumped storage
    hydro_mwh: int  # npshyd - non pumped storage hydro plant
    other_mwh: int  # other - undefined
    france_mwh: int  # intfr ( IFA ) + intelec ( ElecLink ) + intifa2 ( IFA2 )
    ireland_mwh: int  # intirl ( Moyle ) + intew ( East-West )
    netherlands_mwh: int  # intned ( Brit Ned )
    biomass_mwh: int  # biomass
    belgium_mwh: int  # intnem ( Nemo )
    norway_mwh: int  # intnsl ( North Sea Link )
    gridCollectionTime: datetime


class NationalGridWindData(TypedDict):
    todayPeak: float
    tomorrowPeak: float
    todayPeakTime: datetime
    tomorrowPeakTime: datetime


class NationalGridData(TypedDict):
    """Data field"""

    sellPrice: float
    windData: NationalGridWindData
    gridGeneration: NationalGridGeneration


class NationalGridCoordinator(DataUpdateCoordinator[NationalGridData]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize"""
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=timedelta(minutes=1)
        )
        self._entry = entry

    @property
    def entry_id(self) -> str:
        return self._entry.entry_id

    async def _async_update_data(self) -> NationalGridData:
        try:
            data = await self.hass.async_add_executor_job(
                get_data, self.hass, self._entry.data
            )
        except:
            raise Exception()  # pylint: disable=broad-exception-raised

        return data


def get_data(hass: HomeAssistant, config: Mapping[str, Any]) -> NationalGridData:
    api_key = config[CONF_API_KEY]
    _LOGGER.info(api_key)

    today_utc = dt_util.utcnow().strftime("%Y-%m-%d")

    today = dt_util.now().strftime("%Y-%m-%d")
    tomorrow = (dt_util.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    currentPrice = get_current_price(api_key, today_utc)
    windData = get_wind_data(api_key, today, tomorrow)
    grid_generation = get_generation(api_key)

    return NationalGridData(
        sellPrice=currentPrice,
        windData=windData,
        gridGeneration=grid_generation,
    )


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

    # if todayIdx == None or tomorrowIdx == None:

    todayPeak = items[0]["peakMaxGeneration"]
    tomorrowPeak = items[1]["peakMaxGeneration"]

    todayPeakTime = datetime.strptime(
        items[0]["dayAndDate"] + items[0]["startTimeOfHalfHrPeriod"], "%Y-%m-%d%H:%M"
    )
    tomorrowPeakTime = datetime.strptime(
        items[1]["dayAndDate"] + items[1]["startTimeOfHalfHrPeriod"], "%Y-%m-%d%H:%M"
    )

    return NationalGridWindData(
        todayPeak=todayPeak,
        tomorrowPeak=tomorrowPeak,
        todayPeakTime=todayPeakTime,
        tomorrowPeakTime=tomorrowPeakTime,
    )


def get_generation(api_key: str) -> NationalGridGeneration:
    url = "https://api.bmreports.com/BMRS/FUELINST/v1?APIKey=" + api_key
    latestItem = get_bmrs_data_latest(url)
    gridCollectionTime = datetime.strptime(
        latestItem["publishingPeriodCommencingTime"], "%Y-%m-%d %H:%M:%S"
    )
    gridCollectionTime = gridCollectionTime.replace(tzinfo=tz.tzutc())
    gridCollectionTime = gridCollectionTime.astimezone(tz=dt_util.now().tzinfo)

    url = "https://api.bmreports.com/BMRS/INTERFUELHH/v1?APIKey=" + api_key
    latest_interconnectors_item = get_bmrs_data_latest(url)

    return NationalGridGeneration(
        gas_mwh=int(latestItem["ccgt"]) + int(latestItem["ocgt"]),
        oil_mwh=int(latestItem["oil"]),
        coal_mwh=int(latestItem["coal"]),
        nuclear_mwh=int(latestItem["nuclear"]),
        wind_mwh=int(latestItem["wind"]),
        pumped_storage_mwh=int(latestItem["ps"]),
        hydro_mwh=int(latestItem["npshyd"]),
        other_mwh=int(latestItem["other"]),
        france_mwh=int(latest_interconnectors_item["intfrGeneration"])
        + int(latest_interconnectors_item["intelecGeneration"])
        + int(latest_interconnectors_item["intifa2Generation"]),
        ireland_mwh=int(latest_interconnectors_item["intirlGeneration"])
        + int(latest_interconnectors_item["intewGeneration"]),
        netherlands_mwh=int(latest_interconnectors_item["intnedGeneration"]),
        biomass_mwh=int(latestItem["biomass"]),
        belgium_mwh=int(latest_interconnectors_item["intnemGeneration"]),
        norway_mwh=int(latest_interconnectors_item["intnslGeneration"]),
        gridCollectionTime=gridCollectionTime,
    )


def get_bmrs_data(url: str) -> OrderedDict[str, Any]:
    response = requests.get(url, timeout=5)
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
