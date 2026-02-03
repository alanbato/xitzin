"""Static file serving for Xitzin applications.

This module provides static file serving capabilities for Xitzin,
enabling capsules to serve files from a directory with configurable
options for directory listings, MIME types, and security settings.

Example:
    from xitzin import Xitzin
    from xitzin.staticfiles import StaticFiles

    app = Xitzin()

    # Mount static files at a path
    app.mount("/files", StaticFiles("./public"))

    # Or use the convenience method
    app.static("/docs", "./documentation", directory_listing=True)
"""

from __future__ import annotations

import asyncio
import mimetypes
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from nauyaca.protocol.response import GeminiResponse
from nauyaca.protocol.status import StatusCode

from .exceptions import BadRequest, NotFound
from .responses import Redirect

if TYPE_CHECKING:
    from .requests import Request

# Default MIME types for Gemini/common files
DEFAULT_MIME_TYPES: dict[str, str] = {
    ".gmi": "text/gemini",
    ".gemini": "text/gemini",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".html": "text/html",
    ".css": "text/css",
    ".js": "text/javascript",
    ".json": "application/json",
    ".xml": "application/xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
    ".zip": "application/zip",
    ".gz": "application/gzip",
    ".tar": "application/x-tar",
}

# MIME types that should be read as binary
BINARY_MIME_PREFIXES = (
    "image/",
    "video/",
    "audio/",
    "application/pdf",
    "application/zip",
    "application/gzip",
    "application/x-tar",
    "application/octet-stream",
)


@dataclass
class StaticFilesConfig:
    """Configuration for static file serving.

    Attributes:
        index_files: Files to serve for directory requests.
        directory_listing: Enable directory listing when no index found.
        max_file_size: Maximum file size to serve (bytes).
        mime_types: Custom MIME type mappings by extension.
        follow_symlinks: Whether to follow symbolic links.
    """

    index_files: list[str] = field(
        default_factory=lambda: ["index.gmi", "index.gemini"]
    )
    directory_listing: bool = False
    max_file_size: int = 100 * 1024 * 1024  # 100 MiB
    mime_types: dict[str, str] = field(default_factory=dict)
    follow_symlinks: bool = False


def _format_file_size(size: int) -> str:
    """Format file size in human-readable form.

    Args:
        size: Size in bytes.

    Returns:
        Human-readable size string (e.g., "1.5 KB", "100 MB").
    """
    value: float = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024:
            if unit == "B":
                return f"{int(value)} {unit}"
            if value < 10:
                return f"{value:.1f} {unit}"
            return f"{int(value)} {unit}"
        value /= 1024
    return f"{int(value)} PB"


class StaticFiles:
    """Serve static files from a directory.

    This handler serves files from a specified directory, with support
    for directory indexes, directory listings, custom MIME types,
    and security controls.

    Example:
        from xitzin.staticfiles import StaticFiles

        # Basic usage
        handler = StaticFiles("./public")
        app.mount("/files", handler)

        # With configuration
        handler = StaticFiles(
            "./docs",
            directory_listing=True,
            max_file_size=50 * 1024 * 1024,
        )

        @handler.not_found
        def custom_404(request, path_info):
            return "# File Not Found"

        app.mount("/docs", handler)
    """

    def __init__(
        self,
        directory: Path | str,
        *,
        config: StaticFilesConfig | None = None,
        index_files: list[str] | None = None,
        directory_listing: bool | None = None,
        max_file_size: int | None = None,
        mime_types: dict[str, str] | None = None,
        follow_symlinks: bool | None = None,
    ) -> None:
        """Create a static file handler.

        Args:
            directory: Directory to serve files from.
            config: Configuration object (overridden by other params).
            index_files: Files to serve for directory requests.
            directory_listing: Enable directory listing when no index found.
            max_file_size: Maximum file size to serve (bytes).
            mime_types: Custom MIME type mappings by extension.
            follow_symlinks: Whether to follow symbolic links.

        Raises:
            ValueError: If directory doesn't exist or isn't a directory.
        """
        self.directory = Path(directory).resolve()
        self._not_found_handler: Callable[[Any, str], Any] | None = None

        if not self.directory.exists():
            raise ValueError(f"Directory not found: {directory}")
        if not self.directory.is_dir():
            raise ValueError(f"Path is not a directory: {directory}")

        # Start with config defaults, override with explicit parameters
        base_config = config or StaticFilesConfig()

        self.index_files = (
            index_files if index_files is not None else base_config.index_files
        )
        self.directory_listing = (
            directory_listing
            if directory_listing is not None
            else base_config.directory_listing
        )
        self.max_file_size = (
            max_file_size if max_file_size is not None else base_config.max_file_size
        )
        self.follow_symlinks = (
            follow_symlinks
            if follow_symlinks is not None
            else base_config.follow_symlinks
        )

        # Build MIME type mapping: defaults + config + explicit
        self._mime_types = {**DEFAULT_MIME_TYPES}
        self._mime_types.update(base_config.mime_types)
        if mime_types:
            self._mime_types.update(mime_types)

    def not_found(
        self, handler: Callable[[Any, str], Any]
    ) -> Callable[[Any, str], Any]:
        """Register a custom not-found handler.

        The handler receives (request, path_info) and should return a response.

        Example:
            @handler.not_found
            def custom_404(request, path_info):
                return f"# Not Found\\n\\nFile {path_info} doesn't exist."
        """
        self._not_found_handler = handler
        return handler

    async def __call__(self, request: Request, path_info: str) -> GeminiResponse:
        """Handle a request for a static file.

        Args:
            request: The Gemini request.
            path_info: Path after the mount prefix (e.g., "/docs/page.gmi").

        Returns:
            GeminiResponse with the file content or error.

        Raises:
            NotFound: If file doesn't exist (and no custom handler).
            BadRequest: If path validation fails.
        """
        try:
            # Normalize path_info
            path_info = path_info.lstrip("/") if path_info else ""

            # Resolve and validate path
            file_path = self._resolve_path(path_info)

            # Handle directory
            if file_path.is_dir():
                return await self._serve_directory(request, file_path, path_info)

            # Handle file
            return await self._serve_file(file_path)

        except NotFound:
            if self._not_found_handler is not None:
                result = self._not_found_handler(request, path_info)
                if asyncio.iscoroutine(result):
                    result = await result
                return self._convert_handler_result(result)
            raise

    def _resolve_path(self, path_info: str) -> Path:
        """Resolve path_info to a validated filesystem path.

        Args:
            path_info: Requested path relative to mount point.

        Returns:
            Resolved Path object.

        Raises:
            BadRequest: If path contains traversal attempts.
            NotFound: If resolved path doesn't exist.
        """
        # Reject obvious traversal attempts early
        if ".." in path_info:
            raise BadRequest("Invalid path")

        # Build candidate path
        if path_info:
            candidate = self.directory / path_info
        else:
            candidate = self.directory

        # Resolve the path, handling symlinks based on config
        if self.follow_symlinks:
            resolved = candidate.resolve()
        else:
            # Resolve parent but not the final component
            resolved = candidate.parent.resolve() / candidate.name
            # Check if final component is a symlink
            if resolved.is_symlink():
                raise BadRequest("Symbolic links not allowed")
            # Now fully resolve to catch any issues
            resolved = resolved.resolve()

        # Security check: ensure path is within allowed directory
        try:
            resolved.relative_to(self.directory)
        except ValueError:
            raise BadRequest("Invalid path") from None

        # Check existence
        if not resolved.exists():
            raise NotFound("File not found")

        return resolved

    def _get_mime_type(self, file_path: Path) -> str:
        """Determine MIME type for a file.

        Args:
            file_path: Path to the file.

        Returns:
            MIME type string.
        """
        suffix = file_path.suffix.lower()

        # Check custom mappings first
        if suffix in self._mime_types:
            return self._mime_types[suffix]

        # Try stdlib mimetypes
        guessed, _ = mimetypes.guess_type(str(file_path))
        if guessed:
            return guessed

        # Default to text/gemini for Gemini-centric behavior
        return "text/gemini"

    def _is_binary_mime(self, mime_type: str) -> bool:
        """Check if MIME type indicates binary content.

        Args:
            mime_type: MIME type string.

        Returns:
            True if content should be read as binary.
        """
        return mime_type.startswith(BINARY_MIME_PREFIXES)

    async def _serve_file(self, file_path: Path) -> GeminiResponse:
        """Serve a file with appropriate MIME type.

        Args:
            file_path: Path to the file.

        Returns:
            GeminiResponse with file content.

        Raises:
            BadRequest: If file exceeds size limit.
            NotFound: If file cannot be read.
        """
        # Check file size before reading
        try:
            size = file_path.stat().st_size
        except OSError:
            raise NotFound("File not found") from None

        if size > self.max_file_size:
            raise BadRequest(
                f"File too large ({_format_file_size(size)}, "
                f"max {_format_file_size(self.max_file_size)})"
            )

        mime_type = self._get_mime_type(file_path)
        is_binary = self._is_binary_mime(mime_type)

        try:
            if is_binary:
                # Read binary in thread to avoid blocking
                body: str | bytes = await asyncio.to_thread(file_path.read_bytes)
            else:
                body = await asyncio.to_thread(file_path.read_text, encoding="utf-8")
        except UnicodeDecodeError:
            # Fall back to binary if text decode fails
            body = await asyncio.to_thread(file_path.read_bytes)
        except OSError:
            raise NotFound("File not found") from None

        return GeminiResponse(
            status=StatusCode.SUCCESS,
            meta=mime_type,
            body=body,
        )

    async def _serve_directory(
        self, request: Request, dir_path: Path, path_info: str
    ) -> GeminiResponse:
        """Serve a directory request.

        Args:
            request: The Gemini request.
            dir_path: Path to the directory.
            path_info: Original path_info for this request.

        Returns:
            GeminiResponse with index file, directory listing, or redirect.

        Raises:
            NotFound: If no index and directory listing disabled.
        """
        # Ensure trailing slash for directories
        if path_info and not request.path.endswith("/"):
            redirect_url = request.path + "/"
            return Redirect(redirect_url, permanent=False).to_gemini_response()

        # Try to find an index file
        for index_name in self.index_files:
            index_path = dir_path / index_name
            if index_path.is_file():
                return await self._serve_file(index_path)

        # Generate directory listing if enabled
        if self.directory_listing:
            listing = self._generate_directory_listing(dir_path, path_info)
            return GeminiResponse(
                status=StatusCode.SUCCESS,
                meta="text/gemini",
                body=listing,
            )

        raise NotFound("Directory index not found")

    def _generate_directory_listing(self, dir_path: Path, request_path: str) -> str:
        """Generate a Gemini directory listing.

        Args:
            dir_path: Path to the directory.
            request_path: The request path for display.

        Returns:
            Gemtext directory listing.
        """
        display_path = "/" + request_path if request_path else "/"
        lines = [f"# Index of {display_path}", ""]

        # Parent directory link (if not at root)
        if request_path:
            lines.append("=> ../ ..")
            lines.append("")

        # Collect and sort entries: directories first, then files
        entries = []
        try:
            for entry in dir_path.iterdir():
                # Skip hidden files
                if entry.name.startswith("."):
                    continue

                # Skip symlinks if not following them
                if not self.follow_symlinks and entry.is_symlink():
                    continue

                entries.append(entry)
        except OSError:
            pass

        # Sort: directories first, then alphabetically by name
        entries.sort(key=lambda p: (not p.is_dir(), p.name.lower()))

        # Generate links
        for entry in entries:
            name = entry.name
            if entry.is_dir():
                lines.append(f"=> {name}/ {name}/")
            else:
                try:
                    size = _format_file_size(entry.stat().st_size)
                    lines.append(f"=> {name} {name} ({size})")
                except OSError:
                    lines.append(f"=> {name} {name}")

        return "\n".join(lines)

    def _convert_handler_result(self, result: Any) -> GeminiResponse:
        """Convert a custom handler result to GeminiResponse.

        Args:
            result: Handler return value.

        Returns:
            GeminiResponse.
        """
        # Import here to avoid circular import
        from .responses import convert_response

        return convert_response(result)


__all__ = [
    "StaticFiles",
    "StaticFilesConfig",
]
