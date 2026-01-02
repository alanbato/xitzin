# Xitzin

**Application Framework for the Geminispace**

Xitzin brings a modern Python developer experience to the [Gemini protocol](https://geminiprotocol.net/). Build Gemini capsules with familiar patterns: decorators for routing and type-annotated path parameters.

```python
from xitzin import Xitzin, Request

app = Xitzin()

@app.gemini("/")
def home(request: Request):
    return "# Welcome to my capsule!"

@app.gemini("/user/{username}")
def profile(request: Request, username: str):
    return f"# {username}'s Profile"

@app.input("/search", prompt="Enter query:")
def search(request: Request, query: str):
    return f"# Results for: {query}"

if __name__ == "__main__":
    app.run()
```

## Features

- **Decorator-based routing** with `@app.gemini()` and automatic path parameter extraction
- **User input handling** via `@app.input()` for Gemini's status 10/11 prompts
- **Certificate authentication** with `@require_certificate` and fingerprint whitelisting
- **Jinja2 templates** with Gemtext-aware filters (links, headings, lists)
- **Middleware support** for logging, rate limiting, and custom processing
- **Testing utilities** with in-memory `TestClient`
- **Async support** for both sync and async handlers

## Installation

```bash
pip install xitzin
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv add xitzin
```

## Quick Start

1. Create `app.py`:

```python
from xitzin import Xitzin, Request

app = Xitzin()

@app.gemini("/")
def home(request: Request):
    return "# Hello, Geminispace!"

if __name__ == "__main__":
    app.run()
```

2. Generate TLS certificates:

```bash
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes -subj "/CN=localhost"
```

3. Run your capsule:

```bash
python app.py
```

4. Visit `gemini://localhost/` with a Gemini client like [Astronomo](https://github.com/alanbato/astronomo/).

## Documentation

Full documentation is available at [xitzin.readthedocs.io](https://xitzin.readthedocs.io/).

## License

MIT
