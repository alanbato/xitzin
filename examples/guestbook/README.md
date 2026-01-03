# Guestbook Example

A complete guestbook application demonstrating Xitzin's features.

## Features Demonstrated

- **Routing**: Multiple routes with path parameters (`/admin/delete/{entry_id}`)
- **User Input**: Multi-step form flow with `@app.input` decorator
- **Authentication**: Certificate-based auth with `@require_certificate`
- **Authorization**: Admin access with `@require_fingerprint`
- **Middleware**: Request logging and timing
- **Lifecycle Events**: Startup and shutdown handlers
- **Testing**: Comprehensive test suite with `TestClient`

## Quick Start

1. Install dependencies:

   ```bash
   cd examples/guestbook
   uv sync
   ```

2. Run the application:

   ```bash
   uv run python app.py
   ```

   The server will start at `gemini://localhost:1965/` using a self-signed certificate.

3. Connect with a Gemini client (e.g., Lagrange, Amfora, or any other Gemini browser).

## Running Tests

Tests for this example are part of the main test suite:

```bash
uv run pytest tests/test_example_app.py -v
```

## Project Structure

```
guestbook/
├── app.py              # Main application
├── templates/
│   └── base.gmi        # Base template
└── README.md           # This file
```

## Admin Access

To use the admin panel, replace `"your-admin-fingerprint-here"` in `app.py` with your client certificate's SHA-256 fingerprint.

You can find your certificate's fingerprint by examining the certificate or checking the server logs when you connect with a client certificate.

## Using Templates

The example includes a base template that can be used with `app.template()`:

```python
return app.template(
    "base.gmi",
    title="Page Title",
    content="Page content here",
    show_sign=True,
)
```

## Production Considerations

- Replace in-memory `entries` list with a proper database
- Use real TLS certificates instead of self-signed
- Configure rate limiting for spam protection
- Implement input validation and sanitization
