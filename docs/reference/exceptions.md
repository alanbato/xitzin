# Exceptions

Exception classes that map to Gemini status codes. Raise these exceptions in your handlers to return specific status codes.

## Base Exception

::: xitzin.exceptions.GeminiException

## Input Required (1x)

::: xitzin.exceptions.InputRequired

::: xitzin.exceptions.SensitiveInputRequired

## Temporary Failures (4x)

::: xitzin.exceptions.TemporaryFailure

::: xitzin.exceptions.ServerUnavailable

::: xitzin.exceptions.CGIError

::: xitzin.exceptions.ProxyError

::: xitzin.exceptions.SlowDown

## Permanent Failures (5x)

::: xitzin.exceptions.PermanentFailure

::: xitzin.exceptions.NotFound

::: xitzin.exceptions.Gone

::: xitzin.exceptions.ProxyRequestRefused

::: xitzin.exceptions.BadRequest

## Client Certificate (6x)

::: xitzin.exceptions.CertificateRequired

::: xitzin.exceptions.CertificateNotAuthorized

::: xitzin.exceptions.CertificateNotValid
