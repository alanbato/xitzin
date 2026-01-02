# Changelog

All notable changes to Xitzin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2024

### Added

- Initial release of Xitzin
- Core `Xitzin` application class with decorator-based routing
- `@app.gemini()` decorator for defining routes
- `@app.input()` decorator for input handling (status 10/11)
- Path parameter extraction with type conversion
- `Request` wrapper with convenient properties
- Response types: `Response`, `Input`, `Redirect`
- Exception hierarchy mapping to Gemini status codes
- Middleware support (function-based and class-based)
- Built-in middleware: `TimingMiddleware`, `LoggingMiddleware`, `RateLimitMiddleware`
- Certificate authentication decorators: `@require_certificate`, `@require_fingerprint`, `@optional_certificate`
- Jinja2-based templating with Gemtext filters
- Testing utilities: `TestClient`, `TestResponse`, `test_app()`
- Lifecycle events: `@app.on_startup`, `@app.on_shutdown`
- Application state management via `app.state` and `request.state`

### Dependencies

- Nauyaca for Gemini protocol communication
- Pydantic for data validation
- Jinja2 for template rendering
