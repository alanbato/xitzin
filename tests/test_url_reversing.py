"""Tests for URL reversing functionality."""

import pytest

from xitzin import Link, Redirect, Request, Xitzin
from xitzin.routing import Route, Router
from xitzin.testing import TestClient


class TestRouteNaming:
    """Tests for route naming functionality."""

    def test_auto_name_from_function(self):
        """Route is named after handler function by default."""

        def my_handler(request):
            return "hello"

        route = Route("/path", my_handler)
        assert route.name == "my_handler"

    def test_explicit_name_override(self):
        """Explicit name overrides function name."""

        def my_handler(request):
            return "hello"

        route = Route("/path", my_handler, name="custom_name")
        assert route.name == "custom_name"

    def test_lambda_name(self):
        """Lambda functions have name '<lambda>'."""
        route = Route("/path", lambda r: "hello")
        assert route.name == "<lambda>"


class TestRouteReverse:
    """Tests for Route.reverse() method."""

    def test_simple_path(self):
        """Reverse works for paths without parameters."""
        route = Route("/about", lambda r: "about")
        assert route.reverse() == "/about"

    def test_single_parameter(self):
        """Reverse substitutes a single parameter."""
        route = Route("/user/{username}", lambda r, username: username)
        assert route.reverse(username="alice") == "/user/alice"

    def test_multiple_parameters(self):
        """Reverse substitutes multiple parameters."""
        route = Route("/post/{year}/{month}/{slug}", lambda r, year, month, slug: slug)
        assert route.reverse(year=2024, month=12, slug="hello") == "/post/2024/12/hello"

    def test_path_parameter(self):
        """Reverse works with :path parameters."""
        route = Route("/files/{filepath:path}", lambda r, filepath: filepath)
        assert (
            route.reverse(filepath="docs/guide/intro.gmi")
            == "/files/docs/guide/intro.gmi"
        )

    def test_missing_parameter_raises(self):
        """Missing required parameters raise ValueError."""
        route = Route("/user/{id}", lambda r, id: id, name="user")
        with pytest.raises(ValueError) as exc:
            route.reverse()
        assert "Route 'user' missing required parameters: id" in str(exc.value)

    def test_missing_multiple_parameters_raises(self):
        """Missing multiple parameters are listed."""
        route = Route("/post/{year}/{month}", lambda r, year, month: "", name="post")
        with pytest.raises(ValueError) as exc:
            route.reverse()
        assert "month" in str(exc.value)
        assert "year" in str(exc.value)

    def test_extra_parameters_ignored(self):
        """Extra parameters are silently ignored."""
        route = Route("/user/{id}", lambda r, id: id)
        # Should not raise - extra params are ignored
        url = route.reverse(id=42, extra="ignored")
        assert url == "/user/42"

    def test_integer_parameter_converted(self):
        """Integer parameters are converted to strings."""
        route = Route("/user/{id}", lambda r, id: id)
        assert route.reverse(id=123) == "/user/123"

    def test_float_parameter_converted(self):
        """Float parameters are converted to strings."""
        route = Route("/score/{value}", lambda r, value: value)
        assert route.reverse(value=3.14) == "/score/3.14"


class TestRouterReverse:
    """Tests for Router.reverse() method."""

    def test_reverse_by_name(self):
        """Router looks up route by name and reverses."""
        router = Router()

        def user_profile(r, username):
            return username

        route = Route("/user/{username}", user_profile)
        router.add_route(route)

        assert router.reverse("user_profile", username="alice") == "/user/alice"

    def test_route_not_found_raises(self):
        """Non-existent route name raises ValueError."""
        router = Router()
        router.add_route(Route("/home", lambda r: "home", name="home"))

        with pytest.raises(ValueError) as exc:
            router.reverse("nonexistent")
        assert "No route named 'nonexistent'" in str(exc.value)
        assert "Available routes: home" in str(exc.value)

    def test_duplicate_name_raises(self):
        """Adding route with duplicate name raises ValueError."""
        router = Router()
        router.add_route(Route("/first", lambda r: "first", name="same_name"))

        with pytest.raises(ValueError) as exc:
            router.add_route(Route("/second", lambda r: "second", name="same_name"))
        assert "Route name 'same_name' already registered" in str(exc.value)
        assert "/first" in str(exc.value)


class TestXitzinReverse:
    """Tests for Xitzin.reverse() method."""

    def test_app_reverse(self):
        """App can reverse routes by name."""
        app = Xitzin()

        @app.gemini("/user/{username}")
        def user_profile(request: Request, username: str):
            return f"Profile: {username}"

        assert app.reverse("user_profile", username="alice") == "/user/alice"

    def test_app_reverse_with_explicit_name(self):
        """App can reverse routes with explicit names."""
        app = Xitzin()

        @app.gemini("/u/{id}", name="user_detail")
        def user_handler(request: Request, id: int):
            return f"User: {id}"

        assert app.reverse("user_detail", id=42) == "/u/42"

    def test_input_route_naming(self):
        """Input routes can be named and reversed."""
        app = Xitzin()

        @app.input("/search", prompt="Enter query:", name="search")
        def search(request: Request, query: str):
            return f"Results: {query}"

        assert app.reverse("search") == "/search"

    def test_reverse_in_handler(self):
        """Handler can use app.reverse() to build URLs."""
        app = Xitzin()

        @app.gemini("/")
        def home(request: Request):
            profile_url = request.app.reverse("profile", username="alice")
            return f"=> {profile_url} Alice's Profile"

        @app.gemini("/user/{username}", name="profile")
        def profile(request: Request, username: str):
            return f"Profile: {username}"

        client = TestClient(app)
        response = client.get("/")
        assert response.is_success
        assert "/user/alice" in response.body


class TestXitzinRedirect:
    """Tests for Xitzin.redirect() method."""

    def test_redirect_to_named_route(self):
        """App can create redirect to named route."""
        app = Xitzin()

        @app.gemini("/new/{id}", name="new_page")
        def new_page(request: Request, id: int):
            return f"New page: {id}"

        redirect = app.redirect("new_page", id=123)
        assert isinstance(redirect, Redirect)
        assert redirect.url == "/new/123"
        assert redirect.permanent is False

    def test_redirect_permanent(self):
        """Permanent redirect flag is respected."""
        app = Xitzin()

        @app.gemini("/new", name="new_page")
        def new_page(request: Request):
            return "New page"

        redirect = app.redirect("new_page", permanent=True)
        assert redirect.permanent is True

    def test_redirect_in_handler(self):
        """Handler can use app.redirect() for redirects."""
        app = Xitzin()

        @app.gemini("/old/{id}")
        def old_page(request: Request, id: int):
            return request.app.redirect("new_page", id=id)

        @app.gemini("/new/{id}", name="new_page")
        def new_page(request: Request, id: int):
            return f"New: {id}"

        client = TestClient(app)
        response = client.get("/old/42")
        assert response.is_redirect
        assert response.redirect_url == "/new/42"


class TestLinkClass:
    """Tests for Link class."""

    def test_link_with_label(self):
        """Link generates Gemtext link with label."""
        link = Link("/about", "About Us")
        assert str(link) == "=> /about About Us"
        assert link.to_gemtext() == "=> /about About Us"

    def test_link_without_label(self):
        """Link generates Gemtext link without label."""
        link = Link("/about")
        assert str(link) == "=> /about"

    def test_link_to_route(self):
        """Link.to_route() creates link from route name."""
        app = Xitzin()

        @app.gemini("/user/{username}", name="profile")
        def profile(request: Request, username: str):
            return f"Profile: {username}"

        link = Link.to_route(app, "profile", username="alice", label="Alice's Profile")
        assert str(link) == "=> /user/alice Alice's Profile"

    def test_link_to_route_without_label(self):
        """Link.to_route() works without label."""
        app = Xitzin()

        @app.gemini("/about", name="about")
        def about(request: Request):
            return "About"

        link = Link.to_route(app, "about")
        assert str(link) == "=> /about"

    def test_link_in_handler(self):
        """Links can be used in handlers."""
        app = Xitzin()

        @app.gemini("/", name="home")
        def home(request: Request):
            links = [
                Link.to_route(request.app, "profile", username="alice", label="Alice"),
                Link.to_route(request.app, "profile", username="bob", label="Bob"),
            ]
            return "# Users\n" + "\n".join(str(link) for link in links)

        @app.gemini("/user/{username}", name="profile")
        def profile(request: Request, username: str):
            return f"Profile: {username}"

        client = TestClient(app)
        response = client.get("/")
        assert "=> /user/alice Alice" in response.body
        assert "=> /user/bob Bob" in response.body


class TestTemplateIntegration:
    """Tests for template integration with reverse()."""

    def test_reverse_in_template(self, tmp_path):
        """reverse() function is available in templates."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        template = templates_dir / "page.gmi"
        template.write_text(
            "{{ reverse('profile', username='alice') | link('Profile') }}"
        )

        app = Xitzin(templates_dir=templates_dir)

        @app.gemini("/user/{username}", name="profile")
        def profile(request: Request, username: str):
            return f"Profile: {username}"

        @app.gemini("/")
        def home(request: Request):
            return request.app.template("page.gmi")

        client = TestClient(app)
        response = client.get("/")
        assert response.is_success
        assert "=> /user/alice Profile" in response.body

    def test_reverse_with_multiple_params_in_template(self, tmp_path):
        """reverse() with multiple parameters works in templates."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        template = templates_dir / "page.gmi"
        template.write_text("{{ reverse('post', year=2024, month=12, slug='hello') }}")

        app = Xitzin(templates_dir=templates_dir)

        @app.gemini("/post/{year}/{month}/{slug}", name="post")
        def post(request: Request, year: int, month: int, slug: str):
            return f"Post: {slug}"

        @app.gemini("/")
        def home(request: Request):
            return request.app.template("page.gmi")

        client = TestClient(app)
        response = client.get("/")
        assert response.is_success
        assert "/post/2024/12/hello" in response.body
