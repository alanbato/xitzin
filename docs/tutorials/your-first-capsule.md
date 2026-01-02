# Your First Capsule

In this tutorial, you'll build a complete personal capsule with a home page, about page, and a projects section.

## What You'll Learn

- Creating a Xitzin application
- Defining routes with `@app.gemini()`
- Writing Gemtext content
- Using path parameters
- Running and testing your capsule

## Step 1: Project Setup

Create a new directory for your project:

```bash
mkdir my-capsule
cd my-capsule
```

Initialize it with uv (or use pip):

```bash
uv init
uv add xitzin
```

## Step 2: Create the Application

Create a file called `capsule.py`:

```python
from xitzin import Xitzin, Request

app = Xitzin(title="My Personal Capsule")

@app.gemini("/")
def home(request: Request):
    return """# Welcome to My Capsule

Hello, Geminispace! This is my personal corner of the smolnet.

## Navigation

=> /about About Me
=> /projects My Projects
=> /links Cool Links
"""

if __name__ == "__main__":
    app.run()
```

Let's break this down:

- `Xitzin(title="...")` creates your application with a title
- `@app.gemini("/")` registers a handler for the root path
- The handler returns a string in Gemtext format
- `app.run()` starts the server

## Step 3: Add More Pages

Let's add the about and projects pages:

```python
@app.gemini("/about")
def about(request: Request):
    return """# About Me

I'm a Gemini enthusiast exploring the smolnet.

## Interests

* Programming
* Reading
* Photography

=> / Back to Home
"""

@app.gemini("/projects")
def projects(request: Request):
    return """# My Projects

Here are some things I've been working on:

=> /projects/alpha Project Alpha
=> /projects/beta Project Beta
=> /projects/gamma Project Gamma

=> / Back to Home
"""
```

## Step 4: Add Path Parameters

Notice how the projects page links to individual project pages. Let's create a handler that uses path parameters:

```python
# Sample project data
PROJECTS = {
    "alpha": {
        "name": "Project Alpha",
        "description": "A groundbreaking experiment",
        "status": "In Progress",
    },
    "beta": {
        "name": "Project Beta",
        "description": "Building something cool",
        "status": "Planning",
    },
    "gamma": {
        "name": "Project Gamma",
        "description": "Secret project",
        "status": "Completed",
    },
}

@app.gemini("/projects/{project_id}")
def project_detail(request: Request, project_id: str):
    project = PROJECTS.get(project_id)

    if not project:
        return """# Project Not Found

Sorry, that project doesn't exist.

=> /projects Back to Projects
"""

    return f"""# {project['name']}

{project['description']}

Status: {project['status']}

=> /projects Back to Projects
=> / Back to Home
"""
```

The `{project_id}` in the path becomes a parameter in your handler function. Xitzin automatically extracts it from the URL.

## Step 5: Add a Links Page

```python
@app.gemini("/links")
def links(request: Request):
    return """# Cool Links

Some interesting places in Geminispace:

=> gemini://geminiprotocol.net/ Gemini Protocol
=> gemini://geminispace.info/ Gemini Space

=> / Back to Home
"""
```

## Step 6: Generate Certificates

Before running, generate TLS certificates:

```bash
openssl req -x509 -newkey rsa:4096 \
    -keyout key.pem -out cert.pem \
    -days 365 -nodes \
    -subj "/CN=localhost"
```

## Step 7: Run Your Capsule

Start the server:

```bash
python capsule.py
```

Open your Gemini client and navigate to `gemini://localhost/`.

## Complete Code

Here's the complete `capsule.py`:

```python
from xitzin import Xitzin, Request

app = Xitzin(title="My Personal Capsule")

PROJECTS = {
    "alpha": {
        "name": "Project Alpha",
        "description": "A groundbreaking experiment",
        "status": "In Progress",
    },
    "beta": {
        "name": "Project Beta",
        "description": "Building something cool",
        "status": "Planning",
    },
    "gamma": {
        "name": "Project Gamma",
        "description": "Secret project",
        "status": "Completed",
    },
}

@app.gemini("/")
def home(request: Request):
    return """# Welcome to My Capsule

Hello, Geminispace! This is my personal corner of the smolnet.

## Navigation

=> /about About Me
=> /projects My Projects
=> /links Cool Links
"""

@app.gemini("/about")
def about(request: Request):
    return """# About Me

I'm a Gemini enthusiast exploring the smolnet.

## Interests

* Programming
* Reading
* Photography

=> / Back to Home
"""

@app.gemini("/projects")
def projects(request: Request):
    return """# My Projects

Here are some things I've been working on:

=> /projects/alpha Project Alpha
=> /projects/beta Project Beta
=> /projects/gamma Project Gamma

=> / Back to Home
"""

@app.gemini("/projects/{project_id}")
def project_detail(request: Request, project_id: str):
    project = PROJECTS.get(project_id)

    if not project:
        return """# Project Not Found

Sorry, that project doesn't exist.

=> /projects Back to Projects
"""

    return f"""# {project['name']}

{project['description']}

Status: {project['status']}

=> /projects Back to Projects
=> / Back to Home
"""

@app.gemini("/links")
def links(request: Request):
    return """# Cool Links

Some interesting places in Geminispace:

=> gemini://geminiprotocol.net/ Gemini Protocol
=> gemini://geminispace.info/ Gemini Space

=> / Back to Home
"""

if __name__ == "__main__":
    app.run()
```

## Next Steps

Congratulations! You've built your first Gemini capsule. Next, learn how to:

- [Handle user input](handling-user-input.md) for search and forms
- [Add authentication](user-authentication.md) for private content
- [Use templates](../how-to/templates.md) for cleaner code
