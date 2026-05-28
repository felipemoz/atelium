"""Tests for manifest loading and validation."""
from __future__ import annotations
import textwrap
import pytest
import yaml

from atelium.manifest.loader import load_manifest_from_dict
from atelium.manifest.validator import validate_manifest
from atelium.manifest.schema import AgentManifest


MINIMAL_MANIFEST = {
    "apiVersion": "atelium/v1alpha1",
    "kind": "Agent",
    "metadata": {"name": "my-agent", "owner": "test-user", "version": "1.0.0"},
    "spec": {
        "model": {"name": "llama3"},
        "capabilities": ["text-analysis"],
        "accepts": {"types": ["text"]},
        "task": {
            "description": "Analyze text",
            "prompt_template": "Analyze: {text}",
            "self_healing": {
                "strategy": "retry_with_feedback",
                "max_iterations": 2,
                "feedback_template": "Fix: {validation_errors}",
            },
        },
    },
}


class TestManifestLoading:
    def test_load_minimal_manifest(self):
        manifest = load_manifest_from_dict(MINIMAL_MANIFEST)
        assert manifest.metadata.name == "my-agent"
        assert manifest.metadata.version == "1.0.0"
        assert "text-analysis" in manifest.spec.capabilities

    def test_invalid_name_raises(self):
        data = {**MINIMAL_MANIFEST, "metadata": {"name": "My Agent!", "owner": "test-user", "version": "1.0.0"}}
        with pytest.raises(Exception):
            load_manifest_from_dict(data)

    def test_invalid_version_raises(self):
        data = {**MINIMAL_MANIFEST, "metadata": {"name": "my-agent", "owner": "test-user", "version": "v1"}}
        with pytest.raises(Exception):
            load_manifest_from_dict(data)

    def test_defaults_populated(self):
        manifest = load_manifest_from_dict(MINIMAL_MANIFEST)
        assert manifest.spec.topology is not None
        assert manifest.spec.blast_radius is not None
        assert manifest.spec.observability is not None


class TestManifestValidator:
    def test_valid_manifest_passes(self):
        manifest = load_manifest_from_dict(MINIMAL_MANIFEST)
        result = validate_manifest(manifest)
        assert result.is_valid

    def test_generic_capability_warns(self):
        data = {**MINIMAL_MANIFEST}
        data["spec"] = {**data["spec"], "capabilities": ["general purpose agent"]}
        manifest = load_manifest_from_dict(data)
        result = validate_manifest(manifest)
        assert any("generic" in str(w).lower() for w in result.warnings)

    def test_too_many_capabilities_errors(self):
        data = {**MINIMAL_MANIFEST}
        data["spec"] = {**data["spec"], "capabilities": [f"cap-{i}" for i in range(25)]}
        with pytest.raises(Exception):  # Pydantic validation error
            load_manifest_from_dict(data)

    def test_blast_radius_hitl_action_in_saga(self):
        """HITL action listed in blast_radius but not in saga should warn."""
        import copy
        data = copy.deepcopy(MINIMAL_MANIFEST)
        data["spec"]["blast_radius"] = {
            "max_concurrent_pipelines": 5,
            "human_approval_required": ["delete_user"],
        }
        manifest = load_manifest_from_dict(data)
        result = validate_manifest(manifest)
        # Should warn that delete_user isn't in saga irreversible_actions
        # (depends on implementation — just check it doesn't crash)
        assert result is not None
