import logging
from dataclasses import dataclass, field
from importlib import import_module
from inspect import Signature
from pathlib import Path
from types import ModuleType
from typing import _GenericAlias  # type: ignore
from typing import Dict, Iterable, List, Optional, Type, Union, get_args

from bluesky import RunEngine
from bluesky.protocols import HasName
from pydantic import BaseConfig

from blueapi.utils import (
    TypeValidatorDefinition,
    create_model_with_type_validators,
    load_module_all,
)

from .bluesky_types import (
    Device,
    Plan,
    PlanGenerator,
    is_bluesky_compatible_device,
    is_bluesky_compatible_device_type,
    is_bluesky_plan_generator,
)
from .device_lookup import find_component

LOGGER = logging.getLogger(__name__)


class PlanModelConfig(BaseConfig):
    arbitrary_types_allowed = True


@dataclass
class BlueskyContext:
    """
    Context for building a Bluesky application
    """

    run_engine: RunEngine = field(
        default_factory=lambda: RunEngine(context_managers=[])
    )
    plans: Dict[str, Plan] = field(default_factory=dict)
    devices: Dict[str, Device] = field(default_factory=dict)
    plan_functions: Dict[str, PlanGenerator] = field(default_factory=dict)

    def find_device(self, addr: Union[str, List[str]]) -> Optional[Device]:
        """
        Find a device in this context, allows for recursive search.

        Args:
            addr (Union[str, List[str]]): Address of the device, examples:
                                          "motors", "motors.x"

        Returns:
            Optional[Device]: _description_
        """

        if isinstance(addr, str):
            list_addr = list(addr.split("."))
            return self.find_device(list_addr)
        else:
            return find_component(self.devices, addr)

    def with_startup_script(self, path: Union[Path, str]) -> None:
        mod = import_module(str(path))
        self.with_module(mod)

    def with_module(self, module: ModuleType) -> None:
        self.with_plan_module(module)
        self.with_device_module(module)

    def with_plan_module(self, module: ModuleType) -> None:
        """
        Register all functions in the module supplied as plans.
        Module should take the form:

        def plan_1(...):
            ...

        def _helper(...):
            ...

        def plan_2(...):
            ...

        __all__ = ["plan_1", "plan_2"]

        Args:
            module (ModuleType): Module to pass in
        """

        for obj in load_module_all(module):
            if is_bluesky_plan_generator(obj):
                self.plan(obj)

    def with_device_module(self, module: ModuleType) -> None:
        for obj in load_module_all(module):
            if is_bluesky_compatible_device(obj):
                self.device(obj)

    def plan(self, plan: PlanGenerator) -> PlanGenerator:
        """
        Register the argument as a plan in the context. Can be used as a decorator e.g.
        @ctx.plan
        def my_plan(a: int, b: str):
            ...

        Args:
            plan (PlanGenerator): Plan generator function to register

        Returns:
            PlanGenerator: The plan passed in for chaining/decorating
        """

        if not is_bluesky_plan_generator(plan):
            raise TypeError(f"{plan} is not a valid plan generator function")

        validators = list(plan_validators(self, plan))
        model = create_model_with_type_validators(
            plan.__name__,
            validators,
            func=plan,
            config=PlanModelConfig,
        )
        self.plans[plan.__name__] = Plan(name=plan.__name__, model=model)
        self.plan_functions[plan.__name__] = plan
        return plan

    def device(self, device: Device, name: Optional[str] = None) -> None:
        """
        Register a device in the context. The device needs to be registered with a
        name. If the device is Readable, Movable or Flyable it has a `name`
        attribute which can be used. The attribute can be overriden with the
        `name` parameter here. If the device conforms to a different protocol then
        the parameter must be used to name it.

        Args:
            device (Device): The device to register
            name (Optional[str], optional): A name for the device. Defaults to None.

        Raises:
            KeyError: If no name is found/supplied
        """

        if not is_bluesky_compatible_device(device):
            raise TypeError(f"{device} is not a Bluesky compatible device")

        if name is None:
            if isinstance(device, HasName):
                name = device.name
            else:
                raise KeyError(f"Must supply a name for this device: {device}")

        self.devices[name] = device


def plan_validators(
    ctx: BlueskyContext, plan: PlanGenerator
) -> Iterable[TypeValidatorDefinition]:
    def get_validator(plan_arg: str, field_type: Type) -> TypeValidatorDefinition:
        def get_device(name: str):
            device = ctx.find_device(name)
            if device is None:
                raise KeyError(
                    f"Could not find a device named {name} for plan argument {plan_arg}"
                )
            if not isinstance(device, field_type):
                raise KeyError(
                    f"Device named {name} did not comply with expected type"
                    f" {field_type} of plan argument {plan_arg}"
                )
            return device

        return TypeValidatorDefinition(field_type, get_device)

    def get_validators(
        plan_arg: str, field_type: Type
    ) -> Iterable[TypeValidatorDefinition]:
        #  TODO: Allow only list as list-like plan param?
        #  TODO: Only allow dict[str, ?] as dict-like plan param?
        if isinstance(field_type, (_GenericAlias, dict, list, tuple, set)):
            for arg in get_args(field_type):
                yield from get_validators(plan_arg, arg)
        elif is_bluesky_compatible_device_type(field_type):
            yield get_validator(plan_arg, field_type)
        else:
            yield from {}

    for k, v in Signature.from_callable(plan).parameters.items():
        yield from get_validators(k, v.annotation)
