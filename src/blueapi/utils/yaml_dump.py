from pathlib import Path
from typing import Mapping, Union

import orjson
import yaml
from pydantic import BaseModel
from pyparsing import Any


def write_as_yaml(location: Path, data: Union[Mapping[str, Any], BaseModel]) -> None:
    """
    Serialize the input data to YAML and save it to a file

    Args:
        location: The destination file path
        data: Either a dictionary or a pydantic model
    """

    dict_data = _serialize(data)
    with open(location, "w") as stream:
        yaml.dump(dict_data, stream)


def print_as_yaml(data: Union[Mapping[str, Any], BaseModel]) -> None:
    """
    Serialize the input data to YAML and print it to the console.

    Args:
        data: Either a dictionary or a pydantic model
    """

    dict_data = _serialize(data)
    print(yaml.safe_dump(dict_data))


def _serialize(data: Union[Mapping[str, Any], BaseModel]) -> Mapping[str, Any]:
    if isinstance(data, BaseModel):
        # This is annoying, we have to convert the model to a JSON string and then back
        # into a dictionary rather than directly calling .dict() because unserializable
        # objects such as Paths make it into the dict that way. This is resolved in
        # pydantic 2, see:
        # https://stackoverflow.com/questions/65622045/pydantic-convert-to-jsonable-dict-not-full-json-string
        return orjson.loads(data.json())
    else:
        return data
