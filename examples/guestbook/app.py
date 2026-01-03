"""Guestbook Example Application.

A complete guestbook application demonstrating Xitzin's features:
- Routing with path parameters
- User input handling (multi-step form)
- Certificate-based authentication
- Admin authorization with fingerprint checking
- Middleware for logging and timing
- Lifecycle events (startup/shutdown)
"""

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
ADMIN_FINGERPRINTS = ["your-admin-fingerprint-here"]


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


@app.gemini("/", name="home")
@optional_certificate
def home(request: Request):
    """Home page showing recent entries."""
    identity = request.state.identity
    lines = ["# Guestbook", "", "Welcome to my guestbook!", ""]

    if entries:
        lines.append("Recent entries:")
        for entry in entries[-3:]:
            trimmed_entry = min(entry["message"], f"{entry['message'][:50]}...")
            lines.append(f"* {entry['name']}: {trimmed_entry}")
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


if __name__ == "__main__":
    app.run()
