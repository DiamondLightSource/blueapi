from pathlib import Path
from typing import Mapping, Optional
from fastapi import FastAPI
from blueapi.core.context import BlueskyContext
from blueapi.core.event import EventStream
from blueapi.messaging.stomptemplate import StompMessagingTemplate, MessagingTemplate
from blueapi.utils.config import ConfigLoader
from blueapi.worker import run_worker_in_own_thread
from blueapi.worker.reworker import RunEngineWorker
from blueapi.config import ApplicationConfig
from blueapi.worker.worker import Worker
import logging

app = ()


class RestApi:
    _config: ApplicationConfig
    _message_bus: MessagingTemplate
    _ctx: BlueskyContext
    _worker: Worker
    _app: FastAPI

    def __init__(self, config: ApplicationConfig) -> None:
        self._config = config
        self._ctx = BlueskyContext()
        self._ctx.with_startup_script(self._config.env.startup_script)
        self._worker = RunEngineWorker(self._ctx)
        self._worker_future = run_worker_in_own_thread(self._worker)
        self._message_bus = StompMessagingTemplate.autoconfigured(config.stomp)

    def run(self) -> None:
        logging.basicConfig(level=self._config.logging.level)

        self._worker.data_events.subscribe(
            lambda event, corr_id: self._message_bus.send(
                "public.worker.event.data", event, None, corr_id
            )
        )
        self._worker.progress_events.subscribe(
            lambda event, corr_id: self._message_bus.send(
                "public.worker.event.progress", event, None, corr_id
            )
        )

        self._message_bus.connect()
        self._app = FastAPI()

        self._worker.run_forever()


def start(config_path: Optional[Path] = None):
    loader = ConfigLoader(ApplicationConfig)
    if config_path is not None:
        loader.use_yaml_or_json_file(config_path)
    config = loader.load()

    RestApi(config).run()
