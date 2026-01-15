# Titan Protocol Support Implementation

This document tracks the implementation of Titan upload protocol support for Xitzin.

## Status: Complete

All 554 tests pass (522 existing + 32 new Titan tests). Type checking and linting pass with no errors.

## What is Titan?

Titan is Gemini's companion protocol for uploading content. It uses `titan://` URLs with parameters:
- `titan://host/path;size=N;mime=TYPE;token=TOKEN`
- Zero-byte uploads (`size=0`) indicate delete operations

## Implementation Decisions

Based on user requirements:
1. **Decorator approach**: `@app.titan("/path")`
2. **Explicit params**: `def handler(request: TitanRequest, content: bytes, mime_type: str, token: str | None)`
3. **Auth built into decorator**: `@app.titan("/upload", auth_tokens=["secret"])`
4. **Delete via same handler**: Handler checks `request.is_delete()`
5. **TestClient support**: `client.upload()` and `client.delete()` methods
6. **Auto-enable**: Titan enabled automatically when routes registered
7. **Architecture**: Pragmatic balance - modify existing files, no new files

## Files Modified

### 1. `src/xitzin/requests.py`
- Added import for `TitanRequest as NauyacaTitanRequest` from nauyaca
- Added `TitanRequest` class (wrapper around Nauyaca's TitanRequest)
  - Properties: `content`, `mime_type`, `token`, `size`, `path`, `hostname`, `port`, `client_cert`, `client_cert_fingerprint`, `raw_url`, `app`, `state`
  - Method: `is_delete()` - returns True for zero-byte uploads

### 2. `src/xitzin/routing.py`
- Added `TitanRoute` class after `MountedRoute`
  - Similar to `Route` but for Titan handlers
  - Stores `auth_tokens` set for authentication
  - `call_handler()` passes explicit params: `content`, `mime_type`, `token` plus path params
- Modified `Router` class:
  - Added `_titan_routes: list[TitanRoute]` to `__init__`
  - Added `add_titan_route(route: TitanRoute)` method
  - Added `match_titan(path: str)` method
  - Added `has_titan_routes()` method

### 3. `src/xitzin/application.py`
- Added imports:
  - `TitanRequest as NauyacaTitanRequest` from nauyaca
  - `CertificateRequired` from exceptions
  - `TitanRequest` from requests
  - `TitanRoute` from routing
- Added `@app.titan()` decorator method (after `@app.input()`)
  - Parameters: `path`, `name`, `auth_tokens`
  - Registers `TitanRoute` with router
- Added `_handle_titan_request()` method
  - Wraps raw request in `TitanRequest`
  - Matches Titan routes
  - Validates auth tokens (returns status 60 if invalid)
  - Applies middleware chain
  - Calls handler
- Modified `run_async()`:
  - Creates `XitzinUploadHandler` (implements Nauyaca's `UploadHandler` ABC) when Titan routes exist
  - Passes upload handler to `GeminiServerProtocol`
  - Prints "[Xitzin] Titan upload support enabled" message
- Modified `_wrap_middleware()` type signature to accept `Any` for request type

### 4. `src/xitzin/testing.py`
- Added import for `TitanRequest as NauyacaTitanRequest`
- Added `upload()` method to `TestClient`:
  - Parameters: `path`, `content` (bytes|str), `mime_type`, `token`, `cert_fingerprint`
  - Creates Titan URL with parameters
  - Creates `NauyacaTitanRequest` and sets content
  - Calls `_handle_titan_sync()`
- Added `delete()` method to `TestClient`:
  - Convenience method that calls `upload()` with empty content
- Added `_handle_titan_sync()` helper method

### 5. `src/xitzin/responses.py`
- Modified `convert_response()` type signature:
  - Changed `request: Request | None` to `request: Any` to support both Request and TitanRequest

### 6. `src/xitzin/__init__.py`
- Added `TitanRequest` to imports
- Added `TitanRequest` to `__all__`

## Completed Work

### Type Checking
- Fixed type errors in `testing.py` by properly converting `bytes` body to `str`
- Removed unused `type: ignore` comments in `application.py` and `middleware.py`
- Removed unused `Request` import in `responses.py`

### Testing
Added 32 comprehensive tests in `tests/test_titan.py` covering:
- Basic Titan upload (content, MIME type, request properties)
- Token authentication (valid/invalid/missing tokens)
- Delete operations (zero-byte uploads via `is_delete()`)
- Path parameters in Titan routes (single, multiple, type conversion, path type)
- Middleware execution with Titan requests
- Client certificate handling
- Async handlers

## Example Usage

```python
from xitzin import Xitzin, TitanRequest
from pathlib import Path

app = Xitzin()

@app.titan("/upload/{filename}", auth_tokens=["secret123"])
def upload(request: TitanRequest, content: bytes, mime_type: str, token: str | None, filename: str):
    if request.is_delete():
        Path(f"./uploads/{filename}").unlink(missing_ok=True)
        return "# Deleted"

    Path(f"./uploads/{filename}").write_bytes(content)
    return f"# Uploaded {filename}"

# Testing
from xitzin.testing import TestClient

client = TestClient(app)

# Upload
response = client.upload("/upload/test.gmi", "# Hello", token="secret123")
assert response.is_success

# Delete
response = client.delete("/upload/test.gmi", token="secret123")
assert response.is_success
```

## Dependencies

Requires local nauyaca with Titan support (not yet published to PyPI):
- `nauyaca.protocol.request.TitanRequest`
- `nauyaca.server.handler.UploadHandler`

The user has already installed the local nauyaca version with Titan support.

## Commands to Verify

```bash
# Run all tests
uv run pytest -x -v

# Type check
uv run ty check src/

# Lint
uv run ruff check src/
```
