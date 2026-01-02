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
