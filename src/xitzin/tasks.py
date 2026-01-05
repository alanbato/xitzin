"""Background task scheduling for Xitzin.

This module provides background task execution with interval-based
and cron-based scheduling.

Example:
    from xitzin import Xitzin

    app = Xitzin()

    @app.task(interval="1h")
    async def hourly_cleanup():
        await cleanup_old_records()

    @app.task(cron="0 2 * * *")  # 2 AM daily
    def daily_backup():
        backup_database()
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

import structlog

logger = structlog.get_logger("xitzin.tasks")


async def _execute_handler(handler: Callable[[], Any]) -> None:
    """Execute a task handler, wrapping sync handlers in executor.

    Args:
        handler: The handler function to execute.
    """
    if asyncio.iscoroutinefunction(handler):
        await handler()
    else:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, handler)


@dataclass
class BackgroundTask:
    """Configuration for a background task."""

    handler: Callable[[], Any]
    interval: float | None  # Seconds
    cron: str | None
    name: str


def parse_interval(interval: str | int | float) -> float:
    """Parse interval string or int to seconds.

    Args:
        interval: Either an integer/float (seconds) or string like "1h", "30m", "1d"

    Returns:
        Interval in seconds

    Raises:
        ValueError: If format is invalid
    """
    if isinstance(interval, (int, float)):
        if interval <= 0:
            raise ValueError("Interval must be positive")
        return float(interval)

    # Parse duration strings
    pattern = r"^(\d+)([smhd])$"
    match = re.match(pattern, interval.lower().strip())
    if not match:
        raise ValueError(
            f"Invalid interval format: {interval!r}. "
            "Use integer seconds or format like '1h', '30m', '1d'"
        )

    value, unit = match.groups()
    value = int(value)

    multipliers = {
        "s": 1,
        "m": 60,
        "h": 3600,
        "d": 86400,
    }

    return float(value * multipliers[unit])


async def run_interval_task(task: BackgroundTask) -> None:
    """Run a task on a fixed interval.

    Args:
        task: The task to run
    """
    task_logger = logger.bind(task=task.name)
    task_logger.info("task_started", interval=task.interval)

    while True:
        try:
            # Wait first (standard behavior)
            await asyncio.sleep(task.interval)  # type: ignore[arg-type]

            # Execute handler
            await _execute_handler(task.handler)
            task_logger.debug("task_executed")

        except asyncio.CancelledError:
            task_logger.info("task_cancelled")
            raise
        except Exception as e:
            task_logger.error(
                "task_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            # Continue running despite errors


async def run_cron_task(task: BackgroundTask) -> None:
    """Run a task on a cron schedule.

    Args:
        task: The task to run
    """
    from croniter import croniter

    task_logger = logger.bind(task=task.name)
    task_logger.info("task_started", cron=task.cron)

    try:
        cron_iter = croniter(task.cron, datetime.now(timezone.utc))
    except Exception as e:
        task_logger.error(
            "task_cron_invalid",
            cron=task.cron,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise

    while True:
        try:
            # Calculate next run time
            next_run = cron_iter.get_next(datetime)
            now = datetime.now(timezone.utc)

            # Handle timezone-naive datetime from croniter
            if next_run.tzinfo is None:
                next_run = next_run.replace(tzinfo=timezone.utc)

            sleep_seconds = (next_run - now).total_seconds()

            if sleep_seconds > 0:
                task_logger.debug("task_waiting", next_run=next_run.isoformat())
                await asyncio.sleep(sleep_seconds)

            # Execute handler
            await _execute_handler(task.handler)
            task_logger.debug("task_executed")

        except asyncio.CancelledError:
            task_logger.info("task_cancelled")
            raise
        except Exception as e:
            task_logger.error(
                "task_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            # Continue running despite errors
