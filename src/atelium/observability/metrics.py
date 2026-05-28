from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

_pipeline_counter = None
_step_histogram = None
_self_heal_counter = None
_hitl_counter = None


def setup_metrics() -> None:
    global _pipeline_counter, _step_histogram, _self_heal_counter, _hitl_counter
    try:
        from prometheus_client import Counter, Histogram

        _pipeline_counter = Counter(
            "atelium_pipelines_total",
            "Total pipeline executions",
            ["status", "manifest_name"],
        )
        _step_histogram = Histogram(
            "atelium_step_duration_ms",
            "Step execution duration in milliseconds",
            ["agent_name", "status"],
            buckets=[50, 100, 250, 500, 1000, 2500, 5000, 10000, 30000],
        )
        _self_heal_counter = Counter(
            "atelium_self_heals_total",
            "Total self-healing iterations triggered",
            ["agent_name"],
        )
        _hitl_counter = Counter(
            "atelium_hitl_gates_total",
            "Total HITL gate activations",
            ["agent_name", "resolved"],
        )
        logger.info("Prometheus metrics initialized")
    except ImportError:
        logger.warning("prometheus_client not installed; metrics disabled")


def record_pipeline(status: str, manifest_name: str) -> None:
    if _pipeline_counter:
        _pipeline_counter.labels(status=status, manifest_name=manifest_name).inc()


def record_step_duration(agent_name: str, status: str, elapsed_ms: int) -> None:
    if _step_histogram:
        _step_histogram.labels(agent_name=agent_name, status=status).observe(elapsed_ms)


def record_self_heal(agent_name: str) -> None:
    if _self_heal_counter:
        _self_heal_counter.labels(agent_name=agent_name).inc()


def record_hitl(agent_name: str, resolved: bool) -> None:
    if _hitl_counter:
        _hitl_counter.labels(agent_name=agent_name, resolved=str(resolved)).inc()
