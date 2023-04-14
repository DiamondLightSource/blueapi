from typing import Any, Dict, List, Literal, Mapping, Optional, Set, Tuple, Type, Union

import pytest
from pydantic import BaseConfig, BaseModel, Field, parse_obj_as
from pydantic.dataclasses import dataclass
from pydantic.fields import Undefined
from scanspec.regions import Circle
from scanspec.specs import Line, Spec

from blueapi.utils import TypeValidatorDefinition, create_model_with_type_validators


class DefaultConfig(BaseConfig):
    arbitrary_types_allowed = True


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


class SpecWrapper(BaseModel):
    spec: Spec


def spec_wrapper(spec: Spec) -> None:
    ...


class Bar(BaseModel):
    a: int
    b: ComplexObject
    type: Literal["Bar"] = Field(default="Bar")

    class Config:
        arbitrary_types_allowed = True


class Baz(BaseModel):
    obj: Bar
    c: str
    type: Literal["Baz"] = Field(default="Baz")


class ComplexLinkedList(BaseModel):
    obj: ComplexObject
    child: Optional["ComplexLinkedList"] = None

    class Config:
        arbitrary_types_allowed = True


@dataclass(config=DefaultConfig)
class DataclassBar:
    a: int
    b: ComplexObject


@dataclass
class DataclassBaz:
    obj: DataclassBar
    c: str


@dataclass
class DataclassMixed:
    obj: Bar
    c: str


def foo(a: int, b: str) -> None:
    ...


def bar(obj: ComplexObject) -> None:
    ...


def baz(bar: Bar) -> None:
    ...


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
        [TypeValidatorDefinition(int, lookup)],
        fields={"a": (int, Undefined), "b": (str, Undefined)},
    )
    parsed = parse_obj_as(model, {"a": "c", "b": "hello"})
    assert parsed.a == 2  # type: ignore
    assert parsed.b == "hello"  # type: ignore


def test_validates_multiple_types() -> None:
    model = create_model_with_type_validators(
        "Foo",
        [
            TypeValidatorDefinition(int, lookup),
            TypeValidatorDefinition(bool, has_even_length),
        ],
        fields={"a": (int, Undefined), "b": (bool, Undefined)},
    )
    parsed = parse_obj_as(model, {"a": "c", "b": "hello"})
    assert parsed.a == 2  # type: ignore
    assert parsed.b is False  # type: ignore


def test_validates_multiple_fields() -> None:
    model = create_model_with_type_validators(
        "Foo",
        [TypeValidatorDefinition(int, lookup)],
        fields={"a": (int, Undefined), "b": (int, Undefined)},
    )
    parsed = parse_obj_as(model, {"a": "c", "b": "d"})
    assert parsed.a == 2  # type: ignore
    assert parsed.b == 3  # type: ignore


def test_validates_multiple_fields_and_types() -> None:
    model = create_model_with_type_validators(
        "Foo",
        [
            TypeValidatorDefinition(int, lookup),
            TypeValidatorDefinition(bool, has_even_length),
        ],
        fields={
            "a": (int, Undefined),
            "b": (bool, Undefined),
            "c": (int, Undefined),
            "d": (bool, Undefined),
        },
    )
    parsed = parse_obj_as(model, {"a": "c", "b": "hello", "c": "d", "d": "word"})
    assert parsed.a == 2  # type: ignore
    assert parsed.b is False  # type: ignore
    assert parsed.c == 3  # type: ignore
    assert parsed.d is True  # type: ignore


def test_does_not_tolerate_multiple_converters_for_same_type() -> None:
    with pytest.raises(TypeError):
        create_model_with_type_validators(
            "Foo",
            [TypeValidatorDefinition(int, lookup), TypeValidatorDefinition(int, int)],
            fields={"a": (int, Undefined), "b": (int, Undefined)},
        )


def test_validates_list_type() -> None:
    assert_validates_single_type(List[int], ["a", "b", "c"], [0, 1, 2])


def test_validates_set_type() -> None:
    assert_validates_single_type(Set[int], ["a", "b", "c"], {0, 1, 2})


def test_validates_tuple_type() -> None:
    assert_validates_single_type(
        Tuple[int, ...],  # type: ignore
        [
            "a",
            "b",
            "c",
        ],
        (0, 1, 2),
    )


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


def test_applies_to_base() -> None:
    model = create_model_with_type_validators(
        "Foo",
        [TypeValidatorDefinition(ComplexObject, lookup_complex)],
        base=Bar,
    )
    parsed = parse_obj_as(model, {"a": 2, "b": "g"})
    assert parsed.a == 2  # type: ignore
    assert parsed.b == ComplexObject("g")  # type: ignore


def test_applies_to_nested_base() -> None:
    model = create_model_with_type_validators(
        "Foo",
        [TypeValidatorDefinition(ComplexObject, lookup_complex)],
        base=Baz,
    )
    parsed = parse_obj_as(model, {"obj": {"a": 2, "b": "g"}, "c": "hello"})
    assert parsed.obj.a == 2  # type: ignore
    assert parsed.obj.b == ComplexObject("g")  # type: ignore
    assert parsed.c == "hello"  # type: ignore


def test_validates_submodel() -> None:
    model = create_model_with_type_validators(
        "Foo",
        [TypeValidatorDefinition(ComplexObject, lookup_complex)],
        fields={"obj": (Bar, Undefined)},
    )
    parsed = parse_obj_as(
        model,
        {
            "obj": {
                "a": 2,
                "b": "g",
            },
        },
    )
    assert parsed.obj.a == 2  # type: ignore
    assert parsed.obj.b == ComplexObject("g")  # type: ignore


def test_validates_nested_submodel() -> None:
    model = create_model_with_type_validators(
        "Foo",
        [TypeValidatorDefinition(ComplexObject, lookup_complex)],
        fields={"obj": (Baz, Undefined)},
    )
    parsed = parse_obj_as(
        model,
        {
            "obj": {
                "obj": {
                    "a": 2,
                    "b": "g",
                },
                "c": "hello",
            }
        },
    )
    assert parsed.obj.obj.a == 2  # type: ignore
    assert parsed.obj.obj.b == ComplexObject("g")  # type: ignore
    assert parsed.obj.c == "hello"  # type: ignore


def test_validates_dataclass() -> None:
    model = create_model_with_type_validators(
        "Foo",
        [TypeValidatorDefinition(ComplexObject, lookup_complex)],
        fields={"obj": (DataclassBar, Undefined)},
    )
    parsed = parse_obj_as(
        model,
        {
            "obj": {
                "a": 2,
                "b": "g",
            },
        },
    )
    assert parsed.obj.a == 2  # type: ignore
    assert parsed.obj.b == ComplexObject("g")  # type: ignore


def test_validates_nested_dataclass() -> None:
    model = create_model_with_type_validators(
        "Foo",
        [TypeValidatorDefinition(ComplexObject, lookup_complex)],
        fields={"obj": (DataclassBaz, Undefined)},
    )
    parsed = parse_obj_as(
        model,
        {
            "obj": {
                "obj": {
                    "a": 2,
                    "b": "g",
                },
                "c": "hello",
            }
        },
    )
    assert parsed.obj.obj.a == 2  # type: ignore
    assert parsed.obj.obj.b == ComplexObject("g")  # type: ignore
    assert parsed.obj.c == "hello"  # type: ignore


def test_validates_mixed_dataclass() -> None:
    model = create_model_with_type_validators(
        "Foo",
        [TypeValidatorDefinition(ComplexObject, lookup_complex)],
        fields={"obj": (DataclassMixed, Undefined)},
    )
    parsed = parse_obj_as(
        model,
        {
            "obj": {
                "obj": {
                    "a": 2,
                    "b": "g",
                },
                "c": "hello",
            }
        },
    )
    assert parsed.obj.obj.a == 2  # type: ignore
    assert parsed.obj.obj.b == ComplexObject("g")  # type: ignore
    assert parsed.obj.c == "hello"  # type: ignore


def test_validates_default_value() -> None:
    model = create_model_with_type_validators(
        "Foo",
        [TypeValidatorDefinition(int, lookup)],
        fields={"a": (int, "e")},
        config=DefaultConfig,
    )
    assert parse_obj_as(model, {}).a == 4  # type: ignore


def test_validates_complex_value() -> None:
    model = create_model_with_type_validators(
        "Foo",
        [TypeValidatorDefinition(ComplexObject, lookup_complex)],
        fields={"obj": (ComplexObject, "t")},
        config=DefaultConfig,
    )
    assert parse_obj_as(model, {}).obj == ComplexObject("t")  # type: ignore


def test_validates_field_info() -> None:
    model = create_model_with_type_validators(
        "Foo",
        [TypeValidatorDefinition(int, lookup)],
        fields={"a": (int, Field(default="f"))},
        config=DefaultConfig,
    )
    assert parse_obj_as(model, {}).a == 5  # type: ignore


SPECS = [
    Line("x", 0.0, 10.0, 10),
    Line("x", 0.0, 10.0, 10) * Line("y", 0.0, 10.0, 10),
    (Line("x", 0.0, 10.0, 10) * Line("y", 0.0, 10.0, 10))
    & Circle("x", "y", 1.0, 2.8, radius=0.5),
]


@pytest.mark.parametrize("spec", SPECS)
def test_validates_scanspec(spec: Spec) -> None:
    assert parse_spec(spec).spec == spec  # type: ignore


@pytest.mark.parametrize("spec", SPECS)
def test_validates_scanspec_wrapper(spec: Spec) -> None:
    model = create_model_with_type_validators(
        "Foo",
        [TypeValidatorDefinition(ComplexObject, lookup_complex)],
        fields={"wrapper": (SpecWrapper, Undefined)},
    )
    parsed = parse_obj_as(model, {"wrapper": {"spec": spec.serialize()}})
    assert parsed.wrapper.spec == spec  # type: ignore


@pytest.mark.parametrize("spec", SPECS)
def test_validates_scanspec_wrapping_function(spec: Spec) -> None:
    model = create_model_with_type_validators(
        "Foo",
        [TypeValidatorDefinition(ComplexObject, lookup_complex)],
        func=spec_wrapper,
    )
    parsed = parse_obj_as(model, {"spec": spec.serialize()})
    assert parsed.spec == spec  # type: ignore


def lookup_union(value: Union[int, str]) -> int:
    if isinstance(value, str):
        return lookup(value)
    else:
        return value


@pytest.mark.parametrize("value,expected", [(4, 4), ("b", 1)])
def test_validates_union(value: Union[int, str], expected: int) -> None:
    model = create_model_with_type_validators(
        "Foo",
        [TypeValidatorDefinition(Union[int, str], lookup_union)],  # type: ignore
        fields={"un": (Union[int, str], Undefined)},  # type: ignore
        config=DefaultConfig,
    )
    parsed = parse_obj_as(model, {"un": value})
    assert parsed.un == expected  # type: ignore


def test_validates_model_union() -> None:
    model = create_model_with_type_validators(
        "Foo",
        [TypeValidatorDefinition(ComplexObject, lookup_complex)],  # type: ignore
        fields={
            "un": (  # type: ignore
                Union[Bar, Baz],
                Field(..., discriminator="type"),
            )
        },
        config=DefaultConfig,
    )
    parsed = parse_obj_as(model, {"un": {"a": 5, "b": "g", "type": "Bar"}})
    assert parsed.un == Bar(a=5, b=ComplexObject("g"))  # type: ignore


def test_model_from_simple_function_signature() -> None:
    model = create_model_with_type_validators(
        "Foo", [TypeValidatorDefinition(int, lookup)], func=foo
    )
    parsed = parse_obj_as(model, {"a": "g", "b": "hello"})
    assert parsed.a == 6  # type: ignore
    assert parsed.b == "hello"  # type: ignore


def test_model_from_complex_function_signature() -> None:
    model = create_model_with_type_validators(
        "Foo",
        [TypeValidatorDefinition(ComplexObject, lookup_complex)],
        func=bar,
        config=DefaultConfig,
    )
    parsed = parse_obj_as(model, {"obj": "f"})
    assert parsed.obj == ComplexObject("f")  # type: ignore


def test_model_from_nested_function_signature() -> None:
    model = create_model_with_type_validators(
        "Foo",
        [TypeValidatorDefinition(ComplexObject, lookup_complex)],
        func=baz,
        config=DefaultConfig,
    )
    parsed = parse_obj_as(model, {"bar": {"a": 4, "b": "k"}})
    assert parsed.bar.a == 4  # type: ignore
    assert parsed.bar.b == ComplexObject("k")  # type: ignore


def parse_spec(spec: Spec) -> Any:
    model = create_model_with_type_validators(
        "Foo",
        [TypeValidatorDefinition(ComplexObject, lookup_complex)],
        fields={"spec": (Spec, Undefined)},
    )
    return parse_obj_as(model, {"spec": spec.serialize()})


def assert_validates_single_type(
    field_type: Type, input_value: Any, expected_output: Any
) -> None:
    model = create_model_with_type_validators(
        "Foo",
        [TypeValidatorDefinition(int, lookup)],
        fields={"ch": (field_type, Undefined)},
    )
    parsed = parse_obj_as(model, {"ch": input_value})
    assert parsed.ch == expected_output  # type: ignore


def assert_validates_complex_object(
    field_type: Type,
    input_value: Any,
    expected_output: Any,
    default_value: Any = Undefined,
) -> None:
    model = create_model_with_type_validators(
        "Foo",
        [TypeValidatorDefinition(ComplexObject, lookup_complex)],
        fields={"obj": (field_type, default_value)},
        config=DefaultConfig,
    )
    parsed = parse_obj_as(model, {"obj": input_value})
    assert parsed.obj == expected_output  # type: ignore
