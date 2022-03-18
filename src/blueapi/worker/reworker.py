import logging
from queue import Queue

from bluesky import RunEngine

from .task import Task, TaskContext
from .worker import Worker

LOGGER = logging.getLogger(__name__)


class RunEngineWorker(Worker[Task]):
    """
    Worker wrapping RunEngine that can work in its own thread/process

    :param run_engine: The RunEngine to wrap
    :param loop: The event loop of any services communicating with the worker.
    """

    _run_engine: RunEngine
    _task_queue: Queue  # type: ignore

    def __init__(
        self,
        run_engine: RunEngine,
    ) -> None:
        self._run_engine = run_engine
        self._task_queue = Queue()

    def submit_task(self, task: Task) -> None:
        LOGGER.info(f"Submitting: {task}")
        self._task_queue.put(task)

    def run_forever(self) -> None:
        while True:
            self._cycle()

    def _cycle(self) -> None:
        task: Task = self._task_queue.get()
        ctx = TaskContext(self._run_engine)
        task.do_task(ctx)
