"""Main Xitzin application class.

This module provides the Xitzin class, the main entry point for creating
Gemini applications.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from nauyaca.protocol.request import GeminiRequest
from nauyaca.protocol.response import GeminiResponse
from nauyaca.protocol.status import StatusCode

from .exceptions import GeminiException, NotFound
from .requests import Request
from .responses import Input, convert_response
from .routing import Route, Router

if TYPE_CHECKING:
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

        if templates_dir:
            self._init_templates(Path(templates_dir))

    def _init_templates(self, templates_dir: Path) -> None:
        """Initialize the template engine."""
        from .templating import TemplateEngine

        self._templates = TemplateEngine(templates_dir)

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

    def gemini(self, path: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Register a route handler.

        Args:
            path: URL path pattern (e.g., "/user/{id}").

        Returns:
            Decorator function.

        Example:
            @app.gemini("/")
            def home(request: Request):
                return "# Home"

            @app.gemini("/user/{username}")
            def profile(request: Request, username: str):
                return f"# {username}"
        """

        def decorator(handler: Callable[..., Any]) -> Callable[..., Any]:
            route = Route(path, handler)
            self._router.add_route(route)
            return handler

        return decorator

    def input(
        self, path: str, *, prompt: str, sensitive: bool = False
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Register an input route (status 10/11 flow).

        When a request arrives without a query string, the client is prompted
        for input. When the request includes a query string, the handler is
        called with the decoded input as the `query` parameter.

        Args:
            path: URL path pattern.
            prompt: Prompt text shown to the user.
            sensitive: If True, use status 11 (sensitive input).

        Returns:
            Decorator function.

        Example:
            @app.input("/search", prompt="Enter search query:")
            def search(request: Request, query: str):
                return f"# Results for: {query}"
        """

        def decorator(handler: Callable[..., Any]) -> Callable[..., Any]:
            route = Route(path, handler, input_prompt=prompt, sensitive_input=sensitive)
            self._router.add_route(route)
            return handler

        return decorator

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

    async def _handle_request(self, raw_request: GeminiRequest) -> GeminiResponse:
        """Handle an incoming request.

        This is the main request processing logic.
        """
        request = Request(raw_request, self)

        try:
            # Match route
            match = self._router.match(request.path)
            if match is None:
                raise NotFound(f"No route matches: {request.path}")

            route, params = match

            # Handle input flow
            if route.input_prompt and not request.query:
                return Input(
                    route.input_prompt, route.sensitive_input
                ).to_gemini_response()

            # Add query to params for input routes
            if route.input_prompt and request.query:
                params["query"] = request.query

            # Build middleware chain
            async def call_handler(req: Request) -> GeminiResponse:
                result = await route.call_handler(req, params)
                return convert_response(result, req)

            # Apply middleware (in reverse order so first registered runs first)
            handler = call_handler
            for mw in reversed(self._middleware):
                handler = self._wrap_middleware(mw, handler)

            return await handler(request)

        except GeminiException as e:
            return GeminiResponse(status=e.status_code, meta=e.message)
        except Exception as e:
            # Log the error and return a generic failure
            import traceback

            traceback.print_exc()
            return GeminiResponse(
                status=StatusCode.TEMPORARY_FAILURE,
                meta=f"Internal error: {type(e).__name__}",
            )

    def _wrap_middleware(
        self,
        middleware: Callable[..., Any],
        next_handler: Callable[[Request], Any],
    ) -> Callable[[Request], Any]:
        """Wrap a handler with middleware."""

        async def wrapped(request: Request) -> GeminiResponse:
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
        from nauyaca.security.certificates import generate_self_signed_cert
        from nauyaca.security.tls import create_server_context
        import tempfile

        # Run startup handlers
        await self._run_startup()

        try:
            # Create SSL context
            if certfile and keyfile:
                ssl_context = create_server_context(
                    str(certfile),
                    str(keyfile),
                    request_client_cert=False,
                )
            else:
                # Generate self-signed cert for development
                cert_pem, key_pem = generate_self_signed_cert(
                    hostname="localhost",
                    key_size=2048,
                    valid_days=365,
                )
                import ssl

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
                    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                    ssl_context.load_cert_chain(cf.name, kf.name)
                    ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2

            # Create handler that routes to our app
            async def handle(request: GeminiRequest) -> GeminiResponse:
                return await self._handle_request(request)

            loop = asyncio.get_running_loop()
            server = await loop.create_server(
                lambda: GeminiServerProtocol(handle, None),  # type: ignore[arg-type]
                host,
                port,
                ssl=ssl_context,
            )

            print(f"[Xitzin] {self.title} v{self.version}")
            print(f"[Xitzin] Serving at gemini://{host}:{port}/")

            async with server:
                await server.serve_forever()

        finally:
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
