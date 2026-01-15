"""Testing utilities for Xitzin applications.

This module provides a TestClient for testing Gemini handlers
without running a real server.
"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Generator
from urllib.parse import quote_plus

from nauyaca.protocol.request import GeminiRequest
from nauyaca.protocol.request import TitanRequest as NauyacaTitanRequest
from nauyaca.protocol.response import GeminiResponse

if TYPE_CHECKING:
    from .application import Xitzin


@dataclass
class TestResponse:
    """Response from the test client.

    Provides convenient access to response data and status checking methods.
    """

    status: int
    """The status code (10-62)."""

    meta: str
    """The meta field (MIME type, prompt, redirect URL, or error message)."""

    body: str | None
    """The response body (only present for 2x success responses)."""

    @property
    def is_success(self) -> bool:
        """Check if this is a success response (2x)."""
        return 20 <= self.status < 30

    @property
    def is_input_required(self) -> bool:
        """Check if input is required (1x)."""
        return 10 <= self.status < 20

    @property
    def is_redirect(self) -> bool:
        """Check if this is a redirect (3x)."""
        return 30 <= self.status < 40

    @property
    def is_error(self) -> bool:
        """Check if this is an error response (4x, 5x, 6x)."""
        return 40 <= self.status < 70

    @property
    def is_certificate_required(self) -> bool:
        """Check if a client certificate is required (6x)."""
        return 60 <= self.status < 70

    @property
    def redirect_url(self) -> str | None:
        """Get the redirect URL if this is a redirect response."""
        if self.is_redirect:
            return self.meta
        return None

    @property
    def input_prompt(self) -> str | None:
        """Get the input prompt if input is required."""
        if self.is_input_required:
            return self.meta
        return None

    @property
    def mime_type(self) -> str | None:
        """Get the MIME type if this is a success response."""
        if self.is_success:
            return self.meta.split(";")[0].strip()
        return None

    def __str__(self) -> str:
        lines = [f"TestResponse(status={self.status}, meta={self.meta!r})"]
        if self.body:
            preview = self.body[:100] + "..." if len(self.body) > 100 else self.body
            lines.append(f"  body={preview!r}")
        return "\n".join(lines)


class TestClient:
    """Test client for Xitzin applications.

    Allows testing handlers without running a real Gemini server.

    Example:
        app = Xitzin()

        @app.gemini("/")
        def home(request: Request):
            return "# Welcome"

        client = TestClient(app)
        response = client.get("/")
        assert response.status == 20
        assert "Welcome" in response.body
    """

    def __init__(self, app: "Xitzin") -> None:
        """Create a test client for an application.

        Args:
            app: The Xitzin application to test.
        """
        self._app = app
        self._default_fingerprint: str | None = None

    def get(
        self,
        path: str,
        *,
        query: str | None = None,
        cert_fingerprint: str | None = None,
    ) -> TestResponse:
        """Make a test request.

        Args:
            path: The request path (e.g., "/user/alice").
            query: Optional query string (for input responses).
            cert_fingerprint: Mock client certificate fingerprint.

        Returns:
            TestResponse with status, meta, and body.

        Example:
            response = client.get("/")
            assert response.is_success
        """
        # Build URL
        url = f"gemini://testserver{path}"
        if query:
            url += f"?{quote_plus(query)}"

        # Create mock GeminiRequest
        request = GeminiRequest.from_line(url)

        # Set certificate info
        fingerprint = cert_fingerprint or self._default_fingerprint
        if fingerprint:
            request.client_cert_fingerprint = fingerprint

        # Handle request through the app
        response = self._handle_sync(request)

        # Convert bytes body to str for TestResponse
        body = response.body
        if isinstance(body, bytes):
            body = body.decode("utf-8")

        return TestResponse(
            status=response.status,
            meta=response.meta,
            body=body,
        )

    def get_input(
        self,
        path: str,
        input_value: str,
        *,
        cert_fingerprint: str | None = None,
    ) -> TestResponse:
        """Make a request with an input value.

        Simulates a user responding to a status 10/11 input prompt.

        Args:
            path: The request path.
            input_value: The user's input (will be URL-encoded).
            cert_fingerprint: Mock client certificate fingerprint.

        Returns:
            TestResponse from the handler.

        Example:
            # First request gets input prompt
            response = client.get("/search")
            assert response.is_input_required

            # Second request with input value
            response = client.get_input("/search", "hello world")
            assert response.is_success
        """
        return self.get(path, query=input_value, cert_fingerprint=cert_fingerprint)

    def with_certificate(self, fingerprint: str) -> "TestClient":
        """Create a new client with a default certificate fingerprint.

        Args:
            fingerprint: The certificate fingerprint to use for all requests.

        Returns:
            A new TestClient with the default fingerprint set.

        Example:
            # Create authenticated client
            auth_client = client.with_certificate("abc123...")

            # All requests from this client include the certificate
            response = auth_client.get("/admin")
            assert response.is_success
        """
        new_client = TestClient(self._app)
        new_client._default_fingerprint = fingerprint
        return new_client

    def upload(
        self,
        path: str,
        content: bytes | str,
        *,
        mime_type: str = "text/gemini",
        token: str | None = None,
        cert_fingerprint: str | None = None,
    ) -> TestResponse:
        """Make a Titan upload request.

        Args:
            path: The request path (e.g., "/upload/file.gmi").
            content: Content to upload (str will be UTF-8 encoded).
            mime_type: Content MIME type (default: text/gemini).
            token: Authentication token (if required by route).
            cert_fingerprint: Mock client certificate fingerprint.

        Returns:
            TestResponse with status, meta, and body.

        Example:
            response = client.upload(
                "/files/test.gmi",
                "# Hello World",
                mime_type="text/gemini",
                token="secret123"
            )
            assert response.is_success
        """
        # Convert str to bytes
        if isinstance(content, str):
            content_bytes = content.encode("utf-8")
        else:
            content_bytes = content

        # Build Titan URL
        size = len(content_bytes)
        url = f"titan://testserver{path};size={size};mime={mime_type}"
        if token:
            url += f";token={token}"

        # Create TitanRequest
        request = NauyacaTitanRequest.from_line(url)
        request.content = content_bytes

        # Set certificate info
        fingerprint = cert_fingerprint or self._default_fingerprint
        if fingerprint:
            request.client_cert_fingerprint = fingerprint

        # Handle through app
        response = self._handle_titan_sync(request)

        # Convert bytes body to str for TestResponse
        body = response.body
        if isinstance(body, bytes):
            body = body.decode("utf-8")

        return TestResponse(
            status=response.status,
            meta=response.meta,
            body=body,
        )

    def delete(
        self,
        path: str,
        *,
        token: str | None = None,
        cert_fingerprint: str | None = None,
    ) -> TestResponse:
        """Make a Titan delete request (zero-byte upload).

        Args:
            path: The request path to delete.
            token: Authentication token (if required by route).
            cert_fingerprint: Mock client certificate fingerprint.

        Returns:
            TestResponse with status, meta, and body.

        Example:
            response = client.delete("/files/old.gmi", token="secret123")
            assert response.is_success
        """
        return self.upload(
            path,
            b"",
            mime_type="text/gemini",
            token=token,
            cert_fingerprint=cert_fingerprint,
        )

    def _handle_sync(self, request: GeminiRequest) -> GeminiResponse:
        """Handle a request synchronously."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self._app._handle_request(request))

    def _handle_titan_sync(self, request: NauyacaTitanRequest) -> GeminiResponse:
        """Handle a Titan request synchronously."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self._app._handle_titan_request(request))


@contextmanager
def test_app(app: "Xitzin") -> Generator[TestClient, None, None]:
    """Context manager that runs the app's lifespan for testing.

    This runs startup handlers before yielding and shutdown handlers
    when the context exits.

    Args:
        app: The Xitzin application to test.

    Yields:
        A TestClient bound to the application.

    Example:
        app = Xitzin()

        @app.on_startup
        async def startup():
            app.state.db = await connect_db()

        @app.on_shutdown
        async def shutdown():
            await app.state.db.close()

        with test_app(app) as client:
            # Startup has run, db is connected
            response = client.get("/")
            assert response.is_success
        # Shutdown has run, db is closed
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    # Run startup
    loop.run_until_complete(app._run_startup())

    try:
        yield TestClient(app)
    finally:
        # Run shutdown
        loop.run_until_complete(app._run_shutdown())
