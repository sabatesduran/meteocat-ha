"""Diagnostics support for Meteocat Weather."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import MeteocatConfigEntry
from .const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE

TO_REDACT = {CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: MeteocatConfigEntry
) -> dict[str, Any]:
    """Return safe diagnostics without credentials or exact coordinates."""
    runtime = entry.runtime_data
    radar = runtime.radar.data
    return {
        "config": async_redact_data(dict(entry.data), TO_REDACT),
        "options": async_redact_data(dict(entry.options), TO_REDACT),
        "observations": runtime.observations.data.as_dict(),
        "observations_using_cache": runtime.observations.using_cached_data,
        "forecast": {
            "hourly_entries": len(runtime.forecast.data.get("hourly", [])),
            "daily_entries": len(runtime.forecast.data.get("daily", [])),
            "last_update_success": runtime.forecast.last_update_success,
            "using_cache": runtime.forecast.using_cached_data,
        },
        "radar": {
            "available": radar is not None,
            "latest_frame": radar.latest.isoformat() if radar else None,
            "frame_count": radar.frame_count if radar else 0,
            "last_update_success": runtime.radar.last_update_success,
            "using_cache": runtime.radar.using_cached_data,
        },
    }
