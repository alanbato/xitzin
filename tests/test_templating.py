"""Tests for xitzin.templating module."""

import pytest
from nauyaca.protocol.status import StatusCode

from xitzin import Xitzin
from xitzin.templating import (
    GemtextEnvironment,
    TemplateEngine,
    TemplateResponse,
    _heading_filter,
    _link_filter,
    _list_filter,
    _preformat_filter,
    _quote_filter,
)
from xitzin.testing import TestClient


class TestTemplateResponse:
    """Tests for TemplateResponse class."""

    def test_default_mime_type(self):
        """TemplateResponse uses text/gemini by default."""
        response = TemplateResponse("# Hello")
        assert response.mime_type == "text/gemini"

    def test_custom_mime_type(self):
        """TemplateResponse can have custom MIME type."""
        response = TemplateResponse("plain", mime_type="text/plain")
        assert response.mime_type == "text/plain"

    def test_content_stored(self):
        """TemplateResponse stores content."""
        response = TemplateResponse("# Welcome")
        assert response.content == "# Welcome"

    def test_to_gemini_response(self):
        """TemplateResponse converts to GeminiResponse."""
        response = TemplateResponse("# Welcome")
        gemini_response = response.to_gemini_response()

        assert gemini_response.status == StatusCode.SUCCESS
        assert gemini_response.meta == "text/gemini"
        assert gemini_response.body == "# Welcome"

    def test_to_gemini_response_custom_mime(self):
        """TemplateResponse with custom MIME converts correctly."""
        response = TemplateResponse("data", mime_type="application/json")
        gemini_response = response.to_gemini_response()

        assert gemini_response.meta == "application/json"


class TestLinkFilter:
    """Tests for the link filter."""

    def test_link_with_text(self):
        """Link with text generates proper format."""
        result = _link_filter("/about", "About Us")
        assert result == "=> /about About Us"

    def test_link_without_text(self):
        """Link without text generates URL only."""
        result = _link_filter("/page")
        assert result == "=> /page"

    def test_external_link(self):
        """External URLs work correctly."""
        result = _link_filter("gemini://example.com/", "Example")
        assert result == "=> gemini://example.com/ Example"

    def test_link_with_empty_text(self):
        """Link with empty text generates URL only."""
        result = _link_filter("/page", "")
        assert result == "=> /page"


class TestHeadingFilter:
    """Tests for the heading filter."""

    def test_heading_level_1(self):
        """Level 1 heading uses single #."""
        result = _heading_filter("Title", 1)
        assert result == "# Title"

    def test_heading_level_2(self):
        """Level 2 heading uses ##."""
        result = _heading_filter("Section", 2)
        assert result == "## Section"

    def test_heading_level_3(self):
        """Level 3 heading uses ###."""
        result = _heading_filter("Subsection", 3)
        assert result == "### Subsection"

    def test_heading_default_level(self):
        """Default heading level is 1."""
        result = _heading_filter("Title")
        assert result == "# Title"

    def test_heading_clamped_min(self):
        """Level 0 is clamped to 1."""
        result = _heading_filter("Title", 0)
        assert result == "# Title"

    def test_heading_clamped_negative(self):
        """Negative level is clamped to 1."""
        result = _heading_filter("Title", -1)
        assert result == "# Title"

    def test_heading_clamped_max(self):
        """Level 4+ is clamped to 3."""
        result = _heading_filter("Title", 4)
        assert result == "### Title"

    def test_heading_clamped_high(self):
        """High level is clamped to 3."""
        result = _heading_filter("Title", 10)
        assert result == "### Title"


class TestListFilter:
    """Tests for the list filter."""

    def test_single_item(self):
        """Single item list."""
        result = _list_filter(["Apple"])
        assert result == "* Apple"

    def test_multiple_items(self):
        """Multiple items joined by newlines."""
        result = _list_filter(["Apple", "Banana", "Cherry"])
        assert result == "* Apple\n* Banana\n* Cherry"

    def test_empty_list(self):
        """Empty list returns empty string."""
        result = _list_filter([])
        assert result == ""

    def test_list_with_special_chars(self):
        """List items can contain special characters."""
        result = _list_filter(["Item => link", "Item # heading"])
        assert "* Item => link" in result
        assert "* Item # heading" in result


class TestQuoteFilter:
    """Tests for the quote filter."""

    def test_single_line(self):
        """Single line quote."""
        result = _quote_filter("Hello world")
        assert result == "> Hello world"

    def test_multiline(self):
        """Multi-line quote."""
        result = _quote_filter("Line 1\nLine 2\nLine 3")
        assert result == "> Line 1\n> Line 2\n> Line 3"

    def test_empty_string(self):
        """Empty string quote."""
        result = _quote_filter("")
        assert result == "> "


class TestPreformatFilter:
    """Tests for the preformat filter."""

    def test_without_alt_text(self):
        """Preformat block without alt text."""
        result = _preformat_filter("def hello():\n    print('hi')")
        assert result == "```\ndef hello():\n    print('hi')\n```"

    def test_with_alt_text(self):
        """Preformat block with alt text."""
        result = _preformat_filter("print('hello')", "python")
        assert result == "```python\nprint('hello')\n```"

    def test_empty_alt_text(self):
        """Preformat block with empty alt text."""
        result = _preformat_filter("code", "")
        assert result == "```\ncode\n```"

    def test_multiline_code(self):
        """Preformat block with multiple lines."""
        code = "line1\nline2\nline3"
        result = _preformat_filter(code, "text")
        assert result == "```text\nline1\nline2\nline3\n```"


class TestGemtextEnvironment:
    """Tests for GemtextEnvironment class."""

    def test_filters_registered(self, tmp_path):
        """All Gemtext filters are registered."""
        env = GemtextEnvironment(tmp_path)

        assert "link" in env.filters
        assert "heading" in env.filters
        assert "list" in env.filters
        assert "quote" in env.filters
        assert "preformat" in env.filters

    def test_autoescape_disabled(self, tmp_path):
        """Autoescaping is disabled."""
        env = GemtextEnvironment(tmp_path)
        assert env.autoescape is False

    def test_trim_blocks_enabled(self, tmp_path):
        """trim_blocks is enabled."""
        env = GemtextEnvironment(tmp_path)
        assert env.trim_blocks is True

    def test_lstrip_blocks_enabled(self, tmp_path):
        """lstrip_blocks is enabled."""
        env = GemtextEnvironment(tmp_path)
        assert env.lstrip_blocks is True


class TestTemplateEngine:
    """Tests for TemplateEngine class."""

    def test_init_validates_directory(self, tmp_path):
        """Constructor validates templates directory exists."""
        nonexistent = tmp_path / "nonexistent"

        with pytest.raises(ValueError, match="does not exist"):
            TemplateEngine(nonexistent)

    def test_render_basic(self, tmp_path):
        """Basic template rendering."""
        templates = tmp_path / "templates"
        templates.mkdir()
        (templates / "page.gmi").write_text("# {{ title }}")

        engine = TemplateEngine(templates)
        response = engine.render("page.gmi", title="Hello")

        assert isinstance(response, TemplateResponse)
        assert response.content == "# Hello"

    def test_render_with_context(self, tmp_path):
        """Template rendering with multiple context variables."""
        templates = tmp_path / "templates"
        templates.mkdir()
        (templates / "page.gmi").write_text("# {{ title }}\nBy {{ author }}")

        engine = TemplateEngine(templates)
        response = engine.render("page.gmi", title="Blog Post", author="Alice")

        assert "# Blog Post" in response.content
        assert "By Alice" in response.content

    def test_render_with_filters(self, tmp_path):
        """Template rendering with Gemtext filters."""
        templates = tmp_path / "templates"
        templates.mkdir()
        (templates / "page.gmi").write_text(
            "{{ url | link(text) }}\n{{ items | list }}"
        )

        engine = TemplateEngine(templates)
        response = engine.render(
            "page.gmi", url="/about", text="About Us", items=["A", "B"]
        )

        assert "=> /about About Us" in response.content
        assert "* A\n* B" in response.content

    def test_render_with_heading_filter(self, tmp_path):
        """Template rendering with heading filter."""
        templates = tmp_path / "templates"
        templates.mkdir()
        (templates / "page.gmi").write_text("{{ title | heading(2) }}")

        engine = TemplateEngine(templates)
        response = engine.render("page.gmi", title="Section")

        assert response.content == "## Section"

    def test_render_with_quote_filter(self, tmp_path):
        """Template rendering with quote filter."""
        templates = tmp_path / "templates"
        templates.mkdir()
        (templates / "page.gmi").write_text("{{ text | quote }}")

        engine = TemplateEngine(templates)
        response = engine.render("page.gmi", text="Important")

        assert response.content == "> Important"

    def test_render_with_preformat_filter(self, tmp_path):
        """Template rendering with preformat filter."""
        templates = tmp_path / "templates"
        templates.mkdir()
        (templates / "page.gmi").write_text("{{ code | preformat(lang) }}")

        engine = TemplateEngine(templates)
        response = engine.render("page.gmi", code="print('hi')", lang="python")

        assert "```python" in response.content
        assert "print('hi')" in response.content

    def test_render_string(self, tmp_path):
        """Template rendering from string."""
        templates = tmp_path / "templates"
        templates.mkdir()

        engine = TemplateEngine(templates)
        result = engine.render_string("# {{ name }}", name="World")

        assert result == "# World"

    def test_render_string_with_filters(self, tmp_path):
        """String template with filters."""
        templates = tmp_path / "templates"
        templates.mkdir()

        engine = TemplateEngine(templates)
        result = engine.render_string("{{ 'Hello' | quote }}")

        assert result == "> Hello"

    def test_render_string_complex(self, tmp_path):
        """Complex string template."""
        templates = tmp_path / "templates"
        templates.mkdir()

        engine = TemplateEngine(templates)
        result = engine.render_string(
            "{{ title | heading(1) }}\n{{ '/about' | link('About') }}",
            title="Welcome",
        )

        assert "# Welcome" in result
        assert "=> /about About" in result


class TestTemplatingIntegration:
    """Integration tests for templating with the app."""

    def test_app_template_method(self, tmp_path):
        """app.template() renders and returns TemplateResponse."""
        templates = tmp_path / "templates"
        templates.mkdir()
        (templates / "home.gmi").write_text("# {{ message }}")

        app = Xitzin(templates_dir=templates)

        @app.gemini("/")
        def home(request):
            return app.template("home.gmi", message="Welcome")

        client = TestClient(app)
        response = client.get("/")

        assert response.is_success
        assert "# Welcome" in response.body

    def test_template_with_request_data(self, tmp_path):
        """Template can use request data."""
        templates = tmp_path / "templates"
        templates.mkdir()
        (templates / "user.gmi").write_text("# User: {{ username }}")

        app = Xitzin(templates_dir=templates)

        @app.gemini("/user/{username}")
        def user(request, username: str):
            return app.template("user.gmi", username=username)

        client = TestClient(app)
        response = client.get("/user/alice")

        assert response.is_success
        assert "# User: alice" in response.body

    def test_template_with_app_state(self, tmp_path):
        """Template can use app state."""
        templates = tmp_path / "templates"
        templates.mkdir()
        (templates / "info.gmi").write_text("# {{ title }} v{{ version }}")

        app = Xitzin(title="My App", version="1.0", templates_dir=templates)

        @app.gemini("/")
        def home(request):
            return app.template(
                "info.gmi",
                title=request.app.title,
                version=request.app.version,
            )

        client = TestClient(app)
        response = client.get("/")

        assert "# My App v1.0" in response.body
