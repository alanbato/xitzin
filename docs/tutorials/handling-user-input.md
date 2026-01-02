# Handling User Input

Gemini handles user input differently from HTTP. Instead of form fields, Gemini uses a simple prompt-response mechanism. In this tutorial, you'll learn how it works and build a search feature.

## What You'll Learn

- How Gemini's input mechanism works (status 10/11)
- Using the `@app.input()` decorator
- Accessing query strings in handlers
- Handling sensitive input (passwords)

## How Gemini Input Works

In HTTP, you might have a form with multiple fields. Gemini is simpler:

1. The server sends a status 10 (or 11 for sensitive data) with a prompt
2. The client shows an input field to the user
3. The user types their response
4. The client sends a new request with the input as a query string

This single-input mechanism is elegant but requires a different approach to collecting data.

## Step 1: Create a Search Feature

Let's build a simple search feature. Create `search_app.py`:

```python
from xitzin import Xitzin, Request

app = Xitzin(title="Search Demo")

# Sample data to search
ARTICLES = [
    {"title": "Getting Started with Gemini", "content": "Learn the basics..."},
    {"title": "Python Tips and Tricks", "content": "Useful Python patterns..."},
    {"title": "Building a Capsule", "content": "Step by step guide..."},
    {"title": "Gemtext Formatting", "content": "How to format content..."},
    {"title": "Certificate Authentication", "content": "Secure your capsule..."},
]

@app.gemini("/")
def home(request: Request):
    return """# Search Demo

=> /search Search Articles
=> /articles Browse All Articles
"""

@app.input("/search", prompt="Enter your search query:")
def search(request: Request, query: str):
    results = [
        article for article in ARTICLES
        if query.lower() in article["title"].lower()
        or query.lower() in article["content"].lower()
    ]

    if not results:
        return f"""# No Results

No articles found for "{query}".

=> /search Try Another Search
=> / Back to Home
"""

    lines = [f"# Search Results for '{query}'", ""]
    for article in results:
        lines.append(f"* {article['title']}")
    lines.append("")
    lines.append("=> /search Search Again")
    lines.append("=> / Back to Home")

    return "\n".join(lines)

if __name__ == "__main__":
    app.run()
```

## Understanding @app.input()

The `@app.input()` decorator does two things:

1. **First request (no query)**: Returns status 10 with your prompt
2. **Second request (with query)**: Calls your handler with the `query` parameter

```python
@app.input("/search", prompt="Enter your search query:")
def search(request: Request, query: str):
    # This only runs when the user has submitted input
    return f"You searched for: {query}"
```

The flow looks like this:

```
User visits /search
    ↓
Server returns: 10 Enter your search query:
    ↓
Client shows input field
    ↓
User types "python" and submits
    ↓
Client requests /search?python
    ↓
Handler receives query="python"
```

## Step 2: Add Sensitive Input

For passwords or other sensitive data, use `sensitive=True`:

```python
@app.input("/login", prompt="Enter your password:", sensitive=True)
def login(request: Request, query: str):
    # In a real app, you'd verify the password
    if query == "secret123":
        return """# Welcome!

You've successfully logged in.

=> / Home
"""
    return """# Access Denied

Incorrect password.

=> /login Try Again
"""
```

The `sensitive=True` flag tells the client to:

- Hide the input as the user types (like a password field)
- Not store the input in history

## Step 3: Chaining Inputs

Sometimes you need multiple pieces of information. Since Gemini only allows one input at a time, you need to chain them:

```python
# Store temporary data (in a real app, use a proper session store)
pending_registrations = {}

@app.input("/register", prompt="Enter your username:")
def register_username(request: Request, query: str):
    # Store username and redirect to get email
    cert_fp = request.client_cert_fingerprint
    if cert_fp:
        pending_registrations[cert_fp] = {"username": query}
        return """# Username Saved

Now let's get your email.

=> /register/email Continue
"""
    return """# Certificate Required

Please enable client certificates to register.

=> / Home
"""

@app.input("/register/email", prompt="Enter your email:")
def register_email(request: Request, query: str):
    cert_fp = request.client_cert_fingerprint
    if cert_fp and cert_fp in pending_registrations:
        pending_registrations[cert_fp]["email"] = query
        user = pending_registrations.pop(cert_fp)
        return f"""# Registration Complete!

Welcome, {user['username']}!
Your email: {user['email']}

=> / Home
"""
    return """# Session Expired

Please start over.

=> /register Register
"""
```

## Step 4: Manual Input Handling

You can also handle input manually using the `Request.query` property:

```python
from xitzin import Input

@app.gemini("/manual-search")
def manual_search(request: Request):
    if not request.query:
        # No input yet, prompt for it
        return Input(prompt="What are you looking for?")

    # Input received
    query = request.query
    return f"You searched for: {query}"
```

This gives you more control but requires more code.

## Step 5: Complete Example

Here's a complete app with search and filtered browsing:

```python
from xitzin import Xitzin, Request

app = Xitzin(title="Article Search")

ARTICLES = [
    {"id": 1, "title": "Getting Started with Gemini", "category": "tutorial"},
    {"id": 2, "title": "Python Tips and Tricks", "category": "python"},
    {"id": 3, "title": "Building a Capsule", "category": "tutorial"},
    {"id": 4, "title": "Gemtext Formatting", "category": "reference"},
    {"id": 5, "title": "Certificate Authentication", "category": "security"},
    {"id": 6, "title": "Advanced Python Patterns", "category": "python"},
]

@app.gemini("/")
def home(request: Request):
    return """# Article Search

=> /search Search Articles
=> /browse Browse by Category
=> /articles All Articles
"""

@app.input("/search", prompt="Search articles:")
def search(request: Request, query: str):
    results = [a for a in ARTICLES if query.lower() in a["title"].lower()]

    lines = [f"# Results for '{query}'", ""]
    if results:
        for article in results:
            lines.append(f"=> /article/{article['id']} {article['title']}")
    else:
        lines.append("No articles found.")
    lines.extend(["", "=> /search Search Again", "=> / Home"])

    return "\n".join(lines)

@app.gemini("/browse")
def browse(request: Request):
    categories = sorted(set(a["category"] for a in ARTICLES))

    lines = ["# Browse by Category", ""]
    for cat in categories:
        lines.append(f"=> /category/{cat} {cat.title()}")
    lines.extend(["", "=> / Home"])

    return "\n".join(lines)

@app.gemini("/category/{category}")
def category(request: Request, category: str):
    articles = [a for a in ARTICLES if a["category"] == category]

    lines = [f"# {category.title()} Articles", ""]
    for article in articles:
        lines.append(f"=> /article/{article['id']} {article['title']}")
    lines.extend(["", "=> /browse Back to Categories", "=> / Home"])

    return "\n".join(lines)

@app.gemini("/article/{article_id}")
def article(request: Request, article_id: int):
    article = next((a for a in ARTICLES if a["id"] == article_id), None)

    if not article:
        return "# Article Not Found\n\n=> / Home"

    return f"""# {article['title']}

Category: {article['category']}

[Article content would go here...]

=> /category/{article['category']} More {article['category'].title()} Articles
=> / Home
"""

@app.gemini("/articles")
def all_articles(request: Request):
    lines = ["# All Articles", ""]
    for article in ARTICLES:
        lines.append(f"=> /article/{article['id']} {article['title']}")
    lines.extend(["", "=> / Home"])

    return "\n".join(lines)

if __name__ == "__main__":
    app.run()
```

## Key Takeaways

1. **Use `@app.input()`** for simple prompt-response flows
2. **The `query` parameter** receives the user's input
3. **Use `sensitive=True`** for passwords and private data
4. **Chain inputs** by redirecting between routes
5. **Access `request.query`** for manual handling

## Next Steps

- Learn about [user authentication](user-authentication.md) with certificates
- See the [Input Handling how-to](../how-to/input-handling.md) for more patterns
