import logging
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response, status
from observability_utils.tracing import start_as_current_span

from blueapi.config import Tag
from blueapi.service import interface
from blueapi.service.authentication import Fedid
from blueapi.service.authorization import submit_permission
from blueapi.service.model import TaskRequest, TaskResponse, TasksListResponse
from blueapi.worker import TrackableTask
from blueapi.worker.event import TaskStatusEnum
from blueapi.worker.task import TaskParameterError

from .dependencies import TRACER, Opa, Runner, access_task_permission

LOGGER = logging.getLogger(__name__)

router = APIRouter(tags=[Tag.TASK])

example_task_request = TaskRequest(
    name="count",
    params={"detectors": ["x"]},
    instrument_session="cm12345-1",
)


@router.post("/tasks", status_code=status.HTTP_201_CREATED)
@start_as_current_span(
    TRACER,
    "request",
    "task_request.name",
    "task_request.params",
    "task_request.instrument_session",
)
def submit_task(
    request: Request,
    response: Response,
    task_request: Annotated[TaskRequest, Body(..., examples=[example_task_request])],
    _: Annotated[None, Depends(submit_permission)],
    runner: Runner,
    fedid: Fedid,
) -> TaskResponse:
    """Submit a task to the worker."""
    try:
        task_id: str = runner.run(interface.submit_task, task_request, {"user": fedid})
        response.headers["Location"] = f"{request.url}/{task_id}"
        return TaskResponse(task_id=task_id)
    except TaskParameterError as e:
        # Add body/params context to location and ensure that all required
        # fields defined in the generated schema are present
        errors = [
            {
                "loc": ["body", "params", *err.get("loc", [])],
                "msg": err.get("msg", None),
                "type": err.get("type", None),
                # Input is not listed as required but is useful to have if available
                "input": err.get("input", None),
            }
            for err in e.errors
        ]
        LOGGER.info("Error submitting task: %s - %s", task_request, e)
    except Exception as e:
        # Catch all for anything else that can go wrong
        errors = [
            {"loc": ["body", "params"], "msg": str(e), "type": "invalid", "input": None}
        ]
        LOGGER.info("Error submitting task: %s - %s", task_request, e)
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=errors,
    )


@router.delete("/tasks/{task_id}", status_code=status.HTTP_200_OK)
@start_as_current_span(TRACER, "task_id")
def delete_submitted_task(
    task_id: str,
    _: Annotated[None, Depends(access_task_permission)],
    runner: Runner,
) -> TaskResponse:
    return TaskResponse(task_id=runner.run(interface.clear_task, task_id))


@router.get("/tasks", status_code=status.HTTP_200_OK)
@start_as_current_span(TRACER)
async def get_tasks(
    fedid: Fedid,
    runner: Runner,
    opa: Opa,
    task_status: TaskStatusEnum | None = None,
) -> TasksListResponse:
    """
    Retrieve tasks based on their status.
    The status of a newly created task is PENDING.
    """
    tasks = runner.run(interface.get_tasks, task_status)

    if opa and not await opa.admin():
        tasks = [t for t in tasks if t.task.metadata.get("user") == fedid]

    return TasksListResponse(tasks=tasks)


@router.get("/tasks/{task_id}")
@start_as_current_span(TRACER, "task_id")
def get_task(
    task_id: str,
    _: Annotated[None, Depends(access_task_permission)],
    runner: Runner,
) -> TrackableTask:
    """Retrieve a task"""
    task = runner.run(interface.get_task_by_id, task_id)
    if task is None:
        raise KeyError
    return task
