from typing import Any, Mapping, Optional

from fastapi import Body, Depends, FastAPI, HTTPException, Query

from blueapi.cli.amq import AmqClient
from blueapi.config import ApplicationConfig
from blueapi.worker import RunPlan

from .handler import Handler, get_handler, setup_handler, teardown_handler
from .model import DeviceModel, DeviceResponse, PlanModel, PlanResponse, TaskResponse

app = FastAPI(docs_url="/docs", on_shutdown=[teardown_handler])


@app.get("/plans", response_model=PlanResponse)
async def get_plans(handler: Handler = Depends(get_handler)):
    """Retrieve information about all available plans."""
    return PlanResponse(
        plans=[PlanModel.from_plan(plan) for plan in handler.context.plans.values()]
    )


@app.get("/plan/{name}", response_model=PlanModel)
async def get_plan_by_name(name: str, handler: Handler = Depends(get_handler)):
    """Retrieve information about a plan by its (unique) name."""
    try:
        return PlanModel.from_plan(handler.context.plans[name])
    except KeyError:
        raise HTTPException(status_code=404, detail="Item not found")


@app.get("/devices", response_model=DeviceResponse)
async def get_devices(handler: Handler = Depends(get_handler)):
    """Retrieve information about all available devices."""
    return DeviceResponse(
        devices=[
            DeviceModel.from_device(device)
            for device in handler.context.devices.values()
        ]
    )


@app.get("/device/{name}", response_model=DeviceModel)
async def get_device_by_name(name: str, handler: Handler = Depends(get_handler)):
    """Retrieve information about a devices by its (unique) name."""
    try:
        return DeviceModel.from_device(handler.context.devices[name])
    except KeyError:
        raise HTTPException(status_code=404, detail="Item not found")


@app.put("/task", response_model=TaskResponse)
async def create_task(
    task: RunPlan = Body(
        ..., example=RunPlan(name="count", params={"detectors": ["x"]})
    ),
    handler: Handler = Depends(get_handler),
) -> TaskResponse:
    """Submit a task onto the worker queue."""
    task_id = handler.worker.begin_transaction(task)
    return TaskResponse(task_id=task_id)


@app.delete("/task", response_model=TaskResponse)
async def delete_task(handler: Handler = Depends(get_handler)) -> TaskResponse:
    task_id = handler.worker.clear_transaction()
    return TaskResponse(task_id=task_id)


@app.put("/started/{task_id}")
async def start(
    task_id: str,
    handler: Handler = Depends(get_handler),
) -> TaskResponse:
    handler.worker.commit_transaction(task_id)
    return TaskResponse(task_id=task_id)


def start(config: ApplicationConfig):
    import uvicorn

    setup_handler(config)

    uvicorn.run(app, host=config.api.host, port=config.api.port)
