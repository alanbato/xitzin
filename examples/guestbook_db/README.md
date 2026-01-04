# Guestbook with Database

This example demonstrates SQLModel integration with Xitzin for database persistence.

## Features

- SQLite database with SQLModel ORM
- Session-per-request pattern via middleware
- Certificate-based authentication for posting
- CRUD operations (Create, Read)

## Setup

1. Install dependencies:

```bash
pip install xitzin[sqlmodel]
```

2. Run the application:

```bash
python app.py
```

3. Access with a Gemini client:

```
gemini://localhost:1965/
```

## Database

- **File**: `guestbook.db` (created automatically on first run)
- **Tables**: Auto-created on startup via `init_db()`

## Routes

| Path | Description |
|------|-------------|
| `/` | Home page with recent entries |
| `/entries` | List all entries |
| `/sign` | Sign guestbook (requires certificate) |
| `/sign/message` | Second step: enter message |

## Key Patterns

### Database Initialization

```python
from xitzin.sqlmodel import create_engine, init_db, SessionMiddleware

engine = create_engine("sqlite:///./guestbook.db")
init_db(app, engine, create_tables=True)
app.middleware(SessionMiddleware(engine))
```

### Using Sessions in Routes

```python
from xitzin.sqlmodel import get_session

@app.gemini("/entries")
def list_entries(request: Request):
    session = get_session(request)
    entries = session.exec(select(GuestbookEntry)).all()
    return render(entries)
```

### Creating Records

```python
@app.input("/sign/message", prompt="Your message:")
@require_certificate
def sign_message(request: Request, query: str):
    session = get_session(request)
    entry = GuestbookEntry(name=name, message=query)
    session.add(entry)
    # Commit handled automatically by SessionMiddleware
    return "# Success!"
```

## Testing with SQLModel

When testing Xitzin applications with SQLModel, use an **in-memory SQLite database** for fast, isolated tests that automatically clean up.

### Pytest Fixtures Pattern

```python
# conftest.py
import pytest
from sqlmodel import Session, SQLModel
from sqlmodel.pool import StaticPool

from xitzin import Xitzin
from xitzin.sqlmodel import create_engine, init_db, SessionMiddleware
from xitzin.testing import test_app


@pytest.fixture
def app():
    """Fresh Xitzin app for each test."""
    return Xitzin()


@pytest.fixture
def test_engine():
    """In-memory database engine - fresh per test."""
    engine = create_engine(
        "sqlite://",  # In-memory (no file path)
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # Required for in-memory SQLite
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def client(app, test_engine):
    """Test client with database configured."""
    init_db(app, test_engine, create_tables=False)  # Already created
    app.middleware(SessionMiddleware(test_engine))

    with test_app(app) as client:
        yield client
```

### Writing Tests

```python
# test_guestbook.py
from sqlmodel import Session

from app import GuestbookEntry


def test_list_entries_empty(client):
    """Test entries page with no data."""
    response = client.get("/entries")
    assert response.is_success
    assert "No entries yet" in response.body


def test_list_entries_with_data(client, test_engine):
    """Test entries page with seeded data."""
    # Seed test data
    with Session(test_engine) as session:
        entry = GuestbookEntry(
            name="Test User",
            message="Hello!",
            fingerprint="abc123"
        )
        session.add(entry)
        session.commit()

    response = client.get("/entries")
    assert response.is_success
    assert "Test User" in response.body
    assert "Hello!" in response.body
```

### Key Points

- **`"sqlite://"`**: Empty path creates in-memory database (no file to clean up)
- **`StaticPool`**: Required for in-memory SQLite to maintain single connection
- **`check_same_thread=False`**: SQLite threading compatibility
- **Per-test isolation**: Each test gets a fresh database
- **`test_app()` integration**: Runs startup/shutdown hooks correctly

### Session-Scoped Database (Faster)

For large test suites where tests don't modify data:

```python
@pytest.fixture(scope="session")
def shared_engine():
    """Shared database across all tests."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()
```

## Compared to In-Memory Guestbook

The original `examples/guestbook/` uses an in-memory list. This version:

- Persists data across restarts
- Uses proper database transactions
- Demonstrates SQLModel patterns
