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
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from ..const import DOMAIN
from ..errors import InvalidAuthError, UnexpectedDataError, UnexpectedStatusCode

from ..models import (
    CarbonForecastData,
    CarbonForecastItem,
    DFSRequirementItem,
    DFSRequirements,
    MarginForecastData,
    MarginForecastItem,
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
    RegionalCarbonData,
    SystemWarningData,
    SystemWarningItem,
)

_LOGGER = logging.getLogger(__name__)

# Set of even hours for checkpoint filtering (reduces 12 OR conditions to set lookup)
EVEN_HOURS = frozenset({0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22})

# Update intervals for different data categories
UPDATE_INTERVALS = {
    "grid_frequency": timedelta(minutes=2),
    "sell_price": timedelta(minutes=5),
    "grid_generation": timedelta(minutes=5),
    "system_warnings": timedelta(minutes=5),
    "carbon_intensity": timedelta(minutes=15),
    "margin_indicators": timedelta(minutes=15),
    "wind_forecast": timedelta(minutes=30),
    "solar_forecast": timedelta(minutes=30),
    "demand_forecast": timedelta(minutes=30),
    "dfs_requirements": timedelta(minutes=30),
}


def fetch_json(url: str, timeout: int, function_name: str) -> dict:
    """Fetch JSON from URL with consistent error handling.

    Args:
        url: The URL to fetch
        timeout: Request timeout in seconds
        function_name: Name of calling function for error messages

    Returns:
        Parsed JSON response as dict

    Raises:
        UnexpectedStatusCode: If HTTP status is not 200
        UnexpectedDataError: If response is not valid JSON
    """
    response = requests.get(url, timeout=timeout)
    if response.status_code != 200:
        raise UnexpectedStatusCode(
            f"{function_name}: HTTP {response.status_code} - {url}"
        )
    try:
        return json.loads(response.content)
    except json.JSONDecodeError as e:
        raise UnexpectedDataError(f"{function_name}: Invalid JSON - {url}") from e


def is_even_hour_checkpoint(dt: datetime) -> bool:
    """Check if datetime is at minute 0 of an even hour.

    Used for filtering long-term forecasts to reduce data points.
    """
    return dt.minute == 0 and dt.hour in EVEN_HOURS


class NationalGridCoordinator(DataUpdateCoordinator[NationalGridData]):
    """National Grid Data Coordinator."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=timedelta(minutes=2)
        )
        self._entry = entry
        # Track last update times for each data category
        self._last_updates: dict[str, datetime] = {}

    @property
    def entry_id(self) -> str:
        """Return entry id."""
        return self._entry.entry_id

    @property
    def last_updates(self) -> dict[str, datetime]:
        """Return last update times for each data category."""
        return self._last_updates

    async def _async_update_data(self) -> NationalGridData:
        try:
            data = await self.hass.async_add_executor_job(
                get_data,
                self.hass,
                self._entry.data,
                self.data,
                self._last_updates,
            )
        except InvalidAuthError:
            raise
        except (UnexpectedDataError, UnexpectedStatusCode) as e:
            raise UpdateFailed(f"Data fetch error: {e}") from e
        except requests.exceptions.RequestException as e:
            raise UpdateFailed(f"Network error: {e}") from e
        except Exception as e:
            _LOGGER.exception("Unexpected error during data update")
            raise UpdateFailed(f"Unexpected error: {e}") from e

        return data


def should_update(
    category: str, last_updates: dict[str, datetime], now: datetime
) -> bool:
    """Check if a data category should be updated based on its interval.

    Always returns True if no previous update recorded (first run/restart).
    """
    if category not in last_updates:
        return True
    interval = UPDATE_INTERVALS.get(category, timedelta(minutes=5))
    return now - last_updates[category] >= interval


def mark_updated(category: str, last_updates: dict[str, datetime], now: datetime):
    """Mark a data category as updated at the given time."""
    last_updates[category] = now


def get_data(
    hass: HomeAssistant,
    config: Mapping[str, Any],
    current_data: NationalGridData,
    last_updates: dict[str, datetime],
) -> NationalGridData:
    """Get data with differentiated update frequencies.

    Different data categories are updated at different intervals:
    - Grid frequency: every 2 minutes
    - Sell price / Generation: every 5 minutes
    - Carbon intensity: every 15 minutes
    - Forecasts / DFS: every 30 minutes
    """
    yesterday_utc = (dt_util.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    today_utc = dt_util.utcnow().strftime("%Y-%m-%d")

    today = dt_util.now().strftime("%Y-%m-%d")
    tomorrow = (dt_util.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    now_utc_full = dt_util.utcnow()

    # Helper to get existing value or default
    def get_existing(key, default=None):
        if current_data is not None and key in current_data:
            return current_data[key]
        return default

    # Grid frequency - updates every 2 minutes
    if should_update("grid_frequency", last_updates, now_utc_full):
        current_grid_frequency = obtain_data_with_fallback(
            current_data, "grid_frequency", get_current_frequency, now_utc_full
        )
        if current_grid_frequency is not None:
            mark_updated("grid_frequency", last_updates, now_utc_full)
    else:
        current_grid_frequency = get_existing("grid_frequency")

    # Sell price - updates every 5 minutes
    if should_update("sell_price", last_updates, now_utc_full):
        current_price = obtain_data_with_fallback(
            current_data,
            "sell_price",
            get_current_price,
            today_utc,
            yesterday_utc,
        )
        if current_price is not None:
            mark_updated("sell_price", last_updates, now_utc_full)
    else:
        current_price = get_existing("sell_price", 0)

    # Grid generation - updates every 5 minutes
    if should_update("grid_generation", last_updates, now_utc_full):
        grid_generation = obtain_data_with_fallback(
            current_data,
            "grid_generation",
            get_generation_combined,
            now_utc_full,
            today_utc,
        )
        if grid_generation is not None:
            mark_updated("grid_generation", last_updates, now_utc_full)

        # Wind data and demand/transfers depend on generation and update together
        wind_data = obtain_data_with_fallback(
            current_data, "wind_data", get_wind_data, today, tomorrow
        )
        total_demand_mwh = obtain_data_with_fallback(
            current_data, "total_demand_mwh", get_demand, grid_generation
        )
        total_transfers_mwh = obtain_data_with_fallback(
            current_data, "transfers_mwh", get_transfers, grid_generation
        )
    else:
        grid_generation = get_existing("grid_generation")
        wind_data = get_existing("wind_data")
        total_demand_mwh = get_existing("total_demand_mwh")
        total_transfers_mwh = get_existing("transfers_mwh")

    # Carbon intensity and forecast - updates every 15 minutes
    if should_update("carbon_intensity", last_updates, now_utc_full):
        carbon_intensity = obtain_data_with_fallback(
            current_data, "carbon_intensity", get_carbon_intensity, now_utc_full
        )
        carbon_intensity_forecast = obtain_data_with_fallback(
            current_data, "carbon_intensity_forecast", get_carbon_intensity_forecast, now_utc_full
        )
        # Regional carbon - only if region_id is configured
        region_id = config.get("region_id") if config else None
        if region_id is not None:
            regional_carbon = obtain_data_with_fallback(
                current_data, "regional_carbon", get_regional_carbon_data, region_id
            )
        else:
            regional_carbon = None
        if carbon_intensity is not None:
            mark_updated("carbon_intensity", last_updates, now_utc_full)
    else:
        carbon_intensity = get_existing("carbon_intensity")
        carbon_intensity_forecast = get_existing("carbon_intensity_forecast")
        regional_carbon = get_existing("regional_carbon")

    # Wind forecasts - updates every 30 minutes
    if should_update("wind_forecast", last_updates, now_utc_full):
        wind_forecast = obtain_data_with_fallback(
            current_data,
            "wind_forecast",
            get_hourly_wind_forecast,
            now_utc_full,
            "latest",
        )
        wind_forecast_earliest = obtain_data_with_fallback(
            current_data,
            "wind_forecast_earliest",
            get_hourly_wind_forecast,
            now_utc_full,
            "earliest",
        )
        long_term_wind_forecast = obtain_data_with_fallback(
            current_data,
            "long_term_wind_forecast",
            get_long_term_wind_forecast_eso_data,
            now_utc_full,
        )
        long_term_embedded_wind_and_solar_forecast = obtain_data_with_fallback(
            current_data,
            "long_term_embedded_wind_and_solar_forecast",
            get_long_term_embedded_wind_and_solar_forecast,
            now_utc_full,
        )
        if wind_forecast is not None:
            mark_updated("wind_forecast", last_updates, now_utc_full)
    else:
        wind_forecast = get_existing("wind_forecast")
        wind_forecast_earliest = get_existing("wind_forecast_earliest")
        long_term_wind_forecast = get_existing("long_term_wind_forecast")
        long_term_embedded_wind_and_solar_forecast = get_existing(
            "long_term_embedded_wind_and_solar_forecast"
        )

    # Extract wind forecast components
    if long_term_wind_forecast is not None:
        three_day = long_term_wind_forecast[0]
        fourteen_day = long_term_wind_forecast[1]
    else:
        three_day = None
        fourteen_day = None

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

    # Solar forecast - updates every 30 minutes
    if should_update("solar_forecast", last_updates, now_utc_full):
        solar_forecast = obtain_data_with_fallback(
            current_data,
            "solar_forecast",
            get_half_hourly_solar_forecast,
            now_utc_full,
        )
        if solar_forecast is not None:
            mark_updated("solar_forecast", last_updates, now_utc_full)
    else:
        solar_forecast = get_existing("solar_forecast")

    # Demand forecast - updates every 30 minutes
    if should_update("demand_forecast", last_updates, now_utc_full):
        demand_day_ahead_forecast = obtain_data_with_fallback(
            current_data,
            "grid_demand_day_ahead_forecast",
            get_demand_day_ahead_forecast,
            now_utc_full,
        )
        three_day_demand_and_fourteen_day_demand = obtain_data_with_fallback(
            current_data,
            "three_day_demand_and_fourteen_day_demand",
            get_demand_forecast,
            now_utc_full,
            demand_day_ahead_forecast,
        )
        if demand_day_ahead_forecast is not None:
            mark_updated("demand_forecast", last_updates, now_utc_full)
    else:
        demand_day_ahead_forecast = get_existing("grid_demand_day_ahead_forecast")
        three_day_demand_and_fourteen_day_demand = get_existing(
            "three_day_demand_and_fourteen_day_demand"
        )

    if three_day_demand_and_fourteen_day_demand is not None:
        three_day_demand = three_day_demand_and_fourteen_day_demand[0]
        fourteen_day_demand = three_day_demand_and_fourteen_day_demand[1]
    else:
        three_day_demand = None
        fourteen_day_demand = None

    # DFS requirements - updates every 30 minutes
    if should_update("dfs_requirements", last_updates, now_utc_full):
        dfs_requirements = obtain_data_with_fallback(
            current_data, "dfs_requirements", get_dfs_requirements
        )
        if dfs_requirements is not None:
            mark_updated("dfs_requirements", last_updates, now_utc_full)
    else:
        dfs_requirements = get_existing("dfs_requirements")

    # Margin forecast - updates every 15 minutes
    if should_update("margin_indicators", last_updates, now_utc_full):
        margin_forecast = obtain_data_with_fallback(
            current_data, "margin_forecast", get_margin_forecast
        )
        if margin_forecast is not None:
            mark_updated("margin_indicators", last_updates, now_utc_full)
    else:
        margin_forecast = get_existing("margin_forecast")

    # System warnings - updates every 5 minutes
    if should_update("system_warnings", last_updates, now_utc_full):
        system_warnings = obtain_data_with_fallback(
            current_data, "system_warnings", get_system_warnings
        )
        if system_warnings is not None:
            mark_updated("system_warnings", last_updates, now_utc_full)
    else:
        system_warnings = get_existing("system_warnings")

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
        margin_forecast=margin_forecast,
        system_warnings=system_warnings,
        carbon_intensity_forecast=carbon_intensity_forecast,
        regional_carbon=regional_carbon,
    )


def get_data_if_exists(data, key: str, func_name: str = "unknown"):
    """Get data if exists in previous data cache.

    Args:
        data: Previous NationalGridData object
        key: The data key to look up
        func_name: Name of calling function for logging
    """
    if data is None:
        _LOGGER.warning("[%s] No previous data available for key '%s'", func_name, key)
        return None
    if key in data:
        _LOGGER.debug("[%s] Using cached data for key '%s'", func_name, key)
        return data[key]

    _LOGGER.warning("[%s] Key '%s' not found in previous data", func_name, key)
    return None


def get_hourly_wind_forecast(
    now_utc: datetime, forecast_type: str = "latest"
) -> NationalGridWindForecast:
    """Get hourly wind forecast.

    Args:
        now_utc: Current UTC datetime
        forecast_type: Either "latest" or "earliest" for the forecast endpoint

    Returns:
        NationalGridWindForecast with forecast data and current value
    """
    # Need to calculate start. We want data from 8pm on current day to day+2 8pm...
    # however, this is calculated every so often.
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
        f"https://data.elexon.co.uk/bmrs/api/v1/forecast/generation/wind/{forecast_type}"
        f"?from={start_time_formatted}&to={end_time_formatted}&format=json"
    )
    data = fetch_json(url, timeout=10, function_name="get_hourly_wind_forecast")
    item_list = data["data"]

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
        raise UnexpectedDataError(
            f"Hourly wind forecast ({forecast_type}) 'current' is 0"
        )

    return NationalGridWindForecast(
        forecast=wind_forecast, current_value=current_generation
    )


def get_half_hourly_solar_forecast(now: datetime) -> NationalGridSolarForecast:
    """Get half hourly solar forecast."""
    nearest_30_minutes = now + (now.min.replace(tzinfo=now.tzinfo) - now) % timedelta(
        minutes=30
    )

    yesterday = now - timedelta(days=1)
    day_after_tomorrow = now + timedelta(days=2)

    url = (
        f"https://data.elexon.co.uk/bmrs/api/v1/forecast/generation/wind-and-solar/day-ahead"
        f"?from={yesterday.strftime('%Y-%m-%d')}&to={day_after_tomorrow.strftime('%Y-%m-%d')}"
        f"&processType=all&settlementPeriodFrom=1&settlementPeriodTo=50&format=json"
    )

    data = fetch_json(url, timeout=10, function_name="get_half_hourly_solar_forecast")
    results = data["data"]

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
        f"https://data.elexon.co.uk/bmrs/api/v1/balancing/pricing/market-index"
        f"?from={yesterday_utc}&to={today_utc}"
        f"&settlementPeriodFrom=1&settlementPeriodTo=50&dataProviders=APXMIDP&format=json"
    )

    data = fetch_json(url, timeout=10, function_name="get_current_price")
    items = data["data"]
    if len(items) == 0:
        raise UnexpectedDataError(f"get_current_price: No data returned - {url}")

    return round(float(items[0]["price"]), 2)


def get_current_frequency(now_utc: datetime) -> float:
    """Get current grid frequency."""
    from_time = (now_utc - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    to_time = (now_utc + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    url = (
        f"https://data.elexon.co.uk/bmrs/api/v1/system/frequency"
        f"?format=json&from={from_time}&to={to_time}"
    )

    data = fetch_json(url, timeout=10, function_name="get_current_frequency")
    items = data["data"]

    if len(items) == 0:
        raise UnexpectedDataError(f"get_current_frequency: No data returned - {url}")

    return float(items[-1]["frequency"])


def get_wind_data(today: str, tomorrow: str) -> NationalGridWindData:
    """Get wind data."""
    url = "https://data.elexon.co.uk/bmrs/api/v1/forecast/generation/wind/peak?format=json"
    data = fetch_json(url, timeout=10, function_name="get_wind_data")
    items = data["data"]

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
        f"https://data.elexon.co.uk/bmrs/api/v1/forecast/demand/day-ahead/latest"
        f"?format=json&from={utc_now_formatted}&to={two_days}&boundary=N"
    )

    data = fetch_json(url, timeout=10, function_name="get_demand_day_ahead_forecast")
    items = data["data"]

    if len(items) == 0:
        raise UnexpectedDataError(
            f"get_demand_day_ahead_forecast: No data returned - {url}"
        )

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
    """Get national grid data from NESO API (CSV format)."""
    today_minutes = now_utc.hour * 60 + now_utc.minute
    settlement_period = (today_minutes // 30) + 1

    url = "https://api.neso.energy/dataset/7a12172a-939c-404c-b581-a6128b74f588/resource/177f6fa4-ae49-4182-81ea-0c6b35f26ca6/download/demanddataupdate.csv"
    response = requests.get(url, timeout=20)

    if response.status_code != 200:
        raise UnexpectedStatusCode(
            f"get_national_grid_data: HTTP {response.status_code} - {url}"
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
    data = fetch_json(
        url, timeout=20, function_name="get_long_term_wind_forecast_eso_data"
    )

    # Get 7 day forecast. Will just do now + 7 days
    nearest_30_minutes = now + (now.min.replace(tzinfo=now.tzinfo) - now) % timedelta(
        minutes=30
    )
    in_three_days = nearest_30_minutes + timedelta(days=3)
    in_fourteen_days = nearest_30_minutes + timedelta(days=14)

    three_day_forecast = []
    fourteen_day_forecast = []

    all_records = data["result"]["records"]
    for record in all_records:
        formatted_datetime = datetime.strptime(
            record["Datetime"], "%Y-%m-%dT%H:%M:%S"
        ).replace(tzinfo=tz.UTC)
        forecast = int(record["Wind_Forecast"])

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
            and is_even_hour_checkpoint(formatted_datetime)
        ):
            fourteen_day_forecast.append(
                NationalGridWindForecastItem(
                    start_time=formatted_datetime, generation=forecast
                )
            )

    if len(three_day_forecast) == 0 or len(fourteen_day_forecast) == 0:
        raise UnexpectedDataError(
            "get_long_term_wind_forecast_eso_data: Forecast data is empty"
        )

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
    data = fetch_json(
        url, timeout=20, function_name="get_long_term_embedded_wind_and_solar_forecast"
    )

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
            and is_even_hour_checkpoint(formatted_datetime)
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
        raise UnexpectedDataError(
            "get_long_term_embedded_wind_and_solar_forecast: Forecast data is empty"
        )

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
    data = fetch_json(url, timeout=20, function_name="get_dfs_requirements")

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
    data = fetch_json(url, timeout=20, function_name="get_demand_forecast")

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

    # Include the first day from the day-ahead endpoint
    for item in day_ahead_forecast["forecast"]:
        if item["start_time"] < first_record_datetime:
            three_day_forecast.append(
                NationalGridDemandForecastItem(
                    start_time=item["start_time"],
                    national_demand=item["national_demand"],
                )
            )

            if is_even_hour_checkpoint(item["start_time"]):
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
            and is_even_hour_checkpoint(formatted_datetime)
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
    """Get current carbon intensity from Carbon Intensity API."""
    formatted_datetime = now_utc_full.strftime("%Y-%m-%dT%H:%MZ")
    url = f"https://api.carbonintensity.org.uk/intensity/{formatted_datetime}/pt24h"
    data = fetch_json(url, timeout=10, function_name="get_carbon_intensity")

    if "data" not in data:
        raise UnexpectedDataError(f"get_carbon_intensity: No data field - {url}")

    for item in reversed(data["data"]):
        if item["intensity"]["actual"] is not None:
            return int(item["intensity"]["actual"])
    return None


def get_generation(utc_now: datetime) -> NationalGridGeneration:
    """Get current generation mix from BMRS API."""
    utc_now_formatted = utc_now.strftime("%Y-%m-%dT%H:%M:%SZ")
    ten_minutes_ago = (utc_now - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")

    url = (
        f"https://data.elexon.co.uk/bmrs/api/v1/datasets/FUELINST"
        f"?publishDateTimeFrom={ten_minutes_ago}&publishDateTimeTo={utc_now_formatted}&format=json"
    )
    data = fetch_json(url, timeout=10, function_name="get_generation")
    items = data["data"]

    if len(items) == 0:
        raise UnexpectedDataError(f"get_generation: No data returned - {url}")

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
    """Obtain data with fallback to cached values on error.

    Catches various exceptions and falls back to previously cached data.
    Logs warnings with function name for easier debugging.
    """
    func_name = func.__name__
    try:
        return func(*args)
    except UnexpectedDataError as e:
        error_msg = str(e.args[0]) if e.args else "unknown"
        _LOGGER.warning("[%s] Unexpected data: %s - using cached value", func_name, error_msg)
        return get_data_if_exists(current_data, key, func_name)
    except requests.exceptions.ReadTimeout:
        _LOGGER.warning("[%s] Request timeout - using cached value", func_name)
        return get_data_if_exists(current_data, key, func_name)
    except requests.exceptions.ConnectionError:
        _LOGGER.warning("[%s] Connection error - using cached value", func_name)
        return get_data_if_exists(current_data, key, func_name)
    except InvalidAuthError:
        raise
    except UnexpectedStatusCode as e:
        error_msg = str(e.args[0]) if e.args else "unknown"
        _LOGGER.warning("[%s] Unexpected status code: %s - using cached value", func_name, error_msg)
        return get_data_if_exists(current_data, key, func_name)
    except Exception as e:  # pylint: disable=broad-except
        _LOGGER.exception("[%s] Failed to obtain data: %s", func_name, e)
        return get_data_if_exists(current_data, key, func_name)


def get_margin_forecast() -> MarginForecastData:
    """Get daily margin forecast data from BMRS API.

    This shows the forecasted operating margin (MW) for upcoming days.
    A low margin indicates potential grid stress.
    """
    url = "https://data.elexon.co.uk/bmrs/api/v1/forecast/margin/daily?format=json"
    data = fetch_json(url, timeout=10, function_name="get_margin_forecast")
    items = data.get("data", [])

    if len(items) == 0:
        raise UnexpectedDataError(f"get_margin_forecast: No data returned - {url}")

    forecast = []
    current_margin = 0

    for i, item in enumerate(items):
        forecast_date = item.get("forecastDate", "")
        margin = int(item.get("margin", 0))
        publish_time_str = item.get("publishTime", "")

        try:
            publish_time = datetime.strptime(
                publish_time_str, "%Y-%m-%dT%H:%M:%S%z"
            )
        except (ValueError, TypeError):
            publish_time = datetime.now(tz.UTC)

        forecast_item = MarginForecastItem(
            forecast_date=forecast_date,
            margin=margin,
            publish_time=publish_time,
        )
        forecast.append(forecast_item)

        # First item is the closest forecast (today or tomorrow)
        if i == 0:
            current_margin = margin

    return MarginForecastData(
        current_margin=current_margin,
        forecast=forecast,
    )


def get_system_warnings() -> SystemWarningData:
    """Get system warnings from BMRS API."""
    url = "https://data.elexon.co.uk/bmrs/api/v1/system/warnings?format=json"
    data = fetch_json(url, timeout=10, function_name="get_system_warnings")
    items = data.get("data", [])

    warnings = []
    current_warning = None

    # Warning types that indicate margin stress
    margin_warning_types = {"EMN", "HRDC", "DCI", "NRAPM"}

    for item in items:
        warning_type = item.get("warningType", "")
        publish_time_str = item.get("publishTime", "")
        text = item.get("text", "")

        try:
            publish_time = datetime.strptime(
                publish_time_str, "%Y-%m-%dT%H:%M:%S%z"
            )
        except (ValueError, TypeError):
            publish_time = datetime.now(tz.UTC)

        warning_item = SystemWarningItem(
            warning_type=warning_type,
            publish_time=publish_time,
            text=text,
        )
        warnings.append(warning_item)

        # Set current warning if it's a margin-related warning
        if warning_type in margin_warning_types and current_warning is None:
            current_warning = warning_type

    return SystemWarningData(
        current_warning=current_warning,
        warnings=warnings,
    )


def get_carbon_intensity_forecast(now_utc: datetime) -> CarbonForecastData:
    """Get 48-hour carbon intensity forecast from Carbon Intensity API."""
    formatted_datetime = now_utc.strftime("%Y-%m-%dT%H:%MZ")
    url = f"https://api.carbonintensity.org.uk/intensity/{formatted_datetime}/fw48h"
    data = fetch_json(url, timeout=10, function_name="get_carbon_intensity_forecast")

    if "data" not in data:
        raise UnexpectedDataError(
            f"get_carbon_intensity_forecast: No data field - {url}"
        )

    forecast = []
    current_intensity = 0
    current_index = "moderate"

    for i, item in enumerate(data["data"]):
        start_time_str = item.get("from", "")
        try:
            start_time = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%MZ").replace(
                tzinfo=tz.UTC
            )
        except (ValueError, TypeError):
            continue

        intensity_data = item.get("intensity", {})
        intensity = int(intensity_data.get("forecast", 0))
        index = intensity_data.get("index", "moderate")

        forecast_item = CarbonForecastItem(
            start_time=start_time,
            intensity=intensity,
            index=index,
        )
        forecast.append(forecast_item)

        # First item is current
        if i == 0:
            current_intensity = intensity
            current_index = index

    return CarbonForecastData(
        current_intensity=current_intensity,
        current_index=current_index,
        forecast=forecast,
    )


# Region ID to name mapping (based on DNO regions)
CARBON_REGIONS = {
    1: "North Scotland",
    2: "South Scotland",
    3: "North West England",
    4: "North East England",
    5: "Yorkshire",
    6: "North Wales & Merseyside",
    7: "South Wales",
    8: "West Midlands",
    9: "East Midlands",
    10: "East England",
    11: "South West England",
    12: "South England",
    13: "London",
    14: "South East England",
}


def get_regional_carbon_data(region_id: int) -> RegionalCarbonData:
    """Get regional carbon intensity data from Carbon Intensity API."""
    url = f"https://api.carbonintensity.org.uk/regional/regionid/{region_id}"
    data = fetch_json(url, timeout=10, function_name="get_regional_carbon_data")

    if "data" not in data or len(data["data"]) == 0:
        raise UnexpectedDataError(
            f"get_regional_carbon_data: No data field - {url}"
        )

    region_data = data["data"][0]
    region_name = region_data.get("shortname", CARBON_REGIONS.get(region_id, "Unknown"))

    # Get current intensity
    intensity_data = region_data.get("data", [{}])[0].get("intensity", {})
    current_intensity = int(intensity_data.get("forecast", 0))
    current_index = intensity_data.get("index", "moderate")

    # Get forecast - need a different endpoint for regional forecast
    forecast_url = f"https://api.carbonintensity.org.uk/regional/regionid/{region_id}/fw48h"
    try:
        forecast_data = fetch_json(
            forecast_url, timeout=10, function_name="get_regional_carbon_data_forecast"
        )
        forecast = []

        if "data" in forecast_data and "data" in forecast_data["data"]:
            for item in forecast_data["data"]["data"]:
                start_time_str = item.get("from", "")
                try:
                    start_time = datetime.strptime(
                        start_time_str, "%Y-%m-%dT%H:%MZ"
                    ).replace(tzinfo=tz.UTC)
                except (ValueError, TypeError):
                    continue

                intensity_item = item.get("intensity", {})
                intensity = int(intensity_item.get("forecast", 0))
                index = intensity_item.get("index", "moderate")

                forecast_item = CarbonForecastItem(
                    start_time=start_time,
                    intensity=intensity,
                    index=index,
                )
                forecast.append(forecast_item)
    except Exception:
        forecast = []

    return RegionalCarbonData(
        region_id=region_id,
        region_name=region_name,
        current_intensity=current_intensity,
        current_index=current_index,
        forecast=forecast,
    )


def percentage_calc(int_sum, int_total):
    """Calculate percentage."""
    return round(int_sum / int_total * 100, 2)
