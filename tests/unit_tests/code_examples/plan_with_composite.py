from bluesky.utils import MsgGenerator
from dodal.common import inject
from tests.unit_tests.code_examples.device_composite import MyDeviceComposite


def my_plan(
    parameter_one: int,
    parameter_two: str,
    my_necessary_devices: MyDeviceComposite = inject(""),
) -> MsgGenerator[None]:
    # logic goes here
    ...
