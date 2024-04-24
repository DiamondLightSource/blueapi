from typing import Any, TypeVar

from .bluesky_types import Device, is_bluesky_compatible_device

#: Device obeying Bluesky protocols
D = TypeVar("D", bound=Device)


def find_component(obj: Any, addr: list[str]) -> D | None:
    """
    Best effort function to locate a child device, either in a dictionary of
    devices or a device with child attributes.

    Args:
        obj (Any): Root device or dictionary of devices
        addr (List[str]): Address of target device e.g. motors.x

    Raises:
        ValueError: If invalid object passed

    Returns:
        Optional[D]: Device if there is one present at addr
    """

    # Split address into head and tail
    head, tail = addr[0], addr[1:]

    # Best effort of how to extract component, if obj is a dictionary,
    # we assume the component is a key-value within. If obj is a
    # device, we assume the component is an attribute.
    # Otherwise, we error.
    if isinstance(obj, dict):
        component = obj.get(head)
    elif is_bluesky_compatible_device(obj):
        component = getattr(obj, head, None)
    else:
        raise ValueError(
            f"Searching for {addr} in {obj}, but it is not a device or a dictionary"
        )

    # Traverse device tree recursively
    if tail:
        return find_component(component, tail)
    elif is_bluesky_compatible_device(component) or component is None:
        return component
    else:
        raise ValueError(
            f"Found {component} in {obj} while searching for {addr} "
            "but it is not a device"
        )
