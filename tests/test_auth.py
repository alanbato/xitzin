"""Tests for xitzin.auth module."""

import pytest
from nauyaca.protocol.request import GeminiRequest

from xitzin import Request, Xitzin
from xitzin.auth import (
    CertificateIdentity,
    get_identity,
    optional_certificate,
    require_certificate,
    require_fingerprint,
)
from xitzin.exceptions import CertificateNotAuthorized, CertificateRequired
from xitzin.testing import TestClient


class TestCertificateIdentity:
    """Tests for CertificateIdentity dataclass."""

    def test_fingerprint_stored(self):
        """Fingerprint is stored correctly."""
        identity = CertificateIdentity(fingerprint="abc123def456")
        assert identity.fingerprint == "abc123def456"

    def test_cert_optional(self):
        """Certificate is optional."""
        identity = CertificateIdentity(fingerprint="abc123")
        assert identity.cert is None

    def test_short_id(self):
        """short_id returns first 16 characters."""
        identity = CertificateIdentity(
            fingerprint="1234567890abcdef1234567890abcdef"
        )
        assert identity.short_id == "1234567890abcdef"

    def test_short_id_short_fingerprint(self):
        """short_id works with shorter fingerprints."""
        identity = CertificateIdentity(fingerprint="abc123")
        assert identity.short_id == "abc123"

    def test_str_representation(self):
        """str() shows short ID."""
        identity = CertificateIdentity(
            fingerprint="1234567890abcdef1234567890abcdef"
        )
        result = str(identity)
        assert "CertIdentity(" in result
        assert "1234567890abcdef" in result
        assert "..." in result


class TestGetIdentity:
    """Tests for get_identity function."""

    def test_returns_identity_when_cert_present(self):
        """Returns CertificateIdentity when certificate provided."""
        raw = GeminiRequest.from_line("gemini://test/")
        raw.client_cert_fingerprint = "abc123def456"
        request = Request(raw)

        identity = get_identity(request)

        assert identity is not None
        assert identity.fingerprint == "abc123def456"

    def test_returns_none_when_no_cert(self):
        """Returns None when no certificate."""
        raw = GeminiRequest.from_line("gemini://test/")
        request = Request(raw)

        identity = get_identity(request)

        assert identity is None

    def test_includes_cert_object(self):
        """Identity includes cert object if available."""
        raw = GeminiRequest.from_line("gemini://test/")
        raw.client_cert_fingerprint = "abc123"
        raw.client_cert = None  # Normally would be a Certificate object
        request = Request(raw)

        identity = get_identity(request)

        assert identity is not None
        assert identity.cert is None


class TestRequireCertificate:
    """Tests for @require_certificate decorator."""

    def test_raises_when_no_cert(self):
        """Raises CertificateRequired when no certificate."""

        @require_certificate
        def protected(request: Request):
            return "secret"

        raw = GeminiRequest.from_line("gemini://test/")
        request = Request(raw)

        with pytest.raises(CertificateRequired):
            protected(request)

    def test_allows_when_cert_present(self):
        """Allows access when certificate present."""

        @require_certificate
        def protected(request: Request):
            return "secret"

        raw = GeminiRequest.from_line("gemini://test/")
        raw.client_cert_fingerprint = "abc123"
        request = Request(raw)

        result = protected(request)
        assert result == "secret"

    def test_preserves_function_name(self):
        """Decorator preserves function name."""

        @require_certificate
        def my_handler(request: Request):
            pass

        assert my_handler.__name__ == "my_handler"

    def test_passes_args_and_kwargs(self):
        """Decorator passes additional arguments."""

        @require_certificate
        def handler(request: Request, user_id: int, name: str = "default"):
            return f"{user_id}:{name}"

        raw = GeminiRequest.from_line("gemini://test/")
        raw.client_cert_fingerprint = "abc123"
        request = Request(raw)

        result = handler(request, 42, name="alice")
        assert result == "42:alice"

    def test_exception_message(self):
        """CertificateRequired has correct message."""

        @require_certificate
        def protected(request: Request):
            return "secret"

        raw = GeminiRequest.from_line("gemini://test/")
        request = Request(raw)

        with pytest.raises(CertificateRequired) as exc_info:
            protected(request)

        assert exc_info.value.status_code == 60


class TestRequireFingerprint:
    """Tests for @require_fingerprint decorator."""

    def test_raises_when_no_cert(self):
        """Raises CertificateRequired when no certificate."""

        @require_fingerprint("allowed_fp")
        def protected(request: Request):
            return "secret"

        raw = GeminiRequest.from_line("gemini://test/")
        request = Request(raw)

        with pytest.raises(CertificateRequired):
            protected(request)

    def test_raises_when_not_authorized(self):
        """Raises CertificateNotAuthorized when fingerprint not in list."""

        @require_fingerprint("allowed_fp")
        def protected(request: Request):
            return "secret"

        raw = GeminiRequest.from_line("gemini://test/")
        raw.client_cert_fingerprint = "other_fp"
        request = Request(raw)

        with pytest.raises(CertificateNotAuthorized):
            protected(request)

    def test_allows_authorized_fingerprint(self):
        """Allows access when fingerprint is in allowed list."""

        @require_fingerprint("allowed1", "allowed2")
        def protected(request: Request):
            return "secret"

        raw = GeminiRequest.from_line("gemini://test/")
        raw.client_cert_fingerprint = "allowed2"
        request = Request(raw)

        result = protected(request)
        assert result == "secret"

    def test_multiple_allowed_fingerprints(self):
        """Multiple fingerprints can be allowed."""

        @require_fingerprint("fp1", "fp2", "fp3")
        def protected(request: Request):
            return "ok"

        raw = GeminiRequest.from_line("gemini://test/")

        for fp in ["fp1", "fp2", "fp3"]:
            raw.client_cert_fingerprint = fp
            request = Request(raw)
            assert protected(request) == "ok"

    def test_preserves_function_name(self):
        """Decorator preserves function name."""

        @require_fingerprint("fp1")
        def my_handler(request: Request):
            pass

        assert my_handler.__name__ == "my_handler"

    def test_not_authorized_status_code(self):
        """CertificateNotAuthorized has status 61."""

        @require_fingerprint("allowed_fp")
        def protected(request: Request):
            return "secret"

        raw = GeminiRequest.from_line("gemini://test/")
        raw.client_cert_fingerprint = "wrong_fp"
        request = Request(raw)

        with pytest.raises(CertificateNotAuthorized) as exc_info:
            protected(request)

        assert exc_info.value.status_code == 61


class TestOptionalCertificate:
    """Tests for @optional_certificate decorator."""

    def test_sets_identity_when_cert_present(self):
        """Sets request.state.identity when certificate present."""

        @optional_certificate
        def handler(request: Request):
            return request.state.identity

        raw = GeminiRequest.from_line("gemini://test/")
        raw.client_cert_fingerprint = "abc123"
        request = Request(raw)

        identity = handler(request)

        assert identity is not None
        assert identity.fingerprint == "abc123"

    def test_sets_none_when_no_cert(self):
        """Sets request.state.identity to None when no certificate."""

        @optional_certificate
        def handler(request: Request):
            return request.state.identity

        raw = GeminiRequest.from_line("gemini://test/")
        request = Request(raw)

        identity = handler(request)

        assert identity is None

    def test_preserves_function_name(self):
        """Decorator preserves function name."""

        @optional_certificate
        def my_handler(request: Request):
            pass

        assert my_handler.__name__ == "my_handler"

    def test_does_not_raise(self):
        """Does not raise exception without certificate."""

        @optional_certificate
        def handler(request: Request):
            return "ok"

        raw = GeminiRequest.from_line("gemini://test/")
        request = Request(raw)

        result = handler(request)
        assert result == "ok"


class TestAuthIntegration:
    """Integration tests for auth with the app."""

    def test_require_certificate_in_app(self):
        """@require_certificate works with app routes."""
        app = Xitzin()

        @app.gemini("/admin")
        @require_certificate
        def admin(request: Request):
            return "# Admin Panel"

        client = TestClient(app)

        # Without certificate
        response = client.get("/admin")
        assert response.status == 60

        # With certificate
        auth_client = client.with_certificate("valid_cert")
        response = auth_client.get("/admin")
        assert response.is_success

    def test_require_fingerprint_in_app(self):
        """@require_fingerprint works with app routes."""
        app = Xitzin()

        @app.gemini("/admin")
        @require_fingerprint("admin_cert")
        def admin(request: Request):
            return "# Admin Panel"

        client = TestClient(app)

        # Without certificate
        response = client.get("/admin")
        assert response.status == 60

        # With wrong certificate
        wrong_client = client.with_certificate("wrong_cert")
        response = wrong_client.get("/admin")
        assert response.status == 61

        # With correct certificate
        admin_client = client.with_certificate("admin_cert")
        response = admin_client.get("/admin")
        assert response.is_success

    def test_optional_certificate_in_app(self):
        """@optional_certificate works with app routes."""
        app = Xitzin()

        @app.gemini("/profile")
        @optional_certificate
        def profile(request: Request):
            identity = request.state.identity
            if identity:
                return f"# Welcome, {identity.short_id}"
            return "# Welcome, guest"

        client = TestClient(app)

        # Without certificate
        response = client.get("/profile")
        assert response.is_success
        assert "guest" in response.body

        # With certificate
        auth_client = client.with_certificate("user123")
        response = auth_client.get("/profile")
        assert response.is_success
        assert "user123" in response.body

    def test_combined_decorators(self):
        """Multiple auth decorators can be combined."""
        app = Xitzin()

        @app.gemini("/special")
        @require_fingerprint("special_user")
        def special(request: Request):
            return "# Special Access"

        client = TestClient(app)

        # Regular user with cert
        user_client = client.with_certificate("regular_user")
        response = user_client.get("/special")
        assert response.status == 61

        # Special user
        special_client = client.with_certificate("special_user")
        response = special_client.get("/special")
        assert response.is_success
