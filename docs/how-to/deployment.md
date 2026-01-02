# Deployment

## Generate Production Certificates

For production, use properly signed certificates or self-signed with your domain:

```bash
# Self-signed certificate for your domain
openssl req -x509 -newkey rsa:4096 \
    -keyout key.pem -out cert.pem \
    -days 365 -nodes \
    -subj "/CN=your-domain.com"
```

For Let's Encrypt certificates, use the Gemini-specific ACME process or the standard HTTP challenge.

## Run with Custom Certificates

```python
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=1965,
        certfile="cert.pem",
        keyfile="key.pem"
    )
```

## Systemd Service

Create `/etc/systemd/system/my-capsule.service`:

```ini
[Unit]
Description=My Gemini Capsule
After=network.target

[Service]
Type=simple
User=gemini
Group=gemini
WorkingDirectory=/opt/my-capsule
ExecStart=/opt/my-capsule/.venv/bin/python app.py
Restart=always
RestartSec=5

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
ReadWritePaths=/opt/my-capsule/data

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable my-capsule
sudo systemctl start my-capsule
```

## Environment Variables

Use environment variables for configuration:

```python
import os

HOST = os.environ.get("GEMINI_HOST", "localhost")
PORT = int(os.environ.get("GEMINI_PORT", "1965"))
CERT_FILE = os.environ.get("GEMINI_CERT", "cert.pem")
KEY_FILE = os.environ.get("GEMINI_KEY", "key.pem")

if __name__ == "__main__":
    app.run(
        host=HOST,
        port=PORT,
        certfile=CERT_FILE,
        keyfile=KEY_FILE
    )
```

## Docker Deployment

Create a `Dockerfile`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy project files
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

COPY . .

# Expose Gemini port
EXPOSE 1965

CMD ["uv", "run", "python", "app.py"]
```

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  capsule:
    build: .
    ports:
      - "1965:1965"
    volumes:
      - ./certs:/app/certs:ro
      - ./data:/app/data
    environment:
      - GEMINI_HOST=0.0.0.0
      - GEMINI_CERT=/app/certs/cert.pem
      - GEMINI_KEY=/app/certs/key.pem
    restart: unless-stopped
```

## Production Checklist

- [ ] Use production certificates (not self-signed for public capsules)
- [ ] Configure proper file permissions for keys
- [ ] Set up log rotation
- [ ] Use a process manager (systemd, supervisor)
- [ ] Configure firewall (allow port 1965)
- [ ] Set up monitoring
- [ ] Use persistent storage for data
- [ ] Back up certificates and data

## Logging Configuration

Configure Python logging:

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/my-capsule/app.log'),
        logging.StreamHandler()
    ]
)

# Use with LoggingMiddleware
from xitzin.middleware import LoggingMiddleware

logger = logging.getLogger(__name__)
app.add_middleware(LoggingMiddleware(logger=logger.info))
```

## Health Checks

Add a health check endpoint:

```python
@app.gemini("/health")
def health(request: Request):
    return "OK"
```

Use with Docker:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "gemini://localhost:1965/health"]
  interval: 30s
  timeout: 10s
  retries: 3
```

## Reverse Proxy (Optional)

If you need to proxy Gemini traffic (rare), use a TLS-aware proxy. Most setups run Xitzin directly on port 1965.

## Monitoring with Middleware

Track requests for monitoring:

```python
import time
from collections import defaultdict

stats = defaultdict(int)

@app.middleware
async def track_stats(request: Request, call_next):
    stats['total_requests'] += 1
    stats[f'path:{request.path}'] += 1

    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start

    stats['total_time'] += elapsed
    return response

@app.gemini("/stats")
@require_fingerprint(*ADMIN_FINGERPRINTS)
def view_stats(request: Request):
    lines = ["# Statistics", ""]
    for key, value in sorted(stats.items()):
        lines.append(f"* {key}: {value}")
    return "\n".join(lines)
```
