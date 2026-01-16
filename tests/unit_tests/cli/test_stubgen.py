from types import FunctionType

import pytest

from blueapi.cli.stubgen import _docstring, _type_string


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
