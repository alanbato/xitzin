# CGI Scripts

Xitzin supports executing CGI (Common Gateway Interface) scripts, allowing you to run external programs that generate Gemini responses. This is useful for integrating existing scripts, using other programming languages, or running legacy CGI applications.

## Mount a CGI Directory

Use `app.mount()` with a `CGIHandler` to serve scripts from a directory:

```python
from xitzin import Xitzin
from xitzin.cgi import CGIHandler

app = Xitzin()

# Mount all scripts in /srv/gemini/cgi-bin at /cgi-bin
app.mount("/cgi-bin", CGIHandler("/srv/gemini/cgi-bin"))
```

Now requests to `/cgi-bin/hello.py` will execute `/srv/gemini/cgi-bin/hello.py`.

## Use the Convenience Method

For simpler setup, use `app.cgi()`:

```python
app = Xitzin()

# Equivalent to the above
app.cgi("/cgi-bin", "/srv/gemini/cgi-bin")
```

## Mount a Single Script

Use `CGIScript` to mount a single script at a specific path:

```python
from xitzin.cgi import CGIScript

app = Xitzin()

# Mount a single script
app.mount("/calculator", CGIScript("/srv/scripts/calc.py"))
```

All requests to `/calculator` (with any query string) will execute the calculator script.

## Write a CGI Script

CGI scripts must output a Gemini response to stdout. The first line contains the status code and meta field, followed by optional body content:

```python
#!/usr/bin/env python3
import os

# Get the query string from the environment
query = os.environ.get("QUERY_STRING", "")

if not query:
    # Request input (status 10)
    print("10 Enter your name:")
else:
    # Success response (status 20)
    print("20 text/gemini")
    print()  # Empty line separates header from body
    print(f"# Hello, {query}!")
    print()
    print("Welcome to my CGI script.")
```

Make the script executable:

```bash
chmod +x /srv/gemini/cgi-bin/hello.py
```

## CGI Output Format

The script's stdout must follow this format:

```
<STATUS> <META>\r\n
[optional body content]
```

Common status codes:

| Status | Meta | Use |
|--------|------|-----|
| `10` | Prompt text | Request user input |
| `11` | Prompt text | Request sensitive input |
| `20` | MIME type | Success with content |
| `30` | URL | Temporary redirect |
| `31` | URL | Permanent redirect |
| `40` | Error message | Temporary failure |
| `51` | Error message | Not found |

Examples:

```python
# Success with content
print("20 text/gemini")
print()
print("# Page Title")

# Request input
print("10 Enter search query:")

# Redirect
print("30 gemini://example.com/new-location")

# Error
print("51 Page not found")
```

## Environment Variables

Xitzin passes standard CGI environment variables to scripts:

| Variable | Description | Example |
|----------|-------------|---------|
| `GATEWAY_INTERFACE` | CGI version | `CGI/1.1` |
| `SERVER_PROTOCOL` | Protocol | `GEMINI` |
| `SERVER_SOFTWARE` | Server name/version | `Xitzin/0.1.0` |
| `GEMINI_URL` | Full request URL | `gemini://example.com/cgi-bin/script.py?query` |
| `SCRIPT_NAME` | Script path | `/script.py` |
| `PATH_INFO` | Extra path after script | `/extra/path` |
| `QUERY_STRING` | URL-encoded query | `hello%20world` |
| `SERVER_NAME` | Server hostname | `example.com` |
| `SERVER_PORT` | Server port | `1965` |
| `REMOTE_ADDR` | Client IP address | `192.168.1.100` |

### TLS Certificate Variables

When the client provides a certificate:

| Variable | Description |
|----------|-------------|
| `TLS_CLIENT_HASH` | SHA-256 certificate fingerprint |
| `TLS_CLIENT_AUTHORISED` | `1` if cert present, `0` otherwise |
| `AUTH_TYPE` | `CERTIFICATE` if cert present |

Example script using certificate info:

```python
#!/usr/bin/env python3
import os

cert_hash = os.environ.get("TLS_CLIENT_HASH", "")
authorised = os.environ.get("TLS_CLIENT_AUTHORISED", "0")

print("20 text/gemini")
print()
print("# Identity Info")
print()

if authorised == "1":
    print(f"Your certificate: {cert_hash[:16]}...")
else:
    print("You are not using a client certificate.")
```

## Pass Application State

Pass application state to scripts using `app_state_keys`:

```python
from xitzin import Xitzin
from xitzin.cgi import CGIHandler, CGIConfig

app = Xitzin()

@app.on_startup
def setup():
    app.state.db_url = "postgres://localhost/mydb"
    app.state.api_key = "secret123"

# Pass specific state keys to CGI scripts
config = CGIConfig(app_state_keys=["db_url", "api_key"])
app.mount("/cgi-bin", CGIHandler("/srv/cgi-bin", config=config))
```

Scripts receive these as `XITZIN_*` environment variables:

```python
#!/usr/bin/env python3
import os

db_url = os.environ.get("XITZIN_DB_URL", "")
api_key = os.environ.get("XITZIN_API_KEY", "")

print("20 text/gemini")
print()
print(f"DB: {db_url}")
```

## Configure Timeouts

Set execution timeouts to prevent runaway scripts:

```python
from xitzin.cgi import CGIHandler, CGIConfig

# 60 second timeout
config = CGIConfig(timeout=60.0)
app.mount("/cgi-bin", CGIHandler("/srv/cgi-bin", config=config))

# Or with the convenience method
app.cgi("/cgi-bin", "/srv/cgi-bin", timeout=60.0)
```

If a script exceeds the timeout, it's killed and a CGI error (status 42) is returned.

## Handle Extra Path Info

Scripts can receive extra path segments after the script name:

```
/cgi-bin/api.py/users/123
          ^^^^^  ^^^^^^^^^^
       SCRIPT    PATH_INFO
```

```python
#!/usr/bin/env python3
import os

path_info = os.environ.get("PATH_INFO", "")
# path_info = "/users/123"

print("20 text/gemini")
print()
print(f"Path info: {path_info}")
```

## Use with Other Languages

CGI scripts can be written in any language. Here's a shell script example:

```bash
#!/bin/bash

echo "20 text/gemini"
echo ""
echo "# System Info"
echo ""
echo "Date: $(date)"
echo "Hostname: $(hostname)"
echo "Uptime: $(uptime -p)"
```

Or a Perl script:

```perl
#!/usr/bin/perl
use strict;
use warnings;

print "20 text/gemini\r\n";
print "\r\n";
print "# Hello from Perl!\n";
print "\n";
print "Query: $ENV{QUERY_STRING}\n";
```

## Security Considerations

Xitzin implements several security measures:

1. **Path traversal protection**: Scripts must be within the configured directory
2. **Execute permission check**: Scripts must have the execute bit set
3. **Timeout enforcement**: Long-running scripts are killed
4. **Header size limits**: Prevents memory exhaustion from malicious output

!!! warning "Script Security"
    CGI scripts run with the same permissions as the Xitzin process. Be careful when:

    - Accepting user input in scripts
    - Running scripts from untrusted sources
    - Passing sensitive data via environment variables

## Combine with Regular Routes

CGI handlers work alongside regular routes:

```python
from xitzin import Xitzin, Request
from xitzin.cgi import CGIHandler

app = Xitzin()

# Regular route
@app.gemini("/")
def home(request: Request):
    return "# Home\n\n=> /cgi-bin/ CGI Scripts"

# CGI directory
app.mount("/cgi-bin", CGIHandler("/srv/cgi-bin"))

# Regular route after mount
@app.gemini("/about")
def about(request: Request):
    return "# About"
```

Mounted handlers take precedence over regular routes for matching paths.

## Apply Middleware

Middleware applies to CGI requests just like regular routes:

```python
@app.middleware
async def log_requests(request, call_next):
    print(f"Request: {request.path}")
    response = await call_next(request)
    print(f"Response: {response.status}")
    return response

app.mount("/cgi-bin", CGIHandler("/srv/cgi-bin"))
```

## Test CGI Scripts

Use `TestClient` to test CGI integration:

```python
from xitzin import Xitzin
from xitzin.cgi import CGIHandler
from xitzin.testing import TestClient

def test_cgi_script(tmp_path):
    # Create a test script
    script = tmp_path / "hello.py"
    script.write_text('''#!/usr/bin/env python3
print("20 text/gemini")
print()
print("# Hello from CGI")
''')
    script.chmod(0o755)

    # Set up app
    app = Xitzin()
    app.mount("/cgi-bin", CGIHandler(tmp_path))

    # Test
    client = TestClient(app)
    response = client.get("/cgi-bin/hello.py")

    assert response.is_success
    assert "Hello from CGI" in response.body
```

## Configuration Reference

`CGIConfig` accepts these options:

| Option | Default | Description |
|--------|---------|-------------|
| `timeout` | `30.0` | Maximum execution time in seconds |
| `max_header_size` | `8192` | Maximum header line size in bytes |
| `streaming` | `False` | Enable streaming mode (experimental) |
| `check_execute_permission` | `True` | Verify scripts are executable |
| `inherit_environment` | `True` | Pass parent environment to scripts |
| `app_state_keys` | `[]` | App state keys to pass as `XITZIN_*` vars |

```python
from xitzin.cgi import CGIConfig, CGIHandler

config = CGIConfig(
    timeout=60.0,
    max_header_size=4096,
    check_execute_permission=True,
    inherit_environment=True,
    app_state_keys=["db_url", "debug_mode"],
)

app.mount("/cgi-bin", CGIHandler("/srv/cgi-bin", config=config))
```
