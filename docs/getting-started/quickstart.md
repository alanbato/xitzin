# Quickstart

Build your first Gemini capsule in 5 minutes.

## Create Your First App

Create a new file called `app.py`:

```python
from xitzin import Xitzin, Request

app = Xitzin()

@app.gemini("/")
def home(request: Request):
    return "# Welcome to my capsule!"

if __name__ == "__main__":
    app.run()
```

## Generate TLS Certificates

Gemini requires TLS. Generate a self-signed certificate for development:

```bash
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes -subj "/CN=localhost"
```

## Run the Server

```bash
python app.py
```

You should see output indicating the server is running on `gemini://localhost:1965`.

## Connect with a Gemini Client

Open your Gemini client (like [Lagrange](https://gmi.skyjake.fi/lagrange/)) and navigate to:

```
gemini://localhost/
```

You should see your "Welcome to my capsule!" message!

## Adding More Routes

Let's add some more functionality:

```python
from xitzin import Xitzin, Request

app = Xitzin()

@app.gemini("/")
def home(request: Request):
    return """# Welcome to my capsule!

=> /about About me
=> /projects My projects
"""

@app.gemini("/about")
def about(request: Request):
    return """# About Me

I'm building cool things with Xitzin!

=> / Back home
"""

@app.gemini("/projects")
def projects(request: Request):
    return """# My Projects

* Project Alpha
* Project Beta
* Project Gamma

=> / Back home
"""

if __name__ == "__main__":
    app.run()
```

## Path Parameters

Extract values from the URL path:

```python
@app.gemini("/user/{username}")
def profile(request: Request, username: str):
    return f"""# {username}'s Profile

Welcome to the profile of {username}!
"""

@app.gemini("/post/{post_id}")
def post(request: Request, post_id: int):
    # post_id is automatically converted to int
    return f"# Post #{post_id}"
```

## User Input

Gemini uses status codes 10/11 for user input. Use the `@app.input` decorator:

```python
@app.input("/search", prompt="Enter your search query:")
def search(request: Request, query: str):
    return f"""# Search Results

You searched for: {query}

* Result 1
* Result 2
* Result 3
"""
```

When a user visits `/search`, they'll see a prompt. After entering their query, they'll see the results.

## Next Steps

- Learn about [templates](../how-to/templates.md) for cleaner Gemtext
- Add [certificate authentication](../how-to/authentication.md) for user identity
- Explore the [tutorials](../tutorials/index.md) for complete examples
