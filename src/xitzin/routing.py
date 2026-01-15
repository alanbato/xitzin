"""Route decorator and path parameter handling.

This module provides the Route class and path parameter extraction logic.
"""

from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING, Any, Callable, get_type_hints

if TYPE_CHECKING:
    from .requests import Request

# Pattern to match path parameters like {name} or {name:path}
PATH_PARAM_PATTERN = re.compile(r"\{(\w+)(?::(\w+))?\}")


class Route:
    """Represents a registered route.

    Routes match URL paths and extract parameters based on the path template.

    Example:
        route = Route("/user/{username}", handler_func)
        if route.matches("/user/alice"):
            params = route.extract_params("/user/alice")
            # params = {"username": "alice"}
    """

    def __init__(
        self,
        path: str,
        handler: Callable[..., Any],
        *,
        name: str | None = None,
        input_prompt: str | None = None,
        sensitive_input: bool = False,
    ) -> None:
        """Create a new route.

        Args:
            path: Path template with optional parameters (e.g., "/user/{id}").
            handler: The handler function to call.
            name: Route name for URL reversing. Defaults to handler function name.
            input_prompt: If set, request input with this prompt before calling handler.
            sensitive_input: If True, use status 11 (sensitive input) instead of 10.
        """
        self.path = path
        self.handler = handler
        self.name = (
            name if name is not None else getattr(handler, "__name__", "<anonymous>")
        )
        self.input_prompt = input_prompt
        self.sensitive_input = sensitive_input

        self._param_pattern, self._param_names = self._compile_path(path)
        self._type_hints = self._get_handler_type_hints(handler)
        self._is_async = asyncio.iscoroutinefunction(handler)

    def _compile_path(self, path: str) -> tuple[re.Pattern[str], list[str]]:
        """Convert a path template to a regex pattern.

        Args:
            path: Path template like "/user/{id}" or "/files/{path:path}".

        Returns:
            Tuple of (compiled regex, list of parameter names).
        """
        param_names: list[str] = []

        def replace_param(match: re.Match[str]) -> str:
            name = match.group(1)
            param_type = match.group(2)
            param_names.append(name)

            # :path captures everything including slashes
            if param_type == "path":
                return f"(?P<{name}>.+)"
            # Default: capture until next slash
            return f"(?P<{name}>[^/]+)"

        # Escape regex special chars except our parameter syntax
        escaped = re.escape(path)
        # Unescape our parameter syntax
        escaped = escaped.replace(r"\{", "{").replace(r"\}", "}")
        # Replace parameters with capture groups
        regex_path = PATH_PARAM_PATTERN.sub(replace_param, escaped)

        return re.compile(f"^{regex_path}$"), param_names

    def _get_handler_type_hints(self, handler: Callable[..., Any]) -> dict[str, type]:
        """Extract type hints from handler function.

        Excludes 'request' and 'return' from the hints.
        """
        try:
            hints = get_type_hints(handler)
            # Remove non-parameter hints
            hints.pop("request", None)
            hints.pop("return", None)
            return hints
        except Exception:
            return {}

    def matches(self, path: str) -> bool:
        """Check if this route matches the given path.

        Args:
            path: URL path to match.

        Returns:
            True if the path matches this route's pattern.
        """
        return self._param_pattern.match(path) is not None

    def extract_params(self, path: str) -> dict[str, Any]:
        """Extract and type-convert path parameters.

        Args:
            path: URL path to extract parameters from.

        Returns:
            Dictionary of parameter names to values.
        """
        match = self._param_pattern.match(path)
        if not match:
            return {}

        params: dict[str, Any] = {}
        for name, value in match.groupdict().items():
            # Apply type conversion based on handler annotations
            target_type = self._type_hints.get(name, str)
            try:
                if target_type is int:
                    params[name] = int(value)
                elif target_type is float:
                    params[name] = float(value)
                elif target_type is bool:
                    params[name] = value.lower() in ("true", "1", "yes")
                else:
                    params[name] = value
            except (ValueError, TypeError):
                # Keep as string if conversion fails
                params[name] = value

        return params

    async def call_handler(self, request: Request, params: dict[str, Any]) -> Any:
        """Call the handler with the request and extracted parameters.

        Args:
            request: The current request.
            params: Extracted path parameters.

        Returns:
            The handler's return value.
        """
        if self._is_async:
            return await self.handler(request, **params)
        # Wrap sync handler in executor to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.handler(request, **params))

    def reverse(self, **params: Any) -> str:
        """Build URL from this route's path template.

        Args:
            **params: Path parameters to substitute.

        Returns:
            URL path string.

        Raises:
            ValueError: If required parameters are missing.

        Example:
            route = Route("/user/{username}", handler)
            route.reverse(username="alice")  # Returns "/user/alice"
        """
        missing = set(self._param_names) - set(params.keys())
        if missing:
            missing_params = ", ".join(sorted(missing))
            raise ValueError(
                f"Route '{self.name}' missing required parameters: {missing_params}"
            )

        url = self.path
        for name in self._param_names:
            value = str(params[name])
            # Handle both {name} and {name:path} patterns
            url = url.replace(f"{{{name}}}", value)
            url = url.replace(f"{{{name}:path}}", value)

        return url

    def __repr__(self) -> str:
        return f"Route({self.path!r}, name={self.name!r})"


class MountedRoute:
    """Route that delegates to a mounted handler at a path prefix.

    Unlike regular Route, this matches path prefixes and passes the
    remaining path to the handler, enabling directory-style mounting.

    Example:
        mounted = MountedRoute("/cgi-bin", cgi_handler)
        if mounted.matches("/cgi-bin/script.py"):
            # Calls handler with path_info="script.py"
    """

    def __init__(
        self,
        path_prefix: str,
        handler: Callable[..., Any],
        *,
        name: str | None = None,
    ) -> None:
        """Create a mounted route.

        Args:
            path_prefix: Path prefix to match (e.g., "/cgi-bin").
            handler: Handler that receives (request, path_info) where
                path_info is the path after the prefix.
            name: Optional name for the mount.
        """
        # Normalize prefix: ensure it starts with / and doesn't end with /
        self.path_prefix = "/" + path_prefix.strip("/")
        self.handler = handler
        self.name = name or getattr(handler, "__name__", "<mounted>")
        self._is_async = asyncio.iscoroutinefunction(handler) or (
            hasattr(handler, "__call__")
            and asyncio.iscoroutinefunction(handler.__call__)
        )

    def matches(self, path: str) -> bool:
        """Check if this mount matches the given path.

        Args:
            path: URL path to match.

        Returns:
            True if path starts with this mount's prefix.
        """
        # Exact match or prefix with /
        return path == self.path_prefix or path.startswith(self.path_prefix + "/")

    def extract_path_info(self, path: str) -> str:
        """Extract the path info (remaining path after prefix).

        Args:
            path: Full URL path.

        Returns:
            The path after the mount prefix.
        """
        if path == self.path_prefix:
            return ""
        # Remove prefix, keep the leading /
        return path[len(self.path_prefix) :]

    async def call_handler(self, request: Request, path_info: str) -> Any:
        """Call the handler with the request and path info.

        Args:
            request: The current request.
            path_info: Path after the mount prefix.

        Returns:
            The handler's return value.
        """
        if self._is_async:
            return await self.handler(request, path_info)
        # Wrap sync handler in executor to avoid blocking
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, lambda: self.handler(request, path_info)
        )

    def __repr__(self) -> str:
        return f"MountedRoute({self.path_prefix!r}, name={self.name!r})"


class TitanRoute:
    """Route for Titan upload handlers with integrated authentication.

    Similar to Route, but designed for Titan uploads with:
    - Token-based authentication
    - Explicit content/mime_type/token parameters passed to handlers

    Example:
        route = TitanRoute(
            "/upload/{filename}",
            upload_handler,
            auth_tokens=["secret123"]
        )
    """

    def __init__(
        self,
        path: str,
        handler: Callable[..., Any],
        *,
        name: str | None = None,
        auth_tokens: list[str] | None = None,
    ) -> None:
        """Create a new Titan route.

        Args:
            path: Path template with optional parameters (e.g., "/upload/{filename}").
            handler: The handler function to call.
            name: Route name for identification. Defaults to handler function name.
            auth_tokens: List of valid authentication tokens. If provided,
                requests without a valid token are rejected with status 60.
        """
        self.path = path
        self.handler = handler
        self.name = (
            name if name is not None else getattr(handler, "__name__", "<anonymous>")
        )
        self.auth_tokens = set(auth_tokens) if auth_tokens else None

        self._param_pattern, self._param_names = self._compile_path(path)
        self._type_hints = self._get_handler_type_hints(handler)
        self._is_async = asyncio.iscoroutinefunction(handler)

    def _compile_path(self, path: str) -> tuple[re.Pattern[str], list[str]]:
        """Convert a path template to a regex pattern.

        Same logic as Route._compile_path().
        """
        param_names: list[str] = []

        def replace_param(match: re.Match[str]) -> str:
            name = match.group(1)
            param_type = match.group(2)
            param_names.append(name)

            if param_type == "path":
                return f"(?P<{name}>.+)"
            return f"(?P<{name}>[^/]+)"

        escaped = re.escape(path)
        escaped = escaped.replace(r"\{", "{").replace(r"\}", "}")
        regex_path = PATH_PARAM_PATTERN.sub(replace_param, escaped)

        return re.compile(f"^{regex_path}$"), param_names

    def _get_handler_type_hints(self, handler: Callable[..., Any]) -> dict[str, type]:
        """Extract type hints from handler function.

        Excludes 'request', 'content', 'mime_type', 'token', and 'return'.
        """
        try:
            hints = get_type_hints(handler)
            # Remove non-path-parameter hints
            hints.pop("request", None)
            hints.pop("content", None)
            hints.pop("mime_type", None)
            hints.pop("token", None)
            hints.pop("return", None)
            return hints
        except Exception:
            return {}

    def matches(self, path: str) -> bool:
        """Check if this route matches the given path."""
        return self._param_pattern.match(path) is not None

    def extract_params(self, path: str) -> dict[str, Any]:
        """Extract and type-convert path parameters."""
        match = self._param_pattern.match(path)
        if not match:
            return {}

        params: dict[str, Any] = {}
        for name, value in match.groupdict().items():
            target_type = self._type_hints.get(name, str)
            try:
                if target_type is int:
                    params[name] = int(value)
                elif target_type is float:
                    params[name] = float(value)
                elif target_type is bool:
                    params[name] = value.lower() in ("true", "1", "yes")
                else:
                    params[name] = value
            except (ValueError, TypeError):
                params[name] = value

        return params

    async def call_handler(self, request: Any, params: dict[str, Any]) -> Any:
        """Call the handler with request and explicit Titan parameters.

        Args:
            request: TitanRequest object (typed as Any to avoid circular imports).
            params: Path parameters extracted from the URL.

        Handler receives: (request, content, mime_type, token, **path_params)
        """
        # Add Titan-specific parameters
        handler_params = {
            "content": request.content,
            "mime_type": request.mime_type,
            "token": request.token,
            **params,
        }

        if self._is_async:
            return await self.handler(request, **handler_params)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: self.handler(request, **handler_params)
        )

    def __repr__(self) -> str:
        return f"TitanRoute({self.path!r}, name={self.name!r})"


class Router:
    """Collection of routes with matching logic.

    Routes are matched in registration order; first match wins.
    Mounted routes are checked before regular routes.
    """

    def __init__(self) -> None:
        self._routes: list[Route] = []
        self._routes_by_name: dict[str, Route] = {}
        self._mounted_routes: list[MountedRoute] = []
        self._titan_routes: list[TitanRoute] = []

    def add_route(self, route: Route) -> None:
        """Add a route to the router.

        Raises:
            ValueError: If a route with the same name already exists.
        """
        if route.name in self._routes_by_name:
            existing = self._routes_by_name[route.name]
            msg = (
                f"Route name '{route.name}' already registered "
                f"for path '{existing.path}'. "
                f"Use the name= parameter to provide a unique name."
            )
            raise ValueError(msg)
        self._routes.append(route)
        self._routes_by_name[route.name] = route

    def add_mounted_route(self, route: MountedRoute) -> None:
        """Add a mounted route to the router.

        Mounted routes are checked before regular routes.

        Args:
            route: The mounted route to add.
        """
        self._mounted_routes.append(route)

    def match_mount(self, path: str) -> tuple[MountedRoute, str] | None:
        """Find a matching mounted route and extract path info.

        Args:
            path: URL path to match.

        Returns:
            Tuple of (mounted_route, path_info) if found, None otherwise.
        """
        for mounted in self._mounted_routes:
            if mounted.matches(path):
                path_info = mounted.extract_path_info(path)
                return mounted, path_info
        return None

    def match(self, path: str) -> tuple[Route, dict[str, Any]] | None:
        """Find a matching route and extract parameters.

        Args:
            path: URL path to match.

        Returns:
            Tuple of (route, params) if found, None otherwise.
        """
        for route in self._routes:
            if route.matches(path):
                params = route.extract_params(path)
                return route, params
        return None

    def add_titan_route(self, route: TitanRoute) -> None:
        """Add a Titan upload route to the router.

        Args:
            route: The Titan route to add.
        """
        self._titan_routes.append(route)

    def match_titan(self, path: str) -> tuple[TitanRoute, dict[str, Any]] | None:
        """Find a matching Titan route and extract parameters.

        Args:
            path: URL path to match.

        Returns:
            Tuple of (titan_route, params) if found, None otherwise.
        """
        for route in self._titan_routes:
            if route.matches(path):
                params = route.extract_params(path)
                return route, params
        return None

    def has_titan_routes(self) -> bool:
        """Check if any Titan routes are registered."""
        return len(self._titan_routes) > 0

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
            router.reverse("user_profile", username="alice")
            # Returns "/user/alice"
        """
        if name not in self._routes_by_name:
            available = ", ".join(sorted(self._routes_by_name.keys()))
            raise ValueError(f"No route named '{name}'. Available routes: {available}")
        route = self._routes_by_name[name]
        return route.reverse(**params)

    def __iter__(self):
        return iter(self._routes)

    def __len__(self):
        return len(self._routes)
