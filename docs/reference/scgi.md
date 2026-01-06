# SCGI

SCGI (Simple Common Gateway Interface) support for proxying requests to persistent backend processes.

## Configuration

### SCGIConfig

Configuration options for SCGI backend communication.

::: xitzin.scgi.SCGIConfig

## Handlers

### SCGIHandler

Proxy requests to an SCGI backend via TCP socket.

::: xitzin.scgi.SCGIHandler

### SCGIApp

Proxy requests to an SCGI backend via Unix socket.

::: xitzin.scgi.SCGIApp

## Helper Functions

### encode_netstring

Encode data as a netstring for SCGI protocol.

::: xitzin.scgi.encode_netstring

### encode_scgi_headers

Encode CGI environment as SCGI headers.

::: xitzin.scgi.encode_scgi_headers
