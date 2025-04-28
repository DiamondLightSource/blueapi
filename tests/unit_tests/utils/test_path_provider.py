from pathlib import PosixPath

import pytest
from event_model.documents import RunStart
from ophyd_async.core import PathInfo

from blueapi.utils.path_provider import StartDocumentPathProvider


@pytest.fixture
def start_doc_default_template() -> dict:
    return {
        "uid": "27c48d2f-d8c6-4ac0-8146-fedf467ce11f",
        "time": 1741264729.96875,
        "versions": {"ophyd": "1.10.0", "bluesky": "1.13"},
        "data_session": "ab123",
        "instrument": "p01",
        "data_session_directory": "/p01/ab123",
        "scan_id": 22,
        "plan_type": "generator",
        "plan_name": "count",
        "detectors": ["det"],
        "num_points": 1,
        "num_intervals": 0,
        "plan_args": {
            "detectors": [
                "<ophyd_async.epics.adaravis._aravis.AravisDetector object at 0x7f74c02b8710>"  # NOQA: E501
            ],
            "num": 1,
            "delay": 0.0,
        },
        "hints": {"dimensions": [[["time"], "primary"]]},
        "shape": [1],
    }


def test_start_document_path_provider_with_default_template_returns_correct_path_info(
    start_doc_default_template: RunStart,
):
    pp = StartDocumentPathProvider()
    pp.update_run(name="start", start_doc=start_doc_default_template)
    path = pp("det")

    assert path == PathInfo(
        directory_path=PosixPath("/p01/ab123"),
        filename="det-p01-22",
        create_dir_depth=0,
    )


@pytest.fixture
def start_doc_custom_template() -> dict:
    return {
        "uid": "27c48d2f-d8c6-4ac0-8146-fedf467ce11f",
        "time": 1741264729.96875,
        "versions": {"ophyd": "1.10.0", "bluesky": "1.13"},
        "data_session": "ab123",
        "instrument": "p01",
        "data_session_directory": "/p01/ab123",
        "scan_id": 22,
        "data_file_path_template": "{device_name}-{instrument}-{scan_id}-custom",
        "plan_type": "generator",
        "plan_name": "count",
        "detectors": ["det"],
        "num_points": 1,
        "num_intervals": 0,
        "plan_args": {
            "detectors": [
                "<ophyd_async.epics.adaravis._aravis.AravisDetector object at 0x7f74c02b8710>"  # NOQA: E501
            ],
            "num": 1,
            "delay": 0.0,
        },
        "hints": {"dimensions": [[["time"], "primary"]]},
        "shape": [1],
    }


def test_start_document_path_provider_with_custom_template_returns_correct_path_info(
    start_doc_custom_template: RunStart,
):
    pp = StartDocumentPathProvider()
    pp.update_run(name="start", start_doc=start_doc_custom_template)
    path = pp("det")

    assert path == PathInfo(
        directory_path=PosixPath("/p01/ab123"),
        filename="det-p01-22-custom",
        create_dir_depth=0,
    )


@pytest.fixture
def start_doc_missing_instrument() -> dict:
    return {
        "uid": "27c48d2f-d8c6-4ac0-8146-fedf467ce11f",
        "time": 1741264729.96875,
        "versions": {"ophyd": "1.10.0", "bluesky": "1.13"},
        "data_session": "ab123",
        "data_session_directory": "/p01/ab123",
        "scan_id": 22,
        "plan_type": "generator",
        "plan_name": "count",
        "detectors": ["det"],
        "num_points": 1,
        "num_intervals": 0,
        "plan_args": {
            "detectors": [
                "<ophyd_async.epics.adaravis._aravis.AravisDetector object at 0x7f74c02b8710>"  # NOQA: E501
            ],
            "num": 1,
            "delay": 0.0,
        },
        "hints": {"dimensions": [[["time"], "primary"]]},
        "shape": [1],
    }


def test_start_document_path_provider_fails_with_missing_instrument(
    start_doc_missing_instrument: RunStart,
):
    pp = StartDocumentPathProvider()
    pp.update_run(name="start", start_doc=start_doc_missing_instrument)

    with pytest.raises(KeyError, match="'instrument'"):
        pp("det")


@pytest.fixture
def start_doc_missing_scan_id() -> dict:
    return {
        "uid": "27c48d2f-d8c6-4ac0-8146-fedf467ce11f",
        "time": 1741264729.96875,
        "versions": {"ophyd": "1.10.0", "bluesky": "1.13"},
        "data_session": "ab123",
        "instrument": "p01",
        "data_session_directory": "/p01/ab123",
        "plan_type": "generator",
        "plan_name": "count",
        "detectors": ["det"],
        "num_points": 1,
        "num_intervals": 0,
        "plan_args": {
            "detectors": [
                "<ophyd_async.epics.adaravis._aravis.AravisDetector object at 0x7f74c02b8710>"  # NOQA: E501
            ],
            "num": 1,
            "delay": 0.0,
        },
        "hints": {"dimensions": [[["time"], "primary"]]},
        "shape": [1],
    }


def test_start_document_path_provider_fails_with_missing_scan_id(
    start_doc_missing_scan_id: RunStart,
):
    pp = StartDocumentPathProvider()
    pp.update_run(name="start", start_doc=start_doc_missing_scan_id)

    with pytest.raises(KeyError, match="'scan_id'"):
        pp("det")


@pytest.fixture
def start_doc_default_data_session_directory() -> dict:
    return {
        "uid": "27c48d2f-d8c6-4ac0-8146-fedf467ce11f",
        "time": 1741264729.96875,
        "versions": {"ophyd": "1.10.0", "bluesky": "1.13"},
        "data_session": "ab123",
        "instrument": "p01",
        "scan_id": 22,
        "plan_type": "generator",
        "plan_name": "count",
        "detectors": ["det"],
        "num_points": 1,
        "num_intervals": 0,
        "plan_args": {
            "detectors": [
                "<ophyd_async.epics.adaravis._aravis.AravisDetector object at 0x7f74c02b8710>"  # NOQA: E501
            ],
            "num": 1,
            "delay": 0.0,
        },
        "hints": {"dimensions": [[["time"], "primary"]]},
        "shape": [1],
    }


def test_start_document_path_provider_sets_data_session_directory_default_to_tmp(
    start_doc_default_data_session_directory: RunStart,
):
    pp = StartDocumentPathProvider()
    pp.update_run(name="start", start_doc=start_doc_default_data_session_directory)
    path = pp("det")

    assert path == PathInfo(
        directory_path=PosixPath("/tmp"), filename="det-p01-22", create_dir_depth=0
    )


def test_start_document_path_provider_update_called_with_different_document_skips(
    start_doc_default_template: RunStart,
):
    pp = StartDocumentPathProvider()
    pp.update_run(name="descriptor", start_doc=start_doc_default_template)

    assert pp._doc == {}
