# Architecture

How Xitzin is structured internally.

## Module Overview

```
xitzin/
├── application.py   # Main Xitzin class
├── routing.py       # Route and Router
├── requests.py      # Request wrapper
├── responses.py     # Response types
├── exceptions.py    # Exception hierarchy
├── middleware.py    # Middleware system
├── auth.py          # Certificate authentication
├── templating.py    # Jinja2 templates
└── testing.py       # Test client
```

## Core Components

### Xitzin (application.py)

The central class that ties everything together:

```python
class Xitzin:
    def __init__(self, title, version, templates_dir):
        self._router = Router()
        self._middleware = []
        self._startup_handlers = []
        self._shutdown_handlers = []
        self.state = AppState()
```

Key responsibilities:

- Route registration via decorators
- Middleware management
- Lifecycle events
- Template rendering
- Server lifecycle

### Router and Route (routing.py)

**Route** represents a single registered endpoint:

- Path pattern with parameter extraction
- Handler function
- Optional input configuration

**Router** manages route matching:

- Stores routes in registration order
- Matches paths against patterns
- Returns matched route and extracted parameters

### Request (requests.py)

Wraps the raw Gemini request from Nauyaca:

```python
class Request:
    def __init__(self, raw_request, app):
        self._raw = raw_request
        self.app = app
        self.state = RequestState()
```

Provides convenient properties:

- `path`, `query`, `url`
- `client_cert`, `client_cert_fingerprint`
- `state` for middleware data

### Response Types (responses.py)

Three main response classes:

- **Response**: Success with body
- **Input**: Request user input
- **Redirect**: Redirect to URL

All implement `to_gemini_response()` for conversion.

### Exceptions (exceptions.py)

Exception hierarchy mapping to Gemini status codes:

```
GeminiException (50)
├── InputRequired (10)
├── SensitiveInputRequired (11)
├── TemporaryFailure (40)
│   ├── ServerUnavailable (41)
│   ├── CGIError (42)
│   ├── ProxyError (43)
│   └── SlowDown (44)
├── PermanentFailure (50)
│   ├── NotFound (51)
│   ├── Gone (52)
│   ├── ProxyRequestRefused (53)
│   └── BadRequest (59)
└── CertificateRequired (60)
    ├── CertificateNotAuthorized (61)
    └── CertificateNotValid (62)
```

### Middleware (middleware.py)

Two patterns supported:

**Function-based**:

```python
async def middleware(request, call_next):
    response = await call_next(request)
    return response
```

**Class-based**:

```python
class MyMiddleware(BaseMiddleware):
    async def before_request(self, request): ...
    async def after_response(self, request, response): ...
```

### Authentication (auth.py)

Decorators and helpers for certificate auth:

- `@require_certificate` - Enforce authentication
- `@require_fingerprint()` - Whitelist specific certs
- `@optional_certificate` - Optional personalization
- `get_identity()` - Access certificate info

### Templating (templating.py)

Jinja2 integration for Gemtext:

- `TemplateEngine` - Main rendering interface
- `GemtextEnvironment` - Custom Jinja2 environment
- Filters: `link`, `heading`, `list`, `quote`, `preformat`

### Testing (testing.py)

In-memory testing utilities:

- `TestClient` - Make requests without server
- `TestResponse` - Response wrapper with helpers
- `test_app()` - Context manager for lifecycle

## Design Patterns

### Decorator-Based Registration

Routes are registered via decorators, similar to FastAPI:

```python
@app.gemini("/path")
def handler(request: Request):
    ...
```

The decorator stores the handler in the router and returns it unchanged.

### Async/Sync Handler Support

Both sync and async handlers are supported:

```python
# Sync handler - wrapped in executor
@app.gemini("/sync")
def sync_handler(request: Request):
    return "sync"

# Async handler - used directly
@app.gemini("/async")
async def async_handler(request: Request):
    return "async"
```

Sync handlers are automatically wrapped to run in a thread pool executor.

### Response Conversion

Handlers can return various types:

```python
# String → Response with text/gemini
return "# Hello"

# Response object
return Response(body="data", mime_type="text/plain")

# Tuple for control
return ("body", 20, "text/gemini")
```

The `convert_response()` function handles all conversions.

### State Storage

Two levels of state:

- **App state** (`app.state`): Shared across all requests
- **Request state** (`request.state`): Per-request, middleware data

```python
# App startup
app.state.db = connect_database()

# Middleware stores data
request.state.user = get_user(request)

# Handler accesses it
user = request.state.user
```

## Dependencies

Xitzin builds on:

- **Nauyaca**: Gemini protocol implementation
- **Pydantic**: Data validation
- **Jinja2**: Template engine
