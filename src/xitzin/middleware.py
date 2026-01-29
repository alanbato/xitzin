"""Middleware system for Xitzin.

Middleware functions can intercept requests before they reach handlers
and modify responses before they are sent to clients.
"""

from __future__ import annotations

import asyncio
import re
import time
from abc import ABC
from collections import OrderedDict
from functools import lru_cache
from inspect import iscoroutinefunction
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from nauyaca.protocol.response import GeminiResponse
from nauyaca.protocol.status import StatusCode

if TYPE_CHECKING:
    from .application import Xitzin
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

        logging_mw = LoggingMiddleware()

        @app.middleware
        async def logging(request, call_next):
            return await logging_mw(request, call_next)
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
        timing_mw = TimingMiddleware()

        @app.middleware
        async def timing(request, call_next):
            return await timing_mw(request, call_next)

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
        logging_mw = LoggingMiddleware()

        @app.middleware
        async def logging(request, call_next):
            return await logging_mw(request, call_next)
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
        rate_limit_mw = RateLimitMiddleware(max_requests=10, window_seconds=60)

        @app.middleware
        async def rate_limit(request, call_next):
            return await rate_limit_mw(request, call_next)
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
        # Use IP address when available for anonymous clients
        if request.remote_addr:
            return f"ip:{request.remote_addr}"
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


class UserSessionMiddleware(BaseMiddleware):
    """Middleware that loads and caches user data from certificate fingerprints.

    Stores the loaded user in request.state.user. Uses an LRU cache to avoid
    repeated database lookups for the same user across requests.

    Supports both sync and async user_loader functions. Sync loaders are
    executed in a thread pool to avoid blocking the event loop.

    Example with sync loader:
        from xitzin.middleware import UserSessionMiddleware

        def load_user(fingerprint: str) -> User | None:
            with Session(engine) as session:
                return session.exec(
                    select(User).where(User.fingerprint == fingerprint)
                ).first()

        user_mw = UserSessionMiddleware(load_user)

        @app.middleware
        async def user_session(request, call_next):
            return await user_mw(request, call_next)

    Example with async loader:
        async def load_user(fingerprint: str) -> User | None:
            async with async_session() as session:
                result = await session.execute(
                    select(User).where(User.fingerprint == fingerprint)
                )
                return result.scalar_one_or_none()

        user_mw = UserSessionMiddleware(load_user)
    """

    def __init__(
        self,
        user_loader: Callable[[str], Any] | Callable[[str], Awaitable[Any]],
        cache_size: int = 100,
    ) -> None:
        """Create user session middleware.

        Args:
            user_loader: Function that takes a fingerprint and returns a user
                object (or None if not found). Can be sync or async. Sync
                loaders are executed in a thread pool to avoid blocking.
            cache_size: Maximum number of users to cache. Defaults to 100.
        """
        self._user_loader = user_loader
        self._cache_size = cache_size
        self._is_async = iscoroutinefunction(user_loader)

        # For sync loaders, use lru_cache
        # For async loaders, use a simple OrderedDict-based LRU cache
        if self._is_async:
            self._async_cache: OrderedDict[str, Any] = OrderedDict()
            self._cache_hits = 0
            self._cache_misses = 0
        else:
            self._sync_cached_loader = lru_cache(maxsize=cache_size)(user_loader)

    async def _get_user_async(self, fingerprint: str) -> Any:
        """Get user with async loader and caching."""
        if fingerprint in self._async_cache:
            self._cache_hits += 1
            # Move to end (most recently used)
            self._async_cache.move_to_end(fingerprint)
            return self._async_cache[fingerprint]

        self._cache_misses += 1
        user = await self._user_loader(fingerprint)

        # Add to cache
        self._async_cache[fingerprint] = user
        self._async_cache.move_to_end(fingerprint)

        # Evict oldest if over capacity
        while len(self._async_cache) > self._cache_size:
            self._async_cache.popitem(last=False)

        return user

    async def _get_user_sync(self, fingerprint: str) -> Any:
        """Get user with sync loader, running in executor."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._sync_cached_loader, fingerprint)

    async def before_request(
        self, request: "Request"
    ) -> "Request | GeminiResponse | None":
        fingerprint = request.client_cert_fingerprint
        if fingerprint:
            if self._is_async:
                request.state.user = await self._get_user_async(fingerprint)
            else:
                request.state.user = await self._get_user_sync(fingerprint)
        else:
            request.state.user = None
        return None

    def clear_cache(self) -> None:
        """Clear all cached users.

        Call this after updating user data to ensure fresh lookups.

        Example:
            def update_user(user: User):
                with Session(engine) as session:
                    session.add(user)
                    session.commit()
                user_middleware.clear_cache()
        """
        if self._is_async:
            self._async_cache.clear()
            self._cache_hits = 0
            self._cache_misses = 0
        else:
            self._sync_cached_loader.cache_clear()

    def cache_info(self) -> Any:
        """Return cache statistics.

        Returns information about cache hits, misses, and size.

        Example:
            info = user_middleware.cache_info()
            print(f"Cache hits: {info.hits}, misses: {info.misses}")
        """
        if self._is_async:
            from collections import namedtuple

            CacheInfo = namedtuple(
                "CacheInfo", ["hits", "misses", "maxsize", "currsize"]
            )
            return CacheInfo(
                hits=self._cache_hits,
                misses=self._cache_misses,
                maxsize=self._cache_size,
                currsize=len(self._async_cache),
            )
        return self._sync_cached_loader.cache_info()


class VirtualHostMiddleware(BaseMiddleware):
    """Middleware for hostname-based virtual hosting.

    Routes requests to different Xitzin applications based on the hostname
    in the request URL. Supports exact hostname matches and wildcard patterns.

    Example:
        from xitzin import Xitzin
        from xitzin.middleware import VirtualHostMiddleware

        blog_app = Xitzin(title="Blog")
        api_app = Xitzin(title="API")
        main_app = Xitzin(title="Gateway")

        @blog_app.gemini("/")
        def blog_home(request):
            return "# Blog Home"

        @api_app.gemini("/")
        def api_home(request):
            return "# API Home"

        @main_app.gemini("/")
        def main_home(request):
            return "# Main Home"

        # Create virtual host middleware
        vhost_mw = VirtualHostMiddleware({
            "blog.example.com": blog_app,
            "*.api.example.com": api_app,
        }, default_app=main_app)

        @main_app.middleware
        async def vhost(request, call_next):
            return await vhost_mw(request, call_next)

        main_app.run()
    """

    def __init__(
        self,
        hosts: dict[str, "Xitzin"],
        *,
        default_app: "Xitzin | None" = None,
        fallback_status: int = 53,
        fallback_handler: (
            Callable[["Request"], Any] | Callable[["Request"], Awaitable[Any]] | None
        ) = None,
    ) -> None:
        """Create virtual host middleware.

        Args:
            hosts: Mapping of hostname patterns to Xitzin apps.
                Keys can be exact hostnames ("example.com") or wildcard patterns
                ("*.example.com"). Exact matches are checked first, then wildcards
                in definition order.
            default_app: Default app to use when no pattern matches.
                Takes precedence over fallback_status.
            fallback_status: Status code to return when no match and no default_app.
                Defaults to 53 (Proxy Request Refused). Common values:
                - 53: Proxy Request Refused (default)
                - 51: Not Found
                - 59: Bad Request
            fallback_handler: Custom handler function for unmatched hosts.
                Receives the request and must return a response. Takes precedence
                over both default_app and fallback_status. Can be sync or async.
        """
        self._default_app = default_app
        self._fallback_status = fallback_status
        self._fallback_handler = fallback_handler
        self._is_fallback_async = (
            iscoroutinefunction(fallback_handler) if fallback_handler else False
        )

        # Separate exact and wildcard patterns for efficiency
        self._exact_hosts: dict[str, "Xitzin"] = {}
        self._wildcard_patterns: list[tuple[re.Pattern[str], "Xitzin"]] = []

        for pattern, app in hosts.items():
            if pattern.startswith("*."):
                compiled = self._compile_wildcard_pattern(pattern)
                if compiled:
                    self._wildcard_patterns.append((compiled, app))
            else:
                self._exact_hosts[pattern.lower()] = app

    def _compile_wildcard_pattern(self, pattern: str) -> re.Pattern[str] | None:
        """Convert wildcard pattern to regex.

        Supports patterns like:
        - *.example.com -> matches "blog.example.com", "api.example.com"

        Args:
            pattern: Wildcard pattern string starting with "*.".

        Returns:
            Compiled regex pattern, or None if invalid.
        """
        if not pattern.startswith("*."):
            return None

        # Extract domain part after "*."
        domain = pattern[2:]
        # Escape special regex chars in domain
        domain_escaped = re.escape(domain)
        # Replace the wildcard with a pattern that matches any non-dot chars
        regex = f"^[^.]+\\.{domain_escaped}$"

        return re.compile(regex, re.IGNORECASE)

    def _match_hostname(self, hostname: str) -> "Xitzin | None":
        """Find the app for a given hostname.

        Checks exact matches first, then wildcard patterns in order.

        Args:
            hostname: The hostname from the request.

        Returns:
            Matching Xitzin app, or None if no match.
        """
        hostname_lower = hostname.lower()

        # Try exact match first
        if hostname_lower in self._exact_hosts:
            return self._exact_hosts[hostname_lower]

        # Try wildcard patterns
        for pattern, app in self._wildcard_patterns:
            if pattern.match(hostname_lower):
                return app

        return None

    async def before_request(
        self, request: "Request"
    ) -> "Request | GeminiResponse | None":
        """Route request to appropriate app based on hostname."""
        from .requests import TitanRequest
        from .responses import convert_response

        hostname = request.hostname

        # Find matching app
        app = self._match_hostname(hostname)

        # Handle no match
        if app is None:
            # Priority 1: Custom fallback handler
            if self._fallback_handler:
                if self._is_fallback_async:
                    result = await self._fallback_handler(request)
                else:
                    loop = asyncio.get_running_loop()
                    result = await loop.run_in_executor(
                        None, self._fallback_handler, request
                    )
                return convert_response(result, request)

            # Priority 2: Default app
            if self._default_app:
                app = self._default_app
            else:
                # Priority 3: Fallback status
                return GeminiResponse(
                    status=StatusCode(self._fallback_status),
                    meta="Host not configured for this server",
                )

        # If the matched app is the same as the request's app, return None
        # to continue processing through the normal route chain (avoid recursion)
        if request._app is not None and app is request._app:
            return None

        # Dispatch to matched app
        if isinstance(request, TitanRequest):
            response = await app._handle_titan_request(request._raw_request)
        else:
            response = await app._handle_request(request._raw_request)
        return response
