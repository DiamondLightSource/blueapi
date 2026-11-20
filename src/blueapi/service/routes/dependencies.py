from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.requests import HTTPConnection
from observability_utils.tracing import get_tracer

from blueapi.config import ApplicationConfig
from blueapi.service import interface
from blueapi.service.authentication import Fedid
from blueapi.service.authorization import OpaUserClient, opa
from blueapi.service.model import WorkerTask
from blueapi.service.runner import WorkerDispatcher

TRACER = get_tracer("interface")

RUNNER: WorkerDispatcher | None = None


def _runner() -> WorkerDispatcher:
    """Intended to be used only with FastAPI Depends"""
    if RUNNER is None:
        raise ValueError()
    return RUNNER


Runner = Annotated[WorkerDispatcher, Depends(_runner)]
Opa = Annotated[OpaUserClient | None, Depends(opa)]


def setup_runner(
    config: ApplicationConfig | None = None,
    runner: WorkerDispatcher | None = None,
):
    global RUNNER
    runner = runner or WorkerDispatcher(config)
    runner.start()

    RUNNER = runner


def teardown_runner():
    global RUNNER
    if RUNNER is None:
        return
    RUNNER.stop()
    RUNNER = None


async def access_task_permission(
    opa: Opa,
    task_id: str,
    fedid: Fedid,
    runner: Runner,
):
    task = runner.run(interface.get_task_by_id, task_id)

    if (
        opa
        and not await opa.admin()
        and (task and fedid != task.task.metadata.get("user"))
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


# start_task_permission is used when there is WorkerTask
async def start_task_permission(
    task: WorkerTask,
    opa: Opa,
    fedid: Fedid,
    runner: Runner,
):
    if not task.task_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="No task id provided",
        )
    await access_task_permission(opa, task.task_id, fedid, runner)


def get_passthrough_headers(request: HTTPConnection) -> dict[str, str]:
    return {
        key: value
        for key, value in request.headers.items()
        if key.casefold() in ApplicationConfig.PROPAGATED_HEADERS
    }
