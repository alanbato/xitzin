# Building a Guestbook

In this tutorial, you'll build a complete guestbook application that combines everything you've learned: routing, user input, and certificate authentication.

!!! tip "Complete Example Available"
    The complete working code for this tutorial is available in `examples/guestbook/`. You can run it directly:

    ```bash
    cd examples/guestbook
    uv run python app.py
    ```

## What You'll Build

- A public guestbook that anyone can read
- Authenticated signing (requires certificate)
- Admin controls for deleting entries
- Middleware for logging
- Lifecycle events for initialization

## Project Structure

```
guestbook/
├── app.py              # Main application
├── templates/
│   └── base.gmi        # Base template (optional)
└── README.md
```

## Step 1: Project Setup

Create the project structure:

```bash
mkdir guestbook
cd guestbook
mkdir templates
uv init
uv add xitzin
```

## Step 2: Create the Application

Create `app.py` with the basic structure:

```python
from datetime import datetime
from pathlib import Path

from xitzin import Xitzin, Request
from xitzin.auth import (
    get_identity,
    optional_certificate,
    require_certificate,
    require_fingerprint,
)

app = Xitzin(
    title="Guestbook",
    templates_dir=Path(__file__).parent / "templates",
)

# Storage (in production, use a database!)
entries: list[dict] = []

# Admin fingerprints - replace with your own certificate fingerprints
ADMIN_FINGERPRINTS = ["SHA256:your-fingerprint-here"]
```

## Step 3: Add Lifecycle Events

Initialize application state on startup:

```python
@app.on_startup
async def startup():
    """Initialize application state on startup."""
    print("Guestbook starting up...")
    app.state.pending_signs = {}
    app.state.request_count = 0


@app.on_shutdown
async def shutdown():
    """Clean up on shutdown."""
    print(f"Shutting down. Total requests: {app.state.request_count}")
```

## Step 4: Add Middleware

Create custom middleware for logging and request counting:

```python
@app.middleware
async def log_and_count_requests(request: Request, call_next):
    """Log requests and count total requests handled."""
    import time

    # Initialize if not set (for testing without lifecycle)
    if not hasattr(app.state, "request_count"):
        app.state.request_count = 0
    if not hasattr(app.state, "pending_signs"):
        app.state.pending_signs = {}

    app.state.request_count += 1
    start = time.perf_counter()

    cert_info = ""
    if request.client_cert_fingerprint:
        cert_info = f" [cert:{request.client_cert_fingerprint[:8]}]"
    print(f"[Guestbook] Request: {request.path}{cert_info}")

    response = await call_next(request)

    elapsed = time.perf_counter() - start
    print(f"[Guestbook] Response: {response.status} ({elapsed:.3f}s)")

    return response
```

## Step 5: Create Routes

### Home Page

The home page shows recent entries and uses optional certificate detection:

```python
@app.gemini("/", name="home")
@optional_certificate
def home(request: Request):
    """Home page showing recent entries."""
    identity = request.state.identity
    lines = ["# Guestbook", "", "Welcome to my guestbook!", ""]

    if entries:
        lines.append("Recent entries:")
        for entry in entries[-3:]:
            lines.append(f"* {entry['name']}: {entry['message'][:50]}...")
        lines.append("")

    lines.extend(
        [
            "=> /entries View all entries",
            "=> /sign Sign the guestbook",
        ]
    )

    if identity:
        lines.append("")
        lines.append(f"Signed in as: {identity.short_id}")

    return "\n".join(lines)
```

### View All Entries

```python
@app.gemini("/entries", name="entries")
def view_entries(request: Request):
    """List all guestbook entries."""
    lines = ["# Guestbook Entries", ""]

    if not entries:
        lines.append("No entries yet. Be the first to sign!")
    else:
        for entry in reversed(entries):
            lines.extend(
                [
                    f"## {entry['name']}",
                    f"> {entry['message']}",
                    f"Signed on {entry['date']}",
                    "",
                ]
            )

    lines.extend(["=> /sign Sign the guestbook", "=> / Home"])
    return "\n".join(lines)
```

### Multi-Step Signing Flow

The signing flow uses `@app.input` for user input and `@require_certificate` for authentication:

```python
@app.input("/sign", prompt="Enter your name:", name="sign")
@require_certificate
def sign_name(request: Request, query: str):
    """First step of signing: capture the user's name."""
    identity = get_identity(request)
    app.state.pending_signs[identity.fingerprint] = query

    return f"""# Name Saved

Your name: {query}

=> /sign/message Write your message
=> / Cancel
"""


@app.input("/sign/message", prompt="Write your message:", name="sign_message")
@require_certificate
def sign_message(request: Request, query: str):
    """Second step of signing: capture the message and save the entry."""
    identity = get_identity(request)
    name = app.state.pending_signs.pop(identity.fingerprint, identity.short_id)

    entries.append(
        {
            "name": name,
            "message": query,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "fingerprint": identity.fingerprint,
        }
    )

    return f"""# Thanks, {name}!

Your message has been added.

=> /entries View all entries
=> / Home
"""
```

### Admin Panel

The admin routes use `@require_fingerprint` to restrict access to specific certificates:

```python
@app.gemini("/admin", name="admin")
@require_fingerprint(*ADMIN_FINGERPRINTS)
def admin(request: Request):
    """Admin panel for managing entries."""
    lines = ["# Admin Panel", ""]

    if not entries:
        lines.append("No entries to manage.")
    else:
        for i, entry in enumerate(entries):
            lines.append(f"=> /admin/delete/{i} Delete: {entry['name']}")

    lines.extend(["", "=> / Home"])
    return "\n".join(lines)


@app.gemini("/admin/delete/{entry_id}", name="admin_delete")
@require_fingerprint(*ADMIN_FINGERPRINTS)
def delete_entry(request: Request, entry_id: int):
    """Delete a guestbook entry."""
    if 0 <= entry_id < len(entries):
        deleted = entries.pop(entry_id)
        return f"# Deleted\n\nRemoved entry by {deleted['name']}\n\n=> /admin Back"
    return "# Not Found\n\n=> /admin Back"
```

### Run the Application

```python
if __name__ == "__main__":
    app.run()
```

## Step 6: Run the Application

Start the server:

```bash
uv run python app.py
```

The server will start at `gemini://localhost:1965/` using a self-signed certificate for development.

Connect with any Gemini browser (Lagrange, Amfora, Kristall, etc.) to test your guestbook.

## Step 7: Finding Your Admin Fingerprint

To use the admin panel, you need your client certificate's fingerprint. When you connect with a certificate, the server logs it:

```
[Guestbook] Request: / [cert:SHA256:T]
```

Copy the full fingerprint from the logs and add it to `ADMIN_FINGERPRINTS` in your `app.py`.

## Key Concepts Covered

1. **Routing**: Multiple routes with path parameters (`/admin/delete/{entry_id}`)
2. **Route Naming**: Using `name=` for URL reversing
3. **User Input**: Chained inputs with `@app.input` for multi-step forms
4. **Authentication**: Certificate-based auth with `@require_certificate`
5. **Authorization**: Admin access with `@require_fingerprint`
6. **Middleware**: Custom request logging and timing
7. **Lifecycle**: Startup and shutdown handlers
8. **State Management**: Using `app.state` for shared data

## Production Considerations

Before deploying to production:

- Replace in-memory `entries` list with a proper database
- Use real TLS certificates instead of self-signed
- Configure rate limiting for spam protection
- Implement input validation and sanitization

## Next Steps

Congratulations! You've built a complete Gemini application. Explore more:

- [Deployment guide](../how-to/deployment.md) for production
- [Middleware patterns](../how-to/middleware.md) for advanced use cases
- [API Reference](../reference/index.md) for all available features
