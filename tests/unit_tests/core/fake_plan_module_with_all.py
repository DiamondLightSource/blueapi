from bluesky.utils import MsgGenerator
from tests.unit_tests.core.fake_plan_module import plan_a, plan_b  # noqa: F401


def plan_c(c: bool) -> MsgGenerator[None]: ...
def plan_d(d: int) -> MsgGenerator[int]: ...


__all__ = ["plan_a", "plan_d"]
