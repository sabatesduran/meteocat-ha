"""Update coordinators for Meteocat Weather."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigEntryAuthFailed
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    MeteocatApiClient,
    MeteocatAuthenticationError,
    MeteocatError,
    MeteocatRateLimitError,
)
from .const import (
    CONF_FORECAST_INTERVAL,
    CONF_OBSERVATION_INTERVAL,
    DEFAULT_FORECAST_INTERVAL,
    DEFAULT_OBSERVATION_INTERVAL,
    DOMAIN,
)
from .models import Observations, parse_daily_forecast, parse_hourly_forecast, parse_observations

_LOGGER = logging.getLogger(__name__)


class MeteocatObservationCoordinator(DataUpdateCoordinator[Observations]):
    """Fetch and parse XEMA observations."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        client: MeteocatApiClient,
        station_id: str,
        settings: dict[str, Any],
    ) -> None:
        self.client = client
        self.station_id = station_id
        self.using_cached_data = False
        minutes = int(settings.get(CONF_OBSERVATION_INTERVAL, DEFAULT_OBSERVATION_INTERVAL))
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_{station_id}_observations",
            update_interval=timedelta(minutes=minutes),
        )

    async def _async_update_data(self) -> Observations:
        try:
            payload = await self.client.async_get_observations(self.station_id)
        except MeteocatAuthenticationError as err:
            raise ConfigEntryAuthFailed from err
        except MeteocatRateLimitError as err:
            if self.data is not None:
                self.using_cached_data = True
                _LOGGER.warning("Meteocat XEMA quota exhausted; keeping cached observations")
                return self.data
            raise UpdateFailed("Meteocat XEMA quota exhausted") from err
        except MeteocatError as err:
            if self.data is not None:
                self.using_cached_data = True
                _LOGGER.warning("Meteocat XEMA unavailable; keeping cached observations: %s", err)
                return self.data
            raise UpdateFailed(str(err)) from err
        self.using_cached_data = False
        return parse_observations(payload)


class MeteocatForecastCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch and parse municipal forecasts with independent fallback."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        client: MeteocatApiClient,
        town_id: str,
        settings: dict[str, Any],
    ) -> None:
        self.client = client
        self.town_id = town_id
        self.using_cached_data = False
        hours = int(settings.get(CONF_FORECAST_INTERVAL, DEFAULT_FORECAST_INTERVAL))
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_{town_id}_forecast",
            update_interval=timedelta(hours=hours),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        hourly_result, daily_result = await asyncio.gather(
            self.client.async_get_hourly_forecast(self.town_id),
            self.client.async_get_daily_forecast(self.town_id),
            return_exceptions=True,
        )
        errors = [
            result for result in (hourly_result, daily_result) if isinstance(result, BaseException)
        ]
        if any(isinstance(error, MeteocatAuthenticationError) for error in errors):
            raise ConfigEntryAuthFailed from next(
                error for error in errors if isinstance(error, MeteocatAuthenticationError)
            )

        previous = self.data or {}
        hourly = previous.get("hourly", [])
        daily = previous.get("daily", [])
        if not isinstance(hourly_result, BaseException):
            hourly = parse_hourly_forecast(hourly_result)
        if not isinstance(daily_result, BaseException):
            daily = parse_daily_forecast(daily_result)

        if isinstance(hourly_result, BaseException):
            _LOGGER.warning("Hourly Meteocat forecast unavailable: %s", hourly_result)
        if isinstance(daily_result, BaseException):
            _LOGGER.warning("Daily Meteocat forecast unavailable: %s", daily_result)
        if errors and not hourly and not daily:
            if any(isinstance(error, MeteocatRateLimitError) for error in errors):
                raise UpdateFailed("Meteocat prediction quota exhausted")
            raise UpdateFailed(str(errors[0]))
        self.using_cached_data = bool(errors)
        return {"hourly": hourly, "daily": daily}
