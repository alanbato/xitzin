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
            raise ValueError(
                f"Route '{self.name}' missing required parameters: {', '.join(sorted(missing))}"
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


class Router:
    """Collection of routes with matching logic.

    Routes are matched in registration order; first match wins.
    """

    def __init__(self) -> None:
        self._routes: list[Route] = []
        self._routes_by_name: dict[str, Route] = {}

    def add_route(self, route: Route) -> None:
        """Add a route to the router.

        Raises:
            ValueError: If a route with the same name already exists.
        """
        if route.name in self._routes_by_name:
            existing = self._routes_by_name[route.name]
            raise ValueError(
                f"Route name '{route.name}' already registered for path '{existing.path}'. "
                f"Use the name= parameter to provide a unique name."
            )
        self._routes.append(route)
        self._routes_by_name[route.name] = route

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
