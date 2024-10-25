from contextlib import asynccontextmanager

from fastapi import (
    BackgroundTasks,
    Body,
    Depends,
    FastAPI,
    HTTPException,
    Request,
    Response,
    status,
)
from pydantic import ValidationError
from starlette.responses import JSONResponse
from super_state_machine.errors import TransitionError

from blueapi.config import ApplicationConfig
from blueapi.service import interface
from blueapi.worker import Task, TrackableTask, WorkerState
from blueapi.worker.event import TaskStatusEnum

from .model import (
    DeviceModel,
    DeviceResponse,
    EnvironmentResponse,
    PlanModel,
    PlanResponse,
    StateChangeRequest,
    TaskResponse,
    TasksListResponse,
    WorkerTask,
)
from .runner import WorkerDispatcher

REST_API_VERSION = "0.0.5"

RUNNER: WorkerDispatcher | None = None


def _runner() -> WorkerDispatcher:
    """Intended to be used only with FastAPI Depends"""
    if RUNNER is None:
        raise ValueError()
    return RUNNER


def setup_runner(config: ApplicationConfig | None = None, use_subprocess: bool = True):
    global RUNNER
    runner = WorkerDispatcher(config, use_subprocess)
    runner.start()

    RUNNER = runner


def teardown_runner():
    global RUNNER
    if RUNNER is None:
        return
    RUNNER.stop()
    RUNNER = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    config: ApplicationConfig = app.state.config
    setup_runner(config)
    yield
    teardown_runner()


app = FastAPI(
    docs_url="/docs",
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


@app.get("/environment", response_model=EnvironmentResponse)
def get_environment(
    runner: WorkerDispatcher = Depends(_runner),
) -> EnvironmentResponse:
    """Get the current state of the environment, i.e. initialization state."""
    return runner.state


@app.delete("/environment", response_model=EnvironmentResponse)
async def delete_environment(
    background_tasks: BackgroundTasks,
    runner: WorkerDispatcher = Depends(_runner),
) -> EnvironmentResponse:
    """Delete the current environment, causing internal components to be reloaded."""

    if runner.state.initialized or runner.state.error_message is not None:
        background_tasks.add_task(runner.reload)
    return EnvironmentResponse(initialized=False)


@app.get("/plans", response_model=PlanResponse)
def get_plans(runner: WorkerDispatcher = Depends(_runner)):
    """Retrieve information about all available plans."""
    return PlanResponse(plans=runner.run(interface.get_plans))


@app.get(
    "/plans/{name}",
    response_model=PlanModel,
)
def get_plan_by_name(name: str, runner: WorkerDispatcher = Depends(_runner)):
    """Retrieve information about a plan by its (unique) name."""
    return runner.run(interface.get_plan, name)


@app.get("/devices", response_model=DeviceResponse)
def get_devices(runner: WorkerDispatcher = Depends(_runner)):
    """Retrieve information about all available devices."""
    return DeviceResponse(devices=runner.run(interface.get_devices))


@app.get(
    "/devices/{name}",
    response_model=DeviceModel,
)
def get_device_by_name(name: str, runner: WorkerDispatcher = Depends(_runner)):
    """Retrieve information about a devices by its (unique) name."""
    return runner.run(interface.get_device, name)


example_task = Task(name="count", params={"detectors": ["x"]})


@app.post(
    "/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_task(
    request: Request,
    response: Response,
    task: Task = Body(..., example=example_task),
    runner: WorkerDispatcher = Depends(_runner),
):
    """Submit a task to the worker."""
    try:
        plan_model = runner.run(interface.get_plan, task.name)
        task_id: str = runner.run(interface.submit_task, task)
        response.headers["Location"] = f"{request.url}/{task_id}"
        return TaskResponse(task_id=task_id)
    except ValidationError as e:
        errors = e.errors()
        formatted_errors = "; ".join(
            [f"{err['loc'][0]}: {err['msg']}" for err in errors]
        )
        error_detail_response = f"""
        Input validation failed: {formatted_errors},
        suppplied params {task.params},
        do not match the expected params: {plan_model.parameter_schema}
        """
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=error_detail_response,
        ) from e


@app.delete("/tasks/{task_id}", status_code=status.HTTP_200_OK)
def delete_submitted_task(
    task_id: str,
    runner: WorkerDispatcher = Depends(_runner),
) -> TaskResponse:
    return TaskResponse(task_id=runner.run(interface.clear_task, task_id))


def validate_task_status(v: str) -> TaskStatusEnum:
    v_upper = v.upper()
    if v_upper not in TaskStatusEnum.__members__:
        raise ValueError("Invalid status query parameter")
    return TaskStatusEnum(v_upper)


@app.get("/tasks", response_model=TasksListResponse, status_code=status.HTTP_200_OK)
def get_tasks(
    task_status: str | None = None,
    runner: WorkerDispatcher = Depends(_runner),
) -> TasksListResponse:
    """
    Retrieve tasks based on their status.
    The status of a newly created task is 'unstarted'.
    """
    tasks = []
    if task_status:
        try:
            desired_status = validate_task_status(task_status)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid status query parameter",
            ) from e

        tasks = runner.run(interface.get_tasks_by_status, desired_status)
    else:
        tasks = runner.run(interface.get_tasks)
    return TasksListResponse(tasks=tasks)


@app.put(
    "/worker/task",
    response_model=WorkerTask,
    responses={status.HTTP_409_CONFLICT: {"worker": "already active"}},
)
def set_active_task(
    task: WorkerTask,
    runner: WorkerDispatcher = Depends(_runner),
) -> WorkerTask:
    """Set a task to active status, the worker should begin it as soon as possible.
    This will return an error response if the worker is not idle."""
    active_task = runner.run(interface.get_active_task)
    if active_task is not None and not active_task.is_complete:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Worker already active"
        )
    runner.run(interface.begin_task, task)
    return task


@app.get(
    "/tasks/{task_id}",
    response_model=TrackableTask,
)
def get_task(
    task_id: str,
    runner: WorkerDispatcher = Depends(_runner),
) -> TrackableTask:
    """Retrieve a task"""
    task = runner.run(interface.get_task_by_id, task_id)
    if task is None:
        raise KeyError
    return task


@app.get("/worker/task")
def get_active_task(runner: WorkerDispatcher = Depends(_runner)) -> WorkerTask:
    active = runner.run(interface.get_active_task)
    if active is not None:
        return WorkerTask(task_id=active.task_id)
    else:
        return WorkerTask(task_id=None)


@app.get("/worker/state")
def get_state(runner: WorkerDispatcher = Depends(_runner)) -> WorkerState:
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
    runner: WorkerDispatcher = Depends(_runner),
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
    if (
        current_state in _ALLOWED_TRANSITIONS
        and new_state in _ALLOWED_TRANSITIONS[current_state]
    ):
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
            except TransitionError:
                response.status_code = status.HTTP_400_BAD_REQUEST
    else:
        response.status_code = status.HTTP_400_BAD_REQUEST

    return runner.run(interface.get_worker_state)


def start(config: ApplicationConfig):
    import uvicorn

    app.state.config = config
    uvicorn.run(app, host=config.api.host, port=config.api.port)


@app.middleware("http")
async def add_api_version_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-API-Version"] = REST_API_VERSION
    return response
