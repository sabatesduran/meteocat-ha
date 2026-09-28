"""Shared entity helpers for Meteocat Weather."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTRIBUTION,
    CONF_ENTRY_ID,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    CONF_TOWN_NAME,
    DOMAIN,
    MANUFACTURER,
)


def meteocat_device_info(settings: dict[str, Any]) -> DeviceInfo:
    """Return the shared Meteocat device metadata."""
    station_id = settings[CONF_STATION_ID]
    return DeviceInfo(
        identifiers={(DOMAIN, settings[CONF_ENTRY_ID])},
        name=f"Meteocat {settings[CONF_TOWN_NAME]}",
        manufacturer=MANUFACTURER,
        model=f"XEMA {settings[CONF_STATION_NAME]} ({station_id})",
        configuration_url="https://www.meteo.cat/observacions/xema",
    )


class MeteocatCoordinatorEntity(CoordinatorEntity):
    """Base class for Meteocat coordinator entities."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(self, coordinator: Any, settings: dict[str, Any]) -> None:
        super().__init__(coordinator)
        self.settings = settings
        self._attr_device_info = meteocat_device_info(settings)
