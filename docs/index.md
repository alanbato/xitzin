# Xitzin

**FastAPI for the Geminispace**

Xitzin is a Gemini Application Framework that brings the developer experience of FastAPI to the [Gemini protocol](https://geminiprotocol.net/). Build Gemini capsules with familiar patterns: decorators for routing, type-annotated path parameters, and Pydantic-powered validation.

## Quick Example

```python
from xitzin import Xitzin, Request

app = Xitzin()

@app.gemini("/")
def home(request: Request):
    return "# Welcome to my capsule!"

@app.gemini("/user/{username}")
def profile(request: Request, username: str):
    return f"# {username}'s Profile"

@app.input("/search", prompt="Enter search query:")
def search(request: Request, query: str):
    return f"# Results for: {query}"

if __name__ == "__main__":
    app.run()
```

## Key Features

<div class="grid cards" markdown>

-   :material-rocket-launch: **FastAPI-inspired API**

    ---

    Familiar decorator-based routing with `@app.gemini()` and automatic parameter extraction.

-   :material-shield-lock: **Certificate Authentication**

    ---

    Built-in decorators for certificate-based authentication with `@require_certificate`.

-   :material-file-document: **Jinja2 Templates**

    ---

    Gemtext-aware template engine with filters for links, headings, lists, and more.

-   :material-cog: **Middleware Support**

    ---

    Class-based and function-based middleware for logging, rate limiting, and custom processing.

-   :material-test-tube: **Testing Utilities**

    ---

    In-memory `TestClient` for testing your application without running a server.

-   :material-flash: **Async Support**

    ---

    Both sync and async handlers supported out of the box.

</div>

## HTTP vs Gemini: A Quick Comparison

If you're coming from web development, here's how Gemini differs:

| HTTP Concept | Gemini Equivalent |
|--------------|-------------------|
| `GET /path` | `gemini://host/path` |
| Query strings `?q=foo` | Input prompts (status 10/11) |
| Cookies/Sessions | Client certificates |
| HTML | Gemtext (`.gmi`) |
| OAuth/JWT | Certificate fingerprints |
| `@app.get()` | `@app.gemini()` |

## Installation

```bash
pip install xitzin
```

Or with uv:

```bash
uv add xitzin
```

## Next Steps

<div class="grid cards" markdown>

-   :material-clock-fast: [**Quickstart**](getting-started/quickstart.md)

    ---

    Build your first Gemini capsule in 5 minutes.

-   :material-school: [**Tutorials**](tutorials/index.md)

    ---

    Step-by-step guides to learn Xitzin.

-   :material-book-open-variant: [**How-to Guides**](how-to/index.md)

    ---

    Task-oriented guides for specific features.

-   :material-api: [**API Reference**](reference/index.md)

    ---

    Complete API documentation.

</div>
