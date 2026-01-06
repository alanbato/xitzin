"""Tests for SCGI support in Xitzin.

This module tests SCGI protocol encoding, handlers, and integration
with the Xitzin application.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from xitzin import SCGIApp, SCGIConfig, SCGIHandler, Xitzin
from xitzin.exceptions import ProxyError
from xitzin.scgi import encode_netstring, encode_scgi_headers
from xitzin.testing import TestClient


# ============================================================================
# Tests for Netstring Encoding
# ============================================================================


class TestEncodeNetstring:
    """Tests for netstring encoding."""

    def test_encode_empty(self):
        """Empty data encodes correctly."""
        result = encode_netstring(b"")
        assert result == b"0:,"

    def test_encode_hello(self):
        """Simple string encodes correctly."""
        result = encode_netstring(b"hello")
        assert result == b"5:hello,"

    def test_encode_with_special_chars(self):
        """Data with special characters encodes correctly."""
        result = encode_netstring(b"hello\x00world")
        assert result == b"11:hello\x00world,"

    def test_encode_binary_data(self):
        """Binary data encodes correctly."""
        data = bytes(range(256))
        result = encode_netstring(data)
        assert result == b"256:" + data + b","

    def test_encode_unicode_as_bytes(self):
        """UTF-8 encoded unicode encodes correctly."""
        data = "こんにちは".encode("utf-8")
        result = encode_netstring(data)
        assert result == f"{len(data)}:".encode() + data + b","


# ============================================================================
# Tests for SCGI Header Encoding
# ============================================================================


class TestEncodeSCGIHeaders:
    """Tests for SCGI header encoding."""

    def test_content_length_first(self):
        """CONTENT_LENGTH is always first in encoded headers."""
        env = {
            "SCGI": "1",
            "PATH_INFO": "/test",
            "CONTENT_LENGTH": "0",
        }
        result = encode_scgi_headers(env)

        # Decode the netstring to check header order
        # Format: <length>:<headers>,
        colon_idx = result.index(b":")
        headers = result[colon_idx + 1 : -1]  # Strip length: and trailing ,

        # Headers should start with CONTENT_LENGTH
        assert headers.startswith(b"CONTENT_LENGTH\x00")

    def test_basic_headers(self):
        """Basic headers encode correctly."""
        env = {
            "CONTENT_LENGTH": "0",
            "SCGI": "1",
        }
        result = encode_scgi_headers(env)

        # Should be a valid netstring containing the headers
        assert result.endswith(b",")
        colon_idx = result.index(b":")
        length = int(result[:colon_idx])
        headers = result[colon_idx + 1 : -1]
        assert len(headers) == length

        # Check headers contain expected keys
        assert b"CONTENT_LENGTH\x000\x00" in headers
        assert b"SCGI\x001\x00" in headers

    def test_multiple_headers(self):
        """Multiple headers encode correctly."""
        env = {
            "CONTENT_LENGTH": "0",
            "SCGI": "1",
            "SERVER_NAME": "example.com",
            "PATH_INFO": "/test",
        }
        result = encode_scgi_headers(env)

        colon_idx = result.index(b":")
        headers = result[colon_idx + 1 : -1]

        assert b"SERVER_NAME\x00example.com\x00" in headers
        assert b"PATH_INFO\x00/test\x00" in headers

    def test_default_content_length(self):
        """Missing CONTENT_LENGTH defaults to 0."""
        env = {"SCGI": "1"}
        result = encode_scgi_headers(env)

        colon_idx = result.index(b":")
        headers = result[colon_idx + 1 : -1]

        assert b"CONTENT_LENGTH\x000\x00" in headers


# ============================================================================
# Tests for SCGIConfig
# ============================================================================


class TestSCGIConfig:
    """Tests for SCGI configuration."""

    def test_default_values(self):
        """Default configuration values are set correctly."""
        config = SCGIConfig()

        assert config.timeout == 30.0
        assert config.max_response_size == 1048576  # 1MB
        assert config.buffer_size == 8192
        # Security: default to False to avoid leaking server env vars
        assert config.inherit_environment is False
        assert config.app_state_keys == []

    def test_custom_values(self):
        """Custom configuration values are set correctly."""
        config = SCGIConfig(
            timeout=60.0,
            max_response_size=5242880,  # 5MB
            buffer_size=16384,
            inherit_environment=False,
            app_state_keys=["db_url", "api_key"],
        )

        assert config.timeout == 60.0
        assert config.max_response_size == 5242880
        assert config.buffer_size == 16384
        assert config.inherit_environment is False
        assert config.app_state_keys == ["db_url", "api_key"]

    def test_unlimited_response_size(self):
        """Response size can be set to unlimited (None)."""
        config = SCGIConfig(max_response_size=None)
        assert config.max_response_size is None


# ============================================================================
# Tests for SCGIHandler (TCP)
# ============================================================================


class TestSCGIHandler:
    """Tests for the SCGI TCP handler."""

    def test_init(self):
        """Initialize handler with host and port."""
        handler = SCGIHandler("127.0.0.1", 4000)

        assert handler.host == "127.0.0.1"
        assert handler.port == 4000
        assert handler.config.timeout == 30.0

    def test_init_with_config(self):
        """Initialize handler with custom config."""
        config = SCGIConfig(timeout=60.0)
        handler = SCGIHandler("localhost", 9000, config=config)

        assert handler.host == "localhost"
        assert handler.port == 9000
        assert handler.config.timeout == 60.0

    @pytest.mark.asyncio
    async def test_connection_refused(self):
        """Connection refused raises ProxyError."""
        from nauyaca.protocol.request import GeminiRequest

        from xitzin.requests import Request

        # Use a port that's unlikely to be in use
        handler = SCGIHandler("127.0.0.1", 59999, config=SCGIConfig(timeout=1.0))
        raw = GeminiRequest.from_line("gemini://example.com/test")
        request = Request(raw, None)

        with pytest.raises(ProxyError, match="Failed to connect"):
            await handler(request, "/test")


# ============================================================================
# Tests for SCGIApp (Unix Socket)
# ============================================================================


class TestSCGIApp:
    """Tests for the SCGI Unix socket handler."""

    def test_init(self, tmp_path: Path):
        """Initialize handler with socket path."""
        socket_path = tmp_path / "test.sock"
        handler = SCGIApp(socket_path)

        assert handler.socket_path == socket_path
        assert handler.config.timeout == 30.0

    def test_init_with_config(self, tmp_path: Path):
        """Initialize handler with custom config."""
        socket_path = tmp_path / "test.sock"
        config = SCGIConfig(timeout=60.0)
        handler = SCGIApp(socket_path, config=config)

        assert handler.socket_path == socket_path
        assert handler.config.timeout == 60.0

    @pytest.mark.asyncio
    async def test_socket_not_found(self, tmp_path: Path):
        """Non-existent socket raises ProxyError."""
        from nauyaca.protocol.request import GeminiRequest

        from xitzin.requests import Request

        socket_path = tmp_path / "nonexistent.sock"
        handler = SCGIApp(socket_path)
        raw = GeminiRequest.from_line("gemini://example.com/test")
        request = Request(raw, None)

        with pytest.raises(ProxyError, match="socket not found"):
            await handler(request, "/test")


# ============================================================================
# Mock SCGI Server for Integration Tests
# ============================================================================


class MockSCGIServer:
    """Simple mock SCGI server for testing."""

    def __init__(
        self,
        response: bytes = b"20 text/gemini\r\n# Hello from SCGI!\n",
    ):
        self.response = response
        self.received_headers: dict[str, str] = {}
        self._server: asyncio.Server | None = None
        self.host: str = "127.0.0.1"
        self.port: int = 0

    async def start_tcp(self) -> tuple[str, int]:
        """Start TCP server, return (host, port)."""
        self._server = await asyncio.start_server(self._handle_connection, self.host, 0)
        addr = self._server.sockets[0].getsockname()
        self.host = addr[0]
        self.port = addr[1]
        return self.host, self.port

    async def start_unix(self, path: Path) -> Path:
        """Start Unix socket server, return socket path."""
        self._server = await asyncio.start_unix_server(
            self._handle_connection, str(path)
        )
        return path

    async def stop(self):
        """Stop the server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()

    async def _handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        """Handle incoming SCGI connection."""
        try:
            # Read netstring length
            length_str = b""
            while True:
                char = await reader.read(1)
                if char == b":":
                    break
                length_str += char

            length = int(length_str)

            # Read headers
            headers_data = await reader.read(length)

            # Parse headers
            parts = headers_data.split(b"\x00")
            for i in range(0, len(parts) - 1, 2):
                key = parts[i].decode("utf-8")
                value = parts[i + 1].decode("utf-8") if i + 1 < len(parts) else ""
                self.received_headers[key] = value

            # Read trailing comma
            await reader.read(1)

            # Send response
            writer.write(self.response)
            await writer.drain()

        finally:
            writer.close()
            await writer.wait_closed()


# ============================================================================
# Integration Tests with Mock Server
# ============================================================================


class TestSCGIIntegrationTCP:
    """Integration tests with mock SCGI server over TCP."""

    @pytest.mark.asyncio
    async def test_basic_request(self):
        """Basic SCGI request works."""
        from nauyaca.protocol.request import GeminiRequest

        from xitzin.requests import Request

        server = MockSCGIServer()
        host, port = await server.start_tcp()

        try:
            handler = SCGIHandler(host, port)
            raw = GeminiRequest.from_line("gemini://example.com/test")
            request = Request(raw, None)

            response = await handler(request, "/test")

            assert response.status == 20
            assert response.meta == "text/gemini"
            assert "Hello from SCGI" in response.body
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_headers_passed(self):
        """CGI headers are passed to SCGI backend."""
        from nauyaca.protocol.request import GeminiRequest

        from xitzin.requests import Request

        server = MockSCGIServer()
        host, port = await server.start_tcp()

        try:
            handler = SCGIHandler(host, port)
            raw = GeminiRequest.from_line("gemini://example.com/api/test?query=value")
            request = Request(raw, None)

            await handler(request, "/api/test")

            assert server.received_headers.get("SCGI") == "1"
            assert server.received_headers.get("CONTENT_LENGTH") == "0"
            assert server.received_headers.get("PATH_INFO") == "/api/test"
            assert server.received_headers.get("QUERY_STRING") == "query=value"
            assert server.received_headers.get("SERVER_NAME") == "example.com"
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_redirect_response(self):
        """Redirect response from SCGI backend."""
        from nauyaca.protocol.request import GeminiRequest

        from xitzin.requests import Request

        server = MockSCGIServer(response=b"30 gemini://example.com/new\r\n")
        host, port = await server.start_tcp()

        try:
            handler = SCGIHandler(host, port)
            raw = GeminiRequest.from_line("gemini://example.com/old")
            request = Request(raw, None)

            response = await handler(request, "/old")

            assert response.status == 30
            assert response.meta == "gemini://example.com/new"
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_input_response(self):
        """Input prompt response from SCGI backend."""
        from nauyaca.protocol.request import GeminiRequest

        from xitzin.requests import Request

        server = MockSCGIServer(response=b"10 Enter your name:\r\n")
        host, port = await server.start_tcp()

        try:
            handler = SCGIHandler(host, port)
            raw = GeminiRequest.from_line("gemini://example.com/input")
            request = Request(raw, None)

            response = await handler(request, "/input")

            assert response.status == 10
            assert response.meta == "Enter your name:"
        finally:
            await server.stop()


class TestSCGIIntegrationUnix:
    """Integration tests with mock SCGI server over Unix socket."""

    @pytest.mark.asyncio
    async def test_basic_request(self, tmp_path: Path):
        """Basic SCGI request over Unix socket works."""
        from nauyaca.protocol.request import GeminiRequest

        from xitzin.requests import Request

        socket_path = tmp_path / "test.sock"
        server = MockSCGIServer()
        await server.start_unix(socket_path)

        try:
            handler = SCGIApp(socket_path)
            raw = GeminiRequest.from_line("gemini://example.com/test")
            request = Request(raw, None)

            response = await handler(request, "/test")

            assert response.status == 20
            assert response.meta == "text/gemini"
            assert "Hello from SCGI" in response.body
        finally:
            await server.stop()


# ============================================================================
# Integration Tests with Xitzin Application
# ============================================================================


class TestAppSCGIMethod:
    """Tests for the app.scgi() convenience method."""

    def test_tcp_connection(self):
        """app.scgi() with TCP parameters mounts correctly."""
        app = Xitzin()
        app.scgi("/api", host="127.0.0.1", port=4000)

        # Verify mount was created
        assert len(app._router._mounted_routes) == 1
        mounted = app._router._mounted_routes[0]
        assert mounted.path_prefix == "/api"
        assert isinstance(mounted.handler, SCGIHandler)

    def test_unix_socket_connection(self, tmp_path: Path):
        """app.scgi() with Unix socket parameters mounts correctly."""
        app = Xitzin()
        socket_path = tmp_path / "test.sock"
        app.scgi("/api", socket_path=socket_path)

        # Verify mount was created
        assert len(app._router._mounted_routes) == 1
        mounted = app._router._mounted_routes[0]
        assert mounted.path_prefix == "/api"
        assert isinstance(mounted.handler, SCGIApp)

    def test_missing_parameters(self):
        """app.scgi() without connection parameters raises ValueError."""
        app = Xitzin()

        with pytest.raises(ValueError, match="Must specify"):
            app.scgi("/api")

    def test_both_parameters(self, tmp_path: Path):
        """app.scgi() with both TCP and Unix raises ValueError."""
        app = Xitzin()
        socket_path = tmp_path / "test.sock"

        with pytest.raises(ValueError, match="Cannot specify both"):
            app.scgi("/api", host="127.0.0.1", port=4000, socket_path=socket_path)

    def test_incomplete_tcp_parameters(self):
        """app.scgi() with only host raises ValueError."""
        app = Xitzin()

        with pytest.raises(ValueError, match="Both host and port"):
            app.scgi("/api", host="127.0.0.1")

    def test_with_name(self):
        """app.scgi() with name parameter."""
        app = Xitzin()
        app.scgi("/api", host="127.0.0.1", port=4000, name="my_api")

        mounted = app._router._mounted_routes[0]
        assert mounted.name == "my_api"

    def test_with_custom_timeout(self):
        """app.scgi() with custom timeout."""
        app = Xitzin()
        app.scgi("/api", host="127.0.0.1", port=4000, timeout=60.0)

        mounted = app._router._mounted_routes[0]
        assert mounted.handler.config.timeout == 60.0

    def test_with_app_state_keys(self):
        """app.scgi() with app_state_keys."""
        app = Xitzin()
        app.scgi(
            "/api",
            host="127.0.0.1",
            port=4000,
            app_state_keys=["db_url", "api_key"],
        )

        mounted = app._router._mounted_routes[0]
        assert mounted.handler.config.app_state_keys == ["db_url", "api_key"]


@pytest.fixture
def scgi_server():
    """Fixture that manages a mock SCGI server."""
    server = MockSCGIServer()

    async def start():
        return await server.start_tcp()

    async def stop():
        await server.stop()

    # Start server
    host, port = asyncio.get_event_loop().run_until_complete(start())
    server.host = host
    server.port = port

    yield server

    # Stop server
    asyncio.get_event_loop().run_until_complete(stop())


class TestSCGIWithTestClient:
    """Tests using TestClient with mock SCGI server."""

    def test_scgi_through_app(self, scgi_server: MockSCGIServer):
        """SCGI handler works through Xitzin app."""
        app = Xitzin()
        app.scgi("/api", host=scgi_server.host, port=scgi_server.port)

        client = TestClient(app)
        response = client.get("/api/test")

        assert response.is_success
        assert "Hello from SCGI" in response.body

    def test_scgi_with_middleware(self, scgi_server: MockSCGIServer):
        """Middleware applies to SCGI requests."""
        app = Xitzin()

        middleware_called = []

        @app.middleware
        async def tracking_middleware(request, call_next):
            middleware_called.append("before")
            response = await call_next(request)
            middleware_called.append("after")
            return response

        app.scgi("/api", host=scgi_server.host, port=scgi_server.port)

        client = TestClient(app)
        response = client.get("/api/test")

        assert response.is_success
        assert middleware_called == ["before", "after"]

    def test_scgi_with_regular_routes(self, scgi_server: MockSCGIServer):
        """SCGI handler works alongside regular routes."""
        app = Xitzin()

        @app.gemini("/")
        def home(request):
            return "# Home"

        @app.gemini("/about")
        def about(request):
            return "# About"

        app.scgi("/api", host=scgi_server.host, port=scgi_server.port)

        client = TestClient(app)

        # Regular routes work
        assert client.get("/").is_success
        assert client.get("/about").is_success

        # SCGI works
        response = client.get("/api/test")
        assert response.is_success
        assert "Hello from SCGI" in response.body

    def test_scgi_connection_error(self):
        """SCGI connection error returns status 43."""
        app = Xitzin()
        # Use a port that's unlikely to be in use
        app.scgi("/api", host="127.0.0.1", port=59999, timeout=0.5)

        client = TestClient(app)
        response = client.get("/api/test")

        assert response.status == 43  # Proxy error


class TestSCGIResponseSizeLimit:
    """Tests for response size limiting."""

    @pytest.mark.asyncio
    async def test_response_within_limit(self):
        """Response within size limit works."""
        from nauyaca.protocol.request import GeminiRequest

        from xitzin.requests import Request

        # Small response
        response_body = "# Hello\n" * 100
        server = MockSCGIServer(response=f"20 text/gemini\r\n{response_body}".encode())
        host, port = await server.start_tcp()

        try:
            config = SCGIConfig(max_response_size=1048576)  # 1MB
            handler = SCGIHandler(host, port, config=config)
            raw = GeminiRequest.from_line("gemini://example.com/test")
            request = Request(raw, None)

            response = await handler(request, "/test")

            assert response.status == 20
            assert "Hello" in response.body
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_unlimited_response_size(self):
        """Unlimited response size (None) works."""
        from nauyaca.protocol.request import GeminiRequest

        from xitzin.requests import Request

        # Large response
        response_body = "x" * 100000
        server = MockSCGIServer(response=f"20 text/gemini\r\n{response_body}".encode())
        host, port = await server.start_tcp()

        try:
            config = SCGIConfig(max_response_size=None)  # Unlimited
            handler = SCGIHandler(host, port, config=config)
            raw = GeminiRequest.from_line("gemini://example.com/test")
            request = Request(raw, None)

            response = await handler(request, "/test")

            assert response.status == 20
            assert len(response.body) == 100000
        finally:
            await server.stop()
