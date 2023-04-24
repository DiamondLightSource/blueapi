from pydantic import BaseConfig, BaseModel, Extra


def _to_camel(string: str) -> str:
    words = string.split("_")
    return words[0] + "".join(word.capitalize() for word in words[1:])


class BlueapiModelConfig(BaseConfig):
    """
    Pydantic config for blueapi API models with
    common config.
    """

    alias_generator = _to_camel
    extra = Extra.forbid
    allow_population_by_field_name = True


class BlueapiPlanModelConfig(BlueapiModelConfig):
    """
    Pydantic config for plan parameters.
    Includes arbitrary type config so that devices
    can be parameters.
    """

    arbitrary_types_allowed = True


class BlueapiBaseModel(BaseModel):
    """
    Base class for blueapi API models.
    Includes common config.

    Previously, with apischema, the API models
    were serialized with camel case aliasing.
    For example, converting a Python field
    called foo_bar to a JSON field called fooBar
    and vice versa. This is to comply with the
    Google JSON style guide.
    https://google.github.io/styleguide/jsoncstyleguide.xml?showone=Property_Name_Format#Property_Name_Format

    We have a custom base model with custom config
    primarily to preserve this change and also
    to prevent the ingestion of arbirtrary JSON
    alongside a model's known fields, which
    apischema also did not allow.
    """

    Config = BlueapiModelConfig
