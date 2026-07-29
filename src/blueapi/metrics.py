from prometheus_client import (
    CollectorRegistry,
    Counter,
    Histogram,
    make_asgi_app,
    multiprocess,
)


def make_metrics_app():
    """Create metrics ASGI app to mount to FastAPI server"""
    registry = CollectorRegistry()
    multiprocess.MultiProcessCollector(registry)
    return make_asgi_app(registry=registry)


class TaskWorkerMetrics:
    """Metrics instrumenting TaskWorker

    Includes metrics and methods used to instrument TaskWorker
    """

    def __init__(self):
        self._task_success_counter = Counter(
            "blueapi_task_success", "Successful tasks", ["task_name"]
        )
        self._task_failure_counter = Counter(
            "blueapi_task_failure", "Failed tasks", ["task_name"]
        )
        self._task_duration_histogram = Histogram(
            "blueapi_task_duration_seconds",
            "Duration of task in seconds",
            ["task_name", "success"],
        )

    def observe_task(
        self,
        task_name: str,
        success: bool,
        duration: float,
    ):
        """Update metrics to include task

        Increments success or failure task counter and adds duration to
        duration Histogram. All metrics given task_name label.

        Args:
            task_name: Name of task (eg. sleep)
            success: Whether task completed without error
            duration: Runtime of task
        """
        if success:
            self._task_success_counter.labels(task_name=task_name).inc()
        else:
            self._task_failure_counter.labels(task_name=task_name).inc()
        self._task_duration_histogram.labels(
            task_name=task_name, success=success
        ).observe(duration)
