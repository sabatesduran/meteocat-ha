"""Meteocat radar tile downloader and GIF compositor."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from io import BytesIO
from typing import Any

from aiohttp import ClientError, ClientSession
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from PIL import Image, ImageDraw

from .const import (
    BASE_TILE_PATH,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADAR_FRAMES,
    CONF_RADAR_ZOOM,
    DEFAULT_RADAR_FRAMES,
    DEFAULT_RADAR_HEIGHT,
    DEFAULT_RADAR_WIDTH,
    DEFAULT_RADAR_ZOOM,
    DOMAIN,
    RADAR_BASE_URL,
    RADAR_METADATA_PATH,
    RADAR_TILE_PATH,
    RADAR_UPDATE_INTERVAL,
)
from .radar_math import TILE_SIZE, TilePlacement, parse_radar_timestamp, tile_layout

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class RadarResult:
    """Rendered radar animation and metadata."""

    image: bytes
    latest: datetime
    frame_count: int


class RadarProvider:
    """Download official public tiles and produce a cached one-hour GIF."""

    def __init__(self, session: ClientSession, settings: dict[str, Any]) -> None:
        self._session = session
        self.latitude = float(settings[CONF_LATITUDE])
        self.longitude = float(settings[CONF_LONGITUDE])
        self.zoom = int(settings.get(CONF_RADAR_ZOOM, DEFAULT_RADAR_ZOOM))
        self.frame_limit = int(settings.get(CONF_RADAR_FRAMES, DEFAULT_RADAR_FRAMES))
        self.width = DEFAULT_RADAR_WIDTH
        self.height = DEFAULT_RADAR_HEIGHT
        self._base_tiles: dict[tuple[int, int, int], bytes] = {}
        self._radar_tiles: dict[tuple[str, int, int, int], bytes | None] = {}
        self._frames: dict[datetime, Image.Image] = {}
        self._download_limit = asyncio.Semaphore(12)

    async def _get_bytes(self, url: str) -> bytes | None:
        try:
            async with self._download_limit:
                async with asyncio.timeout(20):
                    async with self._session.get(url) as response:
                        if response.status == 404:
                            return None
                        response.raise_for_status()
                        return await response.read()
        except (ClientError, TimeoutError) as err:
            _LOGGER.debug("Radar resource unavailable (%s): %s", url, err)
            return None

    async def _latest_timestamp(self) -> datetime:
        try:
            async with asyncio.timeout(20):
                async with self._session.get(f"{RADAR_BASE_URL}{RADAR_METADATA_PATH}") as response:
                    response.raise_for_status()
                    payload = await response.json(content_type=None)
        except (ClientError, TimeoutError, ValueError) as err:
            raise UpdateFailed("Unable to read Meteocat radar metadata") from err
        value = payload.get("dataUltimaImatge")
        if not isinstance(value, str):
            raise UpdateFailed("Invalid Meteocat radar metadata")
        try:
            return parse_radar_timestamp(value)
        except ValueError as err:
            raise UpdateFailed("Invalid Meteocat radar timestamp") from err

    @staticmethod
    def _tile_parts(zoom: int, x: int, server_y: int) -> tuple[str, str, str]:
        return f"{zoom:02d}", f"{x:03d}", f"{server_y:03d}"

    async def _base_tile(self, placement: TilePlacement) -> bytes | None:
        key = (self.zoom, placement.x, placement.server_y)
        if key not in self._base_tiles:
            z, x, y = self._tile_parts(*key)
            tile = await self._get_bytes(f"{RADAR_BASE_URL}{BASE_TILE_PATH.format(z=z, x=x, y=y)}")
            if tile:
                self._base_tiles[key] = tile
            return tile
        return self._base_tiles[key]

    async def _radar_tile(self, timestamp: datetime, placement: TilePlacement) -> bytes | None:
        stamp = timestamp.strftime("%Y/%m/%d/%H/%M")
        key = (stamp, self.zoom, placement.x, placement.server_y)
        if key not in self._radar_tiles:
            z, x, y = self._tile_parts(self.zoom, placement.x, placement.server_y)
            self._radar_tiles[key] = await self._get_bytes(
                f"{RADAR_BASE_URL}{RADAR_TILE_PATH.format(timestamp=stamp, z=z, x=x, y=y)}"
            )
        return self._radar_tiles[key]

    async def async_build_animation(self, hass: HomeAssistant) -> RadarResult:
        """Fetch missing tiles, render frames, and encode the rolling GIF."""
        latest = await self._latest_timestamp()
        timestamps = [
            latest - timedelta(minutes=6 * offset) for offset in reversed(range(self.frame_limit))
        ]
        placements, crop = tile_layout(
            self.latitude, self.longitude, self.zoom, self.width, self.height
        )
        base_values = await asyncio.gather(
            *(self._base_tile(placement) for placement in placements)
        )
        base = dict(zip(placements, base_values, strict=True))

        for timestamp in timestamps:
            if timestamp in self._frames:
                continue
            radar_values = await asyncio.gather(
                *(self._radar_tile(timestamp, placement) for placement in placements)
            )
            radar = dict(zip(placements, radar_values, strict=True))
            if not any(radar.values()):
                continue
            self._frames[timestamp] = await hass.async_add_executor_job(
                self._render_frame, base, radar, placements, crop, timestamp
            )

        wanted = set(timestamps)
        self._frames = {
            timestamp: frame for timestamp, frame in self._frames.items() if timestamp in wanted
        }
        self._radar_tiles = {
            key: value
            for key, value in self._radar_tiles.items()
            if datetime.strptime(key[0], "%Y/%m/%d/%H/%M").replace(tzinfo=UTC) in wanted
        }
        ordered = [self._frames[item] for item in timestamps if item in self._frames]
        if not ordered:
            raise UpdateFailed("No Meteocat radar frames are available")
        animation = await hass.async_add_executor_job(self._encode_gif, ordered)
        return RadarResult(animation, latest, len(ordered))

    def _render_frame(
        self,
        base: dict[TilePlacement, bytes | None],
        radar: dict[TilePlacement, bytes | None],
        placements: list[TilePlacement],
        crop: tuple[int, int, int, int],
        timestamp: datetime,
    ) -> Image.Image:
        canvas_width = max(item.left for item in placements) + TILE_SIZE
        canvas_height = max(item.top for item in placements) + TILE_SIZE
        canvas = Image.new("RGBA", (canvas_width, canvas_height), "#d8e0e5")
        for placement in placements:
            if tile := base.get(placement):
                with Image.open(BytesIO(tile)) as image:
                    canvas.alpha_composite(image.convert("RGBA"), (placement.left, placement.top))
        for placement in placements:
            if tile := radar.get(placement):
                with Image.open(BytesIO(tile)) as image:
                    canvas.alpha_composite(image.convert("RGBA"), (placement.left, placement.top))
        frame = canvas.crop(crop)
        draw = ImageDraw.Draw(frame, "RGBA")
        center_x, center_y = self.width // 2, self.height // 2
        draw.ellipse(
            (center_x - 7, center_y - 7, center_x + 7, center_y + 7),
            fill=(255, 255, 255, 230),
            outline=(190, 20, 35, 255),
            width=3,
        )
        draw.rectangle((0, self.height - 52, self.width, self.height), fill=(14, 26, 37, 210))
        draw.text(
            (12, self.height - 43),
            f"Radar Meteocat · {timestamp:%d/%m/%Y %H:%M} UTC",
            fill="white",
        )
        colors = ("#2b83ba", "#00a65a", "#ffe135", "#f46d43", "#a50026")
        start_x = self.width - 247
        for index, color in enumerate(colors):
            draw.rectangle(
                (
                    start_x + index * 24,
                    self.height - 24,
                    start_x + 24 + index * 24,
                    self.height - 13,
                ),
                fill=color,
            )
        draw.text((start_x - 38, self.height - 28), "feble", fill="white")
        draw.text((start_x + 127, self.height - 28), "forta", fill="white")
        draw.text((self.width - 103, self.height - 43), "© Meteocat", fill="white")
        return frame.convert("RGB")

    @staticmethod
    def _encode_gif(frames: list[Image.Image]) -> bytes:
        output = BytesIO()
        durations = [450] * len(frames)
        durations[-1] = 1200
        frames[0].save(
            output,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            loop=0,
            disposal=2,
            optimize=False,
        )
        return output.getvalue()


class MeteocatRadarCoordinator(DataUpdateCoordinator[RadarResult]):
    """Coordinate public radar animation updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        provider: RadarProvider,
        settings: dict[str, Any],
    ) -> None:
        self.provider = provider
        self.using_cached_data = False
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_radar",
            update_interval=RADAR_UPDATE_INTERVAL,
        )
        # Radar is intentionally not fetched during config-entry setup.
        self.last_update_success = False

    async def _async_update_data(self) -> RadarResult:
        try:
            result = await self.provider.async_build_animation(self.hass)
        except UpdateFailed as err:
            if self.data is not None:
                self.using_cached_data = True
                _LOGGER.warning("Meteocat radar unavailable; keeping cached animation: %s", err)
                return self.data
            raise
        except Exception as err:
            if self.data is not None:
                self.using_cached_data = True
                _LOGGER.warning("Meteocat radar unavailable; keeping cached animation: %s", err)
                return self.data
            raise UpdateFailed(f"Unable to render Meteocat radar: {err}") from err
        self.using_cached_data = False
        return result
