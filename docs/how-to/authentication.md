# Authentication

## Require Any Certificate

Use `@require_certificate` to require authentication:

```python
from xitzin.auth import require_certificate

@app.gemini("/private")
@require_certificate
def private_page(request: Request):
    return "# Private Content"
```

If no certificate is provided, the client receives status 60 (Certificate Required).

## Get User Identity

Access certificate information with `get_identity()`:

```python
from xitzin.auth import require_certificate, get_identity

@app.gemini("/whoami")
@require_certificate
def whoami(request: Request):
    identity = get_identity(request)

    return f"""# Your Identity

Fingerprint: {identity.fingerprint}
Short ID: {identity.short_id}
"""
```

The `CertificateIdentity` provides:

- `fingerprint`: Full SHA-256 hash (64 chars)
- `short_id`: First 16 characters for display
- `cert`: Raw certificate object

## Restrict to Specific Certificates

Use `@require_fingerprint()` for whitelist-based access:

```python
from xitzin.auth import require_fingerprint

ADMIN_CERTS = [
    "a1b2c3d4e5f6...",  # Alice
    "f6e5d4c3b2a1...",  # Bob
]

@app.gemini("/admin")
@require_fingerprint(*ADMIN_CERTS)
def admin_panel(request: Request):
    return "# Admin Panel"
```

Returns:

- Status 60 if no certificate
- Status 61 if certificate not in list

## Optional Authentication

Use `@optional_certificate` to personalize without requiring auth:

```python
from xitzin.auth import optional_certificate

@app.gemini("/")
@optional_certificate
def home(request: Request):
    identity = request.state.identity

    if identity:
        return f"# Welcome back, {identity.short_id}!"
    return "# Welcome, visitor!"
```

## Check Certificate Directly

Access certificate via the request:

```python
@app.gemini("/check")
def check_cert(request: Request):
    if request.client_cert_fingerprint:
        return f"Certificate: {request.client_cert_fingerprint[:16]}..."
    return "No certificate provided"
```

Properties:

- `request.client_cert`: The certificate object (or None)
- `request.client_cert_fingerprint`: SHA-256 fingerprint (or None)

## Build a User System

```python
# Simple user store
users = {}

@app.gemini("/register")
@require_certificate
def register(request: Request):
    identity = get_identity(request)

    if identity.fingerprint in users:
        return f"# Already registered as {users[identity.fingerprint]['name']}"

    return "=> /register/name Choose a username"

@app.input("/register/name", prompt="Choose a username:")
@require_certificate
def register_name(request: Request, query: str):
    identity = get_identity(request)

    users[identity.fingerprint] = {
        "name": query,
        "registered": datetime.now(),
    }

    return f"# Welcome, {query}!"

@app.gemini("/profile")
@require_certificate
def profile(request: Request):
    identity = get_identity(request)
    user = users.get(identity.fingerprint)

    if not user:
        return "=> /register Please register first"

    return f"""# {user['name']}'s Profile

Registered: {user['registered']}
Certificate: {identity.short_id}
"""
```

## Decorator Order

When combining decorators, `@require_certificate` should be closest to the function:

```python
# Correct order
@app.gemini("/admin")
@require_certificate
def admin(request: Request):
    ...

# Also correct
@app.input("/private", prompt="Enter data:")
@require_certificate
def private_input(request: Request, query: str):
    ...
```
