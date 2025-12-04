import pydantic
from tests.unit_tests.code_examples.device_module import BimorphMirror


@pydantic.dataclasses.dataclass(config={"arbitrary_types_allowed": True})
class MyDeviceComposite:
    oav: BimorphMirror
    # More devices here....
