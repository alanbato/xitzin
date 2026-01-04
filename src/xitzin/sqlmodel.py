"""SQLModel integration for Xitzin.

This module provides database session management through middleware
and helper functions. Requires the 'sqlmodel' optional dependency.

Install with: pip install xitzin[sqlmodel]

Example:
    from sqlmodel import Field, select
    from xitzin import Xitzin, Request
    from xitzin.sqlmodel import (
        SQLModel,
        create_engine,
        SessionMiddleware,
        get_session,
        init_db,
    )

    # Define models
    class Entry(SQLModel, table=True):
        id: int | None = Field(default=None, primary_key=True)
        content: str

    # Setup app
    app = Xitzin()
    engine = create_engine("sqlite:///./database.db")

    # Initialize database and add middleware
    init_db(app, engine)
    app.middleware(SessionMiddleware(engine))

    # Use in routes
    @app.gemini("/entries")
    def list_entries(request: Request):
        session = get_session(request)
        entries = session.exec(select(Entry)).all()
        return render_entries(entries)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Awaitable, Callable

from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, create_engine

if TYPE_CHECKING:
    from nauyaca.protocol.response import GeminiResponse

    from xitzin.application import Xitzin
    from xitzin.requests import Request

__all__ = [
    "SQLModel",
    "Session",
    "create_engine",
    "SessionMiddleware",
    "get_session",
    "init_db",
]


def SessionMiddleware(
    engine: Engine,
    *,
    autoflush: bool = True,
) -> Callable[
    ["Request", Callable[["Request"], Awaitable["GeminiResponse"]]],
    Awaitable["GeminiResponse"],
]:
    """Create a middleware that manages database sessions per request.

    The session is stored in request.state.db and automatically committed
    on success or rolled back on error.

    Args:
        engine: SQLAlchemy engine instance.
        autoflush: If True, flush before queries. Defaults to True.

    Returns:
        Middleware function compatible with @app.middleware.

    Example:
        engine = create_engine("sqlite:///./database.db")
        app.middleware(SessionMiddleware(engine))
    """

    async def middleware(
        request: "Request",
        call_next: Callable[["Request"], Awaitable["GeminiResponse"]],
    ) -> "GeminiResponse":
        session = Session(engine, autoflush=autoflush)
        request.state.db = session

        try:
            response = await call_next(request)
            session.commit()
            return response
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    return middleware


def get_session(request: "Request") -> Session:
    """Get the database session from the current request.

    This helper retrieves the session created by SessionMiddleware.

    Args:
        request: The current Xitzin request object.

    Returns:
        SQLModel Session instance.

    Raises:
        AttributeError: If SessionMiddleware is not configured.

    Example:
        @app.gemini("/users/{user_id}")
        def get_user(request: Request, user_id: int):
            session = get_session(request)
            user = session.get(User, user_id)
            return f"# {user.name}"
    """
    if not hasattr(request.state, "db"):
        raise AttributeError(
            "No database session found. Did you add SessionMiddleware?"
        )
    return request.state.db


def init_db(
    app: "Xitzin",
    engine: Engine,
    *,
    create_tables: bool = True,
    drop_all: bool = False,
) -> None:
    """Initialize database with lifecycle hooks.

    This helper registers startup/shutdown hooks to manage table creation
    and engine cleanup.

    Args:
        app: Xitzin application instance.
        engine: SQLAlchemy engine instance.
        create_tables: Create all tables on startup. Defaults to True.
        drop_all: Drop all tables before creating. Defaults to False.

    Warning:
        Setting drop_all=True will DELETE ALL DATA on startup!

    Example:
        app = Xitzin()
        engine = create_engine("sqlite:///./database.db")
        init_db(app, engine)
    """

    @app.on_startup
    def create_db_tables() -> None:
        if drop_all:
            SQLModel.metadata.drop_all(engine)
        if create_tables:
            SQLModel.metadata.create_all(engine)

    @app.on_shutdown
    def dispose_engine() -> None:
        engine.dispose()
