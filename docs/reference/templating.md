# Templating

Jinja2-based template engine for Gemtext output.

## TemplateEngine

High-level template rendering interface.

::: xitzin.templating.TemplateEngine

## TemplateResponse

Response wrapper for rendered templates.

::: xitzin.templating.TemplateResponse

## Gemtext Filters

The template engine includes these filters for generating Gemtext:

### link

Generate a Gemtext link line.

```jinja
{{ "/about" | link("About Us") }}
{# Output: => /about About Us #}

{{ "/home" | link }}
{# Output: => /home #}
```

### heading

Generate a Gemtext heading (levels 1-3).

```jinja
{{ "Title" | heading(1) }}
{# Output: # Title #}

{{ "Section" | heading(2) }}
{# Output: ## Section #}

{{ "Subsection" | heading(3) }}
{# Output: ### Subsection #}
```

### list

Generate a Gemtext list from an iterable.

```jinja
{{ ["Apple", "Banana", "Cherry"] | list }}
{# Output:
* Apple
* Banana
* Cherry
#}
```

### quote

Generate a Gemtext blockquote.

```jinja
{{ "Hello world" | quote }}
{# Output: > Hello world #}
```

### preformat

Generate a preformatted code block.

```jinja
{{ code | preformat }}
{# Output:
```
code
```
#}

{{ python_code | preformat("python") }}
{# Output:
```python
python_code
```
#}
```
