"""Tests for xitzin.routing module."""

import pytest
from nauyaca.protocol.request import GeminiRequest

from xitzin.requests import Request
from xitzin.routing import Route, Router


class TestRouteCompilePath:
    """Tests for Route._compile_path method."""

    def test_simple_path(self):
        """Simple path compiles to exact match."""
        route = Route("/about", lambda r: "about")
        assert route.matches("/about")
        assert not route.matches("/about/more")
        assert not route.matches("/other")

    def test_path_with_parameter(self):
        """Path with {param} captures segment."""
        route = Route("/user/{id}", lambda r, id: id)
        assert route.matches("/user/123")
        assert route.matches("/user/alice")
        assert not route.matches("/user/123/extra")
        assert not route.matches("/user/")

    def test_path_with_multiple_parameters(self):
        """Path with multiple parameters captures all."""
        route = Route("/user/{id}/post/{post_id}", lambda r, id, post_id: (id, post_id))
        assert route.matches("/user/123/post/456")
        assert not route.matches("/user/123")
        assert not route.matches("/user/123/post/")

    def test_path_parameter(self):
        """Path with {name:path} captures everything including slashes."""
        route = Route("/files/{path:path}", lambda r, path: path)
        assert route.matches("/files/a/b/c")
        assert route.matches("/files/single")
        assert route.matches("/files/deep/nested/path/file.txt")

    def test_root_path(self):
        """Root path matches exactly."""
        route = Route("/", lambda r: "home")
        assert route.matches("/")
        assert not route.matches("/other")

    def test_path_with_special_regex_chars(self):
        """Path with regex special characters is escaped."""
        route = Route("/page.html", lambda r: "page")
        assert route.matches("/page.html")
        assert not route.matches("/pageXhtml")

    def test_path_ending_with_slash(self):
        """Path ending with slash matches correctly."""
        route = Route("/about/", lambda r: "about")
        assert route.matches("/about/")
        assert not route.matches("/about")


class TestRouteExtractParams:
    """Tests for Route.extract_params method."""

    def test_no_params(self):
        """Path without parameters returns empty dict."""
        route = Route("/about", lambda r: "about")
        assert route.extract_params("/about") == {}

    def test_single_param(self):
        """Single parameter extracted correctly."""
        route = Route("/user/{id}", lambda r, id: id)
        assert route.extract_params("/user/123") == {"id": "123"}

    def test_multiple_params(self):
        """Multiple parameters extracted correctly."""
        route = Route("/user/{id}/post/{post_id}", lambda r, id, post_id: (id, post_id))
        params = route.extract_params("/user/alice/post/42")
        assert params == {"id": "alice", "post_id": "42"}

    def test_path_param(self):
        """:path parameter captures full path including slashes."""
        route = Route("/files/{filepath:path}", lambda r, filepath: filepath)
        params = route.extract_params("/files/dir/subdir/file.txt")
        assert params == {"filepath": "dir/subdir/file.txt"}

    def test_no_match_returns_empty(self):
        """Non-matching path returns empty dict."""
        route = Route("/user/{id}", lambda r, id: id)
        assert route.extract_params("/other") == {}


class TestRouteTypeConversion:
    """Tests for Route parameter type conversion."""

    def test_int_conversion(self):
        """Integer parameters are converted."""

        def handler(request, user_id: int):
            return user_id

        route = Route("/user/{user_id}", handler)
        params = route.extract_params("/user/42")
        assert params == {"user_id": 42}
        assert isinstance(params["user_id"], int)

    def test_float_conversion(self):
        """Float parameters are converted."""

        def handler(request, price: float):
            return price

        route = Route("/product/{price}", handler)
        params = route.extract_params("/product/19.99")
        assert params == {"price": 19.99}
        assert isinstance(params["price"], float)

    def test_bool_conversion_true_values(self):
        """Bool parameters convert 'true', '1', 'yes' to True."""

        def handler(request, enabled: bool):
            return enabled

        route = Route("/setting/{enabled}", handler)

        for value in ["true", "True", "TRUE", "1", "yes", "Yes", "YES"]:
            params = route.extract_params(f"/setting/{value}")
            assert params["enabled"] is True

    def test_bool_conversion_false_values(self):
        """Bool parameters convert other values to False."""

        def handler(request, enabled: bool):
            return enabled

        route = Route("/setting/{enabled}", handler)

        for value in ["false", "False", "0", "no", "No", "anything"]:
            params = route.extract_params(f"/setting/{value}")
            assert params["enabled"] is False

    def test_string_fallback(self):
        """Parameters without type hints remain strings."""

        def handler(request, name):
            return name

        route = Route("/user/{name}", handler)
        params = route.extract_params("/user/alice")
        assert params == {"name": "alice"}
        assert isinstance(params["name"], str)

    def test_str_type_hint(self):
        """Parameters with str type hint remain strings."""

        def handler(request, name: str):
            return name

        route = Route("/user/{name}", handler)
        params = route.extract_params("/user/bob")
        assert params == {"name": "bob"}
        assert isinstance(params["name"], str)

    def test_conversion_failure_keeps_string(self):
        """Failed conversion keeps value as string."""

        def handler(request, count: int):
            return count

        route = Route("/count/{count}", handler)
        params = route.extract_params("/count/notanumber")
        assert params == {"count": "notanumber"}
        assert isinstance(params["count"], str)

    def test_float_conversion_failure_keeps_string(self):
        """Failed float conversion keeps value as string."""

        def handler(request, value: float):
            return value

        route = Route("/value/{value}", handler)
        params = route.extract_params("/value/not_a_float")
        assert params == {"value": "not_a_float"}
        assert isinstance(params["value"], str)


class TestRouteCallHandler:
    """Tests for Route.call_handler method."""

    @pytest.fixture
    def mock_request(self):
        """Create a mock request."""
        raw = GeminiRequest.from_line("gemini://testserver/test")
        return Request(raw)

    @pytest.mark.asyncio
    async def test_sync_handler(self, mock_request):
        """Sync handler is wrapped and called."""

        def sync_handler(request, name: str):
            return f"Hello {name}"

        route = Route("/hello/{name}", sync_handler)
        result = await route.call_handler(mock_request, {"name": "world"})
        assert result == "Hello world"

    @pytest.mark.asyncio
    async def test_async_handler(self, mock_request):
        """Async handler is awaited directly."""

        async def async_handler(request, name: str):
            return f"Hello {name}"

        route = Route("/hello/{name}", async_handler)
        result = await route.call_handler(mock_request, {"name": "async"})
        assert result == "Hello async"

    @pytest.mark.asyncio
    async def test_handler_with_multiple_params(self, mock_request):
        """Handler receives multiple parameters."""

        def handler(request, user_id: int, page: int):
            return f"User {user_id}, Page {page}"

        route = Route("/user/{user_id}/page/{page}", handler)
        result = await route.call_handler(mock_request, {"user_id": 1, "page": 5})
        assert result == "User 1, Page 5"

    @pytest.mark.asyncio
    async def test_handler_with_no_params(self, mock_request):
        """Handler with no path parameters."""

        def handler(request):
            return "No params"

        route = Route("/about", handler)
        result = await route.call_handler(mock_request, {})
        assert result == "No params"

    def test_repr(self):
        """Route repr shows the path and name."""
        route = Route("/user/{id}", lambda r, id: id)
        assert repr(route) == "Route('/user/{id}', name='<lambda>')"

    def test_repr_with_named_function(self):
        """Route repr shows the path and function name."""

        def user_profile(r, id):
            return id

        route = Route("/user/{id}", user_profile)
        assert repr(route) == "Route('/user/{id}', name='user_profile')"

    def test_repr_with_explicit_name(self):
        """Route repr shows the path and explicit name."""
        route = Route("/user/{id}", lambda r, id: id, name="user_detail")
        assert repr(route) == "Route('/user/{id}', name='user_detail')"


class TestRouteInputPrompt:
    """Tests for Route input prompt handling."""

    def test_input_route_attributes(self):
        """Route stores input_prompt and sensitive_input."""
        route = Route(
            "/search",
            lambda r, query: query,
            input_prompt="Enter query:",
            sensitive_input=True,
        )
        assert route.input_prompt == "Enter query:"
        assert route.sensitive_input is True

    def test_default_no_input(self):
        """Route has no input prompt by default."""
        route = Route("/page", lambda r: "page")
        assert route.input_prompt is None
        assert route.sensitive_input is False

    def test_sensitive_false_by_default(self):
        """sensitive_input defaults to False."""
        route = Route("/search", lambda r: "result", input_prompt="Query:")
        assert route.input_prompt == "Query:"
        assert route.sensitive_input is False


class TestRouter:
    """Tests for the Router class."""

    def test_add_and_match(self):
        """Routes can be added and matched."""
        router = Router()
        route = Route("/test", lambda r: "test")
        router.add_route(route)

        match = router.match("/test")
        assert match is not None
        matched_route, params = match
        assert matched_route is route
        assert params == {}

    def test_match_with_params(self):
        """Match extracts parameters."""
        router = Router()
        route = Route("/user/{id}", lambda r, id: id)
        router.add_route(route)

        match = router.match("/user/123")
        assert match is not None
        matched_route, params = match
        assert params == {"id": "123"}

    def test_no_match_returns_none(self):
        """Non-matching path returns None."""
        router = Router()
        router.add_route(Route("/page", lambda r: "page"))

        assert router.match("/other") is None

    def test_first_match_wins(self):
        """First matching route wins."""
        router = Router()
        route1 = Route("/page", lambda r: "first", name="first_route")
        route2 = Route("/page", lambda r: "second", name="second_route")
        router.add_route(route1)
        router.add_route(route2)

        match = router.match("/page")
        assert match[0] is route1

    def test_more_specific_route_first(self):
        """More specific route wins when registered first."""
        router = Router()
        specific = Route("/user/admin", lambda r: "admin", name="admin_route")
        generic = Route("/user/{id}", lambda r, id: id, name="user_route")
        router.add_route(specific)
        router.add_route(generic)

        # Specific route wins
        match = router.match("/user/admin")
        assert match[0] is specific

        # Generic route matches other paths
        match = router.match("/user/123")
        assert match[0] is generic

    def test_iter(self):
        """Router is iterable."""
        router = Router()
        route1 = Route("/a", lambda r: "a", name="route_a")
        route2 = Route("/b", lambda r: "b", name="route_b")
        router.add_route(route1)
        router.add_route(route2)

        routes = list(router)
        assert routes == [route1, route2]

    def test_len(self):
        """Router has length."""
        router = Router()
        assert len(router) == 0

        router.add_route(Route("/a", lambda r: "a", name="route_a"))
        assert len(router) == 1

        router.add_route(Route("/b", lambda r: "b", name="route_b"))
        assert len(router) == 2

    def test_empty_router_match(self):
        """Empty router returns None for any path."""
        router = Router()
        assert router.match("/") is None
        assert router.match("/anything") is None
