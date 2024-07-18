import builtins
import enum
import json
import sys
import textwrap
from functools import partial
from pprint import pprint
from textwrap import dedent, indent
from typing import Any, TextIO

from pydantic import BaseModel

from blueapi.service.model import DeviceResponse, PlanResponse

FALLBACK = pprint

Stream = TextIO | None


class OutputFormat(str, enum.Enum):
    JSON = "json"
    FULL = "full"
    COMPACT = "compact"

    def display(self, obj: Any, out: Stream = None):
        out = out or sys.stdout
        match self:
            case OutputFormat.FULL:
                display_full(obj, out)
            case OutputFormat.COMPACT:
                display_compact(obj, out)
            case OutputFormat.JSON:
                display_json(obj, out)


def display_full(obj: Any, stream: Stream):
    print = partial(builtins.print, file=stream)
    match obj:
        case PlanResponse(plans=plans):
            for plan in plans:
                print(plan.name)
                if desc := plan.description:
                    print(indent(dedent(desc).strip(), "    "))
                if schema := plan.parameter_schema:
                    print("    Schema")
                    print(indent(json.dumps(schema, indent=2), "        "))
        case DeviceResponse(devices=devices):
            for dev in devices:
                print(dev.name)
                for proto in dev.protocols:
                    print("    " + proto)
        case other:
            FALLBACK(other, stream=stream)


def display_json(obj: Any, stream: Stream):
    print = partial(builtins.print, file=stream)
    match obj:
        case PlanResponse(plans=plans):
            print(json.dumps([p.dict() for p in plans], indent=2))
        case DeviceResponse(devices=devices):
            print(json.dumps([d.dict() for d in devices], indent=2))
        case BaseModel():
            print(json.dumps(obj.dict(), indent=2))
        case _:
            print(json.dumps(obj))


def display_compact(obj: Any, stream: Stream):
    print = partial(builtins.print, file=stream)
    match obj:
        case PlanResponse(plans=plans):
            for plan in plans:
                print(plan.name)
                if desc := plan.description:
                    print(indent(dedent(desc.split("\n\n")[0].strip("\n")), "    "))
                if schema := plan.parameter_schema:
                    print("    Args")
                    for arg, spec in schema.get("properties", {}).items():
                        req = arg in schema.get("required", {})
                        print(f"      {arg}={_describe_type(spec, req)}")
        case DeviceResponse(devices=devices):
            for dev in devices:
                print(dev.name)
                print(indent(textwrap.fill(", ".join(dev.protocols), 80), "    "))
        case other:
            FALLBACK(other, stream=stream)


def _describe_type(spec: dict[Any, Any], required: bool = False):
    disp = ""
    match spec.get("type"):
        case None:
            if all_of := spec.get("allOf"):
                items = (_describe_type(f, False) for f in all_of)
                disp += f'{" & ".join(items)}'
            else:
                disp += "Any"
        case "array":
            element = spec.get("items", {}).get("type", "Any")
            disp += f"[{element}]"
        case other:
            disp += other
    if required:
        disp += " (Required)"
    return disp
