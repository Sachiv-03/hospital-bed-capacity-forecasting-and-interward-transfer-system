"""add_external_ids_and_data_source

Revision ID: k1l2m3n4o5p6
Revises: j0k1l2m3n4o5
Create Date: 2026-10-04 18:05:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'k1l2m3n4o5p6'
down_revision: Union[str, None] = 'j0k1l2m3n4o5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # 1. Add external_hospital_id to hospitals
    hospital_cols = [c["name"] for c in inspector.get_columns("hospitals")]
    if "external_hospital_id" not in hospital_cols:
        op.add_column("hospitals", sa.Column("external_hospital_id", sa.String(length=100), nullable=True))
        op.create_index("ix_hospitals_external_hospital_id", "hospitals", ["external_hospital_id"], unique=True)

    # 2. Add external_ward_id to wards
    ward_cols = [c["name"] for c in inspector.get_columns("wards")]
    if "external_ward_id" not in ward_cols:
        op.add_column("wards", sa.Column("external_ward_id", sa.String(length=100), nullable=True))
        op.create_index("ix_wards_external_ward_id", "wards", ["external_ward_id"])

    # 3. Add data_source to occupancy_snapshots
    snapshot_cols = [c["name"] for c in inspector.get_columns("occupancy_snapshots")]
    if "data_source" not in snapshot_cols:
        op.add_column(
            "occupancy_snapshots",
            sa.Column("data_source", sa.String(length=50), nullable=False, server_default="SIMULATED")
        )
        op.create_index("ix_occupancy_snapshots_data_source", "occupancy_snapshots", ["data_source"])


def downgrade() -> None:
    op.drop_index("ix_occupancy_snapshots_data_source", table_name="occupancy_snapshots")
    op.drop_column("occupancy_snapshots", "data_source")

    op.drop_index("ix_wards_external_ward_id", table_name="wards")
    op.drop_column("wards", "external_ward_id")

    op.drop_index("ix_hospitals_external_hospital_id", table_name="hospitals")
    op.drop_column("hospitals", "external_hospital_id")
