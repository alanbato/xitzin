# SQLModel Integration

Database session management for Xitzin applications using SQLModel.

!!! note "Optional Dependency"
    Requires the `sqlmodel` extra: `pip install xitzin[sqlmodel]`

## SessionMiddleware

Creates middleware that manages database sessions per request.

::: xitzin.sqlmodel.SessionMiddleware

## get_session

Retrieves the database session from the current request.

::: xitzin.sqlmodel.get_session

## init_db

Registers database lifecycle hooks for table creation and cleanup.

::: xitzin.sqlmodel.init_db

## Re-exports

The following are re-exported from `sqlmodel` for convenience:

- `SQLModel` - Base class for models
- `Session` - Database session class
- `create_engine` - Engine factory function
