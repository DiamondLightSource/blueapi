from functools import partial
from typing import Any, Callable, Iterable, Type

from apischema.conversions.conversions import Conversion

from .bluesky_types import BLUESKY_PROTOCOLS, Device


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
