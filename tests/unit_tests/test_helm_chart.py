import subprocess
from collections.abc import Iterable, Mapping
from pathlib import Path
from tempfile import NamedTemporaryFile
from textwrap import dedent
from typing import Any, Literal
from unittest.mock import ANY

import pytest
import yaml
from pydantic import HttpUrl, Secret, TypeAdapter

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
    "PersistentVolumeClaim",
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
        ApplicationConfig(stomp=StompConfig(enabled=True)),
        ApplicationConfig(
            stomp=StompConfig(
                enabled=True,
                url=HttpUrl("http://example.com:515/"),
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
            },
            "worker": {
                "scratch": {
                    "repositories": [],
                    "root": "/blueapi-plugins/scratch",
                }
            },
        },
        {
            "initContainer": {
                "enabled": True,
            },
            "worker": {
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
            },
        },
    ],
)
def test_helm_chart_creates_init_config_map(values: Values):
    manifests = render_chart(values=values)
    rendered_config = yaml.safe_load(
        manifests["ConfigMap"]["blueapi-init-config"]["data"]["init_config.yaml"]
    )
    assert rendered_config["scratch"] == values["worker"]["scratch"]


def test_init_container_spec_generated():
    manifests = render_chart(
        values={
            "worker": {
                "scratch": {
                    "repositories": [],
                    "root": "/blueapi-plugins/scratch",
                },
            },
            "initContainer": {
                "enabled": True,
            },
        },
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
            }
        }
    )
    assert (
        "initContainers"
        not in manifests["StatefulSet"]["blueapi"]["spec"]["template"]["spec"]
    )


def test_helm_chart_does_not_render_arbitrary_rabbitmq_password():
    manifests = render_chart(
        values={"worker": {"stomp": {"auth": {"password": "foobar"}}}}
    )
    rendered_config = ApplicationConfig(
        **yaml.safe_load(
            manifests["ConfigMap"]["blueapi-config"]["data"]["config.yaml"]
        )
    )
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


@pytest.mark.parametrize(
    "url,expected_port",
    [
        ("http://0.0.0.0", 80),
        ("http://0.0.0.0:8001", 8001),
        ("https://0.0.0.0", 443),
        ("https://0.0.0.0:9090/path", 9090),
        ("https://0.0.0.0:9000", 9000),
        (None, 8000),
    ],
)
def test_container_port_set(url: str | None, expected_port: int):
    if url is None:
        values = {"worker": {"api": {}}}
    else:
        values = {
            "worker": {"api": {"url": url}},
        }
    manifests = render_chart(values=values)
    assert (
        manifests["StatefulSet"]["blueapi"]["spec"]["template"]["spec"]["containers"][
            0
        ]["ports"][0]["containerPort"]
        == expected_port
    )


def test_init_container_gets_container_resources_by_default():
    manifests = render_chart(
        values={
            "worker": {
                "scratch": {
                    "root": "/foo",
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
            },
            "resources": HIGH_RESOURCES,
            "initContainer": {"enabled": True},
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
            "worker": {
                "scratch": {
                    "root": "/foo",
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
            },
            "resources": HIGH_RESOURCES,
            "initResources": LOW_RESOURCES,
            "initContainer": {
                "enabled": True,
            },
        }
    )

    assert (
        manifests["StatefulSet"]["blueapi"]["spec"]["template"]["spec"][
            "initContainers"
        ][0]["resources"]
        == LOW_RESOURCES
    )


def test_worker_scratch_config_used_when_init_container_enabled():
    manifests = render_chart(
        values={
            "worker": {
                "scratch": {
                    "root": "/foo",
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
            },
            "initContainer": {
                "enabled": True,
                "scratch": {
                    "root": "NOT_USED",
                    "required_gid": 54321,
                    "repositories": [
                        {
                            "name": "NOT_USED",
                            "remote_url": "https://example.git",
                        },
                    ],
                },
            },
        }
    )

    config = yaml.safe_load(
        manifests["ConfigMap"]["blueapi-config"]["data"]["config.yaml"]
    )
    init_config = yaml.safe_load(
        manifests["ConfigMap"]["blueapi-init-config"]["data"]["init_config.yaml"]
    )
    type_adapter = TypeAdapter(ApplicationConfig)

    assert config["scratch"]["root"] == "/foo"
    assert init_config["scratch"]["root"] == "/foo"
    assert config["scratch"] == init_config["scratch"]

    init_config = type_adapter.validate_python(init_config)
    config = type_adapter.validate_python(config)

    assert config.scratch == init_config.scratch


def test_fluentd_ignore_true_when_graylog_enabled():
    manifests = render_chart(
        values={
            "worker": {
                "logging": {
                    "graylog": {
                        "enabled": True,
                    }
                },
            },
        }
    )

    assert (
        manifests["StatefulSet"]["blueapi"]["spec"]["template"]["metadata"][
            "annotations"
        ]["fluentd-ignore"]
        == "true"
    )


def test_fluentd_ignore_false_when_graylog_disabled():
    manifests = render_chart(
        values={
            "worker": {
                "logging": {
                    "graylog": {
                        "enabled": False,
                    }
                },
            },
        }
    )

    assert (
        "fluentd-ignore"
        not in manifests["StatefulSet"]["blueapi"]["spec"]["template"]["metadata"][
            "annotations"
        ]
    )


def render_persistent_volume_chart(
    init_container_enabled, persistentVolume_enabled, existingClaimName, debug_enabled
):
    """Generated chart for this section of Values:
    ```
    initContainer:
        enabled: false
        persistentVolume:
            enabled: true
            # existingClaimName: foo

    debug:
        enabled: false
    ```
    """
    return render_chart(
        values={
            "initContainer": {
                "enabled": init_container_enabled,
                "persistentVolume": {
                    "enabled": persistentVolume_enabled,
                }
                | (
                    {"existingClaimName": existingClaimName}
                    if existingClaimName
                    else {}
                ),
            },
            "debug": {"enabled": debug_enabled},
        }
    )


@pytest.fixture
def scratch_volume_mount():
    return {
        "name": "scratch",
        "mountPath": "/blueapi-plugins/scratch",
    }


@pytest.fixture
def scratch_host_volume_mount():
    return {
        "name": "scratch-host",
        "mountPath": "/blueapi-plugins/scratch",
        "mountPropagation": "HostToContainer",
    }


@pytest.fixture
def init_config_volume_mount():
    return {
        "name": "init-config",
        "mountPath": "/config",
        "readOnly": True,
    }


@pytest.fixture
def init_container_venv_volume_mount():
    return {
        "name": "venv",
        "mountPath": "/artefacts",
    }


@pytest.fixture
def venv_volume_mount():
    return {
        "name": "venv",
        "mountPath": "/venv",
    }


@pytest.fixture
def home_volume_mount():
    return {
        "name": "home",
        "mountPath": "/home",
    }


@pytest.fixture
def nslcd_volume_mount():
    return {
        "name": "nslcd",
        "mountPath": "/var/run/nslcd",
    }


@pytest.mark.parametrize("init_container_enabled", [True, False])
def test_init_container_exists_conditions(init_container_enabled):
    manifests = render_chart(
        values={"initContainer": {"enabled": init_container_enabled}}
    )

    if init_container_enabled:
        assert (
            "initContainers"
            in manifests["StatefulSet"]["blueapi"]["spec"]["template"]["spec"]
        )

    else:
        assert "initContainers" not in manifests["StatefulSet"]["blueapi"]["spec"]


@pytest.mark.parametrize("persistentVolume_enabled", [True, False])
@pytest.mark.parametrize("existingClaimName", [None, "foo"])
@pytest.mark.parametrize("debug_enabled", [True, False])
def test_init_container_scratch_mount(
    persistentVolume_enabled,
    existingClaimName,
    debug_enabled,
    scratch_volume_mount,
    scratch_host_volume_mount,
):
    manifests = render_persistent_volume_chart(
        True,
        persistentVolume_enabled,
        existingClaimName,
        debug_enabled,
    )

    volume_mounts = manifests["StatefulSet"]["blueapi"]["spec"]["template"]["spec"][
        "initContainers"
    ][0]["volumeMounts"]

    if persistentVolume_enabled:
        assert scratch_volume_mount in volume_mounts
        assert not any(mount["name"] == "scratch-host" for mount in volume_mounts)
    else:
        assert scratch_host_volume_mount in volume_mounts
        assert not any(mount["name"] == "scratch" for mount in volume_mounts)


@pytest.mark.parametrize("persistentVolume_enabled", [True, False])
@pytest.mark.parametrize("existingClaimName", [None, "foo"])
@pytest.mark.parametrize("debug_enabled", [True, False])
def test_init_container_init_config_mount(
    persistentVolume_enabled,
    existingClaimName,
    debug_enabled,
    init_config_volume_mount,
):
    manifests = render_persistent_volume_chart(
        True,
        persistentVolume_enabled,
        existingClaimName,
        debug_enabled,
    )

    volume_mounts = manifests["StatefulSet"]["blueapi"]["spec"]["template"]["spec"][
        "initContainers"
    ][0]["volumeMounts"]

    assert init_config_volume_mount in volume_mounts


@pytest.mark.parametrize("persistentVolume_enabled", [True, False])
@pytest.mark.parametrize("existingClaimName", [None, "foo"])
@pytest.mark.parametrize("debug_enabled", [True, False])
def test_init_container_venv_volume_mount(
    persistentVolume_enabled,
    existingClaimName,
    debug_enabled,
    init_container_venv_volume_mount,
):
    manifests = render_persistent_volume_chart(
        True,
        persistentVolume_enabled,
        existingClaimName,
        debug_enabled,
    )

    volume_mounts = manifests["StatefulSet"]["blueapi"]["spec"]["template"]["spec"][
        "initContainers"
    ][0]["volumeMounts"]

    assert init_container_venv_volume_mount in volume_mounts


@pytest.mark.parametrize("initContainer_enabled", [True, False])
@pytest.mark.parametrize("persistentVolume_enabled", [True, False])
@pytest.mark.parametrize("existingClaimName", [None, "foo"])
@pytest.mark.parametrize("debug_enabled", [True, False])
def test_persistent_volume_claim_exists(
    initContainer_enabled,
    persistentVolume_enabled,
    existingClaimName,
    debug_enabled,
):
    manifests = render_persistent_volume_chart(
        initContainer_enabled,
        persistentVolume_enabled,
        existingClaimName,
        debug_enabled,
    )

    persistent_volume_claim = {
        "scratch-0.1.0": {
            "apiVersion": "v1",
            "kind": "PersistentVolumeClaim",
            "metadata": {
                "name": "scratch-0.1.0",
                "annotations": {"helm.sh/resource-policy": "keep"},
            },
            "spec": {
                "accessModes": ["ReadWriteMany"],
                "resources": {"requests": {"storage": "1Gi"}},
            },
        }
    }

    if persistentVolume_enabled and not existingClaimName:
        assert persistent_volume_claim == manifests["PersistentVolumeClaim"]
    else:
        assert "PersistentVolumeClaim" not in manifests


@pytest.mark.parametrize("initContainer_enabled", [True, False])
@pytest.mark.parametrize("persistentVolume_enabled", [True, False])
@pytest.mark.parametrize("existingClaimName", [None, "foo"])
@pytest.mark.parametrize("debug_enabled", [True, False])
def test_debug_account_sync_exists(
    initContainer_enabled,
    persistentVolume_enabled,
    existingClaimName,
    debug_enabled,
):
    manifests = render_persistent_volume_chart(
        initContainer_enabled,
        persistentVolume_enabled,
        existingClaimName,
        debug_enabled,
    )

    if debug_enabled or (initContainer_enabled and persistentVolume_enabled):
        assert {
            "name": "debug-account-sync",
            "image": ANY,
            "volumeMounts": [{"mountPath": "/var/run/nslcd", "name": "nslcd"}],
        } == manifests["StatefulSet"]["blueapi"]["spec"]["template"]["spec"][
            "containers"
        ][1]

    else:
        assert (
            len(
                manifests["StatefulSet"]["blueapi"]["spec"]["template"]["spec"][
                    "containers"
                ]
            )
            == 1
        )


@pytest.mark.parametrize("initContainer_enabled", [True, False])
@pytest.mark.parametrize("persistentVolume_enabled", [True, False])
@pytest.mark.parametrize("existingClaimName", [None, "foo"])
@pytest.mark.parametrize("debug_enabled", [True, False])
def test_container_image_has_debug_suffix(
    initContainer_enabled,
    persistentVolume_enabled,
    existingClaimName,
    debug_enabled,
):
    manifests = render_persistent_volume_chart(
        initContainer_enabled,
        persistentVolume_enabled,
        existingClaimName,
        debug_enabled,
    )

    if debug_enabled:
        image = manifests["StatefulSet"]["blueapi"]["spec"]["template"]["spec"][
            "containers"
        ][0]["image"]
        assert str(image).endswith("-debug")

    else:
        image = manifests["StatefulSet"]["blueapi"]["spec"]["template"]["spec"][
            "containers"
        ][0]["image"]
        assert not str(image).endswith("-debug")

    if initContainer_enabled:
        init_image = manifests["StatefulSet"]["blueapi"]["spec"]["template"]["spec"][
            "initContainers"
        ][0]["image"]
        assert init_image == image


@pytest.mark.parametrize("initContainer_enabled", [True, False])
@pytest.mark.parametrize("persistentVolume_enabled", [True, False])
@pytest.mark.parametrize("existingClaimName", [None, "foo"])
@pytest.mark.parametrize("debug_enabled", [True, False])
def test_main_container_scratch_mount(
    initContainer_enabled,
    persistentVolume_enabled,
    existingClaimName,
    debug_enabled,
    scratch_volume_mount,
    scratch_host_volume_mount,
):
    manifests = render_persistent_volume_chart(
        initContainer_enabled,
        persistentVolume_enabled,
        existingClaimName,
        debug_enabled,
    )

    volume_mounts = manifests["StatefulSet"]["blueapi"]["spec"]["template"]["spec"][
        "containers"
    ][0]["volumeMounts"]

    if initContainer_enabled and persistentVolume_enabled:
        assert scratch_volume_mount in volume_mounts
        assert not any(mount["name"] == "scratch-host" for mount in volume_mounts)
    elif initContainer_enabled:
        assert scratch_host_volume_mount in volume_mounts
        assert not any(mount["name"] == "scratch" for mount in volume_mounts)
    else:
        assert not any(mount["name"] == "scratch-host" for mount in volume_mounts)
        assert not any(mount["name"] == "scratch" for mount in volume_mounts)


@pytest.mark.parametrize("initContainer_enabled", [True, False])
@pytest.mark.parametrize("persistentVolume_enabled", [True, False])
@pytest.mark.parametrize("existingClaimName", [None, "foo"])
@pytest.mark.parametrize("debug_enabled", [True, False])
def test_main_container_venv_volume_mount(
    initContainer_enabled,
    persistentVolume_enabled,
    existingClaimName,
    debug_enabled,
    venv_volume_mount,
):
    manifests = render_persistent_volume_chart(
        initContainer_enabled,
        persistentVolume_enabled,
        existingClaimName,
        debug_enabled,
    )

    volume_mounts = manifests["StatefulSet"]["blueapi"]["spec"]["template"]["spec"][
        "containers"
    ][0]["volumeMounts"]

    if initContainer_enabled:
        assert venv_volume_mount in volume_mounts
    else:
        assert venv_volume_mount not in volume_mounts


@pytest.mark.parametrize("initContainer_enabled", [True, False])
@pytest.mark.parametrize("persistentVolume_enabled", [True, False])
@pytest.mark.parametrize("existingClaimName", [None, "foo"])
@pytest.mark.parametrize("debug_enabled", [True, False])
def test_main_container_home_and_nslcd_volume_mounts(
    initContainer_enabled,
    persistentVolume_enabled,
    existingClaimName,
    debug_enabled,
    home_volume_mount,
    nslcd_volume_mount,
):
    manifests = render_persistent_volume_chart(
        initContainer_enabled,
        persistentVolume_enabled,
        existingClaimName,
        debug_enabled,
    )

    volume_mounts = manifests["StatefulSet"]["blueapi"]["spec"]["template"]["spec"][
        "containers"
    ][0]["volumeMounts"]

    if debug_enabled or (initContainer_enabled and persistentVolume_enabled):
        assert home_volume_mount in volume_mounts
        assert nslcd_volume_mount in volume_mounts
    else:
        assert home_volume_mount not in volume_mounts
        assert nslcd_volume_mount not in volume_mounts


@pytest.mark.parametrize("initContainer_enabled", [True, False])
@pytest.mark.parametrize("persistentVolume_enabled", [True, False])
@pytest.mark.parametrize("existingClaimName", [None, "foo"])
@pytest.mark.parametrize("debug_enabled", [True, False])
def test_main_container_args(
    initContainer_enabled,
    persistentVolume_enabled,
    existingClaimName,
    debug_enabled,
    home_volume_mount,
    nslcd_volume_mount,
):
    manifests = render_persistent_volume_chart(
        initContainer_enabled,
        persistentVolume_enabled,
        existingClaimName,
        debug_enabled,
    )

    if not debug_enabled:
        assert manifests["StatefulSet"]["blueapi"]["spec"]["template"]["spec"][
            "containers"
        ][0]["args"] == [
            "-c",
            "/config/config.yaml",
            "serve",
        ]
    else:
        assert (
            "args"
            not in manifests["StatefulSet"]["blueapi"]["spec"]["template"]["spec"][
                "containers"
            ][0]
        )


@pytest.mark.parametrize("existingClaimName", [None, "foo"])
@pytest.mark.parametrize("debug_enabled", [True, False])
def test_scratch_volume_uses_correct_claimName(
    existingClaimName,
    debug_enabled,
):
    manifests = render_persistent_volume_chart(
        True,
        True,
        existingClaimName,
        debug_enabled,
    )

    claim_name = manifests["StatefulSet"]["blueapi"]["spec"]["template"]["spec"][
        "volumes"
    ][3]["persistentVolumeClaim"]["claimName"]

    if existingClaimName:
        assert claim_name == existingClaimName
        assert "PersistentVolumeClaim" not in manifests
    else:
        assert claim_name == "scratch-0.1.0"
        assert claim_name in manifests["PersistentVolumeClaim"]


@pytest.fixture
def worker_config_volume():
    return {
        "name": "worker-config",
        "projected": {"sources": [{"configMap": {"name": "blueapi-config"}}]},
    }


@pytest.fixture
def init_config_volume():
    return {
        "name": "init-config",
        "projected": {"sources": [{"configMap": {"name": "blueapi-init-config"}}]},
    }


@pytest.fixture
def scratch_volume():
    return {"name": "scratch", "persistentVolumeClaim": {"claimName": ANY}}


@pytest.fixture
def scratch_host_volume():
    return {"name": "scratch-host", "hostPath": {"path": ANY, "type": "Directory"}}


@pytest.fixture
def venv_volume():
    return {"name": "venv", "emptyDir": {"sizeLimit": "5Gi"}}


@pytest.fixture
def home_volume():
    return {"name": "home", "emptyDir": {"sizeLimit": "500Mi"}}


@pytest.fixture
def nslcd_volume():
    return {"name": "nslcd", "emptyDir": {"sizeLimit": "5Mi"}}


@pytest.mark.parametrize("initContainer_enabled", [True, False])
@pytest.mark.parametrize("persistentVolume_enabled", [True, False])
@pytest.mark.parametrize("existingClaimName", [None, "foo"])
@pytest.mark.parametrize("debug_enabled", [True, False])
def test_worker_config_volume_declared(
    initContainer_enabled,
    persistentVolume_enabled,
    existingClaimName,
    debug_enabled,
    worker_config_volume,
):
    manifests = render_persistent_volume_chart(
        initContainer_enabled,
        persistentVolume_enabled,
        existingClaimName,
        debug_enabled,
    )

    assert (
        worker_config_volume
        in manifests["StatefulSet"]["blueapi"]["spec"]["template"]["spec"]["volumes"]
    )


@pytest.mark.parametrize("initContainer_enabled", [True, False])
@pytest.mark.parametrize("persistentVolume_enabled", [True, False])
@pytest.mark.parametrize("existingClaimName", [None, "foo"])
@pytest.mark.parametrize("debug_enabled", [True, False])
def test_init_config_and_venv_volumes_declared(
    initContainer_enabled,
    persistentVolume_enabled,
    existingClaimName,
    debug_enabled,
    init_config_volume,
    venv_volume,
):
    manifests = render_persistent_volume_chart(
        initContainer_enabled,
        persistentVolume_enabled,
        existingClaimName,
        debug_enabled,
    )

    if initContainer_enabled:
        assert (
            init_config_volume
            in manifests["StatefulSet"]["blueapi"]["spec"]["template"]["spec"][
                "volumes"
            ]
        )
        assert (
            venv_volume
            in manifests["StatefulSet"]["blueapi"]["spec"]["template"]["spec"][
                "volumes"
            ]
        )
    else:
        assert (
            init_config_volume
            not in manifests["StatefulSet"]["blueapi"]["spec"]["template"]["spec"][
                "volumes"
            ]
        )

        assert (
            venv_volume
            not in manifests["StatefulSet"]["blueapi"]["spec"]["template"]["spec"][
                "volumes"
            ]
        )


@pytest.mark.parametrize("initContainer_enabled", [True, False])
@pytest.mark.parametrize("persistentVolume_enabled", [True, False])
@pytest.mark.parametrize("existingClaimName", [None, "foo"])
@pytest.mark.parametrize("debug_enabled", [True, False])
def test_scratch_volume_declared(
    initContainer_enabled,
    persistentVolume_enabled,
    existingClaimName,
    debug_enabled,
    scratch_volume,
):
    manifests = render_persistent_volume_chart(
        initContainer_enabled,
        persistentVolume_enabled,
        existingClaimName,
        debug_enabled,
    )

    if initContainer_enabled and persistentVolume_enabled:
        assert (
            scratch_volume
            in manifests["StatefulSet"]["blueapi"]["spec"]["template"]["spec"][
                "volumes"
            ]
        )
    else:
        assert (
            scratch_volume
            not in manifests["StatefulSet"]["blueapi"]["spec"]["template"]["spec"][
                "volumes"
            ]
        )


@pytest.mark.parametrize("initContainer_enabled", [True, False])
@pytest.mark.parametrize("persistentVolume_enabled", [True, False])
@pytest.mark.parametrize("existingClaimName", [None, "foo"])
@pytest.mark.parametrize("debug_enabled", [True, False])
def test_scratch_host_volume_declared(
    initContainer_enabled,
    persistentVolume_enabled,
    existingClaimName,
    debug_enabled,
    scratch_host_volume,
):
    manifests = render_persistent_volume_chart(
        initContainer_enabled,
        persistentVolume_enabled,
        existingClaimName,
        debug_enabled,
    )

    if initContainer_enabled and not persistentVolume_enabled:
        assert (
            scratch_host_volume
            in manifests["StatefulSet"]["blueapi"]["spec"]["template"]["spec"][
                "volumes"
            ]
        )
    else:
        assert (
            scratch_host_volume
            not in manifests["StatefulSet"]["blueapi"]["spec"]["template"]["spec"][
                "volumes"
            ]
        )


@pytest.mark.parametrize("initContainer_enabled", [True, False])
@pytest.mark.parametrize("persistentVolume_enabled", [True, False])
@pytest.mark.parametrize("existingClaimName", [None, "foo"])
@pytest.mark.parametrize("debug_enabled", [True, False])
def test_home_and_nslcd_volumes_declared(
    initContainer_enabled,
    persistentVolume_enabled,
    existingClaimName,
    debug_enabled,
    home_volume,
    nslcd_volume,
):
    manifests = render_persistent_volume_chart(
        initContainer_enabled,
        persistentVolume_enabled,
        existingClaimName,
        debug_enabled,
    )

    if debug_enabled or (initContainer_enabled and persistentVolume_enabled):
        assert (
            home_volume
            in manifests["StatefulSet"]["blueapi"]["spec"]["template"]["spec"][
                "volumes"
            ]
        )
        assert (
            nslcd_volume
            in manifests["StatefulSet"]["blueapi"]["spec"]["template"]["spec"][
                "volumes"
            ]
        )
    else:
        assert (
            home_volume
            not in manifests["StatefulSet"]["blueapi"]["spec"]["template"]["spec"][
                "volumes"
            ]
        )
        assert (
            nslcd_volume
            not in manifests["StatefulSet"]["blueapi"]["spec"]["template"]["spec"][
                "volumes"
            ]
        )


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
        if manifest is None:
            continue
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


def test_init_container_config_copied_from_worker_when_enabled():
    manifests = render_chart(
        values={
            "worker": {
                "scratch": {
                    "root": "/foo",
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
            },
            "initContainer": {
                "enabled": True,
            },
        }
    )

    config = ApplicationConfig.model_validate(
        yaml.safe_load(manifests["ConfigMap"]["blueapi-config"]["data"]["config.yaml"])
    )
    init_config = ApplicationConfig.model_validate(
        yaml.safe_load(
            manifests["ConfigMap"]["blueapi-init-config"]["data"]["init_config.yaml"]
        )
    )

    assert config.scratch == init_config.scratch


@pytest.mark.parametrize("service_port", [80, 800])
@pytest.mark.parametrize("service_type", ["LoadBalancer", "ClusterIP"])
def test_service_created(service_type: str, service_port: int):
    manifests = render_chart(
        values={
            "service": {"type": service_type, "port": service_port},
        }
    )
    spec = manifests["Service"]["blueapi"]["spec"]
    assert spec["type"] == service_type
    assert spec["ports"][0] == {
        "name": "http",
        "port": service_port,
        "protocol": "TCP",
        "targetPort": "http",
    }


@pytest.mark.parametrize("ingress_host", ["blueapi.diamond.ac.uk", "ixx.diamond.ac.uk"])
@pytest.mark.parametrize("service_type", ["LoadBalancer", "ClusterIP"])
@pytest.mark.parametrize("service_port", [80, 800])
def test_ingress_created(service_type: str, service_port: int, ingress_host: str):
    manifests = render_chart(
        values={
            "service": {"type": service_type, "port": service_port},
            "ingress": {
                "enabled": True,
                "hosts": [
                    {
                        "host": ingress_host,
                        "paths": [{"path": "/", "pathType": "Prefix"}],
                    }
                ],
            },
        }
    )
    spec = manifests["Ingress"]["blueapi"]["spec"]
    assert spec["ingressClassName"] == "nginx"
    assert spec["rules"][0] == {
        "host": ingress_host,
        "http": {
            "paths": [
                {
                    "path": "/",
                    "pathType": "Prefix",
                    "backend": {
                        "service": {
                            "name": "blueapi",
                            "port": {"number": service_port},
                        }
                    },
                }
            ]
        },
    }


def test_ingress_not_created():
    manifests = render_chart(
        values={
            "ingress": {"enabled": False},
        }
    )
    assert "Ingress" not in manifests


@pytest.mark.parametrize("service_port", [80, 800])
@pytest.mark.parametrize(
    "worker_api_url",
    [
        "https://0.0.0.0",
        "http://0.0.0.0",
        "http://0.0.0.0:800",
        "https://0.0.0.0:800",
        None,
    ],
)
def test_service_linked_to_api(worker_api_url: str | None, service_port: int):
    manifests = render_chart(
        values={
            "service": {"port": service_port},
            "worker": {"api": {"url": worker_api_url}} if worker_api_url else {},
        }
    )
    service_spec = manifests["Service"]["blueapi"]["spec"]
    assert service_spec["ports"][0] == {
        "name": "http",
        "port": service_port,
        "protocol": "TCP",
        "targetPort": "http",
    }

    expected_container_port = {
        "https://0.0.0.0": 443,
        "http://0.0.0.0": 80,
        "http://0.0.0.0:800": 800,
        "https://0.0.0.0:800": 800,
        None: 8000,
    }

    container_ports = manifests["StatefulSet"]["blueapi"]["spec"]["template"]["spec"][
        "containers"
    ][0]["ports"]
    assert len(container_ports) == 1
    assert container_ports[0] == {
        "name": "http",
        "containerPort": expected_container_port[worker_api_url],
        "protocol": "TCP",
    }
