# Testing

## Create a Test Client

```python
from xitzin.testing import TestClient

client = TestClient(app)
```

## Make Requests

Use `client.get()` to make requests:

```python
def test_home():
    client = TestClient(app)
    response = client.get("/")

    assert response.is_success
    assert "Welcome" in response.body
```

## Test Path Parameters

```python
def test_user_profile():
    client = TestClient(app)
    response = client.get("/user/alice")

    assert response.is_success
    assert "alice" in response.body
```

## Test Query Strings

Pass query strings with the `query` parameter:

```python
def test_search():
    client = TestClient(app)
    response = client.get("/search", query="python")

    assert response.is_success
    assert "python" in response.body
```

## Test Input Flow

Test the two-step input process:

```python
def test_input_prompt():
    client = TestClient(app)

    # First request: get the prompt
    response = client.get("/search")
    assert response.is_input_required
    assert response.input_prompt == "Enter search query:"

def test_input_submission():
    client = TestClient(app)

    # Submit input
    response = client.get_input("/search", "hello world")
    assert response.is_success
    assert "hello world" in response.body
```

## Test with Certificates

Simulate certificate authentication:

```python
def test_requires_certificate():
    client = TestClient(app)
    response = client.get("/private")

    assert response.status == 60  # Certificate Required

def test_with_certificate():
    client = TestClient(app)
    auth_client = client.with_certificate("test-fingerprint-123")

    response = auth_client.get("/private")
    assert response.is_success
```

## Response Properties

The `TestResponse` provides convenient properties:

```python
response = client.get("/page")

# Status checks
response.is_success           # True for 2x status
response.is_input_required    # True for 1x status
response.is_redirect          # True for 3x status
response.is_error             # True for 4x/5x/6x status
response.is_certificate_required  # True for 6x status

# Data access
response.status              # Status code (int)
response.meta                # Meta field (str)
response.body                # Response body (str or None)
response.mime_type           # MIME type for success responses
response.input_prompt        # Prompt for input responses
response.redirect_url        # URL for redirects
```

## Test Lifecycle Events

Use `test_app()` to run startup/shutdown handlers:

```python
from xitzin.testing import test_app

def test_with_lifecycle():
    with test_app(app) as client:
        # Startup handlers have run
        response = client.get("/")
        assert response.is_success
    # Shutdown handlers have run
```

## Test Middleware

Middleware runs automatically during tests:

```python
def test_timing_middleware():
    # Assuming TimingMiddleware is registered
    client = TestClient(app)
    response = client.get("/")

    # The handler can access request.state.elapsed_time
    assert response.is_success
```

## Pytest Fixtures

Create reusable fixtures:

```python
import pytest
from xitzin.testing import TestClient

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def auth_client(client):
    return client.with_certificate("test-user-123")

def test_home(client):
    response = client.get("/")
    assert response.is_success

def test_private(auth_client):
    response = auth_client.get("/private")
    assert response.is_success
```

## Test Templates

Templates render during tests:

```python
def test_template_rendering():
    client = TestClient(app)
    response = client.get("/page")

    assert response.is_success
    assert "# Page Title" in response.body
    assert "* Item 1" in response.body
```

## Complete Test Example

```python
import pytest
from xitzin.testing import TestClient, test_app
from myapp import app, users

@pytest.fixture
def client():
    users.clear()  # Reset state
    return TestClient(app)

@pytest.fixture
def auth_client(client):
    return client.with_certificate("test-user")

class TestPublicPages:
    def test_home(self, client):
        response = client.get("/")
        assert response.is_success
        assert "Welcome" in response.body

    def test_about(self, client):
        response = client.get("/about")
        assert response.is_success

class TestAuthentication:
    def test_private_requires_cert(self, client):
        response = client.get("/private")
        assert response.status == 60

    def test_private_with_cert(self, auth_client):
        response = auth_client.get("/private")
        assert response.is_success

class TestRegistration:
    def test_registration_flow(self, auth_client):
        # Enter name
        response = auth_client.get_input("/register", "Alice")
        assert response.is_success
        assert "Welcome, Alice" in response.body
```
