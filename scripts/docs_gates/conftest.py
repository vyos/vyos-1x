"""Shared pytest fixtures for docs_gates tests.

Provides a real local HTTP server (stdlib http.server, no TLS) used to exercise the
_NoRedirect opener pattern (parity.py / smoke.py) end-to-end over an actual network
round trip, rather than only unit-testing the handler class in isolation.
"""
from __future__ import annotations

import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

REDIRECT_PATH = "/redirect-me"
REDIRECT_LOCATION = "https://example.invalid/target"


class _RedirectHandler(BaseHTTPRequestHandler):
    """301+Location for REDIRECT_PATH; 200 for anything else."""

    def do_GET(self) -> None:  # noqa: N802 — stdlib handler method name
        self._respond()

    def do_HEAD(self) -> None:  # noqa: N802
        self._respond()

    def _respond(self) -> None:
        if self.path == REDIRECT_PATH:
            self.send_response(301)
            self.send_header("Location", REDIRECT_LOCATION)
            self.end_headers()
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            if self.command == "GET":
                self.wfile.write(b"ok")

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 — quiet test output
        pass


@pytest.fixture
def redirect_http_server() -> Iterator[str]:
    """Starts the server on 127.0.0.1 (ephemeral port); yields 'host:port'."""
    server = HTTPServer(("127.0.0.1", 0), _RedirectHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
