"""Integration tests for the guestbook example application."""

import sys
from pathlib import Path

from xitzin.testing import TestClient
from xitzin.testing import test_app as run_with_lifecycle

import pytest

# Add examples directory to path so we can import the guestbook app
examples_dir = Path(__file__).parent.parent / "examples" / "guestbook"
sys.path.insert(0, str(examples_dir))


@pytest.fixture
def guestbook_app():
    """Import and return a fresh guestbook app instance."""
    # Import inside fixture to get fresh module each time
    import importlib
    import app as guestbook_module

    importlib.reload(guestbook_module)
    guestbook_module.entries.clear()
    return (
        guestbook_module.app,
        guestbook_module.entries,
        guestbook_module.ADMIN_FINGERPRINTS,
    )


class TestGuestbookHome:
    """Tests for guestbook home page."""

    def test_home_page_renders(self, guestbook_app):
        """Home page should render successfully."""
        app, _entries, _fingerprints = guestbook_app
        client = TestClient(app)
        response = client.get("/")

        assert response.is_success
        assert "Guestbook" in response.body

    def test_home_page_shows_recent_entries(self, guestbook_app):
        """Home page should show recent entries."""
        app, entries, _fingerprints = guestbook_app
        entries.append(
            {
                "name": "Alice",
                "message": "Hello!",
                "date": "2024-01-01 12:00",
                "fingerprint": "abc123",
            }
        )

        client = TestClient(app)
        response = client.get("/")

        assert response.is_success
        assert "Alice" in response.body


class TestGuestbookEntries:
    """Tests for entries listing."""

    def test_entries_empty(self, guestbook_app):
        """Entries page should indicate when empty."""
        app, _entries, _fingerprints = guestbook_app
        client = TestClient(app)
        response = client.get("/entries")

        assert response.is_success
        assert "No entries yet" in response.body

    def test_entries_with_data(self, guestbook_app):
        """Entries page should list all entries."""
        app, entries, _fingerprints = guestbook_app
        entries.extend(
            [
                {
                    "name": "Alice",
                    "message": "Hello!",
                    "date": "2024-01-01 12:00",
                    "fingerprint": "abc123",
                },
                {
                    "name": "Bob",
                    "message": "Hi there!",
                    "date": "2024-01-02 14:00",
                    "fingerprint": "def456",
                },
            ]
        )

        client = TestClient(app)
        response = client.get("/entries")

        assert response.is_success
        assert "Alice" in response.body
        assert "Bob" in response.body


class TestGuestbookSigning:
    """Tests for signing the guestbook."""

    def test_sign_prompts_for_name_without_query(self, guestbook_app):
        """First request to sign should prompt for name."""
        app, _entries, _fingerprints = guestbook_app
        client = TestClient(app)
        auth_client = client.with_certificate("test-user-123")

        response = auth_client.get("/sign")
        assert response.is_input_required
        assert "name" in response.input_prompt.lower()

    def test_sign_flow_complete(self, guestbook_app):
        """Complete signing flow should add entry."""
        app, entries, _fingerprints = guestbook_app
        client = TestClient(app)
        auth_client = client.with_certificate("test-user-123")

        # Enter name
        response = auth_client.get_input("/sign", "Test User")
        assert response.is_success
        assert "Test User" in response.body

        # Enter message
        response = auth_client.get_input("/sign/message", "Hello, world!")
        assert response.is_success
        assert "Thanks" in response.body

        # Verify entry was added
        assert len(entries) == 1
        assert entries[0]["name"] == "Test User"
        assert entries[0]["message"] == "Hello, world!"

    def test_sign_message_requires_certificate(self, guestbook_app):
        """Submitting a message requires a certificate."""
        app, _entries, _fingerprints = guestbook_app
        client = TestClient(app)

        # Try to submit without certificate
        response = client.get_input("/sign/message", "Trying to sign")
        assert response.is_certificate_required


class TestGuestbookAdmin:
    """Tests for admin functionality."""

    def test_admin_requires_certificate(self, guestbook_app):
        """Admin panel requires a certificate."""
        app, _entries, _fingerprints = guestbook_app
        client = TestClient(app)

        response = client.get("/admin")
        assert response.status == 60  # Certificate required

    def test_admin_requires_authorized_fingerprint(self, guestbook_app):
        """Admin panel requires authorized fingerprint."""
        app, _entries, _fingerprints = guestbook_app
        client = TestClient(app)

        # Wrong certificate
        auth_client = client.with_certificate("unauthorized-user")
        response = auth_client.get("/admin")
        assert response.status == 61  # Not authorized

    def test_admin_delete_entry(self, guestbook_app):
        """Admin should be able to delete entries."""
        app, entries, admin_fingerprints = guestbook_app
        entries.append(
            {
                "name": "Spam",
                "message": "Buy stuff!",
                "date": "2024-01-01 12:00",
                "fingerprint": "spammer",
            }
        )

        client = TestClient(app)
        # Use the admin fingerprint from the app
        auth_client = client.with_certificate(admin_fingerprints[0])

        response = auth_client.get("/admin/delete/0")
        assert response.is_success
        assert "Deleted" in response.body
        assert len(entries) == 0

    def test_admin_delete_invalid_index(self, guestbook_app):
        """Deleting non-existent entry should show error."""
        app, _entries, admin_fingerprints = guestbook_app
        client = TestClient(app)
        auth_client = client.with_certificate(admin_fingerprints[0])

        response = auth_client.get("/admin/delete/999")
        assert response.is_success
        assert "Not Found" in response.body


class TestGuestbookLifecycle:
    """Tests for application lifecycle."""

    def test_lifecycle_initializes_state(self, guestbook_app):
        """Test with startup/shutdown lifecycle."""
        app, _entries, _fingerprints = guestbook_app

        with run_with_lifecycle(app) as client:
            # Startup has run
            assert hasattr(app.state, "pending_signs")
            assert hasattr(app.state, "request_count")

            # Make some requests
            response = client.get("/")
            assert response.is_success
