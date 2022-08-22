from dataclasses import dataclass
from typing import Any, Mapping

import pytest

from blueapi.messaging.utils import determine_deserialization_type


@dataclass
class Foo:
    bar: int
    baz: str


def test_determine_deserialization_type() -> None:
    def on_message(headers: Mapping[str, Any], message: Foo) -> None:
        ...

    deserialization_type = determine_deserialization_type(on_message)  # type: ignore
    assert deserialization_type is Foo


def test_determine_deserialization_type_with_no_type() -> None:
    def on_message(headers: Mapping[str, Any], message) -> None:
        ...

    deserialization_type = determine_deserialization_type(on_message)  # type: ignore
    assert deserialization_type is str


def test_determine_deserialization_type_with_wrong_signature() -> None:
    def on_message(message: Foo) -> None:
        ...

    with pytest.raises(ValueError):
        determine_deserialization_type(on_message)  # type: ignore
