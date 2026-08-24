from typing import Any

import pytest
from pydantic import ValidationError
from pydantic_core import InitErrorDetails

from blueapi.service.model import TaskRequest
from blueapi.service.protocol import (
    Abort,
    ArgumentError,
    ControlRequest,
    ControlResponse,
    InvalidArgs,
    Pause,
    Resume,
    Submit,
)


@pytest.mark.parametrize(
    "src,res",
    [
        (
            """{
                "kind": "submit",
                "task": {
                    "name": "foo",
                    "instrument_session": "cm12345-1"
                }
            }""",
            Submit(
                task=TaskRequest(name="foo", params={}, instrument_session="cm12345-1")
            ),
        ),
        ('{"kind": "pause"}', Pause()),
        ('{"kind": "resume"}', Resume()),
        ('{"kind": "abort"}', Abort()),
    ],
)
def test_request_deserialization(src: str, res: Any):
    req = ControlRequest.validate_json(src)
    assert req == res


@pytest.mark.parametrize(
    "src,res",
    [
        (
            """{
                "kind": "invalid_args",
                "errors":[{
                    "loc":["body","params","spec"],
                     "msg":"error_message",
                     "type":"error_type",
                     "input":"original input"
                 }]}""",
            InvalidArgs(
                errors=[
                    ArgumentError(
                        loc=["body", "params", "spec"],
                        msg="error_message",
                        type="error_type",
                        input="original input",
                    )
                ]
            ),
        ),
    ],
)
def test_response_deserialization(src: str, res: Any):
    req = ControlResponse.validate_json(src)
    assert req == res


def test_from_empty_validation_error():
    err = InvalidArgs.from_validation_error(
        ValidationError("Error validating request", [])
    )
    assert err == InvalidArgs(errors=[])


def test_from_validation_error():
    err = InvalidArgs.from_validation_error(
        ValidationError.from_exception_data(
            title="Error validating request",
            line_errors=[
                InitErrorDetails(
                    loc=("foo", "bar"),
                    type="missing",
                    input={"foo": {"no": "bar"}},
                )
            ],
        ),
    )
    assert err == InvalidArgs(
        errors=[
            ArgumentError(
                loc=["body", "params", "foo", "bar"],
                msg="Field required",
                type="missing",
                input={"foo": {"no": "bar"}},
            )
        ]
    )
