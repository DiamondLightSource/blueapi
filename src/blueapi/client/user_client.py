import time
import warnings
from collections.abc import Callable
from pathlib import Path

from bluesky.callbacks.best_effort import BestEffortCallback
from dodal.common import inject
from ophyd_async.core import StandardReadable

from blueapi.cli.updates import CliEventRenderer
from blueapi.client.client import BlueapiClient
from blueapi.client.event_bus import AnyEvent
from blueapi.client.rest import BlueskyRemoteControlError
from blueapi.config import (
    ApplicationConfig,
    ConfigLoader,
)
from blueapi.core import DataEvent
from blueapi.service.model import TaskRequest
from blueapi.worker import ProgressEvent

warnings.filterwarnings("ignore")  # callback complains about not running in main thread

# Currently matplotlib uses tkinter as default, tkinter must be in the main thread
# WebAgg does need ot be, so can allow LivePlots
# import matplotlib
# matplotlib.use("WebAgg")


class UserClient(BlueapiClient):
    """A client that can be easily used by the user, beamline scientist
    in a scripts, for running bluesky plans.

    Example usage:

    blueapi_config_path = "/path/to/ixx_blueapi_config.yaml"

    client = UserClient(blueapi_config_path, "cm12345-1")
    client.run("count", detectors=["det1", "det2"])
    client.change_session("cm12345-2")

    from dodal.plan_stubs.wrapped import move

    client.run(move, moves={"base.x": 0})  # move base.x to 0

    or if passing the bluesky function you can just use args:

    client.run(move, {"base.x": 0})

    """

    def __init__(
        self,
        blueapi_config_path: str | Path,
        instrument_session: str,
        callback: bool = True,
        timeout: int | float | None = None,
        non_callback_delay: int | float = 1,
    ):
        self.instrument_session = instrument_session
        self.callback = callback
        self.retries = 5
        self.timeout = timeout
        self.non_callback_delay = non_callback_delay

        blueapi_config_path = Path(blueapi_config_path)

        config_loader = ConfigLoader(ApplicationConfig)
        config_loader.use_values_from_yaml(blueapi_config_path)
        loaded_config = config_loader.load()
        rest, events = BlueapiClient.config_to_rest_and_events(loaded_config)
        super().__init__(rest, events)

    def _convert_args_to_kwargs(self, plan: Callable, args: tuple) -> dict:
        """Converts args to kwargs
        If the user does not give kwargs, but gives args the bluesky plan is passed
        this function can infer the kwargs, build the kwargs and create the params
        for TaskRequest"""
        arg_names = plan.__code__.co_varnames
        inferred_kwargs = {}

        for key, val in zip(arg_names, args):  # noqa intentionally not strict
            inferred_kwargs[key] = val
        params = inferred_kwargs
        return params

    def _args_and_kwargs_to_params(
        self, plan: Callable | str, args: tuple, kwargs: dict
    ) -> dict:
        """
        Creates the params needed for TaskRequest
        """
        if not args and not kwargs:
            params = {}
            return params
        elif kwargs and (not args):
            params = kwargs
            return params
        elif (
            args
            and (not kwargs)
            and hasattr(plan, "__code__")
            and not isinstance(plan, str)
        ):
            params = self._convert_args_to_kwargs(plan, args)
            return params
        elif (
            args and kwargs and hasattr(plan, "__code__") and not isinstance(plan, str)
        ):
            params = self._convert_args_to_kwargs(plan, args)
            params.update(kwargs)
            return params
        elif isinstance(plan, str) and args:
            raise ValueError("If you pass the bluesky plan str, you can't pass args ")
        else:
            raise ValueError("Could not infer parameters from args and kwargs")

    def run(self, plan: str | Callable, *args, **kwargs):
        """Run a bluesky plan via BlueAPI.
        plan can be a string, or the bluesky plan name"""

        if isinstance(plan, str):
            plan_name = plan
        elif hasattr(plan, "__name__") and hasattr(plan, "__code__"):
            plan_name = plan.__name__
        else:
            raise ValueError("Must be a str or a bluesky plan function")

        params = self._args_and_kwargs_to_params(plan, args=args, kwargs=kwargs)

        task = TaskRequest(
            name=plan_name,
            params=params,
            instrument_session=self.instrument_session,
        )
        if self.callback:
            self.send_with_callback(plan_name, task)
        else:
            self.send_without_callback(plan_name, task)

    def return_detectors(self) -> list[StandardReadable]:
        """Return a list of StandardReadable for the current beamline."""
        devices = self.get_devices().devices
        return [inject(d.name) for d in devices]

    def change_session(self, new_session: str) -> None:
        """Change the instrument session for the client."""
        print(f"New instrument session: {new_session}")
        self.instrument_session = new_session

    def show_plans(self):
        """Shows the bluesky plan names in a nice, human readable way"""
        plans = self.get_plans().plans
        for plan in plans:
            print(plan.name)
        print(f"Total plans: {len(plans)} \n")

    def show_devices(self):
        """Shows the devices in a nice, human readable way"""
        devices = self.get_devices().devices
        for dev in devices:
            print(dev.name)
        print(f"Total devices: {len(devices)} \n")

    def send_with_callback(self, plan_name: str, task: TaskRequest):
        """Sends a bluesky Task to blueapi with callback.
        Callback allows LiveTable and LivePlot to be generated
        """
        try:
            progress_bar = CliEventRenderer()
            callback = BestEffortCallback()

            def on_event(event: AnyEvent) -> None:
                if isinstance(event, ProgressEvent):
                    progress_bar.on_progress_event(event)
                elif isinstance(event, DataEvent):
                    callback(event.name, event.doc)

            resp = self.run_task(task, on_event=on_event, timeout=self.timeout)

            if (
                (resp.task_status is not None)
                and (resp.task_status.task_complete)
                and (not resp.task_status.task_failed)
            ):
                print(f"{plan_name} succeeded")

            return

        except Exception as e:
            raise Exception(f"Task could not run: {e}") from e

    def send_without_callback(self, plan_name: str, task: TaskRequest):
        """Send the TaskRequest as a put request.
        Because it does not have callback
        It does not know if blueapi is busy.
        So it will try multiple times with a delay"""
        success = False

        for _ in range(self.retries):
            try:
                server_task = self.create_and_start_task(task)
                print(f"{plan_name} task sent as {server_task.task_id}")
                success = True
                return
            except BlueskyRemoteControlError:
                time.sleep(self.non_callback_delay)

        if not success:
            raise Exception("Task could not be executed")
