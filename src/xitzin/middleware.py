"""Middleware system for Xitzin.

Middleware functions can intercept requests before they reach handlers
and modify responses before they are sent to clients.
"""

from __future__ import annotations

import time
from abc import ABC
from typing import TYPE_CHECKING, Awaitable, Callable

from nauyaca.protocol.response import GeminiResponse
from nauyaca.protocol.status import StatusCode

if TYPE_CHECKING:
    from .requests import Request

# Type alias for middleware call_next function
CallNext = Callable[["Request"], Awaitable[GeminiResponse]]


class BaseMiddleware(ABC):
    """Base class for class-based middleware.

    Subclass this and implement before_request and/or after_response
    for a cleaner interface than writing raw middleware functions.

    Example:
        class LoggingMiddleware(BaseMiddleware):
            async def before_request(
                self, request: Request
            ) -> Request | GeminiResponse | None:
                print(f"Request: {request.path}")
                return None  # Continue processing

            async def after_response(
                self, request: Request, response: GeminiResponse
            ) -> GeminiResponse:
                print(f"Response: {response.status}")
                return response

        app.add_middleware(LoggingMiddleware())
    """

    async def before_request(
        self, request: "Request"
    ) -> "Request | GeminiResponse | None":
        """Called before the handler.

        Args:
            request: The incoming request.

        Returns:
            - None: Continue to next middleware/handler
            - Request: Use this modified request
            - GeminiResponse: Short-circuit and return this response immediately
        """
        return None

    async def after_response(
        self, request: "Request", response: GeminiResponse
    ) -> GeminiResponse:
        """Called after the handler.

        Args:
            request: The original request.
            response: The response from the handler.

        Returns:
            The response to send (can be modified).
        """
        return response

    async def __call__(self, request: "Request", call_next: CallNext) -> GeminiResponse:
        """Process the request through this middleware.

        This implements the middleware protocol by calling before_request,
        then call_next, then after_response.
        """
        # Before request
        result = await self.before_request(request)
        if isinstance(result, GeminiResponse):
            return result  # Short-circuit
        if result is not None:
            request = result  # Use modified request

        # Call next handler
        response = await call_next(request)

        # After response
        return await self.after_response(request, response)


class TimingMiddleware(BaseMiddleware):
    """Middleware that tracks request processing time.

    Stores the elapsed time in request.state.elapsed_time.

    Example:
        app.add_middleware(TimingMiddleware())

        @app.gemini("/")
        def home(request: Request):
            elapsed = getattr(request.state, 'elapsed_time', 0)
            return f"# Response generated in {elapsed:.3f}s"
    """

    async def before_request(
        self, request: "Request"
    ) -> "Request | GeminiResponse | None":
        request.state.start_time = time.perf_counter()
        return None

    async def after_response(
        self, request: "Request", response: GeminiResponse
    ) -> GeminiResponse:
        elapsed = time.perf_counter() - request.state.start_time
        request.state.elapsed_time = elapsed
        return response


class LoggingMiddleware(BaseMiddleware):
    """Middleware that logs requests and responses.

    Example:
        app.add_middleware(LoggingMiddleware())
    """

    def __init__(self, logger: Callable[[str], None] | None = None) -> None:
        """Create logging middleware.

        Args:
            logger: Custom logging function. Defaults to print.
        """
        self._log = logger or print

    async def before_request(
        self, request: "Request"
    ) -> "Request | GeminiResponse | None":
        cert_info = ""
        if request.client_cert_fingerprint:
            cert_info = f" [cert:{request.client_cert_fingerprint[:8]}]"
        self._log(f"[Xitzin] Request: {request.path}{cert_info}")
        return None

    async def after_response(
        self, request: "Request", response: GeminiResponse
    ) -> GeminiResponse:
        self._log(f"[Xitzin] Response: {response.status} {response.meta}")
        return response


class RateLimitMiddleware(BaseMiddleware):
    """Simple in-memory rate limiting middleware.

    Limits requests per client based on certificate fingerprint or IP.

    Example:
        app.add_middleware(RateLimitMiddleware(max_requests=10, window_seconds=60))
    """

    def __init__(
        self,
        max_requests: int = 10,
        window_seconds: float = 60.0,
        retry_after: int = 30,
    ) -> None:
        """Create rate limit middleware.

        Args:
            max_requests: Maximum requests allowed per window.
            window_seconds: Time window in seconds.
            retry_after: Seconds to tell client to wait.
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.retry_after = retry_after
        self._requests: dict[str, list[float]] = {}

    def _get_client_id(self, request: "Request") -> str:
        """Get a unique identifier for the client."""
        if request.client_cert_fingerprint:
            return f"cert:{request.client_cert_fingerprint}"
        # Fall back to a placeholder (in production, use IP from transport)
        return "unknown"

    def _is_rate_limited(self, client_id: str) -> bool:
        """Check if a client is rate limited."""
        now = time.time()
        cutoff = now - self.window_seconds

        # Get request timestamps for this client
        timestamps = self._requests.get(client_id, [])

        # Filter to only recent requests
        recent = [t for t in timestamps if t > cutoff]
        self._requests[client_id] = recent

        # Check if over limit
        if len(recent) >= self.max_requests:
            return True

        # Record this request
        recent.append(now)
        return False

    async def before_request(
        self, request: "Request"
    ) -> "Request | GeminiResponse | None":
        client_id = self._get_client_id(request)

        if self._is_rate_limited(client_id):
            return GeminiResponse(
                status=StatusCode.SLOW_DOWN,
                meta=str(self.retry_after),
            )

        return None
