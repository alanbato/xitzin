# Templates

## Setup Templates Directory

Configure the templates directory when creating your app:

```python
from pathlib import Path

app = Xitzin(
    templates_dir=Path(__file__).parent / "templates"
)
```

## Create a Template

Create a `.gmi` file in your templates directory:

```jinja
{# templates/page.gmi #}
# {{ title }}

{{ description }}

{% for item in items %}
* {{ item }}
{% endfor %}

=> / Home
```

## Render a Template

Use `app.template()` in your handler:

```python
@app.gemini("/page")
def page(request: Request):
    return app.template(
        "page.gmi",
        title="My Page",
        description="Welcome to my page!",
        items=["Item 1", "Item 2", "Item 3"]
    )
```

## Gemtext Filters

Xitzin provides filters for generating Gemtext:

### link - Generate Links

```jinja
{{ "/about" | link("About Us") }}
{# Output: => /about About Us #}

{{ "/home" | link }}
{# Output: => /home #}
```

### reverse - URL Reversing

The `reverse()` function builds URLs from route names:

```jinja
{# Link to a named route #}
{{ reverse("user_profile", username="alice") | link("Alice's Profile") }}
{# Output: => /user/alice Alice's Profile #}

{# Multiple parameters #}
{{ reverse("blog_post", year=2024, month=12, slug="hello") }}
{# Output: /post/2024/12/hello #}
```

This keeps your templates maintainable - if a route path changes, only the route definition needs updating.

### heading - Generate Headings

```jinja
{{ "Main Title" | heading(1) }}
{# Output: # Main Title #}

{{ "Section" | heading(2) }}
{# Output: ## Section #}

{{ "Subsection" | heading(3) }}
{# Output: ### Subsection #}
```

### list - Generate Lists

```jinja
{{ items | list }}
{# Given items = ["Apple", "Banana", "Cherry"]
   Output:
   * Apple
   * Banana
   * Cherry
#}
```

### quote - Generate Quotes

```jinja
{{ "This is quoted text" | quote }}
{# Output: > This is quoted text #}

{{ multiline_text | quote }}
{# Handles newlines, prefixing each line with > #}
```

### preformat - Code Blocks

```jinja
{{ code | preformat }}
{# Output:
```
code here
```
#}

{{ python_code | preformat("python") }}
{# Output:
```python
python code here
```
#}
```

## Template Inheritance

Create a base template:

```jinja
{# templates/base.gmi #}
# {{ title }}

{% block content %}{% endblock %}

---
{{ "/" | link("Home") }}
```

Extend it in other templates:

```jinja
{# templates/about.gmi #}
{% extends "base.gmi" %}

{% block content %}
Welcome to the about page!

This is my personal capsule.
{% endblock %}
```

## Conditional Content

```jinja
{% if user %}
Welcome back, {{ user.name }}!
{% else %}
{{ "/login" | link("Sign In") }}
{% endif %}
```

## Loops

```jinja
## Articles

{% for article in articles %}
{{ article.url | link(article.title) }}
{% endfor %}

{% if not articles %}
No articles yet.
{% endif %}
```

## Template with Request Context

Pass request data to templates:

```python
@app.gemini("/profile")
@optional_certificate
def profile(request: Request):
    identity = request.state.identity

    return app.template(
        "profile.gmi",
        identity=identity,
        is_authenticated=identity is not None
    )
```

## Inline Templates

For simple cases, use `render_string`:

```python
from xitzin.templating import TemplateEngine

engine = TemplateEngine(Path("templates"))
content = engine.render_string(
    "# {{ title }}\n\n{{ items | list }}",
    title="Quick Page",
    items=["A", "B", "C"]
)
```

## Dynamic Navigation with reverse()

Build navigation menus that don't break when URLs change:

```jinja
{# templates/base.gmi #}
# {{ title }}

{% block content %}{% endblock %}

---
## Navigation
{{ reverse("home") | link("Home") }}
{{ reverse("about") | link("About") }}
{% if user %}
{{ reverse("user_profile", username=user.username) | link("My Profile") }}
{{ reverse("logout") | link("Logout") }}
{% else %}
{{ reverse("login") | link("Login") }}
{% endif %}
```

## Best Practices

1. **Use templates for complex pages** - Keep handlers clean
2. **Use filters for Gemtext** - They handle formatting correctly
3. **Create a base template** - For consistent navigation
4. **Pass minimal context** - Only what the template needs
5. **Use reverse() for links** - Avoid hardcoded URLs
