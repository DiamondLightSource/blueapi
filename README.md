<img src="https://raw.githubusercontent.com/DiamondLightSource/blueapi/main/docs/images/blueapi-logo.svg"
     style="background: none" width="120px" height="120px" align="right">

[![CI](https://github.com/DiamondLightSource/blueapi/actions/workflows/ci.yml/badge.svg)](https://github.com/DiamondLightSource/blueapi/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/DiamondLightSource/blueapi/branch/main/graph/badge.svg)](https://codecov.io/gh/DiamondLightSource/blueapi)
[![PyPI](https://img.shields.io/pypi/v/blueapi.svg)](https://pypi.org/project/blueapi)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0)

# blueapi

Lightweight bluesky-as-a-service wrapper application. Also usable as a library.

Source          | <https://github.com/DiamondLightSource/blueapi>
:---:           | :---:
PyPI            | `pip install blueapi`
Docker          | `docker run ghcr.io/diamondlightsource/blueapi:latest`
Documentation   | <https://diamondlightsource.github.io/blueapi>
Releases        | <https://github.com/DiamondLightSource/blueapi/releases>

This module wraps [bluesky](https://blueskyproject.io/bluesky) plans and devices
inside a server and exposes endpoints to send commands/receive data. Useful for
installation at labs where multiple people may control equipment, possibly from
remote locations.

The main premise of blueapi is to minimize the boilerplate required to get plans
and devices up and running by generating an API for your lab out of
type-annotated plans. For example, take the following plan:

```python
import bluesky.plans as bp
from blueapi.core import MsgGenerator

def my_plan(foo: str, bar: int) -> MsgGenerator:
    yield from bp.scan(...)
```

Blueapi's job is to detect this plan and automatically add it to the lab's API
so it can be invoked easily with a few REST calls. 

<!-- README only content. Anything below this line won't be included in index.md -->

See https://diamondlightsource.github.io/blueapi for more detailed documentation.

[concept]: https://raw.githubusercontent.com/DiamondLightSource/blueapi/main/docs/images/blueapi.png
