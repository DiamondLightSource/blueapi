import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

from aiohttp import web

from blueapi.core import BlueskyService, ControllerBuilder

LOGGER = logging.getLogger(__name__)


@dataclass
class RestEndpointSettings:
    plans: str = "/plans"
    run_plan: str = "/plans/{name}/run"


class RestController(ControllerBuilder):
    _endpoints: RestEndpointSettings

    def __init__(self, endpoints: Optional[RestEndpointSettings] = None) -> None:
        self._endpoints = endpoints or RestEndpointSettings()

    async def run_forever(self, controller: BlueskyService) -> None:
        LOGGER.info("Initializing REST controller")

        routes = web.RouteTableDef()

        @routes.put(self._endpoints.run_plan)
        async def handle_plan_request(request: web.Request) -> web.Response:
            plan_name = request.match_info["name"]
            params = (await request.json())["model_params"]
            asyncio.create_task(controller.run_plan(plan_name, params))
            return web.json_response({"plan": plan_name, "status": "started"})

        LOGGER.info(f"Endpoint initialized: {self._endpoints.run_plan}")

        @routes.get(self._endpoints.plans)
        async def get_plans(request: web.Request) -> web.Response:
            return web.json_response(
                {plan.name: {"model": "TBD"} for plan in (await controller.get_plans())}
            )

        LOGGER.info(f"Endpoint initialized: {self._endpoints.plans}")

        app = web.Application()
        app.add_routes(routes)

        done = asyncio.Event()

        async def cleanup(app: web.Application) -> None:
            done.set()

        app.on_cleanup.append(cleanup)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", 8080)
        await site.start()
        LOGGER.info(f"running {site}")
        await done.wait()
