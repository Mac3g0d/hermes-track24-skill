"""Fixtures that impersonate the Track24 web flow on top of ``pytest_httpx``."""

import asyncio
import urllib.parse
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest
from pytest_httpx import HTTPXMock

import track24
from constants import (
    ENDPOINT_PATH,
    HTTP_OK,
    PAGE_URL_PATTERN,
    PAGE_WITH_LITERAL_TEMPLATE,
    PASSWORD,
    TRACK24_BASE_URL,
)
from fixtures.crypto import Encrypt
from fixtures.payloads import ResultFor
from track24_constants import DEFAULT_TIMEOUT_SECONDS


@dataclass
class FakeTrack24:
    """Registers synthetic Track24 responses and exposes what the client sent."""

    httpx_mock: HTTPXMock
    encrypt: Encrypt
    result_for: ResultFor
    peak_in_flight: int = 0
    _in_flight: int = field(default=0, repr=False)

    @staticmethod
    def literal_page(password: str = PASSWORD, endpoint: str = ENDPOINT_PATH) -> str:
        """A page exposing both literals directly."""
        return PAGE_WITH_LITERAL_TEMPLATE.format(password=password, endpoint=endpoint)

    def page(self, html: str | None = None, **response: Any) -> None:
        """Serve ``html`` (by default the literal page) for every tracking-page GET."""
        content = self.literal_page() if html is None else html
        self.httpx_mock.add_response(method="GET", url=PAGE_URL_PATTERN, html=content, is_reusable=True, **response)

    def payload(self, payload: Any, path: str = ENDPOINT_PATH, **options: Any) -> None:
        """Answer the tracking POST with the encrypted ``payload``."""
        self.respond(json=self.encrypt(payload, **options), path=path)

    def respond(self, path: str = ENDPOINT_PATH, **response: Any) -> None:
        """Answer the tracking POST with an arbitrary response."""
        self.httpx_mock.add_response(method="POST", url=TRACK24_BASE_URL + path, **response)

    def fail_page(self, error: Exception, reusable: bool = False) -> None:
        """Raise ``error`` from the transport for the tracking-page GET."""
        self.httpx_mock.add_exception(error, url=PAGE_URL_PATTERN, is_reusable=reusable)

    def echo(self, delay_seconds: float = 0.0) -> None:
        """Answer every tracking POST with a result for the posted identifier."""

        async def callback(request: httpx.Request) -> httpx.Response:
            self._in_flight += 1
            self.peak_in_flight = max(self.peak_in_flight, self._in_flight)
            try:
                await asyncio.sleep(delay_seconds)
            finally:
                self._in_flight -= 1
            code = self.form_of(request)["code"][0]
            return httpx.Response(HTTP_OK, json=self.encrypt(self.result_for(code)))

        self.httpx_mock.add_callback(callback, method="POST", url=TRACK24_BASE_URL + ENDPOINT_PATH, is_reusable=True)

    @staticmethod
    def form_of(request: httpx.Request) -> dict[str, list[str]]:
        """Decode a urlencoded request body."""
        return urllib.parse.parse_qs(request.content.decode(), keep_blank_values=True)

    @property
    def requests(self) -> list[httpx.Request]:
        """Every request the client sent, in order."""
        return list(self.httpx_mock.get_requests())

    @property
    def calls(self) -> list[tuple[str, str]]:
        """``(method, path)`` for every request the client sent, in order."""
        return [(request.method, request.url.path) for request in self.requests]


@pytest.fixture
def site(httpx_mock: HTTPXMock, encrypt: Encrypt, result_for: ResultFor) -> FakeTrack24:
    """A synthetic Track24 site; nothing is registered until a test asks for it."""
    return FakeTrack24(httpx_mock, encrypt, result_for)


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    """The CLI's own client; ``pytest_httpx`` intercepts every request it sends."""
    async with track24.create_client(DEFAULT_TIMEOUT_SECONDS) as http_client:
        yield http_client
