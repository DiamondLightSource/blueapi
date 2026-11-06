"""Who may read and write each folder of a visit in tiled, as decided by the
central authorisation service's diamond.tiled rules:

    adsim/                  "adsim"
      cm12345-1/            "adsim,cm12345-1"
        raw/                "adsim,cm12345-1"      tiled-writer
        processed/          "adsim,cm12345-1,p"    processing-tiled-writer
        processing/         "adsim,cm12345-1,t"    anyone on the visit
"""

import json
import uuid
from collections.abc import Generator

import httpx
import pytest
import requests
from tiled.client import from_uri
from tiled.client.utils import ClientError

TILED_URL = "http://localhost:8407/api/v1"
TOKEN_URL = "http://localhost:8081/realms/master/protocol/openid-connect/token"
INSTRUMENT = "adsim"
VISIT = "cm12345-1"  # alice is on it, bob is not
FOLDERS = ("raw", "processed", "processing")


def token(client_id: str) -> str:
    response = requests.post(
        TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": "secret",
            "grant_type": "client_credentials",
        },
    )
    response.raise_for_status()
    return response.json()["access_token"]


class BearerAuth(httpx.Auth):
    def __init__(self, token: str):
        self._token = token

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request]:
        request.headers["Authorization"] = f"Bearer {self._token}"
        yield request


_clients = {}


def tiled_as(client_id: str):
    """A tiled client for this Keycloak client, closed at the end of the module."""
    if client_id not in _clients:
        # An auth object, not headers, or the client asks for an interactive login
        _clients[client_id] = from_uri(TILED_URL, auth=BearerAuth(token(client_id)))
    return _clients[client_id]


def access_tags(node) -> set[str]:
    # tiled clients before 0.2.19 only have access_blob
    if (tags := getattr(node, "access_tags", None)) is not None:
        return set(tags)
    return set(node.access_blob["tags"])


def blob(**fields: str) -> list[str]:
    return [json.dumps(fields)]


def get_or_create(client, key: str, access_tags: list[str]):
    try:
        return client.create_container(key=key, access_tags=access_tags)
    except ClientError as e:
        if e.response.status_code != 409:
            raise
        return client[key]


@pytest.fixture(scope="module", autouse=True)
def close_clients():
    yield
    for client in _clients.values():
        client.context.close()
    _clients.clear()


@pytest.fixture(scope="module", autouse=True)
def visit_folders(close_clients):
    """The tree blueapi creates for a visit's first task."""
    writer = tiled_as("tiled-writer")
    instrument = get_or_create(writer, INSTRUMENT, blob(instrument=INSTRUMENT))
    visit = get_or_create(
        instrument, VISIT, blob(instrument=INSTRUMENT, instrument_session=VISIT)
    )
    for folder in FOLDERS:
        get_or_create(
            visit,
            folder,
            blob(instrument=INSTRUMENT, instrument_session=VISIT, folder=folder),
        )


def folder_path(folder: str) -> str:
    return f"{INSTRUMENT}/{VISIT}/{folder}"


def new_node_tags(folder: str) -> list[str]:
    return blob(instrument=INSTRUMENT, instrument_session=VISIT, folder=folder)


@pytest.mark.parametrize(
    "folder,tag",
    [
        ("raw", "adsim,cm12345-1"),
        ("processed", "adsim,cm12345-1,p"),
        ("processing", "adsim,cm12345-1,t"),
    ],
)
def test_folders_tagged(folder: str, tag: str):
    node = tiled_as("system-test-blueapi-alice")[folder_path(folder)]
    assert access_tags(node) == {tag}


def test_user_on_visit_can_write_processing():
    alice = tiled_as("system-test-blueapi-alice")
    key = f"alice-{uuid.uuid4()}"

    alice[folder_path("processing")].create_container(
        key=key, access_tags=new_node_tags("processing")
    )

    assert key in alice[folder_path("processing")]


@pytest.mark.parametrize("folder", ["raw", "processed"])
def test_user_on_visit_cannot_write_raw_or_processed(folder: str):
    alice = tiled_as("system-test-blueapi-alice")

    with pytest.raises(ClientError):
        alice[folder_path(folder)].create_container(
            key=f"alice-{uuid.uuid4()}", access_tags=new_node_tags(folder)
        )


def test_user_off_visit_cannot_see_it():
    bob = tiled_as("system-test-blueapi-bob")

    with pytest.raises(KeyError):
        bob[f"{INSTRUMENT}/{VISIT}"]


def test_processing_writer_writes_processed_and_users_read_it():
    processing = tiled_as("processing-tiled-writer")
    key = f"processed-{uuid.uuid4()}"

    processing[folder_path("processed")].create_container(
        key=key, access_tags=new_node_tags("processed")
    )

    alice = tiled_as("system-test-blueapi-alice")
    assert key in alice[folder_path("processed")]


def test_raw_writer_cannot_write_processed():
    writer = tiled_as("tiled-writer")

    with pytest.raises(ClientError):
        writer[folder_path("processed")].create_container(
            key=f"raw-{uuid.uuid4()}", access_tags=new_node_tags("processed")
        )


# Envoy routes on the instrument in the path, so tags have to match the path


def test_instrument_node_must_be_named_after_instrument():
    writer = tiled_as("tiled-writer")

    with pytest.raises(ClientError) as e:
        writer.create_container(
            key=f"not-{INSTRUMENT}", access_tags=blob(instrument=INSTRUMENT)
        )
    assert e.value.response.status_code == 403


def test_visit_node_must_be_named_after_visit():
    writer = tiled_as("tiled-writer")

    with pytest.raises(ClientError) as e:
        writer[INSTRUMENT].create_container(
            key="cm12345-2",
            access_tags=blob(instrument=INSTRUMENT, instrument_session=VISIT),
        )
    assert e.value.response.status_code == 403


def test_visit_has_only_the_three_folders():
    writer = tiled_as("tiled-writer")

    with pytest.raises(ClientError) as e:
        writer[f"{INSTRUMENT}/{VISIT}"].create_container(
            key="elsewhere", access_tags=new_node_tags("raw")
        )
    assert e.value.response.status_code == 403


def test_node_takes_its_folders_tag():
    # The raw writer may write in processing, but not with raw's tag there
    writer = tiled_as("tiled-writer")

    with pytest.raises(ClientError) as e:
        writer[folder_path("processing")].create_container(
            key=f"raw-{uuid.uuid4()}", access_tags=new_node_tags("raw")
        )
    assert e.value.response.status_code == 403
