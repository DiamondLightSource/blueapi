from unittest.mock import MagicMock

from bluesky import RunEngine
from bluesky.plan_stubs import sleep

from blueapi.worker import RunPlan, TaskContext


def test_run_plan_passes_generator_to_run_engine() -> None:
    run_engine = MagicMock(RunEngine)
    ctx = TaskContext(run_engine)
    plan = sleep(5)
    runner = RunPlan(plan)

    runner.do_task(ctx)

    run_engine.assert_called_with(plan)
