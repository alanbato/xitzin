"""Tests for static file serving."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from xitzin import Xitzin
from xitzin.staticfiles import (
    StaticFiles,
    StaticFilesConfig,
    _format_file_size,
)
from xitzin.testing import TestClient

if TYPE_CHECKING:
    pass


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def static_dir(tmp_path: Path) -> Path:
    """Create a test directory structure for static files."""
    # Create directory structure
    (tmp_path / "index.gmi").write_text("# Welcome\n\nThis is the index page.")
    (tmp_path / "about.gmi").write_text("# About\n\nAbout page content.")
    (tmp_path / "style.css").write_text("body { color: #333; }")
    (tmp_path / "data.json").write_text('{"key": "value"}')
    (tmp_path / "readme.txt").write_text("Plain text file.")

    # Create subdirectory with its own index
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "index.gmi").write_text("# Documentation\n\nDocs index.")
    (docs_dir / "guide.gmi").write_text("# User Guide\n\nGuide content.")

    # Create subdirectory without index
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    # Create a small binary file (PNG header)
    (images_dir / "logo.png").write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    )

    # Create hidden file
    (tmp_path / ".hidden").write_text("hidden content")

    return tmp_path


@pytest.fixture
def app(static_dir: Path) -> Xitzin:
    """Create test app with static files mounted."""
    app = Xitzin()
    app.static("/files", static_dir)
    return app


@pytest.fixture
def client(app: Xitzin) -> TestClient:
    """Create test client for the app."""
    return TestClient(app)


# =============================================================================
# Basic File Serving Tests
# =============================================================================


class TestBasicFileServing:
    """Test basic file serving functionality."""

    def test_serve_text_file(self, client: TestClient) -> None:
        """Test serving a text file."""
        response = client.get("/files/about.gmi")
        assert response.status == 20
        assert response.meta == "text/gemini"
        assert "# About" in response.body

    def test_serve_index_file(self, client: TestClient) -> None:
        """Test serving directory index file."""
        response = client.get("/files/")
        assert response.status == 20
        assert response.meta == "text/gemini"
        assert "# Welcome" in response.body

    def test_serve_subdirectory_index(self, client: TestClient) -> None:
        """Test serving subdirectory index file."""
        response = client.get("/files/docs/")
        assert response.status == 20
        assert response.meta == "text/gemini"
        assert "# Documentation" in response.body

    def test_serve_css_file(self, client: TestClient) -> None:
        """Test serving CSS with correct MIME type."""
        response = client.get("/files/style.css")
        assert response.status == 20
        assert response.meta == "text/css"
        assert "color" in response.body

    def test_serve_json_file(self, client: TestClient) -> None:
        """Test serving JSON with correct MIME type."""
        response = client.get("/files/data.json")
        assert response.status == 20
        assert response.meta == "application/json"
        assert '"key"' in response.body

    def test_serve_binary_file(self, static_dir: Path) -> None:
        """Test serving binary file (PNG)."""
        # Directly test the StaticFiles handler since TestClient decodes as UTF-8
        import asyncio
        from xitzin.requests import Request
        from nauyaca.protocol.request import GeminiRequest

        handler = StaticFiles(static_dir)

        # Create a mock request
        raw_request = GeminiRequest(
            raw_url="gemini://localhost/files/images/logo.png",
            parsed_url=type(
                "ParsedURL",
                (),
                {
                    "scheme": "gemini",
                    "hostname": "localhost",
                    "port": 1965,
                    "path": "/files/images/logo.png",
                    "query": "",
                },
            )(),
            client_cert=None,
            client_cert_fingerprint=None,
        )
        request = Request(raw_request, None)

        response = asyncio.get_event_loop().run_until_complete(
            handler(request, "/images/logo.png")
        )

        assert response.status == 20
        assert response.meta == "image/png"
        # Body should be bytes for binary content
        assert isinstance(response.body, bytes)
        assert response.body.startswith(b"\x89PNG")

    def test_file_not_found(self, client: TestClient) -> None:
        """Test 404 for non-existent file."""
        response = client.get("/files/nonexistent.gmi")
        assert response.status == 51

    def test_root_path(self, client: TestClient) -> None:
        """Test serving at root mount without trailing slash."""
        # Mount path without trailing slash - the MountedRoute.extract_path_info
        # returns "" for exact match, which resolves to the directory
        # Since an index.gmi exists, it gets served
        response = client.get("/files")
        # Because path_info is "" (no subdirectory), redirect isn't triggered
        # The index.gmi at root is served
        assert response.status == 20
        assert "# Welcome" in response.body


# =============================================================================
# Directory Handling Tests
# =============================================================================


class TestDirectoryHandling:
    """Test directory handling and redirects."""

    def test_directory_redirect_adds_trailing_slash(self, client: TestClient) -> None:
        """Test that directory without trailing slash redirects."""
        response = client.get("/files/docs")
        assert response.status == 30
        assert response.meta == "/files/docs/"

    def test_directory_with_trailing_slash_serves_index(
        self, client: TestClient
    ) -> None:
        """Test that directory with trailing slash serves index."""
        response = client.get("/files/docs/")
        assert response.status == 20
        assert "# Documentation" in response.body

    def test_directory_no_index_no_listing(self, static_dir: Path) -> None:
        """Test 404 when no index and listing disabled."""
        app = Xitzin()
        app.static("/files", static_dir, directory_listing=False)
        client = TestClient(app)

        response = client.get("/files/images/")
        assert response.status == 51

    def test_directory_listing_enabled(self, static_dir: Path) -> None:
        """Test directory listing when enabled."""
        app = Xitzin()
        app.static("/files", static_dir, directory_listing=True)
        client = TestClient(app)

        response = client.get("/files/images/")
        assert response.status == 20
        assert response.meta == "text/gemini"
        assert "# Index of /images/" in response.body
        assert "=> logo.png" in response.body
        assert "=> ../" in response.body

    def test_root_directory_listing(self, static_dir: Path) -> None:
        """Test directory listing at root."""
        app = Xitzin()
        app.static("/files", static_dir, directory_listing=True)
        client = TestClient(app)

        response = client.get("/files/")
        # Should serve index.gmi, not listing
        assert response.status == 20
        assert "# Welcome" in response.body

    def test_directory_listing_without_index(self, static_dir: Path) -> None:
        """Test listing shown when no index exists."""
        # Remove index files
        (static_dir / "index.gmi").unlink()
        (static_dir / "index.gemini").unlink(missing_ok=True)

        app = Xitzin()
        app.static("/files", static_dir, directory_listing=True)
        client = TestClient(app)

        response = client.get("/files/")
        assert response.status == 20
        assert "# Index of /" in response.body
        assert "=> about.gmi" in response.body
        assert "=> docs/" in response.body


# =============================================================================
# Custom Index Files Tests
# =============================================================================


class TestCustomIndexFiles:
    """Test custom index file configuration."""

    def test_custom_index_files(self, static_dir: Path) -> None:
        """Test serving custom index file."""
        # Create a custom index
        (static_dir / "home.gmi").write_text("# Custom Home")

        app = Xitzin()
        app.static("/files", static_dir, index_files=["home.gmi", "index.gmi"])
        client = TestClient(app)

        response = client.get("/files/")
        assert response.status == 20
        assert "# Custom Home" in response.body

    def test_fallback_index_files(self, static_dir: Path) -> None:
        """Test fallback to second index file."""
        # index.gmi exists, so it should be served as fallback
        app = Xitzin()
        app.static("/files", static_dir, index_files=["nonexistent.gmi", "index.gmi"])
        client = TestClient(app)

        response = client.get("/files/")
        assert response.status == 20
        assert "# Welcome" in response.body


# =============================================================================
# MIME Type Tests
# =============================================================================


class TestMimeTypes:
    """Test MIME type detection and overrides."""

    def test_default_mime_types(self, static_dir: Path) -> None:
        """Test default MIME type mappings."""
        app = Xitzin()
        app.static("/files", static_dir)
        client = TestClient(app)

        # .gmi -> text/gemini
        response = client.get("/files/about.gmi")
        assert response.meta == "text/gemini"

        # .txt -> text/plain
        response = client.get("/files/readme.txt")
        assert response.meta == "text/plain"

    def test_custom_mime_type_override(self, static_dir: Path) -> None:
        """Test custom MIME type override."""
        # Create a file with custom extension
        (static_dir / "data.custom").write_text("custom content")

        app = Xitzin()
        app.static(
            "/files",
            static_dir,
            mime_types={".custom": "application/x-custom"},
        )
        client = TestClient(app)

        response = client.get("/files/data.custom")
        assert response.status == 20
        assert response.meta == "application/x-custom"

    def test_unknown_extension_defaults_to_gemtext(self, static_dir: Path) -> None:
        """Test unknown extension defaults to text/gemini."""
        (static_dir / "file.unknown").write_text("unknown content")

        app = Xitzin()
        app.static("/files", static_dir)
        client = TestClient(app)

        response = client.get("/files/file.unknown")
        assert response.status == 20
        assert response.meta == "text/gemini"


# =============================================================================
# Security Tests
# =============================================================================


class TestSecurity:
    """Test security features."""

    def test_path_traversal_blocked(self, static_dir: Path) -> None:
        """Test path traversal attack is blocked."""
        # Create a file outside the static dir
        parent = static_dir.parent
        (parent / "secret.txt").write_text("secret data")

        app = Xitzin()
        app.static("/files", static_dir)
        client = TestClient(app)

        response = client.get("/files/../secret.txt")
        assert response.status == 59  # BadRequest

    def test_path_traversal_encoded(self, static_dir: Path) -> None:
        """Test encoded path traversal is blocked."""
        app = Xitzin()
        app.static("/files", static_dir)
        client = TestClient(app)

        # URL-encoded ..
        response = client.get("/files/..%2F..%2Fetc%2Fpasswd")
        # This should be blocked by the .lstrip("/") and .. check
        assert response.status in (51, 59)

    def test_hidden_files_in_listing(self, static_dir: Path) -> None:
        """Test hidden files are excluded from listings."""
        app = Xitzin()
        app.static("/files", static_dir, directory_listing=True)
        client = TestClient(app)

        # Remove index so we get listing
        (static_dir / "index.gmi").unlink()

        response = client.get("/files/")
        assert response.status == 20
        assert ".hidden" not in response.body

    def test_symlink_blocked_by_default(self, static_dir: Path) -> None:
        """Test symlinks are blocked by default."""
        # Create a symlink to a file outside
        target = static_dir.parent / "external.txt"
        target.write_text("external content")
        link = static_dir / "link.txt"

        try:
            link.symlink_to(target)
        except OSError:
            pytest.skip("Cannot create symlinks on this system")

        app = Xitzin()
        app.static("/files", static_dir, follow_symlinks=False)
        client = TestClient(app)

        response = client.get("/files/link.txt")
        assert response.status == 59  # BadRequest

    def test_symlink_allowed_when_enabled(self, static_dir: Path) -> None:
        """Test symlinks work when enabled."""
        # Create a symlink to a file inside the directory
        target = static_dir / "about.gmi"
        link = static_dir / "link.gmi"

        try:
            link.symlink_to(target)
        except OSError:
            pytest.skip("Cannot create symlinks on this system")

        app = Xitzin()
        app.static("/files", static_dir, follow_symlinks=True)
        client = TestClient(app)

        response = client.get("/files/link.gmi")
        assert response.status == 20
        assert "# About" in response.body


# =============================================================================
# File Size Limit Tests
# =============================================================================


class TestFileSizeLimit:
    """Test file size limit enforcement."""

    def test_large_file_blocked(self, static_dir: Path) -> None:
        """Test files exceeding limit are blocked."""
        # Create a file larger than 1KB
        large_content = "x" * 2000
        (static_dir / "large.txt").write_text(large_content)

        app = Xitzin()
        # Set limit to 1KB
        app.static("/files", static_dir, max_file_size=1024)
        client = TestClient(app)

        response = client.get("/files/large.txt")
        assert response.status == 59  # BadRequest
        assert "too large" in response.meta.lower()

    def test_file_within_limit_served(self, static_dir: Path) -> None:
        """Test files within limit are served."""
        small_content = "x" * 500
        (static_dir / "small.txt").write_text(small_content)

        app = Xitzin()
        app.static("/files", static_dir, max_file_size=1024)
        client = TestClient(app)

        response = client.get("/files/small.txt")
        assert response.status == 20


# =============================================================================
# Custom 404 Handler Tests
# =============================================================================


class TestCustom404Handler:
    """Test custom not-found handler."""

    def test_custom_404_handler(self, static_dir: Path) -> None:
        """Test custom 404 handler is called."""
        app = Xitzin()
        handler = app.static("/files", static_dir)

        @handler.not_found
        def custom_404(request, path_info):
            return f"# Custom Not Found\n\nFile {path_info} doesn't exist."

        client = TestClient(app)

        response = client.get("/files/nonexistent.gmi")
        assert response.status == 20  # Custom handler returns success
        assert "# Custom Not Found" in response.body
        assert "nonexistent.gmi" in response.body

    def test_custom_404_handler_async(self, static_dir: Path) -> None:
        """Test async custom 404 handler."""
        app = Xitzin()
        handler = app.static("/files", static_dir)

        @handler.not_found
        async def custom_404(request, path_info):
            return f"# Async Not Found\n\nPath: {path_info}"

        client = TestClient(app)

        response = client.get("/files/nonexistent.gmi")
        assert response.status == 20
        assert "# Async Not Found" in response.body


# =============================================================================
# Configuration Tests
# =============================================================================


class TestConfiguration:
    """Test StaticFilesConfig and initialization."""

    def test_config_object(self, static_dir: Path) -> None:
        """Test using StaticFilesConfig object."""
        config = StaticFilesConfig(
            index_files=["home.gmi"],
            directory_listing=True,
            max_file_size=1024 * 1024,
        )

        handler = StaticFiles(static_dir, config=config)
        assert handler.index_files == ["home.gmi"]
        assert handler.directory_listing is True
        assert handler.max_file_size == 1024 * 1024

    def test_explicit_params_override_config(self, static_dir: Path) -> None:
        """Test explicit parameters override config."""
        config = StaticFilesConfig(
            index_files=["config.gmi"],
            directory_listing=False,
        )

        handler = StaticFiles(
            static_dir,
            config=config,
            index_files=["override.gmi"],
            directory_listing=True,
        )

        assert handler.index_files == ["override.gmi"]
        assert handler.directory_listing is True

    def test_invalid_directory_raises(self, tmp_path: Path) -> None:
        """Test ValueError for non-existent directory."""
        with pytest.raises(ValueError, match="not found"):
            StaticFiles(tmp_path / "nonexistent")

    def test_file_as_directory_raises(self, static_dir: Path) -> None:
        """Test ValueError when directory is a file."""
        with pytest.raises(ValueError, match="not a directory"):
            StaticFiles(static_dir / "about.gmi")


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests with full app."""

    def test_multiple_static_mounts(self, tmp_path: Path) -> None:
        """Test multiple static directories mounted."""
        # Create two directories
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "readme.gmi").write_text("# Docs")

        images = tmp_path / "images"
        images.mkdir()
        (images / "info.gmi").write_text("# Images Info")

        app = Xitzin()
        app.static("/docs", docs)
        app.static("/images", images)
        client = TestClient(app)

        response = client.get("/docs/readme.gmi")
        assert response.status == 20
        assert "# Docs" in response.body

        response = client.get("/images/info.gmi")
        assert response.status == 20
        assert "# Images Info" in response.body

    def test_static_with_regular_routes(self, static_dir: Path) -> None:
        """Test static files work with regular routes."""
        app = Xitzin()

        @app.gemini("/")
        def home(request):
            return "# Home Page"

        @app.gemini("/api/data")
        def api_data(request):
            return "# API Data"

        app.static("/files", static_dir)
        client = TestClient(app)

        # Regular routes work
        response = client.get("/")
        assert response.status == 20
        assert "# Home Page" in response.body

        response = client.get("/api/data")
        assert response.status == 20
        assert "# API Data" in response.body

        # Static files work
        response = client.get("/files/about.gmi")
        assert response.status == 20
        assert "# About" in response.body

    def test_direct_mount_usage(self, static_dir: Path) -> None:
        """Test using mount() directly with StaticFiles."""
        app = Xitzin()
        handler = StaticFiles(static_dir, directory_listing=True)
        app.mount("/static", handler)
        client = TestClient(app)

        response = client.get("/static/about.gmi")
        assert response.status == 20
        assert "# About" in response.body

    def test_root_mount_serves_subpaths(self, static_dir: Path) -> None:
        """Test static files mounted at root serves sub-paths correctly.

        Regression test for: app.static("/", directory) should serve
        all files under the directory, not just the root path.
        """
        app = Xitzin()
        app.static("/", static_dir)
        client = TestClient(app)

        # Root path should serve index
        response = client.get("/")
        assert response.status == 20
        assert "# Welcome" in response.body

        # Sub-path file should be served
        response = client.get("/about.gmi")
        assert response.status == 20
        assert "# About" in response.body

        # Subdirectory index should be served
        response = client.get("/docs/")
        assert response.status == 20
        assert "# Documentation" in response.body

        # File in subdirectory should be served
        response = client.get("/docs/guide.gmi")
        assert response.status == 20
        assert "# User Guide" in response.body

        # Non-existent file should return 404
        response = client.get("/nonexistent.gmi")
        assert response.status == 51


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestHelperFunctions:
    """Test helper functions."""

    @pytest.mark.parametrize(
        "size,expected",
        [
            (0, "0 B"),
            (100, "100 B"),
            (1024, "1.0 KB"),
            (1536, "1.5 KB"),
            (10240, "10 KB"),
            (1024 * 1024, "1.0 MB"),
            (1024 * 1024 * 100, "100 MB"),
            (1024 * 1024 * 1024, "1.0 GB"),
        ],
    )
    def test_format_file_size(self, size: int, expected: str) -> None:
        """Test file size formatting."""
        assert _format_file_size(size) == expected
