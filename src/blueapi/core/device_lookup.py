from functools import partial
from typing import Any, Callable, Iterable, List, Optional, Type, TypeVar

from apischema.conversions.conversions import Conversion

from .bluesky_types import BLUESKY_PROTOCOLS, Device, is_bluesky_compatible_device


def create_bluesky_protocol_conversions(
    device_lookup: Callable[[str], Device],
) -> Iterable[Conversion]:
    """
    Generate a series of APISchema Conversions for the valid Device types.
    The conversions use a user-defined function to lookup devices by name.

    Args:
        device_lookup (Callable[[str], Device]): Function to lookup Device by name,
                                                   expects an Exception if name not
                                                   found

    Returns:
        Iterable[Conversion]: Conversions for locating devices
    """

    def find_device_matching_name_and_type(target_type: Type, name: str) -> Any:
        # Find the device in the
        device = device_lookup(name)

        # The schema has asked for a particular protocol, at this point in the code we
        # have found the device but need to check that it complies with the requested
        # protocol. If it doesn't, it means there is a typing error in the plan.
        if isinstance(device, target_type):
            return device
        else:
            raise TypeError(f"{name} needs to be of type {target_type}")

    # Create a conversion for each type, the conversion function will automatically
    # perform a structural subtyping check
    for a_type in BLUESKY_PROTOCOLS:
        yield Conversion(
            partial(find_device_matching_name_and_type, a_type),
            source=str,
            target=a_type,
        )


#: Device obeying Bluesky protocols
D = TypeVar("D", bound=Device)


def find_component(obj: Any, addr: List[str]) -> Optional[D]:
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
