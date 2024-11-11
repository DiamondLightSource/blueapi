import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from importlib import import_module
from inspect import Parameter, signature
from types import ModuleType, UnionType
from typing import (
    Any,
    Generic,
    TypeVar,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

from bluesky.run_engine import RunEngine
from dodal.utils import make_all_devices
from ophyd_async.core import NotConnected
from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler, create_model
from pydantic.fields import FieldInfo
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema, core_schema

from blueapi.config import EnvironmentConfig, SourceKind
from blueapi.utils import BlueapiPlanModelConfig, load_module_all

from .bluesky_types import (
    BLUESKY_PROTOCOLS,
    Device,
    HasName,
    Plan,
    PlanGenerator,
    is_bluesky_compatible_device,
    is_bluesky_plan_generator,
)
from .device_lookup import find_component

LOGGER = logging.getLogger(__name__)


@dataclass
class BlueskyContext:
    """
    Context for building a Bluesky application.

    The context holds the RunEngine and any plans/devices that you may want to use.
    """

    run_engine: RunEngine = field(
        default_factory=lambda: RunEngine(context_managers=[])
    )
    plans: dict[str, Plan] = field(default_factory=dict)
    devices: dict[str, Device] = field(default_factory=dict)
    plan_functions: dict[str, PlanGenerator] = field(default_factory=dict)

    _reference_cache: dict[type, type] = field(default_factory=dict)

    def find_device(self, addr: str | list[str]) -> Device | None:
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

    def with_config(self, config: EnvironmentConfig) -> None:
        for source in config.sources:
            mod = import_module(str(source.module))

            if source.kind is SourceKind.PLAN_FUNCTIONS:
                self.with_plan_module(mod)
            elif source.kind is SourceKind.DEVICE_FUNCTIONS:
                self.with_device_module(mod)
            elif source.kind is SourceKind.DODAL:
                self.with_dodal_module(mod)

    def with_plan_module(self, module: ModuleType) -> None:
        """
        Register all functions in the module supplied as plans.
        Module should take the form:

        def plan_1(...) -> MsgGenerator:
            ...

        def _helper(...):
            ...

        def plan_2(...) -> MsgGenerator:
            ...

        __all__ = ["plan_1", "plan_2"]

        Args:
            module (ModuleType): Module to pass in
        """

        for obj in load_module_all(module):
            if is_bluesky_plan_generator(obj):
                self.register_plan(obj)

    def with_device_module(self, module: ModuleType) -> None:
        self.with_dodal_module(module)

    def with_dodal_module(self, module: ModuleType, **kwargs) -> None:
        devices, exceptions = make_all_devices(module, **kwargs)

        for device in devices.values():
            self.register_device(device)

        # If exceptions have occurred, we log them but we do not make blueapi
        # fall over
        if len(exceptions) > 0:
            LOGGER.warning(
                f"{len(exceptions)} exceptions occurred while instantiating devices"
            )
            LOGGER.exception(NotConnected(exceptions))

    def register_plan(self, plan: PlanGenerator) -> PlanGenerator:
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

        model = create_model(  # type: ignore
            plan.__name__,
            __config__=BlueapiPlanModelConfig,
            **self._type_spec_for_function(plan),
        )
        self.plans[plan.__name__] = Plan(
            name=plan.__name__, model=model, description=plan.__doc__
        )
        self.plan_functions[plan.__name__] = plan
        return plan

    def register_device(self, device: Device, name: str | None = None) -> None:
        """
        Register an device in the context. The device needs to be registered with a
        name. If the device is Readable, Movable or Flyable it has a `name`
        attribute which can be used. The attribute can be overridden with the
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

    def _reference(self, target: type) -> type:
        """
        Create an intermediate reference type for the required ``target`` type that
        will return an existing device during pydantic deserialisation/validation

        Args:
            target: Expected type of the device that is expected for IDs being
                deserialised by the return type
        Returns:
            New type that can be deserialised by pydantic returning an existing device
                for a string device ID
        """
        if target not in self._reference_cache:

            class Reference(target):
                @classmethod
                def __get_pydantic_core_schema__(
                    cls, source_type: Any, handler: GetCoreSchemaHandler
                ) -> CoreSchema:
                    def valid(value):
                        val = self.find_device(value)
                        if not isinstance(val, target):
                            raise ValueError(f"Device {value} is not of type {target}")
                        return val

                    return core_schema.no_info_after_validator_function(
                        valid, handler(str)
                    )

                @classmethod
                def __get_pydantic_json_schema__(
                    cls, core_schema: CoreSchema, handler: GetJsonSchemaHandler
                ) -> JsonSchemaValue:
                    json_schema = handler(core_schema)
                    json_schema = handler.resolve_ref_schema(json_schema)
                    json_schema["type"] = f"{target.__module__}.{target.__qualname__}"
                    return json_schema

            self._reference_cache[target] = Reference

        return self._reference_cache[target]

    def _type_spec_for_function(
        self, func: Callable[..., Any]
    ) -> dict[str, tuple[type, FieldInfo]]:
        """
        Parse a function signature and build map of field types and default
        values that can be used to deserialise arguments from external sources.
        Any references to any of the bluesky protocols are replaced with an
        intermediate reference type that allows existing devices to be returned
        for device ID strings.

        Args:
            func: The function whose signature is being parsed

        Returns:
            Mapping of {name: (type, default)} to be used by pydantic for deserialising
                    function arguments
        """
        args = signature(func).parameters
        types = get_type_hints(func)
        new_args: dict[str, tuple[type, FieldInfo]] = {}
        for name, para in args.items():
            arg_type = types.get(name, Parameter.empty)
            if arg_type is Parameter.empty:
                raise ValueError(
                    f"Type annotation is required for '{name}' in '{func.__name__}'"
                )

            no_default = para.default is Parameter.empty
            factory = None if no_default else DefaultFactory(para.default)
            new_args[name] = (
                self._convert_type(arg_type),
                FieldInfo(default_factory=factory),
            )
        return new_args

    def _convert_type(self, typ: type | Any) -> type:
        """
        Recursively convert a type to something that can be deserialised by
        pydantic. Bluesky protocols (and types that extend them) are replaced
        with an intermediate reference types that allows the current context to
        be used to look up an existing device when deserialising device ID
        strings.

        Other types are returned as passed in.

        Args:
            typ: The type that is required - potentially referencing Bluesky protocols

        Returns:
            A Type that can be deserialised by Pydantic
        """
        if typ in BLUESKY_PROTOCOLS or any(
            isinstance(typ, dev) for dev in BLUESKY_PROTOCOLS
        ):
            return self._reference(typ)
        args = get_args(typ)
        if args:
            new_types = tuple(self._convert_type(i) for i in args)
            root = get_origin(typ)
            if root == UnionType:
                root = Union
            return root[new_types] if root else typ
        return typ


D = TypeVar("D")


class DefaultFactory(Generic[D]):
    _value: D

    def __init__(self, value: D):
        self._value = value

    def __call__(self) -> D:
        return self._value

    def __eq__(self, other) -> bool:
        return other.__class__ == self.__class__ and self._value == other._value
