# Building a Guestbook

In this tutorial, you'll build a complete guestbook application that combines everything you've learned: routing, templates, user input, and certificate authentication.

## What You'll Build

- A public guestbook that anyone can read
- Authenticated signing (requires certificate)
- Admin controls for deleting entries
- Templates for consistent styling
- Middleware for logging

## Project Structure

```
guestbook/
├── app.py              # Main application
├── templates/
│   ├── base.gmi        # Base template
│   ├── home.gmi        # Home page
│   ├── entries.gmi     # Guestbook entries
│   └── admin.gmi       # Admin page
├── cert.pem            # TLS certificate
└── key.pem             # TLS private key
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

## Step 2: Create Base Template

Create `templates/base.gmi`:

```jinja
{{ title | heading(1) }}

{{ content }}

---

{{ "/" | link("Home") }}
{{ "/entries" | link("View Guestbook") }}
{% if show_sign %}
{{ "/sign" | link("Sign the Guestbook") }}
{% endif %}
```

## Step 3: Create the Application

Create `app.py`:

```python
from datetime import datetime
from pathlib import Path

from xitzin import Xitzin, Request
from xitzin.auth import (
    require_certificate,
    require_fingerprint,
    optional_certificate,
    get_identity,
)

app = Xitzin(
    title="Guestbook",
    templates_dir=Path(__file__).parent / "templates",
)

# In-memory storage (use a database in production!)
entries = []

# Admin fingerprints (replace with your own)
ADMIN_FINGERPRINTS = [
    "your-admin-fingerprint-here",
]


@app.gemini("/")
@optional_certificate
def home(request: Request):
    identity = request.state.identity
    recent_count = min(len(entries), 3)

    content = f"""Welcome to my guestbook!

{recent_count} recent entries:

"""

    for entry in entries[-3:]:
        content += f"* {entry['name']}: {entry['message'][:50]}...\n"

    content += """
=> /entries View all entries
=> /sign Sign the guestbook
"""

    if identity:
        content += f"\nSigned in as: {identity.short_id}"

    return app.template(
        "base.gmi",
        title="Guestbook",
        content=content,
        show_sign=True,
    )


@app.gemini("/entries")
def view_entries(request: Request):
    if not entries:
        content = "No entries yet. Be the first to sign!"
    else:
        lines = []
        for i, entry in enumerate(reversed(entries)):
            lines.append(f"## {entry['name']}")
            lines.append(f"> {entry['message']}")
            lines.append(f"Signed on {entry['date']}")
            lines.append("")
        content = "\n".join(lines)

    return app.template(
        "base.gmi",
        title="Guestbook Entries",
        content=content,
        show_sign=True,
    )


@app.gemini("/sign")
@require_certificate
def sign_start(request: Request):
    identity = get_identity(request)

    content = f"""You're about to sign the guestbook.

Your signature ID: {identity.short_id}

=> /sign/name Continue
"""

    return app.template(
        "base.gmi",
        title="Sign Guestbook",
        content=content,
        show_sign=False,
    )


@app.input("/sign/name", prompt="Enter your display name:")
@require_certificate
def sign_name(request: Request, query: str):
    identity = get_identity(request)

    # Store name temporarily in app state
    if not hasattr(app.state, "pending_signs"):
        app.state.pending_signs = {}

    app.state.pending_signs[identity.fingerprint] = query

    content = f"""Name saved: {query}

=> /sign/message Continue to write your message
"""

    return app.template(
        "base.gmi",
        title="Sign Guestbook",
        content=content,
        show_sign=False,
    )


@app.input("/sign/message", prompt="Write your message:")
@require_certificate
def sign_message(request: Request, query: str):
    identity = get_identity(request)

    # Get stored name
    pending = getattr(app.state, "pending_signs", {})
    name = pending.pop(identity.fingerprint, identity.short_id)

    # Create entry
    entry = {
        "name": name,
        "message": query,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "fingerprint": identity.fingerprint,
    }
    entries.append(entry)

    content = f"""Thanks for signing, {name}!

Your message has been added to the guestbook.

=> /entries View all entries
"""

    return app.template(
        "base.gmi",
        title="Signed!",
        content=content,
        show_sign=True,
    )


@app.gemini("/admin")
@require_fingerprint(*ADMIN_FINGERPRINTS)
def admin(request: Request):
    if not entries:
        content = "No entries to manage."
    else:
        lines = ["Select an entry to delete:", ""]
        for i, entry in enumerate(entries):
            lines.append(f"=> /admin/delete/{i} [{i}] {entry['name']}: {entry['message'][:30]}...")
        content = "\n".join(lines)

    return app.template(
        "base.gmi",
        title="Admin Panel",
        content=content,
        show_sign=False,
    )


@app.gemini("/admin/delete/{entry_id}")
@require_fingerprint(*ADMIN_FINGERPRINTS)
def admin_delete(request: Request, entry_id: int):
    if 0 <= entry_id < len(entries):
        deleted = entries.pop(entry_id)
        content = f"""Entry deleted:

> {deleted['message'][:100]}

=> /admin Back to Admin
"""
    else:
        content = """Entry not found.

=> /admin Back to Admin
"""

    return app.template(
        "base.gmi",
        title="Entry Deleted",
        content=content,
        show_sign=False,
    )


if __name__ == "__main__":
    app.run()
```

## Step 4: Add Middleware

Let's add logging and timing middleware:

```python
from xitzin.middleware import LoggingMiddleware, TimingMiddleware

# Add at the top of app.py, after creating the app
app.add_middleware(TimingMiddleware())
app.add_middleware(LoggingMiddleware())
```

Or create custom middleware:

```python
@app.middleware
async def count_requests(request: Request, call_next):
    if not hasattr(app.state, "request_count"):
        app.state.request_count = 0
    app.state.request_count += 1

    response = await call_next(request)
    return response
```

## Step 5: Add Lifecycle Events

Add startup and shutdown handlers:

```python
@app.on_startup
async def startup():
    print("Guestbook starting up...")
    # In production, connect to database here
    app.state.pending_signs = {}

@app.on_shutdown
async def shutdown():
    print(f"Guestbook shutting down. Total requests: {app.state.request_count}")
    # In production, close database connections here
```

## Step 6: Write Tests

Create `test_app.py`:

```python
from xitzin.testing import TestClient, test_app
from app import app, entries

def test_home_page():
    client = TestClient(app)
    response = client.get("/")

    assert response.is_success
    assert "Guestbook" in response.body


def test_entries_empty():
    entries.clear()
    client = TestClient(app)
    response = client.get("/entries")

    assert response.is_success
    assert "No entries yet" in response.body


def test_sign_requires_certificate():
    client = TestClient(app)
    response = client.get("/sign")

    assert response.is_certificate_required


def test_sign_with_certificate():
    entries.clear()
    client = TestClient(app)
    auth_client = client.with_certificate("test-user-123")

    # Start signing
    response = auth_client.get("/sign")
    assert response.is_success

    # Enter name
    response = auth_client.get_input("/sign/name", "Test User")
    assert response.is_success

    # Enter message
    response = auth_client.get_input("/sign/message", "Hello, world!")
    assert response.is_success
    assert "Thanks for signing" in response.body

    # Verify entry was added
    assert len(entries) == 1
    assert entries[0]["name"] == "Test User"
    assert entries[0]["message"] == "Hello, world!"


def test_admin_requires_specific_fingerprint():
    client = TestClient(app)

    # No certificate
    response = client.get("/admin")
    assert response.status == 60

    # Wrong certificate
    auth_client = client.with_certificate("unauthorized-user")
    response = auth_client.get("/admin")
    assert response.status == 61  # Not Authorized


def test_with_lifecycle():
    entries.clear()

    with test_app(app) as client:
        # Startup has run
        assert hasattr(app.state, "pending_signs")

        # Make some requests
        response = client.get("/")
        assert response.is_success
```

Run tests:

```bash
uv run pytest test_app.py -v
```

## Step 7: Run the Application

Generate certificates and run:

```bash
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes -subj "/CN=localhost"
python app.py
```

## Complete Project Code

Here's the final `app.py`:

```python
from datetime import datetime
from pathlib import Path

from xitzin import Xitzin, Request
from xitzin.auth import (
    require_certificate,
    require_fingerprint,
    optional_certificate,
    get_identity,
)
from xitzin.middleware import LoggingMiddleware, TimingMiddleware

app = Xitzin(
    title="Guestbook",
    templates_dir=Path(__file__).parent / "templates",
)

# Add middleware
app.add_middleware(TimingMiddleware())
app.add_middleware(LoggingMiddleware())

# Storage
entries = []
ADMIN_FINGERPRINTS = ["your-admin-fingerprint-here"]


@app.on_startup
async def startup():
    print("Guestbook starting up...")
    app.state.pending_signs = {}
    app.state.request_count = 0


@app.on_shutdown
async def shutdown():
    print(f"Shutting down. Total requests: {app.state.request_count}")


@app.middleware
async def count_requests(request: Request, call_next):
    app.state.request_count += 1
    return await call_next(request)


@app.gemini("/")
@optional_certificate
def home(request: Request):
    identity = request.state.identity
    lines = ["# Guestbook", "", "Welcome to my guestbook!", ""]

    if entries:
        lines.append("Recent entries:")
        for entry in entries[-3:]:
            lines.append(f"* {entry['name']}: {entry['message'][:50]}...")
        lines.append("")

    lines.extend([
        "=> /entries View all entries",
        "=> /sign Sign the guestbook",
    ])

    if identity:
        lines.append(f"")
        lines.append(f"Signed in as: {identity.short_id}")

    return "\n".join(lines)


@app.gemini("/entries")
def view_entries(request: Request):
    lines = ["# Guestbook Entries", ""]

    if not entries:
        lines.append("No entries yet. Be the first to sign!")
    else:
        for entry in reversed(entries):
            lines.extend([
                f"## {entry['name']}",
                f"> {entry['message']}",
                f"Signed on {entry['date']}",
                "",
            ])

    lines.extend(["=> /sign Sign the guestbook", "=> / Home"])
    return "\n".join(lines)


@app.input("/sign", prompt="Enter your name:")
@require_certificate
def sign_name(request: Request, query: str):
    identity = get_identity(request)
    app.state.pending_signs[identity.fingerprint] = query

    return f"""# Name Saved

Your name: {query}

=> /sign/message Write your message
=> / Cancel
"""


@app.input("/sign/message", prompt="Write your message:")
@require_certificate
def sign_message(request: Request, query: str):
    identity = get_identity(request)
    name = app.state.pending_signs.pop(identity.fingerprint, identity.short_id)

    entries.append({
        "name": name,
        "message": query,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "fingerprint": identity.fingerprint,
    })

    return f"""# Thanks, {name}!

Your message has been added.

=> /entries View all entries
=> / Home
"""


@app.gemini("/admin")
@require_fingerprint(*ADMIN_FINGERPRINTS)
def admin(request: Request):
    lines = ["# Admin Panel", ""]

    if not entries:
        lines.append("No entries to manage.")
    else:
        for i, entry in enumerate(entries):
            lines.append(f"=> /admin/delete/{i} Delete: {entry['name']}")

    lines.extend(["", "=> / Home"])
    return "\n".join(lines)


@app.gemini("/admin/delete/{entry_id}")
@require_fingerprint(*ADMIN_FINGERPRINTS)
def delete_entry(request: Request, entry_id: int):
    if 0 <= entry_id < len(entries):
        deleted = entries.pop(entry_id)
        return f"# Deleted\n\nRemoved entry by {deleted['name']}\n\n=> /admin Back"
    return "# Not Found\n\n=> /admin Back"


if __name__ == "__main__":
    app.run()
```

## Key Concepts Covered

1. **Routing**: Multiple routes with path parameters
2. **Templates**: Using Jinja2 templates for Gemtext
3. **User Input**: Chained inputs for multi-step forms
4. **Authentication**: Certificate-based auth with `@require_certificate`
5. **Authorization**: Admin access with `@require_fingerprint`
6. **Middleware**: Request logging and timing
7. **Lifecycle**: Startup and shutdown handlers
8. **Testing**: Comprehensive test coverage

## Next Steps

Congratulations! You've built a complete Gemini application. Explore more:

- [Deployment guide](../how-to/deployment.md) for production
- [Middleware patterns](../how-to/middleware.md) for advanced use cases
- [API Reference](../reference/index.md) for all available features
