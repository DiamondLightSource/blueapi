from typing import List

from .wrapped import move, move_relative, set_absolute, set_relative, sleep, wait

"""
This package is intended to hold MsgGenerator functions which are not self-contained
data collections: while they may start runs, collect data, or close runs, they are
blocks for larger nested plans, and may not make sense to be run as-is. Functions that
may make sense as isolated blocks of functionality (e.g. moving a motor) should be added
to the __export__ list: without this list, it is assumed that all MsgGenerator functions
in the package should be imported by any services which respect it.
Functions that yield from multiple stubs and offer a complete workflow
should be moved to plans/.
This package should never have a dependency on plans/.
Stubs:
- Must have type hinted arguments, Should use the loosest sensible bounds
- Must have docstrings describing behaviour and arguments of the function
- Must not have variadic args or kwargs, Should pass collections instead
- Allow metadata to be propagated through if calling other stubs that take metadata
"""

__all__: List[str] = [  # Available for import by BlueAPI and other modules
    "set_absolute",
    "set_relative",
    "move",
    "move_relative",
    "sleep",
    "wait",
]
