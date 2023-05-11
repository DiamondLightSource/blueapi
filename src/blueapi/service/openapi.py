"""Generate openapi.json."""

import json
from pathlib import Path

from fastapi.openapi.utils import get_openapi

from blueapi.service.main import app

if __name__ == "__main__":
    location = (
        Path(__file__).parents[3] / "docs" / "user" / "reference" / "openapi.json"
    )
    with open(location, "w") as f:
        json.dump(
            get_openapi(
                title=app.title,
                version=app.version,
                openapi_version=app.openapi_version,
                description=app.description,
                routes=app.routes,
            ),
            f,
            indent=4,
        )
