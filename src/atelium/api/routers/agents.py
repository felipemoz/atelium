from __future__ import annotations
from typing import Annotated
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel

from ..deps import get_registry
from ...runtime.registry import AgentRegistry

router = APIRouter(prefix="/agents", tags=["agents"])


class AgentInfo(BaseModel):
    name: str
    version: str
    registered_at: str | None = None


@router.get("/", response_model=list[AgentInfo])
async def list_agents(registry: Annotated[AgentRegistry, Depends(get_registry)]):
    agents = await registry.list_agents()
    return [AgentInfo(**{k: str(v) if v else None for k, v in a.items()}) for a in agents]


@router.post("/register", status_code=201)
async def register_agent(
    manifest_file: UploadFile = File(...),
    registry: AgentRegistry = Depends(get_registry),
):
    content = await manifest_file.read()
    tmp = Path(f"/tmp/{manifest_file.filename}")
    tmp.write_bytes(content)
    try:
        manifest = await registry.register(tmp)
        return {"name": manifest.metadata.name, "version": manifest.metadata.version}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    finally:
        tmp.unlink(missing_ok=True)


@router.delete("/{agent_name}", status_code=204)
async def unregister_agent(
    agent_name: str,
    registry: Annotated[AgentRegistry, Depends(get_registry)],
):
    await registry.unregister(agent_name)


@router.get("/{agent_name}")
async def get_agent(
    agent_name: str,
    registry: Annotated[AgentRegistry, Depends(get_registry)],
):
    manifest = await registry.get(agent_name)
    if not manifest:
        raise HTTPException(status_code=404, detail=f"Agent {agent_name!r} not found")
    return manifest.model_dump()
