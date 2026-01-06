# SCGI Backends

Xitzin supports proxying requests to SCGI (Simple Common Gateway Interface) backends. Unlike CGI which spawns a new process for each request, SCGI connects to a persistent backend process, providing better performance for high-traffic applications.

## When to Use SCGI

Use SCGI when you need:

- **Better performance**: No process spawn overhead per request
- **Persistent state**: Backend can maintain connections (databases, caches)
- **Language flexibility**: Backend can be written in any language with SCGI support
- **Process isolation**: Backend runs as a separate process

## Connect via TCP

Use `app.scgi()` to proxy requests to an SCGI backend over TCP:

```python
from xitzin import Xitzin

app = Xitzin()

# Connect to SCGI backend at localhost:4000
app.scgi("/api", host="127.0.0.1", port=4000)
```

Requests to `/api/*` will be forwarded to the SCGI backend.

## Connect via Unix Socket

For better performance on local backends, use Unix sockets:

```python
app = Xitzin()

# Connect via Unix socket
app.scgi("/api", socket_path="/tmp/myapp.sock")
```

Unix sockets avoid TCP overhead and are more secure for local communication.

## Use Explicit Handlers

For more control, use `SCGIHandler` (TCP) or `SCGIApp` (Unix socket) directly:

```python
from xitzin import Xitzin
from xitzin.scgi import SCGIHandler, SCGIConfig

app = Xitzin()

config = SCGIConfig(
    timeout=60.0,
    max_response_size=10 * 1024 * 1024,  # 10MB
)

handler = SCGIHandler("127.0.0.1", 4000, config=config)
app.mount("/api", handler)
```

Or with Unix sockets:

```python
from xitzin.scgi import SCGIApp, SCGIConfig

config = SCGIConfig(timeout=60.0)
handler = SCGIApp("/tmp/myapp.sock", config=config)
app.mount("/api", handler)
```

## Write an SCGI Backend

SCGI backends receive the same environment variables as CGI scripts and must output responses in the same format.

### Python Example (using flup)

```python
from flup.server.scgi import WSGIServer

def app(environ, start_response):
    path_info = environ.get("PATH_INFO", "/")
    query = environ.get("QUERY_STRING", "")

    # Build Gemini response
    status = "20 text/gemini"
    body = f"# Hello from SCGI!\n\nPath: {path_info}\nQuery: {query}\n"

    start_response(status, [])
    return [body.encode()]

if __name__ == "__main__":
    WSGIServer(app, bindAddress=("127.0.0.1", 4000)).run()
```

### Simple Python SCGI Server

Here's a minimal SCGI server without external dependencies:

```python
#!/usr/bin/env python3
import socket
import os

def parse_scgi_request(data):
    """Parse SCGI netstring headers."""
    colon = data.index(b":")
    length = int(data[:colon])
    headers_data = data[colon + 1:colon + 1 + length]

    # Parse null-separated key-value pairs
    parts = headers_data.split(b"\x00")
    env = {}
    for i in range(0, len(parts) - 1, 2):
        key = parts[i].decode()
        value = parts[i + 1].decode() if i + 1 < len(parts) else ""
        env[key] = value

    return env

def handle_request(env):
    """Generate Gemini response."""
    path = env.get("PATH_INFO", "/")
    query = env.get("QUERY_STRING", "")

    body = f"# SCGI Response\n\nPath: {path}\nQuery: {query}\n"
    return f"20 text/gemini\r\n{body}"

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 4000))
    sock.listen(5)

    print("SCGI server listening on 127.0.0.1:4000")

    while True:
        conn, addr = sock.accept()
        try:
            data = conn.recv(65536)
            env = parse_scgi_request(data)
            response = handle_request(env)
            conn.sendall(response.encode())
        finally:
            conn.close()

if __name__ == "__main__":
    main()
```

## Response Format

SCGI backends must output responses in standard CGI format:

```
<STATUS> <META>\r\n
[optional body content]
```

Examples:

```python
# Success with content
print("20 text/gemini\r\n# Hello World")

# Request input
print("10 Enter your name:\r\n")

# Redirect
print("30 gemini://example.com/new-location\r\n")

# Error
print("51 Not found\r\n")
```

## Environment Variables

SCGI backends receive the same environment variables as CGI scripts, plus SCGI-specific ones:

| Variable | Description | Example |
|----------|-------------|---------|
| `SCGI` | Always `1` for SCGI requests | `1` |
| `CONTENT_LENGTH` | Request body length (always `0` for Gemini) | `0` |
| `PATH_INFO` | Path after mount point | `/users/123` |
| `QUERY_STRING` | URL-encoded query string | `search=hello` |
| `SERVER_NAME` | Server hostname | `example.com` |
| `SERVER_PORT` | Server port | `1965` |
| `GEMINI_URL` | Full request URL | `gemini://example.com/api/test` |
| `TLS_CLIENT_HASH` | Client certificate fingerprint | `abc123...` |
| `TLS_CLIENT_AUTHORISED` | `1` if cert present, `0` otherwise | `1` |

## Pass Application State

Share application state with SCGI backends:

```python
from xitzin import Xitzin

app = Xitzin()

@app.on_startup
def setup():
    app.state.db_url = "postgres://localhost/mydb"
    app.state.api_key = "secret123"

# Pass state keys to backend
app.scgi(
    "/api",
    host="127.0.0.1",
    port=4000,
    app_state_keys=["db_url", "api_key"],
)
```

The backend receives these as `XITZIN_*` environment variables:

```python
# In your SCGI backend
db_url = environ.get("XITZIN_DB_URL", "")
api_key = environ.get("XITZIN_API_KEY", "")
```

## Configure Timeouts

Set timeouts to handle slow or unresponsive backends:

```python
# 60 second timeout
app.scgi("/api", host="127.0.0.1", port=4000, timeout=60.0)

# Or with explicit config
from xitzin.scgi import SCGIHandler, SCGIConfig

config = SCGIConfig(timeout=60.0)
handler = SCGIHandler("127.0.0.1", 4000, config=config)
```

If the backend doesn't respond within the timeout, a proxy error (status 43) is returned.

## Limit Response Size

Protect against memory exhaustion from large responses:

```python
from xitzin.scgi import SCGIConfig, SCGIHandler

config = SCGIConfig(
    max_response_size=5 * 1024 * 1024,  # 5MB limit
)
handler = SCGIHandler("127.0.0.1", 4000, config=config)
```

Set to `None` for unlimited response size (use with caution).

## Error Handling

When SCGI communication fails, Xitzin returns a proxy error (status 43):

| Error | Status | Message |
|-------|--------|---------|
| Connection refused | 43 | Failed to connect to SCGI backend |
| Connection timeout | 43 | SCGI connection timeout |
| Read timeout | 43 | SCGI backend timeout |
| Response too large | 43 | SCGI response exceeds maximum size |
| Invalid response | 43 | SCGI backend error |

Handle these gracefully in your application:

```python
@app.middleware
async def handle_proxy_errors(request, call_next):
    response = await call_next(request)
    if response.status == 43:
        # Log the error, maybe try a fallback
        print(f"Proxy error: {response.meta}")
    return response
```

## Combine with Regular Routes

SCGI handlers work alongside regular routes:

```python
from xitzin import Xitzin, Request

app = Xitzin()

# Regular route
@app.gemini("/")
def home(request: Request):
    return "# Home\n\n=> /api/ API (SCGI backend)"

# SCGI backend
app.scgi("/api", host="127.0.0.1", port=4000)

# Another regular route
@app.gemini("/about")
def about(request: Request):
    return "# About"
```

Mounted handlers (like SCGI) take precedence over regular routes for matching paths.

## Apply Middleware

Middleware applies to SCGI requests just like regular routes:

```python
@app.middleware
async def log_requests(request, call_next):
    print(f"Request: {request.path}")
    response = await call_next(request)
    print(f"Response: {response.status}")
    return response

app.scgi("/api", host="127.0.0.1", port=4000)
```

## Test SCGI Integration

Use `TestClient` with a mock server for testing:

```python
import asyncio
from xitzin import Xitzin
from xitzin.testing import TestClient

# Simple mock SCGI server for testing
async def mock_scgi_server(reader, writer):
    # Read request (simplified)
    data = await reader.read(65536)

    # Send response
    writer.write(b"20 text/gemini\r\n# Mock Response\n")
    await writer.drain()
    writer.close()

def test_scgi_integration():
    # Start mock server
    loop = asyncio.get_event_loop()
    server = loop.run_until_complete(
        asyncio.start_server(mock_scgi_server, "127.0.0.1", 0)
    )
    port = server.sockets[0].getsockname()[1]

    try:
        app = Xitzin()
        app.scgi("/api", host="127.0.0.1", port=port)

        client = TestClient(app)
        response = client.get("/api/test")

        assert response.is_success
        assert "Mock Response" in response.body
    finally:
        server.close()
        loop.run_until_complete(server.wait_closed())
```

## Configuration Reference

`SCGIConfig` accepts these options:

| Option | Default | Description |
|--------|---------|-------------|
| `timeout` | `30.0` | Maximum response wait time in seconds |
| `max_response_size` | `1048576` (1MB) | Maximum response size in bytes, or `None` for unlimited |
| `buffer_size` | `8192` | Read buffer size in bytes |
| `inherit_environment` | `True` | Pass parent environment to backend |
| `app_state_keys` | `[]` | App state keys to pass as `XITZIN_*` vars |

```python
from xitzin.scgi import SCGIConfig, SCGIHandler

config = SCGIConfig(
    timeout=60.0,
    max_response_size=10 * 1024 * 1024,  # 10MB
    buffer_size=16384,
    inherit_environment=True,
    app_state_keys=["db_url", "api_key"],
)

handler = SCGIHandler("127.0.0.1", 4000, config=config)
app.mount("/api", handler)
```

## CGI vs SCGI Comparison

| Aspect | CGI | SCGI |
|--------|-----|------|
| Process model | New process per request | Persistent process |
| Startup overhead | High | Low |
| State persistence | None | Yes |
| Configuration | Script path | Host:port or socket path |
| Error status | 42 (CGI error) | 43 (Proxy error) |
| Use case | Simple scripts, legacy apps | High-traffic apps, complex backends |
