"""Loopback HTTP server that impersonates the Track24 web flow for integration tests."""

from __future__ import annotations

import json
import threading
import urllib.parse
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from helpers.constants import (
    HTML_CONTENT_TYPE,
    HTTP_NOT_FOUND,
    HTTP_OK,
    JSON_CONTENT_TYPE,
    LOOPBACK_HOST,
    LOOPBACK_SCHEME,
    SERVER_POLL_INTERVAL_SECONDS,
    TRACK24_BASE_URL,
)


@dataclass(frozen=True)
class RecordedRequest:
    """A request as the fake server received it."""

    method: str
    path: str
    query: dict[str, list[str]]
    headers: dict[str, str]
    form: dict[str, list[str]]


@dataclass(frozen=True)
class Reply:
    """A canned response for one path."""

    body: bytes
    content_type: str = JSON_CONTENT_TYPE
    status: int = HTTP_OK

    @classmethod
    def html(cls, text: str) -> Reply:
        """Build an HTML page reply."""
        return cls(text.encode(), HTML_CONTENT_TYPE)

    @classmethod
    def json(cls, payload: Any, status: int = HTTP_OK) -> Reply:
        """Build a JSON reply."""
        return cls(json.dumps(payload).encode(), JSON_CONTENT_TYPE, status)


@dataclass
class FakeTrack24:
    """Routes by request path and records every request it handles."""

    routes: dict[str, Reply] = field(default_factory=dict)
    requests: list[RecordedRequest] = field(default_factory=list)

    def handle(self, handler: BaseHTTPRequestHandler) -> None:
        """Answer ``handler`` from ``routes`` and record what arrived."""
        parts = urllib.parse.urlsplit(handler.path)
        length = int(handler.headers.get("Content-Length") or 0)
        body = handler.rfile.read(length).decode() if length else ""
        self.requests.append(
            RecordedRequest(
                method=handler.command,
                path=parts.path,
                query=urllib.parse.parse_qs(parts.query, keep_blank_values=True),
                headers={key.lower(): value for key, value in handler.headers.items()},
                form=urllib.parse.parse_qs(body, keep_blank_values=True),
            )
        )
        reply = self.routes.get(parts.path)
        if reply is None:
            handler.send_error(HTTP_NOT_FOUND)
            return
        handler.send_response(reply.status)
        handler.send_header("Content-Type", reply.content_type)
        handler.send_header("Content-Length", str(len(reply.body)))
        handler.end_headers()
        handler.wfile.write(reply.body)

    def paths(self) -> list[tuple[str, str]]:
        """Return ``(method, path)`` pairs in arrival order."""
        return [(request.method, request.path) for request in self.requests]


class LoopbackHandler(urllib.request.HTTPHandler):
    """Send ``https://track24.ru`` traffic to the loopback server over plain HTTP."""

    handler_order = 100

    def __init__(self, port: int) -> None:
        super().__init__()
        self.port = port

    def https_open(self, request: urllib.request.Request) -> Any:
        """Rewrite the Track24 URL and forward the request unchanged otherwise."""
        if not request.full_url.startswith(TRACK24_BASE_URL + "/"):
            raise AssertionError(f"Unexpected outbound URL: {request.full_url}")
        parts = urllib.parse.urlsplit(request.full_url)
        local_url = urllib.parse.urlunsplit(
            (LOOPBACK_SCHEME, f"{LOOPBACK_HOST}:{self.port}", parts.path, parts.query, "")
        )
        forwarded = urllib.request.Request(
            local_url,
            data=request.data,
            headers=dict(request.header_items()),
            method=request.get_method(),
        )
        forwarded.timeout = request.timeout
        return self.http_open(forwarded)


@contextmanager
def serve(fake: FakeTrack24) -> Iterator[urllib.request.OpenerDirector]:
    """Run ``fake`` on an ephemeral port and yield an opener routed to it."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            fake.handle(self)

        def do_POST(self) -> None:
            fake.handle(self)

        def log_message(self, *_args: Any) -> None:
            """Keep test output quiet."""

    server = ThreadingHTTPServer((LOOPBACK_HOST, 0), Handler)
    thread = threading.Thread(target=server.serve_forever, args=(SERVER_POLL_INTERVAL_SECONDS,), daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        yield urllib.request.build_opener(urllib.request.ProxyHandler({}), LoopbackHandler(port))
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
