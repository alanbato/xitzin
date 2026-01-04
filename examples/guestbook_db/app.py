"""Guestbook Example with SQLModel Database.

A guestbook application demonstrating SQLModel integration with Xitzin:
- SQLModel models for data persistence
- SessionMiddleware for automatic session management
- get_session() helper for database access
- Certificate-based authentication for signing

Setup:
    pip install xitzin[sqlmodel]
    python app.py

Database:
    SQLite database created at ./guestbook.db
    Tables auto-created on startup.
"""

from datetime import datetime, timezone

from sqlmodel import Field, select

from xitzin import Xitzin, Request
from xitzin.auth import get_identity, optional_certificate, require_certificate
from xitzin.sqlmodel import (
    SQLModel,
    create_engine,
    init_db,
    SessionMiddleware,
    get_session,
)


# Database Models
class GuestbookEntry(SQLModel, table=True):
    """A guestbook entry with author information."""

    __tablename__ = "entries"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=100)
    message: str = Field(max_length=500)
    fingerprint: str = Field(max_length=128)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# Application Setup
app = Xitzin(title="Guestbook DB")

# Database Setup
engine = create_engine(
    "sqlite:///./guestbook.db",
    echo=False,  # Set to True to log SQL queries
)

# Initialize database with lifecycle hooks
init_db(app, engine, create_tables=True)

# Session middleware - creates session per request
session_middleware = SessionMiddleware(engine)
app.middleware(session_middleware)


# Routes
@app.gemini("/", name="home")
@optional_certificate
def home(request: Request) -> str:
    """Home page showing recent entries."""
    session = get_session(request)
    identity = request.state.identity

    # Get 3 most recent entries
    statement = (
        select(GuestbookEntry).order_by(GuestbookEntry.created_at.desc()).limit(3)
    )
    entries = session.exec(statement).all()

    lines = ["# Guestbook (Database Edition)", "", "Welcome to my guestbook!", ""]

    if entries:
        lines.append("## Recent Entries")
        lines.append("")
        for entry in entries:
            preview = (
                entry.message[:50] + "..." if len(entry.message) > 50 else entry.message
            )
            lines.append(f"* {entry.name}: {preview}")
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
def view_entries(request: Request) -> str:
    """List all guestbook entries."""
    session = get_session(request)

    statement = select(GuestbookEntry).order_by(GuestbookEntry.created_at.desc())
    entries = session.exec(statement).all()

    lines = ["# All Guestbook Entries", ""]

    if not entries:
        lines.append("No entries yet. Be the first to sign!")
    else:
        lines.append(f"{len(entries)} entries total.")
        lines.append("")
        for entry in entries:
            lines.extend(
                [
                    f"## {entry.name}",
                    f"> {entry.message}",
                    f"Signed on {entry.created_at.strftime('%Y-%m-%d %H:%M')}",
                    "",
                ]
            )

    lines.extend(["=> /sign Sign the guestbook", "=> / Home"])
    return "\n".join(lines)


@app.input("/sign", prompt="Enter your name:", name="sign")
@require_certificate
def sign_name(request: Request, query: str) -> str:
    """First step: capture the user's name."""
    identity = get_identity(request)
    if not identity:
        return "# Error\n\nCertificate required."

    # Store name in pending state (using app.state temporarily)
    if not hasattr(request.app.state, "pending_signs"):
        request.app.state.pending_signs = {}
    request.app.state.pending_signs[identity.fingerprint] = query.strip()

    return f"""# Name Saved

Your name: {query}

=> /sign/message Write your message
=> / Cancel
"""


@app.input(
    "/sign/message", prompt="Write your message (max 500 chars):", name="sign_message"
)
@require_certificate
def sign_message(request: Request, query: str) -> str:
    """Second step: capture the message and save."""
    identity = get_identity(request)
    if not identity:
        return "# Error\n\nCertificate required."

    # Get pending name
    pending = getattr(request.app.state, "pending_signs", {})
    name = pending.pop(identity.fingerprint, identity.short_id)

    # Validate message
    message = query.strip()
    if not message:
        return "# Error\n\nMessage cannot be empty.\n\n=> /sign Try again"

    if len(message) > 500:
        return "# Error\n\nMessage too long (max 500 characters).\n\n=> /sign Try again"

    # Create entry
    session = get_session(request)
    entry = GuestbookEntry(
        name=name,
        message=message,
        fingerprint=identity.fingerprint,
    )
    session.add(entry)
    # Commit handled by middleware

    return f"""# Thanks, {name}!

Your message has been added to the guestbook.

=> /entries View all entries
=> / Home
"""


if __name__ == "__main__":
    app.run()
