"""Tests for xitzin.application module."""

import asyncio

import pytest
from nauyaca.protocol.request import GeminiRequest

from xitzin import Request, Xitzin
from xitzin.application import AppState
from xitzin.exceptions import NotFound, TemporaryFailure
from xitzin.testing import TestClient, test_app


class TestAppState:
    """Tests for AppState class."""

    def test_setattr(self):
        """Can set attributes on AppState."""
        state = AppState()
        state.db = "database"
        state.cache = {"key": "value"}
        assert state.db == "database"
        assert state.cache == {"key": "value"}

    def test_getattr_missing_raises_attribute_error(self):
        """Accessing missing attribute raises AttributeError."""
        state = AppState()
        with pytest.raises(
            AttributeError, match="'AppState' has no attribute 'missing'"
        ):
            _ = state.missing

    def test_multiple_values(self):
        """Can store multiple values."""
        state = AppState()
        state.a = 1
        state.b = "two"
        state.c = [3]
        assert state.a == 1
        assert state.b == "two"
        assert state.c == [3]


class TestXitzinInit:
    """Tests for Xitzin initialization."""

    def test_default_values(self):
        """Xitzin uses default values when not specified."""
        app = Xitzin()
        assert app.title == "Xitzin App"
        assert app.version == "0.1.0"

    def test_custom_values(self):
        """Xitzin accepts custom title and version."""
        app = Xitzin(title="My Capsule", version="2.0.0")
        assert app.title == "My Capsule"
        assert app.version == "2.0.0"

    def test_templates_dir_initialization(self, tmp_path):
        """Templates dir initializes template engine."""
        templates = tmp_path / "templates"
        templates.mkdir()
        (templates / "test.gmi").write_text("# Test")

        app = Xitzin(templates_dir=templates)
        assert app._templates is not None

    def test_no_templates_by_default(self):
        """No template engine by default."""
        app = Xitzin()
        assert app._templates is None


class TestXitzinState:
    """Tests for Xitzin.state property."""

    def test_state_returns_app_state(self):
        """state property returns AppState instance."""
        app = Xitzin()
        assert isinstance(app.state, AppState)

    def test_state_is_mutable(self):
        """state can store values."""
        app = Xitzin()
        app.state.config = {"debug": True}
        assert app.state.config == {"debug": True}

    def test_state_persists(self):
        """state returns same instance."""
        app = Xitzin()
        app.state.value = 42
        assert app.state.value == 42


class TestXitzinTemplates:
    """Tests for Xitzin template rendering."""

    def test_template_without_dir_raises(self):
        """template() raises RuntimeError when no templates_dir."""
        app = Xitzin()
        with pytest.raises(RuntimeError, match="No templates directory configured"):
            app.template("page.gmi")

    def test_template_renders(self, tmp_path):
        """template() renders template with context."""
        templates = tmp_path / "templates"
        templates.mkdir()
        (templates / "page.gmi").write_text("# {{ title }}")

        app = Xitzin(templates_dir=templates)
        result = app.template("page.gmi", title="Hello")

        assert "# Hello" in result.content

    def test_template_with_multiple_context_vars(self, tmp_path):
        """template() passes all context variables."""
        templates = tmp_path / "templates"
        templates.mkdir()
        (templates / "page.gmi").write_text("# {{ title }}\n{{ body }}")

        app = Xitzin(templates_dir=templates)
        result = app.template("page.gmi", title="Title", body="Content")

        assert "# Title" in result.content
        assert "Content" in result.content


class TestXitzinGeminiDecorator:
    """Tests for @app.gemini() decorator."""

    def test_registers_route(self):
        """gemini() registers a route."""
        app = Xitzin()

        @app.gemini("/test")
        def handler(request: Request):
            return "test"

        assert len(app._router) == 1

    def test_handler_is_returned(self):
        """gemini() returns the original handler."""
        app = Xitzin()

        def original_handler(request: Request):
            return "test"

        decorated = app.gemini("/test")(original_handler)
        assert decorated is original_handler

    def test_multiple_routes(self):
        """Multiple routes can be registered."""
        app = Xitzin()

        @app.gemini("/a")
        def handler_a(request: Request):
            return "a"

        @app.gemini("/b")
        def handler_b(request: Request):
            return "b"

        assert len(app._router) == 2


class TestXitzinInputDecorator:
    """Tests for @app.input() decorator."""

    def test_registers_input_route(self):
        """input() registers a route with prompt."""
        app = Xitzin()

        @app.input("/search", prompt="Enter query:")
        def search(request: Request, query: str):
            return f"Results for: {query}"

        assert len(app._router) == 1
        route = list(app._router)[0]
        assert route.input_prompt == "Enter query:"
        assert route.sensitive_input is False

    def test_sensitive_input(self):
        """input() with sensitive=True sets flag."""
        app = Xitzin()

        @app.input("/login", prompt="Password:", sensitive=True)
        def login(request: Request, query: str):
            return "logged in"

        route = list(app._router)[0]
        assert route.sensitive_input is True

    def test_handler_is_returned(self):
        """input() returns the original handler."""
        app = Xitzin()

        def original_handler(request: Request, query: str):
            return query

        decorated = app.input("/search", prompt="Query:")(original_handler)
        assert decorated is original_handler


class TestXitzinLifecycle:
    """Tests for startup/shutdown handlers."""

    def test_on_startup_registers_handler(self):
        """on_startup registers startup handler."""
        app = Xitzin()

        @app.on_startup
        def startup():
            pass

        assert len(app._startup_handlers) == 1

    def test_on_shutdown_registers_handler(self):
        """on_shutdown registers shutdown handler."""
        app = Xitzin()

        @app.on_shutdown
        def shutdown():
            pass

        assert len(app._shutdown_handlers) == 1

    def test_startup_handlers_run(self):
        """Startup handlers are executed."""
        app = Xitzin()
        results = []

        @app.on_startup
        def startup1():
            results.append("sync")

        @app.on_startup
        async def startup2():
            results.append("async")

        asyncio.get_event_loop().run_until_complete(app._run_startup())
        assert results == ["sync", "async"]

    def test_shutdown_handlers_run_reverse_order(self):
        """Shutdown handlers run in reverse order."""
        app = Xitzin()
        results = []

        @app.on_shutdown
        def shutdown1():
            results.append("first")

        @app.on_shutdown
        def shutdown2():
            results.append("second")

        asyncio.get_event_loop().run_until_complete(app._run_shutdown())
        assert results == ["second", "first"]

    def test_async_shutdown_handlers(self):
        """Async shutdown handlers are awaited."""
        app = Xitzin()
        results = []

        @app.on_shutdown
        async def shutdown():
            results.append("async_shutdown")

        asyncio.get_event_loop().run_until_complete(app._run_shutdown())
        assert results == ["async_shutdown"]

    def test_multiple_startup_handlers(self):
        """Multiple startup handlers run in order."""
        app = Xitzin()
        order = []

        @app.on_startup
        def first():
            order.append(1)

        @app.on_startup
        def second():
            order.append(2)

        @app.on_startup
        def third():
            order.append(3)

        asyncio.get_event_loop().run_until_complete(app._run_startup())
        assert order == [1, 2, 3]


class TestXitzinMiddleware:
    """Tests for middleware handling."""

    def test_middleware_decorator(self):
        """middleware() registers middleware."""
        app = Xitzin()

        @app.middleware
        async def my_middleware(request, call_next):
            return await call_next(request)

        assert len(app._middleware) == 1

    def test_middleware_execution_order(self):
        """Middleware runs in registration order."""
        app = Xitzin()
        order = []

        @app.middleware
        async def first(request, call_next):
            order.append("first_before")
            response = await call_next(request)
            order.append("first_after")
            return response

        @app.middleware
        async def second(request, call_next):
            order.append("second_before")
            response = await call_next(request)
            order.append("second_after")
            return response

        @app.gemini("/")
        def home(request: Request):
            order.append("handler")
            return "# Home"

        client = TestClient(app)
        client.get("/")

        assert order == [
            "first_before",
            "second_before",
            "handler",
            "second_after",
            "first_after",
        ]

    def test_middleware_can_modify_response(self):
        """Middleware can modify response."""
        from nauyaca.protocol.response import GeminiResponse
        from nauyaca.protocol.status import StatusCode

        app = Xitzin()

        @app.middleware
        async def modify_middleware(request, call_next):
            _response = await call_next(request)
            return GeminiResponse(
                status=StatusCode.SUCCESS,
                meta="text/plain",
                body="Modified",
            )

        @app.gemini("/")
        def home(request: Request):
            return "# Original"

        client = TestClient(app)
        response = client.get("/")

        assert response.body == "Modified"
        assert response.meta == "text/plain"


class TestXitzinRequestHandling:
    """Tests for request handling."""

    def test_simple_route(self):
        """Simple route returns success."""
        app = Xitzin()

        @app.gemini("/")
        def home(request: Request):
            return "# Welcome"

        client = TestClient(app)
        response = client.get("/")

        assert response.status == 20
        assert "Welcome" in response.body

    def test_path_parameters(self):
        """Path parameters are passed to handler."""
        app = Xitzin()

        @app.gemini("/user/{username}")
        def profile(request: Request, username: str):
            return f"# {username}'s Profile"

        client = TestClient(app)
        response = client.get("/user/alice")

        assert response.is_success
        assert "alice's Profile" in response.body

    def test_multiple_path_parameters(self):
        """Multiple path parameters work correctly."""
        app = Xitzin()

        @app.gemini("/user/{user_id}/post/{post_id}")
        def post(request: Request, user_id: str, post_id: str):
            return f"# User {user_id}, Post {post_id}"

        client = TestClient(app)
        response = client.get("/user/123/post/456")

        assert response.is_success
        assert "User 123" in response.body
        assert "Post 456" in response.body

    def test_typed_path_parameters(self):
        """Typed path parameters are converted."""
        app = Xitzin()

        @app.gemini("/page/{num}")
        def page(request: Request, num: int):
            return f"# Page {num + 1}"

        client = TestClient(app)
        response = client.get("/page/5")

        assert response.is_success
        assert "Page 6" in response.body

    def test_not_found(self):
        """Unmatched route returns 51."""
        app = Xitzin()

        @app.gemini("/")
        def home(request: Request):
            return "# Home"

        client = TestClient(app)
        response = client.get("/nonexistent")

        assert response.status == 51

    def test_input_flow_prompt(self):
        """Input route without query returns prompt."""
        app = Xitzin()

        @app.input("/search", prompt="Enter search query:")
        def search(request: Request, query: str):
            return f"# Results for: {query}"

        client = TestClient(app)
        response = client.get("/search")

        assert response.status == 10
        assert response.meta == "Enter search query:"

    def test_input_flow_with_query(self):
        """Input route with query calls handler."""
        app = Xitzin()

        @app.input("/search", prompt="Enter search query:")
        def search(request: Request, query: str):
            return f"# Results for: {query}"

        client = TestClient(app)
        response = client.get_input("/search", "hello world")

        assert response.is_success
        assert "Results for: hello world" in response.body

    def test_sensitive_input_status_11(self):
        """Sensitive input returns status 11."""
        app = Xitzin()

        @app.input("/login", prompt="Password:", sensitive=True)
        def login(request: Request, query: str):
            return "# Logged in"

        client = TestClient(app)
        response = client.get("/login")

        assert response.status == 11

    def test_gemini_exception_handling(self):
        """GeminiException returns appropriate status."""
        app = Xitzin()

        @app.gemini("/error")
        def error(request: Request):
            raise TemporaryFailure("Server overloaded")

        client = TestClient(app)
        response = client.get("/error")

        assert response.status == 40
        assert "Server overloaded" in response.meta

    def test_not_found_exception(self):
        """NotFound exception returns 51."""
        app = Xitzin()

        @app.gemini("/check")
        def check(request: Request):
            raise NotFound("Resource not found")

        client = TestClient(app)
        response = client.get("/check")

        assert response.status == 51
        assert "Resource not found" in response.meta

    def test_generic_exception_handling(self):
        """Generic exception returns 40 with generic error message."""
        app = Xitzin()

        @app.gemini("/crash")
        def crash(request: Request):
            raise ValueError("Something went wrong")

        client = TestClient(app)
        response = client.get("/crash")

        assert response.status == 40
        # Security: error message should be generic, not expose exception type
        assert response.meta == "Internal server error"

    def test_async_handler(self):
        """Async handler is awaited."""
        app = Xitzin()

        @app.gemini("/async")
        async def async_handler(request: Request):
            return "# Async Response"

        client = TestClient(app)
        response = client.get("/async")

        assert response.is_success
        assert "Async Response" in response.body

    def test_handler_access_request_properties(self):
        """Handler can access request properties."""
        app = Xitzin()

        @app.gemini("/info")
        def info(request: Request):
            return f"# Path: {request.path}"

        client = TestClient(app)
        response = client.get("/info")

        assert "Path: /info" in response.body

    def test_handler_access_app(self):
        """Handler can access app via request."""
        app = Xitzin(title="Test Capsule")
        app.state.config = {"version": "1.0"}

        @app.gemini("/")
        def home(request: Request):
            return f"# {request.app.title}"

        client = TestClient(app)
        response = client.get("/")

        assert "Test Capsule" in response.body


class TestXitzinHandleRequestSync:
    """Tests for handle_request_sync method."""

    def test_handle_request_sync(self):
        """handle_request_sync processes requests synchronously."""
        app = Xitzin()

        @app.gemini("/")
        def home(request: Request):
            return "# Home"

        raw_request = GeminiRequest.from_line("gemini://testserver/")
        response = app.handle_request_sync(raw_request)

        assert response.status == 20
        assert "Home" in response.body

    def test_handle_request_sync_with_params(self):
        """handle_request_sync handles path parameters."""
        app = Xitzin()

        @app.gemini("/user/{name}")
        def user(request: Request, name: str):
            return f"# {name}"

        raw_request = GeminiRequest.from_line("gemini://testserver/user/alice")
        response = app.handle_request_sync(raw_request)

        assert response.status == 20
        assert "alice" in response.body


class TestXitzinWithTestApp:
    """Tests using test_app context manager."""

    def test_startup_runs(self):
        """test_app runs startup handlers."""
        app = Xitzin()
        started = []

        @app.on_startup
        def startup():
            started.append(True)

        @app.gemini("/")
        def home(request: Request):
            return "# Home"

        with test_app(app) as client:
            assert started == [True]
            response = client.get("/")
            assert response.is_success

    def test_shutdown_runs(self):
        """test_app runs shutdown handlers."""
        app = Xitzin()
        stopped = []

        @app.on_shutdown
        def shutdown():
            stopped.append(True)

        @app.gemini("/")
        def home(request: Request):
            return "# Home"

        with test_app(app) as client:
            assert stopped == []
            client.get("/")

        assert stopped == [True]

    def test_state_from_startup(self):
        """State set in startup is available."""
        app = Xitzin()

        @app.on_startup
        def startup():
            app.state.db = "connected"

        @app.gemini("/")
        def home(request: Request):
            return f"# DB: {request.app.state.db}"

        with test_app(app) as client:
            response = client.get("/")
            assert "connected" in response.body
