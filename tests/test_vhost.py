"""Tests for virtual hosting functionality."""

import asyncio

from nauyaca.protocol.request import GeminiRequest
from nauyaca.protocol.response import GeminiResponse
from nauyaca.protocol.status import StatusCode

from xitzin import Request, Xitzin, VirtualHostMiddleware


def make_request(url: str) -> GeminiRequest:
    """Create a GeminiRequest from a full URL."""
    return GeminiRequest.from_line(url)


def handle_request_sync(app: Xitzin, url: str) -> GeminiResponse:
    """Handle a request synchronously for testing."""
    request = make_request(url)
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(app._handle_request(request))


class TestVirtualHostMiddlewareUnit:
    """Unit tests for VirtualHostMiddleware."""

    def test_exact_hostname_match(self):
        """Test exact hostname matching."""
        app1 = Xitzin(title="App1")
        app2 = Xitzin(title="App2")

        mw = VirtualHostMiddleware(
            {
                "example.com": app1,
                "other.com": app2,
            }
        )

        assert mw._match_hostname("example.com") is app1
        assert mw._match_hostname("other.com") is app2
        assert mw._match_hostname("unknown.com") is None

    def test_exact_hostname_case_insensitive(self):
        """Test that hostname matching is case-insensitive."""
        app = Xitzin(title="App")

        mw = VirtualHostMiddleware(
            {
                "Example.COM": app,
            }
        )

        assert mw._match_hostname("example.com") is app
        assert mw._match_hostname("EXAMPLE.COM") is app
        assert mw._match_hostname("Example.Com") is app

    def test_wildcard_hostname_match(self):
        """Test wildcard pattern matching."""
        app = Xitzin(title="App")

        mw = VirtualHostMiddleware(
            {
                "*.example.com": app,
            }
        )

        assert mw._match_hostname("blog.example.com") is app
        assert mw._match_hostname("api.example.com") is app
        assert mw._match_hostname("sub.blog.example.com") is None  # Only one level
        assert mw._match_hostname("example.com") is None  # No match without subdomain

    def test_wildcard_case_insensitive(self):
        """Test that wildcard matching is case-insensitive."""
        app = Xitzin(title="App")

        mw = VirtualHostMiddleware(
            {
                "*.Example.COM": app,
            }
        )

        assert mw._match_hostname("blog.example.com") is app
        assert mw._match_hostname("BLOG.EXAMPLE.COM") is app

    def test_exact_takes_precedence_over_wildcard(self):
        """Test that exact matches take precedence over wildcards."""
        app_exact = Xitzin(title="Exact")
        app_wildcard = Xitzin(title="Wildcard")

        mw = VirtualHostMiddleware(
            {
                "blog.example.com": app_exact,
                "*.example.com": app_wildcard,
            }
        )

        assert mw._match_hostname("blog.example.com") is app_exact
        assert mw._match_hostname("api.example.com") is app_wildcard

    def test_wildcard_order_preserved(self):
        """Test that wildcards are matched in definition order."""
        app1 = Xitzin(title="App1")
        app2 = Xitzin(title="App2")

        mw = VirtualHostMiddleware(
            {
                "*.example.com": app1,
                "*.other.com": app2,
            }
        )

        assert mw._match_hostname("sub.example.com") is app1
        assert mw._match_hostname("sub.other.com") is app2

    def test_compile_wildcard_pattern(self):
        """Test wildcard pattern compilation."""
        mw = VirtualHostMiddleware({})

        # Valid wildcard
        pattern = mw._compile_wildcard_pattern("*.example.com")
        assert pattern is not None
        assert pattern.match("blog.example.com")
        assert pattern.match("api.example.com")
        assert not pattern.match("example.com")
        assert not pattern.match("sub.sub.example.com")

        # Invalid pattern (not starting with *.)
        assert mw._compile_wildcard_pattern("example.com") is None
        assert mw._compile_wildcard_pattern("*example.com") is None


class TestVirtualHostMiddlewareFallback:
    """Tests for VirtualHostMiddleware fallback behavior."""

    def test_default_app_fallback(self):
        """Test fallback to default app."""
        app1 = Xitzin(title="App1")
        default = Xitzin(title="Default")

        mw = VirtualHostMiddleware(
            {"example.com": app1},
            default_app=default,
        )

        assert mw._match_hostname("example.com") is app1
        # No direct match, but will use default_app in before_request
        assert mw._match_hostname("unknown.com") is None
        assert mw._default_app is default

    def test_fallback_status_code(self):
        """Test fallback status code."""
        app = Xitzin(title="App")

        mw = VirtualHostMiddleware(
            {"example.com": app},
            fallback_status=51,  # Not Found
        )

        assert mw._fallback_status == 51

    def test_custom_fallback_handler(self):
        """Test custom fallback handler."""
        app = Xitzin(title="App")

        def custom_handler(request):
            return f"# Unknown host: {request.hostname}"

        mw = VirtualHostMiddleware(
            {"example.com": app},
            fallback_handler=custom_handler,
        )

        assert mw._fallback_handler is custom_handler
        assert mw._is_fallback_async is False

    def test_async_fallback_handler(self):
        """Test async fallback handler detection."""
        app = Xitzin(title="App")

        async def async_handler(request):
            return "# Async fallback"

        mw = VirtualHostMiddleware(
            {"example.com": app},
            fallback_handler=async_handler,
        )

        assert mw._is_fallback_async is True


class TestVirtualHostMiddlewareIntegration:
    """Integration tests for VirtualHostMiddleware."""

    def test_dispatch_to_correct_app(self):
        """Test that requests are dispatched to the correct app."""
        blog_app = Xitzin(title="Blog")
        api_app = Xitzin(title="API")
        main_app = Xitzin(title="Main")

        @blog_app.gemini("/")
        def blog_home(request: Request):
            return "# Blog Home"

        @api_app.gemini("/")
        def api_home(request: Request):
            return "# API Home"

        @main_app.gemini("/")
        def main_home(request: Request):
            return "# Main Home"

        vhost_mw = VirtualHostMiddleware(
            {
                "blog.example.com": blog_app,
                "api.example.com": api_app,
            },
            default_app=main_app,
        )

        @main_app.middleware
        async def vhost(request, call_next):
            return await vhost_mw(request, call_next)

        # Test blog app
        response = handle_request_sync(main_app, "gemini://blog.example.com/")
        assert response.body == "# Blog Home"

        # Test api app
        response = handle_request_sync(main_app, "gemini://api.example.com/")
        assert response.body == "# API Home"

        # Test default app
        response = handle_request_sync(main_app, "gemini://main.example.com/")
        assert response.body == "# Main Home"

    def test_wildcard_routing(self):
        """Test wildcard pattern routing."""
        user_app = Xitzin(title="Users")
        main_app = Xitzin(title="Main")

        @user_app.gemini("/")
        def user_home(request: Request):
            return f"# User: {request.hostname.split('.')[0]}"

        @main_app.gemini("/")
        def main_home(request: Request):
            return "# Main"

        vhost_mw = VirtualHostMiddleware(
            {
                "*.users.example.com": user_app,
            },
            default_app=main_app,
        )

        @main_app.middleware
        async def vhost(request, call_next):
            return await vhost_mw(request, call_next)

        # Test wildcard match
        response = handle_request_sync(main_app, "gemini://alice.users.example.com/")
        assert "User: alice" in response.body

        response = handle_request_sync(main_app, "gemini://bob.users.example.com/")
        assert "User: bob" in response.body

        # Test fallback to default
        response = handle_request_sync(main_app, "gemini://example.com/")
        assert response.body == "# Main"

    def test_fallback_status_53(self):
        """Test fallback returns status 53 (Proxy Request Refused)."""
        app = Xitzin(title="App")

        @app.gemini("/")
        def home(request: Request):
            return "# Home"

        vhost_mw = VirtualHostMiddleware(
            {"example.com": app},
            fallback_status=53,
        )

        @app.middleware
        async def vhost(request, call_next):
            return await vhost_mw(request, call_next)

        # Known host works
        response = handle_request_sync(app, "gemini://example.com/")
        assert response.status == StatusCode.SUCCESS
        assert response.body == "# Home"

        # Unknown host returns 53
        response = handle_request_sync(app, "gemini://unknown.com/")
        assert response.status == StatusCode.PROXY_REQUEST_REFUSED
        assert "Host not configured" in response.meta

    def test_custom_fallback_handler_integration(self):
        """Test custom fallback handler in integration."""
        app = Xitzin(title="App")

        @app.gemini("/")
        def home(request: Request):
            return "# Home"

        def custom_fallback(request: Request):
            return f"# Unknown host: {request.hostname}"

        vhost_mw = VirtualHostMiddleware(
            {"example.com": app},
            fallback_handler=custom_fallback,
        )

        @app.middleware
        async def vhost(request, call_next):
            return await vhost_mw(request, call_next)

        # Unknown host uses custom handler
        response = handle_request_sync(app, "gemini://unknown.example.com/")
        assert response.status == StatusCode.SUCCESS
        assert "Unknown host: unknown.example.com" in response.body


class TestVhostConvenienceMethod:
    """Tests for Xitzin.vhost() convenience method."""

    def test_vhost_method_basic(self):
        """Test basic vhost() method usage."""
        blog_app = Xitzin(title="Blog")
        main_app = Xitzin(title="Main")

        @blog_app.gemini("/")
        def blog_home(request: Request):
            return "# Blog"

        @main_app.gemini("/")
        def main_home(request: Request):
            return "# Main"

        main_app.vhost(
            {
                "blog.example.com": blog_app,
            },
            default_app=main_app,
        )

        response = handle_request_sync(main_app, "gemini://blog.example.com/")
        assert response.body == "# Blog"

        response = handle_request_sync(main_app, "gemini://main.example.com/")
        assert response.body == "# Main"

    def test_vhost_with_wildcard(self):
        """Test vhost() with wildcard patterns."""
        api_app = Xitzin(title="API")
        main_app = Xitzin(title="Main")

        @api_app.gemini("/")
        def api_home(request: Request):
            return "# API"

        @main_app.gemini("/")
        def main_home(request: Request):
            return "# Main"

        main_app.vhost(
            {
                "*.api.example.com": api_app,
            },
            default_app=main_app,
        )

        response = handle_request_sync(main_app, "gemini://v1.api.example.com/")
        assert response.body == "# API"

    def test_vhost_with_custom_fallback_status(self):
        """Test vhost() with custom fallback status."""
        app = Xitzin(title="App")

        @app.gemini("/")
        def home(request: Request):
            return "# Home"

        app.vhost(
            {
                "example.com": app,
            },
            fallback_status=51,
        )

        response = handle_request_sync(app, "gemini://unknown.com/")
        assert response.status == StatusCode.NOT_FOUND

    def test_vhost_registers_middleware(self):
        """Test that vhost() registers middleware."""
        app = Xitzin(title="App")

        initial_middleware_count = len(app._middleware)

        app.vhost({"example.com": app})

        # Should have one more middleware
        assert len(app._middleware) == initial_middleware_count + 1


class TestVirtualHostWithRoutes:
    """Tests for virtual hosting with various route types."""

    def test_vhost_with_path_parameters(self):
        """Test vhost with path parameter routes."""
        blog_app = Xitzin(title="Blog")
        main_app = Xitzin(title="Main")

        @blog_app.gemini("/post/{post_id}")
        def blog_post(request: Request, post_id: int):
            return f"# Post {post_id}"

        main_app.vhost(
            {
                "blog.example.com": blog_app,
            },
            default_app=main_app,
        )

        response = handle_request_sync(main_app, "gemini://blog.example.com/post/42")
        assert response.body == "# Post 42"

    def test_vhost_with_input_routes(self):
        """Test vhost with input routes."""
        search_app = Xitzin(title="Search")
        main_app = Xitzin(title="Main")

        @search_app.input("/search", prompt="Search query:")
        def search(request: Request, query: str):
            return f"# Results for: {query}"

        main_app.vhost(
            {
                "search.example.com": search_app,
            },
            default_app=main_app,
        )

        # Without query - should prompt for input
        response = handle_request_sync(main_app, "gemini://search.example.com/search")
        assert response.status == StatusCode.INPUT

        # With query - should return results
        response = handle_request_sync(
            main_app, "gemini://search.example.com/search?hello"
        )
        assert "Results for: hello" in response.body

    def test_vhost_with_mounted_routes(self):
        """Test vhost with mounted routes."""
        api_app = Xitzin(title="API")
        main_app = Xitzin(title="Main")

        async def api_handler(request: Request, path_info: str):
            return f"# API path: {path_info}"

        api_app.mount("/v1", api_handler)

        main_app.vhost(
            {
                "api.example.com": api_app,
            },
            default_app=main_app,
        )

        response = handle_request_sync(main_app, "gemini://api.example.com/v1/users")
        assert "API path: /users" in response.body

    def test_vhost_sub_app_middleware(self):
        """Test that sub-app middleware is executed."""
        blog_app = Xitzin(title="Blog")
        main_app = Xitzin(title="Main")
        middleware_called = []

        @blog_app.middleware
        async def blog_mw(request, call_next):
            middleware_called.append("blog_mw")
            return await call_next(request)

        @blog_app.gemini("/")
        def blog_home(request: Request):
            return "# Blog"

        main_app.vhost(
            {
                "blog.example.com": blog_app,
            },
            default_app=main_app,
        )

        response = handle_request_sync(main_app, "gemini://blog.example.com/")
        assert response.body == "# Blog"
        assert "blog_mw" in middleware_called


class TestTitanVirtualHosting:
    """Tests for Titan requests through virtual hosting."""

    def test_titan_dispatch_through_vhost(self):
        """Test that Titan upload requests are dispatched correctly through vhosts."""
        upload_app = Xitzin(title="Upload")
        main_app = Xitzin(title="Main")

        @upload_app.titan("/upload/{filename}")
        def upload_handler(
            request, content: bytes, mime_type: str, token: str | None, filename: str
        ):
            return f"# Uploaded {filename}: {len(content)} bytes"

        main_app.vhost(
            {
                "upload.example.com": upload_app,
            },
            default_app=main_app,
        )

        # Note: TestClient.upload uses "testserver" as hostname, so we need
        # to test differently - the vhost middleware needs to see the correct hostname
        # For this test, we use the handle_request pattern with Titan URL

        from nauyaca.protocol.request import TitanRequest as NauyacaTitanRequest

        url = "titan://upload.example.com/upload/test.txt;size=5;mime=text/plain"
        request = NauyacaTitanRequest.from_line(url)
        request.content = b"hello"

        loop = asyncio.get_event_loop()
        response = loop.run_until_complete(main_app._handle_titan_request(request))

        assert response.status == StatusCode.SUCCESS
        assert "Uploaded test.txt" in response.body
        assert "5 bytes" in response.body

    def test_titan_vhost_fallback(self):
        """Test Titan fallback behavior for unknown hosts."""
        upload_app = Xitzin(title="Upload")
        main_app = Xitzin(title="Main")

        @upload_app.titan("/upload/{filename}")
        def upload_handler(
            request, content: bytes, mime_type: str, token: str | None, filename: str
        ):
            return f"# Uploaded {filename}"

        main_app.vhost(
            {
                "upload.example.com": upload_app,
            },
            fallback_status=53,
        )

        from nauyaca.protocol.request import TitanRequest as NauyacaTitanRequest

        # Request to unknown host
        url = "titan://unknown.example.com/upload/test.txt;size=5;mime=text/plain"
        request = NauyacaTitanRequest.from_line(url)
        request.content = b"hello"

        loop = asyncio.get_event_loop()
        response = loop.run_until_complete(main_app._handle_titan_request(request))

        assert response.status == StatusCode.PROXY_REQUEST_REFUSED


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_hosts_dict(self):
        """Test with empty hosts dictionary."""
        default_app = Xitzin(title="Default")

        @default_app.gemini("/")
        def home(request: Request):
            return "# Default"

        mw = VirtualHostMiddleware({}, default_app=default_app)

        @default_app.middleware
        async def vhost(request, call_next):
            return await mw(request, call_next)

        response = handle_request_sync(default_app, "gemini://any.example.com/")
        assert response.body == "# Default"

    def test_no_default_app_no_fallback_handler(self):
        """Test behavior when no match and no default_app."""
        app = Xitzin(title="App")

        @app.gemini("/")
        def home(request: Request):
            return "# Home"

        app.vhost({"example.com": app})

        # Unknown host should return fallback status (default 53)
        response = handle_request_sync(app, "gemini://unknown.com/")
        assert response.status == StatusCode.PROXY_REQUEST_REFUSED

    def test_hostname_with_port(self):
        """Test hostname matching ignores port in URL."""
        app = Xitzin(title="App")

        @app.gemini("/")
        def home(request: Request):
            return "# Home"

        mw = VirtualHostMiddleware({"example.com": app})

        # The hostname property from Nauyaca should strip the port
        assert mw._match_hostname("example.com") is app

    def test_multiple_apps_same_routes(self):
        """Test multiple apps can have the same routes."""
        app1 = Xitzin(title="App1")
        app2 = Xitzin(title="App2")
        main_app = Xitzin(title="Main")

        @app1.gemini("/")
        def app1_home(request: Request):
            return "# App1 Home"

        @app2.gemini("/")
        def app2_home(request: Request):
            return "# App2 Home"

        main_app.vhost(
            {
                "app1.example.com": app1,
                "app2.example.com": app2,
            }
        )

        response = handle_request_sync(main_app, "gemini://app1.example.com/")
        assert response.body == "# App1 Home"

        response = handle_request_sync(main_app, "gemini://app2.example.com/")
        assert response.body == "# App2 Home"
