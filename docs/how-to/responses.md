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

### Redirect to Named Routes

Use `app.redirect()` to redirect to a named route:

```python
@app.gemini("/old-profile/{username}")
def old_profile(request: Request, username: str):
    # Redirect to the new profile route
    return request.app.redirect("user_profile", username=username)

@app.gemini("/user/{username}", name="user_profile")
def profile(request: Request, username: str):
    return f"# {username}'s Profile"
```

This is equivalent to:

```python
return Redirect(app.reverse("user_profile", username=username))
```

For permanent redirects:

```python
return request.app.redirect("user_profile", username=username, permanent=True)
```

## Build Links

Use the `Link` class to build Gemtext link lines:

```python
from xitzin import Link

@app.gemini("/")
def home(request: Request):
    links = [
        Link("/about", "About Us"),
        Link("/contact", "Contact"),
        Link("/blog"),  # No label
    ]
    return "# Home\n\n" + "\n".join(str(link) for link in links)
```

Output:

```
# Home

=> /about About Us
=> /contact Contact
=> /blog
```

### Link to Named Routes

Use `Link.to_route()` to build links using route names:

```python
from xitzin import Link

@app.gemini("/", name="home")
def home(request: Request):
    links = [
        Link.to_route(request.app, "user_profile", username="alice", label="Alice"),
        Link.to_route(request.app, "user_profile", username="bob", label="Bob"),
    ]
    return "# Users\n\n" + "\n".join(str(link) for link in links)

@app.gemini("/user/{username}", name="user_profile")
def profile(request: Request, username: str):
    # Link back to home
    home_link = Link.to_route(request.app, "home", label="Back to Home")
    return f"# {username}'s Profile\n\n{home_link}"
```

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

## Helper Classes

| Class | Purpose |
|-------|---------|
| `Link(url, label)` | Build Gemtext link lines (`=> url label`) |
| `Link.to_route(app, name, **params)` | Build link to named route |
