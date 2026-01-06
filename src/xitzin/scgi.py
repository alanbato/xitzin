"""SCGI support for Xitzin applications.

This module provides SCGI (Simple Common Gateway Interface) client support
for proxying requests to persistent backend processes. Unlike CGI which
spawns a new process per request, SCGI connects to a running server process.

Example:
    from xitzin import Xitzin
    from xitzin.scgi import SCGIHandler, SCGIConfig

    app = Xitzin()

    # Mount an SCGI backend via TCP
    config = SCGIConfig(timeout=30)
    app.mount("/dynamic", SCGIHandler("127.0.0.1", 4000, config=config))

    # Or via Unix socket
    app.mount("/api", SCGIApp("/tmp/scgi.sock", config=config))
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from nauyaca.protocol.response import GeminiResponse

from .cgi import build_cgi_env, parse_cgi_output
from .exceptions import CGIError, ProxyError

if TYPE_CHECKING:
    from .requests import Request


@dataclass
class SCGIConfig:
    """Configuration for SCGI backend communication.

    Attributes:
        timeout: Maximum time to wait for SCGI response in seconds.
        max_response_size: Maximum response size in bytes (None = unlimited).
        buffer_size: Read buffer size for streaming responses.
        inherit_environment: Whether to inherit parent environment variables.
        app_state_keys: App state keys to pass as XITZIN_* env vars.
    """

    timeout: float = 30.0
    max_response_size: int | None = 1048576  # 1MB default
    buffer_size: int = 8192
    inherit_environment: bool = False
    app_state_keys: list[str] = field(default_factory=list)


def encode_netstring(data: bytes) -> bytes:
    """Encode data as a netstring.

    Netstring format: <length>:<data>,

    Args:
        data: Bytes to encode.

    Returns:
        Netstring-encoded bytes.

    Example:
        >>> encode_netstring(b"hello")
        b'5:hello,'
    """
    length = str(len(data)).encode("ascii")
    return length + b":" + data + b","


def encode_scgi_headers(env: dict[str, str]) -> bytes:
    """Encode CGI environment as SCGI headers.

    SCGI format is a netstring containing null-separated key-value pairs:
    <key>\\0<value>\\0<key>\\0<value>\\0...

    The CONTENT_LENGTH header must come first per SCGI spec.

    Args:
        env: CGI environment dictionary.

    Returns:
        Netstring-encoded headers ready for SCGI transmission.

    Example:
        >>> env = {"CONTENT_LENGTH": "0", "SCGI": "1", "PATH_INFO": "/test"}
        >>> encode_scgi_headers(env)  # Returns netstring with headers
    """
    parts: list[bytes] = []

    # CONTENT_LENGTH must be first per SCGI spec
    content_length = env.get("CONTENT_LENGTH", "0")
    parts.append(b"CONTENT_LENGTH\x00")
    parts.append(content_length.encode("utf-8"))
    parts.append(b"\x00")

    # Add remaining headers
    for key, value in env.items():
        if key == "CONTENT_LENGTH":
            continue  # Already added first
        parts.append(key.encode("utf-8"))
        parts.append(b"\x00")
        parts.append(value.encode("utf-8"))
        parts.append(b"\x00")

    headers = b"".join(parts)
    return encode_netstring(headers)


class SCGIHandler:
    """Proxy requests to an SCGI backend server via TCP socket.

    This handler forwards requests to an SCGI application server
    (like Python's flup, or custom SCGI servers) over a TCP connection.

    Example:
        from xitzin.scgi import SCGIHandler, SCGIConfig

        config = SCGIConfig(timeout=30)
        handler = SCGIHandler("127.0.0.1", 4000, config=config)
        app.mount("/dynamic", handler)

        # Requests to /dynamic/* are forwarded to 127.0.0.1:4000
    """

    def __init__(
        self,
        host: str,
        port: int,
        *,
        config: SCGIConfig | None = None,
    ) -> None:
        """Create an SCGI TCP handler.

        Args:
            host: SCGI server hostname or IP.
            port: SCGI server port.
            config: SCGI communication configuration.
        """
        self.host = host
        self.port = port
        self.config = config or SCGIConfig()

    async def __call__(self, request: Request, path_info: str) -> GeminiResponse:
        """Forward request to SCGI backend.

        Args:
            request: The Gemini request.
            path_info: Path after the mount prefix.

        Returns:
            GeminiResponse from the SCGI backend.

        Raises:
            ProxyError: If connection or communication fails.
        """
        # Build CGI environment (reuse from cgi.py)
        app_state_vars = self._get_app_state_vars(request)
        env = build_cgi_env(
            request,
            script_name="",  # SCGI app handles routing internally
            path_info=path_info,
            app_state_vars=app_state_vars,
            inherit_environment=self.config.inherit_environment,
        )

        # Add SCGI-specific variables
        env["SCGI"] = "1"
        env["CONTENT_LENGTH"] = "0"  # Gemini has no request body

        # Connect to SCGI backend
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=self.config.timeout,
            )
        except asyncio.TimeoutError:
            raise ProxyError(
                f"SCGI connection timeout to {self.host}:{self.port}"
            ) from None
        except OSError as e:
            raise ProxyError(
                f"Failed to connect to SCGI backend at {self.host}:{self.port}: {e}"
            ) from e

        try:
            # Send SCGI headers
            headers = encode_scgi_headers(env)
            writer.write(headers)
            await writer.drain()

            # Read response
            response_data = await self._read_response(reader)

            # Parse as CGI output (reuse from cgi.py)
            cgi_response = parse_cgi_output(response_data, None)

            return GeminiResponse(
                status=cgi_response.status,
                meta=cgi_response.meta,
                body=cgi_response.body,
            )

        except asyncio.TimeoutError:
            raise ProxyError(
                f"SCGI backend timeout after {self.config.timeout}s"
            ) from None
        except CGIError as e:
            # Re-raise as ProxyError (status 43 instead of 42)
            raise ProxyError(f"SCGI backend error: {e.message}") from e
        except ProxyError:
            raise
        except Exception as e:
            raise ProxyError(f"SCGI communication error: {e}") from e
        finally:
            writer.close()
            await writer.wait_closed()

    async def _read_response(self, reader: asyncio.StreamReader) -> bytes:
        """Read full response from SCGI backend.

        Args:
            reader: Stream reader connected to SCGI backend.

        Returns:
            Complete response bytes.

        Raises:
            ProxyError: If response exceeds max size or read fails.
        """
        chunks: list[bytes] = []
        total_size = 0

        while True:
            try:
                chunk = await asyncio.wait_for(
                    reader.read(self.config.buffer_size),
                    timeout=self.config.timeout,
                )
            except asyncio.TimeoutError:
                raise ProxyError("SCGI backend read timeout") from None

            if not chunk:
                break

            chunks.append(chunk)
            total_size += len(chunk)

            if (
                self.config.max_response_size
                and total_size > self.config.max_response_size
            ):
                raise ProxyError(
                    f"SCGI response exceeds maximum size "
                    f"({self.config.max_response_size} bytes)"
                )

        return b"".join(chunks)

    def _get_app_state_vars(self, request: Request) -> dict[str, str]:
        """Extract app state variables to pass to SCGI backend."""
        if not self.config.app_state_keys:
            return {}

        result: dict[str, str] = {}
        try:
            app_state = request.app.state
            for key in self.config.app_state_keys:
                try:
                    value = getattr(app_state, key)
                    result[key] = str(value)
                except AttributeError:
                    pass
        except RuntimeError:
            # Request not bound to app
            pass

        return result


class SCGIApp:
    """Proxy requests to an SCGI backend server via Unix socket.

    This handler forwards requests to an SCGI application server
    over a Unix domain socket (more efficient for local communication).

    Example:
        from xitzin.scgi import SCGIApp, SCGIConfig

        config = SCGIConfig(timeout=30)
        handler = SCGIApp("/tmp/scgi.sock", config=config)
        app.mount("/dynamic", handler)

        # Requests to /dynamic/* are forwarded to /tmp/scgi.sock
    """

    def __init__(
        self,
        socket_path: Path | str,
        *,
        config: SCGIConfig | None = None,
    ) -> None:
        """Create an SCGI Unix socket handler.

        Args:
            socket_path: Path to the Unix socket.
            config: SCGI communication configuration.
        """
        self.socket_path = Path(socket_path)
        self.config = config or SCGIConfig()

    async def __call__(self, request: Request, path_info: str) -> GeminiResponse:
        """Forward request to SCGI backend via Unix socket.

        Args:
            request: The Gemini request.
            path_info: Path after the mount prefix.

        Returns:
            GeminiResponse from the SCGI backend.

        Raises:
            ProxyError: If connection or communication fails.
        """
        # Build CGI environment (reuse from cgi.py)
        app_state_vars = self._get_app_state_vars(request)
        env = build_cgi_env(
            request,
            script_name="",
            path_info=path_info,
            app_state_vars=app_state_vars,
            inherit_environment=self.config.inherit_environment,
        )

        # Add SCGI-specific variables
        env["SCGI"] = "1"
        env["CONTENT_LENGTH"] = "0"

        # Connect via Unix socket
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_unix_connection(str(self.socket_path)),
                timeout=self.config.timeout,
            )
        except FileNotFoundError:
            raise ProxyError(f"SCGI socket not found: {self.socket_path}") from None
        except asyncio.TimeoutError:
            raise ProxyError(f"SCGI connection timeout to {self.socket_path}") from None
        except OSError as e:
            raise ProxyError(
                f"Failed to connect to SCGI backend at {self.socket_path}: {e}"
            ) from e

        try:
            # Send SCGI headers
            headers = encode_scgi_headers(env)
            writer.write(headers)
            await writer.drain()

            # Read response
            response_data = await self._read_response(reader)

            # Parse as CGI output (reuse from cgi.py)
            cgi_response = parse_cgi_output(response_data, None)

            return GeminiResponse(
                status=cgi_response.status,
                meta=cgi_response.meta,
                body=cgi_response.body,
            )

        except asyncio.TimeoutError:
            raise ProxyError(
                f"SCGI backend timeout after {self.config.timeout}s"
            ) from None
        except CGIError as e:
            raise ProxyError(f"SCGI backend error: {e.message}") from e
        except ProxyError:
            raise
        except Exception as e:
            raise ProxyError(f"SCGI communication error: {e}") from e
        finally:
            writer.close()
            await writer.wait_closed()

    async def _read_response(self, reader: asyncio.StreamReader) -> bytes:
        """Read full response from SCGI backend."""
        chunks: list[bytes] = []
        total_size = 0

        while True:
            try:
                chunk = await asyncio.wait_for(
                    reader.read(self.config.buffer_size),
                    timeout=self.config.timeout,
                )
            except asyncio.TimeoutError:
                raise ProxyError("SCGI backend read timeout") from None

            if not chunk:
                break

            chunks.append(chunk)
            total_size += len(chunk)

            if (
                self.config.max_response_size
                and total_size > self.config.max_response_size
            ):
                raise ProxyError(
                    f"SCGI response exceeds maximum size "
                    f"({self.config.max_response_size} bytes)"
                )

        return b"".join(chunks)

    def _get_app_state_vars(self, request: Request) -> dict[str, str]:
        """Extract app state variables to pass to SCGI backend."""
        if not self.config.app_state_keys:
            return {}

        result: dict[str, str] = {}
        try:
            app_state = request.app.state
            for key in self.config.app_state_keys:
                try:
                    value = getattr(app_state, key)
                    result[key] = str(value)
                except AttributeError:
                    pass
        except RuntimeError:
            pass

        return result


__all__ = [
    "SCGIApp",
    "SCGIConfig",
    "SCGIHandler",
    "encode_netstring",
    "encode_scgi_headers",
]
