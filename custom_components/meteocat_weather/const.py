"""Constants for Meteocat Weather."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "meteocat_weather"
NAME: Final = "Meteocat Weather"
MANUFACTURER: Final = "Servei Meteorològic de Catalunya"
ATTRIBUTION: Final = "Dades del Servei Meteorològic de Catalunya (Meteocat)"

CONF_API_KEY: Final = "api_key"
CONF_LATITUDE: Final = "latitude"
CONF_LONGITUDE: Final = "longitude"
CONF_TOWN_ID: Final = "town_id"
CONF_TOWN_NAME: Final = "town_name"
CONF_STATION_ID: Final = "station_id"
CONF_STATION_NAME: Final = "station_name"
CONF_OBSERVATION_INTERVAL: Final = "observation_interval"
CONF_FORECAST_INTERVAL: Final = "forecast_interval"
CONF_RADAR_ZOOM: Final = "radar_zoom"
CONF_RADAR_FRAMES: Final = "radar_frames"
CONF_ENTRY_ID: Final = "_entry_id"

DEFAULT_OBSERVATION_INTERVAL: Final = 90
DEFAULT_FORECAST_INTERVAL: Final = 24
DEFAULT_RADAR_ZOOM: Final = 7
DEFAULT_RADAR_FRAMES: Final = 11
DEFAULT_RADAR_WIDTH: Final = 640
DEFAULT_RADAR_HEIGHT: Final = 480

MIN_LATITUDE: Final = 40.45
MAX_LATITUDE: Final = 42.95
MIN_LONGITUDE: Final = -0.2
MAX_LONGITUDE: Final = 3.45

OBSERVATION_UPDATE_INTERVAL: Final = timedelta(minutes=DEFAULT_OBSERVATION_INTERVAL)
FORECAST_UPDATE_INTERVAL: Final = timedelta(hours=DEFAULT_FORECAST_INTERVAL)
RADAR_UPDATE_INTERVAL: Final = timedelta(minutes=6)

API_BASE_URL: Final = "https://api.meteo.cat"
RADAR_BASE_URL: Final = "https://static-m.meteo.cat"
RADAR_METADATA_PATH: Final = "/ginys/referencia/tiles/dates-tiles-CAPPI_0m.json"
RADAR_TILE_PATH: Final = "/tiles/radar/{timestamp}/{z}/000/000/{x}/000/000/{y}.png"
BASE_TILE_PATH: Final = "/tiles/fons/GoogleMapsCompatible/{z}/000/000/{x}/000/000/{y}.png"

PLATFORMS: Final = ["sensor", "weather", "camera"]

VARIABLE_CODES: Final = {
    "wind_speed": 30,
    "wind_bearing": 31,
    "temperature": 32,
    "humidity": 33,
    "pressure": 34,
    "precipitation": 35,
    "wind_gust": 50,
}

CONDITION_CODES: Final = {
    "sunny": {1},
    "partlycloudy": {2, 3},
    "cloudy": {4, 20, 21, 22},
    "rainy": {5, 6, 23},
    "pouring": {7, 25},
    "lightning-rainy": {8, 24},
    "hail": {9},
    "snowy": {10, 26, 28},
    "fog": {11, 12},
    "snowy-rainy": {27, 29, 30},
}
