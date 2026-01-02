"""Tests for xitzin.middleware module."""

import asyncio
import time

import pytest
from nauyaca.protocol.request import GeminiRequest
from nauyaca.protocol.response import GeminiResponse
from nauyaca.protocol.status import StatusCode

from xitzin import Request, Xitzin
from xitzin.middleware import (
    BaseMiddleware,
    LoggingMiddleware,
    RateLimitMiddleware,
    TimingMiddleware,
)
from xitzin.testing import TestClient


class TestBaseMiddleware:
    """Tests for BaseMiddleware class."""

    def test_default_before_request_returns_none(self):
        """Default before_request returns None (continue)."""

        class CustomMiddleware(BaseMiddleware):
            pass

        mw = CustomMiddleware()
        raw = GeminiRequest.from_line("gemini://test/")
        request = Request(raw)

        result = asyncio.get_event_loop().run_until_complete(
            mw.before_request(request)
        )
        assert result is None

    def test_default_after_response_returns_response(self):
        """Default after_response returns response unchanged."""

        class CustomMiddleware(BaseMiddleware):
            pass

        mw = CustomMiddleware()
        raw = GeminiRequest.from_line("gemini://test/")
        request = Request(raw)
        response = GeminiResponse(status=20, meta="text/gemini", body="test")

        result = asyncio.get_event_loop().run_until_complete(
            mw.after_response(request, response)
        )
        assert result is response

    def test_call_invokes_before_and_after(self):
        """__call__ invokes before_request and after_response."""
        order = []

        class TrackingMiddleware(BaseMiddleware):
            async def before_request(self, request):
                order.append("before")
                return None

            async def after_response(self, request, response):
                order.append("after")
                return response

        mw = TrackingMiddleware()
        raw = GeminiRequest.from_line("gemini://test/")
        request = Request(raw)

        async def next_handler(req):
            order.append("handler")
            return GeminiResponse(status=20, meta="text/gemini", body="test")

        asyncio.get_event_loop().run_until_complete(mw(request, next_handler))

        assert order == ["before", "handler", "after"]

    def test_before_request_short_circuit(self):
        """Returning GeminiResponse from before_request short-circuits."""

        class ShortCircuitMiddleware(BaseMiddleware):
            async def before_request(self, request):
                return GeminiResponse(status=51, meta="Blocked")

        mw = ShortCircuitMiddleware()
        raw = GeminiRequest.from_line("gemini://test/")
        request = Request(raw)

        async def next_handler(req):
            pytest.fail("Handler should not be called")
            return GeminiResponse(status=20, meta="text/gemini")

        result = asyncio.get_event_loop().run_until_complete(
            mw(request, next_handler)
        )

        assert result.status == 51

    def test_before_request_modify_request(self):
        """Returning Request from before_request modifies request."""

        class ModifyMiddleware(BaseMiddleware):
            async def before_request(self, request):
                request.state.modified = True
                return request

        mw = ModifyMiddleware()
        raw = GeminiRequest.from_line("gemini://test/")
        request = Request(raw)

        async def next_handler(req):
            assert req.state.modified is True
            return GeminiResponse(status=20, meta="text/gemini")

        asyncio.get_event_loop().run_until_complete(mw(request, next_handler))

    def test_after_response_can_modify_response(self):
        """after_response can return modified response."""

        class ModifyResponseMiddleware(BaseMiddleware):
            async def after_response(self, request, response):
                return GeminiResponse(
                    status=response.status,
                    meta=response.meta,
                    body="Modified: " + (response.body or ""),
                )

        mw = ModifyResponseMiddleware()
        raw = GeminiRequest.from_line("gemini://test/")
        request = Request(raw)

        async def next_handler(req):
            return GeminiResponse(status=20, meta="text/gemini", body="Original")

        result = asyncio.get_event_loop().run_until_complete(
            mw(request, next_handler)
        )

        assert "Modified: Original" in result.body


class TestTimingMiddleware:
    """Tests for TimingMiddleware."""

    def test_sets_start_time(self):
        """TimingMiddleware sets request.state.start_time."""
        mw = TimingMiddleware()
        raw = GeminiRequest.from_line("gemini://test/")
        request = Request(raw)

        asyncio.get_event_loop().run_until_complete(mw.before_request(request))

        assert hasattr(request.state, "start_time")
        assert isinstance(request.state.start_time, float)

    def test_sets_elapsed_time(self):
        """TimingMiddleware sets request.state.elapsed_time."""
        mw = TimingMiddleware()
        raw = GeminiRequest.from_line("gemini://test/")
        request = Request(raw)
        response = GeminiResponse(status=20, meta="text/gemini")

        async def run():
            await mw.before_request(request)
            await asyncio.sleep(0.01)
            return await mw.after_response(request, response)

        asyncio.get_event_loop().run_until_complete(run())

        assert hasattr(request.state, "elapsed_time")
        assert request.state.elapsed_time >= 0.01

    def test_elapsed_time_is_positive(self):
        """Elapsed time is always positive."""
        mw = TimingMiddleware()
        raw = GeminiRequest.from_line("gemini://test/")
        request = Request(raw)
        response = GeminiResponse(status=20, meta="text/gemini")

        async def run():
            await mw.before_request(request)
            return await mw.after_response(request, response)

        asyncio.get_event_loop().run_until_complete(run())

        assert request.state.elapsed_time >= 0


class TestLoggingMiddleware:
    """Tests for LoggingMiddleware."""

    def test_default_logger_is_print(self):
        """Default logger is print."""
        mw = LoggingMiddleware()
        assert mw._log is print

    def test_custom_logger(self):
        """Custom logger can be provided."""
        logs = []
        mw = LoggingMiddleware(logger=logs.append)

        raw = GeminiRequest.from_line("gemini://test/page")
        request = Request(raw)

        asyncio.get_event_loop().run_until_complete(mw.before_request(request))

        assert len(logs) == 1
        assert "Request: /page" in logs[0]

    def test_logs_request_path(self):
        """Logs the request path."""
        logs = []
        mw = LoggingMiddleware(logger=logs.append)

        raw = GeminiRequest.from_line("gemini://test/users/alice")
        request = Request(raw)

        asyncio.get_event_loop().run_until_complete(mw.before_request(request))

        assert "/users/alice" in logs[0]

    def test_logs_cert_fingerprint(self):
        """Logs certificate fingerprint if present."""
        logs = []
        mw = LoggingMiddleware(logger=logs.append)

        raw = GeminiRequest.from_line("gemini://test/")
        raw.client_cert_fingerprint = "abc123def456"
        request = Request(raw)

        asyncio.get_event_loop().run_until_complete(mw.before_request(request))

        assert "cert:abc123de" in logs[0]

    def test_logs_without_cert(self):
        """Logs correctly without certificate."""
        logs = []
        mw = LoggingMiddleware(logger=logs.append)

        raw = GeminiRequest.from_line("gemini://test/path")
        request = Request(raw)

        asyncio.get_event_loop().run_until_complete(mw.before_request(request))

        assert "cert:" not in logs[0]
        assert "/path" in logs[0]

    def test_logs_response_status(self):
        """Logs the response status and meta."""
        logs = []
        mw = LoggingMiddleware(logger=logs.append)

        raw = GeminiRequest.from_line("gemini://test/")
        request = Request(raw)
        response = GeminiResponse(status=20, meta="text/gemini")

        asyncio.get_event_loop().run_until_complete(
            mw.after_response(request, response)
        )

        assert "Response: 20" in logs[0]
        assert "text/gemini" in logs[0]

    def test_logs_error_response(self):
        """Logs error response status."""
        logs = []
        mw = LoggingMiddleware(logger=logs.append)

        raw = GeminiRequest.from_line("gemini://test/")
        request = Request(raw)
        response = GeminiResponse(status=51, meta="Not found")

        asyncio.get_event_loop().run_until_complete(
            mw.after_response(request, response)
        )

        assert "Response: 51" in logs[0]
        assert "Not found" in logs[0]


class TestRateLimitMiddleware:
    """Tests for RateLimitMiddleware."""

    def test_default_values(self):
        """Default rate limit values."""
        mw = RateLimitMiddleware()
        assert mw.max_requests == 10
        assert mw.window_seconds == 60.0
        assert mw.retry_after == 30

    def test_custom_values(self):
        """Custom rate limit values."""
        mw = RateLimitMiddleware(max_requests=5, window_seconds=30, retry_after=10)
        assert mw.max_requests == 5
        assert mw.window_seconds == 30
        assert mw.retry_after == 10

    def test_get_client_id_with_cert(self):
        """Client ID from certificate fingerprint."""
        mw = RateLimitMiddleware()
        raw = GeminiRequest.from_line("gemini://test/")
        raw.client_cert_fingerprint = "abc123"
        request = Request(raw)

        client_id = mw._get_client_id(request)
        assert client_id == "cert:abc123"

    def test_get_client_id_without_cert(self):
        """Client ID fallback when no certificate."""
        mw = RateLimitMiddleware()
        raw = GeminiRequest.from_line("gemini://test/")
        request = Request(raw)

        client_id = mw._get_client_id(request)
        assert client_id == "unknown"

    def test_allows_requests_under_limit(self):
        """Requests under limit are allowed."""
        mw = RateLimitMiddleware(max_requests=3, window_seconds=60)
        raw = GeminiRequest.from_line("gemini://test/")
        raw.client_cert_fingerprint = "test_client_under"
        request = Request(raw)

        for _ in range(3):
            result = asyncio.get_event_loop().run_until_complete(
                mw.before_request(request)
            )
            assert result is None  # Not rate limited

    def test_blocks_requests_over_limit(self):
        """Requests over limit are blocked."""
        mw = RateLimitMiddleware(max_requests=2, window_seconds=60)
        raw = GeminiRequest.from_line("gemini://test/")
        raw.client_cert_fingerprint = "test_client_over"
        request = Request(raw)

        # First two should pass
        asyncio.get_event_loop().run_until_complete(mw.before_request(request))
        asyncio.get_event_loop().run_until_complete(mw.before_request(request))

        # Third should be blocked
        result = asyncio.get_event_loop().run_until_complete(
            mw.before_request(request)
        )

        assert isinstance(result, GeminiResponse)
        assert result.status == StatusCode.SLOW_DOWN

    def test_retry_after_in_response(self):
        """Rate limit response includes retry_after."""
        mw = RateLimitMiddleware(max_requests=1, window_seconds=60, retry_after=15)
        raw = GeminiRequest.from_line("gemini://test/")
        raw.client_cert_fingerprint = "test_client_retry"
        request = Request(raw)

        asyncio.get_event_loop().run_until_complete(mw.before_request(request))
        result = asyncio.get_event_loop().run_until_complete(
            mw.before_request(request)
        )

        assert result.meta == "15"

    def test_different_clients_tracked_separately(self):
        """Different clients have separate rate limits."""
        mw = RateLimitMiddleware(max_requests=1, window_seconds=60)

        raw1 = GeminiRequest.from_line("gemini://test/")
        raw1.client_cert_fingerprint = "client_a"
        request1 = Request(raw1)

        raw2 = GeminiRequest.from_line("gemini://test/")
        raw2.client_cert_fingerprint = "client_b"
        request2 = Request(raw2)

        # Client A uses their one request
        result1 = asyncio.get_event_loop().run_until_complete(
            mw.before_request(request1)
        )
        assert result1 is None

        # Client B should still be allowed
        result2 = asyncio.get_event_loop().run_until_complete(
            mw.before_request(request2)
        )
        assert result2 is None


class TestMiddlewareIntegration:
    """Integration tests for middleware with the app."""

    def test_middleware_class_integration(self):
        """Middleware class integrates with app via wrapper."""
        app = Xitzin()
        logs = []
        logging_mw = LoggingMiddleware(logger=logs.append)

        # Wrap the class-based middleware properly
        @app.middleware
        async def wrapped_logging(request, call_next):
            return await logging_mw(request, call_next)

        @app.gemini("/")
        def home(request: Request):
            return "# Home"

        client = TestClient(app)
        response = client.get("/")

        assert response.is_success
        assert len(logs) == 2  # before and after

    def test_timing_middleware_integration(self):
        """TimingMiddleware works with app."""
        app = Xitzin()
        timing_mw = TimingMiddleware()

        # Capture the request object to check elapsed_time after response
        captured_request = []

        @app.middleware
        async def wrapped_timing(request, call_next):
            captured_request.append(request)
            return await timing_mw(request, call_next)

        @app.gemini("/")
        def home(request: Request):
            return "# Home"

        client = TestClient(app)
        client.get("/")

        # Check that timing was captured
        assert len(captured_request) == 1
        assert hasattr(captured_request[0].state, "elapsed_time")
        assert captured_request[0].state.elapsed_time >= 0

    def test_multiple_middleware_classes(self):
        """Multiple middleware classes work together."""
        app = Xitzin()
        logs = []
        timing_mw = TimingMiddleware()
        logging_mw = LoggingMiddleware(logger=logs.append)

        @app.middleware
        async def wrapped_timing(request, call_next):
            return await timing_mw(request, call_next)

        @app.middleware
        async def wrapped_logging(request, call_next):
            return await logging_mw(request, call_next)

        @app.gemini("/")
        def home(request: Request):
            return "# Home"

        client = TestClient(app)
        response = client.get("/")

        assert response.is_success
        assert len(logs) >= 2
