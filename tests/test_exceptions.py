"""Tests for xitzin.exceptions module."""

import pytest

from xitzin.exceptions import (
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


class TestGeminiException:
    """Tests for the base GeminiException class."""

    def test_default_message(self):
        """Exception uses default_message when no message provided."""
        exc = GeminiException()
        assert exc.message == "Permanent failure"
        assert exc.status_code == 50

    def test_custom_message(self):
        """Exception uses custom message when provided."""
        exc = GeminiException("Custom error")
        assert exc.message == "Custom error"

    def test_str_representation(self):
        """Exception string is the message."""
        exc = GeminiException("Test error")
        assert str(exc) == "Test error"

    def test_is_exception(self):
        """GeminiException is an Exception."""
        exc = GeminiException()
        assert isinstance(exc, Exception)


class TestInputExceptions:
    """Tests for input-related exceptions (1x status codes)."""

    def test_input_required(self):
        """InputRequired has status 10."""
        exc = InputRequired()
        assert exc.status_code == 10
        assert exc.message == "Input required"

    def test_input_required_custom_message(self):
        """InputRequired accepts custom message."""
        exc = InputRequired("Enter your name:")
        assert exc.status_code == 10
        assert exc.message == "Enter your name:"

    def test_sensitive_input_required(self):
        """SensitiveInputRequired has status 11."""
        exc = SensitiveInputRequired()
        assert exc.status_code == 11
        assert exc.message == "Sensitive input required"

    def test_sensitive_input_custom_message(self):
        """SensitiveInputRequired accepts custom message."""
        exc = SensitiveInputRequired("Enter password:")
        assert exc.message == "Enter password:"


class TestTemporaryFailureExceptions:
    """Tests for temporary failure exceptions (4x status codes)."""

    def test_temporary_failure(self):
        """TemporaryFailure has status 40."""
        exc = TemporaryFailure()
        assert exc.status_code == 40
        assert exc.message == "Temporary failure"

    def test_temporary_failure_custom_message(self):
        """TemporaryFailure accepts custom message."""
        exc = TemporaryFailure("Server is overloaded")
        assert exc.message == "Server is overloaded"

    def test_server_unavailable(self):
        """ServerUnavailable has status 41."""
        exc = ServerUnavailable()
        assert exc.status_code == 41
        assert exc.message == "Server unavailable"

    def test_cgi_error(self):
        """CGIError has status 42."""
        exc = CGIError()
        assert exc.status_code == 42
        assert exc.message == "CGI error"

    def test_proxy_error(self):
        """ProxyError has status 43."""
        exc = ProxyError()
        assert exc.status_code == 43
        assert exc.message == "Proxy error"

    def test_slow_down(self):
        """SlowDown has status 44."""
        exc = SlowDown()
        assert exc.status_code == 44
        assert exc.message == "Slow down"


class TestPermanentFailureExceptions:
    """Tests for permanent failure exceptions (5x status codes)."""

    def test_permanent_failure(self):
        """PermanentFailure has status 50."""
        exc = PermanentFailure()
        assert exc.status_code == 50
        assert exc.message == "Permanent failure"

    def test_not_found(self):
        """NotFound has status 51."""
        exc = NotFound()
        assert exc.status_code == 51
        assert exc.message == "Not found"

    def test_not_found_custom_message(self):
        """NotFound accepts custom message."""
        exc = NotFound("Page not found")
        assert exc.message == "Page not found"

    def test_gone(self):
        """Gone has status 52."""
        exc = Gone()
        assert exc.status_code == 52
        assert exc.message == "Gone"

    def test_proxy_request_refused(self):
        """ProxyRequestRefused has status 53."""
        exc = ProxyRequestRefused()
        assert exc.status_code == 53
        assert exc.message == "Proxy request refused"

    def test_bad_request(self):
        """BadRequest has status 59."""
        exc = BadRequest()
        assert exc.status_code == 59
        assert exc.message == "Bad request"


class TestCertificateExceptions:
    """Tests for certificate exceptions (6x status codes)."""

    def test_certificate_required(self):
        """CertificateRequired has status 60."""
        exc = CertificateRequired()
        assert exc.status_code == 60
        assert exc.message == "Client certificate required"

    def test_certificate_not_authorized(self):
        """CertificateNotAuthorized has status 61."""
        exc = CertificateNotAuthorized()
        assert exc.status_code == 61
        assert exc.message == "Certificate not authorized"

    def test_certificate_not_valid(self):
        """CertificateNotValid has status 62."""
        exc = CertificateNotValid()
        assert exc.status_code == 62
        assert exc.message == "Certificate not valid"


class TestExceptionInheritance:
    """Tests that all exceptions inherit from GeminiException."""

    @pytest.mark.parametrize(
        "exc_class",
        [
            InputRequired,
            SensitiveInputRequired,
            TemporaryFailure,
            ServerUnavailable,
            CGIError,
            ProxyError,
            SlowDown,
            PermanentFailure,
            NotFound,
            Gone,
            ProxyRequestRefused,
            BadRequest,
            CertificateRequired,
            CertificateNotAuthorized,
            CertificateNotValid,
        ],
    )
    def test_inheritance(self, exc_class):
        """All exception classes inherit from GeminiException."""
        assert issubclass(exc_class, GeminiException)
        exc = exc_class()
        assert isinstance(exc, GeminiException)
        assert isinstance(exc, Exception)

    @pytest.mark.parametrize(
        ("exc_class", "expected_status"),
        [
            (InputRequired, 10),
            (SensitiveInputRequired, 11),
            (TemporaryFailure, 40),
            (ServerUnavailable, 41),
            (CGIError, 42),
            (ProxyError, 43),
            (SlowDown, 44),
            (PermanentFailure, 50),
            (NotFound, 51),
            (Gone, 52),
            (ProxyRequestRefused, 53),
            (BadRequest, 59),
            (CertificateRequired, 60),
            (CertificateNotAuthorized, 61),
            (CertificateNotValid, 62),
        ],
    )
    def test_status_codes(self, exc_class, expected_status):
        """Each exception class has the correct status code."""
        exc = exc_class()
        assert exc.status_code == expected_status
