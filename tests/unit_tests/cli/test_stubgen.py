from io import StringIO
from textwrap import dedent
from types import FunctionType
from unittest.mock import Mock

import pytest

from blueapi.cli.stubgen import (
    _docstring,
    _type_string,
    generate_stubs,
    render_stub_file,
)
from blueapi.client.cache import DeviceRef, Plan
from blueapi.service.model import DeviceModel, PlanModel


def single_line():
    """Single line docstring"""


def single_line_new_line():
    """
    Single line docstring
    """


def multi_line_inline():
    """First line
    Second line"""


def multi_line_new_line():
    """
    First line
    Second line
    """


def indented_multi_line():
    """
    First line
        indented
    """


@pytest.mark.parametrize(
    "input,expected",
    [
        (single_line, "Single line docstring"),
        (single_line_new_line, "Single line docstring"),
        (multi_line_inline, "First line\nSecond line"),
        (multi_line_new_line, "First line\nSecond line"),
        (indented_multi_line, "First line\n    indented"),
    ],
)
def test_docstring_filter(input: FunctionType, expected: str):
    assert input.__doc__
    assert _docstring(input.__doc__) == expected


@pytest.mark.parametrize(
    "typ,expected",
    [
        ({"type": "string"}, "str"),
        ({"type": "number"}, "float"),
        ({"type": "integer"}, "int"),
        ({"type": "object"}, "dict[str, Any]"),
        ({"type": "boolean"}, "bool"),
        ({"type": "array", "items": {"type": "integer"}}, "list[int]"),
        ({"type": "array", "items": {"type": "object"}}, "list[dict[str, Any]]"),
        (
            {
                "type": "array",
                "items": {"anyOf": [{"type": "integer"}, {"type": "boolean"}]},
            },
            "list[int | bool]",
        ),
        ({"anyOf": [{"type": "object"}, {"type": "string"}]}, "dict[str, Any] | str"),
        ({"type": "unknown.other.Type"}, "Any"),
        # Special case the bluesky protocols to require device references
        ({"type": "bluesky.protocols.Readable"}, "DeviceRef"),
        ({}, "Any"),
    ],
    ids=lambda param: param.get("type") if isinstance(param, dict) else param,
)
def test_type_string(typ: dict, expected: str):
    assert _type_string(typ) == expected


def test_render_empty():
    output = StringIO()

    render_stub_file(output, [], [])
    plan_text, device_text = _extract_rendered(output)

    assert plan_text == ""
    assert device_text == ""


FOO = PlanModel(name="empty", description="Doc string for empty", schema={})

BAR = PlanModel(
    name="two_args",
    description="Doc string for two_args",
    schema={
        "properties": {
            "one": {"type": "integer"},
            "two": {"type": "string"},
        },
        "required": ["one"],
    },
)


def test_render_empty_plan_function():
    output = StringIO()
    plans = [Plan(model=FOO, runner=Mock())]
    render_stub_file(output, plans, [])
    plan_text, device_text = _extract_rendered(output)

    assert device_text == ""

    assert (
        plan_text
        == """\
    def empty(self,
    ) -> WorkerEvent:
        \"""
        Doc string for empty
        \"""
        ...\n"""
    )


def test_render_multiple_plan_functions():
    output = StringIO()
    runner = Mock()
    plans = [Plan(FOO, runner), Plan(BAR, runner)]
    render_stub_file(output, plans, [])
    plan_text, device_text = _extract_rendered(output)
    assert device_text == ""

    assert (
        plan_text
        == """\
    def empty(self,
    ) -> WorkerEvent:
        \"""
        Doc string for empty
        \"""
        ...
    def two_args(self,
            one: int,
            two: str | None = None,
    ) -> WorkerEvent:
        \"""
        Doc string for two_args
        \"""
        ...\n"""
    )


def test_device_fields():
    output = StringIO()
    cache = Mock()
    devices = [
        DeviceRef("one", cache, DeviceModel(name="one", protocols=[])),
        DeviceRef("two", cache, DeviceModel(name="two", protocols=[])),
    ]
    render_stub_file(output, [], devices)

    plan_text, device_text = _extract_rendered(output)
    assert plan_text == ""
    assert device_text == "    one: DeviceRef\n    two: DeviceRef\n"


def test_package_creation(tmp_path):
    generate_stubs(tmp_path / "blueapi-stubs", [], [])
    with open(tmp_path / "blueapi-stubs" / "pyproject.toml") as pyproj:
        assert pyproj.read().startswith(
            dedent("""
            [project]
            name = "blueapi-stubs"
            version = "0.1.0"
            """)
        )
    with open(
        tmp_path / "blueapi-stubs" / "src" / "blueapi-stubs" / "py.typed"
    ) as typed:
        assert typed.read() == "partial\n"

    assert (
        tmp_path / "blueapi-stubs" / "src" / "blueapi-stubs" / "client" / "cache.pyi"
    ).exists()


def _extract_rendered(src: StringIO) -> tuple[str, str]:
    src.seek(0)
    _read_until_line(src, "### Generated plans")
    plan_text = _read_until_line(src, "### End")
    _read_until_line(src, "### Generated devices")
    device_text = _read_until_line(src, "### End")
    return plan_text, device_text


def _read_until_line(src: StringIO, match: str) -> str:
    text = ""
    for line in src:
        if line.startswith(match):
            break
        text += line

    return text
