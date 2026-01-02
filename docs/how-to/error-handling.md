# Error Handling

## Raise Exceptions

Raise `GeminiException` subclasses to return status codes:

```python
from xitzin import NotFound, BadRequest

@app.gemini("/user/{user_id}")
def get_user(request: Request, user_id: int):
    user = database.get(user_id)
    if not user:
        raise NotFound(f"User {user_id} not found")
    return f"# {user.name}"

@app.gemini("/validate")
def validate(request: Request):
    if not request.query:
        raise BadRequest("Query parameter required")
    return f"Valid: {request.query}"
```

## Available Exceptions

### Input Required (1x)

```python
from xitzin import InputRequired, SensitiveInputRequired

raise InputRequired("Enter your name")  # Status 10
raise SensitiveInputRequired("Enter password")  # Status 11
```

### Temporary Failures (4x)

```python
from xitzin import (
    TemporaryFailure,
    ServerUnavailable,
    CGIError,
    ProxyError,
    SlowDown,
)

raise TemporaryFailure("Try again later")      # Status 40
raise ServerUnavailable("Maintenance mode")     # Status 41
raise CGIError("Script failed")                 # Status 42
raise ProxyError("Upstream failed")             # Status 43
raise SlowDown("Rate limited")                  # Status 44
```

### Permanent Failures (5x)

```python
from xitzin import (
    PermanentFailure,
    NotFound,
    Gone,
    ProxyRequestRefused,
    BadRequest,
)

raise PermanentFailure("Cannot process")        # Status 50
raise NotFound("Page not found")                # Status 51
raise Gone("Content removed")                   # Status 52
raise ProxyRequestRefused("Blocked")            # Status 53
raise BadRequest("Invalid input")               # Status 59
```

### Certificate Errors (6x)

```python
from xitzin import (
    CertificateRequired,
    CertificateNotAuthorized,
    CertificateNotValid,
)

raise CertificateRequired("Login required")     # Status 60
raise CertificateNotAuthorized("Not allowed")   # Status 61
raise CertificateNotValid("Cert expired")       # Status 62
```

## Custom Error Messages

Each exception accepts an optional message:

```python
# With custom message
raise NotFound("Article 123 does not exist")

# With default message
raise NotFound()  # Uses "Not found"
```

## Status Code Reference

| Status | Exception | Meaning |
|--------|-----------|---------|
| 10 | `InputRequired` | Input requested |
| 11 | `SensitiveInputRequired` | Sensitive input requested |
| 40 | `TemporaryFailure` | Temporary failure |
| 41 | `ServerUnavailable` | Server unavailable |
| 42 | `CGIError` | CGI error |
| 43 | `ProxyError` | Proxy error |
| 44 | `SlowDown` | Rate limited |
| 50 | `PermanentFailure` | Permanent failure |
| 51 | `NotFound` | Not found |
| 52 | `Gone` | Gone |
| 53 | `ProxyRequestRefused` | Proxy refused |
| 59 | `BadRequest` | Bad request |
| 60 | `CertificateRequired` | Certificate required |
| 61 | `CertificateNotAuthorized` | Not authorized |
| 62 | `CertificateNotValid` | Invalid certificate |

## Handle Errors in Middleware

Catch and handle errors globally:

```python
from nauyaca import GeminiResponse, StatusCode

@app.middleware
async def error_handler(request: Request, call_next):
    try:
        return await call_next(request)
    except GeminiException as e:
        # Let Xitzin handle GeminiExceptions normally
        raise
    except Exception as e:
        # Log unexpected errors
        print(f"Unexpected error: {e}")
        return GeminiResponse(
            status=StatusCode.TEMPORARY_FAILURE,
            meta="An unexpected error occurred"
        )
```

## Custom Exception Classes

Create domain-specific exceptions:

```python
class ArticleNotFound(NotFound):
    def __init__(self, article_id: int):
        super().__init__(f"Article {article_id} not found")
        self.article_id = article_id

@app.gemini("/article/{article_id}")
def get_article(request: Request, article_id: int):
    article = articles.get(article_id)
    if not article:
        raise ArticleNotFound(article_id)
    return f"# {article.title}"
```
