"""Services for the system tests.

The EPICS IOCs and gateways come from the example-services compose project. The
blueapi side runs as testcontainers that share one network namespace, like a k8s
pod: they all see each other on localhost, so the OIDC issuer
(http://localhost:8081/realms/master) is the same URL inside the containers and
on the host. The pod joins the EPICS compose network to reach the IOCs.

Run standalone for local development (without the blueapi server):
    uv run python -m tests.system_tests.stack [command to run once it is up]
"""

import subprocess
import sys
import time
import tomllib
from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path

import docker
import requests
from docker.types import Ulimit
from testcontainers.compose import DockerCompose
from testcontainers.core.container import DockerContainer

HERE = Path(__file__).parent
SERVICES = HERE / "services"
ROOT = HERE.parent.parent
LOGS = HERE / "logs"

BLUEAPI_IMAGE = "blueapi-system-test"

# Published on the host at the same port the service uses inside the pod
PORTS = [
    1883,  # rabbitmq mqtt
    5672,  # rabbitmq amqp
    15672,  # rabbitmq dashboard
    61613,  # rabbitmq stomp
    8081,  # keycloak
    8406,  # numtracker
    8407,  # tiled
    8181,  # opa
    8000,  # blueapi
    4180,  # blueapi oauth2-proxy
    4181,  # tiled oauth2-proxy
]


def _wait_http(url: str, container: DockerContainer, timeout: float = 120) -> None:
    """Wait until url answers with a non-5xx response, failing fast if the
    container dies"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        container.reload()
        if container.status == "exited":
            raise RuntimeError(f"{container.image} exited, see {LOGS}")
        try:
            if requests.get(url, timeout=5).status_code < 500:
                return
        except requests.RequestException:
            pass
        time.sleep(2)
    raise TimeoutError(f"{container.image} not ready at {url} after {timeout}s")


def _dodal_version() -> str:
    lock = tomllib.loads((ROOT / "uv.lock").read_text())
    return next(p["version"] for p in lock["package"] if p["name"] == "dls-dodal")


@contextmanager
def services(blueapi: bool = True) -> Iterator[Callable[[], None]]:
    """Start the services, yielding a function that writes their logs to LOGS.
    Logs are also written if startup fails."""
    containers: dict[str, DockerContainer] = {}

    def dump_logs() -> None:
        LOGS.mkdir(exist_ok=True)
        stdout, stderr = compose.get_logs()
        (LOGS / "epics.log").write_text(stdout + stderr)
        for name, container in containers.items():
            stdout, stderr = container.get_logs()
            (LOGS / f"{name}.log").write_bytes(stdout + stderr)

    with ExitStack() as stack:
        build = None
        if blueapi:
            # docker build rather than the SDK: the Dockerfile needs BuildKit.
            # Started first as it is the slowest step.
            build = subprocess.Popen(
                ["docker", "build", "--target", "runtime", "-t", BLUEAPI_IMAGE, ROOT]
            )
            stack.callback(build.wait)
            stack.callback(build.kill)

        compose = stack.enter_context(
            DockerCompose(HERE, "compose.yaml", profiles=["test"], wait=False)
        )
        try:
            client = docker.from_env()
            gateway = client.containers.get("ca-gateway")
            epics_network = next(iter(gateway.attrs["NetworkSettings"]["Networks"]))
            # Talk to the IOCs directly: on this network a broadcast also finds
            # ca-gateway, so every PV would be served twice
            ioc_addresses = " ".join(
                ioc.attrs["NetworkSettings"]["Networks"][epics_network]["IPAddress"]
                for ioc in client.containers.list(
                    filters={"label": "is_ioc=true", "network": epics_network}
                )
            )

            def start(name: str, container: DockerContainer) -> DockerContainer:
                containers[name] = stack.enter_context(container)
                return container

            pod = DockerContainer("registry.k8s.io/pause:3.10").with_kwargs(
                network=epics_network, security_opt=["label=disable"]
            )
            # Set directly as with_bind_ports cannot bind to localhost only
            pod.ports = {port: ("127.0.0.1", port) for port in PORTS}  # type: ignore
            start("pod", pod)

            def container(image: str, **kwargs) -> DockerContainer:
                return DockerContainer(image).with_kwargs(
                    network_mode=f"container:{pod.get_wrapped_container().id}",
                    # Stops testcontainers adding its own network when run in a
                    # container, which docker rejects alongside network_mode
                    network=None,
                    security_opt=["label=disable"],
                    **kwargs,
                )

            rabbitmq = start(
                "rabbitmq",
                container("docker.io/rabbitmq:4.0-management").with_volume_mapping(
                    SERVICES / "rabbitmq_plugins", "/etc/rabbitmq/enabled_plugins"
                ),
            )
            keycloak = start(
                "keycloak",
                container("keycloak/keycloak:26.4")
                .with_envs(
                    KC_BOOTSTRAP_ADMIN_USERNAME="admin",
                    KC_BOOTSTRAP_ADMIN_PASSWORD="admin",
                    KC_HOSTNAME="http://localhost:8081",
                    KC_HTTP_PORT="8081",
                )
                .with_command("start-dev"),
            )
            opa = start(
                "opa",
                container(
                    "openpolicyagent/opa:1.21.2-static-debug",
                    entrypoint=["sh", "/mnt/entrypoint.sh"],
                )
                .with_volume_mapping(SERVICES / "opa_config", "/mnt")
                .with_env("ISSUER", "http://localhost:8081/realms/master"),
            )
            numtracker = start(
                "numtracker",
                container("ghcr.io/diamondlightsource/numtracker:1.0.2").with_envs(
                    NUMTRACKER_AUTH_HOST="http://localhost:8181",
                    NUMTRACKER_PORT="8406",
                    NUMTRACKER_LOG_LEVEL="info",
                    NUMTRACKER_AUTH_ACCESS="v1/data/diamond/policy/numtracker/write_to_beamline_visit",
                    NUMTRACKER_AUTH_ADMIN="v1/data/diamond/policy/admin/configure_beamline",
                ),
            )
            _wait_http("http://localhost:15672", rabbitmq)
            _wait_http("http://localhost:8081/realms/master", keycloak)
            # Host requests arrive from the EPICS network gateway, which is not a
            # private address, so keycloak would otherwise insist on HTTPS
            for cmd in (
                "config credentials --server http://localhost:8081 --realm master"
                " --user admin --password admin",
                "update realms/master -s sslRequired=NONE",
            ):
                code, output = keycloak.exec(f"/opt/keycloak/bin/kcadm.sh {cmd}")
                assert code == 0, output
            _wait_http("http://localhost:8181/health?bundles", opa)
            _wait_http("http://localhost:8406/graphql", numtracker)

            # Everything below fetches the keycloak OIDC config on startup
            tiled = start(
                "tiled",
                container("ghcr.io/diamondlightsource/dls-tiled:0.5.0")
                .with_volume_mapping(SERVICES / "tiled_config", "/deploy/config")
                .with_env("VITE_LOGIN_REDIRECT", "false")
                .with_command("tiled serve config --host 0.0.0.0 --port 8407"),
            )
            for proxy in ("blueapi-oauth2-proxy", "tiled-oauth2-proxy"):
                start(
                    proxy,
                    container("quay.io/oauth2-proxy/oauth2-proxy:v7.13.0")
                    .with_volume_mapping(SERVICES / proxy, "/opt/config")
                    .with_command(
                        "--alpha-config=/opt/config/oauth2-alpha.yaml"
                        " --config=/opt/config/oauth2-proxy.cfg"
                    ),
                )
            subprocess.run(["uv", "run", SERVICES / "startup.py"], check=True)
            _wait_http("http://localhost:8407/api/v1/", tiled)

            if build:
                if build.wait():
                    raise RuntimeError("docker build of the blueapi image failed")
                server = start(
                    "blueapi",
                    container(
                        BLUEAPI_IMAGE,
                        entrypoint=["sh", "/blueapi/start.sh"],
                        # A huge default nofile limit makes the EPICS CA client
                        # spin and devices fail to connect
                        ulimits=[Ulimit(name="nofile", soft=1024, hard=1024)],
                    )
                    .with_envs(
                        EPICS_CA_ADDR_LIST=ioc_addresses,
                        EPICS_CA_AUTO_ADDR_LIST="NO",
                        EPICS_CA_SERVER_PORT="9064",
                        DODAL_VERSION=_dodal_version(),
                    )
                    .with_volume_mapping(HERE / "config.yaml", "/blueapi/config.yaml")
                    .with_volume_mapping(
                        HERE / "config-scratch.yaml", "/blueapi/config-scratch.yaml"
                    )
                    .with_volume_mapping(
                        SERVICES / "blueapi" / "start.sh", "/blueapi/start.sh"
                    ),
                )
                # setup-scratch plus device connection can take several minutes
                _wait_http("http://localhost:8000/healthz", server, timeout=600)

            yield dump_logs
        except Exception:
            dump_logs()
            raise


if __name__ == "__main__":
    try:
        with services(blueapi=False):
            if sys.argv[1:]:
                sys.exit(subprocess.run(sys.argv[1:]).returncode)
            print("Services are up, Ctrl-C to stop")
            while True:
                time.sleep(3600)
    except KeyboardInterrupt:
        pass
