from contextlib import asynccontextmanager
from typing import Dict, Set

from fastapi import Body, Depends, FastAPI, HTTPException, Request, Response, status
from pydantic import ValidationError
from starlette.responses import JSONResponse
from super_state_machine.errors import TransitionError

from blueapi.config import ApplicationConfig
from blueapi.worker import RunPlan, TrackableTask, WorkerState

from .controller import (
    BlueskyController,
    get_controller,
    initialize_controller,
    teardown_controller,
)
from .model import (
    DeviceModel,
    DeviceResponse,
    PlanModel,
    PlanResponse,
    StateChangeRequest,
    TaskResponse,
    WorkerTask,
)

REST_API_VERSION = "0.0.3"


@asynccontextmanager
async def lifespan(app: FastAPI):
    config: ApplicationConfig = app.state.config
    initialize_controller(config)
    yield
    teardown_controller()


app = FastAPI(
    docs_url="/docs",
    on_shutdown=[teardown_controller],
    title="BlueAPI Control",
    lifespan=lifespan,
    version=REST_API_VERSION,
)


@app.exception_handler(KeyError)
async def on_key_error_404(_: Request, __: KeyError):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": "Item not found"},
    )


@app.get("/plans", response_model=PlanResponse)
def get_plans(controller: BlueskyController = Depends(get_controller)):
    """Retrieve information about all available plans."""
    return PlanResponse(
        plans=[PlanModel.from_plan(plan) for plan in controller.context.plans.values()]
    )


@app.get(
    "/plans/{name}",
    response_model=PlanModel,
)
def get_plan_by_name(
    name: str, controller: BlueskyController = Depends(get_controller)
):
    """Retrieve information about a plan by its (unique) name."""
    return PlanModel.from_plan(controller.context.plans[name])


@app.get("/devices", response_model=DeviceResponse)
def get_devices(controller: BlueskyController = Depends(get_controller)):
    """Retrieve information about all available devices."""
    return DeviceResponse(
        devices=[
            DeviceModel.from_device(device)
            for device in controller.context.devices.values()
        ]
    )


@app.get(
    "/devices/{name}",
    response_model=DeviceModel,
)
def get_device_by_name(
    name: str, controller: BlueskyController = Depends(get_controller)
):
    """Retrieve information about a devices by its (unique) name."""
    return DeviceModel.from_device(controller.context.devices[name])


@app.post(
    "/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_task(
    request: Request,
    response: Response,
    task: RunPlan = Body(
        ..., example=RunPlan(name="count", params={"detectors": ["x"]})
    ),
    controller: BlueskyController = Depends(get_controller),
):
    """Submit a task to the worker."""
    try:
        task_id: str = controller.worker.submit_task(task)
        response.headers["Location"] = f"{request.url}/{task_id}"
        return TaskResponse(task_id=task_id)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.errors()
        )


@app.delete("/tasks/{task_id}", status_code=status.HTTP_200_OK)
def delete_submitted_task(
    task_id: str,
    controller: BlueskyController = Depends(get_controller),
) -> TaskResponse:
    return TaskResponse(task_id=controller.worker.clear_task(task_id))


@app.put(
    "/worker/task",
    response_model=WorkerTask,
    responses={status.HTTP_409_CONFLICT: {"worker": "already active"}},
)
def update_task(
    task: WorkerTask,
    controller: BlueskyController = Depends(get_controller),
) -> WorkerTask:
    active_task = controller.worker.get_active_task()
    if active_task is not None and not active_task.is_complete:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Worker already active"
        )
    elif task.task_id is not None:
        controller.worker.begin_task(task.task_id)
    return task


@app.get(
    "/tasks/{task_id}",
    response_model=TrackableTask,
)
def get_task(
    task_id: str,
    controller: BlueskyController = Depends(get_controller),
) -> TrackableTask:
    """Retrieve a task"""

    task = controller.worker.get_pending_task(task_id)
    if task is None:
        raise KeyError
    return task


@app.get("/worker/task")
def get_active_task(
    controller: BlueskyController = Depends(get_controller),
) -> WorkerTask:
    return WorkerTask.of_worker(controller.worker)


@app.get("/worker/state")
def get_state(controller: BlueskyController = Depends(get_controller)) -> WorkerState:
    """Get the State of the Worker"""
    return controller.worker.state


# Map of current_state: allowed new_states
_ALLOWED_TRANSITIONS: Dict[WorkerState, Set[WorkerState]] = {
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


@app.put(
    "/worker/state",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        status.HTTP_400_BAD_REQUEST: {"detail": "Transition not allowed"},
        status.HTTP_202_ACCEPTED: {"detail": "Transition requested"},
    },
)
def set_state(
    state_change_request: StateChangeRequest,
    response: Response,
    controller: BlueskyController = Depends(get_controller),
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
    current_state = controller.worker.state
    new_state = state_change_request.new_state
    if (
        current_state in _ALLOWED_TRANSITIONS
        and new_state in _ALLOWED_TRANSITIONS[current_state]
    ):
        if new_state == WorkerState.PAUSED:
            controller.worker.pause(defer=state_change_request.defer)
        elif new_state == WorkerState.RUNNING:
            controller.worker.resume()
        elif new_state in {WorkerState.ABORTING, WorkerState.STOPPING}:
            try:
                controller.worker.cancel_active_task(
                    state_change_request.new_state is WorkerState.ABORTING,
                    state_change_request.reason,
                )
            except TransitionError:
                response.status_code = status.HTTP_400_BAD_REQUEST
    else:
        response.status_code = status.HTTP_400_BAD_REQUEST

    return controller.worker.state


def start(config: ApplicationConfig):
    import uvicorn

    app.state.config = config
    uvicorn.run(app, host=config.api.host, port=config.api.port)


@app.middleware("http")
async def add_api_version_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-API-Version"] = REST_API_VERSION
    return response
