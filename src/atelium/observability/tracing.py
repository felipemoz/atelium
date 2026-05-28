from __future__ import annotations
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from ..config import settings

logger = logging.getLogger(__name__)

_tracer = None


def setup_tracing(service_name: str = "atelium") -> None:
    global _tracer
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource

        resource = Resource(attributes={"service.name": service_name})
        provider = TracerProvider(resource=resource)

        if settings.otel_endpoint:
            exporter = OTLPSpanExporter(endpoint=settings.otel_endpoint)
            provider.add_span_processor(BatchSpanProcessor(exporter))

        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer(service_name)
        logger.info("OpenTelemetry tracing initialized (endpoint=%s)", settings.otel_endpoint)
    except ImportError:
        logger.warning("opentelemetry not installed; tracing disabled")


def get_tracer():
    global _tracer
    if _tracer is None:
        try:
            from opentelemetry import trace
            _tracer = trace.get_tracer("atelium")
        except ImportError:
            pass
    return _tracer


@asynccontextmanager
async def trace_step(
    step_id: str, agent_name: str, pipeline_id: str
) -> AsyncGenerator[None, None]:
    tracer = get_tracer()
    if tracer is None:
        yield
        return

    with tracer.start_as_current_span(
        f"step:{agent_name}",
        attributes={
            "atelium.step_id": step_id,
            "atelium.agent_name": agent_name,
            "atelium.pipeline_id": pipeline_id,
        },
    ):
        yield
