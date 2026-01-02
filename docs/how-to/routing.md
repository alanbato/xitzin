# Routing

## Define a Route

Use the `@app.gemini()` decorator to define a route:

```python
@app.gemini("/")
def home(request: Request):
    return "# Home Page"

@app.gemini("/about")
def about(request: Request):
    return "# About"
```

## Extract Path Parameters

Use curly braces to define path parameters:

```python
@app.gemini("/user/{username}")
def user_profile(request: Request, username: str):
    return f"# {username}'s Profile"
```

The parameter name in the path must match the function parameter name.

## Type Conversion

Add type hints to automatically convert parameters:

```python
@app.gemini("/post/{post_id}")
def get_post(request: Request, post_id: int):
    # post_id is automatically converted to int
    return f"# Post #{post_id}"

@app.gemini("/price/{amount}")
def show_price(request: Request, amount: float):
    return f"Price: ${amount:.2f}"
```

Supported types:

| Type | Example | Converts |
|------|---------|----------|
| `str` | `"hello"` | No conversion |
| `int` | `"42"` → `42` | Integers |
| `float` | `"3.14"` → `3.14` | Decimals |
| `bool` | `"true"` → `True` | Booleans |

## Match Path Segments with Slashes

Use `:path` to match segments containing slashes:

```python
@app.gemini("/files/{filepath:path}")
def get_file(request: Request, filepath: str):
    # filepath can be "docs/readme.md" or "images/photo.jpg"
    return f"File: {filepath}"
```

Without `:path`, a parameter only matches a single segment.

## Multiple Parameters

Combine multiple parameters:

```python
@app.gemini("/user/{username}/post/{post_id}")
def user_post(request: Request, username: str, post_id: int):
    return f"# {username}'s Post #{post_id}"
```

## Route Order

Routes are matched in the order they're defined. More specific routes should come first:

```python
# This order works correctly
@app.gemini("/user/settings")
def user_settings(request: Request):
    return "# Settings"

@app.gemini("/user/{username}")
def user_profile(request: Request, username: str):
    return f"# {username}"
```

If you reverse the order, `/user/settings` would be captured by the `{username}` parameter.

## Access URL Information

The `Request` object provides URL information:

```python
@app.gemini("/debug")
def debug(request: Request):
    return f"""# Request Info

Path: {request.path}
URL: {request.url}
Hostname: {request.hostname}
Port: {request.port}
Query: {request.query}
"""
```

## Name Routes

Give routes a name for URL reversing:

```python
# Auto-named after the function (name="home")
@app.gemini("/")
def home(request: Request):
    return "# Home"

# Explicit name
@app.gemini("/user/{username}", name="user_profile")
def profile(request: Request, username: str):
    return f"# {username}'s Profile"

# Input routes can be named too
@app.input("/search", prompt="Query:", name="search")
def search(request: Request, query: str):
    return f"Results: {query}"
```

By default, routes are named after their handler function. Use the `name=` parameter to override.

## Reverse URLs

Build URLs from route names using `app.reverse()`:

```python
@app.gemini("/")
def home(request: Request):
    # Build URL to another route
    profile_url = request.app.reverse("user_profile", username="alice")
    return f"# Home\n\n=> {profile_url} Visit Alice's Profile"

@app.gemini("/user/{username}", name="user_profile")
def profile(request: Request, username: str):
    return f"# {username}"
```

This avoids hardcoding URLs throughout your application. If the path changes, only the route definition needs updating.

### Multiple Parameters

```python
@app.gemini("/post/{year}/{month}/{slug}", name="blog_post")
def post(request: Request, year: int, month: int, slug: str):
    return f"# {slug}"

# Build URL with all parameters
url = app.reverse("blog_post", year=2024, month=12, slug="hello-world")
# Returns: "/post/2024/12/hello-world"
```

### Error Handling

```python
# Missing route name raises ValueError
app.reverse("nonexistent")
# ValueError: No route named 'nonexistent'. Available routes: home, user_profile

# Missing required parameter raises ValueError
app.reverse("user_profile")
# ValueError: Route 'user_profile' missing required parameters: username
```
