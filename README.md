# blueapi

[![Code CI](https://github.com/DiamondLightSource/blueapi/actions/workflows/code.yml/badge.svg?branch=main)](https://github.com/DiamondLightSource/blueapi/actions/workflows/code.yml)
[![Docs CI](https://github.com/DiamondLightSource/blueapi/actions/workflows/docs.yml/badge.svg?branch=main)](https://github.com/DiamondLightSource/blueapi/actions/workflows/docs.yml)
[![Test Coverage](https://codecov.io/gh/DiamondLightSource/blueapi/branch/main/graph/badge.svg)](https://codecov.io/gh/DiamondLightSource/blueapi)
[![Latest PyPI version](https://img.shields.io/pypi/v/blueapi.svg)](https://pypi.org/project/blueapi)
[![Apache License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

Lightweight bluesky-as-a-service wrapper application. Also usable as a
library.

|               |                                                          |
|---------------|----------------------------------------------------------|
| PyPI          | `pip install blueapi`                                    |
| Source code   | <https://github.com/DiamondLightSource/blueapi>          |
| Documentation | <https://DiamondLightSource.github.io/blueapi>           |
| Releases      | <https://github.com/DiamondLightSource/blueapi/releases> |

This module wraps [bluesky](https://blueskyproject.io/bluesky) plans and
devices inside a server and exposes endpoints to send commands/receive
data. Useful for installation at labs where multiple people may control
equipment, possibly from remote locations.

<img src="docs/images/blueapi.png" width="800" alt="concept" />

The main premise of blueapi is to minimize the boilerplate required to
get plans and devices up and running by generating an API for your lab
out of type-annotated plans. For example, take the following plan:

``` python
import bluesky.plans as bp
from blueapi.core import MsgGenerator

def my_plan(foo: str, bar: int) -> MsgGenerator:
    yield from bp.scan(...)
```

Blueapi's job is to detect this plan and automatically add it to the
lab's API so it can be invoked easily with a few REST calls.

See <https://DiamondLightSource.github.io/blueapi> for more detailed
documentation.
