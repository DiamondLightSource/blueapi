from prometheus_client import CollectorRegistry, Counter, make_asgi_app, multiprocess


def make_metrics_app():
    registry = CollectorRegistry()
    multiprocess.MultiProcessCollector(registry)
    return make_asgi_app(registry=registry)


class TaskWorkerMetrics:
    def __init__(self):
        self.task_success_counter = Counter("task_success", "Successful tasks")
        self.task_failure_counter = Counter("task_failure", "Failed tasks")

    def inc_task_success(self):
        self.task_success_counter.inc()

    def inc_task_failure(self):
        self.task_failure_counter.inc()
