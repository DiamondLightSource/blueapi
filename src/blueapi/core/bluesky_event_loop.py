import asyncio

from bluesky.run_engine import get_bluesky_event_loop


def configure_bluesky_event_loop() -> None:
    """
    Make asyncio set the event loop of the calling thread to the bluesky event loop
    """

    loop = get_bluesky_event_loop()
    asyncio.set_event_loop(loop)
