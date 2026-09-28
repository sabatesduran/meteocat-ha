"""Config flow for Meteocat Weather."""

from __future__ import annotations

import asyncio
from typing import Any, override

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import (
    MeteocatApiClient,
    MeteocatAuthenticationError,
    MeteocatConnectionError,
    MeteocatError,
    MeteocatRateLimitError,
)
from .const import (
    CONF_API_KEY,
    CONF_FORECAST_INTERVAL,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_OBSERVATION_INTERVAL,
    CONF_RADAR_FRAMES,
    CONF_RADAR_ZOOM,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    CONF_TOWN_ID,
    CONF_TOWN_NAME,
    DEFAULT_FORECAST_INTERVAL,
    DEFAULT_OBSERVATION_INTERVAL,
    DEFAULT_RADAR_FRAMES,
    DEFAULT_RADAR_ZOOM,
    DOMAIN,
    MAX_LATITUDE,
    MAX_LONGITUDE,
    MIN_LATITUDE,
    MIN_LONGITUDE,
)
from .models import (
    Municipality,
    Station,
    closest_station,
    distance_km,
    normalize_municipalities,
    normalize_stations,
    quota_aware_intervals,
    station_from_dict,
)


def _error_key(error: Exception) -> str:
    if isinstance(error, MeteocatAuthenticationError):
        return "invalid_auth_or_plan"
    if isinstance(error, MeteocatRateLimitError):
        return "rate_limited"
    if isinstance(error, MeteocatConnectionError):
        return "cannot_connect"
    return "unknown"


def _coordinates_schema(latitude: float, longitude: float) -> dict[Any, Any]:
    return {
        vol.Required(CONF_LATITUDE, default=latitude): vol.All(
            vol.Coerce(float), vol.Range(min=MIN_LATITUDE, max=MAX_LATITUDE)
        ),
        vol.Required(CONF_LONGITUDE, default=longitude): vol.All(
            vol.Coerce(float), vol.Range(min=MIN_LONGITUDE, max=MAX_LONGITUDE)
        ),
    }


class MeteocatWeatherConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle Meteocat Weather setup."""

    VERSION = 1

    def __init__(self) -> None:
        self._api_key = ""
        self._latitude = 0.0
        self._longitude = 0.0
        self._municipalities: list[Municipality] = []
        self._stations: list[Station] = []
        self._automatic_town_id: str | None = None
        self._automatic_station_id: str | None = None
        self._observation_interval = DEFAULT_OBSERVATION_INTERVAL
        self._forecast_interval = DEFAULT_FORECAST_INTERVAL

    @staticmethod
    @callback
    @override
    def async_get_options_flow(config_entry: ConfigEntry) -> MeteocatWeatherOptionsFlow:
        return MeteocatWeatherOptionsFlow()

    async def _async_load_reference(self) -> None:
        client = MeteocatApiClient(async_get_clientsession(self.hass), self._api_key)
        towns_payload, stations_payload, quotas_payload = await asyncio.gather(
            client.async_get_municipalities(),
            client.async_get_stations(),
            client.async_get_quotas(),
            return_exceptions=True,
        )
        if isinstance(towns_payload, BaseException):
            raise towns_payload
        if isinstance(stations_payload, BaseException):
            raise stations_payload
        if not isinstance(quotas_payload, BaseException):
            self._observation_interval, self._forecast_interval = quota_aware_intervals(
                quotas_payload
            )
        self._municipalities = normalize_municipalities(towns_payload)
        self._stations = normalize_stations(stations_payload)
        if not self._municipalities or not self._stations:
            raise MeteocatError("Meteocat returned no municipalities or stations")
        nearest = closest_station(self._stations, self._latitude, self._longitude)
        if nearest is None:
            raise MeteocatError("No operational XEMA station was found")
        self._automatic_station_id = nearest.code
        self._automatic_town_id = nearest.municipality_code
        if self._automatic_town_id is None:
            metadata = await client.async_get_station_metadata(nearest.code)
            metadata_station = station_from_dict(metadata)
            if metadata_station:
                self._automatic_town_id = metadata_station.municipality_code
        if not any(item.code == self._automatic_town_id for item in self._municipalities):
            self._automatic_town_id = self._municipalities[0].code

    @override
    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            self._api_key = user_input[CONF_API_KEY]
            self._latitude = user_input[CONF_LATITUDE]
            self._longitude = user_input[CONF_LONGITUDE]
            try:
                await self._async_load_reference()
            except MeteocatError as err:
                errors["base"] = _error_key(err)
            else:
                return await self.async_step_location()

        schema = vol.Schema(
            {
                vol.Required(CONF_API_KEY): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
                **_coordinates_schema(self.hass.config.latitude, self.hass.config.longitude),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @override
    async def async_step_location(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        towns = {item.code: item.name for item in self._municipalities}
        ordered_stations = sorted(
            self._stations,
            key=lambda item: distance_km(self._latitude, self._longitude, item),
        )
        stations = {
            item.code: f"{item.name} · {distance_km(self._latitude, self._longitude, item):.1f} km"
            for item in ordered_stations
        }
        if user_input is not None:
            town = next(
                item for item in self._municipalities if item.code == user_input[CONF_TOWN_ID]
            )
            station = next(
                item for item in self._stations if item.code == user_input[CONF_STATION_ID]
            )
            client = MeteocatApiClient(async_get_clientsession(self.hass), self._api_key)
            try:
                await asyncio.gather(
                    client.async_get_observations(station.code),
                    client.async_get_hourly_forecast(town.code),
                )
            except MeteocatError as err:
                errors["base"] = _error_key(err)
            else:
                await self.async_set_unique_id(f"{town.code}:{station.code}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=town.name,
                    data={
                        CONF_API_KEY: self._api_key,
                        CONF_LATITUDE: self._latitude,
                        CONF_LONGITUDE: self._longitude,
                        CONF_TOWN_ID: town.code,
                        CONF_TOWN_NAME: town.name,
                        CONF_STATION_ID: station.code,
                        CONF_STATION_NAME: station.name,
                    },
                    options={
                        CONF_OBSERVATION_INTERVAL: self._observation_interval,
                        CONF_FORECAST_INTERVAL: self._forecast_interval,
                        CONF_RADAR_ZOOM: DEFAULT_RADAR_ZOOM,
                        CONF_RADAR_FRAMES: DEFAULT_RADAR_FRAMES,
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_TOWN_ID, default=self._automatic_town_id): vol.In(towns),
                vol.Required(CONF_STATION_ID, default=self._automatic_station_id): vol.In(stations),
            }
        )
        return self.async_show_form(step_id="location", data_schema=schema, errors=errors)

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Start API key reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate and save a replacement API key."""
        errors: dict[str, str] = {}
        if user_input is not None:
            key = user_input[CONF_API_KEY]
            client = MeteocatApiClient(async_get_clientsession(self.hass), key)
            try:
                await client.async_get_municipalities()
            except MeteocatError as err:
                errors["base"] = _error_key(err)
            else:
                entry = self._get_reauth_entry()
                return self.async_update_reload_and_abort(
                    entry, data={**entry.data, CONF_API_KEY: key}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    )
                }
            ),
            errors=errors,
        )


class MeteocatWeatherOptionsFlow(OptionsFlow):
    """Edit station, municipality, intervals, and radar settings."""

    def __init__(self) -> None:
        self._municipalities: list[Municipality] = []
        self._stations: list[Station] = []

    async def _async_load_reference(self) -> None:
        client = MeteocatApiClient(
            async_get_clientsession(self.hass), self.config_entry.data[CONF_API_KEY]
        )
        towns_payload, stations_payload = await asyncio.gather(
            client.async_get_municipalities(), client.async_get_stations()
        )
        self._municipalities = normalize_municipalities(towns_payload)
        self._stations = normalize_stations(stations_payload)

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manage Meteocat options."""
        errors: dict[str, str] = {}
        current = {**self.config_entry.data, **self.config_entry.options}
        if not self._municipalities or not self._stations:
            try:
                await self._async_load_reference()
            except MeteocatError as err:
                errors["base"] = _error_key(err)
                self._municipalities = [
                    Municipality(current[CONF_TOWN_ID], current[CONF_TOWN_NAME])
                ]
                self._stations = [
                    Station(
                        current[CONF_STATION_ID],
                        current[CONF_STATION_NAME],
                        None,
                        None,
                    )
                ]

        if user_input is not None and not errors:
            town = next(
                item for item in self._municipalities if item.code == user_input[CONF_TOWN_ID]
            )
            station = next(
                item for item in self._stations if item.code == user_input[CONF_STATION_ID]
            )
            return self.async_create_entry(
                title="",
                data={
                    **user_input,
                    CONF_TOWN_NAME: town.name,
                    CONF_STATION_NAME: station.name,
                },
            )

        towns = {item.code: item.name for item in self._municipalities}
        stations = {item.code: item.name for item in self._stations}
        schema = vol.Schema(
            {
                **_coordinates_schema(current[CONF_LATITUDE], current[CONF_LONGITUDE]),
                vol.Required(CONF_TOWN_ID, default=current[CONF_TOWN_ID]): vol.In(towns),
                vol.Required(CONF_STATION_ID, default=current[CONF_STATION_ID]): vol.In(stations),
                vol.Required(
                    CONF_OBSERVATION_INTERVAL,
                    default=current.get(CONF_OBSERVATION_INTERVAL, DEFAULT_OBSERVATION_INTERVAL),
                ): vol.In({30: "30 min", 60: "1 h", 90: "1 h 30 min", 180: "3 h"}),
                vol.Required(
                    CONF_FORECAST_INTERVAL,
                    default=current.get(CONF_FORECAST_INTERVAL, DEFAULT_FORECAST_INTERVAL),
                ): vol.In({6: "6 h", 12: "12 h", 24: "24 h"}),
                vol.Required(
                    CONF_RADAR_ZOOM,
                    default=current.get(CONF_RADAR_ZOOM, DEFAULT_RADAR_ZOOM),
                ): vol.In({6: "Catalunya", 7: "Local"}),
                vol.Required(
                    CONF_RADAR_FRAMES,
                    default=current.get(CONF_RADAR_FRAMES, DEFAULT_RADAR_FRAMES),
                ): vol.In({6: "30 min", 11: "1 h"}),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
