# Responses

## Return a String

The simplest response - returns status 20 with `text/gemini` MIME type:

```python
@app.gemini("/")
def home(request: Request):
    return "# Welcome!"
```

## Custom MIME Type

Use the `Response` class for different content types:

```python
from xitzin import Response

@app.gemini("/data.json")
def json_data(request: Request):
    return Response(
        body='{"message": "hello"}',
        mime_type="application/json"
    )

@app.gemini("/plain.txt")
def plain_text(request: Request):
    return Response(
        body="Plain text content",
        mime_type="text/plain"
    )
```

## Request Input

Use the `Input` class to prompt for user input:

```python
from xitzin import Input

@app.gemini("/search")
def search(request: Request):
    if not request.query:
        return Input(prompt="Enter search query:")
    return f"Results for: {request.query}"

@app.gemini("/login")
def login(request: Request):
    if not request.query:
        return Input(prompt="Enter password:", sensitive=True)
    # Validate password...
```

## Redirect

Use the `Redirect` class:

```python
from xitzin import Redirect

@app.gemini("/old-page")
def old_page(request: Request):
    return Redirect(url="/new-page")

@app.gemini("/moved")
def moved(request: Request):
    return Redirect(url="/new-location", permanent=True)
```

- `permanent=False` (default): Status 30 (temporary redirect)
- `permanent=True`: Status 31 (permanent redirect)

## Tuple Response

For full control, return a tuple:

```python
# (body, status)
@app.gemini("/custom-status")
def custom_status(request: Request):
    return ("# Custom Response", 20)

# (body, status, meta)
@app.gemini("/full-control")
def full_control(request: Request):
    return ("Binary data here", 20, "application/octet-stream")
```

## Template Response

Use templates for complex Gemtext:

```python
@app.gemini("/page")
def page(request: Request):
    return app.template(
        "page.gmi",
        title="My Page",
        items=["One", "Two", "Three"]
    )
```

## Return None

Returning `None` sends an empty success response:

```python
@app.gemini("/empty")
def empty(request: Request):
    return None  # Status 20 with empty body
```

## Response Conversion Table

| Return Type | Status | MIME Type |
|-------------|--------|-----------|
| `str` | 20 | `text/gemini` |
| `Response(body, mime)` | 20 | Custom |
| `Input(prompt)` | 10 | Prompt text |
| `Input(prompt, sensitive=True)` | 11 | Prompt text |
| `Redirect(url)` | 30 | Target URL |
| `Redirect(url, permanent=True)` | 31 | Target URL |
| `TemplateResponse` | 20 | `text/gemini` |
| `(body, status)` | Custom | Auto |
| `(body, status, meta)` | Custom | Custom |
| `None` | 20 | Empty |
