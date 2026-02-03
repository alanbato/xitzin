# Static Files

Xitzin provides native static file serving to host Gemtext pages, images, and other files directly from a directory. This eliminates the need for external file servers or adapter patterns.

## Mount a Static Directory

Use `app.static()` to serve files from a directory:

```python
from xitzin import Xitzin

app = Xitzin()

# Serve files from ./public at /files
app.static("/files", "./public")
```

Now requests to `/files/page.gmi` will serve `./public/page.gmi`.

## Use StaticFiles Directly

For more control, use the `StaticFiles` handler with `app.mount()`:

```python
from xitzin import Xitzin
from xitzin.staticfiles import StaticFiles

app = Xitzin()

handler = StaticFiles("./public", directory_listing=True)
app.mount("/files", handler)
```

## Enable Directory Listing

By default, directories without an index file return a 404. Enable directory listing to show a navigable file list:

```python
app.static("/files", "./public", directory_listing=True)
```

This generates a Gemini page listing all files and subdirectories, with file sizes and navigation links.

Example output:

```gemini
# Index of /docs/

=> ../ ..

=> guides/ guides/
=> tutorials/ tutorials/
=> readme.gmi readme.gmi (2.4 KB)
=> changelog.gmi changelog.gmi (1.1 KB)
```

## Directory Index Files

When a directory is requested, Xitzin looks for index files in order:

1. `index.gmi`
2. `index.gemini`

Customize the index files:

```python
app.static(
    "/files",
    "./public",
    index_files=["home.gmi", "index.gmi", "default.gmi"]
)
```

## Custom MIME Types

Xitzin detects MIME types automatically. Override or add custom types:

```python
app.static(
    "/files",
    "./public",
    mime_types={
        ".gmi": "text/gemini",
        ".gem": "text/gemini",
        ".custom": "application/x-custom",
    }
)
```

Default MIME type mappings include:

| Extension | MIME Type |
|-----------|-----------|
| `.gmi`, `.gemini` | `text/gemini` |
| `.txt` | `text/plain` |
| `.md` | `text/markdown` |
| `.html` | `text/html` |
| `.css` | `text/css` |
| `.json` | `application/json` |
| `.png` | `image/png` |
| `.jpg`, `.jpeg` | `image/jpeg` |
| `.gif` | `image/gif` |
| `.pdf` | `application/pdf` |

Unknown extensions default to `text/gemini`.

## Serve Binary Files

StaticFiles automatically handles binary content like images and PDFs:

```python
app.static("/assets", "./static")
```

Requests for `/assets/logo.png` will serve the image with the correct `image/png` MIME type.

## Custom 404 Handler

Add a custom handler for missing files using the `@handler.not_found` decorator:

```python
static = app.static("/files", "./public")

@static.not_found
def custom_404(request, path_info):
    return f"# File Not Found\n\nThe file `{path_info}` doesn't exist."
```

The handler receives the request and the path that wasn't found. It can return any valid Xitzin response.

Async handlers are also supported:

```python
@static.not_found
async def custom_404(request, path_info):
    # Maybe log to database
    await log_missing_file(path_info)
    return f"# Not Found\n\n`{path_info}` is missing."
```

## File Size Limits

By default, files larger than 100 MiB are rejected. Configure the limit:

```python
# 50 MiB limit
app.static("/files", "./public", max_file_size=50 * 1024 * 1024)

# 10 MiB limit
app.static("/files", "./public", max_file_size=10 * 1024 * 1024)
```

Files exceeding the limit return a `59 Bad Request` error.

## Symlink Security

By default, symbolic links are blocked to prevent directory escapes:

```python
# Default: symlinks blocked
app.static("/files", "./public", follow_symlinks=False)

# Allow symlinks (use with caution)
app.static("/files", "./public", follow_symlinks=True)
```

!!! warning "Symlink Security"
    Enabling `follow_symlinks` allows serving files outside your document root if symlinks point there. Only enable this when you control all symlinks in the directory.

## Configuration with StaticFilesConfig

For reusable configuration, use `StaticFilesConfig`:

```python
from xitzin.staticfiles import StaticFiles, StaticFilesConfig

config = StaticFilesConfig(
    index_files=["index.gmi", "home.gmi"],
    directory_listing=True,
    max_file_size=50 * 1024 * 1024,
    mime_types={".gem": "text/gemini"},
    follow_symlinks=False,
)

# Reuse config across multiple handlers
app.mount("/docs", StaticFiles("./docs", config=config))
app.mount("/assets", StaticFiles("./assets", config=config))
```

## Combine with Regular Routes

Static files work alongside regular routes:

```python
from xitzin import Xitzin, Request

app = Xitzin()

# Regular route
@app.gemini("/")
def home(request: Request):
    return "# Home\n\n=> /docs/ Documentation\n=> /about About"

# Another regular route
@app.gemini("/about")
def about(request: Request):
    return "# About\n\nThis is my capsule."

# Static files
app.static("/docs", "./documentation", directory_listing=True)
```

Mounted handlers (including static files) are checked before regular routes.

## Apply Middleware

Middleware applies to static file requests:

```python
@app.middleware
async def log_requests(request, call_next):
    print(f"Request: {request.path}")
    response = await call_next(request)
    print(f"Response: {response.status}")
    return response

# Static files go through middleware
app.static("/files", "./public")
```

## Test Static Files

Use `TestClient` to test static file serving:

```python
from xitzin import Xitzin
from xitzin.testing import TestClient

def test_static_files(tmp_path):
    # Create test files
    (tmp_path / "index.gmi").write_text("# Welcome")
    (tmp_path / "about.gmi").write_text("# About")

    # Set up app
    app = Xitzin()
    app.static("/", tmp_path)

    # Test
    client = TestClient(app)

    response = client.get("/")
    assert response.is_success
    assert "# Welcome" in response.body

    response = client.get("/about.gmi")
    assert response.is_success
    assert "# About" in response.body

    response = client.get("/nonexistent.gmi")
    assert response.status == 51  # Not found
```

## Configuration Reference

`app.static()` and `StaticFilesConfig` accept these options:

| Option | Default | Description |
|--------|---------|-------------|
| `index_files` | `["index.gmi", "index.gemini"]` | Files to serve for directory requests |
| `directory_listing` | `False` | Show directory contents when no index found |
| `max_file_size` | `100 * 1024 * 1024` (100 MiB) | Maximum file size to serve |
| `mime_types` | `{}` | Custom MIME type mappings by extension |
| `follow_symlinks` | `False` | Whether to follow symbolic links |

## Security Considerations

Xitzin implements several security measures:

1. **Path traversal protection**: Requests like `/../secret.txt` are blocked
2. **Symlink control**: Symlinks blocked by default to prevent escapes
3. **File size limits**: Prevents memory exhaustion from large files
4. **Hidden files**: Files starting with `.` are excluded from directory listings
5. **Generic errors**: Error messages don't expose internal paths

!!! tip "Best Practices"
    - Keep `follow_symlinks=False` unless you have a specific need
    - Set appropriate `max_file_size` for your use case
    - Use `directory_listing=False` for directories with sensitive file names
    - Place static files in a dedicated directory, not mixed with application code
