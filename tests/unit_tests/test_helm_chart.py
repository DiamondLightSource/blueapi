import subprocess
from collections.abc import Iterable, Mapping
from pathlib import Path
from tempfile import NamedTemporaryFile
from textwrap import dedent
from typing import Any, Literal

import pytest
import yaml
from pydantic import Secret, TypeAdapter

from blueapi.config import (
    ApplicationConfig,
    LoggingConfig,
    OIDCConfig,
    ScratchConfig,
    ScratchRepository,
    StompConfig,
)

BLUEAPI_HELM_CHART = Path(__file__).parent.parent.parent / "helm" / "blueapi"
Values = Mapping[str, Any]
ManifestKind = Literal[
    "ConfigMap",
    "Ingress",
    "Service",
    "StatefulSet",
    "Pod",
    "ServiceAccount",
]
GroupedManifests = Mapping[ManifestKind, Mapping[str, Mapping[str, Any]]]

HIGH_RESOURCES = {
    "requests": {
        "cpu": "10000m",
        "memory": "100Gi",
    },
    "limits": {
        "cpu": "20000m",
        "memory": "200Gi",
    },
}

LOW_RESOURCES = {
    "requests": {
        "cpu": "100m",
        "memory": "1Gi",
    },
    "limits": {
        "cpu": "200m",
        "memory": "2Gi",
    },
}


@pytest.mark.parametrize(
    "worker_config",
    [
        ApplicationConfig(),
        ApplicationConfig(stomp=StompConfig()),
        ApplicationConfig(
            stomp=StompConfig(
                host="example.com",
                port=515,
            ),
            logging=LoggingConfig(level="CRITICAL"),
            oidc=OIDCConfig(
                well_known_url="foo.bar",
                client_id="blueapi2",
                client_audience="blueapi++",
            ),
            scratch=ScratchConfig(
                root=Path("/dls_sw/i22/scratch"),
                required_gid=12345,
                repositories=[
                    ScratchRepository(
                        name="foo",
                        remote_url="https://example.git",
                    ),
                    ScratchRepository(
                        name="bar",
                        remote_url="https://example.git",
                    ),
                ],
            ),
        ),
    ],
)
def test_helm_chart_creates_config_map(worker_config: ApplicationConfig):
    manifests = render_chart(values={"worker": worker_config.model_dump()})
    rendered_config = ApplicationConfig(
        **yaml.safe_load(
            manifests["ConfigMap"]["blueapi-config"]["data"]["config.yaml"]
        )
    )
    assert rendered_config == worker_config


@pytest.mark.parametrize(
    "values",
    [
        {
            "initContainer": {
                "enabled": True,
                "scratch": {
                    "repositories": [],
                    "root": "/blueapi-plugins/scratch",
                },
            }
        },
        {
            "initContainer": {
                "enabled": True,
                "scratch": {
                    "root": "/dls_sw/i22/scratch",
                    "required_gid": 12345,
                    "repositories": [
                        {
                            "name": "foo",
                            "remote_url": "https://example.git",
                        },
                        {
                            "name": "bar",
                            "remote_url": "https://example.git",
                        },
                    ],
                },
            }
        },
    ],
)
def test_helm_chart_creates_init_config_map(values: Values):
    manifests = render_chart(values=values)
    rendered_config = yaml.safe_load(
        manifests["ConfigMap"]["blueapi-initconfig"]["data"]["initconfig.yaml"]
    )
    assert rendered_config == values["initContainer"]


def test_init_container_spec_generated():
    manifests = render_chart(
        values={
            "initContainer": {
                "enabled": True,
                "scratch": {
                    "repositories": [],
                    "root": "/blueapi-plugins/scratch",
                },
            }
        }
    )
    init_containers = manifests["StatefulSet"]["blueapi"]["spec"]["template"]["spec"][
        "initContainers"
    ]
    assert len(init_containers) == 1


def test_init_container_spec_disablable():
    manifests = render_chart(
        values={
            "initContainer": {
                "enabled": False,
                "scratch": {
                    "repositories": [],
                    "root": "/blueapi-plugins/scratch",
                },
            }
        }
    )
    init_containers = manifests["StatefulSet"]["blueapi"]["spec"]["template"]["spec"][
        "initContainers"
    ]
    assert init_containers is None


def test_helm_chart_does_not_render_arbitrary_rabbitmq_password():
    manifests = render_chart(
        values={"worker": {"stomp": {"auth": {"password": "foobar"}}}}
    )
    rendered_config = ApplicationConfig(
        **yaml.safe_load(
            manifests["ConfigMap"]["blueapi-config"]["data"]["config.yaml"]
        )
    )
    assert rendered_config.stomp is not None
    assert rendered_config.stomp.auth is not None
    assert isinstance(rendered_config.stomp.auth.password, Secret)


def test_container_gets_container_resources():
    manifests = render_chart(values={"resources": HIGH_RESOURCES})
    assert (
        manifests["StatefulSet"]["blueapi"]["spec"]["template"]["spec"]["containers"][
            0
        ]["resources"]
        == HIGH_RESOURCES
    )


def test_init_container_gets_container_resources_by_default():
    manifests = render_chart(
        values={
            "resources": HIGH_RESOURCES,
            "initContainer": {"enabled": True, "scratch": {"root": "/foo"}},
        }
    )
    assert (
        manifests["StatefulSet"]["blueapi"]["spec"]["template"]["spec"][
            "initContainers"
        ][0]["resources"]
        == HIGH_RESOURCES
    )


def test_init_container_resources_overridable():
    manifests = render_chart(
        values={
            "resources": HIGH_RESOURCES,
            "initResources": LOW_RESOURCES,
            "initContainer": {"enabled": True},
        }
    )

    assert (
        manifests["StatefulSet"]["blueapi"]["spec"]["template"]["spec"][
            "initContainers"
        ][0]["resources"]
        == LOW_RESOURCES
    )


def test_do_not_have_to_provide_scratch_host_path_twice():
    manifests = render_chart(
        values={
            "initContainer": {
                "enabled": True,
                "scratch": {
                    "root": "/foo",
                },
            },
        }
    )

    config = yaml.safe_load(
        manifests["ConfigMap"]["blueapi-config"]["data"]["config.yaml"]
    )
    init_config = yaml.safe_load(
        manifests["ConfigMap"]["blueapi-initconfig"]["data"]["initconfig.yaml"]
    )
    assert config["scratch"]["root"] == "/foo"
    assert init_config["scratch"]["root"] == "/foo"


def render_chart(
    path: Path = BLUEAPI_HELM_CHART,
    name: str | None = None,
    values: Values | None = None,
) -> GroupedManifests:
    content = TypeAdapter(Any).dump_json(values or {})
    with NamedTemporaryFile() as tmp_file:
        tmp_file.write(content)
        tmp_file.flush()
        result = subprocess.run(
            [
                "helm",
                "template",
                name or path.name,
                path,
                "--values",
                tmp_file.name,
            ],
            capture_output=True,
        )
    if result.returncode == 0:
        manifests = yaml.safe_load_all(result.stdout)
        return group_manifests(manifests)
    else:
        raise RuntimeError(f"Unable to render helm chart: {result.stderr}")


def group_manifests(ungrouped: Iterable[Mapping[str, Any]]) -> GroupedManifests:
    groups = {}
    for manifest in ungrouped:
        name = manifest["metadata"]["name"]
        kind = manifest["kind"]
        group = groups.setdefault(kind, {})
        if name in group:
            raise KeyError(
                dedent(f"""
                Cannot have 2 manifests of the same type with the same name.
                The chart currently renders at least 2 {kind}s named {name}.
                """)
            )
        group[name] = manifest
    return groups


def test_init_container_config_not_available_when_disabled():
    manifests = render_chart(
        values={
            "resources": HIGH_RESOURCES,
            "initResources": LOW_RESOURCES,
            "initContainer": {"enabled": False},
        }
    )

    assert (manifests["StatefulSet"]["blueapi"]["spec"]["template"]["spec"][
            "initContainers"]) is None

    manifests = render_chart(
        values={
            "resources": HIGH_RESOURCES,
            "initContainer": {"enabled": False},
        }
    )
    assert (
        manifests["StatefulSet"]["blueapi"]["spec"]["template"]["spec"][
            "initContainers"
        ]
        is None
    )
