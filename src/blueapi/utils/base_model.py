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
    """

    Config = BlueapiModelConfig
