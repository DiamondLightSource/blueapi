from prometheus_client import CollectorRegistry, make_asgi_app, multiprocess


def make_metrics_app():
    registry = CollectorRegistry()
    multiprocess.MultiProcessCollector(registry)
    return make_asgi_app(registry=registry)
