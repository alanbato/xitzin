# Middleware

Middleware base class and built-in implementations.

## BaseMiddleware

Abstract base class for creating class-based middleware.

::: xitzin.middleware.BaseMiddleware

## Built-in Middleware

### TimingMiddleware

Tracks request processing time.

::: xitzin.middleware.TimingMiddleware

### LoggingMiddleware

Logs incoming requests and outgoing responses.

::: xitzin.middleware.LoggingMiddleware

### RateLimitMiddleware

Simple in-memory rate limiting.

::: xitzin.middleware.RateLimitMiddleware

### UserSessionMiddleware

Loads and caches user data from certificate fingerprints.

::: xitzin.middleware.UserSessionMiddleware

### VirtualHostMiddleware

Routes requests to different applications based on hostname.

::: xitzin.middleware.VirtualHostMiddleware
