"""Tests for Meteocat API error handling."""

import asyncio
import re
from typing import Any

import pytest

from custom_components.meteocat_weather.api import (
    MeteocatApiClient,
    MeteocatAuthenticationError,
)


class FakeResponse:
    """Minimal aiohttp response context manager."""

    def __init__(self, status: int, payload: Any = None, text: str = "") -> None:
        self.status = status
        self.payload = payload
        self.text_value = text

    async def __aenter__(self) -> "FakeResponse":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def json(self, content_type: Any = None) -> Any:
        return self.payload

    async def text(self) -> str:
        return self.text_value


class FakeSession:
    """Return queued responses and record requested URLs."""

    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.urls: list[str] = []

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.urls.append(url)
        return self.responses.pop(0)


def test_station_filter_includes_required_date() -> None:
    session = FakeSession([FakeResponse(200, payload=[])])

    asyncio.run(MeteocatApiClient(session, "secret").async_get_stations())

    assert re.search(
        r"/xema/v1/estacions/metadades\?estat=ope&data=\d{4}-\d{2}-\d{2}Z$",
        session.urls[-1],
    )


def test_observations_retry_last_available_date() -> None:
    session = FakeSession(
        [
            FakeResponse(
                400,
                text='{"message":"Dades disponibles entre 27-09-2026 i 28-09-2026"}',
            ),
            FakeResponse(200, payload=[{"codi": "X1", "variables": []}]),
        ]
    )
    result = asyncio.run(MeteocatApiClient(session, "secret").async_get_observations("X1"))
    assert result == [{"codi": "X1", "variables": []}]
    assert session.urls[-1].endswith("/X1/2026/09/27")


def test_authentication_error_does_not_include_key() -> None:
    session = FakeSession([FakeResponse(403)])
    with pytest.raises(MeteocatAuthenticationError) as caught:
        asyncio.run(MeteocatApiClient(session, "very-secret").async_get_municipalities())
    assert "very-secret" not in str(caught.value)
