# Gemini Protocol

A guide to the Gemini protocol for developers familiar with HTTP.

## What is Gemini?

Gemini is a lightweight internet protocol that sits between Gopher and the Web. It was designed to be:

- **Simpler than HTTP**: No headers, cookies, or complex negotiation
- **More capable than Gopher**: Supports TLS and richer content
- **Privacy-focused**: No tracking mechanisms by design
- **Content-focused**: Documents over applications

## The Request Format

A Gemini request is just a URL followed by CRLF:

```
gemini://example.com/path/to/page\r\n
```

That's it. No headers, no body, no cookies. The entire request must be under 1024 bytes.

Compare to HTTP:

```http
GET /path/to/page HTTP/1.1
Host: example.com
User-Agent: ...
Accept: ...
Cookie: ...
[many more headers]
```

## The Response Format

A Gemini response has a single header line:

```
<STATUS><SPACE><META>\r\n
<BODY>
```

- **STATUS**: Two-digit status code
- **META**: Status-dependent metadata (MIME type, prompt, URL, or error message)
- **BODY**: Content (only for success responses)

## Status Codes

Gemini uses two-digit status codes grouped by first digit:

### 1x: Input

```
10 <prompt>   # Request input
11 <prompt>   # Request sensitive input (hidden)
```

The client shows an input field and re-requests with the user's input as a query string.

### 2x: Success

```
20 <mime-type>   # Success with content
```

The body follows the header. Default MIME type is `text/gemini`.

### 3x: Redirect

```
30 <url>   # Temporary redirect
31 <url>   # Permanent redirect
```

No body. Client follows the redirect.

### 4x: Temporary Failure

```
40 <message>   # Temporary failure
41 <message>   # Server unavailable
42 <message>   # CGI error
43 <message>   # Proxy error
44 <seconds>   # Slow down (rate limiting)
```

### 5x: Permanent Failure

```
50 <message>   # Permanent failure
51 <message>   # Not found
52 <message>   # Gone
53 <message>   # Proxy refused
59 <message>   # Bad request
```

### 6x: Client Certificate

```
60 <message>   # Certificate required
61 <message>   # Certificate not authorized
62 <message>   # Certificate not valid
```

## TLS and Certificates

All Gemini connections use TLS. There's no unencrypted option.

### Server Certificates

Gemini is more lenient than HTTPS:

- Self-signed certificates are common and accepted
- TOFU (Trust On First Use) is the recommended trust model
- No centralized certificate authorities required

### Client Certificates

Client certificates replace cookies and sessions:

- Users generate their own certificates
- Certificates provide persistent identity
- The server identifies users by certificate fingerprint
- No password needed—the private key proves identity

## The Input Mechanism

Since there's no request body, Gemini handles user input via status codes:

1. Server returns status 10 with a prompt
2. Client shows input field to user
3. User types response
4. Client re-requests with input as query string

```
Request:  gemini://example.com/search
Response: 10 Enter search query:\r\n

[User types "gemini protocol"]

Request:  gemini://example.com/search?gemini%20protocol
Response: 20 text/gemini\r\n
          # Results for "gemini protocol"
          ...
```

## Limitations

Gemini intentionally limits what's possible:

| HTTP Feature | Gemini Equivalent |
|--------------|-------------------|
| Multiple form fields | Chained inputs |
| Cookies | Client certificates |
| JavaScript | Not possible |
| CSS | Not possible |
| POST/PUT/DELETE | Not possible |
| Custom headers | Not possible |
| Streaming | Not possible |

These aren't bugs—they're features that keep Gemini simple and private.

## Why Use Gemini?

- **Focus on content**: No ads, tracking, or distractions
- **Privacy by design**: No cookies or fingerprinting
- **Low barrier**: Easy to self-host
- **Accessible**: Works well with screen readers
- **Sustainable**: Low bandwidth and energy use

## Further Reading

- [Gemini Protocol Specification](gemini://geminiprotocol.net/docs/specification.gmi)
- [Gemini FAQ](gemini://geminiprotocol.net/docs/faq.gmi)
- [Project Gemini](gemini://geminiprotocol.net/)
