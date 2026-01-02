# Middleware

## Function-Based Middleware

The simplest way to create middleware:

```python
@app.middleware
async def log_requests(request: Request, call_next):
    print(f"Request: {request.path}")
    response = await call_next(request)
    print(f"Response: {response.status}")
    return response
```

The middleware:

1. Receives the request and a `call_next` function
2. Can modify the request before calling `call_next`
3. Calls `call_next(request)` to continue processing
4. Can modify the response before returning it

## Class-Based Middleware

For more complex middleware, extend `BaseMiddleware`:

```python
from xitzin.middleware import BaseMiddleware
from nauyaca import GeminiResponse

class MyMiddleware(BaseMiddleware):
    async def before_request(self, request: Request):
        # Called before the handler
        # Return None to continue
        # Return Request to modify the request
        # Return GeminiResponse to short-circuit
        print(f"Before: {request.path}")
        return None

    async def after_response(self, request: Request, response: GeminiResponse):
        # Called after the handler
        print(f"After: {response.status}")
        return response
```

Register it:

```python
app.add_middleware(MyMiddleware())
```

## Built-in Middleware

### TimingMiddleware

Tracks request processing time:

```python
from xitzin.middleware import TimingMiddleware

app.add_middleware(TimingMiddleware())

@app.gemini("/")
def home(request: Request):
    elapsed = getattr(request.state, 'elapsed_time', 0)
    return f"Request took {elapsed:.3f} seconds"
```

### LoggingMiddleware

Logs requests and responses:

```python
from xitzin.middleware import LoggingMiddleware

# With default print logging
app.add_middleware(LoggingMiddleware())

# With custom logger
import logging
logger = logging.getLogger(__name__)
app.add_middleware(LoggingMiddleware(logger=logger.info))
```

### RateLimitMiddleware

Simple rate limiting by certificate:

```python
from xitzin.middleware import RateLimitMiddleware

app.add_middleware(RateLimitMiddleware(
    max_requests=10,      # Max requests per window
    window_seconds=60.0,  # Time window
    retry_after=30        # Seconds to wait when rate limited
))
```

## Middleware Order

Middleware runs in the order registered (first registered runs first):

```python
@app.middleware
async def first(request, call_next):
    print("1. First - before")
    response = await call_next(request)
    print("4. First - after")
    return response

@app.middleware
async def second(request, call_next):
    print("2. Second - before")
    response = await call_next(request)
    print("3. Second - after")
    return response

# Output:
# 1. First - before
# 2. Second - before
# [handler runs]
# 3. Second - after
# 4. First - after
```

## Short-Circuit Response

Return a response early to skip the handler:

```python
from nauyaca import GeminiResponse, StatusCode

class MaintenanceMiddleware(BaseMiddleware):
    def __init__(self, maintenance_mode: bool = False):
        self.maintenance_mode = maintenance_mode

    async def before_request(self, request: Request):
        if self.maintenance_mode:
            return GeminiResponse(
                status=StatusCode.TEMPORARY_FAILURE,
                meta="Under maintenance"
            )
        return None
```

## Store Data in Request State

Pass data from middleware to handlers:

```python
@app.middleware
async def add_user_info(request: Request, call_next):
    if request.client_cert_fingerprint:
        request.state.user = get_user(request.client_cert_fingerprint)
    else:
        request.state.user = None

    return await call_next(request)

@app.gemini("/profile")
def profile(request: Request):
    user = request.state.user
    if user:
        return f"# Welcome, {user.name}!"
    return "# Anonymous User"
```

## Error Handling in Middleware

Wrap handler calls in try/except:

```python
@app.middleware
async def error_handler(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        print(f"Error: {e}")
        return GeminiResponse(
            status=StatusCode.TEMPORARY_FAILURE,
            meta="Something went wrong"
        )
```

## Combine Multiple Middleware

```python
from xitzin.middleware import (
    TimingMiddleware,
    LoggingMiddleware,
    RateLimitMiddleware,
)

# Add in desired order
app.add_middleware(TimingMiddleware())
app.add_middleware(LoggingMiddleware())
app.add_middleware(RateLimitMiddleware(max_requests=100))
```
