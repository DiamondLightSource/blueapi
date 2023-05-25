"""Generate openapi.json."""

from pathlib import Path
from typing import Mapping

import yaml
from fastapi.openapi.utils import get_openapi
from pyparsing import Any

from blueapi.service.main import app

DOCS_SCHEMA_LOCATION = (
    Path(__file__).parents[3] / "docs" / "user" / "reference" / "openapi.yaml"
)


def generate_schema() -> Mapping[str, Any]:
    return get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        description=app.description,
        routes=app.routes,
    )


def write_schema_as_yaml(location: Path, schema: Mapping[str, Any]) -> None:
    with open(location, "w") as stream:
        yaml.dump(schema, stream)


def print_schema_as_yaml(schema: Mapping[str, Any]) -> None:
    print(yaml.safe_dump(schema))
