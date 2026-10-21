from bluesky.utils import MsgGenerator


def demo(foo: int, /, bar: int) -> MsgGenerator[None]:
    yield from ()
