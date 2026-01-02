"""Tests for xitzin.responses module."""

import pytest
from nauyaca.protocol.request import GeminiRequest
from nauyaca.protocol.response import GeminiResponse
from nauyaca.protocol.status import StatusCode

from xitzin import Request
from xitzin.responses import Input, Redirect, Response, convert_response


class TestResponse:
    """Tests for the Response dataclass."""

    def test_default_mime_type(self):
        """Response uses text/gemini by default."""
        resp = Response("# Hello")
        assert resp.mime_type == "text/gemini"

    def test_custom_mime_type(self):
        """Response can have custom MIME type."""
        resp = Response("plain text", mime_type="text/plain")
        assert resp.mime_type == "text/plain"

    def test_body_stored(self):
        """Response stores body."""
        resp = Response("# Hello World")
        assert resp.body == "# Hello World"

    def test_to_gemini_response(self):
        """Response converts to GeminiResponse correctly."""
        resp = Response("# Hello", mime_type="text/gemini")
        gemini_resp = resp.to_gemini_response()

        assert gemini_resp.status == StatusCode.SUCCESS
        assert gemini_resp.meta == "text/gemini"
        assert gemini_resp.body == "# Hello"

    def test_to_gemini_response_custom_mime(self):
        """Response with custom MIME type converts correctly."""
        resp = Response("data", mime_type="application/json")
        gemini_resp = resp.to_gemini_response()

        assert gemini_resp.meta == "application/json"


class TestInput:
    """Tests for the Input dataclass."""

    def test_default_not_sensitive(self):
        """Input is not sensitive by default."""
        inp = Input("Enter name:")
        assert inp.sensitive is False

    def test_sensitive_true(self):
        """Input can be set to sensitive."""
        inp = Input("Enter password:", sensitive=True)
        assert inp.sensitive is True

    def test_prompt_stored(self):
        """Input stores prompt."""
        inp = Input("What is your query?")
        assert inp.prompt == "What is your query?"

    def test_to_gemini_response_status_10(self):
        """Non-sensitive Input produces status 10."""
        inp = Input("Enter query:")
        gemini_resp = inp.to_gemini_response()

        assert gemini_resp.status == StatusCode.INPUT
        assert gemini_resp.meta == "Enter query:"

    def test_to_gemini_response_sensitive_status_11(self):
        """Sensitive Input produces status 11."""
        inp = Input("Enter password:", sensitive=True)
        gemini_resp = inp.to_gemini_response()

        assert gemini_resp.status == StatusCode.SENSITIVE_INPUT
        assert gemini_resp.meta == "Enter password:"


class TestRedirect:
    """Tests for the Redirect dataclass."""

    def test_default_temporary(self):
        """Redirect is temporary by default."""
        redir = Redirect("/new-page")
        assert redir.permanent is False

    def test_permanent_true(self):
        """Redirect can be set to permanent."""
        redir = Redirect("/moved", permanent=True)
        assert redir.permanent is True

    def test_url_stored(self):
        """Redirect stores URL."""
        redir = Redirect("/new-location")
        assert redir.url == "/new-location"

    def test_to_gemini_response_temporary(self):
        """Temporary Redirect produces status 30."""
        redir = Redirect("/new-page")
        gemini_resp = redir.to_gemini_response()

        assert gemini_resp.status == StatusCode.REDIRECT_TEMPORARY
        assert gemini_resp.meta == "/new-page"

    def test_to_gemini_response_permanent(self):
        """Permanent Redirect produces status 31."""
        redir = Redirect("/moved", permanent=True)
        gemini_resp = redir.to_gemini_response()

        assert gemini_resp.status == StatusCode.REDIRECT_PERMANENT
        assert gemini_resp.meta == "/moved"


class TestConvertResponse:
    """Tests for the convert_response function."""

    @pytest.fixture
    def mock_request(self):
        """Create a mock request for testing."""
        raw = GeminiRequest.from_line("gemini://testserver/page")
        return Request(raw)

    def test_convert_gemini_response_passthrough(self, mock_request):
        """GeminiResponse is returned as-is."""
        original = GeminiResponse(status=20, meta="text/gemini", body="test")
        result = convert_response(original, mock_request)
        assert result is original

    def test_convert_string_to_success(self, mock_request):
        """String converts to success response."""
        result = convert_response("# Hello", mock_request)

        assert result.status == StatusCode.SUCCESS
        assert result.meta == "text/gemini"
        assert result.body == "# Hello"

    def test_convert_response_object(self, mock_request):
        """Response object converts correctly."""
        resp = Response("body", mime_type="text/plain")
        result = convert_response(resp, mock_request)

        assert result.status == StatusCode.SUCCESS
        assert result.meta == "text/plain"
        assert result.body == "body"

    def test_convert_input_object(self, mock_request):
        """Input object converts correctly."""
        inp = Input("Prompt?")
        result = convert_response(inp, mock_request)

        assert result.status == StatusCode.INPUT
        assert result.meta == "Prompt?"

    def test_convert_redirect_object(self, mock_request):
        """Redirect object converts correctly."""
        redir = Redirect("/other")
        result = convert_response(redir, mock_request)

        assert result.status == StatusCode.REDIRECT_TEMPORARY
        assert result.meta == "/other"

    def test_convert_tuple_two_elements(self, mock_request):
        """Tuple (body, status) converts correctly."""
        result = convert_response(("body", StatusCode.SUCCESS), mock_request)

        assert result.status == StatusCode.SUCCESS
        assert result.meta == "text/gemini"
        assert result.body == "body"

    def test_convert_tuple_three_elements(self, mock_request):
        """Tuple (body, status, meta) converts correctly."""
        result = convert_response(
            ("body", StatusCode.SUCCESS, "text/plain"), mock_request
        )

        assert result.status == StatusCode.SUCCESS
        assert result.meta == "text/plain"
        assert result.body == "body"

    def test_convert_tuple_error_status_no_body(self, mock_request):
        """Error status tuple has no body."""
        result = convert_response(
            ("error", StatusCode.NOT_FOUND, "Not found"), mock_request
        )

        assert result.status == StatusCode.NOT_FOUND
        assert result.meta == "Not found"
        assert result.body is None

    def test_convert_tuple_non_success_no_body(self, mock_request):
        """Non-2x status has no body."""
        result = convert_response(
            ("ignored", StatusCode.REDIRECT_TEMPORARY, "/other"), mock_request
        )

        assert result.status == StatusCode.REDIRECT_TEMPORARY
        assert result.body is None

    def test_convert_tuple_wrong_length_raises(self, mock_request):
        """Tuple with wrong length raises TypeError."""
        with pytest.raises(TypeError, match="Tuple must have 2 or 3 elements"):
            convert_response(("a", "b", "c", "d"), mock_request)

    def test_convert_tuple_single_element_raises(self, mock_request):
        """Tuple with single element raises TypeError."""
        with pytest.raises(TypeError, match="Tuple must have 2 or 3 elements"):
            convert_response(("only_one",), mock_request)

    def test_convert_none_to_empty_success(self, mock_request):
        """None converts to empty success response."""
        result = convert_response(None, mock_request)

        assert result.status == StatusCode.SUCCESS
        assert result.meta == "text/gemini"
        assert result.body == ""

    def test_convert_unknown_type_raises(self, mock_request):
        """Unknown type raises TypeError."""
        with pytest.raises(TypeError, match="Cannot convert"):
            convert_response(12345, mock_request)

    def test_convert_list_raises(self, mock_request):
        """List raises TypeError."""
        with pytest.raises(TypeError, match="Cannot convert"):
            convert_response([1, 2, 3], mock_request)

    def test_convert_string_without_request(self):
        """String converts without request (url is None)."""
        result = convert_response("# Hello", None)

        assert result.status == StatusCode.SUCCESS
        assert result.url is None

    def test_url_tracking(self, mock_request):
        """URL is tracked from request."""
        result = convert_response("# Hello", mock_request)
        assert result.url is not None
        assert "testserver" in result.url
