from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.metrics import get_meter, set_meter_provider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.trace import get_tracer_provider

METER = get_meter("blueapi")

TASK_DURATION = METER.create_histogram(
    "blueapi.task.duration",
    unit="s",
    description="Time taken to run a task, by task name and outcome",
    # Plans run for anything between a fraction of a second and hours
    explicit_bucket_boundaries_advisory=[
        0.1, 0.5, 1, 5, 10, 30, 60, 300, 600, 1800, 3600, 7200, 14400
    ],
)  # fmt: skip


def setup_metrics(with_otlp_export: bool = True) -> None:
    """Push metrics over OTLP, to the same place and with the same resource
    (service name, instrument) as the traces. Call after setup_tracing.

    Pushing rather than serving a /metrics endpoint means the API process and
    the worker subprocess each report for themselves, with nothing shared.
    """
    if with_otlp_export:
        # The API only allows the global provider to be set once, later calls
        # are ignored with a warning
        set_meter_provider(
            MeterProvider(
                metric_readers=[PeriodicExportingMetricReader(OTLPMetricExporter())],
                resource=getattr(get_tracer_provider(), "resource", None),
            )
        )
