"""Tests for xitzin.requests module."""

import pytest
from nauyaca.protocol.request import GeminiRequest

from xitzin import Request, Xitzin
from xitzin.requests import RequestState


class TestRequestState:
    """Tests for RequestState class."""

    def test_setattr(self):
        """Can set arbitrary attributes on RequestState."""
        state = RequestState()
        state.user = "alice"
        state.count = 42
        assert state.user == "alice"
        assert state.count == 42

    def test_getattr_missing_raises_attribute_error(self):
        """Accessing missing attribute raises AttributeError."""
        state = RequestState()
        with pytest.raises(
            AttributeError, match="'RequestState' has no attribute 'missing'"
        ):
            _ = state.missing

    def test_delattr(self):
        """Can delete attributes from RequestState."""
        state = RequestState()
        state.temp = "value"
        assert state.temp == "value"
        del state.temp
        with pytest.raises(AttributeError):
            _ = state.temp

    def test_delattr_missing_raises_attribute_error(self):
        """Deleting missing attribute raises AttributeError."""
        state = RequestState()
        with pytest.raises(
            AttributeError, match="'RequestState' has no attribute 'missing'"
        ):
            del state.missing

    def test_multiple_attributes(self):
        """Can set and access multiple attributes."""
        state = RequestState()
        state.a = 1
        state.b = "two"
        state.c = [3, 4, 5]
        assert state.a == 1
        assert state.b == "two"
        assert state.c == [3, 4, 5]


class TestRequest:
    """Tests for Request class."""

    def test_path_property(self):
        """Request.path returns the URL path."""
        raw = GeminiRequest.from_line("gemini://example.com/users/alice")
        request = Request(raw)
        assert request.path == "/users/alice"

    def test_path_property_root(self):
        """Request.path returns root path."""
        raw = GeminiRequest.from_line("gemini://example.com/")
        request = Request(raw)
        assert request.path == "/"

    def test_raw_query_property(self):
        """Request.raw_query returns URL-encoded query."""
        raw = GeminiRequest.from_line("gemini://example.com/search?hello%20world")
        request = Request(raw)
        assert request.raw_query == "hello%20world"

    def test_query_property_decoded(self):
        """Request.query returns decoded query string."""
        raw = GeminiRequest.from_line("gemini://example.com/search?hello%20world")
        request = Request(raw)
        assert request.query == "hello world"

    def test_query_property_plus_decoded(self):
        """Request.query decodes + as space."""
        raw = GeminiRequest.from_line("gemini://example.com/search?hello+world")
        request = Request(raw)
        assert request.query == "hello world"

    def test_query_property_empty(self):
        """Request.query returns empty string when no query."""
        raw = GeminiRequest.from_line("gemini://example.com/page")
        request = Request(raw)
        assert request.query == ""

    def test_url_property(self):
        """Request.url returns normalized URL."""
        raw = GeminiRequest.from_line("gemini://example.com/page")
        request = Request(raw)
        assert "gemini://example.com" in request.url

    def test_raw_url_property(self):
        """Request.raw_url returns original URL."""
        url = "gemini://example.com/page"
        raw = GeminiRequest.from_line(url)
        request = Request(raw)
        assert request.raw_url == url

    def test_hostname_property(self):
        """Request.hostname returns server hostname."""
        raw = GeminiRequest.from_line("gemini://example.com:1965/page")
        request = Request(raw)
        assert request.hostname == "example.com"

    def test_port_property_default(self):
        """Request.port returns default Gemini port."""
        raw = GeminiRequest.from_line("gemini://example.com/page")
        request = Request(raw)
        assert request.port == 1965

    def test_port_property_custom(self):
        """Request.port returns custom port."""
        raw = GeminiRequest.from_line("gemini://example.com:1966/page")
        request = Request(raw)
        assert request.port == 1966

    def test_app_property_raises_when_unbound(self):
        """Request.app raises RuntimeError when not bound."""
        raw = GeminiRequest.from_line("gemini://example.com/page")
        request = Request(raw)
        with pytest.raises(RuntimeError, match="Request is not bound to an application"):
            _ = request.app

    def test_app_property_returns_app_when_bound(self):
        """Request.app returns the bound application."""
        raw = GeminiRequest.from_line("gemini://example.com/page")
        app = Xitzin()
        request = Request(raw, app)
        assert request.app is app

    def test_state_property(self):
        """Request.state returns a RequestState instance."""
        raw = GeminiRequest.from_line("gemini://example.com/page")
        request = Request(raw)
        assert isinstance(request.state, RequestState)

    def test_state_is_mutable(self):
        """Request.state can store arbitrary values."""
        raw = GeminiRequest.from_line("gemini://example.com/page")
        request = Request(raw)
        request.state.user = "bob"
        assert request.state.user == "bob"

    def test_state_persists(self):
        """Request.state returns same instance on multiple accesses."""
        raw = GeminiRequest.from_line("gemini://example.com/page")
        request = Request(raw)
        request.state.value = 42
        assert request.state.value == 42

    def test_client_cert_none_by_default(self):
        """Request.client_cert is None when no certificate provided."""
        raw = GeminiRequest.from_line("gemini://example.com/page")
        request = Request(raw)
        assert request.client_cert is None

    def test_client_cert_fingerprint_none_by_default(self):
        """Request.client_cert_fingerprint is None when no certificate."""
        raw = GeminiRequest.from_line("gemini://example.com/page")
        request = Request(raw)
        assert request.client_cert_fingerprint is None

    def test_client_cert_fingerprint_when_set(self):
        """Request.client_cert_fingerprint returns fingerprint when set."""
        raw = GeminiRequest.from_line("gemini://example.com/page")
        raw.client_cert_fingerprint = "abc123"
        request = Request(raw)
        assert request.client_cert_fingerprint == "abc123"

    def test_repr(self):
        """Request.__repr__ shows the raw URL."""
        raw = GeminiRequest.from_line("gemini://example.com/page")
        request = Request(raw)
        result = repr(request)
        assert "gemini://example.com/page" in result
        assert "Request(" in result
