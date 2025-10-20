from pathlib import PosixPath

import pytest
from event_model import RunStart, RunStop
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
    pp.run_start(name="start", start_document=start_doc_default_template)
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
    pp.run_start(name="start", start_document=start_doc_custom_template)
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
    pp.run_start(name="start", start_document=start_doc_missing_instrument)

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
    pp.run_start(name="start", start_document=start_doc_missing_scan_id)

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
    pp.run_start(name="start", start_document=start_doc_default_data_session_directory)
    path = pp("det")

    assert path == PathInfo(
        directory_path=PosixPath("/tmp"), filename="det-p01-22", create_dir_depth=0
    )


@pytest.fixture
def stop_doc_default_template() -> dict:
    return {
        "name": "stop",
        "doc": {
            "run_start": "27c48d2f-d8c6-4ac0-8146-fedf467ce11f",
            "time": 1741264732.96875,
            "uid": "401ad197-5456-4a7d-ba5b-9cf8ad38d914",
            "exit_status": "success",
            "reason": "",
            "num_events": {"primary": 1},
        },
    }


def test_start_document_path_provider_run_start_called_with_different_document_skips(
    stop_doc_default_template: RunStop,
):
    pp = StartDocumentPathProvider()
    pp.run_start(name="stop", start_document=stop_doc_default_template)  # type: ignore

    assert pp._doc is None


def test_start_document_path_provider_run_stop_called_with_different_document_skips(
    start_doc_default_template: RunStart,
):
    pp = StartDocumentPathProvider()
    pp.run_stop(name="start", stop_document=start_doc_default_template)  # type: ignore

    assert pp._doc is None


@pytest.fixture
def start_doc() -> dict:
    return {
        "uid": "fa2feced-4098-4c0e-869d-285d2a69c24a",
        "time": 1690463918.3893268,
        "versions": {"ophyd": "1.10.0", "bluesky": "1.13"},
        "data_session": "ab123",
        "instrument": "p02",
        "data_session_directory": "/p02/ab123",
        "scan_id": 50,
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


@pytest.fixture
def stop_doc() -> dict:
    return {
        "name": "stop",
        "doc": {
            "run_start": "fa2feced-4098-4c0e-869d-285d2a69c24a",
            "time": 1690463920.3893268,
            "uid": "401ad197-5456-4a7d-ba5b-9cf8ad38d914",
            "exit_status": "success",
            "reason": "",
            "num_events": {"primary": 1},
        },
    }


def test_start_document_path_provider_start_doc_persists_until_stop_with_matching_id(
    start_doc: RunStart,
    stop_doc: RunStop,
    start_doc_default_template: RunStart,
    stop_doc_default_template: RunStop,
):
    pp = StartDocumentPathProvider()
    pp.run_start(name="start", start_document=start_doc)

    assert pp._doc == start_doc
    assert pp._doc["uid"] == "fa2feced-4098-4c0e-869d-285d2a69c24a"  # type: ignore

    pp.run_start(name="start", start_document=start_doc_default_template)
    assert pp._doc == start_doc
    assert pp._doc["uid"] == "fa2feced-4098-4c0e-869d-285d2a69c24a"  # type: ignore

    pp.run_stop(name="stop", stop_document=stop_doc_default_template)
    assert pp._doc == start_doc
    assert pp._doc["uid"] == "fa2feced-4098-4c0e-869d-285d2a69c24a"  # type: ignore

    pp.run_stop(name="stop", stop_document=stop_doc)
    assert pp._doc is None


def test_start_document_path_provider_nested_runs_use_parent_run_info(
    start_doc_default_template: RunStart,
    stop_doc_default_template: RunStop,
    start_doc: RunStart,
    stop_doc: RunStop,
):
    pp = StartDocumentPathProvider()
    pp.run_start(name="start", start_document=start_doc_default_template)
    parent_path_info = pp("det")

    assert pp._doc == start_doc_default_template
    assert pp._doc["uid"] == "27c48d2f-d8c6-4ac0-8146-fedf467ce11f"  # type: ignore
    assert parent_path_info == PathInfo(
        directory_path=PosixPath("/p01/ab123"),
        filename="det-p01-22",
        create_dir_depth=0,
    )

    pp.run_start(name="start", start_document=start_doc)
    assert pp._doc == start_doc_default_template
    assert pp._doc["uid"] == "27c48d2f-d8c6-4ac0-8146-fedf467ce11f"  # type: ignore

    assert pp("det") == parent_path_info

    pp.run_stop(name="stop", stop_document=stop_doc)
    assert pp._doc == start_doc_default_template
    assert pp._doc["uid"] == "27c48d2f-d8c6-4ac0-8146-fedf467ce11f"  # type: ignore

    assert pp("det") == parent_path_info

    pp.run_stop(name="stop", stop_document=stop_doc_default_template)
    assert pp._doc is None


def test_start_document_path_provider_called_without_start_raises():
    pp = StartDocumentPathProvider()
    with pytest.raises(
        AttributeError,
        match="Start document not found. This call must be made inside a run.",
    ):
        pp("det")
