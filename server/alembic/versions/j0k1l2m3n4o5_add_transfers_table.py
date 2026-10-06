"""add_transfers_table

Revision ID: j0k1l2m3n4o5
Revises: i9j0k1l2m3n4
Create Date: 2026-09-22 15:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'j0k1l2m3n4o5'
down_revision: Union[str, None] = 'i9j0k1l2m3n4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "transfers" not in tables:
        op.create_table(
            "transfers",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False),
            sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False),
            sa.Column("admission_id", sa.Integer(), sa.ForeignKey("admissions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source_ward_id", sa.Integer(), sa.ForeignKey("wards.id", ondelete="CASCADE"), nullable=False),
            sa.Column("destination_ward_id", sa.Integer(), sa.ForeignKey("wards.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source_bed_id", sa.Integer(), sa.ForeignKey("beds.id", ondelete="CASCADE"), nullable=False),
            sa.Column("destination_bed_id", sa.Integer(), sa.ForeignKey("beds.id", ondelete="CASCADE"), nullable=False),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("rejection_reason", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=50), nullable=False, server_default="REQUESTED"),
            sa.Column("requested_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("approved_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("rejected_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("completed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("requested_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("approved_at", sa.DateTime(), nullable=True),
            sa.Column("rejected_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_transfers_id", "transfers", ["id"])
        op.create_index("ix_transfers_hospital_id", "transfers", ["hospital_id"])
        op.create_index("ix_transfers_patient_id", "transfers", ["patient_id"])
        op.create_index("ix_transfers_admission_id", "transfers", ["admission_id"])
        op.create_index("ix_transfers_source_ward_id", "transfers", ["source_ward_id"])
        op.create_index("ix_transfers_destination_ward_id", "transfers", ["destination_ward_id"])
        op.create_index("ix_transfers_source_bed_id", "transfers", ["source_bed_id"])
        op.create_index("ix_transfers_destination_bed_id", "transfers", ["destination_bed_id"])
        op.create_index("ix_transfers_status", "transfers", ["status"])


def downgrade() -> None:
    op.drop_table("transfers")
