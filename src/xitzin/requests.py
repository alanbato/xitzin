"""Request wrapper for Xitzin handlers.

Provides a convenient interface to the underlying Nauyaca GeminiRequest.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import unquote_plus

from nauyaca.protocol.request import GeminiRequest
from nauyaca.protocol.request import TitanRequest as NauyacaTitanRequest

if TYPE_CHECKING:
    from cryptography.x509 import Certificate

    from .application import Xitzin


class RequestState:
    """Arbitrary state storage for a request.

    Middleware and handlers can store arbitrary data here.

    Example:
        request.state.user = get_current_user()
        request.state.start_time = time.time()
    """

    def __setattr__(self, name: str, value: Any) -> None:
        self.__dict__[name] = value

    def __getattr__(self, name: str) -> Any:
        try:
            return self.__dict__[name]
        except KeyError:
            raise AttributeError(f"'RequestState' has no attribute '{name}'") from None

    def __delattr__(self, name: str) -> None:
        try:
            del self.__dict__[name]
        except KeyError:
            raise AttributeError(f"'RequestState' has no attribute '{name}'") from None


class Request:
    """Wraps a Nauyaca GeminiRequest with convenient accessors.

    Handlers receive this object as their first argument.

    Example:
        @app.gemini("/user/{username}")
        def profile(request: Request, username: str):
            cert_id = request.client_cert_fingerprint
            viewer = cert_id[:16] if cert_id else 'anonymous'
            return f"# {username}'s Profile\\n\\nViewing as: {viewer}"

    Attributes:
        app: The Xitzin application instance.
        state: Arbitrary state storage for this request.
        path: The URL path component.
        query: The decoded query string (user input).
        raw_query: The raw (URL-encoded) query string.
        client_cert: The client's TLS certificate, if provided.
        client_cert_fingerprint: SHA-256 fingerprint of client certificate.
    """

    def __init__(self, raw_request: GeminiRequest, app: Xitzin | None = None) -> None:
        self._raw_request = raw_request
        self._app = app
        self._state = RequestState()

    @property
    def app(self) -> Xitzin:
        """The Xitzin application handling this request."""
        if self._app is None:
            msg = "Request is not bound to an application"
            raise RuntimeError(msg)
        return self._app

    @property
    def state(self) -> RequestState:
        """Arbitrary state storage for this request."""
        return self._state

    @property
    def path(self) -> str:
        """The URL path component."""
        return self._raw_request.path

    @property
    def raw_query(self) -> str:
        """The raw (URL-encoded) query string."""
        return self._raw_request.query

    @property
    def query(self) -> str:
        """The decoded query string.

        Gemini uses URL query strings for user input (status 10/11 flow).
        This property decodes the query string for convenient access.
        """
        if not self._raw_request.query:
            return ""
        return unquote_plus(self._raw_request.query)

    @property
    def url(self) -> str:
        """The full normalized URL."""
        return self._raw_request.normalized_url

    @property
    def raw_url(self) -> str:
        """The original URL from the request."""
        return self._raw_request.raw_url

    @property
    def hostname(self) -> str:
        """The server hostname from the URL."""
        return self._raw_request.hostname

    @property
    def port(self) -> int:
        """The server port from the URL."""
        return self._raw_request.port

    @property
    def client_cert(self) -> Certificate | None:
        """The client's TLS certificate, if provided."""
        return self._raw_request.client_cert

    @property
    def client_cert_fingerprint(self) -> str | None:
        """SHA-256 fingerprint of the client certificate."""
        return self._raw_request.client_cert_fingerprint

    @property
    def remote_addr(self) -> str | None:
        """The client's IP address, if available.

        Note: This property returns the client IP address if it was set
        by the server or middleware. In CGI context, this is passed to
        scripts via the REMOTE_ADDR environment variable.

        Returns:
            The client IP address string, or None if not available.
        """
        return getattr(self._raw_request, "remote_addr", None)

    def __repr__(self) -> str:
        return f"Request({self._raw_request.raw_url!r})"


class TitanRequest:
    """Wraps a Nauyaca TitanRequest for Titan upload handlers.

    Handlers receive this object as their first argument for @app.titan routes.

    Example:
        @app.titan("/upload/{filename}", auth_tokens=["secret"])
        def upload(request: TitanRequest, content: bytes,
                   mime_type: str, token: str | None, filename: str):
            if request.is_delete():
                return "# Deleted"
            Path(f"./uploads/{filename}").write_bytes(content)
            return "# Upload successful"

    Attributes:
        app: The Xitzin application instance.
        state: Arbitrary state storage for this request.
        path: The URL path component.
        content: The uploaded content bytes.
        mime_type: Content MIME type.
        token: Authentication token (if provided).
        size: Content size in bytes.
    """

    def __init__(
        self, raw_request: NauyacaTitanRequest, app: Xitzin | None = None
    ) -> None:
        self._raw_request = raw_request
        self._app = app
        self._state = RequestState()

    @property
    def app(self) -> Xitzin:
        """The Xitzin application handling this request."""
        if self._app is None:
            msg = "Request is not bound to an application"
            raise RuntimeError(msg)
        return self._app

    @property
    def state(self) -> RequestState:
        """Arbitrary state storage for this request."""
        return self._state

    @property
    def path(self) -> str:
        """The URL path component."""
        return self._raw_request.path

    @property
    def content(self) -> bytes:
        """The uploaded content bytes."""
        return self._raw_request.content

    @property
    def mime_type(self) -> str:
        """Content MIME type."""
        return self._raw_request.mime_type

    @property
    def token(self) -> str | None:
        """Authentication token (if provided)."""
        return self._raw_request.token

    @property
    def size(self) -> int:
        """Content size in bytes."""
        return self._raw_request.size

    def is_delete(self) -> bool:
        """Check if this is a delete request (zero-byte upload)."""
        return self._raw_request.is_delete()

    @property
    def hostname(self) -> str:
        """The server hostname from the URL."""
        return self._raw_request.hostname

    @property
    def port(self) -> int:
        """The server port from the URL."""
        return self._raw_request.port

    @property
    def client_cert(self) -> Certificate | None:
        """The client's TLS certificate, if provided."""
        return self._raw_request.client_cert

    @property
    def client_cert_fingerprint(self) -> str | None:
        """SHA-256 fingerprint of the client certificate."""
        return self._raw_request.client_cert_fingerprint

    @property
    def raw_url(self) -> str:
        """The original URL from the request."""
        return self._raw_request.raw_url

    def __repr__(self) -> str:
        return f"TitanRequest({self._raw_request.raw_url!r})"
