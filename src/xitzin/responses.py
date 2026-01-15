"""Response classes for Xitzin handlers.

These classes provide a convenient way to return different types of Gemini responses.
Handlers can return these objects, and Xitzin will convert them to GeminiResponse.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from nauyaca.protocol.response import GeminiResponse
from nauyaca.protocol.status import StatusCode

if TYPE_CHECKING:
    from .application import Xitzin


class ResponseConvertible(Protocol):
    """Protocol for objects that can be converted to GeminiResponse."""

    def to_gemini_response(self) -> GeminiResponse: ...


@dataclass
class Response:
    """Success response with a body.

    Example:
        @app.gemini("/")
        def home(request: Request):
            return Response("# Welcome!", mime_type="text/gemini")
    """

    body: str
    mime_type: str = "text/gemini"

    def to_gemini_response(self) -> GeminiResponse:
        return GeminiResponse(
            status=StatusCode.SUCCESS,
            meta=self.mime_type,
            body=self.body,
        )


@dataclass
class Input:
    """Request input from the client (status 10/11).

    When returned from a handler, the client will prompt the user for input
    and re-request the same URL with the input as a query string.

    Example:
        @app.gemini("/search")
        def search(request: Request):
            if not request.query:
                return Input("Enter your search query:")
            return f"# Results for: {request.query}"
    """

    prompt: str
    sensitive: bool = False

    def to_gemini_response(self) -> GeminiResponse:
        status = StatusCode.SENSITIVE_INPUT if self.sensitive else StatusCode.INPUT
        return GeminiResponse(status=status, meta=self.prompt)


@dataclass
class Redirect:
    """Redirect to another URL (status 30/31).

    Example:
        @app.gemini("/old-page")
        def old_page(request: Request):
            return Redirect("/new-page", permanent=True)
    """

    url: str
    permanent: bool = False

    def to_gemini_response(self) -> GeminiResponse:
        status = (
            StatusCode.REDIRECT_PERMANENT
            if self.permanent
            else StatusCode.REDIRECT_TEMPORARY
        )
        return GeminiResponse(status=status, meta=self.url)


@dataclass
class Link:
    """Build Gemtext link lines.

    Generates link lines in the format: => URL [LABEL]

    Example:
        # Basic link
        link = Link("/about", "About Us")
        str(link)  # "=> /about About Us"

        # Link without label
        link = Link("/about")
        str(link)  # "=> /about"

        # Using with app.reverse()
        link = Link(app.reverse("user_profile", username="alice"), "Alice's Profile")
        str(link)  # "=> /user/alice Alice's Profile"

        # Using to_route() classmethod
        link = Link.to_route(
            app, "user_profile", username="alice", label="Alice's Profile"
        )
        str(link)  # "=> /user/alice Alice's Profile"
    """

    url: str
    label: str | None = None

    def to_gemtext(self) -> str:
        """Generate Gemtext link line."""
        if self.label:
            return f"=> {self.url} {self.label}"
        return f"=> {self.url}"

    @classmethod
    def to_route(
        cls,
        app: "Xitzin",
        name: str,
        *,
        label: str | None = None,
        **params: Any,
    ) -> "Link":
        """Create a link to a named route.

        Args:
            app: Xitzin application instance.
            name: Route name.
            label: Optional link label text.
            **params: Path parameters for URL building.

        Returns:
            Link instance pointing to the route.

        Example:
            link = Link.to_route(app, "user_profile", username="alice", label="Profile")
            str(link)  # "=> /user/alice Profile"
        """
        url = app.reverse(name, **params)
        return cls(url, label)

    def __str__(self) -> str:
        """Return Gemtext representation."""
        return self.to_gemtext()


def convert_response(result: Any, request: Any = None) -> GeminiResponse:
    """Convert a handler return value to a GeminiResponse.

    Handlers can return:
    - str: Converted to success response with text/gemini MIME type
    - Response, Input, Redirect: Converted via to_gemini_response()
    - GeminiResponse: Returned as-is
    - tuple: (body, status) or (body, status, meta)
    - None: Empty success response

    Args:
        result: The return value from a handler.
        request: The current request (Request or TitanRequest, for URL tracking).

    Returns:
        A GeminiResponse instance.

    Raises:
        TypeError: If the result cannot be converted.
    """
    url = request._raw_request.normalized_url if request else None

    # Already a GeminiResponse
    if isinstance(result, GeminiResponse):
        return result

    # Objects with to_gemini_response method
    if hasattr(result, "to_gemini_response"):
        response = result.to_gemini_response()
        # Add URL tracking if not present
        if response.url is None and url:
            return GeminiResponse(
                status=response.status,
                meta=response.meta,
                body=response.body,
                url=url,
            )
        return response

    # Plain string -> success with text/gemini
    if isinstance(result, str):
        return GeminiResponse(
            status=StatusCode.SUCCESS,
            meta="text/gemini",
            body=result,
            url=url,
        )

    # Tuple: (body, status) or (body, status, meta)
    if isinstance(result, tuple):
        if len(result) == 2:
            body, status = result
            meta = "text/gemini" if status == StatusCode.SUCCESS else ""
        elif len(result) == 3:
            body, status, meta = result
        else:
            msg = f"Tuple must have 2 or 3 elements, got {len(result)}"
            raise TypeError(msg)

        return GeminiResponse(
            status=status,
            meta=meta,
            body=body if 20 <= status < 30 else None,
            url=url,
        )

    # None -> empty success
    if result is None:
        return GeminiResponse(
            status=StatusCode.SUCCESS,
            meta="text/gemini",
            body="",
            url=url,
        )

    msg = f"Cannot convert {type(result).__name__} to GeminiResponse"
    raise TypeError(msg)
