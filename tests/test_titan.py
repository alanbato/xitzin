"""Tests for Titan upload protocol support."""

from xitzin import TitanRequest, Xitzin
from xitzin.testing import TestClient


class TestTitanBasicUpload:
    """Tests for basic Titan upload functionality."""

    def test_simple_upload(self):
        """Basic upload returns content to handler."""
        app = Xitzin()

        @app.titan("/upload")
        def upload(
            request: TitanRequest, content: bytes, mime_type: str, token: str | None
        ):
            return f"# Received {len(content)} bytes"

        client = TestClient(app)
        response = client.upload("/upload", b"Hello World")

        assert response.is_success
        assert "11 bytes" in response.body

    def test_upload_string_content(self):
        """String content is automatically encoded to UTF-8."""
        app = Xitzin()

        @app.titan("/upload")
        def upload(
            request: TitanRequest, content: bytes, mime_type: str, token: str | None
        ):
            return f"# Got: {content.decode()}"

        client = TestClient(app)
        response = client.upload("/upload", "Hello World")

        assert response.is_success
        assert "Hello World" in response.body

    def test_upload_mime_type(self):
        """MIME type is passed to handler."""
        app = Xitzin()

        @app.titan("/upload")
        def upload(
            request: TitanRequest, content: bytes, mime_type: str, token: str | None
        ):
            return f"# Type: {mime_type}"

        client = TestClient(app)
        response = client.upload("/upload", b"data", mime_type="application/json")

        assert response.is_success
        assert "application/json" in response.body

    def test_upload_default_mime_type(self):
        """Default MIME type is text/gemini."""
        app = Xitzin()

        @app.titan("/upload")
        def upload(
            request: TitanRequest, content: bytes, mime_type: str, token: str | None
        ):
            return f"# Type: {mime_type}"

        client = TestClient(app)
        response = client.upload("/upload", b"# Gemini content")

        assert response.is_success
        assert "text/gemini" in response.body

    def test_request_properties(self):
        """TitanRequest exposes correct properties."""
        app = Xitzin()
        captured = {}

        @app.titan("/upload")
        def upload(
            request: TitanRequest, content: bytes, mime_type: str, token: str | None
        ):
            captured["path"] = request.path
            captured["size"] = request.size
            captured["content"] = request.content
            captured["mime_type"] = request.mime_type
            captured["hostname"] = request.hostname
            return "# OK"

        client = TestClient(app)
        client.upload("/upload", b"test data", mime_type="text/plain")

        assert captured["path"] == "/upload"
        assert captured["size"] == 9
        assert captured["content"] == b"test data"
        assert captured["mime_type"] == "text/plain"
        assert captured["hostname"] == "testserver"

    def test_request_app_access(self):
        """TitanRequest provides access to app."""
        app = Xitzin()
        app.state.config = "test_value"

        @app.titan("/upload")
        def upload(
            request: TitanRequest, content: bytes, mime_type: str, token: str | None
        ):
            return f"# Config: {request.app.state.config}"

        client = TestClient(app)
        response = client.upload("/upload", b"test")

        assert response.is_success
        assert "test_value" in response.body

    def test_request_state(self):
        """TitanRequest has its own state."""
        app = Xitzin()

        @app.titan("/upload")
        def upload(
            request: TitanRequest, content: bytes, mime_type: str, token: str | None
        ):
            request.state.processed = True
            return f"# State: {request.state.processed}"

        client = TestClient(app)
        response = client.upload("/upload", b"test")

        assert response.is_success
        assert "True" in response.body


class TestTitanAuthentication:
    """Tests for Titan token authentication."""

    def test_valid_token(self):
        """Valid token allows upload."""
        app = Xitzin()

        @app.titan("/secure", auth_tokens=["secret123"])
        def upload(
            request: TitanRequest, content: bytes, mime_type: str, token: str | None
        ):
            return f"# Token: {token}"

        client = TestClient(app)
        response = client.upload("/secure", b"data", token="secret123")

        assert response.is_success
        assert "secret123" in response.body

    def test_invalid_token_rejected(self):
        """Invalid token returns certificate required (60)."""
        app = Xitzin()

        @app.titan("/secure", auth_tokens=["secret123"])
        def upload(
            request: TitanRequest, content: bytes, mime_type: str, token: str | None
        ):
            return "# Success"

        client = TestClient(app)
        response = client.upload("/secure", b"data", token="wrong_token")

        assert response.status == 60
        assert response.is_certificate_required

    def test_missing_token_rejected(self):
        """Missing token returns certificate required (60)."""
        app = Xitzin()

        @app.titan("/secure", auth_tokens=["secret123"])
        def upload(
            request: TitanRequest, content: bytes, mime_type: str, token: str | None
        ):
            return "# Success"

        client = TestClient(app)
        response = client.upload("/secure", b"data")

        assert response.status == 60
        assert response.is_certificate_required

    def test_multiple_valid_tokens(self):
        """Multiple valid tokens supported."""
        app = Xitzin()

        @app.titan("/secure", auth_tokens=["token1", "token2", "token3"])
        def upload(
            request: TitanRequest, content: bytes, mime_type: str, token: str | None
        ):
            return f"# Used: {token}"

        client = TestClient(app)

        # All tokens should work
        response1 = client.upload("/secure", b"data", token="token1")
        assert response1.is_success
        assert "token1" in response1.body

        response2 = client.upload("/secure", b"data", token="token2")
        assert response2.is_success
        assert "token2" in response2.body

        response3 = client.upload("/secure", b"data", token="token3")
        assert response3.is_success
        assert "token3" in response3.body

    def test_no_auth_required_without_tokens(self):
        """Route without auth_tokens accepts any request."""
        app = Xitzin()

        @app.titan("/public")
        def upload(
            request: TitanRequest, content: bytes, mime_type: str, token: str | None
        ):
            return f"# Token was: {token}"

        client = TestClient(app)

        # No token
        response1 = client.upload("/public", b"data")
        assert response1.is_success

        # With token (still accepted, just not validated)
        response2 = client.upload("/public", b"data", token="any_token")
        assert response2.is_success
        assert "any_token" in response2.body


class TestTitanDelete:
    """Tests for Titan delete operations (zero-byte uploads)."""

    def test_is_delete_for_empty_content(self):
        """is_delete() returns True for zero-byte uploads."""
        app = Xitzin()
        captured = {}

        @app.titan("/files")
        def handle(
            request: TitanRequest, content: bytes, mime_type: str, token: str | None
        ):
            captured["is_delete"] = request.is_delete()
            captured["size"] = len(content)
            return "# OK"

        client = TestClient(app)
        client.delete("/files")

        assert captured["is_delete"] is True
        assert captured["size"] == 0

    def test_is_delete_false_for_content(self):
        """is_delete() returns False for non-empty uploads."""
        app = Xitzin()
        captured = {}

        @app.titan("/files")
        def handle(
            request: TitanRequest, content: bytes, mime_type: str, token: str | None
        ):
            captured["is_delete"] = request.is_delete()
            return "# OK"

        client = TestClient(app)
        client.upload("/files", b"some data")

        assert captured["is_delete"] is False

    def test_delete_with_token(self):
        """Delete method supports authentication token."""
        app = Xitzin()

        @app.titan("/secure", auth_tokens=["delete_key"])
        def handle(
            request: TitanRequest, content: bytes, mime_type: str, token: str | None
        ):
            if request.is_delete():
                return "# Deleted"
            return "# Uploaded"

        client = TestClient(app)
        response = client.delete("/secure", token="delete_key")

        assert response.is_success
        assert "Deleted" in response.body

    def test_delete_without_token_rejected(self):
        """Delete without token on protected route is rejected."""
        app = Xitzin()

        @app.titan("/secure", auth_tokens=["delete_key"])
        def handle(
            request: TitanRequest, content: bytes, mime_type: str, token: str | None
        ):
            return "# Should not reach"

        client = TestClient(app)
        response = client.delete("/secure")

        assert response.status == 60

    def test_handler_distinguishes_upload_and_delete(self):
        """Handler can handle both upload and delete in same route."""
        app = Xitzin()
        operations = []

        @app.titan("/resource")
        def handle(
            request: TitanRequest, content: bytes, mime_type: str, token: str | None
        ):
            if request.is_delete():
                operations.append("delete")
                return "# Deleted"
            operations.append("upload")
            return "# Uploaded"

        client = TestClient(app)

        client.upload("/resource", b"data")
        assert operations == ["upload"]

        client.delete("/resource")
        assert operations == ["upload", "delete"]


class TestTitanPathParameters:
    """Tests for path parameters in Titan routes."""

    def test_single_path_parameter(self):
        """Single path parameter extracted correctly."""
        app = Xitzin()

        @app.titan("/files/{filename}")
        def upload(
            request: TitanRequest,
            content: bytes,
            mime_type: str,
            token: str | None,
            filename: str,
        ):
            return f"# Uploaded: {filename}"

        client = TestClient(app)
        response = client.upload("/files/test.txt", b"content")

        assert response.is_success
        assert "test.txt" in response.body

    def test_multiple_path_parameters(self):
        """Multiple path parameters extracted correctly."""
        app = Xitzin()

        @app.titan("/users/{user}/files/{filename}")
        def upload(
            request: TitanRequest,
            content: bytes,
            mime_type: str,
            token: str | None,
            user: str,
            filename: str,
        ):
            return f"# {user}/{filename}"

        client = TestClient(app)
        response = client.upload("/users/alice/files/doc.gmi", b"content")

        assert response.is_success
        assert "alice/doc.gmi" in response.body

    def test_int_type_conversion(self):
        """Integer path parameters are converted."""
        app = Xitzin()

        @app.titan("/posts/{post_id}/attachments")
        def upload(
            request: TitanRequest,
            content: bytes,
            mime_type: str,
            token: str | None,
            post_id: int,
        ):
            return f"# Post ID type: {type(post_id).__name__}, value: {post_id}"

        client = TestClient(app)
        response = client.upload("/posts/42/attachments", b"data")

        assert response.is_success
        assert "int" in response.body
        assert "42" in response.body

    def test_path_type_parameter(self):
        """Path-type parameter captures segments with slashes."""
        app = Xitzin()

        @app.titan("/repo/{path:path}")
        def upload(
            request: TitanRequest,
            content: bytes,
            mime_type: str,
            token: str | None,
            path: str,
        ):
            return f"# Path: {path}"

        client = TestClient(app)
        response = client.upload("/repo/src/lib/main.py", b"code")

        assert response.is_success
        assert "src/lib/main.py" in response.body


class TestTitanRouting:
    """Tests for Titan route matching."""

    def test_no_matching_route(self):
        """Non-matching path returns not found (51)."""
        app = Xitzin()

        @app.titan("/upload")
        def upload(
            request: TitanRequest, content: bytes, mime_type: str, token: str | None
        ):
            return "# OK"

        client = TestClient(app)
        response = client.upload("/wrong/path", b"data")

        assert response.status == 51
        assert response.is_error

    def test_multiple_titan_routes(self):
        """Multiple Titan routes are matched correctly."""
        app = Xitzin()

        @app.titan("/images")
        def images(
            request: TitanRequest, content: bytes, mime_type: str, token: str | None
        ):
            return "# Images"

        @app.titan("/documents")
        def documents(
            request: TitanRequest, content: bytes, mime_type: str, token: str | None
        ):
            return "# Documents"

        client = TestClient(app)

        response1 = client.upload("/images", b"image data")
        assert "Images" in response1.body

        response2 = client.upload("/documents", b"doc data")
        assert "Documents" in response2.body

    def test_gemini_and_titan_routes_separate(self):
        """Gemini and Titan routes are handled separately."""
        app = Xitzin()

        @app.gemini("/resource")
        def get_resource(request):
            return "# GET resource"

        @app.titan("/resource")
        def upload_resource(
            request: TitanRequest, content: bytes, mime_type: str, token: str | None
        ):
            return "# POST resource"

        client = TestClient(app)

        # Gemini request
        get_response = client.get("/resource")
        assert "GET" in get_response.body

        # Titan request
        upload_response = client.upload("/resource", b"data")
        assert "POST" in upload_response.body


class TestTitanMiddleware:
    """Tests for middleware execution with Titan requests."""

    def test_middleware_runs_for_titan(self):
        """Middleware is executed for Titan requests."""
        app = Xitzin()
        middleware_called = []

        @app.middleware
        async def tracking_middleware(request, call_next):
            middleware_called.append("before")
            response = await call_next(request)
            middleware_called.append("after")
            return response

        @app.titan("/upload")
        def upload(
            request: TitanRequest, content: bytes, mime_type: str, token: str | None
        ):
            middleware_called.append("handler")
            return "# OK"

        client = TestClient(app)
        client.upload("/upload", b"data")

        assert middleware_called == ["before", "handler", "after"]

    def test_multiple_middleware_order(self):
        """Multiple middleware run in correct order."""
        app = Xitzin()
        order = []

        @app.middleware
        async def first_middleware(request, call_next):
            order.append("first-before")
            response = await call_next(request)
            order.append("first-after")
            return response

        @app.middleware
        async def second_middleware(request, call_next):
            order.append("second-before")
            response = await call_next(request)
            order.append("second-after")
            return response

        @app.titan("/upload")
        def upload(
            request: TitanRequest, content: bytes, mime_type: str, token: str | None
        ):
            order.append("handler")
            return "# OK"

        client = TestClient(app)
        client.upload("/upload", b"data")

        assert order == [
            "first-before",
            "second-before",
            "handler",
            "second-after",
            "first-after",
        ]

    def test_middleware_can_modify_request_state(self):
        """Middleware can set state on TitanRequest."""
        app = Xitzin()

        @app.middleware
        async def state_middleware(request, call_next):
            request.state.middleware_value = "set_by_middleware"
            return await call_next(request)

        @app.titan("/upload")
        def upload(
            request: TitanRequest, content: bytes, mime_type: str, token: str | None
        ):
            return f"# State: {request.state.middleware_value}"

        client = TestClient(app)
        response = client.upload("/upload", b"data")

        assert response.is_success
        assert "set_by_middleware" in response.body


class TestTitanCertificate:
    """Tests for client certificate handling in Titan requests."""

    def test_cert_fingerprint_available(self):
        """Client certificate fingerprint is available in handler."""
        app = Xitzin()

        @app.titan("/upload")
        def upload(
            request: TitanRequest, content: bytes, mime_type: str, token: str | None
        ):
            fp = request.client_cert_fingerprint or "none"
            return f"# Cert: {fp}"

        client = TestClient(app)
        response = client.upload("/upload", b"data", cert_fingerprint="abc123def456")

        assert response.is_success
        assert "abc123def456" in response.body

    def test_with_certificate_applies_to_upload(self):
        """with_certificate() applies to upload requests."""
        app = Xitzin()

        @app.titan("/upload")
        def upload(
            request: TitanRequest, content: bytes, mime_type: str, token: str | None
        ):
            return f"# Cert: {request.client_cert_fingerprint}"

        client = TestClient(app)
        auth_client = client.with_certificate("default_cert_fp")

        response = auth_client.upload("/upload", b"data")
        assert "default_cert_fp" in response.body

    def test_cert_fingerprint_override(self):
        """cert_fingerprint parameter overrides default."""
        app = Xitzin()

        @app.titan("/upload")
        def upload(
            request: TitanRequest, content: bytes, mime_type: str, token: str | None
        ):
            return f"# Cert: {request.client_cert_fingerprint}"

        client = TestClient(app)
        auth_client = client.with_certificate("default_fp")

        response = auth_client.upload(
            "/upload", b"data", cert_fingerprint="override_fp"
        )
        assert "override_fp" in response.body


class TestTitanAsyncHandler:
    """Tests for async Titan handlers."""

    def test_async_handler(self):
        """Async Titan handlers work correctly."""
        app = Xitzin()

        @app.titan("/upload")
        async def upload(
            request: TitanRequest, content: bytes, mime_type: str, token: str | None
        ):
            return f"# Async: {len(content)} bytes"

        client = TestClient(app)
        response = client.upload("/upload", b"async data")

        assert response.is_success
        assert "10 bytes" in response.body

    def test_async_handler_with_path_params(self):
        """Async handler with path parameters works."""
        app = Xitzin()

        @app.titan("/files/{name}")
        async def upload(
            request: TitanRequest,
            content: bytes,
            mime_type: str,
            token: str | None,
            name: str,
        ):
            return f"# Async upload: {name}"

        client = TestClient(app)
        response = client.upload("/files/test.gmi", b"content")

        assert response.is_success
        assert "test.gmi" in response.body
