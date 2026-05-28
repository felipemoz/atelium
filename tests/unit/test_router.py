"""Tests for EmergentRouter."""
from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from atelium.core.router import EmergentRouter, RoutingRequest
from atelium.core.models import RoutingDecision
from atelium.manifest.schema import DelegationMode


class TestEmergentRouter:
    def setup_method(self):
        self.router = EmergentRouter()  # no redis/pg — uses fallbacks

    @pytest.mark.asyncio
    async def test_returns_empty_without_redis(self):
        req = RoutingRequest(
            task_description="analyze sentiment",
            input_types=["text"],
        )
        decisions = await self.router.route(req)
        assert decisions == []

    @pytest.mark.asyncio
    async def test_circuit_open_excludes_agent(self):
        self.router.open_circuit("broken-agent", 60_000)
        assert self.router._is_circuit_open("broken-agent") is True

    def test_circuit_expires(self):
        import time
        self.router._circuit_open["expired-agent"] = time.monotonic() - 1
        assert self.router._is_circuit_open("expired-agent") is False
        assert "expired-agent" not in self.router._circuit_open

    @pytest.mark.asyncio
    async def test_score_candidate_formula(self):
        router = EmergentRouter()
        router._get_success_rate = AsyncMock(return_value=0.9)
        router._get_age_days = AsyncMock(return_value=0.0)
        router._get_load = AsyncMock(return_value=0.0)

        candidate = {
            "name": "test-agent",
            "version": "1.0.0",
            "semantic_score": 0.8,
        }
        decision = await router._score_candidate(candidate, [])

        # affinity = 0.50*0.8 + 0.30*0.9 + 0.10*1.0 + 0.10*1.0 = 0.40 + 0.27 + 0.10 + 0.10 = 0.87
        import math
        expected_recency = math.exp(-0.10 * 0.0)  # = 1.0
        expected = (
            0.50 * 0.8
            + 0.30 * 0.9
            + 0.10 * expected_recency
            + 0.10 * 1.0
        )
        assert abs(decision.affinity_score - round(expected, 4)) < 0.001

    @pytest.mark.asyncio
    async def test_route_best_returns_one(self):
        router = EmergentRouter()
        # Inject mock candidates bypassing Redis
        router._retrieve_candidates = AsyncMock(return_value=[
            {"name": "agent-a", "version": "1.0", "semantic_score": 0.9},
            {"name": "agent-b", "version": "1.0", "semantic_score": 0.6},
        ])
        router._get_success_rate = AsyncMock(return_value=0.8)
        router._get_age_days = AsyncMock(return_value=1.0)
        router._get_load = AsyncMock(return_value=0.1)
        router._embed = AsyncMock(return_value=[0.0] * 768)

        req = RoutingRequest(task_description="task", input_types=["text"])
        decisions = await router.route(req, mode=DelegationMode.ROUTE_BEST)
        assert len(decisions) == 1
        assert decisions[0].agent_name == "agent-a"

    @pytest.mark.asyncio
    async def test_route_n_returns_n(self):
        router = EmergentRouter()
        router._retrieve_candidates = AsyncMock(return_value=[
            {"name": f"agent-{i}", "version": "1.0", "semantic_score": 0.9 - i * 0.1}
            for i in range(5)
        ])
        router._get_success_rate = AsyncMock(return_value=0.8)
        router._get_age_days = AsyncMock(return_value=0.0)
        router._get_load = AsyncMock(return_value=0.0)
        router._embed = AsyncMock(return_value=[0.0] * 768)

        req = RoutingRequest(task_description="task", input_types=["text"])
        decisions = await router.route(req, mode=DelegationMode.ROUTE_N, n=3)
        assert len(decisions) == 3
