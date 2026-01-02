"""Shared pytest fixtures for Xitzin tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from nauyaca.protocol.request import GeminiRequest

from xitzin import Request, Xitzin
from xitzin.testing import TestClient


@pytest.fixture
def app() -> Xitzin:
    """Create a basic Xitzin application."""
    return Xitzin(title="Test App", version="1.0.0")


@pytest.fixture
def client(app: Xitzin) -> TestClient:
    """Create a test client for the app."""
    return TestClient(app)


@pytest.fixture
def raw_request() -> GeminiRequest:
    """Create a basic GeminiRequest."""
    return GeminiRequest.from_line("gemini://testserver/path")


@pytest.fixture
def request_with_app(raw_request: GeminiRequest, app: Xitzin) -> Request:
    """Create a Request bound to an app."""
    return Request(raw_request, app)


@pytest.fixture
def request_without_app(raw_request: GeminiRequest) -> Request:
    """Create a Request not bound to an app."""
    return Request(raw_request)


@pytest.fixture
def templates_dir(tmp_path: Path) -> Path:
    """Create a temporary templates directory with test templates."""
    templates = tmp_path / "templates"
    templates.mkdir()

    # Basic template
    (templates / "test_page.gmi").write_text("# {{ title }}\n{{ content }}")

    # Template with filters
    (templates / "test_filters.gmi").write_text(
        """{{ url | link(text) }}
{{ heading_text | heading(level) }}
{{ items | list }}
{{ quote_text | quote }}
{{ code | preformat(alt_text) }}"""
    )

    return templates


@pytest.fixture
def app_with_templates(templates_dir: Path) -> Xitzin:
    """Create an app with templates configured."""
    return Xitzin(title="Template App", templates_dir=templates_dir)


@pytest.fixture
def mock_fingerprint() -> str:
    """Return a mock certificate fingerprint."""
    return "abc123def456789012345678901234567890abcdef1234567890abcdef12345678"
