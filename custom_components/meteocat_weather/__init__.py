"""Meteocat Weather integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import MeteocatApiClient
from .const import (
    CONF_API_KEY,
    CONF_ENTRY_ID,
    CONF_STATION_ID,
    CONF_TOWN_ID,
    PLATFORMS,
)
from .coordinator import MeteocatForecastCoordinator, MeteocatObservationCoordinator
from .radar import MeteocatRadarCoordinator, RadarProvider


@dataclass(slots=True)
class MeteocatRuntimeData:
    """Objects shared by Meteocat platforms."""

    settings: dict[str, Any]
    client: MeteocatApiClient
    observations: MeteocatObservationCoordinator
    forecast: MeteocatForecastCoordinator
    radar: MeteocatRadarCoordinator


type MeteocatConfigEntry = ConfigEntry[MeteocatRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: MeteocatConfigEntry) -> bool:
    """Set up Meteocat Weather from a config entry."""
    settings = {**entry.data, **entry.options}
    settings[CONF_ENTRY_ID] = entry.entry_id
    session = async_get_clientsession(hass)
    client = MeteocatApiClient(session, entry.data[CONF_API_KEY])
    observations = MeteocatObservationCoordinator(hass, client, settings[CONF_STATION_ID], settings)
    forecast = MeteocatForecastCoordinator(hass, client, settings[CONF_TOWN_ID], settings)
    radar = MeteocatRadarCoordinator(hass, RadarProvider(session, settings), settings)

    await asyncio.gather(
        observations.async_config_entry_first_refresh(),
        forecast.async_config_entry_first_refresh(),
    )
    entry.runtime_data = MeteocatRuntimeData(
        settings=settings,
        client=client,
        observations=observations,
        forecast=forecast,
        radar=radar,
    )
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MeteocatConfigEntry) -> bool:
    """Unload a Meteocat Weather config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(hass: HomeAssistant, entry: MeteocatConfigEntry) -> None:
    """Reload after options or credentials change."""
    await hass.config_entries.async_reload(entry.entry_id)
