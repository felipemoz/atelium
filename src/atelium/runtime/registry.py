from __future__ import annotations
import json
import logging
from pathlib import Path

from ..manifest.schema import AgentManifest
from ..manifest.loader import load_manifest
from ..manifest.validator import validate_manifest
from ..infra.redis import get_redis, register_agent_vector, ensure_vector_index
from ..infra.postgres import get_pool
from ..infra.ollama import get_ollama
from ..config import settings

logger = logging.getLogger(__name__)


class AgentRegistry:
    """Registers and looks up agents in Redis Stack + PostgreSQL."""

    async def register(self, manifest_path: str | Path) -> AgentManifest:
        manifest = load_manifest(manifest_path)
        result = validate_manifest(manifest)

        if result.errors:
            raise ValueError(f"Manifest validation failed: {result.errors}")

        if result.warnings:
            for w in result.warnings:
                logger.warning("Manifest warning: %s", w)

        await self._store_metadata(manifest)
        await self._index_vector(manifest)
        logger.info("Registered agent: %s@%s", manifest.metadata.name, manifest.metadata.version)
        return manifest

    async def unregister(self, agent_name: str) -> None:
        redis = await get_redis()
        await redis.delete(f"agent:{agent_name}")
        pool = await get_pool()
        await pool.execute("DELETE FROM agents WHERE name = $1", agent_name)
        logger.info("Unregistered agent: %s", agent_name)

    async def get(self, agent_name: str) -> AgentManifest | None:
        pool = await get_pool()
        row = await pool.fetchrow(
            "SELECT manifest_yaml FROM agents WHERE name = $1", agent_name
        )
        if not row:
            return None
        from ..manifest.loader import load_manifest_from_dict
        import yaml
        return load_manifest_from_dict(yaml.safe_load(row["manifest_yaml"]))

    async def list_agents(self) -> list[dict]:
        pool = await get_pool()
        rows = await pool.fetch(
            "SELECT name, version, registered_at FROM agents ORDER BY name"
        )
        return [dict(r) for r in rows]

    async def _store_metadata(self, manifest: AgentManifest) -> None:
        from ..manifest.loader import dump_manifest
        pool = await get_pool()
        yaml_str = dump_manifest(manifest)
        await pool.execute(
            """
            INSERT INTO agents (name, version, manifest_yaml, registered_at)
            VALUES ($1, $2, $3, NOW())
            ON CONFLICT (name) DO UPDATE SET
                version = EXCLUDED.version,
                manifest_yaml = EXCLUDED.manifest_yaml,
                registered_at = NOW()
            """,
            manifest.metadata.name,
            manifest.metadata.version,
            yaml_str,
        )

    async def _index_vector(self, manifest: AgentManifest) -> None:
        redis = await get_redis()
        await ensure_vector_index(redis, dim=settings.embed_dim)

        ollama = get_ollama()
        capability_text = " ".join(manifest.spec.capabilities)
        vector = await ollama.embed(capability_text)

        import numpy as np
        vector_bytes = np.array(vector, dtype=np.float32).tobytes()

        await register_agent_vector(
            redis=redis,
            agent_name=manifest.metadata.name,
            version=manifest.metadata.version,
            capability_vector=vector_bytes,
            input_types=manifest.spec.accepts.types,
            max_concurrent=getattr(manifest.spec.blast_radius, "max_concurrent_pipelines", 10),
        )
