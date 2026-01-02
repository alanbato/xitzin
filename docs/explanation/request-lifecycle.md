# Request Lifecycle

How a request flows through Xitzin from arrival to response.

## Overview

```
Request Arrives
       ↓
   Route Matching
       ↓
   Input Flow Check
       ↓
   Middleware Chain (before)
       ↓
   Handler Execution
       ↓
   Response Conversion
       ↓
   Middleware Chain (after)
       ↓
   Exception Handling
       ↓
Response Sent
```

## Step 1: Request Arrives

A raw Gemini request arrives via Nauyaca:

```
gemini://example.com/user/alice?query\r\n
```

Xitzin wraps it in a `Request` object:

```python
request = Request(raw_request, app)
# request.path = "/user/alice"
# request.query = "query"
# request.client_cert = <cert or None>
```

## Step 2: Route Matching

The router searches for a matching route:

```python
match = router.match(request.path)
# Returns: (Route, {"username": "alice"}) or None
```

If no route matches:

```python
raise NotFound(f"No route matches: {request.path}")
```

## Step 3: Input Flow Check

For routes with `input_prompt`:

```python
@app.input("/search", prompt="Enter query:")
def search(request, query):
    ...
```

If no query is provided:

```python
if route.input_prompt and not request.query:
    return Input(route.input_prompt, route.sensitive_input)
```

If query is provided, it's added to the parameters:

```python
if route.input_prompt and request.query:
    params["query"] = request.query
```

## Step 4: Middleware Chain (Before)

Middleware wraps the handler in reverse registration order:

```python
# Registration order
@app.middleware
async def first(request, call_next): ...

@app.middleware
async def second(request, call_next): ...

# Execution order: first → second → handler → second → first
```

Each middleware can:

- **Modify the request** and pass it along
- **Short-circuit** by returning a response early
- **Add to request.state** for later middleware/handler

```python
@app.middleware
async def auth_check(request, call_next):
    if not request.client_cert:
        return GeminiResponse(status=60, meta="Login required")
    request.state.user = get_user(request.client_cert)
    return await call_next(request)
```

## Step 5: Handler Execution

The handler is called with the request and extracted parameters:

```python
result = await route.call_handler(request, params)
```

For sync handlers, they're wrapped in an executor:

```python
# Sync handler
def handler(request, username):
    return f"# {username}"

# Becomes
result = await asyncio.to_thread(handler, request, username)
```

Parameters are type-converted based on annotations:

```python
@app.gemini("/post/{post_id}")
def get_post(request, post_id: int):  # "42" → 42
    ...
```

## Step 6: Response Conversion

Handler return values are converted to `GeminiResponse`:

| Return Type | Conversion |
|-------------|------------|
| `str` | `GeminiResponse(status=20, meta="text/gemini", body=str)` |
| `Response` | Call `to_gemini_response()` |
| `Input` | Status 10/11 with prompt |
| `Redirect` | Status 30/31 with URL |
| `TemplateResponse` | Status 20 with rendered content |
| `tuple` | Custom status and meta |
| `None` | Empty success response |

## Step 7: Middleware Chain (After)

The response flows back through middleware in reverse order:

```python
class TimingMiddleware(BaseMiddleware):
    async def before_request(self, request):
        request.state.start_time = time.perf_counter()
        return None

    async def after_response(self, request, response):
        elapsed = time.perf_counter() - request.state.start_time
        request.state.elapsed_time = elapsed
        return response
```

Middleware can:

- **Modify the response** before it's sent
- **Log or track** request/response data
- **Add headers** (via custom response wrapping)

## Step 8: Exception Handling

Exceptions are caught and converted to responses:

```python
try:
    response = await handler(request)
except GeminiException as e:
    response = GeminiResponse(status=e.status_code, meta=e.message)
except Exception as e:
    response = GeminiResponse(
        status=StatusCode.TEMPORARY_FAILURE,
        meta=f"Internal error: {type(e).__name__}"
    )
```

## Complete Flow Example

```python
# 1. Request: gemini://example.com/user/alice

# 2. Route matched: /user/{username}
#    params = {"username": "alice"}

# 3. No input_prompt, skip input flow

# 4. Middleware before:
#    - LoggingMiddleware: logs "Request: /user/alice"
#    - TimingMiddleware: sets start_time

# 5. Handler called:
@app.gemini("/user/{username}")
def profile(request, username):
    return f"# {username}'s Profile"
#    returns: "# alice's Profile"

# 6. Response converted:
#    GeminiResponse(status=20, meta="text/gemini", body="# alice's Profile")

# 7. Middleware after:
#    - TimingMiddleware: calculates elapsed_time
#    - LoggingMiddleware: logs "Response: 20"

# 8. No exceptions, response sent:
#    20 text/gemini\r\n
#    # alice's Profile
```

## Error Flow Example

```python
# 1. Request: gemini://example.com/user/unknown

# 2-4. Same as above

# 5. Handler raises exception:
@app.gemini("/user/{username}")
def profile(request, username):
    user = db.get(username)
    if not user:
        raise NotFound(f"User {username} not found")
    return f"# {user.name}'s Profile"

# 6. Exception caught:
#    NotFound → GeminiResponse(status=51, meta="User unknown not found")

# 7. Middleware after still runs

# 8. Error response sent:
#    51 User unknown not found\r\n
```

## Async Execution

The entire request handling is async:

- Async handlers run directly
- Sync handlers wrapped in `asyncio.to_thread()`
- Middleware is always async
- I/O operations don't block other requests
