"""Sensors for Meteocat XEMA observations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    DEGREE,
    PERCENTAGE,
    EntityCategory,
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


@dataclass(frozen=True, kw_only=True)
class MeteocatSensorDescription(SensorEntityDescription):
    """Describe a Meteocat sensor."""


SENSORS: tuple[MeteocatSensorDescription, ...] = (
    MeteocatSensorDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    MeteocatSensorDescription(
        key="humidity",
        translation_key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    MeteocatSensorDescription(
        key="pressure",
        translation_key="pressure",
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.HPA,
    ),
    MeteocatSensorDescription(
        key="precipitation",
        translation_key="precipitation",
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
    ),
    MeteocatSensorDescription(
        key="wind_speed",
        translation_key="wind_speed",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
    ),
    MeteocatSensorDescription(
        key="wind_bearing",
        translation_key="wind_bearing",
        icon="mdi:compass",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=DEGREE,
    ),
    MeteocatSensorDescription(
        key="wind_gust",
        translation_key="wind_gust",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
    ),
    MeteocatSensorDescription(
        key="observed_at",
        translation_key="observed_at",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MeteocatConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up available Meteocat observation sensors."""
    runtime = entry.runtime_data
    data = runtime.observations.data
    async_add_entities(
        MeteocatObservationSensor(runtime.observations, runtime.settings, description)
        for description in SENSORS
        if description.key in data.available_fields
        or (description.key == "observed_at" and data.observed_at is not None)
    )


class MeteocatObservationSensor(MeteocatCoordinatorEntity, SensorEntity):
    """Representation of one XEMA observation."""

    def __init__(
        self, coordinator: Any, settings: dict[str, Any], description: MeteocatSensorDescription
    ) -> None:
        super().__init__(coordinator, settings)
        self.entity_description = description
        self._attr_unique_id = f"{settings[CONF_ENTRY_ID]}_{description.key}"

    @property
    def native_value(self) -> Any:
        """Return the latest measured value."""
        return getattr(self.coordinator.data, self.entity_description.key, None)
