"""Animated Meteocat radar camera."""

from __future__ import annotations

from typing import Any, override

from homeassistant.components.camera import Camera
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MeteocatConfigEntry
from .const import ATTRIBUTION, CONF_ENTRY_ID
from .entity import meteocat_device_info
from .radar import MeteocatRadarCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MeteocatConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Meteocat radar camera."""
    runtime = entry.runtime_data
    async_add_entities([MeteocatRadarCamera(runtime.radar, runtime.settings)])


class MeteocatRadarCamera(CoordinatorEntity[MeteocatRadarCoordinator], Camera):
    """Animated one-hour rain radar."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
    _attr_translation_key = "radar"

    def __init__(self, coordinator: MeteocatRadarCoordinator, settings: dict[str, Any]) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        Camera.__init__(self)
        self._attr_unique_id = f"{settings[CONF_ENTRY_ID]}_radar"
        self._attr_device_info = meteocat_device_info(settings)
        self.content_type = "image/gif"

    @override
    async def async_added_to_hass(self) -> None:
        """Build the animation only when the camera entity is enabled."""
        await super().async_added_to_hass()
        if not self.coordinator.last_update_success:
            await self.coordinator.async_request_refresh()

    @override
    def camera_image(self, width: int | None = None, height: int | None = None) -> bytes | None:
        """Return the latest rendered GIF."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.image

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return radar timestamp and frame count."""
        if not self.coordinator.data:
            return {}
        return {
            "latest_frame": self.coordinator.data.latest.isoformat(),
            "frame_count": self.coordinator.data.frame_count,
        }
