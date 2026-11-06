import pytest

from blueapi.utils.serialization import access_blob


@pytest.mark.parametrize(
    "input,output",
    [
        (
            "cm12345-1",
            {"instrument": "ixx", "instrument_session": "cm12345-1", "folder": "raw"},
        ),
        (
            "cm12345-111",
            {"instrument": "ixx", "instrument_session": "cm12345-111", "folder": "raw"},
        ),
        (
            "cv12345-1",
            {"instrument": "ixx", "instrument_session": "cv12345-1", "folder": "raw"},
        ),
        (
            "cm12345678-1",
            {
                "instrument": "ixx",
                "instrument_session": "cm12345678-1",
                "folder": "raw",
            },
        ),
        (
            "cm12345678-111",
            {
                "instrument": "ixx",
                "instrument_session": "cm12345678-111",
                "folder": "raw",
            },
        ),
        (
            "cv12345678-111",
            {
                "instrument": "ixx",
                "instrument_session": "cv12345678-111",
                "folder": "raw",
            },
        ),
    ],
)
def test_access_blob_regex(input: str, output: dict):
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
        match=f"Unable to extract proposal and visit from instrument session {input}",
    ):
        access_blob(input, instrument="ixx")


@pytest.mark.parametrize("folder", ["raw", "processed", "processing"])
def test_access_blob_folder(folder):
    assert access_blob("cm12345-1", "ixx", folder) == {
        "instrument": "ixx",
        "instrument_session": "cm12345-1",
        "folder": folder,
    }
