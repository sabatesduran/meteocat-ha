"""Tests for Meteocat data normalization."""

from datetime import UTC, datetime

from custom_components.meteocat_weather.models import (
    closest_station,
    condition_from_code,
    normalize_municipalities,
    normalize_stations,
    parse_daily_forecast,
    parse_hourly_forecast,
    parse_observations,
    quota_aware_intervals,
)


def test_normalizes_reference_data_and_finds_nearest_station() -> None:
    towns = normalize_municipalities(
        [{"codi": "080193", "nom": "Barcelona"}, {"codi": "170792", "nom": "Girona"}]
    )
    stations = normalize_stations(
        [
            {
                "codi": "X1",
                "nom": "Barcelona - Observatori Fabra",
                "coordenades": {"latitud": 41.418, "longitud": 2.124},
                "municipi": {"codi": "080193", "nom": "Barcelona"},
                "estats": [{"codi": 2}],
            },
            {
                "codi": "X2",
                "nom": "Girona",
                "coordenades": {"latitud": 41.98, "longitud": 2.82},
                "municipi": {"codi": "170792", "nom": "Girona"},
                "estats": [{"codi": "ope"}],
            },
        ]
    )
    assert [town.name for town in towns] == ["Barcelona", "Girona"]
    assert [station.code for station in stations] == ["X1", "X2"]
    assert closest_station(stations, 41.39, 2.17).code == "X1"


def test_parses_latest_station_observations() -> None:
    payload = [
        {
            "codi": "X1",
            "variables": [
                {
                    "codi": 32,
                    "lectures": [
                        {"data": "2026-09-28T12:00:00Z", "valor": 21.4},
                        {"data": "2026-09-28T13:00:00Z", "valor": "22.1"},
                    ],
                },
                {"codi": 33, "lectures": [{"data": "2026-09-28T13:00:00Z", "valor": 61}]},
                {"codi": 34, "lectures": [{"data": "2026-09-28T13:00:00Z", "valor": 1014.2}]},
                {"codi": 35, "lectures": [{"data": "2026-09-28T13:00:00Z", "valor": 0.4}]},
                {"codi": 30, "lectures": [{"data": "2026-09-28T13:00:00Z", "valor": 8.2}]},
                {"codi": 31, "lectures": [{"data": "2026-09-28T13:00:00Z", "valor": 225}]},
                {"codi": 50, "lectures": [{"data": "2026-09-28T13:00:00Z", "valor": 16.8}]},
            ],
        }
    ]
    result = parse_observations(payload)
    assert result.temperature == 22.1
    assert result.humidity == 61
    assert result.precipitation == 0.4
    assert result.wind_gust == 16.8
    assert result.observed_at == datetime(2026, 9, 28, 13, tzinfo=UTC)


def test_parses_hourly_forecast() -> None:
    payload = {
        "dies": [
            {
                "data": "2026-09-28Z",
                "variables": {
                    "estatCel": {"valors": [{"data": "2026-09-28T12:00:00Z", "valor": 3}]},
                    "temp": {"valors": [{"data": "2026-09-28T12:00:00Z", "valor": 24}]},
                    "precipitacio": {"valors": [{"data": "2026-09-28T12:00:00Z", "valor": 35}]},
                    "velVent": {"valors": [{"data": "2026-09-28T12:00:00Z", "valor": 12}]},
                    "dirVent": {"valors": [{"data": "2026-09-28T12:00:00Z", "valor": 180}]},
                    "humitat": {"valors": [{"data": "2026-09-28T12:00:00Z", "valor": 56}]},
                },
            }
        ]
    }
    assert parse_hourly_forecast(payload) == [
        {
            "datetime": "2026-09-28T12:00:00+00:00",
            "condition": "partlycloudy",
            "temperature": 24.0,
            "precipitation_probability": 35.0,
            "wind_speed": 12.0,
            "wind_bearing": 180.0,
            "humidity": 56.0,
        }
    ]


def test_parses_daily_forecast_and_conditions() -> None:
    payload = {
        "dies": [
            {
                "data": "2026-09-29T00:00:00Z",
                "variables": {
                    "estatCel": {"valor": 6},
                    "tmax": {"valor": "25"},
                    "tmin": {"valor": "14"},
                    "precipitacio": {"valor": "70"},
                },
            }
        ]
    }
    assert parse_daily_forecast(payload)[0] == {
        "datetime": "2026-09-29",
        "condition": "rainy",
        "temperature": 25.0,
        "templow": 14.0,
        "precipitation_probability": 70.0,
    }
    assert condition_from_code(1, datetime(2026, 9, 29, 2, tzinfo=UTC)) == "clear-night"
    assert condition_from_code("bad") is None


def test_chooses_quota_aware_intervals() -> None:
    payload = {
        "plans": [
            {"nom": "XEMA_750", "maxConsultes": 750},
            {"nom": "Predicció_100", "maxConsultes": 100},
        ]
    }
    assert quota_aware_intervals(payload) == (90, 24)
    assert quota_aware_intervals({"plans": []}) == (90, 24)
    assert quota_aware_intervals(
        {
            "plans": [
                {"nom": "XEMA", "maxConsultes": 10_000},
                {"nom": "Predicció", "maxConsultes": 10_000},
            ]
        }
    ) == (90, 24)
