import time
from collections.abc import Generator, Mapping
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import yaml
from playwright.sync_api import sync_playwright
from tests.system_tests.test_blueapi_system import (
    _DATA_PATH,
    VALID_INSTRUMENT_SESSION,
    User,
)

from blueapi.client import BlueapiClient
from blueapi.client.client import MissingInstrumentSessionError
from blueapi.client.device_cache import DeviceRef
from blueapi.client.event_bus import AnyEvent
from blueapi.client.plan_cache import Plan
from blueapi.client.rest import ServiceUnavailableError, UnauthorisedAccessError
from blueapi.config import ApplicationConfig
from blueapi.core.bluesky_types import DataEvent
from blueapi.service.model import TaskRequest
from blueapi.worker.event import WorkerEvent, WorkerState

# Tests for the BlueapiClient as a user would drive it: built from a config
# file, logged in through the OIDC device flow, plans run as methods.


def browser_login(url: str, user: User):
    """Complete the Keycloak device flow login page as the given user"""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url)
        page.fill("#username", user.value)
        page.fill("#password", user.value)
        page.click("#kc-login")
        # Keycloak always asks for consent on device grants
        page.click("#kc-login")
        page.wait_for_selector("text=Device Login Successful")
        browser.close()


def login(token_path: Path, user: User) -> BlueapiClient:
    """Log in via device flow and return a client built from config file"""
    config_file = token_path.parent / "config.yaml"
    config = yaml.safe_load((_DATA_PATH / "config-cli.yaml").read_text())
    config["auth_token_path"] = str(token_path)
    config_file.write_text(yaml.dump(config))

    with patch(
        "blueapi.service.authentication.webbrowser.open_new_tab",
        side_effect=lambda url: browser_login(url, user),
    ):
        BlueapiClient.from_config_file(str(config_file)).login(token_path)

    # New client should pick up the cached token without logging in again
    return BlueapiClient.from_config_file(str(config_file))


@pytest.fixture(scope="module", autouse=True)
def wait_for_server():
    client = BlueapiClient.from_config(ApplicationConfig())
    for _ in range(20):
        try:
            _ = client.oidc_config
            return
        except ServiceUnavailableError:
            time.sleep(0.5)
    raise TimeoutError("No connection to the blueapi server")


@pytest.fixture(scope="module")
def bc(tmp_path_factory) -> BlueapiClient:
    client = login(tmp_path_factory.mktemp("alice") / "token", User.alice)
    client.instrument_session = VALID_INSTRUMENT_SESSION[User.alice]
    return client


@pytest.fixture(autouse=True)
def idle_worker(bc: BlueapiClient) -> Generator[None]:
    yield
    if bc.state != WorkerState.IDLE:
        bc.abort()


def test_login_caches_token(tmp_path: Path):
    token = tmp_path / "token"
    client = login(token, User.bob)
    assert token.exists()
    assert client._rest.session_manager is not None
    assert client.state == WorkerState.IDLE


def test_logout_removes_token(tmp_path: Path):
    token = tmp_path / "token"
    client = login(token, User.bob)
    client.logout()
    assert not token.exists()
    assert client._rest.session_manager is None
    with pytest.raises(UnauthorisedAccessError):
        _ = client.state


def test_from_config_file_without_login(tmp_path: Path):
    config = yaml.safe_load((_DATA_PATH / "config-cli.yaml").read_text())
    config["auth_token_path"] = str(tmp_path / "missing")
    (tmp_path / "config.yaml").write_text(yaml.dump(config))
    client = BlueapiClient.from_config_file(str(tmp_path / "config.yaml"))
    assert client.oidc_config is not None
    with pytest.raises(UnauthorisedAccessError):
        _ = client.devices


def test_oidc_config(bc: BlueapiClient):
    assert bc.oidc_config is not None
    assert bc.oidc_config.client_id == "ixx-cli-blueapi"


def test_environment(bc: BlueapiClient):
    assert bc.environment.initialized
    assert bc.environment.error_message is None


def test_state(bc: BlueapiClient):
    assert bc.state == WorkerState.IDLE


def test_instrument_session_required_to_run_plans(tmp_path: Path):
    client = login(tmp_path / "token", User.alice)
    with pytest.raises(MissingInstrumentSessionError):
        _ = client.instrument_session
    with pytest.raises(MissingInstrumentSessionError):
        client.plans.sleep(0)


def test_with_instrument_session(bc: BlueapiClient):
    session = bc.instrument_session
    assert bc.with_instrument_session(session) is bc


def test_devices_iterable(bc: BlueapiClient):
    names = {dev.name for dev in bc.devices}
    assert {"det", "stage"} <= names
    for dev in bc.devices:
        assert isinstance(dev, DeviceRef)
        assert dev.model.name == dev.name
        assert dev.model.protocols


def test_devices_as_attributes(bc: BlueapiClient):
    assert bc.devices.det is bc.devices["det"]
    assert repr(bc.devices.stage) == "Device(stage)"


def test_sub_device(bc: BlueapiClient):
    stage_x = bc.devices.stage.x
    assert isinstance(stage_x, DeviceRef)
    assert stage_x.name == "stage.x"
    assert stage_x.model.name == "stage-x"


def test_missing_sub_device(bc: BlueapiClient):
    with pytest.raises(AttributeError, match="No device named 'det.x' available"):
        _ = bc.devices.det.x


def test_plans_iterable(bc: BlueapiClient):
    names = {plan.name for plan in bc.plans}
    assert {
        "list_rscan",
        "rel_set",
        "step_rscan",
        "sleep",
        "list_scan",
        "mv",
        "step_scan",
        "abs_set",
        "list_grid_scan",
        "list_grid_rscan",
        "count",
        "step_grid_rscan",
        "mvr",
        "rd",
        "spec_scan",
        "num_grid_scan",
        "wait",
        "num_scan",
        "num_grid_rscan",
        "num_rscan",
        "step_grid_scan",
        "stop",
    } <= names
    assert all(isinstance(plan, Plan) for plan in bc.plans)


def test_plan_docs_and_signature(bc: BlueapiClient):
    count = bc.plans.count
    assert count.__doc__ == count.model.description
    assert count.__doc__
    assert str(count).startswith("count(")
    for arg in ("detectors", "num", "delay", "metadata"):
        assert arg in str(count)
    assert count.required == ["detectors"]


def test_plans_and_devices_are_cached(bc: BlueapiClient):
    assert bc.plans is bc.plans
    assert bc.devices is bc.devices


@pytest.mark.parametrize(
    "a,kw,err",
    [
        (("det",), {"detectors": ["det"]}, "multiple values for argument 'detectors'"),
        (("det",), {"foo": "bar"}, "got an unexpected keyword argument 'foo'"),
        ((("det",), 2, 3, 4, 5), {}, "too many positional arguments"),
        ((), {}, "Missing value for 'detectors'"),
    ],
)
def test_plan_argument_errors(bc: BlueapiClient, a, kw, err: str):
    with pytest.raises(TypeError, match=err):
        bc.plans.count(*a, **kw)


def _record_events(bc: BlueapiClient) -> tuple[list[AnyEvent], int]:
    events: list[AnyEvent] = []
    return events, bc.add_callback(events.append)


def _start_doc(events: list[AnyEvent]) -> Mapping[str, Any]:
    return next(e.doc for e in events if isinstance(e, DataEvent) and e.name == "start")


def test_run_plan_positional_args(bc: BlueapiClient):
    events, cb = _record_events(bc)
    try:
        bc.plans.count([bc.devices.det, bc.devices.stage.x], 3)
    finally:
        bc.remove_callback(cb)
    start = _start_doc(events)
    assert start["scan_file"] == f"adsim-{start['scan_id']}"
    assert start["num_points"] == 3
    assert start["detectors"] == ["det", "stage-x"]
    assert start["instrument_session"] == VALID_INSTRUMENT_SESSION[User.alice]


def test_run_plan_keyword_args(bc: BlueapiClient):
    events, cb = _record_events(bc)
    try:
        bc.plans.count(detectors=[bc.devices.det], num=2, delay=0.1)
    finally:
        bc.remove_callback(cb)
    start = _start_doc(events)
    assert start["scan_file"] == f"adsim-{start['scan_id']}"
    assert start["num_points"] == 2


def test_run_stub_with_device(bc: BlueapiClient):
    bc.plans.abs_set(bc.devices.stage.x, 1.0)


def test_removed_callback_not_called(bc: BlueapiClient):
    events, cb = _record_events(bc)
    bc.remove_callback(cb)
    bc.plans.sleep(0)
    assert events == []


def test_run_task_with_task_request(bc: BlueapiClient):
    status = bc.run_task(
        TaskRequest(
            name="sleep",
            params={"time": 0},
            instrument_session=bc.instrument_session,
        )
    )
    assert status.task_complete
    assert not status.task_failed


def test_active_task_while_running(bc: BlueapiClient):
    response = bc.create_and_start_task(
        TaskRequest(
            name="sleep",
            params={"time": 2},
            instrument_session=bc.instrument_session,
        )
    )
    assert bc.state == WorkerState.RUNNING
    assert bc.active_task.task_id == response.task_id


# Pause and resume are currently broken on the server, re-enable once fixed
# See https://github.com/DiamondLightSource/blueapi/issues/1420
# def _start_sleep(bc: BlueapiClient):
#     return bc.create_and_start_task(
#         TaskRequest(
#             name="sleep",
#             params={"time": 2},
#             instrument_session=bc.instrument_session,
#         )
#     )


# def _wait_for_idle(bc: BlueapiClient):
#     while bc.state != WorkerState.IDLE:
#         time.sleep(0.1)


# def test_pause_and_resume(bc: BlueapiClient):
#     _start_sleep(bc)
#     assert bc.pause() == WorkerState.PAUSED
#     assert bc.state == WorkerState.PAUSED
#     assert bc.resume() != WorkerState.RUNNING
#     _wait_for_idle(bc)


# def test_pause_and_stop(bc: BlueapiClient):
#     _start_sleep(bc)
#     assert bc.pause() == WorkerState.PAUSED
#     bc.stop()
#     _wait_for_idle(bc)


def test_reload_environment_clears_caches(bc: BlueapiClient):
    plans, devices = bc.plans, bc.devices
    old_env = bc.environment
    new_env = bc.reload_environment()
    assert new_env.environment_id != old_env.environment_id
    assert bc.plans is not plans
    assert bc.devices is not devices
    assert {p.name for p in bc.plans} == {p.name for p in plans}


def test_callbacks_receive_worker_events(bc: BlueapiClient):
    events, cb = _record_events(bc)
    try:
        bc.plans.sleep(0)
    finally:
        bc.remove_callback(cb)
    assert any(isinstance(e, WorkerEvent) and e.is_complete() for e in events)
