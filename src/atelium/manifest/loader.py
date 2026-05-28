from pathlib import Path
import yaml
from .schema import AgentManifest


def load_manifest(path: str | Path) -> AgentManifest:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Manifest not found: {path}")
    with open(path) as f:
        data = yaml.safe_load(f)
    return AgentManifest.model_validate(data)


def load_manifest_from_dict(data: dict) -> AgentManifest:
    return AgentManifest.model_validate(data)


def dump_manifest(manifest: AgentManifest) -> str:
    return yaml.dump(manifest.model_dump(exclude_none=True), allow_unicode=True, sort_keys=False)
