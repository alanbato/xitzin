# Virtual Hosting

Virtual hosting allows a single Xitzin server to host multiple applications under different hostnames. Each hostname can have its own routes, middleware, templates, and configuration.

## Basic Setup

Create separate `Xitzin` apps for each domain and configure virtual hosting on your main app:

```python
from xitzin import Xitzin, Request

# Create apps for different domains
blog_app = Xitzin(title="Blog")
api_app = Xitzin(title="API")
main_app = Xitzin(title="Main Site")

# Define routes for each app
@blog_app.gemini("/")
def blog_home(request: Request):
    return "# Welcome to the Blog"

@blog_app.gemini("/post/{post_id}")
def blog_post(request: Request, post_id: int):
    return f"# Post {post_id}"

@api_app.gemini("/")
def api_home(request: Request):
    return "# API v1.0"

@main_app.gemini("/")
def main_home(request: Request):
    return "# Welcome to Example.com"

# Configure virtual hosting
main_app.vhost({
    "blog.example.com": blog_app,
    "api.example.com": api_app,
}, default_app=main_app)

if __name__ == "__main__":
    main_app.run()
```

Requests to `gemini://blog.example.com/` go to `blog_app`, requests to `gemini://api.example.com/` go to `api_app`, and all other hostnames fall back to `main_app`.

## Wildcard Patterns

Match multiple subdomains with wildcard patterns:

```python
user_app = Xitzin(title="User Pages")

@user_app.gemini("/")
def user_home(request: Request):
    # Extract username from hostname
    username = request.hostname.split(".")[0]
    return f"# {username}'s Page"

main_app.vhost({
    "*.users.example.com": user_app,
}, default_app=main_app)
```

Now `alice.users.example.com` and `bob.users.example.com` both route to `user_app`.

!!! note "Wildcard Matching"
    Wildcards only match a single subdomain level. The pattern `*.example.com` matches `blog.example.com` but **not** `sub.blog.example.com`.

## Fallback Behavior

### Default App

When a request comes for an unknown hostname, route to a default app:

```python
main_app.vhost({
    "blog.example.com": blog_app,
}, default_app=main_app)
```

### Status Code

Return a specific status code for unknown hosts (default is 53 - Proxy Request Refused):

```python
main_app.vhost({
    "example.com": main_app,
    "www.example.com": main_app,
}, fallback_status=53)  # Proxy Request Refused
```

Other useful status codes:

- `51` - Not Found
- `53` - Proxy Request Refused (default)
- `59` - Bad Request

### Custom Handler

Use a custom handler for unknown hosts:

```python
def unknown_host_handler(request: Request):
    return f"""# Unknown Host

The hostname '{request.hostname}' is not configured.

=> gemini://example.com/ Visit the main site
"""

main_app.vhost({
    "example.com": main_app,
}, fallback_handler=unknown_host_handler)
```

The fallback handler can be sync or async.

## Priority Order

Hostname matching follows this priority:

1. **Exact matches** - `blog.example.com` matches before any wildcard
2. **Wildcards** - Checked in definition order
3. **Fallback** - Custom handler → default app → status code

```python
main_app.vhost({
    "blog.example.com": blog_app,    # Exact match (highest priority)
    "*.example.com": wildcard_app,   # Wildcard (lower priority)
}, default_app=main_app)             # Fallback (lowest priority)
```

## Sub-App Features

Each virtual host app is a full `Xitzin` instance with all features:

### Templates

```python
blog_app = Xitzin(title="Blog", templates_dir="blog/templates")

@blog_app.gemini("/")
def blog_home(request: Request):
    return blog_app.template("home.gmi", posts=get_posts())
```

### Middleware

```python
@blog_app.middleware
async def blog_logging(request, call_next):
    print(f"[Blog] {request.path}")
    return await call_next(request)
```

### Input Routes

```python
@blog_app.input("/search", prompt="Search posts:")
def search(request: Request, query: str):
    return f"# Results for: {query}"
```

### Titan Uploads

```python
@blog_app.titan("/upload/{filename}", auth_tokens=["secret"])
def upload(request, content: bytes, mime_type: str,
           token: str | None, filename: str):
    return f"# Uploaded {filename}"
```

## Using VirtualHostMiddleware Directly

For more control, use `VirtualHostMiddleware` directly:

```python
from xitzin import Xitzin, Request
from xitzin.middleware import VirtualHostMiddleware

main_app = Xitzin(title="Gateway")
blog_app = Xitzin(title="Blog")

# Create middleware instance
vhost_mw = VirtualHostMiddleware({
    "blog.example.com": blog_app,
    "*.api.example.com": api_app,
}, default_app=main_app)

# Register manually
@main_app.middleware
async def virtual_hosting(request, call_next):
    return await vhost_mw(request, call_next)

main_app.run()
```

This is equivalent to calling `main_app.vhost()` but gives you direct access to the middleware instance.

## Combining with Other Middleware

Virtual hosting middleware can be combined with other middleware:

```python
from xitzin.middleware import LoggingMiddleware, RateLimitMiddleware

# Create middleware
logging_mw = LoggingMiddleware()
rate_limit_mw = RateLimitMiddleware(max_requests=100)

# Register in order (first registered runs first)
@main_app.middleware
async def logging(request, call_next):
    return await logging_mw(request, call_next)

@main_app.middleware
async def rate_limit(request, call_next):
    return await rate_limit_mw(request, call_next)

# Virtual hosting should typically be registered last
# so it runs before other middleware
main_app.vhost({
    "blog.example.com": blog_app,
}, default_app=main_app)
```

## Complete Example

```python
from xitzin import Xitzin, Request
from xitzin.middleware import LoggingMiddleware

# Create apps
main_app = Xitzin(title="Example.com")
blog_app = Xitzin(title="Blog", templates_dir="blog/templates")
api_app = Xitzin(title="API")

# Main app routes
@main_app.gemini("/")
def main_home(request: Request):
    return """# Welcome to Example.com

=> gemini://blog.example.com/ Visit our blog
=> gemini://api.example.com/ API documentation
"""

# Blog routes
@blog_app.gemini("/")
def blog_home(request: Request):
    return "# Blog Home"

@blog_app.gemini("/post/{slug}")
def blog_post(request: Request, slug: str):
    return f"# {slug.replace('-', ' ').title()}"

@blog_app.input("/search", prompt="Search blog:")
def blog_search(request: Request, query: str):
    return f"# Search: {query}"

# API routes
@api_app.gemini("/")
def api_docs(request: Request):
    return "# API Documentation"

@api_app.gemini("/v1/status")
def api_status(request: Request):
    return "# Status: OK"

# Custom fallback for unknown hosts
def handle_unknown(request: Request):
    return f"# Unknown Host: {request.hostname}"

# Configure virtual hosting
main_app.vhost({
    "blog.example.com": blog_app,
    "www.blog.example.com": blog_app,
    "api.example.com": api_app,
    "*.staging.example.com": api_app,  # Staging subdomains
}, default_app=main_app, fallback_handler=handle_unknown)

if __name__ == "__main__":
    main_app.run(
        host="0.0.0.0",
        port=1965,
        certfile="cert.pem",
        keyfile="key.pem",
    )
```
