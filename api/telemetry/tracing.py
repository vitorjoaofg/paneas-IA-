from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from config import get_settings

_settings = get_settings()


def configure_tracing() -> None:
    if not _settings.otel_endpoint:
        return

    resource = Resource.create({"service.name": "ai-stack-api", "service.version": _settings.stack_version})
    provider = TracerProvider(resource=resource)
    span_exporter = OTLPSpanExporter(endpoint=str(_settings.otel_endpoint))
    span_processor = BatchSpanProcessor(span_exporter)
    provider.add_span_processor(span_processor)
    trace.set_tracer_provider(provider)
