# Gemtext Format

Understanding the Gemtext markup format used by Gemini.

## What is Gemtext?

Gemtext is the native markup format for Gemini content, similar to how HTML is for the web. It's intentionally simple:

- Line-oriented (each line is a complete element)
- No inline formatting
- No nested structures
- Human-readable source

## Line Types

### Text Lines

Any line not starting with a special character is a text paragraph:

```
This is a paragraph of text.

This is another paragraph.
```

Blank lines separate paragraphs.

### Headings

Three levels, using `#`:

```
# Heading Level 1
## Heading Level 2
### Heading Level 3
```

### Links

Links start with `=>`:

```
=> gemini://example.com/ Link to example
=> /about About this site
=> /file.txt
```

Format: `=> {url} [optional link text]`

Without text, the URL itself is displayed.

### Lists

Unordered lists use `*`:

```
* First item
* Second item
* Third item
```

There are no ordered lists or nested lists.

### Quotes

Blockquotes use `>`:

```
> This is a quote.
> It can span multiple lines.
```

### Preformatted Text

Toggle preformatted mode with triple backticks:

```
​```
This is preformatted text.
  Whitespace is preserved.
    Code goes here.
​```
```

Optional alt text after opening backticks:

```
​```python
def hello():
    print("Hello, World!")
​```
```

## No Inline Formatting

Unlike Markdown, Gemtext has **no inline formatting**:

- No **bold** or *italic*
- No `inline code`
- No inline links (like Markdown's `[text](url)` syntax)

This is intentional—it keeps parsing simple and ensures consistent rendering.

## Template Filters for Gemtext

Xitzin provides filters to generate Gemtext correctly:

### link

```jinja
{{ "/about" | link("About Us") }}
{# Output: => /about About Us #}
```

### heading

```jinja
{{ "Welcome" | heading(1) }}
{# Output: # Welcome #}
```

### list

```jinja
{{ ["Apple", "Banana"] | list }}
{# Output:
* Apple
* Banana
#}
```

### quote

```jinja
{{ "Wise words" | quote }}
{# Output: > Wise words #}
```

### preformat

```jinja
{{ code | preformat("python") }}
{# Output:
```python
code
```
#}
```

## Writing Good Gemtext

### Keep It Simple

```gemtext
# My Page

Welcome to my page. This is a simple introduction.

## Links

=> /about About me
=> /projects My projects

## Lists

Things I like:

* Reading
* Programming
* Coffee
```

### Use Links for Navigation

Unlike HTML, links are always block-level:

```gemtext
# Articles

Here are my recent articles:

=> /articles/one First Article
=> /articles/two Second Article
=> /articles/three Third Article
```

### Preformatted for Code

```gemtext
Here's how to install:

​```bash
pip install xitzin
​```

Then create your app:

​```python
from xitzin import Xitzin

app = Xitzin()
​```
```

### Quotes for Citations

```gemtext
As the documentation says:

> Gemini is designed to be simple and private.

This is the core philosophy.
```

## Common Patterns

### Page with Navigation

```gemtext
# Page Title

Content here.

---

=> / Home
=> /about About
=> /contact Contact
```

### Article List

```gemtext
# Recent Articles

=> /article/3 [2024-01-15] Latest thoughts
=> /article/2 [2024-01-10] Project update
=> /article/1 [2024-01-05] Getting started
```

### Search Results

```gemtext
# Results for "python"

Found 3 results:

=> /article/1 Python Tips and Tricks
=> /article/5 Learning Python
=> /article/8 Python Best Practices

=> /search Search again
```

## Accessibility

Gemtext is inherently accessible:

- Simple structure works well with screen readers
- No complex styling to navigate
- Links are clearly marked
- Content is the focus

## MIME Type

Gemtext uses the MIME type `text/gemini`:

```
20 text/gemini
# Hello, World!
```

You can also serve other formats:

```python
@app.gemini("/data.json")
def json_data(request: Request):
    return Response('{"key": "value"}', mime_type="application/json")
```

## Further Reading

- [Gemtext Specification](gemini://geminiprotocol.net/docs/gemtext.gmi)
- [Gemini Best Practices](gemini://geminiprotocol.net/docs/best-practices.gmi)
