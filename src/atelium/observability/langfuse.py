from __future__ import annotations
import logging
from typing import Any

from ..config import settings
from ..core.models import Step

logger = logging.getLogger(__name__)

_langfuse = None


def get_langfuse():
    global _langfuse
    if _langfuse is None and settings.langfuse_public_key and settings.langfuse_secret_key:
        try:
            from langfuse import Langfuse
            _langfuse = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host,
            )
        except ImportError:
            logger.warning("langfuse not installed; LLM tracing disabled")
    return _langfuse


def trace_step_start(step: Step, manifest_name: str) -> Any | None:
    lf = get_langfuse()
    if not lf:
        return None
    try:
        trace = lf.trace(
            name=f"{manifest_name}:{step.agent_name}",
            id=str(step.step_id),
            input=step.input,
            metadata={
                "pipeline_id": str(step.pipeline_id),
                "agent_version": step.agent_version,
                "iteration": step.iteration,
            },
        )
        step.langfuse_trace_id = str(step.step_id)
        return trace
    except Exception as exc:
        logger.debug("Langfuse trace_start failed: %s", exc)
        return None


def trace_step_end(step: Step, trace: Any | None) -> None:
    if not trace:
        return
    try:
        trace.update(
            output=step.output,
            metadata={
                "status": step.status.value,
                "tokens_used": step.tokens_used,
                "cost_usd": step.cost_usd,
                "elapsed_ms": step.elapsed_ms,
                "validation_errors": step.validation_errors,
            },
        )
    except Exception as exc:
        logger.debug("Langfuse trace_end failed: %s", exc)
