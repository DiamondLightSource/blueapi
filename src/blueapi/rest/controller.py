import asyncio
from dataclasses import dataclass
from typing import Optional

from aiohttp import web

from blueapi.core import AgnosticBlueskyController, ControllerBuilder


@dataclass
class RestEndpointSettings:
    plans: str = "/plans"


class RestController(ControllerBuilder):
    _endpoints: RestEndpointSettings

    def __init__(self, endpoints: Optional[RestEndpointSettings] = None) -> None:
        self._endpoints = endpoints or RestEndpointSettings()

    async def run_forever(self, controller: AgnosticBlueskyController) -> None:
        routes = web.RouteTableDef()

        @routes.put(f"{self._endpoints.plans}/{{name}}/run")
        async def handle_plan_request(request: web.Request) -> web.Response:
            plan_name = request.match_info["name"]
            params = (await request.json())["model_params"]
            asyncio.create_task(controller.run_plan(plan_name, params))
            return web.json_response({"plan": plan_name, "status": "started"})

        @routes.get(f"{self._endpoints.plans}")
        async def get_plans(request: web.Request) -> web.Response:
            return web.json_response(
                {plan.name: {"model": "TBD"} for plan in (await controller.get_plans())}
            )

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
        print(f"running {site}")
        await done.wait()
