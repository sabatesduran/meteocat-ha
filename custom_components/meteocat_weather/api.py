"""Async client for the official Meteocat API."""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from aiohttp import ClientError, ClientResponseError, ClientSession

from .const import API_BASE_URL


class MeteocatError(Exception):
    """Base Meteocat client error."""


class MeteocatAuthenticationError(MeteocatError):
    """The API key is absent, invalid, or lacks a required plan."""


class MeteocatRateLimitError(MeteocatError):
    """The account quota was exhausted."""


class MeteocatConnectionError(MeteocatError):
    """The service could not be reached."""


class MeteocatApiError(MeteocatError):
    """The service returned an unexpected response."""

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(f"Meteocat API error ({status}): {detail}")
        self.status = status
        self.detail = detail


class MeteocatApiClient:
    """Small API client using Home Assistant's shared aiohttp session."""

    def __init__(self, session: ClientSession, api_key: str) -> None:
        self._session = session
        self._headers = {"X-Api-Key": api_key, "Accept": "application/json"}

    async def _request(self, path: str) -> Any:
        try:
            async with asyncio.timeout(30):
                async with self._session.get(
                    f"{API_BASE_URL}{path}", headers=self._headers
                ) as response:
                    if response.status in (401, 403):
                        raise MeteocatAuthenticationError(
                            "API key invalid or required Meteocat plan unavailable"
                        )
                    if response.status == 429:
                        raise MeteocatRateLimitError("Meteocat API quota exhausted")
                    if response.status >= 500:
                        raise MeteocatConnectionError(f"Meteocat service error ({response.status})")
                    if response.status >= 400:
                        detail = (await response.text())[:200]
                        raise MeteocatApiError(response.status, detail)
                    return await response.json(content_type=None)
        except TimeoutError as err:
            raise MeteocatConnectionError("Meteocat request timed out") from err
        except (ClientError, ClientResponseError) as err:
            raise MeteocatConnectionError("Unable to connect to Meteocat") from err

    async def async_get_municipalities(self) -> Any:
        """Return reference municipalities."""
        return await self._request("/referencia/v1/municipis")

    async def async_get_stations(self) -> Any:
        """Return operational XEMA stations."""
        now = datetime.now(ZoneInfo("Europe/Madrid"))
        payload: Any = []
        # Meteocat commonly returns an empty list for the current date. Start
        # with yesterday and tolerate a few additional publication delays.
        for days_ago in range(1, 8):
            date = (now - timedelta(days=days_ago)).strftime("%Y-%m-%dZ")
            payload = await self._request(f"/xema/v1/estacions/metadades?estat=ope&data={date}")
            stations = payload
            if isinstance(payload, dict):
                stations = payload.get("estacions", payload.get("stations", payload.get("data")))
            if isinstance(stations, list) and stations:
                return payload
        return payload

    async def async_get_station_metadata(self, station_id: str) -> Any:
        """Return metadata for one XEMA station."""
        return await self._request(f"/xema/v1/estacions/{station_id}/metadades")

    async def async_get_observations(self, station_id: str) -> Any:
        """Return today's measured station values."""
        now = datetime.now(ZoneInfo("Europe/Madrid"))

        async def request_date(value: datetime) -> Any:
            return await self._request(
                f"/xema/v1/estacions/mesurades/{station_id}/"
                f"{value.year}/{value.month:02d}/{value.day:02d}"
            )

        try:
            return await request_date(now)
        except MeteocatApiError as err:
            if err.status != 400:
                raise
            match = re.search(r"entre\s+(\d{2}-\d{2}-\d{4})\s+i", err.detail)
            if match:
                fallback = datetime.strptime(match.group(1), "%d-%m-%Y").replace(tzinfo=now.tzinfo)
                return await request_date(fallback)
            if "no mesura la variable 'null'" in err.detail:
                return await request_date(now - timedelta(days=1))
            raise

    async def async_get_hourly_forecast(self, town_id: str) -> Any:
        """Return the 72-hour municipal forecast."""
        return await self._request(f"/pronostic/v1/municipalHoraria/{town_id}")

    async def async_get_daily_forecast(self, town_id: str) -> Any:
        """Return the daily municipal forecast."""
        return await self._request(f"/pronostic/v1/municipal/{town_id}")

    async def async_get_quotas(self) -> Any:
        """Return current API consumption."""
        return await self._request("/quotes/v1/consum-actual")
