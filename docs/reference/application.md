# Application

The main application class and lifecycle management.

## Xitzin

The core application class that handles routing, middleware, and server lifecycle.

::: xitzin.application.Xitzin
    options:
      members:
        - __init__
        - state
        - template
        - reverse
        - redirect
        - gemini
        - input
        - on_startup
        - on_shutdown
        - middleware
        - run
        - run_async

## AppState

Application-level state storage for shared resources like database connections.

::: xitzin.application.AppState
