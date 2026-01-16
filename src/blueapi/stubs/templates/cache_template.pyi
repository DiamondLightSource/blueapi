from collections.abc import Callable
from typing import Any
from blueapi.client.rest import BlueapiRestClient
from blueapi.service.model import DeviceModel, PlanModel
from blueapi.worker.event import WorkerEvent

{#-
 This file is based on the cache.py file in blueapi/client/cache.py and should
 be kept in sync with changes there.
#}

# This file is auto-generated for a live server and should not be modified directly

PlanRunner = Callable[[str, dict[str, Any]], WorkerEvent]

class PlanCache:
    def __init__(self, runner: PlanRunner, plans: list[PlanModel]) -> None: ...
    def __getitem__(self, name: str) -> Plan: ...
    def __iter__(self):  # -> Iterator[Plan]:
        ...
    def __repr__(self) -> str: ...

    {% for item in plans -%}
    def {{ item.name }}(self,{% for arg in item.args %}
            {{ arg.name }}: {{ arg.type }}{% if arg.optional %} | None = None{% endif %},
            {%- endfor %}
    ) -> WorkerEvent:
        """{{ item.docs }}"""
        ...
    {% endfor %}


class Plan:
    model: PlanModel
    name: str
    def __init__(self, name, model: PlanModel, runner: PlanRunner) -> None: ...
    def __call__(self, *args, **kwargs):  # -> None:
        ...
    @property
    def help_text(self) -> str: ...
    @property
    def properties(self) -> set[str]: ...
    @property
    def required(self) -> list[str]: ...
    def __repr__(self) -> str: ...


class DeviceRef(str):
    model: DeviceModel
    _cache: DeviceCache
    def __new__(cls, name: str, cache: DeviceCache, model: DeviceModel): ...
    def __getattr__(self, name) -> DeviceRef: ...
    def __repr__(self) -> str: ...

class DeviceCache:
    def __init__(self, rest: BlueapiRestClient) -> None: ...
    def __getitem__(self, name: str) -> DeviceRef: ...
    def __iter__(self):  # -> Iterator[DeviceRef]:
        ...
    def __repr__(self) -> str: ...

    {% for item in devices -%}
    {{ item }}: DeviceRef
    {% endfor %}
