from collections import OrderedDict
import csv
import dateutil
from datetime import datetime, timedelta
import io
import json
import logging
from typing import Any

from _collections_abc import Mapping
from dateutil import tz
import requests
import xmltodict

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from ..const import DOMAIN
from ..errors import InvalidAuthError, UnexpectedDataError, UnexpectedStatusCode
from ..models import (
    DFSRequirementItem,
    DFSRequirements,
    NationalGridData,
    NationalGridDemandDayAheadForecast,
    NationalGridDemandDayAheadForecastItem,
    NationalGridDemandForecast,
    NationalGridDemandForecastItem,
    NationalGridGeneration,
    NationalGridSolarForecast,
    NationalGridSolarForecastItem,
    NationalGridWindData,
    NationalGridWindForecast,
    NationalGridWindForecastItem,
    NationalGridWindForecastLongTerm,
)

_LOGGER = logging.getLogger(__name__)


class NationalGridCoordinator(DataUpdateCoordinator[NationalGridData]):
    """National Grid Data Coordinator."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=timedelta(minutes=5)
        )
        self._entry = entry

    @property
    def entry_id(self) -> str:
        """Return entry id."""
        return self._entry.entry_id

    async def _async_update_data(self) -> NationalGridData:
        try:
            data = await self.hass.async_add_executor_job(
                get_data, self.hass, self._entry.data, self.data
            )
        except:  # noqa: E722
            raise Exception()  # pylint: disable=broad-exception-raised  # noqa: B904

        return data


def get_data(
    hass: HomeAssistant, config: Mapping[str, Any], current_data: NationalGridData
) -> NationalGridData:
    """Get data."""

    yesterday_utc = (dt_util.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    today_utc = dt_util.utcnow().strftime("%Y-%m-%d")

    today = dt_util.now().strftime("%Y-%m-%d")
    tomorrow = (dt_util.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    now_utc_full = dt_util.utcnow()

    current_price = 0
    solar_forecast = None

    current_price = obtain_data_with_fallback(
        current_data,
        "sell_price",
        get_current_price,
        today_utc,
        yesterday_utc,
    )
    solar_forecast = obtain_data_with_fallback(
        current_data,
        "solar_forecast",
        get_half_hourly_solar_forecast,
        now_utc_full,
    )

    current_grid_frequency = obtain_data_with_fallback(
        current_data, "grid_frequency", get_current_frequency, now_utc_full
    )

    wind_forecast = obtain_data_with_fallback(
        current_data,
        "wind_forecast",
        get_hourly_wind_forecast,
        now_utc_full,
    )

    wind_forecast_earliest = obtain_data_with_fallback(
        current_data,
        "wind_forecast_earliest",
        get_hourly_wind_forecast_earliest,
        now_utc_full,
    )

    carbon_intensity = obtain_data_with_fallback(
        current_data, "carbon_intensity", get_carbon_intensity, now_utc_full
    )

    grid_generation = obtain_data_with_fallback(
        current_data,
        "grid_generation",
        get_generation_combined,
        now_utc_full,
        today_utc,
    )

    wind_data = obtain_data_with_fallback(
        current_data, "wind_data", get_wind_data, today, tomorrow
    )

    total_demand_mwh = obtain_data_with_fallback(
        current_data, "total_demand_mwh", get_demand, grid_generation
    )

    total_transfers_mwh = obtain_data_with_fallback(
        current_data, "transfers_mwh", get_transfers, grid_generation
    )

    long_term_wind_forecast = obtain_data_with_fallback(
        current_data,
        "long_term_wind_forecast",
        get_long_term_wind_forecast_eso_data,
        now_utc_full,
    )

    if long_term_wind_forecast is not None:
        three_day = long_term_wind_forecast[0]
        fourteen_day = long_term_wind_forecast[1]
    else:
        three_day = None
        fourteen_day = None

    long_term_embedded_wind_and_solar_forecast = obtain_data_with_fallback(
        current_data,
        "long_term_embedded_wind_and_solar_forecast",
        get_long_term_embedded_wind_and_solar_forecast,
        now_utc_full,
    )

    if long_term_embedded_wind_and_solar_forecast is not None:
        three_day_solar = long_term_embedded_wind_and_solar_forecast[0]
        solar = long_term_embedded_wind_and_solar_forecast[1]
        three_day_wind = long_term_embedded_wind_and_solar_forecast[2]
        wind = long_term_embedded_wind_and_solar_forecast[3]
    else:
        three_day_solar = None
        solar = None
        three_day_wind = None
        wind = None

    demand_day_ahead_forecast = obtain_data_with_fallback(
        current_data,
        "grid_demand_day_ahead_forecast",
        get_demand_day_ahead_forecast,
        now_utc_full,
    )

    dfs_requirements = obtain_data_with_fallback(
        current_data, "dfs_requirements", get_dfs_requirements
    )

    three_day_demand_and_fourteen_day_demand = obtain_data_with_fallback(
        current_data,
        "three_day_demand_and_fourteen_day_demand",
        get_demand_forecast,
        now_utc_full,
        demand_day_ahead_forecast,
    )

    if three_day_demand_and_fourteen_day_demand is not None:
        three_day_demand = three_day_demand_and_fourteen_day_demand[0]
        fourteen_day_demand = three_day_demand_and_fourteen_day_demand[1]
    else:
        three_day_demand = None
        fourteen_day_demand = None

    return NationalGridData(
        sell_price=current_price,
        carbon_intensity=carbon_intensity,
        grid_frequency=current_grid_frequency,
        wind_data=wind_data,
        wind_forecast=wind_forecast,
        wind_forecast_earliest=wind_forecast_earliest,
        now_to_three_wind_forecast=three_day,
        fourteen_wind_forecast=fourteen_day,
        long_term_wind_forecast=long_term_wind_forecast,
        solar_forecast=solar_forecast,
        three_embedded_solar=three_day_solar,
        fourteen_embedded_solar=solar,
        three_embedded_wind=three_day_wind,
        fourteen_embedded_wind=wind,
        long_term_embedded_wind_and_solar_forecast=long_term_embedded_wind_and_solar_forecast,
        grid_generation=grid_generation,
        grid_demand_day_ahead_forecast=demand_day_ahead_forecast,
        grid_demand_three_day_forecast=three_day_demand,
        grid_demand_fourteen_day_forecast=fourteen_day_demand,
        three_day_demand_and_fourteen_day_demand=three_day_demand_and_fourteen_day_demand,
        total_demand_mwh=total_demand_mwh,
        total_transfers_mwh=total_transfers_mwh,
        dfs_requirements=dfs_requirements,
    )


def get_data_if_exists(data, key: str):
    """Get data if exists."""
    if data is None:
        _LOGGER.error("Previous data is None, returning None")
        return None
    if key in data:
        _LOGGER.warning("Returning previous data")
        return data[key]

    return None


def get_hourly_wind_forecast(now_utc: datetime) -> NationalGridWindForecast:
    """Get hourly wind forecast."""
    # Need to calculate start. We want data from 8pm on current day to day+2 8pm... however, this is calculated every so often.
    # This means that day + 2 isn't calculated until 03:30 GMT

    start_time = now_utc

    # If before the forecast time set start day to previous day
    comparison = now_utc.replace(hour=3, minute=30)
    if now_utc < comparison:
        start_time = start_time - timedelta(days=1)

    start_time = start_time.replace(hour=00, minute=00, second=00)
    end_time = start_time + timedelta(days=2)
    end_time = end_time.replace(hour=20, minute=00, second=00)

    start_time = start_time - timedelta(days=1)

    # Get forecast from now to today + 2 days at 8pm
    start_time_formatted = start_time.strftime("%Y-%m-%dT%H:%M:%S")
    end_time_formatted = end_time.strftime("%Y-%m-%dT%H:%M:%S")

    current_hour = now_utc.replace(minute=0, second=0, microsecond=0)

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
    current_generation = 0

    for item in item_list:
        forecast_item_start_time = datetime.strptime(
            item["startTime"], "%Y-%m-%dT%H:%M:%S%z"
        )

        wind_forecast.append(
            NationalGridWindForecastItem(
                start_time=forecast_item_start_time,
                generation=int(item["generation"]),
            )
        )

        if forecast_item_start_time == current_hour:
            current_generation = int(item["generation"])

    if current_generation == 0:
        raise UnexpectedDataError("Hourly wind forecast 'current' is 0")

    return NationalGridWindForecast(
        forecast=wind_forecast, current_value=current_generation
    )


def get_hourly_wind_forecast_earliest(now_utc: datetime) -> NationalGridWindForecast:
    """Get hourly wind forecast."""
    # Need to calculate start. We want data from 8pm on current day to day+2 8pm... however, this is calculated every so often.
    # This means that day + 2 isn't calculated until 03:30 GMT

    start_time = now_utc

    # If before the forecast time set start day to previous day
    comparison = now_utc.replace(hour=3, minute=30)
    if now_utc < comparison:
        start_time = start_time - timedelta(days=1)

    start_time = start_time.replace(hour=00, minute=00, second=00)
    end_time = start_time + timedelta(days=2)
    end_time = end_time.replace(hour=20, minute=00, second=00)

    start_time = start_time - timedelta(days=1)

    # Get forecast from now to today + 2 days at 8pm
    start_time_formatted = start_time.strftime("%Y-%m-%dT%H:%M:%S")
    end_time_formatted = end_time.strftime("%Y-%m-%dT%H:%M:%S")

    current_hour = now_utc.replace(minute=0, second=0, microsecond=0)

    url = (
        "https://data.elexon.co.uk/bmrs/api/v1/forecast/generation/wind/earliest?from="
        + start_time_formatted
        + "&to="
        + end_time_formatted
        + "&format=json"
    )
    response = requests.get(url, timeout=10)
    item_list = json.loads(response.content)["data"]

    wind_forecast_earliest = []
    current_generation = 0

    for item in item_list:
        forecast_item_start_time = datetime.strptime(
            item["startTime"], "%Y-%m-%dT%H:%M:%S%z"
        )

        wind_forecast_earliest.append(
            NationalGridWindForecastItem(
                start_time=forecast_item_start_time,
                generation=int(item["generation"]),
            )
        )

        if forecast_item_start_time == current_hour:
            current_generation = int(item["generation"])

    if current_generation == 0:
        raise UnexpectedDataError("Earliest hourly wind forecast 'current' is 0")

    return NationalGridWindForecast(
        forecast=wind_forecast_earliest, current_value=current_generation
    )


def get_half_hourly_solar_forecast(now: datetime) -> NationalGridSolarForecast:
    """Get half hourly solar forecast."""
    nearest_30_minutes = now + (now.min.replace(tzinfo=now.tzinfo) - now) % timedelta(
        minutes=30
    )

    yesterday = now - timedelta(days=1)
    tomorrow = now + timedelta(days=1)
    day_after_tomorrow = now + timedelta(days=2)

    url = (
        "https://data.elexon.co.uk/bmrs/api/v1/forecast/generation/wind-and-solar/day-ahead?from="
        + yesterday.strftime("%Y-%m-%d")
        + "&to="
        + day_after_tomorrow.strftime("%Y-%m-%d")
        + "&processType=all"
        + "&settlementPeriodFrom=1"
        + "&settlementPeriodTo=50"
        + "&format=json"
    )

    response = requests.get(url, timeout=10)
    results = json.loads(response.content)["data"]

    unique_date_list = []
    forecast = []
    current_value = 0
    for item in results:
        if item["businessType"] != "Solar generation":
            continue

        settlementDate = item["settlementDate"]
        settlementPeriod = item["settlementPeriod"]

        unique_key = str(settlementDate) + str(settlementPeriod)
        if unique_key in unique_date_list:
            continue

        unique_date_list.append(unique_key)

        period_from_midnight = timedelta(minutes=30 * (int(settlementPeriod) - 1))

        start_time = (
            datetime.strptime(settlementDate, "%Y-%m-%d") + period_from_midnight
        ).replace(tzinfo=now.tzinfo)

        gen_value = int(float(item["quantity"]))

        forecast.append(
            NationalGridSolarForecastItem(start_time=start_time, generation=gen_value)
        )

        if start_time == nearest_30_minutes:
            current_value = gen_value

    forecast = sorted(forecast, key=lambda x: x["start_time"])

    return NationalGridSolarForecast(
        current_value=current_value,
        forecast=forecast,
    )


def get_current_price(today_utc: str, yesterday_utc: str) -> float:
    """Get current grid price."""
    url = (
        "https://data.elexon.co.uk/bmrs/api/v1/balancing/pricing/market-index?from="
        + yesterday_utc
        + "&to="
        + today_utc
        + "&settlementPeriodFrom=1"
        + "&settlementPeriodTo=50&dataProviders=APXMIDP&format=json"
    )

    response = requests.get(url, timeout=10)
    items = json.loads(response.content)["data"]
    if len(items) == 0:
        raise UnexpectedDataError(url)

    return round(float(items[0]["price"]), 2)


def get_current_frequency(now_utc: datetime) -> float:
    """Get current grid frequency."""
    url = (
        "https://data.elexon.co.uk/bmrs/api/v1/system/frequency?format=json&from="
        + (now_utc - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
        + "&to="
        + (now_utc + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    )

    response = requests.get(url, timeout=10)
    items = json.loads(response.content)["data"]

    if len(items) == 0:
        raise UnexpectedDataError(url)

    return float(items[len(items) - 1]["frequency"])


def get_wind_data(today: str, tomorrow: str) -> NationalGridWindData:
    """Get wind data."""
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


def get_demand_day_ahead_forecast(
    utc_now: datetime,
) -> NationalGridDemandDayAheadForecast:
    """Get demand day ahead forecast."""
    utc_now_formatted = utc_now.strftime("%Y-%m-%dT%H:%M:%SZ")
    two_days = (utc_now + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")

    nearest_30_minutes = utc_now + (
        utc_now.min.replace(tzinfo=utc_now.tzinfo) - utc_now
    ) % timedelta(minutes=30)

    url = (
        "https://data.elexon.co.uk/bmrs/api/v1/forecast/demand/day-ahead/latest?format=json&from="
        + utc_now_formatted
        + "&to="
        + two_days
        + "&boundary=N"
    )

    response = requests.get(url, timeout=10)
    items = json.loads(response.content)["data"]

    if len(items) == 0:
        raise UnexpectedDataError(url)

    current = 0
    forecast = []

    for item in items:
        transmission_demand = item["transmissionSystemDemand"]
        national_demand = item["nationalDemand"]
        start_time_datetime = datetime.strptime(
            item["startTime"], "%Y-%m-%dT%H:%M:%S%z"
        )

        if start_time_datetime == nearest_30_minutes:
            current = national_demand

        forecast.append(
            NationalGridDemandDayAheadForecastItem(
                start_time=start_time_datetime,
                transmission_demand=transmission_demand,
                national_demand=national_demand,
            )
        )

    return NationalGridDemandDayAheadForecast(
        current_value=current,
        forecast=forecast,
    )


def get_national_grid_data(today_utc: str, now_utc: datetime) -> dict[str, Any]:
    """Get national grid data."""
    today_minutes = now_utc.hour * 60 + now_utc.minute
    settlement_period = (today_minutes // 30) + 1

    url = "https://api.neso.energy/dataset/7a12172a-939c-404c-b581-a6128b74f588/resource/177f6fa4-ae49-4182-81ea-0c6b35f26ca6/download/demanddataupdate.csv"
    response = requests.get(url, timeout=20)

    if response.status_code != 200:
        raise UnexpectedStatusCode(
            url + " - " + "get_national_grid_data" + " - " + str(response.status_code)
        )

    response_data = response.content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(response_data))
    for row in reader:
        if (
            dateutil.parser.parse(row["SETTLEMENT_DATE"]).date() == now_utc.date()
            and int(row["SETTLEMENT_PERIOD"]) == settlement_period
        ):
            return row

    return None


def get_long_term_wind_forecast_eso_data(
    now: datetime,
) -> (
    NationalGridWindForecastLongTerm,
    NationalGridWindForecastLongTerm,
):
    """Get long term wind forecast."""
    url = "https://api.neso.energy/api/3/action/datastore_search?resource_id=93c3048e-1dab-4057-a2a9-417540583929&limit=32000"
    response = requests.get(url, timeout=20)

    if response.status_code != 200:
        raise UnexpectedStatusCode(
            url
            + " - "
            + "get_long_term_wind_forecast_eso_data"
            + " - "
            + str(response.status_code)
        )

    data = json.loads(response.content)

    # Get 7 day forecast. Will just do now + 7 days
    nearest_30_minutes = now + (now.min.replace(tzinfo=now.tzinfo) - now) % timedelta(
        minutes=30
    )
    in_three_days = nearest_30_minutes + timedelta(days=3)
    in_fourteen_days = nearest_30_minutes + timedelta(days=14)

    three_day_forecast = []
    fourteen_day_forecast = []

    current_forecast = 0

    all_records = data["result"]["records"]
    for record in all_records:
        formatted_datetime = datetime.strptime(
            record["Datetime"], "%Y-%m-%dT%H:%M:%S"
        ).replace(tzinfo=tz.UTC)
        forecast = int(record["Wind_Forecast"])

        if formatted_datetime == nearest_30_minutes:
            current_forecast = forecast

        if (
            formatted_datetime >= nearest_30_minutes
            and formatted_datetime <= in_three_days
        ):
            three_day_forecast.append(
                NationalGridWindForecastItem(
                    start_time=formatted_datetime,
                    generation=forecast,
                )
            )

        if (
            formatted_datetime >= nearest_30_minutes
            and formatted_datetime <= in_fourteen_days
            and (
                hour_minute_check(formatted_datetime, 0, 0)
                or hour_minute_check(formatted_datetime, 2, 0)
                or hour_minute_check(formatted_datetime, 4, 0)
                or hour_minute_check(formatted_datetime, 6, 0)
                or hour_minute_check(formatted_datetime, 8, 0)
                or hour_minute_check(formatted_datetime, 10, 0)
                or hour_minute_check(formatted_datetime, 12, 0)
                or hour_minute_check(formatted_datetime, 14, 0)
                or hour_minute_check(formatted_datetime, 16, 0)
                or hour_minute_check(formatted_datetime, 18, 0)
                or hour_minute_check(formatted_datetime, 20, 0)
                or hour_minute_check(formatted_datetime, 22, 0)
            )
        ):
            fourteen_day_forecast.append(
                NationalGridWindForecastItem(
                    start_time=formatted_datetime, generation=forecast
                )
            )

    if len(three_day_forecast) == 0 or len(fourteen_day_forecast) == 0:
        raise UnexpectedDataError("Long term wind forecast is empty")

    three_day = NationalGridWindForecastLongTerm(forecast=three_day_forecast)

    fourteen_day = NationalGridWindForecastLongTerm(forecast=fourteen_day_forecast)

    return (three_day, fourteen_day)


def get_long_term_embedded_wind_and_solar_forecast(
    now: datetime,
) -> (
    NationalGridSolarForecast,
    NationalGridSolarForecast,
    NationalGridWindForecast,
    NationalGridWindForecast,
):
    """Get long term embedded wind and solar forecast."""
    url = "https://api.neso.energy/api/3/action/datastore_search?resource_id=db6c038f-98af-4570-ab60-24d71ebd0ae5&limit=32000"
    response = requests.get(url, timeout=20)

    if response.status_code != 200:
        raise UnexpectedStatusCode(
            url
            + " - "
            + "get_long_term_embedded_wind_and_solar_forecast"
            + " - "
            + str(response.status_code)
        )

    data = json.loads(response.content)

    nearest_30_minutes = now + (now.min.replace(tzinfo=now.tzinfo) - now) % timedelta(
        minutes=30
    )
    in_three_days = nearest_30_minutes + timedelta(days=3)
    in_fourteen_days = nearest_30_minutes + timedelta(days=14)

    three_day_solar_forecast = []
    three_day_wind_forecast = []

    solar_forecast = []
    wind_forecast = []

    current_solar_forecast = 0
    current_wind_forecast = 0

    all_records = data["result"]["records"]
    for record in all_records:
        formatted_datetime = datetime.strptime(
            record["DATE_GMT"], "%Y-%m-%dT%H:%M:%S"
        ).replace(tzinfo=tz.UTC)

        time = datetime.strptime(record["TIME_GMT"], "%H:%M").time()
        formatted_datetime = datetime.combine(formatted_datetime, time).replace(
            tzinfo=tz.UTC
        )

        solar_forecast_val = int(record["EMBEDDED_SOLAR_FORECAST"])
        wind_forecast_val = int(record["EMBEDDED_WIND_FORECAST"])

        if formatted_datetime == nearest_30_minutes:
            current_solar_forecast = solar_forecast_val
            current_wind_forecast = wind_forecast_val

        if (
            formatted_datetime >= nearest_30_minutes
            and formatted_datetime <= in_three_days
        ):
            three_day_solar_forecast.append(
                NationalGridSolarForecastItem(
                    start_time=formatted_datetime, generation=solar_forecast_val
                )
            )

            three_day_wind_forecast.append(
                NationalGridWindForecastItem(
                    start_time=formatted_datetime, generation=wind_forecast_val
                )
            )

        if (
            formatted_datetime >= nearest_30_minutes
            and formatted_datetime <= in_fourteen_days
            and (
                hour_minute_check(formatted_datetime, 0, 0)
                or hour_minute_check(formatted_datetime, 2, 0)
                or hour_minute_check(formatted_datetime, 4, 0)
                or hour_minute_check(formatted_datetime, 6, 0)
                or hour_minute_check(formatted_datetime, 8, 0)
                or hour_minute_check(formatted_datetime, 10, 0)
                or hour_minute_check(formatted_datetime, 12, 0)
                or hour_minute_check(formatted_datetime, 14, 0)
                or hour_minute_check(formatted_datetime, 16, 0)
                or hour_minute_check(formatted_datetime, 18, 0)
                or hour_minute_check(formatted_datetime, 20, 0)
                or hour_minute_check(formatted_datetime, 22, 0)
            )
        ):
            solar_forecast.append(
                NationalGridSolarForecastItem(
                    start_time=formatted_datetime, generation=solar_forecast_val
                )
            )

            wind_forecast.append(
                NationalGridWindForecastItem(
                    start_time=formatted_datetime, generation=wind_forecast_val
                )
            )

    if (
        len(three_day_solar_forecast) == 0
        or len(three_day_wind_forecast) == 0
        or len(solar_forecast) == 0
        or len(wind_forecast) == 0
    ):
        raise UnexpectedDataError("Long term embedded wind and solar forecast is empty")

    three_day_solar = NationalGridSolarForecast(
        current_value=current_solar_forecast, forecast=three_day_solar_forecast
    )
    three_day_wind = NationalGridWindForecast(
        current_value=current_wind_forecast, forecast=three_day_wind_forecast
    )

    solar = NationalGridSolarForecast(
        current_value=current_solar_forecast, forecast=solar_forecast
    )
    wind = NationalGridWindForecast(
        current_value=current_wind_forecast, forecast=wind_forecast
    )

    return (three_day_solar, solar, three_day_wind, wind)


def get_dfs_requirements() -> DFSRequirements:
    """Get DFS requirements."""
    url = "https://api.neso.energy/api/3/action/datastore_search?resource_id=f5605e2b-b677-424c-8df7-d0ce4ee03cef&sort=Delivery%20Date%20desc,From%20desc&limit=10"
    response = requests.get(url, timeout=20)

    if response.status_code != 200:
        raise UnexpectedStatusCode(
            url + " - " + "get_dfs_requirements" + " - " + str(response.status_code)
        )

    data = json.loads(response.content)

    all_requirements = []

    all_records = data["result"]["records"]
    for record in all_records:
        participants_eligible = record["Participant Bids Eligible"].split(",")

        start_time = datetime.strptime(
            record["Delivery Date"] + "T" + record["From"], "%Y-%m-%dT%H:%M"
        ).replace(tzinfo=tz.UTC)

        end_time = datetime.strptime(
            record["Delivery Date"] + "T" + record["To"], "%Y-%m-%dT%H:%M"
        ).replace(tzinfo=tz.UTC)

        all_requirements.append(
            DFSRequirementItem(
                start_time=start_time,
                end_time=end_time,
                required_mw=record["Service Requirement MW"],
                requirement_type=record["Service Requirement Type"],
                despatch_type=record["Dispatch Type"],
                participants_eligible=participants_eligible,
            )
        )

    dfs_requirements = DFSRequirements(requirements=all_requirements)

    return dfs_requirements


def get_demand_forecast(
    now: datetime, day_ahead_forecast: NationalGridDemandDayAheadForecast
) -> (NationalGridDemandForecast, NationalGridDemandForecast):
    """Get demand forecast."""
    url = "https://api.neso.energy/api/3/action/datastore_search?resource_id=7c0411cd-2714-4bb5-a408-adb065edf34d&limit=1000"
    response = requests.get(url, timeout=20)

    if response.status_code != 200:
        raise UnexpectedStatusCode(
            url + " - " + "get_demand_forecast" + " - " + str(response.status_code)
        )

    data = json.loads(response.content)

    nearest_30_minutes = now + (now.min.replace(tzinfo=now.tzinfo) - now) % timedelta(
        minutes=30
    )
    in_three_days = nearest_30_minutes + timedelta(days=3)
    in_fourteen_days = nearest_30_minutes + timedelta(days=14)

    three_day_forecast = []
    fourteen_day_forecast = []

    current_forecast = 0

    all_records = data["result"]["records"]

    first_record = all_records[0]
    first_record_datetime = datetime.strptime(
        first_record["GDATETIME"], "%Y-%m-%dT%H:%M:%S"
    ).replace(tzinfo=tz.UTC)

    # So this is a bit annoying, I want to include the first day too so we pull that from the other endpoint
    for item in day_ahead_forecast["forecast"]:
        if item["start_time"] < first_record_datetime:
            three_day_forecast.append(
                NationalGridDemandForecastItem(
                    start_time=item["start_time"],
                    national_demand=item["national_demand"],
                )
            )

            if (
                hour_minute_check(item["start_time"], 0, 0)
                or hour_minute_check(item["start_time"], 2, 0)
                or hour_minute_check(item["start_time"], 4, 0)
                or hour_minute_check(item["start_time"], 6, 0)
                or hour_minute_check(item["start_time"], 8, 0)
                or hour_minute_check(item["start_time"], 10, 0)
                or hour_minute_check(item["start_time"], 12, 0)
                or hour_minute_check(item["start_time"], 14, 0)
                or hour_minute_check(item["start_time"], 16, 0)
                or hour_minute_check(item["start_time"], 18, 0)
                or hour_minute_check(item["start_time"], 20, 0)
                or hour_minute_check(item["start_time"], 22, 0)
            ):
                fourteen_day_forecast.append(
                    NationalGridDemandForecastItem(
                        start_time=item["start_time"],
                        national_demand=item["national_demand"],
                    )
                )

    for record in all_records:
        formatted_datetime = datetime.strptime(
            record["GDATETIME"], "%Y-%m-%dT%H:%M:%S"
        ).replace(tzinfo=tz.UTC)

        if (
            formatted_datetime >= nearest_30_minutes
            and formatted_datetime <= in_three_days
        ):
            three_day_forecast.append(
                NationalGridDemandForecastItem(
                    start_time=formatted_datetime,
                    national_demand=record["NATIONALDEMAND"],
                )
            )

        if (
            formatted_datetime >= nearest_30_minutes
            and formatted_datetime <= in_fourteen_days
            and (
                hour_minute_check(formatted_datetime, 0, 0)
                or hour_minute_check(formatted_datetime, 2, 0)
                or hour_minute_check(formatted_datetime, 4, 0)
                or hour_minute_check(formatted_datetime, 6, 0)
                or hour_minute_check(formatted_datetime, 8, 0)
                or hour_minute_check(formatted_datetime, 10, 0)
                or hour_minute_check(formatted_datetime, 12, 0)
                or hour_minute_check(formatted_datetime, 14, 0)
                or hour_minute_check(formatted_datetime, 16, 0)
                or hour_minute_check(formatted_datetime, 18, 0)
                or hour_minute_check(formatted_datetime, 20, 0)
                or hour_minute_check(formatted_datetime, 22, 0)
            )
        ):
            fourteen_day_forecast.append(
                NationalGridDemandForecastItem(
                    start_time=formatted_datetime,
                    national_demand=record["NATIONALDEMAND"],
                )
            )

    for item in three_day_forecast:
        if item["start_time"] == nearest_30_minutes:
            current_forecast = item["national_demand"]

    three_day = NationalGridDemandForecast(
        current_value=current_forecast,
        forecast=three_day_forecast,
    )

    fourteen_day = NationalGridDemandForecast(
        current_value=current_forecast,
        forecast=fourteen_day_forecast,
    )

    return (three_day, fourteen_day)


def get_carbon_intensity(now_utc_full: datetime) -> int:
    formatted_datetime = now_utc_full.strftime("%Y-%m-%dT%H:%MZ")
    url = (
        "https://api.carbonintensity.org.uk/intensity/" + formatted_datetime + "/pt24h"
    )
    response = requests.get(url, timeout=10)
    data = json.loads(response.content)
    if "data" not in data:
        raise UnexpectedDataError(url)

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

    if len(items) == 0:
        raise UnexpectedDataError(url)

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
        national_wind_mwh=0,
        embedded_wind_mwh=0,
        solar_mwh=0,
        pumped_storage_mwh=0,
        hydro_mwh=0,
        other_mwh=0,
        france_mwh=0,
        ireland_mwh=0,
        netherlands_mwh=0,
        belgium_mwh=0,
        norway_mwh=0,
        denmark_mw=0,
        total_generation_mwh=0,
        fossil_fuel_percentage_generation=0,
        renewable_percentage_generation=0,
        other_percentage_generation=0,
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
                national_grid_generation["national_wind_mwh"] = generation
            elif fuelType == "PS":
                national_grid_generation["pumped_storage_mwh"] = generation
            elif fuelType == "NPSHYD":
                national_grid_generation["hydro_mwh"] = generation
            elif fuelType == "OTHER":
                national_grid_generation["other_mwh"] = generation
            elif fuelType == "INTFR" or fuelType == "INTELEC" or fuelType == "INTIFA2":
                national_grid_generation["france_mwh"] += generation
            elif fuelType == "INTIRL" or fuelType == "INTEW" or fuelType == "INTGRNL":
                national_grid_generation["ireland_mwh"] += generation
            elif fuelType == "INTNED":
                national_grid_generation["netherlands_mwh"] = generation
            elif fuelType == "INTNEM":
                national_grid_generation["belgium_mwh"] = generation
            elif fuelType == "INTNSL":
                national_grid_generation["norway_mwh"] = generation
            elif fuelType == "INTVKL":
                national_grid_generation["denmark_mw"] = generation

    # Do a quick check for data validity
    if (
        national_grid_generation["gas_mwh"] == 0
        and national_grid_generation["coal_mwh"] == 0
        and national_grid_generation["biomass_mwh"] == 0
        and national_grid_generation["nuclear_mwh"] == 0
        and national_grid_generation["hydro_mwh"] == 0
    ):
        raise UnexpectedDataError("Getting generation returned numerous zero values")

    return national_grid_generation


def get_generation_combined(now_utc_full: datetime, today_utc: str):
    grid_generation = get_generation(
        now_utc_full,
    )

    now_utc_formatted_datetime = now_utc_full.strftime("%Y-%m-%d %H:%M:%S")
    two_hours_ago_utc_formatted_datetime = (now_utc_full - timedelta(hours=2)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    national_grid_data = get_national_grid_data(today_utc, now_utc_full)
    if national_grid_data is None:
        raise UnexpectedDataError("National Grid ESO data None")

    grid_generation["wind_mwh"] += int(national_grid_data["EMBEDDED_WIND_GENERATION"])
    grid_generation["solar_mwh"] = int(national_grid_data["EMBEDDED_SOLAR_GENERATION"])
    grid_generation["embedded_wind_mwh"] = int(
        national_grid_data["EMBEDDED_WIND_GENERATION"]
    )

    grid_generation["total_generation_mwh"] = (
        grid_generation["gas_mwh"]
        + grid_generation["oil_mwh"]
        + grid_generation["coal_mwh"]
        + grid_generation["biomass_mwh"]
        + grid_generation["nuclear_mwh"]
        + grid_generation["wind_mwh"]
        + grid_generation["solar_mwh"]
        + grid_generation["hydro_mwh"]
        + grid_generation["other_mwh"]
    )

    grid_generation["fossil_fuel_percentage_generation"] = percentage_calc(
        (
            grid_generation["gas_mwh"]
            + grid_generation["oil_mwh"]
            + grid_generation["coal_mwh"]
        ),
        grid_generation["total_generation_mwh"],
    )

    grid_generation["renewable_percentage_generation"] = percentage_calc(
        (
            grid_generation["solar_mwh"]
            + grid_generation["wind_mwh"]
            + grid_generation["hydro_mwh"]
        ),
        grid_generation["total_generation_mwh"],
    )

    grid_generation["low_carbon_percentage_generation"] = percentage_calc(
        (
            grid_generation["solar_mwh"]
            + grid_generation["wind_mwh"]
            + grid_generation["hydro_mwh"]
            + grid_generation["nuclear_mwh"]
        ),
        grid_generation["total_generation_mwh"],
    )

    grid_generation["low_carbon_with_biomass_percentage_generation"] = percentage_calc(
        (
            grid_generation["solar_mwh"]
            + grid_generation["wind_mwh"]
            + grid_generation["hydro_mwh"]
            + grid_generation["nuclear_mwh"]
            + grid_generation["biomass_mwh"]
        ),
        grid_generation["total_generation_mwh"],
    )

    grid_generation["other_percentage_generation"] = percentage_calc(
        (
            grid_generation["nuclear_mwh"]
            + grid_generation["biomass_mwh"]
            + grid_generation["other_mwh"]
        ),
        grid_generation["total_generation_mwh"],
    )

    return grid_generation


# Just adds up all of the generation and transfers
def get_demand(grid_generation: NationalGridGeneration):
    if grid_generation is None:
        raise UnexpectedDataError("grid generation None")

    return (
        grid_generation["gas_mwh"]
        + grid_generation["oil_mwh"]
        + grid_generation["coal_mwh"]
        + grid_generation["biomass_mwh"]
        + grid_generation["nuclear_mwh"]
        + grid_generation["wind_mwh"]
        + grid_generation["solar_mwh"]
        + grid_generation["pumped_storage_mwh"]
        + grid_generation["hydro_mwh"]
        + grid_generation["other_mwh"]
        + grid_generation["france_mwh"]
        + grid_generation["ireland_mwh"]
        + grid_generation["netherlands_mwh"]
        + grid_generation["belgium_mwh"]
        + grid_generation["norway_mwh"]
        + grid_generation["denmark_mw"]
    )


# Just adds up all of the transfers from interconnectors and storage
def get_transfers(grid_generation: NationalGridGeneration):
    """Get transfers."""
    if grid_generation is None:
        raise UnexpectedDataError("grid generation None")

    return (
        grid_generation["france_mwh"]
        + grid_generation["ireland_mwh"]
        + grid_generation["netherlands_mwh"]
        + grid_generation["belgium_mwh"]
        + grid_generation["norway_mwh"]
        + grid_generation["denmark_mw"]
        + grid_generation["pumped_storage_mwh"]
    )


def obtain_data_with_fallback(current_data, key, func, *args):
    """Obtain data with fallback."""
    try:
        return func(*args)
    except UnexpectedDataError as e:
        argument_str = ""
        if len(e.args) != 0:
            argument_str = e.args[0]
        _LOGGER.warning("Data unexpected " + argument_str)  # noqa: G003
        return get_data_if_exists(current_data, key)
    except requests.exceptions.ReadTimeout as e:
        _LOGGER.warning("Read timeout error")
        return get_data_if_exists(current_data, key)
    except requests.exceptions.ConnectionError as e:
        _LOGGER.warning("Request connection error")
        return get_data_if_exists(current_data, key)
    except InvalidAuthError as e:
        raise e
    except UnexpectedStatusCode as e:
        argument_str = ""
        if len(e.args) != 0:
            argument_str = e.args[0]
        if type(argument_str) is not str:  # noqa: E721
            argument_str = str(argument_str)
        _LOGGER.warning("Unexpected status code " + argument_str)  # noqa: G003
        return get_data_if_exists(current_data, key)
    except Exception as e:  # pylint: disable=broad-except
        _LOGGER.exception("Failed to obtain data")
        return get_data_if_exists(current_data, key)


def percentage_calc(int_sum, int_total):
    """Calculate percentage."""
    return round(int_sum / int_total * 100, 2)


def hour_minute_check(date: datetime, hour: int, minute: int) -> bool:
    """Check if hour and minute match."""
    return date.hour == hour and date.minute == minute
