import pytest

from blueapi.utils.serialization import access_blob


@pytest.mark.parametrize(
    "input,output",
    [
        (
            "cm12345-1",
            '{"proposal": 12345, "instrument_session": 1, '
            '"instrument": "ixx", "proposal_category": "CM"}',
        ),
        (
            "cm12345-111",
            '{"proposal": 12345, "instrument_session": 111, '
            '"instrument": "ixx", "proposal_category": "CM"}',
        ),
        (
            "cv12345-1",
            '{"proposal": 12345, "instrument_session": 1, '
            '"instrument": "ixx", "proposal_category": "CV"}',
        ),
        (
            "cm12345678-1",
            '{"proposal": 12345678, "instrument_session": 1, '
            '"instrument": "ixx", "proposal_category": "CM"}',
        ),
        (
            "cm12345678-111",
            '{"proposal": 12345678, "instrument_session": 111, '
            '"instrument": "ixx", "proposal_category": "CM"}',
        ),
        (
            "cv12345678-111",
            '{"proposal": 12345678, "instrument_session": 111, '
            '"instrument": "ixx", "proposal_category": "CV"}',
        ),
    ],
)
def test_access_blob_regex(input: str, output: str):
    assert access_blob(input, instrument="ixx") == output


@pytest.mark.parametrize(
    "input",
    [
        "abc12345-1",
        "ab12345--1",
        "ab12345--1",
        "ab12345£1",
        "ab12345-1g",
        "ab12345g-1",
        "ab12g345-1",
    ],
)
def test_access_blob_regex_errors(input: str):
    with pytest.raises(
        ValueError,
        match="Unable to extract proposal and instrument session number from "
        f"instrument session {input}",
    ):
        access_blob(input, instrument="ixx")
