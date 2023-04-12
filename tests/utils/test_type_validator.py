from typing import Any, Dict, List, Mapping, NamedTuple, Set, Tuple, Type

import pytest
from pydantic import BaseConfig, BaseModel, parse_obj_as
from pydantic.fields import Undefined

from blueapi.utils import TypeConverter, create_model_with_type_validators

_REG: Mapping[str, int] = {
    letter: number for number, letter in enumerate("abcdefghijklmnopqrstuvwxyz")
}


class ComplexObject:
    _name: str

    def __init__(self, name: str) -> None:
        self._name = name

    def name(self) -> str:
        return self._name

    def __eq__(self, __value: object) -> bool:
        return isinstance(__value, ComplexObject) and __value.name() == self._name

    def __str__(self) -> str:
        return f"ComplexObject({self._name})"

    def __repr__(self) -> str:
        return f"ComplexObject({self._name})"


_DB: Mapping[str, ComplexObject] = {name: ComplexObject(name) for name in _REG.keys()}


def lookup(letter: str) -> int:
    assert type(letter) is str, f"Expteced a string, got a {type(letter)}"
    return _REG[letter]


def has_even_length(msg: str) -> bool:
    assert type(msg) is str, f"Expteced a string, got a {type(msg)}"
    return len(msg) % 2 == 0


def lookup_complex(name: str) -> ComplexObject:
    assert type(name) is str, f"Expteced a string, got a {type(name)}"
    return _DB[name]


def test_validates_single_type() -> None:
    assert_validates_single_type(int, "c", 2)


def test_leaves_unvalidated_types_alone() -> None:
    model = create_model_with_type_validators(
        "Foo",
        {"a": (int, Undefined), "b": (str, Undefined)},
        [TypeConverter(int, lookup)],
    )
    parsed = parse_obj_as(model, {"a": "c", "b": "hello"})
    assert parsed.a == 2
    assert parsed.b == "hello"


def test_validates_multiple_types() -> None:
    model = create_model_with_type_validators(
        "Foo",
        {"a": (int, Undefined), "b": (bool, Undefined)},
        [TypeConverter(int, lookup), TypeConverter(bool, has_even_length)],
    )
    parsed = parse_obj_as(model, {"a": "c", "b": "hello"})
    assert parsed.a == 2
    assert parsed.b == False


def test_validates_multiple_fields() -> None:
    model = create_model_with_type_validators(
        "Foo",
        {"a": (int, Undefined), "b": (int, Undefined)},
        [TypeConverter(int, lookup)],
    )
    parsed = parse_obj_as(model, {"a": "c", "b": "d"})
    assert parsed.a == 2
    assert parsed.b == 3


def test_validates_multiple_fields_and_types() -> None:
    model = create_model_with_type_validators(
        "Foo",
        {
            "a": (int, Undefined),
            "b": (bool, Undefined),
            "c": (int, Undefined),
            "d": (bool, Undefined),
        },
        [TypeConverter(int, lookup), TypeConverter(bool, has_even_length)],
    )
    parsed = parse_obj_as(model, {"a": "c", "b": "hello", "c": "d", "d": "word"})
    assert parsed.a == 2
    assert parsed.b == False
    assert parsed.c == 3
    assert parsed.d == True


def test_does_not_tolerate_multiple_converters_for_same_type() -> None:
    with pytest.raises(TypeError):
        create_model_with_type_validators(
            "Foo",
            {"a": (int, Undefined), "b": (int, Undefined)},
            [TypeConverter(int, lookup), TypeConverter(int, int)],
        )


def test_validates_list_type() -> None:
    assert_validates_single_type(List[int], ["a", "b", "c"], [0, 1, 2])


def test_validates_set_type() -> None:
    assert_validates_single_type(Set[int], ["a", "b", "c"], {0, 1, 2})


def test_validates_tuple_type() -> None:
    assert_validates_single_type(Tuple[int, ...], ["a", "b", "c"], (0, 1, 2))


def test_validates_nested_container_type() -> None:
    assert_validates_single_type(
        List[Set[Tuple[int, int]]],
        [[["a", "b"], ["c", "d"]], [["e", "f"]]],
        [{(0, 1), (2, 3)}, {(4, 5)}],
    )


@pytest.mark.parametrize("dict_type", [Dict, Mapping])
def test_validates_dict_type(dict_type: Type) -> None:
    assert_validates_single_type(
        dict_type[str, int],
        {
            "a": "a",
            "b": "b",
            "c": "c",
        },
        {
            "a": 0,
            "b": 1,
            "c": 2,
        },
    )


def test_validates_nested_mapping() -> None:
    assert_validates_single_type(
        Dict[str, List[int]],
        {
            "a": ["a", "b"],
            "b": ["c", "d", "e"],
            "c": ["f"],
        },
        {
            "a": [0, 1],
            "b": [2, 3, 4],
            "c": [5],
        },
    )


def test_validates_complex_object() -> None:
    assert_validates_complex_object(ComplexObject, "d", ComplexObject("d"))


def test_validates_complex_object_list() -> None:
    assert_validates_complex_object(
        List[ComplexObject],
        ["a", "b", "c"],
        [
            ComplexObject("a"),
            ComplexObject("b"),
            ComplexObject("c"),
        ],
    )


def assert_validates_single_type(
    field_type: Type, input_value: Any, expected_output: Any
) -> None:
    model = create_model_with_type_validators(
        "Foo", {"ch": (field_type, Undefined)}, [TypeConverter(int, lookup)]
    )
    assert parse_obj_as(model, {"ch": input_value}).ch == expected_output


def assert_validates_complex_object(
    field_type: Type, input_value: Any, expected_output: Any
) -> None:
    model = create_model_with_type_validators(
        "Foo",
        {"obj": (field_type, Undefined)},
        [TypeConverter(ComplexObject, lookup_complex)],
    )
    assert parse_obj_as(model, {"obj": input_value}).obj == expected_output
