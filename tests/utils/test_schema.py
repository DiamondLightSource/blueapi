import dataclasses
from typing import Any

import pytest

from blueapi.utils import schema_for_func


def test_schema_generated() -> None:
    def func(foo: int, bar: str = "hello") -> None:
        ...

    schema = schema_for_func(func)
    assert dataclasses.is_dataclass(schema)
    foo, bar = dataclasses.fields(schema)

    assert foo.name == "foo"
    assert foo.type == int
    assert foo.default == dataclasses.MISSING

    assert bar.name == "bar"
    assert bar.type == str
    assert bar.default == "hello"


def test_rejects_any() -> None:
    def func(foo: int, bar: Any) -> None:
        ...

    with pytest.raises(TypeError):
        schema_for_func(func)


def test_rejects_no_param() -> None:
    def func(foo: int, bar) -> None:
        ...

    with pytest.raises(TypeError):
        schema_for_func(func)
