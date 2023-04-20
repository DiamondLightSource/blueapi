from importlib.metadata import version
from blueapi.core.context import BlueskyContext

from blueapi.worker.reworker import RunEngineWorker

__version__ = version("blueapi")
del version

context = BlueskyContext()
worker = RunEngineWorker(context)

__all__ = ["__version__", "context", "worker"]
