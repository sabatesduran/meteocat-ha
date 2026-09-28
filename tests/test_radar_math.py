"""Tests for Meteocat's TMS radar tile geometry."""

from datetime import UTC, datetime

from custom_components.meteocat_weather.radar_math import (
    parse_radar_timestamp,
    tile_layout,
    web_mercator_pixel,
)


def test_barcelona_tile_matches_meteocat_tms_layout() -> None:
    x, y = web_mercator_pixel(41.3874, 2.1686, 7)
    assert int(x // 256) == 64
    slippy_y = int(y // 256)
    assert 127 - slippy_y == 80

    placements, crop = tile_layout(41.3874, 2.1686, 7, 640, 480)
    assert any(item.x == 64 and item.server_y == 80 for item in placements)
    assert crop[2] - crop[0] == 640
    assert crop[3] - crop[1] == 480


def test_radar_timestamp_formats() -> None:
    expected = datetime(2026, 9, 28, 15, 54, tzinfo=UTC)
    assert parse_radar_timestamp("09/28/2026 15:54Z") == expected
    assert parse_radar_timestamp("2026-09-28T15:54:00Z") == expected
