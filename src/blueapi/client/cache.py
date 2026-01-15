import logging
from collections.abc import Callable
from itertools import chain
from typing import Any

from blueapi.client.rest import BlueapiRestClient
from blueapi.service.model import DeviceModel, PlanModel
from blueapi.worker.event import WorkerEvent

log = logging.getLogger(__name__)

PlanRunner = Callable[[str, dict[str, Any]], WorkerEvent]


class PlanCache:
    def __init__(self, runner: PlanRunner, plans: list[PlanModel]):
        self._cache = {
            model.name: Plan(name=model.name, model=model, runner=runner)
            for model in plans
        }
        for name, plan in self._cache.items():
            if name.startswith("_"):
                continue
            setattr(self, name, plan)

    def __getitem__(self, name: str) -> "Plan":
        return self._cache[name]

    def __getattr__(self, name: str) -> "Plan":
        raise AttributeError(f"No plan named '{name}' available")

    def __iter__(self):
        return iter(self._cache.values())

    def __repr__(self) -> str:
        return f"PlanCache({len(self._cache)} plans)"


class Plan:
    def __init__(self, name, model: PlanModel, runner: PlanRunner):
        self.name = name
        self.model = model
        self._runner = runner
        self.__doc__ = model.description

    def __call__(self, *args, **kwargs) -> WorkerEvent:
        return self._runner(self.name, self._build_args(*args, **kwargs))

    @property
    def help_text(self) -> str:
        return self.model.description or f"Plan {self!r}"

    @property
    def properties(self) -> set[str]:
        return self.model.parameter_schema.get("properties", {}).keys()

    @property
    def required(self) -> list[str]:
        return self.model.parameter_schema.get("required", [])

    def _build_args(self, *args, **kwargs):
        log.info(
            "Building args for %s, using %s and %s",
            "[" + ",".join(self.properties) + "]",
            args,
            kwargs,
        )

        if len(args) > len(self.properties):
            raise TypeError(f"{self.name} got too many arguments")
        if extra := {k for k in kwargs if k not in self.properties}:
            raise TypeError(f"{self.name} got unexpected arguments: {extra}")

        params = {}
        # Initially fill parameters using positional args assuming the order
        # from the parameter_schema
        for req, arg in zip(self.properties, args, strict=False):
            params[req] = arg

        # Then append any values given via kwargs
        for key, value in kwargs.items():
            # If we've already assumed a positional arg was this value, bail out
            if key in params:
                raise TypeError(f"{self.name} got multiple values for {key}")
            params[key] = value

        if missing := {k for k in self.required if k not in params}:
            raise TypeError(f"Missing argument(s) for {missing}")
        return params

    def __repr__(self):
        opts = [p for p in self.properties if p not in self.required]
        params = ", ".join(chain(self.required, (f"{opt}=None" for opt in opts)))
        return f"{self.name}({params})"


class DeviceCache:
    def __init__(self, rest: BlueapiRestClient):
        self._rest = rest
        self._cache = {
            model.name: DeviceRef(name=model.name, cache=self, model=model)
            for model in rest.get_devices().devices
        }
        for name, device in self._cache.items():
            if name.startswith("_"):
                continue
            setattr(self, name, device)

    def __getitem__(self, name: str) -> "DeviceRef":
        if dev := self._cache.get(name):
            return dev
        try:
            model = self._rest.get_device(name)
            device = DeviceRef(name=name, cache=self, model=model)
            self._cache[name] = device
            setattr(self, model.name, device)
            return device
        except KeyError:
            pass
        raise AttributeError(f"No device named '{name}' available")

    def __getattr__(self, name: str) -> "DeviceRef":
        if name.startswith("_"):
            return super().__getattribute__(name)
        return self[name]

    def __iter__(self):
        return iter(self._cache.values())

    def __repr__(self) -> str:
        return f"DeviceCache({len(self._cache)} devices)"


class DeviceRef(str):
    model: DeviceModel
    _cache: DeviceCache

    def __new__(cls, name: str, cache: DeviceCache, model: DeviceModel):
        instance = super().__new__(cls, name)
        instance.model = model
        instance._cache = cache
        return instance

    def __getattr__(self, name) -> "DeviceRef":
        if name.startswith("_"):
            raise AttributeError(f"No child device named {name}")
        return self._cache[f"{self}.{name}"]

    def __repr__(self):
        return f"Device({self})"
