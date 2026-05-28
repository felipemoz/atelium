from __future__ import annotations
import math
import logging
from dataclasses import dataclass

from ..manifest.schema import AgentManifest, DelegationMode
from ..config import settings
from .models import RoutingDecision

logger = logging.getLogger(__name__)


@dataclass
class RoutingRequest:
    task_description: str
    input_types: list[str]
    pipeline_id: str = ""
    required_capabilities: list[str] | None = None


class EmergentRouter:
    def __init__(self, redis_client=None, postgres_pool=None, embedder=None):
        self._redis = redis_client
        self._postgres = postgres_pool
        self._embedder = embedder
        self._circuit_open: dict[str, float] = {}  # agent_name -> open_until timestamp

    async def route(
        self,
        request: RoutingRequest,
        mode: DelegationMode = DelegationMode.ROUTE_BEST,
        n: int = 1,
        exclude: list[str] | None = None,
    ) -> list[RoutingDecision]:
        exclude = exclude or []

        # 1. Embed task description
        task_vector = await self._embed(request.task_description)

        # 2. ANN candidate retrieval from Redis Stack
        candidates = await self._retrieve_candidates(task_vector, request.input_types, exclude)

        if not candidates:
            logger.warning("No candidates found for task: %s", request.task_description[:60])
            return []

        # 3. Score each candidate with full affinity formula
        scored: list[RoutingDecision] = []
        for candidate in candidates:
            if self._is_circuit_open(candidate["name"]):
                continue
            decision = await self._score_candidate(candidate, task_vector)
            if decision.affinity_score >= settings.routing_min_affinity:
                scored.append(decision)

        scored.sort(key=lambda d: d.affinity_score, reverse=True)

        if mode == DelegationMode.ROUTE_BEST:
            return scored[:1]
        elif mode == DelegationMode.ROUTE_N:
            return scored[:n]
        else:  # ROUTE_ALL
            return scored

    async def _embed(self, text: str) -> list[float]:
        if self._embedder:
            return await self._embedder.embed(text)
        return [0.0] * settings.embed_dim

    async def _retrieve_candidates(
        self, vector: list[float], input_types: list[str], exclude: list[str]
    ) -> list[dict]:
        if not self._redis:
            return []
        try:
            import numpy as np
            query_bytes = np.array(vector, dtype=np.float32).tobytes()
            results = await self._redis.ft("agent_capabilities").search(
                f"*=>[KNN {settings.routing_candidate_pool} @capability_vector $vec AS score]",
                query_params={"vec": query_bytes},
            )
            candidates = []
            for doc in results.docs:
                name = doc.name.replace("agent:", "")
                if name not in exclude:
                    candidates.append({
                        "name": name,
                        "version": getattr(doc, "version", "0.0.0"),
                        "capability_vector": getattr(doc, "capability_vector", None),
                        "input_types": getattr(doc, "input_types", "").split(","),
                        "semantic_score": float(getattr(doc, "score", 0.0)),
                    })
            return candidates
        except Exception as exc:
            logger.error("Registry search failed: %s", exc)
            return []

    async def _score_candidate(self, candidate: dict, task_vector: list[float]) -> RoutingDecision:
        sr = await self._get_success_rate(candidate["name"])
        age_days = await self._get_age_days(candidate["name"])
        load = await self._get_load(candidate["name"])

        semantic = candidate.get("semantic_score", 0.5)
        recency = math.exp(-settings.routing_lambda * age_days)
        load_score = 1.0 - min(load, 1.0)

        affinity = (
            settings.routing_alpha * semantic
            + settings.routing_beta * sr
            + settings.routing_gamma * recency
            + settings.routing_delta * load_score
        )

        return RoutingDecision(
            agent_name=candidate["name"],
            agent_version=candidate.get("version", "unknown"),
            affinity_score=round(affinity, 4),
            semantic_similarity=round(semantic, 4),
            success_rate=round(sr, 4),
            recency_score=round(recency, 4),
            load_score=round(load_score, 4),
        )

    async def _get_success_rate(self, agent_name: str) -> float:
        if not self._postgres:
            return 0.5
        try:
            row = await self._postgres.fetchrow(
                "SELECT success_rate FROM agent_stats WHERE name = $1", agent_name
            )
            return float(row["success_rate"]) if row else 0.5
        except Exception:
            return 0.5

    async def _get_age_days(self, agent_name: str) -> float:
        if not self._redis:
            return 0.0
        try:
            ts = await self._redis.hget(f"agent:{agent_name}", "last_success_at")
            if ts:
                from datetime import datetime
                last = datetime.fromisoformat(ts.decode())
                return (datetime.utcnow() - last).days
            return 0.0
        except Exception:
            return 0.0

    async def _get_load(self, agent_name: str) -> float:
        if not self._redis:
            return 0.0
        try:
            active = await self._redis.get(f"agent:{agent_name}:active_pipelines")
            max_pipelines = await self._redis.hget(f"agent:{agent_name}", "max_concurrent_pipelines")
            if active and max_pipelines:
                return int(active) / int(max_pipelines)
            return 0.0
        except Exception:
            return 0.0

    def open_circuit(self, agent_name: str, timeout_ms: int) -> None:
        import time
        self._circuit_open[agent_name] = time.monotonic() + timeout_ms / 1000

    def _is_circuit_open(self, agent_name: str) -> bool:
        import time
        until = self._circuit_open.get(agent_name)
        if until is None:
            return False
        if time.monotonic() > until:
            del self._circuit_open[agent_name]
            return False
        return True
