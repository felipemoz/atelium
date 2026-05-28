import pytest


@pytest.fixture(autouse=True)
def _override_settings(monkeypatch):
    """Ensure tests never hit real infrastructure."""
    monkeypatch.setenv("ATELIUM_REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("ATELIUM_POSTGRES_DSN", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("ATELIUM_NATS_URL", "nats://localhost:4222")
