"""Xitzin - A Gemini Application Framework.

Xitzin is a framework for building Gemini protocol applications.
It uses Nauyaca for Gemini protocol communication.

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
from .cgi import CGIConfig, CGIHandler, CGIScript
from .middleware import VirtualHostMiddleware
from .scgi import SCGIApp, SCGIConfig, SCGIHandler
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
    TaskConfigurationError,
    TemporaryFailure,
)
from .requests import Request, TitanRequest
from .responses import Input, Link, Redirect, Response

__all__ = [
    # Main application
    "Xitzin",
    # Request/Response
    "Request",
    "TitanRequest",
    "Response",
    "Input",
    "Redirect",
    "Link",
    # Middleware
    "VirtualHostMiddleware",
    # CGI support
    "CGIConfig",
    "CGIHandler",
    "CGIScript",
    # SCGI support
    "SCGIApp",
    "SCGIConfig",
    "SCGIHandler",
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
    "TaskConfigurationError",
]

__version__ = "0.1.0"
