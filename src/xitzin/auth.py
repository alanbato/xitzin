"""Certificate authentication helpers.

This module provides decorators and utilities for working with
Gemini client certificate authentication.
"""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable

from .exceptions import CertificateNotAuthorized, CertificateRequired

if TYPE_CHECKING:
    from cryptography.x509 import Certificate

    from .requests import Request


@dataclass
class CertificateIdentity:
    """Represents a user identity based on their client certificate.

    Example:
        identity = get_identity(request)
        if identity:
            print(f"User: {identity.short_id}")
    """

    fingerprint: str
    """SHA-256 fingerprint of the certificate."""

    cert: "Certificate | None" = None
    """The raw certificate object (if available)."""

    @property
    def short_id(self) -> str:
        """Short identifier suitable for display (first 16 chars)."""
        return self.fingerprint[:16]

    def __str__(self) -> str:
        return f"CertIdentity({self.short_id}...)"


def get_identity(request: "Request") -> CertificateIdentity | None:
    """Get the certificate-based identity from a request.

    Args:
        request: The current request.

    Returns:
        CertificateIdentity if a client certificate was provided, None otherwise.

    Example:
        @app.gemini("/whoami")
        def whoami(request: Request):
            identity = get_identity(request)
            if identity:
                return f"# Your ID: {identity.short_id}"
            return "# You are anonymous"
    """
    if request.client_cert_fingerprint:
        return CertificateIdentity(
            fingerprint=request.client_cert_fingerprint,
            cert=request.client_cert,
        )
    return None


def require_certificate(handler: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator that requires a valid client certificate.

    If no certificate is provided, returns status 60 (certificate required).

    Example:
        @app.gemini("/admin")
        @require_certificate
        def admin_panel(request: Request):
            return "# Admin Panel"
    """

    @wraps(handler)
    def wrapper(request: "Request", *args: Any, **kwargs: Any) -> Any:
        if not request.client_cert_fingerprint:
            raise CertificateRequired("Client certificate required")
        return handler(request, *args, **kwargs)

    return wrapper


def _timing_safe_fingerprint_check(fingerprint: str, allowed: list[str]) -> bool:
    """Check if fingerprint matches any allowed value using timing-safe comparison.

    This prevents timing attacks that could reveal valid fingerprints.

    Args:
        fingerprint: The fingerprint to check.
        allowed: List of allowed fingerprints.

    Returns:
        True if fingerprint matches any allowed value.
    """
    # Encode once for comparison
    fp_bytes = fingerprint.encode("utf-8")

    for allowed_fp in allowed:
        if hmac.compare_digest(fp_bytes, allowed_fp.encode("utf-8")):
            return True
    return False


def require_fingerprint(
    *allowed_fingerprints: str,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator factory that requires specific certificate fingerprints.

    If the client certificate fingerprint is not in the allowed list,
    returns status 61 (certificate not authorized).

    Uses timing-safe comparison to prevent fingerprint enumeration attacks.

    Args:
        *allowed_fingerprints: SHA-256 fingerprints that are allowed.

    Example:
        ADMIN_CERTS = [
            "abc123...",  # Alice's certificate
            "def456...",  # Bob's certificate
        ]

        @app.gemini("/admin")
        @require_fingerprint(*ADMIN_CERTS)
        def admin_panel(request: Request):
            return "# Admin Panel"
    """
    allowed_list = list(allowed_fingerprints)

    def decorator(handler: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(handler)
        def wrapper(request: "Request", *args: Any, **kwargs: Any) -> Any:
            if not request.client_cert_fingerprint:
                raise CertificateRequired("Client certificate required")

            if not _timing_safe_fingerprint_check(
                request.client_cert_fingerprint, allowed_list
            ):
                raise CertificateNotAuthorized("Certificate not authorized")

            return handler(request, *args, **kwargs)

        return wrapper

    return decorator


def optional_certificate(handler: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator that makes certificate identity available but not required.

    Sets request.state.identity to CertificateIdentity or None.

    Example:
        @app.gemini("/profile")
        @optional_certificate
        def profile(request: Request):
            identity = request.state.identity
            if identity:
                return f"# Welcome back, {identity.short_id}"
            return "# Welcome, anonymous visitor"
    """

    @wraps(handler)
    def wrapper(request: "Request", *args: Any, **kwargs: Any) -> Any:
        request.state.identity = get_identity(request)
        return handler(request, *args, **kwargs)

    return wrapper
