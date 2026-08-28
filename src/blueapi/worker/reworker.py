from dataclasses import dataclass
from enum import Enum
from threading import Condition, Event

from bluesky._vendor.super_state_machine.errors import TransitionError
from bluesky.run_engine import RunEngine
from bluesky.utils import RunEngineInterrupted


class TaskState(Enum):
    PENDING = "pending"
    STARTED = "started"
    COMPLETE = "complete"
    ABORTED = "aborted"
    FAILED = "failed"


class Task:
    state: TaskState
    name: str

    def __init__(self, name, plan):
        self._name = name
        self._plan = plan
        self.state = TaskState.PENDING

    def run(self, run_engine: RunEngine):
        print(f"Running task from a {self.state}")
        match self.state:
            case TaskState.PENDING:
                self.state = TaskState.STARTED
                run_engine(self.plan())
            case TaskState.STARTED:
                run_engine.resume()
            case _:
                raise ValueError("Task is already complete")

    def plan(self):
        print("Starting plan")
        yield from self._plan

    def __repr__(self) -> str:
        return f"Task(name: {self._name}, {self.state})"


class Shutdown:
    pass


class Resume:
    pass


@dataclass
class Abort:
    result: RunEngineInterrupted


class Alert(Enum):
    ABORT = "abort"
    RESUME = "resume"


class RunEngineWorker:
    run_engine: RunEngine

    task_lock: Condition
    active_task: Task | Shutdown | None

    wake_up_lock: Condition
    wake_up: Resume | Abort | None
    _shutdown: Event

    def __init__(self, run_engine: RunEngine):
        self.run_engine = run_engine
        self.task_lock = Condition()
        self.active_task = None

        self.wake_up_lock = Condition()
        self.wake_up = None

        self._shutdown = Event()

    def submit(self, task: Task):
        idle = self.task_lock.acquire(blocking=False)
        try:
            if not idle or self.active_task is not None:
                raise ValueError("Worker is busy")
            print("  worker was idle")
            self.active_task = task
            self.task_lock.notify()
        finally:
            if idle:
                self.task_lock.release()

    def pause(self):
        try:
            print("Requesting pause")
            self.run_engine.request_pause()
        except TransitionError:
            # run_engine could not be paused
            pass

    def resume(self):
        self._nudge(Resume())

    def abort(self):
        idle = self.task_lock.acquire(blocking=False)
        try:
            if idle:
                if self.active_task is not None:
                    print(
                        "Aborted between task being submitted and it being accepted "
                        "- drop task"
                    )
                    self.active_task = None
            else:
                print("Aborting run engine")
                res = self.run_engine.abort()
                print("    aborted")
                self._nudge(Abort(result=res))
        except TransitionError:
            pass
        finally:
            if idle:
                self.task_lock.release()

    def shutdown(self):
        idle = self.task_lock.acquire(blocking=False)
        self._shutdown.set()
        if idle:
            self.active_task = Shutdown()
            self.task_lock.notify()
            self.task_lock.release()

    def _nudge(self, alert: Resume | Abort):
        waiting = self.wake_up_lock.acquire(blocking=False)
        if waiting:
            print("Setting wake up to ", alert)
            self.wake_up = alert
            self.wake_up_lock.notify()
            self.wake_up_lock.release()
        else:
            print("Not setting alert")

    def cycle(self):
        while not self._shutdown.is_set():
            print("Not shutdown - starting loop")
            with self.task_lock, self.wake_up_lock:
                if self.active_task is None:
                    print("No active task - waiting for new task")
                    # TODO: Break out of here when worker shuts down
                    self.task_lock.wait()  # _for(lambda: self.active_task is not None)
                    print("    End of waiting")
                else:
                    print("??? active task was present at start of loop")

                match self.active_task:
                    case None:
                        continue
                    case Shutdown():
                        break
                    case Task() as task:
                        self.active_task = None
                        print("New task: ", task)
                        try:
                            self._run_task(task)
                        except Exception as e:
                            print("Task failed: ", e)
                            task.state = TaskState.FAILED
                        print("Task complete")
        print("Shutting down")

    def _run_task(self, task: Task):
        """
        Run a task to completion including any pause/resume required.
        """
        while True:
            print("(re)running task")
            try:
                task.run(self.run_engine)
                task.state = TaskState.COMPLETE
                break
            except RunEngineInterrupted:
                print(f"Run engine was interrupted: {self.run_engine.state=}")
                if self.run_engine.state != "paused":
                    task.state = TaskState.ABORTED
                    return

                # We're paused, wait until someone wakes us up
                print("Waiting to be woken up")
                self.wake_up_lock.wait()
                print(f"Woken up: {self.wake_up=}")
                match self.wake_up:
                    case Resume():
                        pass
                    case Abort(result):
                        print("Task aborted with result: ", result)
                        break
