from .scanspec import scan
from .wrapped import count

"""
This package is intended to hold MsgGenerator functions which act as self-contained
experiments: they start runs, collect data, and close the runs. While they may be used
as building blocks for larger nested plans, they are primarily intended to be run as-is,
and any common functionality which may be useful to multiple plans extracted to stubs/.
Plans:
- Must have type hinted arguments, Should use the loosest sensible bounds
- Must have docstrings describing behaviour and arguments of the function
- Must not have variadic args or kwargs, Should pass collections instead
- Must have optional argument named 'metadata' to add metadata to run(s)
- Must add 'plan_args' to metadata with complete representation including defaults, None
- Must add 'detectors', 'motors' metadata with list of names of relevant devices
- Should pass 'shape' to metadata if the run's shape is knowable
"""

__all__ = [
    "count",
    "scan",
]
