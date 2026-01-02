# Input Handling

## Basic Input with @app.input()

The simplest way to collect user input:

```python
@app.input("/search", prompt="Enter search query:")
def search(request: Request, query: str):
    return f"# Results for: {query}"
```

When a user visits `/search`:

1. First visit: They see the prompt "Enter search query:"
2. After submitting: The handler runs with their input in `query`

## Sensitive Input

For passwords and private data, use `sensitive=True`:

```python
@app.input("/login", prompt="Enter password:", sensitive=True)
def login(request: Request, query: str):
    if verify_password(query):
        return "# Welcome!"
    return "# Access denied"
```

The client will:

- Hide input as the user types
- Not save the input in history

## Manual Input Handling

For more control, use the `Input` response class:

```python
from xitzin import Input

@app.gemini("/custom-search")
def custom_search(request: Request):
    if not request.query:
        return Input(prompt="What would you like to find?")

    # Process the query
    return f"Searching for: {request.query}"
```

## Access Raw Query String

The query is URL-encoded by the client. Access both forms:

```python
@app.gemini("/query-info")
def query_info(request: Request):
    return f"""# Query Information

Decoded: {request.query}
Raw (URL-encoded): {request.raw_query}
"""
```

## Chain Multiple Inputs

Gemini only allows one input at a time. Chain them with redirects:

```python
# Store data between requests (use a proper session store in production)
sessions = {}

@app.input("/signup", prompt="Enter username:")
@require_certificate
def signup_username(request: Request, query: str):
    identity = get_identity(request)
    sessions[identity.fingerprint] = {"username": query}
    return "=> /signup/email Continue"

@app.input("/signup/email", prompt="Enter email:")
@require_certificate
def signup_email(request: Request, query: str):
    identity = get_identity(request)
    data = sessions.get(identity.fingerprint, {})
    data["email"] = query

    return f"""# Registration Complete

Username: {data.get('username')}
Email: {data.get('email')}
"""
```

## Validate Input

Validate input before processing:

```python
@app.input("/age", prompt="Enter your age:")
def get_age(request: Request, query: str):
    try:
        age = int(query)
        if age < 0 or age > 150:
            return "# Invalid age. Please try again.\n\n=> /age Try Again"
        return f"# You are {age} years old"
    except ValueError:
        return "# Please enter a number.\n\n=> /age Try Again"
```

## Optional Input

Make input optional by checking for it:

```python
@app.gemini("/browse")
def browse(request: Request):
    filter_term = request.query

    items = get_all_items()
    if filter_term:
        items = [i for i in items if filter_term.lower() in i.lower()]

    lines = ["# Browse Items", ""]
    lines.append("=> /browse?filter Enter a filter (optional)")
    lines.append("")
    for item in items:
        lines.append(f"* {item}")

    return "\n".join(lines)
```
