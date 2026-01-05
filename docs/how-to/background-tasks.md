# Background Tasks

Run periodic tasks while your server is running using the `@app.task()` decorator.

## Interval-Based Tasks

Run a task at fixed intervals:

```python
from xitzin import Xitzin

app = Xitzin()

@app.task(interval=3600)  # Every hour (in seconds)
async def hourly_cleanup():
    await cleanup_old_sessions()

@app.task(interval="30m")  # Human-readable format
def check_feeds():
    update_rss_feeds()
```

Supported interval formats:

- Integer seconds: `interval=3600`
- Seconds: `interval="30s"`
- Minutes: `interval="5m"`
- Hours: `interval="1h"`
- Days: `interval="1d"`

## Cron-Based Tasks

For more complex schedules, use cron expressions:

```python
@app.task(cron="0 2 * * *")  # 2 AM daily
def nightly_backup():
    backup_database()

@app.task(cron="0 * * * *")  # Every hour at :00
async def hourly_stats():
    await update_statistics()

@app.task(cron="0 0 * * 0")  # Sunday at midnight
def weekly_report():
    generate_weekly_report()
```

!!! note "Cron support requires croniter"
    Install with: `pip install 'xitzin[tasks]'`

Common cron patterns:

| Pattern | Description |
|---------|-------------|
| `* * * * *` | Every minute |
| `0 * * * *` | Every hour |
| `0 0 * * *` | Daily at midnight |
| `0 0 * * 0` | Weekly (Sunday) |
| `0 0 1 * *` | Monthly (1st) |

## Async and Sync Handlers

Both async and sync handlers are supported:

```python
# Async handler - runs directly
@app.task(interval="1h")
async def async_task():
    await some_async_operation()

# Sync handler - wrapped in executor automatically
@app.task(interval="1h")
def sync_task():
    some_blocking_operation()
```

## Accessing Application State

Tasks can access `app.state` via closure:

```python
app = Xitzin()

@app.on_startup
async def setup_db():
    app.state.db = await create_db_connection()

@app.task(interval="1h")
async def cleanup():
    # Access app.state from the task
    await app.state.db.cleanup_old_records()
```

## Task Lifecycle

Tasks are automatically managed:

1. **Start**: Tasks begin after startup handlers complete
2. **Wait**: Tasks wait for the first interval/cron trigger before executing
3. **Execute**: Handler runs, errors are logged but don't stop the task
4. **Repeat**: Task continues on schedule
5. **Stop**: Tasks are cancelled before shutdown handlers run

```python
@app.on_startup
def startup():
    print("1. Startup handlers run")

@app.task(interval="1h")
def my_task():
    print("3. Task executes (after waiting 1 hour)")

@app.on_shutdown
def shutdown():
    print("4. Shutdown handlers run")

# Lifecycle:
# 1. Startup handlers run
# 2. Tasks start (but wait for first interval)
# 3. Server runs, tasks execute on schedule
# 4. Ctrl+C pressed
# 5. Tasks cancelled
# 6. Shutdown handlers run
```

## Error Handling

Task errors are logged but don't stop the task:

```python
@app.task(interval="5m")
def risky_task():
    # If this raises an exception:
    # - Error is logged with structlog
    # - Task continues running on schedule
    external_api_call()
```

Errors are logged with:

- Task name
- Error message
- Error type

## Multiple Tasks

Register multiple tasks with different schedules:

```python
@app.task(interval="1m")
async def quick_check():
    await check_health()

@app.task(interval="1h")
async def hourly_maintenance():
    await cleanup_cache()

@app.task(cron="0 3 * * *")
def daily_backup():
    backup_all_data()
```

## Configuration Validation

The `@app.task()` decorator validates configuration at decoration time:

```python
# Error: Neither interval nor cron provided
@app.task()  # Raises TaskConfigurationError
def my_task():
    pass

# Error: Both interval and cron provided
@app.task(interval="1h", cron="* * * * *")  # Raises TaskConfigurationError
def my_task():
    pass

# Error: Invalid interval format
@app.task(interval="invalid")  # Raises ValueError
def my_task():
    pass
```

## Best Practices

### Keep Tasks Fast

Long-running tasks block their own schedule:

```python
# Bad: Task takes 10 minutes, interval is 5 minutes
@app.task(interval="5m")
def slow_task():
    time.sleep(600)  # Blocks for 10 minutes!

# Good: Use shorter intervals or async operations
@app.task(interval="5m")
async def fast_task():
    await quick_check()  # Returns quickly
```

### Handle External Dependencies

Gracefully handle failures in external services:

```python
@app.task(interval="5m")
def check_external_api():
    try:
        response = requests.get("https://api.example.com/status")
        response.raise_for_status()
        process_response(response)
    except requests.RequestException as e:
        # Log but don't crash - task will retry next interval
        print(f"API check failed: {e}")
```

### Use Async for I/O Operations

Prefer async handlers for I/O-bound tasks:

```python
import aiohttp

@app.task(interval="1m")
async def fetch_updates():
    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.example.com/updates") as resp:
            data = await resp.json()
            await process_updates(data)
```

## Complete Example

```python
from xitzin import Xitzin

app = Xitzin(title="Task Demo")

# Application state
@app.on_startup
def setup():
    app.state.request_count = 0
    app.state.cache = {}

# Track requests
@app.gemini("/")
def home(request):
    app.state.request_count += 1
    return f"# Welcome\nTotal requests: {app.state.request_count}"

# Background tasks
@app.task(interval="1m")
def log_stats():
    print(f"Requests in last minute: {app.state.request_count}")

@app.task(interval="1h")
def cleanup_cache():
    old_keys = [k for k, v in app.state.cache.items() if v.is_expired()]
    for key in old_keys:
        del app.state.cache[key]
    print(f"Cleaned {len(old_keys)} cache entries")

@app.task(cron="0 0 * * *")  # Daily at midnight
def daily_report():
    print(f"Daily stats: {app.state.request_count} total requests")
    app.state.request_count = 0  # Reset counter

if __name__ == "__main__":
    app.run()
```
