from prometheus_client import (
    CollectorRegistry,
    Counter,
    Histogram,
    make_asgi_app,
    multiprocess,
)
from prometheus_client.context_managers import Timer


def make_metrics_app():
    registry = CollectorRegistry()
    multiprocess.MultiProcessCollector(registry)
    return make_asgi_app(registry=registry)


class TaskWorkerMetrics:
    def __init__(self):
        self.task_success_counter = Counter("task_success", "Successful tasks")
        self.task_failure_counter = Counter("task_failure", "Failed tasks")
        self.task_duration_histogram = Histogram(
            "task_duration_seconds", "Duration of task in seconds"
        )

    def inc_task_success(self):
        self.task_success_counter.inc()

    def inc_task_failure(self):
        self.task_failure_counter.inc()

    def time_task(self) -> Timer:
        return self.task_duration_histogram.time()
