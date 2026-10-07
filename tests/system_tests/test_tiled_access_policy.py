"""
System tests for the Diamond tiled access policy (services/tiled_config/dls.py)
backed by the authorisation OPA policies.

Self contained (tiled, httpx and pytest only) so it can move to another repo.
Requires the system test services (tiled, keycloak, opa) to be running.

Users and service accounts, see services/startup.py and opa_data/data.json:
    alice: named on adsim session CM12345-1
    bob: named on adsim session CM12345-2
    admin: super admin
    tiled-writer: adsim service account, audience tiled_writer_raw
    tiled-writer-processed: adsim service account, audience tiled_writer_processed
    tiled-writer-i22: i22 service account, audience tiled_writer_raw
"""

import uuid
from collections.abc import Callable, Generator

import httpx
import pytest
from tiled.client import from_uri
from tiled.client.container import Container
from tiled.client.utils import ClientError

TILED_URL = "http://localhost:8407/api/v1"
TOKEN_URL = "http://localhost:8081/realms/master/protocol/openid-connect/token"

ALICE = "system-test-blueapi-alice"
BOB = "system-test-blueapi-bob"
ADMIN = "system-test-blueapi-admin"
RAW_WRITER = "tiled-writer"
PROCESSED_WRITER = "tiled-writer-processed"
I22_WRITER = "tiled-writer-i22"

SESSION_1 = ["adsim", "CM12345-1"]
SESSION_2 = ["adsim", "CM12345-2"]


class ClientCredentials(httpx.Auth):
    def __init__(self, client_id: str):
        self._client_id = client_id

    def auth_flow(
        self, request: httpx.Request
    ) -> Generator[httpx.Request, httpx.Response, None]:
        response = httpx.post(
            TOKEN_URL,
            data={
                "client_id": self._client_id,
                "client_secret": "secret",
                "grant_type": "client_credentials",
            },
        )
        response.raise_for_status()
        request.headers["Authorization"] = f"Bearer {response.json()['access_token']}"
        yield request


_clients: dict[str, Container] = {}


def tiled(client_id: str) -> Container:
    """A tiled client authenticated as client_id, closed when the tests finish"""
    if client_id not in _clients:
        _clients[client_id] = from_uri(TILED_URL, auth=ClientCredentials(client_id))  # type: ignore
    return _clients[client_id]


def path(client: Container, *keys: str) -> Container:
    node = client
    for key in keys:
        node = node[key]
    return node


def ensure(node: Container, key: str, tags: list[str]) -> Container:
    if key in node:
        return node[key]
    return node.create_container(key, access_tags=tags)


def new_key() -> str:
    return uuid.uuid4().hex


def assert_forbidden(action: Callable[[], object]):
    with pytest.raises(ClientError) as e:
        action()
    assert e.value.response.status_code == 403


@pytest.fixture(scope="module", autouse=True)
def catalog():
    """Build the tree the tests use, as the service accounts would"""
    for client_id, area in ((RAW_WRITER, "raw"), (PROCESSED_WRITER, "processed")):
        adsim = ensure(tiled(client_id), "adsim", ["adsim"])
        proposal = ensure(
            ensure(adsim, area, ["adsim"]), "CM12345", ["adsim", "CM12345"]
        )
        ensure(proposal, "1", SESSION_1)
        ensure(proposal, "2", SESSION_2)
    ensure(tiled(I22_WRITER), "i22", ["i22"])
    yield
    for client in _clients.values():
        client.context.close()
    _clients.clear()


# Creating the raw tree


def test_raw_writer_creates_run_in_session():
    session = path(tiled(RAW_WRITER), "adsim", "raw", "CM12345", "1")
    key = new_key()
    run = session.create_container(key, access_tags=SESSION_1)
    run.create_container("primary", access_tags=SESSION_1)
    assert run.access_blob == {"tags": SESSION_1}
    assert key in session


def test_admin_creates_run_in_session():
    session = path(tiled(ADMIN), "adsim", "raw", "CM12345", "2")
    session.create_container(new_key(), access_tags=SESSION_2)


@pytest.mark.parametrize(
    "keys,tags",
    [
        # instrument node must be tagged with the service account's instrument
        ((), ["i22"]),
        ((), ["adsim", "CM12345"]),
        # raw/processed nodes are tagged with just the instrument
        (("adsim",), ["i22"]),
        (("adsim",), ["adsim", "CM12345"]),
        # proposal nodes are tagged with the instrument and proposal
        (("adsim", "raw"), ["adsim"]),
        (("adsim", "raw"), ["adsim", "cm12345"]),
        (("adsim", "raw"), SESSION_1),
        (("adsim", "raw"), ["i22", "CM12345"]),
        # proposals must have a session on the instrument
        (("adsim", "raw"), ["adsim", "CM99999"]),
        # session nodes are tagged with a session of their proposal
        (("adsim", "raw", "CM12345"), ["adsim", "CM12345"]),
        (("adsim", "raw", "CM12345"), ["adsim", "CM54321-1"]),
        # everything under a session is tagged with that session
        (("adsim", "raw", "CM12345", "1"), SESSION_2),
        (("adsim", "raw", "CM12345", "1"), ["adsim"]),
        (("adsim", "raw", "CM12345", "1"), []),
    ],
)
def test_raw_writer_cannot_create_with_wrong_tags(keys: tuple[str], tags: list[str]):
    parent = path(tiled(RAW_WRITER), *keys)
    assert_forbidden(lambda: parent.create_container(new_key(), access_tags=tags))


def test_raw_session_must_exist():
    proposal = path(tiled(RAW_WRITER), "adsim", "raw", "CM12345")
    assert_forbidden(
        lambda: proposal.create_container("9", access_tags=["adsim", "CM12345-9"])
    )


@pytest.mark.parametrize("client_id", [ALICE, BOB, PROCESSED_WRITER])
def test_only_raw_writer_creates_raw_nodes(client_id: str):
    raw = path(tiled(client_id), "adsim", "raw")
    assert_forbidden(
        lambda: raw.create_container("CM12345", access_tags=["adsim", "CM12345"])
    )


@pytest.mark.parametrize("client_id", [ALICE, PROCESSED_WRITER])
def test_only_raw_writer_creates_in_session(client_id: str):
    session = path(tiled(client_id), "adsim", "raw", "CM12345", "1")
    assert_forbidden(lambda: session.create_container(new_key(), access_tags=SESSION_1))


@pytest.mark.parametrize("client_id", [ALICE, BOB])
def test_users_cannot_create_instruments(client_id: str):
    assert_forbidden(
        lambda: tiled(client_id).create_container("adsim2", access_tags=["adsim"])
    )


def test_other_instrument_writer_cannot_see_adsim():
    assert "adsim" not in tiled(I22_WRITER)
    assert_forbidden(
        lambda: tiled(I22_WRITER).create_container(new_key(), access_tags=["adsim"])
    )


def test_wrongly_keyed_node_is_hidden():
    # tiled does not tell the policy the key of a new node, so a node keyed
    # differently to its tags can be created, but is then not accessible
    proposal = path(tiled(RAW_WRITER), "adsim", "raw", "CM12345")
    key = new_key()
    proposal.create_container(key, access_tags=SESSION_1)
    with pytest.raises(KeyError):
        proposal[key]


# Reading


def test_admin_sees_everything():
    admin = tiled(ADMIN)
    assert {"adsim", "i22"} <= set(admin)
    assert {"1", "2"} <= set(path(admin, "adsim", "raw", "CM12345"))


@pytest.mark.parametrize("area", ["raw", "processed"])
@pytest.mark.parametrize(
    "client_id,visible,hidden",
    [(ALICE, "1", "2"), (BOB, "2", "1")],
)
def test_users_see_only_their_sessions(
    client_id: str, visible: str, hidden: str, area: str
):
    client = tiled(client_id)
    assert "adsim" in client
    assert "i22" not in client
    assert set(path(client, "adsim")) == {"raw", "processed"}
    assert "CM12345" in path(client, "adsim", area)
    proposal = path(client, "adsim", area, "CM12345")
    assert visible in proposal
    assert hidden not in proposal
    with pytest.raises(KeyError):
        proposal[hidden]


def test_user_reads_runs_in_their_session():
    key = new_key()
    path(tiled(RAW_WRITER), "adsim", "raw", "CM12345", "1").create_container(
        key, access_tags=SESSION_1
    )
    assert key in path(tiled(ALICE), "adsim", "raw", "CM12345", "1")
    with pytest.raises(KeyError):
        path(tiled(BOB), "adsim", "raw", "CM12345", "1", key)


def test_service_account_sees_its_instrument():
    assert "adsim" in tiled(RAW_WRITER)
    assert "adsim" in tiled(PROCESSED_WRITER)
    assert set(tiled(I22_WRITER)) == {"i22"}


# Writing to existing raw nodes


def test_raw_writer_updates_run_metadata():
    run = path(tiled(RAW_WRITER), "adsim", "raw", "CM12345", "1").create_container(
        new_key(), access_tags=SESSION_1
    )
    run.update_metadata(metadata={"stage": "done"})
    assert run.metadata["stage"] == "done"


def test_user_cannot_update_raw_metadata():
    key = new_key()
    path(tiled(RAW_WRITER), "adsim", "raw", "CM12345", "1").create_container(
        key, access_tags=SESSION_1
    )
    run = path(tiled(ALICE), "adsim", "raw", "CM12345", "1", key)
    assert_forbidden(lambda: run.update_metadata(metadata={"stage": "done"}))


def test_raw_writer_cannot_move_run_to_another_session():
    run = path(tiled(RAW_WRITER), "adsim", "raw", "CM12345", "1").create_container(
        new_key(), access_tags=SESSION_1
    )
    assert_forbidden(lambda: run.update_metadata(access_tags=SESSION_2))


# Processed data, laid out the same as raw


def test_processed_writer_creates_processed_nodes():
    session = path(tiled(PROCESSED_WRITER), "adsim", "processed", "CM12345", "1")
    key = new_key()
    session.create_container(key, access_tags=SESSION_1)
    assert key in path(tiled(ALICE), "adsim", "processed", "CM12345", "1")


@pytest.mark.parametrize(
    "keys,tags",
    [
        (("adsim", "processed"), SESSION_1),
        (("adsim", "processed"), ["adsim", "CM99999"]),
        (("adsim", "processed", "CM12345"), ["adsim", "CM12345"]),
        (("adsim", "processed", "CM12345", "1"), SESSION_2),
        (("adsim", "processed", "CM12345", "1"), ["adsim"]),
    ],
)
def test_processed_writer_cannot_create_with_wrong_tags(
    keys: tuple[str], tags: list[str]
):
    parent = path(tiled(PROCESSED_WRITER), *keys)
    assert_forbidden(lambda: parent.create_container(new_key(), access_tags=tags))


def test_raw_writer_cannot_create_processed_nodes():
    session = path(tiled(RAW_WRITER), "adsim", "processed", "CM12345", "1")
    assert_forbidden(lambda: session.create_container(new_key(), access_tags=SESSION_1))


def test_user_creates_processed_node_in_their_session():
    key = new_key()
    path(tiled(ALICE), "adsim", "processed", "CM12345", "1").create_container(
        key, access_tags=SESSION_1
    )
    assert key in path(tiled(ALICE), "adsim", "processed", "CM12345", "1")
    assert "1" not in path(tiled(BOB), "adsim", "processed", "CM12345")


def test_user_cannot_tag_processed_node_with_another_session():
    session = path(tiled(ALICE), "adsim", "processed", "CM12345", "1")
    assert_forbidden(lambda: session.create_container(new_key(), access_tags=SESSION_2))


def test_user_cannot_create_session_they_are_not_on():
    proposal = path(tiled(ALICE), "adsim", "processed", "CM12345")
    assert_forbidden(lambda: proposal.create_container("3", access_tags=SESSION_2))


def test_user_cannot_create_proposal_they_are_not_on():
    processed = path(tiled(ALICE), "adsim", "processed")
    assert_forbidden(
        lambda: processed.create_container("CM99999", access_tags=["adsim", "CM99999"])
    )


def test_user_cannot_write_raw_session_structure():
    proposal = path(tiled(ALICE), "adsim", "raw", "CM12345")
    assert_forbidden(lambda: proposal.create_container("3", access_tags=SESSION_1))
