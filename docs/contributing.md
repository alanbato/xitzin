# Contributing

Thank you for your interest in contributing to Xitzin!

## Development Setup

1. Clone the repository:

```bash
git clone https://github.com/alanbato/xitzin.git
cd xitzin
```

2. Install dependencies with uv:

```bash
uv sync --group dev --group docs
```

3. Run tests:

```bash
uv run pytest
```

4. Run linting:

```bash
uv run ruff check src/
```

5. Run type checking:

```bash
uv run ty check src/
```

## Documentation

To build and preview documentation locally:

```bash
# Serve with hot reload
uv run mkdocs serve

# Build for production
uv run mkdocs build
```

Documentation is built with MkDocs and uses the Material theme.

## Code Style

- Follow PEP 8 guidelines
- Use type hints for all public functions
- Write docstrings in Google style
- Keep line length under 88 characters (Black default)

## Pull Requests

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests and linting
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to your branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## Reporting Issues

When reporting issues, please include:

- Python version
- Xitzin version
- Operating system
- Minimal reproducible example
- Expected vs actual behavior

## Code of Conduct

Please be respectful and constructive in all interactions.
