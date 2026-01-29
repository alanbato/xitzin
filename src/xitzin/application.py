"""Main Xitzin application class.

This module provides the Xitzin class, the main entry point for creating
Gemini applications.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from nauyaca.protocol.request import GeminiRequest
from nauyaca.protocol.request import TitanRequest as NauyacaTitanRequest
from nauyaca.protocol.response import GeminiResponse
from nauyaca.protocol.status import StatusCode

from .exceptions import (
    CertificateRequired,
    GeminiException,
    NotFound,
    TaskConfigurationError,
)
from .requests import Request, TitanRequest
from .responses import Input, Redirect, convert_response
from .routing import MountedRoute, Route, Router, TitanRoute

if TYPE_CHECKING:
    from .tasks import BackgroundTask
    from .templating import TemplateEngine


class AppState:
    """Application-level state storage.

    Store shared resources like database connections here.

    Example:
        app.state.db = create_db_connection()
    """

    def __setattr__(self, name: str, value: Any) -> None:
        self.__dict__[name] = value

    def __getattr__(self, name: str) -> Any:
        try:
            return self.__dict__[name]
        except KeyError:
            raise AttributeError(f"'AppState' has no attribute '{name}'") from None


class Xitzin:
    """Gemini Application Framework.

    Xitzin provides an interface for building Gemini applications.

    Example:
        app = Xitzin(title="My Capsule")

        @app.gemini("/")
        def homepage(request: Request):
            return "# Welcome to my capsule!"

        @app.gemini("/user/{username}")
        def profile(request: Request, username: str):
            return f"# {username}'s Profile"

        if __name__ == "__main__":
            app.run()
    """

    def __init__(
        self,
        *,
        title: str = "Xitzin App",
        version: str = "0.1.0",
        templates_dir: Path | str | None = None,
    ) -> None:
        """Create a new Xitzin application.

        Args:
            title: Application title (for documentation).
            version: Application version.
            templates_dir: Directory containing Gemtext templates.
        """
        self.title = title
        self.version = version
        self._router = Router()
        self._state = AppState()
        self._templates: TemplateEngine | None = None
        self._startup_handlers: list[Callable[[], Any]] = []
        self._shutdown_handlers: list[Callable[[], Any]] = []
        self._middleware: list[Callable[..., Any]] = []
        self._tasks: list[BackgroundTask] = []
        self._task_handles: list[asyncio.Task[Any]] = []

        if templates_dir:
            self._init_templates(Path(templates_dir))

    def _init_templates(self, templates_dir: Path) -> None:
        """Initialize the template engine."""
        from .templating import TemplateEngine

        self._templates = TemplateEngine(templates_dir, app=self)

    @property
    def state(self) -> AppState:
        """Application-level state storage."""
        return self._state

    def template(self, name: str, **context: Any) -> Any:
        """Render a template.

        Args:
            name: Template filename (e.g., "page.gmi").
            **context: Variables to pass to the template.

        Returns:
            TemplateResponse that can be returned from handlers.

        Raises:
            RuntimeError: If no templates directory was configured.
        """
        if self._templates is None:
            msg = "No templates directory configured"
            raise RuntimeError(msg)
        return self._templates.render(name, **context)

    def reverse(self, name: str, **params: Any) -> str:
        """Build URL for a named route.

        Args:
            name: Route name.
            **params: Path parameters.

        Returns:
            URL path string.

        Raises:
            ValueError: If route name not found or parameters missing.

        Example:
            url = app.reverse("user_profile", username="alice")
            # Returns "/user/alice"
        """
        return self._router.reverse(name, **params)

    def redirect(
        self, name: str, *, permanent: bool = False, **params: Any
    ) -> Redirect:
        """Create a redirect to a named route.

        Args:
            name: Route name.
            permanent: If True, use status 31 (permanent redirect).
            **params: Path parameters.

        Returns:
            Redirect response object.

        Example:
            @app.gemini("/old-profile/{username}")
            def old_profile(request: Request, username: str):
                return app.redirect("user_profile", username=username, permanent=True)
        """
        url = self.reverse(name, **params)
        return Redirect(url, permanent=permanent)

    def gemini(
        self, path: str, *, name: str | None = None
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Register a route handler.

        Args:
            path: URL path pattern (e.g., "/user/{id}").
            name: Optional route name for URL reversing. Defaults to function name.

        Returns:
            Decorator function.

        Example:
            @app.gemini("/")
            def home(request: Request):
                return "# Home"

            @app.gemini("/user/{username}", name="user_profile")
            def profile(request: Request, username: str):
                return f"# {username}"
        """

        def decorator(handler: Callable[..., Any]) -> Callable[..., Any]:
            route = Route(path, handler, name=name)
            self._router.add_route(route)
            return handler

        return decorator

    def input(
        self,
        path: str,
        *,
        prompt: str,
        sensitive: bool = False,
        name: str | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Register an input route (status 10/11 flow).

        When a request arrives without a query string, the client is prompted
        for input. When the request includes a query string, the handler is
        called with the decoded input as the `query` parameter.

        Args:
            path: URL path pattern.
            prompt: Prompt text shown to the user.
            sensitive: If True, use status 11 (sensitive input).
            name: Optional route name for URL reversing. Defaults to function name.

        Returns:
            Decorator function.

        Example:
            @app.input("/search", prompt="Enter search query:", name="search")
            def search(request: Request, query: str):
                return f"# Results for: {query}"
        """

        def decorator(handler: Callable[..., Any]) -> Callable[..., Any]:
            route = Route(
                path, handler, name=name, input_prompt=prompt, sensitive_input=sensitive
            )
            self._router.add_route(route)
            return handler

        return decorator

    def titan(
        self,
        path: str,
        *,
        name: str | None = None,
        auth_tokens: list[str] | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Register a Titan upload handler.

        Titan is the upload companion protocol to Gemini. This decorator
        registers a handler for Titan upload requests.

        Args:
            path: URL path pattern (e.g., "/upload/{filename}").
            name: Optional route name. Defaults to function name.
            auth_tokens: List of valid authentication tokens. If provided,
                requests without a valid token are rejected with status 60.

        Returns:
            Decorator function.

        Example:
            @app.titan("/upload/{filename}", auth_tokens=["secret123"])
            def upload(request: TitanRequest, content: bytes,
                       mime_type: str, token: str | None, filename: str):
                if request.is_delete():
                    Path(f"./uploads/{filename}").unlink()
                    return "# Deleted"
                Path(f"./uploads/{filename}").write_bytes(content)
                return "# Upload successful"
        """

        def decorator(handler: Callable[..., Any]) -> Callable[..., Any]:
            route = TitanRoute(path, handler, name=name, auth_tokens=auth_tokens)
            self._router.add_titan_route(route)
            return handler

        return decorator

    def mount(
        self,
        path: str,
        handler: Callable[..., Any],
        *,
        name: str | None = None,
    ) -> None:
        """Mount a handler at a path prefix.

        Mounted handlers receive requests for any path starting with the prefix.
        The handler receives (request, path_info) where path_info is the
        remaining path after the mount prefix.

        Args:
            path: Mount point prefix (e.g., "/cgi-bin", "/api").
            handler: Callable that takes (request, path_info) and returns a response.
            name: Optional name for the mount.

        Example:
            from xitzin.cgi import CGIHandler

            app.mount("/cgi-bin", CGIHandler(script_dir="./scripts"))

            # Requests to /cgi-bin/hello.py will call:
            # handler(request, path_info="/hello.py")
        """
        mounted = MountedRoute(path, handler, name=name)
        self._router.add_mounted_route(mounted)

    def cgi(
        self,
        path: str,
        script_dir: Path | str,
        *,
        name: str | None = None,
        timeout: float = 30.0,
        app_state_keys: list[str] | None = None,
    ) -> None:
        """Mount a CGI directory at a path prefix.

        This is a convenience method that creates a CGIHandler and mounts it.

        Args:
            path: Mount point prefix (e.g., "/cgi-bin").
            script_dir: Directory containing CGI scripts.
            name: Optional name for the mount.
            timeout: Maximum script execution time in seconds.
            app_state_keys: App state keys to pass as XITZIN_* env vars.

        Example:
            app.cgi("/cgi-bin", "/srv/gemini/cgi-bin", timeout=30)

            # Requests to /cgi-bin/hello.py execute:
            # /srv/gemini/cgi-bin/hello.py
        """
        from .cgi import CGIConfig, CGIHandler

        config = CGIConfig(
            timeout=timeout,
            app_state_keys=app_state_keys or [],
        )
        handler = CGIHandler(script_dir, config=config)
        self.mount(path, handler, name=name)

    def scgi(
        self,
        path: str,
        host: str | None = None,
        port: int | None = None,
        socket_path: Path | str | None = None,
        *,
        name: str | None = None,
        timeout: float = 30.0,
        app_state_keys: list[str] | None = None,
    ) -> None:
        """Mount an SCGI backend at a path prefix.

        This is a convenience method that creates an SCGIHandler or SCGIApp
        and mounts it. Exactly one of (host+port) or socket_path must be provided.

        Args:
            path: Mount point prefix (e.g., "/dynamic").
            host: SCGI server hostname (for TCP connection).
            port: SCGI server port (for TCP connection).
            socket_path: Path to Unix socket (for local connection).
            name: Optional name for the mount.
            timeout: Maximum response wait time in seconds.
            app_state_keys: App state keys to pass as XITZIN_* env vars.

        Raises:
            ValueError: If neither or both connection types are specified.

        Example:
            # TCP connection
            app.scgi("/dynamic", host="127.0.0.1", port=4000, timeout=30)

            # Unix socket connection
            app.scgi("/dynamic", socket_path="/tmp/scgi.sock", timeout=30)
        """
        from .scgi import SCGIApp, SCGIConfig, SCGIHandler

        # Validate parameters
        tcp_specified = host is not None or port is not None
        unix_specified = socket_path is not None

        if tcp_specified and unix_specified:
            msg = "Cannot specify both TCP (host/port) and Unix socket (socket_path)"
            raise ValueError(msg)
        if not tcp_specified and not unix_specified:
            msg = "Must specify either TCP (host and port) or Unix socket (socket_path)"
            raise ValueError(msg)
        if tcp_specified and (host is None or port is None):
            msg = "Both host and port must be specified for TCP connection"
            raise ValueError(msg)

        config = SCGIConfig(
            timeout=timeout,
            app_state_keys=app_state_keys or [],
        )

        if tcp_specified:
            handler = SCGIHandler(host, port, config=config)  # type: ignore[arg-type]
        else:
            handler = SCGIApp(socket_path, config=config)  # type: ignore[arg-type]

        self.mount(path, handler, name=name)

    def vhost(
        self,
        hosts: dict[str, "Xitzin"],
        *,
        default_app: "Xitzin | None" = None,
        fallback_status: int = 53,
        fallback_handler: Callable[[Request], Any] | None = None,
    ) -> None:
        """Configure virtual hosting for this application.

        This is a convenience method that creates and registers VirtualHostMiddleware.
        The middleware routes requests to different apps based on hostname.

        Args:
            hosts: Mapping of hostname patterns to Xitzin apps.
                Patterns can be exact ("example.com") or wildcards ("*.example.com").
                Exact matches are checked first, then wildcards in definition order.
            default_app: Default app when no pattern matches.
            fallback_status: Status code for unmatched hosts (default: 53).
                Common values: 53 (Proxy Refused), 51 (Not Found), 59 (Bad Request).
            fallback_handler: Custom handler for unmatched hosts.
                Takes precedence over default_app and fallback_status.

        Example:
            main_app = Xitzin(title="Main")
            blog_app = Xitzin(title="Blog")
            api_app = Xitzin(title="API")

            @blog_app.gemini("/")
            def blog_home(request: Request):
                return "# Blog Home"

            @api_app.gemini("/")
            def api_home(request: Request):
                return "# API Home"

            @main_app.gemini("/")
            def main_home(request: Request):
                return "# Main Home"

            # Configure as gateway
            main_app.vhost({
                "blog.example.com": blog_app,
                "*.api.example.com": api_app,
            }, default_app=main_app)

            main_app.run()
        """
        from .middleware import VirtualHostMiddleware

        vhost_mw = VirtualHostMiddleware(
            hosts,
            default_app=default_app,
            fallback_status=fallback_status,
            fallback_handler=fallback_handler,
        )

        @self.middleware
        async def virtual_host_dispatcher(
            request: Request, call_next: Callable[..., Any]
        ) -> GeminiResponse:
            return await vhost_mw(request, call_next)

    def on_startup(self, handler: Callable[[], Any]) -> Callable[[], Any]:
        """Register a startup event handler.

        Args:
            handler: Function to call on startup.

        Example:
            @app.on_startup
            async def startup():
                app.state.db = await create_db_pool()
        """
        self._startup_handlers.append(handler)
        return handler

    def on_shutdown(self, handler: Callable[[], Any]) -> Callable[[], Any]:
        """Register a shutdown event handler.

        Args:
            handler: Function to call on shutdown.

        Example:
            @app.on_shutdown
            async def shutdown():
                await app.state.db.close()
        """
        self._shutdown_handlers.append(handler)
        return handler

    def middleware(self, handler: Callable[..., Any]) -> Callable[..., Any]:
        """Register middleware as a decorator.

        Middleware receives (request, call_next) and must call call_next
        to continue processing.

        Args:
            handler: Middleware function.

        Example:
            @app.middleware
            async def log_requests(request: Request, call_next):
                print(f"Request: {request.path}")
                response = await call_next(request)
                print(f"Response: {response.status}")
                return response
        """
        self._middleware.append(handler)
        return handler

    def task(
        self,
        *,
        interval: str | int | float | None = None,
        cron: str | None = None,
    ) -> Callable[[Callable[[], Any]], Callable[[], Any]]:
        """Register a background task.

        Tasks run continuously while the server is running. They are started
        after startup handlers and stopped before shutdown handlers.

        Args:
            interval: Run every N seconds (int) or duration string ("1h", "30m", "1d").
            cron: Cron expression string ("0 * * * *" runs hourly).
                Requires croniter: pip install 'xitzin[tasks]'

        Exactly one of interval or cron must be provided.

        Returns:
            Decorator function.

        Raises:
            TaskConfigurationError: If neither or both parameters provided,
                or if cron is used but croniter is not installed.

        Example:
            @app.task(interval="1h")
            async def cleanup():
                await app.state.db.cleanup_old_records()

            @app.task(cron="0 2 * * *")  # 2 AM daily
            def backup():
                backup_database()
        """
        from .tasks import BackgroundTask, parse_interval

        # Validate parameters
        if interval is None and cron is None:
            raise TaskConfigurationError("Either 'interval' or 'cron' must be provided")
        if interval is not None and cron is not None:
            raise TaskConfigurationError(
                "Only one of 'interval' or 'cron' can be provided, not both"
            )

        # Check croniter availability
        if cron is not None:
            try:
                from croniter import croniter as _  # noqa: F401
            except ImportError:
                raise TaskConfigurationError(
                    "croniter is required for cron tasks. "
                    "Install with: pip install 'xitzin[tasks]'"
                ) from None

        def decorator(handler: Callable[[], Any]) -> Callable[[], Any]:
            # Parse interval if provided
            parsed_interval = parse_interval(interval) if interval else None

            task = BackgroundTask(
                handler=handler,
                interval=parsed_interval,
                cron=cron,
                name=getattr(handler, "__name__", "<anonymous>"),
            )
            self._tasks.append(task)
            return handler

        return decorator

    async def _run_startup(self) -> None:
        """Run all startup handlers."""
        for handler in self._startup_handlers:
            if asyncio.iscoroutinefunction(handler):
                await handler()
            else:
                handler()

    async def _run_shutdown(self) -> None:
        """Run all shutdown handlers in reverse order."""
        for handler in reversed(self._shutdown_handlers):
            if asyncio.iscoroutinefunction(handler):
                await handler()
            else:
                handler()

    async def _run_tasks(self) -> None:
        """Start all registered background tasks."""
        from .tasks import run_cron_task, run_interval_task

        for task in self._tasks:
            if task.interval is not None:
                handle = asyncio.create_task(run_interval_task(task))
            else:  # task.cron is not None
                handle = asyncio.create_task(run_cron_task(task))
            self._task_handles.append(handle)

    async def _stop_tasks(self) -> None:
        """Stop all running background tasks."""
        for handle in self._task_handles:
            handle.cancel()
        # Wait for all tasks to finish cancelling
        if self._task_handles:
            await asyncio.gather(*self._task_handles, return_exceptions=True)
        self._task_handles.clear()

    async def _handle_request(self, raw_request: GeminiRequest) -> GeminiResponse:
        """Handle an incoming request.

        This is the main request processing logic.
        """
        request = Request(raw_request, self)

        # Build middleware chain around the entire routing logic
        async def route_and_handle(req: Request) -> GeminiResponse:
            try:
                # Check mounted routes first
                mount_match = self._router.match_mount(req.path)
                if mount_match is not None:
                    mounted_route, path_info = mount_match
                    result = await mounted_route.call_handler(req, path_info)
                    return convert_response(result, req)

                # Match regular route
                match = self._router.match(req.path)
                if match is None:
                    raise NotFound(f"No route matches: {req.path}")

                route, params = match

                # Handle input flow
                if route.input_prompt and not req.query:
                    return Input(
                        route.input_prompt, route.sensitive_input
                    ).to_gemini_response()

                # Add query to params for input routes
                if route.input_prompt and req.query:
                    params["query"] = req.query

                # Call the handler
                result = await route.call_handler(req, params)
                return convert_response(result, req)

            except GeminiException as e:
                return GeminiResponse(status=e.status_code, meta=e.message)
            except Exception:
                # Log the error and return a generic failure
                import traceback

                traceback.print_exc()
                return GeminiResponse(
                    status=StatusCode.TEMPORARY_FAILURE,
                    meta="Internal server error",
                )

        # Apply middleware around the entire routing logic
        # This allows middleware to intercept requests before routing
        handler = route_and_handle
        for mw in reversed(self._middleware):
            handler = self._wrap_middleware(mw, handler)

        return await handler(request)

    async def _handle_titan_request(
        self, raw_request: NauyacaTitanRequest
    ) -> GeminiResponse:
        """Handle an incoming Titan upload request.

        This is the Titan request processing logic, separate from Gemini.
        """
        request = TitanRequest(raw_request, self)

        # Build middleware chain around the entire routing logic
        async def route_and_handle(req: TitanRequest) -> GeminiResponse:
            try:
                # Match Titan route
                match = self._router.match_titan(req.path)
                if match is None:
                    raise NotFound(f"No Titan route matches: {req.path}")

                route, params = match

                # Validate auth token if required
                if route.auth_tokens is not None:
                    if not req.token or req.token not in route.auth_tokens:
                        raise CertificateRequired("Valid authentication token required")

                # Call the handler
                result = await route.call_handler(req, params)
                return convert_response(result, req)

            except GeminiException as e:
                return GeminiResponse(status=e.status_code, meta=e.message)
            except Exception:
                import traceback

                traceback.print_exc()
                return GeminiResponse(
                    status=StatusCode.TEMPORARY_FAILURE,
                    meta="Internal server error",
                )

        # Apply middleware around the entire routing logic
        handler = route_and_handle
        for mw in reversed(self._middleware):
            handler = self._wrap_middleware(mw, handler)

        return await handler(request)

    def _wrap_middleware(
        self,
        middleware: Callable[..., Any],
        next_handler: Callable[..., Any],
    ) -> Callable[..., Any]:
        """Wrap a handler with middleware."""

        async def wrapped(request: Any) -> GeminiResponse:
            if asyncio.iscoroutinefunction(middleware):
                return await middleware(request, next_handler)
            return middleware(request, next_handler)

        return wrapped

    def handle_request_sync(self, raw_request: GeminiRequest) -> GeminiResponse:
        """Handle a request synchronously (for testing)."""
        return asyncio.get_event_loop().run_until_complete(
            self._handle_request(raw_request)
        )

    async def run_async(
        self,
        host: str = "localhost",
        port: int = 1965,
        certfile: Path | str | None = None,
        keyfile: Path | str | None = None,
    ) -> None:
        """Run the server asynchronously.

        Args:
            host: Host address to bind to.
            port: Port to bind to.
            certfile: Path to TLS certificate file.
            keyfile: Path to TLS private key file.
        """
        from nauyaca.server.protocol import GeminiServerProtocol
        from nauyaca.server.tls_protocol import TLSServerProtocol
        from nauyaca.security.certificates import generate_self_signed_cert
        from nauyaca.security.pyopenssl_tls import create_pyopenssl_server_context
        import tempfile

        # Run startup handlers
        await self._run_startup()

        # Start background tasks
        await self._run_tasks()

        try:
            # Create PyOpenSSL context (accepts any self-signed client cert)
            if certfile and keyfile:
                ssl_context = create_pyopenssl_server_context(
                    str(certfile),
                    str(keyfile),
                    request_client_cert=True,
                )
            else:
                # Generate self-signed cert for development
                cert_pem, key_pem = generate_self_signed_cert(
                    hostname="localhost",
                    key_size=2048,
                    valid_days=365,
                )

                with (
                    tempfile.NamedTemporaryFile(
                        suffix=".pem", delete=False, mode="wb"
                    ) as cf,
                    tempfile.NamedTemporaryFile(
                        suffix=".key", delete=False, mode="wb"
                    ) as kf,
                ):
                    cf.write(cert_pem)
                    kf.write(key_pem)
                    cf.flush()
                    kf.flush()
                    print("[Xitzin] Using self-signed certificate (development only)")
                    ssl_context = create_pyopenssl_server_context(
                        cf.name,
                        kf.name,
                        request_client_cert=True,
                    )

            # Create handler that routes to our app
            async def handle(request: GeminiRequest) -> GeminiResponse:
                return await self._handle_request(request)

            # Create Titan upload handler if Titan routes are registered
            upload_handler = None
            if self._router.has_titan_routes():
                from nauyaca.server.handler import UploadHandler

                class XitzinUploadHandler(UploadHandler):
                    """Wrapper to route Titan uploads to Xitzin handlers."""

                    def __init__(self, app: "Xitzin") -> None:
                        self._app = app

                    async def handle_upload(
                        self, request: NauyacaTitanRequest
                    ) -> GeminiResponse:
                        return await self._app._handle_titan_request(request)

                upload_handler = XitzinUploadHandler(self)
                print("[Xitzin] Titan upload support enabled")

            # Use TLSServerProtocol for manual TLS handling
            # (supports self-signed client certs)
            def create_protocol() -> TLSServerProtocol:
                return TLSServerProtocol(
                    lambda: GeminiServerProtocol(handle, None, upload_handler),
                    ssl_context,
                )

            loop = asyncio.get_running_loop()
            server = await loop.create_server(
                create_protocol,
                host,
                port,
            )

            print(f"[Xitzin] {self.title} v{self.version}")
            print(f"[Xitzin] Serving at gemini://{host}:{port}/")

            async with server:
                await server.serve_forever()

        finally:
            # Stop background tasks
            await self._stop_tasks()
            await self._run_shutdown()

    def run(
        self,
        host: str = "localhost",
        port: int = 1965,
        certfile: Path | str | None = None,
        keyfile: Path | str | None = None,
    ) -> None:
        """Run the server (blocking).

        Args:
            host: Host address to bind to.
            port: Port to bind to.
            certfile: Path to TLS certificate file.
            keyfile: Path to TLS private key file.
        """
        try:
            asyncio.run(
                self.run_async(host=host, port=port, certfile=certfile, keyfile=keyfile)
            )
        except KeyboardInterrupt:
            print("\n[Xitzin] Shutting down...")
