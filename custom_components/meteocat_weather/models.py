"""Data models and pure parsers for Meteocat Weather."""

from __future__ import annotations

import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from math import asin, cos, radians, sin, sqrt
from typing import Any

from .const import (
    ALLOWED_FORECAST_INTERVALS,
    ALLOWED_OBSERVATION_INTERVALS,
    CONDITION_CODES,
    DEFAULT_FORECAST_INTERVAL,
    DEFAULT_OBSERVATION_INTERVAL,
    VARIABLE_CODES,
)


@dataclass(slots=True, frozen=True)
class Municipality:
    """A Meteocat municipality."""

    code: str
    name: str


@dataclass(slots=True, frozen=True)
class Station:
    """A Meteocat XEMA station."""

    code: str
    name: str
    latitude: float | None
    longitude: float | None
    municipality_code: str | None = None
    municipality_name: str | None = None


@dataclass(slots=True)
class Observations:
    """Latest observations from one XEMA station."""

    temperature: float | None = None
    humidity: float | None = None
    pressure: float | None = None
    precipitation: float | None = None
    wind_speed: float | None = None
    wind_bearing: float | None = None
    wind_gust: float | None = None
    observed_at: datetime | None = None
    available_fields: frozenset[str] = field(default_factory=frozenset)

    def as_dict(self) -> dict[str, Any]:
        """Return a serializable diagnostic dictionary."""
        values = asdict(self)
        if self.observed_at:
            values["observed_at"] = self.observed_at.isoformat()
        values["available_fields"] = sorted(self.available_fields)
        return values


def _float(value: Any) -> float | None:
    """Convert an API value to float."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first_present(mapping: dict[str, Any], *keys: str) -> Any:
    """Return the first present, non-null mapping value."""
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return None


def _probability(value: Any) -> float | None:
    """Normalize percentage values and discard Meteocat's negative no-data markers."""
    parsed = _float(value)
    if parsed is None or parsed < 0:
        return None
    return min(parsed, 100.0)


def parse_datetime(value: Any) -> datetime | None:
    """Parse Meteocat's ISO timestamps as timezone-aware datetimes."""
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=parsed.tzinfo or UTC)


def quota_aware_intervals(payload: Any) -> tuple[int, int]:
    """Choose conservative polling intervals from the account's monthly quotas."""
    observation_interval = DEFAULT_OBSERVATION_INTERVAL
    forecast_interval = DEFAULT_FORECAST_INTERVAL
    minutes_per_month = 31 * 24 * 60
    hours_per_month = 31 * 24
    plans = payload.get("plans", []) if isinstance(payload, dict) else []
    for plan in plans:
        if not isinstance(plan, dict):
            continue
        name = unicodedata.normalize("NFKD", str(plan.get("nom", "")))
        name = name.encode("ascii", "ignore").decode().casefold()
        try:
            maximum = int(plan.get("maxConsultes", 0))
        except (TypeError, ValueError):
            continue
        budget = maximum * 0.8
        if name.startswith("xema"):
            observation_interval = next(
                (
                    minutes
                    for minutes in ALLOWED_OBSERVATION_INTERVALS
                    if minutes_per_month / minutes <= budget
                ),
                ALLOWED_OBSERVATION_INTERVALS[-1],
            )
        elif name.startswith("prediccio"):
            # Each forecast refresh uses two calls: hourly and daily.
            forecast_interval = next(
                (
                    hours
                    for hours in ALLOWED_FORECAST_INTERVALS
                    if hours_per_month * 2 / hours <= budget
                ),
                ALLOWED_FORECAST_INTERVALS[-1],
            )
    return observation_interval, forecast_interval


def normalize_municipalities(payload: Any) -> list[Municipality]:
    """Normalize the municipality reference response."""
    if isinstance(payload, dict):
        payload = payload.get("municipis", payload.get("towns", payload.get("data", [])))
    if not isinstance(payload, list):
        return []
    result: list[Municipality] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        code = item.get("codi") or item.get("code")
        name = item.get("nom") or item.get("name")
        if code is not None and name:
            result.append(Municipality(str(code), str(name)))
    return sorted(result, key=lambda item: item.name.casefold())


def _coordinates(item: dict[str, Any]) -> tuple[float | None, float | None]:
    coordinates = item.get("coordenades") or item.get("coordinates") or {}
    latitude = _float(_first_present(coordinates, "latitud", "latitude"))
    longitude = _float(_first_present(coordinates, "longitud", "longitude"))
    if latitude is None:
        latitude = _float(_first_present(item, "latitud", "latitude"))
    if longitude is None:
        longitude = _float(_first_present(item, "longitud", "longitude"))
    return latitude, longitude


def station_from_dict(item: dict[str, Any]) -> Station | None:
    """Normalize one station metadata object."""
    code = item.get("codi") or item.get("code")
    name = item.get("nom") or item.get("name")
    if code is None or not name:
        return None
    latitude, longitude = _coordinates(item)
    town = item.get("municipi") or item.get("municipality") or {}
    town_code = town.get("codi") or town.get("code") if isinstance(town, dict) else None
    town_name = town.get("nom") or town.get("name") if isinstance(town, dict) else None
    return Station(
        code=str(code),
        name=str(name),
        latitude=latitude,
        longitude=longitude,
        municipality_code=str(town_code) if town_code is not None else None,
        municipality_name=str(town_name) if town_name else None,
    )


def normalize_stations(payload: Any) -> list[Station]:
    """Normalize the station metadata response and keep usable stations."""
    if isinstance(payload, dict):
        payload = payload.get("estacions", payload.get("stations", payload.get("data", [])))
    if not isinstance(payload, list):
        return []
    stations: list[Station] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        states = item.get("estats") or item.get("states") or []
        if states and isinstance(states, list):
            state_codes = {
                str(state.get("codi", state.get("code", ""))).lower()
                for state in states
                if isinstance(state, dict)
            }
            # The query parameter uses "ope", while Meteocat serializes that
            # operational state as numeric code 2 in station metadata.
            if state_codes and state_codes.isdisjoint({"ope", "2"}):
                continue
        station = station_from_dict(item)
        if station and station.latitude is not None and station.longitude is not None:
            stations.append(station)
    return stations


def distance_km(latitude: float, longitude: float, station: Station) -> float:
    """Calculate great-circle distance from coordinates to a station."""
    if station.latitude is None or station.longitude is None:
        return float("inf")
    lat1, lon1, lat2, lon2 = map(
        radians, (latitude, longitude, station.latitude, station.longitude)
    )
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    value = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 6371.0088 * 2 * asin(sqrt(value))


def closest_station(stations: list[Station], latitude: float, longitude: float) -> Station | None:
    """Return the closest station to a coordinate."""
    return min(stations, key=lambda item: distance_km(latitude, longitude, item), default=None)


def parse_observations(payload: Any) -> Observations:
    """Extract the latest value for each essential XEMA variable."""
    if isinstance(payload, dict):
        payload = payload.get("data", payload.get("estacions", []))
    blocks = payload if isinstance(payload, list) else []
    reverse_codes = {value: key for key, value in VARIABLE_CODES.items()}
    latest: dict[str, tuple[datetime | None, float]] = {}
    latest_timestamp: datetime | None = None
    available_fields: set[str] = set()

    for block in blocks:
        if not isinstance(block, dict):
            continue
        for variable in block.get("variables", []):
            if not isinstance(variable, dict):
                continue
            try:
                key = reverse_codes.get(int(variable.get("codi")))
            except (TypeError, ValueError):
                key = None
            if key is None:
                continue
            available_fields.add(key)
            readings = variable.get("lectures") or []
            if not isinstance(readings, list):
                continue
            for reading in readings:
                if not isinstance(reading, dict) or (value := _float(reading.get("valor"))) is None:
                    continue
                timestamp = parse_datetime(reading.get("data"))
                current = latest.get(key)
                if current is None or (
                    timestamp is not None and (current[0] is None or timestamp > current[0])
                ):
                    latest[key] = (timestamp, value)
                if timestamp and (latest_timestamp is None or timestamp > latest_timestamp):
                    latest_timestamp = timestamp

    result = Observations(
        observed_at=latest_timestamp, available_fields=frozenset(available_fields)
    )
    for key, (_, value) in latest.items():
        setattr(result, key, value)
    return result


def condition_from_code(code: Any, timestamp: datetime | None = None) -> str | None:
    """Map a Meteocat sky-state code to a Home Assistant condition."""
    try:
        number = int(code)
    except (TypeError, ValueError):
        return None
    for condition, codes in CONDITION_CODES.items():
        if number in codes:
            if condition == "sunny" and timestamp and (timestamp.hour < 7 or timestamp.hour >= 20):
                return "clear-night"
            return condition
    return None


def _variable_values(day: dict[str, Any], name: str) -> list[dict[str, Any]]:
    variable = day.get("variables", {}).get(name, {})
    values = variable.get("valors", variable.get("valor", [])) if isinstance(variable, dict) else []
    return values if isinstance(values, list) else []


def _value_at(day: dict[str, Any], name: str, timestamp: datetime) -> float | None:
    for item in _variable_values(day, name):
        if not isinstance(item, dict):
            continue
        item_time = parse_datetime(item.get("data"))
        if item_time == timestamp:
            return _float(item.get("valor"))
    return None


def _scalar_value(variables: Any, name: str) -> Any:
    """Return one scalar daily forecast value."""
    variable = variables.get(name, {}) if isinstance(variables, dict) else {}
    return variable.get("valor") if isinstance(variable, dict) else None


def parse_hourly_forecast(payload: Any) -> list[dict[str, Any]]:
    """Convert Meteocat municipal hourly data to HA forecast dictionaries."""
    days = payload.get("dies", []) if isinstance(payload, dict) else []
    result: list[dict[str, Any]] = []
    for day in days:
        if not isinstance(day, dict):
            continue
        for sky in _variable_values(day, "estatCel"):
            if not isinstance(sky, dict) or (timestamp := parse_datetime(sky.get("data"))) is None:
                continue
            item: dict[str, Any] = {"datetime": timestamp.isoformat()}
            values = {
                "condition": condition_from_code(sky.get("valor"), timestamp),
                "temperature": _value_at(day, "temp", timestamp),
                "precipitation_probability": _probability(
                    _value_at(day, "precipitacio", timestamp)
                ),
                "wind_speed": _value_at(day, "velVent", timestamp),
                "wind_bearing": _value_at(day, "dirVent", timestamp),
                "humidity": _value_at(day, "humitat", timestamp),
            }
            item.update({key: value for key, value in values.items() if value is not None})
            result.append(item)
    return sorted(result, key=lambda item: item["datetime"])


def parse_daily_forecast(payload: Any) -> list[dict[str, Any]]:
    """Convert Meteocat municipal daily data to HA forecast dictionaries."""
    days = payload.get("dies", []) if isinstance(payload, dict) else []
    result: list[dict[str, Any]] = []
    for day in days:
        if not isinstance(day, dict) or (timestamp := parse_datetime(day.get("data"))) is None:
            continue
        variables = day.get("variables", {})

        item: dict[str, Any] = {"datetime": timestamp.date().isoformat()}
        values = {
            "condition": condition_from_code(_scalar_value(variables, "estatCel"), timestamp),
            "temperature": _float(_scalar_value(variables, "tmax")),
            "templow": _float(_scalar_value(variables, "tmin")),
            "precipitation_probability": _probability(_scalar_value(variables, "precipitacio")),
        }
        item.update({key: value for key, value in values.items() if value is not None})
        result.append(item)
    return sorted(result, key=lambda item: item["datetime"])
