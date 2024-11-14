from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    FastAPI,
    HTTPException,
    Request,
    Response,
    status,
)
from observability_utils.tracing import (
    add_span_attributes,
    get_tracer,
    start_as_current_span,
)
from opentelemetry.context import attach
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.propagate import get_global_textmap
from opentelemetry.trace import get_tracer_provider
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

CONTEXT_HEADER = "traceparent"


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


router = APIRouter()


def get_app():
    app = FastAPI(
        docs_url="/docs",
        title="BlueAPI Control",
        lifespan=lifespan,
        version=REST_API_VERSION,
    )
    app.include_router(router)
    app.add_exception_handler(KeyError, on_key_error_404)
    app.middleware("http")(add_api_version_header)
    app.middleware("http")(inject_propagated_observability_context)
    return app


TRACER = get_tracer("interface")


async def on_key_error_404(_: Request, __: KeyError):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": "Item not found"},
    )


@router.get("/environment", response_model=EnvironmentResponse)
@start_as_current_span(TRACER, "runner")
def get_environment(
    runner: WorkerDispatcher = Depends(_runner),
) -> EnvironmentResponse:
    """Get the current state of the environment, i.e. initialization state."""
    return runner.state


@router.delete("/environment", response_model=EnvironmentResponse)
async def delete_environment(
    background_tasks: BackgroundTasks,
    runner: WorkerDispatcher = Depends(_runner),
) -> EnvironmentResponse:
    """Delete the current environment, causing internal components to be reloaded."""

    if runner.state.initialized or runner.state.error_message is not None:
        background_tasks.add_task(runner.reload)
    return EnvironmentResponse(initialized=False)


@router.get("/plans", response_model=PlanResponse)
@start_as_current_span(TRACER)
def get_plans(runner: WorkerDispatcher = Depends(_runner)):
    """Retrieve information about all available plans."""
    plans = runner.run(interface.get_plans)
    return PlanResponse(plans=plans)


@router.get(
    "/plans/{name}",
    response_model=PlanModel,
)
@start_as_current_span(TRACER, "name")
def get_plan_by_name(name: str, runner: WorkerDispatcher = Depends(_runner)):
    """Retrieve information about a plan by its (unique) name."""
    return runner.run(interface.get_plan, name)


@router.get("/devices", response_model=DeviceResponse)
@start_as_current_span(TRACER)
def get_devices(runner: WorkerDispatcher = Depends(_runner)):
    """Retrieve information about all available devices."""
    devices = runner.run(interface.get_devices)
    return DeviceResponse(devices=devices)


@router.get(
    "/devices/{name}",
    response_model=DeviceModel,
)
@start_as_current_span(TRACER, "name")
def get_device_by_name(name: str, runner: WorkerDispatcher = Depends(_runner)):
    """Retrieve information about a devices by its (unique) name."""
    return runner.run(interface.get_device, name)


example_task = Task(name="count", params={"detectors": ["x"]})


@router.post(
    "/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
@start_as_current_span(TRACER, "request", "task.name", "task.params")
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


@router.delete("/tasks/{task_id}", status_code=status.HTTP_200_OK)
@start_as_current_span(TRACER, "task_id")
def delete_submitted_task(
    task_id: str,
    runner: WorkerDispatcher = Depends(_runner),
) -> TaskResponse:
    return TaskResponse(task_id=runner.run(interface.clear_task, task_id))


@start_as_current_span(TRACER, "v")
def validate_task_status(v: str) -> TaskStatusEnum:
    v_upper = v.upper()
    if v_upper not in TaskStatusEnum.__members__:
        raise ValueError("Invalid status query parameter")
    return TaskStatusEnum(v_upper)


@router.get("/tasks", response_model=TasksListResponse, status_code=status.HTTP_200_OK)
@start_as_current_span(TRACER)
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
        add_span_attributes({"status": task_status})
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


@router.put(
    "/worker/task",
    response_model=WorkerTask,
    responses={status.HTTP_409_CONFLICT: {"worker": "already active"}},
)
@start_as_current_span(TRACER, "task.task_id")
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


@router.get(
    "/tasks/{task_id}",
    response_model=TrackableTask,
)
@start_as_current_span(TRACER, "task_id")
def get_task(
    task_id: str,
    runner: WorkerDispatcher = Depends(_runner),
) -> TrackableTask:
    """Retrieve a task"""
    task = runner.run(interface.get_task_by_id, task_id)
    if task is None:
        raise KeyError
    return task


@router.get("/worker/task")
@start_as_current_span(TRACER)
def get_active_task(runner: WorkerDispatcher = Depends(_runner)) -> WorkerTask:
    active = runner.run(interface.get_active_task)
    task_id = active.task_id if active is not None else None
    return WorkerTask(task_id=task_id)


@router.get("/worker/state")
@start_as_current_span(TRACER)
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


@router.put(
    "/worker/state",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        status.HTTP_400_BAD_REQUEST: {"detail": "Transition not allowed"},
        status.HTTP_202_ACCEPTED: {"detail": "Transition requested"},
    },
)
@start_as_current_span(TRACER, "state_change_request.new_state")
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
    add_span_attributes({"current_state": current_state})
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


@start_as_current_span(TRACER, "config")
def start(config: ApplicationConfig):
    import uvicorn
    from uvicorn.config import LOGGING_CONFIG

    LOGGING_CONFIG["formatters"]["default"]["fmt"] = (
        "%(asctime)s %(levelprefix)s %(message)s"
    )
    LOGGING_CONFIG["formatters"]["access"]["fmt"] = (
        "%(asctime)s %(levelprefix)s %(client_addr)s"
        + " - '%(request_line)s' %(status_code)s"
    )
    app = get_app()

    FastAPIInstrumentor().instrument_app(
        app,
        tracer_provider=get_tracer_provider(),
        http_capture_headers_server_request=[",*"],
        http_capture_headers_server_response=[",*"],
    )
    app.state.config = config

    uvicorn.run(app, host=config.api.host, port=config.api.port)


async def add_api_version_header(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
):
    response = await call_next(request)
    response.headers["X-API-Version"] = REST_API_VERSION
    return response


async def inject_propagated_observability_context(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Middleware to extract the any propagated observability context from the
    HTTP headers and attach it to the local one.
    """
    if CONTEXT_HEADER in request.headers:
        ctx = get_global_textmap().extract(
            {CONTEXT_HEADER: request.headers[CONTEXT_HEADER]}
        )
        attach(ctx)
    response = await call_next(request)
    return response
