from bluesky.utils import MsgGenerator


def demo(foo: int, *args, **kwargs) -> MsgGenerator[None]:
    yield from ()
