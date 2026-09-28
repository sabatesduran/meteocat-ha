"""Weather entity for Meteocat."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from homeassistant.components.weather import Forecast, WeatherEntity, WeatherEntityFeature
from homeassistant.const import (
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MeteocatConfigEntry
from .const import CONF_ENTRY_ID
from .entity import MeteocatCoordinatorEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MeteocatConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Meteocat weather entity."""
    runtime = entry.runtime_data
    async_add_entities([MeteocatWeather(runtime.observations, runtime.forecast, runtime.settings)])


class MeteocatWeather(MeteocatCoordinatorEntity, WeatherEntity):
    """Combined XEMA observations and municipal forecast."""

    _attr_translation_key = "weather"
    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_HOURLY | WeatherEntityFeature.FORECAST_DAILY
    )
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_wind_speed_unit = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_native_precipitation_unit = UnitOfPrecipitationDepth.MILLIMETERS

    def __init__(self, observations: Any, forecast: Any, settings: dict[str, Any]) -> None:
        super().__init__(observations, settings)
        self.forecast_coordinator = forecast
        self._attr_unique_id = f"{settings[CONF_ENTRY_ID]}_weather"

    async def async_added_to_hass(self) -> None:
        """Listen for both coordinator updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.forecast_coordinator.async_add_listener(self.async_write_ha_state)
        )

    @property
    def native_temperature(self) -> float | None:
        return self.coordinator.data.temperature

    @property
    def humidity(self) -> float | None:
        return self.coordinator.data.humidity

    @property
    def native_pressure(self) -> float | None:
        return self.coordinator.data.pressure

    @property
    def native_wind_speed(self) -> float | None:
        return self.coordinator.data.wind_speed

    @property
    def wind_bearing(self) -> float | None:
        return self.coordinator.data.wind_bearing

    @property
    def native_wind_gust_speed(self) -> float | None:
        return self.coordinator.data.wind_gust

    @property
    def condition(self) -> str | None:
        hourly = self.forecast_coordinator.data.get("hourly", [])
        if not hourly:
            return None
        now = datetime.now(UTC)
        closest = min(
            hourly,
            key=lambda item: abs((datetime.fromisoformat(item["datetime"]) - now).total_seconds()),
        )
        return closest.get("condition")

    async def async_forecast_hourly(self) -> list[Forecast]:
        """Return the 72-hour forecast."""
        cutoff = datetime.now(UTC)
        return [
            Forecast(**item)
            for item in self.forecast_coordinator.data.get("hourly", [])
            if datetime.fromisoformat(item["datetime"]) >= cutoff
        ]

    async def async_forecast_daily(self) -> list[Forecast]:
        """Return the daily forecast."""
        today = datetime.now(UTC).date().isoformat()
        return [
            Forecast(**item)
            for item in self.forecast_coordinator.data.get("daily", [])
            if item["datetime"] >= today
        ]
