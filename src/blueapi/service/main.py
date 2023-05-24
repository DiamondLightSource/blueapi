from contextlib import asynccontextmanager

from fastapi import Body, Depends, FastAPI, HTTPException, Request, Response

from blueapi.config import ApplicationConfig
from blueapi.worker import RunPlan, TrackableTask, WorkerState

from .handler import Handler, get_handler, setup_handler, teardown_handler
from .model import (
    DeviceModel,
    DeviceResponse,
    PlanModel,
    PlanResponse,
    TaskResponse,
    WorkerTask,
)

REST_API_VERSION = "0.0.2"


@asynccontextmanager
async def lifespan(app: FastAPI):
    config: ApplicationConfig = app.state.config
    setup_handler(config)
    yield
    teardown_handler()


app = FastAPI(
    docs_url="/docs",
    on_shutdown=[teardown_handler],
    title="BlueAPI Control",
    lifespan=lifespan,
    version=REST_API_VERSION,
)


@app.get("/plans", response_model=PlanResponse)
def get_plans(handler: Handler = Depends(get_handler)):
    """Retrieve information about all available plans."""
    return PlanResponse(
        plans=[PlanModel.from_plan(plan) for plan in handler.context.plans.values()]
    )


@app.get("/plans/{name}", response_model=PlanModel)
def get_plan_by_name(name: str, handler: Handler = Depends(get_handler)):
    """Retrieve information about a plan by its (unique) name."""
    try:
        return PlanModel.from_plan(handler.context.plans[name])
    except KeyError:
        raise HTTPException(status_code=404, detail="Item not found")


@app.get("/devices", response_model=DeviceResponse)
def get_devices(handler: Handler = Depends(get_handler)):
    """Retrieve information about all available devices."""
    return DeviceResponse(
        devices=[
            DeviceModel.from_device(device)
            for device in handler.context.devices.values()
        ]
    )


@app.get("/devices/{name}", response_model=DeviceModel)
def get_device_by_name(name: str, handler: Handler = Depends(get_handler)):
    """Retrieve information about a devices by its (unique) name."""
    try:
        return DeviceModel.from_device(handler.context.devices[name])
    except KeyError:
        raise HTTPException(status_code=404, detail="Item not found")


@app.post("/tasks", response_model=TaskResponse, status_code=201)
def submit_task(
    request: Request,
    response: Response,
    task: RunPlan = Body(
        ..., example=RunPlan(name="count", params={"detectors": ["x"]})
    ),
    handler: Handler = Depends(get_handler),
):
    """Submit a task to the worker."""
    task_id: str = handler.worker.submit_task(task)
    response.headers["Location"] = f"{request.url}/{task_id}"
    return TaskResponse(task_id=task_id)


@app.put("/worker/task", response_model=WorkerTask)
def update_task(
    task: WorkerTask,
    handler: Handler = Depends(get_handler),
) -> WorkerTask:
    if task.task_id is not None:
        handler.worker.begin_task(task.task_id)
    return task


@app.get("/tasks/{task_id}", response_model=TrackableTask)
def get_task(
    task_id: str,
    handler: Handler = Depends(get_handler),
) -> TrackableTask:
    """Retrieve a task"""

    task = handler.worker.get_pending_task(task_id)
    if task is not None:
        return task
    else:
        raise HTTPException(status_code=404, detail="Item not found")


@app.get("/worker/task")
def get_active_task(handler: Handler = Depends(get_handler)) -> WorkerTask:
    return WorkerTask.of_worker(handler.worker)


@app.get("/worker/state")
def get_state(handler: Handler = Depends(get_handler)) -> WorkerState:
    """Get the State of the Worker"""
    return handler.worker.state


def start(config: ApplicationConfig):
    import uvicorn

    app.state.config = config
    uvicorn.run(app, host=config.api.host, port=config.api.port)


@app.middleware("http")
async def add_api_version_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-API-Version"] = REST_API_VERSION
    return response
