"""Xitzin - A Gemini Application Framework.

Xitzin is a framework for building Gemini protocol applications.
It uses Nauyaca for protocol communication and Pydantic for data validation.

Example:
    from xitzin import Xitzin, Request

    app = Xitzin()

    @app.gemini("/")
    def home(request: Request):
        return "# Welcome to Gemini!"

    @app.gemini("/user/{username}")
    def profile(request: Request, username: str):
        return f"# {username}'s Profile"

    if __name__ == "__main__":
        app.run()
"""

from .application import Xitzin
from .exceptions import (
    BadRequest,
    CertificateNotAuthorized,
    CertificateNotValid,
    CertificateRequired,
    CGIError,
    GeminiException,
    Gone,
    InputRequired,
    NotFound,
    PermanentFailure,
    ProxyError,
    ProxyRequestRefused,
    SensitiveInputRequired,
    ServerUnavailable,
    SlowDown,
    TemporaryFailure,
)
from .requests import Request
from .responses import Input, Redirect, Response

__all__ = [
    # Main application
    "Xitzin",
    # Request/Response
    "Request",
    "Response",
    "Input",
    "Redirect",
    # Exceptions
    "GeminiException",
    "InputRequired",
    "SensitiveInputRequired",
    "TemporaryFailure",
    "ServerUnavailable",
    "CGIError",
    "ProxyError",
    "SlowDown",
    "PermanentFailure",
    "NotFound",
    "Gone",
    "ProxyRequestRefused",
    "BadRequest",
    "CertificateRequired",
    "CertificateNotAuthorized",
    "CertificateNotValid",
]

__version__ = "0.1.0"
