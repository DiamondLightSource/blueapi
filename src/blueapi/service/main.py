from fastapi import Body, Depends, FastAPI, HTTPException

from blueapi.config import ApplicationConfig
from blueapi.worker import RunPlan

from .handler import Handler, get_handler, setup_handler, teardown_handler
from .model import DeviceModel, DeviceResponse, PlanModel, PlanResponse

app = FastAPI(docs_url="/docs", on_shutdown=[teardown_handler])


@app.get("/plans", response_model=PlanResponse)
async def get_plans(handler: Handler = Depends(get_handler)):
    return PlanResponse(
        plans=[PlanModel.from_plan(plan) for plan in handler.context.plans.values()]
    )


@app.get("/plan/{name}", response_model=PlanModel)
async def get_plan_by_name(name: str, handler: Handler = Depends(get_handler)):
    try:
        return PlanModel.from_plan(handler.context.plans[name])
    except KeyError:
        raise HTTPException(status_code=404, detail="Item not found")


@app.get("/devices", response_model=DeviceResponse)
async def get_devices(handler: Handler = Depends(get_handler)):
    return DeviceResponse(
        devices=[
            DeviceModel.from_device(device)
            for device in handler.context.devices.values()
        ]
    )


@app.get("/device/{name}", response_model=DeviceModel)
async def get_device_by_name(name: str, handler: Handler = Depends(get_handler)):
    try:
        return DeviceModel.from_device(handler.context.devices[name])
    except KeyError:
        raise HTTPException(status_code=404, detail="Item not found")


@app.put("/task/{name}")
async def execute_task(
    name: str,
    task: RunPlan = Body(
        ..., example={"name": "count", "params": {"detectors": ["x"]}}
    ),
    handler: Handler = Depends(get_handler),
):
    # basically in here, do the same thing the service once did...
    handler.worker.submit_task(name, task)
    pass


def start(config: ApplicationConfig):
    import uvicorn

    setup_handler(config)

    uvicorn.run(app, host=config.api.host, port=config.api.port)
