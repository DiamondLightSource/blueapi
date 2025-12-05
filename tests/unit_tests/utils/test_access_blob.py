import pytest

from blueapi.utils.serialization import access_blob


@pytest.mark.parametrize(
    "instrument_session,output",
    [
        (
            "cm12345-1",
            '{"proposal": 12345, "visit": 1, "beamline": "ixx"}',
        ),
        (
            "cm12345-111",
            '{"proposal": 12345, "visit": 111, "beamline": "ixx"}',
        ),
        (
            "cv12345-1",
            '{"proposal": 12345, "visit": 1, "beamline": "ixx"}',
        ),
        (
            "cm12345678-1",
            '{"proposal": 12345678, "visit": 1, "beamline": "ixx"}',
        ),
        (
            "cm12345678-111",
            '{"proposal": 12345678, "visit": 111, "beamline": "ixx"}',
        ),
        (
            "cv12345678-111",
            '{"proposal": 12345678, "visit": 111, "beamline": "ixx"}',
        ),
    ],
)
def test_access_blob_regex(instrument_session: str, output: str):
    assert access_blob(instrument_session, beamline="ixx") == output


@pytest.mark.parametrize(
    "instrument_session",
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
def test_access_blob_regex_errors(instrument_session: str):
    with pytest.raises(
        ValueError,
        match=f"Unable to extract proposal and visit from instrument session \
            {instrument_session}",
    ):
        access_blob(instrument_session, beamline="ixx")
