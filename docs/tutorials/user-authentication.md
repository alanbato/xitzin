# User Authentication

Gemini uses client certificates for authentication instead of passwords or OAuth. In this tutorial, you'll learn how to implement certificate-based authentication in your capsule.

## What You'll Learn

- How Gemini certificate authentication works
- Using `@require_certificate` for protected routes
- Accessing certificate information
- Whitelisting specific certificates with `@require_fingerprint`
- Optional authentication with `@optional_certificate`

## How Certificate Auth Works

In HTTP, authentication typically uses:

- Username/password
- OAuth tokens
- Session cookies

Gemini uses TLS client certificates:

1. The user generates a certificate (usually their Gemini client does this)
2. When visiting a protected page, the server requests a certificate
3. The client presents the certificate
4. The server identifies the user by their certificate fingerprint

This provides:

- **Persistent identity** without passwords
- **Cryptographic proof** of identity
- **User-controlled** credentials

## Step 1: Basic Protected Route

Create `auth_app.py`:

```python
from xitzin import Xitzin, Request
from xitzin.auth import require_certificate, get_identity

app = Xitzin(title="Auth Demo")

@app.gemini("/")
def home(request: Request):
    return """# Auth Demo

=> /public Public Page
=> /private Private Page (requires certificate)
=> /profile Your Profile
"""

@app.gemini("/public")
def public(request: Request):
    return """# Public Page

Anyone can see this!

=> / Home
"""

@app.gemini("/private")
@require_certificate
def private(request: Request):
    identity = get_identity(request)
    return f"""# Private Page

Welcome! Your certificate ID: {identity.short_id}

This page is only visible to authenticated users.

=> / Home
"""

if __name__ == "__main__":
    app.run()
```

The `@require_certificate` decorator:

- Returns status 60 (Certificate Required) if no certificate is provided
- Allows access if a valid certificate is presented
- Works with any valid client certificate

## Step 2: Understanding Certificate Identity

The `get_identity()` function returns a `CertificateIdentity` object:

```python
from xitzin.auth import get_identity, CertificateIdentity

@app.gemini("/whoami")
@require_certificate
def whoami(request: Request):
    identity: CertificateIdentity = get_identity(request)

    return f"""# Your Identity

Full fingerprint: {identity.fingerprint}
Short ID: {identity.short_id}

The fingerprint is a SHA-256 hash of your certificate.

=> / Home
"""
```

Properties of `CertificateIdentity`:

- `fingerprint`: Full SHA-256 hash (64 characters)
- `short_id`: First 16 characters (for display)
- `cert`: The raw certificate object (if available)

## Step 3: Admin Access with Fingerprint Whitelist

For admin panels, you might want to restrict access to specific certificates:

```python
from xitzin.auth import require_fingerprint

# List of allowed admin certificate fingerprints
ADMIN_FINGERPRINTS = [
    "a1b2c3d4e5f6789...",  # Alice's certificate
    "9876543210fedcba...",  # Bob's certificate
]

@app.gemini("/admin")
@require_fingerprint(*ADMIN_FINGERPRINTS)
def admin(request: Request):
    return """# Admin Panel

Welcome, administrator!

=> /admin/users Manage Users
=> /admin/content Manage Content
=> / Home
"""
```

The `@require_fingerprint()` decorator:

- Returns status 60 if no certificate is provided
- Returns status 61 (Certificate Not Authorized) if the fingerprint isn't in the list
- Only allows access to whitelisted certificates

## Step 4: Optional Authentication

Sometimes you want to show different content based on whether the user is authenticated:

```python
from xitzin.auth import optional_certificate

@app.gemini("/profile")
@optional_certificate
def profile(request: Request):
    identity = request.state.identity

    if identity:
        return f"""# Your Profile

Certificate ID: {identity.short_id}

You're authenticated! Here's your personalized content.

=> /settings Your Settings
=> / Home
"""
    else:
        return """# Profile

You're browsing anonymously.

To see your profile, please enable client certificates in your Gemini client.

=> / Home
"""
```

The `@optional_certificate` decorator:

- Sets `request.state.identity` to a `CertificateIdentity` or `None`
- Never blocks access
- Lets you customize content based on authentication status

## Step 5: Building a User System

Here's a more complete example with user registration:

```python
from xitzin import Xitzin, Request
from xitzin.auth import (
    require_certificate,
    optional_certificate,
    get_identity,
)

app = Xitzin(title="User System")

# Simple in-memory user store
users = {}

@app.gemini("/")
@optional_certificate
def home(request: Request):
    identity = request.state.identity

    if identity and identity.fingerprint in users:
        user = users[identity.fingerprint]
        return f"""# Welcome back, {user['name']}!

=> /dashboard Your Dashboard
=> /logout Sign Out
"""
    elif identity:
        return """# Welcome!

You have a certificate but haven't registered yet.

=> /register Register
"""
    else:
        return """# Welcome!

=> /about About This Capsule
"""

@app.gemini("/register")
@require_certificate
def register_start(request: Request):
    identity = get_identity(request)

    if identity.fingerprint in users:
        return """# Already Registered

You already have an account!

=> /dashboard Go to Dashboard
"""

    return f"""# Register

Your certificate ID: {identity.short_id}

=> /register/name Choose Your Name
"""

@app.input("/register/name", prompt="Enter your display name:")
@require_certificate
def register_name(request: Request, query: str):
    identity = get_identity(request)

    users[identity.fingerprint] = {
        "name": query,
        "created": "today",
    }

    return f"""# Registration Complete!

Welcome, {query}!

Your account is now linked to your certificate.

=> /dashboard Go to Dashboard
=> / Home
"""

@app.gemini("/dashboard")
@require_certificate
def dashboard(request: Request):
    identity = get_identity(request)
    user = users.get(identity.fingerprint)

    if not user:
        return "# Not Registered\n\n=> /register Register First"

    return f"""# Dashboard

Hello, {user['name']}!

Account created: {user['created']}

=> /dashboard/settings Settings
=> / Home
"""

@app.gemini("/logout")
def logout(request: Request):
    return """# Signed Out

To fully sign out, you may need to close your Gemini client or disable your certificate.

=> / Home
"""

if __name__ == "__main__":
    app.run()
```

## Testing with Certificates

When testing, you can simulate certificates:

```python
from xitzin.testing import TestClient

client = TestClient(app)

# Without certificate
response = client.get("/private")
assert response.status == 60  # Certificate Required

# With certificate
auth_client = client.with_certificate("test-fingerprint-123")
response = auth_client.get("/private")
assert response.is_success
```

## Key Takeaways

1. **`@require_certificate`** enforces authentication
2. **`@require_fingerprint()`** restricts to specific certificates
3. **`@optional_certificate`** enables optional personalization
4. **`get_identity()`** retrieves the certificate identity
5. **Fingerprints** are the primary way to identify users

## Security Considerations

- Fingerprints are public identifiers (like usernames)
- The private key never leaves the user's device
- Consider what happens if a user loses their certificate
- Provide a way to add multiple certificates to an account

## Next Steps

- Build a complete [guestbook](building-a-guestbook.md) with authentication
- Learn about [middleware](../how-to/middleware.md) for request logging
