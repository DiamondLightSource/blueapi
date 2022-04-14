from dataclasses import make_dataclass
from inspect import Parameter, signature
from typing import Any, Callable, Iterable, List, Optional, Tuple, Type, TypeVar, Union

from apischema import deserialize
from apischema.conversions.conversions import Conversion
from apischema.conversions.converters import AnyConversion, default_deserialization


def schema_for_func(func: Callable[..., Any]) -> Type:
    """
    Generate a dataclass that acts as a schema for validation with apischema.
    Inspect the parameters, default values and type annotations of a function and
    generate the schema.

    Example:

    def foo(a: int, b: str, c: bool):
        ...

    schema = schema_for_func(foo)

    Schema is the runtime equivalent of:

    @dataclass
    class fooo_params:
        a: int
        b: str
        c: bool

    Args:
        func (Callable[..., Any]): The source function, all parameters must have type
                                   annotations

    Raises:
        TypeError: If a type annotation is either `Any` or not supplied

    Returns:
        Type: A runtime dataclass whose fields encapsulate the names, types and default
             values of the function parameters
    """

    class_name = f"{func.__name__}_params"
    fields: List[Union[Tuple[str, Type, Any], Tuple[str, Type]]] = []

    # Iterate through parameters and convert them to dataclass fields
    for name, param in signature(func).parameters.items():
        a_type = param.annotation
        # Do not allow parameters without type annotations or with the `Any` annotation
        if a_type is Parameter.empty:
            raise TypeError(
                f"Error serializing function {func.__name__}, all parameters must have "
                "a type annotation"
            )
        elif a_type is Any:
            raise TypeError(
                f"Error serializing function {func.__name__} parameter {name} all "
                "parameters cannot have `Any` as a type annotation"
            )

        default_value = param.default

        # Include the default value in the field if there is onee
        if default_value is not Parameter.empty:
            fields.append((name, a_type, default_value))
        else:
            fields.append((name, a_type))

    data_class = make_dataclass(class_name, fields)
    return data_class


T = TypeVar("T")


def nested_deserialize_with_overrides(
    schema: Type[T], obj: Any, overrides: Optional[Iterable[Conversion]] = None
) -> T:
    """
    Deserialize a dictionary using apischema with custom overrides. Unlike apischema's
    built-in override argument, this propagates the overrides to nested dictionaries.

    Args:
        schema (Type[T]): Type to deserialize to
        obj (Any): Raw object to deserialize, usually a dictionary
        overrides (Optional[Iterable[Conversion]], optional): apischema conversions to
                                                              customize deserialization.
                                                              Defaults to None.

    Returns:
        T: Deserialized object
    """

    conversions = {conversion.target: conversion for conversion in overrides or []}

    def deserialize_with_converters(a_type: Type[Any]) -> Optional[AnyConversion]:
        # If the type is in _conversions then we can override the function used to
        # resolve the parameter, otherwise we use apischema's default deserializer
        if a_type in conversions.keys():
            return conversions[a_type]
        return default_deserialization(a_type)

    return deserialize(schema, obj, default_conversion=deserialize_with_converters)
