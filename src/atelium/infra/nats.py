from __future__ import annotations
import json
import logging
from typing import Callable, Awaitable

import nats
import nats.js

from ..config import settings

logger = logging.getLogger(__name__)

_nc: nats.NATS | None = None
_js: nats.js.JetStreamContext | None = None

STREAM_NAME = "ATELIUM"
SUBJECTS = [
    "atelium.pipeline.>",
    "atelium.step.>",
    "atelium.hitl.>",
]


async def get_nats() -> tuple[nats.NATS, nats.js.JetStreamContext]:
    global _nc, _js
    if _nc is None or not _nc.is_connected:
        _nc = await nats.connect(settings.nats_url)
        _js = _nc.jetstream()
        await _ensure_stream(_js)
        logger.info("NATS JetStream connected")
    return _nc, _js


async def close_nats() -> None:
    global _nc
    if _nc and _nc.is_connected:
        await _nc.drain()
        _nc = None


async def _ensure_stream(js: nats.js.JetStreamContext) -> None:
    try:
        await js.find_stream(STREAM_NAME)
    except Exception:
        from nats.js.api import StreamConfig, RetentionPolicy, StorageType
        await js.add_stream(StreamConfig(
            name=STREAM_NAME,
            subjects=SUBJECTS,
            retention=RetentionPolicy.LIMITS,
            storage=StorageType.FILE,
            max_age=7 * 24 * 3600,  # 7 days
        ))
        logger.info("Created NATS stream: %s", STREAM_NAME)


async def publish(subject: str, payload: dict) -> None:
    _, js = await get_nats()
    await js.publish(subject, json.dumps(payload).encode())


async def subscribe(
    subject: str,
    durable: str,
    handler: Callable[[dict], Awaitable[None]],
) -> None:
    _, js = await get_nats()

    async def _msg_handler(msg):
        try:
            data = json.loads(msg.data.decode())
            await handler(data)
            await msg.ack()
        except Exception as exc:
            logger.error("NATS handler error on %s: %s", subject, exc)
            await msg.nak()

    await js.subscribe(subject, durable=durable, cb=_msg_handler)


# ------------------------------------------------------------------
# Typed event helpers
# ------------------------------------------------------------------

async def emit_pipeline_started(pipeline_id: str, manifest_name: str) -> None:
    await publish(f"atelium.pipeline.started", {
        "pipeline_id": pipeline_id,
        "manifest_name": manifest_name,
    })


async def emit_step_completed(pipeline_id: str, step_id: str, status: str) -> None:
    await publish(f"atelium.step.completed", {
        "pipeline_id": pipeline_id,
        "step_id": step_id,
        "status": status,
    })


async def emit_hitl_gate(pipeline_id: str, step_id: str, errors: list[str]) -> None:
    await publish("atelium.hitl.gate", {
        "pipeline_id": pipeline_id,
        "step_id": step_id,
        "errors": errors,
    })
