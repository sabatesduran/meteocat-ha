"""Compatibility smoke tests for the pinned Home Assistant release."""

import logging
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch

import pytest
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.meteocat_weather.camera import MeteocatRadarCamera
from custom_components.meteocat_weather.config_flow import MeteocatWeatherConfigFlow
from custom_components.meteocat_weather.const import (
    CONF_API_KEY,
    CONF_ENTRY_ID,
    CONF_FORECAST_INTERVAL,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_OBSERVATION_INTERVAL,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    CONF_TOWN_ID,
    CONF_TOWN_NAME,
    DOMAIN,
)
from custom_components.meteocat_weather.coordinator import (
    MeteocatForecastCoordinator,
    MeteocatObservationCoordinator,
)
from custom_components.meteocat_weather.models import Municipality, Observations, Station
from custom_components.meteocat_weather.radar import MeteocatRadarCoordinator, RadarResult
from custom_components.meteocat_weather.sensor import SENSORS, MeteocatObservationSensor
from custom_components.meteocat_weather.weather import MeteocatWeather

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")

_LOGGER = logging.getLogger(__name__)


async def test_config_flow_user_form(hass) -> None:
    """The config flow proceeds from credentials to town and station selection."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    async def load_reference(flow: MeteocatWeatherConfigFlow) -> None:
        flow._municipalities = [Municipality("08019", "Barcelona")]
        flow._stations = [Station("X8", "Barcelona", 41.39, 2.17, "08019")]
        flow._automatic_town_id = "08019"
        flow._automatic_station_id = "X8"

    with patch.object(MeteocatWeatherConfigFlow, "_async_load_reference", load_reference):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "test-api-key",
                CONF_LATITUDE: 41.39,
                CONF_LONGITUDE: 2.17,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "location"
    fields = {marker.schema for marker in result["data_schema"].schema}
    assert {CONF_TOWN_ID, CONF_STATION_ID} <= fields


async def test_entities_construct_against_home_assistant(hass) -> None:
    """Core entities construct and expose data with the pinned HA APIs."""
    now = datetime.now(UTC)
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    settings = {
        CONF_ENTRY_ID: entry.entry_id,
        CONF_FORECAST_INTERVAL: 6,
        CONF_LATITUDE: 41.39,
        CONF_LONGITUDE: 2.17,
        CONF_OBSERVATION_INTERVAL: 30,
        CONF_TOWN_NAME: "Barcelona",
        CONF_STATION_ID: "X8",
        CONF_STATION_NAME: "Barcelona - Zona Universitària",
    }
    observations = MeteocatObservationCoordinator(
        hass, entry, Mock(), settings[CONF_STATION_ID], settings
    )
    observations.async_set_updated_data(
        Observations(
            temperature=21.5,
            observed_at=now,
            available_fields=frozenset({"temperature"}),
        )
    )
    forecast = MeteocatForecastCoordinator(hass, entry, Mock(), "08019", settings)
    forecast.async_set_updated_data(
        {
            "hourly": [
                {
                    "datetime": (now + timedelta(hours=1)).isoformat(),
                    "condition": "sunny",
                    "temperature": 22.0,
                }
            ],
            "daily": [
                {
                    "datetime": (now + timedelta(days=1)).date().isoformat(),
                    "condition": "sunny",
                    "temperature": 24.0,
                    "templow": 15.0,
                }
            ],
        }
    )
    radar = MeteocatRadarCoordinator(hass, entry, Mock(), settings)
    radar.async_set_updated_data(RadarResult(b"GIF89a", now, 1))

    sensor = MeteocatObservationSensor(observations, settings, SENSORS[0])
    weather = MeteocatWeather(observations, forecast, settings)
    camera = MeteocatRadarCamera(radar, settings)

    assert sensor.unique_id == f"{entry.entry_id}_temperature"
    assert observations.update_interval == timedelta(minutes=90)
    assert forecast.update_interval == timedelta(hours=24)
    assert sensor.native_value == 21.5
    assert weather.unique_id == f"{entry.entry_id}_weather"
    assert weather.condition == "sunny"
    assert len(await weather.async_forecast_hourly()) == 1
    assert len(await weather.async_forecast_daily()) == 1
    assert camera.unique_id == f"{entry.entry_id}_radar"
    assert camera.camera_image() == b"GIF89a"
