import asyncio
import unittest

from blueapi.utils.ophyd_async_connect import _format_awaited_task_error_message
from blueapi.worker.task import Task

_SIMPLE_TASK = Task(name="sleep", params={"time": 0.0})
_LONG_TASK = Task(name="sleep", params={"time": 1.0})


class TestFormatErrorMessage(unittest.TestCase):
    def setUp(self):
        # Setup the asyncio event loop for each test
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        # Close the loop at the end of each test
        self.loop.close()

    async def _create_task_with_exception(self, exception):
        """Helper coroutine to create a task that raises an exception."""

        async def raise_exception():
            raise exception

        task = self.loop.create_task(raise_exception())
        await asyncio.sleep(0.1)  # Allow time for the task to raise the exception
        return task

    def test_format_error_message_single_line(self):
        # Test formatting with an exception that has a single-line message
        exception = ValueError("A single-line error")
        task = self.loop.run_until_complete(self._create_task_with_exception(exception))
        tasks = {task: "Task1"}
        expected_output = "\n  Task1: ValueError: A single-line error"
        self.assertEqual(
            _format_awaited_task_error_message(tasks, task), expected_output
        )

    def test_format_error_message_multi_line(self):
        # Test formatting with an exception that has a multi-line message
        exception = ValueError("A multi-line\nerror message")
        task = self.loop.run_until_complete(self._create_task_with_exception(exception))
        tasks = {task: "Task2"}
        expected_output = "\n  Task2: ValueError\n    A multi-line\n    error message"
        self.assertEqual(
            _format_awaited_task_error_message(tasks, task), expected_output
        )

    def test_format_error_message_simple_task_failure(self):
        # Test formatting with the _SIMPLE_TASK key and a failing asyncio task
        exception = RuntimeError("Simple task error")
        failing_task = self.loop.run_until_complete(
            self._create_task_with_exception(exception)
        )
        tasks = {failing_task: _SIMPLE_TASK.name}
        expected_output = "\n  sleep: RuntimeError: Simple task error"
        self.assertEqual(
            _format_awaited_task_error_message(tasks, failing_task), expected_output
        )

    def test_format_error_message_long_task_failure(self):
        # Test formatting with the _LONG_TASK key and a failing asyncio task
        exception = RuntimeError("Long task error")
        failing_task = self.loop.run_until_complete(
            self._create_task_with_exception(exception)
        )
        tasks = {failing_task: _LONG_TASK.name}
        expected_output = "\n  sleep: RuntimeError: Long task error"
        self.assertEqual(
            _format_awaited_task_error_message(tasks, failing_task), expected_output
        )


if __name__ == "__main__":
    unittest.main()
