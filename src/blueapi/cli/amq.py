import threading
from typing import Any, Callable, Mapping, Optional, TypeVar

from blueapi.messaging import MessageContext, MessagingTemplate
from blueapi.service.model import (
    DeviceRequest,
    DeviceResponse,
    PlanRequest,
    PlanResponse,
    TaskResponse,
)
from blueapi.worker import TaskEvent, WorkerEvent, WorkerStatusEvent

T = TypeVar("T")


class BlueskyRemoteError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class AmqClient:
    app: MessagingTemplate

    def __init__(self, app: MessagingTemplate) -> None:
        self.app = app

    def run_plan(
        self,
        name: str,
        params: Mapping[str, Any],
        on_event: Optional[Callable[[WorkerEvent], None]] = None,
        timeout: Optional[float] = None,
    ) -> str:
        complete = threading.Event()

        def on_event_wrapper(ctx: MessageContext, event: WorkerEvent) -> None:
            if on_event is not None:
                on_event(event)

            if (isinstance(event, TaskEvent) and event.is_task_terminated()) or (
                isinstance(event, WorkerStatusEvent) and event.is_error()
            ):
                complete.set()
                if event.is_error():
                    raise BlueskyRemoteError(event.error_message or "Unknown error")

        self.app.subscribe(
            self.app.destinations.topic("public.worker.event"), on_event_wrapper
        )
        # self.app.send("worker.run", {"name": name, "params": params})
        task_response = self.app.send_and_recieve(
            "worker.run", {"name": name, "params": params}, reply_type=TaskResponse
        ).result(5.0)
        task_id = task_response.task_name

        if timeout is not None:
            complete.wait(timeout)

        return task_id

    def get_plans(self) -> PlanResponse:
        return self.app.send_and_recieve(
            "worker.plans", PlanRequest(), PlanResponse
        ).result(5.0)

    def get_devices(self) -> DeviceResponse:
        return self.app.send_and_recieve(
            "worker.devices", DeviceRequest(), DeviceResponse
        ).result(5.0)
