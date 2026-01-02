"""Tests for xitzin.testing module."""

from xitzin import Request, Xitzin
from xitzin.testing import TestClient, TestResponse, test_app


class TestTestResponse:
    """Tests for TestResponse class."""

    def test_is_success_20(self):
        """is_success is True for status 20."""
        response = TestResponse(status=20, meta="text/gemini", body="content")
        assert response.is_success is True

    def test_is_success_2x(self):
        """is_success is True for 2x status."""
        for status in [20, 21, 25, 29]:
            response = TestResponse(status=status, meta="text/gemini", body="")
            assert response.is_success is True

    def test_is_success_false_for_others(self):
        """is_success is False for non-2x status."""
        for status in [10, 11, 30, 31, 40, 51, 60]:
            response = TestResponse(status=status, meta="", body=None)
            assert response.is_success is False

    def test_is_input_required_10(self):
        """is_input_required is True for status 10."""
        response = TestResponse(status=10, meta="Prompt", body=None)
        assert response.is_input_required is True

    def test_is_input_required_11(self):
        """is_input_required is True for status 11."""
        response = TestResponse(status=11, meta="Password:", body=None)
        assert response.is_input_required is True

    def test_is_input_required_false_for_others(self):
        """is_input_required is False for non-1x status."""
        for status in [20, 30, 40, 51]:
            response = TestResponse(status=status, meta="", body=None)
            assert response.is_input_required is False

    def test_is_redirect_30(self):
        """is_redirect is True for status 30."""
        response = TestResponse(status=30, meta="/new", body=None)
        assert response.is_redirect is True

    def test_is_redirect_31(self):
        """is_redirect is True for status 31."""
        response = TestResponse(status=31, meta="/moved", body=None)
        assert response.is_redirect is True

    def test_is_redirect_false_for_others(self):
        """is_redirect is False for non-3x status."""
        for status in [20, 10, 40, 51]:
            response = TestResponse(status=status, meta="", body=None)
            assert response.is_redirect is False

    def test_is_error_4x(self):
        """is_error is True for 4x status."""
        for status in [40, 41, 42, 43, 44]:
            response = TestResponse(status=status, meta="Error", body=None)
            assert response.is_error is True

    def test_is_error_5x(self):
        """is_error is True for 5x status."""
        for status in [50, 51, 52, 53, 59]:
            response = TestResponse(status=status, meta="Error", body=None)
            assert response.is_error is True

    def test_is_error_6x(self):
        """is_error is True for 6x status."""
        for status in [60, 61, 62]:
            response = TestResponse(status=status, meta="Error", body=None)
            assert response.is_error is True

    def test_is_error_false_for_success(self):
        """is_error is False for success status."""
        response = TestResponse(status=20, meta="text/gemini", body="")
        assert response.is_error is False

    def test_is_certificate_required_6x(self):
        """is_certificate_required is True for 6x status."""
        for status in [60, 61, 62]:
            response = TestResponse(status=status, meta="", body=None)
            assert response.is_certificate_required is True

    def test_is_certificate_required_false_for_others(self):
        """is_certificate_required is False for non-6x status."""
        for status in [20, 10, 40, 51]:
            response = TestResponse(status=status, meta="", body=None)
            assert response.is_certificate_required is False

    def test_redirect_url_for_redirect(self):
        """redirect_url returns meta for redirect responses."""
        response = TestResponse(status=30, meta="/new-location", body=None)
        assert response.redirect_url == "/new-location"

    def test_redirect_url_none_for_non_redirect(self):
        """redirect_url is None for non-redirect responses."""
        response = TestResponse(status=20, meta="text/gemini", body="")
        assert response.redirect_url is None

    def test_input_prompt_for_input(self):
        """input_prompt returns meta for input responses."""
        response = TestResponse(status=10, meta="Enter query:", body=None)
        assert response.input_prompt == "Enter query:"

    def test_input_prompt_none_for_non_input(self):
        """input_prompt is None for non-input responses."""
        response = TestResponse(status=20, meta="text/gemini", body="")
        assert response.input_prompt is None

    def test_mime_type_for_success(self):
        """mime_type returns MIME type for success responses."""
        response = TestResponse(status=20, meta="text/gemini", body="")
        assert response.mime_type == "text/gemini"

    def test_mime_type_strips_params(self):
        """mime_type strips charset and other parameters."""
        response = TestResponse(status=20, meta="text/gemini; charset=utf-8", body="")
        assert response.mime_type == "text/gemini"

    def test_mime_type_strips_multiple_params(self):
        """mime_type handles multiple parameters."""
        response = TestResponse(
            status=20, meta="text/html; charset=utf-8; boundary=something", body=""
        )
        assert response.mime_type == "text/html"

    def test_mime_type_none_for_non_success(self):
        """mime_type is None for non-success responses."""
        response = TestResponse(status=51, meta="Not found", body=None)
        assert response.mime_type is None

    def test_str_representation(self):
        """str() shows status and meta."""
        response = TestResponse(status=20, meta="text/gemini", body="# Hello")
        result = str(response)
        assert "status=20" in result
        assert "text/gemini" in result

    def test_str_with_body(self):
        """str() includes body preview."""
        response = TestResponse(status=20, meta="text/gemini", body="# Hello")
        result = str(response)
        assert "body=" in result
        assert "Hello" in result

    def test_str_truncates_long_body(self):
        """str() truncates long body."""
        long_body = "x" * 200
        response = TestResponse(status=20, meta="text/gemini", body=long_body)
        result = str(response)
        assert "..." in result

    def test_str_without_body(self):
        """str() works without body."""
        response = TestResponse(status=51, meta="Not found", body=None)
        result = str(response)
        assert "status=51" in result


class TestTestClient:
    """Tests for TestClient class."""

    def test_get_simple_route(self):
        """get() makes request to simple route."""
        app = Xitzin()

        @app.gemini("/")
        def home(request: Request):
            return "# Home"

        client = TestClient(app)
        response = client.get("/")

        assert response.is_success
        assert "Home" in response.body

    def test_get_with_path_params(self):
        """get() handles path parameters."""
        app = Xitzin()

        @app.gemini("/user/{name}")
        def user(request: Request, name: str):
            return f"# {name}"

        client = TestClient(app)
        response = client.get("/user/alice")

        assert "alice" in response.body

    def test_get_with_query(self):
        """get() includes query string."""
        app = Xitzin()

        @app.gemini("/search")
        def search(request: Request):
            return f"# Query: {request.query}"

        client = TestClient(app)
        response = client.get("/search", query="hello")

        assert "hello" in response.body

    def test_get_with_query_encoding(self):
        """get() URL-encodes query string."""
        app = Xitzin()

        @app.gemini("/search")
        def search(request: Request):
            return f"# Query: {request.query}"

        client = TestClient(app)
        response = client.get("/search", query="hello world")

        assert "hello world" in response.body

    def test_get_with_cert_fingerprint(self):
        """get() sets certificate fingerprint."""
        app = Xitzin()

        @app.gemini("/whoami")
        def whoami(request: Request):
            fp = request.client_cert_fingerprint or "anonymous"
            return f"# {fp}"

        client = TestClient(app)
        response = client.get("/whoami", cert_fingerprint="abc123")

        assert "abc123" in response.body

    def test_get_input_convenience(self):
        """get_input() is shorthand for get with query."""
        app = Xitzin()

        @app.input("/search", prompt="Query:")
        def search(request: Request, query: str):
            return f"# {query}"

        client = TestClient(app)
        response = client.get_input("/search", "hello world")

        assert response.is_success
        assert "hello world" in response.body

    def test_get_input_with_cert(self):
        """get_input() accepts certificate fingerprint."""
        app = Xitzin()

        @app.input("/search", prompt="Query:")
        def search(request: Request, query: str):
            fp = request.client_cert_fingerprint or "anon"
            return f"# {query} by {fp}"

        client = TestClient(app)
        response = client.get_input("/search", "test", cert_fingerprint="user1")

        assert "test" in response.body
        assert "user1" in response.body

    def test_with_certificate_returns_new_client(self):
        """with_certificate() returns new client."""
        app = Xitzin()
        client = TestClient(app)

        auth_client = client.with_certificate("abc123")

        assert auth_client is not client
        assert auth_client._default_fingerprint == "abc123"

    def test_with_certificate_used_by_default(self):
        """with_certificate() fingerprint used for all requests."""
        app = Xitzin()

        @app.gemini("/check")
        def check(request: Request):
            return f"# {request.client_cert_fingerprint}"

        client = TestClient(app)
        auth_client = client.with_certificate("default_cert")

        response = auth_client.get("/check")
        assert "default_cert" in response.body

    def test_get_cert_overrides_default(self):
        """get() cert_fingerprint overrides default."""
        app = Xitzin()

        @app.gemini("/check")
        def check(request: Request):
            return f"# {request.client_cert_fingerprint}"

        client = TestClient(app)
        auth_client = client.with_certificate("default_cert")

        response = auth_client.get("/check", cert_fingerprint="override")
        assert "override" in response.body

    def test_handles_not_found(self):
        """get() handles 404 responses."""
        app = Xitzin()

        @app.gemini("/")
        def home(request: Request):
            return "# Home"

        client = TestClient(app)
        response = client.get("/nonexistent")

        assert response.status == 51
        assert response.is_error

    def test_handles_input_response(self):
        """get() handles input prompt responses."""
        app = Xitzin()

        @app.input("/search", prompt="Enter query:")
        def search(request: Request, query: str):
            return f"# {query}"

        client = TestClient(app)
        response = client.get("/search")

        assert response.status == 10
        assert response.is_input_required
        assert response.input_prompt == "Enter query:"


class TestTestApp:
    """Tests for test_app context manager."""

    def test_runs_startup_handlers(self):
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

    def test_runs_shutdown_handlers(self):
        """test_app runs shutdown handlers."""
        app = Xitzin()
        stopped = []

        @app.on_shutdown
        def shutdown():
            stopped.append(True)

        @app.gemini("/")
        def home(request: Request):
            return "# Home"

        with test_app(app) as _client:
            assert stopped == []

        assert stopped == [True]

    def test_async_startup_shutdown(self):
        """test_app handles async handlers."""
        app = Xitzin()
        events = []

        @app.on_startup
        async def startup():
            events.append("started")

        @app.on_shutdown
        async def shutdown():
            events.append("stopped")

        @app.gemini("/")
        def home(request: Request):
            return "# Home"

        with test_app(app):
            assert events == ["started"]

        assert events == ["started", "stopped"]

    def test_yields_test_client(self):
        """test_app yields a TestClient."""
        app = Xitzin()

        @app.gemini("/")
        def home(request: Request):
            return "# Home"

        with test_app(app) as client:
            assert isinstance(client, TestClient)

    def test_state_available_during_tests(self):
        """State set in startup is available during tests."""
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

    def test_shutdown_runs_on_exception(self):
        """test_app runs shutdown even if exception occurs."""
        app = Xitzin()
        stopped = []

        @app.on_shutdown
        def shutdown():
            stopped.append(True)

        @app.gemini("/")
        def home(request: Request):
            return "# Home"

        try:
            with test_app(app) as client:
                client.get("/")
                raise ValueError("Test error")
        except ValueError:
            pass

        assert stopped == [True]

    def test_multiple_startup_handlers(self):
        """test_app runs multiple startup handlers."""
        app = Xitzin()
        order = []

        @app.on_startup
        def first():
            order.append(1)

        @app.on_startup
        def second():
            order.append(2)

        @app.gemini("/")
        def home(request: Request):
            return "# Home"

        with test_app(app):
            assert order == [1, 2]

    def test_multiple_shutdown_handlers_reverse(self):
        """test_app runs shutdown handlers in reverse order."""
        app = Xitzin()
        order = []

        @app.on_shutdown
        def first():
            order.append(1)

        @app.on_shutdown
        def second():
            order.append(2)

        @app.gemini("/")
        def home(request: Request):
            return "# Home"

        with test_app(app):
            pass

        assert order == [2, 1]
