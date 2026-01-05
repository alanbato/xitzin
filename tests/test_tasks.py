"""Tests for xitzin.tasks module."""

import asyncio

import pytest

from xitzin import Xitzin
from xitzin.exceptions import TaskConfigurationError
from xitzin.tasks import BackgroundTask, parse_interval


class TestParseInterval:
    """Tests for parse_interval function."""

    def test_parse_int_seconds(self):
        """Integer values are returned as float seconds."""
        assert parse_interval(60) == 60.0
        assert parse_interval(3600) == 3600.0
        assert parse_interval(1) == 1.0

    def test_parse_seconds_string(self):
        """Seconds string format is parsed correctly."""
        assert parse_interval("30s") == 30.0
        assert parse_interval("1s") == 1.0

    def test_parse_minutes_string(self):
        """Minutes string format is parsed correctly."""
        assert parse_interval("1m") == 60.0
        assert parse_interval("30m") == 1800.0

    def test_parse_hours_string(self):
        """Hours string format is parsed correctly."""
        assert parse_interval("1h") == 3600.0
        assert parse_interval("2h") == 7200.0

    def test_parse_days_string(self):
        """Days string format is parsed correctly."""
        assert parse_interval("1d") == 86400.0
        assert parse_interval("7d") == 604800.0

    def test_case_insensitive(self):
        """Parsing is case-insensitive."""
        assert parse_interval("1H") == 3600.0
        assert parse_interval("1M") == 60.0
        assert parse_interval("1D") == 86400.0

    def test_strips_whitespace(self):
        """Leading/trailing whitespace is stripped."""
        assert parse_interval("  1h  ") == 3600.0
        assert parse_interval(" 30m ") == 1800.0

    def test_invalid_format_raises(self):
        """Invalid format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid interval format"):
            parse_interval("invalid")

        with pytest.raises(ValueError, match="Invalid interval format"):
            parse_interval("1x")

        with pytest.raises(ValueError, match="Invalid interval format"):
            parse_interval("h1")

    def test_zero_raises(self):
        """Zero interval raises ValueError."""
        with pytest.raises(ValueError, match="must be positive"):
            parse_interval(0)

    def test_negative_raises(self):
        """Negative interval raises ValueError."""
        with pytest.raises(ValueError, match="must be positive"):
            parse_interval(-1)


class TestBackgroundTask:
    """Tests for BackgroundTask dataclass."""

    def test_create_interval_task(self):
        """Can create task with interval."""

        def my_handler():
            pass

        task = BackgroundTask(
            handler=my_handler,
            interval=3600.0,
            cron=None,
            name="my_task",
        )
        assert task.handler is my_handler
        assert task.interval == 3600.0
        assert task.cron is None
        assert task.name == "my_task"

    def test_create_cron_task(self):
        """Can create task with cron expression."""

        def my_handler():
            pass

        task = BackgroundTask(
            handler=my_handler,
            interval=None,
            cron="0 * * * *",
            name="cron_task",
        )
        assert task.interval is None
        assert task.cron == "0 * * * *"


class TestTaskDecorator:
    """Tests for @app.task() decorator."""

    def test_registers_interval_task(self):
        """task() with interval registers task."""
        app = Xitzin()

        @app.task(interval=3600)
        def my_task():
            pass

        assert len(app._tasks) == 1
        task = app._tasks[0]
        assert task.name == "my_task"
        assert task.interval == 3600.0
        assert task.cron is None

    def test_registers_interval_string_task(self):
        """task() with interval string registers task."""
        app = Xitzin()

        @app.task(interval="1h")
        def my_task():
            pass

        assert len(app._tasks) == 1
        task = app._tasks[0]
        assert task.interval == 3600.0

    def test_handler_is_returned(self):
        """task() returns the original handler."""
        app = Xitzin()

        def original_handler():
            return "original"

        decorated = app.task(interval=60)(original_handler)
        assert decorated is original_handler
        assert decorated() == "original"

    def test_multiple_tasks(self):
        """Multiple tasks can be registered."""
        app = Xitzin()

        @app.task(interval=60)
        def task1():
            pass

        @app.task(interval=120)
        def task2():
            pass

        assert len(app._tasks) == 2
        assert app._tasks[0].name == "task1"
        assert app._tasks[1].name == "task2"

    def test_async_handler_supported(self):
        """Async handlers are supported."""
        app = Xitzin()

        @app.task(interval=60)
        async def async_task():
            await asyncio.sleep(0)

        assert len(app._tasks) == 1
        assert asyncio.iscoroutinefunction(app._tasks[0].handler)

    def test_no_params_raises(self):
        """task() without interval or cron raises."""
        app = Xitzin()

        with pytest.raises(
            TaskConfigurationError, match="Either 'interval' or 'cron' must be provided"
        ):

            @app.task()
            def my_task():
                pass

    def test_both_params_raises(self):
        """task() with both interval and cron raises."""
        app = Xitzin()

        with pytest.raises(
            TaskConfigurationError,
            match="Only one of 'interval' or 'cron' can be provided",
        ):

            @app.task(interval=60, cron="* * * * *")
            def my_task():
                pass


class TestTaskDecoratorCron:
    """Tests for @app.task(cron=...) decorator."""

    def test_cron_task_requires_croniter(self):
        """Cron task without croniter raises helpful error."""
        # Note: This test will pass if croniter IS installed,
        # so we need to check both cases
        app = Xitzin()

        try:
            import croniter  # noqa: F401

            # If croniter is available, the decorator should work
            @app.task(cron="0 * * * *")
            def my_task():
                pass

            assert len(app._tasks) == 1
            assert app._tasks[0].cron == "0 * * * *"

        except ImportError:
            # If croniter is not available, should raise helpful error
            with pytest.raises(
                TaskConfigurationError,
                match="croniter is required for cron tasks",
            ):

                @app.task(cron="0 * * * *")
                def my_task():
                    pass


class TestIntervalTaskExecution:
    """Tests for interval task execution."""

    @pytest.mark.asyncio
    async def test_interval_task_executes(self):
        """Interval task executes handler after interval."""
        from xitzin.tasks import BackgroundTask, run_interval_task

        call_count = 0

        async def handler():
            nonlocal call_count
            call_count += 1

        task = BackgroundTask(
            handler=handler,
            interval=0.05,  # 50ms for testing
            cron=None,
            name="test_task",
        )

        # Start task
        asyncio_task = asyncio.create_task(run_interval_task(task))

        # Wait for a couple of executions
        await asyncio.sleep(0.15)

        # Cancel task
        asyncio_task.cancel()
        try:
            await asyncio_task
        except asyncio.CancelledError:
            pass

        # Should have executed at least once (waited 50ms, ran once, waited, ran again)
        assert call_count >= 1

    @pytest.mark.asyncio
    async def test_interval_task_handles_sync_handler(self):
        """Interval task wraps sync handler in executor."""
        from xitzin.tasks import BackgroundTask, run_interval_task

        call_count = 0

        def sync_handler():
            nonlocal call_count
            call_count += 1

        task = BackgroundTask(
            handler=sync_handler,
            interval=0.05,
            cron=None,
            name="sync_task",
        )

        asyncio_task = asyncio.create_task(run_interval_task(task))
        await asyncio.sleep(0.12)

        asyncio_task.cancel()
        try:
            await asyncio_task
        except asyncio.CancelledError:
            pass

        assert call_count >= 1

    @pytest.mark.asyncio
    async def test_interval_task_continues_after_error(self):
        """Interval task continues running after handler error."""
        from xitzin.tasks import BackgroundTask, run_interval_task

        call_count = 0

        def failing_handler():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("Test error")

        task = BackgroundTask(
            handler=failing_handler,
            interval=0.03,
            cron=None,
            name="failing_task",
        )

        asyncio_task = asyncio.create_task(run_interval_task(task))
        await asyncio.sleep(0.12)

        asyncio_task.cancel()
        try:
            await asyncio_task
        except asyncio.CancelledError:
            pass

        # Should have continued after first error
        assert call_count >= 2


class TestTaskLifecycle:
    """Tests for task lifecycle integration."""

    def test_tasks_start_empty(self):
        """App starts with no tasks."""
        app = Xitzin()
        assert len(app._tasks) == 0
        assert len(app._task_handles) == 0

    @pytest.mark.asyncio
    async def test_run_tasks_creates_handles(self):
        """_run_tasks creates asyncio task handles."""
        app = Xitzin()

        @app.task(interval=3600)
        def my_task():
            pass

        # Start tasks
        await app._run_tasks()

        assert len(app._task_handles) == 1
        assert isinstance(app._task_handles[0], asyncio.Task)

        # Clean up
        await app._stop_tasks()

    @pytest.mark.asyncio
    async def test_stop_tasks_cancels_handles(self):
        """_stop_tasks cancels all task handles."""
        app = Xitzin()

        @app.task(interval=3600)
        def my_task():
            pass

        await app._run_tasks()
        assert len(app._task_handles) == 1

        await app._stop_tasks()
        assert len(app._task_handles) == 0

    @pytest.mark.asyncio
    async def test_stop_tasks_waits_for_cancellation(self):
        """_stop_tasks waits for tasks to be cancelled."""
        app = Xitzin()
        started = False
        cancelled = False

        @app.task(interval=0.01)  # Very short interval so we can test cancellation
        async def my_task():
            nonlocal started, cancelled
            started = True
            try:
                await asyncio.sleep(3600)  # Long sleep to wait for cancellation
            except asyncio.CancelledError:
                cancelled = True
                raise

        await app._run_tasks()
        # Wait for task to start (after first interval elapses)
        await asyncio.sleep(0.05)
        await app._stop_tasks()

        # Task should have started and then been cancelled
        assert started
        assert cancelled


class TestTaskConfigurationError:
    """Tests for TaskConfigurationError exception."""

    def test_exception_is_exported(self):
        """TaskConfigurationError is exported from xitzin package."""
        from xitzin import TaskConfigurationError

        assert issubclass(TaskConfigurationError, Exception)

    def test_exception_message(self):
        """TaskConfigurationError has correct message."""
        error = TaskConfigurationError("Test message")
        assert str(error) == "Test message"
