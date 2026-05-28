"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Agents registry
    op.execute("""
        CREATE TABLE IF NOT EXISTS agents (
            name            TEXT PRIMARY KEY,
            version         TEXT NOT NULL,
            manifest_yaml   TEXT NOT NULL,
            registered_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # Steps (Step-Resident State)
    op.execute("""
        CREATE TABLE IF NOT EXISTS steps (
            step_id         UUID PRIMARY KEY,
            pipeline_id     UUID NOT NULL,
            parent_step_id  UUID,
            branch_id       TEXT,
            agent_name      TEXT NOT NULL,
            agent_version   TEXT NOT NULL DEFAULT '0.0.0',
            status          TEXT NOT NULL DEFAULT 'pending',
            iteration       INT  NOT NULL DEFAULT 0,
            input           JSONB,
            output          JSONB,
            validation_errors JSONB DEFAULT '[]',
            snapshot        JSONB,
            tokens_used     INT  NOT NULL DEFAULT 0,
            cost_usd        NUMERIC(12,6) NOT NULL DEFAULT 0,
            started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at    TIMESTAMPTZ,
            elapsed_ms      INT
        )
    """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_steps_pipeline ON steps(pipeline_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_steps_status   ON steps(status)")

    # Agent stats (for routing success rate)
    op.execute("""
        CREATE TABLE IF NOT EXISTS agent_stats (
            name            TEXT PRIMARY KEY,
            success_rate    NUMERIC(5,4) NOT NULL DEFAULT 0.5,
            total_runs      INT NOT NULL DEFAULT 0,
            last_updated    TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # SAGA log (persistent complement to in-memory pipeline.saga_log)
    op.execute("""
        CREATE TABLE IF NOT EXISTS saga_entries (
            entry_id               UUID PRIMARY KEY,
            pipeline_id            UUID NOT NULL,
            step_id                UUID NOT NULL,
            agent_name             TEXT NOT NULL,
            action_name            TEXT NOT NULL,
            irreversibility_class  TEXT NOT NULL,
            compensating_action    TEXT NOT NULL,
            status                 TEXT NOT NULL DEFAULT 'committed',
            snapshot               JSONB,
            timestamp              TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_saga_pipeline ON saga_entries(pipeline_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS saga_entries")
    op.execute("DROP TABLE IF EXISTS agent_stats")
    op.execute("DROP TABLE IF EXISTS steps")
    op.execute("DROP TABLE IF EXISTS agents")
