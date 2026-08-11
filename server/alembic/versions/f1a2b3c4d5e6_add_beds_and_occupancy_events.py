"""Add beds and occupancy_events tables (Phase 6 Stage 1)

Revision ID: f1a2b3c4d5e6
Revises: e7f89a012345
Create Date: 2026-08-11 21:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'e7f89a012345'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use raw SQL with IF NOT EXISTS so this migration is idempotent.
    # The tables may already exist if SQLAlchemy Base.metadata.create_all() ran
    # before this migration was applied.
    from alembic import op
    from sqlalchemy import text

    conn = op.get_bind()

    # ── Create beds table (if not exists) ───────────────────────────────────
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS beds (
            id          SERIAL PRIMARY KEY,
            hospital_id INTEGER NOT NULL REFERENCES hospitals(id) ON DELETE CASCADE,
            ward_id     INTEGER NOT NULL REFERENCES wards(id) ON DELETE CASCADE,
            bed_number  VARCHAR(50) NOT NULL,
            status      VARCHAR(50) NOT NULL DEFAULT 'AVAILABLE',
            bed_type    VARCHAR(50) NOT NULL DEFAULT 'STANDARD',
            created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at  TIMESTAMP NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_bed_ward_number UNIQUE (ward_id, bed_number)
        )
    """))

    # ── Beds indexes ──────────────────────────────────────────────────────────
    for idx_sql in [
        "CREATE INDEX IF NOT EXISTS ix_beds_id ON beds (id)",
        "CREATE INDEX IF NOT EXISTS ix_beds_hospital_id ON beds (hospital_id)",
        "CREATE INDEX IF NOT EXISTS ix_beds_ward_id ON beds (ward_id)",
        "CREATE INDEX IF NOT EXISTS ix_beds_bed_number ON beds (bed_number)",
        "CREATE INDEX IF NOT EXISTS ix_beds_status ON beds (status)",
        "CREATE INDEX IF NOT EXISTS ix_beds_bed_type ON beds (bed_type)",
    ]:
        conn.execute(text(idx_sql))

    # ── Create occupancy_events table (if not exists) ────────────────────────
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS occupancy_events (
            id          SERIAL PRIMARY KEY,
            hospital_id INTEGER NOT NULL REFERENCES hospitals(id) ON DELETE CASCADE,
            ward_id     INTEGER NOT NULL REFERENCES wards(id) ON DELETE CASCADE,
            bed_id      INTEGER NOT NULL REFERENCES beds(id) ON DELETE CASCADE,
            event_type  VARCHAR(50) NOT NULL,
            event_time  TIMESTAMP NOT NULL,
            source      VARCHAR(50) NOT NULL DEFAULT 'SIMULATOR',
            event_id    VARCHAR(100) NOT NULL,
            processed   BOOLEAN NOT NULL DEFAULT true,
            created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_occupancy_event_id UNIQUE (event_id)
        )
    """))

    # ── OccupancyEvent indexes ────────────────────────────────────────────────
    for idx_sql in [
        "CREATE INDEX IF NOT EXISTS ix_occupancy_events_id ON occupancy_events (id)",
        "CREATE INDEX IF NOT EXISTS ix_occupancy_events_hospital_id ON occupancy_events (hospital_id)",
        "CREATE INDEX IF NOT EXISTS ix_occupancy_events_ward_id ON occupancy_events (ward_id)",
        "CREATE INDEX IF NOT EXISTS ix_occupancy_events_bed_id ON occupancy_events (bed_id)",
        "CREATE INDEX IF NOT EXISTS ix_occupancy_events_event_type ON occupancy_events (event_type)",
        "CREATE INDEX IF NOT EXISTS ix_occupancy_events_event_time ON occupancy_events (event_time)",
        "CREATE INDEX IF NOT EXISTS ix_occupancy_events_source ON occupancy_events (source)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_occupancy_events_event_id ON occupancy_events (event_id)",
    ]:
        conn.execute(text(idx_sql))


def downgrade() -> None:
    # Drop occupancy_events first (depends on beds)
    op.drop_index('ix_occupancy_events_event_id', table_name='occupancy_events')
    op.drop_index('ix_occupancy_events_source', table_name='occupancy_events')
    op.drop_index('ix_occupancy_events_event_time', table_name='occupancy_events')
    op.drop_index('ix_occupancy_events_event_type', table_name='occupancy_events')
    op.drop_index('ix_occupancy_events_bed_id', table_name='occupancy_events')
    op.drop_index('ix_occupancy_events_ward_id', table_name='occupancy_events')
    op.drop_index('ix_occupancy_events_hospital_id', table_name='occupancy_events')
    op.drop_index('ix_occupancy_events_id', table_name='occupancy_events')
    op.drop_table('occupancy_events')

    # Then beds
    op.drop_index('ix_beds_bed_type', table_name='beds')
    op.drop_index('ix_beds_status', table_name='beds')
    op.drop_index('ix_beds_bed_number', table_name='beds')
    op.drop_index('ix_beds_ward_id', table_name='beds')
    op.drop_index('ix_beds_hospital_id', table_name='beds')
    op.drop_index('ix_beds_id', table_name='beds')
    op.drop_table('beds')
