# Comparison to FastAPI

Xitzin is heavily inspired by FastAPI. This guide highlights the similarities and differences.

## Route Decorators

**FastAPI**:
```python
@app.get("/users/{user_id}")
def get_user(user_id: int):
    ...
```

**Xitzin**:
```python
@app.gemini("/users/{user_id}")
def get_user(request: Request, user_id: int):
    ...
```

Key difference: Xitzin handlers always receive `Request` as the first argument.

## Path Parameters

Both frameworks support path parameters with type conversion:

**FastAPI**:
```python
@app.get("/items/{item_id}")
def get_item(item_id: int, q: str = None):
    ...
```

**Xitzin**:
```python
@app.gemini("/items/{item_id}")
def get_item(request: Request, item_id: int):
    # No query parameters in Gemini!
    ...
```

Gemini doesn't have query parameters in the same way—user input comes via the input mechanism.

## User Input

**FastAPI** (query parameters and request body):
```python
@app.get("/search")
def search(q: str):
    return {"results": find(q)}

@app.post("/users")
def create_user(user: UserCreate):
    ...
```

**Xitzin** (input prompts):
```python
@app.input("/search", prompt="Enter search query:")
def search(request: Request, query: str):
    return f"# Results for {query}"

# No POST equivalent—all requests are "GET"-like
```

Gemini's input mechanism is simpler but more limited.

## Authentication

**FastAPI** (OAuth2, JWT, API keys):
```python
@app.get("/users/me")
def get_current_user(token: str = Depends(oauth2_scheme)):
    user = decode_token(token)
    return user
```

**Xitzin** (certificates):
```python
@app.gemini("/users/me")
@require_certificate
def get_current_user(request: Request):
    identity = get_identity(request)
    return f"# User: {identity.short_id}"
```

Certificate authentication is simpler but less flexible.

## Middleware

Both frameworks support middleware with similar patterns:

**FastAPI**:
```python
@app.middleware("http")
async def log_requests(request: Request, call_next):
    response = await call_next(request)
    return response
```

**Xitzin**:
```python
@app.middleware
async def log_requests(request: Request, call_next):
    response = await call_next(request)
    return response
```

Nearly identical!

## Response Types

**FastAPI**:
```python
# Dict → JSON
return {"message": "hello"}

# Custom response
return Response(content="hello", media_type="text/plain")

# Template
return templates.TemplateResponse("page.html", {"request": request})
```

**Xitzin**:
```python
# String → Gemtext
return "# Hello"

# Custom response
return Response(body="hello", mime_type="text/plain")

# Template
return app.template("page.gmi", title="Hello")
```

## Templates

**FastAPI** (Jinja2 for HTML):
```html
<html>
<body>
    <h1>{{ title }}</h1>
    <ul>
    {% for item in items %}
        <li>{{ item }}</li>
    {% endfor %}
    </ul>
</body>
</html>
```

**Xitzin** (Jinja2 for Gemtext):
```jinja
# {{ title }}

{% for item in items %}
* {{ item }}
{% endfor %}
```

Same template engine, different output format.

## Dependency Injection

**FastAPI**:
```python
def get_db():
    db = Database()
    try:
        yield db
    finally:
        db.close()

@app.get("/items")
def get_items(db: Database = Depends(get_db)):
    return db.query(Item).all()
```

**Xitzin**: No built-in dependency injection. Use lifecycle events and app state:

```python
@app.on_startup
async def startup():
    app.state.db = Database()

@app.on_shutdown
async def shutdown():
    app.state.db.close()

@app.gemini("/items")
def get_items(request: Request):
    return str(request.app.state.db.query(Item).all())
```

## Lifecycle Events

**FastAPI**:
```python
@app.on_event("startup")
async def startup():
    ...

@app.on_event("shutdown")
async def shutdown():
    ...
```

**Xitzin**:
```python
@app.on_startup
async def startup():
    ...

@app.on_shutdown
async def shutdown():
    ...
```

Nearly identical!

## Testing

**FastAPI**:
```python
from fastapi.testclient import TestClient

client = TestClient(app)
response = client.get("/")
assert response.status_code == 200
```

**Xitzin**:
```python
from xitzin.testing import TestClient

client = TestClient(app)
response = client.get("/")
assert response.is_success
```

Similar pattern, different status code handling.

## Feature Comparison Table

| Feature | FastAPI | Xitzin |
|---------|---------|--------|
| Decorator routing | ✅ | ✅ |
| Path parameters | ✅ | ✅ |
| Query parameters | ✅ | ❌ (use input) |
| Request body | ✅ | ❌ |
| Multiple HTTP methods | ✅ | ❌ (Gemini has one) |
| Middleware | ✅ | ✅ |
| Lifecycle events | ✅ | ✅ |
| Dependency injection | ✅ | ❌ |
| Pydantic validation | ✅ | Partial |
| Auto-docs (Swagger) | ✅ | ❌ |
| WebSockets | ✅ | ❌ |
| Background tasks | ✅ | ❌ |
| OAuth2/JWT | ✅ | ❌ (certificates) |
| Testing utilities | ✅ | ✅ |

## When to Choose Each

**Choose FastAPI when**:

- Building HTTP APIs
- Need complex request/response handling
- Want auto-generated documentation
- Need multiple HTTP methods
- Building for browsers or HTTP clients

**Choose Xitzin when**:

- Building for Geminispace
- Want simpler, content-focused applications
- Privacy is a priority
- Want to avoid the complexity of modern web
- Building for Gemini clients
