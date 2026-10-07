import pytest

from blueapi.utils.serialization import tiled_session_path


@pytest.mark.parametrize(
    "input,proposal,session",
    [
        ("cm12345-1", "CM12345", "1"),
        ("cm12345-111", "CM12345", "111"),
        ("cv12345-1", "CV12345", "1"),
        ("cm12345678-111", "CM12345678", "111"),
    ],
)
def test_tiled_session_path(input: str, proposal: str, session: str):
    assert tiled_session_path(input, instrument="ixx") == [
        ("ixx", ["ixx"]),
        ("raw", ["ixx"]),
        (proposal, ["ixx", proposal]),
        (session, ["ixx", f"{proposal}-{session}"]),
    ]


@pytest.mark.parametrize(
    "input",
    [
        "abc12345-1",
        "ab12345--1",
        "ab12345£1",
        "ab12345-1g",
        "ab12345g-1",
        "ab12g345-1",
    ],
)
def test_tiled_session_path_errors(input: str):
    with pytest.raises(
        ValueError,
        match="Unable to extract proposal and instrument session number from "
        f"instrument session {input}",
    ):
        tiled_session_path(input, instrument="ixx")
