from collections.abc import Mapping as AbcMapping
from dataclasses import dataclass
from inspect import Parameter, isclass, signature
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Generic,
    Iterable,
    List,
    Mapping,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    get_args,
    overload,
)

from pydantic import BaseConfig, BaseModel, create_model, validator
from pydantic.fields import Undefined

if TYPE_CHECKING:
    from pydantic.typing import AnyCallable, AnyClassMethod
else:
    AnyCallable, AnyClassMethod = Any, Any


_PYDANTIC_LIST_TYPES: List[Type] = [List, Tuple, Set]  # type: ignore
_PYDANTIC_DICT_TYPES: List[Type] = [Dict, Mapping]

T = TypeVar("T")
U = TypeVar("U")
FieldDefinition = Tuple[Type, Any]
Fields = Mapping[str, FieldDefinition]
Validator = Union[Callable[[AnyCallable], AnyClassMethod], classmethod]


@dataclass
class TypeValidatorDefinition(Generic[T]):
    """
    Definition of a validator to be applied to all
    types during validation.

    Args:
        field_type: Convert all fields of this type
        func: Convert using this function
    """

    field_type: Type[T]
    func: Callable[[Any], T]

    def __str__(self) -> str:
        type_name = getattr(
            self.field_type, "__name__", str(hash(str(self.field_type)))
        )
        return f"converter_{type_name}"


@overload
def create_model_with_type_validators(
    name: str,
    definitions: List[TypeValidatorDefinition],
    *,
    fields: Fields,
    config: Optional[Type[BaseConfig]] = None,
) -> Type[BaseModel]:
    """
    Create a model based on the fields supplied

    Args:
        name: Name of the new model
        definitions: Definitions of how to validate which types of field
        fields: Definitions of fields from which to make the model.
        config: Pydantic config for the model. Defaults to None.

    Returns:
        Type[BaseModel]: A new pydantic model with the fields and
            type validators supplied.
    """

    ...


@overload
def create_model_with_type_validators(
    name: str,
    definitions: List[TypeValidatorDefinition],
    *,
    func: Callable[..., Any],
    config: Optional[Type[BaseConfig]] = None,
) -> Type[BaseModel]:
    """
    Create a model from a function's parameters with type
    validators.

    Args:
        name: Name of the new model
        definitions: Definitions of how to validate which types of field
        func: The model is constructed from the function parameters,
            which must be type-annotated.
        config: Pydantic config for the model. Defaults to None.

    Returns:
        Type[BaseModel]: A new pydantic model based on the
            function parameters.
    """

    ...


@overload
def create_model_with_type_validators(
    name: str,
    definitions: List[TypeValidatorDefinition],
    *,
    base: Type[BaseModel],
) -> Type[BaseModel]:
    """
    Apply type validators to an existing model

    Args:
        name: Name of the new model
        definitions: Definitions of how to validate which types of field
        base: Base class for the model

    Returns:
        Type[BaseModel]: A new version of `base` with type validators
    """

    ...


def create_model_with_type_validators(
    name: str,
    definitions: List[TypeValidatorDefinition],
    *,
    fields: Optional[Fields] = None,
    base: Optional[Type[BaseModel]] = None,
    func: Optional[Callable[..., Any]] = None,
    config: Optional[Type[BaseConfig]] = None,
) -> Type[BaseModel]:
    """
    Create a pydantic model with type validators according to
    definitions given. Validators are applied to all fields
    of a particular type.

    Args:
        name: Name of the new model
        definitions: Definitions of how to validate which types of field
        fields: Definitions of fields from which to make the model.
            Defaults to None.
        base: Optional base class for the model. Defaults to None.
        func: Function, if supplied, the model is constructed from the
            function parameters, which must be type-annotated.
            Defaults to None.
        config: Pydantic config for the model. Defaults to None.

    Returns:
        Type[BaseModel]: A new pydantic model
    """

    # Fields are determined from various sources, directly passed, a base class
    # and/or a function signature.
    all_fields = {**(fields or {})}
    if base is not None:
        all_fields = {**all_fields, **_extract_fields_from_model(base)}
    if func is not None:
        all_fields = {**all_fields, **_extract_fields_from_function(func)}
    for name, field in all_fields.items():
        annotation, val = field
        all_fields[name] = apply_type_validators(annotation, definitions), val

    validators = _type_validators(all_fields, definitions)
    return create_model(  # type: ignore
        name, **all_fields, __base__=base, __validators__=validators, __config__=config
    )


def apply_type_validators(
    model_type: Type,
    definitions: List[TypeValidatorDefinition],
) -> Type:
    """
    Create a copy of a model (or modellable type) that has the defined
    type validators.

    Args:
        model_type: The model to copy (e.g. a BaseModel or pydantic dataclass)
        definitions: Definitions of type validators that the copy should have

    Returns:
        Type: A new pydantic model
    """

    if isclass(model_type) and issubclass(model_type, BaseModel):
        if "__root__" in model_type.__fields__:
            return apply_type_validators(
                model_type.__fields__["__root__"].type_,
                definitions,
            )
        else:
            return create_model_with_type_validators(
                model_type.__name__,
                definitions,
                base=model_type,
            )
    elif isclass(model_type) and hasattr(model_type, "__pydantic_model__"):
        model = getattr(model_type, "__pydantic_model__")
        # Recursively apply to inner model
        return apply_type_validators(
            model,
            definitions,
        )
    else:
        # Apply to type parameters, e.g. apply to int in List[int]
        params = [
            apply_type_validators(
                param,
                definitions,
            )
            for param in get_args(model_type)
        ]

        # __origin__ converts Union[int, str] to Union
        if params and hasattr(model_type, "__origin__"):
            origin = getattr(model_type, "__origin__")
            # Certain origins are different to their code notations,
            # e.g. list vs List.
            origin = _sanitise_origin(origin)
            return origin[tuple(params)]
    return model_type


def _sanitise_origin(origin: Type) -> Type:
    return {  # type: ignore
        list: List,
        set: Set,
        tuple: Tuple,
        AbcMapping: Mapping,
        dict: Mapping,
    }.get(origin, origin)


def _extract_fields_from_model(model: Type[BaseModel]) -> Fields:
    return {
        name: (field.type_, field.field_info)
        for name, field in model.__fields__.items()
    }


def _extract_fields_from_function(func: Callable[..., Any]) -> Fields:
    fields: Dict[str, FieldDefinition] = {}
    for name, param in signature(func).parameters.items():
        type_annotation = param.annotation
        if type_annotation is Parameter.empty:
            raise TypeError(f"Missing type annotation for parameter {name}")
        default_value = param.default
        if default_value is Parameter.empty:
            default_value = Undefined

        anno = (type_annotation, default_value)
        fields[name] = anno

    return fields


def _type_validators(
    fields: Fields,
    definitions: Iterable[TypeValidatorDefinition],
) -> Mapping[str, Validator]:
    """
    Generate type validators from fields and definitions.

    Args:
        fields: fields to validate.
        definitions: Definitions of how to validate which types of field

    Raises:
        TypeError: If a validator can be applied to more than one field.

    Returns:
        Mapping[str, Validator]: Dict-like structure mapping validator
            names to pydantic validators.
    """

    all_validators = {}

    for definition in definitions:
        field_names = _determine_fields_of_type(fields, definition.field_type)
        for name in field_names:
            val = _make_type_validator(name, definition)
            val_method_name = f"validate_{name}"
            if val_method_name in all_validators:
                raise TypeError(f"Ambiguous type validator for field: {name}")
            all_validators[val_method_name] = val

    return all_validators


def _make_type_validator(name: str, definition: TypeValidatorDefinition) -> Validator:
    def validate_type(value: Any) -> Any:
        return apply_to_scalars(definition.func, value)

    return validator(name, allow_reuse=True, pre=True, always=True)(validate_type)


def _determine_fields_of_type(fields: Fields, field_type: Type) -> Iterable[str]:
    for name, field in fields.items():
        annotation, _ = field
        if is_type_or_container_type(annotation, field_type):
            yield name


def is_type_or_container_type(type_to_check: Type, field_type: Type) -> bool:
    """
    Is the supplied type either the type to check against or a type that
    contains it?
    For example, if field_type=int, then this should return True if type_to_check
    is int, List[int], Dict[str, int], Set[int] etc.

    Args:
        type_to_check: The type to check
        field_type: The expected type

    Returns:
        bool: True if the types match
    """
    return params_contains(type_to_check, field_type)


def params_contains(type_to_check: Type, field_type: Type) -> bool:
    """
    Do the parameters of a type contain the type to check?
    For example, do the parameters of List[int] conain int? Yes

    Args:
        type_to_check: The type to check
        field_type: The expected type

    Returns:
        bool: True if the types match
    """

    type_params = get_args(type_to_check)
    return type_to_check is field_type or any(
        map(lambda v: params_contains(v, field_type), type_params)
    )


def apply_to_scalars(func: Callable[[T], U], obj: Any) -> Any:
    """
    Apply the supplied function to all scalars within the JSON-serializable
    object. In this case, scalars are values of type int, str, float, and bool.
    For example, if the function multiplies by 2 and the object is:
    {"a": 3, "b": [4, 5]} then the result should be {"a": 6, "b": [8, 10]}

    Args:
        func: The function to apply.
        obj: An object that can be serialized to JSON

    Returns:
        Any: A new JSON-serializable object with the function
            applied to all scalars.
    """

    if is_list_type(obj):
        return list(map(lambda v: apply_to_scalars(func, v), obj))
    elif is_dict_type(obj):
        return {k: apply_to_scalars(func, v) for k, v in obj.items()}
    else:
        return func(obj)


def is_list_type(obj: Any) -> bool:
    return any(map(lambda t: isinstance(obj, t), _PYDANTIC_LIST_TYPES))


def is_dict_type(obj: Any) -> bool:
    return any(map(lambda t: isinstance(obj, t), _PYDANTIC_DICT_TYPES))


def find_model_type(anno: Type) -> Optional[Type[BaseModel]]:
    if isclass(anno):
        if issubclass(anno, BaseModel):
            return anno
        elif hasattr(anno, "__pydantic_model__"):
            return getattr(anno, "__pydantic_model__")
    return None
