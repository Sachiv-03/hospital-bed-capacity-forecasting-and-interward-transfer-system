"""add_patients_and_admissions

Revision ID: i9j0k1l2m3n4
Revises: h9i0j1k2l3m4
Create Date: 2026-08-25 09:50:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'i9j0k1l2m3n4'
down_revision: Union[str, None] = 'h9i0j1k2l3m4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    # 1. patients
    if "patients" not in tables:
        op.create_table(
            "patients",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False),
            sa.Column("patient_identifier", sa.String(length=100), nullable=False),
            sa.Column("first_name", sa.String(length=100), nullable=False),
            sa.Column("last_name", sa.String(length=100), nullable=False),
            sa.Column("date_of_birth", sa.Date(), nullable=False),
            sa.Column("gender", sa.String(length=50), nullable=False, server_default="OTHER"),
            sa.Column("phone", sa.String(length=50), nullable=True),
            sa.Column("email", sa.String(length=255), nullable=True),
            sa.Column("address", sa.Text(), nullable=True),
            sa.Column("emergency_contact_name", sa.String(length=255), nullable=True),
            sa.Column("emergency_contact_phone", sa.String(length=50), nullable=True),
            sa.Column("status", sa.String(length=50), nullable=False, server_default="ACTIVE"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("hospital_id", "patient_identifier", name="uq_patient_hospital_identifier"),
        )
        op.create_index("ix_patients_id", "patients", ["id"])
        op.create_index("ix_patients_hospital_id", "patients", ["hospital_id"])
        op.create_index("ix_patients_patient_identifier", "patients", ["patient_identifier"])
        op.create_index("ix_patients_first_name", "patients", ["first_name"])
        op.create_index("ix_patients_last_name", "patients", ["last_name"])
        op.create_index("ix_patients_gender", "patients", ["gender"])
        op.create_index("ix_patients_status", "patients", ["status"])

    # 2. admissions
    if "admissions" not in tables:
        op.create_table(
            "admissions",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False),
            sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False),
            sa.Column("ward_id", sa.Integer(), sa.ForeignKey("wards.id", ondelete="CASCADE"), nullable=False),
            sa.Column("bed_id", sa.Integer(), sa.ForeignKey("beds.id", ondelete="CASCADE"), nullable=False),
            sa.Column("admission_number", sa.String(length=100), nullable=False),
            sa.Column("admission_date", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("discharge_date", sa.DateTime(), nullable=True),
            sa.Column("status", sa.String(length=50), nullable=False, server_default="ADMITTED"),
            sa.Column("admission_reason", sa.Text(), nullable=True),
            sa.Column("discharge_notes", sa.Text(), nullable=True),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("discharged_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("admission_number", name="uq_admission_number"),
        )
        op.create_index("ix_admissions_id", "admissions", ["id"])
        op.create_index("ix_admissions_hospital_id", "admissions", ["hospital_id"])
        op.create_index("ix_admissions_patient_id", "admissions", ["patient_id"])
        op.create_index("ix_admissions_ward_id", "admissions", ["ward_id"])
        op.create_index("ix_admissions_bed_id", "admissions", ["bed_id"])
        op.create_index("ix_admissions_admission_number", "admissions", ["admission_number"])
        op.create_index("ix_admissions_admission_date", "admissions", ["admission_date"])
        op.create_index("ix_admissions_discharge_date", "admissions", ["discharge_date"])
        op.create_index("ix_admissions_status", "admissions", ["status"])
        op.create_index("ix_admissions_created_by", "admissions", ["created_by"])
        op.create_index("ix_admissions_discharged_by", "admissions", ["discharged_by"])


def downgrade() -> None:
    op.drop_table("admissions")
    op.drop_table("patients")
