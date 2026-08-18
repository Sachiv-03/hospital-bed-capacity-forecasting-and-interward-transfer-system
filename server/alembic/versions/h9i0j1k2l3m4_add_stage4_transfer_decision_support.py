"""add_stage4_transfer_decision_support

Revision ID: h9i0j1k2l3m4
Revises: g8h9i0j1k2l3
Create Date: 2026-08-18 14:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'h9i0j1k2l3m4'
down_revision: Union[str, None] = 'g8h9i0j1k2l3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    # 1. ward_transfer_rules
    if "ward_transfer_rules" not in tables:
        op.create_table(
            "ward_transfer_rules",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source_ward_id", sa.Integer(), sa.ForeignKey("wards.id", ondelete="CASCADE"), nullable=True),
            sa.Column("destination_ward_id", sa.Integer(), sa.ForeignKey("wards.id", ondelete="CASCADE"), nullable=True),
            sa.Column("source_ward_type", sa.String(length=50), nullable=True),
            sa.Column("destination_ward_type", sa.String(length=50), nullable=True),
            sa.Column("allowed", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("priority", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("minimum_available_beds", sa.Integer(), nullable=False, server_default="2"),
            sa.Column("maximum_destination_occupancy", sa.Float(), nullable=False, server_default="85.0"),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_ward_transfer_rules_id", "ward_transfer_rules", ["id"])
        op.create_index("ix_ward_transfer_rules_hospital_id", "ward_transfer_rules", ["hospital_id"])
        op.create_index("ix_ward_transfer_rules_source_ward_id", "ward_transfer_rules", ["source_ward_id"])
        op.create_index("ix_ward_transfer_rules_destination_ward_id", "ward_transfer_rules", ["destination_ward_id"])

    # 2. transfer_recommendations
    if "transfer_recommendations" not in tables:
        op.create_table(
            "transfer_recommendations",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source_ward_id", sa.Integer(), sa.ForeignKey("wards.id", ondelete="CASCADE"), nullable=False),
            sa.Column("destination_ward_id", sa.Integer(), sa.ForeignKey("wards.id", ondelete="CASCADE"), nullable=False),
            sa.Column("recommended_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("source_current_occupancy", sa.Float(), nullable=False),
            sa.Column("source_predicted_occupancy", sa.Float(), nullable=False),
            sa.Column("destination_current_occupancy", sa.Float(), nullable=False),
            sa.Column("destination_predicted_occupancy", sa.Float(), nullable=False),
            sa.Column("available_beds", sa.Integer(), nullable=False),
            sa.Column("safe_transfer_capacity", sa.Integer(), nullable=False),
            sa.Column("recommended_transfer_count", sa.Integer(), nullable=False),
            sa.Column("priority_score", sa.Float(), nullable=False),
            sa.Column("priority_level", sa.String(length=20), nullable=False, server_default="MEDIUM"),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING"),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("warnings", sa.JSON(), nullable=True),
            sa.Column("score_breakdown", sa.JSON(), nullable=True),
            sa.Column("forecast_horizon_days", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("forecast_confidence_lower", sa.Float(), nullable=True),
            sa.Column("forecast_confidence_upper", sa.Float(), nullable=True),
            sa.Column("approved_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("approved_at", sa.DateTime(), nullable=True),
            sa.Column("rejected_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("rejected_at", sa.DateTime(), nullable=True),
            sa.Column("rejection_reason", sa.Text(), nullable=True),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_transfer_recommendations_id", "transfer_recommendations", ["id"])
        op.create_index("ix_transfer_recommendations_hospital_id", "transfer_recommendations", ["hospital_id"])
        op.create_index("ix_transfer_recommendations_source_ward_id", "transfer_recommendations", ["source_ward_id"])
        op.create_index("ix_transfer_recommendations_destination_ward_id", "transfer_recommendations", ["destination_ward_id"])
        op.create_index("ix_transfer_recommendations_status", "transfer_recommendations", ["status"])

    # 3. audit_logs
    if "audit_logs" not in tables:
        op.create_table(
            "audit_logs",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("action", sa.String(length=100), nullable=False),
            sa.Column("resource_type", sa.String(length=50), nullable=False),
            sa.Column("resource_id", sa.String(length=50), nullable=True),
            sa.Column("timestamp", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
        )
        op.create_index("ix_audit_logs_id", "audit_logs", ["id"])
        op.create_index("ix_audit_logs_hospital_id", "audit_logs", ["hospital_id"])
        op.create_index("ix_audit_logs_action", "audit_logs", ["action"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("transfer_recommendations")
    op.drop_table("ward_transfer_rules")
