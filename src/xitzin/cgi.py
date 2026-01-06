"""CGI support for Xitzin applications.

This module provides CGI script execution capabilities for Xitzin,
following the Gemini CGI specification conventions established by
servers like Jetforce.

Example:
    from xitzin import Xitzin
    from xitzin.cgi import CGIHandler, CGIConfig

    app = Xitzin()

    # Mount a CGI directory
    config = CGIConfig(timeout=30)
    app.mount("/cgi-bin", CGIHandler("/srv/cgi-bin", config=config))

    # Or mount a single script
    app.mount("/calculator", CGIScript("/srv/scripts/calc.py"))
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from nauyaca.protocol.response import GeminiResponse

from .exceptions import BadRequest, CGIError, NotFound

logger = structlog.get_logger("xitzin.cgi")

if TYPE_CHECKING:
    from .requests import Request


# CGI protocol constants
GATEWAY_INTERFACE = "CGI/1.1"
SERVER_PROTOCOL = "GEMINI"
SERVER_SOFTWARE = "Xitzin/0.1.0"


@dataclass
class CGIConfig:
    """Configuration for CGI script execution.

    Attributes:
        timeout: Maximum execution time in seconds.
        max_header_size: Maximum size of the status line in bytes.
        streaming: Enable streaming mode for large responses.
        check_execute_permission: Whether to verify execute permission.
        inherit_environment: Whether to inherit parent environment variables.
    """

    timeout: float = 30.0
    max_header_size: int = 8192
    streaming: bool = False
    check_execute_permission: bool = True
    inherit_environment: bool = False
    app_state_keys: list[str] = field(default_factory=list)


@dataclass
class CGIResponse:
    """Parsed response from a CGI script.

    Attributes:
        status: Gemini status code (10-62).
        meta: Status meta field (MIME type, prompt, URL, or error message).
        body: Response body content, if any.
    """

    status: int
    meta: str
    body: str | None = None


def build_cgi_env(
    request: Request,
    script_name: str,
    path_info: str,
    *,
    app_state_vars: dict[str, str] | None = None,
    inherit_environment: bool = True,
) -> dict[str, str]:
    """Build CGI environment variables from a request.

    This follows the Gemini CGI conventions established by Jetforce
    and other Gemini servers, based on RFC 3875.

    Args:
        request: The Gemini request.
        script_name: Name/path of the CGI script.
        path_info: Additional path info after the script name.
        app_state_vars: Application state variables to pass as XITZIN_*.
        inherit_environment: Whether to inherit current environment.

    Returns:
        Dictionary of environment variables for the CGI script.
    """
    if inherit_environment:
        env = os.environ.copy()
    else:
        env = {}

    # Standard CGI variables (RFC 3875)
    env["GATEWAY_INTERFACE"] = GATEWAY_INTERFACE
    env["SERVER_PROTOCOL"] = SERVER_PROTOCOL
    env["SERVER_SOFTWARE"] = SERVER_SOFTWARE

    # Gemini-specific
    env["GEMINI_URL"] = request.url
    env["SCRIPT_NAME"] = script_name
    env["PATH_INFO"] = path_info
    env["QUERY_STRING"] = request.raw_query or ""

    # Server information
    env["SERVER_NAME"] = request.hostname
    env["SERVER_PORT"] = str(request.port)

    # Client information
    if request.remote_addr:
        env["REMOTE_ADDR"] = request.remote_addr
        env["REMOTE_HOST"] = request.remote_addr  # Could do reverse DNS

    # TLS/Certificate information
    if request.client_cert_fingerprint:
        env["TLS_CLIENT_HASH"] = request.client_cert_fingerprint
        env["TLS_CLIENT_AUTHORISED"] = "1"
        env["AUTH_TYPE"] = "CERTIFICATE"
    else:
        env["TLS_CLIENT_AUTHORISED"] = "0"

    # Application state as XITZIN_* variables
    if app_state_vars:
        for key, value in app_state_vars.items():
            env[f"XITZIN_{key.upper()}"] = str(value)

    return env


def parse_cgi_output(stdout: bytes, stderr: bytes | None = None) -> CGIResponse:
    """Parse CGI script output into a structured response.

    The expected format is:
        <STATUS><SPACE><META>\\r\\n
        [optional body]

    Or for backwards compatibility:
        <META>\\r\\n
        [body]  # Assumes status 20

    Args:
        stdout: The script's standard output.
        stderr: The script's standard error (for error messages).

    Returns:
        Parsed CGI response.

    Raises:
        CGIError: If the output format is invalid.
    """
    if not stdout:
        raise CGIError("CGI script produced no output")

    try:
        output = stdout.decode("utf-8")
    except UnicodeDecodeError:
        output = stdout.decode("utf-8", errors="replace")

    # Split header from body
    if "\r\n" in output:
        header, body = output.split("\r\n", 1)
    elif "\n" in output:
        header, body = output.split("\n", 1)
    else:
        # No newline - treat entire output as header (no body)
        header = output
        body = ""

    # Parse header line: "20 text/gemini" or just "text/gemini"
    header = header.strip()
    if not header:
        raise CGIError("CGI script produced empty header")

    parts = header.split(None, 1)  # Split on first whitespace

    if len(parts) == 2 and parts[0].isdigit():
        # Format: "20 text/gemini"
        status = int(parts[0])
        meta = parts[1]
    elif len(parts) == 1 and not parts[0][0].isdigit():
        # Format: "text/gemini" (assume status 20)
        status = 20
        meta = parts[0]
    elif len(parts) == 1 and parts[0].isdigit():
        # Just a status code without meta
        status = int(parts[0])
        meta = "text/gemini" if status == 20 else ""
    else:
        raise CGIError(f"Invalid CGI header format: {header[:100]}")

    # Validate status code
    if not (10 <= status <= 69):
        raise CGIError(f"Invalid CGI status code: {status}")

    return CGIResponse(status=status, meta=meta, body=body if body else None)


class CGIHandler:
    """Execute CGI scripts from a directory.

    This handler executes scripts located in a specified directory,
    with proper environment variable setup and security validation.

    Example:
        from xitzin.cgi import CGIHandler, CGIConfig

        config = CGIConfig(timeout=30)
        handler = CGIHandler("/srv/gemini/cgi-bin", config=config)
        app.mount("/cgi-bin", handler)

        # Requests to /cgi-bin/hello.py execute /srv/gemini/cgi-bin/hello.py
    """

    def __init__(
        self,
        script_dir: Path | str,
        *,
        config: CGIConfig | None = None,
    ) -> None:
        """Create a CGI directory handler.

        Args:
            script_dir: Directory containing CGI scripts.
            config: CGI execution configuration.

        Raises:
            ValueError: If script_dir doesn't exist or isn't a directory.
        """
        self.script_dir = Path(script_dir).resolve()
        self.config = config or CGIConfig()

        if not self.script_dir.exists():
            msg = f"CGI script directory not found: {script_dir}"
            raise ValueError(msg)
        if not self.script_dir.is_dir():
            msg = f"CGI script path is not a directory: {script_dir}"
            raise ValueError(msg)

    async def __call__(self, request: Request, path_info: str) -> GeminiResponse:
        """Handle a request by executing the appropriate CGI script.

        Args:
            request: The Gemini request.
            path_info: Path after the mount prefix (e.g., "/script.py").

        Returns:
            GeminiResponse from the CGI script.

        Raises:
            NotFound: If the script doesn't exist.
            CGIError: If execution fails.
            BadRequest: If path validation fails.
        """
        # Extract script name and extra path info
        # path_info is like "/script.py" or "/script.py/extra/path"
        path_info = path_info.lstrip("/")
        if not path_info:
            raise NotFound("No CGI script specified")

        parts = path_info.split("/", 1)
        script_name = parts[0]
        extra_path = "/" + parts[1] if len(parts) > 1 else ""

        # Validate script name
        if not script_name:
            raise NotFound("No CGI script specified")

        # Security: check for path traversal attempts
        if ".." in script_name or script_name.startswith("/"):
            raise BadRequest("Invalid script name")

        # Resolve script path
        script_path = (self.script_dir / script_name).resolve()

        # Security: ensure script is within allowed directory
        try:
            script_path.relative_to(self.script_dir)
        except ValueError:
            raise BadRequest("Script path outside CGI directory") from None

        # Check script exists
        if not script_path.exists():
            raise NotFound(f"CGI script not found: {script_name}")

        if not script_path.is_file():
            raise NotFound(f"CGI script is not a file: {script_name}")

        # Check execute permission
        if self.config.check_execute_permission:
            if not os.access(script_path, os.X_OK):
                raise CGIError(f"CGI script not executable: {script_name}")

        # Build environment
        app_state_vars = self._get_app_state_vars(request)
        env = build_cgi_env(
            request,
            script_name=f"/{script_name}",
            path_info=extra_path,
            app_state_vars=app_state_vars,
            inherit_environment=self.config.inherit_environment,
        )

        # Execute script
        cgi_response = await self._execute_script(script_path, env)

        return GeminiResponse(
            status=cgi_response.status,
            meta=cgi_response.meta,
            body=cgi_response.body,
        )

    def _get_app_state_vars(self, request: Request) -> dict[str, str]:
        """Extract app state variables to pass to CGI scripts."""
        if not self.config.app_state_keys:
            return {}

        result = {}
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

    async def _execute_script(
        self, script_path: Path, env: dict[str, str]
    ) -> CGIResponse:
        """Execute a CGI script and return the parsed response.

        Args:
            script_path: Path to the script.
            env: Environment variables.

        Returns:
            Parsed CGI response.

        Raises:
            CGIError: If execution fails or times out.
        """
        try:
            process = await asyncio.create_subprocess_exec(
                str(script_path),
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.config.timeout,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise CGIError(
                    f"CGI script timeout after {self.config.timeout}s"
                ) from None

            # Check exit code
            if process.returncode != 0:
                # Log stderr server-side but don't expose to client
                if stderr:
                    error_detail = stderr.decode("utf-8", errors="replace")[:500]
                    logger.error(
                        "cgi_script_failed",
                        script=str(script_path),
                        returncode=process.returncode,
                        stderr=error_detail,
                    )
                raise CGIError(f"CGI script exited with code {process.returncode}")

            # Check header size
            first_line_end = stdout.find(b"\n")
            if first_line_end > self.config.max_header_size:
                raise CGIError("CGI header exceeds maximum size")

            return parse_cgi_output(stdout, stderr)

        except FileNotFoundError:
            raise NotFound(f"CGI script not found: {script_path.name}") from None
        except PermissionError:
            raise CGIError(f"Permission denied: {script_path.name}") from None


class CGIScript:
    """Execute a single CGI script.

    This handler executes a specific CGI script for all requests,
    useful for mounting a single script at a specific path.

    Example:
        from xitzin.cgi import CGIScript

        handler = CGIScript("/srv/scripts/calculator.py", timeout=10)
        app.mount("/calculator", handler)

        # All requests to /calculator execute /srv/scripts/calculator.py
    """

    def __init__(
        self,
        script_path: Path | str,
        *,
        timeout: float = 30.0,
        check_execute_permission: bool = True,
        inherit_environment: bool = False,
        app_state_keys: list[str] | None = None,
    ) -> None:
        """Create a single-script CGI handler.

        Args:
            script_path: Path to the CGI script.
            timeout: Maximum execution time in seconds.
            check_execute_permission: Whether to verify execute permission.
            inherit_environment: Whether to inherit parent environment.
            app_state_keys: App state keys to pass as XITZIN_* variables.

        Raises:
            ValueError: If script doesn't exist.
        """
        self.script_path = Path(script_path).resolve()
        self.config = CGIConfig(
            timeout=timeout,
            check_execute_permission=check_execute_permission,
            inherit_environment=inherit_environment,
            app_state_keys=app_state_keys or [],
        )

        if not self.script_path.exists():
            msg = f"CGI script not found: {script_path}"
            raise ValueError(msg)
        if not self.script_path.is_file():
            msg = f"CGI script path is not a file: {script_path}"
            raise ValueError(msg)

    async def __call__(self, request: Request, path_info: str = "") -> GeminiResponse:
        """Execute the CGI script for this request.

        Args:
            request: The Gemini request.
            path_info: Additional path info (usually empty for single scripts).

        Returns:
            GeminiResponse from the CGI script.

        Raises:
            CGIError: If execution fails.
        """
        # Check execute permission
        if self.config.check_execute_permission:
            if not os.access(self.script_path, os.X_OK):
                raise CGIError(f"CGI script not executable: {self.script_path.name}")

        # Build environment
        app_state_vars = self._get_app_state_vars(request)
        env = build_cgi_env(
            request,
            script_name=f"/{self.script_path.name}",
            path_info=path_info,
            app_state_vars=app_state_vars,
            inherit_environment=self.config.inherit_environment,
        )

        # Execute script
        cgi_response = await self._execute_script(env)

        return GeminiResponse(
            status=cgi_response.status,
            meta=cgi_response.meta,
            body=cgi_response.body,
        )

    def _get_app_state_vars(self, request: Request) -> dict[str, str]:
        """Extract app state variables to pass to CGI scripts."""
        if not self.config.app_state_keys:
            return {}

        result = {}
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

    async def _execute_script(self, env: dict[str, str]) -> CGIResponse:
        """Execute the CGI script and return the parsed response."""
        try:
            process = await asyncio.create_subprocess_exec(
                str(self.script_path),
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.config.timeout,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise CGIError(
                    f"CGI script timeout after {self.config.timeout}s"
                ) from None

            if process.returncode != 0:
                # Log stderr server-side but don't expose to client
                if stderr:
                    error_detail = stderr.decode("utf-8", errors="replace")[:500]
                    logger.error(
                        "cgi_script_failed",
                        script=str(self.script_path),
                        returncode=process.returncode,
                        stderr=error_detail,
                    )
                raise CGIError(f"CGI script exited with code {process.returncode}")

            return parse_cgi_output(stdout, stderr)

        except FileNotFoundError:
            raise NotFound(f"CGI script not found: {self.script_path.name}") from None
        except PermissionError:
            raise CGIError(f"Permission denied: {self.script_path.name}") from None


__all__ = [
    "CGIConfig",
    "CGIHandler",
    "CGIResponse",
    "CGIScript",
    "build_cgi_env",
    "parse_cgi_output",
]
