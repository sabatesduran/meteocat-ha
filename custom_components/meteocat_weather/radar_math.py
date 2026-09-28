"""Pure map calculations used by the Meteocat radar renderer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from math import asinh, floor, pi, radians, tan

TILE_SIZE = 256


@dataclass(slots=True, frozen=True)
class TilePlacement:
    """One map tile and its position on the uncropped canvas."""

    x: int
    y: int
    server_y: int
    left: int
    top: int


def web_mercator_pixel(latitude: float, longitude: float, zoom: int) -> tuple[float, float]:
    """Return global slippy-map pixel coordinates."""
    latitude = max(-85.05112878, min(85.05112878, latitude))
    scale = (2**zoom) * TILE_SIZE
    x = (longitude + 180.0) / 360.0 * scale
    y = (1.0 - asinh(tan(radians(latitude))) / pi) / 2.0 * scale
    return x, y


def tile_layout(
    latitude: float,
    longitude: float,
    zoom: int,
    width: int,
    height: int,
) -> tuple[list[TilePlacement], tuple[int, int, int, int]]:
    """Calculate the tiles and crop rectangle for a centered viewport."""
    center_x, center_y = web_mercator_pixel(latitude, longitude, zoom)
    viewport_left = center_x - width / 2
    viewport_top = center_y - height / 2
    first_x = floor(viewport_left / TILE_SIZE)
    first_y = floor(viewport_top / TILE_SIZE)
    last_x = floor((viewport_left + width - 1) / TILE_SIZE)
    last_y = floor((viewport_top + height - 1) / TILE_SIZE)
    world_tiles = 2**zoom
    placements: list[TilePlacement] = []
    for tile_y in range(first_y, last_y + 1):
        if tile_y < 0 or tile_y >= world_tiles:
            continue
        for tile_x in range(first_x, last_x + 1):
            wrapped_x = tile_x % world_tiles
            placements.append(
                TilePlacement(
                    x=wrapped_x,
                    y=tile_y,
                    server_y=world_tiles - 1 - tile_y,
                    left=(tile_x - first_x) * TILE_SIZE,
                    top=(tile_y - first_y) * TILE_SIZE,
                )
            )
    crop_left = round(viewport_left - first_x * TILE_SIZE)
    crop_top = round(viewport_top - first_y * TILE_SIZE)
    return placements, (crop_left, crop_top, crop_left + width, crop_top + height)


def parse_radar_timestamp(value: str) -> datetime:
    """Parse the public radar metadata timestamp."""
    for pattern in ("%m/%d/%Y %H:%MZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(value, pattern).replace(tzinfo=UTC)
        except ValueError:
            continue
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.astimezone(UTC)
