"""Tests for CGI support in Xitzin.

This module tests CGI script execution, environment variable handling,
security validation, and integration with the Xitzin application.
"""

from __future__ import annotations

import stat
import sys
from pathlib import Path

import pytest

from xitzin import CGIConfig, CGIHandler, CGIScript, Xitzin
from xitzin.cgi import build_cgi_env, parse_cgi_output
from xitzin.exceptions import BadRequest, CGIError, NotFound
from xitzin.testing import TestClient


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def cgi_dir(tmp_path: Path) -> Path:
    """Create a temporary CGI directory with test scripts."""
    cgi_bin = tmp_path / "cgi-bin"
    cgi_bin.mkdir()
    return cgi_bin


@pytest.fixture
def hello_script(cgi_dir: Path) -> Path:
    """Create a simple hello world CGI script."""
    script = cgi_dir / "hello.py"
    script.write_text(
        f"""#!{sys.executable}
import os

print("20 text/gemini")
print()
print("# Hello from CGI!")
print()
print(f"Query: {{os.environ.get('QUERY_STRING', 'none')}}")
"""
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return script


@pytest.fixture
def env_script(cgi_dir: Path) -> Path:
    """Create a script that dumps environment variables."""
    script = cgi_dir / "env.py"
    script.write_text(
        f"""#!{sys.executable}
import os

print("20 text/gemini")
print()
print("# Environment Variables")
print()
for key in sorted(os.environ.keys()):
    if key.startswith(('GATEWAY', 'SERVER', 'GEMINI', 'SCRIPT', 'PATH_INFO',
                       'QUERY', 'REMOTE', 'TLS', 'XITZIN')):
        print(f"{{key}}: {{os.environ[key]}}")
"""
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return script


@pytest.fixture
def error_script(cgi_dir: Path) -> Path:
    """Create a script that exits with an error."""
    script = cgi_dir / "error.py"
    script.write_text(
        f"""#!{sys.executable}
import sys
print("Error message", file=sys.stderr)
sys.exit(1)
"""
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return script


@pytest.fixture
def timeout_script(cgi_dir: Path) -> Path:
    """Create a script that takes too long to execute."""
    script = cgi_dir / "timeout.py"
    script.write_text(
        f"""#!{sys.executable}
import time
time.sleep(100)
print("20 text/gemini")
print()
print("# Done")
"""
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return script


@pytest.fixture
def redirect_script(cgi_dir: Path) -> Path:
    """Create a script that returns a redirect."""
    script = cgi_dir / "redirect.py"
    script.write_text(
        f"""#!{sys.executable}
print("30 gemini://example.com/new-location")
"""
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return script


@pytest.fixture
def input_script(cgi_dir: Path) -> Path:
    """Create a script that requests input."""
    script = cgi_dir / "input.py"
    script.write_text(
        f"""#!{sys.executable}
import os

query = os.environ.get('QUERY_STRING', '')
if not query:
    print("10 Enter your name:")
else:
    print("20 text/gemini")
    print()
    print(f"# Hello, {{query}}!")
"""
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return script


@pytest.fixture
def non_executable_script(cgi_dir: Path) -> Path:
    """Create a non-executable script."""
    script = cgi_dir / "noexec.py"
    script.write_text(
        f"""#!{sys.executable}
print("20 text/gemini")
print()
print("# Should not run")
"""
    )
    # Don't add execute permission
    return script


# ============================================================================
# Tests for parse_cgi_output
# ============================================================================


class TestParseCGIOutput:
    """Tests for CGI output parsing."""

    def test_parse_standard_output(self):
        """Parse standard CGI output with status and MIME type."""
        stdout = b"20 text/gemini\r\n# Hello World\n"
        response = parse_cgi_output(stdout, None)

        assert response.status == 20
        assert response.meta == "text/gemini"
        assert response.body == "# Hello World\n"

    def test_parse_output_with_lf_only(self):
        """Parse output using LF instead of CRLF."""
        stdout = b"20 text/gemini\n# Hello World\n"
        response = parse_cgi_output(stdout, None)

        assert response.status == 20
        assert response.meta == "text/gemini"
        assert response.body == "# Hello World\n"

    def test_parse_redirect(self):
        """Parse redirect response."""
        stdout = b"30 gemini://example.com/new\r\n"
        response = parse_cgi_output(stdout, None)

        assert response.status == 30
        assert response.meta == "gemini://example.com/new"
        assert response.body is None

    def test_parse_input_required(self):
        """Parse input prompt response."""
        stdout = b"10 Enter your name:\r\n"
        response = parse_cgi_output(stdout, None)

        assert response.status == 10
        assert response.meta == "Enter your name:"
        assert response.body is None

    def test_parse_error_response(self):
        """Parse error response."""
        stdout = b"51 Page not found\r\n"
        response = parse_cgi_output(stdout, None)

        assert response.status == 51
        assert response.meta == "Page not found"

    def test_parse_mime_type_only(self):
        """Parse output with implicit status 20."""
        stdout = b"text/gemini\r\n# Hello World\n"
        response = parse_cgi_output(stdout, None)

        assert response.status == 20
        assert response.meta == "text/gemini"
        assert response.body == "# Hello World\n"

    def test_parse_empty_body(self):
        """Parse output with no body."""
        stdout = b"20 text/gemini\r\n"
        response = parse_cgi_output(stdout, None)

        assert response.status == 20
        assert response.meta == "text/gemini"
        assert response.body is None

    def test_parse_multiline_body(self):
        """Parse output with multi-line body."""
        stdout = b"20 text/gemini\r\n# Title\n\nParagraph 1\n\nParagraph 2\n"
        response = parse_cgi_output(stdout, None)

        assert response.status == 20
        assert "Title" in response.body
        assert "Paragraph 1" in response.body
        assert "Paragraph 2" in response.body

    def test_parse_empty_output_raises_error(self):
        """Empty output raises CGIError."""
        with pytest.raises(CGIError, match="no output"):
            parse_cgi_output(b"", None)

    def test_parse_empty_header_raises_error(self):
        """Empty header line raises CGIError."""
        with pytest.raises(CGIError, match="empty header"):
            parse_cgi_output(b"\r\n# Body", None)

    def test_parse_invalid_status_raises_error(self):
        """Invalid status code raises CGIError."""
        with pytest.raises(CGIError, match="Invalid CGI status"):
            parse_cgi_output(b"99 Invalid\r\n", None)

    def test_parse_unicode_content(self):
        """Parse output with Unicode content."""
        stdout = "20 text/gemini\r\n# こんにちは\n".encode("utf-8")
        response = parse_cgi_output(stdout, None)

        assert response.status == 20
        assert "こんにちは" in response.body


# ============================================================================
# Tests for build_cgi_env
# ============================================================================


class TestBuildCGIEnv:
    """Tests for CGI environment variable building."""

    def test_standard_cgi_variables(self):
        """Standard CGI variables are set correctly."""
        from nauyaca.protocol.request import GeminiRequest

        from xitzin.requests import Request

        raw = GeminiRequest.from_line("gemini://example.com/cgi-bin/test.py?query")
        request = Request(raw, None)

        env = build_cgi_env(request, script_name="/test.py", path_info="/extra")

        assert env["GATEWAY_INTERFACE"] == "CGI/1.1"
        assert env["SERVER_PROTOCOL"] == "GEMINI"
        assert env["SERVER_SOFTWARE"].startswith("Xitzin")
        assert env["GEMINI_URL"] == request.url
        assert env["SCRIPT_NAME"] == "/test.py"
        assert env["PATH_INFO"] == "/extra"
        assert env["QUERY_STRING"] == "query"
        assert env["SERVER_NAME"] == "example.com"
        assert env["SERVER_PORT"] == "1965"

    def test_empty_query_string(self):
        """Empty query string is handled correctly."""
        from nauyaca.protocol.request import GeminiRequest

        from xitzin.requests import Request

        raw = GeminiRequest.from_line("gemini://example.com/script.py")
        request = Request(raw, None)

        env = build_cgi_env(request, script_name="/script.py", path_info="")

        assert env["QUERY_STRING"] == ""

    def test_certificate_variables(self):
        """TLS certificate variables are set when cert is present."""
        from nauyaca.protocol.request import GeminiRequest

        from xitzin.requests import Request

        raw = GeminiRequest.from_line("gemini://example.com/script.py")
        raw.client_cert_fingerprint = "abc123def456"
        request = Request(raw, None)

        env = build_cgi_env(request, script_name="/script.py", path_info="")

        assert env["TLS_CLIENT_HASH"] == "abc123def456"
        assert env["TLS_CLIENT_AUTHORISED"] == "1"
        assert env["AUTH_TYPE"] == "CERTIFICATE"

    def test_no_certificate_variables(self):
        """TLS variables when no certificate is present."""
        from nauyaca.protocol.request import GeminiRequest

        from xitzin.requests import Request

        raw = GeminiRequest.from_line("gemini://example.com/script.py")
        request = Request(raw, None)

        env = build_cgi_env(request, script_name="/script.py", path_info="")

        assert "TLS_CLIENT_HASH" not in env
        assert env["TLS_CLIENT_AUTHORISED"] == "0"

    def test_app_state_variables(self):
        """App state variables are prefixed with XITZIN_."""
        from nauyaca.protocol.request import GeminiRequest

        from xitzin.requests import Request

        raw = GeminiRequest.from_line("gemini://example.com/script.py")
        request = Request(raw, None)

        app_state_vars = {"db_url": "postgres://localhost/db", "api_key": "secret123"}
        env = build_cgi_env(
            request,
            script_name="/script.py",
            path_info="",
            app_state_vars=app_state_vars,
        )

        assert env["XITZIN_DB_URL"] == "postgres://localhost/db"
        assert env["XITZIN_API_KEY"] == "secret123"

    def test_inherit_environment_true(self):
        """Inheriting environment includes parent variables."""
        from nauyaca.protocol.request import GeminiRequest

        from xitzin.requests import Request

        raw = GeminiRequest.from_line("gemini://example.com/script.py")
        request = Request(raw, None)

        env = build_cgi_env(
            request, script_name="/script.py", path_info="", inherit_environment=True
        )

        # Should include PATH from parent environment
        assert "PATH" in env

    def test_inherit_environment_false(self):
        """Not inheriting environment excludes parent variables."""
        from nauyaca.protocol.request import GeminiRequest

        from xitzin.requests import Request

        raw = GeminiRequest.from_line("gemini://example.com/script.py")
        request = Request(raw, None)

        env = build_cgi_env(
            request, script_name="/script.py", path_info="", inherit_environment=False
        )

        # Should still include CGI variables but not PATH
        assert "GATEWAY_INTERFACE" in env
        assert "PATH" not in env


# ============================================================================
# Tests for CGIHandler
# ============================================================================


class TestCGIHandler:
    """Tests for the CGI directory handler."""

    def test_init_with_valid_directory(self, cgi_dir: Path):
        """Initialize handler with a valid directory."""
        handler = CGIHandler(cgi_dir)

        assert handler.script_dir == cgi_dir

    def test_init_with_nonexistent_directory(self, tmp_path: Path):
        """Initialize with non-existent directory raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            CGIHandler(tmp_path / "nonexistent")

    def test_init_with_file_instead_of_directory(self, hello_script: Path):
        """Initialize with a file instead of directory raises ValueError."""
        with pytest.raises(ValueError, match="not a directory"):
            CGIHandler(hello_script)

    @pytest.mark.asyncio
    async def test_execute_simple_script(self, cgi_dir: Path, hello_script: Path):
        """Execute a simple CGI script."""
        from nauyaca.protocol.request import GeminiRequest

        from xitzin.requests import Request

        handler = CGIHandler(cgi_dir)
        raw = GeminiRequest.from_line("gemini://example.com/cgi-bin/hello.py")
        request = Request(raw, None)

        response = await handler(request, "/hello.py")

        assert response.status == 20
        assert response.meta == "text/gemini"
        assert "Hello from CGI" in response.body

    @pytest.mark.asyncio
    async def test_execute_with_query_string(self, cgi_dir: Path, hello_script: Path):
        """Execute script with query string."""
        from nauyaca.protocol.request import GeminiRequest

        from xitzin.requests import Request

        handler = CGIHandler(cgi_dir)
        raw = GeminiRequest.from_line(
            "gemini://example.com/cgi-bin/hello.py?test-query"
        )
        request = Request(raw, None)

        response = await handler(request, "/hello.py")

        assert response.status == 20
        assert "test-query" in response.body

    @pytest.mark.asyncio
    async def test_execute_nonexistent_script(self, cgi_dir: Path):
        """Execute non-existent script raises NotFound."""
        from nauyaca.protocol.request import GeminiRequest

        from xitzin.requests import Request

        handler = CGIHandler(cgi_dir)
        raw = GeminiRequest.from_line("gemini://example.com/cgi-bin/missing.py")
        request = Request(raw, None)

        with pytest.raises(NotFound, match="not found"):
            await handler(request, "/missing.py")

    @pytest.mark.asyncio
    async def test_execute_non_executable_script(
        self, cgi_dir: Path, non_executable_script: Path
    ):
        """Execute non-executable script raises CGIError."""
        from nauyaca.protocol.request import GeminiRequest

        from xitzin.requests import Request

        handler = CGIHandler(cgi_dir)
        raw = GeminiRequest.from_line("gemini://example.com/cgi-bin/noexec.py")
        request = Request(raw, None)

        with pytest.raises(CGIError, match="not executable"):
            await handler(request, "/noexec.py")

    @pytest.mark.asyncio
    async def test_execute_error_script(self, cgi_dir: Path, error_script: Path):
        """Execute script that exits with error raises CGIError."""
        from nauyaca.protocol.request import GeminiRequest

        from xitzin.requests import Request

        handler = CGIHandler(cgi_dir)
        raw = GeminiRequest.from_line("gemini://example.com/cgi-bin/error.py")
        request = Request(raw, None)

        with pytest.raises(CGIError, match="exited with code"):
            await handler(request, "/error.py")

    @pytest.mark.asyncio
    async def test_execute_redirect_script(self, cgi_dir: Path, redirect_script: Path):
        """Execute script that returns a redirect."""
        from nauyaca.protocol.request import GeminiRequest

        from xitzin.requests import Request

        handler = CGIHandler(cgi_dir)
        raw = GeminiRequest.from_line("gemini://example.com/cgi-bin/redirect.py")
        request = Request(raw, None)

        response = await handler(request, "/redirect.py")

        assert response.status == 30
        assert response.meta == "gemini://example.com/new-location"

    @pytest.mark.asyncio
    async def test_execute_input_script(self, cgi_dir: Path, input_script: Path):
        """Execute script that requests input."""
        from nauyaca.protocol.request import GeminiRequest

        from xitzin.requests import Request

        handler = CGIHandler(cgi_dir)

        # First request without query - should prompt for input
        raw1 = GeminiRequest.from_line("gemini://example.com/cgi-bin/input.py")
        request1 = Request(raw1, None)
        response1 = await handler(request1, "/input.py")

        assert response1.status == 10
        assert "Enter your name" in response1.meta

        # Second request with query - should return greeting
        raw2 = GeminiRequest.from_line("gemini://example.com/cgi-bin/input.py?Alice")
        request2 = Request(raw2, None)
        response2 = await handler(request2, "/input.py")

        assert response2.status == 20
        assert "Hello, Alice" in response2.body

    @pytest.mark.asyncio
    async def test_timeout_handling(self, cgi_dir: Path, timeout_script: Path):
        """Script that exceeds timeout is killed."""
        from nauyaca.protocol.request import GeminiRequest

        from xitzin.requests import Request

        config = CGIConfig(timeout=0.1)  # Very short timeout
        handler = CGIHandler(cgi_dir, config=config)
        raw = GeminiRequest.from_line("gemini://example.com/cgi-bin/timeout.py")
        request = Request(raw, None)

        with pytest.raises(CGIError, match="timeout"):
            await handler(request, "/timeout.py")

    @pytest.mark.asyncio
    async def test_path_traversal_prevention(self, cgi_dir: Path, hello_script: Path):
        """Path traversal attempts are blocked."""
        from nauyaca.protocol.request import GeminiRequest

        from xitzin.requests import Request

        handler = CGIHandler(cgi_dir)
        raw = GeminiRequest.from_line(
            "gemini://example.com/cgi-bin/../../../etc/passwd"
        )
        request = Request(raw, None)

        with pytest.raises(BadRequest, match="Invalid script name"):
            await handler(request, "/../../../etc/passwd")

    @pytest.mark.asyncio
    async def test_absolute_path_blocked(self, cgi_dir: Path):
        """Absolute paths are blocked (stripped and return NotFound)."""
        from nauyaca.protocol.request import GeminiRequest

        from xitzin.requests import Request

        handler = CGIHandler(cgi_dir)
        raw = GeminiRequest.from_line("gemini://example.com/cgi-bin//etc/passwd")
        request = Request(raw, None)

        # Absolute paths are stripped, so it looks for "etc" which doesn't exist
        # This is secure behavior - it can't access /etc/passwd
        with pytest.raises(NotFound):
            await handler(request, "//etc/passwd")

    @pytest.mark.asyncio
    async def test_empty_path_info(self, cgi_dir: Path):
        """Empty path info raises NotFound."""
        from nauyaca.protocol.request import GeminiRequest

        from xitzin.requests import Request

        handler = CGIHandler(cgi_dir)
        raw = GeminiRequest.from_line("gemini://example.com/cgi-bin/")
        request = Request(raw, None)

        with pytest.raises(NotFound, match="No CGI script"):
            await handler(request, "")

    @pytest.mark.asyncio
    async def test_extra_path_info(self, cgi_dir: Path, env_script: Path):
        """Extra path info after script name is passed correctly."""
        from nauyaca.protocol.request import GeminiRequest

        from xitzin.requests import Request

        handler = CGIHandler(cgi_dir)
        raw = GeminiRequest.from_line("gemini://example.com/cgi-bin/env.py/extra/path")
        request = Request(raw, None)

        response = await handler(request, "/env.py/extra/path")

        assert response.status == 20
        assert "PATH_INFO: /extra/path" in response.body


# ============================================================================
# Tests for CGIScript
# ============================================================================


class TestCGIScript:
    """Tests for the single-script CGI handler."""

    def test_init_with_valid_script(self, hello_script: Path):
        """Initialize handler with a valid script."""
        handler = CGIScript(hello_script)

        assert handler.script_path == hello_script

    def test_init_with_nonexistent_script(self, tmp_path: Path):
        """Initialize with non-existent script raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            CGIScript(tmp_path / "nonexistent.py")

    def test_init_with_directory(self, cgi_dir: Path):
        """Initialize with a directory raises ValueError."""
        with pytest.raises(ValueError, match="not a file"):
            CGIScript(cgi_dir)

    @pytest.mark.asyncio
    async def test_execute_script(self, hello_script: Path):
        """Execute the configured CGI script."""
        from nauyaca.protocol.request import GeminiRequest

        from xitzin.requests import Request

        handler = CGIScript(hello_script)
        raw = GeminiRequest.from_line("gemini://example.com/hello")
        request = Request(raw, None)

        response = await handler(request)

        assert response.status == 20
        assert "Hello from CGI" in response.body

    @pytest.mark.asyncio
    async def test_execute_with_query(self, hello_script: Path):
        """Execute script with query string."""
        from nauyaca.protocol.request import GeminiRequest

        from xitzin.requests import Request

        handler = CGIScript(hello_script)
        raw = GeminiRequest.from_line("gemini://example.com/hello?test")
        request = Request(raw, None)

        response = await handler(request)

        assert response.status == 20
        assert "test" in response.body

    @pytest.mark.asyncio
    async def test_custom_timeout(self, timeout_script: Path):
        """Custom timeout is respected."""
        from nauyaca.protocol.request import GeminiRequest

        from xitzin.requests import Request

        handler = CGIScript(timeout_script, timeout=0.1)
        raw = GeminiRequest.from_line("gemini://example.com/timeout")
        request = Request(raw, None)

        with pytest.raises(CGIError, match="timeout"):
            await handler(request)


# ============================================================================
# Tests for CGIConfig
# ============================================================================


class TestCGIConfig:
    """Tests for CGI configuration."""

    def test_default_values(self):
        """Default configuration values are set correctly."""
        config = CGIConfig()

        assert config.timeout == 30.0
        assert config.max_header_size == 8192
        assert config.streaming is False
        assert config.check_execute_permission is True
        assert config.inherit_environment is True
        assert config.app_state_keys == []

    def test_custom_values(self):
        """Custom configuration values are set correctly."""
        config = CGIConfig(
            timeout=60.0,
            max_header_size=4096,
            streaming=True,
            check_execute_permission=False,
            inherit_environment=False,
            app_state_keys=["db_url", "api_key"],
        )

        assert config.timeout == 60.0
        assert config.max_header_size == 4096
        assert config.streaming is True
        assert config.check_execute_permission is False
        assert config.inherit_environment is False
        assert config.app_state_keys == ["db_url", "api_key"]


# ============================================================================
# Integration Tests with Xitzin Application
# ============================================================================


class TestCGIIntegration:
    """Integration tests with the Xitzin application."""

    def test_mount_cgi_handler(self, cgi_dir: Path, hello_script: Path):
        """Mount CGI handler and handle requests."""
        app = Xitzin()
        app.mount("/cgi-bin", CGIHandler(cgi_dir))

        client = TestClient(app)
        response = client.get("/cgi-bin/hello.py")

        assert response.is_success
        assert "Hello from CGI" in response.body

    def test_mount_cgi_with_query(self, cgi_dir: Path, hello_script: Path):
        """CGI handler receives query string."""
        app = Xitzin()
        app.mount("/cgi-bin", CGIHandler(cgi_dir))

        client = TestClient(app)
        response = client.get("/cgi-bin/hello.py", query="test-query")

        assert response.is_success
        assert "test-query" in response.body

    def test_mount_cgi_script(self, hello_script: Path):
        """Mount single CGI script."""
        app = Xitzin()
        app.mount("/hello", CGIScript(hello_script))

        client = TestClient(app)
        response = client.get("/hello")

        assert response.is_success
        assert "Hello from CGI" in response.body

    def test_cgi_convenience_method(self, cgi_dir: Path, hello_script: Path):
        """Use app.cgi() convenience method."""
        app = Xitzin()
        app.cgi("/cgi-bin", cgi_dir)

        client = TestClient(app)
        response = client.get("/cgi-bin/hello.py")

        assert response.is_success
        assert "Hello from CGI" in response.body

    def test_cgi_with_middleware(self, cgi_dir: Path, hello_script: Path):
        """Middleware applies to CGI requests."""
        app = Xitzin()

        middleware_called = []

        @app.middleware
        async def tracking_middleware(request, call_next):
            middleware_called.append("before")
            response = await call_next(request)
            middleware_called.append("after")
            return response

        app.mount("/cgi-bin", CGIHandler(cgi_dir))

        client = TestClient(app)
        response = client.get("/cgi-bin/hello.py")

        assert response.is_success
        assert middleware_called == ["before", "after"]

    def test_cgi_not_found(self, cgi_dir: Path):
        """Non-existent CGI script returns 51."""
        app = Xitzin()
        app.mount("/cgi-bin", CGIHandler(cgi_dir))

        client = TestClient(app)
        response = client.get("/cgi-bin/missing.py")

        assert response.status == 51

    def test_cgi_error(self, cgi_dir: Path, error_script: Path):
        """CGI script error returns 42."""
        app = Xitzin()
        app.mount("/cgi-bin", CGIHandler(cgi_dir))

        client = TestClient(app)
        response = client.get("/cgi-bin/error.py")

        assert response.status == 42

    def test_cgi_with_certificate(self, cgi_dir: Path, env_script: Path):
        """CGI script receives certificate fingerprint."""
        app = Xitzin()
        app.mount("/cgi-bin", CGIHandler(cgi_dir))

        client = TestClient(app)
        auth_client = client.with_certificate("test-fingerprint-123")
        response = auth_client.get("/cgi-bin/env.py")

        assert response.is_success
        assert "TLS_CLIENT_HASH: test-fingerprint-123" in response.body
        assert "TLS_CLIENT_AUTHORISED: 1" in response.body

    def test_cgi_without_certificate(self, cgi_dir: Path, env_script: Path):
        """CGI script without certificate has TLS_CLIENT_AUTHORISED=0."""
        app = Xitzin()
        app.mount("/cgi-bin", CGIHandler(cgi_dir))

        client = TestClient(app)
        response = client.get("/cgi-bin/env.py")

        assert response.is_success
        assert "TLS_CLIENT_AUTHORISED: 0" in response.body

    def test_cgi_with_regular_routes(self, cgi_dir: Path, hello_script: Path):
        """CGI handler works alongside regular routes."""
        app = Xitzin()

        @app.gemini("/")
        def home(request):
            return "# Home"

        @app.gemini("/about")
        def about(request):
            return "# About"

        app.mount("/cgi-bin", CGIHandler(cgi_dir))

        client = TestClient(app)

        # Regular routes work
        assert client.get("/").is_success
        assert client.get("/about").is_success

        # CGI works
        response = client.get("/cgi-bin/hello.py")
        assert response.is_success
        assert "Hello from CGI" in response.body

    def test_mount_precedence_over_routes(self, cgi_dir: Path, hello_script: Path):
        """Mounted handlers take precedence over regular routes."""
        app = Xitzin()

        # This route would match /cgi-bin/anything but mount should win
        @app.gemini("/cgi-bin/{script:path}")
        def cgi_route(request, script):
            return "# Regular route"

        app.mount("/cgi-bin", CGIHandler(cgi_dir))

        client = TestClient(app)
        response = client.get("/cgi-bin/hello.py")

        # Mount handler should win
        assert "Hello from CGI" in response.body


# ============================================================================
# Tests for MountedRoute
# ============================================================================


class TestMountedRoute:
    """Tests for the MountedRoute class."""

    def test_prefix_matching(self):
        """MountedRoute matches path prefixes correctly."""
        from xitzin.routing import MountedRoute

        async def handler(request, path_info):
            return f"Path: {path_info}"

        route = MountedRoute("/api", handler)

        assert route.matches("/api") is True
        assert route.matches("/api/") is True
        assert route.matches("/api/users") is True
        assert route.matches("/api/users/123") is True
        assert route.matches("/apiv2") is False
        assert route.matches("/other") is False

    def test_path_info_extraction(self):
        """MountedRoute extracts path info correctly."""
        from xitzin.routing import MountedRoute

        async def handler(request, path_info):
            return f"Path: {path_info}"

        route = MountedRoute("/api", handler)

        assert route.extract_path_info("/api") == ""
        assert route.extract_path_info("/api/") == "/"
        assert route.extract_path_info("/api/users") == "/users"
        assert route.extract_path_info("/api/users/123") == "/users/123"

    def test_prefix_normalization(self):
        """MountedRoute normalizes path prefixes."""
        from xitzin.routing import MountedRoute

        async def handler(request, path_info):
            return ""

        route1 = MountedRoute("api", handler)
        route2 = MountedRoute("/api/", handler)
        route3 = MountedRoute("//api//", handler)

        assert route1.path_prefix == "/api"
        assert route2.path_prefix == "/api"
        assert route3.path_prefix == "/api"


# ============================================================================
# Tests for app.mount()
# ============================================================================


class TestAppMount:
    """Tests for the app.mount() method."""

    def test_mount_async_handler(self):
        """Mount an async handler."""
        app = Xitzin()

        async def handler(request, path_info):
            return f"# Path: {path_info}"

        app.mount("/api", handler)

        client = TestClient(app)
        response = client.get("/api/users")

        assert response.is_success
        assert "Path: /users" in response.body

    def test_mount_sync_handler(self):
        """Mount a sync handler."""
        app = Xitzin()

        def handler(request, path_info):
            return f"# Path: {path_info}"

        app.mount("/api", handler)

        client = TestClient(app)
        response = client.get("/api/users")

        assert response.is_success
        assert "Path: /users" in response.body

    def test_mount_with_name(self):
        """Mount handler with a custom name."""
        app = Xitzin()

        async def handler(request, path_info):
            return "# OK"

        app.mount("/api", handler, name="my_api")

        # Verify it's mounted (internal check)
        assert any(m.name == "my_api" for m in app._router._mounted_routes)

    def test_multiple_mounts(self):
        """Multiple mounts work correctly."""
        app = Xitzin()

        async def api_handler(request, path_info):
            return "# API"

        async def cgi_handler(request, path_info):
            return "# CGI"

        app.mount("/api", api_handler)
        app.mount("/cgi", cgi_handler)

        client = TestClient(app)

        assert "API" in client.get("/api/test").body
        assert "CGI" in client.get("/cgi/test").body

    def test_mount_with_callable_class(self):
        """Mount a callable class instance."""
        app = Xitzin()

        class Handler:
            async def __call__(self, request, path_info):
                return f"# Handler: {path_info}"

        app.mount("/api", Handler())

        client = TestClient(app)
        response = client.get("/api/test")

        assert response.is_success
        assert "Handler: /test" in response.body
