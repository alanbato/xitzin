# Installation

## Requirements

- Python 3.10 or higher
- pip, uv, or another Python package manager

## Installing with pip

```bash
pip install xitzin
```

## Installing with uv

[uv](https://docs.astral.sh/uv/) is the recommended package manager for Python projects:

```bash
uv add xitzin
```

## Installing from Source

For development or to get the latest changes:

```bash
git clone https://github.com/alanbato/xitzin.git
cd xitzin
uv sync
```

## Verifying Installation

Open a Python interpreter and verify the installation:

```python
>>> import xitzin
>>> xitzin.__version__
'0.1.0'
```

## Dependencies

Xitzin automatically installs its core dependencies:

- **[Nauyaca](https://github.com/alanbato/nauyaca)**: Gemini protocol implementation
- **[Jinja2](https://jinja.palletsprojects.com/)**: Template engine

## Next Steps

Now that you have Xitzin installed, head to the [Quickstart](quickstart.md) to build your first Gemini capsule!
