from threading import Thread
from time import sleep

from bluesky import Msg, RunEngine
from bluesky import plan_stubs as bps

from blueapi.worker.reworker import RunEngineWorker, Task


def demo():
    yield Msg("print", "pre pause")
    yield from bps.sleep(1)
    yield Msg("pause")
    yield from bps.sleep(1)
    yield Msg("print", "post pause")


def broken():
    yield Msg("print", "started")
    yield from bps.sleep(2)
    raise ValueError("broken")


def slow(delay=30):
    yield from bps.sleep(delay)


async def echo(*a, **kw):
    """Print out a message to show sign of life"""
    print(a, kw)


def state_change(before, after):
    print(f"=== {before} -> {after} ===")


re = RunEngine(context_managers=[], call_returns_result=True)
re.register_command("print", echo)
re.state_hook = state_change  # type: ignore


# Start the worker running in a background thread
wk = RunEngineWorker(re)
bg = Thread(target=wk.cycle)
bg.start()

# give the worker a chance to start up
sleep(0.5)

print("==> Starting demo task")
# Plans can be run via submit
wk.submit(Task("demo1", demo()))

# Plans cannot be submitted if a task is running, even if paused
try:
    print("==> Trying to start demo task")
    wk.submit(Task("demo2", demo()))
except ValueError:
    print("    worker was busy")

# wait until demo plan has paused itself
sleep(2)

# And then resumed
wk.resume()

# wait for plan to finish
sleep(4)


print("==> Starting slow task")

# or aborted
wk.submit(Task("slow", slow()))
wk.abort()

# Worker can be shutdown via the shutdown method
wk.shutdown()
