
import asyncio
from services.blueworker.core.bluesky_event_loop import configure_bluesky_event_loop
from services.blueworker.worker.worker import Worker


from bluesky.run_engine import get_bluesky_event_loop


def configure_bluesky_event_loop() -> None:
    """
    Make asyncio set the event loop of the calling thread to the bluesky event loop
    """

    loop = get_bluesky_event_loop()
    asyncio.set_event_loop(loop)

@handle_all_exceptions
def _run_worker_thread(worker: Worker[T]) -> None:
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
    worker = Worker()
    _run_worker_thread(worker)