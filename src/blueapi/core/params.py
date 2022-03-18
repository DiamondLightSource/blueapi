from dataclasses import make_dataclass
from inspect import Parameter, signature
from typing import Any, Callable, List, Tuple, Type, Union


def schema_for_func(func: Callable[..., Any]) -> Type:
    """
    Generate a dataclass that acts as a schema for validation with apischema.
    Inspect the parameters, default values and type annotations of a function and
    generate the schema.

    :param func: The source function, all parameters must have type annotations
    :return: A runtime dataclass whose fields encapsulate the names, types and default
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
