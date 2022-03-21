import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, TypeVar

from blueapi.utils import handle_all_exceptions

from .worker import Worker

LOGGER = logging.getLogger(__name__)

T = TypeVar("T")


def run_worker_in_own_thread(
    worker: Worker[T], executor: Optional[ThreadPoolExecutor] = None
) -> None:
    """
    Helper function, make a worker run in a new thread managed by a ThreadPoolExecutor

    :param worker: The worker to run
    :param executor: The executor to manage the thread, defaults to None in which
                     case a new one is created
    """

    if executor is None:
        executor = ThreadPoolExecutor(1, "run-engine-worker")
    executor.submit(_run_worker_thread, worker)


@handle_all_exceptions
def _run_worker_thread(worker: Worker[T]) -> None:
    """
    Helper function, run a worker forever, includes support for
    printing exceptions to stdout from a non-main thread.

    :param worker: The worker to run
    """

    LOGGER.info("Worker starting")
    worker.run_forever()
