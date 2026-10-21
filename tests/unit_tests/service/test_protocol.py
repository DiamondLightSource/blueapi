from typing import Any

import pytest

from blueapi.service.model import TaskRequestV1, TaskRequestV2
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
from blueapi.worker import TaskParametersV2
from blueapi.worker.task import InvalidTaskParameter, TaskParameterError


@pytest.mark.parametrize(
    "src,res",
    [
        pytest.param(
            """{
                "kind": "submit",
                "task": {
                    "name": "foo",
                    "instrument_session": "cm12345-1"
                }
            }""",
            Submit(
                task=TaskRequestV2(
                    name="foo",
                    params=TaskParametersV2(),
                    instrument_session="cm12345-1",
                )
            ),
            id="submit-v2",
        ),
        pytest.param(
            """{
                "kind": "submit",
                "task": {
                    "name": "foo",
                    "params": {"one": "two"},
                    "instrument_session": "cm12345-1"
                }
            }""",
            Submit(
                task=TaskRequestV1(
                    name="foo",
                    params={"one": "two"},
                    instrument_session="cm12345-1",
                )
            ),
            id="submit-v1",
        ),
        pytest.param('{"kind": "pause"}', Pause(), id="pause"),
        pytest.param('{"kind": "resume"}', Resume(), id="resume"),
        pytest.param('{"kind": "abort"}', Abort(), id="abort"),
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


def test_from_empty_parameter_error():
    err = InvalidArgs.from_parameter_error(
        TaskParameterError("Error validating request", [])
    )
    assert err == InvalidArgs(errors=[])


def test_from_parameter_error():
    err = InvalidArgs.from_parameter_error(
        TaskParameterError(
            "Error validating request",
            [
                InvalidTaskParameter(
                    msg="foo.bar is missing",
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
                msg="foo.bar is missing",
                type="missing",
                input={"foo": {"no": "bar"}},
            )
        ]
    )
