import threading
import time as ttime
from collections.abc import Callable

from ophyd.sim import SynAxis
from ophyd.status import MoveStatus, Status


class SynAxisWithMotionEvents(SynAxis):
    event_delay: float

    def __init__(
        self,
        *,
        name: str,
        readback_func: Callable | None = None,
        value: float = 0.0,
        delay: float = 0.0,
        events_per_move: int = 6,
        precision: int = 3,
        egu: str = "mm",
        parent=None,
        labels=None,
        kind=None,
        **kwargs,
    ):
        super().__init__(
            name=name,
            readback_func=readback_func,
            value=value,
            delay=delay,
            precision=precision,
            parent=parent,
            labels=labels,
            kind=kind,
            **kwargs,
        )
        self._events_per_move = events_per_move
        self.egu = egu

    def set(self, value: float) -> None:
        old_setpoint = self.sim_state["setpoint"]
        distance = value - old_setpoint
        self.sim_state["setpoint"] = value
        self.sim_state["setpoint_ts"] = ttime.time()
        self.setpoint._run_subs(  # noqa
            sub_type=self.setpoint.SUB_VALUE,
            old_value=old_setpoint,
            value=self.sim_state["setpoint"],
            timestamp=self.sim_state["setpoint_ts"],
        )

        def update_state(position: float) -> None:
            old_readback = self.sim_state["readback"]
            self.sim_state["readback"] = self._readback_func(position)
            self.sim_state["readback_ts"] = ttime.time()
            self.readback._run_subs(  # noqa
                sub_type=self.readback.SUB_VALUE,
                old_value=old_readback,
                value=self.sim_state["readback"],
                timestamp=self.sim_state["readback_ts"],
            )
            self._run_subs(
                sub_type=self.SUB_READBACK,
                old_value=old_readback,
                value=self.sim_state["readback"],
                timestamp=self.sim_state["readback_ts"],
            )

        st = MoveStatus(positioner=self, target=value)

        def sleep_and_finish():
            event_delay = self.delay / self._events_per_move
            for i in range(self._events_per_move):
                if self.delay:
                    ttime.sleep(event_delay)
                position = old_setpoint + (distance * ((i + 1) / self._events_per_move))
                update_state(position)
            st.set_finished()

        threading.Thread(target=sleep_and_finish, daemon=True).start()

        return st


class BrokenSynAxis(SynAxis):
    _timeout: float

    def __init__(self, *, timeout: float, **kwargs) -> None:
        super().__init__(**kwargs)
        self._timeout = timeout

    def set(self, value: float) -> Status:
        return Status(timeout=self._timeout)
