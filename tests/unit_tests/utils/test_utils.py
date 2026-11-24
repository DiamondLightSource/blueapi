import logging
from unittest.mock import Mock, call

import pytest
from pydantic import BaseModel, Field

from blueapi.utils import InvalidConfigError, report_successful_devices, serialize


class Model(BaseModel):
    snake_case: int = Field(alias="snakeCase")


class HasPydanticModel:
    __pydantic_model__ = Model(snakeCase=1)


@pytest.mark.parametrize("obj", [4, "a", None, [1, 2], {"a": 1}])
def test_serialize_passes_through_primitives(obj):
    assert serialize(obj) is obj


def test_serialize_model_by_alias():
    assert serialize(Model(snakeCase=1)) == {"snakeCase": 1}


def test_serialize_object_with_pydantic_model():
    assert serialize(HasPydanticModel()) == {"snakeCase": 1}


@pytest.mark.parametrize("sim, suffix", [(True, " (sim mode)"), (False, "")])
def test_report_successful_devices(sim: bool, suffix: str):
    logger = Mock(spec=logging.Logger)
    report_successful_devices({"b": 1, "a": 2}, sim, logger)
    assert logger.info.call_args_list == [
        call(f"2 devices connected{suffix}:"),
        call("\ta\n\tb"),
    ]


def test_invalid_config_error_messages():
    assert str(InvalidConfigError()) == "Configuration is invalid"
    assert str(InvalidConfigError("bad")) == "bad"
