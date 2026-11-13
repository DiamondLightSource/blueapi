from typing import Annotated

from bluesky._vendor.super_state_machine.errors import TransitionError
from fastapi import APIRouter, Depends, HTTPException, Request, status
from observability_utils.tracing import (
    add_span_attributes,
    start_as_current_span,
)

from blueapi.config import Tag
from blueapi.service import interface
from blueapi.service.authentication import Fedid
from blueapi.service.model import StateChangeRequest, WorkerTask
from blueapi.worker import WorkerState

from .dependencies import (
    TRACER,
    Opa,
    Runner,
    get_passthrough_headers,
    start_task_permission,
)

router = APIRouter(tags=[Tag.TASK])


@router.put("/worker/task", responses={status.HTTP_409_CONFLICT: {}})
@start_as_current_span(TRACER, "task.task_id")
def set_active_task(
    request: Request,
    task: WorkerTask,
    _: Annotated[None, Depends(start_task_permission)],
    runner: Runner,
) -> WorkerTask:
    """Set a task to active status, the worker should begin it as soon as possible.
    This will return an error response if the worker is not idle."""
    active_task = runner.run(interface.get_active_task)
    if active_task is not None and not active_task.is_complete:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Worker already active"
        )
    runner.run(
        interface.begin_task,
        task=task,
        pass_through_headers=get_passthrough_headers(request),
    )
    return task


@router.get("/worker/task")
@start_as_current_span(TRACER)
def get_active_task(runner: Runner) -> WorkerTask:
    active = runner.run(interface.get_active_task)
    task_id = active.task_id if active is not None else None
    return WorkerTask(task_id=task_id)


@router.get("/worker/state")
@start_as_current_span(TRACER)
def get_state(runner: Runner) -> WorkerState:
    """Get the State of the Worker"""
    return runner.run(interface.get_worker_state)


# Map of current_state: allowed new_states
_ALLOWED_TRANSITIONS: dict[WorkerState, set[WorkerState]] = {
    WorkerState.RUNNING: {
        WorkerState.PAUSED,
        WorkerState.ABORTING,
        WorkerState.STOPPING,
    },
    WorkerState.PAUSED: {
        WorkerState.RUNNING,
        WorkerState.ABORTING,
        WorkerState.STOPPING,
    },
}


@router.put(
    "/worker/state",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        status.HTTP_400_BAD_REQUEST: {},
        status.HTTP_202_ACCEPTED: {},
    },
)
@start_as_current_span(TRACER, "state_change_request.new_state")
async def set_state(
    state_change_request: StateChangeRequest,
    fedid: Fedid,
    opa: Opa,
    runner: Runner,
) -> WorkerState:
    """
    Request that the worker is put into a particular state.
    Returns the state of the worker at the end of the call.

    - **The following transitions are allowed and return 202: Accepted**
    - If the worker is **PAUSED**, new_state may be **RUNNING** to resume.
    - If the worker is **RUNNING**, new_state may be **PAUSED** to pause:
        - If defer is False (default): pauses and rewinds to the previous checkpoint
        - If defer is True: waits until the next checkpoint to pause
        - **If the task has no checkpoints, the task will instead be Aborted**
    - If the worker is **RUNNING/PAUSED**, new_state may be **STOPPING** to stop.
        Stop marks any currently open Runs in the Task as a success and ends the task.
    - If the worker is **RUNNING/PAUSED**, new_state may be **ABORTING** to abort.
        Abort marks any currently open Runs in the Task as a Failure and ends the task.
        - If reason is set, the reason will be passed as the reason for the Run failure.
    - **All other transitions return 400: Bad Request**
    """
    current_state = runner.run(interface.get_worker_state)
    new_state = state_change_request.new_state
    add_span_attributes({"current_state": current_state})
    if (
        current_state in _ALLOWED_TRANSITIONS
        and new_state in _ALLOWED_TRANSITIONS[current_state]
    ):
        active = runner.run(interface.get_active_task)

        if (
            opa
            and not await opa.admin()
            and active
            and active.task.metadata.get("user") != fedid
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to set worker state",
            )

        if new_state == WorkerState.PAUSED:
            runner.run(interface.pause_worker, state_change_request.defer)
        elif new_state == WorkerState.RUNNING:
            runner.run(interface.resume_worker)
        elif new_state in {WorkerState.ABORTING, WorkerState.STOPPING}:
            try:
                runner.run(
                    interface.cancel_active_task,
                    state_change_request.new_state is WorkerState.ABORTING,
                    state_change_request.reason,
                )
            except TransitionError as e:
                suffix = f" - {e}" if str(e) else ""
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Error while transitioning from {current_state} "
                        f"to {new_state}{suffix}"
                    ),
                ) from e
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(f"Cannot transition from {current_state} to {new_state}"),
        )
    return runner.run(interface.get_worker_state)
