from typing import Any

import pytest

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
