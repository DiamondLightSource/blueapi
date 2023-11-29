import tempfile
from pathlib import Path
from typing import Any, Mapping, Union

import pytest
from pydantic import BaseModel

from blueapi.utils import print_as_yaml, write_as_yaml


class Foo(BaseModel):
    c: int
    d: str


class Bar(BaseModel):
    a: bool
    b: Foo


EXPECTED_YAML = """a: true
b:
  c: 5
  d: Hello World
"""

DATA = [
    Bar(a=True, b=Foo(c=5, d="Hello World")),
    {
        "a": True,
        "b": {
            "c": 5,
            "d": "Hello World",
        },
    },
]


@pytest.mark.parametrize("data", DATA)
def test_yaml_print(
    capfd: pytest.CaptureFixture, data: Union[Mapping[str, Any], BaseModel]
):
    print_as_yaml(data)
    out, _ = capfd.readouterr()
    assert out == (EXPECTED_YAML + "\n")


@pytest.mark.parametrize("data", DATA)
def test_yaml_write(data: Union[Mapping[str, Any], BaseModel]):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "test_data.yaml"
        write_as_yaml(path, data)
        with path.open("r") as stream:
            output_yaml = stream.read()
        assert output_yaml == EXPECTED_YAML
