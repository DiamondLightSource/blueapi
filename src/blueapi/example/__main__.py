import logging

from .app import app

logging.basicConfig(level=logging.DEBUG)
LOGGER = logging.getLogger()


if __name__ == "__main__":
    LOGGER.info("Running example")
    app.run()
