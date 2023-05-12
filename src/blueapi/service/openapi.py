"""Generate openapi.json."""

import yaml
from pathlib import Path

from fastapi.openapi.utils import get_openapi

from blueapi.service.main import app


def write_openapi_file(location: Path):
    with open(location, "w") as f:
        yaml.dump(
            get_openapi(
                title=app.title,
                version=app.version,
                openapi_version=app.openapi_version,
                description=app.description,
                routes=app.routes,
            ),
            f,
        )


def init(location: Path):
    if __name__ == "__main__":
        write_openapi_file(location)


location = Path(__file__).parents[3] / "docs" / "user" / "reference" / "openapi.yaml"
init(location)
