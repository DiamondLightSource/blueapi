
import asyncio
from bluesky.run_engine import get_bluesky_event_loop

from services.bluecommon.thread_exception import handle_all_exceptions
from services.blueworker.core.task_worker import LOGGER, TaskWorker


def configure_bluesky_event_loop() -> None:
    """
    Make asyncio set the event loop of the calling thread to the bluesky event loop
    """

    loop = get_bluesky_event_loop()
    asyncio.set_event_loop(loop)

@handle_all_exceptions
def _run_worker_thread(worker: TaskWorker) -> None:
    """
    Helper function, run a worker forever, includes support for
    printing exceptions to stdout from a non-main thread.

    Args:
        worker (Worker[T]): The worker to run
    """

    LOGGER.info("Setting up event loop")
    configure_bluesky_event_loop()
    LOGGER.info("Worker starting")
    worker.run()

if __name__ == "__main__":
    worker = TaskWorker()
    _run_worker_thread(worker)