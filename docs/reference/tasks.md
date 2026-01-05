# Tasks

Background task scheduling for running periodic operations.

## Overview

The tasks module provides background task execution with interval-based and cron-based scheduling. Tasks run while the server is running and are automatically started after startup handlers and stopped before shutdown handlers.

## Task Decorator

Register tasks using the `@app.task()` decorator on your Xitzin application:

```python
from xitzin import Xitzin

app = Xitzin()

@app.task(interval="1h")
async def hourly_cleanup():
    await cleanup_old_records()

@app.task(cron="0 2 * * *")
def daily_backup():
    backup_database()
```

See the [Application reference](application.md) for the `Xitzin.task()` decorator API.

## BackgroundTask

Data class representing a registered background task.

::: xitzin.tasks.BackgroundTask

## Helper Functions

### parse_interval

::: xitzin.tasks.parse_interval

### run_interval_task

::: xitzin.tasks.run_interval_task

### run_cron_task

::: xitzin.tasks.run_cron_task

## Exceptions

### TaskConfigurationError

::: xitzin.exceptions.TaskConfigurationError

## Installation

Cron-based tasks require the `croniter` package:

```bash
pip install 'xitzin[tasks]'
```

Interval-based tasks work without any additional dependencies.
