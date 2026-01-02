# Routing

Route definition, path parameter extraction, and URL reversing.

## Route

Represents a registered route with path parameter support.

Routes can be named for URL reversing:

```python
# Auto-named from function name
@app.gemini("/user/{id}")
def user_profile(request, id):  # name="user_profile"
    pass

# Explicit name
@app.gemini("/u/{id}", name="user_detail")
def handler(request, id):
    pass
```

::: xitzin.routing.Route

## Router

Collection of routes with matching logic and URL reversing.

::: xitzin.routing.Router
