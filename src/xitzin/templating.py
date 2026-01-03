"""Gemtext template engine using Jinja2.

This module provides a Jinja2-based template engine configured for
rendering Gemtext (.gmi) templates.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from jinja2 import Environment, FileSystemLoader

if TYPE_CHECKING:
    from .application import Xitzin

from nauyaca.protocol.response import GeminiResponse
from nauyaca.protocol.status import StatusCode


class TemplateResponse:
    """Response from a rendered template.

    Can be returned from handlers and will be converted to a GeminiResponse.
    """

    def __init__(self, content: str, mime_type: str = "text/gemini") -> None:
        self.content = content
        self.mime_type = mime_type

    def to_gemini_response(self) -> GeminiResponse:
        return GeminiResponse(
            status=StatusCode.SUCCESS,
            meta=self.mime_type,
            body=self.content,
        )


def _link_filter(url: str, text: str | None = None) -> str:
    """Generate a Gemtext link line.

    Args:
        url: The URL to link to.
        text: Optional link text.

    Returns:
        A Gemtext link line.

    Example:
        {{ "/about" | link("About Us") }}
        => /about About Us
    """
    if text:
        return f"=> {url} {text}"
    return f"=> {url}"


def _heading_filter(text: str, level: int = 1) -> str:
    """Generate a Gemtext heading.

    Args:
        text: The heading text.
        level: Heading level (1-3).

    Returns:
        A Gemtext heading line.

    Example:
        {{ "Welcome" | heading(1) }}
        # Welcome
    """
    prefix = "#" * min(max(level, 1), 3)
    return f"{prefix} {text}"


def _list_filter(items: list[str]) -> str:
    """Generate a Gemtext list.

    Args:
        items: List of items.

    Returns:
        Gemtext list lines joined by newlines.

    Example:
        {{ ["Apple", "Banana", "Cherry"] | list }}
        * Apple
        * Banana
        * Cherry
    """
    return "\n".join(f"* {item}" for item in items)


def _quote_filter(text: str) -> str:
    """Generate a Gemtext blockquote.

    Args:
        text: The text to quote. Multi-line text is supported.

    Returns:
        Gemtext quote lines.

    Example:
        {{ "Hello world" | quote }}
        > Hello world
    """
    lines = text.split("\n")
    return "\n".join(f"> {line}" for line in lines)


def _preformat_filter(text: str, alt_text: str = "") -> str:
    """Generate a Gemtext preformatted block.

    Args:
        text: The preformatted text.
        alt_text: Optional alt text for the preformat toggle.

    Returns:
        Gemtext preformatted block.

    Example:
        {{ code | preformat("python") }}
        ```python
        def hello():
            print("Hello!")
        ```
    """
    return f"```{alt_text}\n{text}\n```"


class GemtextEnvironment(Environment):
    """Jinja2 environment configured for Gemtext templates.

    This environment:
    - Disables HTML autoescaping (not needed for Gemtext)
    - Trims blocks and strips leading whitespace
    - Adds Gemtext-specific filters
    - Provides a `reverse()` global function for URL reversing (when app is provided)
    """

    def __init__(self, templates_dir: Path, app: Xitzin | None = None) -> None:
        loader = FileSystemLoader(str(templates_dir))
        super().__init__(
            loader=loader,
            autoescape=False,  # Gemtext doesn't need HTML escaping
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Register Gemtext-specific filters
        self.filters["link"] = _link_filter
        self.filters["heading"] = _heading_filter
        self.filters["list"] = _list_filter
        self.filters["quote"] = _quote_filter
        self.filters["preformat"] = _preformat_filter

        # Register reverse() global if app is provided
        if app is not None:
            self.globals["reverse"] = app.reverse


class TemplateEngine:
    """High-level template rendering interface.

    Example:
        engine = TemplateEngine(Path("templates"))
        response = engine.render("page.gmi", title="Welcome", items=["a", "b"])

    With app integration (enables reverse() in templates):
        engine = TemplateEngine(Path("templates"), app=app)
        # In templates:
        # {{ reverse("user_profile", username="alice") | link("Profile") }}
    """

    def __init__(self, templates_dir: Path, app: Xitzin | None = None) -> None:
        """Create a template engine.

        Args:
            templates_dir: Directory containing template files.
            app: Optional Xitzin app instance for URL reversing in templates.

        Raises:
            ValueError: If templates_dir doesn't exist.
        """
        if not templates_dir.exists():
            msg = f"Templates directory does not exist: {templates_dir}"
            raise ValueError(msg)

        self._env = GemtextEnvironment(templates_dir, app=app)

    def render(self, template_name: str, **context: Any) -> TemplateResponse:
        """Render a template file.

        Args:
            template_name: Name of the template file (e.g., "page.gmi").
            **context: Variables to pass to the template.

        Returns:
            TemplateResponse that can be returned from handlers.

        Example:
            return engine.render("user.gmi", username="alice", posts=posts)
        """
        template = self._env.get_template(template_name)
        content = template.render(**context)
        return TemplateResponse(content)

    def render_string(self, source: str, **context: Any) -> str:
        """Render a template from a string.

        Args:
            source: Template source string.
            **context: Variables to pass to the template.

        Returns:
            Rendered string.

        Example:
            result = engine.render_string("# {{ title }}", title="Hello")
        """
        template = self._env.from_string(source)
        return template.render(**context)
