"""Gemini exception classes for error responses.

These exceptions can be raised in handlers to return specific Gemini status codes.
"""

from __future__ import annotations


class GeminiException(Exception):
    """Base exception for Gemini error responses.

    Subclasses define specific status codes for different error types.
    Raise these in handlers to return the appropriate Gemini status.

    Example:
        @app.gemini("/page/{page_id}")
        def get_page(request: Request, page_id: int):
            page = db.get(page_id)
            if not page:
                raise NotFound(f"Page {page_id} not found")
            return page.content
    """

    status_code: int = 50
    default_message: str = "Permanent failure"

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.default_message
        super().__init__(self.message)


# Input required (1x)
class InputRequired(GeminiException):
    """Request requires user input (status 10)."""

    status_code = 10
    default_message = "Input required"


class SensitiveInputRequired(GeminiException):
    """Request requires sensitive user input (status 11)."""

    status_code = 11
    default_message = "Sensitive input required"


# Temporary failures (4x)
class TemporaryFailure(GeminiException):
    """Temporary failure - client may retry (status 40)."""

    status_code = 40
    default_message = "Temporary failure"


class ServerUnavailable(GeminiException):
    """Server unavailable due to maintenance or overload (status 41)."""

    status_code = 41
    default_message = "Server unavailable"


class CGIError(GeminiException):
    """CGI or similar process error (status 42)."""

    status_code = 42
    default_message = "CGI error"


class ProxyError(GeminiException):
    """Proxy request failed (status 43)."""

    status_code = 43
    default_message = "Proxy error"


class SlowDown(GeminiException):
    """Rate limiting - client should slow down (status 44)."""

    status_code = 44
    default_message = "Slow down"


# Permanent failures (5x)
class PermanentFailure(GeminiException):
    """Permanent failure - client should not retry (status 50)."""

    status_code = 50
    default_message = "Permanent failure"


class NotFound(GeminiException):
    """Resource not found (status 51)."""

    status_code = 51
    default_message = "Not found"


class Gone(GeminiException):
    """Resource permanently removed (status 52)."""

    status_code = 52
    default_message = "Gone"


class ProxyRequestRefused(GeminiException):
    """Proxy request refused (status 53)."""

    status_code = 53
    default_message = "Proxy request refused"


class BadRequest(GeminiException):
    """Malformed request (status 59)."""

    status_code = 59
    default_message = "Bad request"


# Client certificate errors (6x)
class CertificateRequired(GeminiException):
    """Client certificate required (status 60)."""

    status_code = 60
    default_message = "Client certificate required"


class CertificateNotAuthorized(GeminiException):
    """Certificate not authorized for this resource (status 61)."""

    status_code = 61
    default_message = "Certificate not authorized"


class CertificateNotValid(GeminiException):
    """Certificate is not valid (status 62)."""

    status_code = 62
    default_message = "Certificate not valid"


# Application configuration errors
class TaskConfigurationError(Exception):
    """Raised when a background task is misconfigured.

    This typically indicates mutually exclusive parameters were provided,
    or a required optional dependency is missing.

    Example:
        @app.task()  # Error: neither interval nor cron provided
        def my_task():
            pass

        @app.task(interval="1h", cron="* * * * *")  # Error: both provided
        def my_task():
            pass
    """
