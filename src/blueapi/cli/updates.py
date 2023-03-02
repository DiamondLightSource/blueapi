import itertools
from typing import Dict, Mapping, Optional, Union

from tqdm import tqdm

from blueapi.worker import ProgressEvent, StatusView, WorkerEvent, WorkerStatusEvent

_BAR_FMT = "{desc}: |{bar}| {percentage:3.0f}% [{elapsed}/{remaining}]"


class ProgressBarRenderer:
    _bars: Dict[str, tqdm]
    _count: itertools.count

    def __init__(self) -> None:
        self._bars = {}
        self._count = itertools.count()

    def update(self, status_view: Mapping[str, StatusView]) -> None:
        for name, view in status_view.items():
            if name not in self._bars:
                pos = next(self._count)
                self._bars[name] = tqdm(
                    position=pos,
                    total=1.0,
                    initial=0.0,
                    bar_format=_BAR_FMT,
                )
            self._update(name, view)

    def _update(self, name: str, view: StatusView) -> None:
        bar = self._bars[name]
        if (
            view.current is not None
            and view.target is not None
            and view.initial is not None
            and view.percentage is not None
            and view.time_elapsed is not None
        ):
            bar.desc = view.display_name
            bar.update(view.percentage - bar.n)
            bar.unit = view.unit


class CliEventRenderer:
    _task_name: Optional[str]
    _pbar_renderer: ProgressBarRenderer

    def __init__(
        self,
        task_name: Optional[str] = None,
        pbar_renderer: Optional[ProgressBarRenderer] = None,
    ) -> None:
        self._task_name = task_name
        self._pbar_renderer = pbar_renderer or ProgressBarRenderer()

    def render_event(self, event: WorkerEvent) -> None:
        if isinstance(event, ProgressEvent) and self._relates_to_task(event):
            self._pbar_renderer.update(event.statuses)
        elif isinstance(event, WorkerStatusEvent) and self._relates_to_task(event):
            print("")
            print(str(event.state))

    def _relates_to_task(self, event: Union[WorkerStatusEvent, ProgressEvent]) -> bool:
        if self._task_name is None:
            return True
        elif isinstance(event, WorkerStatusEvent):
            return (
                event.task_status is not None
                and event.task_status.task_name == self._task_name
            )
        elif isinstance(event, ProgressEvent):
            return event.task_name == self._task_name
        else:
            return False
